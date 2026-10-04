# frozen_string_literal: true

require 'net/http'
require 'uri'
require 'json'
require 'logger'

module Core
  class ThreadPool
    attr_reader :size, :queue_capacity

    def initialize(size:, queue_capacity:)
      @size = size
      @queue_capacity = queue_capacity
      @work_queue = SizedQueue.new(queue_capacity)
      @workers = []
      @shutdown_flag = false
      @mutex = Mutex.new
      @logger = Logger.new($stdout)
      @logger.formatter = proc do |severity, datetime, _progname, msg|
        "[#{datetime.strftime('%Y-%m-%d %H:%M:%S.%L')}] [#{severity}] [TID-#{Thread.current.object_id}] #{msg}\n"
      end

      spawn_workers!
    end

    def post(payload, &block)
      @mutex.synchronize do
        raise 'ThreadPool is shutdown, rejecting new work' if @shutdown_flag
      end

      # Blocking push: jika antrean mencapai @queue_capacity, caller thread akan disuspend
      # Ini mencegah buffer-bloat / memory exhaustion
      @work_queue.push([payload, block])
      true
    end

    def shutdown
      @mutex.synchronize do
        return if @shutdown_flag
        @logger.info("Menerima sinyal shutdown. Menghentikan worker...")
        @shutdown_flag = true
      end

      # Mengirim 'POISON PILL' sejumlah worker untuk memutus loop worker secara anggun
      @size.times do
        @work_queue.push(:POISON_PILL)
      end

      @workers.each(&:join)
      @logger.info("Semua worker berhasil dimatikan secara aman.")
    end

    private

    def spawn_workers!
      @size.times do |i|
        @workers << Thread.new do
          Thread.current.name = "ThreadPool-Worker-#{i + 1}"
          loop do
            work = @work_queue.pop

            break if work == :POISON_PILL

            payload, task = work
            execute_task(payload, task)
          end
        rescue Exception => e
          # Tangkal fatal error di luar task execution agar thread pool tidak bocor
          @logger.fatal("FATAL: Worker thread anjlok akibat: #{e.class}: #{e.message}")
        end
      end
    end

    def execute_task(payload, task)
      task.call(payload)
    rescue StandardError => e
      @logger.error("Kegagalan task pada payload #{payload}: #{e.class} - #{e.message}")
      @logger.debug(e.backtrace.join("\n"))
    end
  end
end

# === Skenario Penggunaan Nyata: Batch Verification Worker ===

class TransactionAuditor
  def initialize
    @pool = Core::ThreadPool.new(size: 5, queue_capacity: 10)
    @metrics_mutex = Mutex.new
    @processed_count = 0
    @failure_count = 0
  end

  def run_audit(transactions)
    puts "Mulai menjadwalkan #{transactions.size} transaksi..."

    transactions.each do |tx|
      # Backpressure bekerja di sini: jika antrean penuh, caller ditahan
      @pool.post(tx) do |data|
        process_transaction(data)
      end
    end

    # Graceful shutdown saat selesai
    @pool.shutdown
    print_metrics
  end

  private

  def process_transaction(tx)
    # Simulasi I/O HTTP Request ke Payment Gateway API
    # MRI melepaskan GVL selama operasi sleep ini!
    latency = rand(0.05..0.2)
    sleep(latency)

    if rand < 0.1 # Simulasi kegagalan 10%
      raise StandardError, "Network Gateway Timeout (HTTP 504) untuk TX_ID: #{tx[:id]}"
    end

    record_metric(success: true)
  rescue StandardError => e
    record_metric(success: false)
    raise e # Re-raise agar logger internal ThreadPool menangkap error ini
  end

  def record_metric(success:)
    @metrics_mutex.synchronize do
      if success
        @processed_count += 1
      else
        @failure_count += 1
      end
    end
  end

  def print_metrics
    puts "\n=== LAPORAN EKSEKUSI AUDIT ==="
    puts "Total Sukses : #{@processed_count}"
    puts "Total Gagal  : #{@failure_count}"
    puts "Total Diproses: #{@processed_count + @failure_count}"
  end
end

# Eksekusi Demo
dummy_transactions = (1..50).map { |i| { id: "TX-#{1000 + i}", amount: rand(10..500) } }
auditor = TransactionAuditor.new
auditor.run_audit(dummy_transactions)

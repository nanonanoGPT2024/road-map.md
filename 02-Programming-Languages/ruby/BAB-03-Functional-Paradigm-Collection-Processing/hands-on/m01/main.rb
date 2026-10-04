# frozen_string_literal: true

require 'date'
require 'bigdecimal'
require 'bigdecimal/util'
require 'stringio'

# Immutable Value Object mewakili domain transaksi
class TransactionRecord
  attr_reader :id, :account_id, :amount, :currency, :timestamp, :status

  def initialize(id:, account_id:, amount:, currency:, timestamp:, status:)
    @id = id.freeze
    @account_id = account_id.freeze
    @amount = amount.freeze       # Menggunakan BigDecimal untuk presisi finansial
    @currency = currency.freeze
    @timestamp = timestamp.freeze
    @status = status.freeze
    freeze # Mengunci instance TransactionRecord secara rekursif
  end

  # Factory method murni untuk mengurai baris CSV
  def self.parse_csv_line(line)
    parts = line.strip.split(',')
    return nil if parts.size != 6

    new(
      id: parts[0],
      account_id: parts[1],
      amount: parts[2].to_d,
      currency: parts[3],
      timestamp: Time.at(Integer(parts[4])).utc,
      status: parts[5].to_sym
    )
  rescue ArgumentError, TypeError
    nil # Membuang parsing error tanpa melempar runtime interrupt
  end
end

# Modul fungsional murni untuk audit ledger
module LedgerProcessor
  # Tabel kurs konversi mata uang (Immutable Reference)
  EXCHANGE_RATES = {
    'USD' => '1.0'.to_d,
    'EUR' => '1.08'.to_d,
    'IDR' => '0.000064'.to_d
  }.freeze

  # Higher-Order Function: Filter Builder
  def self.build_status_filter(allowed_status)
    ->(tx) { tx.status == allowed_status }
  end

  # Pure Transformation Function
  def self.normalize_to_usd(tx)
    rate = EXCHANGE_RATES.fetch(tx.currency) do
      raise KeyError, "Mata uang tidak didukung: #{tx.currency}"
    end

    TransactionRecord.new(
      id: tx.id,
      account_id: tx.account_id,
      amount: (tx.amount * rate).round(4),
      currency: 'USD',
      timestamp: tx.timestamp,
      status: tx.status
    )
  end

  # Engine Pemrosesan Stream
  def self.process_stream(io_stream)
    is_settled = build_status_filter(:SETTLED)
    converter  = method(:normalize_to_usd).to_proc

    # Menggunakan Lazy Enumerator untuk mencegah pemuatan seluruh data ke RAM
    io_stream
      .each_line
      .lazy
      .map { |line| TransactionRecord.parse_csv_line(line) }
      .reject(&:nil?)
      .select(&is_settled)
      .map(&converter)
  end

  # Pure Aggregator menggunakan functional reduce
  def self.aggregate_metrics(processed_lazy_stream)
    initial_acc = { total_volume_usd: '0.0'.to_d, count: 0, by_account: {} }.freeze

    processed_lazy_stream.reduce(initial_acc) do |acc, tx|
      current_account_total = acc[:by_account].fetch(tx.account_id, '0.0'.to_d)

      # Mengembalikan hash baru sepenuhnya tanpa memutasi acc sebelumnya
      {
        total_volume_usd: acc[:total_volume_usd] + tx.amount,
        count: acc[:count] + 1,
        by_account: acc[:by_account].merge(tx.account_id => current_account_total + tx.amount).freeze
      }.freeze
    end
  end
end

# ==========================================
# SIMULASI PRODUKSI STREAMING BESAR
# ==========================================

# Mock dataset menyerupai input IO stream (cth: Socket atau File stream)
raw_stream_data = <<~CSV
  TXN-001,ACC-A,100.50,USD,1704067200,SETTLED
  TXN-002,ACC-B,50.00,EUR,1704067205,PENDING
  TXN-003,ACC-A,2000000.00,IDR,1704067210,SETTLED
  TXN-INVALID,DATA,ERROR,FORMAT
  TXN-004,ACC-C,75.25,EUR,1704067215,SETTLED
  TXN-005,ACC-B,300.00,USD,1704067220,FAILED
  TXN-006,ACC-A,25.00,USD,1704067225,SETTLED
CSV

io_source = StringIO.new(raw_stream_data)

# Eksekusi pipeline fungsional
puts "Memulai pemrosesan stream data..."
lazy_pipeline = LedgerProcessor.process_stream(io_source)

# Agregasi metrik dihitung dalam 1 siklus evaluasi (single terminal operation)
metrics = LedgerProcessor.aggregate_metrics(lazy_pipeline)

puts "\n=== LAPORAN AUDIT LEDGER (PROCESSED) ==="
puts "Total Transaksi Valid (SETTLED) : #{metrics[:count]}"
puts "Total Volume Normalisasi (USD)  : #{metrics[:total_volume_usd].to_s('F')}"
puts "Breakdown Volume per Akun:"
metrics[:by_account].each do |account, volume|
  puts "  - Akun #{account}: $#{volume.to_s('F')} USD"
end

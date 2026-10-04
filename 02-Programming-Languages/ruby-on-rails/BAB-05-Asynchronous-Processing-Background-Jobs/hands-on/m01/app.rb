# app/workers/process_order_checkout_worker.rb
class ProcessOrderCheckoutWorker
  include Sidekiq::Job

  # Konfigurasi spesifik Sidekiq
  sidekiq_options queue: :critical, 
                  retry: 5, 
                  backtrace: true

  # Custom backoff logic
  sidekiq_retry_in do |count, exception|
    case exception
    when RateLimitExceededError
      # Tunggu 2 detik secara linear jika terbentur rate limit
      2 + (count * 2)
    else
      # Eksponensial default untuk transient network errors
      (count ** 4) + 15
    end
  end

  def perform(order_id, idempotency_key)
    # 1. Database Lock & Idempotency Check
    order = Order.find(order_id)
    
    # Memastikan tidak terjadi double execution
    return if already_processed?(idempotency_key)

    # 2. Redis Distributed Rate Limiting untuk eksternal API
    RedisRateLimiter.throttle!("erp_api_rate_limit", limit: 5, period: 1)

    # 3. Transaksi Internal untuk Eksekusi dan Audit Trail
    ActiveRecord::Base.transaction do
      # Set status pemrosesan
      order.lock! # Pessimistic locking baris database
      return if order.processed?

      # Generasi Invoice PDF (I/O & CPU intensif)
      pdf_url = InvoiceGeneratorService.new(order).generate_and_upload!

      # Integrasi Third Party (ERP Sync)
      ErpSyncService.new(order, pdf_url).broadcast!

      # Update status Order dan simpan Idempotency Key
      order.update!(
        status: :processed,
        invoice_url: pdf_url,
        processed_at: Time.current
      )

      # Mark idempotency key sebagai selesai dengan TTL 24 jam
      mark_processed(idempotency_key)
    end

    # 4. Enqueue follow-up job untuk notifikasi email
    SendInvoiceEmailWorker.perform_async(order.id)

  rescue RateLimitExceededError => e
    # Log warning dan trigger retry mekanisme Sidekiq
    Sidekiq.logger.warn("Throttled by external ERP for Order ##{order_id}. Retrying... Err: #{e.message}")
    raise e
  rescue ActiveRecord::RecordNotFound => e
    Sidekiq.logger.error("Non-recoverable error: Order ##{order_id} not found. Aborting job.")
    # Tidak me-raise ulang error agar job tidak di-retry (poison pill prevention)
  end

  private

  def already_processed?(key)
    Sidekiq.redis { |r| r.exists?("idempotency:#{key}") }
  end

  def mark_processed(key)
    Sidekiq.redis { |r| r.set("idempotency:#{key}", "COMPLETED", ex: 86_400) }
  end
end

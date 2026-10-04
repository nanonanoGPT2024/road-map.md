class OrderBookBroadcastJob < ApplicationJob
  queue_as :realtime_broadcasting
  
  # Pastikan background job tidak menumpuk di worker queue
  discard_on ActiveJob::DeserializationError

  def perform(market_symbol)
    # Mengambil aggregated state dari Redis Cache (Memory-to-Memory, NO DB QUERY)
    cache_key = "market_data:#{market_symbol}:snapshot"
    snapshot = Rails.cache.fetch(cache_key, expires_in: 5.seconds) do
      fetch_order_book_snapshot(market_symbol)
    end

    # Render Turbo Stream fragment sekali saja untuk semua client
    rendered_stream = ApplicationController.render(
      turbo_stream: Turbo::StreamsTagBuilder.new(ActionView::Base.empty).replace(
        "order_book_#{market_symbol.downcase}",
        partial: "markets/order_book_table",
        locals: { order_book: snapshot }
      )
    )

    # Sebarkan ke seluruh subscriber yang terhubung ke symbol ini
    ActionCable.server.broadcast("order_book:#{market_symbol}", rendered_stream)
  end

  private

  def fetch_order_book_snapshot(symbol)
    # Query database yang dioptimasi via Read-Replica
    Order.where(symbol: symbol)
         .order(created_at: :desc)
         .limit(25)
         .pluck(:id, :price, :amount, :order_type, :created_at)
  end
end

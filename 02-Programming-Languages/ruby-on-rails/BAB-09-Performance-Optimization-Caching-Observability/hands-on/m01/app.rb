# app/controllers/catalog_controller.rb
class CatalogController < ApplicationController
  def show
    @category = Category.find(params[:id])

    # 1. HTTP CONDITIONAL CACHING (ETag / 304 Not Modified)
    # Jika browser/CDN memiliki ETag yang cocok dengan category.updated_at, eksekusi berhenti di sini
    return if stale?(etag: @category, last_modified: @category.updated_at, public: true)

    # 2. QUERY OPTIMIZATION MENGGUNAKAN PRELOAD DENGAN KONDISI STRICT
    @products = @category.products
                         .active
                         .strict_loading
                         .preload(:variants)
                         .order(created_at: :desc)
                         .limit(50)

    respond_to do |format|
      format.html
      format.json { render json: cached_catalog_json }
    end
  end

  private

  def cached_catalog_json
    # Low-level cache untuk response JSON
    cache_key = "category_json:#{@category.id}:#{@category.updated_at.to_fs(:usec)}"
    
    Rails.cache.fetch(cache_key, expires_in: 1.hour, race_condition_ttl: 10.seconds) do
      @products.map do |product|
        {
          id: product.id,
          name: product.name,
          rating: product.average_rating,
          review_count: product.reviews_count,
          variants: product.variants.map { |v| { id: v.id, sku: v.sku, price: v.price.to_s } }
        }
      end.to_json
    end
  end
end

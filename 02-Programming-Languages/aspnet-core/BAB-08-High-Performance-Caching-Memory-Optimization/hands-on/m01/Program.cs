using System;
using System.Buffers;
using System.IO;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using HighPerformance.Engine.Models;
using Microsoft.Extensions.Caching.Distributed;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Logging;

namespace HighPerformance.Engine.Services;

public sealed class ProductCatalogService
{
    private readonly IMemoryCache _l1Cache;
    private readonly IDistributedCache _l2Cache;
    private readonly ILogger<ProductCatalogService> _logger;
    
    // Key-based Semaphore Pool untuk mencegah Thundering Herd per produk
    private static readonly System.Collections.Concurrent.ConcurrentDictionary<string, SemaphoreSlim> KeyLocks = new();

    public ProductCatalogService(
        IMemoryCache l1Cache, 
        IDistributedCache l2Cache, 
        ILogger<ProductCatalogService> logger)
    {
        _l1Cache = l1Cache;
        _l2Cache = l2Cache;
        _logger = logger;
    }

    public async ValueTask<ProductInventoryPrice?> GetProductDetailsAsync(string productId, CancellationToken ct)
    {
        string cacheKey = $"prod:{productId}";

        // --- LAYER 1: FAST IN-MEMORY CACHE (Zero Network overhead) ---
        if (_l1Cache.TryGetValue(cacheKey, out ProductInventoryPrice? localItem))
        {
            return localItem;
        }

        // --- LAYER 2: DISTRIBUTED CACHE (Redis) ---
        // Menggunakan pooling untuk pembacaan payload byte Redis
        byte[]? l2Bytes = await _l2Cache.GetAsync(cacheKey, ct).ConfigureAwait(false);
        if (l2Bytes != null)
        {
            // Zero-string-allocation deserialization langsung dari byte buffer
            var productFromL2 = DeserializeFromUtf8(l2Bytes);
            
            // Rehydrate L1 Cache dengan Sliding Window pendek
            _l1Cache.Set(cacheKey, productFromL2, new MemoryCacheEntryOptions
            {
                AbsoluteExpirationRelativeToNow = TimeSpan.FromSeconds(30),
                Size = 1 // Enforce size-tracking
            });

            return productFromL2;
        }

        // --- LAYER 3: ATOMIC DATABASE ACCESS (Mitigasi Cache Stampede) ---
        SemaphoreSlim mutex = KeyLocks.GetOrAdd(cacheKey, _ => new SemaphoreSlim(1, 1));
        await mutex.WaitAsync(ct).ConfigureAwait(false);

        try
        {
            // Double-Check Locking pattern setelah acquire mutex
            if (_l1Cache.TryGetValue(cacheKey, out localItem))
            {
                return localItem;
            }

            // Simulasi Query Database
            ProductInventoryPrice? dbProduct = await FetchFromDatabaseSlowAsync(productId, ct).ConfigureAwait(false);
            if (dbProduct == null)
            {
                return null;
            }

            // Simpan ke L1
            _l1Cache.Set(cacheKey, dbProduct, new MemoryCacheEntryOptions
            {
                AbsoluteExpirationRelativeToNow = TimeSpan.FromSeconds(30),
                Size = 1
            });

            // Serialisasi via Source Generator & simpan ke L2 Redis
            byte[] serialized = SerializeToUtf8Bytes(dbProduct);
            await _l2Cache.SetAsync(
                cacheKey, 
                serialized, 
                new DistributedCacheEntryOptions { AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(10) }, 
                ct
            ).ConfigureAwait(false);

            return dbProduct;
        }
        finally
        {
            mutex.Release();
            // Pembersihan agresif jika tidak ada thread lain yang antre
            if (mutex.CurrentCount == 1)
            {
                KeyLocks.TryRemove(cacheKey, out _);
            }
        }
    }

    private static byte[] SerializeToUtf8Bytes(ProductInventoryPrice data)
    {
        return JsonSerializer.SerializeToUtf8Bytes(data, InventoryJsonContext.Default.ProductInventoryPrice);
    }

    private static ProductInventoryPrice? DeserializeFromUtf8(byte[] bytes)
    {
        var reader = new Utf8JsonReader(bytes);
        return JsonSerializer.Deserialize(ref reader, InventoryJsonContext.Default.ProductInventoryPrice);
    }

    private async Task<ProductInventoryPrice?> FetchFromDatabaseSlowAsync(string productId, CancellationToken ct)
    {
        _logger.LogInformation("DOWNSTREAM HIT: Querying Primary Database for {ProductId}", productId);
        await Task.Delay(150, ct).ConfigureAwait(false); // Simulasi latensi I/O DB
        
        return new ProductInventoryPrice
        {
            ProductId = productId,
            BasePrice = 1250000m,
            DiscountPercentage = 15m,
            AvailableStock = 42
        };
    }
}

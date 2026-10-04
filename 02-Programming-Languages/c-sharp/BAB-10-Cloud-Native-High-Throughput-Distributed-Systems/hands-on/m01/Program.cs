using System.Text.Json;
using System.Threading.Channels;
using System.Threading.RateLimiting;
using Microsoft.AspNetCore.Mvc;
using Polly;
using Polly.CircuitBreaker;
using StackExchange.Redis;

var builder = WebApplication.CreateBuilder(args);

// 1. Registrasi StackExchange.Redis
builder.Services.AddSingleton<IConnectionMultiplexer>(_ => 
    ConnectionMultiplexer.Connect("localhost:6379,abortConnect=false"));

// 2. Registrasi Channel In-Memory Bounded Buffer
builder.Services.AddSingleton(Channel.CreateBounded<OrderCreatedEvent>(new BoundedChannelOptions(50_000)
{
    FullMode = BoundedChannelFullMode.Wait,
    SingleReader = false,
    SingleWriter = false
}));

// 3. Registrasi Polly v8 Resilience Pipeline
builder.Services.AddSingleton<ResiliencePipeline>(sp =>
{
    return new ResiliencePipelineBuilder()
        .AddRateLimiter(new SlidingWindowRateLimiter(new SlidingWindowRateLimiterOptions
        {
            PermitLimit = 100_000,
            Window = TimeSpan.FromSeconds(1),
            SegmentsPerWindow = 4,
            QueueLimit = 5_000
        }))
        .AddCircuitBreaker(new HttpCircuitBreakerStrategyOptions
        {
            FailureRatio = 0.5,
            SamplingDuration = TimeSpan.FromSeconds(10),
            MinimumThroughput = 100,
            BreakDuration = TimeSpan.FromSeconds(15)
        })
        .AddTimeout(TimeSpan.FromMilliseconds(500))
        .Build();
});

// 4. Registrasi Background Outbox Dispatcher
builder.Services.AddHostedService<OutboxDispatcherWorker>();

var app = builder.Build();

// Endpoint Ingestion dengan Idempotensi & Resilience Pipeline
app.MapPost("/api/v1/orders", async (
    [FromBody] CreateOrderRequest request,
    [FromHeader(Name = "X-Idempotency-Key")] string? idempotencyKey,
    [FromServices] IConnectionMultiplexer redis,
    [FromServices] Channel<OrderCreatedEvent> channel,
    [FromServices] ResiliencePipeline resiliencePipeline,
    CancellationToken ct) =>
{
    if (string.IsNullOrWhiteSpace(idempotencyKey))
    {
        return Results.BadRequest(new { Error = "Header 'X-Idempotency-Key' wajib disertakan." });
    }

    var db = redis.GetDatabase();
    var redisKey = $"idempotency:order:{idempotencyKey}";

    // Eksekusi pipeline resilience untuk rate limiting & fail-fast
    try
    {
        return await resiliencePipeline.ExecuteAsync(async state =>
        {
            // Cek idempotensi atomik via Redis (SET NX dengan expiry 1 jam)
            bool acquired = await db.StringSetAsync(redisKey, "PENDING", TimeSpan.FromHours(1), When.NotExists);
            if (!acquired)
            {
                return Results.Conflict(new { Error = "Permintaan duplikat terdeteksi. Transaksi sedang atau telah diproses." });
            }

            var orderEvent = new OrderCreatedEvent(
                OrderId: Guid.NewGuid(),
                CustomerId: request.CustomerId,
                Amount: request.Amount,
                IdempotencyKey: idempotencyKey,
                CreatedAtUtc: DateTime.UtcNow
            );

            // Tulis ke bounded channel pipeline (menerapkan backpressure non-blocking)
            await channel.Writer.WriteAsync(orderEvent, state);

            return Results.Accepted($"/api/v1/orders/{orderEvent.OrderId}", new { orderEvent.OrderId, Status = "Enqueued" });
        }, ct);
    }
    catch (RateLimiterRejectedException)
    {
        return Results.StatusCode(StatusCodes.Status429TooManyRequests);
    }
    catch (BrokenCircuitException)
    {
        return Results.StatusCode(StatusCodes.Status503ServiceUnavailable);
    }
});

app.Run();

// ==========================================
// KONTRAK DATA & MODELS
// ==========================================
public sealed record CreateOrderRequest(Guid CustomerId, decimal Amount);

public sealed record OrderCreatedEvent(
    Guid OrderId,
    Guid CustomerId,
    decimal Amount,
    string IdempotencyKey,
    DateTime CreatedAtUtc
);

// ==========================================
// WORKER OUTBOX DENGAN BATCH BULK INSERT
// ==========================================
public sealed class OutboxDispatcherWorker : BackgroundService
{
    private readonly Channel<OrderCreatedEvent> _channel;
    private readonly ILogger<OutboxDispatcherWorker> _logger;
    private const int BatchSize = 1000;
    private readonly TimeSpan _drainTimeout = TimeSpan.FromMilliseconds(50);

    public OutboxDispatcherWorker(Channel<OrderCreatedEvent> channel, ILogger<OutboxDispatcherWorker> logger)
    {
        _channel = channel;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("Outbox Dispatcher Engine aktif.");
        var buffer = new List<OrderCreatedEvent>(BatchSize);

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                // Tarik pesan pertama dengan await untuk efisiensi CPU
                if (await _channel.Reader.WaitToReadAsync(stoppingToken))
                {
                    var timeoutCts = new CancellationTokenSource(_drainTimeout);
                    using var linkedCts = CancellationTokenSource.CreateLinkedTokenSource(stoppingToken, timeoutCts.Token);

                    try
                    {
                        while (buffer.Count < BatchSize && _channel.Reader.TryRead(out var orderEvent))
                        {
                            buffer.Add(orderEvent);
                        }
                    }
                    catch (OperationCanceledException) when (timeoutCts.IsCancellationRequested)
                    {
                        // Batas waktu drain interval tercapai, lanjutkan flush
                    }

                    if (buffer.Count > 0)
                    {
                        await PersistBatchToOutboxStorageAsync(buffer, stoppingToken);
                        buffer.Clear();
                    }
                }
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Kesalahan fatal pada pipeline pemrosesan batch outbox.");
                await Task.Delay(1000, stoppingToken); // Backoff jika ada failure storage
            }
        }

        // Tangani sisa data saat gracefully stopping
        while (_channel.Reader.TryRead(out var residual))
        {
            buffer.Add(residual);
        }
        if (buffer.Count > 0)
        {
            await PersistBatchToOutboxStorageAsync(buffer, CancellationToken.None);
        }
    }

    private async Task PersistBatchToOutboxStorageAsync(List<OrderCreatedEvent> events, CancellationToken ct)
    {
        // Di lingkungan nyata: Gunakan PostgreSQL NpgsqlBatch atau EF Core BulkExtensions
        // Contoh ini mensimulasikan persistensi bulk batch yang atomik
        _logger.LogInformation("Berhasil melakukan bulk write {Count} orders ke DB Outbox.", events.Count);
        await Task.Delay(5, ct); // Simulasi high-speed disk I/O
    }
}

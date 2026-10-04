// Program.cs
using System.Diagnostics;
using System.Diagnostics.Metrics;
using System.Net;
using System.Security.Cryptography;
using System.Text.Json;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.AspNetCore.Mvc;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;
using Polly;
using Polly.CircuitBreaker;
using Polly.Retry;
using Polly.Timeout;

var builder = WebApplication.CreateBuilder(args);

// ==========================================
// 1. OBSERVABILITY CONFIGURATION (OpenTelemetry)
// ==========================================
const string ServiceName = "Fintech.PaymentProcessor";
const string ServiceVersion = "1.0.0";

var paymentActivitySource = new ActivitySource(ServiceName, ServiceVersion);
var paymentMeter = new Meter(ServiceName, ServiceVersion);
var transactionCounter = paymentMeter.CreateCounter<long>("payments.processed.count", "transaksi", "Jumlah transaksi berhasil/gagal");
var transactionDurationHistogram = paymentMeter.CreateHistogram<double>("payments.processing.duration", "ms", "Durasi pemrosesan transaksi");

builder.Services.AddSingleton(paymentActivitySource);
builder.Services.AddSingleton(paymentMeter);

builder.Services.AddOpenTelemetry()
    .ConfigureResource(resource => resource
        .AddService(serviceName: ServiceName, serviceVersion: ServiceVersion)
        .AddAttributes([new KeyValuePair<string, object>("deployment.environment", builder.Environment.EnvironmentName)]))
    .WithTracing(tracing => tracing
        .AddSource(ServiceName)
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddOtlpExporter(opt => opt.Endpoint = new Uri(builder.Configuration["OTEL_EXPORTER_OTLP_ENDPOINT"] ?? "http://localhost:4317")))
    .WithMetrics(metrics => metrics
        .AddMeter(ServiceName)
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddOtlpExporter(opt => opt.Endpoint = new Uri(builder.Configuration["OTEL_EXPORTER_OTLP_ENDPOINT"] ?? "http://localhost:4317")));

// ==========================================
// 2. ENTERPRISE DATA PROTECTION (DPAPI)
// ==========================================
// Menyimpan key secara persisten ke direktori aman (di produksi: Azure Blob/Redis/Vault)
var keysFolder = Path.Combine(builder.Environment.ContentRootPath, "temp-keys");
builder.Services.AddDataProtection()
    .SetApplicationName("FintechEnterpriseSystem")
    .PersistKeysToFileSystem(new DirectoryInfo(keysFolder))
    .SetDefaultKeyLifetime(TimeSpan.FromDays(90));

// ==========================================
// 3. RESILIENCE PIPELINE DEFINITION (Polly v8)
// ==========================================
builder.Services.AddResiliencePipeline<string, HttpResponseMessage>("BankGatewayPipeline", pipelineBuilder =>
{
    pipelineBuilder.AddTimeout(new TimeoutStrategyOptions { Timeout = TimeSpan.FromSeconds(5) });
    pipelineBuilder.AddRetry(new RetryStrategyOptions<HttpResponseMessage>
    {
        ShouldHandle = new PredicateBuilder<HttpResponseMessage>()
            .Handle<HttpRequestException>()
            .Handle<TimeoutRejectedException>()
            .HandleResult(r => r.StatusCode == HttpStatusCode.RequestTimeout || (int)r.StatusCode >= 500),
        MaxRetryAttempts = 2,
        BackoffType = DelayBackoffType.Exponential,
        UseJitter = true,
        Delay = TimeSpan.FromMilliseconds(300)
    });
    pipelineBuilder.AddCircuitBreaker(new HttpCircuitBreakerStrategyOptions<HttpResponseMessage>
    {
        ShouldHandle = new PredicateBuilder<HttpResponseMessage>()
            .Handle<HttpRequestException>()
            .HandleResult(r => (int)r.StatusCode >= 500),
        FailureRatio = 0.4,
        MinimumThroughput = 5,
        SamplingDuration = TimeSpan.FromSeconds(20),
        BreakDuration = TimeSpan.FromSeconds(10)
    });
    pipelineBuilder.AddTimeout(new TimeoutStrategyOptions { Timeout = TimeSpan.FromSeconds(1.5) });
});

builder.Services.AddHttpClient("BankClient", client =>
{
    client.BaseAddress = new Uri("https://httpbin.org");
    client.DefaultRequestHeaders.Add("Accept", "application/json");
});

var app = builder.Build();

// ==========================================
// 4. BUSINESS LOGIC & ENDPOINTS
// ==========================================
app.MapPost("/api/v1/payments/process", async (
    [FromBody] PaymentRequest request,
    [FromServices] IHttpClientFactory httpClientFactory,
    [FromServices] ResiliencePipelineProvider<string> pipelineProvider,
    [FromServices] IDataProtectionProvider dataProtectionProvider,
    [FromServices] ActivitySource activitySource,
    CancellationToken cancellationToken) =>
{
    var stopwatch = Stopwatch.StartNew();
    using var activity = activitySource.StartActivity("ProcessPaymentTransaction", ActivityKind.Internal);
    
    // Proteksi Data Sensitif (PII Enkripsi)
    var protector = dataProtectionProvider.CreateProtector("Payment.CardDetails.v1");
    string encryptedCardNumber = protector.Protect(request.CardNumber);
    
    activity?.SetTag("payment.order_id", request.OrderId);
    activity?.SetTag("payment.encrypted_payload_len", encryptedCardNumber.Length);

    var client = httpClientFactory.CreateClient("BankClient");
    var pipeline = pipelineProvider.GetPipeline<HttpResponseMessage>("BankGatewayPipeline");

    try
    {
        // Eksekusi panggilan dengan Resilience Pipeline yang memantau token eksekusi
        var response = await pipeline.ExecuteAsync(async stateToken =>
        {
            var payload = new { OrderId = request.OrderId, Amount = request.Amount };
            return await client.PostAsJsonAsync("/status/200", payload, stateToken);
        }, cancellationToken);

        stopwatch.Stop();
        transactionCounter.Add(1, new KeyValuePair<string, object>("status", "success"));
        transactionDurationHistogram.Record(stopwatch.ElapsedMilliseconds, new KeyValuePair<string, object>("status", "success"));

        activity?.SetStatus(ActivityStatusCode.Ok);
        return Results.Ok(new PaymentResponse(true, "Transaction approved", Guid.NewGuid().ToString()));
    }
    catch (BrokenCircuitException ex)
    {
        stopwatch.Stop();
        transactionCounter.Add(1, new KeyValuePair<string, object>("status", "circuit_broken"));
        activity?.SetStatus(ActivityStatusCode.Error, "Downstream circuit open");
        activity?.RecordException(ex);

        return Results.StatusCode(StatusCodes.Status503ServiceUnavailable);
    }
    catch (Exception ex)
    {
        stopwatch.Stop();
        transactionCounter.Add(1, new KeyValuePair<string, object>("status", "error"));
        activity?.SetStatus(ActivityStatusCode.Error, ex.Message);
        activity?.RecordException(ex);

        return Results.StatusCode(StatusCodes.Status500InternalServerError);
    }
});

app.Run();

// ==========================================
// 5. CONTRACTS
// ==========================================
public record PaymentRequest(string OrderId, decimal Amount, string CardNumber);
public record PaymentResponse(bool IsSuccess, string Message, string TransactionId);

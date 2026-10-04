// Program.cs
using Enterprise.Observability.Logging;
using Enterprise.Observability.Telemetry;
using OpenTelemetry.Logs;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

var builder = WebApplication.CreateBuilder(args);

// Konfigurasi Resource Attributes yang mengidentifikasi instance service
var resourceBuilder = ResourceBuilder.CreateDefault()
    .AddService(serviceName: AppDiagnostics.ServiceName, serviceVersion: AppDiagnostics.ServiceVersion)
    .AddTelemetrySdk()
    .AddEnvironmentVariableDetector();

// 1. Logging Setup (OpenTelemetry Logging Bridge)
builder.Logging.ClearProviders();
builder.Logging.AddOpenTelemetry(loggingOptions =>
{
    loggingOptions.SetResourceBuilder(resourceBuilder);
    loggingOptions.IncludeFormattedMessage = true;
    loggingOptions.IncludeScopes = true;
    loggingOptions.AddOtlpExporter(otlpOptions =>
    {
        otlpOptions.Endpoint = new Uri(builder.Configuration["Otlp:Endpoint"] ?? "http://localhost:4317");
    });
});

// 2. Tracing & Metrics Setup
builder.Services.AddOpenTelemetry()
    .WithTracing(tracing =>
    {
        tracing
            .SetResourceBuilder(resourceBuilder)
            .AddSource(AppDiagnostics.ServiceName)
            .AddAspNetCoreInstrumentation(opts =>
            {
                opts.RecordException = true;
            })
            .AddHttpClientInstrumentation(opts =>
            {
                opts.RecordException = true;
            })
            .AddOtlpExporter(otlpOptions =>
            {
                otlpOptions.Endpoint = new Uri(builder.Configuration["Otlp:Endpoint"] ?? "http://localhost:4317");
            });
    })
    .WithMetrics(metrics =>
    {
        metrics
            .SetResourceBuilder(resourceBuilder)
            .AddMeter(AppDiagnostics.ServiceName)
            .AddAspNetCoreInstrumentation()
            .AddHttpClientInstrumentation()
            .AddRuntimeInstrumentation()
            .AddOtlpExporter(otlpOptions =>
            {
                otlpOptions.Endpoint = new Uri(builder.Configuration["Otlp:Endpoint"] ?? "http://localhost:4317");
            });
    });

var app = builder.Build();

app.MapPost("/orders", async (OrderRequest request, ILogger<Program> logger) =>
{
    var stopwatch = Stopwatch.StartNew();
    
    // Membuka Span tracing kustom
    using (var activity = AppDiagnostics.ActivitySource.StartActivity("ProcessOrderTransaction"))
    {
        activity?.SetTag("order.id", request.OrderId);
        activity?.SetTag("customer.id", request.CustomerId);

        logger.LogOrderInitialized(request.OrderId, request.CustomerId, request.TotalAmount);

        // Simulasi kalkulasi/eksekusi
        await Task.Delay(Random.Shared.Next(50, 150));

        // Update metrics
        AppDiagnostics.OrdersPlacedCounter.Add(1, new KeyValuePair<string, object?>("currency", request.Currency));
        
        stopwatch.Stop();
        AppDiagnostics.OrderProcessingDuration.Record(
            stopwatch.Elapsed.TotalMilliseconds, 
            new KeyValuePair<string, object?>("payment_method", request.PaymentMethod));

        activity?.SetStatus(ActivityStatusCode.Ok);
        
        return Results.Ok(new { Status = "Completed", Id = request.OrderId });
    }
});

app.Run();

public record OrderRequest(string OrderId, string CustomerId, decimal TotalAmount, string Currency, string PaymentMethod);

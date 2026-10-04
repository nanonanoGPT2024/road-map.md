// Program.cs
using System.Net;
using FluentValidation;
using Microsoft.AspNetCore.Diagnostics;
using Microsoft.AspNetCore.Mvc;
using Polly;
using Polly.CircuitBreaker;
using Polly.Retry;

var builder = WebApplication.CreateBuilder(args);

// 1. Registrasi Validasi
builder.Services.AddValidatorsFromAssemblyContaining<CreateOrderRequestValidator>();

// 2. Registrasi Global Error Handling (.NET 8 standard)
builder.Services.AddExceptionHandler<GlobalExceptionHandler>();
builder.Services.AddProblemDetails();

// 3. Registrasi Polly v8 Resilience Pipeline
builder.Services.AddResiliencePipeline("downstream-pipeline", pipelineBuilder =>
{
    pipelineBuilder
        .AddRetry(new RetryStrategyOptions
        {
            ShouldHandle = new PredicateBuilder().Handle<HttpRequestException>(),
            MaxRetryAttempts = 3,
            BackoffType = DelayBackoffType.Exponential,
            UseJitter = true,
            BaseDelay = TimeSpan.FromMilliseconds(200)
        })
        .AddCircuitBreaker(new CircuitBreakerStrategyOptions
        {
            ShouldHandle = new PredicateBuilder().Handle<HttpRequestException>(),
            FailureRatio = 0.5, // 50% failures
            SamplingDuration = TimeSpan.FromSeconds(10),
            MinimumThroughput = 8,
            BreakDuration = TimeSpan.FromSeconds(30)
        })
        .AddTimeout(TimeSpan.FromSeconds(3));
});

var app = builder.Build();

// Pipeline Middleware
app.UseExceptionHandler(); // Mengaktifkan ExceptionHandlerMiddleware
app.UseHttpsRedirection();

// 4. Minimal API Endpoint dengan Manual Validation Execution
app.MapPost("/api/orders", async (
    [FromBody] CreateOrderRequest request,
    IValidator<CreateOrderRequest> validator,
    ResiliencePipelineProvider<string> pipelineProvider,
    CancellationToken ct) =>
{
    var validationResult = await validator.ValidateAsync(request, ct);
    if (!validationResult.IsValid)
    {
        return Results.ValidationProblem(
            validationResult.ToDictionary(),
            statusCode: (int)HttpStatusCode.BadRequest,
            title: "Validation Failed");
    }

    var pipeline = pipelineProvider.GetPipeline("downstream-pipeline");

    // Eksekusi outbound call di dalam Resilience Pipeline
    var downstreamResult = await pipeline.ExecuteAsync(
        async token => await MockExternalPaymentGatewayCall(request, token),
        ct);

    return Results.Ok(new { OrderId = Guid.NewGuid(), Status = downstreamResult });
});

app.Run();

// --- MOCK SERVICE ---
static async ValueTask<string> MockExternalPaymentGatewayCall(CreateOrderRequest req, CancellationToken ct)
{
    // Simulasi transient error
    if (Random.Shared.Next(1, 4) == 1)
    {
        throw new HttpRequestException("Payment gateway unreachable (Transient Error).");
    }

    await Task.Delay(100, ct); // Network latency
    return "PAID_SUCCESSFULLY";
}

// --- DTO & VALIDATOR ---
public record CreateOrderRequest(string CustomerEmail, decimal Amount, string Currency);

public class CreateOrderRequestValidator : AbstractValidator<CreateOrderRequest>
{
    public CreateOrderRequestValidator()
    {
        RuleFor(x => x.CustomerEmail)
            .NotEmpty().WithMessage("CustomerEmail wajib diisi.")
            .EmailAddress().WithMessage("Format email tidak valid.");

        RuleFor(x => x.Amount)
            .GreaterThan(0).WithMessage("Amount harus lebih besar dari 0.");

        RuleFor(x => x.Currency)
            .NotEmpty()
            .Length(3).WithMessage("Currency harus 3 karakter ISO (e.g. IDR, USD).");
    }
}

// --- GLOBAL EXCEPTION HANDLER (.NET 8) ---
public sealed class GlobalExceptionHandler(ILogger<GlobalExceptionHandler> logger) : IExceptionHandler
{
    public async ValueTask<bool> TryHandleAsync(
        HttpContext httpContext,
        Exception exception,
        CancellationToken cancellationToken)
    {
        logger.LogError(exception, "Unhandled exception captured: {Message}", exception.Message);

        var (statusCode, title, detail) = exception switch
        {
            BrokenCircuitException => (
                (int)HttpStatusCode.ServiceUnavailable,
                "Circuit Breaker Triggered",
                "Layanan downstream sedang tidak tersedia sementara waktu. Silakan coba kembali nanti."),
            TimeoutException => (
                (int)HttpStatusCode.GatewayTimeout,
                "Network Timeout",
                "Downstream request melampaui batas waktu yang ditentukan."),
            _ => (
                (int)HttpStatusCode.InternalServerError,
                "Internal Server Error",
                "Terjadi kesalahan internal pada server.")
        };

        var problemDetails = new ProblemDetails
        {
            Status = statusCode,
            Title = title,
            Detail = detail,
            Instance = httpContext.Request.Path
        };

        problemDetails.Extensions.Add("traceId", httpContext.TraceIdentifier);

        httpContext.Response.StatusCode = statusCode;
        await httpContext.Response.WriteAsJsonAsync(problemDetails, cancellationToken);

        return true; // Exception berhasil ditangani
    }
}

// Program.cs
using System.Text.Json.Serialization;
using FluentValidation;
using Microsoft.AspNetCore.Http.HttpResults;

var builder = WebApplication.CreateSlimBuilder(args);

// Konfigurasi JSON Serializer untuk Native AOT & High Efficiency
builder.Services.ConfigureHttpJsonOptions(options =>
{
    options.SerializerOptions.TypeInfoResolverChain.Insert(0, AppJsonSerializerContext.Default);
});

// Registrasi Core Services
builder.Services.AddSingleton<ITransactionLedgerQueue, InMemoryHighThroughputQueue>();
builder.Services.AddValidatorsFromAssemblyContaining<CreateLedgerTransactionValidator>();

var app = builder.Build();

// Pemetaan Route Group
var v1Ledger = app.MapGroup("/api/v1/ledger-transactions")
                  .AddEndpointFilter<ValidationEndpointFilter<CreateLedgerTransactionRequest>>();

// Definisi Endpoint
v1Ledger.MapPost("/", async Task<Results<Accepted<TransactionReceipt>, BadRequest<string>>> (
    CreateLedgerTransactionRequest request,
    ITransactionLedgerQueue queue,
    CancellationToken ct) =>
{
    var transactionId = Guid.NewGuid();
    var entity = new LedgerEntry(
        transactionId, 
        request.SourceAccountId, 
        request.DestinationAccountId, 
        request.Amount, 
        request.Currency, 
        DateTimeOffset.UtcNow
    );

    await queue.EnqueueAsync(entity, ct);

    var receipt = new TransactionReceipt(transactionId, "QUEUED", DateTimeOffset.UtcNow);
    return TypedResults.Accepted($"/api/v1/ledger-transactions/{transactionId}", receipt);
});

app.Run();

// ==========================================
// KONTRAK DATA & VALIDASI
// ==========================================

public readonly record struct CreateLedgerTransactionRequest(
    Guid SourceAccountId,
    Guid DestinationAccountId,
    decimal Amount,
    string Currency
);

public readonly record struct TransactionReceipt(
    Guid TransactionId,
    string Status,
    DateTimeOffset Timestamp
);

public sealed class CreateLedgerTransactionValidator : AbstractValidator<CreateLedgerTransactionRequest>
{
    public CreateLedgerTransactionValidator()
    {
        RuleFor(x => x.SourceAccountId).NotEmpty();
        RuleFor(x => x.DestinationAccountId).NotEmpty();
        RuleFor(x => x.SourceAccountId).NotEqual(x => x.DestinationAccountId)
            .WithMessage("Source and Destination accounts must be distinct.");
        RuleFor(x => x.Amount).GreaterThan(0.0001m);
        RuleFor(x => x.Currency).NotEmpty().Length(3);
    }
}

// ==========================================
// ENTERPRISE ENDPOINT FILTER PIPELINE
// ==========================================

public sealed class ValidationEndpointFilter<T> : IEndpointFilter where T : class
{
    private readonly IValidator<T>? _validator;

    public ValidationEndpointFilter(IValidator<T>? validator = null)
    {
        _validator = validator;
    }

    public async ValueTask<object?> InvokeAsync(EndpointFilterInvocationContext context, EndpointFilterDelegate next)
    {
        if (_validator is null)
        {
            return await next(context);
        }

        // Cari argumen dalam konteks handler yang sesuai dengan generic T
        for (int i = 0; i < context.Arguments.Count; i++)
        {
            if (context.Arguments[i] is T validatableObject)
            {
                var validationResult = await _validator.ValidateAsync(validatableObject, context.HttpContext.RequestAborted);
                if (!validationResult.IsValid)
                {
                    return TypedResults.ValidationProblem(validationResult.ToDictionary());
                }
                break;
            }
        }

        return await next(context);
    }
}

// ==========================================
// INFRASTRUKTUR / MODEL DOMAIN
// ==========================================

public record LedgerEntry(
    Guid Id, 
    Guid SourceAccountId, 
    Guid DestinationAccountId, 
    decimal Amount, 
    string Currency, 
    DateTimeOffset CreatedAt
);

public interface ITransactionLedgerQueue
{
    ValueTask EnqueueAsync(LedgerEntry entry, CancellationToken ct);
}

public sealed class InMemoryHighThroughputQueue : ITransactionLedgerQueue
{
    public ValueTask EnqueueAsync(LedgerEntry entry, CancellationToken ct)
    {
        // Simulasi penulisan internal non-allocating ring buffer / Channel<T>
        return ValueTask.CompletedTask;
    }
}

// ==========================================
// NATIVE AOT JSON SERIALIZER CONTEXT
// ==========================================

[JsonSerializable(typeof(CreateLedgerTransactionRequest))]
[JsonSerializable(typeof(TransactionReceipt))]
[JsonSerializable(typeof(Microsoft.AspNetCore.Mvc.ValidationProblemDetails))]
public partial class AppJsonSerializerContext : JsonSerializerContext
{
}

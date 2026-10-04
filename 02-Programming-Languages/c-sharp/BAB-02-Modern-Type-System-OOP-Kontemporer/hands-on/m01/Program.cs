namespace ProductionBanking.Core;

using System;
using System.Diagnostics.CodeAnalysis;

// 1. Zero-Allocation Lightweight Structure for High-Throughput Transit Telemetry
public readonly record struct DeviceTelemetry(
    int TerminalId,
    long SequenceNumber,
    short ResponseCodeUtc)
{
    public bool IsTerminalHealthy => ResponseCodeUtc == 200;
}

// 2. Strongly Typed ID pattern eliminating primitive obsession
public readonly record struct AccountId(Guid Value)
{
    public static AccountId New() => new(Guid.NewGuid());
    public static AccountId Empty => new(Guid.Empty);
}

// 3. Domain Invariants via Positional Value Record
public sealed record CurrencyValue
{
    public decimal Amount { get; }
    public string IsoCode { get; }

    public CurrencyValue(decimal amount, string isoCode)
    {
        if (amount < 0)
            throw new ArgumentOutOfRangeException(nameof(amount), "Amount cannot be negative.");
        
        if (string.IsNullOrWhiteSpace(isoCode) || isoCode.Length != 3)
            throw new ArgumentException("Currency ISO code must be exactly 3 characters.", nameof(isoCode));

        Amount = amount;
        IsoCode = isoCode.ToUpperInvariant();
    }
}

// 4. Closed Discriminated Union for Domain Events
public abstract record PaymentOperation
{
    private PaymentOperation() { }

    public sealed record Authorize(
        AccountId SourceAccount, 
        AccountId DestinationAccount, 
        CurrencyValue Value, 
        DeviceTelemetry Telemetry) : PaymentOperation;

    public sealed record Reverse(
        Guid OriginalTransactionId, 
        string Reason) : PaymentOperation;

    public sealed record SettleBatch(
        Guid BatchId, 
        int TotalTransactions, 
        CurrencyValue BatchVolume) : PaymentOperation;
}

// 5. Result Pattern resolving "Billion-Dollar Mistake" without throwing exceptions for control flow
public abstract record ProcessResult<T>
{
    private ProcessResult() { }

    public sealed record Success(T Data) : ProcessResult<T>;
    public sealed record Failure(string ErrorMessage, int ErrorCode) : ProcessResult<T>;

    // Type guard utility for compiler flow analysis
    public bool TryGetSuccess([NotNullWhen(true)] out T? data)
    {
        if (this is Success success)
        {
            data = success.Data;
            return true;
        }

        data = default;
        return false;
    }
}

// 6. High-Performance Processing Pipeline Engine
public sealed class PaymentProcessorPipeline
{
    public ProcessResult<string> Process(PaymentOperation operation)
    {
        // Compiler guarantees all types derived from PaymentOperation are handled or matched
        return operation switch
        {
            // Case 1: Terminal un-healthy via nested struct property pattern
            PaymentOperation.Authorize { Telemetry: { IsTerminalHealthy: false } telemetry } =>
                new ProcessResult<string>.Failure(
                    $"Terminal ID {telemetry.TerminalId} failed health-check signal.", 
                    ErrorCode: 1001),

            // Case 2: Zero-amount transaction forbidden using relational pattern matching
            PaymentOperation.Authorize { Value: { Amount: 0 } } =>
                new ProcessResult<string>.Failure("Zero-value authorization is rejected.", ErrorCode: 1002),

            // Case 3: Valid Authorize transaction - functional processing
            PaymentOperation.Authorize auth =>
                ExecuteAuthorization(auth),

            // Case 4: Reversal logic via property pattern
            PaymentOperation.Reverse { Reason: "TIMEOUT" or "COMMUNICATION_ERROR" } rev =>
                new ProcessResult<string>.Success($"Reversal {rev.OriginalTransactionId} processed without penalty fees."),

            PaymentOperation.Reverse rev =>
                new ProcessResult<string>.Success($"Manual review scheduled for reversal: {rev.OriginalTransactionId}"),

            // Case 5: Batch settlement processing
            PaymentOperation.SettleBatch { TotalTransactions: <= 0 } =>
                new ProcessResult<string>.Failure("Empty batch cannot be settled.", ErrorCode: 1003),

            PaymentOperation.SettleBatch batch =>
                new ProcessResult<string>.Success($"Batch {batch.BatchId} locked. Processed Volume: {batch.BatchVolume.Amount} {batch.BatchVolume.IsoCode}")
        };
    }

    private static ProcessResult<string> ExecuteAuthorization(PaymentOperation.Authorize auth)
    {
        // Logic execution mock
        return new ProcessResult<string>.Success(
            $"AUTH_OK: Transferred {auth.Value.Amount} {auth.Value.IsoCode} from {auth.SourceAccount.Value} to {auth.DestinationAccount.Value}"
        );
    }
}

// 7. Verification Harness
public static class ProductionVerification
{
    public static void Main()
    {
        var pipeline = new PaymentProcessorPipeline();

        var telemetryOk = new DeviceTelemetry(TerminalId: 8820, SequenceNumber: 105432, ResponseCodeUtc: 200);
        var telemetryFaulty = telemetryOk with { ResponseCodeUtc = 503 };

        var source = AccountId.New();
        var dest = AccountId.New();
        var amount = new CurrencyValue(500.50m, "USD");

        PaymentOperation validAuth = new PaymentOperation.Authorize(source, dest, amount, telemetryOk);
        PaymentOperation faultyAuth = new PaymentOperation.Authorize(source, dest, amount, telemetryFaulty);

        // Process operations
        var res1 = pipeline.Process(validAuth);
        var res2 = pipeline.Process(faultyAuth);

        PrintResult("Valid Tx", res1);
        PrintResult("Faulty Tx", res2);
    }

    private static void PrintResult(string context, ProcessResult<string> result)
    {
        if (result.TryGetSuccess(out var successData))
        {
            Console.WriteLine($"[{context}] SUCCESS: {successData}");
        }
        else if (result is ProcessResult<string>.Failure failure)
        {
            Console.WriteLine($"[{context}] FAILURE: Code {failure.ErrorCode} - {failure.ErrorMessage}");
        }
    }
}

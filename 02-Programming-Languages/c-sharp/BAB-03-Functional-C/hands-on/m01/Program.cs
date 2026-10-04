using System;

namespace FunctionalCSharp.ProductionCase;

// Domain Errors as Sum Types
public abstract record DomainError(string Message)
{
    public sealed record ValidationError(string PropertyName, string Detail) 
        : DomainError($"Validation failed on '{PropertyName}': {Detail}");
    
    public sealed record InsufficientFunds(decimal AttemptedAmount, decimal CurrentBalance) 
        : DomainError($"Insufficient funds. Attempted: {AttemptedAmount}, Available: {CurrentBalance}");
    
    public sealed record AccountFrozen(string Reason) 
        : DomainError($"Account is frozen: {Reason}");
    
    public sealed record NetworkGatewayTimeout(string Gateway) 
        : DomainError($"Gateway timeout connecting to {Gateway}");
}

// Immutable Domain States
public readonly record struct CustomerAccount(Guid Id, decimal Balance, bool IsFrozen);
public readonly record struct PaymentRequest(Guid TransactionId, Guid AccountId, decimal Amount, string Currency);
public readonly record struct ProcessedPayment(Guid TransactionId, decimal DebitedAmount, decimal RemainingBalance, DateTime Timestamp);

// Functional Processing Pipeline
public static class PaymentEngine
{
    // Step 1: Pure Validation
    public static Result<PaymentRequest, DomainError> ValidateRequest(PaymentRequest request)
    {
        return request switch
        {
            { Amount: <= 0 } => Result<PaymentRequest, DomainError>.Failure(
                new DomainError.ValidationError(nameof(request.Amount), "Amount must be strictly positive.")),
            { Currency: not "IDR" } => Result<PaymentRequest, DomainError>.Failure(
                new DomainError.ValidationError(nameof(request.Currency), "Only 'IDR' currency is supported.")),
            _ => Result<PaymentRequest, DomainError>.Success(request)
        };
    }

    // Step 2: Pure Business Rule Check
    public static Result<(PaymentRequest Request, CustomerAccount Account), DomainError> VerifyAccountState(
        PaymentRequest request, 
        CustomerAccount account)
    {
        return account switch
        {
            { IsFrozen: true } => Result<(PaymentRequest, CustomerAccount), DomainError>.Failure(
                new DomainError.AccountFrozen("Suspicious fraudulent activity detected.")),
            { Balance: var balance } when balance < request.Amount => Result<(PaymentRequest, CustomerAccount), DomainError>.Failure(
                new DomainError.InsufficientFunds(request.Amount, balance)),
            _ => Result<(PaymentRequest, CustomerAccount), DomainError>.Success((request, account))
        };
    }

    // Step 3: Pure State Transformation
    public static Result<ProcessedPayment, DomainError> ApplyDebit(PaymentRequest request, CustomerAccount account)
    {
        // Zero mutations to input parameters. Produces fresh state.
        decimal updatedBalance = account.Balance - request.Amount;
        
        var receipt = new ProcessedPayment(
            TransactionId: request.TransactionId,
            DebitedAmount: request.Amount,
            RemainingBalance: updatedBalance,
            Timestamp: DateTime.UtcNow
        );

        return Result<ProcessedPayment, DomainError>.Success(receipt);
    }

    // Orchestrator: Pure Functional Pipeline Chain
    public static Result<ProcessedPayment, DomainError> ExecuteTransaction(
        PaymentRequest request, 
        CustomerAccount account)
    {
        return ValidateRequest(request)
            .Bind(validReq => VerifyAccountState(validReq, account))
            .Bind(context => ApplyDebit(context.Request, context.Account));
    }
}

// Interactive Test Program
public class Program
{
    public static void Main()
    {
        var account = new CustomerAccount(Guid.NewGuid(), Balance: 500_000m, IsFrozen: false);
        
        // Scenario A: Successful Flow
        var validRequest = new PaymentRequest(Guid.NewGuid(), account.Id, Amount: 150_000m, Currency: "IDR");
        var resultSuccess = PaymentEngine.ExecuteTransaction(validRequest, account);
        PrintResult(resultSuccess);

        // Scenario B: Validation Failure (Bypasses Step 2 & 3)
        var invalidRequest = new PaymentRequest(Guid.NewGuid(), account.Id, Amount: -10m, Currency: "IDR");
        var resultInvalid = PaymentEngine.ExecuteTransaction(invalidRequest, account);
        PrintResult(resultInvalid);

        // Scenario C: Business Failure (Insufficient balance)
        var expensiveRequest = new PaymentRequest(Guid.NewGuid(), account.Id, Amount: 1_000_000m, Currency: "IDR");
        var resultOverdraw = PaymentEngine.ExecuteTransaction(expensiveRequest, account);
        PrintResult(resultOverdraw);
    }

    private static void PrintResult(Result<ProcessedPayment, DomainError> result)
    {
        string output = result.Match(
            onSuccess: payment => $"[SUCCESS] Transaction {payment.TransactionId} processed. Remaining: {payment.RemainingBalance:C}",
            onFailure: error => error switch
            {
                DomainError.ValidationError valErr => $"[VALIDATION REJECTED] {valErr.PropertyName}: {valErr.Detail}",
                DomainError.InsufficientFunds insFunds => $"[REJECTED] {insFunds.Message}",
                DomainError.AccountFrozen frozen => $"[SECURITY LOCK] {frozen.Reason}",
                _ => $"[UNKNOWN ERROR] {error.Message}"
            }
        );

        Console.WriteLine(output);
    }
}

using System.Data;
using Dapper;
using FinancialLedger.Domain;
using Microsoft.EntityFrameworkCore;

namespace FinancialLedger.Infrastructure;

public sealed record TransactionReportDto
{
    public Guid TransactionId { get; init; }
    public string ReferenceId { get; init; } = null!;
    public string SourceAccountNumber { get; init; } = null!;
    public string DestinationAccountNumber { get; init; } = null!;
    public decimal Amount { get; init; }
    public DateTime TimestampUtc { get; init; }
}

public interface ILedgerService
{
    Task ExecuteTransferAsync(string refId, Guid sourceId, Guid destId, decimal amount, CancellationToken ct);
    IAsyncEnumerable<TransactionReportDto> StreamAccountStatementsAsync(Guid accountId, CancellationToken ct);
}

public sealed class LedgerService : ILedgerService
{
    private readonly LedgerDbContext _dbContext;

    public LedgerService(LedgerDbContext dbContext)
    {
        _dbContext = dbContext;
    }

    // WRITE WORKFLOW: Fully Protected via EF Core Transaction & Optimistic Concurrency
    public async Task ExecuteTransferAsync(string refId, Guid sourceId, Guid destId, decimal amount, CancellationToken ct)
    {
        // Resilient execution strategy handles transient connection drops
        var strategy = _dbContext.Database.CreateExecutionStrategy();

        await strategy.ExecuteAsync(async () =>
        {
            await using var transaction = await _dbContext.Database.BeginTransactionAsync(IsolationLevel.ReadCommitted, ct);

            try
            {
                var sourceAccount = await _dbContext.Accounts
                    .SingleOrDefaultAsync(a => a.Id == sourceId, ct)
                    ?? throw new KeyNotFoundException($"Source account not found: {sourceId}");

                var destAccount = await _dbContext.Accounts
                    .SingleOrDefaultAsync(a => a.Id == destId, ct)
                    ?? throw new KeyNotFoundException($"Destination account not found: {destId}");

                // Enforce Business Logic / Invariants
                sourceAccount.Debit(amount);
                destAccount.Credit(amount);

                var ledgerEntry = new LedgerTransaction(refId, sourceId, destId, amount);
                await _dbContext.Transactions.AddAsync(ledgerEntry, ct);

                // Menjalankan SaveChanges. Jika ada intervensi thread lain terhadap row_version, DbUpdateConcurrencyException dipicu
                await _dbContext.SaveChangesAsync(ct);
                await transaction.CommitAsync(ct);
            }
            catch (DbUpdateConcurrencyException ex)
            {
                await transaction.RollbackAsync(ct);
                throw new InvalidOperationException("High contention detected. Concurrency collision on Account balance update. Retry transaction.", ex);
            }
            catch (Exception)
            {
                await transaction.RollbackAsync(ct);
                throw;
            }
        });
    }

    // READ WORKFLOW: Dapper Pipeline with Memory-Stream Optimization (Unbuffered)
    public async IAsyncEnumerable<TransactionReportDto> StreamAccountStatementsAsync(
        Guid accountId, 
        [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken ct)
    {
        var connection = _dbContext.Database.GetDbConnection();
        if (connection.State != ConnectionState.Open)
        {
            await connection.OpenAsync(ct);
        }

        const string sql = """
            SELECT 
                t.id AS TransactionId,
                t.reference_id AS ReferenceId,
                s.account_number AS SourceAccountNumber,
                d.account_number AS DestinationAccountNumber,
                t.amount AS Amount,
                t.timestamp_utc AS TimestampUtc
            FROM transactions t
            INNER JOIN accounts s ON t.source_account_id = s.id
            INNER JOIN accounts d ON t.destination_account_id = d.id
            WHERE t.source_account_id = @AccountId OR t.destination_account_id = @AccountId
            ORDER BY t.timestamp_utc DESC;
            """;

        // Menggunakan CommandFlags.None untuk eksekusi Unbuffered: Data distreaming langsung dari network buffer
        // Tidak memuat 100k data ke memori List<T> terlebih dahulu!
        var command = new CommandDefinition(
            commandText: sql,
            parameters: new { AccountId = accountId },
            flags: CommandFlags.None,
            cancellationToken: ct
        );

        // Eksekusi raw IDataReader via Dapper reader
        var reader = await connection.ExecuteReaderAsync(command);
        var rowParser = reader.GetRowParser<TransactionReportDto>();

        while (await reader.ReadAsync(ct))
        {
            yield return rowParser(reader);
        }
    }
}

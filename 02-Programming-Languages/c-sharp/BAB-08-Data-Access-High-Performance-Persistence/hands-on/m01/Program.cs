// HighPerformanceBulkWriter.cs
using System;
using System.Collections.Generic;
using System.Data;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Data.SqlClient;

namespace HighPerformancePersistence.RealWorld;

public sealed class LedgerBulkPayload
{
    public long Id { get; init; }
    public Guid TransactionReference { get; init; }
    public decimal Amount { get; init; }
    public string Currency { get; init; } = "USD";
    public DateTime CreatedAtUtc { get; init; }
}

/// <summary>
/// Custom In-Memory DataReader Adapter.
/// Mengalirkan enumerable objek secara langsung ke SqlBulkCopy tanpa memuat DataTable ke RAM.
/// </summary>
public sealed class ObjectDataReaderAdapter<T> : IDataReader
{
    private readonly IEnumerator<T> _enumerator;
    private readonly IReadOnlyList<Func<T, object>> _propertyAccessors;
    private readonly IReadOnlyList<string> _propertyNames;

    public ObjectDataReaderAdapter(
        IEnumerable<T> data,
        IReadOnlyList<string> propertyNames,
        IReadOnlyList<Func<T, object>> propertyAccessors)
    {
        _enumerator = data.GetEnumerator();
        _propertyNames = propertyNames;
        _propertyAccessors = propertyAccessors;
    }

    public bool Read() => _enumerator.MoveNext();
    public object GetValue(int i) => _propertyAccessors[i](_enumerator.Current);
    public int FieldCount => _propertyAccessors.Count;
    public string GetName(int i) => _propertyNames[i];

    // Implementasi interface minimum yang disyaratkan SqlBulkCopy
    public void Dispose() => _enumerator.Dispose();
    public void Close() => Dispose();
    public bool IsClosed => false;
    public int Depth => 0;
    public DataTable GetSchemaTable() => throw new NotSupportedException();
    public bool NextResult() => false;
    public int RecordsAffected => -1;

    // Primitives accessors
    public int GetOrdinal(string name)
    {
        for (int i = 0; i < _propertyNames.Count; i++)
        {
            if (string.Equals(_propertyNames[i], name, StringComparison.OrdinalIgnoreCase))
                return i;
        }
        return -1;
    }

    public object this[int i] => GetValue(i);
    public object this[string name] => GetValue(GetOrdinal(name));
    public bool GetBoolean(int i) => (bool)GetValue(i);
    public byte GetByte(int i) => (byte)GetValue(i);
    public long GetBytes(int i, long fieldOffset, byte[]? buffer, int bufferoffset, int length) => 0;
    public char GetChar(int i) => (char)GetValue(i);
    public long GetChars(int i, long fieldoffset, char[]? buffer, int bufferoffset, int length) => 0;
    public IDataReader GetData(int i) => throw new NotSupportedException();
    public string GetDataTypeName(int i) => GetFieldType(i).Name;
    public DateTime GetDateTime(int i) => (DateTime)GetValue(i);
    public decimal GetDecimal(int i) => (decimal)GetValue(i);
    public double GetDouble(int i) => (double)GetValue(i);
    public Type GetFieldType(int i) => _propertyAccessors[i](_enumerator.Current).GetType();
    public float GetFloat(int i) => (float)GetValue(i);
    public Guid GetGuid(int i) => (Guid)GetValue(i);
    public short GetInt16(int i) => (short)GetValue(i);
    public int GetInt32(int i) => (int)GetValue(i);
    public long GetInt64(int i) => (long)GetValue(i);
    public string GetString(int i) => (string)GetValue(i);
    public int GetValues(object[] values)
    {
        int count = Math.Min(values.Length, FieldCount);
        for (int i = 0; i < count; i++) values[i] = GetValue(i);
        return count;
    }
    public bool IsDBNull(int i) => GetValue(i) == null;
}

public sealed class BulkPersistenceEngine
{
    private readonly string _connectionString;

    public BulkPersistenceEngine(string connectionString)
    {
        _connectionString = connectionString;
    }

    public async Task<long> BulkInsertLedgersAsync(
        IEnumerable<LedgerBulkPayload> transactions,
        int batchSize = 10_000,
        CancellationToken cancellationToken = default)
    {
        await using var connection = new SqlConnection(_connectionString);
        await connection.OpenAsync(cancellationToken).ConfigureAwait(false);

        // SqlBulkCopyOptions.TableLock: Mengurangi transaction-log overhead secara signifikan
        // SqlBulkCopyOptions.CheckConstraints: Tetap menjaga integritas data model relasional
        var copyOptions = SqlBulkCopyOptions.TableLock | 
                          SqlBulkCopyOptions.CheckConstraints | 
                          SqlBulkCopyOptions.KeepIdentity;

        using var bulkCopy = new SqlBulkCopy(connection, copyOptions, externalTransaction: null)
        {
            DestinationTableName = "dbo.FinancialLedgers",
            BatchSize = batchSize,
            BulkCopyTimeout = 300 // 5 Menit
        };

        // Explicit Column Mapping untuk menghindari mismatch schema metadata database
        bulkCopy.ColumnMappings.Add(nameof(LedgerBulkPayload.Id), "Id");
        bulkCopy.ColumnMappings.Add(nameof(LedgerBulkPayload.TransactionReference), "TransactionReference");
        bulkCopy.ColumnMappings.Add(nameof(LedgerBulkPayload.Amount), "Amount");
        bulkCopy.ColumnMappings.Add(nameof(LedgerBulkPayload.Currency), "Currency");
        bulkCopy.ColumnMappings.Add(nameof(LedgerBulkPayload.CreatedAtUtc), "CreatedAtUtc");

        var columnNames = new[] { "Id", "TransactionReference", "Amount", "Currency", "CreatedAtUtc" };
        var columnAccessors = new Func<LedgerBulkPayload, object>[]
        {
            x => x.Id,
            x => x.TransactionReference,
            x => x.Amount,
            x => x.Currency,
            x => x.CreatedAtUtc
        };

        using var readerAdapter = new ObjectDataReaderAdapter<LedgerBulkPayload>(
            transactions,
            columnNames,
            columnAccessors
        );

        var stopwatch = Stopwatch.StartNew();
        
        // Eksekusi streaming langsung melalui Tabular Data Stream protocol
        await bulkCopy.WriteToServerAsync(readerAdapter, cancellationToken).ConfigureAwait(false);
        
        stopwatch.Stop();
        return stopwatch.ElapsedMilliseconds;
    }
}

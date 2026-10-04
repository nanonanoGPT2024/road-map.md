using System;
using System.Buffers;
using System.Buffers.Text;
using System.IO;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace HighPerformance.ProductionEngine
{
    public readonly record struct TradeExecutionMessage(long OrderId, decimal ExecutionPrice, int Quantity);

    public sealed class FastMessageProcessor : IAsyncDisposable
    {
        private readonly Stream _networkStream;
        private readonly ArrayPool<byte> _pool;
        private byte[]? _leasedBuffer;
        private const int MaxMessageSize = 4096;

        public FastMessageProcessor(Stream networkStream, ArrayPool<byte>? pool = null)
        {
            _networkStream = networkStream ?? throw new ArgumentNullException(nameof(networkStream));
            _pool = pool ?? ArrayPool<byte>.Shared;
            // Menyewa buffer dari Pool; tidak ada alokasi heap baru
            _leasedBuffer = _pool.Rent(MaxMessageSize);
        }

        /// <summary>
        /// Memproses stream pesan kontinu dengan alokasi heap 0-byte pada hot path.
        /// Format payload: "ORD:10029348|PRC:450.25|QTY:150\n"
        /// </summary>
        public async ValueTask ProcessIncomingTradesAsync(
            Func<TradeExecutionMessage, ValueTask> onMessageProcessed, 
            CancellationToken ct)
        {
            if (_leasedBuffer == null) 
                throw new ObjectDisposedException(nameof(FastMessageProcessor));

            int bytesInBuffer = 0;

            while (!ct.IsCancellationRequested)
            {
                // Baca langsung ke sisa ruang buffer yang disewa
                Memory<byte> memorySlice = _leasedBuffer.AsMemory(bytesInBuffer, _leasedBuffer.Length - bytesInBuffer);
                int bytesRead = await _networkStream.ReadAsync(memorySlice, ct).ConfigureAwait(false);

                if (bytesRead == 0) break; // End of Stream
                bytesInBuffer += bytesRead;

                ReadOnlySpan<byte> currentSpan = _leasedBuffer.AsSpan(0, bytesInBuffer);
                int processedOffset = 0;

                while (true)
                {
                    ReadOnlySpan<byte> unparsedSpan = currentSpan.Slice(processedOffset);
                    int newlineIndex = unparsedSpan.IndexOf((byte)'\n');

                    if (newlineIndex == -1)
                    {
                        // Pesan belum lengkap, geser sisa byte yang belum terurai ke awal buffer
                        break;
                    }

                    // Ambil frame payload persis 1 pesan tanpa tanda newline
                    ReadOnlySpan<byte> messagePayload = unparsedSpan.Slice(0, newlineIndex);
                    
                    // Parse field langsung dari byte span (UTF-8 binary parsing)
                    if (TryParseTradeMessage(messagePayload, out TradeExecutionMessage trade))
                    {
                        await onMessageProcessed(trade).ConfigureAwait(false);
                    }

                    processedOffset += newlineIndex + 1;
                }

                // Geser data parsial yang tersisa ke indeks awal buffer
                if (processedOffset < bytesInBuffer)
                {
                    int remaining = bytesInBuffer - processedOffset;
                    Array.Copy(_leasedBuffer, processedOffset, _leasedBuffer, 0, remaining);
                    bytesInBuffer = remaining;
                }
                else
                {
                    bytesInBuffer = 0;
                }
            }
        }

        private static bool TryParseTradeMessage(ReadOnlySpan<byte> payload, out TradeExecutionMessage trade)
        {
            // Format yang diharapkan: ORD:10029348|PRC:450.25|QTY:150
            trade = default;
            long orderId = 0;
            decimal price = 0;
            int quantity = 0;

            int pos = 0;
            while (pos < payload.Length)
            {
                ReadOnlySpan<byte> remaining = payload.Slice(pos);
                int pipeIndex = remaining.IndexOf((byte)'|');
                ReadOnlySpan<byte> segment = pipeIndex == -1 ? remaining : remaining.Slice(0, pipeIndex);
                pos += pipeIndex == -1 ? remaining.Length : pipeIndex + 1;

                if (segment.StartsWith("ORD:"u8))
                {
                    if (!Utf8Parser.TryParse(segment.Slice(4), out orderId, out _))
                        return false;
                }
                else if (segment.StartsWith("PRC:"u8))
                {
                    if (!Utf8Parser.TryParse(segment.Slice(4), out price, out _))
                        return false;
                }
                else if (segment.StartsWith("QTY:"u8))
                {
                    if (!Utf8Parser.TryParse(segment.Slice(4), out quantity, out _))
                        return false;
                }
            }

            trade = new TradeExecutionMessage(orderId, price, quantity);
            return true;
        }

        public ValueTask DisposeAsync()
        {
            if (_leasedBuffer != null)
            {
                // Mengembalikan buffer ke Pool. SANGAT KRUSIAL untuk mencegah resource starvation
                _pool.Return(_leasedBuffer, clearArray: false);
                _leasedBuffer = null;
            }
            return ValueTask.CompletedTask;
        }
    }
}

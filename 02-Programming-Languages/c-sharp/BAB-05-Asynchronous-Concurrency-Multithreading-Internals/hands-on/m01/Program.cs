using System;
using System.Buffers;
using System.Collections.Concurrent;
using System.IO;
using System.Net.Http;
using System.Runtime.CompilerServices;
using System.Threading;
using System.Threading.Channels;
using System.Threading.Tasks;

namespace CSharpMastery.ProductionEngine
{
    // ========================================================================
    // MODEL TRANSAKSI
    // ========================================================================
    public readonly record struct PaymentRequest(
        Guid TransactionId, 
        decimal Amount, 
        long AccountNumber, 
        long TimestampTicks);

    public readonly record struct PaymentResult(
        Guid TransactionId, 
        bool IsSuccess, 
        string FailureReason);

    // ========================================================================
    // CACHE VALIDASI CEPAT (ZERO-ALLOCATION MEMORY PATTERN)
    // ========================================================================
    public sealed class PaymentValidator
    {
        // Cache statis untuk menghindari alokasi Task baru saat validasi berhasil
        private static readonly ValueTask<bool> s_cachedSuccess = new(true);

        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public ValueTask<bool> ValidateTransactionFastAsync(in PaymentRequest request)
        {
            // Fast-path: Validasi murni in-memory (98% kasus transaksi normal)
            if (request.Amount > 0 && request.AccountNumber > 1000)
            {
                return s_cachedSuccess; // 0 Alokasi Heap
            }

            // Slow-path: Memerlukan pengecekan I/O eksternal (Blacklist Database)
            return ValidateExternalDatabaseSlowAsync(request);
        }

        private async ValueTask<bool> ValidateExternalDatabaseSlowAsync(PaymentRequest request)
        {
            // Menembak database secara asinkron murni tanpa blocking thread
            await Task.Delay(10).ConfigureAwait(false); 
            return request.Amount <= 10_000_000; // Contoh limit batas transaksi
        }
    }

    // ========================================================================
    // PIPELINE PEMROSESAN HIGH-THROUGHPUT DENGAN BACKPRESSURE CHANNELS
    // ========================================================================
    public sealed class PaymentProcessingEngine : IAsyncDisposable
    {
        private readonly Channel<PaymentRequest> _channel;
        private readonly PaymentValidator _validator;
        private readonly CancellationTokenSource _shutdownCts;
        private readonly Task[] _workerTasks;
        private const int MaxQueueCapacity = 50_000;
        private const int WorkerCount = 4;

        public PaymentProcessingEngine(PaymentValidator validator)
        {
            _validator = validator;
            _shutdownCts = new CancellationTokenSource();

            // Gunakan BoundedChannel untuk mencegah OutOfMemoryException (OOM)
            // saat sistem dihantam lonjakan beban tak terduga.
            var channelOptions = new BoundedChannelOptions(MaxQueueCapacity)
            {
                FullMode = BoundedChannelFullMode.Wait, // Menerapkan Backpressure
                SingleReader = false,
                SingleWriter = false
            };

            _channel = Channel.CreateBounded<PaymentRequest>(channelOptions);
            _workerTasks = new Task[WorkerCount];

            // Inisialisasi thread pool worker berdedikasi untuk konsumsi channel
            for (int i = 0; i < WorkerCount; i++)
            {
                int workerId = i;
                _workerTasks[i] = Task.Run(() => ProcessQueueLoopAsync(workerId, _channel.Reader, _shutdownCts.Token));
            }
        }

        public async ValueTask<bool> SubmitPaymentAsync(PaymentRequest request, CancellationToken ct)
        {
            // 1. Validasi transaksi menggunakan ValueTask pattern (Zero Heap Allocation pada fast-path)
            bool isValid = await _validator.ValidateTransactionFastAsync(request).ConfigureAwait(false);
            if (!isValid)
            {
                return false;
            }

            // 2. Terapkan Backpressure asinkron: Jika channel penuh, caller menunggu
            // tanpa memblokir thread sistem OS.
            await _channel.Writer.WriteAsync(request, ct).ConfigureAwait(false);
            return true;
        }

        private async Task ProcessQueueLoopAsync(int workerId, ChannelReader<PaymentRequest> reader, CancellationToken ct)
        {
            // Loop asinkron non-blocking terus membaca selama stream data terbuka
            while (await reader.WaitToReadAsync(ct).ConfigureAwait(false))
            {
                while (reader.TryRead(out PaymentRequest item))
                {
                    try
                    {
                        await ExecutePaymentLifecycleAsync(workerId, item, ct).ConfigureAwait(false);
                    }
                    catch (OperationCanceledException) when (ct.IsCancellationRequested)
                    {
                        return;
                    }
                    catch (Exception ex)
                    {
                        // Hardening: Jangan biarkan unhandled exception mematikan task loop
                        Console.Error.WriteLine($"[CRITICAL WORKER ERROR] Worker {workerId} Error: {ex.Message}");
                    }
                }
            }
        }

        private static async ValueTask ExecutePaymentLifecycleAsync(int workerId, PaymentRequest item, CancellationToken ct)
        {
            // Simulasi panggilan Core Banking Network I/O
            // Tidak ada Thread.Sleep! Menggunakan non-blocking token-aware delay
            await Task.Delay(5, ct).ConfigureAwait(false);
            
            // Console print hanya untuk observabilitas simulasi
            // Pada produksi riil, ganti dengan High-Performance Logging (ILogger Source Generators)
        }

        public async ValueTask DisposeAsync()
        {
            // Graceful Shutdown Sequence
            _channel.Writer.Complete(); // Tutup akses penulisan antrean
            _shutdownCts.Cancel();     // Picu pembatalan token kerja

            try
            {
                // Tunggu seluruh worker menyelesaikan sisa item yang terlanjur masuk
                await Task.WhenAll(_workerTasks).ConfigureAwait(false);
            }
            catch (Exception)
            {
                // Mengabaikan TaskCanceledException saat proses tearing down
            }
            finally
            {
                _shutdownCts.Dispose();
            }
        }
    }
}

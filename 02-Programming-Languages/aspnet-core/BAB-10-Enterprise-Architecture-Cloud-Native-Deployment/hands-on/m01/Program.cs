// File: src/EnterpriseApp.Infrastructure/BackgroundServices/PaymentQueueConsumer.cs
namespace EnterpriseApp.Infrastructure.BackgroundServices;

using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

public sealed class PaymentQueueConsumer : BackgroundService
{
    private readonly ILogger<PaymentQueueConsumer> _logger;
    private readonly IHostApplicationLifetime _lifetime;

    public PaymentQueueConsumer(
        ILogger<PaymentQueueConsumer> logger,
        IHostApplicationLifetime lifetime)
    {
        _logger = logger;
        _lifetime = lifetime;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _lifetime.ApplicationStopping.Register(() =>
        {
            _logger.LogWarning("SIGTERM terdeteksi. Menghentikan penarikan pesan baru dari Queue...");
        });

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                // Mensimulasikan konsumsi antrean transaksi finansial
                await ProcessPaymentQueueAsync(stoppingToken);
                await Task.Delay(1000, stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                _logger.LogInformation("Operasi antrean dibatalkan secara aman.");
                break;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Kesalahan tidak terduga dalam antrean pembayaran.");
            }
        }

        _logger.LogInformation("Drain antrean selesai. Worker berhenti total.");
    }

    private async Task ProcessPaymentQueueAsync(CancellationToken cancellationToken)
    {
        // Logika pemrosesan transaksi
        await Task.CompletedTask;
    }
}

using System.Collections.Concurrent;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Primitives;

namespace Enterprise.Fintech.Core;

// 1. DATA MODEL FOR TENANT CONFIGURATION
public record TenantPaymentConfig(string MerchantId, string ApiKey, string GatewayUrl, int TimeoutMs);

// 2. CUSTOM CONFIGURATION SOURCE & PROVIDER (Thread-Safe & Reloadable)
public class TenantDatabaseConfigurationSource : IConfigurationSource
{
    public IConfigurationProvider Build(IConfigurationBuilder builder)
    {
        return new TenantDatabaseConfigurationProvider();
    }
}

public class TenantDatabaseConfigurationProvider : ConfigurationProvider
{
    private readonly Timer _reloadTimer;

    public TenantDatabaseConfigurationProvider()
    {
        // Polling setiap 30 detik untuk mendeteksi perubahan konfigurasi dari database
        _reloadTimer = new Timer(_ => LoadDataFromDatabase(), null, Timeout.Infinite, Timeout.Infinite);
    }

    public override void Load()
    {
        LoadDataFromDatabase();
        // Aktifkan timer berkala setelah pembacaan awal
        _reloadTimer.Change(TimeSpan.FromSeconds(30), TimeSpan.FromSeconds(30));
    }

    private void LoadDataFromDatabase()
    {
        // Simulasi query database / Vault:
        var externalData = FetchMockDataFromDatabase();

        var newDictionary = new Dictionary<string, string?>(StringComparer.OrdinalIgnoreCase);

        foreach (var tenant in externalData)
        {
            // Meratakan hierarki (flattening) ke format path IConfiguration
            // Format: Tenants:{MerchantId}:{Property}
            newDictionary[$"Tenants:{tenant.MerchantId}:ApiKey"] = tenant.ApiKey;
            newDictionary[$"Tenants:{tenant.MerchantId}:GatewayUrl"] = tenant.GatewayUrl;
            newDictionary[$"Tenants:{tenant.MerchantId}:TimeoutMs"] = tenant.TimeoutMs.ToString();
        }

        // Bandingkan apakah ada data yang berubah
        if (!DictionariesAreEqual(Data, newDictionary))
        {
            Data = newDictionary;
            OnReload(); // Trigger IChangeToken reload notifications
        }
    }

    private static List<TenantPaymentConfig> FetchMockDataFromDatabase()
    {
        return
        [
            new("MERCHANT-ALPHA", "SEC-KEY-ALPHA-12345", "https://bank-a.com/api", 5000),
            new("MERCHANT-BETA", "SEC-KEY-BETA-99999", "https://bank-b.com/api", 3000)
        ];
    }

    private static bool DictionariesAreEqual(IDictionary<string, string?> first, IDictionary<string, string?> second)
    {
        if (first.Count != second.Count) return false;
        foreach (var pair in first)
        {
            if (!second.TryGetValue(pair.Key, out var val) || val != pair.Value)
                return false;
        }
        return true;
    }
}

// 3. EXTENSION METHODS
public static class CustomConfigurationExtensions
{
    public static IConfigurationBuilder AddTenantDatabaseSource(this IConfigurationBuilder builder)
    {
        return builder.Add(new TenantDatabaseConfigurationSource());
    }
}

// 4. TENANT ACCESSOR ABSTRACTION
public interface ITenantContextAccessor
{
    string CurrentTenantId { get; set; }
}

public class TenantContextAccessor : ITenantContextAccessor
{
    // Scoped request context
    public string CurrentTenantId { get; set; } = string.Empty;
}

// 5. SECURE RUNTIME RESOLVER FOR MERCHANTS
public interface IPaymentGatewayExecutor
{
    Task<string> ExecutePaymentAsync(decimal amount);
}

public class PaymentGatewayExecutor : IPaymentGatewayExecutor
{
    private readonly ITenantContextAccessor _tenantAccessor;
    private readonly IConfiguration _configuration;
    private readonly IHttpClientFactory _httpClientFactory;

    public PaymentGatewayExecutor(
        ITenantContextAccessor tenantAccessor,
        IConfiguration configuration,
        IHttpClientFactory httpClientFactory)
    {
        _tenantAccessor = tenantAccessor;
        _configuration = configuration;
        _httpClientFactory = httpClientFactory;
    }

    public async Task<string> ExecutePaymentAsync(decimal amount)
    {
        var tenantId = _tenantAccessor.CurrentTenantId;
        if (string.IsNullOrWhiteSpace(tenantId))
        {
            throw new InvalidOperationException("Tenant Context tidak teridentifikasi pada pipeline!");
        }

        // Pembacaan konfigurasi instan melalui internal memory provider
        var apiKey = _configuration[$"Tenants:{tenantId}:ApiKey"];
        var gatewayUrl = _configuration[$"Tenants:{tenantId}:GatewayUrl"];
        var timeout = _configuration.GetValue<int>($"Tenants:{tenantId}:TimeoutMs");

        if (apiKey == null || gatewayUrl == null)
        {
            throw new KeyNotFoundException($"Merchant '{tenantId}' tidak memiliki konfigurasi gateway valid!");
        }

        var client = _httpClientFactory.CreateClient("PaymentClient");
        client.Timeout = TimeSpan.FromMilliseconds(timeout);

        // Simulasi request payment
        return await Task.FromResult($"Transacted {amount} for {tenantId} via {gatewayUrl}. Key: {apiKey[..4]}****");
    }
}

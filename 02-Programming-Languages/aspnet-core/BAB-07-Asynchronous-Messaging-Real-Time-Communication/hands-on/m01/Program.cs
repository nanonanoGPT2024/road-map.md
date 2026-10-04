// Program.cs
using MessagePack;
using MessagePack.Resolvers;
using RealTimeEngine.Hubs;
using RealTimeEngine.Services;
using RealTimeEngine.Workers;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();

// Registrasi In-Memory Channel Pipeline
builder.Services.AddSingleton<MarketFeedChannel>();
builder.Services.AddHostedService<MarketBroadcastWorker>();

// Registrasi & Optimasi SignalR dengan MessagePack dan Redis
var signalRBuilder = builder.Services.AddSignalR(options =>
{
    options.EnableDetailedErrors = builder.Environment.IsDevelopment();
    options.KeepAliveInterval = TimeSpan.FromSeconds(15);
    options.ClientTimeoutInterval = TimeSpan.FromSeconds(30);
    options.MaximumReceiveMessageSize = 32 * 1024; // 32 KB per frame
})
.AddMessagePackProtocol(options =>
{
    options.SerializerOptions = MessagePackSerializerOptions.Standard
        .WithResolver(ContractlessStandardResolver.Instance)
        .WithSecurity(MessagePackSecurity.UntrustedData);
});

// Konfigurasi Redis Scale-Out jika Connection String tersedia
var redisConnectionString = builder.Configuration.GetConnectionString("RedisSignalR");
if (!string.IsNullOrWhiteSpace(redisConnectionString))
{
    signalRBuilder.AddStackExchangeRedis(redisConnectionString, options =>
    {
        options.Configuration.ChannelPrefix = "MarketCluster";
    });
}

builder.Services.AddCors(options =>
{
    options.AddPolicy("SignalRPolicy", policy =>
    {
        policy.WithOrigins("https://trading.internal.domain")
              .AllowAnyHeader()
              .AllowAnyMethod()
              .AllowCredentials(); // WAJIB untuk SignalR transport credentials
    });
});

var app = builder.Build();

app.UseCors("SignalRPolicy");
app.UseRouting();

app.MapControllers();
app.MapHub<MarketHub>("/hubs/market");

app.Run();

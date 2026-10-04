// Security/Handlers/LoanApprovalAuthorizationHandler.cs
using System.Security.Claims;
using Enterprise.Security.Domain;
using Enterprise.Security.Requirements;
using Microsoft.AspNetCore.Authorization;

namespace Enterprise.Security.Handlers;

public class LoanApprovalAuthorizationHandler : AuthorizationHandler<LoanApprovalRequirement, LoanApplication>
{
    private readonly ILogger<LoanApprovalAuthorizationHandler> _logger;

    public LoanApprovalAuthorizationHandler(ILogger<LoanApprovalAuthorizationHandler> logger)
    {
        _logger = logger;
    }

    protected override Task HandleRequirementAsync(
        AuthorizationHandlerContext context,
        LoanApprovalRequirement requirement,
        LoanApplication resource)
    {
        var user = context.User;

        // 1. Ekstraksi Klaim Identitas FinTech
        var userTenantId = user.FindFirst("tenant_id")?.Value;
        var approvalLimitClaim = user.FindFirst("max_approval_limit")?.Value;
        var userId = user.FindFirst(ClaimTypes.NameIdentifier)?.Value;

        if (string.IsNullOrEmpty(userTenantId) || string.IsNullOrEmpty(approvalLimitClaim) || string.IsNullOrEmpty(userId))
        {
            _logger.LogWarning("Otorisasi gagal: User {UserId} tidak memiliki struktur klaim tenant/limit lengkap.", userId);
            context.Fail(); // Short-circuit kegagalan
            return Task.CompletedTask;
        }

        // 2. Evaluasi Isolasi Multi-Tenant
        if (!string.Equals(userTenantId, resource.TenantId, StringComparison.Ordinal))
        {
            _logger.LogCritical("Pelanggaran Keamanan Tenant: User {UserId} dari Tenant {UserTenant} mencoba mengakses Resource milik Tenant {ResourceTenant}",
                userId, userTenantId, resource.TenantId);
            context.Fail();
            return Task.CompletedTask;
        }

        // 3. Evaluasi Limit Persetujuan Finansial (ABAC Logic)
        if (!decimal.TryParse(approvalLimitClaim, out var maxApprovalLimit))
        {
            _logger.LogError("Format klaim limit approval korup untuk User {UserId}: {RawClaim}", userId, approvalLimitClaim);
            context.Fail();
            return Task.CompletedTask;
        }

        if (resource.Amount > maxApprovalLimit)
        {
            _logger.LogInformation("Otorisasi ditolak: Nominal aplikasi ({Amount}) melampaui limit wewenang User {UserId} ({Limit})",
                resource.Amount, userId, maxApprovalLimit);
            
            // Jangan panggil context.Fail() di sini jika Anda ingin membiarkan handler lain mengevaluasi fallback;
            // tetapi jika limit ini sifatnya absolut, biarkan tanpa context.Succeed().
            return Task.CompletedTask;
        }

        // 4. Evaluasi Self-Approval Anti-Fraud Rule
        if (string.Equals(userId, resource.SubmitterUserId, StringComparison.OrdinalIgnoreCase))
        {
            _logger.LogWarning("Fraud Prevention: User {UserId} dilarang menyetujui aplikasi kredit miliknya sendiri.", userId);
            context.Fail();
            return Task.CompletedTask;
        }

        // Semua kriteria terpenuhi
        context.Succeed(requirement);
        return Task.CompletedTask;
    }
}

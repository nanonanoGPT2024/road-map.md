package com.architect.coroutines.production

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineName
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import java.io.IOException

// Model Domain
data class PaymentContext(val transactionId: String, val customerId: String, val amount: Double)
data class BalanceInfo(val availableAmount: Double, val currency: String)
data class FraudCheck(val isBlacklisted: Boolean, val riskLevel: String)
data class LoyaltyProfile(val points: Long)

data class AggregatedPaymentProfile(
    val transactionId: String,
    val balance: BalanceInfo,
    val fraudCheck: FraudCheck,
    val loyaltyProfile: LoyaltyProfile
)

// Custom Business Exceptions
class HighRiskFraudException(message: String) : RuntimeException(message)
class InsufficientFundsException(message: String) : RuntimeException(message)

interface DownstreamGateway {
    suspend fun getBalance(customerId: String): BalanceInfo
    suspend fun getFraudStatus(customerId: String, amount: Double): FraudCheck
    suspend fun getLoyaltyPoints(customerId: String): LoyaltyProfile
}

// Implementasi Mock dengan Latensi Asinkron
class HttpDownstreamGateway(private val ioDispatcher: CoroutineDispatcher) : DownstreamGateway {
    override suspend fun getBalance(customerId: String): BalanceInfo = withContext(ioDispatcher) {
        delay(120) // simulasi response time
        BalanceInfo(availableAmount = 5000.0, currency = "USD")
    }

    override suspend fun getFraudStatus(customerId: String, amount: Double): FraudCheck = withContext(ioDispatcher) {
        delay(180) // simulasi compute time fraud network
        if (amount > 10000.0) {
            FraudCheck(isBlacklisted = true, riskLevel = "CRITICAL")
        } else {
            FraudCheck(isBlacklisted = false, riskLevel = "LOW")
        }
    }

    override suspend fun getLoyaltyPoints(customerId: String): LoyaltyProfile = withContext(ioDispatcher) {
        delay(350) // simulasi layanan legacy yang lambat
        LoyaltyProfile(points = 1250)
    }
}

class PaymentAggregatorService(
    private val gateway: DownstreamGateway,
    private val defaultDispatcher: CoroutineDispatcher = Dispatchers.Default
) {
    suspend fun aggregatePaymentData(context: PaymentContext): AggregatedPaymentProfile = coroutineScope {
        // coroutineScope menjamin Structured Concurrency:
        // Jika ada child yang melempar exception tak tertangani, semua saudara dibatalkan otomatis.

        println("[AGGREGATOR] Mulai memproses transaksi: ${context.transactionId} pada coroutine: ${coroutineContext[CoroutineName]}")

        // 1. Fetch Fraud Check (Critical Path)
        val fraudDeferred: Deferred<FraudCheck> = async(defaultDispatcher + CoroutineName("Async-Fraud")) {
            withTimeout(300) {
                gateway.getFraudStatus(context.customerId, context.amount)
            }
        }

        // 2. Fetch Balance (Critical Path)
        val balanceDeferred: Deferred<BalanceInfo> = async(defaultDispatcher + CoroutineName("Async-Balance")) {
            withTimeout(300) {
                gateway.getBalance(context.customerId)
            }
        }

        // 3. Fetch Loyalty (Optional Path / Non-critical)
        // Kita tangani error di dalam coroutine child agar tidak membatalkan coroutineScope parent
        val loyaltyDeferred: Deferred<LoyaltyProfile> = async(defaultDispatcher + CoroutineName("Async-Loyalty")) {
            try {
                withTimeout(200) { // SLA ketat untuk data sekunder
                    gateway.getLoyaltyPoints(context.customerId)
                }
            } catch (e: Exception) {
                if (e is CancellationException) throw e // WAJIB rethrow cancellation exception!
                println("[WARN] Gagal mengambil profil Loyalty (${e.message}). Menggunakan fallback 0 poin.")
                LoyaltyProfile(points = 0)
            }
        }

        // Evaluasi Fail-Fast: Validasi Fraud
        val fraudResult = fraudDeferred.await()
        if (fraudResult.isBlacklisted) {
            // Membatalkan child jobs yang belum selesai secara otomatis karena kita melempar exception di coroutineScope
            throw HighRiskFraudException("Transaksi DITOLAK! Terdeteksi Fraud dengan tingkat: ${fraudResult.riskLevel}")
        }

        // Validasi Saldo
        val balanceResult = balanceDeferred.await()
        if (balanceResult.availableAmount < context.amount) {
            throw InsufficientFundsException("Saldo tidak mencukupi untuk transaksi: ${context.transactionId}")
        }

        val loyaltyResult = loyaltyDeferred.await()

        AggregatedPaymentProfile(
            transactionId = context.transactionId,
            balance = balanceResult,
            fraudCheck = fraudResult,
            loyaltyProfile = loyaltyResult
        )
    }
}

// Runtime Execution Test Driver
fun main() = kotlinx.coroutines.runBlocking {
    val gateway = HttpDownstreamGateway(Dispatchers.IO)
    val service = PaymentAggregatorService(gateway)

    println("--- SKENARIO 1: TRANSAKSI VALID ---")
    val validContext = PaymentContext("TX-1001", "CUST-A", 150.0)
    try {
        val result = service.aggregatePaymentData(validContext)
        println("Transaksi Berhasil Dimuat: $result")
    } catch (e: Exception) {
        println("Transaksi Gagal: ${e.message}")
    }

    println("\n--- SKENARIO 2: TRANSAKSI FRAUD (FAIL-FAST) ---")
    val fraudContext = PaymentContext("TX-6666", "CUST-EVIL", 50000.0)
    try {
        service.aggregatePaymentData(fraudContext)
    } catch (e: HighRiskFraudException) {
        println("Intercepted Exception Sukses: ${e.message}")
    }
}

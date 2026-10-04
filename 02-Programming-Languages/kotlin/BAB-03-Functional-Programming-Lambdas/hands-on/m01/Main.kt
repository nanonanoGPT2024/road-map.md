package com.payment.gateway.pipeline

import java.math.BigDecimal
import java.time.Instant

// Model Entitas Domain
data class Transaction(
    val id: String,
    val merchantId: String,
    val amount: BigDecimal,
    val currency: String,
    val timestamp: Instant,
    val metadata: Map<String, String> = emptyMap()
)

sealed class PipelineResult {
    data class Success(val transaction: Transaction) : PipelineResult()
    data class Rejected(val reason: String, val transaction: Transaction) : PipelineResult()
}

// Tipe Alias untuk Middleware Function
typealias Middleware = (Transaction) -> MiddlewareDecision

sealed class MiddlewareDecision {
    data class Proceed(val transaction: Transaction) : MiddlewareDecision()
    data class Abort(val reason: String) : MiddlewareDecision()
}

// DSL Builder untuk Komposisi Middleware
class PaymentPipelineBuilder {
    private val middlewares = mutableListOf<Middleware>()

    fun sanitize(action: (Transaction) -> Transaction) {
        middlewares.add { tx -> 
            MiddlewareDecision.Proceed(action(tx)) 
        }
    }

    fun verify(predicate: (Transaction) -> Boolean, rejectionReason: String) {
        middlewares.add { tx ->
            if (predicate(tx)) {
                MiddlewareDecision.Proceed(tx)
            } else {
                MiddlewareDecision.Abort(rejectionReason)
            }
        }
    }

    fun build(): PaymentPipeline = PaymentPipeline(middlewares.toList())
}

// Eksekutor Pipeline
class PaymentPipeline(private val middlewares: List<Middleware>) {
    
    // Inline loop engine untuk mengeksekusi pipeline berantai
    inline fun execute(
        initialTransaction: Transaction,
        onAbort: (String, Transaction) -> Unit
    ): PipelineResult {
        var currentTx = initialTransaction

        for (i in middlewares.indices) {
            val decision = middlewares[i](currentTx)
            when (decision) {
                is MiddlewareDecision.Proceed -> {
                    currentTx = decision.transaction
                }
                is MiddlewareDecision.Abort -> {
                    onAbort(decision.reason, currentTx)
                    return PipelineResult.Rejected(decision.reason, currentTx)
                }
            }
        }

        return PipelineResult.Success(currentTx)
    }
}

// Factory Function Menggunakan Function Literals with Receiver
fun configurePipeline(builderAction: PaymentPipelineBuilder.() -> Unit): PaymentPipeline {
    val builder = PaymentPipelineBuilder()
    builder.builderAction()
    return builder.build()
}

// =========================================================================
// Eksekusi Produksi
// =========================================================================
fun main() {
    // 1. Inisialisasi Pipeline Deklaratif
    val gatewayPipeline = configurePipeline {
        // Step 1: Sanitasi
        sanitize { tx ->
            tx.copy(merchantId = tx.merchantId.trim().uppercase())
        }

        // Step 2: Fraud Check
        verify(
            predicate = { tx -> tx.amount < BigDecimal("50000.00") },
            rejectionReason = "ERR_FRAUD_LIMIT_EXCEEDED"
        )

        // Step 3: Currency Validation
        verify(
            predicate = { tx -> tx.currency in setOf("USD", "EUR", "IDR") },
            rejectionReason = "ERR_UNSUPPORTED_CURRENCY"
        )
    }

    // 2. Simulasi Transaksi Masuk
    val incomingTx = Transaction(
        id = "TX-998811",
        merchantId = "  merch_stripe_887   ",
        amount = BigDecimal("12500.00"),
        currency = "IDR",
        timestamp = Instant.now()
    )

    // 3. Eksekusi
    val result = gatewayPipeline.execute(
        initialTransaction = incomingTx,
        onAbort = { reason, tx ->
            System.err.println("[AUDIT REJECTED] Tx: ${tx.id} dropped due to: $reason")
        }
    )

    when (result) {
        is PipelineResult.Success -> {
            println("[PROCESSED] Tx ${result.transaction.id} Clean Merchant: ${result.transaction.merchantId}")
        }
        is PipelineResult.Rejected -> {
            println("[FAILED] Transaction validation failed.")
        }
    }
}

package com.backend.reconciliation

import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.decodeToSequence
import java.io.InputStream
import java.math.BigDecimal
import java.time.Instant

// ============================================================================
// LAYER 1: DOMAIN ENTITIES & VALUE OBJECTS (No framework dependencies)
// ============================================================================
enum class ReconciliationStatus { MATCHED, DISCREPANCY_AMOUNT, UNRECOGNIZED_ACCOUNT }

data class ExternalReference(val systemId: String, val externalId: String)

data class ReconciliationRecord(
    val reference: ExternalReference,
    val clearedAmount: BigDecimal,
    val currency: String,
    val executedAt: Instant
)

data class DiscrepancyReport(
    val reference: ExternalReference,
    val status: ReconciliationStatus,
    val differenceAmount: BigDecimal
)

// Ports (Interface Boundary)
interface TransactionLedgerPort {
    fun fetchLedgerAmount(reference: ExternalReference): BigDecimal?
}

interface ReconciliationAuditPort {
    fun recordDiscrepancies(discrepancies: Sequence<DiscrepancyReport>): Long
}

// ============================================================================
// LAYER 2: USE CASE / APPLICATION ENGINE
// ============================================================================
class ReconcileTransactionsUseCase(
    private val ledgerPort: TransactionLedgerPort,
    private val auditPort: ReconciliationAuditPort
) {
    fun execute(recordsStream: Sequence<ReconciliationRecord>): Long {
        val discrepancySequence = recordsStream
            .map { record ->
                val systemAmount = ledgerPort.fetchLedgerAmount(record.reference)
                evaluateDiscrepancy(record, systemAmount)
            }
            .filter { it.status != ReconciliationStatus.MATCHED }

        return auditPort.recordDiscrepancies(discrepancySequence)
    }

    private fun evaluateDiscrepancy(
        record: ReconciliationRecord,
        systemAmount: BigDecimal?
    ): DiscrepancyReport {
        if (systemAmount == null) {
            return DiscrepancyReport(
                reference = record.reference,
                status = ReconciliationStatus.UNRECOGNIZED_ACCOUNT,
                differenceAmount = record.clearedAmount
            )
        }

        val diff = record.clearedAmount.subtract(systemAmount).abs()
        val isMatched = diff.compareTo(BigDecimal("0.001")) <= 0

        return DiscrepancyReport(
            reference = record.reference,
            status = if (isMatched) ReconciliationStatus.MATCHED else ReconciliationStatus.DISCREPANCY_AMOUNT,
            differenceAmount = diff
        )
    }
}

// ============================================================================
// LAYER 3: INTERFACE ADAPTERS (DTOs, Serializers, Extension Mappers)
// ============================================================================
@Serializable
data class GatewayReconciliationItemDto(
    @SerialName("partner_id") val partnerId: String,
    @SerialName("ext_tx_id") val externalTxId: String,
    @SerialName("settled_amount") val amount: String,
    @SerialName("iso_currency") val currency: String,
    @SerialName("timestamp_epoch_ms") val timestampEpochMs: Long
)

// Zero-overhead boundary mapper via Kotlin Extension Function
fun GatewayReconciliationItemDto.toDomain(): ReconciliationRecord {
    return ReconciliationRecord(
        reference = ExternalReference(
            systemId = this.partnerId,
            externalId = this.externalTxId
        ),
        clearedAmount = BigDecimal(this.amount),
        currency = this.currency.uppercase(),
        executedAt = Instant.ofEpochMilli(this.timestampEpochMs)
    )
}

// ============================================================================
// LAYER 4: INFRASTRUCTURE (Streaming Parsers & Ports Mock)
// ============================================================================
class JsonStreamingReconciliationReader(
    private val jsonConfiguration: Json = Json {
        ignoreUnknownKeys = true
        isLenient = false
    }
) {
    @OptIn(ExperimentalSerializationApi::class)
    fun streamFromInputStream(inputStream: InputStream): Sequence<ReconciliationRecord> {
        // decodeToSequence does not load the entire JSON array in-memory;
        // it parses records one-by-one lazily from the stream.
        return jsonConfiguration.decodeToSequence<GatewayReconciliationItemDto>(inputStream)
            .map { it.toDomain() }
    }
}

// ============================================================================
// SYSTEM DEMONSTRATION & VERIFICATION
// ============================================================================
fun main() {
    val rawJsonPayload = """
        [
          {"partner_id": "STRIPE", "ext_tx_id": "ch_1", "settled_amount": "100.50", "iso_currency": "USD", "timestamp_epoch_ms": 1704067200000},
          {"partner_id": "STRIPE", "ext_tx_id": "ch_2", "settled_amount": "500.00", "iso_currency": "USD", "timestamp_epoch_ms": 1704067260000},
          {"partner_id": "XENDIT", "ext_tx_id": "inv_9", "settled_amount": "250.00", "iso_currency": "USD", "timestamp_epoch_ms": 1704067320000}
        ]
    """.trimIndent()

    // 1. Mock Ports
    val mockLedger = object : TransactionLedgerPort {
        override fun fetchLedgerAmount(reference: ExternalReference): BigDecimal? {
            return when (reference.externalId) {
                "ch_1" -> BigDecimal("100.50") // MATCHED
                "ch_2" -> BigDecimal("480.00") // DISCREPANCY
                else -> null                   // UNRECOGNIZED
            }
        }
    }

    val mockAudit = object : ReconciliationAuditPort {
        override fun recordDiscrepancies(discrepancies: Sequence<DiscrepancyReport>): Long {
            var count = 0L
            discrepancies.forEach {
                count++
                println("AUDIT DISCREPANCY DETECTED: Ref=${it.reference.externalId}, Status=${it.status}, Diff=${it.differenceAmount}")
            }
            return count
        }
    }

    // 2. Assemble Architecture Pipeline
    val reader = JsonStreamingReconciliationReader()
    val useCase = ReconcileTransactionsUseCase(mockLedger, mockAudit)

    // 3. Execute lazy stream processing
    val inputStream = rawJsonPayload.byteInputStream()
    val recordSequence = reader.streamFromInputStream(inputStream)
    val discrepanciesLogged = useCase.execute(recordSequence)

    println("Pipeline Processed Successfully. Total Anomaly Count: $discrepanciesLogged")
}

// File: LedgerEngineProduction.scala
package com.fintech.ledger.advanced

import java.time.Instant
import java.util.UUID
import scala.collection.concurrent.TrieMap

// ==========================================
// 1. MODEL DOMAIN & KONTRAK DASAR
// ==========================================

case class Transaction(
  id: UUID,
  accountId: String,
  amount: BigDecimal,
  currency: String,
  timestamp: Instant
)

enum EngineStatus:
  case Success(txId: UUID, ledgerOffset: Long)
  case Rejected(reason: String)

abstract class BaseLedgerEngine:
  def process(tx: Transaction): EngineStatus

// ==========================================
// 2. CONTEXT DEPENDENCIES (VIA SELF-TYPES)
// ==========================================

trait MetricsService:
  def incrementCounter(metricName: String): Unit
  def recordLatency(operation: String, durationNanos: Long): Unit

trait ClockService:
  def now(): Instant

// ==========================================
// 3. CORE CONCRETE IMPLEMENTATION
// ==========================================

open class CoreLedgerEngine(private var sequenceTracker: Long = 0L) extends BaseLedgerEngine:
  private val stateStorage = TrieMap[UUID, Transaction]()

  override def process(tx: Transaction): EngineStatus =
    // Mutasi state terkontrol
    synchronized {
      sequenceTracker += 1
      stateStorage.put(tx.id, tx)
      EngineStatus.Success(tx.id, sequenceTracker)
    }

// ==========================================
// 4. STACKABLE INTERCEPTORS (TRAITS)
// ==========================================

// Trait 1: Idempotency Protection
trait IdempotencyGuard extends BaseLedgerEngine:
  private val processedTransactions = TrieMap[UUID, EngineStatus]()

  abstract override def process(tx: Transaction): EngineStatus =
    processedTransactions.get(tx.id) match
      case Some(cachedResult) =>
        cachedResult
      case None =>
        val result = super.process(tx)
        processedTransactions.put(tx.id, result)
        result

// Trait 2: Telemetry & Metrics (Membutuhkan MetricsService & ClockService)
trait TelemetryInterceptor extends BaseLedgerEngine:
  this: MetricsService & ClockService =>

  abstract override def process(tx: Transaction): EngineStatus =
    val start = System.nanoTime()
    try
      val status = super.process(tx)
      status match
        case EngineStatus.Success(_, _) => 
          incrementCounter("ledger.transactions.success")
        case EngineStatus.Rejected(_) => 
          incrementCounter("ledger.transactions.rejected")
      status
    finally
      val duration = System.nanoTime() - start
      recordLatency("ledger.process.duration", duration)

// Trait 3: Financial Invariant Validator
trait InvariantValidator extends BaseLedgerEngine:
  abstract override def process(tx: Transaction): EngineStatus =
    if tx.amount <= BigDecimal(0) then
      EngineStatus.Rejected(s"Validation Violation: Amount ${tx.amount} must be positive.")
    else if tx.currency.length != 3 then
      EngineStatus.Rejected(s"Validation Violation: Currency ${tx.currency} is invalid ISO code.")
    else
      super.process(tx)

// ==========================================
// 5. PRODUCTION ASSEMBLY (COMPOSITION ROOT)
// ==========================================

class ProductionLedgerEngine extends CoreLedgerEngine
  with InvariantValidator
  with IdempotencyGuard
  with TelemetryInterceptor
  with MetricsService
  with ClockService:

  // Implementasi Context Dependencies
  override def incrementCounter(metricName: String): Unit =
    println(s"[METRICS-METRIC-INC] Name: $metricName")

  override def recordLatency(operation: String, durationNanos: Long): Unit =
    println(s"[METRICS-LATENCY] Op: $operation, Time: ${durationNanos / 1_000_000.0} ms")

  override def now(): Instant = Instant.now()

// ==========================================
// 6. TESTING EXECUTION ENGINE
// ==========================================

@main def runLedgerPipeline(): Unit =
  val engine = new ProductionLedgerEngine()

  val validTx = Transaction(
    id = UUID.randomUUID(),
    accountId = "acc-9901-usd",
    amount = BigDecimal("1500.50"),
    currency = "USD",
    timestamp = Instant.now()
  )

  val invalidTx = Transaction(
    id = UUID.randomUUID(),
    accountId = "acc-9902-eur",
    amount = BigDecimal("-20.00"),
    currency = "EUR",
    timestamp = Instant.now()
  )

  println("=== TEST 1: Transaksi Normal ===")
  val result1 = engine.process(validTx)
  println(s"Hasil 1: $result1\n")

  println("=== TEST 2: Transaksi Idempotent (Mengulang TX 1) ===")
  val result2 = engine.process(validTx)
  println(s"Hasil 2: $result2 (Harus identik dan tidak menambah sequence)\n")

  println("=== TEST 3: Transaksi Pelanggaran Invariant ===")
  val result3 = engine.process(invalidTx)
  println(s"Hasil 3: $result3\n")

// File: SettlementEngine.scala
package fintech.settlement

import scala.annotation.implicitNotFound

// --- 1. PHANTOM TYPES UNTUK STATE TRANSAKSI ---
sealed trait SettlementState
sealed trait Initialized  extends SettlementState
sealed trait RiskAssessed extends SettlementState
sealed trait Authorized   extends SettlementState

// --- 2. TYPED CURRENCIES & TOKENS ---
sealed trait Currency
sealed trait IDR extends Currency
sealed trait USD extends Currency

final case class Money[C <: Currency](amount: BigDecimal)

// --- 3. METRICS MAPPING VIA MATCH TYPE ---
sealed trait SettlementRail
trait LocalRTGS extends SettlementRail
trait CrossBorderSWIFT extends SettlementRail

type RailReport[R <: SettlementRail] = R match
  case LocalRTGS          => FastSettlementReceipt
  case CrossBorderSWIFT   => SwiftClearingReport

final case class FastSettlementReceipt(refId: String, clearingWindowMs: Long)
final case class SwiftClearingReport(refId: String, intermediaryBic: String, chargesBorneBy: String)

// --- 4. ENGINE DENGAN PHANTOM TYPING & COMPILE-TIME GUARDS ---
final class Transaction[C <: Currency, S <: SettlementState] private (
  val id: String,
  val amount: Money[C],
  val auditLog: Vector[String]
):
  // Helper internal untuk transisi state tanpa alokasi payload baru
  private[settlement] def transition[NextState <: SettlementState](logMessage: String): Transaction[C, NextState] =
    new Transaction[C, NextState](this.id, this.amount, this.auditLog :+ logMessage)

object Transaction:
  // Entry point: Transaksi hanya bisa dibuat dalam status Initialized
  def initiate[C <: Currency](id: String, amount: Money[C]): Transaction[C, Initialized] =
    new Transaction[C, Initialized](id, amount, Vector(s"Transaction $id initiated."))

// Service pemrosesan state
object SettlementWorkflow:

  // Batasan hanya dapat dipanggil jika state = Initialized
  def assessRisk[C <: Currency](tx: Transaction[C, Initialized])(using
    ev: tx.type <:< Transaction[C, Initialized]
  ): Transaction[C, RiskAssessed] =
    println(s"Evaluating credit & AML risk for TX: ${tx.id}")
    tx.transition[RiskAssessed]("AML Risk Assessed: PASSED")

  // Batasan hanya dapat dipanggil jika state = RiskAssessed
  def authorize[C <: Currency](tx: Transaction[C, RiskAssessed]): Transaction[C, Authorized] =
    println(s"Securing cryptographic signatures for TX: ${tx.id}")
    tx.transition[Authorized]("Transaction Authorized by Signers")

  // Eksekusi settlement: Mengembalikan tipe spesifik berdasarkan Rail secara kompilatif
  def executeSettlement[C <: Currency, R <: SettlementRail](
    tx: Transaction[C, Authorized],
    rail: R
  ): RailReport[R] =
    println(s"Executing irrevocable settlement on TX: ${tx.id}")
    rail match
      case _: LocalRTGS =>
        FastSettlementReceipt(tx.id, clearingWindowMs = 250L).asInstanceOf[RailReport[R]]
      case _: CrossBorderSWIFT =>
        SwiftClearingReport(tx.id, intermediaryBic = "DEUTDEDDFXX", chargesBorneBy = "OUR").asInstanceOf[RailReport[R]]

// --- 5. EKSEKUSI RUNTIME DENGAN VALIDASI KOMPILASI ---
@main def runSettlementSystem(): Unit =
  val txInitial = Transaction.initiate[IDR]("TX-90210", Money[IDR](BigDecimal(50_000_000_000L)))
  
  // Transisi State yang Valid
  val txRiskChecked = SettlementWorkflow.assessRisk(txInitial)
  val txAuthorized  = SettlementWorkflow.authorize(txRiskChecked)
  
  // Settlement via LocalRTGS menghasilkan FastSettlementReceipt
  val localRail: LocalRTGS = new LocalRTGS {}
  val localReceipt: FastSettlementReceipt = SettlementWorkflow.executeSettlement(txAuthorized, localRail)
  println(s"Settlement Succeeded: RTGS Reference=${localReceipt.refId}, Window=${localReceipt.clearingWindowMs}ms")

  // Settlement via SWIFT menghasilkan SwiftClearingReport
  val swiftRail: CrossBorderSWIFT = new CrossBorderSWIFT {}
  val swiftReceipt: SwiftClearingReport = SettlementWorkflow.executeSettlement(txAuthorized, swiftRail)
  println(s"Settlement Succeeded: SWIFT Ref=${swiftReceipt.refId}, Intermediary=${swiftReceipt.intermediaryBic}")

  // =========================================================================
  // NEGATIVE COMPILE TESTS (Uncomment untuk membuktikan penolakan kompilator)
  // =========================================================================
  
  // ERROR 1: Mencoba authorize langsung dari Initialized (melompati RiskAssessed)
  // SettlementWorkflow.authorize(txInitial)
  // COMPILER ERROR: Type mismatch. Required: Transaction[IDR, RiskAssessed], Found: Transaction[IDR, Initialized]

  // ERROR 2: Mencoba mengeksekusi settlement pada state yang belum di-otorisasi
  // SettlementWorkflow.executeSettlement(txRiskChecked, localRail)
  // COMPILER ERROR: Type mismatch. Required: Transaction[C, Authorized], Found: Transaction[IDR, RiskAssessed]

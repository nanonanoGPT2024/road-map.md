package com.architect.finance

import java.time.Instant
import scala.annotation.tailrec

// Model domain transaksi immutable
final case class Transaction(
    id: String,
    accountId: String,
    amount: BigDecimal,
    timestamp: Instant,
    isSuspicious: Boolean
)

final case class AuditMetrics(
    totalProcessed: Long,
    flaggedCount: Long,
    totalVolume: BigDecimal,
    peakAnomalyAmount: BigDecimal
)

object FinancialAuditEngine:

  // Generator data stream tak berhingga (mensimulasikan antrean broker Kafka / storage)
  def infiniteTransactionFeed(initialId: Long): LazyList[Transaction] =
    val current = Transaction(
      id = s"TXN-$initialId",
      accountId = s"ACC-${initialId % 100}",
      amount = BigDecimal((initialId * 37 % 5000) + 10),
      timestamp = Instant.now(),
      isSuspicious = (initialId % 13 == 0) // Pola anomali periodik
    )
    current #:: infiniteTransactionFeed(initialId + 1)

  /**
   * Pipeline Analisis:
   * Menggunakan evaluasi bertahap untuk membatasi footprint memori.
   */
  def runAuditPipeline(
      dataSource: LazyList[Transaction],
      maxScanDepth: Int,
      riskThreshold: BigDecimal
  ): Either[String, AuditMetrics] =
    
    // Tahap 1: Batasi kedalaman evaluasi agar tidak meluap ke batas infinite
    val boundedStream = dataSource.take(maxScanDepth)

    // Tahap 2: Transformasi melalui View guna fusi operasi tanpa alokasi intermediat
    val processedView = boundedStream.view
      .filter(_.amount > 50) // Eliminasi transaksi mikro
      .map { txn =>
        if txn.amount > 4500 then txn.copy(isSuspicious = true)
        else txn
      }

    // Tahap 3: Traversal analitik dengan rekursi ekor (Strict Aggregator)
    @tailrec
    def aggregateLoop(
        remaining: Iterator[Transaction],
        acc: AuditMetrics
    ): Either[String, AuditMetrics] =
      if !remaining.hasNext then Right(acc)
      else
        val txn = remaining.next()
        
        // Pemutusan sirkuit darurat (Circuit Breaker Pattern)
        if txn.isSuspicious && txn.amount >= riskThreshold then
          Left(s"CRITICAL RISK BREACH: Terdeteksi transaksi berbahaya ID ${txn.id} sebesar ${txn.amount}")
        else
          val updatedAcc = acc.copy(
            totalProcessed = acc.totalProcessed + 1,
            flaggedCount = if txn.isSuspicious then acc.flaggedCount + 1 else acc.flaggedCount,
            totalVolume = acc.totalVolume + txn.amount,
            peakAnomalyAmount = if txn.isSuspicious && txn.amount > acc.peakAnomalyAmount then txn.amount else acc.peakAnomalyAmount
          )
          aggregateLoop(remaining, updatedAcc)

    val initialMetrics = AuditMetrics(
      totalProcessed = 0L,
      flaggedCount = 0L,
      totalVolume = BigDecimal(0),
      peakAnomalyAmount = BigDecimal(0)
    )

    // Konversi view ke iterator untuk konsumsi single-pass yang aman dari GC Head Retention
    aggregateLoop(processedView.iterator, initialMetrics)

  def main(args: Array[String]): Unit =
    println("Menginisialisasi Engine Audit Finansial...")
    val streamSource = infiniteTransactionFeed(1000L)

    // Kasus 1: Eksekusi normal tanpa memicu circuit breaker
    println("\nEksekusi Skenario 1: Parameter Normal")
    val result1 = runAuditPipeline(streamSource, maxScanDepth = 1000, riskThreshold = 6000)
    result1 match
      case Right(metrics) =>
        println(s"Audit Sukses:")
        println(s" - Transaksi Diproses : ${metrics.totalProcessed}")
        println(s" - Transaksi Flagged  : ${metrics.flaggedCount}")
        println(s" - Total Volume       : Rp ${metrics.totalVolume}")
        println(s" - Puncak Anomali     : Rp ${metrics.peakAnomalyAmount}")
      case Left(error) =>
        println(s"Kegagalan Sistem: $error")

    // Kasus 2: Memicu terminasi dini dengan nilai risk threshold rendah
    println("\nEksekusi Skenario 2: Parameter Risiko Ketat (Early Termination)")
    val result2 = runAuditPipeline(streamSource, maxScanDepth = 1000, riskThreshold = 4600)
    result2 match
      case Right(_)    => println("Audit tidak terduga sukses.")
      case Left(alert) => println(s"Sinyal Interupsi Berhasil Dipicu: $alert")

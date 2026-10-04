// File: src/main/scala/com/enterprise/streaming/fraud/FraudDetectionPipeline.scala
package com.enterprise.streaming.fraud

import org.apache.pekko.actor.typed.ActorSystem
import org.apache.pekko.actor.typed.scaladsl.Behaviors
import org.apache.pekko.stream.*
import org.apache.pekko.stream.scaladsl.*
import org.apache.pekko.Done

import scala.concurrent.{ExecutionContext, Future}
import scala.concurrent.duration.*
import scala.util.control.NonFatal

// Domain Models
case class PaymentTransaction(
    txnId: String,
    accountId: String,
    amount: BigDecimal,
    currency: String,
    timestamp: Long
)

case class FraudAlert(
    txnId: String,
    accountId: String,
    riskScore: Double,
    reason: String
)

case class AuditBatch(records: Seq[PaymentTransaction])

object FraudDetectionPipeline:

  def main(args: Array[String]): Unit =
    implicit val system: ActorSystem[Nothing] = ActorSystem(Behaviors.empty, "FraudPipelineSystem")
    implicit val ec: ExecutionContext = system.executionContext

    // 1. Decider Strategi Penanganan Error (Resilience Strategy)
    val customDecider: Supervision.Decider = {
      case _: IllegalArgumentException =>
        // Data format cacat, lewati record dan lanjutkan stream
        Supervision.Resume
      case NonFatal(e) =>
        System.err.println(s"[SUPERVISOR] Terjadi kegagalan non-fatal: ${e.getMessage}. Melakukan resume stream.")
        Supervision.Resume
      case fatal =>
        System.err.println(s"[SUPERVISOR FATAL] Mematikan stream akibat error kritis: ${fatal.getMessage}")
        Supervision.Stop
    }

    val actorMaterializerSettings = ActorAttributes.supervisionStrategy(customDecider)

    // 2. Mock Source Transaksi Finansial
    val transactionSource: Source[PaymentTransaction, ?] = Source(1 to 1000).map { i =>
      if i == 13 then
        // Injeksi anomali/poison pill data untuk membuktikan error tolerance
        throw new IllegalArgumentException(s"Payload Corrupted pada transaksi #$i")
      PaymentTransaction(
        txnId = s"TXN-$i",
        accountId = s"ACC-${i % 20}",
        amount = BigDecimal(10 * i),
        currency = "USD",
        timestamp = System.currentTimeMillis()
      )
    }

    // 3. Async Flow: Simulasi Lookup Machine Learning Model Asinkron
    def evaluateRiskAsync(txn: PaymentTransaction): Future[(PaymentTransaction, Double)] =
      Future {
        // Simulasi latensi komputasi I/O
        val calculatedScore = if txn.amount > BigDecimal(5000) then 0.95 else 0.15
        (txn, calculatedScore)
      }

    // 4. Sink Khusus
    val alertSink: Sink[FraudAlert, Future[Done]] = Sink.foreach[FraudAlert] { alert =>
      System.err.println(s"⚠️  [SECURITY ALERT] Rekening: ${alert.accountId} | Skor: ${alert.riskScore} | ID: ${alert.txnId}")
    }

    val auditLogSink: Sink[AuditBatch, Future[Done]] = Sink.foreach[AuditBatch] { batch =>
      println(s"📦 [AUDIT STORAGE] Berhasil menyimpan batch sebesar ${batch.records.size} transaksi.")
    }

    // 5. Graph DSL: Konstruksi Topologi Non-Linear Kompleks
    val complexTopologyGraph = GraphDSL.createGraph(alertSink, auditLogSink)(Keep.both) { implicit builder =>
      (alertOut, auditOut) =>
        import GraphDSL.Implicits.*

        // Inlets & Outlets komponen graf
        val broadcast = builder.add(Broadcast[PaymentTransaction](2))

        // Alur Cabang 1: Evaluasi Fraud
        val riskScoreFlow = Flow[PaymentTransaction]
          .mapAsync(parallelism = 4)(evaluateRiskAsync)
          .collect {
            case (txn, score) if score > 0.80 =>
              FraudAlert(txn.txnId, txn.accountId, score, "High transaction value threshold exceeded")
          }

        // Alur Cabang 2: Agregasi Batch
        val batchingFlow = Flow[PaymentTransaction]
          .groupedWithin(n = 50, d = 250.millis)
          .map(AuditBatch.apply)

        // Koneksi Jalur Aliran Topologi
        // Uplink
        val sourceStage = builder.add(transactionSource)
        
        sourceStage ~> broadcast.in

        // Cabang 1 -> Alert Sink
        broadcast.out(0) ~> riskScoreFlow.async ~> alertOut

        // Cabang 2 -> Audit Log Sink
        broadcast.out(1) ~> batchingFlow.async  ~> auditOut

        ClosedShape
    }

    // 6. Eksekusi Topologi dengan Konfigurasi Decider
    val (alertCompletion, auditCompletion) = RunnableGraph
      .fromGraph(complexTopologyGraph)
      .withAttributes(actorMaterializerSettings)
      .run()

    // 7. Monitor Penyelesaian Stream
    val allCompleted = for
      _ <- alertCompletion
      _ <- auditCompletion
    yield Done

    allCompleted.onComplete { result =>
      println(s"=== Eksekusi Seluruh Pipeline Berakhir: $result ===")
      system.terminate()
    }

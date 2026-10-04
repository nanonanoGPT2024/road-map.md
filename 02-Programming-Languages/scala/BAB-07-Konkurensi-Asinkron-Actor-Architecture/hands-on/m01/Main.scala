package com.architecture.concurrency.production

import org.apache.pekko.actor.typed.{ActorRef, ActorSystem, Behavior, SupervisorStrategy}
import org.apache.pekko.actor.typed.scaladsl.{ActorContext, Behaviors}
import org.apache.pekko.util.Timeout
import java.util.concurrent.Executors
import scala.concurrent.{ExecutionContext, Future}
import scala.concurrent.duration.*
import scala.util.{Failure, Success}

// =========================================================================
// 1. DOMAIN MODELS & TYPED PROTOCOLS
// =========================================================================

case class OrderId(value: String) extends AnyVal
case class Money(amount: BigDecimal, currency: String)

sealed trait PaymentResult
case class PaymentSuccess(transactionId: String) extends PaymentResult
case class PaymentDeclined(reason: String) extends PaymentResult

// Protokol Komunikasi Order Actor
sealed trait OrderCommand
final case class InitializeOrder(id: OrderId, total: Money, replyTo: ActorRef[OrderEvent]) extends OrderCommand
private final case class WrappedPaymentResponse(result: PaymentResult) extends OrderCommand
private final case class PaymentFailedTechnical(cause: Throwable) extends OrderCommand

// Protokol Event Output
sealed trait OrderEvent
case class OrderCompleted(orderId: OrderId, txId: String) extends OrderEvent
case class OrderFailed(orderId: OrderId, reason: String) extends OrderEvent

// =========================================================================
// 2. ISOLATED BLOCKING INFRASTRUCTURE LAYER
// =========================================================================

object PaymentGatewayClient {
  // BULKHEADING: Thread pool terisolasi khusus untuk operasi blocking HTTP I/O
  // Mencegah kelaparan thread pada ForkJoinPool milik Actor System utama!
  private val blockingThreadPool = Executors.newFixedThreadPool(16)
  implicit val blockingIoEc: ExecutionContext = ExecutionContext.fromExecutor(blockingThreadPool)

  def executePayment(orderId: OrderId, money: Money): Future[PaymentResult] = Future {
    // Simulasi panggilan jaringan HTTP blocking ke Payment Provider pihak ke-3
    if (money.amount <= 0) {
      PaymentDeclined("Jumlah pembayaran tidak valid.")
    } else if (orderId.value.contains("SIMULATE_IO_CRASH")) {
      throw new java.net.ConnectException("Koneksi gateway eksternal terputus (503 Service Unavailable)")
    } else {
      // Sukses
      PaymentSuccess(s"TX-${java.util.UUID.randomUUID().toString.take(8).toUpperCase}")
    }
  }
}

// =========================================================================
// 3. CORE ORDER ACTOR FSM (FINITE STATE MACHINE)
// =========================================================================

object OrderProcessorActor {

  // Initial State
  def apply(): Behavior[OrderCommand] = waitingForInit()

  private def waitingForInit(): Behavior[OrderCommand] =
    Behaviors.receive { (context, message) =>
      message match {
        case InitializeOrder(id, total, replyTo) =>
          context.log.info(s"[Order: ${id.value}] Memulai proses pesanan senilai ${total.currency} ${total.amount}")
          
          // Memanggil layanan asinkron via dedicated IO EC dan memetakan hasilnya kembali ke diri sendiri
          // Pola: Context.pipeToSelf menjamin respons Future masuk secara thread-safe ke Mailbox aktor
          implicit val ec: ExecutionContext = context.system.executionContext
          
          context.pipeToSelf(PaymentGatewayClient.executePayment(id, total)) {
            case Success(result) => WrappedPaymentResponse(result)
            case Failure(ex)     => PaymentFailedTechnical(ex)
          }

          // Transisi ke State Processing
          processingState(id, replyTo)

        case other =>
          context.log.warn(s"Pesan tidak valid di status uninitialized: $other")
          Behaviors.unhandled
      }
    }

  private def processingState(orderId: OrderId, customerChannel: ActorRef[OrderEvent]): Behavior[OrderCommand] =
    Behaviors.receive { (context, message) =>
      message match {
        case WrappedPaymentResponse(PaymentSuccess(txId)) =>
          context.log.info(s"[Order: ${orderId.value}] Pembayaran SUKSES via TX: $txId")
          customerChannel ! OrderCompleted(orderId, txId)
          Behaviors.stopped // Hentikan siklus hidup aktor pesanan setelah selesai

        case WrappedPaymentResponse(PaymentDeclined(reason)) =>
          context.log.warn(s"[Order: ${orderId.value}] Pembayaran DITOLAK. Alasan: $reason")
          customerChannel ! OrderFailed(orderId, reason)
          Behaviors.stopped

        case PaymentFailedTechnical(cause) =>
          context.log.error(s"[Order: ${orderId.value}] Kesalahan fatal komunikasi gateway: ${cause.getMessage}")
          customerChannel ! OrderFailed(orderId, "Infrastruktur Gateway Mengalami Gangguan")
          // Membiarkan aktor crash untuk di-handle pohon supervisi jika diperlukan, atau stop secara aman
          Behaviors.stopped

        case InitializeOrder(id, _, _) =>
          context.log.warn(s"[Order: ${id.value}] Duplicate Initialize Order diabaikan. Status: IN_PROGRESS.")
          Behaviors.same
      }
    }
}

// =========================================================================
// 4. SUPERVISED RESILIENT ORCHESTRATOR
// =========================================================================

object OrderSystemSupervisor {
  sealed trait SupervisorCommand
  case class ProcessOrder(id: OrderId, total: Money, replyTo: ActorRef[OrderEvent]) extends SupervisorCommand

  def apply(): Behavior[SupervisorCommand] = Behaviors.setup { context =>
    Behaviors.receiveMessage {
      case ProcessOrder(id, total, replyTo) =>
        // Terapkan Supervision Strategy: Restart on RuntimeException with Backoff
        val supervisedBehavior = Behaviors.supervise(OrderProcessorActor())
          .onFailure[RuntimeException](SupervisorStrategy.restartWithBackoff(minBackoff = 200.millis, maxBackoff = 2.seconds, randomFactor = 0.2))

        // Spawn child actor per pesanan (Pola ephemeral worker)
        val childRef = context.spawn(supervisedBehavior, s"order-worker-${id.value}")
        childRef ! InitializeOrder(id, total, replyTo)
        
        Behaviors.same
    }
  }
}

// =========================================================================
// 5. APPLICATION RUNNER
// =========================================================================

object ProductionECommerceApp extends App {
  val rootGuardian: Behavior[Void] = Behaviors.setup { context =>
    val supervisor = context.spawn(OrderSystemSupervisor(), "OrderSupervisor")

    // Event Listener Probe
    val eventProbe = context.spawn(Behaviors.receiveMessage[OrderEvent] {
      case OrderCompleted(id, txId) =>
        context.log.info(s">> NOTIFIKASI KLIEN: Order ${id.value} SELESAI. Ref: $txId")
        Behaviors.same
      case OrderFailed(id, reason) =>
        context.log.error(s">> NOTIFIKASI KLIEN: Order ${id.value} GAGAL! Detail: $reason")
        Behaviors.same
    }, "EventProbeListener")

    // 1. Eksekusi Order Normal
    supervisor ! OrderSystemSupervisor.ProcessOrder(OrderId("ORD-SUCCESS-001"), Money(150000.0, "IDR"), eventProbe)

    // 2. Eksekusi Order Ditolak
    supervisor ! OrderSystemSupervisor.ProcessOrder(OrderId("ORD-DECLINED-002"), Money(-5000.0, "IDR"), eventProbe)

    // 3. Eksekusi Order Network Error
    supervisor ! OrderSystemSupervisor.ProcessOrder(OrderId("SIMULATE_IO_CRASH_003"), Money(250000.0, "IDR"), eventProbe)

    Behaviors.empty
  }

  val system = ActorSystem[Void](rootGuardian, "ECommerceSystem")
  
  // Cleanup hook
  scala.sys.addShutdownHook {
    system.terminate()
  }
}

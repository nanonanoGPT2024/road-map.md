// File: WebhookDispatcher.scala
package advanced.effects.production

import cats.effect._
import cats.effect.std.Semaphore
import cats.syntax.all._
import scala.concurrent.duration._

// 1. Domain Entities
final case class WebhookPayload(id: String, targetUrl: String, body: String)
final case class DispatchResult(id: String, statusCode: Int, durationMs: Long)

// 2. Resource Abstraction: HTTP Client Simulator
trait HttpClient {
  def post(url: String, data: String): IO[Int]
}

object HttpClient {
  // Mengalokasikan client sebagai cats.effect.Resource
  def makeResource(poolName: String): Resource[IO, HttpClient] = {
    val acquire = IO.println(s"[Pool-$poolName] Inisialisasi TCP Socket Pool...") >>
      IO.pure(new HttpClient {
        override def post(url: String, data: String): IO[Int] = {
          for {
            _ <- IO.sleep(100.millis) // Simulasi Network Round-Trip
            _ <- IO.raiseWhen(url.contains("malicious"))(new RuntimeException("Connection refused"))
          } yield 200
        }
      })

    val release: HttpClient => IO[Unit] = _ =>
      IO.println(s"[Pool-$poolName] Menutup seluruh koneksi TCP dan membersihkan memori.")

    Resource.make(acquire)(release)
  }
}

// 3. Dispatcher Service
class WebhookDispatcher private (client: HttpClient, concurrencyLimiter: Semaphore[IO]) {

  def dispatch(payload: WebhookPayload): IO[DispatchResult] = {
    val executeWithMetric = for {
      start  <- IO.realTime
      status <- client.post(payload.targetUrl, payload.body)
      end    <- IO.realTime
      dur     = (end - start).toMillis
    } yield DispatchResult(payload.id, status, dur)

    // Bungkus operasi dengan Concurrency Control (Semaphore) dan Timeout Protection
    concurrencyLimiter.permit.use { _ =>
      executeWithMetric
        .timeout(3.seconds)
        .handleErrorWith { error =>
          IO.println(s"[ERROR] Dispatching Webhook ID ${payload.id} gagal: ${error.getMessage}") >>
            IO.pure(DispatchResult(payload.id, 500, 0L))
        }
    }
  }

  def dispatchBatch(payloads: List[WebhookPayload]): IO[List[DispatchResult]] = {
    // Mengeksekusi seluruh pengiriman webhook secara paralel di atas Fiber terpisah
    payloads.parTraverse(dispatch)
  }
}

object WebhookDispatcher {
  def make(client: HttpClient, maxConcurrentRequests: Long): IO[WebhookDispatcher] =
    Semaphore[IO](maxConcurrentRequests).map(sem => new WebhookDispatcher(client, sem))
}

// 4. Production Application Entry Point
object WebhookApplication extends IOApp.Simple {

  val payloads: List[WebhookPayload] = (1 to 20).toList.map { i =>
    val target = if (i == 13) "http://malicious-node.internal" else s"http://api.partner-$i.com/webhook"
    WebhookPayload(s"evt-$i", target, s"""{"event": "invoice.paid", "seq": $i}""")
  }

  override def run: IO[Unit] = {
    val appResource = for {
      client     <- HttpClient.makeResource("Production-Gateway")
      dispatcher <- Resource.eval(WebhookDispatcher.make(client, maxConcurrentRequests = 5))
    } yield dispatcher

    appResource.use { dispatcher =>
      for {
        _       <- IO.println("--- MEMULAI PENGIRIMAN DISPATCH SECARA PARALEL ---")
        results <- dispatcher.dispatchBatch(payloads)
        _       <- IO.println(s"--- SELESAI. Total Berhasil Diproses: ${results.length} item ---")
        _       <- results.traverse(r => IO.println(s"Result: [${r.id}] Status: ${r.statusCode} Time: ${r.durationMs}ms"))
      } yield ()
    }
  }
}

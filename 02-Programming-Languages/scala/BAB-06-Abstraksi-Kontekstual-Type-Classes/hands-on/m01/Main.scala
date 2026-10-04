package tech.fintech.audit

import java.time.Instant
import java.util.UUID

// --- LINGKUP INFRASTRUKTUR AUDIT KONTEKSTUAL ---
final case class TraceContext(traceId: UUID, correlationId: String, timestamp: Instant)

object ContextProvider:
  // Menyediakan konteks default untuk lingkungan eksekusi
  given currentTraceContext: TraceContext = TraceContext(
    traceId = UUID.randomUUID(),
    correlationId = "CORR-SYS-" + UUID.randomUUID().toString.take(8),
    timestamp = Instant.now()
  )

// --- KONTRAK TYPE CLASS AUDIT DATA (SANITISASI) ---
trait AuditSanitizer[A]:
  def sanitize(data: A): String

object AuditSanitizer:
  def apply[A](using s: AuditSanitizer[A]): AuditSanitizer[A] = s

  // Extension method untuk ergonomi
  extension [A: AuditSanitizer](data: A)
    def toAuditString: String = AuditSanitizer[A].sanitize(data)

  // Primitive Type Instances
  given stringSanitizer: AuditSanitizer[String] with
    def sanitize(data: String): String = data

  given longSanitizer: AuditSanitizer[Long] with
    def sanitize(data: Long): String = data.toString

  given bigDecimalSanitizer: AuditSanitizer[BigDecimal] with
    def sanitize(data: BigDecimal): String = data.setScale(2).toString()

// --- MODEL DOMAIN ENTITAS FINTECH ---
final case class CustomerId(value: String)
final case class AccountNumber(value: String)
final case class SensitiveTransaction(
    txId: String,
    senderAccount: AccountNumber,
    receiverAccount: AccountNumber,
    amount: BigDecimal,
    note: String
)

// --- TYPE CLASS INSTANCES UNTUK DOMAIN ENTITIES ---
object FinancialSanitizerInstances:
  import AuditSanitizer.*

  // Masking nomor rekening: Menampilkan hanya 4 digit terakhir
  given accountSanitizer: AuditSanitizer[AccountNumber] with
    def sanitize(acc: AccountNumber): String =
      val raw = acc.value
      if raw.length <= 4 then "****"
      else s"****-****-${raw.takeRight(4)}"

  // Masking komprehensif transaksi
  given transactionSanitizer(using
      accSanitizer: AuditSanitizer[AccountNumber],
      bdSanitizer: AuditSanitizer[BigDecimal]
  ): AuditSanitizer[SensitiveTransaction] with
    def sanitize(tx: SensitiveTransaction): String =
      s"Transaction[ID=${tx.txId}, " +
      s"Sender=${accSanitizer.sanitize(tx.senderAccount)}, " +
      s"Receiver=${accSanitizer.sanitize(tx.receiverAccount)}, " +
      s"Amount=${bdSanitizer.sanitize(tx.amount)}, Note=CONFIDENTIAL]"

// --- SISTEM AUDIT ENGINE TINGKAT TINGGI ---
object AuditEngine:
  import AuditSanitizer.*

  def logEvent[T: AuditSanitizer](event: T)(using ctx: TraceContext): Unit =
    val sanitizedLog = event.toAuditString
    val logOutput =
      s"{\"timestamp\": \"${ctx.timestamp}\", " +
      s"\"trace_id\": \"${ctx.traceId}\", " +
      s"\"correlation_id\": \"${ctx.correlationId}\", " +
      s"\"payload\": \"$sanitizedLog\"}"
    
    // Output simulasi I/O
    println(s"[SECURE AUDIT PIPELINE] $logOutput")

// --- RUNTIME TESTING & DEMONSTRASI KEAMANAN TIPE ---
@main def runFintechAuditPipeline(): Unit =
  import ContextProvider.given
  import FinancialSanitizerInstances.given
  import AuditSanitizer.*

  val tx = SensitiveTransaction(
    txId = "TXN-90218391",
    senderAccount = AccountNumber("1092837461928374"),
    receiverAccount = AccountNumber("9876543210123456"),
    amount = BigDecimal(15750000.50),
    note = "Pembayaran Layanan Cloud Korporat"
  )

  // Eksekusi Log: traceContext diinjeksi via Context Provider,
  // dan transactionSanitizer diselesaikan oleh kompilator secara otomatis.
  AuditEngine.logEvent(tx)

  // Contoh derivasi koleksi: List otomatis aman diaudit jika elemennya punya instance
  given listSanitizer[A: AuditSanitizer]: AuditSanitizer[List[A]] with
    def sanitize(list: List[A]): String =
      list.map(item => summon[AuditSanitizer[A]].sanitize(item)).mkString("[", ", ", "]")

  val multipleAccounts = List(
    AccountNumber("5555444433332222"),
    AccountNumber("1111222233334444")
  )
  
  AuditEngine.logEvent(multipleAccounts)

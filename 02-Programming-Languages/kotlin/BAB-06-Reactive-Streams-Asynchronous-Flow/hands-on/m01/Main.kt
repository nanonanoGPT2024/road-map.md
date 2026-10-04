package com.architect.reactive.production

import kotlinx.coroutines.*
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.*
import java.math.BigDecimal
import java.util.concurrent.atomic.AtomicLong

// --- CONTRACT & DOMAIN MODELS ---
enum class OrderType { BUY, SELL }

data class TradeTick(
    val transactionId: Long,
    val symbol: String,
    val price: BigDecimal,
    val volume: Double,
    val timestamp: Long
)

// --- PRODUCTION INGESTION SERVICE ---
class MarketDataBroadcaster(
    private val scope: CoroutineScope
) {
    // SharedFlow bertindak sebagai Hot Event-Bus
    private val _rawTickStream = MutableSharedFlow<TradeTick>(
        replay = 0,                                   // Data historis tidak diputar ulang ke subscriber baru
        extraBufferCapacity = 64,                     // Buffer penahan burst-traffic
        onBufferOverflow = BufferOverflow.DROP_OLDEST // Lindungi integritas heap: buang data usang jika lagging
    )
    val rawTickStream: SharedFlow<TradeTick> = _rawTickStream.asSharedFlow()

    fun dispatchSocketEvent(tick: TradeTick) {
        val success = _rawTickStream.tryEmit(tick)
        if (!success) {
            // Log metrik ke sistem observabilitas jika terjadi pembuangan data di buffer hulu
            System.err.println("[Ingestion Warning] Buffer jenuh. Dropping event: ${tick.transactionId}")
        }
    }
}

// --- PERSISTENCE & ANALYTICS PIPELINE ---
class TradeAnalyticsPipeline(
    private val marketBroadcaster: MarketDataBroadcaster,
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO
) {
    private val processedCounter = AtomicLong(0)

    fun initializePipeline(scope: CoroutineScope): Job {
        return marketBroadcaster.rawTickStream
            // 1. Eksekusi filter dan de-duplikasi dasar
            .filter { tick -> tick.volume > 0.05 }
            
            // 2. Transmisi ke buffer internal untuk memisahkan producer rate dari pipeline analysis
            .buffer(capacity = 32, onBufferOverflow = BufferOverflow.SUSPEND)
            
            // 3. Transformasi data I/O bound dialihkan ke I/O Dispatcher
            .flowOn(ioDispatcher)
            
            // 4. Batching / Conflation / Throttling simulation via collectLatest
            // Mengambil aksi terpenting saat terjadi antrian persisten
            .onEach { tick ->
                persistToDatabase(tick)
                val total = processedCounter.incrementAndGet()
                println("[Database] Transaksi tersimpan: ID=${tick.transactionId} | Vol=${tick.volume} | Total=$total")
            }
            .catch { ex ->
                println("[Fatal Error Pipeline] Uncaught exception terdeteksi: ${ex.message}")
                ex.printStackTrace()
            }
            .launchIn(scope) // Menjalankan eksekusi stream terikat pada coroutine lifecycle scope
    }

    private suspend fun persistToDatabase(tick: TradeTick) {
        // Simulasi latensi Disk I/O Database 15ms
        delay(15)
    }
}

// --- SIMULATION HARNESS ---
fun main() = runBlocking {
    val masterScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    val broadcaster = MarketDataBroadcaster(masterScope)
    val pipeline = TradeAnalyticsPipeline(broadcaster, Dispatchers.IO)

    // Inisialisasi pipeline konsumen
    val pipelineJob = pipeline.initializePipeline(masterScope)

    println("=== SIMULASI BURST TRAFFIC TICK BURSA DIMULAI ===")
    
    // Produsen: Mensimulasikan data tick masuk dari 3 thread socket secara bersamaan
    val socketProducers = List(3) { producerIndex ->
        masterScope.launch {
            for (i in 1..50) {
                val tick = TradeTick(
                    transactionId = (producerIndex * 1000L) + i,
                    symbol = "BTC/USDT",
                    price = BigDecimal("65000.00"),
                    volume = (i % 5 + 1) * 0.02, // Sebagian akan difilter (< 0.05)
                    timestamp = System.currentTimeMillis()
                )
                broadcaster.dispatchSocketEvent(tick)
                delay(5) // Produksi super cepat (5ms) melampaui kemampuan DB (15ms)
            }
        }
    }

    // Tunggu produsen selesai membanjiri data
    socketProducers.joinAll()
    
    // Berikan ruang buffer terusan untuk menguras antrian secara kooperatif
    delay(1000)

    println("=== MEMATIKAN PIPELINE SECARA GRACEFUL ===")
    pipelineJob.cancelAndJoin()
    masterScope.cancel()
}

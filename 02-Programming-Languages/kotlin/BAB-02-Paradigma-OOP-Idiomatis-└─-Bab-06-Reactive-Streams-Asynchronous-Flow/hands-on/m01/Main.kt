package com.architect.reactive.production

import kotlinx.coroutines.*
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.*
import java.math.BigDecimal
import java.time.Instant

// 1. Kontrak Data
enum class OrderSide { BUY, SELL }

data class MarketTick(
    val symbol: String,
    val price: BigDecimal,
    val volume: Double,
    val timestamp: Instant
)

// 2. Simulasi External High-Frequency Producer
class HighFrequencyTickerSource {
    fun streamTicks(): Flow<MarketTick> = flow {
        var currentPrice = BigDecimal("50000.00")
        var counter = 0L
        while (true) {
            counter++
            val delta = BigDecimal((Math.random() - 0.49).toString()).setScale(2, java.math.RoundingMode.HALF_UP)
            currentPrice = currentPrice.add(delta)
            
            emit(
                MarketTick(
                    symbol = "BTC/USDT",
                    price = currentPrice,
                    volume = Math.random() * 2.0,
                    timestamp = Instant.now()
                )
            )
            // Simulasi emisi data sangat cepat (1000 event per detik)
            delay(1)
        }
    }.flowOn(Dispatchers.IO)
}

// 3. Trading Engine Orchestrator
class TradingEngineOrchestrator(
    private val tickerSource: HighFrequencyTickerSource,
    private val engineScope: CoroutineScope
) {
    // Hot State Flow untuk menampung data pasar terkini (UI consumption)
    private val _latestPriceState = MutableStateFlow<MarketTick?>(null)
    val latestPriceState: StateFlow<MarketTick?> = _latestPriceState.asStateFlow()

    // Shared Flow untuk event critical ledger (Storage consumption)
    private val _criticalAuditEvents = MutableSharedFlow<MarketTick>(
        replay = 0,
        extraBufferCapacity = 64,
        onBufferOverflow = BufferOverflow.SUSPEND
    )
    val criticalAuditEvents: SharedFlow<MarketTick> = _criticalAuditEvents.asSharedFlow()

    fun startPipeline() {
        val baseStream = tickerSource.streamTicks()
            .shareIn(
                scope = engineScope,
                started = SharingStarted.Eagerly,
                replay = 1
            )

        // Pipeline 1: UI Display Pipeline (Menghindari Lag dengan Conflate)
        engineScope.launch(Dispatchers.Default) {
            baseStream
                .conflate() // Jatuhkan data intermediate jika consumer belum selesai
                .collect { tick ->
                    _latestPriceState.value = tick
                    // Simulasi konsumsi render UI lambat
                    delay(50)
                }
        }

        // Pipeline 2: Ledger Audit Pipeline (Tidak boleh ada data yang hilang)
        engineScope.launch(Dispatchers.IO) {
            baseStream
                .buffer(
                    capacity = 256,
                    onBufferOverflow = BufferOverflow.SUSPEND // Terapkan Backpressure native
                )
                .collect { tick ->
                    persistToAuditLog(tick)
                }
        }
    }

    private suspend fun persistToAuditLog(tick: MarketTick) {
        // Simulasi penulisan IO database yang menelan waktu
        delay(5) 
    }
}

// 4. Driver Verifikasi Sistem
fun main(): Unit = runBlocking {
    val orchestratorScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    val source = HighFrequencyTickerSource()
    val orchestrator = TradingEngineOrchestrator(source, orchestratorScope)

    println("[SYSTEM] Menyalakan Pipeline Trading Engine...")
    orchestrator.startPipeline()

    // Observer UI Consumer (Mengambil pembacaan state conflated)
    val uiWatcher = launch {
        orchestrator.latestPriceState
            .filterNotNull()
            .collect { tick ->
                println("[UI MONITOR] Ticker Terkini: ${tick.price} pada ${tick.timestamp} (Thread: ${Thread.currentThread().name})")
            }
    }

    // Biarkan sistem bekerja selama 500 milidetik untuk simulasi
    delay(500)

    println("[SYSTEM] Menghentikan Engine Pipeline...")
    orchestratorScope.cancel()
    uiWatcher.cancel()
    println("[SYSTEM] Berhasil dihentikan dengan aman.")
}

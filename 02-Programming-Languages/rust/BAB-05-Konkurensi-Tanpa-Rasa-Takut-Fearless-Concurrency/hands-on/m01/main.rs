use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::{mpsc, Arc};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

#[derive(Debug, Clone)]
pub struct MetricPayload {
    pub service_name: &'static str,
    pub latency_ms: f64,
    pub status_code: u16,
}

pub struct TelemetryEngine {
    sender: mpsc::SyncSender<MetricPayload>,
    worker_handles: Vec<JoinHandle<()>>,
    flusher_handle: Option<JoinHandle<usize>>,
    is_running: Arc<AtomicBool>,
    metrics_received: Arc<AtomicUsize>,
}

impl TelemetryEngine {
    pub fn new(channel_capacity: usize) -> Self {
        // Menggunakan sync_channel untuk bounded queue (Backpressure support)
        let (tx, rx) = mpsc::sync_channel::<MetricPayload>(channel_capacity);
        let is_running = Arc::new(AtomicBool::new(true));
        let metrics_received = Arc::new(AtomicUsize::new(0));

        // Inisialisasi Flusher / Consumer Thread
        let flusher_running = Arc::clone(&is_running);
        let flusher_handle = thread::Builder::new()
            .name("telemetry-flusher".to_string())
            .spawn(move || {
                let mut batch_buffer: Vec<MetricPayload> = Vec::with_capacity(1000);
                let mut last_flush = Instant::now();
                let mut total_persisted = 0;

                loop {
                    // Cek ketersediaan data via non-blocking try_recv atau timeout manual
                    match rx.recv_timeout(Duration::from_millis(100)) {
                        Ok(metric) => {
                            batch_buffer.push(metric);
                            // Flush jika batas batch tercapai
                            if batch_buffer.len() >= 1000 {
                                total_persisted += Self::flush_batch(&mut batch_buffer);
                                last_flush = Instant::now();
                            }
                        }
                        Err(mpsc::RecvTimeoutError::Timeout) => {
                            // Flush berbasis interval waktu (misal tiap 500ms)
                            if !batch_buffer.is_empty() && last_flush.elapsed() >= Duration::from_millis(500) {
                                total_persisted += Self::flush_batch(&mut batch_buffer);
                                last_flush = Instant::now();
                            }
                        }
                        Err(mpsc::RecvTimeoutError::Disconnected) => {
                            // Seluruh sender telah mati, kuras sisa buffer
                            if !batch_buffer.is_empty() {
                                total_persisted += Self::flush_batch(&mut batch_buffer);
                            }
                            break;
                        }
                    }

                    // Kondisi pemutusan loop saat shutdown diinisiasi dan channel kosong
                    if !flusher_running.load(Ordering::SeqCst) && rx.try_iter().count() == 0 && batch_buffer.is_empty() {
                        break;
                    }
                }

                println!("[Flusher] Thread dimatikan. Total metrik tersimpan: {}", total_persisted);
                total_persisted
            })
            .expect("Gagal mengalokasikan flusher thread");

        TelemetryEngine {
            sender: tx,
            worker_handles: Vec::new(),
            flusher_handle: Some(flusher_handle),
            is_running,
            metrics_received,
        }
    }

    fn flush_batch(batch: &mut Vec<MetricPayload>) -> usize {
        let count = batch.len();
        // Simulasi penulisan I/O berkecepatan tinggi ke media persisten
        // Di produksi: WAL file write atau socket sinkron
        batch.clear();
        count
    }

    pub fn register_producer(&mut self, id: usize, events_to_generate: usize) {
        let tx_clone = self.sender.clone();
        let running_flag = Arc::clone(&self.is_running);
        let counter_ref = Arc::clone(&self.metrics_received);

        let handle = thread::Builder::new()
            .name(format!("producer-worker-{}", id))
            .spawn(move || {
                for i in 0..events_to_generate {
                    if !running_flag.load(Ordering::Relaxed) {
                        break;
                    }

                    let payload = MetricPayload {
                        service_name: "auth-gateway",
                        latency_ms: 12.4 + (i as f64 * 0.1),
                        status_code: 200,
                    };

                    // Mengirimkan payload. Jika channel penuh, thread produsen akan diblokir
                    // oleh OS scheduler hingga konsumen membersihkan ruang (Backpressure).
                    match tx_clone.send(payload) {
                        Ok(_) => {
                            counter_ref.fetch_add(1, Ordering::Relaxed);
                        }
                        Err(_) => {
                            // Receiver dimatikan, batalkan loop
                            break;
                        }
                    }
                }
            })
            .expect("Gagal mengalokasikan producer thread");

        self.worker_handles.push(handle);
    }

    pub fn shutdown(mut self) -> (usize, usize) {
        println!("[Engine] Memulai prosedur graceful shutdown...");

        // 1. Matikan tanda operasional
        self.is_running.store(false, Ordering::SeqCst);

        // 2. Tunggu semua thread produsen selesai memproduksi dan drop transmitter mereka
        for handle in self.worker_handles {
            let thread_name = handle.thread().name().unwrap_or("unnamed").to_string();
            handle.join().expect("Producer thread mengalami kepanikan");
            println!("[Engine] {} berhasil ditutup.", thread_name);
        }

        // 3. PENTING: Drop instance internal sender milik struct TelemetryEngine
        // Hal ini menurunkan reference count sender channel menjadi 0,
        // memicu status Disconnected pada sisi receiver.
        drop(self.sender);

        // 4. Tunggu flusher thread mengosongkan sisa buffer dan terminasi
        let total_flushed = if let Some(flusher) = self.flusher_handle.take() {
            flusher.join().expect("Flusher thread mengalami kepanikan")
        } else {
            0
        };

        let total_ingested = self.metrics_received.load(Ordering::SeqCst);
        (total_ingested, total_flushed)
    }
}

fn main() {
    let start_time = Instant::now();
    println!("=== MEMULAI ENGINE TELEMETRI INDUSTRI ===");

    // Inisialisasi engine dengan kapasitas bounded queue 500 item
    let mut engine = TelemetryEngine::new(500);

    let num_producers = 4;
    let events_per_producer = 5000;

    println!("Spawning {} thread produsen, masing-masing {} events...", num_producers, events_per_producer);
    for id in 1..=num_producers {
        engine.register_producer(id, events_per_producer);
    }

    // Biarkan engine bekerja selama periode operasional tertentu
    thread::sleep(Duration::from_millis(200));

    // Lakukan graceful shutdown dan validasi konsistensi data
    let (ingested, flushed) = engine.shutdown();

    println!("==========================================");
    println!("Eksekusi Selesai dalam : {:?}", start_time.elapsed());
    println!("Total Metrik Diterima  : {}", ingested);
    println!("Total Metrik Di-flush  : {}", flushed);
    
    assert_eq!(
        ingested, flushed,
        "Anomali Terdeteksi: Data yang diterima tidak sama dengan data yang di-flush!"
    );
    println!("Audit Integritas Data : SUKSES (Zero Data Loss)");
}

use std::cell::RefCell;
use std::collections::HashMap;
use std::fmt::Debug;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, RwLock};

// Representasi paket data mentah
pub struct RawPacket {
    pub id: u64,
    pub payload: Vec<u8>,
}

// Event yang meminjam payload mentah secara zero-copy
pub struct PacketEvent<'a> {
    pub id: u64,
    pub headers: &'a [u8],
    pub body: &'a [u8],
}

// Trait interceptor dengan Higher-Rank Trait Bound logic
pub trait PacketInterceptor: Send + Sync {
    fn name(&self) -> &'static str;
    // HRTB: Interceptor harus mampu menangani PacketEvent dengan lifetime 'any
    fn intercept(&self, event: &PacketEvent<'_>);
}

// Engine Pipeline
pub struct PipelineEngine {
    interceptors: Vec<Box<dyn PacketInterceptor>>,
    metrics: Arc<RwLock<HashMap<&'static str, AtomicU64>>>,
}

impl PipelineEngine {
    pub fn new() -> Self {
        PipelineEngine {
            interceptors: Vec::new(),
            metrics: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    pub fn register_interceptor(&mut self, interceptor: Box<dyn PacketInterceptor>) {
        let name = interceptor.name();
        {
            let mut map = self.metrics.write().unwrap();
            map.entry(name).or_insert_with(|| AtomicU64::new(0));
        }
        self.interceptors.push(interceptor);
    }

    // Mengonsumsi paket mentah, membangun event internal, dan menjalankan HRTB interceptors
    pub fn process_packet(&self, raw: &RawPacket) {
        // Logika zero-copy slicing
        let split_idx = raw.payload.len().min(4);
        let event = PacketEvent {
            id: raw.id,
            headers: &raw.payload[..split_idx],
            body: &raw.payload[split_idx..],
        };

        for interceptor in &self.interceptors {
            interceptor.intercept(&event);
            
            // Catat metrik via interior mutability
            let map = self.metrics.read().unwrap();
            if let Some(counter) = map.get(interceptor.name()) {
                counter.fetch_add(1, Ordering::Relaxed);
            }
        }
    }

    pub fn print_metrics(&self) {
        let map = self.metrics.read().unwrap();
        for (name, count) in map.iter() {
            println!("Interceptor: [{}], Dipanggil: {} kali", name, count.load(Ordering::Relaxed));
        }
    }
}

// Implementasi Plugin Konkret 1: Audit Log
pub struct AuditLogger;
impl PacketInterceptor for AuditLogger {
    fn name(&self) -> &'static str {
        "AuditLogger"
    }

    fn intercept(&self, event: &PacketEvent<'_>) {
        // Parsing aman zero-copy
        println!(
            "[AUDIT] Event ID: {}, Header Bytes: {:?}, Body Len: {}",
            event.id,
            event.headers,
            event.body.len()
        );
    }
}

// Implementasi Plugin Konkret 2: Threat Detector dengan Thread-Local RefCell Buffer
pub struct AnomalyDetector {
    // Penggunaan RefCell untuk interior mutability single-thread inspection
    // Dibungkus thread-safe container untuk pemenuhan trait Send + Sync
    threat_cache: Arc<RwLock<RefCell<Vec<u64>>>>,
}

impl AnomalyDetector {
    pub fn new() -> Self {
        AnomalyDetector {
            threat_cache: Arc::new(RwLock::new(RefCell::new(Vec::new()))),
        }
    }
}

impl PacketInterceptor for AnomalyDetector {
    fn name(&self) -> &'static str {
        "AnomalyDetector"
    }

    fn intercept(&self, event: &PacketEvent<'_>) {
        // Deteksi pola mencurigakan pada header
        if event.headers.contains(&0xFF) {
            println!("[ALERT] Pola anomali terdeteksi pada Paket ID: {}", event.id);
            let lock = self.threat_cache.write().unwrap();
            let mut cache = lock.borrow_mut();
            cache.push(event.id);
        }
    }
}

// Eksekusi Pipeline
fn main() {
    let mut engine = PipelineEngine::new();
    engine.register_interceptor(Box::new(AuditLogger));
    engine.register_interceptor(Box::new(AnomalyDetector::new()));

    let packet_a = RawPacket {
        id: 1001,
        payload: vec![0x01, 0x02, 0x03, 0x04, 0xAA, 0xBB],
    };

    let packet_b = RawPacket {
        id: 1002,
        payload: vec![0xFF, 0x02, 0x00, 0x01, 0xCC],
    };

    println!("--- MEMULAI PEMROSESAN PAKET ---");
    engine.process_packet(&packet_a);
    engine.process_packet(&packet_b);

    println!("\n--- METRIK SISTEM ---");
    engine.print_metrics();
}

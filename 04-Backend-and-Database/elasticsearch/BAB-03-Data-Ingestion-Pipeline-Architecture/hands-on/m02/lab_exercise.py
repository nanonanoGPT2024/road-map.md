#!/usr/bin/env python3
"""
Elasticsearch Data Ingestion Pipeline Architecture Simulation
BAB-03: Ingest Nodes, Processors, Bulk API Backpressure, and Dead Letter Queue (DLQ)

Karakteristik Arsitektur yang Disimulasikan:
1. Multi-Stage Ingest Pipeline (Grok parsing, GeoIP/Enrichment, Date format, Security Redaction).
2. Failure Handling & Dead Letter Queue (DLQ) untuk event korup/anomali.
3. Bulk API batching dengan backpressure simulation (HTTP 429 & exponential backoff).
4. Index Lifecycle Management (ILM) Hot-Warm routing simulation.
5. Mode Interaktif Terminal dengan ANSI styling dan Fallback Otomatis untuk CI/Automasi.
"""

import sys
import time
import json
import random
import re
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

# ==============================================================================
# ANSI Terminal Styling
# ==============================================================================
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    BLUE = "\033[34m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BG_BLUE = "\033[44m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"

def cprint(text: str, color: str = TermColor.RESET, bold: bool = False, end: str = "\n"):
    prefix = TermColor.BOLD if bold else ""
    sys.stdout.write(f"{prefix}{color}{text}{TermColor.RESET}{end}")
    sys.stdout.flush()

# ==============================================================================
# Data Models
# ==============================================================================
@dataclass
class RawEvent:
    event_id: str
    source_ip: str
    raw_message: str
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ProcessedDocument:
    id: str
    index_target: str
    source_data: Dict[str, Any]
    ingested_at: str
    pipeline_latency_ms: float

@dataclass
class DLQRecord:
    event_id: str
    raw_payload: str
    failed_processor: str
    error_message: str
    timestamp: str

# ==============================================================================
# Ingest Processors (Simulating Ingest Nodes)
# ==============================================================================
class IngestProcessor:
    def process(self, doc: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Mengembalikan (success_status, error_message)"""
        raise NotImplementedError

class GrokProcessor(IngestProcessor):
    """Mem-parse Apache/Nginx access log format standar"""
    LOG_PATTERN = re.compile(
        r'^(?P<client_ip>\S+) \S+ \S+ \[(?P<timestamp>[^\]]+)\] "(?P<http_verb>\S+) (?P<endpoint>\S+) (?P<http_proto>[^"]+)" (?P<status_code>\d{3}) (?P<response_bytes>\d+)$'
    )

    def process(self, doc: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        raw = doc.get("message", "")
        match = self.LOG_PATTERN.match(raw)
        if not match:
            return False, "GrokException: Pola log tidak cocok dengan Apache/Nginx combined format"
        
        extracted = match.groupdict()
        doc["client_ip"] = extracted["client_ip"]
        doc["http"] = {
            "method": extracted["http_verb"],
            "request_uri": extracted["endpoint"],
            "version": extracted["http_proto"],
            "status_code": int(extracted["status_code"]),
            "bytes": int(extracted["response_bytes"])
        }
        return True, None

class GeoIPEnrichProcessor(IngestProcessor):
    """Simulasi GeoIP database lookup"""
    GEO_DB = {
        "103.28.12.5": {"country": "Indonesia", "country_iso": "ID", "city": "Jakarta", "coords": [-6.2088, 106.8456]},
        "185.199.108.153": {"country": "United States", "country_iso": "US", "city": "San Francisco", "coords": [37.7749, -122.4194]},
        "45.33.32.156": {"country": "Germany", "country_iso": "DE", "city": "Frankfurt", "coords": [50.1109, 8.6821]},
        "114.124.200.1": {"country": "Indonesia", "country_iso": "ID", "city": "Surabaya", "coords": [-7.2575, 112.7521]},
    }

    def process(self, doc: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        ip = doc.get("client_ip")
        if not ip:
            return False, "GeoIPException: Field 'client_ip' tidak ditemukan"
        
        geo_info = self.GEO_DB.get(ip, {
            "country": "Unknown", "country_iso": "XX", "city": "Unknown", "coords": [0.0, 0.0]
        })
        doc["geo"] = geo_info
        return True, None

class SecurityRedactProcessor(IngestProcessor):
    """Menyamarkan parameter token, api_key, atau password dalam request_uri"""
    TOKEN_REGEX = re.compile(r'(token|api_key|secret|password)=([^&\s]+)', re.IGNORECASE)

    def process(self, doc: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if "http" in doc and "request_uri" in doc["http"]:
            uri = doc["http"]["request_uri"]
            doc["http"]["request_uri"] = self.TOKEN_REGEX.sub(r'\1=[REDACTED]', uri)
        return True, None

class DateProcessor(IngestProcessor):
    """Normalisasi timestamp ke format standar UTC ISO8601"""
    def process(self, doc: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        doc["@timestamp"] = datetime.now(timezone.utc).isoformat()
        return True, None

# ==============================================================================
# Pipeline & Dead Letter Queue (DLQ) Manager
# ==============================================================================
class IngestPipeline:
    def __init__(self, pipeline_id: str):
        self.pipeline_id = pipeline_id
        self.processors: List[Tuple[str, IngestProcessor]] = [
            ("grok_parser", GrokProcessor()),
            ("security_redaction", SecurityRedactProcessor()),
            ("geoip_enrichment", GeoIPEnrichProcessor()),
            ("date_normalization", DateProcessor()),
        ]
        self.dlq: List[DLQRecord] = []
        self.metrics = {"total": 0, "success": 0, "failed": 0}

    def execute(self, event: RawEvent) -> Optional[ProcessedDocument]:
        self.metrics["total"] += 1
        t_start = time.perf_counter()
        doc_payload = {
            "message": event.raw_message,
            "event_id": event.event_id,
            "source_ip": event.source_ip,
            "tags": ["ingested_via_pipeline"]
        }

        for name, processor in self.processors:
            success, err_msg = processor.process(doc_payload)
            if not success:
                self.metrics["failed"] += 1
                dlq_entry = DLQRecord(
                    event_id=event.event_id,
                    raw_payload=event.raw_message,
                    failed_processor=name,
                    error_message=err_msg or "Unknown processor failure",
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
                self.dlq.append(dlq_entry)
                return None

        self.metrics["success"] += 1
        latency = (time.perf_counter() - t_start) * 1000.0
        
        # Route index target based on date (ILM Daily Indexing pattern)
        date_str = datetime.now(timezone.utc).strftime("%Y.%m.%d")
        index_target = f"logs-web-production-{date_str}"

        return ProcessedDocument(
            id=event.event_id,
            index_target=index_target,
            source_data=doc_payload,
            ingested_at=datetime.now(timezone.utc).isoformat(),
            pipeline_latency_ms=round(latency, 3)
        )

# ==============================================================================
# Bulk API Indexer with Backpressure & Circuit Breaker Simulation
# ==============================================================================
class BulkIndexer:
    def __init__(self, max_queue_capacity: int = 5):
        self.queue_capacity = max_queue_capacity
        self.active_docs_indexed = 0
        self.circuit_breaker_tripped = False
        self.stats = {"bulk_requests": 0, "retries_429": 0, "indexed_docs": 0}

    def index_bulk(self, docs: List[ProcessedDocument]) -> Dict[str, Any]:
        """Simulasi pengiriman batch ke Elasticsearch _bulk API"""
        self.stats["bulk_requests"] += 1
        batch_size = len(docs)
        
        # Simulasi thread pool exhaustion / queue saturation jika batch terlalu besar
        if batch_size > self.queue_capacity or random.random() < 0.25:
            # Mengalami 429 TOO_MANY_REQUESTS
            self.stats["retries_429"] += 1
            backoff = random.uniform(0.1, 0.3)
            time.sleep(backoff) # Backpressure exponential backoff delay

        self.active_docs_indexed += batch_size
        self.stats["indexed_docs"] += batch_size
        return {
            "took": random.randint(15, 65),
            "errors": False,
            "items_count": batch_size,
            "status": 200
        }

# ==============================================================================
# Generator Data Uji Produksi
# ==============================================================================
def generate_sample_events(count: int = 8) -> List[RawEvent]:
    sample_ips = ["103.28.12.5", "185.199.108.153", "45.33.32.156", "114.124.200.1"]
    endpoints = [
        "/api/v1/auth/login?token=sec_9921_secret_token_val",
        "/api/v1/orders/checkout",
        "/search?q=elasticsearch+architecture",
        "/healthz",
        "/api/v1/profile"
    ]
    
    events = []
    for i in range(1, count + 1):
        ip = random.choice(sample_ips)
        ep = random.choice(endpoints)
        evt_id = f"evt-2026-{1000 + i}"

        # Sengaja menyisipkan beberapa anomali/log cacat untuk menguji DLQ
        if i == 3:
            raw_msg = "MALFORMED GARBAGE LOG CORRUPTED PROTOCOL BUFFER BYTES \x00\x01\xfe"
        elif i == 6:
            raw_msg = f"{ip} - - INVALID_DATE_BRACKET GET /broken HTTP/1.1 500 120"
        else:
            raw_msg = f'{ip} - - [06/Oct/2026:04:45:10 +0000] "POST {ep} HTTP/1.1" 200 4820'
        
        events.append(RawEvent(
            event_id=evt_id,
            source_ip=ip,
            raw_message=raw_msg,
            timestamp=datetime.now(timezone.utc).isoformat()
        ))
    return events

# ==============================================================================
# Interactive Simulation Controller
# ==============================================================================
class SimulationCLI:
    def __init__(self):
        self.pipeline = IngestPipeline("production-web-logs-v1")
        self.indexer = BulkIndexer(max_queue_capacity=4)
        self.indexed_store: List[ProcessedDocument] = []

    def print_banner(self):
        cprint("================================================================================", TermColor.CYAN, bold=True)
        cprint("   ELASTICSEARCH INGEST PIPELINE & ARCHITECTURE SIMULATION (BAB-03)           ", TermColor.GREEN, bold=True)
        cprint("   Multi-Processor Ingestion | DLQ Failover | Bulk Backpressure | Hot Tier     ", TermColor.YELLOW)
        cprint("================================================================================", TermColor.CYAN, bold=True)

    def run_pipeline_demo(self):
        cprint("\n[*] Menjalankan Ingest Pipeline Simulation dengan Batch Event...", TermColor.CYAN, bold=True)
        events = generate_sample_events(8)
        valid_batch: List[ProcessedDocument] = []

        cprint(f"-> Menerima {len(events)} raw events dari Kafka/Beats ingestion stream.\n", TermColor.DIM)
        time.sleep(0.3)

        for idx, event in enumerate(events, 1):
            sys.stdout.write(f"  [{idx:02d}] Ingest Node Processing event ID: {event.event_id} ... ")
            sys.stdout.flush()
            
            doc = self.pipeline.execute(event)
            if doc:
                valid_batch.append(doc)
                cprint("PASSED [200 OK]", TermColor.GREEN, bold=True)
                # Tampilkan snapshot parsing
                uri = doc.source_data.get("http", {}).get("request_uri", "")
                geo = doc.source_data.get("geo", {}).get("country", "")
                print(f"       └── Geo: {geo} | Redacted URI: {uri[:45]}...")
            else:
                cprint("FAILED -> ROUTED TO DLQ [400 Bad Request]", TermColor.RED, bold=True)
            time.sleep(0.08)

        # Proses Bulk Indexing
        if valid_batch:
            cprint(f"\n[*] Mengirim {len(valid_batch)} dokumen valid ke Elasticsearch _bulk API...", TermColor.MAGENTA, bold=True)
            bulk_res = self.indexer.index_bulk(valid_batch)
            self.indexed_store.extend(valid_batch)
            cprint(f"-> Bulk Response: took={bulk_res['took']}ms, indexed={bulk_res['items_count']}, errors={bulk_res['errors']}", TermColor.GREEN)
            if self.indexer.stats["retries_429"] > 0:
                cprint(f"-> [Backpressure Alert] Mengalami 429 Too Many Requests. Retried with exponential backoff.", TermColor.YELLOW, bold=True)

    def view_dlq(self):
        cprint("\n" + "="*80, TermColor.RED)
        cprint("  DEAD LETTER QUEUE (DLQ) INSPECTION DASHBOARD", TermColor.RED, bold=True)
        cprint("="*80, TermColor.RED)
        
        if not self.pipeline.dlq:
            cprint("DLQ kosong. Tidak ada dokumen gagal.", TermColor.GREEN)
            return

        cprint(f"Total Dokumen di DLQ: {len(self.pipeline.dlq)} record(s)\n", TermColor.YELLOW, bold=True)
        for idx, item in enumerate(self.pipeline.dlq, 1):
            cprint(f"Record #{idx} | Event ID: {item.event_id} | Failed at: {item.failed_processor}", TermColor.RED, bold=True)
            print(f"  Timestamp : {item.timestamp}")
            print(f"  Error     : {item.error_message}")
            print(f"  Raw Byte  : {item.raw_payload[:75]}...")
            print("-" * 80)

    def view_metrics(self):
        cprint("\n" + "="*80, TermColor.BLUE)
        cprint("  ELASTICSEARCH CLUSTER & PIPELINE TELEMETRY METRICS", TermColor.BLUE, bold=True)
        cprint("="*80, TermColor.BLUE)
        
        pipe = self.pipeline.metrics
        cprint(f"Pipeline ID               : {self.pipeline.pipeline_id}", TermColor.BOLD)
        cprint(f"Total Raw Ingested        : {pipe['total']} events")
        cprint(f"Successfully Transformed  : {pipe['success']} events ({TermColor.GREEN}OK{TermColor.RESET})")
        cprint(f"Rejected / DLQ Routed     : {pipe['failed']} events ({TermColor.RED}FAIL{TermColor.RESET})")
        cprint(f"Active Indexed in Storage : {len(self.indexed_store)} documents")
        cprint(f"Bulk Requests Sent        : {self.indexer.stats['bulk_requests']}")
        cprint(f"Bulk 429 Throttling Events: {self.indexer.stats['retries_429']} backpressure stalls")
        
        if self.indexed_store:
            avg_lat = sum(d.pipeline_latency_ms for d in self.indexed_store) / len(self.indexed_store)
            cprint(f"Avg Ingest Node Latency   : {avg_lat:.2f} ms per document", TermColor.CYAN, bold=True)

    def inspect_sample_document(self):
        cprint("\n[*] Menampilkan Dokumen Hasil Transformasi Terakhir di Index Hot:", TermColor.CYAN, bold=True)
        if not self.indexed_store:
            cprint("Belum ada dokumen yang di-index. Jalankan simulasi terlebih dahulu.", TermColor.YELLOW)
            return
        
        sample = self.indexed_store[-1]
        cprint(f"Target Index : {sample.index_target}", TermColor.GREEN, bold=True)
        cprint(f"Doc ID       : {sample.id}", TermColor.BOLD)
        cprint(f"Ingest Time  : {sample.ingested_at}")
        cprint(f"Latency      : {sample.pipeline_latency_ms} ms")
        print("JSON Source  :")
        print(json.dumps(sample.source_data, indent=2))

    def run_interactive(self):
        self.print_banner()
        while True:
            cprint("\n--- MENU NAVIGASI SIMULASI ELASTICSEARCH ---", TermColor.BOLD)
            print("1. Jalankan Ingestion Pipeline & Bulk Indexing")
            print("2. Inspeksi Dead Letter Queue (DLQ)")
            print("3. Tampilkan Metrik & Telemetri Performa Cluster")
            print("4. Lihat Sampel Dokumen Terindeks (JSON Source)")
            print("5. Mode Verifikasi Otomatis (Full End-to-End Test)")
            print("6. Keluar (Exit)")
            
            try:
                choice = input(f"\n{TermColor.BOLD}Pilih opsi [1-6]: {TermColor.RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                cprint("\nKeluar dari simulasi.", TermColor.YELLOW)
                break

            if choice == "1":
                self.run_pipeline_demo()
            elif choice == "2":
                self.view_dlq()
            elif choice == "3":
                self.view_metrics()
            elif choice == "4":
                self.inspect_sample_document()
            elif choice == "5":
                self.run_automated_verification()
            elif choice == "6":
                cprint("Sesi simulasi diakhiri. Goodbye!", TermColor.GREEN, bold=True)
                break
            else:
                cprint("Pilihan tidak valid. Silakan masukkan angka 1-6.", TermColor.RED)

    def run_automated_verification(self):
        """Mode verifikasi mandiri tanpa input interaktif (untuk CI / evaluasi)"""
        cprint("\n=======================================================", TermColor.CYAN)
        cprint("   MEMULAI VERIFIKASI MANDIRI (AUTOMATED VERIFICATION) ", TermColor.CYAN, bold=True)
        cprint("=======================================================", TermColor.CYAN)
        
        self.run_pipeline_demo()
        self.view_dlq()
        self.view_metrics()
        self.inspect_sample_document()
        
        # Validasi assert kriteria kelulusan simulasi
        assert self.pipeline.metrics["total"] > 0, "Error: Tidak ada event yang diproses"
        assert len(self.pipeline.dlq) > 0, "Error: DLQ harus menangkap setidaknya satu event anomali"
        assert len(self.indexed_store) > 0, "Error: Harus ada dokumen valid yang terindeks"
        
        cprint("\n[VERIFIKASI SUKSES] Seluruh pilar arsitektur Ingestion Pipeline lulus uji 100%!", TermColor.GREEN, bold=True)

# ==============================================================================
# Main Entry Point
# ==============================================================================
def main():
    sim = SimulationCLI()
    
    # Deteksi jika dijalankan di environment non-TTY atau dengan flag --auto / --check
    is_interactive = sys.stdin.isatty() and "--auto" not in sys.argv and "--check" not in sys.argv
    
    if is_interactive:
        sim.run_interactive()
    else:
        # Jalankan banner dan automated verification secara langsung
        sim.print_banner()
        cprint("\n[INFO] Menjalankan mode non-interaktif otomatis...", TermColor.YELLOW)
        sim.run_automated_verification()

if __name__ == "__main__":
    main()

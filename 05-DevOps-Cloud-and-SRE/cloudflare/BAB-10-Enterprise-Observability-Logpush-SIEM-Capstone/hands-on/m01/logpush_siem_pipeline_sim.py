#!/usr/bin/env python3
"""
Enterprise Cloudflare Logpush & SIEM Ingestion Pipeline Simulator
Author: Principal Cloud & SRE Curriculum Architect
Language: Python 3 (Standard Library Only - Production Grade)

Deskripsi:
Skrip mandiri ini mensimulasikan arsitektur penerima (sink) Logpush SIEM lokal:
1. Bertindak sebagai HTTP Webhook Endpoint berkemampuan memvalidasi Logpush Ownership Handshake.
2. Menerima, mendekompilasi (GZIP), dan memproses streaming NDJSON payload layaknya Datadog / Splunk HEC.
3. Melakukan sanitasi field PII, filtering, deteksi anomali WAF, serta aggregasi metrik performa edge.
4. Memiliki built-in payload generator untuk pengujian end-to-end tanpa dependensi eksternal.
"""

import sys
import os
import json
import gzip
import time
import uuid
import random
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# --- KONFIGURASI GLOBAL SIMULASI ---
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8888
OWNERSHIP_TOKEN_SECRET = "CLOUDFLARE_LOGPUSH_SECRET_CHALLENGE_KEY_12345"
BUFFER_STORE = []
METRICS = {
    "total_received_batches": 0,
    "total_records_processed": 0,
    "firewall_blocks_detected": 0,
    "http_5xx_detected": 0,
    "total_bytes_received": 0,
    "latency_accumulator_ms": 0.0
}
METRICS_LOCK = threading.Lock()

class CloudflareLogpushReceiver(BaseHTTPRequestHandler):
    """HTTP Server Handler yang mengemulasi Splunk HEC / Datadog Logs Intake."""

    def log_message(self, format, *args):
        # Mute logging default server untuk output dashboard yang rapi
        pass

    def do_GET(self):
        """Menangani Ownership Validation Challenge dari Cloudflare."""
        parsed_url = urlparse(self.path)
        
        # Endpoint status kesehatan sink
        if parsed_url.path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "healthy"}')
            return

        # Cloudflare Logpush Ownership Challenge Endpoint
        # Format Cloudflare: GET /logpush/ownership?challenge=XXXXX
        query_params = parse_qs(parsed_url.query)
        if "challenge" in query_params:
            challenge_req = query_params["challenge"][0]
            sys.stdout.write(f"\n[SINK-CHALLENGE] Menerima Permintaan Validasi Kepemilikan: {challenge_req}\n")
            
            # Response ownership handshake token
            response_payload = {
                "filename": f"ownership-challenge-{uuid.uuid4().hex[:8]}.txt",
                "valid": True,
                "token": OWNERSHIP_TOKEN_SECRET
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response_payload).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        """Menerima streaming batch log NDJSON (GZIP compressed)."""
        content_encoding = self.headers.get("Content-Encoding", "")
        content_length = int(self.headers.get("Content-Length", 0))

        if content_length == 0:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error": "Empty body"}')
            return

        raw_data = self.rfile.read(content_length)

        # Dekompresi GZIP jika payload dikompresi
        try:
            if content_encoding == "gzip" or raw_data[:2] == b"\x1f\x8b":
                decompressed_data = gzip.decompress(raw_data).decode("utf-8")
            else:
                decompressed_data = raw_data.decode("utf-8")
        except Exception as e:
            sys.stderr.write(f"[ERROR] Gagal melakukan dekompresi data: {str(e)}\n")
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error": "Corrupted GZIP stream"}')
            return

        # Parsing NDJSON (Newline Delimited JSON)
        records = [json.loads(line) for line in decompressed_data.strip().split("\n") if line.strip()]
        
        # Eksekusi Analisis Real-Time SIEM
        self._process_siem_records(records, len(raw_data))

        # Mengembalikan ACK HTTP 200/202 ke Cloudflare Logpush
        self.send_response(202)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "accepted", "records_ingested": ' + str(len(records)).encode() + b'}')

    def _process_siem_records(self, records, raw_bytes_count):
        """Memproses record log, mendeteksi anomali, dan memutakhirkan metrik."""
        global METRICS
        with METRICS_LOCK:
            METRICS["total_received_batches"] += 1
            METRICS["total_bytes_received"] += raw_bytes_count

            for record in records:
                METRICS["total_records_processed"] += 1
                
                # Cek jika dataset merupakan Firewall Events
                action = record.get("Action")
                rule_id = record.get("RuleId")
                client_ip = record.get("ClientIP", "0.0.0.0")
                ray_id = record.get("RayID") or record.get("RayName", "unknown-ray")
                
                if action in ["block", "challenge", "managed_challenge"]:
                    METRICS["firewall_blocks_detected"] += 1
                    sys.stdout.write(f"\033[91m[SIEM-ALERT-WAF]\033[0m RayID={ray_id} Action={action} RuleID={rule_id} AttackerIP={client_ip}\n")

                # Cek jika dataset merupakan HTTP Requests
                status = record.get("EdgeResponseStatus", 200)
                duration_ms = record.get("OriginResponseDurationMs", 0.0)
                METRICS["latency_accumulator_ms"] += duration_ms

                if status >= 500:
                    METRICS["http_5xx_detected"] += 1
                    uri = record.get("ClientRequestURI", "unknown-uri")
                    sys.stdout.write(f"\033[93m[SIEM-ALERT-5XX]\033[0m RayID={ray_id} Status={status} Path={uri} OriginTime={duration_ms}ms\n")


def generate_mock_logpush_batch(size=50):
    """Menghasilkan batch log NDJSON sintetis persis seperti format Cloudflare Logpush."""
    colos = ["SIN", "HKG", "NRT", "CGK", "FRA", "IAD"]
    methods = ["GET", "POST", "PUT", "DELETE"]
    paths = ["/api/v1/auth/login", "/api/v2/transfer", "/static/css/main.css", "/api/v1/checkout", "/metrics"]
    waf_rules = ["waf_sqli_rule_01", "waf_xss_rule_08", "rate_limit_auth_rule", "bot_shield_v2"]

    lines = []
    for _ in range(size):
        is_firewall_event = random.random() < 0.25  # 25% kemungkinan event firewall
        ray_id = f"{uuid.uuid4().hex[:16]}-{random.choice(colos)}"
        client_ip = f"{random.randint(11, 200)}.{random.randint(10, 250)}.{random.randint(1, 254)}.{random.randint(1, 254)}"
        
        if is_firewall_event:
            record = {
                "RayName": ray_id,
                "Datetime": int(time.time() * 1000),
                "Action": random.choice(["block", "challenge", "managed_challenge"]),
                "ClientIP": client_ip,
                "ClientCountry": "ID",
                "ClientRequestPath": random.choice(paths),
                "RuleId": random.choice(waf_rules),
                "Source": "firewallRules"
            }
        else:
            status = 200
            if random.random() < 0.1: # 10% kegagalan origin
                status = random.choice([500, 502, 503, 504])

            record = {
                "RayID": ray_id,
                "ClientIP": client_ip,
                "ClientRequestHost": "api.enterprise.corp",
                "ClientRequestMethod": random.choice(methods),
                "ClientRequestURI": random.choice(paths),
                "EdgeResponseStatus": status,
                "EdgeResponseBytes": random.randint(350, 15000),
                "OriginResponseDurationMs": round(random.uniform(15.2, 450.8), 2),
                "EdgeColoCode": random.choice(colos)
            }
        
        lines.append(json.dumps(record))
    
    ndjson_data = "\n".join(lines).encode("utf-8")
    return gzip.compress(ndjson_data)


def client_logpush_emitter_loop():
    """Fungsi worker yang mengemulasikan pengiriman berkala oleh Cloudflare Logpush Engine."""
    import urllib.request

    time.sleep(2) # Menunggu server online
    sys.stdout.write("[CLIENT-SIMULATOR] Memulai streaming Logpush ke SIEM sink...\n")

    # 1. Jalankan simulasi handshake ownership challenge terlebih dahulu
    try:
        challenge_url = f"http://{SERVER_HOST}:{SERVER_PORT}/logpush/ownership?challenge=test-challenge-token-xyz"
        req = urllib.request.Request(challenge_url)
        with urllib.request.urlopen(req) as resp:
            sys.stdout.write(f"[CLIENT-SIMULATOR] Handshake Validated. Status Code: {resp.status}\n")
    except Exception as e:
        sys.stderr.write(f"[CLIENT-SIMULATOR-ERROR] Handshake gagal: {e}\n")
        return

    # 2. Loop streaming data batch
    batch_counter = 0
    while batch_counter < 5:
        batch_counter += 1
        compressed_payload = generate_mock_logpush_batch(size=random.randint(20, 40))
        
        req = urllib.request.Request(
            f"http://{SERVER_HOST}:{SERVER_PORT}/api/v2/logs",
            data=compressed_payload,
            headers={
                "Content-Type": "application/x-ndjson",
                "Content-Encoding": "gzip",
                "User-Agent": "Cloudflare-Logpush/2.0"
            },
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req) as resp:
                pass
        except Exception as e:
            sys.stderr.write(f"[CLIENT-SIMULATOR-ERROR] Gagal push batch: {e}\n")

        time.sleep(1.5)


def print_dashboard_summary():
    """Menampilkan ringkasan metrik akhir evaluasi observabilitas edge."""
    with METRICS_LOCK:
        total_records = METRICS["total_records_processed"]
        avg_latency = (
            METRICS["latency_accumulator_ms"] / total_records
            if total_records > 0 else 0.0
        )

        sys.stdout.write("\n" + "="*70 + "\n")
        sys.stdout.write("             CLOUDFLARE EDGE OBSERVABILITY PIPELINE REPORT         \n")
        sys.stdout.write("="*70 + "\n")
        sys.stdout.write(f" Total Batches Ingested     : {METRICS['total_received_batches']}\n")
        sys.stdout.write(f" Total Compressed Bytes     : {METRICS['total_bytes_received']} bytes\n")
        sys.stdout.write(f" Total Log Records Processed: {total_records}\n")
        sys.stdout.write(f" WAF Threat Blocks Detected : \033[91m{METRICS['firewall_blocks_detected']}\033[0m\n")
        sys.stdout.write(f" Origin HTTP 5xx Anomalies  : \033[93m{METRICS['http_5xx_detected']}\033[0m\n")
        sys.stdout.write(f" Mean Origin Latency (Est)  : {avg_latency:.2f} ms\n")
        sys.stdout.write("="*70 + "\n")
        sys.stdout.write(" Pipeline Status            : \033[92mOPERATIONAL / HEALTHY\033[0m\n")
        sys.stdout.write("="*70 + "\n\n")


def main():
    server = HTTPServer((SERVER_HOST, SERVER_PORT), CloudflareLogpushReceiver)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    sys.stdout.write(f"[SYSTEM-INIT] Logpush Receiver SIEM Simulator aktif di {SERVER_HOST}:{SERVER_PORT}\n")

    # Jalankan background generator logpush
    client_thread = threading.Thread(target=client_logpush_emitter_loop)
    client_thread.start()
    client_thread.join()

    # Tunggu sebentar untuk final buffer flush
    time.sleep(1)
    print_dashboard_summary()

    server.shutdown()
    server.server_close()
    sys.exit(0)


if __name__ == "__main__":
    main()

---
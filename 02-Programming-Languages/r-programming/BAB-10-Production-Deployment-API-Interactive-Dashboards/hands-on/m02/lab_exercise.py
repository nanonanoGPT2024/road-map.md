#!/usr/bin/env python3
"""
Lab Hands-on: Production Deployment, API, & Interactive Dashboards (R-Programming Deep Dive)
Topic: Simulating R Production Architecture (Plumber API Worker Pooling, Reactive Caching, & Load Balancing)

Deskripsi:
Script ini mensimulasikan arsitektur deployment produksi untuk model R (seperti plumber/Shiny Server).
Karena runtime R bersifat single-threaded, arsitektur produksi umumnya menggunakan pool worker
proses R di balik load balancer, dilengkapi dengan caching memoization (seperti package 'memoise')
dan endpoint monitoring telemetri.
"""

import json
import math
import time
import socket
import hashlib
import threading
from urllib.request import Request, urlopen
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import deque

# --- ANSI Color Formatting ---
CLR_RESET  = "\033[0m"
CLR_BOLD   = "\033[1m"
CLR_RED    = "\033[31m"
CLR_GREEN  = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE   = "\033[34m"
CLR_CYAN   = "\033[36m"
CLR_GRAY   = "\033[90m"

# --- Simulating R Model & Plumber Environment ---
class RSerializedModel:
    """
    Simulasi model R (.rds) terlatih: Logistic Regression untuk prediksi Credit Default.
    y_hat = 1 / (1 + exp(-(b0 + b1*x1 + b2*x2 + b3*x3)))
    """
    def __init__(self):
        # Bobot model terlatih dari R (glm package)
        self.intercept = -1.8542
        self.weights = [0.0451, -0.0128, 0.8920]  # [Usia, Pendapatan_k, Skor_Kredit_Norm]
        self.model_version = "R-glm-v2.4.1"

    def predict(self, features):
        if len(features) != len(self.weights):
            raise ValueError(f"Dimensi fitur tidak cocok: diharapkan {len(self.weights)}, didapat {len(features)}")
        # Hitung log-odds
        z = self.intercept + sum(w * x for w, x in zip(self.weights, features))
        # Sigmoid activation (Logistic link function)
        probability = 1.0 / (1.0 + math.exp(-z))
        prediction = 1 if probability >= 0.5 else 0
        return {
            "prediction": prediction,
            "probability": round(probability, 4),
            "engine": self.model_version
        }

class PlumberWorker:
    """
    Simulasi R Process Worker mandiri (Single-threaded execution runtime)
    Dilengkapi sistem in-memory memoize cache (seperti package 'memoise' di R).
    """
    def __init__(self, worker_id: int):
        self.worker_id = worker_id
        self.model = RSerializedModel()
        self.cache = {}
        self.lock = threading.Lock()
        self.tasks_handled = 0

    def compute(self, features: list):
        with self.lock:
            self.tasks_handled += 1
            # Simulasi hashing input payload untuk memoise
            cache_key = hashlib.md5(json.dumps(features, sort_keys=True).encode()).hexdigest()
            
            if cache_key in self.cache:
                return self.cache[cache_key], True  # Cache Hit

            # Simulasi latensi interpretasi R runtime (15ms - 25ms)
            time.sleep(0.018)
            result = self.model.predict(features)
            self.cache[cache_key] = result
            return result, False  # Cache Miss

class WorkerPool:
    """
    Load Balancer Round-Robin untuk pool R-worker processes.
    """
    def __init__(self, num_workers=3):
        self.workers = [PlumberWorker(i + 1) for i in range(num_workers)]
        self.index = 0
        self.lock = threading.Lock()

    def get_worker(self) -> PlumberWorker:
        with self.lock:
            worker = self.workers[self.index]
            self.index = (self.index + 1) % len(self.workers)
            return worker

    def get_stats(self):
        return [
            {
                "worker_id": w.worker_id,
                "tasks_handled": w.tasks_handled,
                "cache_entries": len(w.cache)
            }
            for w in self.workers
        ]

# Global worker pool instance
WORKER_POOL = WorkerPool(num_workers=3)

# --- Plumber HTTP Server Implementation ---
class PlumberRouterHandler(BaseHTTPRequestHandler):
    """
    HTTP Request Handler meniru routing decorasi Plumber:
    #* @get /health
    #* @post /predict
    """
    def log_message(self, format, *args):
        # Override untuk menonaktifkan default logging console http.server
        return

    def _send_json_response(self, status_code: int, data: dict):
        response_bytes = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def do_GET(self):
        if self.path == "/health":
            stats = WORKER_POOL.get_stats()
            self._send_json_response(200, {
                "status": "UP",
                "service": "R-Plumber-Production-API",
                "workers": stats
            })
        else:
            self._send_json_response(404, {"error": "Endpoint tidak ditemukan"})

    def do_POST(self):
        if self.path == "/predict":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            
            try:
                payload = json.loads(body.decode("utf-8"))
                features = payload.get("features")
                
                if not isinstance(features, list):
                    raise ValueError("Parameter 'features' harus bertipe array")
                
                worker = WORKER_POOL.get_worker()
                start_time = time.perf_counter()
                inference, cached = worker.compute(features)
                elapsed_ms = (time.perf_counter() - start_time) * 1000

                response = {
                    "worker_id": worker.worker_id,
                    "cached": cached,
                    "execution_time_ms": round(elapsed_ms, 2),
                    "result": inference
                }
                self._send_json_response(200, response)

            except Exception as e:
                self._send_json_response(400, {"error": str(e)})
        else:
            self._send_json_response(404, {"error": "Endpoint tidak ditemukan"})

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

# --- Benchmarking & Client Verification ---
def run_stress_test(port: int, total_requests: int = 40):
    url = f"http://127.0.0.1:{port}/predict"
    sample_inputs = [
        [35, 65.0, 0.72],
        [45, 120.0, 0.88],
        [22, 18.5, 0.45],
        [35, 65.0, 0.72],  # Duplicate untuk memicu hit cache
        [58, 45.0, 0.35],
    ]
    
    latencies = []
    cache_hits = 0
    lock = threading.Lock()

    def client_worker(batch):
        nonlocal cache_hits
        for features in batch:
            req_data = json.dumps({"features": features}).encode("utf-8")
            req = Request(url, data=req_data, headers={"Content-Type": "application/json"})
            t0 = time.perf_counter()
            try:
                with urlopen(req) as resp:
                    data = json.loads(resp.read().decode())
                    lat = (time.perf_counter() - t0) * 1000
                    with lock:
                        latencies.append(lat)
                        if data.get("cached"):
                            cache_hits += 1
            except Exception as ex:
                print(f"{CLR_RED}[Error Client]: {ex}{CLR_RESET}")

    # Distribusikan request ke 4 worker thread paralel
    threads = []
    chunk_size = math.ceil(total_requests / 4)
    chunks = [
        [sample_inputs[i % len(sample_inputs)] for i in range(j, min(j + chunk_size, total_requests))]
        for j in range(0, total_requests, chunk_size)
    ]

    for chunk in chunks:
        t = threading.Thread(target=client_worker, args=(chunk,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    return latencies, cache_hits

# --- Main Lab Execution ---
def main():
    print(f"\n{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}  LAB: R PRODUCTION DEPLOYMENT & HIGH-PERFORMANCE PLUMBER API POOL{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}\n")

    port = find_free_port()
    server = HTTPServer(("127.0.0.1", port), PlumberRouterHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    print(f"{CLR_GREEN}✔ Plumber Core Engine aktif pada port :{port}{CLR_RESET}")
    print(f"{CLR_GRAY}ℹ Worker Pool: 3 Single-threaded Process Emulators terdaftar.{CLR_RESET}")
    print(f"{CLR_GRAY}ℹ Memoise Caching Subsystem: Enabled (MD5 Content Hash).{CLR_RESET}\n")

    time.sleep(0.1)

    # 1. Healthcheck Verifikasi
    print(f"{CLR_YELLOW}[1/3] Menjalankan API Healthcheck (/health)...{CLR_RESET}")
    health_url = f"http://127.0.0.1:{port}/health"
    with urlopen(health_url) as resp:
        health_data = json.loads(resp.read().decode())
        print(f"      Status: {CLR_GREEN}{health_data['status']}{CLR_RESET}")
        print(f"      Cluster Node Info: {health_data['service']}")

    # 2. Benchmarking Simulasi
    total_reqs = 35
    print(f"\n{CLR_YELLOW}[2/3] Mengirimkan {total_reqs} concurrent inference requests (/predict)...{CLR_RESET}")
    t_start = time.perf_counter()
    latencies, cache_hits = run_stress_test(port, total_requests=total_reqs)
    t_total = time.perf_counter() - t_start

    # 3. Analisis Hasil & Monitoring Metrics
    print(f"\n{CLR_YELLOW}[3/3] Telemetri & Evaluasi Kinerja Produksi:{CLR_RESET}")
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
    sorted_lat = sorted(latencies)
    p95_lat = sorted_lat[int(0.95 * len(sorted_lat))] if sorted_lat else 0.0
    rps = len(latencies) / t_total

    print(f"      ┌──────────────────────────────┬─────────────────────────┐")
    print(f"      │ {CLR_BOLD}Metric Performance{CLR_RESET}           │ {CLR_BOLD}Nilai Terukur{CLR_RESET}           │")
    print(f"      ├──────────────────────────────┼─────────────────────────┤")
    print(f"      │ Total Request Sukses         │ {CLR_GREEN}{len(latencies):>19} pcs{CLR_RESET} │")
    print(f"      │ Throughput R API (RPS)       │ {CLR_CYAN}{rps:>19.2f} req/s{CLR_RESET} │")
    print(f"      │ Rata-rata Latensi Endpoint   │ {CLR_GRAY}{avg_lat:>19.2f} ms{CLR_RESET} │")
    print(f"      │ Latensi 95th Percentile      │ {CLR_GRAY}{p95_lat:>19.2f} ms{CLR_RESET} │")
    print(f"      │ Cache Hits (Memoise Ratio)   │ {CLR_YELLOW}{cache_hits:>14} ({round(cache_hits/total_reqs*100, 1)}%){CLR_RESET} │")
    print(f"      └──────────────────────────────┴─────────────────────────┘")

    print(f"\n{CLR_BOLD}Distribusi Utilisasi Pool Worker R:{CLR_RESET}")
    stats = WORKER_POOL.get_stats()
    for w in stats:
        bar = "█" * (w["tasks_handled"] * 2)
        print(f"  Worker #{w['worker_id']}: [{CLR_CYAN}{bar:<30}{CLR_RESET}] "
              f"Task: {w['tasks_handled']} | Cache Saved: {w['cache_entries']}")

    # Shutdown Server
    server.shutdown()
    server.server_close()
    print(f"\n{CLR_GREEN}✔ Lab selesai dengan sukses. Semua pipeline produksi R berjalan valid.{CLR_RESET}\n")

if __name__ == "__main__":
    main()
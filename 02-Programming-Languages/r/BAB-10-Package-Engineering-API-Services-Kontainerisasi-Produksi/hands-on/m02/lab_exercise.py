#!/usr/bin/env python3
"""
Lab Hands-on: Bab 10 - Package Engineering, API Services, & Kontainerisasi Produksi
Topik: R Runtime & Plumber API Simulation Engine in Microservice Environments

Deskripsi:
Skrip ini mensimulasikan siklus hidup rekayasa paket R (Package Engineering)
tingkat lanjut, resolusi ketergantungan deterministik (berbasis renv.lock),
dan orkestrasi runtime REST API mikroservis (memodelkan engine Plumber / OpenCPU)
lengkap dengan validasi sandbox, parsing anotasi dekorator R, dan server HTTP aktif.
"""

import sys
import os
import json
import time
import math
import hashlib
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.error

# --- ANSI Formatting Configuration ---
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[31m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_BLUE    = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN    = "\033[36m"
CLR_WHITE   = "\033[37m"

def log_step(component: str, message: str, status: str = "INFO"):
    colors = {
        "INFO": CLR_CYAN,
        "OK": CLR_GREEN,
        "WARN": CLR_YELLOW,
        "FAIL": CLR_RED,
        "BUILD": CLR_MAGENTA
    }
    color = colors.get(status, CLR_WHITE)
    timestamp = time.strftime("%H:%M:%S")
    print(f"{CLR_BOLD}[{timestamp}] [{color}{status:<5}{CLR_RESET}{CLR_BOLD}] "
          f"[{CLR_BLUE}{component:<16}{CLR_RESET}{CLR_BOLD}]{CLR_RESET} {message}")

# --- Komponen 1: R Package & Dependency Engine (Simulasi renv & DESCRIPTION) ---
class RPackageArtifact:
    """
    Memvalidasi manifest DESCRIPTION, ekspor NAMESPACE, dan lockfile renv
    untuk memastikan build reproducibility sebelum deploy ke kontainer.
    """
    def __init__(self, pkg_name: str, version: str):
        self.pkg_name = pkg_name
        self.version = version
        self.namespace_exports = []
        self.dependencies = {}
        self.lockfile_hash = ""

    def define_namespace(self, exports: list):
        self.namespace_exports = exports

    def register_dependency(self, package: str, version: str, repository: str = "CRAN"):
        self.dependencies[package] = {
            "Version": version,
            "Repository": repository,
            "Hash": hashlib.sha256(f"{package}@{version}".encode()).hexdigest()[:12]
        }

    def generate_lockfile(self) -> str:
        """Membuat representasi JSON struktur renv.lock."""
        lock_data = {
            "R": {"Version": "4.3.2", "Repositories": [{"Name": "CRAN", "URL": "https://cloud.r-project.org"}]},
            "Packages": self.dependencies
        }
        serialized = json.dumps(lock_data, sort_keys=True, indent=2)
        self.lockfile_hash = hashlib.sha256(serialized.encode()).hexdigest()
        return serialized

    def verify_integrity(self) -> bool:
        """Memverifikasi bahwa namespace diekspor secara valid."""
        return len(self.namespace_exports) > 0 and len(self.dependencies) > 0

# --- Komponen 2: Engine Komputasi Statistik R (Linear Modeling) ---
class RStatisticalEngine:
    """
    Simulasi eksekusi kernel R untuk Ordinary Least Squares (OLS) Regression
    model: y = beta_0 + beta_1 * x
    """
    def __init__(self):
        self.beta_0 = 0.0
        self.beta_1 = 0.0
        self.fitted = False

    def fit_ols(self, x: list, y: list) -> dict:
        n = len(x)
        if n != len(y) or n < 2:
            raise ValueError("Vektor data x dan y harus berukuran sama dan n >= 2.")

        x_bar = sum(x) / n
        y_bar = sum(y) / n

        ss_xy = sum((x[i] - x_bar) * (y[i] - y_bar) for i in range(n))
        ss_xx = sum((x[i] - x_bar) ** 2 for i in range(n))

        if ss_xx == 0:
            raise ZeroDivisionError("Varians x bernilai 0, estimasi singular.")

        self.beta_1 = ss_xy / ss_xx
        self.beta_0 = y_bar - (self.beta_1 * x_bar)
        
        residuals = [y[i] - (self.beta_0 + self.beta_1 * x[i]) for i in range(n)]
        sse = sum(r ** 2 for r in residuals)
        r_squared = 1.0 - (sse / sum((y[i] - y_bar) ** 2 for i in range(n)))

        self.fitted = True
        return {
            "intercept": round(self.beta_0, 4),
            "slope": round(self.beta_1, 4),
            "r_squared": round(r_squared, 4),
            "sample_size": n
        }

    def predict(self, new_x: list) -> list:
        if not self.fitted:
            raise RuntimeError("Model belum di-fit dengan dataset.")
        return [round(self.beta_0 + self.beta_1 * val, 4) for val in new_x]

# --- Komponen 3: Plumber API Gateway & Container Runtime Simulation ---
class PlumberRouter:
    """
    Memetakan anotasi R Plumber (#* @get, #* @post) ke endpoint callable.
    """
    def __init__(self):
        self.routes = {"GET": {}, "POST": {}}
        self.engine = RStatisticalEngine()
        # Seed awal model statistika
        train_x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        train_y = [2.2, 2.8, 3.6, 4.5, 5.1, 5.9, 6.4, 7.2]
        self.engine.fit_ols(train_x, train_y)

    def register(self, method: str, path: str, handler):
        self.routes[method.upper()][path] = handler

    def dispatch(self, method: str, path: str, payload: dict = None) -> tuple:
        handlers = self.routes.get(method.upper(), {})
        if path not in handlers:
            return 404, {"error": "Endpoint tidak ditemukan", "status_code": 404}
        try:
            return 200, handlers[path](payload)
        except Exception as e:
            return 500, {"error": str(e), "status_code": 500}

# Global Router Instance
router_instance = PlumberRouter()

# R Plumber Annotation Endpoints:
def r_endpoint_health(_):
    return {
        "status": "UP",
        "runtime": "R-Plumber-Microservice",
        "container_id": "r-pkg-container-amd64-01",
        "timestamp": time.time()
    }

def r_endpoint_predict(payload):
    if not payload or "newdata" not in payload:
        raise ValueError("Payload JSON wajib menyertakan array 'newdata'.")
    raw_data = payload.get("newdata", [])
    preds = router_instance.engine.predict(raw_data)
    return {
        "model": "OLS_Linear_Regression",
        "inputs": raw_data,
        "fitted_values": preds,
        "engine_state": "converged"
    }

router_instance.register("GET", "/health", r_endpoint_health)
router_instance.register("POST", "/predict", r_endpoint_predict)

class PlumberHttpHandler(BaseHTTPRequestHandler):
    """HTTP Handler mengalihkan koneksi socket masuk ke kernel Plumber."""
    def log_message(self, format, *args):
        # Mute default access logs agar CLI bersih
        return

    def do_GET(self):
        code, resp = router_instance.dispatch("GET", self.path)
        self._send_json_response(code, resp)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        payload = {}
        if post_data:
            try:
                payload = json.loads(post_data.decode("utf-8"))
            except json.JSONDecodeError:
                self._send_json_response(400, {"error": "Malformed JSON payload"})
                return

        code, resp = router_instance.dispatch("POST", self.path, payload)
        self._send_json_response(code, resp)

    def _send_json_response(self, status_code: int, data: dict):
        encoded = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

# --- Komponen 4: Runner & Verifikasi Produksi ---
def run_lab():
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}  ADVANCED R LAB: PACKAGE ENGINEERING & PLUMBER CONTAINERIZATION     {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}\n")

    # Tahap 1: Validasi Manifest Paket R
    log_step("PKG-BUILDER", "Inisialisasi manifest R Package 'StatStreamer' v1.2.0...", "BUILD")
    pkg = RPackageArtifact("StatStreamer", "1.2.0")
    pkg.define_namespace(["predict_ols", "fit_ols", "stream_metrics"])
    pkg.register_dependency("plumber", "1.2.1")
    pkg.register_dependency("jsonlite", "1.8.7")
    pkg.register_dependency("Rcpp", "1.0.11")

    lockfile_content = pkg.generate_lockfile()
    if not pkg.verify_integrity():
        log_step("PKG-BUILDER", "Integritas paket korup atau dependensi hilang!", "FAIL")
        sys.exit(1)

    log_step("PKG-BUILDER", f"Lockfile renv.lock dibuat (SHA256: {pkg.lockfile_hash[:16]}...)", "OK")
    log_step("PKG-BUILDER", f"Namespace exports terdaftar: {pkg.namespace_exports}", "INFO")

    # Tahap 2: Simulasi Sandbox Kontainerisasi (OCI Image Build)
    log_step("CONTAINER-RUNTIME", "Membangun image kontainer berbasis rocker/r-ver:4.3.2...", "BUILD")
    time.sleep(0.3)
    dockerfile_steps = [
        "FROM rocker/r-ver:4.3.2",
        "RUN R -e 'install.packages(\"renv\")'",
        "COPY renv.lock renv.lock",
        "RUN R -e 'renv::restore()'",
        "EXPOSE 8080",
        "ENTRYPOINT [\"R\", \"-e\", \"pr <- plumber::pr('plumber.R'); pr$run(port=8080)\"]"
    ]
    for step in dockerfile_steps:
        print(f"  {CLR_WHITE}→ {step}{CLR_RESET}")
    log_step("CONTAINER-RUNTIME", "Image OCI 'statstreamer:production-v1.2.0' siap dijalankan.", "OK")

    # Tahap 3: Menjalankan Background Mock Server (Plumber Service)
    port = 8889
    server = HTTPServer(("127.0.0.1", port), PlumberHttpHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    log_step("MICROSERVICE", f"Server Plumber mendengarkan pada http://127.0.0.1:{port}", "OK")

    # Tahap 4: Pengujian E2E Integrasi API Service
    time.sleep(0.2)
    base_url = f"http://127.0.0.1:{port}"

    try:
        # Request 1: GET /health
        log_step("TEST-CLIENT", "Mengirim GET /health request...", "INFO")
        req = urllib.request.Request(f"{base_url}/health")
        with urllib.request.urlopen(req) as response:
            res_body = json.loads(response.read().decode())
            status = response.status
            log_step("TEST-CLIENT", f"Status: {status} | Response: {res_body}", "OK")

        # Request 2: POST /predict (Valid Data)
        log_step("TEST-CLIENT", "Mengirim POST /predict dengan vektor fitur input...", "INFO")
        payload = json.dumps({"newdata": [10.5, 12.0, 15.5]}).encode("utf-8")
        req_post = urllib.request.Request(
            f"{base_url}/predict",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        t_start = time.perf_counter()
        with urllib.request.urlopen(req_post) as response:
            t_latency = (time.perf_counter() - t_start) * 1000
            res_body = json.loads(response.read().decode())
            log_step("TEST-CLIENT", f"Latency: {t_latency:.2f}ms | Prediksi: {res_body['fitted_values']}", "OK")

        # Request 3: POST /predict (Bad Request Handling)
        log_step("TEST-CLIENT", "Uji validasi anomali input (Edge-case payload kosong)...", "INFO")
        req_bad = urllib.request.Request(
            f"{base_url}/predict",
            data=json.dumps({"invalid_key": []}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            urllib.request.urlopen(req_bad)
        except urllib.error.HTTPError as e:
            err_body = json.loads(e.read().decode())
            log_step("TEST-CLIENT", f"Handled Expectation: HTTP {e.code} -> {err_body['error']}", "OK")

    finally:
        # Tahap 5: Teardown Graceful
        log_step("CONTAINER-RUNTIME", "Mengirim sinyal SIGTERM ke daemon Plumber...", "WARN")
        server.shutdown()
        server.server_close()
        log_step("CONTAINER-RUNTIME", "Container worker berhasil dihentikan secara graceful.", "OK")

    print(f"\n{CLR_BOLD}{CLR_GREEN}✔ SELURUH SUITE PENGUJIAN REKAYASA PAKET R & API SELESAI DENGAN SUKSES.{CLR_RESET}\n")

if __name__ == "__main__":
    run_lab()
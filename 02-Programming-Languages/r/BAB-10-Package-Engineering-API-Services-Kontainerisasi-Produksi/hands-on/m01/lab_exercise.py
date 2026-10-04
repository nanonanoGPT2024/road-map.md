#!/usr/bin/env python3
"""
Lab Exercise: Simulasi R Package Engineering, Plumber API Services, & Kontainerisasi Produksi
BAB-10 R Programming Language Roadmap

File ini adalah modul simulasi interaktif mandiri (Python 3) untuk mendalami
arsitektur teknis ekosistem R pada level produksi:
1. R Package Engineering (DESCRIPTION, NAMESPACE, Roxygen2, R CMD check, testthat)
2. Microservice REST API dengan Plumber (Decorators, Serialization, Middleware)
3. Kontainerisasi Docker multi-stage & reproducible environment (renv.lock)
4. Validasi pipeline CI/CD release ke production
"""

import sys
import time
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# ANSI Color Codes
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"

def print_header(title: str):
    print(f"\n{Style.BG_BLUE}{Style.WHITE}{Style.BOLD} === {title} === {Style.RESET}\n")

def print_step(step_num: int, title: str):
    print(f"{Style.CYAN}{Style.BOLD}[Step {step_num}]{Style.RESET} {Style.YELLOW}{title}{Style.RESET}")

def print_success(msg: str):
    print(f"  {Style.GREEN}✓ {msg}{Style.RESET}")

def print_info(msg: str):
    print(f"  {Style.BLUE}ℹ {msg}{Style.RESET}")

def print_warning(msg: str):
    print(f"  {Style.YELLOW}⚠ {msg}{Style.RESET}")

def print_error(msg: str):
    print(f"  {Style.RED}✗ {msg}{Style.RESET}")

def simulate_progress(action: str, duration: float = 0.6):
    print(f"  {Style.DIM}→ {action}...{Style.RESET}", end="", flush=True)
    time.sleep(duration)
    print(f"\r  {Style.GREEN}✓ {action} [SELESAI]{Style.RESET}")

@dataclass
class RPackageManifest:
    name: str = "prodanalyticsR"
    version: str = "1.2.0"
    title: str = "Enterprise Production Analytics & Scoring Engine"
    dependencies: List[str] = field(default_factory=lambda: ["data.table (>= 1.14.0)", "jsonlite", "promises", "plumber"])
    suggests: List[str] = field(default_factory=lambda: ["testthat (>= 3.0.0)", "roxygen2", "covr", "httptest"])
    exported_functions: List[str] = field(default_factory=lambda: ["score_customer", "audit_pipeline", "serve_api"])

class PackageEngineeringSimulator:
    """Simulasi siklus hidup pengembangan paket R dan audit R CMD check"""

    def __init__(self, manifest: RPackageManifest):
        self.manifest = manifest

    def display_metadata(self):
        print_header(f"Inspeksi Metadata R Package: {self.manifest.name}")
        print(f"{Style.BOLD}Package:{Style.RESET}    {self.manifest.name}")
        print(f"{Style.BOLD}Version:{Style.RESET}    {self.manifest.version}")
        print(f"{Style.BOLD}Title:{Style.RESET}      {self.manifest.title}")
        print(f"{Style.BOLD}Imports:{Style.RESET}    {', '.join(self.manifest.dependencies)}")
        print(f"{Style.BOLD}Suggests:{Style.RESET}   {', '.join(self.manifest.suggests)}")
        print(f"{Style.BOLD}Exports:{Style.RESET}    {', '.join(self.manifest.exported_functions)}")
        print()

    def run_roxygen_and_namespace(self):
        print_step(1, "Roxygen2 Documentation & NAMESPACE Generation")
        simulate_progress("Parsing tag @export, @param, @return, dan @importFrom", 0.4)
        print_info("File NAMESPACE dimutakhirkan secara otomatis:")
        print(f"    {Style.DIM}export(score_customer){Style.RESET}")
        print(f"    {Style.DIM}export(audit_pipeline){Style.RESET}")
        print(f"    {Style.DIM}export(serve_api){Style.RESET}")
        print(f"    {Style.DIM}importFrom(data.table, ':=' , as.data.table){Style.RESET}")
        simulate_progress("Kompilasi man/pages .Rd help docs", 0.3)
        print_success("Dokumentasi Roxygen2 sinkron dengan kode sumber.")

    def run_unit_tests(self):
        print_step(2, "Testthat Test Suite Execution (Unit & Integration)")
        tests = [
            ("test-scoring.R: score_customer menghitung probabilitas churn valid [0, 1]", True),
            ("test-scoring.R: penanganan missing values dan input tak terduga", True),
            ("test-pipeline.R: validasi schema data.table dan streaming chunks", True),
            ("test-api-contracts.R: endpoint HTTP merespons sesuai spesifikasi JSON", True)
        ]
        for name, passed in tests:
            time.sleep(0.2)
            if passed:
                print(f"    {Style.GREEN}[ PASS ]{Style.RESET} {name}")
            else:
                print(f"    {Style.RED}[ FAIL ]{Style.RESET} {name}")
        print_success("Semua 4 unit test suite lolos 100%. Code coverage: 94.8%")

    def run_rcmd_check(self):
        print_step(3, "R CMD check --as-cran Execution")
        stages = [
            "checking for working pdflatex",
            "checking DESCRIPTION meta-information",
            "checking top-level files",
            "checking for left-over files",
            "checking index information",
            "checking package subdirectories",
            "checking R code for non-ASCII characters",
            "checking R code for syntax errors",
            "checking dependencies in R code",
            "checking S3 generic/method consistency",
            "checking replacement functions",
            "checking foreign function calls",
            "checking R code for possible problems (no visible binding)",
            "checking Rd files and math expressions",
            "checking examples",
            "checking tests"
        ]
        for s in stages:
            time.sleep(0.08)
            print(f"  * {s} ... {Style.GREEN}OK{Style.RESET}")

        print(f"\n  {Style.BOLD}Status R CMD check:{Style.RESET}")
        print(f"  {Style.GREEN}0 ERRORs | 0 WARNINGs | 0 NOTEs{Style.RESET}")
        print_success("Paket siap dirilis ke CRAN / internal enterprise repo!")

class PlumberAPISimulator:
    """Simulasi R Plumber REST API Router, Filters, dan Middleware"""

    def __init__(self):
        self.routes = [
            {"method": "GET", "path": "/healthz", "summary": "Liveness & Readiness probe"},
            {"method": "GET", "path": "/metrics", "summary": "Prometheus metric scraper"},
            {"method": "POST", "path": "/api/v1/score", "summary": "Model scoring inference batch/single"},
            {"method": "POST", "path": "/api/v1/audit", "summary": "Trigger audit run asinkron"}
        ]

    def display_routes(self):
        print_header("Spesifikasi Plumber REST API Router (plumber.R)")
        print(f"{'METODE':<8} {'PATH':<20} {'DESKRIPSI':<40}")
        print("-" * 70)
        for r in self.routes:
            method_color = Style.GREEN if r["method"] == "GET" else Style.YELLOW
            print(f"{method_color}{r['method']:<8}{Style.RESET} {Style.BOLD}{r['path']:<20}{Style.RESET} {r['summary']:<40}")
        print()

    def simulate_request(self, path: str, payload: Optional[Dict[str, Any]] = None):
        print_step(1, f"Menjalankan request simulasi: POST {path}")
        print_info("Filter: @filter auth-logger (Middleware execution)")
        time.sleep(0.3)
        print_success("Token valid. Client IP: 10.0.4.12 authenticated.")

        print_step(2, "Plumber Serializer: #* @serializer json")
        simulate_progress("Parsing body JSON dan validasi tipe numerik R data.frame", 0.4)

        if path == "/api/v1/score":
            age = payload.get("age", 35) if payload else 35
            balance = payload.get("balance", 12500.0) if payload else 12500.0
            score = round(1.0 / (1.0 + (2.71828 ** -(0.02 * age + 0.00008 * balance - 2.1))), 4)
            decision = "APPROVED" if score > 0.45 else "REJECTED"

            response = {
                "status": "success",
                "timestamp": "2026-10-05T04:20:00Z",
                "customer_id": payload.get("customer_id", "CUST-8831") if payload else "CUST-8831",
                "risk_score": score,
                "decision": decision,
                "model_version": "v1.2.0-prod"
            }
            print_step(3, "HTTP 200 OK Response Dispatch")
            print(f"{Style.CYAN}{json.dumps(response, indent=2)}{Style.RESET}")
            print_success(f"Inference berhasil dieksekusi dalam 4.2ms (Keputusan: {decision})")
        else:
            print_error(f"Route {path} tidak ditemukan.")

class ContainerizationSimulator:
    """Simulasi Docker build & multi-stage packaging untuk servis R"""

    DOCKERFILE_CONTENT = """# Multi-Stage Dockerfile untuk R Plumber Service
FROM rocker/r-ver:4.4.1 AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \\
    libcurl4-openssl-dev libssl-dev libxml2-dev git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY renv.lock renv/activate.R ./
RUN R -e "install.packages('renv', repos='https://cloud.r-project.org')"
RUN R -e "renv::restore(clean=TRUE)"

FROM rocker/r-ver:4.4.1 AS runner
WORKDIR /app
COPY --from=builder /usr/local/lib/R/site-library /usr/local/lib/R/site-library
COPY . /app
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s CMD curl -f http://localhost:8080/healthz || exit 1
ENTRYPOINT ["R", "-e", "pr <- plumber::plumb('plumber.R'); pr$run(host='0.0.0.0', port=8080)"]
"""

    def show_dockerfile(self):
        print_header("Arsitektur Kontainerisasi Produksi: Multi-Stage Dockerfile")
        print(f"{Style.DIM}{self.DOCKERFILE_CONTENT}{Style.RESET}")

    def simulate_docker_build(self):
        print_step(1, "Docker Build Process (Multi-Stage Execution)")
        steps = [
            ("Stage 1 [builder]: rocker/r-ver:4.4.1 base pulled", 0.3),
            ("Stage 1 [builder]: System libraries (libssl, libcurl, libxml2) installed", 0.4),
            ("Stage 1 [builder]: renv::restore() mengunci dependency exact SHA/CRAN snapshot", 0.6),
            ("Stage 2 [runner]: Menyalin compiled site-library dari builder stage", 0.3),
            ("Stage 2 [runner]: Setting non-root worker user & HEALTHCHECK probe", 0.2),
            ("Finalizing image: prodanalyticsr:v1.2.0 (Ukuran tereduksi 62%: 412 MB)", 0.3)
        ]
        for label, dur in steps:
            simulate_progress(label, dur)
        print_success("Docker image prodanalyticsr:v1.2.0 berhasil dibangun!")

    def simulate_runtime_healthcheck(self):
        print_step(2, "Verifikasi Container Runtime & Healthcheck")
        print_info("Memulai container: docker run -d -p 8080:8080 prodanalyticsr:v1.2.0")
        time.sleep(0.3)
        print("  GET /healthz HTTP/1.1 -> 200 OK (latency: 1.1ms)")
        print_success("Status container: HEALTHY (ready for traffic routing)")

def interactive_menu():
    manifest = RPackageManifest()
    pkg_sim = PackageEngineeringSimulator(manifest)
    plumber_sim = PlumberAPISimulator()
    docker_sim = ContainerizationSimulator()

    while True:
        print("\n" + "=" * 65)
        print(f"{Style.BOLD}{Style.MAGENTA}SIMULATOR R PRODUKSI: BAB-10 (PACKAGE & API CONTAINER){Style.RESET}")
        print("=" * 65)
        print("  1. Inspeksi Metadata & Struktur R Package Enterprise")
        print("  2. Jalankan Toolchain Package Dev (Roxygen2, Testthat, R CMD check)")
        print("  3. Tinjau Rute & Serializer Plumber REST API")
        print("  4. Uji Simulasi Request Inference (POST /api/v1/score)")
        print("  5. Tampilkan Dockerfile Multi-Stage & Simulasi Build Container")
        print("  6. Jalankan Seluruh Pipeline CI/CD Release (End-to-End)")
        print("  7. Keluar")
        print("-" * 65)

        try:
            choice = input(f"{Style.CYAN}Pilih opsi (1-7): {Style.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulator.")
            break

        if choice == "1":
            pkg_sim.display_metadata()
        elif choice == "2":
            pkg_sim.run_roxygen_and_namespace()
            pkg_sim.run_unit_tests()
            pkg_sim.run_rcmd_check()
        elif choice == "3":
            plumber_sim.display_routes()
        elif choice == "4":
            plumber_sim.simulate_request("/api/v1/score", {"customer_id": "CUST-9921", "age": 42, "balance": 48200.0})
        elif choice == "5":
            docker_sim.show_dockerfile()
            docker_sim.simulate_docker_build()
            docker_sim.simulate_runtime_healthcheck()
        elif choice == "6":
            print_header("PIPELINE CI/CD: GITHUB ACTIONS / ENTERPRISE RUNNER")
            pkg_sim.run_roxygen_and_namespace()
            pkg_sim.run_unit_tests()
            pkg_sim.run_rcmd_check()
            docker_sim.simulate_docker_build()
            plumber_sim.simulate_request("/api/v1/score")
            docker_sim.simulate_runtime_healthcheck()
            print_header("HASIL PIPELINE: RELEASE ARTIFACT DEPLOYED TO KUBERNETES CLUSTER")
            print_success("Service live: https://scoring.internal.corp/api/v1/score")
        elif choice == "7":
            print(f"{Style.GREEN}Terima kasih! Sesi lab simulasi selesai.{Style.RESET}")
            break
        else:
            print_warning("Pilihan tidak valid. Silakan masukkan nomor 1 - 7.")

def main():
    # Jika dipanggil dengan flag otomatis --ci / --all
    if len(sys.argv) > 1 and sys.argv[1] in ("--ci", "--all", "--test"):
        manifest = RPackageManifest()
        pkg_sim = PackageEngineeringSimulator(manifest)
        plumber_sim = PlumberAPISimulator()
        docker_sim = ContainerizationSimulator()

        print_header("RUNNING HEADLESS CI SIMULATION")
        pkg_sim.display_metadata()
        pkg_sim.run_roxygen_and_namespace()
        pkg_sim.run_unit_tests()
        pkg_sim.run_rcmd_check()
        plumber_sim.display_routes()
        plumber_sim.simulate_request("/api/v1/score", {"customer_id": "CI-BOT-01", "age": 29, "balance": 18500.0})
        docker_sim.show_dockerfile()
        docker_sim.simulate_docker_build()
        docker_sim.simulate_runtime_healthcheck()
        print_success("All technical validations passed successfully.")
        return

    interactive_menu()

if __name__ == "__main__":
    main()

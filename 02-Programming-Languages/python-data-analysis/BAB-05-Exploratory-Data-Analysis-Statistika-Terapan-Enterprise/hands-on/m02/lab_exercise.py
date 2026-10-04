#!/usr/bin/env python3
"""
Lab Hands-on: Enterprise Exploratory Data Analysis & Applied Statistics
Bab 05: Exploratory Data Analysis & Statistika Terapan Enterprise (Modul 02 Deep Dive)

Deskripsi:
Script ini mengimplementasikan engine analitik data streaming mandiri tanpa dependensi pihak ketiga.
Mencakup:
1. Welford's Algorithm untuk komputasi mean dan varians numerik stabil dalam single-pass O(1) memory.
2. Estimasi Moment Tingkat Tinggi (Skewness, Kurtosis) untuk deteksi deviasi distribusi normal.
3. Quantile Computation & Interquartile Range (IQR) filtering untuk isolasi outlier enterprise.
4. Matriks Korelasi Bivariat Pearson Streaming untuk analisa korelasi latency vs payload.
"""

import math
import random
import time
import sys
from typing import List, Dict, Tuple, Optional

# --- ANSI Terminal Color Formatting ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_CYAN = "\033[36m"
CLR_MAGENTA = "\033[35m"
CLR_GRAY = "\033[90m"


class WelfordAggregator:
    """
    Mengimplementasikan algoritma B. P. Welford (1962) untuk menghitung mean,
    varians, dan standar deviasi terbobot secara online (single-pass streaming)
    guna menghindari catastrophic cancellation pada floating point.
    """
    def __init__(self, name: str):
        self.name = name
        self.count: int = 0
        self.mean: float = 0.0
        self.M2: float = 0.0  # Sum of squared differences from the current mean
        self.min_val: float = float("inf")
        self.max_val: float = float("-inf")
        self.reservoir: List[float] = []  # Ring buffer reservoir sampling
        self.max_reservoir_size: int = 2000

    def update(self, x: float) -> None:
        """Memperbarui state statistik dengan nilai observasi baru x."""
        self.count += 1
        delta = x - self.mean
        self.mean += delta / self.count
        delta2 = x - self.mean
        self.M2 += delta * delta2

        if x < self.min_val:
            self.min_val = x
        if x > self.max_val:
            self.max_val = x

        # Reservoir sampling untuk estimasi quantile kontinu
        if len(self.reservoir) < self.max_reservoir_size:
            self.reservoir.append(x)
        else:
            idx = random.randint(0, self.count - 1)
            if idx < self.max_reservoir_size:
                self.reservoir[idx] = x

    @property
    def variance(self) -> float:
        """Mengembalikan sample variance (n - 1 degrees of freedom)."""
        return self.M2 / (self.count - 1) if self.count > 1 else 0.0

    @property
    def stdev(self) -> float:
        """Mengembalikan sample standard deviation."""
        return math.sqrt(self.variance)

    def get_percentile(self, p: float) -> float:
        """Menghitung persentil menggunakan nearest-rank/linear interpolation pada reservoir."""
        if not self.reservoir:
            return 0.0
        sorted_res = sorted(self.reservoir)
        k = (len(sorted_res) - 1) * (p / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_res[int(k)]
        d0 = sorted_res[int(f)] * (c - k)
        d1 = sorted_res[int(c)] * (k - f)
        return d0 + d1

    def compute_skewness_and_kurtosis(self) -> Tuple[float, float]:
        """
        Menghitung Sample Skewness (kemiringan) dan Excess Kurtosis (ketajaman puncak)
        berdasarkan sampel pada reservoir untuk validasi asumsi Gaussian.
        """
        n = len(self.reservoir)
        if n < 4 or self.stdev == 0.0:
            return 0.0, 0.0
        m = self.mean
        s = self.stdev
        m3 = sum((x - m) ** 3 for x in self.reservoir) / n
        m4 = sum((x - m) ** 4 for x in self.reservoir) / n
        
        skewness = m3 / (s ** 3)
        excess_kurtosis = (m4 / (s ** 4)) - 3.0
        return skewness, excess_kurtosis


class BivariateCorrelationEngine:
    """Menghitung koefisien korelasi Pearson secara streaming antara dua metrik."""
    def __init__(self):
        self.count: int = 0
        self.sum_x: float = 0.0
        self.sum_y: float = 0.0
        self.sum_xy: float = 0.0
        self.sum_x2: float = 0.0
        self.sum_y2: float = 0.0

    def update(self, x: float, y: float) -> None:
        self.count += 1
        self.sum_x += x
        self.sum_y += y
        self.sum_xy += x * y
        self.sum_x2 += x * x
        self.sum_y2 += y * y

    def pearson_r(self) -> float:
        n = self.count
        if n < 2:
            return 0.0
        numerator = (n * self.sum_xy) - (self.sum_x * self.sum_y)
        denominator = math.sqrt(abs((n * self.sum_x2 - self.sum_x ** 2) * (n * self.sum_y2 - self.sum_y ** 2)))
        return (numerator / denominator) if denominator != 0.0 else 0.0


class EnterpriseEDAPipeline:
    """Pipeline orkestrator eksplorasi data, deteksi anomali, dan profiling."""
    def __init__(self):
        self.stats_latency = WelfordAggregator("Request Latency (ms)")
        self.stats_payload = WelfordAggregator("Payload Size (KB)")
        self.corr_engine = BivariateCorrelationEngine()
        self.outliers_detected: List[Dict[str, float]] = []

    def ingest_record(self, trace_id: str, latency: float, payload: float) -> None:
        """Memproses satu unit data telemetri secara real-time."""
        self.stats_latency.update(latency)
        self.stats_payload.update(payload)
        self.corr_engine.update(latency, payload)

    def run_iqr_anomaly_detection(self) -> Tuple[float, float, int]:
        """Deteksi outlier latency menggunakan Tukey's Interquartile Range fence (1.5 * IQR)."""
        q1 = self.stats_latency.get_percentile(25.0)
        q3 = self.stats_latency.get_percentile(75.0)
        iqr = q3 - q1
        upper_fence = q3 + (1.5 * iqr)
        
        outlier_count = sum(1 for val in self.stats_latency.reservoir if val > upper_fence)
        return q1, q3, outlier_count

    def render_report(self, duration_ms: float) -> None:
        """Mencetak laporan analytical EDA berformat enterprise ke konsol."""
        print(f"\n{CLR_BOLD}{CLR_BLUE}========================================================================{CLR_RESET}")
        print(f"{CLR_BOLD}{CLR_CYAN}    ENTERPRISE EXPLORATORY DATA ANALYSIS (EDA) & INFERENCE REPORT       {CLR_RESET}")
        print(f"{CLR_BOLD}{CLR_BLUE}========================================================================{CLR_RESET}")
        print(f"{CLR_GRAY}Throughput: {self.stats_latency.count} records processed in {duration_ms:.2f} ms ({self.stats_latency.count / (duration_ms / 1000):,.0f} evt/sec){CLR_RESET}\n")

        # 1. Tabel Univariate Summary
        print(f"{CLR_BOLD}{CLR_YELLOW}[1] UNIVARIATE SUMMARY STATISTICS (Single-Pass Welford & Reservoir){CLR_RESET}")
        header = f"{'Metric':<22} | {'Count':<7} | {'Mean':<9} | {'StdDev':<8} | {'Min':<7} | {'Max':<8} | {'P95':<7} | {'P99':<7}"
        print(f"{CLR_GRAY}{'-' * len(header)}{CLR_RESET}")
        print(f"{CLR_BOLD}{header}{CLR_RESET}")
        print(f"{CLR_GRAY}{'-' * len(header)}{CLR_RESET}")

        for s in [self.stats_latency, self.stats_payload]:
            p95 = s.get_percentile(95.0)
            p99 = s.get_percentile(99.0)
            print(f"{s.name:<22} | {s.count:<7} | {s.mean:<9.2f} | {s.stdev:<8.2f} | {s.min_val:<7.2f} | {s.max_val:<8.2f} | {p95:<7.2f} | {p99:<7.2f}")
        print(f"{CLR_GRAY}{'-' * len(header)}{CLR_RESET}\n")

        # 2. Analisis Distribusi Bentuk (Shape Analysis)
        skew_lat, kurt_lat = self.stats_latency.compute_skewness_and_kurtosis()
        print(f"{CLR_BOLD}{CLR_YELLOW}[2] DISTRIBUTION SHAPE & NORMALITY VALIDATION (Latency){CLR_RESET}")
        print(f" • Sample Skewness   : {CLR_BOLD}{skew_lat:+.4f}{CLR_RESET} ", end="")
        if abs(skew_lat) < 0.5:
            print(f"[{CLR_GREEN}Simetris / Gaussian-like{CLR_RESET}]")
        elif skew_lat > 0.5:
            print(f"[{CLR_RED}Positive Right-Skewed (Long tail degradation){CLR_RESET}]")
        else:
            print(f"[{CLR_RED}Negative Left-Skewed{CLR_RESET}]")

        print(f" • Excess Kurtosis   : {CLR_BOLD}{kurt_lat:+.4f}{CLR_RESET} ", end="")
        if kurt_lat > 1.0:
            print(f"[{CLR_MAGENTA}Leptokurtic (Heavy-tailed, rentan spike anomali){CLR_RESET}]")
        else:
            print(f"[{CLR_GREEN}Mesokurtic/Platykurtic (Penyebaran wajar){CLR_RESET}]")
        print()

        # 3. Tukey Outlier Analysis
        q1, q3, outliers = self.run_iqr_anomaly_detection()
        iqr = q3 - q1
        upper_bound = q3 + (1.5 * iqr)
        print(f"{CLR_BOLD}{CLR_YELLOW}[3] IQR-BASED OUTLIER SURVEILLANCE{CLR_RESET}")
        print(f" • Q1 (25th percentile) : {q1:.2f} ms")
        print(f" • Q3 (75th percentile) : {q3:.2f} ms")
        print(f" • Interquartile (IQR)  : {iqr:.2f} ms")
        print(f" • Upper Outlier Fence  : {upper_bound:.2f} ms (Q3 + 1.5*IQR)")
        outlier_pct = (outliers / len(self.stats_latency.reservoir)) * 100
        print(f" • Outliers Flagged     : {CLR_BOLD}{CLR_RED}{outliers} ({outlier_pct:.2f}% dari sampled pool){CLR_RESET}\n")

        # 4. Korelasi Bivariat
        r = self.corr_engine.pearson_r()
        r_sq = r ** 2
        print(f"{CLR_BOLD}{CLR_YELLOW}[4] BIVARIATE RELATIONSHIP: Latency vs. Payload{CLR_RESET}")
        print(f" • Pearson's r Correlation : {CLR_BOLD}{r:+.4f}{CLR_RESET}")
        print(f" • Coeff of Determination  : {CLR_BOLD}{r_sq * 100:.2f}%{CLR_RESET} (R² variance explained)")
        print(f" • Interpretation          : ", end="")
        if r > 0.7:
            print(f"{CLR_RED}Korelasi linier positif kuat: Payload besar mendikte degradasi latency.{CLR_RESET}")
        elif r > 0.3:
            print(f"{CLR_YELLOW}Korelasi linier moderat: Payload berdampak parsial pada latency.{CLR_RESET}")
        else:
            print(f"{CLR_GREEN}Korelasi linier lemah/independen: Bottleneck bukan disebabkan oleh ukuran payload.{CLR_RESET}")
        print(f"{CLR_BOLD}{CLR_BLUE}========================================================================{CLR_RESET}\n")


def simulate_production_stream(num_records: int = 25000) -> None:
    """Mensimulasikan ingestion stream transaksi mikroservis realistik."""
    random.seed(42)
    pipeline = EnterpriseEDAPipeline()
    
    print(f"{CLR_CYAN}[*] Memulai Ingestion Stream Telemetri ({num_records:,} records)...{CLR_RESET}")
    start_time = time.perf_counter()

    for i in range(1, num_records + 1):
        # Basis payload log-normal: mean 15KB, variasi logaritmik
        payload = random.lognormvariate(2.5, 0.45)

        # Baseline latency dipengaruhi payload + noise Gaussian
        latency = 20.0 + (payload * 2.8) + random.gauss(0, 5.0)

        # Injeksi spike latency (outlier deterministik 1.5% probabilitas)
        if random.random() < 0.015:
            latency += random.uniform(150.0, 450.0)

        pipeline.ingest_record(f"TRX-{i:07d}", max(1.0, latency), max(0.1, payload))

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    pipeline.render_report(elapsed_ms)


if __name__ == "__main__":
    try:
        simulate_production_stream(num_records=30000)
    except KeyboardInterrupt:
        print(f"\n{CLR_RED}[!] Stream ingestion diinterupsi oleh user.{CLR_RESET}")
        sys.exit(0)
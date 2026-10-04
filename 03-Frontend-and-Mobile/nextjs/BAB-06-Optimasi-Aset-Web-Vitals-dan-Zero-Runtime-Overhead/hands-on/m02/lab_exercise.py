import os
import sys
import time
import json
import random
import threading
from urllib.request import urlopen, Request
from collections import defaultdict

# ANSI colors
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== {text} ==={Colors.ENDC}\n")

def simulate_loading(task_name, duration=1.5):
    print(f"{Colors.OKBLUE}[*] {task_name}...{Colors.ENDC}", end="", flush=True)
    for _ in range(10):
        time.sleep(duration / 10)
        print(".", end="", flush=True)
    print(f" {Colors.OKGREEN}Selesai!{Colors.ENDC}")

def analyze_assets():
    print_header("Analisis Aset Statis & Zero-Runtime Overhead")
    simulate_loading("Memindai folder .next/static", 2.0)
    
    assets = [
        {"name": "main-app.js", "type": "js", "size_kb": random.randint(150, 400), "optimized": False},
        {"name": "framework.js", "type": "js", "size_kb": random.randint(80, 150), "optimized": True},
        {"name": "hero-image.png", "type": "image", "size_kb": random.randint(500, 2500), "optimized": False},
        {"name": "logo.svg", "type": "image", "size_kb": random.randint(5, 15), "optimized": True},
        {"name": "Inter-bold.woff2", "type": "font", "size_kb": random.randint(30, 80), "optimized": True},
    ]

    total_size = 0
    print(f"\n{Colors.BOLD}{'Nama File':<20} | {'Tipe':<8} | {'Ukuran (KB)':<12} | {'Status Optimasi'}{Colors.ENDC}")
    print("-" * 65)
    
    for asset in assets:
        total_size += asset['size_kb']
        status = f"{Colors.OKGREEN}Optimal (Zero-Runtime){Colors.ENDC}" if asset['optimized'] else f"{Colors.FAIL}Perlu Optimasi{Colors.ENDC}"
        size_color = Colors.FAIL if asset['size_kb'] > 300 else Colors.OKGREEN
        print(f"{asset['name']:<20} | {asset['type']:<8} | {size_color}{asset['size_kb']:<12}{Colors.ENDC} | {status}")

    print("-" * 65)
    print(f"{Colors.BOLD}Total Ukuran Aset: {total_size} KB{Colors.ENDC}\n")

def measure_web_vitals():
    print_header("Simulasi Pengukuran Core Web Vitals (Lighthouse Mock)")
    simulate_loading("Menjalankan audit performa", 2.5)
    
    vitals = {
        "LCP (Largest Contentful Paint)": {"value": random.uniform(1.2, 4.5), "unit": "s", "good": 2.5, "poor": 4.0},
        "FID (First Input Delay)": {"value": random.uniform(50, 400), "unit": "ms", "good": 100, "poor": 300},
        "CLS (Cumulative Layout Shift)": {"value": random.uniform(0.01, 0.3), "unit": "", "good": 0.1, "poor": 0.25},
        "TTFB (Time to First Byte)": {"value": random.uniform(100, 900), "unit": "ms", "good": 800, "poor": 1800},
        "INP (Interaction to Next Paint)": {"value": random.uniform(100, 600), "unit": "ms", "good": 200, "poor": 500}
    }

    print(f"\n{Colors.BOLD}{'Metrik Web Vitals':<35} | {'Skor':<10} | {'Status'}{Colors.ENDC}")
    print("-" * 65)

    score = 100
    for metric, data in vitals.items():
        val = data['value']
        if val <= data['good']:
            status = f"{Colors.OKGREEN}GOOD{Colors.ENDC}"
        elif val <= data['poor']:
            status = f"{Colors.WARNING}NEEDS IMPROVEMENT{Colors.ENDC}"
            score -= 10
        else:
            status = f"{Colors.FAIL}POOR{Colors.ENDC}"
            score -= 20
            
        formatted_val = f"{val:.2f} {data['unit']}"
        print(f"{metric:<35} | {formatted_val:<10} | {status}")
        
    print("-" * 65)
    
    score_color = Colors.OKGREEN if score >= 90 else (Colors.WARNING if score >= 50 else Colors.FAIL)
    print(f"{Colors.BOLD}Skor Performa Keseluruhan: {score_color}{score} / 100{Colors.ENDC}\n")

def recommend_optimizations():
    print_header("Rekomendasi Optimasi Next.js")
    simulate_loading("Menganalisis hasil audit", 1.5)
    
    recommendations = [
        "Gunakan komponen <Image> bawaan Next.js untuk format WebP/AVIF otomatis dan lazy loading.",
        "Pindahkan logika state yang berat ke Server Components untuk mendapatkan Zero-Runtime Overhead.",
        "Gunakan next/font untuk memuat font secara optimal dan menghilangkan layout shift (CLS).",
        "Implementasikan dynamic import (next/dynamic) untuk komponen berat yang tidak ada di above-the-fold.",
        "Aktifkan route caching dan data cache untuk menurunkan TTFB."
    ]
    
    print("\nLangkah-langkah yang harus dilakukan:")
    for i, rec in enumerate(recommendations, 1):
        print(f"  {Colors.OKCYAN}{i}.{Colors.ENDC} {rec}")
    print("\n")

def main():
    try:
        print(f"\n{Colors.BOLD}{Colors.OKBLUE}=== Next.js Asset & Web Vitals Analyzer (Mock CLI) ==={Colors.ENDC}")
        analyze_assets()
        time.sleep(1)
        measure_web_vitals()
        time.sleep(1)
        recommend_optimizations()
        print(f"{Colors.OKGREEN}Simulasi Selesai. Selamat belajar optimasi Next.js!{Colors.ENDC}\n")
    except KeyboardInterrupt:
        print(f"\n{Colors.FAIL}Operasi dibatalkan oleh user.{Colors.ENDC}")
        sys.exit(1)

if __name__ == "__main__":
    main()

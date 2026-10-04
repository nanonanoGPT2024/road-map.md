#!/usr/bin/env python3
"""
Lab Exercise: Build Tools, Deployment Pipeline, dan Audit Kinerja
BAB-10: Frontend Beginner Core Foundations
Simulasi interaktif: Bundling, Minifikasi, CI/CD Pipeline, dan Lighthouse Audit (Core Web Vitals).
"""

import sys
import time
import random
import os
import json

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"

def print_banner():
    print(f"{CYAN}{BOLD}" + "=" * 68)
    print("  🚀 LAB SIMULASI FRONTEND BUILD TOOLS, CI/CD & AUDIT KINERJA 🚀")
    print("=" * 68 + f"{RESET}\n")

def simulate_progress(task_name, duration=1.2, steps=10):
    print(f"{BLUE}[RUNNING]{RESET} {task_name}...", end="", flush=True)
    for _ in range(steps):
        time.sleep(duration / steps)
        print(".", end="", flush=True)
    print(f" {GREEN}[SELESAI]{RESET}")

def module_build_tools():
    print(f"\n{BOLD}{MAGENTA}--- MODUL 1: BUNDLER & OPTIMASI ASET (Vite / Webpack / Rollup) ---{RESET}")
    print("Simulasi proses kompilasi kode sumber ES Modules menjadi bundle siap produksi.")
    
    mock_files = {
        "index.js": "import { add } from './math.js'; import { unused } from './math.js'; console.log(add(2, 5));",
        "math.js": "export function add(a, b) { return a + b; }\nexport function unused() { return 'dead code'; }",
        "style.css": "body { margin: 0; padding: 20px; background-color: #ffffff; }\n.btn { display: flex; }"
    }
    
    print(f"\n{YELLOW}File sumber ditemukan:{RESET}")
    total_raw_size = 0
    for name, content in mock_files.items():
        size = len(content.encode('utf-8'))
        total_raw_size += size
        print(f"  • {name:<12} : {size} bytes")
    print(f"Total ukuran mentah: {BOLD}{total_raw_size} bytes{RESET}\n")
    
    input(f"{CYAN}Tekan [Enter] untuk memulai simulasi Tree-Shaking & Minifikasi...{RESET}")
    simulate_progress("Parsing AST & Tree-shaking (menghapus unused function)", 0.8)
    simulate_progress("Terser minification & CSS Nano compression", 0.9)
    simulate_progress("Generating Content-Hash filenames", 0.6)
    
    # Hasil bundling
    minified_js = "console.log(7);"
    minified_css = "body{margin:0;padding:20px;background:#fff}.btn{display:flex}"
    hashed_js = f"bundle.a3f91b.{len(minified_js)}.js"
    hashed_css = f"style.d49e1a.{len(minified_css)}.css"
    
    bundled_size = len(minified_js.encode('utf-8')) + len(minified_css.encode('utf-8'))
    reduction = ((total_raw_size - bundled_size) / total_raw_size) * 100
    
    print(f"\n{GREEN}{BOLD}✓ Hasil Produksi (Distributable Bundle):{RESET}")
    print(f"  📦 dist/{hashed_js:<25} : {len(minified_js.encode('utf-8'))} bytes")
    print(f"  🎨 dist/{hashed_css:<25} : {len(minified_css.encode('utf-8'))} bytes")
    print(f"Total dist size : {BOLD}{bundled_size} bytes{RESET}")
    print(f"Penghematan     : {GREEN}{reduction:.1f}% ukuran terpangkas berkat Tree-shaking & Minifikasi!{RESET}\n")

def module_pipeline_cicd():
    print(f"\n{BOLD}{MAGENTA}--- MODUL 2: AUTOMATION & CI/CD PIPELINE ---{RESET}")
    print("Simulasi pipeline GitHub Actions / GitLab CI untuk verifikasi kualitas kode frontend.")
    
    stages = [
        ("Linting (ESLint + Stylelint)", 0.8, True),
        ("Type Checking (TypeScript compiler tsc --noEmit)", 0.9, True),
        ("Unit Testing (Vitest / Jest)", 1.2, True),
        ("Production Build (vite build)", 1.0, True),
        ("Deploy Preview ke CDN (Cloudflare Pages / Vercel)", 1.1, True),
    ]
    
    pipeline_ok = True
    for stage_name, duration, can_pass in stages:
        simulate_progress(stage_name, duration)
        # 10% chance to simulate intermittent lint failure if needed, but keep deterministic default
        status = "PASSED" if can_pass else "FAILED"
        print(f"      └─ Status: {GREEN}✓ {status}{RESET}")
    
    print(f"\n{GREEN}{BOLD}🎉 Pipeline Status: SUCCESS{RESET}")
    print(f"Preview URL: {CYAN}https://pr-42-feat-dashboard.app-preview.dev{RESET}\n")

def module_performance_audit():
    print(f"\n{BOLD}{MAGENTA}--- MODUL 3: AUDIT KINERJA & CORE WEB VITALS (Lighthouse) ---{RESET}")
    print("Menganalisis performa runtime website di jaringan simulated 4G mobile throttling.")
    
    input(f"{CYAN}Tekan [Enter] untuk menjalankan Audit Lighthouse...{RESET}")
    simulate_progress("Collecting Trace & First Contentful Paint", 0.7)
    simulate_progress("Measuring Largest Contentful Paint (LCP)", 0.8)
    simulate_progress("Simulating Interaction to Next Paint (INP)", 0.8)
    simulate_progress("Calculating Cumulative Layout Shift (CLS)", 0.7)
    
    # Metrik Core Web Vitals
    lcp = round(random.uniform(1.6, 2.4), 2)  # Ideal < 2.5s
    inp = random.randint(45, 130)             # Ideal < 200ms
    cls_score = round(random.uniform(0.01, 0.08), 3) # Ideal < 0.1
    performance_score = random.randint(92, 99)
    
    print(f"\n{BOLD}Hasil Audit Core Web Vitals:{RESET}")
    
    def metric_badge(val, threshold, unit=""):
        if val <= threshold:
            return f"{GREEN}[GOOD] {val}{unit}{RESET}"
        return f"{YELLOW}[NEEDS IMPROVEMENT] {val}{unit}{RESET}"
    
    print(f"  • LCP (Largest Contentful Paint) : {metric_badge(lcp, 2.5, 's')} (Batas: ≤ 2.5s)")
    print(f"  • INP (Interaction to Next Paint): {metric_badge(inp, 200, 'ms')} (Batas: ≤ 200ms)")
    print(f"  • CLS (Cumulative Layout Shift)  : {metric_badge(cls_score, 0.1)} (Batas: ≤ 0.1)")
    
    print(f"\n{BOLD}Skor Kategori Lighthouse:{RESET}")
    print(f"  ⚡ Performance  : {GREEN if performance_score >= 90 else YELLOW}{performance_score}/100{RESET}")
    print(f"  ♿ Accessibility: {GREEN}98/100{RESET}")
    print(f"  🛡️  Best Practices: {GREEN}100/100{RESET}")
    print(f"  🔍 SEO           : {GREEN}96/100{RESET}\n")

def run_interactive_quiz():
    print(f"\n{BOLD}{MAGENTA}--- CHECKPOINT KUIS MANDIRI (BAB 10) ---{RESET}")
    questions = [
        {
            "q": "Apa tujuan utama dari Tree-Shaking pada bundler modern seperti Rollup/Vite?",
            "options": [
                "A. Mengubah sintaks JavaScript menjadi CSS",
                "B. Menghapus kode mati (dead code/unused exports) dari bundle akhir",
                "C. Mempercepat koneksi internet pengguna",
                "D. Melakukan enkripsi kode agar tidak bisa dibaca"
            ],
            "ans": "B",
            "explanation": "Tree-shaking menganalisis ES Modules secara statis dan mengeliminasi export yang tidak pernah diimpor."
        },
        {
            "q": "Metrik Core Web Vitals manakah yang mengukur stabilitas visual halaman saat dimuat?",
            "options": [
                "A. LCP (Largest Contentful Paint)",
                "B. FID (First Input Delay)",
                "C. CLS (Cumulative Layout Shift)",
                "D. TTFB (Time to First Byte)"
            ],
            "ans": "C",
            "explanation": "CLS mengukur pergeseran layout tak terduga yang dapat mengganggu pengalaman visual pengguna."
        }
    ]
    
    score = 0
    for idx, item in enumerate(questions, 1):
        print(f"\n{BOLD}Pertanyaan {idx}:{RESET} {item['q']}")
        for opt in item['options']:
            print(f"  {opt}")
        user_choice = input(f"{YELLOW}Jawaban Anda (A/B/C/D): {RESET}").strip().upper()
        if user_choice == item['ans']:
            print(f"{GREEN}✓ Tepat Sekali!{RESET} {item['explanation']}")
            score += 1
        else:
            print(f"{RED}✗ Kurang tepat.{RESET} Jawaban benar adalah {BOLD}{item['ans']}{RESET}. {item['explanation']}")
            
    print(f"\nSkor Anda: {BOLD}{score}/{len(questions)}{RESET}")

def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print_banner()
    
    while True:
        print(f"{BOLD}Pilih Modul Simulasi:{RESET}")
        print("  1. Simulasi Bundler, Minifikasi & Tree-Shaking")
        print("  2. Simulasi CI/CD Deployment Pipeline")
        print("  3. Simulasi Audit Kinerja & Core Web Vitals (Lighthouse)")
        print("  4. Uji Pemahaman Mandiri (Quick Quiz)")
        print("  5. Jalankan Seluruh Alur Otomatis")
        print("  0. Keluar")
        
        choice = input(f"\n{CYAN}Masukkan nomor menu [0-5]: {RESET}").strip()
        
        if choice == "1":
            module_build_tools()
        elif choice == "2":
            module_pipeline_cicd()
        elif choice == "3":
            module_performance_audit()
        elif choice == "4":
            run_interactive_quiz()
        elif choice == "5":
            module_build_tools()
            module_pipeline_cicd()
            module_performance_audit()
            run_interactive_quiz()
            print(f"{GREEN}{BOLD}Semua modul selesai dijalankan!{RESET}\n")
        elif choice == "0":
            print(f"\n{CYAN}Terima kasih telah belajar fondasi Build Tools & Audit Kinerja! Sampai jumpa.{RESET}")
            sys.exit(0)
        else:
            print(f"{RED}Pilihan tidak valid. Silakan coba lagi.{RESET}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Program dihentikan oleh user.{RESET}")
        sys.exit(0)

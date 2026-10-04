#!/usr/bin/env python3
"""
Continuous Experimentation & A/B Testing Simulator
Mokup server sederhana untuk mensimulasikan traffic pengguna pada 2 varian desain (Control & Variant)
serta memproses perhitungan conversion rate secara real-time.
"""

import time
import random
import sys
import threading
from collections import defaultdict

# --- ANSI Colors ---
RESET = '\033[0m'
BOLD = '\033[1m'
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
CYAN = '\033[96m'
MAGENTA = '\033[95m'

# --- Configuration ---
TRAFFIC_VOLUME = 500  # Total simulated users
CONTROL_GROUP = 'A'   # Original Design
VARIANT_GROUP = 'B'   # New Design

# Probabilitas Konversi (Dalam skenario nyata, ini yang sedang kita uji)
# Di sini kita mengatur Variant B memiliki conversion rate yang sedikit lebih baik.
TRUE_CONVERSION_RATE_A = 0.12  # 12%
TRUE_CONVERSION_RATE_B = 0.18  # 18%

# In-memory Metrics Data Store
metrics_store = {
    CONTROL_GROUP: {'visitors': 0, 'conversions': 0, 'bounces': 0},
    VARIANT_GROUP: {'visitors': 0, 'conversions': 0, 'bounces': 0}
}
lock = threading.Lock()

def print_header(text):
    print(f"\n{BOLD}{CYAN}=== {text} ==={RESET}\n")

def simulate_user_session(user_id):
    """Mensimulasikan satu user yang mengunjungi aplikasi."""
    # 1. Traffic Allocation (50/50 Split)
    assigned_variant = CONTROL_GROUP if random.random() < 0.5 else VARIANT_GROUP
    
    # 2. Simulate User Behavior based on variant's true conversion probability
    prob = TRUE_CONVERSION_RATE_A if assigned_variant == CONTROL_GROUP else TRUE_CONVERSION_RATE_B
    
    # Random chance user converts
    is_converted = random.random() < prob
    
    # 3. Simulate processing time & network latency
    time.sleep(random.uniform(0.01, 0.05))
    
    # 4. Record Metrics (Thread-safe)
    with lock:
        metrics_store[assigned_variant]['visitors'] += 1
        if is_converted:
            metrics_store[assigned_variant]['conversions'] += 1
        else:
            metrics_store[assigned_variant]['bounces'] += 1

def generate_traffic(total_users):
    """Menjalankan thread untuk mensimulasikan traffic paralel."""
    threads = []
    print(f"{YELLOW}Menyiapkan simulasi untuk {total_users} users...{RESET}")
    for i in range(total_users):
        t = threading.Thread(target=simulate_user_session, args=(f"user_{i}",))
        threads.append(t)
        t.start()
        # Sedikit delay antar kedatangan user agar log terlihat realistis
        if i % 50 == 0 and i > 0:
            print(f"   [{i}/{total_users}] users allocated...")
            time.sleep(0.1)
    
    for t in threads:
        t.join()
    print(f"{GREEN}Simulasi traffic selesai.{RESET}")

def calculate_results():
    """Menghitung dan mencetak Analytics Report."""
    print_header("A/B Test Analytics Report")
    
    for variant in [CONTROL_GROUP, VARIANT_GROUP]:
        data = metrics_store[variant]
        visitors = data['visitors']
        conversions = data['conversions']
        
        # Guard terhadap division by zero
        if visitors == 0:
            cr = 0.0
        else:
            cr = (conversions / visitors) * 100
            
        color = BLUE if variant == CONTROL_GROUP else MAGENTA
        print(f"{BOLD}{color}Variant {variant}{RESET}:")
        print(f"  - Total Visitors : {visitors}")
        print(f"  - Conversions    : {conversions}")
        print(f"  - Bounce         : {data['bounces']}")
        print(f"  - {BOLD}Conversion Rate: {cr:.2f}%{RESET}\n")

    # Simple Analysis
    cr_a = (metrics_store[CONTROL_GROUP]['conversions'] / max(1, metrics_store[CONTROL_GROUP]['visitors']))
    cr_b = (metrics_store[VARIANT_GROUP]['conversions'] / max(1, metrics_store[VARIANT_GROUP]['visitors']))
    
    if cr_b > cr_a:
        uplift = ((cr_b - cr_a) / max(0.0001, cr_a)) * 100
        print(f"{GREEN}{BOLD}Kesimpulan: Variant B LEBIH BAIK dengan uplift sebesar {uplift:.2f}% dibanding Control (A).{RESET}")
        print(f"{YELLOW}*Catatan: Dalam dunia nyata, Anda harus menghitung Statistical Significance (p-value) sebelum mengambil keputusan final.{RESET}")
    elif cr_a > cr_b:
        uplift = ((cr_a - cr_b) / max(0.0001, cr_b)) * 100
        print(f"{RED}{BOLD}Kesimpulan: Variant B GAGAL mengalahkan Control. Control lebih baik sebesar {uplift:.2f}%.{RESET}")
        print("Aksi: Tolak hipotesis, jangan implementasi Variant B.")
    else:
        print(f"{YELLOW}{BOLD}Kesimpulan: Hasil seri (Netral). Tidak ada perbedaan signifikan.{RESET}")

def main():
    print_header("Inisialisasi Sistem Analytics & Eksperimen")
    print(f"Server tracking siap. Akan menerima {TRAFFIC_VOLUME} sesi pengguna.")
    
    start_time = time.time()
    
    try:
        generate_traffic(TRAFFIC_VOLUME)
        calculate_results()
    except KeyboardInterrupt:
        print(f"\n{RED}Eksperimen dihentikan oleh admin.{RESET}")
        sys.exit(1)
        
    end_time = time.time()
    print(f"\n{CYAN}Waktu eksekusi simulasi: {end_time - start_time:.2f} detik.{RESET}")
    print(f"{BOLD}Simulasi Selesai. Data berhasil diproses.{RESET}\n")

if __name__ == '__main__':
    main()

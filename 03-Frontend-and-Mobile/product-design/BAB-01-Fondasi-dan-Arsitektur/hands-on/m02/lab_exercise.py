import random
import time
import math
import json
import sys

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

def simulate_user_session(variant_type, user_id):
    """Mensimulasikan interaksi pengguna dengan desain antarmuka."""
    # Simulate time spent (seconds) and conversion based on variant
    if variant_type == 'A': # Control
        time_spent = random.gauss(120, 30)
        conversion_prob = 0.05
        frustration_clicks = random.randint(0, 5)
    else: # Variant B - New Design
        time_spent = random.gauss(140, 25)
        conversion_prob = 0.08
        frustration_clicks = random.randint(0, 2)
    
    time_spent = max(10, time_spent) # Minimum 10 seconds
    converted = random.random() < conversion_prob
    
    return {
        'user_id': f'usr_{user_id}',
        'variant': variant_type,
        'time_spent_seconds': round(time_spent, 2),
        'frustration_clicks': frustration_clicks,
        'converted': converted,
        'timestamp': time.time()
    }

def run_ab_test_simulation(sample_size=1000):
    print_header("Mulai Simulasi A/B Testing - Desain Produk")
    
    data_A = []
    data_B = []
    
    print(f"{Colors.OKCYAN}Memulai injeksi data untuk {sample_size} sesi pengguna per varian...{Colors.ENDC}")
    
    for i in range(sample_size):
        if i > 0 and i % (sample_size // 10) == 0:
            print(f"  [{Colors.OKBLUE}INFO{Colors.ENDC}] Processing session batch {i}...")
            time.sleep(0.1) # Simulasi delay network/processing
        data_A.append(simulate_user_session('A', i))
        data_B.append(simulate_user_session('B', i + sample_size))
        
    print(f"  [{Colors.OKGREEN}DONE{Colors.ENDC}] Simulasi injeksi data selesai.\n")
    return data_A, data_B

def calculate_usability_score(data):
    """Menghitung skor usabilitas kasar berdasarkan jumlah 'frustration clicks'"""
    total_clicks = sum(d['frustration_clicks'] for d in data)
    avg_clicks = total_clicks / len(data)
    # Semakin banyak klik frustrasi, semakin rendah skor usabilitas (skala 0-100)
    score = max(0, 100 - (avg_clicks * 15))
    return score

def analyze_results(data_A, data_B):
    print_header("Hasil Analisis & Product Metrics")
    
    # Analyze Variant A
    conv_A = sum(1 for d in data_A if d['converted'])
    rate_A = conv_A / len(data_A)
    avg_time_A = sum(d['time_spent_seconds'] for d in data_A) / len(data_A)
    usability_A = calculate_usability_score(data_A)
    
    # Analyze Variant B
    conv_B = sum(1 for d in data_B if d['converted'])
    rate_B = conv_B / len(data_B)
    avg_time_B = sum(d['time_spent_seconds'] for d in data_B) / len(data_B)
    usability_B = calculate_usability_score(data_B)
    
    print(f"{Colors.BOLD}Varian A (Desain Kontrol Lama):{Colors.ENDC}")
    print(f"  - Total User: {len(data_A)}")
    print(f"  - Konversi: {conv_A} users ({rate_A*100:.2f}%)")
    print(f"  - Rata-rata Waktu di Halaman: {avg_time_A:.2f} detik")
    print(f"  - Usability Score (Est): {usability_A:.2f}/100\n")
    
    print(f"{Colors.BOLD}Varian B (Desain Baru - Hipotesis):{Colors.ENDC}")
    print(f"  - Total User: {len(data_B)}")
    print(f"  - Konversi: {conv_B} users ({rate_B*100:.2f}%)")
    print(f"  - Rata-rata Waktu di Halaman: {avg_time_B:.2f} detik")
    print(f"  - Usability Score (Est): {usability_B:.2f}/100\n")
    
    print_header("Uji Signifikansi Statistik")
    
    # Simple significance calculation (Z-test for proportions)
    p = (conv_A + conv_B) / (len(data_A) + len(data_B))
    se = math.sqrt(p * (1 - p) * (1/len(data_A) + 1/len(data_B)))
    if se == 0:
        z_stat = 0
    else:
        z_stat = (rate_B - rate_A) / se
        
    print(f"  {Colors.WARNING}Z-Score (Conversion Rate):{Colors.ENDC} {z_stat:.4f}")
    
    if z_stat > 1.96:
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}Kesimpulan: Varian B secara signifikan lebih baik dari Varian A!{Colors.ENDC}")
        print("  - Hipotesis tervalidasi.")
        print("  - Rekomendasi: Rollout Varian B secara bertahap ke seluruh pengguna (Production).")
    elif z_stat < -1.96:
        print(f"\n{Colors.FAIL}{Colors.BOLD}Kesimpulan: Varian B secara signifikan lebih buruk dari Varian A!{Colors.ENDC}")
        print("  - Hipotesis ditolak.")
        print("  - Rekomendasi: Jangan diluncurkan. Evaluasi kembali masalah di tahap desain.")
    else:
        print(f"\n{Colors.OKCYAN}{Colors.BOLD}Kesimpulan: Tidak ada perbedaan signifikan antara Varian A dan B.{Colors.ENDC}")
        print("  - Hipotesis belum meyakinkan.")
        print("  - Rekomendasi: Kumpulkan lebih banyak data pengguna atau iterasi desain antarmuka.")

def export_logs(data_A, data_B, filename="ab_test_logs.json"):
    """Mengekspor log sesi ke file JSON sebagai simulasi analitik penyimpanan."""
    print_header("Eksport Log Data Sesi")
    all_data = data_A + data_B
    try:
        with open(filename, 'w') as f:
            json.dump(all_data[:10], f, indent=4) # Simpan sampel 10 data saja untuk log
        print(f"  [{Colors.OKGREEN}SUCCESS{Colors.ENDC}] Data log sampel berhasil diekspor ke {filename}")
    except IOError as e:
        print(f"  [{Colors.FAIL}ERROR{Colors.ENDC}] Gagal menyimpan file log: {e}")

if __name__ == '__main__':
    try:
        print(f"{Colors.HEADER}=== Product Design Engineering: A/B Test Simulator ==={Colors.ENDC}")
        data_A, data_B = run_ab_test_simulation(sample_size=3000)
        analyze_results(data_A, data_B)
        export_logs(data_A, data_B)
        print("\nSelesai.")
        sys.exit(0)
    except KeyboardInterrupt:
        print(f"\n{Colors.FAIL}Simulasi dihentikan paksa oleh pengguna.{Colors.ENDC}")
        sys.exit(1)

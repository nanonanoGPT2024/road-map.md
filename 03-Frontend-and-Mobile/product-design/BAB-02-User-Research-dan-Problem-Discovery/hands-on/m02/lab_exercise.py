import os
import sys
import time
import json
from collections import Counter
import threading

# ==============================================================================
# BAB 02 - USER RESEARCH & PROBLEM DISCOVERY
# Lab Exercise: Simulasi Sintesis Data User Research (NPS & Text Analysis)
# ==============================================================================
# Skrip ini mensimulasikan bagaimana data riset pengguna (survey kuantitatif 
# dan feedback kualitatif) diproses untuk menemukan "Pain Points" dan 
# Actionable Insights di dunia nyata.
# ==============================================================================

# ANSI Colors untuk output terminal yang informatif
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# Mock Data: User Survey Responses (Problem Discovery Phase)
# Data ini mencerminkan raw data yang biasa didapatkan dari Typeform, Google Forms, dll.
SURVEY_DATA = [
    {"user_id": 1, "age": 24, "feedback": "Aplikasi terlalu lambat saat memuat katalog produk, saya sering frustrasi.", "nps_score": 4},
    {"user_id": 2, "age": 35, "feedback": "Susah mencari tombol filter. Saya harus scroll berkali-kali.", "nps_score": 6},
    {"user_id": 3, "age": 28, "feedback": "Proses checkout membingungkan, banyak field yang tidak perlu diisi berulang.", "nps_score": 5},
    {"user_id": 4, "age": 22, "feedback": "Desainnya bagus, tapi loadingnya lambat sekali.", "nps_score": 7},
    {"user_id": 5, "age": 40, "feedback": "Saya tidak tahu cara membatalkan pesanan. Fitur bantuan sulit ditemukan.", "nps_score": 3},
    {"user_id": 6, "age": 27, "feedback": "Checkout terlalu rumit. Kenapa harus isi alamat dua kali?", "nps_score": 4},
    {"user_id": 7, "age": 31, "feedback": "Sering error saat pembayaran. Saya batal beli karena takut uang hilang.", "nps_score": 2},
    {"user_id": 8, "age": 29, "feedback": "Filter pencarian tidak berfungsi dengan baik.", "nps_score": 5},
    {"user_id": 9, "age": 25, "feedback": "Terkadang aplikasi force close sendiri saat mau checkout.", "nps_score": 3},
    {"user_id": 10, "age": 33, "feedback": "Lambat. Itu saja. Sangat lambat.", "nps_score": 5},
    {"user_id": 11, "age": 26, "feedback": "Aplikasi sangat membantu, tetapi masih lambat di beberapa halaman.", "nps_score": 8},
    {"user_id": 12, "age": 38, "feedback": "Checkoutnya bikin emosi, saya tidak jadi belanja.", "nps_score": 1}
]

def print_step(message):
    """Mencetak langkah proses dengan warna cyan."""
    print(f"{Colors.CYAN}[*] {message}{Colors.ENDC}")
    time.sleep(0.5)

def simulate_processing(task_name, duration=2.0):
    """Fungsi pembantu untuk membuat visualisasi loading spinner/progress bar."""
    print_step(f"Memulai: {task_name}")
    steps = 20
    for i in range(steps + 1):
        progress = (i / steps) * 100
        bar = '#' * i + '.' * (steps - i)
        sys.stdout.write(f"\r{Colors.BLUE}Prosesing... [{bar}] {progress:.0f}%{Colors.ENDC}")
        sys.stdout.flush()
        time.sleep(duration / steps)
    print(f"\r{Colors.GREEN}Selesai: {task_name} [{'#' * steps}] 100%{Colors.ENDC}")
    print()

def analyze_nps(data):
    """
    Menghitung skor Net Promoter Score (NPS).
    - Promoters (score 9-10)
    - Passives (score 7-8)
    - Detractors (score 0-6)
    Formula: % Promoters - % Detractors
    """
    promoters = sum(1 for d in data if d['nps_score'] >= 9)
    passives = sum(1 for d in data if d['nps_score'] in [7, 8])
    detractors = sum(1 for d in data if d['nps_score'] <= 6)
    
    total = len(data)
    if total == 0: return 0, 0, 0, 0

    nps = ((promoters / total) - (detractors / total)) * 100
    return nps, promoters, passives, detractors

def extract_keywords(data):
    """
    Ekstraksi kata kunci sederhana untuk simulasi analisis teks kualitatif.
    Menggunakan standard library `collections.Counter`.
    """
    # Stop words (kata-kata yang akan diabaikan karena kurang bermakna)
    stop_words = {'saya', 'yang', 'di', 'ke', 'dari', 'ini', 'itu', 'dan', 'atau', 
                  'tapi', 'saat', 'tidak', 'dengan', 'karena', 'bikin', 'jadi', 
                  'untuk', 'sangat', 'sekali', 'itu'}
    
    all_words = []
    
    for entry in data:
        # Normalisasi teks: lowercase, hilangkan titik dan koma
        clean_text = entry['feedback'].lower().replace('.', '').replace(',', '').replace('?', '')
        words = clean_text.split()
        # Filter stopwords dan kata yang terlalu pendek
        filtered_words = [w for w in words if w not in stop_words and len(w) > 3]
        all_words.extend(filtered_words)
        
    return Counter(all_words).most_common(5)

def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{Colors.HEADER}{Colors.BOLD}=== SIMULASI SINTESIS DATA USER RESEARCH ==={Colors.ENDC}")
    print(f"{Colors.WARNING}Modul: Problem Discovery (BAB 02){Colors.ENDC}")
    print("-" * 50 + "\n")
    
    # Tahap 1: Memuat Data
    simulate_processing("Membaca dan Memuat Data Survei Pengguna", 1.5)
    print_step(f"Data berhasil dimuat. Total responden diproses: {len(SURVEY_DATA)}\n")
    
    # Tahap 2: Analisis Kuantitatif (NPS)
    simulate_processing("Menganalisis Skor NPS (Kuantitatif)", 2.0)
    nps_score, p, pas, d = analyze_nps(SURVEY_DATA)
    
    print(f"{Colors.BOLD}--- HASIL NPS (NET PROMOTER SCORE) ---{Colors.ENDC}")
    print(f"Promoters : {Colors.GREEN}{p}{Colors.ENDC} pengguna (Score 9-10)")
    print(f"Passives  : {Colors.WARNING}{pas}{Colors.ENDC} pengguna (Score 7-8)")
    print(f"Detractors: {Colors.FAIL}{d}{Colors.ENDC} pengguna (Score 0-6)")
    print(f"Total NPS : {Colors.BOLD}{Colors.FAIL if nps_score < 0 else Colors.GREEN}{nps_score:.1f}{Colors.ENDC}")
    
    if nps_score < 0:
         print(f"{Colors.FAIL}>> Peringatan: NPS negatif mengindikasikan tingkat kepuasan yang sangat buruk!{Colors.ENDC}\n")
    else:
         print(f"{Colors.GREEN}>> NPS positif, namun masih terdapat banyak ruang untuk perbaikan.{Colors.ENDC}\n")
    
    # Tahap 3: Analisis Kualitatif (Pain Points)
    simulate_processing("Mengekstraksi Pain Points dari Feedback (Kualitatif)", 2.5)
    top_keywords = extract_keywords(SURVEY_DATA)
    
    print(f"{Colors.BOLD}--- TOP 5 PAIN POINTS (KATA KUNCI) ---{Colors.ENDC}")
    for idx, (word, count) in enumerate(top_keywords, 1):
        print(f" {idx}. {Colors.WARNING}{word.upper()}{Colors.ENDC} (Muncul {count} kali dalam feedback)")
    print()
    
    # Tahap 4: Sintesis (Actionable Insights)
    simulate_processing("Menghasilkan Laporan Problem Discovery", 1.5)
    
    print(f"{Colors.HEADER}{Colors.BOLD}=== ACTIONABLE INSIGHTS (HASIL SINTESIS) ==={Colors.ENDC}")
    print("Berdasarkan triangulasi data kuantitatif dan kualitatif, prioritas masalah (Problem Statement) adalah:")
    print(f" 1. {Colors.BOLD}Performa Sistem:{Colors.ENDC} Mengatasi masalah {Colors.WARNING}'lambat'{Colors.ENDC} dan 'force close' saat memuat katalog produk.")
    print(f" 2. {Colors.BOLD}Redesain Checkout:{Colors.ENDC} Menyederhanakan alur {Colors.WARNING}'checkout'{Colors.ENDC} yang dianggap membingungkan dan redundan.")
    print(f" 3. {Colors.BOLD}Navigasi & Pencarian:{Colors.ENDC} Memperbaiki visibilitas dan fungsi {Colors.WARNING}'filter'{Colors.ENDC} pencarian.")
    print(f"\n{Colors.GREEN}{Colors.BOLD}✓ Riset Selesai! Tim siap melanjutkan ke fase Ideation & Prototyping.{Colors.ENDC}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.FAIL}Proses dihentikan secara manual oleh pengguna.{Colors.ENDC}")
        sys.exit(0)

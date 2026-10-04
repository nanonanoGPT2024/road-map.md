import os
import sys
import time
import json
import random
from collections import defaultdict
import threading

# Konstanta Warna ANSI untuk Output Terminal
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== {text} ==={Colors.ENDC}\n")

def print_step(text):
    print(f"{Colors.CYAN}➜ {text}{Colors.ENDC}")

def print_success(text):
    print(f"{Colors.GREEN}✔ {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")

# ---------------------------------------------------------
# Bagian 1: Mock Server Data Generation
# Simulasi penyimpanan log analitik untuk eksperimental desain
# ---------------------------------------------------------

class MockAnalyticsServer:
    def __init__(self):
        self.logs = []
        self.variants = ['Control (A)', 'Variant (B)']
        
    def generate_traffic(self, num_users=1000):
        print_step(f"Menghasilkan mock data analitik untuk {num_users} pengguna...")
        time.sleep(1) # Simulasi network delay
        
        for i in range(num_users):
            user_id = f"user_{i:04d}"
            variant = random.choice(self.variants)
            
            # Simulasi perilaku pengguna (bounce, click, conversion)
            # Variant B didesain memiliki conversion rate sedikit lebih tinggi
            if variant == 'Control (A)':
                bounced = random.random() < 0.60
                clicked = False if bounced else random.random() < 0.30
                converted = False if not clicked else random.random() < 0.20
            else:
                bounced = random.random() < 0.55
                clicked = False if bounced else random.random() < 0.35
                converted = False if not clicked else random.random() < 0.25
                
            log_entry = {
                "timestamp": time.time() - random.randint(10, 10000),
                "user_id": user_id,
                "variant": variant,
                "events": {
                    "page_view": True,
                    "bounced": bounced,
                    "clicked_cta": clicked,
                    "purchased": converted
                },
                "session_duration": random.randint(5, 300) if not bounced else random.randint(1, 10)
            }
            self.logs.append(log_entry)
            
        print_success("Mock data berhasil di-generate dan tersimpan di memori server.")
        return self.logs

# ---------------------------------------------------------
# Bagian 2: Data Analyzer & Visualizer
# ---------------------------------------------------------

class ExperimentAnalyzer:
    def __init__(self, data):
        self.data = data
        self.metrics = defaultdict(lambda: {
            "total_users": 0,
            "bounces": 0,
            "clicks": 0,
            "conversions": 0,
            "total_duration": 0
        })
        
    def run_analysis(self):
        print_step("Menganalisis log data eksperimen (A/B Test)...")
        # Simulasi proses komputasi yang berat
        for _ in range(3):
            sys.stdout.write(f"{Colors.BLUE}.{Colors.ENDC}")
            sys.stdout.flush()
            time.sleep(0.3)
        print("\n")
        
        for entry in self.data:
            var = entry['variant']
            ev = entry['events']
            
            self.metrics[var]["total_users"] += 1
            if ev["bounced"]:
                self.metrics[var]["bounces"] += 1
            if ev["clicked_cta"]:
                self.metrics[var]["clicks"] += 1
            if ev["purchased"]:
                self.metrics[var]["conversions"] += 1
                
            self.metrics[var]["total_duration"] += entry["session_duration"]
            
    def display_report(self):
        print_header("HASIL EKSPERIMEN: A/B TESTING REPORT")
        
        for variant, metric in self.metrics.items():
            total = metric["total_users"]
            bounces = metric["bounces"]
            clicks = metric["clicks"]
            conversions = metric["conversions"]
            avg_duration = metric["total_duration"] / total if total > 0 else 0
            
            bounce_rate = (bounces / total) * 100 if total > 0 else 0
            ctr = (clicks / total) * 100 if total > 0 else 0
            conversion_rate = (conversions / total) * 100 if total > 0 else 0
            
            color = Colors.GREEN if variant == 'Variant (B)' else Colors.CYAN
            
            print(f"{color}{Colors.BOLD}Variasi: {variant}{Colors.ENDC}")
            print(f"  - Total Pengguna    : {total}")
            print(f"  - Bounce Rate       : {bounce_rate:.2f}% ({bounces} users)")
            print(f"  - Click-Through Rate: {ctr:.2f}% ({clicks} users)")
            print(f"  - Conversion Rate   : {conversion_rate:.2f}% ({conversions} purchases)")
            print(f"  - Avg Session Time  : {avg_duration:.2f} detik\n")
            
        self._calculate_winner()

    def _calculate_winner(self):
        # Logika sederhana penentuan pemenang (Hanya untuk keperluan simulasi)
        ctrl_cr = (self.metrics['Control (A)']['conversions'] / self.metrics['Control (A)']['total_users']) * 100
        var_cr = (self.metrics['Variant (B)']['conversions'] / self.metrics['Variant (B)']['total_users']) * 100
        
        print_header("KESIMPULAN")
        if var_cr > ctrl_cr:
            improvement = ((var_cr - ctrl_cr) / ctrl_cr) * 100 if ctrl_cr > 0 else 0
            print(f"{Colors.GREEN}{Colors.BOLD}🎉 Variant (B) MENANG!{Colors.ENDC}")
            print(f"Terdapat peningkatan Conversion Rate sebesar {improvement:.2f}% dibandingkan Control (A).")
            print("Rekomendasi: Lanjutkan dengan implementasi desain baru (Variant B) ke tahap produksi.")
        else:
            print(f"{Colors.WARNING}⚠ Eksperimen Gagal Membuktikan Hipotesis.{Colors.ENDC}")
            print("Control (A) masih memiliki performa lebih baik atau sama dengan Variant (B).")
            print("Rekomendasi: Jangan implementasikan desain baru. Lakukan iterasi pada desain Wireframe B.")

# ---------------------------------------------------------
# Bagian 3: Main Workflow Execution
# ---------------------------------------------------------

def main():
    try:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_header("Simulasi Lab Eksperimen Desain (A/B Testing)")
        print(f"Sistem operasi terdeteksi: {os.name}")
        print(f"Versi Python: {sys.version.split(' ')[0]}\n")
        
        # 1. Inisialisasi mock server dan generate data
        server = MockAnalyticsServer()
        data = server.generate_traffic(num_users=2500)
        
        # 2. Inisialisasi analyzer
        analyzer = ExperimentAnalyzer(data)
        
        # 3. Jalankan analisis
        analyzer.run_analysis()
        
        # 4. Tampilkan laporan
        analyzer.display_report()
        
    except KeyboardInterrupt:
        print(f"\n{Colors.FAIL}Eksekusi dibatalkan oleh pengguna.{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.FAIL}Terjadi kesalahan sistem: {str(e)}{Colors.ENDC}")
        sys.exit(1)

if __name__ == "__main__":
    main()

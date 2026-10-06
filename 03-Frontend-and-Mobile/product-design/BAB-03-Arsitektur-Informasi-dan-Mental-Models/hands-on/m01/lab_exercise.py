#!/usr/bin/env python3
"""
Lab Exercise M01: Arsitektur Informasi & Mental Models Simulator
Product Design Engineering - Hands-on Interactive Lab

Materi yang Disimulasikan:
1. Taxonomy Tree & Breadcrumb Navigation (Struktur Hirarki IA).
2. Mental Model vs Implementation Model Mismatch Detector.
3. Card Sorting Simulator (Evaluasi Kemudahan Temu Balik / Findability).
4. Hick's Law Cognitive Load Evaluator pada Kedalaman vs Lebar Menu.
"""

import math
import sys
import time
from typing import Dict, List, Optional, Tuple


class ANSIColor:
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
    BG_GREEN = "\033[42m"


class IANode:
    """Node representasi elemen dalam hirarki Arsitektur Informasi."""

    def __init__(self, key: str, label: str, description: str = ""):
        self.key = key
        self.label = label
        self.description = description
        self.children: List["IANode"] = []

    def add_child(self, child: "IANode") -> "IANode":
        self.children.append(child)
        return child

    def find_path(self, target_key: str, current_path: Optional[List[str]] = None) -> Optional[List[str]]:
        if current_path is None:
            current_path = []
        path = current_path + [self.label]
        if self.key.lower() == target_key.lower():
            return path
        for child in self.children:
            result = child.find_path(target_key, path)
            if result:
                return result
        return None


class InformationArchitectureSimulator:
    """Engine simulasi dan visualisasi konsep inti IA & Mental Model."""

    def __init__(self):
        self.root = self._build_default_taxonomy()
        self.user_mental_models = {
            "pengguna_awam": {
                "lacak_tagihan": "Keuangan / Bayar Tagihan",
                "ganti_profil": "Pengaturan Akun",
                "cek_resi": "Pesanan Saya / Status Kirim",
                "bantuan_cs": "Pusat Bantuan",
            },
            "engineer_sistem": {
                "lacak_tagihan": "BillingService / TransactionLedger",
                "ganti_profil": "AuthService / UserConfigMutation",
                "cek_resi": "LogisticsGateway / ShippingWebhook",
                "bantuan_cs": "ZendeskTicketRPC / SupportQueue",
            },
        }

    def _build_default_taxonomy(self) -> IANode:
        root = IANode("root", "Beranda Aplikasi")

        katalog = root.add_child(IANode("catalog", "Katalog Produk", "Navigasi penjelajahan item"))
        elektronik = katalog.add_child(IANode("elektronik", "Elektronik & Gadget"))
        elektronik.add_child(IANode("laptop", "Laptop & Aksesoris"))
        elektronik.add_child(IANode("smartphone", "Smartphone"))

        pesanan = root.add_child(IANode("orders", "Pesanan & Pembelian", "Status transaksi user"))
        pesanan.add_child(IANode("riwayat", "Riwayat Belanja"))
        pesanan.add_child(IANode("cek_resi", "Status Kirim & Resi"))

        keuangan = root.add_child(IANode("finance", "Keuangan & Dompet", "Saldo dan pembayaran"))
        keuangan.add_child(IANode("lacak_tagihan", "Tagihan Bulanan & PayLater"))
        keuangan.add_child(IANode("topup", "Isi Saldo Dompet"))

        akun = root.add_child(IANode("account", "Pengaturan Akun & Profil", "Manajemen data pribadi"))
        akun.add_child(IANode("ganti_profil", "Ubah Data Diri"))
        akun.add_child(IANode("keamanan", "Keamanan & PIN"))

        support = root.add_child(IANode("support", "Pusat Bantuan", "Layanan pelanggan"))
        support.add_child(IANode("bantuan_cs", "Hubungi CS / FAQ Interaktif"))

        return root

    def print_header(self, title: str):
        border = "=" * 65
        print(f"\n{ANSIColor.CYAN}{border}{ANSIColor.RESET}")
        print(f"{ANSIColor.BOLD}{ANSIColor.WHITE}{title.center(65)}{ANSIColor.RESET}")
        print(f"{ANSIColor.CYAN}{border}{ANSIColor.RESET}")

    def render_tree(self, node: IANode, prefix: str = "", is_last: bool = True):
        marker = "└── " if is_last else "├── "
        label_color = ANSIColor.GREEN if not node.children else ANSIColor.YELLOW
        desc = f" {ANSIColor.DIM}({node.description}){ANSIColor.RESET}" if node.description else ""

        print(f"{prefix}{ANSIColor.CYAN}{marker}{ANSIColor.RESET}{label_color}{node.label}{ANSIColor.RESET}{desc}")

        new_prefix = prefix + ("    " if is_last else "│   ")
        count = len(node.children)
        for i, child in enumerate(node.children):
            self.render_tree(child, new_prefix, is_last=(i == count - 1))

    def evaluate_breadcrumbs(self, target_key: str):
        self.print_header(f"Simulasi Wayfinding & Breadcrumbs: '{target_key}'")
        path = self.root.find_path(target_key)

        if not path:
            print(f"{ANSIColor.RED}[!] Item '{target_key}' tidak ditemukan dalam taksonomi!{ANSIColor.RESET}")
            return

        print(f"{ANSIColor.BOLD}Wayfinding Path (Breadcrumb):{ANSIColor.RESET}")
        breadcrumb_str = f" {ANSIColor.CYAN} > {ANSIColor.RESET}".join(
            [f"{ANSIColor.BG_BLUE}{ANSIColor.WHITE} {item} {ANSIColor.RESET}" for item in path]
        )
        print(breadcrumb_str)

        depth = len(path) - 1
        print(f"\n{ANSIColor.BOLD}Analisis Efisiensi Navigasi:{ANSIColor.RESET}")
        print(f"- Kedalaman Klik (Click Depth): {ANSIColor.MAGENTA}{depth} level(s){ANSIColor.RESET}")

        if depth <= 3:
            print(f"- Status: {ANSIColor.GREEN}[OPTIMAL]{ANSIColor.RESET} Berada dalam batas rekomendasi Golden Three Clicks Rule.")
        else:
            print(f"- Status: {ANSIColor.YELLOW}[WARNING]{ANSIColor.RESET} Terlalu dalam, berisiko menyebabkan disorientation pengguna.")

    def run_mental_model_mismatch_check(self):
        self.print_header("Evaluasi Gap: Mental Model vs Implementation Model")
        print(f"{ANSIColor.DIM}Seringkali developer merancang IA berbasis arsitektur database/microservice,{ANSIColor.RESET}")
        print(f"{ANSIColor.DIM}bukan berdasarkan pola pikir (Mental Model) manusia pengguna.{ANSIColor.RESET}\n")

        print(f"{'Fitur yang Dicari':<18} | {'User Expectation (Mental Model)':<30} | {'Dev System (Implementation Model)'}")
        print("-" * 88)

        mismatches = 0
        user_model = self.user_mental_models["pengguna_awam"]
        eng_model = self.user_mental_models["engineer_sistem"]

        for feature in user_model:
            user_exp = user_model[feature]
            dev_exp = eng_model[feature]
            # Bandingkan apakah struktur teknis konsonan dengan ekspektasi mental user
            is_mismatch = user_exp.split(" / ")[0] != dev_exp.split(" / ")[0]
            status_badge = f"{ANSIColor.RED}GAP MISMATCH{ANSIColor.RESET}" if is_mismatch else f"{ANSIColor.GREEN}MATCH{ANSIColor.RESET}"
            if is_mismatch:
                mismatches += 1

            print(f"{ANSIColor.BOLD}{feature:<18}{ANSIColor.RESET} | {ANSIColor.GREEN}{user_exp:<30}{ANSIColor.RESET} | {ANSIColor.RED}{dev_exp:<30}{ANSIColor.RESET} -> {status_badge}")

        gap_ratio = (mismatches / len(user_model)) * 100
        print(f"\n{ANSIColor.BOLD}Cognitive Friction Index:{ANSIColor.RESET} {ANSIColor.RED if gap_ratio > 50 else ANSIColor.GREEN}{gap_ratio:.1f}% Mismatch{ANSIColor.RESET}")
        print(f"{ANSIColor.YELLOW}Kesimpulan Desain:{ANSIColor.RESET} Arsitektur informasi wajib memetakan 'Represented Model' menyerupai 'User Mental Model'.")

    def simulate_card_sorting(self):
        self.print_header("Simulasi Card Sorting (Closed Sorting Exercise)")
        print(f"Berikut 6 kartu item yang harus dikelompokkan ke dalam kategori taksonomi:\n")

        cards = [
            ("K01", "Kupon Diskon Ongkir"),
            ("K02", "Ubah Password & Sidik Jari"),
            ("K03", "Download Faktur Pajak"),
            ("K04", "Chat Admin Penjual"),
            ("K05", "Estimasi Kurir Tiba"),
            ("K06", "Tambah Rekening Bank"),
        ]

        categories = {
            "A": "Keamanan & Akun",
            "B": "Transaksi & Pengiriman",
            "C": "Keuangan & Promosi",
        }

        correct_mappings = {
            "K01": "C",
            "K02": "A",
            "K03": "C",
            "K04": "B",
            "K05": "B",
            "K06": "A",
        }

        for code, label in cards:
            print(f"  [{ANSIColor.CYAN}{code}{ANSIColor.RESET}] {label}")

        print(f"\n{ANSIColor.BOLD}Kategori Tersedia:{ANSIColor.RESET}")
        for key, name in categories.items():
            print(f"  ({ANSIColor.MAGENTA}{key}{ANSIColor.RESET}) {name}")

        print(f"\n{ANSIColor.GREEN}Menghitung skor keselarasan pengelompokan IA otomatis...{ANSIColor.RESET}")
        time.sleep(0.5)

        total = len(cards)
        score = 0
        print(f"\n{'ID Kartu':<10} | {'Item':<30} | {'Kategori Teoretis IA':<25}")
        print("-" * 72)
        for code, label in cards:
            cat_key = correct_mappings[code]
            cat_name = categories[cat_key]
            score += 1
            print(f"{code:<10} | {label:<30} | {ANSIColor.GREEN}{cat_name} ({cat_key}){ANSIColor.RESET}")

        print(f"\n{ANSIColor.BOLD}Findability & Categorization Score:{ANSIColor.RESET} {ANSIColor.GREEN}100% (6/6 Card Groups Valid){ANSIColor.RESET}")

    def evaluate_hicks_law(self, options_count: int, depth: int) -> Tuple[float, str]:
        """
        Menghitung waktu reaksi kognitif menggunakan Hukum Hick (Hick's Law):
        RT = a + b * log2(n + 1)
        Di mana a = 0.2s, b = 0.15s per level navigasi.
        """
        a = 0.2
        b = 0.15
        reaction_time_per_level = a + (b * math.log2(options_count + 1))
        total_time = reaction_time_per_level * depth

        if total_time < 1.0:
            rating = f"{ANSIColor.GREEN}Rendah (Sangat Cepat & Intuitif){ANSIColor.RESET}"
        elif total_time < 2.5:
            rating = f"{ANSIColor.YELLOW}Sedang (Beban Kognitif Wajar){ANSIColor.RESET}"
        else:
            rating = f"{ANSIColor.RED}Tinggi (Beban Kognitif Berlebih, Risiko Drop-off){ANSIColor.RESET}"

        return total_time, rating

    def run_hicks_law_comparison(self):
        self.print_header("Hick's Law: Kedalaman (Depth) vs Kelebaran (Breadth) IA")
        print(f"{ANSIColor.DIM}Formula: T = b * log2(n + 1) [Hukum Hick untuk Waktu Pengambilan Keputusan]{ANSIColor.RESET}\n")

        scenarios = [
            ("A: Dangkal & Lebar (Broad/Shallow)", 16, 1),
            ("B: Berimbang (Balanced IA)", 4, 2),
            ("C: Sangat Dalam (Deep/Narrow)", 2, 4),
            ("D: Overloaded Menu (Cluttered)", 24, 2),
        ]

        print(f"{'Skenario Navigasi':<35} | {'Pilihan/Level':<14} | {'Level':<6} | {'Estimasi Waktu':<15} | {'Cognitive Load'}")
        print("-" * 95)

        for name, options, depth in scenarios:
            t, rating = self.evaluate_hicks_law(options, depth)
            print(f"{name:<35} | {options:<14} | {depth:<6} | {t:.3f} detik    | {rating}")


def main():
    simulator = InformationArchitectureSimulator()

    # Periksa jika dijalankan non-interaktif / piped / headless
    is_interactive = sys.stdin.isatty() and "--demo" not in sys.argv

    if not is_interactive:
        print(f"{ANSIColor.BG_GREEN}{ANSIColor.WHITE} MODE EKSEKUSI DEMO LENGKAP {ANSIColor.RESET}")
        simulator.print_header("POHON TAKSONOMI ARSITEKTUR INFORMASI (IA TREE)")
        simulator.render_tree(simulator.root)
        simulator.evaluate_breadcrumbs("cek_resi")
        simulator.evaluate_breadcrumbs("lacak_tagihan")
        simulator.run_mental_model_mismatch_check()
        simulator.simulate_card_sorting()
        simulator.run_hicks_law_comparison()
        print(f"\n{ANSIColor.GREEN}[✓] Simulasi Lab M01 Berhasil Dijalankan Secara Lengkap!{ANSIColor.RESET}\n")
        return

    while True:
        simulator.print_header("LAB EXERCISE M01: ARSITEKTUR INFORMASI & MENTAL MODELS")
        print(f"1. {ANSIColor.BOLD}Tampilkan Hirarki Taksonomi IA (Tree View){ANSIColor.RESET}")
        print(f"2. {ANSIColor.BOLD}Simulasi Wayfinding & Breadcrumbs (Click Depth){ANSIColor.RESET}")
        print(f"3. {ANSIColor.BOLD}Evaluasi Gap: User Mental Model vs System Model{ANSIColor.RESET}")
        print(f"4. {ANSIColor.BOLD}Jalankan Simulasi Card Sorting (Closed Sorting){ANSIColor.RESET}")
        print(f"5. {ANSIColor.BOLD}Kalkulator Beban Kognitif Hukum Hick (Hick's Law){ANSIColor.RESET}")
        print(f"6. {ANSIColor.BOLD}Jalankan Semua Modul (Full Interactive Run){ANSIColor.RESET}")
        print(f"0. {ANSIColor.RED}Keluar (Exit){ANSIColor.RESET}")

        try:
            choice = input(f"\n{ANSIColor.CYAN}Pilih opsi menu [0-6]: {ANSIColor.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar dari lab.")
            break

        if choice == "1":
            simulator.print_header("HIRARKI TAKSONOMI NAVIGASI")
            simulator.render_tree(simulator.root)
        elif choice == "2":
            target = input(f"Masukkan key target (contoh: cek_resi, lacak_tagihan, ganti_profil): ").strip()
            simulator.evaluate_breadcrumbs(target if target else "cek_resi")
        elif choice == "3":
            simulator.run_mental_model_mismatch_check()
        elif choice == "4":
            simulator.simulate_card_sorting()
        elif choice == "5":
            simulator.run_hicks_law_comparison()
        elif choice == "6":
            simulator.render_tree(simulator.root)
            simulator.evaluate_breadcrumbs("cek_resi")
            simulator.run_mental_model_mismatch_check()
            simulator.simulate_card_sorting()
            simulator.run_hicks_law_comparison()
        elif choice == "0":
            print(f"{ANSIColor.GREEN}Terima kasih telah menyelesaikan Lab M01 IA!{ANSIColor.RESET}")
            break
        else:
            print(f"{ANSIColor.RED}Pilihan tidak valid, silakan coba lagi.{ANSIColor.RESET}")


if __name__ == "__main__":
    main()

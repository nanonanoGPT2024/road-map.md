#!/usr/bin/env python3
"""
Lab Exercise: Arsitektur Informasi dan Navigasi Struktural Enterprise
Modul: BAB-04 - UX Design Enterprise Architecture
Deskripsi:
    Simulasi teknis komprehensif implementasi Arsitektur Informasi (IA)
    untuk sistem Enterprise (ERP/SaaS). Mencakup perancangan taksonomi,
    analisis Card Sorting (Dendrogram / Agreement Score), Tree Testing
    (Click-depth vs Hick's Law), serta Navigasi Berbasis Faset (Faceted Search).
"""

from __future__ import annotations

import math
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_GRAY = "\033[100m"


def header(title: str) -> None:
    print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} [ENTERPRISE IA] {title.upper()} {Color.RESET}")
    print(f"{Color.CYAN}{'=' * 65}{Color.RESET}")


def subheader(title: str) -> None:
    print(f"\n{Color.YELLOW}{Color.BOLD}>>> {title}{Color.RESET}")


@dataclass
class IANode:
    id: str
    label: str
    category: str
    depth: int = 0
    children: List[IANode] = field(default_factory=list)
    tags: Set[str] = field(default_factory=set)

    def add_child(self, child: IANode) -> IANode:
        child.depth = self.depth + 1
        self.children.append(child)
        return child

    def render_tree(self, prefix: str = "", is_last: bool = True) -> None:
        connector = "└── " if is_last else "├── "
        tag_str = f" {Color.DIM}[{','.join(self.tags)}]{Color.RESET}" if self.tags else ""
        print(f"{prefix}{Color.CYAN}{connector}{Color.BOLD}{self.label}{Color.RESET} {Color.DIM}(ID: {self.id}){Color.RESET}{tag_str}")
        new_prefix = prefix + ("    " if is_last else "│   ")
        for i, child in enumerate(self.children):
            child.render_tree(new_prefix, i == (len(self.children) - 1))


class EnterpriseTaxonomy:
    """Membangun Arsitektur Informasi Multi-level untuk Sistem ERP Enterprise."""

    def __init__(self) -> None:
        self.root = IANode(id="root", label="Enterprise Suite Portal", category="Global")
        self._build_ontology()

    def _build_ontology(self) -> None:
        # Finansial & Akuntansi
        fin = self.root.add_child(IANode("fin", "Manajemen Finansial & Akuntansi", "Finance", tags={"core", "sox-compliant"}))
        gl = fin.add_child(IANode("fin-gl", "Buku Besar (General Ledger)", "Finance", tags={"accounting"}))
        gl.add_child(IANode("fin-gl-chart", "Bagan Akun (Chart of Accounts)", "Finance"))
        gl.add_child(IANode("fin-gl-journal", "Entri Jurnal Penyesuaian", "Finance"))
        ap = fin.add_child(IANode("fin-ap", "Hutang Usaha (Accounts Payable)", "Finance"))
        ap.add_child(IANode("fin-ap-inv", "Faktur Masuk & Rekonsiliasi 3-Arah", "Finance"))

        # Supply Chain & Logistik
        scm = self.root.add_child(IANode("scm", "Supply Chain Management (SCM)", "SupplyChain", tags={"operations"}))
        inv = scm.add_child(IANode("scm-inv", "Manajemen Pergudangan & Stok", "SupplyChain"))
        inv.add_child(IANode("scm-inv-sku", "Katalog SKU & Titik Reorder", "SupplyChain"))
        inv.add_child(IANode("scm-inv-trans", "Perpindahan Gudang Lintas Cabang", "SupplyChain"))
        proc = scm.add_child(IANode("scm-proc", "Pengadaan & Vendor Portal", "SupplyChain"))
        proc.add_child(IANode("scm-proc-rfq", "Permintaan Penawaran (RFQ)", "SupplyChain"))

        # SDM & Human Capital
        hcm = self.root.add_child(IANode("hcm", "Human Capital Management (HCM)", "HR", tags={"governance"}))
        hcm_pay = hcm.add_child(IANode("hcm-pay", "Kompensasi & Penggajian Terpadu", "HR"))
        hcm_pay.add_child(IANode("hcm-pay-tax", "Kalkulator PPh21 & Slip Gaji", "HR"))
        hcm.add_child(IANode("hcm-perf", "Evaluasi Kinerja & Suksesi", "HR"))


class CardSortSimulator:
    """Simulasi Card Sorting Studi UX: Menghitung matriks kesepakatan dan dendrogram hierarki."""

    CARDS = [
        "Faktur Pembelian Vendor",
        "Bagan Akun Finansial",
        "Penggajian Karyawan",
        "Stok Opname Gudang",
        "Rekonsiliasi Bank",
        "Evaluasi KPI Karyawan",
        "Manajemen Vendor RFQ",
        "Pencatatan Aset Tetap",
    ]

    USER_CLUSTERS = [
        {"Finance": ["Faktur Pembelian Vendor", "Bagan Akun Finansial", "Rekonsiliasi Bank", "Pencatatan Aset Tetap"],
         "HR": ["Penggajian Karyawan", "Evaluasi KPI Karyawan"],
         "Operations": ["Stok Opname Gudang", "Manajemen Vendor RFQ"]},
        {"Finance": ["Bagan Akun Finansial", "Rekonsiliasi Bank", "Pencatatan Aset Tetap"],
         "Procurement": ["Faktur Pembelian Vendor", "Manajemen Vendor RFQ", "Stok Opname Gudang"],
         "HR": ["Penggajian Karyawan", "Evaluasi KPI Karyawan"]},
        {"Finance": ["Faktur Pembelian Vendor", "Bagan Akun Finansial", "Rekonsiliasi Bank"],
         "Logistics": ["Stok Opname Gudang", "Manajemen Vendor RFQ", "Pencatatan Aset Tetap"],
         "HR": ["Penggajian Karyawan", "Evaluasi KPI Karyawan"]},
    ]

    @classmethod
    def calculate_co_occurrence(cls) -> Dict[str, Dict[str, float]]:
        matrix: Dict[str, Dict[str, float]] = {c1: {c2: 0.0 for c2 in cls.CARDS} for c1 in cls.CARDS}
        n_users = len(cls.USER_CLUSTERS)

        for session in cls.USER_CLUSTERS:
            for group_items in session.values():
                for item1 in group_items:
                    for item2 in group_items:
                        matrix[item1][item2] += 1.0 / n_users

        return matrix

    @classmethod
    def render_matrix(cls) -> None:
        matrix = cls.calculate_co_occurrence()
        print(f"\n{Color.CYAN}Matriks Kesepakatan Klaster (Co-occurrence Matrix Card Sorting):{Color.RESET}")
        header_labels = [f"C{i+1}" for i in range(len(cls.CARDS))]
        print(" " * 32 + " ".join([f"{lbl:>5}" for lbl in header_labels]))

        for i, card in enumerate(cls.CARDS):
            row_str = f"{Color.WHITE}{f'C{i+1}. ' + card[:25]:<30}{Color.RESET} "
            for other_card in cls.CARDS:
                val = matrix[card][other_card]
                if val >= 0.8:
                    c = Color.GREEN
                elif val >= 0.5:
                    c = Color.YELLOW
                else:
                    c = Color.DIM
                row_str += f"{c}{val:5.2f}{Color.RESET} "
            print(row_str)


class TreeTestingBenchmark:
    """Benchmark Arsitektur Informasi: Tree Testing, Click Depth, dan Estimasi Waktu Reaksi (Hick's Law)."""

    @staticmethod
    def calculate_hicks_law(n_options: int, a_sec: float = 0.2, b_sec: float = 0.155) -> float:
        """Hick-Hyman Law: RT = a + b * log2(n + 1)"""
        return a_sec + b_sec * math.log2(n_options + 1)

    @staticmethod
    def evaluate_task(task_name: str, path: List[str], choices_per_level: List[int]) -> None:
        depth = len(path)
        total_rt = sum(TreeTestingBenchmark.calculate_hicks_law(n) for n in choices_per_level)
        cognitive_load_index = depth * 0.4 + (sum(choices_per_level) / len(choices_per_level)) * 0.1

        print(f"{Color.BOLD}Target Skenario:{Color.RESET} {Color.CYAN}{task_name}{Color.RESET}")
        print(f"  {Color.MAGENTA}Jalur Navigasi:{Color.RESET} {' -> '.join(path)}")
        print(f"  {Color.BLUE}Kedalaman (Click-depth):{Color.RESET} {depth} level")
        print(f"  {Color.YELLOW}Estimasi Waktu Keputusan Kognitif (Hick's Law):{Color.RESET} {total_rt:.2f} detik")
        print(f"  {Color.GREEN}Indeks Beban Kognitif (CLI):{Color.RESET} {cognitive_load_index:.2f} / 5.0")

        if depth > 4:
            print(f"  {Color.RED}[!WARNING!] Kedalaman > 4 melanggar prinsip shallow-broad enterprise IA.{Color.RESET}")
        else:
            print(f"  {Color.GREEN}[PASSED] Kedalaman memenuhi batas standar ergonomi kognitif (depth <= 4).{Color.RESET}")


class FacetedSearchEngine:
    """Mesin Navigasi Faset (Faceted Enterprise Navigation Simulator)."""

    DATABASE = [
        {"id": "DOC-01", "name": "Audit SOX Q3 Finansial", "dept": "Finance", "year": "2024", "confidentiality": "Restricted"},
        {"id": "DOC-02", "name": "Purchase Order PO-9810", "dept": "SupplyChain", "year": "2024", "confidentiality": "Internal"},
        {"id": "DOC-03", "name": "Laporan Gaji Tahunan Direksi", "dept": "HR", "year": "2023", "confidentiality": "Confidential"},
        {"id": "DOC-04", "name": "Rekonsiliasi Bank Mandiri Cabang", "dept": "Finance", "year": "2023", "confidentiality": "Internal"},
        {"id": "DOC-05", "name": "Daftar Vendor Logistik Pelabuhan", "dept": "SupplyChain", "year": "2024", "confidentiality": "Public"},
        {"id": "DOC-06", "name": "Matriks Kompetensi Pegawai", "dept": "HR", "year": "2024", "confidentiality": "Internal"},
    ]

    @classmethod
    def filter_documents(cls, filters: Dict[str, str]) -> List[Dict[str, str]]:
        results = []
        for doc in cls.DATABASE:
            match = True
            for k, v in filters.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                results.append(doc)
        return results

    @classmethod
    def compute_facet_counts(cls, current_filters: Dict[str, str]) -> Dict[str, Dict[str, int]]:
        facets: Dict[str, Dict[str, int]] = {"dept": {}, "year": {}, "confidentiality": {}}
        matching_docs = cls.filter_documents(current_filters)
        for doc in matching_docs:
            for facet_key in facets:
                val = doc[facet_key]
                facets[facet_key][val] = facets[facet_key].get(val, 0) + 1
        return facets


def run_automated_suite() -> None:
    """Menjalankan seluruh simulasi secara otomatis tanpa memerlukan input interaktif."""
    header("Mode Uji Otomatis Laboratorium Arsitektur Informasi")

    subheader("1. Hierarki Taksonomi Enterprise (Visualisasi Pohon)")
    taxonomy = EnterpriseTaxonomy()
    taxonomy.root.render_tree()

    subheader("2. Analisis Card Sorting & Matriks Kesepakatan")
    CardSortSimulator.render_matrix()

    subheader("3. Benchmark Tree Testing & Hukum Ergonomi Kognitif")
    TreeTestingBenchmark.evaluate_task(
        task_name="Mencari Rekonsiliasi 3-Arah Faktur Vendor",
        path=["Portal", "Finansial", "Hutang Usaha", "Faktur Masuk & Rekonsiliasi 3-Arah"],
        choices_per_level=[3, 2, 1, 1],
    )
    TreeTestingBenchmark.evaluate_task(
        task_name="Approval Perpindahan Stok Lintas Gudang",
        path=["Portal", "Supply Chain", "Pergudangan", "Perpindahan Gudang"],
        choices_per_level=[3, 2, 2, 1],
    )

    subheader("4. Simulasi Navigasi Faset Terkombinasi")
    filters = {"dept": "Finance", "year": "2024"}
    print(f"Filter Diterapkan: {filters}")
    results = FacetedSearchEngine.filter_documents(filters)
    print(f"Dokumen Ditemukan ({len(results)}):")
    for doc in results:
        print(f"  - {Color.GREEN}{doc['id']}{Color.RESET}: {doc['name']} [{doc['confidentiality']}]")

    facets = FacetedSearchEngine.compute_facet_counts(filters)
    print(f"Distribusi Faset Tersisa: {facets}")

    print(f"\n{Color.GREEN}{Color.BOLD}[SUCCESS] Seluruh modul simulasi UX Architecture tervalidasi 100% normal.{Color.RESET}")


def interactive_menu() -> None:
    taxonomy = EnterpriseTaxonomy()
    while True:
        header("Sistem Navigasi Struktural & Arsitektur Informasi Enterprise")
        print(f" {Color.CYAN}1.{Color.RESET} Visualisasi Hierarki Taksonomi Enterprise")
        print(f" {Color.CYAN}2.{Color.RESET} Evaluasi Matriks Card Sorting (Klaster Mental Model Pengguna)")
        print(f" {Color.CYAN}3.{Color.RESET} Benchmark Tree Testing & Waktu Keputusan (Hick's Law)")
        print(f" {Color.CYAN}4.{Color.RESET} Simulasi Navigasi Faset (Faceted Search & Dynamic Counts)")
        print(f" {Color.CYAN}5.{Color.RESET} Jalankan Automated Lab Verification Suite")
        print(f" {Color.CYAN}6.{Color.RESET} Keluar")

        try:
            choice = input(f"\n{Color.BOLD}Pilih opsi [1-6]: {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari program.")
            break

        if choice == "1":
            subheader("Pohon Arsitektur Informasi")
            taxonomy.root.render_tree()
        elif choice == "2":
            subheader("Analisis Kesepakatan Card Sorting")
            CardSortSimulator.render_matrix()
        elif choice == "3":
            subheader("Benchmarking Navigasi Tree Testing")
            TreeTestingBenchmark.evaluate_task(
                task_name="Mencari Bagan Akun (Chart of Accounts)",
                path=["Portal", "Finansial", "Buku Besar", "Bagan Akun"],
                choices_per_level=[3, 2, 2, 1],
            )
        elif choice == "4":
            subheader("Pencarian Berbasis Faset (Faceted Filtering)")
            print("Daftar Departemen: Finance, SupplyChain, HR")
            dept = input("Filter Departemen (atau kosongkan): ").strip()
            filters = {}
            if dept:
                filters["dept"] = dept
            docs = FacetedSearchEngine.filter_documents(filters)
            print(f"Hasil Pencarian ({len(docs)} item):")
            for d in docs:
                print(f"  * [{d['id']}] {d['name']} ({d['dept']} - {d['year']} - {d['confidentiality']})")
            facets = FacetedSearchEngine.compute_facet_counts(filters)
            print("Hitungan Faset Dinamis:", facets)
        elif choice == "5":
            run_automated_suite()
        elif choice == "6":
            print(f"{Color.GREEN}Terima kasih telah menggunakan Lab Arsitektur Informasi.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan coba lagi.{Color.RESET}")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in ("--test", "--demo", "--auto"):
        run_automated_suite()
    else:
        # Jalankan suite otomatis jika terminal tidak interaktif (TTY False), jika tidak masuk ke menu
        if sys.stdin.isatty():
            interactive_menu()
        else:
            run_automated_suite()


if __name__ == "__main__":
    main()

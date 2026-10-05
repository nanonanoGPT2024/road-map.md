#!/usr/bin/env python3
"""
Lab Exercise: Pemodelan Perilaku, Sintesis Riset, dan Service Blueprint (UX Design)
Bab 03: Pemodelan Perilaku, Sintesis Riset, dan Service Blueprint

Simulasi arsitektur produksi interaktif untuk sintesis riset UX, pemodelan perilaku persona,
dan eksekusi evaluasi Service Blueprint multi-layer (Frontstage, Backstage, Support Process).
"""

from __future__ import annotations
import sys
import time
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional

# --- Terminal ANSI Color Codes ---
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
    BG_MAGENTA = "\033[45m"

def print_header(title: str) -> None:
    line = "=" * 70
    print(f"\n{Color.CYAN}{Color.BOLD}{line}")
    print(f" {title.center(68)} ")
    print(f"{line}{Color.RESET}\n")

def print_step(step_num: int, label: str) -> None:
    print(f"{Color.MAGENTA}{Color.BOLD}[Tahap {step_num}]{Color.RESET} {Color.WHITE}{label}{Color.RESET}")

# --- Data Structures & Domain Models ---

class BehavioralArchetype(Enum):
    EFFICIENCY_SEEKER = "Efficiency Seeker (Fast, task-focused, intolerant of friction)"
    EXPLORER_ANALYST = "Explorer Analyst (Detail-oriented, compares options, risk-averse)"
    CONVENIENCE_DRIVEN = "Convenience Driven (Mobile-first, delegates decisions, values automation)"

@dataclass
class ResearchDataPoint:
    quote: str
    behavior_indicator: str
    sentiment_score: float  # -1.0 to 1.0
    touchpoint: str

@dataclass
class BehavioralPersona:
    archetype: BehavioralArchetype
    primary_goal: str
    friction_threshold: float
    mental_model: str
    core_frustrations: List[str]

@dataclass
class ServiceBlueprintNode:
    step_id: str
    stage_name: str
    customer_action: str
    physical_evidence: str
    frontstage_interaction: str       # Line of Interaction
    backstage_action: str             # Line of Visibility
    support_process: str              # Line of Internal Interaction
    max_sla_ms: int
    failure_probability: float

# --- Synthesizer & Blueprint Engine ---

class ResearchSynthesisEngine:
    def __init__(self) -> None:
        self.raw_data: List[ResearchDataPoint] = [
            ResearchDataPoint(
                quote="Saya bingung membedakan opsi asuransi tambahan di keranjang belanja.",
                behavior_indicator="Decision Paralysis saat checkout",
                sentiment_score=-0.65,
                touchpoint="Review Cart Page"
            ),
            ResearchDataPoint(
                quote="Proses verifikasi OTP memakan waktu 45 detik, saya hampir batalkan pesanan.",
                behavior_indicator="Friction saat otentikasi",
                sentiment_score=-0.80,
                touchpoint="Payment Gateway Screen"
            ),
            ResearchDataPoint(
                quote="Riwayat pelacakan kurir live sangat menenangkan, saya tidak perlu hubungi CS.",
                behavior_indicator="Proactive Anxiety Mitigation",
                sentiment_score=0.90,
                touchpoint="Live Order Tracking"
            ),
            ResearchDataPoint(
                quote="Tombol konfirmasi pembayaran terkadang loading tanpa status yang jelas.",
                behavior_indicator="System Feedback Deficiency",
                sentiment_score=-0.75,
                touchpoint="Payment Submission"
            )
        ]

    def run_affinity_clustering(self) -> Dict[str, List[ResearchDataPoint]]:
        print_step(1, "Menjalankan Sintesis Riset Kualitatif (Affinity Clustering)...")
        clusters: Dict[str, List[ResearchDataPoint]] = {
            "Decision Clarity": [],
            "Friction & Latency": [],
            "Trust & Post-Purchase Confidence": []
        }

        for dp in self.raw_data:
            time.sleep(0.15)
            if dp.sentiment_score < -0.7:
                clusters["Friction & Latency"].append(dp)
                status_color = Color.RED
            elif dp.sentiment_score < 0:
                clusters["Decision Clarity"].append(dp)
                status_color = Color.YELLOW
            else:
                clusters["Trust & Post-Purchase Confidence"].append(dp)
                status_color = Color.GREEN

            print(f"  {Color.DIM}* Memetakan data point:{Color.RESET} \"{dp.quote[:42]}...\" -> {status_color}[{dp.touchpoint}]{Color.RESET}")

        return clusters

class ServiceBlueprintSimulator:
    def __init__(self) -> None:
        self.stages: List[ServiceBlueprintNode] = [
            ServiceBlueprintNode(
                step_id="BP-01",
                stage_name="Penemuan & Pemilihan Item",
                customer_action="Memilih SKU & membandingkan spesifikasi produk",
                physical_evidence="Halaman PDP, Komparator Tabel, Review Badge",
                frontstage_interaction="UI Rendering Catalog, Micro-interactions Filter",
                backstage_action="Dynamic Pricing Engine & Realtime Inventory Lock",
                support_process="Redis Cluster Cache & ElasticSearch Query",
                max_sla_ms=250,
                failure_probability=0.03
            ),
            ServiceBlueprintNode(
                step_id="BP-02",
                stage_name="Checkout & Validasi Risiko",
                customer_action="Mengisi alamat, memilih kurir, dan klik 'Bayar'",
                physical_evidence="Modal Ringkasan Biaya, SLA ETA Pengiriman",
                frontstage_interaction="Client Form Validation & Payment Gateway SDK iframe",
                backstage_action="Fraud Detection Matrix & Address Geocoding Parsing",
                support_process="3rd-party Logistics API & Payment Switcher Gateway",
                max_sla_ms=800,
                failure_probability=0.15
            ),
            ServiceBlueprintNode(
                step_id="BP-03",
                stage_name="Fulfillment & Dispatch",
                customer_action="Menerima notifikasi status pesanan & invoice digital",
                physical_evidence="Push Notification, Email Faktur Pajak, Live Map",
                frontstage_interaction="Order Status Dashboard & Realtime Webhook Listener",
                backstage_action="WMS (Warehouse Management System) Automated Pick-Pack Ticket",
                support_process="Kafka Event Streaming & Courier API Integration",
                max_sla_ms=1200,
                failure_probability=0.08
            )
        ]

    def render_blueprint_matrix(self) -> None:
        print_header("ARSITEKTUR SERVICE BLUEPRINT (3-LAYER TRACEABILITY)")
        for node in self.stages:
            print(f"{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} STAGE: {node.step_id} - {node.stage_name} {Color.RESET}")
            print(f"  {Color.CYAN}1. Customer Action      :{Color.RESET} {node.customer_action}")
            print(f"  {Color.WHITE}   Physical Evidence    :{Color.RESET} {Color.DIM}{node.physical_evidence}{Color.RESET}")
            print(f"  {Color.MAGENTA}--- [Line of Interaction] ---------------------------------------------{Color.RESET}")
            print(f"  {Color.GREEN}2. Frontstage (Visible) :{Color.RESET} {node.frontstage_interaction}")
            print(f"  {Color.YELLOW}--- [Line of Visibility] ----------------------------------------------{Color.RESET}")
            print(f"  {Color.YELLOW}3. Backstage (Invisible):{Color.RESET} {node.backstage_action}")
            print(f"  {Color.RED}--- [Line of Internal Interaction] -----------------------------------{Color.RESET}")
            print(f"  {Color.RED}4. Support Processes    :{Color.RESET} {node.support_process}")
            print(f"  {Color.WHITE}   SLA Benchmark        :{Color.RESET} <= {node.max_sla_ms}ms | Resiko Gagal: {int(node.failure_probability*100)}%\n")

    def run_stress_test(self, persona: BehavioralPersona) -> None:
        print_header(f"STRESS TEST RUNTIME: {persona.archetype.value}")
        print(f"Target Mental Model : {Color.CYAN}{persona.mental_model}{Color.RESET}")
        print(f"Friction Threshold  : {Color.YELLOW}{persona.friction_threshold}s latency tolerance{Color.RESET}\n")

        total_latency = 0
        overall_status = True

        for idx, stage in enumerate(self.stages, 1):
            print(f"{Color.BOLD}Simulasi Tahap {idx}: {stage.stage_name}...{Color.RESET}")
            # Simulasi latensi runtime
            simulated_latency = stage.max_sla_ms + (180 if stage.failure_probability > 0.1 else -40)
            total_latency += simulated_latency
            time.sleep(0.2)

            is_breached = (simulated_latency / 1000.0) > persona.friction_threshold
            if is_breached:
                overall_status = False
                print(f"  {Color.RED}[FAIL SLA BREACH]{Color.RESET} Latensi: {simulated_latency}ms (Batas Persona: {int(persona.friction_threshold*1000)}ms)")
                print(f"  {Color.RED}* Dampak Perilaku:{Color.RESET} Frustrasi pada titik \"{stage.frontstage_interaction}\"")
                print(f"  {Color.RED}* Akar Kegagalan :{Color.RESET} Backstage bottleneck pada [{stage.backstage_action}]")
            else:
                print(f"  {Color.GREEN}[PASS HEALTHY]{Color.RESET} Latensi: {simulated_latency}ms <= Target SLA")
            print()

        print("-" * 70)
        if overall_status:
            print(f"{Color.GREEN}{Color.BOLD}HASIL: SERVICE BLUEPRINT LOLOS PENGUJIAN USER RESILIENCE!{Color.RESET}")
        else:
            print(f"{Color.RED}{Color.BOLD}HASIL: SERVICE BLUEPRINT MEMBUTUHKAN MITIGASI FRONTSTAGE/BACKSTAGE!{Color.RESET}")
            print(f"{Color.YELLOW}Rekomendasi Arsitektur UX:{Color.RESET}")
            print(f"  - Terapkan Optimistic UI Update pada Frontstage Interaction.")
            print(f"  - Sediakan Fallback Asinkron (Graceful Degradation) pada Support Processes.")

# --- Interactive CLI Workflow ---

def display_menu() -> None:
    print(f"\n{Color.CYAN}{Color.BOLD}=== SIMULASI PEMODELAN PERILAKU & SERVICE BLUEPRINT ==={Color.RESET}")
    print(f" {Color.WHITE}1.{Color.RESET} Jalankan Sintesis Riset Kualitatif (Affinity Matrix)")
    print(f" {Color.WHITE}2.{Color.RESET} Tampilkan Arsitektur Service Blueprint Lengkap (3-Line Framework)")
    print(f" {Color.WHITE}3.{Color.RESET} Jalankan Simulasi Stress-Test Resiliensi Persona Pengguna")
    print(f" {Color.WHITE}4.{Color.RESET} Ekspor Spesifikasi Blueprint JSON (Production Contract)")
    print(f" {Color.WHITE}5.{Color.RESET} Keluar dari Lab")

def export_json_spec(engine: ServiceBlueprintSimulator) -> None:
    blueprint_dict = {
        "blueprint_version": "3.0.0-PROD",
        "domain": "E-Commerce Checkout & Fulfillment",
        "lines_of_separation": [
            "Line of Interaction (Customer <-> Frontstage)",
            "Line of Visibility (Frontstage <-> Backstage)",
            "Line of Internal Interaction (Backstage <-> Support)"
        ],
        "stages": [
            {
                "id": node.step_id,
                "stage": node.stage_name,
                "customer_action": node.customer_action,
                "frontstage": node.frontstage_interaction,
                "backstage": node.backstage_action,
                "support": node.support_process,
                "sla_ms": node.max_sla_ms
            }
            for node in engine.stages
        ]
    }
    print_header("EKSPOR SPESIFIKASI BLUEPRINT KE JSON RUNTIME")
    formatted = json.dumps(blueprint_dict, indent=2, ensure_ascii=False)
    print(f"{Color.GREEN}{formatted}{Color.RESET}")

def main() -> None:
    synthesis_engine = ResearchSynthesisEngine()
    blueprint_sim = ServiceBlueprintSimulator()

    default_persona = BehavioralPersona(
        archetype=BehavioralArchetype.EFFICIENCY_SEEKER,
        primary_goal="Menyelesaikan transaksi belanja dalam waktu kurang dari 60 detik",
        friction_threshold=0.6,
        mental_model="Satu klik konfirmasi instan tanpa interupsi layar sekunder",
        core_frustrations=[
            "Loading bar tanpa indikator persentase",
            "Validasi form yang lambat merespons"
        ]
    )

    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        # Mode non-interaktif untuk CI/CD / pengujian otomatis
        print(f"{Color.CYAN}Menjalankan demonstrasi mode otomatis...{Color.RESET}")
        synthesis_engine.run_affinity_clustering()
        blueprint_sim.render_blueprint_matrix()
        blueprint_sim.run_stress_test(default_persona)
        return

    while True:
        display_menu()
        try:
            choice = input(f"\n{Color.YELLOW}Pilih menu (1-5): {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Color.DIM}Lab dihentikan.{Color.RESET}")
            break

        if choice == "1":
            clusters = synthesis_engine.run_affinity_clustering()
            print_header("RINGKASAN KLASTER AFINITAS")
            for cluster_name, items in clusters.items():
                print(f"{Color.BOLD}{Color.WHITE}Kategori: {cluster_name} ({len(items)} Temuan){Color.RESET}")
                for item in items:
                    print(f"  - [{item.behavior_indicator}] Skor Sentimen: {item.sentiment_score:+.2f}")
        elif choice == "2":
            blueprint_sim.render_blueprint_matrix()
        elif choice == "3":
            blueprint_sim.run_stress_test(default_persona)
        elif choice == "4":
            export_json_spec(blueprint_sim)
        elif choice == "5":
            print(f"{Color.GREEN}Lab selesai. Selamat memodelkan arsitektur Service Blueprint!{Color.RESET}\n")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan masukkan nomor 1 - 5.{Color.RESET}")

if __name__ == "__main__":
    main()

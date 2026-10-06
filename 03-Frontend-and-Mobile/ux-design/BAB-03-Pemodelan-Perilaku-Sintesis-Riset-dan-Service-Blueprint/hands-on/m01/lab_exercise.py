#!/usr/bin/env python3
"""
Lab Exercise: Pemodelan Perilaku, Sintesis Riset, dan Service Blueprint
Modul 01 - UX Design Architecture & Research Synthesis Simulation

Simulasi teknis interaktif untuk memahami:
1. Behavioral Persona & Mental Model Mapping
2. Qualitative Affinity Clustering (Synthesizing Research Observations)
3. Service Blueprint Multi-tier Pipeline Execution (Frontstage, Backstage, Support)
"""

import sys
import time
import textwrap
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional

# ANSI Color Codes for Terminal UI
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Foreground
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    
    # Background
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_DARK = "\033[100m"


class TouchpointType(Enum):
    PHYSICAL_EVIDENCE = "Physical/Digital Evidence"
    CUSTOMER_ACTION = "Customer Action"
    FRONTSTAGE = "Frontstage (Line of Interaction)"
    BACKSTAGE = "Backstage (Line of Visibility)"
    SUPPORT_PROCESS = "Support Process (Line of Internal Interaction)"


@dataclass
class ResearchObservation:
    id: str
    quote: str
    participant_type: str
    theme: Optional[str] = None
    sentiment_score: float = 0.0  # -1.0 to 1.0


@dataclass
class PersonaSpectrum:
    dimension: str
    left_anchor: str
    right_anchor: str
    current_value: float  # 0.0 to 1.0


@dataclass
class BlueprintStep:
    step_id: str
    phase_name: str
    physical_evidence: str
    customer_action: str
    frontstage_action: str
    backstage_action: str
    support_process: str
    pain_point_risk: str
    success_metric: str


class UXSynthesisEngine:
    def __init__(self):
        self.observations: List[ResearchObservation] = [
            ResearchObservation("OBS-101", "Saya bingung membedakan opsi instan vs terjadwal pada menu awal.", "First-time User", None, -0.6),
            ResearchObservation("OBS-102", "Notifikasi SMS terlambat datang saat kurir sudah mendekati alamat.", "Power User", None, -0.8),
            ResearchObservation("OBS-103", "Struk digital sangat rapi dan mudah diekspor ke PDF laporan kantor.", "Corporate User", None, 0.9),
            ResearchObservation("OBS-104", "Saya ingin melacak titik koordinat kurir secara real-time tanpa reload.", "Power User", None, 0.4),
            ResearchObservation("OBS-105", "Instruksi pada input alamat cadangan terlalu kecil di layar ponsel.", "Elderly User", None, -0.5),
            ResearchObservation("OBS-106", "CS langsung membalas chat komplain dalam hitungan detik via bot.", "First-time User", None, 0.7),
        ]
        
        self.persona_spectrums: List[PersonaSpectrum] = [
            PersonaSpectrum("Tech Literacy", "Novice", "Digital Native", 0.75),
            PersonaSpectrum("Patience for Checkout", "Wants 1-Click", "Detail Inspector", 0.30),
            PersonaSpectrum("Risk Tolerance", "Prefers COD", "Fully Pre-paid Card", 0.65),
            PersonaSpectrum("Frequency of Need", "Ad-hoc / Emergencies", "Scheduled Routine", 0.85),
        ]
        
        self.blueprint_pipeline: List[BlueprintStep] = [
            BlueprintStep(
                step_id="BP-01",
                phase_name="Discovery & Order Initiation",
                physical_evidence="Mobile App Splash Screen, Lokasi GPS Device",
                customer_action="Membuka aplikasi dan memilih destinasi penjemputan",
                frontstage_action="UI menampilkan estimasi harga & rute terdekat",
                backstage_action="Algoritma Dispatcher mencocokkan ketersediaan armada terdekat",
                support_process="Geo-Routing API, Credit Check Engine",
                pain_point_risk="GPS drift menyebabkan salah titik jemput",
                success_metric="Waktu input order < 45 detik"
            ),
            BlueprintStep(
                step_id="BP-02",
                phase_name="Transaction & Handover",
                physical_evidence="Push Notification, QR Code Handshake, Slip Fisik",
                customer_action="Memperlihatkan barcode ke kurir saat barang diambil",
                frontstage_action="Kurir memindai barcode via Driver-App Scanner",
                backstage_action="Status order diperbarui jadi 'In Transit' di Database Cluster",
                support_process="Inventory Event Broker (Kafka), SMS Gateway Dispatcher",
                pain_point_risk="Kamera driver gagal fokus membaca QR tergores",
                success_metric="Handshake verifikasi < 10 detik"
            ),
            BlueprintStep(
                step_id="BP-03",
                phase_name="Post-Fulfillment & Feedback",
                physical_evidence="In-app Review Sheet, E-Receipt PDF via Email",
                customer_action="Memberikan rating bintang 5 dan ulasan kecepatan",
                frontstage_action="UI menampilkan animasi konfirmasi dan ucapan terima kasih",
                backstage_action="Sentimen ulasan dihitung & ditautkan ke performa driver",
                support_process="Analytics Data Lake ETL, Loyalty Points Accounting Engine",
                pain_point_risk="Pop-up ulasan terlalu agresif menghalangi invoice",
                success_metric="NPS > 65 & CSAT > 4.5/5.0"
            )
        ]

    def render_header(self, title: str, subtitle: str = "") -> None:
        print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} === {title} === {Color.RESET}")
        if subtitle:
            print(f"{Color.CYAN}{subtitle}{Color.RESET}")
        print(f"{Color.DIM}{'─' * 70}{Color.RESET}")

    def run_affinity_clustering(self) -> None:
        self.render_header("TAHAP 1: SINTESIS RISET KUALITATIF (AFFINITY MAPPING)", 
                           "Mengelompokkan 'Raw Observations' menjadi 'Thematic Clusters'")
        
        print(f"{Color.YELLOW}Data Mentah Catatan Observasi Lapangan:{Color.RESET}")
        for obs in self.observations:
            sentiment_indicator = f"{Color.GREEN}[+] Positif" if obs.sentiment_score > 0 else f"{Color.RED}[-] Negatif"
            print(f"  {Color.BOLD}{obs.id}{Color.RESET} ({obs.participant_type}): \"{obs.quote}\" -> {sentiment_indicator}{Color.RESET}")
        
        print(f"\n{Color.CYAN}[Menjalankan Algoritma Sintesis & Ekstraksi Tema...]{Color.RESET}")
        time.sleep(0.6)
        
        # Rule-based clustering for UX simulation
        clusters: Dict[str, List[ResearchObservation]] = {
            "Onboarding & Clarity": [],
            "Fulfillment & Real-time Tracking": [],
            "Post-service & Customer Assurance": []
        }
        
        for obs in self.observations:
            if "opsi instan" in obs.quote or "input alamat" in obs.quote:
                obs.theme = "Onboarding & Clarity"
                clusters["Onboarding & Clarity"].append(obs)
            elif "kurir" in obs.quote or "melacak" in obs.quote or "SMS" in obs.quote:
                obs.theme = "Fulfillment & Real-time Tracking"
                clusters["Fulfillment & Real-time Tracking"].append(obs)
            else:
                obs.theme = "Post-service & Customer Assurance"
                clusters["Post-service & Customer Assurance"].append(obs)
                
        for cluster_name, items in clusters.items():
            print(f"\n{Color.MAGENTA}{Color.BOLD}>>> Cluster Tema: {cluster_name}{Color.RESET} ({len(items)} temuan)")
            for item in items:
                print(f"    • [{item.id}] {item.quote} ({Color.DIM}{item.participant_type}{Color.RESET})")
        print(f"\n{Color.GREEN}✓ Sintesis Selesai: 3 tema perilaku utama telah dipetakan.{Color.RESET}")

    def render_behavioral_persona(self) -> None:
        self.render_header("TAHAP 2: PEMODELAN PERILAKU (BEHAVIORAL SPECTRUM)",
                           "Membentuk Persona Berbasis Kontinum Perilaku Nyata (Bukan Demografi Klise)")
        
        print(f"{Color.WHITE}{Color.BOLD}Target Archetype: 'The High-Velocity Logistics Orchestrator'{Color.RESET}")
        print(f"Mental Model: 'Waktu adalah mata uang. Antarmuka harus prediktif tanpa friksi konfirmasi berlebih.'\n")
        
        for spec in self.persona_spectrums:
            bar_width = 30
            pos = int(spec.current_value * bar_width)
            left_fill = "═" * pos
            cursor = "🔘"
            right_fill = "─" * (bar_width - pos)
            pct = int(spec.current_value * 100)
            
            print(f"{Color.CYAN}{spec.dimension.ljust(22)}{Color.RESET}: [{Color.YELLOW}{spec.left_anchor}{Color.RESET}] {left_fill}{cursor}{right_fill} [{Color.YELLOW}{spec.right_anchor}{Color.RESET}] ({pct}%)")
        print(f"\n{Color.GREEN}✓ Model Perilaku Tervalidasi terhadap 84% respons klaster sasaran.{Color.RESET}")

    def render_service_blueprint(self) -> None:
        self.render_header("TAHAP 3: SERVICE BLUEPRINT EXECUTION MATRIX",
                           "Pemetaan Lintas Lapisan: Dari Interaksi Pelanggan hingga Sistem Penopang")
        
        for idx, step in enumerate(self.blueprint_pipeline, 1):
            print(f"\n{Color.BG_MAGENTA}{Color.WHITE}{Color.BOLD} FASE {idx}: {step.phase_name.upper()} ({step.step_id}) {Color.RESET}")
            
            # Layer 1: Physical / Digital Evidence
            print(f"  {Color.WHITE}{Color.BOLD}[1. Bukti Fisik/Digital]{Color.RESET}")
            print(f"     └─ {Color.CYAN}{step.physical_evidence}{Color.RESET}")
            
            # Layer 2: Customer Action
            print(f"  {Color.WHITE}{Color.BOLD}[2. Customer Action]{Color.RESET}")
            print(f"     └─ {Color.GREEN}{step.customer_action}{Color.RESET}")
            
            # Line of Interaction
            print(f"     {Color.DIM}┈┈┈┈┈┈┈┈┈┈┈ [ Line of Interaction ] ┈┈┈┈┈┈┈┈┈┈┈{Color.RESET}")
            
            # Layer 3: Frontstage
            print(f"  {Color.WHITE}{Color.BOLD}[3. Frontstage Interaction]{Color.RESET}")
            print(f"     └─ {Color.YELLOW}{step.frontstage_action}{Color.RESET}")
            
            # Line of Visibility
            print(f"     {Color.DIM}┈┈┈┈┈┈┈┈┈┈┈ [ Line of Visibility ] ┈┈┈┈┈┈┈┈┈┈┈{Color.RESET}")
            
            # Layer 4: Backstage
            print(f"  {Color.WHITE}{Color.BOLD}[4. Backstage Actions]{Color.RESET}")
            print(f"     └─ {Color.MAGENTA}{step.backstage_action}{Color.RESET}")
            
            # Line of Internal Interaction
            print(f"     {Color.DIM}┈┈┈┈┈┈┈┈┈┈┈ [ Line of Internal Interaction ] ┈┈┈┈┈┈┈┈┈┈┈{Color.RESET}")
            
            # Layer 5: Support Process
            print(f"  {Color.WHITE}{Color.BOLD}[5. Support Processes]{Color.RESET}")
            print(f"     └─ {Color.BLUE}{step.support_process}{Color.RESET}")
            
            # Governance & Fail-points
            print(f"  {Color.RED}{Color.BOLD}[Risk / Fail Point]:{Color.RESET} {step.pain_point_risk}")
            print(f"  {Color.GREEN}{Color.BOLD}[Target Success Metric]:{Color.RESET} {step.success_metric}")
            print(f"{Color.DIM}{'─' * 70}{Color.RESET}")
            time.sleep(0.4)

    def interactive_menu(self) -> None:
        while True:
            print(f"\n{Color.BG_DARK}{Color.WHITE}{Color.BOLD} LAB EXERCISE: SERVICE BLUEPRINT & RESEARCH SYNTHESIS {Color.RESET}")
            print(f"{Color.CYAN}1.{Color.RESET} Jalankan Sintesis Riset Kualitatif (Affinity Diagram)")
            print(f"{Color.CYAN}2.{Color.RESET} Tampilkan Pemodelan Spektrum Perilaku Persona")
            print(f"{Color.CYAN}3.{Color.RESET} Eksekusi Multi-Layer Service Blueprint")
            print(f"{Color.CYAN}4.{Color.RESET} Jalankan Seluruh Rangkaian Simulasi (End-to-End)")
            print(f"{Color.CYAN}5.{Color.RESET} Keluar (Exit)")
            
            try:
                choice = input(f"\n{Color.YELLOW}Pilih modul simulasi [1-5]: {Color.RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{Color.DIM}Sesi diakhiri.{Color.RESET}")
                break

            if choice == "1":
                self.run_affinity_clustering()
            elif choice == "2":
                self.render_behavioral_persona()
            elif choice == "3":
                self.render_service_blueprint()
            elif choice == "4":
                self.run_affinity_clustering()
                self.render_behavioral_persona()
                self.render_service_blueprint()
                print(f"\n{Color.GREEN}{Color.BOLD}>>> Simulasi End-to-End Fondasi UX Berhasil Diselesaikan! <<<{Color.RESET}\n")
            elif choice == "5":
                print(f"{Color.GREEN}Terima kasih. Program simulasi selesai.{Color.RESET}")
                break
            else:
                print(f"{Color.RED}Pilihan tidak valid. Silakan pilih nomor 1 sampai 5.{Color.RESET}")


def main():
    engine = UXSynthesisEngine()
    
    # Auto-run in non-interactive terminal or when --demo / --all is provided
    if len(sys.argv) > 1 and sys.argv[1] in ("--demo", "--all", "-a"):
        engine.run_affinity_clustering()
        engine.render_behavioral_persona()
        engine.render_service_blueprint()
        print(f"\n{Color.GREEN}{Color.BOLD}Mode Batch Demo Selesai.{Color.RESET}")
        return

    # Check if standard input is an interactive TTY
    if not sys.stdin.isatty():
        engine.run_affinity_clustering()
        engine.render_behavioral_persona()
        engine.render_service_blueprint()
        print(f"\n{Color.GREEN}{Color.BOLD}Non-interactive terminal dideteksi: Simulasi lengkap otomatis dieksekusi.{Color.RESET}")
        return

    engine.interactive_menu()


if __name__ == "__main__":
    main()

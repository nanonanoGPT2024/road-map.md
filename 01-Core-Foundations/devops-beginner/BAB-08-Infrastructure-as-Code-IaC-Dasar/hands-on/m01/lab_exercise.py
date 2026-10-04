#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi Infrastructure as Code (IaC) Dasar
BAB 08: Infrastructure as Code (IaC) Dasar - DevOps Beginner

Materi Praktik:
1. Konsep Deklaratif vs Imperatif
2. Desired State vs Actual State & State Management (state file)
3. Siklus Hidup IaC: Init -> Plan -> Apply -> Drift Detection -> Destroy
4. Pembuktian Sifat Idempoten (Idempotency)
"""

import sys
import time
import json
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional

# ANSI Color Codes untuk visualisasi terminal interaktif
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

@dataclass
class Resource:
    id: str
    resource_type: str
    properties: Dict[str, Any]
    status: str = "PROVISIONED"

class MiniIaCEngine:
    """Simulasi Mini Engine IaC (mirip arsitektur core Terraform/OpenTofu)"""

    def __init__(self):
        # Desired State: Definisi deklaratif spesifikasi infrastruktur yang diinginkan
        self.desired_state: Dict[str, Resource] = {
            "vpc-main": Resource(
                id="vpc-main",
                resource_type="aws_vpc",
                properties={"cidr_block": "10.0.0.0/16", "enable_dns": True}
            ),
            "subnet-public": Resource(
                id="subnet-public",
                resource_type="aws_subnet",
                properties={"cidr_block": "10.0.1.0/24", "zone": "ap-southeast-1a"}
            ),
            "vm-web-server": Resource(
                id="vm-web-server",
                resource_type="aws_instance",
                properties={"instance_type": "t3.micro", "ami": "ami-ubuntu-22.04", "tags": {"Env": "Production"}}
            )
        }
        # Actual State: Kondisi riil infrastruktur di cloud provider
        self.actual_cloud_state: Dict[str, Resource] = {}
        # State File (iac.tfstate): Catatan pemetaan engine antara kode deklaratif dan resource nyata
        self.state_file: Dict[str, Any] = {}
        self.initialized: bool = False

    def init_workspace(self):
        """Tahap init: Menyiapkan backend state & provider plugin simulasi"""
        print(f"\n{Colors.CYAN}{Colors.BOLD}[STEP 1: INIT - Inisialisasi Backend & Provider]{Colors.RESET}")
        time.sleep(0.4)
        print(f"{Colors.DIM}Mengunduh provider simulasi 'hashicorp/aws' v5.0...{Colors.RESET}")
        time.sleep(0.4)
        print(f"{Colors.DIM}Menyiapkan backend penyimpanan state lokal (mini-terraform.tfstate)...{Colors.RESET}")
        self.initialized = True
        print(f"{Colors.GREEN}✔ Inisialisasi selesai. Workspace siap untuk operasi IaC.{Colors.RESET}")

    def generate_plan(self) -> List[Dict[str, Any]]:
        """Tahap plan: Membandingkan Desired State vs State File (Diff Calculation)"""
        if not self.initialized:
            print(f"{Colors.RED}✖ Error: Jalankan init terlebih dahulu!{Colors.RESET}")
            return []

        print(f"\n{Colors.CYAN}{Colors.BOLD}[STEP 2: PLAN - Kalkulasi Execution Plan (Diff Engine)]{Colors.RESET}")
        diff_actions: List[Dict[str, Any]] = []

        # 1. Deteksi create (+) atau update (~)
        for res_id, desired_res in self.desired_state.items():
            if res_id not in self.state_file:
                diff_actions.append({"action": "CREATE", "resource": desired_res})
            else:
                # Periksa apakah atribut berubah
                recorded = self.state_file[res_id]
                if recorded.get("properties") != desired_res.properties:
                    diff_actions.append({
                        "action": "UPDATE",
                        "resource": desired_res,
                        "old_props": recorded.get("properties"),
                        "new_props": desired_res.properties
                    })

        # 2. Deteksi destroy (-) jika ada resource di state file tapi hilang dari desired state
        for res_id in self.state_file:
            if res_id not in self.desired_state:
                diff_actions.append({"action": "DESTROY", "resource_id": res_id})

        # Cetak output visual diff seperti format Terraform
        if not diff_actions:
            print(f"{Colors.GREEN}✔ No changes. Infrastruktur Anda sudah sesuai dengan target state (Idempoten).{Colors.RESET}")
            return []

        print(f"{Colors.YELLOW}Rencana eksekusi terdeteksi ({len(diff_actions)} perubahan):{Colors.RESET}")
        for item in diff_actions:
            act = item["action"]
            if act == "CREATE":
                res = item["resource"]
                print(f"  {Colors.GREEN}+ create {res.resource_type}.{res.id}{Colors.RESET}")
                for k, v in res.properties.items():
                    print(f"      + {k} = {json.dumps(v)}")
            elif act == "UPDATE":
                res = item["resource"]
                print(f"  {Colors.YELLOW}~ update in-place {res.resource_type}.{res.id}{Colors.RESET}")
                print(f"      ~ properties: {json.dumps(item['old_props'])} -> {json.dumps(item['new_props'])}")
            elif act == "DESTROY":
                print(f"  {Colors.RED}- destroy {item['resource_id']}{Colors.RESET}")

        return diff_actions

    def apply_plan(self, actions: List[Dict[str, Any]]):
        """Tahap apply: Menerapkan perubahan ke Cloud & Memperbarui State File"""
        if not actions:
            print(f"{Colors.DIM}Tidak ada aksi perubahan yang perlu diaplikasikan.{Colors.RESET}")
            return

        print(f"\n{Colors.CYAN}{Colors.BOLD}[STEP 3: APPLY - Menerapkan Perubahan ke Infrastruktur]{Colors.RESET}")
        for item in actions:
            act = item["action"]
            if act == "CREATE":
                res: Resource = item["resource"]
                print(f"Membuat {res.resource_type}.{res.id} ... ", end="", flush=True)
                time.sleep(0.5)
                # Provision ke real cloud & record ke state
                self.actual_cloud_state[res.id] = Resource(
                    id=res.id,
                    resource_type=res.resource_type,
                    properties=dict(res.properties),
                    status="ACTIVE"
                )
                self.state_file[res.id] = {
                    "resource_type": res.resource_type,
                    "properties": dict(res.properties),
                    "status": "ACTIVE"
                }
                print(f"{Colors.GREEN}[DIBUAT]{Colors.RESET}")

            elif act == "UPDATE":
                res = item["resource"]
                print(f"Mengubah {res.resource_type}.{res.id} ... ", end="", flush=True)
                time.sleep(0.5)
                self.actual_cloud_state[res.id].properties = dict(res.properties)
                self.state_file[res.id]["properties"] = dict(res.properties)
                print(f"{Colors.YELLOW}[DIPERBARUI]{Colors.RESET}")

            elif act == "DESTROY":
                res_id = item["resource_id"]
                print(f"Menghapus {res_id} ... ", end="", flush=True)
                time.sleep(0.5)
                self.actual_cloud_state.pop(res_id, None)
                self.state_file.pop(res_id, None)
                print(f"{Colors.RED}[DIHAPUS]{Colors.RESET}")

        print(f"\n{Colors.GREEN}{Colors.BOLD}Apply selesai! State file telah diperbarui secara otomatis.{Colors.RESET}")

    def simulate_drift(self):
        """Simulasi Configuration Drift: Out-of-band manual modification di cloud"""
        print(f"\n{Colors.RED}{Colors.BOLD}[SIMULASI CONFIGURATION DRIFT]{Colors.RESET}")
        print(f"{Colors.YELLOW}Seorang operator manual login ke Web Console Cloud dan:")
        print(f"1. Mengubah ukuran VM 'vm-web-server' dari t3.micro ke t3.2xlarge secara diam-diam.")
        print(f"2. Menghapus subnet 'subnet-public' langsung dari dashboard.{Colors.RESET}")

        if "vm-web-server" in self.actual_cloud_state:
            self.actual_cloud_state["vm-web-server"].properties["instance_type"] = "t3.2xlarge"
        if "subnet-public" in self.actual_cloud_state:
            del self.actual_cloud_state["subnet-public"]

        time.sleep(0.5)
        print(f"{Colors.RED}⚠ Drift berhasil disimulasikan: Cloud nyata sekarang tidak sinkron dengan State File & Desired Code!{Colors.RESET}")

    def refresh_and_reconcile(self):
        """Penyelarasan drift: sinkronisasi state file dengan realita cloud, lalu rekonsiliasi"""
        print(f"\n{Colors.CYAN}{Colors.BOLD}[STEP 4: DRIFT DETECTION & RECONCILIATION]{Colors.RESET}")
        print(f"{Colors.DIM}Menjalankan `iac refresh` untuk membaca kondisi aktual cloud...{Colors.RESET}")
        time.sleep(0.5)

        # Sync state file with actual cloud
        self.state_file.clear()
        for res_id, res in self.actual_cloud_state.items():
            self.state_file[res_id] = {
                "resource_type": res.resource_type,
                "properties": dict(res.properties),
                "status": res.status
            }

        print(f"{Colors.YELLOW}Hasil Refresh: Drift teridentifikasi dalam state!{Colors.RESET}")
        print(f"Mengkalkulasi ulang plan untuk memulihkan Desired State (Self-Healing)...")
        plan = self.generate_plan()
        if plan:
            self.apply_plan(plan)
            print(f"{Colors.GREEN}✔ Infrastruktur berhasil dipulihkan (reconciled) sesuai kode deklaratif!{Colors.RESET}")

    def destroy_all(self):
        """Tahap destroy: Membersihkan seluruh infrastruktur yang terdaftar di state"""
        print(f"\n{Colors.RED}{Colors.BOLD}[STEP 5: DESTROY - Membersihkan Seluruh Resource]{Colors.RESET}")
        time.sleep(0.4)
        for res_id in list(self.state_file.keys()):
            print(f"Menghancurkan {res_id} ... ", end="", flush=True)
            time.sleep(0.3)
            self.actual_cloud_state.pop(res_id, None)
            self.state_file.pop(res_id, None)
            print(f"{Colors.RED}[DESTROYED]{Colors.RESET}")
        print(f"{Colors.GREEN}✔ Seluruh resource telah dibersihkan. Biaya cloud $0.{Colors.RESET}")


def interactive_menu():
    engine = MiniIaCEngine()
    
    header = f"""
{Colors.HEADER}{Colors.BOLD}=====================================================================
    LAB SIMULASI INTERAKTIF: INFRASTRUCTURE AS CODE (IaC) DASAR
               (Mini-IaC Engine Core Concepts Simulation)
====================================================================={Colors.RESET}
Mempelajari:
- Deklaratif vs Imperatif
- Desired State vs Actual State vs State File
- Siklus: Init -> Plan -> Apply -> Idempotency -> Drift Reconcile
"""
    print(header)

    while True:
        print(f"\n{Colors.BOLD}--- MENU PILIHAN SIMULASI ---{Colors.RESET}")
        print(f"{Colors.CYAN}1.{Colors.RESET} Inisialisasi Project (iac init)")
        print(f"{Colors.CYAN}2.{Colors.RESET} Buat Rencana Perubahan (iac plan)")
        print(f"{Colors.CYAN}3.{Colors.RESET} Eksekusi Perubahan (iac apply)")
        print(f"{Colors.CYAN}4.{Colors.RESET} Uji Sifat Idempoten (Jalankan plan/apply ulang tanpa ubah kode)")
        print(f"{Colors.CYAN}5.{Colors.RESET} Simulasikan Configuration Drift (Perubahan manual di cloud)")
        print(f"{Colors.CYAN}6.{Colors.RESET} Deteksi Drift & Rekonsiliasi Otomatis (Self-Healing)")
        print(f"{Colors.CYAN}7.{Colors.RESET} Hancurkan Semua Resource (iac destroy)")
        print(f"{Colors.CYAN}8.{Colors.RESET} Jalankan Skenario Otomatis Penuh (Demo Guided Walkthrough)")
        print(f"{Colors.RED}0.{Colors.RESET} Keluar")

        try:
            choice = input(f"\n{Colors.BOLD}Pilih nomor [0-8]: {Colors.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar dari simulasi.")
            break

        if choice == "1":
            engine.init_workspace()
        elif choice == "2":
            engine.generate_plan()
        elif choice == "3":
            plan = engine.generate_plan()
            engine.apply_plan(plan)
        elif choice == "4":
            print(f"\n{Colors.BLUE}{Colors.BOLD}[PENGUJIAN IDEMPOTENCY]{Colors.RESET}")
            print("Idempotensi menjamin bahwa mengeksekusi instruksi yang sama berkali-kali")
            print("akan menghasilkan kondisi infrastruktur yang sama persis tanpa duplikasi.")
            plan = engine.generate_plan()
            engine.apply_plan(plan)
        elif choice == "5":
            engine.simulate_drift()
        elif choice == "6":
            engine.refresh_and_reconcile()
        elif choice == "7":
            engine.destroy_all()
        elif choice == "8":
            print(f"\n{Colors.CYAN}{Colors.BOLD}=== MEMULAI GUIDED WALKTHROUGH SKENARIO LENGKAP ==={Colors.RESET}")
            engine.init_workspace()
            time.sleep(1)
            plan1 = engine.generate_plan()
            time.sleep(1)
            engine.apply_plan(plan1)
            time.sleep(1)
            print(f"\n{Colors.BLUE}--- Menguji Idempotensi ---{Colors.RESET}")
            plan_idempotent = engine.generate_plan()
            engine.apply_plan(plan_idempotent)
            time.sleep(1)
            print(f"\n{Colors.RED}--- Mensimulasikan Drift ---{Colors.RESET}")
            engine.simulate_drift()
            time.sleep(1)
            engine.refresh_and_reconcile()
            time.sleep(1)
            engine.destroy_all()
            print(f"\n{Colors.GREEN}{Colors.BOLD}=== GUIDED WALKTHROUGH SELESAI ==={Colors.RESET}")
        elif choice == "0":
            print(f"{Colors.GREEN}Terima kasih telah mempelajari fondasi IaC! Sampai jumpa.{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid. Silakan pilih 0-8.{Colors.RESET}")

if __name__ == "__main__":
    interactive_menu()

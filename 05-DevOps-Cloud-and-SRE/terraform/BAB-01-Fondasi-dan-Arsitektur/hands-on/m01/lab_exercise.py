#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Fondasi dan Arsitektur Inti Terraform
BAB-01: Fondasi dan Arsitektur (Desired State, State Management, Provider Core, Lifecycle & Drift)

Skrip ini adalah simulator interaktif mandiri yang memperagakan bagaimana Terraform Core:
1. Membaca Desired State (Kode HCL)
2. Membandingkan dengan State File (terraform.tfstate) dan Actual Cloud Infrastructure
3. Menyusun Execution Graph & Plan (+ create, ~ update, - destroy)
4. Melakukan Apply dan Reconciliation Engine
5. Mendeteksi Drift (Manual configuration change di luar Terraform)
"""

import sys
import time
import json
import copy

# ANSI Color Codes untuk output visual terminal
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"

def print_banner():
    print(f"\n{CYAN}{BOLD}========================================================================{RESET}")
    print(f"{CYAN}{BOLD}   LAB 01: TERRAFORM CORE ARCHITECTURE & LIFECYCLE SIMULATOR           {RESET}")
    print(f"{CYAN}{BOLD}   Mekanisme Desired State vs Actual State & State Management           {RESET}")
    print(f"{CYAN}{BOLD}========================================================================{RESET}\n")

class TerraformSimulator:
    def __init__(self):
        self.initialized = False
        self.state_version = 4
        self.serial = 0
        
        # 1. Desired State (Representasi kode HCL main.tf)
        self.desired_code = {
            "aws_instance.web_server": {
                "ami": "ami-0c55b159cbfafe1f0",
                "instance_type": "t3.micro",
                "tags": {"Environment": "Production", "Role": "Web"}
            },
            "aws_s3_bucket.app_storage": {
                "bucket": "acme-corp-assets-prod-2026",
                "versioning": True,
                "tags": {"Owner": "DevOps Team"}
            }
        }

        # 2. State File (terraform.tfstate snapshot)
        self.state_file = {}

        # 3. Actual State (Realita di Cloud Provider AWS)
        self.cloud_reality = {}

    def init(self):
        print(f"\n{BOLD}{BLUE}[+] Menjalankan 'terraform init'...{RESET}")
        time.sleep(0.4)
        print(f"  {CYAN}* Initializing provider plugins...{RESET}")
        time.sleep(0.3)
        print(f"  {CYAN}* Finding hashicorp/aws versions matching '~> 5.0'...{RESET}")
        time.sleep(0.3)
        print(f"  {GREEN}✓ Installing hashicorp/aws v5.42.0 (plugin binary verified){RESET}")
        print(f"  {GREEN}✓ Created lock file .terraform.lock.hcl{RESET}")
        self.initialized = True
        print(f"{GREEN}{BOLD}Terraform has been successfully initialized!{RESET}\n")

    def plan(self):
        if not self.initialized:
            print(f"{RED}{BOLD}ERROR: Provider plugin belum diinisialisasi. Jalankan 'terraform init' terlebih dahulu!{RESET}")
            return None

        print(f"\n{BOLD}{BLUE}[+] Menjalankan 'terraform plan'...{RESET}")
        print(f"  {CYAN}1. Membaca HCL code (Desired State){RESET}")
        print(f"  {CYAN}2. Membaca local terraform.tfstate (Recorded State){RESET}")
        print(f"  {CYAN}3. Refreshing actual cloud resource state via Provider RPC...{RESET}")
        time.sleep(0.5)

        plan_actions = {}
        all_res_keys = set(self.desired_code.keys()).union(self.state_file.keys())

        for key in all_res_keys:
            in_code = key in self.desired_code
            in_state = key in self.state_file
            in_cloud = key in self.cloud_reality

            if in_code and not in_state:
                plan_actions[key] = {
                    "action": "CREATE",
                    "diff": self.desired_code[key]
                }
            elif in_code and in_state:
                # Cek modifikasi atribut
                if self.desired_code[key] != self.cloud_reality.get(key):
                    plan_actions[key] = {
                        "action": "UPDATE",
                        "old": self.cloud_reality.get(key, {}),
                        "new": self.desired_code[key]
                    }
                else:
                    plan_actions[key] = {"action": "NO_OP"}
            elif not in_code and in_state:
                plan_actions[key] = {
                    "action": "DESTROY",
                    "current": self.state_file[key]
                }

        # Print plan diff
        print(f"\n{BOLD}Terraform will perform the following actions:{RESET}")
        create_c, update_c, destroy_c = 0, 0, 0

        for res, data in plan_actions.items():
            act = data["action"]
            if act == "CREATE":
                create_c += 1
                print(f"  {GREEN}{BOLD}+ {res}{RESET} will be created")
                for k, v in data["diff"].items():
                    print(f"      {GREEN}+ {k:<15} = {json.dumps(v)}{RESET}")
            elif act == "UPDATE":
                update_c += 1
                print(f"  {YELLOW}{BOLD}~ {res}{RESET} will be updated in-place")
                for k, v in data["new"].items():
                    old_v = data["old"].get(k)
                    if old_v != v:
                        print(f"      {YELLOW}~ {k:<15} = {json.dumps(old_v)} => {json.dumps(v)}{RESET}")
            elif act == "DESTROY":
                destroy_c += 1
                print(f"  {RED}{BOLD}- {res}{RESET} will be destroyed")
            elif act == "NO_OP":
                print(f"  {WHITE}• {res}: No changes. Infrastructure matches configuration.{RESET}")

        print(f"\n{BOLD}Plan Summary:{RESET} "
              f"{GREEN}{create_c} to add{RESET}, "
              f"{YELLOW}{update_c} to change{RESET}, "
              f"{RED}{destroy_c} to destroy{RESET}.")
        return plan_actions

    def apply(self, plan_actions):
        if not self.initialized:
            print(f"{RED}Error: Inisialisasi belum dilakukan.{RESET}")
            return
        if not plan_actions:
            print(f"{YELLOW}Tidak ada plan aktif untuk dieksekusi.{RESET}")
            return

        has_changes = any(item["action"] != "NO_OP" for item in plan_actions.values())
        if not has_changes:
            print(f"{GREEN}Infrastructure sudah up-to-date. Tidak ada apply yang dibutuhkan.{RESET}")
            return

        print(f"\n{BOLD}{YELLOW}[?] Apakah Anda ingin mengeksekusi rencana ini? (yes/no): {RESET}", end="")
        try:
            confirm = input().strip().lower()
        except EOFError:
            confirm = "yes"

        if confirm != "yes":
            print(f"{RED}Apply dibatalkan oleh pengguna.{RESET}")
            return

        print(f"\n{BOLD}{BLUE}[+] Menjalankan 'terraform apply'...{RESET}")
        self.serial += 1

        for res, data in plan_actions.items():
            act = data["action"]
            if act == "CREATE":
                print(f"  {CYAN}{res}: Creating...{RESET}")
                time.sleep(0.4)
                # Sinkronkan ke cloud & state
                self.cloud_reality[res] = copy.deepcopy(data["diff"])
                self.state_file[res] = copy.deepcopy(data["diff"])
                print(f"  {GREEN}{res}: Creation complete after 1s (ID: {hex(abs(hash(res)))[:10]}){RESET}")
            elif act == "UPDATE":
                print(f"  {YELLOW}{res}: Modifying...{RESET}")
                time.sleep(0.4)
                self.cloud_reality[res] = copy.deepcopy(data["new"])
                self.state_file[res] = copy.deepcopy(data["new"])
                print(f"  {GREEN}{res}: Modifications complete after 1s{RESET}")
            elif act == "DESTROY":
                print(f"  {RED}{res}: Destroying...{RESET}")
                time.sleep(0.4)
                self.cloud_reality.pop(res, None)
                self.state_file.pop(res, None)
                print(f"  {RED}{res}: Destruction complete after 1s{RESET}")

        print(f"\n{GREEN}{BOLD}Apply complete! Resources: Updated state file (serial: {self.serial}).{RESET}")

    def simulate_drift(self):
        """Simulasikan modifikasi langsung di Cloud Console tanpa melalui Terraform"""
        print(f"\n{BOLD}{MAGENTA}[!] SIMULASI MANUAL CLOUD DRIFT (Out-of-band Mutation){RESET}")
        if not self.cloud_reality:
            print(f"{YELLOW}Cloud masih kosong! Lakukan apply resource terlebih dahulu.{RESET}")
            return

        print("Pilih simulasi drift yang akan diinjeksikan langsung ke AWS Cloud:")
        print("  1. Ubah instance_type aws_instance.web_server menjadi 't3.large' via AWS Console")
        print("  2. Hapus manual bucket aws_s3_bucket.app_storage via CLI AWS")
        print("  3. Batal")
        try:
            choice = input(f"{BOLD}Pilih (1-3): {RESET}").strip()
        except EOFError:
            choice = "1"

        if choice == "1" and "aws_instance.web_server" in self.cloud_reality:
            self.cloud_reality["aws_instance.web_server"]["instance_type"] = "t3.large"
            print(f"{RED}DRIFT BERHASIL DIINJEKSI: AWS Instance web_server sekarang 't3.large' di Cloud.{RESET}")
            print(f"{YELLOW}Catatan: Kode HCL dan terraform.tfstate masih mencatat 't3.micro'.{RESET}")
        elif choice == "2" and "aws_s3_bucket.app_storage" in self.cloud_reality:
            del self.cloud_reality["aws_s3_bucket.app_storage"]
            print(f"{RED}DRIFT BERHASIL DIINJEKSI: S3 Bucket dihapus langsung dari Cloud.{RESET}")
            print(f"{YELLOW}Catatan: Kode HCL dan terraform.tfstate masih menganggap bucket ada.{RESET}")
        else:
            print("Aksi dibatalkan atau resource belum ada.")

    def inspect_states(self):
        print(f"\n{BOLD}{WHITE}--- DIAGNOSTIK TRI-STATE ENGINE ---{RESET}")
        print(f"{CYAN}{BOLD}1. Desired State (HCL Code - main.tf):{RESET}")
        print(json.dumps(self.desired_code, indent=2))

        print(f"\n{YELLOW}{BOLD}2. Recorded State (terraform.tfstate - Serial: {self.serial}):{RESET}")
        print(json.dumps(self.state_file, indent=2) if self.state_file else "  (State Kosong / Belum ada Apply)")

        print(f"\n{GREEN}{BOLD}3. Actual State (Real-world Cloud Reality):{RESET}")
        print(json.dumps(self.cloud_reality, indent=2) if self.cloud_reality else "  (Cloud Kosong / No Infrastructure)")

    def destroy(self):
        if not self.initialized:
            print(f"{RED}Error: Inisialisasi belum dilakukan.{RESET}")
            return
        if not self.state_file:
            print(f"{YELLOW}Tidak ada resource terkelola di state file untuk di-destroy.{RESET}")
            return

        print(f"\n{BOLD}{RED}[!] 'terraform destroy' diminta.{RESET}")
        print(f"{RED}Resource berikut akan dimusnahkan secara permanen:{RESET}")
        for res in self.state_file.keys():
            print(f"  {RED}- {res}{RESET}")

        try:
            confirm = input(f"{BOLD}{YELLOW}Ketik 'yes' untuk konfirmasi destroy: {RESET}").strip().lower()
        except EOFError:
            confirm = "yes"

        if confirm == "yes":
            self.serial += 1
            print(f"{CYAN}Memusnahkan resource di Cloud Provider...{RESET}")
            time.sleep(0.5)
            self.cloud_reality.clear()
            self.state_file.clear()
            print(f"{GREEN}{BOLD}Destroy complete! Resources: {len(self.state_file)} destroyed. State cleared.{RESET}")
        else:
            print(f"{YELLOW}Destroy dibatalkan.{RESET}")


def interactive_menu():
    sim = TerraformSimulator()
    print_banner()

    while True:
        print(f"\n{BOLD}{WHITE}MENU KONTROL TERRAFORM CORE:{RESET}")
        print("  1. Inisialisasi Plugin (terraform init)")
        print("  2. Hitung Diff & Rencana (terraform plan)")
        print("  3. Rekonsiliasi & Eksekusi (terraform apply)")
        print("  4. Periksa Tri-State (Desired vs State File vs Cloud)")
        print("  5. Injeksikan Manual Cloud Drift (Simulasi Mutasi Liar)")
        print("  6. Hancurkan Infrastruktur (terraform destroy)")
        print("  7. Keluar")

        try:
            choice = input(f"\n{BOLD}{CYAN}Pilih opsi (1-7): {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar dari simulator.")
            break

        if choice == "1":
            sim.init()
        elif choice == "2":
            sim.plan()
        elif choice == "3":
            current_plan = sim.plan()
            if current_plan:
                sim.apply(current_plan)
        elif choice == "4":
            sim.inspect_states()
        elif choice == "5":
            sim.simulate_drift()
        elif choice == "6":
            sim.destroy()
        elif choice == "7":
            print(f"{GREEN}Selesai. Terima kasih telah menjalankan Lab Fondasi Terraform.{RESET}")
            break
        else:
            print(f"{RED}Opsi tidak valid. Masukkan angka 1 sampai 7.{RESET}")

if __name__ == "__main__":
    interactive_menu()

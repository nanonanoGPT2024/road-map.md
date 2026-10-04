#!/usr/bin/env python3
"""
Lab Exercise BAB-06: Data Sources, Remote State, & Multi-Provider Architectures
Simulasi Interaktif Eksekusi Terraform Tingkat Lanjut (Production Grade)
"""

import sys
import time
import json
import random

# ANSI Escape Sequences untuk Pewarnaan Terminal
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_GRAY = "\033[90m"
CLR_WHITE_BG = "\033[47m\033[30m"

class ArchitectureEngine:
    def __init__(self):
        self.remote_state_backend = {
            "bucket": "acme-corp-terraform-state-prod",
            "key": "network/vpc/terraform.tfstate",
            "region": "us-east-1",
            "outputs": {
                "vpc_id_primary": "vpc-088f12a9bc41d01a",
                "vpc_cidr_primary": "10.100.0.0/16",
                "public_subnets_primary": [
                    "subnet-011a88bb99cc",
                    "subnet-022a88bb99dd"
                ],
                "vpc_id_secondary": "vpc-0aa55c91ee8801b",
                "vpc_cidr_secondary": "10.200.0.0/16",
                "public_subnets_secondary": [
                    "subnet-033c77dd88ee"
                ]
            }
        }
        self.providers = {
            "aws.us_east": {
                "region": "us-east-1",
                "role_arn": "arn:aws:iam::112233445566:role/TerraformDeployerUS"
            },
            "aws.eu_central": {
                "region": "eu-central-1",
                "alias": "failover",
                "role_arn": "arn:aws:iam::112233445566:role/TerraformDeployerEU"
            }
        }
        self.data_sources = {}
        self.resources_to_apply = []

    def log(self, tag, message, color=CLR_CYAN):
        timestamp = time.strftime("%H:%M:%S")
        print(f"{CLR_GRAY}[{timestamp}]{CLR_RESET} {color}[{tag}]{CLR_RESET} {message}")

    def banner(self):
        print(f"{CLR_BLUE}{CLR_BOLD}" + "=" * 78 + f"{CLR_RESET}")
        print(f"{CLR_MAGENTA}{CLR_BOLD}   TERRAFORM ENTERPRISE SIMULATOR: BAB 06 ADVANCED ARCHITECTURE{CLR_RESET}")
        print(f"{CLR_CYAN}   Focus: data \"aws_ami\", terraform_remote_state, & Multi-Provider Aliasing{CLR_RESET}")
        print(f"{CLR_BLUE}{CLR_BOLD}" + "=" * 78 + f"{CLR_RESET}\n")

    def simulate_remote_state_fetch(self):
        self.log("INIT", "Reading remote state backend: s3://acme-corp-terraform-state-prod ...", CLR_YELLOW)
        time.sleep(0.6)
        print(f"  {CLR_GRAY}→ Acquiring DynamoDB State Lock (LockID: tf-lock-state-network-prod)...{CLR_RESET}")
        time.sleep(0.4)
        print(f"  {CLR_GREEN}✔ State lock acquired.{CLR_RESET}")
        print(f"  {CLR_GREEN}✔ Remote state fetched and decoded successfully.{CLR_RESET}")
        print(f"  {CLR_GRAY}→ Output schema verified: 2 VPC definitions extracted.{CLR_RESET}\n")

    def simulate_data_sources_lookup(self):
        self.log("DATA_SOURCE", "Querying Provider [aws.us_east (us-east-1)] for latest Ubuntu 22.04 AMI...", CLR_CYAN)
        time.sleep(0.5)
        ami_primary = {
            "id": f"ami-0{random.randint(10000000, 99999999):x}",
            "name": "ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-20261001",
            "owner": "099720109477 (Canonical)",
            "virtualization_type": "hvm",
            "root_device_name": "/dev/sda1"
        }
        self.data_sources["ami_primary"] = ami_primary
        print(f"  {CLR_GREEN}✔ Discovered Primary AMI:{CLR_RESET} {CLR_BOLD}{ami_primary['id']}{CLR_RESET} ({ami_primary['name']})")

        self.log("DATA_SOURCE", "Querying Provider [aws.eu_central (eu-central-1)] for latest Ubuntu 22.04 AMI...", CLR_CYAN)
        time.sleep(0.5)
        ami_secondary = {
            "id": f"ami-0{random.randint(10000000, 99999999):x}",
            "name": "ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-20261001",
            "owner": "099720109477 (Canonical)",
            "virtualization_type": "hvm",
            "root_device_name": "/dev/sda1"
        }
        self.data_sources["ami_secondary"] = ami_secondary
        print(f"  {CLR_GREEN}✔ Discovered Secondary AMI:{CLR_RESET} {CLR_BOLD}{ami_secondary['id']}{CLR_RESET} ({ami_secondary['name']})\n")

    def simulate_plan(self):
        self.log("PLAN", "Compiling Execution Graph & Generating Resource Delta...", CLR_MAGENTA)
        time.sleep(0.7)
        self.resources_to_apply = [
            {
                "action": "create",
                "type": "aws_instance",
                "name": "primary_app_cluster",
                "provider": "aws.us_east",
                "details": {
                    "ami": self.data_sources["ami_primary"]["id"],
                    "instance_type": "c6i.xlarge",
                    "subnet_id": self.remote_state_backend["outputs"]["public_subnets_primary"][0],
                    "vpc_id": self.remote_state_backend["outputs"]["vpc_id_primary"]
                }
            },
            {
                "action": "create",
                "type": "aws_instance",
                "name": "dr_standby_cluster",
                "provider": "aws.eu_central",
                "details": {
                    "ami": self.data_sources["ami_secondary"]["id"],
                    "instance_type": "c6i.large",
                    "subnet_id": self.remote_state_backend["outputs"]["public_subnets_secondary"][0],
                    "vpc_id": self.remote_state_backend["outputs"]["vpc_id_secondary"]
                }
            },
            {
                "action": "create",
                "type": "aws_vpc_peering_connection",
                "name": "cross_region_interconnect",
                "provider": "aws.us_east",
                "details": {
                    "peer_owner_id": "112233445566",
                    "peer_vpc_id": self.remote_state_backend["outputs"]["vpc_id_secondary"],
                    "vpc_id": self.remote_state_backend["outputs"]["vpc_id_primary"],
                    "peer_region": "eu-central-1",
                    "auto_accept": False
                }
            },
            {
                "action": "create",
                "type": "aws_vpc_peering_connection_accepter",
                "name": "cross_region_acceptor",
                "provider": "aws.eu_central",
                "details": {
                    "vpc_peering_connection_id": "(known after apply)"
                }
            }
        ]

        print(f"\n{CLR_WHITE_BG} Terraform Plan Preview: 4 to add, 0 to change, 0 to destroy. {CLR_RESET}\n")
        for res in self.resources_to_apply:
            print(f"  {CLR_GREEN}+ resource \"{res['type']}\" \"{res['name']}\"{CLR_RESET} {{")
            print(f"      {CLR_GRAY}# Configured via provider alias: {res['provider']}{CLR_RESET}")
            for k, v in res["details"].items():
                print(f"      {k:<26} = {CLR_YELLOW}\"{v}\"{CLR_RESET}")
            print("    }\n")

    def simulate_apply(self):
        self.log("APPLY", "Starting parallel resource orchestration...", CLR_YELLOW)
        for i, res in enumerate(self.resources_to_apply, 1):
            time.sleep(0.5)
            print(f"  {CLR_CYAN}[{i}/4] Creating {res['type']}.{res['name']} via [{res['provider']}]...{CLR_RESET}")
            time.sleep(0.4)
            print(f"  {CLR_GREEN}✔ Creation complete after {random.randint(4, 9)}s [id={res['name']}-inst-0x{random.randint(100, 999)}]{CLR_RESET}")

        time.sleep(0.5)
        print(f"\n{CLR_GREEN}{CLR_BOLD}Apply complete! Resources: 4 added, 0 changed, 0 destroyed.{CLR_RESET}")
        print(f"{CLR_GRAY}State lock released successfully from DynamoDB.{CLR_RESET}\n")

    def inspect_remote_state_contract(self):
        print(f"\n{CLR_BOLD}=== Contract Schema: Data Remote State (outputs) ==={CLR_RESET}")
        print(json.dumps(self.remote_state_backend["outputs"], indent=2))
        print()

    def run_interactive(self):
        self.banner()
        while True:
            print(f"{CLR_BOLD}Silakan pilih langkah simulasi:{CLR_RESET}")
            print(f"  {CLR_CYAN}1.{CLR_RESET} Fetch Data Remote State (VPC Network Outputs)")
            print(f"  {CLR_CYAN}2.{CLR_RESET} Query Dynamic Data Sources (AMI Multi-Region)")
            print(f"  {CLR_CYAN}3.{CLR_RESET} Run Terraform Plan (Multi-Provider Aliasing)")
            print(f"  {CLR_CYAN}4.{CLR_RESET} Run Terraform Apply (Deploy Cross-Region)")
            print(f"  {CLR_CYAN}5.{CLR_RESET} Inspect Remote State JSON Schema")
            print(f"  {CLR_CYAN}6.{CLR_RESET} Run Full Automated Pipeline (End-to-End)")
            print(f"  {CLR_RED}0. Keluar{CLR_RESET}")
            choice = input(f"\n{CLR_YELLOW}Pilihan Anda [0-6]: {CLR_RESET}").strip()

            if choice == "1":
                self.simulate_remote_state_fetch()
            elif choice == "2":
                self.simulate_data_sources_lookup()
            elif choice == "3":
                if not self.data_sources:
                    print(f"{CLR_RED}Peringatan: Jalankan opsi 2 terlebih dahulu untuk menginisialisasi Data Sources.{CLR_RESET}\n")
                    self.simulate_data_sources_lookup()
                self.simulate_plan()
            elif choice == "4":
                if not self.resources_to_apply:
                    print(f"{CLR_RED}Peringatan: Menjalankan Plan terlebih dahulu...{CLR_RESET}\n")
                    if not self.data_sources:
                        self.simulate_data_sources_lookup()
                    self.simulate_plan()
                self.simulate_apply()
            elif choice == "5":
                self.inspect_remote_state_contract()
            elif choice == "6":
                print(f"\n{CLR_MAGENTA}--- Memulai Eksekusi Pipeline Otomatis ---{CLR_RESET}")
                self.simulate_remote_state_fetch()
                self.simulate_data_sources_lookup()
                self.simulate_plan()
                self.simulate_apply()
                self.inspect_remote_state_contract()
            elif choice == "0":
                print(f"\n{CLR_GREEN}Selesai. Keluar dari lab exercise BAB-06.{CLR_RESET}")
                break
            else:
                print(f"{CLR_RED}Pilihan tidak valid, coba lagi.{CLR_RESET}\n")

if __name__ == "__main__":
    try:
        engine = ArchitectureEngine()
        if len(sys.argv) > 1 and sys.argv[1] == "--auto":
            engine.banner()
            engine.simulate_remote_state_fetch()
            engine.simulate_data_sources_lookup()
            engine.simulate_plan()
            engine.simulate_apply()
        else:
            engine.run_interactive()
    except KeyboardInterrupt:
        print(f"\n\n{CLR_YELLOW}Operasi dibatalkan oleh pengguna.{CLR_RESET}")
        sys.exit(0)

#!/usr/bin/env python3
"""
Terraform State Refactoring, Brownfield Import & Moved Block Simulation Engine.
Standard: GEMINI.md Enterprise Architecture

Skrip ini mensimulasikan mekanisme internal Terraform Core:
1. Parsing dan manipulasi in-memory State File JSON.
2. Resolusi declarative import blocks.
3. Graph reconciliation menggunakan declarative moved blocks.
4. State splitting: Ekstraksi monolithic state menjadi micro-states terpisah.
5. Verifikasi idempotensi dan validasi zero-destruction.
"""

import copy
import json
import os
import sys
import uuid
from typing import Any, Dict, List, Tuple


class TerraformStateEngine:
    def __init__(self, state_name: str = "monolithic.tfstate"):
        self.state_name = state_name
        self.state: Dict[str, Any] = {
            "version": 4,
            "terraform_version": "1.7.0",
            "serial": 1,
            "lineage": str(uuid.uuid4()),
            "resources": []
        }
        self.moved_blocks: List[Tuple[str, str]] = []
        self.import_blocks: List[Tuple[str, str]] = []

    def load_state(self, filepath: str) -> None:
        """Memuat state file dari JSON file."""
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                self.state = json.load(f)
            print(f"[STATE LOADED] {filepath} (Serial: {self.state.get('serial')})")
        else:
            print(f"[INFO] File {filepath} belum ada. Menginisialisasi state kosong.")

    def save_state(self, filepath: str) -> None:
        """Menyimpan state file ke JSON file."""
        self.state["serial"] += 1
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)
        print(f"[STATE SAVED] {filepath} (Serial: {self.state.get('serial')})")

    def register_simulated_cloud_resource(self, res_type: str, res_name: str, res_id: str, attributes: Dict[str, Any], module: str = "") -> None:
        """Menambahkan resource secara langsung ke in-memory state."""
        resource_entry = {
            "module": module,
            "mode": "managed",
            "type": res_type,
            "name": res_name,
            "provider": f"provider[\"registry.terraform.io/hashicorp/{res_type.split('_')[0]}\"]",
            "instances": [
                {
                    "schema_version": 1,
                    "attributes": {
                        "id": res_id,
                        **attributes
                    }
                }
            ]
        }
        self.state["resources"].append(resource_entry)

    def add_import_block(self, target_address: str, cloud_id: str) -> None:
        """Mendaftarkan blok deklaratif import."""
        self.import_blocks.append((target_address, cloud_id))
        print(f"[HCL PARSER] Ditemukan import block: to = {target_address}, id = {cloud_id}")

    def add_moved_block(self, from_addr: str, to_addr: str) -> None:
        """Mendaftarkan blok deklaratif moved."""
        self.moved_blocks.append((from_addr, to_addr))
        print(f"[HCL PARSER] Ditemukan moved block: from = {from_addr} -> to = {to_addr}")

    def parse_address(self, address: str) -> Tuple[str, str, str, str]:
        """
        Memecah address Terraform:
        Contoh: 'module.networking.aws_vpc.vpc_main["primary"]' ->
        module: 'module.networking', type: 'aws_vpc', name: 'vpc_main', index: 'primary'
        """
        module = ""
        remainder = address
        if address.startswith("module."):
            parts = address.split(".")
            module = f"{parts[0]}.{parts[1]}"
            remainder = ".".join(parts[2:])

        index = ""
        if "[" in remainder and remainder.endswith("]"):
            name_part, index_part = remainder.split("[", 1)
            index = index_part.rstrip("]").strip('"\'')
            remainder = name_part

        parts = remainder.split(".")
        res_type = parts[0]
        res_name = parts[1] if len(parts) > 1 else ""

        return module, res_type, res_name, index

    def apply_imports(self, mock_cloud_catalog: Dict[str, Dict[str, Any]]) -> None:
        """Mengeksekusi simulasi declarative import."""
        print("\n--- MENGEKSEKUSI DECLARATIVE IMPORTS ---")
        for target_address, cloud_id in self.import_blocks:
            module, res_type, res_name, _ = self.parse_address(target_address)
            
            # Cek apakah ID ada di cloud catalog
            if cloud_id not in mock_cloud_catalog:
                print(f"[ERROR] Import Gagal: Cloud ID '{cloud_id}' tidak ditemukan pada provider API!")
                continue

            # Cek apakah sudah ada di state
            existing = self.find_resource(module, res_type, res_name)
            if existing:
                print(f"[WARN] Resource {target_address} sudah dikelola di state. Melewati import.")
                continue

            cloud_data = mock_cloud_catalog[cloud_id]
            self.register_simulated_cloud_resource(res_type, res_name, cloud_id, cloud_data, module=module)
            print(f"[SUCCESS IMPORTED] Cloud ID '{cloud_id}' berhasil diimpor ke state address: '{target_address}'")

    def find_resource(self, module: str, res_type: str, res_name: str) -> Dict[str, Any]:
        """Mencari resource di dalam state."""
        for res in self.state["resources"]:
            if res.get("module", "") == module and res.get("type") == res_type and res.get("name") == res_name:
                return res
        return {}

    def apply_moved_blocks(self) -> None:
        """Mengeksekusi mutasi address menggunakan blok moved."""
        print("\n--- MENGEKSEKUSI RECONCILIATION BLOK MOVED ---")
        for from_addr, to_addr in self.moved_blocks:
            f_mod, f_type, f_name, _ = self.parse_address(from_addr)
            t_mod, t_type, t_name, _ = self.parse_address(to_addr)

            target = None
            for res in self.state["resources"]:
                if res.get("module", "") == f_mod and res.get("type") == f_type and res.get("name") == f_name:
                    target = res
                    break

            if not target:
                print(f"[SKIP MOVED] Resource asal '{from_addr}' tidak ditemukan di state (mungkin sudah dimigrasikan).")
                continue

            # Mutasi pointer alamat state secara atomik
            target["module"] = t_mod
            target["type"] = t_type
            target["name"] = t_name

            print(f"[SUCCESS MOVED] {from_addr} ===(ZERO DOWNTIME)===> {to_addr}")

    def split_state(self, extract_filter: str, target_state_filename: str) -> 'TerraformStateEngine':
        """
        Memisahkan resource tertentu ke state file baru (State Splitting).
        Mirip dengan operasi `terraform state mv -state-out=...`
        """
        print(f"\n--- MEMISAHKAN MONOLITHIC STATE KE '{target_state_filename}' ---")
        new_engine = TerraformStateEngine(state_name=target_state_filename)
        retained_resources = []

        for res in self.state["resources"]:
            full_addr = f"{res.get('module', '')}.{res.get('type')}.{res.get('name')}".strip(".")
            if extract_filter in full_addr:
                print(f"[STATE MV] Memindahkan '{full_addr}' ke '{target_state_filename}'")
                new_engine.state["resources"].append(copy.deepcopy(res))
            else:
                retained_resources.append(res)

        self.state["resources"] = retained_resources
        return new_engine

    def plan_diff(self, intended_hcl_addresses: List[str]) -> None:
        """
        Simulasi Terraform Plan Engine:
        Memeriksa apakah konfigurasi HCL cocok persis dengan State (Zero diff validation).
        """
        print("\n--- TERRAFORM PLAN SIMULATION ---")
        state_addresses = []
        for res in self.state["resources"]:
            mod = res.get("module", "")
            addr = f"{mod}.{res.get('type')}.{res.get('name')}".strip(".")
            state_addresses.append(addr)

        to_add = [h for h in intended_hcl_addresses if h not in state_addresses]
        to_destroy = [s for s in state_addresses if s not in intended_hcl_addresses]
        unmodified = [s for s in state_addresses if s in intended_hcl_addresses]

        print(f"Plan Status:")
        print(f"  [+] To Add    : {len(to_add)}")
        for a in to_add:
            print(f"      + {a}")
        print(f"  [-] To Destroy: {len(to_destroy)}")
        for d in to_destroy:
            print(f"      - {d}")
        print(f"  [~] Unchanged : {len(unmodified)}")
        for u in unmodified:
            print(f"      ~ {u} (ID: {self.get_resource_id_by_address(u)})")

        if len(to_add) == 0 and len(to_destroy) == 0:
            print("\nRESULT: ZERO DESTRUCTION ACHIEVED. State matches HCL perfectly!")
        else:
            print("\nRESULT: WARNING! DRIFT OR DESTRUCTION DETECTED!")

    def get_resource_id_by_address(self, address: str) -> str:
        mod, res_type, res_name, _ = self.parse_address(address)
        res = self.find_resource(mod, res_type, res_name)
        if res and "instances" in res and len(res["instances"]) > 0:
            return res["instances"][0]["attributes"].get("id", "unknown")
        return "none"


def main():
    print("================================================================================")
    print("   TERRAFORM REFACTORING, BROWNFIELD & STATE SPLITTING SIMULATION LAB           ")
    print("================================================================================")

    # Inisialisasi Engine Monolithic State
    monolith = TerraformStateEngine("monolithic.tfstate")

    # 1. SETUP STATE MONOLITH EKSISTING
    print("\n[FASE 1] Menyiapkan Monolithic State Awal...")
    monolith.register_simulated_cloud_resource(
        "aws_vpc", "main_vpc", "vpc-011223344", {"cidr_block": "10.0.0.0/16"}
    )
    monolith.register_simulated_cloud_resource(
        "aws_instance", "legacy_api", "i-0a8b7c6d5e4f3", {"instance_type": "t3.large"}
    )
    monolith.register_simulated_cloud_resource(
        "aws_db_instance", "core_db", "rds-db-pg-core", {"allocated_storage": 100}
    )

    # 2. BROWNFIELD MIGRATION VIA DECLARATIVE IMPORT
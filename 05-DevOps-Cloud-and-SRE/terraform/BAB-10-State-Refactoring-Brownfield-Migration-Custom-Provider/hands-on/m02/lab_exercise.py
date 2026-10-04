#!/usr/bin/env python3
"""
Hands-on Lab Exercise: BAB-10 State Refactoring, Brownfield Migration & Custom Provider
Interactive Production Simulation Engine (Terraform v1.5+ Paradigm)
No external dependencies required (Pure Python 3 standard library).
"""

import sys
import time
import json
import uuid
import hashlib
from typing import Dict, Any, List, Optional

# --- ANSI Terminal Color Palette ---
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    BG_DARK = "\033[48;5;235m"
    BG_BLUE = "\033[44m"


def header(title: str) -> None:
    border = "=" * 70
    print(f"\n{Style.CYAN}{Style.BOLD}{border}")
    print(f" [*] {title.upper()}")
    print(f"{border}{Style.RESET}")


def step(msg: str) -> None:
    print(f"\n{Style.YELLOW}{Style.BOLD}>>> [STEP] {msg}{Style.RESET}")


def success(msg: str) -> None:
    print(f" {Style.GREEN}✔ [SUCCESS]{Style.RESET} {msg}")


def info(msg: str) -> None:
    print(f" {Style.BLUE}ℹ [INFO]{Style.RESET} {msg}")


def warn(msg: str) -> None:
    print(f" {Style.MAGENTA}⚠ [WARN]{Style.RESET} {msg}")


def error(msg: str) -> None:
    print(f" {Style.RED}✖ [ERROR]{Style.RESET} {msg}")


def print_json(data: Any) -> None:
    formatted = json.dumps(data, indent=2)
    print(f"{Style.DIM}{formatted}{Style.RESET}")


# --- Simulation Model: Terraform State (v4 Schema) ---
class TerraformState:
    def __init__(self, serial: int = 1):
        self.version = 4
        self.terraform_version = "1.8.5"
        self.serial = serial
        self.lineage = str(uuid.uuid4())
        self.resources: List[Dict[str, Any]] = []

    def commit(self) -> None:
        self.serial += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "terraform_version": self.terraform_version,
            "serial": self.serial,
            "lineage": self.lineage,
            "resources": self.resources
        }

    def get_resource(self, address: str) -> Optional[Dict[str, Any]]:
        for res in self.resources:
            addr = f"{res.get('module', '')}.{res['type']}.{res['name']}".lstrip(".")
            if addr == address or f"{res['type']}.{res['name']}" == address:
                return res
        return None


# --- Engine 1: Brownfield Discovery & Import Generation ---
class BrownfieldMigrationEngine:
    """Simulates Terraform 1.5+ declarative import blocks and config generation."""
    
    def __init__(self):
        # Simulated unmanaged infrastructure residing on Cloud Provider
        self.unmanaged_cloud_inventory = [
            {
                "cloud_id": "vpc-0abc987654321fed0",
                "type": "aws_vpc",
                "cidr_block": "10.200.0.0/16",
                "tags": {"Name": "legacy-production-core", "ManagedBy": "ClickOps"}
            },
            {
                "cloud_id": "subnet-01122334455667788",
                "type": "aws_subnet",
                "vpc_id": "vpc-0abc987654321fed0",
                "cidr_block": "10.200.1.0/24",
                "tags": {"Name": "legacy-app-subnet-a", "Env": "Brownfield"}
            },
            {
                "cloud_id": "i-09988776655443322",
                "type": "aws_instance",
                "instance_type": "c6i.2xlarge",
                "subnet_id": "subnet-01122334455667788",
                "tags": {"Role": "legacy-db-monolith"}
            }
        ]

    def discover_resources(self) -> List[Dict[str, Any]]:
        info("Scanning cloud tenant for unmanaged Brownfield resources (ClickOps detection)...")
        time.sleep(0.4)
        for r in self.unmanaged_cloud_inventory:
            print(f"  {Style.MAGENTA}* Discovered Cloud Object:{Style.RESET} {r['type']} (ID: {r['cloud_id']})")
        return self.unmanaged_cloud_inventory

    def generate_hcl_import_blocks(self) -> str:
        hcl_blocks = []
        for r in self.unmanaged_cloud_inventory:
            target_name = r['tags'].get('Name', r['tags'].get('Role', 'imported_res')).replace("-", "_")
            block = (
                f'import {{\n'
                f'  to = {r["type"]}.{target_name}\n'
                f'  id = "{r["cloud_id"]}"\n'
                f'}}'
            )
            hcl_blocks.append(block)
        return "\n\n".join(hcl_blocks)

    def execute_import(self, state: TerraformState) -> None:
        step("Executing declarative import into Terraform State (v4)...")
        for r in self.unmanaged_cloud_inventory:
            target_name = r['tags'].get('Name', r['tags'].get('Role', 'imported_res')).replace("-", "_")
            address = f"{r['type']}.{target_name}"
            
            res_entry = {
                "mode": "managed",
                "type": r["type"],
                "name": target_name,
                "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
                "instances": [
                    {
                        "schema_version": 1,
                        "attributes": {
                            "id": r["cloud_id"],
                            "tags": r["tags"],
                            **{k: v for k, v in r.items() if k not in ["cloud_id", "tags", "type"]}
                        }
                    }
                ]
            }
            state.resources.append(res_entry)
            success(f"State synced for address: {Style.BOLD}{address}{Style.RESET} (Remote ID: {r['cloud_id']})")
        state.commit()


# --- Engine 2: State Refactoring & 'moved' Block Evaluator ---
class StateRefactoringEngine:
    """Handles Monolith-to-Modular migration using both CLI state mv and moved {} blocks."""

    @staticmethod
    def inspect_state_tree(state: TerraformState) -> None:
        info(f"Inspecting Current State Tree (Serial: {state.serial}, Lineage: {state.lineage})")
        if not state.resources:
            print(f"  {Style.DIM}(State is empty){Style.RESET}")
            return
        for r in state.resources:
            mod = r.get("module", "(root)")
            addr = f"{mod}.{r['type']}.{r['name']}" if mod != "(root)" else f"{r['type']}.{r['name']}"
            inst_id = r["instances"][0]["attributes"].get("id", "N/A")
            print(f"  - [{Style.CYAN}{addr}{Style.RESET}] -> Remote ID: {inst_id}")

    @staticmethod
    def simulate_state_mv(state: TerraformState, source_addr: str, dest_addr: str) -> bool:
        step(f"Executing: terraform state mv '{source_addr}' '{dest_addr}'")
        res = state.get_resource(source_addr)
        if not res:
            error(f"Cannot find resource at source address: {source_addr}")
            return False

        # Parse destination address
        parts = dest_addr.split(".")
        if parts[0] == "module":
            res["module"] = f"module.{parts[1]}"
            res["type"] = parts[2]
            res["name"] = parts[3]
        else:
            res.pop("module", None)
            res["type"] = parts[0]
            res["name"] = parts[1]

        state.commit()
        success(f"State pointer remapped without infrastructure destruction: {source_addr} -> {dest_addr}")
        return True

    @staticmethod
    def evaluate_moved_blocks(state: TerraformState, moved_declarations: List[Dict[str, str]]) -> None:
        step("Evaluating HCL moved {} blocks during terraform plan/apply lifecycle...")
        for m in moved_declarations:
            src = m["from"]
            dst = m["to"]
            info(f"Declarative rule detected: moved {{ from = {src}  to = {dst} }}")
            res = state.get_resource(src)
            if res:
                StateRefactoringEngine.simulate_state_mv(state, src, dst)
            else:
                warn(f"Source address {src} already migrated or absent; skipping rule.")


# --- Engine 3: Custom Terraform Provider Protocol Handshake & RPC Engine ---
class CustomProviderEngine:
    """Simulates HashiCorp Terraform Plugin Framework Protocol v6 (gRPC over Stdout)."""

    def __init__(self, provider_name: str = "customcloud"):
        self.provider_name = provider_name
        self.protocol_version = 6
        self.managed_records: Dict[str, Dict[str, Any]] = {}

    def handshake(self) -> Dict[str, Any]:
        info(f"Initiating Plugin Handshake for provider: {self.provider_name}...")
        time.sleep(0.3)
        # Terraform Plugin Protocol v6 Handshake contract
        handshake_magic = {
            "CORE_PROTOCOL": self.protocol_version,
            "APP_PROTOCOL": "grpc/proto3",
            "MIN_COMPATIBLE_VERSION": 5,
            "CERT_SHA256": hashlib.sha256(b"custom-provider-secure-handshake").hexdigest()[:16]
        }
        success(f"Plugin Handshake Accepted! Protocol Version: {self.protocol_version}")
        print_json(handshake_magic)
        return handshake_magic

    def rpc_apply_resource(self, type_name: str, config: Dict[str, Any], state: TerraformState) -> str:
        res_id = f"cld-{uuid.uuid4().hex[:12]}"
        step(f"RPC [ApplyResourceChange] -> Creating {type_name} (ID: {res_id})")
        time.sleep(0.2)
        
        self.managed_records[res_id] = {
            "type": type_name,
            "attributes": config,
            "status": "PROVISIONED"
        }
        
        # Write into terraform state
        res_entry = {
            "mode": "managed",
            "type": type_name,
            "name": config.get("name", "cluster_core"),
            "provider": f'provider["registry.internal/{self.provider_name}"]',
            "instances": [
                {
                    "schema_version": 1,
                    "attributes": {
                        "id": res_id,
                        **config
                    }
                }
            ]
        }
        state.resources.append(res_entry)
        state.commit()
        success(f"Resource {type_name}.{config.get('name')} committed with remote ID: {res_id}")
        return res_id


# --- Interactive CLI Orchestrator ---
class LabOrchestrator:
    def __init__(self):
        self.state = TerraformState()
        self.brownfield = BrownfieldMigrationEngine()
        self.custom_provider = CustomProviderEngine("enterprisek8s")

    def run_menu(self) -> None:
        while True:
            header("BAB-10 Terraform Production Architecture Lab Simulator")
            print(f"{Style.BOLD}Target Topics:{Style.RESET} Brownfield Import, State Refactoring, Moved Blocks, Custom Provider RPC")
            print(f"Current State Serial: {Style.YELLOW}{self.state.serial}{Style.RESET} | Resources: {Style.GREEN}{len(self.state.resources)}{Style.RESET}\n")
            print(" [1] Run Brownfield Discovery & Generate Declarative 'import {}' Blocks")
            print(" [2] Execute Terraform Brownfield Import into Live State")
            print(" [3] Refactor Monolith State to Modular Architecture (State MV)")
            print(" [4] Simulate HCL 1.5+ 'moved {}' Declarative Migration Pipeline")
            print(" [5] Custom Provider Handshake & Plugin Framework RPC Simulation")
            print(" [6] Inspect Complete Terraform State File (.tfstate JSON)")
            print(" [7] Run Full Automated End-to-End Production Simulation")
            print(" [0] Exit Lab")
            
            choice = input(f"\n{Style.CYAN}{Style.BOLD}Select an option [0-7]: {Style.RESET}").strip()
            
            if choice == "1":
                self.action_brownfield_discovery()
            elif choice == "2":
                self.action_brownfield_import()
            elif choice == "3":
                self.action_state_mv()
            elif choice == "4":
                self.action_moved_blocks()
            elif choice == "5":
                self.action_custom_provider()
            elif choice == "6":
                self.action_inspect_state()
            elif choice == "7":
                self.action_full_pipeline()
            elif choice == "0":
                print(f"\n{Style.GREEN}Terima kasih telah menyelesaikan Lab BAB-10! Selesai.{Style.RESET}\n")
                sys.exit(0)
            else:
                warn("Invalid selection. Please choose an option between 0 and 7.")
            
            input(f"\n{Style.DIM}Press [Enter] to return to the main menu...{Style.RESET}")

    def action_brownfield_discovery(self) -> None:
        header("Phase 1: Brownfield Discovery & Code Generation")
        self.brownfield.discover_resources()
        step("Generating HCL import {} configuration blocks (Terraform v1.5+ standard):")
        code = self.brownfield.generate_hcl_import_blocks()
        print(f"\n{Style.WHITE}{code}{Style.RESET}")
        info("You can persist this into 'imports.tf' and run: terraform plan -generate-config-out=generated.tf")

    def action_brownfield_import(self) -> None:
        header("Phase 2: Executing Brownfield State Import")
        if any(r["name"] == "legacy_production_core" for r in self.state.resources):
            warn("Brownfield resources are already imported into state.")
            return
        self.brownfield.execute_import(self.state)
        StateRefactoringEngine.inspect_state_tree(self.state)

    def action_state_mv(self) -> None:
        header("Phase 3: State Refactoring - Monolith to Module")
        StateRefactoringEngine.inspect_state_tree(self.state)
        if not self.state.resources:
            warn("State is currently empty. Run Option [2] to import resources first.")
            return
        
        src = "aws_vpc.legacy_production_core"
        dst = "module.network_core.aws_vpc.vpc"
        print(f"\nTarget refactor: Move unmodularized root resource to structured deep module.")
        confirm = input(f"Move '{src}' -> '{dst}'? [Y/n]: ").strip().lower()
        if confirm in ["", "y", "yes"]:
            StateRefactoringEngine.simulate_state_mv(self.state, src, dst)
            StateRefactoringEngine.inspect_state_tree(self.state)

    def action_moved_blocks(self) -> None:
        header("Phase 4: Declarative 'moved {}' Migration Block Evaluation")
        moved_rules = [
            {"from": "aws_subnet.legacy_app_subnet_a", "to": "module.network_core.aws_subnet.private_subnets[0]"},
            {"from": "aws_instance.legacy_db_monolith", "to": "module.database_tier.aws_instance.primary_db"}
        ]
        StateRefactoringEngine.evaluate_moved_blocks(self.state, moved_rules)
        StateRefactoringEngine.inspect_state_tree(self.state)

    def action_custom_provider(self) -> None:
        header("Phase 5: Terraform Plugin Framework & Custom Provider Lifecycle")
        self.custom_provider.handshake()
        cfg = {
            "name": "enterprise-omega-k8s",
            "control_plane_replicas": 3,
            "cni_plugin": "cilium-ebpf",
            "enable_mtls": True
        }
        self.custom_provider.rpc_apply_resource("enterprisek8s_control_plane", cfg, self.state)
        StateRefactoringEngine.inspect_state_tree(self.state)

    def action_inspect_state(self) -> None:
        header("Inspection: Complete Terraform State (.tfstate)")
        print_json(self.state.to_dict())

    def action_full_pipeline(self) -> None:
        header("Automated End-to-End Production Simulation")
        self.action_brownfield_discovery()
        time.sleep(0.5)
        self.action_brownfield_import()
        time.sleep(0.5)
        self.action_state_mv()
        time.sleep(0.5)
        self.action_moved_blocks()
        time.sleep(0.5)
        self.action_custom_provider()
        time.sleep(0.5)
        header("End-to-End Simulation Finished Successfully")
        success(f"Final State Serial: {self.state.serial} with {len(self.state.resources)} active resources.")
        StateRefactoringEngine.inspect_state_tree(self.state)


def main() -> None:
    # If run in non-interactive environment (CI/test flags)
    if len(sys.argv) > 1 and sys.argv[1] in ["--auto", "-a", "--ci"]:
        orchestrator = LabOrchestrator()
        orchestrator.action_full_pipeline()
        sys.exit(0)
        
    try:
        orchestrator = LabOrchestrator()
        orchestrator.run_menu()
    except KeyboardInterrupt:
        print(f"\n\n{Style.RED}[!] Process interrupted by operator. Exiting safely.{Style.RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()

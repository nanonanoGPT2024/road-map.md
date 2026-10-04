#!/usr/bin/env python3
"""
Lab Hands-on: Simulasi Internal Engine Terraform (IaC Deep Dive)
Topik: 01-Core-Foundations / Bab 08 - Infrastructure as Code Menggunakan Terraform

Script ini memodelkan algoritma inti Terraform:
1. Directed Acyclic Graph (DAG) Dependency Resolution & Topological Sort
2. State Management (Reconciliation Loop, Desired vs Actual State)
3. Three-Way Diff Engine (Plan Phase: Create, Update-in-place, Destroy)
4. State Locking & Atomic State Commit (Serial & Lineage tracking)
"""

import sys
import time
import json
import hashlib
import re
from collections import defaultdict, deque
from typing import Dict, List, Any, Tuple, Optional

# --- ANSI Terminal Color Palette ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_GREEN = "\033[32m"   # Create (+)
CLR_YELLOW = "\033[33m"  # Update (~)
CLR_RED = "\033[31m"     # Destroy (-)
CLR_CYAN = "\033[36m"    # Info
CLR_MAGENTA = "\033[35m" # Graph/State
CLR_GRAY = "\033[90m"


class CircularDependencyError(Exception):
    """Dilempar ketika terdeteksi dependensi siklik antar resource."""
    pass


class Resource:
    """Mempresentasikan blok resource Terraform (misal: resource "aws_vpc" "main")."""
    def __init__(self, r_type: str, name: str, attributes: Dict[str, Any], depends_on: Optional[List[str]] = None):
        self.r_type = r_type
        self.name = name
        self.attributes = attributes
        self.depends_on = depends_on or []
        self.address = f"{r_type}.{name}"

    def extract_implicit_dependencies(self) -> List[str]:
        """
        Menganalisis atribut untuk mencari referensi resource lain (${resource_type.name.attr}).
        Memodelkan implicit dependency discovery di Terraform.
        """
        deps = set(self.depends_on)
        pattern = re.compile(r"\$\{([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)\.[a-zA-Z0-9_]+\}")
        
        for val in self.attributes.values():
            if isinstance(val, str):
                matches = pattern.findall(val)
                for r_type, r_name in matches:
                    deps.add(f"{r_type}.{r_name}")
        return list(deps)


class TerraformState:
    """
    Simulasi State Manager terraform.tfstate dengan serial incrementing,
    lineage locking, dan checksum integrity.
    """
    def __init__(self, lineage: str = "7a8f9b12-55c3-4d32-bb12-9011e4f901ab"):
        self.version = 4
        self.terraform_version = "1.6.0-sim"
        self.serial = 0
        self.lineage = lineage
        self.resources: Dict[str, Dict[str, Any]] = {}
        self.locked = False

    def acquire_lock(self) -> None:
        if self.locked:
            raise RuntimeError("Error: State terkunci oleh proses lain!")
        self.locked = True

    def release_lock(self) -> None:
        self.locked = False

    def commit(self, address: str, r_type: str, name: str, attributes: Dict[str, Any], destroy: bool = False) -> None:
        """Menyimpan hasil mutasi resource ke state dan menaikkan serial."""
        self.acquire_lock()
        try:
            if destroy:
                if address in self.resources:
                    del self.resources[address]
            else:
                self.resources[address] = {
                    "type": r_type,
                    "name": name,
                    "attributes": attributes,
                    "id": hashlib.md5(f"{address}:{time.time()}".encode()).hexdigest()[:12]
                }
            self.serial += 1
        finally:
            self.release_lock()

    def export_json(self) -> str:
        return json.dumps({
            "version": self.version,
            "terraform_version": self.terraform_version,
            "serial": self.serial,
            "lineage": self.lineage,
            "resources": self.resources
        }, indent=2)


class TerraformEngine:
    """Core Engine yang mereplikasi logika Graph Walk, Plan Diff, dan Apply."""
    def __init__(self, state: TerraformState):
        self.state = state

    def build_dag(self, desired_resources: Dict[str, Resource]) -> List[str]:
        """
        Membangun Directed Acyclic Graph (DAG) dan mengeksekusi Topological Sort (Kahn's Algorithm).
        Menentukan urutan provisioning yang valid berdasarkan dependensi.
        """
        in_degree = {addr: 0 for addr in desired_resources}
        adj_list = defaultdict(list)

        for addr, res in desired_resources.items():
            deps = res.extract_implicit_dependencies()
            for dep in deps:
                if dep in desired_resources:
                    adj_list[dep].append(addr)
                    in_degree[addr] += 1

        queue = deque([node for node, deg in in_degree.items() if deg == 0])
        ordered = []

        while queue:
            curr = queue.popleft()
            ordered.append(curr)
            for neighbor in adj_list[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(ordered) != len(desired_resources):
            raise CircularDependencyError("Siklus terdeteksi pada graph dependensi HCL!")

        return ordered

    def plan(self, desired_resources: Dict[str, Resource]) -> List[Tuple[str, str, Dict[str, Any], Dict[str, Any]]]:
        """
        Menghasilkan execution plan dengan membandingkan Desired Config vs State File.
        Mengembalikan tuple: (action, address, old_attrs, new_attrs)
        Action: '+' (CREATE), '~' (UPDATE), '-' (DESTROY)
        """
        actions = []
        current_state_addrs = set(self.state.resources.keys())
        desired_addrs = set(desired_resources.keys())

        # Resource yang harus dibuat (+)
        for addr in desired_addrs - current_state_addrs:
            actions.append(("+", addr, {}, desired_resources[addr].attributes))

        # Resource yang mungkin diubah in-place (~)
        for addr in desired_addrs & current_state_addrs:
            old_attrs = self.state.resources[addr]["attributes"]
            new_attrs = desired_resources[addr].attributes
            if old_attrs != new_attrs:
                actions.append(("~", addr, old_attrs, new_attrs))

        # Resource yang tidak ada di config, harus dihapus (-)
        for addr in current_state_addrs - desired_addrs:
            actions.append(("-", addr, self.state.resources[addr]["attributes"], {}))

        return actions

    def apply(self, execution_order: List[str], plan_actions: List[Tuple[str, str, Dict[str, Any], Dict[str, Any]]], desired_resources: Dict[str, Resource]) -> None:
        """
        Mengeksekusi rencana aksi sesuai urutan DAG topological sort.
        Melakukan evaluasi dinamis untuk binding variabel antar-resource.
        """
        action_map = {addr: act for act in plan_actions}
        
        for addr in execution_order:
            if addr not in action_map:
                continue

            action, _, old_attrs, new_attrs = action_map[addr]
            res = desired_resources.get(addr)

            if action == "+":
                print(f"{CLR_GREEN}+ [CREATE]{CLR_RESET} Provisioning: {CLR_BOLD}{addr}{CLR_RESET}")
                resolved_attrs = self._resolve_interpolations(new_attrs)
                self._simulate_io_latency(addr)
                self.state.commit(addr, res.r_type, res.name, resolved_attrs)
                print(f"  {CLR_GRAY}└─ ID didapatkan: {self.state.resources[addr]['id']}{CLR_RESET}")

            elif action == "~":
                print(f"{CLR_YELLOW}~ [UPDATE]{CLR_RESET} Modifying in-place: {CLR_BOLD}{addr}{CLR_RESET}")
                resolved_attrs = self._resolve_interpolations(new_attrs)
                self._simulate_io_latency(addr)
                self.state.commit(addr, res.r_type, res.name, resolved_attrs)

        # Handle destruction untuk resource yang dihapus dari config
        for action, addr, _, _ in plan_actions:
            if action == "-":
                print(f"{CLR_RED}- [DESTROY]{CLR_RESET} Tearing down: {CLR_BOLD}{addr}{CLR_RESET}")
                self._simulate_io_latency(addr)
                self.state.commit(addr, "", "", {}, destroy=True)

    def _resolve_interpolations(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Mengganti sintaks ${aws_vpc.name.id} dengan data nyata dari state saat apply."""
        resolved = {}
        pattern = re.compile(r"\$\{([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)\}")
        
        for k, v in attrs.items():
            if isinstance(v, str):
                match = pattern.search(v)
                if match:
                    target_type, target_name, target_field = match.groups()
                    target_addr = f"{target_type}.{target_name}"
                    if target_addr in self.state.resources:
                        val = self.state.resources[target_addr]["id"] if target_field == "id" else self.state.resources[target_addr]["attributes"].get(target_field, "unknown")
                        resolved[k] = pattern.sub(val, v)
                    else:
                        resolved[k] = v
                else:
                    resolved[k] = v
            else:
                resolved[k] = v
        return resolved

    def _simulate_io_latency(self, address: str) -> None:
        """Simulasi panggilan REST API asynchronous ke Cloud Provider."""
        print(f"  {CLR_GRAY}  API Calling Provider for {address}...{CLR_RESET}", end="\r")
        time.sleep(0.35)
        sys.stdout.write("\033[K")


def render_diff(plan_actions: List[Tuple[str, str, Dict[str, Any], Dict[str, Any]]]) -> None:
    """Menampilkan representasi visual Terraform Plan seperti CLI asli."""
    print(f"\n{CLR_BOLD}Terraform will perform the following actions:{CLR_RESET}\n")
    for action, addr, old_attrs, new_attrs in plan_actions:
        if action == "+":
            print(f"  {CLR_GREEN}+ resource \"{addr.split('.')[0]}\" \"{addr.split('.')[1]}\"{CLR_RESET} {{")
            for k, v in new_attrs.items():
                print(f"      {CLR_GREEN}+ {k:<15} = {json.dumps(v)}{CLR_RESET}")
            print("    }\n")
        elif action == "~":
            print(f"  {CLR_YELLOW}~ resource \"{addr.split('.')[0]}\" \"{addr.split('.')[1]}\"{CLR_RESET} {{")
            all_keys = set(old_attrs.keys()) | set(new_attrs.keys())
            for k in all_keys:
                v_old = old_attrs.get(k)
                v_new = new_attrs.get(k)
                if v_old != v_new:
                    print(f"      {CLR_YELLOW}~ {k:<15} = {json.dumps(v_old)} -> {json.dumps(v_new)}{CLR_RESET}")
                else:
                    print(f"        {k:<15} = {json.dumps(v_old)}")
            print("    }\n")
        elif action == "-":
            print(f"  {CLR_RED}- resource \"{addr.split('.')[0]}\" \"{addr.split('.')[1]}\"{CLR_RESET} {{")
            for k, v in old_attrs.items():
                print(f"      {CLR_RED}- {k:<15} = {json.dumps(v)}{CLR_RESET}")
            print("    }\n")


def main():
    print(f"{CLR_CYAN}{CLR_BOLD}=== SIMULASI INTERFACE & ENGINE TERRAFORM (IaC) ==={CLR_RESET}\n")

    # Inisialisasi State Backend
    state = TerraformState()
    engine = TerraformEngine(state)

    # ----------------------------------------------------
    # RUN 1: FRESH DEPLOYMENT (All Create)
    # ----------------------------------------------------
    print(f"{CLR_MAGENTA}--- [FASE 1: PARSING CONFIG & GRAPH RESOLUTION] ---{CLR_RESET}")
    hcl_manifest_v1 = {
        "aws_vpc.primary": Resource("aws_vpc", "primary", {
            "cidr_block": "10.0.0.0/16",
            "enable_dns": True
        }),
        "aws_subnet.public_a": Resource("aws_subnet", "public_a", {
            "vpc_id": "${aws_vpc.primary.id}",
            "cidr_block": "10.0.1.0/24"
        }),
        "aws_security_group.web": Resource("aws_security_group", "web", {
            "vpc_id": "${aws_vpc.primary.id}",
            "ingress_port": 80
        }),
        "aws_instance.app_server": Resource("aws_instance", "app_server", {
            "subnet_id": "${aws_subnet.public_a.id}",
            "sec_group": "${aws_security_group.web.id}",
            "instance_type": "t3.micro"
        }, depends_on=["aws_security_group.web"])
    }

    # Hitung DAG
    dag_order = engine.build_dag(hcl_manifest_v1)
    print(f"Resolved Execution Order (DAG Topo-Sort):")
    for idx, node in enumerate(dag_order, start=1):
        print(f"  {idx}. {CLR_BOLD}{node}{CLR_RESET}")

    # Generate Plan
    plan_v1 = engine.plan(hcl_manifest_v1)
    render_diff(plan_v1)

    print(f"{CLR_CYAN}{CLR_BOLD}Plan:{CLR_RESET} {len(plan_v1)} to add, 0 to change, 0 to destroy.")
    print(f"\n{CLR_MAGENTA}--- [FASE 2: TERRAFORM APPLY] ---{CLR_RESET}")
    engine.apply(dag_order, plan_v1, hcl_manifest_v1)

    print(f"\n{CLR_GREEN}Apply complete! Resources: 4 added, 0 changed, 0 destroyed.{CLR_RESET}")
    print(f"State Serial Saat Ini: {state.serial}\n")

    # ----------------------------------------------------
    # RUN 2: INFRASTRUCTURE DRIFT / UPDATE & DESTRUCTION
    # ----------------------------------------------------
    print(f"{CLR_MAGENTA}--- [FASE 3: MUTASI MANIFEST (UPDATE & DELETE RESOURCE)] ---{CLR_RESET}")
    print(f"{CLR_GRAY}Mengubah instance_type -> 't3.large' dan menghapus 'aws_security_group.web'{CLR_RESET}")
    
    hcl_manifest_v2 = {
        "aws_vpc.primary": Resource("aws_vpc", "primary", {
            "cidr_block": "10.0.0.0/16",
            "enable_dns": True
        }),
        "aws_subnet.public_a": Resource("aws_subnet", "public_a", {
            "vpc_id": "${aws_vpc.primary.id}",
            "cidr_block": "10.0.1.0/24"
        }),
        # Security Group dihapus dari manifest
        "aws_instance.app_server": Resource("aws_instance", "app_server", {
            "subnet_id": "${aws_subnet.public_a.id}",
            "sec_group": "default-sg",
            "instance_type": "t3.large" # Update in-place
        })
    }

    dag_order_v2 = engine.build_dag(hcl_manifest_v2)
    plan_v2 = engine.plan(hcl_manifest_v2)
    render_diff(plan_v2)

    engine.apply(dag_order_v2, plan_v2, hcl_manifest_v2)
    print(f"\n{CLR_GREEN}Apply complete! Resources: 0 added, 1 changed, 1 destroyed.{CLR_RESET}")

    # Inspect State Persistence
    print(f"\n{CLR_MAGENTA}--- [FASE 4: INSPEKSI STATE FILE (terraform.tfstate)] ---{CLR_RESET}")
    print(state.export_json())


if __name__ == "__main__":
    main()
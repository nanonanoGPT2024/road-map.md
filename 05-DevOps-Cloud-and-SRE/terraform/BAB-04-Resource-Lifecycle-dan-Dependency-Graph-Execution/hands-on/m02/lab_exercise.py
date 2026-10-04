#!/usr/bin/env python3
"""
Terraform Architecture & DAG Execution Simulator
BAB-04: Resource Lifecycle & Dependency Graph Execution Engine

Simulasi interaktif tingkat lanjut yang mendemonstrasikan:
1. Directed Acyclic Graph (DAG) construction & Kahn's Algorithm Topological Sort
2. Lifecycle Meta-arguments: create_before_destroy, prevent_destroy, ignore_changes
3. Parallel execution waves (Level-by-Level Graph Walking)
4. Cycle Detection & Graph Invalidation
5. Zero-downtime rolling update via Create-Before-Destroy (CBD)
"""

import sys
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Optional

# --- ANSI Terminal Color Palette ---
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Foreground Colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright Foreground
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background Colors
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"
    BG_YELLOW = "\033[43m"
    BG_DARK = "\033[40m"


class ActionType(Enum):
    NOOP = "no-op"
    CREATE = "+ create"
    UPDATE = "~ update in-place"
    DESTROY = "- destroy"
    REPLACE_DESTROY_FIRST = "-/+ destroy-then-create"
    REPLACE_CREATE_FIRST = "+/- create-before-destroy"


@dataclass
class LifecyclePolicy:
    create_before_destroy: bool = False
    prevent_destroy: bool = False
    ignore_changes: List[str] = field(default_factory=list)
    replace_triggered_by: List[str] = field(default_factory=list)


@dataclass
class ResourceNode:
    id: str
    type: str
    name: str
    dependencies: Set[str] = field(default_factory=set)
    lifecycle: LifecyclePolicy = field(default_factory=LifecyclePolicy)
    attributes: Dict[str, str] = field(default_factory=dict)
    state_attributes: Dict[str, str] = field(default_factory=dict)
    planned_action: ActionType = ActionType.NOOP
    status: str = "PENDING"


class TerraformGraphEngine:
    def __init__(self):
        self.resources: Dict[str, ResourceNode] = {}
        self.setup_production_topology()

    def setup_production_topology(self):
        """Membangun arsitektur produksi 3-tier tipikal AWS."""
        self.resources = {
            "aws_vpc.main": ResourceNode(
                id="aws_vpc.main",
                type="aws_vpc",
                name="main",
                lifecycle=LifecyclePolicy(prevent_destroy=True),
                attributes={"cidr_block": "10.0.0.0/16", "enable_dns_hostnames": "true"},
            ),
            "aws_internet_gateway.igw": ResourceNode(
                id="aws_internet_gateway.igw",
                type="aws_internet_gateway",
                name="igw",
                dependencies={"aws_vpc.main"},
                attributes={"vpc_id": "aws_vpc.main.id"},
            ),
            "aws_subnet.public_a": ResourceNode(
                id="aws_subnet.public_a",
                type="aws_subnet",
                name="public_a",
                dependencies={"aws_vpc.main"},
                attributes={"cidr_block": "10.0.1.0/24", "availability_zone": "ap-southeast-1a"},
            ),
            "aws_subnet.public_b": ResourceNode(
                id="aws_subnet.public_b",
                type="aws_subnet",
                name="public_b",
                dependencies={"aws_vpc.main"},
                attributes={"cidr_block": "10.0.2.0/24", "availability_zone": "ap-southeast-1b"},
            ),
            "aws_security_group.lb_sg": ResourceNode(
                id="aws_security_group.lb_sg",
                type="aws_security_group",
                name="lb_sg",
                dependencies={"aws_vpc.main"},
                attributes={"ingress_port": "443", "protocol": "tcp"},
            ),
            "aws_lb.ingress": ResourceNode(
                id="aws_lb.ingress",
                type="aws_lb",
                name="ingress",
                dependencies={"aws_subnet.public_a", "aws_subnet.public_b", "aws_security_group.lb_sg"},
                lifecycle=LifecyclePolicy(create_before_destroy=True),
                attributes={"load_balancer_type": "application", "internal": "false"},
            ),
            "aws_security_group.app_sg": ResourceNode(
                id="aws_security_group.app_sg",
                type="aws_security_group",
                name="app_sg",
                dependencies={"aws_security_group.lb_sg", "aws_vpc.main"},
                attributes={"source_sg": "aws_security_group.lb_sg.id", "port": "8080"},
            ),
            "aws_launch_template.app": ResourceNode(
                id="aws_launch_template.app",
                type="aws_launch_template",
                name="app",
                dependencies={"aws_security_group.app_sg"},
                lifecycle=LifecyclePolicy(create_before_destroy=True),
                attributes={"image_id": "ami-0123456789abcdef0", "instance_type": "c6i.xlarge"},
            ),
            "aws_autoscaling_group.asg": ResourceNode(
                id="aws_autoscaling_group.asg",
                type="aws_autoscaling_group",
                name="asg",
                dependencies={"aws_launch_template.app", "aws_lb.ingress"},
                lifecycle=LifecyclePolicy(
                    create_before_destroy=True,
                    ignore_changes=["desired_capacity", "target_group_arns"]
                ),
                attributes={"min_size": "2", "max_size": "10", "desired_capacity": "4"},
            ),
            "aws_rds_cluster.primary": ResourceNode(
                id="aws_rds_cluster.primary",
                type="aws_rds_cluster",
                name="primary",
                dependencies={"aws_vpc.main", "aws_security_group.app_sg"},
                lifecycle=LifecyclePolicy(prevent_destroy=True),
                attributes={"engine": "aurora-postgresql", "engine_version": "15.4"},
            ),
        }

    def compute_dag_waves(self, custom_deps: Optional[Dict[str, Set[str]]] = None) -> List[List[str]]:
        """
        Kahn's Algorithm untuk menghitung tingkatan eksekusi paralel (execution waves)
        sekaligus mendeteksi apakah terdapat Circular Dependency (Cycle).
        """
        deps = custom_deps if custom_deps is not None else {
            k: set(v.dependencies) for k, v in self.resources.items()
        }

        # Calculate in-degree: number of dependencies a node depends on
        in_degree = {u: len(deps[u]) for u in deps}
        # Adjacency list: node -> dependents who wait for it
        dependents = defaultdict(list)
        for u, parents in deps.items():
            for p in parents:
                if p in deps:
                    dependents[p].append(u)

        queue = deque([u for u in in_degree if in_degree[u] == 0])
        waves = []
        visited_count = 0

        while queue:
            current_wave = []
            for _ in range(len(queue)):
                curr = queue.popleft()
                current_wave.append(curr)
                visited_count += 1
                for nxt in dependents[curr]:
                    in_degree[nxt] -= 1
                    if in_degree[nxt] == 0:
                        queue.append(nxt)
            waves.append(current_wave)

        if visited_count != len(deps):
            raise ValueError("Dependency Cycle Detected! Graf tidak memenuhi kriteria Directed Acyclic Graph (DAG).")

        return waves

    def display_ascii_banner(self):
        print(f"{Style.BRIGHT_CYAN}{Style.BOLD}")
        print("╔════════════════════════════════════════════════════════════════════════════════╗")
        print("║        TERRAFORM GRAPH ENGINE & LIFECYCLE CONTROLLER SIMULATOR (CLI)          ║")
        print("║            BAB-04: Resource Lifecycle & Dependency Graph Execution             ║")
        print("╚════════════════════════════════════════════════════════════════════════════════╝")
        print(f"{Style.RESET}")

    def display_dependency_graph(self):
        print(f"\n{Style.BRIGHT_MAGENTA}{Style.BOLD}=== VISUALISASI DIRECTED ACYCLIC GRAPH (DAG) PRODUKSI ==={Style.RESET}\n")
        try:
            waves = self.compute_dag_waves()
        except ValueError as e:
            print(f"{Style.BRIGHT_RED}Gagal merender graf: {e}{Style.RESET}")
            return

        for wave_idx, wave in enumerate(waves):
            print(f"{Style.BRIGHT_YELLOW}─── [Wave {wave_idx + 1}] (Paralelisme Level {len(wave)}) ──────────────────────────────{Style.RESET}")
            for node_id in wave:
                res = self.resources[node_id]
                deps_str = ", ".join(res.dependencies) if res.dependencies else "None (Root Node)"
                flags = []
                if res.lifecycle.create_before_destroy:
                    flags.append(f"{Style.BRIGHT_CYAN}CBD{Style.RESET}")
                if res.lifecycle.prevent_destroy:
                    flags.append(f"{Style.BRIGHT_RED}PREVENT_DESTROY{Style.RESET}")
                if res.lifecycle.ignore_changes:
                    flags.append(f"{Style.DIM}IGNORE({','.join(res.lifecycle.ignore_changes)}){Style.RESET}")

                flags_badge = f" [{' '.join(flags)}]" if flags else ""
                print(f"  {Style.GREEN}●{Style.RESET} {Style.BOLD}{node_id:<32}{Style.RESET} {flags_badge}")
                print(f"    {Style.DIM}└── Depends On: {Style.CYAN}{deps_str}{Style.RESET}")
            print()

    def run_plan_phase(self, mutate_mode: str = "normal"):
        print(f"\n{Style.BG_BLUE}{Style.WHITE}{Style.BOLD} TERRAFORM PLAN ---------------------------------------------------- {Style.RESET}\n")
        
        # Reset plan
        for res in self.resources.values():
            res.planned_action = ActionType.NOOP

        if mutate_mode == "normal":
            for res in self.resources.values():
                res.planned_action = ActionType.CREATE
        elif mutate_mode == "cbd_upgrade":
            # Upgrade AMI in launch template requiring replacement
            lt = self.resources["aws_launch_template.app"]
            lt.planned_action = ActionType.REPLACE_CREATE_FIRST if lt.lifecycle.create_before_destroy else ActionType.REPLACE_DESTROY_FIRST
            asg = self.resources["aws_autoscaling_group.asg"]
            asg.planned_action = ActionType.UPDATE
        elif mutate_mode == "disaster_prevent_destroy":
            rds = self.resources["aws_rds_cluster.primary"]
            rds.planned_action = ActionType.DESTROY

        create_cnt = sum(1 for r in self.resources.values() if r.planned_action in (ActionType.CREATE, ActionType.REPLACE_CREATE_FIRST))
        update_cnt = sum(1 for r in self.resources.values() if r.planned_action == ActionType.UPDATE)
        destroy_cnt = sum(1 for r in self.resources.values() if r.planned_action in (ActionType.DESTROY, ActionType.REPLACE_DESTROY_FIRST))

        print(f"{Style.BOLD}Terraform used the selected providers to generate the following execution plan:{Style.RESET}\n")
        
        for node_id, res in self.resources.items():
            if res.planned_action == ActionType.NOOP:
                continue

            color = Style.GREEN
            prefix = "+"
            if res.planned_action == ActionType.UPDATE:
                color = Style.YELLOW
                prefix = "~"
            elif res.planned_action == ActionType.DESTROY:
                color = Style.RED
                prefix = "-"
            elif res.planned_action == ActionType.REPLACE_CREATE_FIRST:
                color = Style.BRIGHT_CYAN
                prefix = "+/-"
            elif res.planned_action == ActionType.REPLACE_DESTROY_FIRST:
                color = Style.BRIGHT_RED
                prefix = "-/+"

            print(f"  {color}{Style.BOLD}{prefix} resource \"{res.type}\" \"{res.name}\"{Style.RESET} {{")
            for k, v in res.attributes.items():
                if res.planned_action == ActionType.REPLACE_CREATE_FIRST and k == "image_id":
                    print(f"      {color}~ {k:<20} = \"{v}\" -> \"ami-099999999newami\" (forces replacement){Style.RESET}")
                elif res.planned_action == ActionType.UPDATE and k == "desired_capacity" and "desired_capacity" in res.lifecycle.ignore_changes:
                    print(f"      {Style.DIM}# {k:<20} changes ignored by lifecycle.ignore_changes{Style.RESET}")
                else:
                    print(f"      {color}{prefix} {k:<20} = \"{v}\"{Style.RESET}")
            
            if res.lifecycle.create_before_destroy:
                print(f"      {Style.CYAN}# lifecycle {{ create_before_destroy = true }}{Style.RESET}")
            if res.lifecycle.prevent_destroy:
                print(f"      {Style.RED}# lifecycle {{ prevent_destroy = true }}{Style.RESET}")
            print(f"  {color}}}{Style.RESET}\n")

        print(f"{Style.BOLD}Plan:{Style.RESET} {create_cnt} to add, {update_cnt} to change, {destroy_cnt} to destroy.")

    def run_apply_phase(self):
        print(f"\n{Style.BG_GREEN}{Style.BLACK}{Style.BOLD} TERRAFORM APPLY --------------------------------------------------- {Style.RESET}\n")
        try:
            waves = self.compute_dag_waves()
        except ValueError as e:
            print(f"{Style.BRIGHT_RED}[FATAL ERROR] {e}{Style.RESET}")
            return

        total_nodes = len(self.resources)
        applied_count = 0

        for wave_idx, wave in enumerate(waves):
            print(f"{Style.BRIGHT_BLUE}==> Executing Wave {wave_idx + 1} ({len(wave)} resources concurrently)...{Style.RESET}")
            for node_id in wave:
                res = self.resources[node_id]
                print(f"  {Style.YELLOW}▶ {node_id}: Creating...{Style.RESET}")
                time.sleep(0.12)  # Visual execution tick
                res.status = "APPLIED"
                applied_count += 1
                progress = int((applied_count / total_nodes) * 30)
                bar = f"[{'=' * progress}{' ' * (30 - progress)}]"
                print(f"  {Style.GREEN}✔ {node_id}: Creation complete after 1s {Style.DIM}{bar} ({applied_count}/{total_nodes}){Style.RESET}")
            print()

        print(f"{Style.BRIGHT_GREEN}{Style.BOLD}Apply complete! Resources: {total_nodes} added, 0 changed, 0 destroyed.{Style.RESET}")

    def simulate_cbd_rolling_update(self):
        print(f"\n{Style.BRIGHT_CYAN}{Style.BOLD}=== SIMULASI ZERO-DOWNTIME REPLACEMENT (create_before_destroy) ==={Style.RESET}")
        print(f"{Style.DIM}Skenario: Patch Keamanan Kernel - Pergantian AMI pada AutoScaling Launch Template{Style.RESET}\n")

        lt = self.resources["aws_launch_template.app"]
        print(f"1. Evaluasi Resource: {Style.BOLD}{lt.id}{Style.RESET}")
        print(f"   Lifecycle Rule: {Style.GREEN}create_before_destroy = True{Style.RESET}")
        print(f"\n{Style.YELLOW}[Standard Replace (Tanpa CBD)]:{Style.RESET} Destroy Old Template -> DOWNTIME GAP -> Create New Template")
        print(f"{Style.BRIGHT_GREEN}[Terraform CBD Walk Graph]:{Style.RESET}")
        
        # Step-by-step simulation
        print(f"   1. {Style.CYAN}[CREATE NEW]{Style.RESET} aws_launch_template.app.tmp-024fa (New AMI)")
        time.sleep(0.15)
        print(f"   2. {Style.CYAN}[ATTACH/SWAP]{Style.RESET} aws_autoscaling_group.asg poin ke instance baru")
        time.sleep(0.15)
        print(f"   3. {Style.RED}[DESTROY OLD]{Style.RESET} aws_launch_template.app.old-99a3e dihapus tanpa outage!")
        print(f"\n{Style.BRIGHT_GREEN}✔ Sukses! Ketersediaan layanan terjaga 100% tanpa service disruption.{Style.RESET}")

    def simulate_prevent_destroy_block(self):
        print(f"\n{Style.BRIGHT_RED}{Style.BOLD}=== SIMULASI PREVENT DESTROY GUARDRAIL ==={Style.RESET}")
        print(f"{Style.DIM}Skenario: Developer sengaja/tidak sengaja menghapus resource database kritikal{Style.RESET}\n")

        rds = self.resources["aws_rds_cluster.primary"]
        print(f"Target Resource: {Style.BOLD}{rds.id}{Style.RESET}")
        print(f"Proteksi Terpasang: {Style.BRIGHT_RED}lifecycle {{ prevent_destroy = true }}{Style.RESET}\n")
        print(f"{Style.BOLD}Menjalankan: terraform destroy -target=aws_rds_cluster.primary{Style.RESET} ...\n")
        time.sleep(0.2)

        # ANSI Error Block
        print(f"{Style.BG_RED}{Style.WHITE}{Style.BOLD} Error: Instance cannot be destroyed {Style.RESET}")
        print(f"\n  {Style.RED}on database.tf line 42:{Style.RESET}")
        print(f"  {Style.RED}42: resource \"aws_rds_cluster\" \"primary\" {{{Style.RESET}")
        print(f"\n  Resource {Style.BOLD}{rds.id}{Style.RESET} has {Style.BRIGHT_RED}lifecycle.prevent_destroy{Style.RESET} set to true, but")
        print("  the plan calls for it to be destroyed. To permit this destruction, you")
        print("  must first remove the prevent_destroy lifecycle configuration from code.")
        print(f"\n{Style.GREEN}✔ GUARDRAIL TERBUKTI: State penghancuran digagalkan sebelum menyentuh cloud API.{Style.RESET}")

    def simulate_dependency_cycle_detection(self):
        print(f"\n{Style.BRIGHT_YELLOW}{Style.BOLD}=== SIMULASI SIKLUS DEPENDENSI (CIRCULAR DEPENDENCY / CYCLE ERROR) ==={Style.RESET}")
        print(f"{Style.DIM}Skenario: VPC Route Table saling bergantung secara melingkar dengan Security Group{Style.RESET}\n")

        # Create cycle: A -> B -> C -> A
        cyclic_deps = {
            "aws_vpc.main": {"aws_security_group.app_sg"},  # Injeksi siklus terbalik
            "aws_security_group.app_sg": {"aws_launch_template.app"},
            "aws_launch_template.app": {"aws_vpc.main"}
        }

        print("Graf dependensi diinjeksikan ketergantungan melingkar:")
        print(f"  {Style.RED}aws_vpc.main{Style.RESET} ──depends on──> {Style.YELLOW}aws_security_group.app_sg{Style.RESET}")
        print(f"  {Style.YELLOW}aws_security_group.app_sg{Style.RESET} ──depends on──> {Style.BLUE}aws_launch_template.app{Style.RESET}")
        print(f"  {Style.BLUE}aws_launch_template.app{Style.RESET} ──depends on──> {Style.RED}aws_vpc.main{Style.RESET}\n")

        time.sleep(0.2)
        try:
            self.compute_dag_waves(cyclic_deps)
        except ValueError as err:
            print(f"{Style.BG_RED}{Style.WHITE}{Style.BOLD} Error: Cycle detected in graph execution {Style.RESET}")
            print(f"\n  {Style.BRIGHT_RED}Cycle:{Style.RESET} aws_vpc.main -> aws_security_group.app_sg -> aws_launch_template.app -> aws_vpc.main")
            print("\n  Terraform cannot determine a valid topological execution order.")
            print(f"  {Style.CYAN}Solusi Arsitektur:{Style.RESET} Pecah konfigurasi menjadi decoupled resource (misal: aws_security_group_rule mandiri).")


def interactive_menu():
    engine = TerraformGraphEngine()
    
    while True:
        engine.display_ascii_banner()
        print(f"{Style.BOLD}Menu Simulasi Interaktif:{Style.RESET}")
        print(f"  {Style.CYAN}[1]{Style.RESET} Tampilkan Visualisasi Graf Dependensi (DAG & Execution Waves)")
        print(f"  {Style.CYAN}[2]{Style.RESET} Jalankan 'terraform plan' (Evaluasi State & Lifecycle Metadata)")
        print(f"  {Style.CYAN}[3]{Style.RESET} Jalankan 'terraform apply' (Simulasi Eksekusi Multi-Wave Paralel)")
        print(f"  {Style.CYAN}[4]{Style.RESET} Uji Kasus: Zero-Downtime Rolling Update (create_before_destroy)")
        print(f"  {Style.CYAN}[5]{Style.RESET} Uji Kasus: Proteksi Penghancuran Database (prevent_destroy guardrail)")
        print(f"  {Style.CYAN}[6]{Style.RESET} Uji Kasus: Deteksi Siklus Melingkar (Cycle Detection Error)")
        print(f"  {Style.CYAN}[7]{Style.RESET} Jalankan Otomatis Semua Skenario Uji (End-to-End Demo)")
        print(f"  {Style.RED}[0]{Style.RESET} Keluar (Exit)")
        print()

        try:
            choice = input(f"{Style.BOLD}Pilih opsi [0-7]: {Style.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Style.YELLOW}Simulasi dihentikan.{Style.RESET}")
            sys.exit(0)

        if choice == "1":
            engine.display_dependency_graph()
        elif choice == "2":
            engine.run_plan_phase("normal")
        elif choice == "3":
            engine.run_apply_phase()
        elif choice == "4":
            engine.simulate_cbd_rolling_update()
        elif choice == "5":
            engine.simulate_prevent_destroy_block()
        elif choice == "6":
            engine.simulate_dependency_cycle_detection()
        elif choice == "7":
            print(f"\n{Style.BRIGHT_MAGENTA}>>> MENJALANKAN SELURUH SKENARIO UJI SECARA OTOMATIS <<<{Style.RESET}")
            engine.display_dependency_graph()
            time.sleep(0.5)
            engine.run_plan_phase("normal")
            time.sleep(0.5)
            engine.run_apply_phase()
            time.sleep(0.5)
            engine.simulate_cbd_rolling_update()
            time.sleep(0.5)
            engine.simulate_prevent_destroy_block()
            time.sleep(0.5)
            engine.simulate_dependency_cycle_detection()
        elif choice == "0":
            print(f"\n{Style.GREEN}Terima kasih telah menggunakan simulator arsitektur Terraform.{Style.RESET}")
            sys.exit(0)
        else:
            print(f"\n{Style.RED}Pilihan tidak valid, silakan coba lagi.{Style.RESET}")

        input(f"\n{Style.DIM}Tekan [Enter] untuk kembali ke menu utama...{Style.RESET}")


if __name__ == "__main__":
    # Jika dijalankan dengan argumen non-interaktif seperti --all
    if len(sys.argv) > 1 and sys.argv[1] in ("--all", "-a", "--auto"):
        eng = TerraformGraphEngine()
        eng.display_ascii_banner()
        eng.display_dependency_graph()
        eng.run_plan_phase("normal")
        eng.run_apply_phase()
        eng.simulate_cbd_rolling_update()
        eng.simulate_prevent_destroy_block()
        eng.simulate_dependency_cycle_detection()
    else:
        interactive_menu()

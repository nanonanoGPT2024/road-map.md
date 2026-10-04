#!/usr/bin/env python3
"""
Lab Exercise M02: Terraform Core Engine, Distributed State Lock & DAG Walker Simulation
Bab 01: Fondasi dan Arsitektur - Modul 02

Simulasi teknis independen arsitektur internal Terraform Core:
1. Distributed State Lock (Algoritma Mutex DynamoDB/Consul)
2. Directed Acyclic Graph (DAG) Engine & Dependency Resolution (Kahn's Algorithm)
3. RPC-based Provider Plugin Interface (gRPC / go-plugin emulation)
4. State Serialization, Serial Increment, and Lineage Validation
"""

import json
import time
import uuid
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"


def print_banner(text: str) -> None:
    line = "=" * 70
    print(f"\n{Color.CYAN}{Color.BOLD}{line}")
    print(f" {text}")
    print(f"{line}{Color.RESET}")


@dataclass
class LockInfo:
    lock_id: str
    owner: str
    operation: str
    created_at: float
    info: str


class DistributedLockManager:
    """Simulasi mekanisme state locking pada backend terdistribusi (DynamoDB / S3)."""

    def __init__(self, backend_name: str = "s3-dynamodb-backend"):
        self.backend_name = backend_name
        self._current_lock: Optional[LockInfo] = None

    def acquire_lock(self, owner: str, operation: str) -> bool:
        if self._current_lock is not None:
            print(
                f"{Color.RED}[LOCK ERROR] Gagal mengakuisisi lock! State terkunci oleh:{Color.RESET}\n"
                f"  ID: {self._current_lock.lock_id}\n"
                f"  Owner: {self._current_lock.owner}\n"
                f"  Operasi: {self._current_lock.operation}\n"
                f"  Waktu: {time.ctime(self._current_lock.created_at)}"
            )
            return False

        lock_id = str(uuid.uuid4())[:8]
        self._current_lock = LockInfo(
            lock_id=lock_id,
            owner=owner,
            operation=operation,
            created_at=time.time(),
            info=f"Backend: {self.backend_name}",
        )
        print(
            f"{Color.GREEN}[LOCK ACQUIRED] Distributed lock berhasil didapat. Lock ID: {lock_id} (Owner: {owner}){Color.RESET}"
        )
        return True

    def release_lock(self, owner: str) -> bool:
        if self._current_lock is None:
            print(f"{Color.YELLOW}[LOCK WARN] Tidak ada lock aktif untuk dilepas.{Color.RESET}")
            return True

        if self._current_lock.owner != owner:
            print(
                f"{Color.RED}[LOCK REJECTED] Owner '{owner}' tidak berhak melepas lock milik '{self._current_lock.owner}'.{Color.RESET}"
            )
            return False

        print(f"{Color.GRAY}[LOCK RELEASED] Lock ID {self._current_lock.lock_id} dilepas.{Color.RESET}")
        self._current_lock = None
        return True


@dataclass
class ResourceNode:
    address: str
    provider: str
    attributes: Dict[str, str] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)


class MockProviderPluginRPC:
    """Emulasi komunikasi gRPC via go-plugin antara Core dan Provider Plugin."""

    def __init__(self, name: str):
        self.name = name

    def configure(self, config: Dict[str, str]) -> None:
        print(f"{Color.MAGENTA}[RPC gRPC::{self.name}] ConfigureProvider: region={config.get('region')}{Color.RESET}")

    def apply_resource(self, address: str, attrs: Dict[str, str]) -> Dict[str, str]:
        time.sleep(0.3)  # Simulasi latency network API cloud
        res_id = f"{attrs.get('type', 'res')}-{uuid.uuid4().hex[:6]}"
        output_state = {
            "id": res_id,
            "status": "ready",
            "arn": f"arn:cloud:provider::{res_id}",
            **attrs,
        }
        return output_state


class DAGEngine:
    """Directed Acyclic Graph (DAG) evaluator dengan topological sort & parallel walk."""

    def __init__(self, nodes: Dict[str, ResourceNode]):
        self.nodes = nodes
        self.adj_list: Dict[str, List[str]] = defaultdict(list)
        self.in_degree: Dict[str, int] = {k: 0 for k in nodes}
        self._build_graph()

    def _build_graph(self) -> None:
        for addr, node in self.nodes.items():
            for dep in node.dependencies:
                if dep in self.nodes:
                    self.adj_list[dep].append(addr)
                    self.in_degree[addr] += 1
                else:
                    raise ValueError(f"Dependency error: {dep} tidak ditemukan untuk {addr}")

    def detect_cycles(self) -> bool:
        temp_in_degree = dict(self.in_degree)
        queue = deque([k for k, v in temp_in_degree.items() if v == 0])
        visited_count = 0

        while queue:
            node = queue.popleft()
            visited_count += 1
            for neighbor in self.adj_list[node]:
                temp_in_degree[neighbor] -= 1
                if temp_in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return visited_count != len(self.nodes)

    def topological_levels(self) -> List[List[str]]:
        """Membagi nodes ke dalam tingkatan eksekusi paralel (Execution Waves)."""
        temp_in_degree = dict(self.in_degree)
        ready_queue = [k for k, v in temp_in_degree.items() if v == 0]
        waves = []

        while ready_queue:
            current_wave = list(ready_queue)
            waves.append(current_wave)
            next_queue = []
            for node in current_wave:
                for neighbor in self.adj_list[node]:
                    temp_in_degree[neighbor] -= 1
                    if temp_in_degree[neighbor] == 0:
                        next_queue.append(neighbor)
            ready_queue = next_queue

        return waves


class TerraformCoreSimulator:
    """Komponen sentral Terraform Core: State manager, Graph Walk, dan RPC bridge."""

    def __init__(self):
        self.lineage = str(uuid.uuid4())
        self.serial = 0
        self.state_resources: Dict[str, dict] = {}
        self.lock_mgr = DistributedLockManager()
        self.provider = MockProviderPluginRPC("aws-provider-v5.0")

    def execute_plan_and_apply(self, graph_nodes: Dict[str, ResourceNode], parallelism: int = 2) -> bool:
        operator = "devops-engineer@terminal-1"
        print(f"{Color.CYAN}[CORE] Mengawali alur Terraform Apply (Parallelism={parallelism})...{Color.RESET}")

        # 1. Akuisisi Lock
        if not self.lock_mgr.acquire_lock(owner=operator, operation="Apply"):
            return False

        try:
            # 2. Inisialisasi Plugin RPC
            self.provider.configure({"region": "ap-southeast-1"})

            # 3. Evaluasi Graf DAG
            dag = DAGEngine(graph_nodes)
            if dag.detect_cycles():
                raise RuntimeError("Circular dependency terdeteksi pada deklarasi resource HCL!")

            waves = dag.topological_levels()
            print(f"{Color.BLUE}[DAG ENGINE] Graf berhasil diurai menjadi {len(waves)} Execution Wave(s):{Color.RESET}")
            for idx, wave in enumerate(waves, 1):
                print(f"  - Wave {idx}: {', '.join(wave)}")

            # 4. Graph Walk Paralel per Wave
            print(f"\n{Color.BOLD}>>> Memulai Evaluasi Node Graf (Core-to-Provider Walk) <<<{Color.RESET}")
            for wave_idx, wave_nodes in enumerate(waves, 1):
                print(f"\n{Color.YELLOW}--- Menjalankan Wave {wave_idx} ({len(wave_nodes)} node bersamaan) ---{Color.RESET}")
                with ThreadPoolExecutor(max_workers=parallelism) as executor:
                    futures = {
                        executor.submit(
                            self.provider.apply_resource,
                            addr,
                            graph_nodes[addr].attributes,
                        ): addr
                        for addr in wave_nodes
                    }
                    for future in as_completed(futures):
                        addr = futures[future]
                        res_state = future.result()
                        self.state_resources[addr] = res_state
                        print(
                            f"  {Color.GREEN}+ {addr}{Color.RESET} -> "
                            f"{Color.GRAY}ID={res_state['id']}, ARN={res_state['arn']}{Color.RESET}"
                        )

            # 5. Sinkronisasi State File (Serial increment)
            self.serial += 1
            self._save_state()
            return True

        finally:
            # 6. Lepas Lock
            self.lock_mgr.release_lock(owner=operator)

    def _save_state(self) -> None:
        state_payload = {
            "version": 4,
            "terraform_version": "1.8.5",
            "serial": self.serial,
            "lineage": self.lineage,
            "resources": [
                {
                    "mode": "managed",
                    "type": v.get("type", "custom"),
                    "name": k.split(".")[-1],
                    "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
                    "instances": [{"attributes": v}],
                }
                for k, v in self.state_resources.items()
            ],
        }
        print(f"\n{Color.CYAN}[STATE ENGINE] State berhasil diperbarui secara atomik:{Color.RESET}")
        print(f"  Lineage : {self.lineage}")
        print(f"  Serial  : {self.serial}")
        print(f"  Objects : {len(state_payload['resources'])} resource tersimpan.")


def run_lab():
    print_banner("SIMULASI TEKNIS INTERNAL TERRAFORM CORE & DAG ENGINE (M02)")

    # Definisi skenario resources dengan relasi eksplisit
    resources = {
        "aws_vpc.main": ResourceNode(
            address="aws_vpc.main",
            provider="aws",
            attributes={"type": "vpc", "cidr_block": "10.0.0.0/16"},
            dependencies=[],
        ),
        "aws_subnet.public_a": ResourceNode(
            address="aws_subnet.public_a",
            provider="aws",
            attributes={"type": "subnet", "cidr_block": "10.0.1.0/24"},
            dependencies=["aws_vpc.main"],
        ),
        "aws_subnet.public_b": ResourceNode(
            address="aws_subnet.public_b",
            provider="aws",
            attributes={"type": "subnet", "cidr_block": "10.0.2.0/24"},
            dependencies=["aws_vpc.main"],
        ),
        "aws_security_group.web": ResourceNode(
            address="aws_security_group.web",
            provider="aws",
            attributes={"type": "security_group", "ingress_port": "443"},
            dependencies=["aws_vpc.main"],
        ),
        "aws_instance.web_server": ResourceNode(
            address="aws_instance.web_server",
            provider="aws",
            attributes={"type": "instance", "ami": "ami-0123456789abcdef0", "instance_type": "t3.micro"},
            dependencies=["aws_subnet.public_a", "aws_security_group.web"],
        ),
    }

    core = TerraformCoreSimulator()

    # Eksekusi Apply Pertama
    print_banner("Langkah 1: Eksekusi Graf Terraform Apply Normal")
    success = core.execute_plan_and_apply(resources, parallelism=2)

    # Uji Konflik State Lock
    print_banner("Langkah 2: Uji Resiliensi Distributed Lock Concurrency Collision")
    print(f"{Color.GRAY}Mensimulasikan proses CLI kedua mencoba melakukan apply secara serentak...{Color.RESET}")
    core.lock_mgr.acquire_lock(owner="rogue-process-pid-9921", operation="Apply")
    second_attempt = core.lock_mgr.acquire_lock(owner="ci-runner-pid-1044", operation="Plan")
    if not second_attempt:
        print(f"{Color.GREEN}[VERIFIKASI SUKSES] Mekanisme Distributed State Locking berhasil mencegah korupsi state.{Color.RESET}")
    core.lock_mgr.release_lock(owner="rogue-process-pid-9921")

    # Uji Deteksi Circular Dependency
    print_banner("Langkah 3: Uji Deteksi Circular Dependency pada DAG Engine")
    bad_resources = {
        "module.a": ResourceNode("module.a", "aws", {"type": "mod_a"}, dependencies=["module.b"]),
        "module.b": ResourceNode("module.b", "aws", {"type": "mod_b"}, dependencies=["module.a"]),
    }
    dag_bad = DAGEngine(bad_resources)
    is_circular = dag_bad.detect_cycles()
    if is_circular:
        print(f"{Color.RED}[DAG DETECTED] Siklus sirkuler terdeteksi antara module.a <-> module.b! Graph walk digagalkan.{Color.RESET}")

    print_banner("LAB M02 SELESAI: ARSITEKTUR CORE & ENGINE TERVALIDASI")


if __name__ == "__main__":
    run_lab()

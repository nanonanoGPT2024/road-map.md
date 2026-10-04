#!/usr/bin/env python3
"""
Terraform DAG (Directed Acyclic Graph) & Lifecycle Simulator Engine
Kategori: 05-DevOps-Cloud-and-SRE | Bab 04: Resource Lifecycle & Dependency Graph Execution

Deskripsi:
Program mandiri (zero external dependencies selain library standar Python) yang
mensimulasikan algoritma kompilasi Terraform DAG:
1. Parsing Node Resource dan Relasi Dependensi (Implicit & Explicit).
2. Deteksi Siklus (Cycle Detection) menggunakan DFS Colors Algorithm.
3. Topological Sort untuk eksekusi paralel multi-worker sesuai bobot konkurensi.
4. Simulasi Lifecycle Hooks (create_before_destroy, prevent_destroy, replace_triggered_by).
"""

import sys
import time
import threading
from collections import defaultdict, deque
from typing import Dict, List, Set, Any, Optional

class ResourceNode:
    def __init__(self, resource_id: str, resource_type: str, attributes: Dict[str, Any]):
        self.id = resource_id
        self.type = resource_type
        self.attributes = attributes
        
        # Lifecycle metadata
        self.create_before_destroy = False
        self.prevent_destroy = False
        self.ignore_changes: List[str] = []
        self.replace_triggered_by: List[str] = []
        
        # Dependency tracking
        self.implicit_dependencies: Set[str] = set()
        self.explicit_dependencies: Set[str] = set()
        
        # State tracking
        self.current_state: Optional[Dict[str, Any]] = None
        self.action = "CREATE"  # NOOP, CREATE, UPDATE, DESTROY, REPLACE

    @property
    def all_dependencies(self) -> Set[str]:
        return self.implicit_dependencies.union(self.explicit_dependencies)

    def __repr__(self):
        return f"<Node: {self.id} | Action: {self.action}>"


class TerraformGraphEngine:
    def __init__(self, parallelism: int = 4):
        self.nodes: Dict[str, ResourceNode] = {}
        self.parallelism = parallelism
        self.execution_log: List[str] = []
        self._lock = threading.Lock()

    def add_node(self, node: ResourceNode):
        self.nodes[node.id] = node

    def detect_cycles(self) -> Optional[List[str]]:
        """
        Mendeteksi siklus menggunakan algoritma pewarnaan DFS 3-state:
        0 (WHITE): Belum dikunjungi
        1 (GRAY): Sedang dalam proses kunjungan (call stack aktif)
        2 (BLACK): Selesai dikunjungi
        """
        color = {node_id: 0 for node_id in self.nodes}
        parent_map = {}
        cycle_path = []

        def dfs(u: str) -> bool:
            color[u] = 1 # GRAY
            for v in self.nodes[u].all_dependencies:
                if v not in self.nodes:
                    continue # Asumsi simpul eksternal/provider
                if color[v] == 1:
                    # Terdeteksi cycle
                    cycle_path.append(v)
                    curr = u
                    while curr != v:
                        cycle_path.append(curr)
                        curr = parent_map.get(curr, v)
                    cycle_path.append(v)
                    cycle_path.reverse()
                    return True
                elif color[v] == 0:
                    parent_map[v] = u
                    if dfs(v):
                        return True
            color[u] = 2 # BLACK
            return False

        for node_id in self.nodes:
            if color[node_id] == 0:
                if dfs(node_id):
                    return cycle_path
        return None

    def export_dot_graph(self) -> str:
        """Menghasilkan representasi Graphviz DOT language."""
        lines = ["digraph G {", "  rankdir = \"BT\";", "  node [shape=box, fontname=\"Courier\"];"]
        for node_id, node in self.nodes.items():
            color = "black"
            if node.action == "CREATE":
                color = "green"
            elif node.action == "DESTROY":
                color = "red"
            elif node.action == "REPLACE":
                color = "orange"

            lines.append(f'  "{node_id}" [color="{color}", label="{node_id}\\n({node.action})"];')
            for dep in node.all_dependencies:
                style = "solid" if dep in node.implicit_dependencies else "dashed"
                lines.append(f'  "{node_id}" -> "{dep}" [style={style}];')
        lines.append("}")
        return "\n".join(lines)

    def compute_execution_plan(self):
        """Memvalidasi dan menyiapkan rencana aksi berdasarkan lifecycle hooks."""
        for node_id, node in self.nodes.items():
            # Evaluasi replace_triggered_by
            for trigger_id in node.replace_triggered_by:
                if trigger_id in self.nodes:
                    trigger_node = self.nodes[trigger_id]
                    if trigger_node.action in ["UPDATE", "REPLACE", "CREATE"]:
                        node.action = "REPLACE"
                        break

            # Evaluasi prevent_destroy
            if (node.action in ["DESTROY", "REPLACE"]) and node.prevent_destroy:
                raise RuntimeError(
                    f"CRITICAL STATE REJECTED: Resource '{node.id}' memiliki lifecycle.prevent_destroy = true. "
                    f"Rencana eksekusi '{node.action}' dibatalkan demi keamanan!"
                )

    def execute_graph(self):
        """
        Topological Sort + Parallel Concurrency Worker Pool.
        Node dieksekusi saat in-degree (dependensi yang belum selesai) bernilai 0.
        """
        cycle = self.detect_cycles()
        if cycle:
            raise ValueError(f"Graph Cycle Detected: {' -> '.join(cycle)}")

        self.compute_execution_plan()

        # In-degree tracking
        # Dependensi: node A bergantung pada node B -> B harus selesai SEBELUM A dieksekusi.
        # Edge arah eksekusi: B -> A (Ketika B selesai, cek A).
        dependents = defaultdict(list)
        remaining_dependencies = {}

        for node_id, node in self.nodes.items():
            valid_deps = [d for d in node.all_dependencies if d in self.nodes]
            remaining_dependencies[node_id] = len(valid_deps)
            for dep in valid_deps:
                dependents[dep].append(node_id)

        # Antrean simpul siap eksekusi (in-degree = 0)
        ready_queue = deque([n for n, count in remaining_dependencies.items() if count == 0])
        completed_nodes = set()
        total_nodes = len(self.nodes)

        print(f"\n[*] Memulai DAG Engine dengan Concurrency Level (-parallelism={self.parallelism})")
        print(f"[*] Total Node Terdaftar: {total_nodes}\n" + "="*60)

        def worker_task(node: ResourceNode):
            with self._lock:
                print(f"[EXECUTING] {node.id} via Worker [{threading.current_thread().name}]...")

            # Simulasi eksekusi lifecycle create_before_destroy vs destroy-then-create
            if node.action == "REPLACE":
                if node.create_before_destroy:
                    print(f"  └─> [CBD Mode] {node.id}: 1. Create New Instance...")
                    time.sleep(0.3)
                    print(f"  └─> [CBD Mode] {node.id}: 2. Destroy Old Instance (Zero-Downtime Swap)")
                else:
                    print(f"  └─> [Standard Mode] {node.id}: 1. Destroy Old Instance (Downtime Begun)...")
                    time.sleep(0.3)
                    print(f"  └─> [Standard Mode] {node.id}: 2. Create New Instance")
            else:
                time.sleep(0.2) # Simulasi latensi I/O API call

            with self._lock:
                print(f"[COMPLETED] {node.id} successfully applied.")
                completed_nodes.add(node.id)
                self.execution_log.append(node.id)

                # Notifikasi downstream nodes
                for downstream_id in dependents[node.id]:
                    remaining_dependencies[downstream_id] -= 1
                    if remaining_dependencies[downstream_id] == 0:
                        ready_queue.append(downstream_id)

        while len(completed_nodes) < total_nodes:
            threads = []
            while ready_queue and len(threads) < self.parallelism:
                next_node_id = ready_queue.popleft()
                node = self.nodes[next_node_id]
                t = threading.Thread(target=worker_task, args=(node,))
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

        print("="*60 + "\n[✔] Eksekusi State Graph Selesai Tanpa Kegagalan.")


# =====================================================================
# DEMONSTRASI MANDIRI
# =====================================================================
if __name__ == "__main__":
    print("[+] Menginisialisasi Terraform Architecture DAG Simulator...")
    engine = TerraformGraphEngine(parallelism=2)

    # 1. Definisikan Simpul Virtual
    vpc = ResourceNode("aws_vpc.main", "aws_vpc", {"cidr_block": "10.0.0.0/16"})
    
    subnet_a = ResourceNode("aws_subnet.public_a", "aws_subnet", {"cidr_block": "10.0.1.0/24"})
    subnet_a.implicit_dependencies.add("aws_vpc.main")

    subnet_b = ResourceNode("aws_subnet.public_b", "aws_subnet", {"cidr_block": "10.0.2.0/24"})
    subnet_b.implicit_dependencies.add("aws_vpc.main")

    trigger_data = ResourceNode("terraform_data.ami_rotator", "terraform_data", {"value": "v2.1.0"})
    trigger_data.action = "UPDATE" # Terjadi perubahan versi

    app_vm = ResourceNode("aws_instance.app_server", "aws_instance", {"instance_type": "t3.medium"})
    app_vm.implicit_dependencies.add("aws_subnet.public_a")
    app_vm.replace_triggered_by.append("terraform_data.ami_rotator")
    app_vm.create_before_destroy = True # Terapkan Zero-Downtime lifecycle

    db = ResourceNode("aws_db_instance.primary_db", "aws_db_instance", {"allocated_storage": 100})
    db.implicit_dependencies.add("aws_subnet.public_b")
    db.prevent_destroy = False # Set True jika ingin menguji mekanisme kegagalan prevent_destroy

    audit_observer = ResourceNode("local_file.audit_log", "local_file", {})
    audit_observer.explicit_dependencies.add("aws_instance.app_server") # depends_on

    # Daftarkan ke Engine
    for r in [vpc, subnet_a, subnet_b, trigger_data, app_vm, db, audit_observer]:
        engine.add_node(r)

    # Cetak DOT Graph
    print("\n--- Visualisasi Graphviz (DOT Language) ---")
    print(engine.export_dot_graph())
    print("-------------------------------------------\n")

    # Jalankan Eksekusi
    try:
        engine.execute_graph()
    except Exception as err:
        print(f"\n[!] TERRAFORM ENGINE HALTED: {err}", file=sys.stderr)
        sys.exit(1)

    print("\nUrutan Riil Eksekusi Selesai:")
    for idx, name in enumerate(engine.execution_log, 1):
        print(f" {idx}. {name}")
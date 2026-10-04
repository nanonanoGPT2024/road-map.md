#!/usr/bin/env python3
"""
Terragrunt DRY Catalog, DAG Orchestration & FinOps Governance Simulator
----------------------------------------------------------------------
File: terragrunt_dry_catalog_sim.py
Standar Mutu: GEMINI.md Enterprise DevOps Simulator Engine
Dependensi: Zero external dependency (Standard Python 3.8+ library only)
"""

import sys
import json
import logging
from typing import Dict, List, Set, Any, Optional

# Setup Logging Standard
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("TerragruntFinOpsSimulator")


class CatalogNode:
    """Merepresentasikan satu modul leaf terragrunt.hcl dalam hierarki live."""

    def __init__(
        self,
        node_id: str,
        path: str,
        dependencies: List[str],
        inputs: Dict[str, Any],
        monthly_cost_usd: float
    ):
        self.node_id = node_id
        self.path = path
        self.dependencies = dependencies
        self.inputs = inputs
        self.monthly_cost_usd = monthly_cost_usd

    def __repr__(self):
        return f"<CatalogNode: {self.node_id} -> Deps: {self.dependencies}>"


class TerragruntDAGOrchestrator:
    """Mengelola evaluasi dependensi, deteksi cycle, dan urutan eksekusi."""

    def __init__(self):
        self.nodes: Dict[str, CatalogNode] = {}

    def register_node(self, node: CatalogNode):
        if node.node_id in self.nodes:
            raise ValueError(f"Duplicate node detected: {node.node_id}")
        self.nodes[node.node_id] = node

    def detect_cycles(self) -> Optional[List[str]]:
        """Mendeteksi apakah terdapat circular dependency via DFS."""
        visited: Set[str] = set()
        recursion_stack: Set[str] = set()
        cycle_path: List[str] = []

        def dfs(current: str, path: List[str]) -> bool:
            visited.add(current)
            recursion_stack.add(current)
            path.append(current)

            for dep in self.nodes.get(current, CatalogNode(current, "", [], {}, 0.0)).dependencies:
                if dep not in self.nodes:
                    raise KeyError(f"Dependensi '{dep}' yang dideklarasikan oleh '{current}' tidak ditemukan dalam katalog!")
                
                if dep not in visited:
                    if dfs(dep, path):
                        return True
                elif dep in recursion_stack:
                    path.append(dep)
                    cycle_path.extend(path)
                    return True

            recursion_stack.remove(current)
            path.pop()
            return False

        for node_id in self.nodes:
            if node_id not in visited:
                if dfs(node_id, []):
                    return cycle_path
        return None

    def resolve_execution_order(self) -> List[List[str]]:
        """Menghasilkan batch eksekusi paralel berbasis Topological Sort (DAG Level)."""
        in_degree = {node_id: 0 for node_id in self.nodes}
        dependent_map: Dict[str, List[str]] = {node_id: [] for node_id in self.nodes}

        for node_id, node in self.nodes.items():
            for dep in node.dependencies:
                dependent_map[dep].append(node_id)
                in_degree[node_id] += 1

        queue = [node_id for node_id, deg in in_degree.items() if deg == 0]
        execution_batches: List[List[str]] = []

        while queue:
            current_batch = sorted(queue)
            execution_batches.append(current_batch)
            next_queue = []

            for node_id in current_batch:
                for dependent in dependent_map[node_id]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        next_queue.append(dependent)

            queue = next_queue

        total_resolved = sum(len(b) for b in execution_batches)
        if total_resolved != len(self.nodes):
            raise RuntimeError("Gagal menyelesaikan urutan eksekusi: Terjadi Circular Dependency yang belum tersaring!")

        return execution_batches


class GovernanceAndFinOpsEngine:
    """Audit penandaan (Resource Tagging) dan Guardrail Biaya (Infracost Simulator)."""

    REQUIRED_TAGS = {"Environment", "Owner", "CostCenter", "ManagedBy"}
    MAX_ALLOWABLE_DELTA_COST_USD = 1500.00

    @classmethod
    def audit_tags(cls, node: CatalogNode, root_default_tags: Dict[str, str]) -> Dict[str, Any]:
        """Memvalidasi pewarisan root default tags dan integritas tag modul."""
        merged_tags = {**root_default_tags, **node.inputs.get("tags", {})}
        missing = [tag for tag in cls.REQUIRED_TAGS if tag not in merged_tags]

        return {
            "node_id": node.node_id,
            "status": "PASS" if not missing else "FAILED",
            "effective_tags": merged_tags,
            "missing_tags": missing
        }

    @classmethod
    def evaluate_finops_budget(cls, total_cost: float, baseline_cost: float) -> Dict[str, Any]:
        delta = total_cost - baseline_cost
        pct_increase = (delta / baseline_cost * 100.0) if baseline_cost > 0 else 0.0
        exceeded = delta > cls.MAX_ALLOWABLE_DELTA_COST_USD

        return {
            "baseline_cost_usd": baseline_cost,
            "proposed_cost_usd": total_cost,
            "delta_usd": delta,
            "pct_increase": round(pct_increase, 2),
            "guardrail_limit_usd": cls.MAX_ALLOWABLE_DELTA_COST_USD,
            "policy_decision": "DENY" if exceeded else "APPROVE"
        }


def run_enterprise_catalog_simulation():
    print("=" * 80)
    print("  TERRAGRUNT MONOREPO ARCHITECTURE & FINOPS SIMULATION ENGINE")
    print("=" * 80)

    # 1. Konfigurasi Global Root (Mewakili infrastructure-live/terragrunt.hcl)
    root_default_tags = {
        "ManagedBy": "Terragrunt",
        "CostCenter": "Core-Platform-8082",
        "Owner": "SRE-Cloud-Team"
    }

    # 2. Definisikan Topologi Komponen Monorepo
    catalog = TerragruntDAGOrchestrator()

    # Leaf 1: Core Networking (VPC)
    vpc_node = CatalogNode(
        node_id="prod/ap-southeast-1/network/vpc",
        path="live/prod/ap-southeast-1/network/vpc/terragrunt.hcl",
        dependencies=[],
        inputs={
            "cidr": "10.0.0.0/16",
            "tags": {"Environment": "production", "Layer": "Network"}
        },
        monthly_cost_usd=145.00  # NAT Gateway & Data Transfer
    )

    # Leaf 2: Data Storage (RDS Postgres) - Bergantung pada VPC
    rds_node = CatalogNode(
        node_id="prod/ap-southeast-1/data/rds-postgres",
        path="live/prod/ap-southeast-1/data/rds-postgres/terragrunt.hcl",
        dependencies=["prod/ap-southeast-1/network/vpc"],
        inputs={
            "instance_class": "db.r6g.xlarge",
            "multi_az": True,
            "tags": {"Environment": "production", "DataSensitivity": "High"}
        },
        monthly_cost_usd=520.00
    )

    # Leaf 3: Compute Cluster (EKS) - Bergantung pada VPC
    eks_node = CatalogNode(
        node_id="prod/ap-southeast-1/compute/eks-cluster",
        path="live/prod/ap-southeast-1/compute/eks-cluster/terragrunt.hcl",
        dependencies=["prod/ap-southeast-1/network/vpc"],
        inputs={
            "cluster_version": "1.28",
            "node_count": 6,
            "tags": {"Environment": "production", "Workload": "Microservices"}
        },
        monthly_cost_usd=830.00
    )

    # Leaf 4: App Gateway (Ingress ALB) - Bergantung pada EKS & VPC
    alb_node = CatalogNode(
        node_id="prod/ap-southeast-1/app/ingress-alb",
        path="live/prod/ap-southeast-1/app/ingress-alb/terragrunt.hcl",
        dependencies=["prod/ap-southeast-1/network/vpc", "prod/ap-southeast-1/compute/eks-cluster"],
        inputs={
            "internal": False,
            "tags": {"Environment": "production", "IngressTier": "Public"}
        },
        monthly_cost_usd=95.00
    )

    # Daftarkan modul ke dalam DAG engine
    nodes_to_register = [vpc_node, rds_node, eks_node, alb_node]
    for n in nodes_to_register:
        catalog.register_node(n)
        logger.info(f"Modul terdaftar: {n.node_id} (Path: {n.path})")

    # 3. Validasi Siklus Ketergantungan (Cycle Detection)
    print("\n" + "-" * 40)
    print("FASE 1: VERIFIKASI SIKLUS DAG (CIRCULAR DEPENDENCY AUDIT)")
    print("-" * 40)
    cycle = catalog.detect_cycles()
    if cycle:
        logger.error(f"CRITICAL: Circular dependency terdeteksi -> {' -> '.join(cycle)}")
        sys.exit(1)
    else:
        logger.info("DAG Check PASS: Tidak ada siklus sirkular. Struktur dependency valid.")

    # 4. Hitung Urutan Eksekusi Terisolasi (Topological Sort Levels)
    print("\n" + "-" * 40)
    print("FASE 2: ORKESTRASI URUTAN EKSEKUSI (BLAST RADIUS ISOLATION)")
    print("-" * 40)
    execution_plan = catalog.resolve_execution_order()
    for stage_idx, batch in enumerate(execution_plan, start=1):
        print(f"  [Tahap Eksekusi {stage_idx}]:")
        for item in batch:
            print(f"    └── Leaf Module: {item}")

    # 5. Audit Resource Tagging Governance
    print("\n" + "-" * 40)
    print("FASE 3: AUDIT TATA KELOLA PENANDAAN (TAGGING GOVERNANCE)")
    print("-" * 40)
    compliance_failed = False
    for node in catalog.nodes.values():
        audit_result = GovernanceAndFinOpsEngine.audit_tags(node, root_default_tags)
        if audit_result["status"] == "PASS":
            logger.info(f"Tag Compliance PASS: {node.node_id}")
            print(f"       Effective Tags: {json.dumps(audit_result['effective_tags'])}")
        else:
            logger.error(f"Tag Compliance FAILED: {node.node_id}")
            print(f"       Missing Tags: {audit_result['missing_tags']}")
            compliance_failed = True

    if compliance_failed:
        logger.error("Kebijakan Governance ditolak karena ada modul yang tidak patuh tag.")
        sys.exit(1)

    # 6. Analisis FinOps Shift-Left Guardrails
    print("\n" + "-" * 40)
    print("FASE 4: ANALISIS FINOPS & SHIFT-LEFT COST ESTIMATE")
    print("-" * 40)
    baseline_cost = 900.00  # Baseline bulan sebelumnya
    total_proposed_cost = sum(node.monthly_cost_usd for node in catalog.nodes.values())
    finops_report = GovernanceAndFinOpsEngine.evaluate_finops_budget(total_proposed_cost, baseline_cost)

    print(f"  Biaya Baseline Sebelumnya : ${finops_report['baseline_cost_usd']:.2f} /bulan")
    print(f"  Total Estimasi Biaya Baru : ${finops_report['proposed_cost_usd']:.2f} /bulan")
    print(f"  Delta Peningkatan Biaya   : +${finops_report['delta_usd']:.2f} /bulan (+{finops_report['pct_increase']}%)")
    print(f"  Batas Maksimum Guardrail  : ${finops_report['guardrail_limit_usd']:.2f} /bulan")
    print(f"  Status Evaluasi FinOps    : [{finops_report['policy_decision']}]")

    if finops_report["policy_decision"] == "APPROVE":
        logger.info("FinOps Gate APPROVED: Estimasi biaya berada di bawah ambang batas delta maksimum.")
    else:
        logger.error("FinOps Gate BLOCKED: Kenaikan biaya melebihi ambang batas toleransi tanpa persetujuan Lead FinOps!")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("  SIMULASI BERHASIL: SELURUH PARAMETER SKALABILITAS TERVERIFIKASI AMAN.")
    print("=" * 80)


if __name__ == "__main__":
    run_enterprise_catalog_simulation()
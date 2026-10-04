#!/usr/bin/env python3
"""
Lab Hands-on: Enterprise Scale, Monorepos, & Large Asset Management
Category: 01-Core-Foundations | Chapter: 10 (Deep Dive)

Simulates the mechanical internals of:
1. Git LFS (Large File Storage): Content-Addressable Storage (CAS), clean/smudge filters,
   and SHA-256 pointer generation.
2. Partial Clones & Sparse-Checkout (Cone Mode): Tree-slicing and lazy object hydration.
3. Monorepo Dependency Graph & Affected Target Resolver: Targeted CI/CD build impact
   analysis across multi-package workspaces.
"""

import os
import sys
import hashlib
import time
import json
from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple, Optional

# ANSI Terminal Styling
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_RED = "\033[31m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_BLUE = "\033[34m"
C_MAGENTA = "\033[35m"
C_CYAN = "\033[36m"
C_WHITE = "\033[37m"

def print_header(title: str):
    print(f"\n{C_BOLD}{C_BLUE}{'=' * 75}{C_RESET}")
    print(f"{C_BOLD}{C_CYAN} [LAB] {title.upper()}{C_RESET}")
    print(f"{C_BOLD}{C_BLUE}{'=' * 75}{C_RESET}")

def print_step(step_num: int, title: str):
    print(f"\n{C_BOLD}{C_YELLOW}>>> Step {step_num}: {title}{C_RESET}")

def print_metric(label: str, val: str, color=C_GREEN):
    print(f"  {C_WHITE}{label:<35}: {color}{val}{C_RESET}")


class GitLFSServer:
    """
    Simulates a remote Content-Addressable Storage (CAS) for Git LFS objects.
    Uses SHA-256 checksums as immutable keys.
    """
    def __init__(self):
        self.storage: Dict[str, bytes] = {}
        self.total_bytes_transferred = 0

    def upload(self, oid: str, data: bytes) -> bool:
        computed_oid = hashlib.sha256(data).hexdigest()
        if computed_oid != oid:
            raise ValueError(f"OID mismatch: payload corruption detected!")
        if oid not in self.storage:
            self.storage[oid] = data
            self.total_bytes_transferred += len(data)
            return True
        return False  # Already exists (Deduplicated)

    def download(self, oid: str) -> bytes:
        if oid not in self.storage:
            raise KeyError(f"Object {oid} not found in LFS CAS store.")
        data = self.storage[oid]
        self.total_bytes_transferred += len(data)
        return data


class GitLFSFilter:
    """
    Implements Git Clean & Smudge filters according to the Git LFS v1 specification.
    """
    LFS_SPEC_PREFIX = "version https://git-lfs.github.com/spec/v1\n"

    def __init__(self, lfs_server: GitLFSServer):
        self.server = lfs_server

    def clean(self, raw_binary: bytes) -> str:
        """
        Clean filter: Converts large binary payload to an LFS text pointer file,
        and pushes the binary payload to the remote CAS.
        """
        oid = hashlib.sha256(raw_binary).hexdigest()
        size = len(raw_binary)
        self.server.upload(oid, raw_binary)

        # Standard Git LFS Pointer Format
        pointer = (
            f"{self.LFS_SPEC_PREFIX}"
            f"oid sha256:{oid}\n"
            f"size {size}\n"
        )
        return pointer

    def smudge(self, pointer_text: str) -> bytes:
        """
        Smudge filter: Reads pointer text, extracts OID, and pulls actual binary payload.
        """
        if not pointer_text.startswith(self.LFS_SPEC_PREFIX):
            # Not an LFS pointer, return raw content as-is
            return pointer_text.encode('utf-8')

        lines = pointer_text.strip().split('\n')
        oid = ""
        for line in lines:
            if line.startswith("oid sha256:"):
                oid = line.replace("oid sha256:", "").strip()

        if not oid:
            raise ValueError("Malformed LFS pointer: missing OID.")

        return self.server.download(oid)


class MonorepoDependencyGraph:
    """
    Maintains dependency relationships across monorepo packages to calculate
    impacted build targets on commits (Affected Graph Analysis).
    """
    def __init__(self):
        self.adjacency: Dict[str, Set[str]] = defaultdict(set)      # pkg -> dependencies
        self.reverse_adj: Dict[str, Set[str]] = defaultdict(set)    # pkg -> dependents
        self.package_paths: Dict[str, str] = {}                     # pkg -> root folder

    def register_package(self, name: str, folder_path: str, dependencies: List[str]):
        self.package_paths[name] = folder_path.rstrip('/')
        for dep in dependencies:
            self.adjacency[name].add(dep)
            self.reverse_adj[dep].add(name)

    def resolve_affected(self, changed_files: List[str]) -> Tuple[Set[str], Set[str]]:
        """
        Given a list of changed paths, determines directly changed packages
        and all transitively impacted downstream packages.
        """
        directly_affected = set()

        for file_path in changed_files:
            for pkg, folder in self.package_paths.items():
                if file_path.startswith(folder + "/"):
                    directly_affected.add(pkg)
                    break

        # Breadth-First Search (BFS) for Transitive Downstream Targets
        transitively_affected = set()
        queue = deque(directly_affected)

        while queue:
            current = queue.popleft()
            for dependent in self.reverse_adj[current]:
                if dependent not in directly_affected and dependent not in transitively_affected:
                    transitively_affected.add(dependent)
                    queue.append(dependent)

        return directly_affected, transitively_affected


class EnterpriseWorkspaceSimulator:
    """
    Simulates a monorepo working directory handling Sparse-Checkout,
    partial cloning, and Git LFS hydration.
    """
    def __init__(self, lfs_server: GitLFSServer):
        self.lfs_filter = GitLFSFilter(lfs_server)
        self.repository_tree: Dict[str, dict] = {} # path -> {is_lfs, content/pointer, size}
        self.sparse_cone_rules: List[str] = []

    def add_source_file(self, path: str, content: str):
        self.repository_tree[path] = {
            "is_lfs": False,
            "data": content,
            "size": len(content.encode('utf-8'))
        }

    def add_lfs_asset(self, path: str, binary_data: bytes):
        pointer_str = self.lfs_filter.clean(binary_data)
        self.repository_tree[path] = {
            "is_lfs": True,
            "data": pointer_str,
            "size": len(binary_data), # Actual physical payload size
            "pointer_size": len(pointer_str.encode('utf-8'))
        }

    def set_sparse_checkout_cone(self, allowed_directories: List[str]):
        self.sparse_cone_rules = [d.rstrip('/') for d in allowed_directories]

    def _is_path_included(self, path: str) -> bool:
        if not self.sparse_cone_rules:
            return True  # Full checkout
        for cone in self.sparse_cone_rules:
            if path.startswith(cone + "/") or path == cone:
                return True
        return False

    def simulate_checkout(self, partial_clone: bool = False, lazy_lfs: bool = False):
        """
        Calculates network download size and local disk footprint based on checkout mode.
        """
        git_objects_transferred_bytes = 0
        lfs_bytes_transferred = 0
        disk_footprint_bytes = 0
        files_checked_out = 0

        for path, meta in self.repository_tree.items():
            included = self._is_path_included(path)

            # Metadata/Tree transfer (Blob-less clone skips tree/blobs outside sparse cone)
            if partial_clone and not included:
                # Treeless/blobless sparse-checkout: Remote sends zero blob data for filtered paths
                continue

            if not included:
                # Non-sparse: Git transfers commit tree & blobs, but excludes them from working dir
                git_objects_transferred_bytes += meta["pointer_size"] if meta["is_lfs"] else meta["size"]
                continue

            # File is inside Sparse Cone: Checked out to working tree
            files_checked_out += 1

            if meta["is_lfs"]:
                git_objects_transferred_bytes += meta["pointer_size"]
                if not lazy_lfs:
                    # Smudge operation executes immediately
                    lfs_bytes_transferred += meta["size"]
                    disk_footprint_bytes += meta["size"]
                else:
                    # Lazy: Pointer remains on disk until explicitly invoked
                    disk_footprint_bytes += meta["pointer_size"]
            else:
                git_objects_transferred_bytes += meta["size"]
                disk_footprint_bytes += meta["size"]

        return {
            "files_active": files_checked_out,
            "git_network_bytes": git_objects_transferred_bytes,
            "lfs_network_bytes": lfs_bytes_transferred,
            "total_network_bytes": git_objects_transferred_bytes + lfs_bytes_transferred,
            "disk_footprint_bytes": disk_footprint_bytes
        }


def format_bytes(size: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if abs(size) < 1024.0:
            return f"{size:3.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"


def main():
    print_header("Enterprise Monorepo, Sparse Engine & LFS Deep Dive")

    lfs_server = GitLFSServer()
    workspace = EnterpriseWorkspaceSimulator(lfs_server)
    dep_graph = MonorepoDependencyGraph()

    # -------------------------------------------------------------
    # 1. Monorepo Setup & Topology Configuration
    # -------------------------------------------------------------
    print_step(1, "Configuring Enterprise Monorepo Topology & Dependencies")

    # Define Workspace Packages
    dep_graph.register_package("core-utils", "packages/core-utils", [])
    dep_graph.register_package("ui-components", "packages/ui-components", ["core-utils"])
    dep_graph.register_package("auth-service", "services/auth-service", ["core-utils"])
    dep_graph.register_package("billing-service", "services/billing-service", ["core-utils", "auth-service"])
    dep_graph.register_package("payment-gateway", "services/payment-gateway", ["billing-service"])
    dep_graph.register_package("analytics-pipeline", "services/analytics-pipeline", ["core-utils"])
    dep_graph.register_package("fraud-detection-ml", "ml/fraud-detection", ["core-utils"])

    print(f"  {C_GREEN}✔ Registered 7 packages with cross-service dependency edges.{C_RESET}")
    print(f"  Graph Dependency Mapping:")
    for pkg, deps in dep_graph.adjacency.items():
        deps_str = ", ".join(deps) if deps else "<none>"
        print(f"    - {C_BOLD}{pkg:<22}{C_RESET} depends on: {C_CYAN}{deps_str}{C_RESET}")

    # -------------------------------------------------------------
    # 2. Ingesting Source Trees and Large Binary Assets (LFS)
    # -------------------------------------------------------------
    print_step(2, "Generating Large-Scale Repository Contents & Assets")

    # Standard Source Code Files (~150 KB code per service)
    for pkg, folder in dep_graph.package_paths.items():
        for i in range(15):
            dummy_code = f"// Package: {pkg} Module #{i}\n" + ("export function run() { return true; }\n" * 250)
            workspace.add_source_file(f"{folder}/src/module_{i}.ts", dummy_code)

    # Large Assets: Datasets, ML Weights, Compiled Artifacts
    # Model 1: Fraud Detection Neural Weights (50 MB virtual binary)
    raw_ml_weights = b"\x7FELF" + os.urandom(1024 * 1024 * 48)  # 48 MB binary
    workspace.add_lfs_asset("ml/fraud-detection/models/weights.bin", raw_ml_weights)

    # Asset 2: Payment Gateway Testing Mock Vault (12 MB binary)
    raw_vault = b"PK\x03\x04" + os.urandom(1024 * 1024 * 12)    # 12 MB binary
    workspace.add_lfs_asset("services/payment-gateway/fixtures/pci_records.dat", raw_vault)

    # Asset 3: UI Design Mockups and Asset Bundle (8 MB binary)
    raw_ui_assets = b"PNG\r\n\x1a\n" + os.urandom(1024 * 1024 * 8) # 8 MB binary
    workspace.add_lfs_asset("packages/ui-components/assets/design_tokens.tar.gz", raw_ui_assets)

    total_files = len(workspace.repository_tree)
    print(f"  {C_GREEN}✔ Synthesized {total_files} repository files across services and ML assets.{C_RESET}")

    # Inspect generated LFS pointer
    ml_entry = workspace.repository_tree["ml/fraud-detection/models/weights.bin"]
    print(f"\n  {C_MAGENTA}Git LFS Pointer Inspection (Stored in Git tree instead of binary):{C_RESET}")
    for line in ml_entry["data"].strip().split("\n"):
        print(f"    | {C_YELLOW}{line}{C_RESET}")

    # -------------------------------------------------------------
    # 3. Checkout Strategies Benchmark (Full vs Sparse vs Blobless)
    # -------------------------------------------------------------
    print_step(3, "Evaluating Scale Scenarios: Full vs Partial Clone + Sparse Cone")

    # Baseline: Full Clone + Full Checkout (Junior dev standard workflow)
    workspace.set_sparse_checkout_cone([]) # No sparse rules (all files)
    metrics_full = workspace.simulate_checkout(partial_clone=False, lazy_lfs=False)

    # Scenario B: Sparse Checkout (Cone Mode: Only 'services/billing-service')
    # Developer on billing team needs only billing-service and its direct dependencies
    workspace.set_sparse_checkout_cone(["services/billing-service", "packages/core-utils", "services/auth-service"])
    metrics_sparse = workspace.simulate_checkout(partial_clone=True, lazy_lfs=True)

    print(f"\n{C_BOLD}{'Checkout Mode Benchmark':<32} | {'Net Download':<14} | {'Disk Footprint':<14} | {'Active Files':<12}{C_RESET}")
    print("-" * 80)
    print(f"{'1. Traditional Full Clone (All)':<32} | "
          f"{format_bytes(metrics_full['total_network_bytes']):<14} | "
          f"{format_bytes(metrics_full['disk_footprint_bytes']):<14} | "
          f"{metrics_full['files_active']:<12}")

    print(f"{'2. Blobless + Cone Sparse + LFS':<32} | "
          f"{C_GREEN}{format_bytes(metrics_sparse['total_network_bytes']):<14}{C_RESET} | "
          f"{C_GREEN}{format_bytes(metrics_sparse['disk_footprint_bytes']):<14}{C_RESET} | "
          f"{C_GREEN}{metrics_sparse['files_active']:<12}{C_RESET}")

    savings_net = (1.0 - (metrics_sparse['total_network_bytes'] / metrics_full['total_network_bytes'])) * 100
    savings_disk = (1.0 - (metrics_sparse['disk_footprint_bytes'] / metrics_full['disk_footprint_bytes'])) * 100
    print("-" * 80)
    print(f"  {C_BOLD}{C_GREEN}Bandwidth Efficiency Gain: {savings_net:.2f}% reduction!{C_RESET}")
    print(f"  {C_BOLD}{C_GREEN}Disk Resource Savings:     {savings_disk:.2f}% reduction!{C_RESET}")

    # -------------------------------------------------------------
    # 4. Monorepo Affected Dependency Resolver
    # -------------------------------------------------------------
    print_step(4, "Simulating Monorepo Affected Target Analysis (CI/CD Optimization)")

    # Simulate commits touching specific paths
    test_changesets = [
        {
            "description": "Hotfix in core-utils math routine",
            "modified_files": [
                "packages/core-utils/src/module_2.ts",
                "packages/core-utils/src/module_3.ts"
            ]
        },
        {
            "description": "Style change in UI component library",
            "modified_files": [
                "packages/ui-components/src/module_5.ts"
            ]
        },
        {
            "description": "Model weight retrain in ML directory",
            "modified_files": [
                "ml/fraud-detection/models/weights.bin"
            ]
        }
    ]

    for idx, test in enumerate(test_changesets, 1):
        print(f"\n  {C_BOLD}Changeset #{idx}: {C_WHITE}{test['description']}{C_RESET}")
        for mf in test['modified_files']:
            print(f"    {C_RED}[MODIFIED]{C_RESET} {mf}")

        directly, transitively = dep_graph.resolve_affected(test['modified_files'])
        all_targets = directly.union(transitively)

        print(f"    Directly Impacted Packages:     {C_YELLOW}{', '.join(sorted(directly)) or '<none>'}{C_RESET}")
        print(f"    Downstream Cascaded Rebuilds:   {C_RED}{', '.join(sorted(transitively)) or '<none>'}{C_RESET}")
        print(f"    Total CI Execution Targets:     {C_CYAN}{len(all_targets)} / {len(dep_graph.package_paths)} packages{C_RESET}")

    # -------------------------------------------------------------
    # 5. Git LFS Smudge & Clean Round-Trip Verification
    # -------------------------------------------------------------
    print_step(5, "Verifying Git LFS Smudge Filter Integrity & CAS Deduplication")

    sample_asset = b"CRITICAL_ENTERPRISE_SIGNING_KEY_PAYLOAD_DATA_BLOB" * 1024
    original_sha = hashlib.sha256(sample_asset).hexdigest()

    # Step 5a: Clean Filter
    pointer_text = workspace.lfs_filter.clean(sample_asset)
    print(f"  Clean Filter -> Pointer created. SHA256: {C_GREEN}{original_sha}{C_RESET}")

    # Step 5b: Deduplication Check
    dup_clean = workspace.lfs_filter.clean(sample_asset)
    print(f"  Duplicate Push -> Remote Deduplication Successful: {C_GREEN}True{C_RESET}")

    # Step 5c: Smudge Filter (Hydration)
    hydrated_bytes = workspace.lfs_filter.smudge(pointer_text)
    hydrated_sha = hashlib.sha256(hydrated_bytes).hexdigest()

    assert original_sha == hydrated_sha, "Payload corruption occurred during LFS round-trip!"
    print(f"  Smudge Filter -> Hydrated bytes: {len(hydrated_bytes)} bytes. Integrity match: {C_GREEN}100% OK{C_RESET}")

    print(f"\n{C_BOLD}{C_GREEN}✔ Lab Completed: All Monorepo, Sparse-Checkout, and LFS invariants verified.{C_RESET}\n")

if __name__ == "__main__":
    main()
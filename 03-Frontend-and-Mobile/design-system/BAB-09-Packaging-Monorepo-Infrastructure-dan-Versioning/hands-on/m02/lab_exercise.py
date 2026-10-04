#!/usr/bin/env python3
"""
Lab Hands-on: Monorepo Infrastructure, Build Orchestration, and SemVer Cascading.
Topic: Design System Packaging & Multi-Package Architecture
Category: 03-Frontend-and-Mobile (Ch 09 - Mod 02 Deep Dive)

Deskripsi:
Skrip ini mensimulasikan sistem orkestrasi Monorepo canggih (mirip Turborepo/Lerna/Nx)
khusus Design System. Mensimulasikan:
1. Resolusi Dependency Graph (Directed Acyclic Graph) dengan Topological Sort.
2. Content-Addressable Caching (kalkulasi hash gabungan sumber + dependency upstream).
3. Incremental Build Pipeline (Cold vs Warm execution).
4. Semantic Versioning (SemVer) bumping engine dengan propagasi otomatis ke downstream consumers.
"""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import time
from typing import Dict, List, Optional, Set, Tuple

# ANSI Palette untuk output terminal interaktif
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"
CLR_GRAY = "\033[90m"


class ReleaseType(Enum):
    PATCH = 1
    MINOR = 2
    MAJOR = 3


@dataclass
class SemVer:
    """Parser dan manipulator Semantic Versioning (SemVer 2.0.0)."""
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, version_str: str) -> "SemVer":
        parts = [int(p) for p in version_str.strip().split(".")]
        return cls(parts[0], parts[1], parts[2])

    def bump(self, release_type: ReleaseType) -> "SemVer":
        if release_type == ReleaseType.MAJOR:
            return SemVer(self.major + 1, 0, 0)
        elif release_type == ReleaseType.MINOR:
            return SemVer(self.major, self.minor + 1, 0)
        elif release_type == ReleaseType.PATCH:
            return SemVer(self.major, self.minor, self.patch + 1)
        return self

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass
class Package:
    """Representasi package individual dalam monorepo."""
    name: str
    version: SemVer
    dependencies: List[str] = field(default_factory=list)
    source_files: Dict[str, str] = field(default_factory=dict)  # path -> content string

    def calculate_source_hash(self) -> str:
        """Menghitung SHA-256 murni dari konten file internal paket."""
        hasher = hashlib.sha256()
        for path in sorted(self.source_files.keys()):
            hasher.update(path.encode("utf-8"))
            hasher.update(self.source_files[path].encode("utf-8"))
        return hasher.hexdigest()[:12]


class MonorepoWorkspace:
    """Mesin orkestrasi monorepo: dependency graph, build caching, dan release cascading."""

    def __init__(self):
        self.packages: Dict[str, Package] = {}
        self.build_cache: Dict[str, str] = {}  # package_name -> composite_hash

    def register_package(self, pkg: Package) -> None:
        self.packages[pkg.name] = pkg

    def get_topological_order(self) -> List[str]:
        """
        Kahn's Algorithm untuk mendeteksi siklus dan mengurutkan eksekusi build
        dari leaf dependencies ke root consumers.
        """
        in_degree = {pkg_name: 0 for pkg_name in self.packages}
        adjacency = defaultdict(list)

        for name, pkg in self.packages.items():
            for dep in pkg.dependencies:
                if dep in self.packages:
                    adjacency[dep].append(name)
                    in_degree[name] += 1

        queue = deque([pkg for pkg, deg in in_degree.items() if deg == 0])
        order = []

        while queue:
            curr = queue.popleft()
            order.append(curr)
            for neighbor in adjacency[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.packages):
            raise ValueError(f"{CLR_RED}Cyclic dependency terdeteksi dalam monorepo!{CLR_RESET}")

        return order

    def compute_composite_hash(self, pkg_name: str, upstream_hashes: Dict[str, str]) -> str:
        """
        Composite Cache Key = SHA256(Source Hash + Hashes dari semua direct dependencies).
        Memastikan jika `@tokens` berubah, `@button` otomatis invalid walau kode `@button` sama.
        """
        pkg = self.packages[pkg_name]
        hasher = hashlib.sha256()
        hasher.update(pkg.calculate_source_hash().encode("utf-8"))

        for dep in sorted(pkg.dependencies):
            if dep in upstream_hashes:
                hasher.update(upstream_hashes[dep].encode("utf-8"))

        return hasher.hexdigest()[:12]

    def build_pipeline(self) -> None:
        """Menjalankan pipeline build incremental berbasis Directed Acyclic Graph."""
        print(f"\n{CLR_BOLD}{CLR_CYAN}=== MENJALANKAN MONOREPO BUILD PIPELINE ==={CLR_RESET}")
        order = self.get_topological_order()
        current_hashes: Dict[str, str] = {}

        for pkg_name in order:
            pkg = self.packages[pkg_name]
            composite_hash = self.compute_composite_hash(pkg_name, current_hashes)
            current_hashes[pkg_name] = composite_hash

            cached_hash = self.build_cache.get(pkg_name)
            is_cache_hit = (cached_hash == composite_hash)

            if is_cache_hit:
                status = f"{CLR_GREEN}[CACHE HIT]{CLR_RESET}"
                exec_time = "0.01ms"
            else:
                status = f"{CLR_YELLOW}[BUILDING]{CLR_RESET}"
                time.sleep(0.06)  # Simulasi kompilasi rollup/esbuild
                self.build_cache[pkg_name] = composite_hash
                exec_time = "62.40ms"

            deps_repr = f"{CLR_GRAY}(deps: {', '.join(pkg.dependencies) if pkg.dependencies else 'none'}){CLR_RESET}"
            print(f"  {status} {CLR_BOLD}{pkg_name:<20}{CLR_RESET} [Hash: {composite_hash}] {exec_time:<8} {deps_repr}")

    def apply_changeset(self, target_pkg: str, release_type: ReleaseType, reason: str) -> None:
        """
        Menerapkan SemVer bump dan secara otomatis melakukan propagasi SemVer
        (Patch bump) ke seluruh downstream consumer yang bergantung pada paket tersebut.
        """
        print(f"\n{CLR_BOLD}{CLR_MAGENTA}=== MENERAPKAN CHANGESET: {target_pkg} ({release_type.name}) ==={CLR_RESET}")
        print(f"Alasan: {CLR_GRAY}{reason}{CLR_RESET}")

        if target_pkg not in self.packages:
            raise KeyError(f"Package {target_pkg} tidak ditemukan.")

        # Bump target
        old_v = self.packages[target_pkg].version
        new_v = old_v.bump(release_type)
        self.packages[target_pkg].version = new_v
        print(f"  {CLR_GREEN}✓{CLR_RESET} Bumped target {CLR_BOLD}{target_pkg}{CLR_RESET}: {old_v} -> {CLR_BOLD}{new_v}{CLR_RESET}")

        # Identifikasi Downstream Packages (BFS)
        downstream = defaultdict(list)
        for name, pkg in self.packages.items():
            for dep in pkg.dependencies:
                downstream[dep].append(name)

        visited: Set[str] = set()
        queue = deque(downstream[target_pkg])

        while queue:
            consumer = queue.popleft()
            if consumer in visited:
                continue
            visited.add(consumer)

            # Downstream consumers otomatis menerima PATCH bump karena perubahan dependensi
            c_pkg = self.packages[consumer]
            c_old_v = c_pkg.version
            c_pkg.version = c_old_v.bump(ReleaseType.PATCH)
            print(f"  {CLR_CYAN}↳ Cascaded bump{CLR_RESET} {consumer}: {c_old_v} -> {CLR_BOLD}{c_pkg.version}{CLR_RESET} (due to {target_pkg})")

            for next_consumer in downstream[consumer]:
                if next_consumer not in visited:
                    queue.append(next_consumer)


def main():
    print(f"{CLR_BOLD}LAB: Packaging, Monorepo Infrastructure & Versioning Simulation{CLR_RESET}")
    print(f"Engine: In-Memory DAG Task Runner & Changeset Analyzer\n")

    workspace = MonorepoWorkspace()

    # 1. Setup Desain Sistem Package Topology
    # Structure:
    # @ds/tokens          (Level 0)
    # @ds/primitives      (Level 0)
    # @ds/button          (Level 1, depends on: @ds/tokens, @ds/primitives)
    # @ds/card            (Level 1, depends on: @ds/tokens)
    # @ds/dialog          (Level 2, depends on: @ds/button)
    # @ds/documentation   (Level 3, depends on: @ds/button, @ds/card, @ds/dialog)

    workspace.register_package(Package(
        name="@ds/tokens",
        version=SemVer(1, 0, 0),
        source_files={"colors.json": '{"primary": "#0055ff", "bg": "#ffffff"}'}
    ))

    workspace.register_package(Package(
        name="@ds/primitives",
        version=SemVer(1, 0, 0),
        source_files={"box.tsx": "export const Box = ({children}) => <div>{children}</div>;"}
    ))

    workspace.register_package(Package(
        name="@ds/button",
        version=SemVer(1, 0, 0),
        dependencies=["@ds/tokens", "@ds/primitives"],
        source_files={"button.tsx": "import { Box } from '@ds/primitives'; export const Button = () => null;"}
    ))

    workspace.register_package(Package(
        name="@ds/card",
        version=SemVer(1, 0, 0),
        dependencies=["@ds/tokens"],
        source_files={"card.tsx": "export const Card = () => null;"}
    ))

    workspace.register_package(Package(
        name="@ds/dialog",
        version=SemVer(1, 0, 0),
        dependencies=["@ds/button"],
        source_files={"dialog.tsx": "import { Button } from '@ds/button'; export const Dialog = () => null;"}
    ))

    workspace.register_package(Package(
        name="@ds/documentation",
        version=SemVer(1, 0, 0),
        dependencies=["@ds/button", "@ds/card", "@ds/dialog"],
        source_files={"index.html": "<div id='app'>Design System Docs</div>"}
    ))

    # Review DAG Execution Order
    build_order = workspace.get_topological_order()
    print(f"{CLR_BOLD}Topological Build Order:{CLR_RESET}")
    print(" -> ".join([f"{CLR_CYAN}{pkg}{CLR_RESET}" for pkg in build_order]))

    # RUN 1: Cold Build (Semua paket harus di-compile)
    workspace.build_pipeline()

    # RUN 2: Re-run tanpa perubahan (Verifikasi 100% Cache Hit)
    workspace.build_pipeline()

    # MODIFIKASI: Ubah kode internal pada @ds/tokens saja
    print(f"\n{CLR_BOLD}{CLR_YELLOW}[ACTION] Mengubah color palette di @ds/tokens...{CLR_RESET}")
    workspace.packages["@ds/tokens"].source_files["colors.json"] = '{"primary": "#0044ee", "bg": "#f9f9f9"}'

    # RUN 3: Incremental Build (Hanya @ds/tokens dan dependan-nya yang rebuild; @ds/primitives harus CACHE HIT)
    workspace.build_pipeline()

    # CHANGESET & PROPAGASI VERSI:
    # Mengumumkan breaking change atau minor update pada @ds/tokens
    workspace.apply_changeset(
        target_pkg="@ds/tokens",
        release_type=ReleaseType.MINOR,
        reason="Menambahkan token semantic color baru untuk dark-mode palette."
    )

    # Status Versi Akhir Monorepo
    print(f"\n{CLR_BOLD}{CLR_GREEN}=== STATUS AKHIR VERSI MONOREPO ==={CLR_RESET}")
    for name in workspace.get_topological_order():
        pkg = workspace.packages[name]
        print(f"  {CLR_BOLD}{pkg.name:<20}{CLR_RESET}: v{pkg.version}")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Lab Hands-on: Modern Frontend Tooling, Version Control & Git Internals
Category: 01-Core-Foundations | Chapter 09 - Deep Dive

Simulasi teknis implementasi internal Git (Content-Addressable Storage / CAS)
dan Content Hash Tree (DAG Engine) yang mendasari sistem kontrol versi modern
serta sistem bundler/caching frontend (seperti Vite, Webpack, dan Turbopack).
"""

import hashlib
import time
from typing import Dict, List, Optional, Tuple

# Konstanta warna ANSI untuk output terminal
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_CYAN = "\033[36m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_RED = "\033[31m"
COLOR_MAGENTA = "\033[35m"


class ContentAddressableStore:
    """
    Meniru mekanisme database objek internal Git (Blob, Tree, Commit).
    Menggunakan SHA-1 hashing berdasarkan konten persis sesuai standar format Git:
    '<type> <size>\\0<content>'
    """
    def __init__(self) -> None:
        self._storage: Dict[str, bytes] = {}

    def write_object(self, obj_type: str, content: bytes) -> str:
        """Menyimpan objek terkomputasi hash ke dalam CAS."""
        header = f"{obj_type} {len(content)}\0".encode("utf-8")
        store_payload = header + content
        sha1_hash = hashlib.sha1(store_payload).hexdigest()
        self._storage[sha1_hash] = store_payload
        return sha1_hash

    def read_object(self, sha1_hash: str) -> Tuple[str, bytes]:
        """Membaca dan mem-parsing tipe serta konten objek dari CAS."""
        raw = self._storage.get(sha1_hash)
        if not raw:
            raise KeyError(f"Objek dengan hash {sha1_hash} tidak ditemukan!")
        null_idx = raw.index(b"\0")
        header = raw[:null_idx].decode("utf-8")
        obj_type, _ = header.split(" ")
        content = raw[null_idx + 1 :]
        return obj_type, content


class MiniGitVCS:
    """
    Engine kontrol versi minimalis yang mengelola:
    - Staging Area (Index)
    - Tree builder (Snapshot direktori frontend)
    - Directed Acyclic Graph (DAG) commit history
    - Branching & HEAD pointer manipulation
    """
    def __init__(self) -> None:
        self.cas = ContentAddressableStore()
        self.index: Dict[str, str] = {}          # path -> blob_sha1
        self.branches: Dict[str, str] = {}       # branch_name -> commit_sha1
        self.head_branch: str = "main"
        self.branches[self.head_branch] = ""
        self.commit_history: List[str] = []

    def stage_file(self, filepath: str, content: str) -> str:
        """
        Plumbing: git hash-object -w + git update-index
        Menyimpan file frontend (HTML/CSS/JS) sebagai Blob dan mendaftarkannya ke Index.
        """
        blob_sha = self.cas.write_object("blob", content.encode("utf-8"))
        self.index[filepath] = blob_sha
        return blob_sha

    def _write_tree(self) -> str:
        """
        Plumbing: git write-tree
        Membentuk Tree Object dari Staging Area yang mencatat struktur file frontend.
        """
        entries = []
        for path in sorted(self.index.keys()):
            sha = self.index[path]
            entries.append(f"100644 blob {sha}\t{path}")
        tree_content = "\n".join(entries).encode("utf-8")
        return self.cas.write_object("tree", tree_content)

    def commit(self, message: str, author: str = "Frontend Dev <dev@lab.local>") -> str:
        """
        Plumbing: git commit-tree
        Membuat commit node di DAG yang mengikat snapshot tree, parent commit, dan metadata.
        """
        if not self.index:
            raise ValueError("Staging area kosong. Tidak ada perubahan untuk di-commit!")

        tree_sha = self._write_tree()
        parent_sha = self.branches.get(self.head_branch, "")
        timestamp = int(time.time())

        commit_lines = [f"tree {tree_sha}"]
        if parent_sha:
            commit_lines.append(f"parent {parent_sha}")
        commit_lines.append(f"author {author} {timestamp} +0000")
        commit_lines.append(f"committer {author} {timestamp} +0000")
        commit_lines.append("")
        commit_lines.append(message)

        commit_content = "\n".join(commit_lines).encode("utf-8")
        commit_sha = self.cas.write_object("commit", commit_content)

        # Update pointer branch aktif
        self.branches[self.head_branch] = commit_sha
        self.commit_history.append(commit_sha)
        return commit_sha

    def create_branch(self, branch_name: str) -> None:
        """Membuat referensi branch baru yang menunjuk ke commit HEAD saat ini."""
        current_commit = self.branches[self.head_branch]
        self.branches[branch_name] = current_commit

    def switch_branch(self, branch_name: str) -> None:
        """Beralih ke branch lain dan memulihkan representasi state index."""
        if branch_name not in self.branches:
            raise ValueError(f"Branch '{branch_name}' tidak terdaftar!")
        self.head_branch = branch_name

    def get_commit_details(self, commit_sha: str) -> Dict[str, str]:
        """Membaca isi commit dari CAS dan mem-parsing metadata kuncinya."""
        _, content = self.cas.read_object(commit_sha)
        text = content.decode("utf-8")
        lines = text.split("\n")
        details = {"sha": commit_sha, "parent": "", "tree": "", "message": ""}
        for i, line in enumerate(lines):
            if line.startswith("tree "):
                details["tree"] = line.split(" ")[1]
            elif line.startswith("parent "):
                details["parent"] = line.split(" ")[1]
            elif line == "":
                details["message"] = "\n".join(lines[i + 1 :])
                break
        return details


def run_laboratory_exercise() -> None:
    """Eksekusi skenario lab frontend tooling dan kontrol versi Git."""
    print(f"{COLOR_BOLD}{COLOR_CYAN}=== LAB: FRONTEND TOOLING & GIT DAG INTERNALS ==={COLOR_RESET}\n")

    vcs = MiniGitVCS()

    # Skenario 1: Initial Scaffolding Project Frontend
    print(f"{COLOR_YELLOW}[Langkah 1: Scaffolding Vanilla Frontend]{COLOR_RESET}")
    pkg_json = '{\n  "name": "modern-app",\n  "version": "0.1.0",\n  "private": true\n}'
    index_html = '<!DOCTYPE html>\n<html><head><title>App</title></head><body><h1>Hello</h1></body></html>'
    style_css = "body { margin: 0; font-family: sans-serif; background: #fafafa; }"

    s_pkg = vcs.stage_file("package.json", pkg_json)
    s_htm = vcs.stage_file("index.html", index_html)
    s_css = vcs.stage_file("src/style.css", style_css)

    print(f" -> Blob package.json : {COLOR_MAGENTA}{s_pkg[:8]}...{COLOR_RESET}")
    print(f" -> Blob index.html   : {COLOR_MAGENTA}{s_htm[:8]}...{COLOR_RESET}")
    print(f" -> Blob src/style.css: {COLOR_MAGENTA}{s_css[:8]}...{COLOR_RESET}")

    c1 = vcs.commit("chore(scaffold): initial frontend structure")
    print(f"{COLOR_GREEN}✓ Commit 1 ({vcs.head_branch}): {c1[:8]} | Snapshot Tree tersimpan.{COLOR_RESET}\n")

    # Skenario 2: Migrasi ke Modern Bundler Tooling di Feature Branch
    print(f"{COLOR_YELLOW}[Langkah 2: Feature Branching (Vite + TypeScript Setup)]{COLOR_RESET}")
    vcs.create_branch("feature/modern-vite")
    vcs.switch_branch("feature/modern-vite")
    print(f" -> Active branch: {COLOR_BOLD}{vcs.head_branch}{COLOR_RESET}")

    vite_config = "import { defineConfig } from 'vite';\nexport default defineConfig({ server: { port: 3000 } });"
    app_ts = "const title: string = 'Vite Optimized App';\ndocument.querySelector('h1')!.textContent = title;"
    
    vcs.stage_file("vite.config.ts", vite_config)
    vcs.stage_file("src/main.ts", app_ts)
    c2 = vcs.commit("feat(tooling): implement Vite HMR and TypeScript compiler pipeline")
    print(f"{COLOR_GREEN}✓ Commit 2 ({vcs.head_branch}): {c2[:8]} | Tooling branch diperbarui.{COLOR_RESET}\n")

    # Skenario 3: Hotfix pada Branch Main
    print(f"{COLOR_YELLOW}[Langkah 3: Hotfix Isolasi pada Branch Main]{COLOR_RESET}")
    vcs.switch_branch("main")
    print(f" -> Active branch: {COLOR_BOLD}{vcs.head_branch}{COLOR_RESET}")

    hotfix_html = '<!DOCTYPE html>\n<html><head><meta charset="UTF-8"><title>App</title></head><body><h1>Hello</h1></body></html>'
    vcs.stage_file("index.html", hotfix_html)
    c3 = vcs.commit("fix(seo): inject explicit UTF-8 charset metadata")
    print(f"{COLOR_GREEN}✓ Commit 3 ({vcs.head_branch}): {c3[:8]} | Hotfix committed independently.{COLOR_RESET}\n")

    # Skenario 4: Visualisasi Log DAG (Directed Acyclic Graph)
    print(f"{COLOR_BOLD}{COLOR_CYAN}=== REPRESENTASI DAG COMMIT GRAPH ==={COLOR_RESET}")
    for commit_sha in reversed(vcs.commit_history):
        details = vcs.get_commit_details(commit_sha)
        parent_info = details['parent'][:8] if details['parent'] else "ROOT"
        
        # Identifikasi branch pointer
        branch_labels = [b for b, h in vcs.branches.items() if h == commit_sha]
        tag_str = f" {COLOR_YELLOW}<- ({', '.join(branch_labels)}){COLOR_RESET}" if branch_labels else ""

        print(f"Commit: {COLOR_GREEN}{details['sha'][:8]}{COLOR_RESET}{tag_str}")
        print(f"  Parent: {COLOR_MAGENTA}{parent_info}{COLOR_RESET}")
        print(f"  Tree  : {details['tree'][:8]}")
        print(f"  Msg   : {details['message']}")
        print("  |")
    print("  * End of commit history.\n")

    # Skenario 5: Verifikasi Content-Addressable Immutability
    print(f"{COLOR_BOLD}{COLOR_CYAN}=== VERIFIKASI INTEGRITAS CONTENT ADDRESSING ==={COLOR_RESET}")
    _, raw_content = vcs.cas.read_object(s_pkg)
    recalculated = hashlib.sha1(f"blob {len(raw_content)}\0".encode("utf-8") + raw_content).hexdigest()
    is_valid = (s_pkg == recalculated)
    print(f"Original Blob SHA  : {s_pkg}")
    print(f"Recalculated SHA   : {recalculated}")
    print(f"Status Integritas  : {'VALID' if is_valid else 'CORRUPTED'}")


if __name__ == "__main__":
    run_laboratory_exercise()
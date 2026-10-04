#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Distributed Architectures & Remote Collaboration di Git
BAB-05: Remote Collaboration dan Distributed Architectures

Skrip ini menyediakan simulasi interaktif berbasis terminal (CLI) untuk memahami
secara visual bagaimana Git mengelola remote tracking references, network sync
(fetch, pull, push), handling non-fast-forward rejections, serta model Fork & Upstream.
"""

import sys
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ANSI Color Codes untuk visualisasi terminal
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"
    GRAY = "\033[90m"
    WHITE = "\033[97m"

def print_banner():
    banner = f"""
{Colors.CYAN}{Colors.BOLD}================================================================================{Colors.RESET}
{Colors.WHITE}{Colors.BOLD}   GIT DISTRIBUTED ARCHITECTURE & REMOTE COLLABORATION SIMULATOR{Colors.RESET}
{Colors.MAGENTA}   Bab 05: Remote-Tracking Branches, Refspecs, Sync & Distributed Topologies{Colors.RESET}
{Colors.CYAN}{Colors.BOLD}================================================================================{Colors.RESET}
"""
    print(banner)

@dataclass
class Commit:
    hash_val: str
    message: str
    parent: Optional[str] = None

@dataclass
class GitRepoState:
    name: str
    commits: Dict[str, Commit] = field(default_factory=dict)
    branches: Dict[str, str] = field(default_factory=dict) # branch_name -> commit_hash
    remotes: Dict[str, str] = field(default_factory=dict)  # remote_name -> url
    remote_tracking: Dict[str, str] = field(default_factory=dict) # 'origin/main' -> commit_hash
    head: str = "main"

def init_simulator_state() -> Dict[str, GitRepoState]:
    """Menginisialisasi repositori: Upstream, Origin (Fork/Central), dan Local Developer."""
    # Commit awal
    c1 = Commit("a1b2c3d", "Initial commit: scaffold base project", None)
    c2 = Commit("e4f5g6h", "feat: add user authentication interface", "a1b2c3d")

    # Upstream (Official repo)
    upstream = GitRepoState(
        name="upstream (Organization Repo)",
        commits={"a1b2c3d": c1, "e4f5g6h": c2},
        branches={"main": "e4f5g6h"},
        remotes={}
    )

    # Origin (Personal Fork / Central Bare)
    origin = GitRepoState(
        name="origin (Remote Server / GitHub)",
        commits={"a1b2c3d": c1, "e4f5g6h": c2},
        branches={"main": "e4f5g6h"},
        remotes={"upstream": "git@github.com:core-team/app.git"}
    )

    # Local Workspace Developer
    local = GitRepoState(
        name="local (Developer Workstation)",
        commits={"a1b2c3d": c1, "e4f5g6h": c2},
        branches={"main": "e4f5g6h"},
        remotes={
            "origin": "git@github.com:developer/app.git",
            "upstream": "git@github.com:core-team/app.git"
        },
        remote_tracking={
            "origin/main": "e4f5g6h",
            "upstream/main": "e4f5g6h"
        },
        head="main"
    )

    return {"upstream": upstream, "origin": origin, "local": local}

def render_status(states: Dict[str, GitRepoState]):
    local = states["local"]
    origin = states["origin"]
    upstream = states["upstream"]

    print(f"\n{Colors.YELLOW}{Colors.BOLD}--- [STATUS REPOSITORI DISTRIBUSI] ---{Colors.RESET}")
    print(f"{Colors.BLUE}[1] Local Workspace:{Colors.RESET}")
    print(f"    HEAD -> {Colors.GREEN}{local.head}{Colors.RESET} ({local.branches.get(local.head, 'empty')})")
    print(f"    Remote Tracking Refs: {Colors.GRAY}.git/refs/remotes/{Colors.RESET}")
    for ref, h in local.remote_tracking.items():
        print(f"      * {ref} -> {h}")

    print(f"{Colors.MAGENTA}[2] Remote Server (origin):{Colors.RESET}")
    print(f"    refs/heads/main -> {origin.branches.get('main')}")

    print(f"{Colors.CYAN}[3] Upstream Organization:{Colors.RESET}")
    print(f"    refs/heads/main -> {upstream.branches.get('main')}")
    print(f"{Colors.YELLOW}--------------------------------------{Colors.RESET}\n")

def simulate_inspect_remotes(states: Dict[str, GitRepoState]):
    local = states["local"]
    print(f"\n{Colors.BOLD}>>> Menjalankan: git remote -v & analisa Refspec{Colors.RESET}")
    time.sleep(0.3)
    for r_name, r_url in local.remotes.items():
        print(f"{Colors.CYAN}{r_name}\t{r_url} (fetch){Colors.RESET}")
        print(f"{Colors.CYAN}{r_name}\t{r_url} (push){Colors.RESET}")
    
    print(f"\n{Colors.WHITE}{Colors.BOLD}[Konsep Arsitektur Inti]:{Colors.RESET}")
    print(f"1. Remote bukan koneksi live/socket yang terus terhubung, melainkan {Colors.GREEN}metadata bookmark URL{Colors.RESET}.")
    print(f"2. Konfigurasi refspec standar di .git/config:")
    print(f"   {Colors.YELLOW}+refs/heads/*:refs/remotes/origin/*{Colors.RESET}")
    print(f"   Tanda '+' berarti force update referensi tracking lokal saat git fetch.")
    print(f"3. Remote tracking branch ({Colors.MAGENTA}origin/main{Colors.RESET}) berada di storage lokal pengembang")
    print(f"   sebagai 'foto snapshot terakhir' dari remote.")

def simulate_local_and_remote_divergence(states: Dict[str, GitRepoState]):
    local = states["local"]
    origin = states["origin"]

    print(f"\n{Colors.BOLD}>>> Simulasi: Perubahan Paralel (Divergence){Colors.RESET}")
    # Rekan tim push commit baru ke origin
    c_remote = Commit("7a8b9c0", "feat(api): endpoint authentication token", "e4f5g6h")
    origin.commits["7a8b9c0"] = c_remote
    origin.branches["main"] = "7a8b9c0"
    print(f"{Colors.MAGENTA}[Remote origin]{Colors.RESET} Rekan tim mem-push commit {Colors.YELLOW}7a8b9c0{Colors.RESET} ke main.")

    # Developer membuat commit lokal baru
    c_local = Commit("1d2e3f4", "fix(client): handle null token exception", "e4f5g6h")
    local.commits["1d2e3f4"] = c_local
    local.branches["main"] = "1d2e3f4"
    print(f"{Colors.BLUE}[Local Workspace]{Colors.RESET} Anda membuat commit lokal {Colors.GREEN}1d2e3f4{Colors.RESET} pada main.")

    print(f"\n{Colors.RED}{Colors.BOLD}[Kondisi Divergen]:{Colors.RESET}")
    print(f"Local main dan origin main memiliki parent sama ({Colors.YELLOW}e4f5g6h{Colors.RESET}),")
    print(f"namun riwayat sejarahnya telah bercabang dua (diverged)!")

def simulate_git_fetch(states: Dict[str, GitRepoState]):
    local = states["local"]
    origin = states["origin"]

    print(f"\n{Colors.BOLD}>>> Menjalankan: git fetch origin{Colors.RESET}")
    time.sleep(0.4)
    remote_head = origin.branches["main"]
    
    # Ambil commit dari origin ke database lokal
    for chash, cobj in origin.commits.items():
        if chash not in local.commits:
            local.commits[chash] = cobj
            print(f"Receiving objects: commit {chash} ({cobj.message})")

    # Update remote tracking branch SAJA, bukan working tree / local main
    local.remote_tracking["origin/main"] = remote_head
    print(f"{Colors.GREEN}From git@github.com:developer/app.git{Colors.RESET}")
    print(f"   e4f5g6h..{remote_head}  main -> origin/main")
    
    print(f"\n{Colors.WHITE}{Colors.BOLD}[Pembedahan Konsep]:{Colors.RESET}")
    print(f"* 'git fetch' aman dijalankan kapan saja karena {Colors.GREEN}TIDAK PERNAH{Colors.RESET} menyentuh Working Tree atau file kerja Anda.")
    print(f"* Local 'main' masih di commit: {Colors.YELLOW}{local.branches['main']}{Colors.RESET}")
    print(f"* 'origin/main' sekarang diperbarui ke: {Colors.MAGENTA}{local.remote_tracking['origin/main']}{Colors.RESET}")

def simulate_push_collision_and_lease(states: Dict[str, GitRepoState]):
    local = states["local"]
    origin = states["origin"]

    print(f"\n{Colors.BOLD}>>> Simulasi: Mencoba 'git push origin main' saat divergen{Colors.RESET}")
    time.sleep(0.4)
    if local.branches["main"] != origin.branches["main"]:
        print(f"{Colors.RED}To git@github.com:developer/app.git{Colors.RESET}")
        print(f"{Colors.RED} ! [rejected]        main -> main (non-fast-forward){Colors.RESET}")
        print(f"{Colors.YELLOW}error: failed to push some refs to 'git@github.com:developer/app.git'")
        print("hint: Updates were rejected because the remote contains work that you do")
        print("hint: not have locally. Integrate the remote changes (e.g. 'git pull ...')")
        print(f"hint: before pushing again.{Colors.RESET}")

        print(f"\n{Colors.CYAN}[Keamanan: Mengapa Git menolak?]{Colors.RESET}")
        print("Jika Git menerima push ini secara buta, commit rekan Anda (7a8b9c0) akan terhapus dari HEAD remote.")
        print(f"\n{Colors.YELLOW}[Bahaya 'git push --force' vs Solusi Modern '--force-with-lease']:{Colors.RESET}")
        print(f" - {Colors.RED}--force:{Colors.RESET} Menimpa paksa remote tanpa peduli apakah ada rekan yang baru saja push.")
        print(f" - {Colors.GREEN}--force-with-lease:{Colors.RESET} Memeriksa apakah commit remote cocok dengan 'origin/main' lokal kita.")
        print("   Jika ada commit baru yang belum kita fetch, push tetap DIBATALKAN demi proteksi.")

def simulate_rebase_sync(states: Dict[str, GitRepoState]):
    local = states["local"]
    print(f"\n{Colors.BOLD}>>> Menjalankan: git pull --rebase origin main{Colors.RESET}")
    print(f"{Colors.GRAY}Langkah 1: Menyimpan commit lokal Anda (1d2e3f4) sementara ke stash / commit pool{Colors.RESET}")
    print(f"{Colors.GRAY}Langkah 2: Memajukan local main ke commit remote origin/main (7a8b9c0){Colors.RESET}")
    print(f"{Colors.GRAY}Langkah 3: Meng-apply ulang commit lokal Anda di atas commit terbaru{Colors.RESET}")
    time.sleep(0.5)

    # Rebased commit menghasilkan commit hash baru karena parent hash berubah!
    new_hash = "9f8e7d6"
    rebased_commit = Commit(new_hash, "fix(client): handle null token exception", parent="7a8b9c0")
    local.commits[new_hash] = rebased_commit
    local.branches["main"] = new_hash

    print(f"{Colors.GREEN}Successfully rebased and updated refs/heads/main.{Colors.RESET}")
    print(f"HEAD sekarang berada di commit baru: {Colors.CYAN}{new_hash}{Colors.RESET}")
    print(f"\n{Colors.WHITE}{Colors.BOLD}[Arsitektur DAG Riwayat]:{Colors.RESET}")
    print(f"  (e4f5g6h) ---> (7a8b9c0 [origin/main]) ---> ({new_hash} [main, HEAD])")
    print(f"{Colors.GREEN}Riwayat linier bersih tanpa commit merge tambahan ('merge bubble').{Colors.RESET}")

def simulate_upstream_fork_sync(states: Dict[str, GitRepoState]):
    local = states["local"]
    upstream = states["upstream"]
    origin = states["origin"]

    print(f"\n{Colors.BOLD}>>> Simulasi: Upstream Synchronization (Model Forking GitHub){Colors.RESET}")
    # Upstream merilis patch resmi
    c_up = Commit("33aabb4", "chore(release): security patch v1.0.1", "e4f5g6h")
    upstream.commits["33aabb4"] = c_up
    upstream.branches["main"] = "33aabb4"
    print(f"{Colors.CYAN}[Upstream Organization]{Colors.RESET} Rilis security patch: commit {Colors.YELLOW}33aabb4{Colors.RESET}")

    print(f"\nPerintah sinkronisasi standar:")
    print(f"  1. {Colors.WHITE}git fetch upstream{Colors.RESET}")
    local.commits["33aabb4"] = c_up
    local.remote_tracking["upstream/main"] = "33aabb4"
    print(f"     -> Memperbarui upstream/main ke 33aabb4")

    print(f"  2. {Colors.WHITE}git merge upstream/main (atau git rebase upstream/main){Colors.RESET}")
    print(f"  3. {Colors.WHITE}git push origin main{Colors.RESET}")
    origin.commits["33aabb4"] = c_up
    origin.branches["main"] = "33aabb4"
    local.remote_tracking["origin/main"] = "33aabb4"
    print(f"     -> Fork personal Anda di GitHub (origin) kini sinkron dengan Upstream!")

def print_menu():
    print(f"\n{Colors.WHITE}{Colors.BOLD}PILIH SKENARIO SIMULASI:{Colors.RESET}")
    print(f" {Colors.GREEN}1.{Colors.RESET} Cek status topologi repositori & tracking branch")
    print(f" {Colors.GREEN}2.{Colors.RESET} Analisa Remote Metadata & Refspec (+refs/heads/*...)")
    print(f" {Colors.GREEN}3.{Colors.RESET} Simulasikan Divergence (Perubahan paralel Lokal vs Remote)")
    print(f" {Colors.GREEN}4.{Colors.RESET} Jalankan 'git fetch' & amati pemisahan HEAD vs Tracking Ref")
    print(f" {Colors.GREEN}5.{Colors.RESET} Uji Proteksi Collision & Keamanan '--force-with-lease'")
    print(f" {Colors.GREEN}6.{Colors.RESET} Jalankan 'git pull --rebase' untuk rekonsiliasi linier")
    print(f" {Colors.GREEN}7.{Colors.RESET} Alur Sinkronisasi Fork & Upstream (Triangular Workflow)")
    print(f" {Colors.GREEN}8.{Colors.RESET} Keluar (Exit)")

def main():
    print_banner()
    states = init_simulator_state()

    # Mode otomatis jika argumen --auto / non-interaktif
    if len(sys.argv) > 1 and sys.argv[1] in ("--auto", "-a", "--test"):
        print(f"{Colors.YELLOW}[Mode Automasi]: Menjalankan seluruh pengujian skenario...{Colors.RESET}")
        render_status(states)
        simulate_inspect_remotes(states)
        simulate_local_and_remote_divergence(states)
        simulate_git_fetch(states)
        simulate_push_collision_and_lease(states)
        simulate_rebase_sync(states)
        simulate_upstream_fork_sync(states)
        render_status(states)
        print(f"\n{Colors.GREEN}{Colors.BOLD}[OK] Seluruh simulasi BAB-05 selesai divalidasi dengan sukses!{Colors.RESET}")
        return

    # Loop interaktif CLI
    while True:
        print_menu()
        try:
            choice = input(f"\n{Colors.BOLD}Masukkan pilihan (1-8): {Colors.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.YELLOW}Keluar dari simulasi.{Colors.RESET}")
            break

        if choice == "1":
            render_status(states)
        elif choice == "2":
            simulate_inspect_remotes(states)
        elif choice == "3":
            simulate_local_and_remote_divergence(states)
        elif choice == "4":
            simulate_git_fetch(states)
        elif choice == "5":
            simulate_push_collision_and_lease(states)
        elif choice == "6":
            simulate_rebase_sync(states)
        elif choice == "7":
            simulate_upstream_fork_sync(states)
        elif choice == "8" or choice.lower() == "q":
            print(f"\n{Colors.GREEN}Terima kasih telah mempelajari arsitektur kolaborasi Git!{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid, silakan masukkan angka 1-8.{Colors.RESET}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Lab Exercise: BAB-04 History Rewriting, Recovery, dan Auditing
Simulasi CLI interaktif konsep:
- Commit Amending & Hash Immutability
- Soft, Mixed, dan Hard Reset
- Git Reflog & Dangling Commit Recovery
- Interactive Rebase (Squash, Reword, Drop)
- Git Bisect (Binary Search Bug Finding)
- Git Blame & History Audit
"""

import sys
import time
import hashlib
from typing import Dict, List, Optional

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"


class SimulatedCommit:
    def __init__(self, message: str, parent: Optional[str] = None, author: str = "Dev <dev@example.com>", content: str = ""):
        self.message = message
        self.parent = parent
        self.author = author
        self.timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.content = content
        raw = f"{message}|{parent}|{author}|{self.timestamp}|{content}"
        self.sha = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:7]


class GitAuditingSimulator:
    def __init__(self):
        self.commits: Dict[str, SimulatedCommit] = {}
        self.reflog: List[dict] = []
        self.head: Optional[str] = None
        self.branch: str = "main"
        self._init_repository()

    def _log_reflog(self, action: str, target_sha: Optional[str]):
        entry = {
            "index": len(self.reflog),
            "sha": target_sha,
            "action": action,
            "timestamp": time.strftime("%H:%M:%S")
        }
        self.reflog.append(entry)

    def _init_repository(self):
        c1 = SimulatedCommit("Initial commit: repo setup", parent=None, content="print('hello')")
        self.commits[c1.sha] = c1
        self.head = c1.sha
        self._log_reflog("commit (initial): Initial commit: repo setup", c1.sha)

        c2 = SimulatedCommit("feat: add core payment processing", parent=c1.sha, content="def pay(): return True")
        self.commits[c2.sha] = c2
        self.head = c2.sha
        self._log_reflog("commit: feat: add core payment processing", c2.sha)

        c3 = SimulatedCommit("fix: typo in payment handler", parent=c2.sha, content="def pay(): return True # typo fixed")
        self.commits[c3.sha] = c3
        self.head = c3.sha
        self._log_reflog("commit: fix: typo in payment handler", c3.sha)

    def show_header(self, title: str):
        print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
        print(f"{BOLD}{WHITE}{title.center(65)}{RESET}")
        print(f"{BOLD}{CYAN}{'=' * 65}{RESET}\n")

    def show_graph(self):
        self.show_header("CURRENT COMMIT GRAPH & HEAD")
        current = self.head
        chain = []
        while current:
            c = self.commits.get(current)
            if not c:
                break
            chain.append(c)
            current = c.parent

        print(f"HEAD pointer -> {BOLD}{GREEN}{self.branch}{RESET} ({self.head})")
        print("-" * 65)
        for i, c in enumerate(chain):
            is_tip = " (HEAD)" if i == 0 else ""
            print(f"  * {BOLD}{YELLOW}{c.sha}{RESET}{is_tip} {c.message} {DIM}[{c.timestamp}]{RESET}")
            if c.parent:
                print(f"  |")
        print()

    def show_reflog(self):
        self.show_header("GIT REFLOG (HEAD history tracker)")
        print(f"{BOLD}{'INDEX':<10} {'TARGET SHA':<12} {'ACTION':<40}{RESET}")
        print("-" * 65)
        for entry in reversed(self.reflog):
            sha_str = entry['sha'] if entry['sha'] else "null"
            print(f"HEAD@{{{entry['index']}}}    {YELLOW}{sha_str:<12}{RESET} {entry['action']}")
        print()

    def demonstrate_amend(self):
        self.show_header("1. REWRITE: git commit --amend")
        old_tip = self.commits[self.head]
        print(f"Current Tip SHA  : {RED}{old_tip.sha}{RESET} -> '{old_tip.message}'")
        print(f"{DIM}Memperbaiki commit pesan tanpa menambah commit baru di atasnya...{RESET}")
        
        # Amending generates a completely new SHA-1 because commit objects are immutable
        new_commit = SimulatedCommit(
            "fix(payment): correctly handle edge cases and typos",
            parent=old_tip.parent,
            content=old_tip.content + " # amended"
        )
        self.commits[new_commit.sha] = new_commit
        self.head = new_commit.sha
        self._log_reflog("commit (amend): fix(payment): correctly handle edge cases and typos", new_commit.sha)

        print(f"New Tip SHA      : {GREEN}{new_commit.sha}{RESET} -> '{new_commit.message}'")
        print(f"{YELLOW}Perhatikan:{RESET} SHA berganti dari {RED}{old_tip.sha}{RESET} ke {GREEN}{new_commit.sha}{RESET}.")
        print(f"Commit lama ({old_tip.sha}) kini berstatus {BOLD}{RED}DANGLING / ORPHAN{RESET}, tapi tersimpan di reflog!\n")

    def demonstrate_reset_and_recovery(self):
        self.show_header("2. RECOVERY: git reset --hard & git reflog recovery")
        target_parent = self.commits[self.head].parent
        old_head = self.head

        print(f"Simulasi bencana: User tidak sengaja menjalankan {BOLD}{RED}git reset --hard HEAD~1{RESET}")
        self.head = target_parent
        self._log_reflog(f"reset: moving to HEAD~1 ({target_parent})", self.head)

        print(f"HEAD sekarang mundur ke: {YELLOW}{self.head}{RESET}")
        print(f"Commit {RED}{old_head}{RESET} hilang dari 'git log' biasa!")

        print(f"\n{BOLD}{GREEN}Langkah Penyelamatan:{RESET}")
        print(f"1. Periksa `git reflog` mencari SHA commit yang hilang ({old_head}).")
        print(f"2. Eksekusi `git reset --hard {old_head}` atau buat cabang recovery.")

        # Recovery
        print(f"\nMenjalankan: {BOLD}{CYAN}git reset --hard {old_head}{RESET}")
        self.head = old_head
        self._log_reflog(f"reset: moving to {old_head} (RECOVERY)", self.head)
        print(f"{GREEN}✓ Berhasil!{RESET} HEAD berhasil dikembalikan ke: {YELLOW}{self.head}{RESET}\n")

    def demonstrate_interactive_rebase(self):
        self.show_header("3. SQUASH & REWORD: git rebase -i")
        print("Skenario 3 commit eksperimen:")
        c_a = SimulatedCommit("wip: start feature foo", parent=self.head)
        c_b = SimulatedCommit("wip: fix typo foo", parent=c_a.sha)
        c_c = SimulatedCommit("wip: finish feature foo", parent=c_b.sha)
        for c in [c_a, c_b, c_c]:
            self.commits[c.sha] = c
            self.head = c.sha
            self._log_reflog(f"commit: {c.message}", c.sha)

        print(f"  * {c_a.sha} - {c_a.message}")
        print(f"  * {c_b.sha} - {c_b.message}")
        print(f"  * {c_c.sha} - {c_c.message}")

        print(f"\nMenjalankan Interactive Rebase squashing 3 commit menjadi 1:")
        squashed = SimulatedCommit(
            "feat(foo): implement complete feature foo with tests",
            parent=c_a.parent,
            content="full feature content"
        )
        self.commits[squashed.sha] = squashed
        self.head = squashed.sha
        self._log_reflog("rebase -i (finish): returning to refs/heads/main", squashed.sha)

        print(f"{GREEN}✓ Rebase selesai!{RESET} Menghasilkan clean atomic commit: {YELLOW}{squashed.sha}{RESET}")
        print(f"Pesan bersih: '{squashed.message}'\n")

    def demonstrate_bisect(self):
        self.show_header("4. AUDITING: git bisect (Binary Search Bug Hunting)")
        # Buat sequence 7 commit, bug muncul di commit ke-4
        history = []
        curr = self.head
        for i in range(1, 8):
            has_bug = (i >= 4)
            msg = f"build v1.{i}: {'[BUG INTRODUCED]' if i == 4 else 'regular updates'}"
            cmt = SimulatedCommit(msg, parent=curr, content=f"state_v{i}_bug={has_bug}")
            cmt.has_bug = has_bug
            self.commits[cmt.sha] = cmt
            curr = cmt.sha
            history.append(cmt)

        self.head = curr
        print(f"Riwayat versi v1.1 sampai v1.7 ({len(history)} commits).")
        print(f"Mencari commit pertama yang memperkenalkan regression bug...\n")

        low = 0
        high = len(history) - 1
        bad_sha = history[high].sha
        good_sha = history[0].sha

        print(f"{CYAN}$ git bisect start{RESET}")
        print(f"{CYAN}$ git bisect bad {bad_sha}{RESET}")
        print(f"{CYAN}$ git bisect good {good_sha}{RESET}")

        steps = 1
        culprit = None
        while low <= high:
            mid = (low + high) // 2
            test_cmt = history[mid]
            print(f"\n[Step {steps}] Bisecting: {YELLOW}{len(history[low:high+1])}{RESET} revisions left (~{round((high-low).bit_length())} steps)")
            print(f"Testing commit {YELLOW}{test_cmt.sha}{RESET}: '{test_cmt.message}'")
            
            if getattr(test_cmt, 'has_bug', False):
                print(f"  -> Result: {RED}BAD{RESET} (bug terdeteksi)")
                culprit = test_cmt
                high = mid - 1
            else:
                print(f"  -> Result: {GREEN}GOOD{RESET} (bersih)")
                low = mid + 1
            steps += 1

        print(f"\n{BOLD}{GREEN}✓ Bisect Selesai!{RESET}")
        print(f"Culprit pertama kali ditemukan pada: {BOLD}{RED}{culprit.sha}{RESET}")
        print(f"Commit message: {BOLD}{WHITE}{culprit.message}{RESET}\n")

    def demonstrate_blame(self):
        self.show_header("5. AUDITING: git blame line-by-line inspection")
        code_lines = [
            ("a3f120c", "Alice", "2026-03-01", "import os"),
            ("b59e210", "Bob  ", "2026-03-02", "DATABASE_URL = os.getenv('DB_URI')"),
            ("c71d98a", "Alice", "2026-03-03", "def connect():"),
            ("d8820f4", "Eve  ", "2026-03-04", "    return db.connect(DATABASE_URL, timeout=10) # audited change"),
        ]
        print(f"{BOLD}{'COMMIT':<10} {'AUTHOR':<10} {'DATE':<12} {'LINE CONTENT'}{RESET}")
        print("-" * 65)
        for sha, author, dt, line in code_lines:
            print(f"{YELLOW}{sha:<10}{RESET} {CYAN}{author:<10}{RESET} {DIM}{dt:<12}{RESET} {line}")
        print(f"\n{DIM}Tip: Gunakan `git log -S <string>` (pickaxe) untuk mencari commit yang mengubah frekuensi string tertentu.{RESET}\n")


def interactive_menu():
    sim = GitAuditingSimulator()
    while True:
        print(f"{BOLD}{BG_BLUE}  LAB EXERCISE: BAB-04 HISTORY REWRITING & RECOVERY  {RESET}")
        print(f"1. Tampilkan Visual Graph & HEAD")
        print(f"2. Tampilkan `git reflog`")
        print(f"3. Jalankan `git commit --amend` (Hash immutability)")
        print(f"4. Jalankan Bencana `git reset --hard` & Recovery via Reflog")
        print(f"5. Jalankan `git rebase -i` (Squashing history)")
        print(f"6. Jalankan `git bisect` (Automated binary audit)")
        print(f"7. Jalankan `git blame` (Line auditing)")
        print(f"8. Jalankan Semua Skenario Berurutan (Demo Otomatis)")
        print(f"0. Keluar")
        
        choice = input(f"\n{BOLD}{CYAN}Pilih opsi [0-8]: {RESET}").strip()
        if choice == "1":
            sim.show_graph()
        elif choice == "2":
            sim.show_reflog()
        elif choice == "3":
            sim.demonstrate_amend()
        elif choice == "4":
            sim.demonstrate_reset_and_recovery()
        elif choice == "5":
            sim.demonstrate_interactive_rebase()
        elif choice == "6":
            sim.demonstrate_bisect()
        elif choice == "7":
            sim.demonstrate_blame()
        elif choice == "8":
            sim.show_graph()
            sim.demonstrate_amend()
            sim.demonstrate_reset_and_recovery()
            sim.demonstrate_interactive_rebase()
            sim.demonstrate_bisect()
            sim.demonstrate_blame()
            sim.show_reflog()
            print(f"{BOLD}{GREEN}✓ Seluruh skenario lab telah dieksekusi dengan sukses!{RESET}\n")
            break
        elif choice == "0":
            print(f"{GREEN}Lab selesai. Sampai jumpa!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid, coba lagi.{RESET}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        # Mode non-interaktif untuk CI/CD atau test harness
        sim = GitAuditingSimulator()
        sim.show_graph()
        sim.demonstrate_amend()
        sim.demonstrate_reset_and_recovery()
        sim.demonstrate_interactive_rebase()
        sim.demonstrate_bisect()
        sim.demonstrate_blame()
        sim.show_reflog()
        sys.exit(0)
    else:
        try:
            interactive_menu()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Lab dihentikan pengguna.{RESET}")
            sys.exit(0)

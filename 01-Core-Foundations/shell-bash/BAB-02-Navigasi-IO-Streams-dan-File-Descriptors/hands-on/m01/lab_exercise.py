#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Interaktif Navigasi, I/O Streams, dan File Descriptors (FD)
Topik: BAB-02 - Navigasi, I/O Streams, dan File Descriptors
Python 3 Runnable Mandiri - Tanpa Dependensi Eksternal
"""

import sys
import os
import time
from typing import Dict, List, Optional, Tuple

# ==============================================================================
# ANSI Color Palette untuk Visualisasi Terminal
# ==============================================================================
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Foreground
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    
    # Background
    BG_DARK = "\033[40m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"


def banner(title: str) -> None:
    line = "=" * 68
    print(f"\n{Color.CYAN}{line}")
    print(f" {Color.BOLD}{Color.WHITE}{title.center(66)}{Color.RESET}{Color.CYAN}")
    print(f"{line}{Color.RESET}\n")


def section(title: str) -> None:
    print(f"\n{Color.YELLOW}{Color.BOLD}>>> {title}{Color.RESET}")


# ==============================================================================
# 1. Virtual File System & Path Resolution Engine
# ==============================================================================
class VirtualFileSystem:
    """Simulasi hierarki direktori UNIX (inode, absolute & relative path)."""
    
    def __init__(self) -> None:
        self.tree: Dict[str, dict] = {
            "/": {"type": "dir", "inode": 2, "children": ["etc", "home", "var", "dev"]},
            "/etc": {"type": "dir", "inode": 101, "children": ["passwd", "hosts"]},
            "/etc/passwd": {"type": "file", "inode": 102, "size": 1240, "content": "root:x:0:0:root:/root:/bin/bash\nuser:x:1000:1000:user:/home/user:/bin/bash"},
            "/etc/hosts": {"type": "file", "inode": 103, "size": 158, "content": "127.0.0.1 localhost\n::1 localhost"},
            "/home": {"type": "dir", "inode": 201, "children": ["student"]},
            "/home/student": {"type": "dir", "inode": 202, "children": ["docs", "notes.txt"]},
            "/home/student/docs": {"type": "dir", "inode": 203, "children": ["project.md"]},
            "/home/student/docs/project.md": {"type": "file", "inode": 204, "size": 512, "content": "# Architecture Roadmap\nI/O streams foundation."},
            "/home/student/notes.txt": {"type": "file", "inode": 205, "size": 64, "content": "Belajar File Descriptors: 0=stdin, 1=stdout, 2=stderr"},
            "/var": {"type": "dir", "inode": 301, "children": ["log"]},
            "/var/log": {"type": "dir", "inode": 302, "children": ["syslog"]},
            "/var/log/syslog": {"type": "file", "inode": 303, "size": 4096, "content": "[INFO] System booted cleanly.\n[WARN] High memory usage.\n[ERROR] Connection refused on port 8080."},
            "/dev": {"type": "dir", "inode": 401, "children": ["null", "zero", "stdin", "stdout", "stderr"]},
            "/dev/null": {"type": "special", "inode": 402, "content": "Bit-bucket / Black hole"},
            "/dev/stdin": {"type": "symlink", "inode": 403, "target": "/proc/self/fd/0"},
            "/dev/stdout": {"type": "symlink", "inode": 404, "target": "/proc/self/fd/1"},
            "/dev/stderr": {"type": "symlink", "inode": 405, "target": "/proc/self/fd/2"},
        }
        self.cwd: str = "/home/student"

    def canonicalize(self, path: str) -> str:
        """Menyelesaikan path absolut vs relatif, '.', dan '..' ala POSIX."""
        if not path.startswith("/"):
            combined = f"{self.cwd}/{path}"
        else:
            combined = path

        parts = combined.split("/")
        resolved: List[str] = []
        for part in parts:
            if not part or part == ".":
                continue
            elif part == "..":
                if resolved:
                    resolved.pop()
            else:
                resolved.append(part)
        return "/" + "/".join(resolved)

    def change_directory(self, target: str) -> Tuple[bool, str]:
        resolved = self.canonicalize(target)
        if resolved not in self.tree:
            return False, f"bash: cd: {target}: No such file or directory"
        if self.tree[resolved]["type"] != "dir":
            return False, f"bash: cd: {target}: Not a directory"
        self.cwd = resolved
        return True, f"Berpindah ke: {self.cwd}"

    def list_dir(self, target: Optional[str] = None) -> List[Tuple[str, str, int]]:
        path = self.canonicalize(target) if target else self.cwd
        if path not in self.tree or self.tree[path]["type"] != "dir":
            return []
        results = []
        for child_name in self.tree[path].get("children", []):
            child_path = f"{path.rstrip('/')}/{child_name}"
            node = self.tree.get(child_path, {})
            results.append((child_name, node.get("type", "unknown"), node.get("inode", 0)))
        return results


# ==============================================================================
# 2. File Descriptors & I/O Redirection Engine
# ==============================================================================
class ProcessFileDescriptorTable:
    """Simulasi Process Table File Descriptors (0, 1, 2, 3+) di Linux Kernel."""
    
    def __init__(self, pid: int = 1337) -> None:
        self.pid = pid
        # FD Table: Mapping integer fd -> target device/file
        self.table: Dict[int, Dict[str, str]] = {
            0: {"name": "stdin", "target": "/dev/pts/0 (Keyboard)", "mode": "r", "flags": "O_RDONLY"},
            1: {"name": "stdout", "target": "/dev/pts/0 (Terminal Screen)", "mode": "w", "flags": "O_WRONLY|O_CREAT"},
            2: {"name": "stderr", "target": "/dev/pts/0 (Terminal Screen)", "mode": "w", "flags": "O_WRONLY|O_CREAT"},
        }
        self.next_fd = 3

    def display(self) -> None:
        print(f"{Color.CYAN}┌─────┬──────────┬────────┬───────────────────────────────┬──────────────────────┐")
        print(f"│ {Color.BOLD}FD{Color.RESET}{Color.CYAN}  │ {Color.BOLD}Name{Color.RESET}{Color.CYAN}     │ {Color.BOLD}Mode{Color.RESET}{Color.CYAN}   │ {Color.BOLD}Target (vnode / file){Color.RESET}{Color.CYAN}         │ {Color.BOLD}POSIX Flags{Color.RESET}{Color.CYAN}          │")
        print(f"├─────┼──────────┼────────┼───────────────────────────────┼──────────────────────┤{Color.RESET}")
        for fd in sorted(self.table.keys()):
            entry = self.table[fd]
            fd_color = Color.GREEN if fd == 1 else (Color.RED if fd == 2 else (Color.BLUE if fd == 0 else Color.MAGENTA))
            print(f"│ {fd_color}{fd:<3}{Color.RESET} │ {entry['name']:<8} │ {entry['mode']:<6} │ {entry['target']:<29} │ {entry['flags']:<20} │")
        print(f"{Color.CYAN}└─────┴──────────┴────────┴───────────────────────────────┴──────────────────────┘{Color.RESET}")

    def redirect(self, fd: int, target: str, mode: str = "w", flags: str = "O_WRONLY") -> None:
        self.table[fd] = {
            "name": f"custom_{fd}" if fd >= 3 else ("stdin" if fd == 0 else ("stdout" if fd == 1 else "stderr")),
            "target": target,
            "mode": mode,
            "flags": flags
        }

    def duplicate(self, old_fd: int, new_fd: int) -> bool:
        """Simulasi dup2(old_fd, new_fd) - analogi untuk '2>&1'."""
        if old_fd not in self.table:
            return False
        self.table[new_fd] = dict(self.table[old_fd])
        self.table[new_fd]["flags"] += f" [dup of FD {old_fd}]"
        return True


# ==============================================================================
# 3. Stream Dispatcher & Pipeline Simulation
# ==============================================================================
class CommandExecutionSimulator:
    """Mengeksekusi simulasi perintah Bash dan memecah output ke FD 1 dan FD 2."""
    
    @staticmethod
    def run_mock_command(cmd: str, vfs: VirtualFileSystem) -> Tuple[List[str], List[str]]:
        """Mengembalikan tuple (stdout_lines, stderr_lines)."""
        stdout_buf: List[str] = []
        stderr_buf: List[str] = []
        parts = cmd.strip().split()
        if not parts:
            return stdout_buf, stderr_buf
        
        op = parts[0]
        args = parts[1:]
        
        if op == "pwd":
            stdout_buf.append(vfs.cwd)
        elif op == "ls":
            target = args[0] if args else vfs.cwd
            resolved = vfs.canonicalize(target)
            if resolved in vfs.tree and vfs.tree[resolved]["type"] == "dir":
                items = [name for name in vfs.tree[resolved].get("children", [])]
                stdout_buf.append("  ".join(items))
            else:
                stderr_buf.append(f"ls: cannot access '{target}': No such file or directory")
        elif op == "cat":
            if not args:
                stderr_buf.append("cat: standard input requested (simulated empty EOF)")
            else:
                for arg in args:
                    resolved = vfs.canonicalize(arg)
                    if resolved in vfs.tree:
                        node = vfs.tree[resolved]
                        if node["type"] == "file":
                            stdout_buf.extend(node["content"].split("\n"))
                        else:
                            stderr_buf.append(f"cat: {arg}: Is a directory or special device")
                    else:
                        stderr_buf.append(f"cat: {arg}: No such file or directory")
        elif op == "grep":
            if len(args) < 2:
                stderr_buf.append("grep: usage: grep PATTERN FILE")
            else:
                pattern, filepath = args[0], args[1]
                resolved = vfs.canonicalize(filepath)
                if resolved in vfs.tree and vfs.tree[resolved]["type"] == "file":
                    lines = vfs.tree[resolved]["content"].split("\n")
                    matched = [l for l in lines if pattern.lower() in l.lower()]
                    stdout_buf.extend(matched)
                else:
                    stderr_buf.append(f"grep: {filepath}: No such file or directory")
        else:
            stderr_buf.append(f"bash: {op}: command not found")
            
        return stdout_buf, stderr_buf


# ==============================================================================
# 4. Interactive Scenarios & Demonstrations
# ==============================================================================
def demo_fd_table() -> None:
    section("Modul 1: Tabel File Descriptor Standar Linux")
    print("Setiap proses Linux baru yang di-fork mewarisi 3 File Descriptor default:")
    print(f" - {Color.BLUE}FD 0 (stdin){Color.RESET}  : Input stream standar")
    print(f" - {Color.GREEN}FD 1 (stdout){Color.RESET} : Output stream normal")
    print(f" - {Color.RED}FD 2 (stderr){Color.RESET} : Error diagnostics stream\n")
    
    fd_table = ProcessFileDescriptorTable()
    fd_table.display()
    
    print(f"\n{Color.YELLOW}Simulasi Redirection Sintaks Bash:{Color.RESET}")
    print(f"Perintah: {Color.BOLD}my_script.sh > app.log 2>&1{Color.RESET}")
    print("Langkah 1: `> app.log` mengarahkan FD 1 ke file 'app.log'")
    fd_table.redirect(1, "/tmp/app.log", "w", "O_WRONLY|O_CREAT|O_TRUNC")
    time.sleep(0.3)
    
    print("Langkah 2: `2>&1` menduplikasi FD 1 ke FD 2 (dup2)")
    fd_table.duplicate(1, 2)
    time.sleep(0.3)
    
    print("\nTabel FD Proses setelah Redirection:")
    fd_table.display()


def demo_redirection_separation() -> None:
    section("Modul 2: Pemisahan Aliran stdout vs stderr")
    vfs = VirtualFileSystem()
    print("Menjalankan perintah campuran yang menghasilkan normal output dan error:")
    print(f"{Color.BOLD}$ cat /etc/hosts /etc/doesnotexist{Color.RESET}\n")
    
    stdout_res, stderr_res = CommandExecutionSimulator.run_mock_command("cat /etc/hosts /etc/doesnotexist", vfs)
    
    print(f"{Color.CYAN}[Aliran Asli di Terminal]:{Color.RESET}")
    for line in stdout_res:
        print(f"  {Color.GREEN}[STDOUT (FD 1)]{Color.RESET} {line}")
    for line in stderr_res:
        print(f"  {Color.RED}[STDERR (FD 2)]{Color.RESET} {line}")
        
    print(f"\n{Color.YELLOW}Simulasi: cat /etc/hosts /etc/doesnotexist > output.txt 2> error.log{Color.RESET}")
    print(f"  => {Color.GREEN}output.txt{Color.RESET} hanya menyimpan {len(stdout_res)} baris STDOUT")
    print(f"  => {Color.RED}error.log{Color.RESET} hanya menyimpan {len(stderr_res)} baris STDERR")


def demo_navigation_mechanics() -> None:
    section("Modul 3: Mekanisme Navigasi Direktori & Path Resolution")
    vfs = VirtualFileSystem()
    print(f"Direktori awal (PWD): {Color.BOLD}{vfs.cwd}{Color.RESET}")
    
    test_paths = [
        "docs",
        "../..",
        "../../var/log/./syslog",
        "/etc/../dev/stdin",
        "nonexistent_dir"
    ]
    
    print(f"{Color.CYAN}┌─────────────────────────────┬───────────────────────────────┬────────────┐")
    print(f"│ Input Path                  │ Resolved Canonical Path       │ Status     │")
    print(f"├─────────────────────────────┼───────────────────────────────┼────────────┤{Color.RESET}")
    for p in test_paths:
        canonical = vfs.canonicalize(p)
        exists = canonical in vfs.tree
        status_str = f"{Color.GREEN}EXISTS{Color.RESET}" if exists else f"{Color.RED}ENOENT{Color.RESET}"
        print(f"│ {p:<27} │ {canonical:<29} │ {status_str:<10} │")
    print(f"{Color.CYAN}└─────────────────────────────┴───────────────────────────────┴────────────┘{Color.RESET}")


def interactive_shell() -> None:
    banner("LAB SIMULATOR: BAB 02 - NAVIGASI & I/O FILE DESCRIPTORS")
    print(f"{Color.WHITE}Ketik perintah simulasi di bawah ini.{Color.RESET}")
    print(f"Perintah didukung: {Color.BOLD}pwd, cd <dir>, ls [dir], cat <file>, grep <kw> <file>, fdtable, help, exit{Color.RESET}\n")
    
    vfs = VirtualFileSystem()
    fd_table = ProcessFileDescriptorTable()
    
    while True:
        try:
            prompt = f"{Color.GREEN}user@posix-lab{Color.RESET}:{Color.BLUE}{vfs.cwd}{Color.RESET}$ "
            raw_input = input(prompt).strip()
            if not raw_input:
                continue
            
            if raw_input in ("exit", "quit"):
                print(f"{Color.YELLOW}Menutup sesi lab I/O streams. Sampai jumpa!{Color.RESET}")
                break
                
            elif raw_input == "help":
                print("\nDaftar Perintah:")
                print("  pwd                     - Cetak working directory saat ini")
                print("  cd <path>               - Pindah direktori (mendukung '.', '..', relatif, absolut)")
                print("  ls [path]               - Tampilkan isi direktori virtual")
                print("  cat <file>              - Tampilkan konten file")
                print("  grep <kata> <file>      - Filter baris file yang cocok")
                print("  fdtable                 - Tampilkan status tabel File Descriptor saat ini")
                print("  demo                    - Jalankan seluruh showcase demonstrasi otomatis")
                print("  exit / quit             - Keluar dari simulator\n")
                
            elif raw_input == "demo":
                demo_fd_table()
                demo_redirection_separation()
                demo_navigation_mechanics()
                
            elif raw_input == "fdtable":
                fd_table.display()
                
            elif raw_input.startswith("cd"):
                parts = raw_input.split(maxsplit=1)
                target = parts[1] if len(parts) > 1 else "/home/student"
                success, msg = vfs.change_directory(target)
                if not success:
                    print(f"{Color.RED}{msg}{Color.RESET}")
                    
            else:
                stdout_lines, stderr_lines = CommandExecutionSimulator.run_mock_command(raw_input, vfs)
                for out in stdout_lines:
                    print(f"{Color.WHITE}{out}{Color.RESET}")
                for err in stderr_lines:
                    print(f"{Color.RED}{err}{Color.RESET}", file=sys.stderr)
                    
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Color.YELLOW}Sesi dihentikan pengguna.{Color.RESET}")
            break


# ==============================================================================
# Main Entry Point
# ==============================================================================
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        banner("DEMO OTOMATIS: FONDASI I/O STREAMS & FILE DESCRIPTORS")
        demo_fd_table()
        demo_redirection_separation()
        demo_navigation_mechanics()
    else:
        interactive_shell()

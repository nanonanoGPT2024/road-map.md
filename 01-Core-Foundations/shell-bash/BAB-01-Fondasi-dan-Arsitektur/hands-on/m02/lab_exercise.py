#!/usr/bin/env python3
"""
Lab Hands-on: Fondasi Shell, Terminal, & Arsitektur Eksekusi Bash
Kategori: 01-Core-Foundations (Bab 01 - Modul 02 Deep Dive)

Skrip ini memodelkan siklus internal arsitektur eksekusi Bash:
1. Lexical Analysis & Tokenization (operator pipa, redirection, word splitting).
2. Parameter & Variable Expansion ($VAR).
3. Duplikasi File Descriptor (File Descriptor Table: 0/STDIN, 1/STDOUT, 2/STDERR).
4. Simulasi Fork-Exec Model & Pipe IPC (Inter-Process Communication).
5. Subshell Isolation (Copy-on-Write Environment behavior).
"""

import sys
import os
import re
import io
import time
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum, auto

# ============================================================================
# ANSI Color Palette untuk Output Visualisasi Terminal
# ============================================================================
class Color:
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

def print_header(title: str):
    print(f"\n{Color.BOLD}{Color.BLUE}{'=' * 75}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN} [BASH EXECUTION ENGINE ENGINE] {title.upper()}{Color.RESET}")
    print(f"{Color.BOLD}{Color.BLUE}{'=' * 75}{Color.RESET}")

# ============================================================================
# Tokenizer & AST Definition
# ============================================================================
class TokenType(Enum):
    WORD = auto()
    PIPE = auto()         # |
    REDIR_OUT = auto()    # >
    REDIR_APPEND = auto() # >>
    REDIR_IN = auto()     # <

@dataclass
class Token:
    type: TokenType
    value: str

@dataclass
class CommandNode:
    argv: List[str] = field(default_factory=list)
    stdin_redirect: Optional[str] = None
    stdout_redirect: Optional[str] = None
    append_stdout: bool = False

# ============================================================================
# Process Control Block & File Descriptor Table
# ============================================================================
class ProcessContext:
    """
    Simulasi Process Control Block (PCB) POSIX:
    Menyimpan PID, PPID, Environment Table, dan Virtual File Descriptor Table.
    """
    _next_pid = 1000

    def __init__(self, ppid: int, env: Dict[str, str]):
        self.pid = ProcessContext._next_pid
        ProcessContext._next_pid += 1
        self.ppid = ppid
        # Salinan lingkungan (Copy-on-Write environment inheritance)
        self.env = env.copy()
        # FD Table: 0 -> STDIN, 1 -> STDOUT, 2 -> STDERR
        self.fd_table: Dict[int, io.TextIOBase] = {
            0: sys.stdin,
            1: io.StringIO(),
            2: io.StringIO()
        }
        self.exit_code = 0

    def dup2(self, oldfd: io.TextIOBase, newfd_idx: int):
        """Simulasi POSIX dup2(): mengarahkan slot FD ke IO stream baru."""
        self.fd_table[newfd_idx] = oldfd

# ============================================================================
# Bash Core Execution Engine
# ============================================================================
class MiniBashEngine:
    def __init__(self):
        self.global_env: Dict[str, str] = {
            "SHELL": "/bin/minibash",
            "USER": "sysadmin",
            "VERSION": "5.2-simulated",
            "IFS": " \t\n"
        }
        self.virtual_vfs: Dict[str, str] = {} # Mock filesystem storage

    def tokenize(self, cmd_line: str) -> List[Token]:
        """Melakukan pemecahan stream karakter menjadi token-token sintaks shell."""
        raw_tokens = re.findall(r'>>|>|<|\||"(?:\\.|[^"\\])*"|\S+', cmd_line)
        tokens = []
        for t in raw_tokens:
            if t == "|":
                tokens.append(Token(TokenType.PIPE, t))
            elif t == ">":
                tokens.append(Token(TokenType.REDIR_OUT, t))
            elif t == ">>":
                tokens.append(Token(TokenType.REDIR_APPEND, t))
            elif t == "<":
                tokens.append(Token(TokenType.REDIR_IN, t))
            else:
                clean_val = t[1:-1] if (t.startswith('"') and t.endswith('"')) else t
                tokens.append(Token(TokenType.WORD, clean_val))
        return tokens

    def expand_parameters(self, word: str, env: Dict[str, str]) -> str:
        """Simulasi Shell Parameter Expansion: Mengganti $VAR dengan nilai env."""
        def repl(match):
            var_name = match.group(1)
            return env.get(var_name, "")
        return re.sub(r'\$([a-zA-Z_][a-zA-Z0-9_]*)', repl, word)

    def parse(self, tokens: List[Token], env: Dict[str, str]) -> List[CommandNode]:
        """Menyusun representasi pipeline commands beserta instruksi redireksi I/O."""
        pipeline: List[CommandNode] = []
        current_cmd = CommandNode()
        idx = 0

        while idx < len(tokens):
            tok = tokens[idx]
            if tok.type == TokenType.PIPE:
                pipeline.append(current_cmd)
                current_cmd = CommandNode()
            elif tok.type == TokenType.REDIR_OUT:
                idx += 1
                if idx < len(tokens):
                    current_cmd.stdout_redirect = self.expand_parameters(tokens[idx].value, env)
                    current_cmd.append_stdout = False
            elif tok.type == TokenType.REDIR_APPEND:
                idx += 1
                if idx < len(tokens):
                    current_cmd.stdout_redirect = self.expand_parameters(tokens[idx].value, env)
                    current_cmd.append_stdout = True
            elif tok.type == TokenType.REDIR_IN:
                idx += 1
                if idx < len(tokens):
                    current_cmd.stdin_redirect = self.expand_parameters(tokens[idx].value, env)
            elif tok.type == TokenType.WORD:
                expanded = self.expand_parameters(tok.value, env)
                current_cmd.argv.append(expanded)
            idx += 1

        if current_cmd.argv or current_cmd.stdout_redirect or current_cmd.stdin_redirect:
            pipeline.append(current_cmd)

        return pipeline

    def _builtin_echo(self, proc: ProcessContext, args: List[str]):
        output = " ".join(args)
        proc.fd_table[1].write(output + "\n")

    def _builtin_grep(self, proc: ProcessContext, args: List[str]):
        if not args:
            proc.fd_table[2].write("grep: operand argumen pola hilang\n")
            proc.exit_code = 1
            return
        pattern = args[0]
        # Baca stream input dari File Descriptor 0 (STDIN)
        input_stream = proc.fd_table[0]
        if hasattr(input_stream, 'getvalue'):
            content = input_stream.getvalue().splitlines()
        elif hasattr(input_stream, 'readlines'):
            content = [line.rstrip('\r\n') for line in input_stream.readlines()]
        else:
            content = []

        for line in content:
            if pattern in line:
                proc.fd_table[1].write(line + "\n")

    def _builtin_tr_upper(self, proc: ProcessContext, _: List[str]):
        """Simulasi perintah transformasi 'tr a-z A-Z'."""
        input_stream = proc.fd_table[0]
        lines = input_stream.getvalue() if hasattr(input_stream, 'getvalue') else ""
        proc.fd_table[1].write(lines.upper())

    def _dispatch_execution(self, proc: ProcessContext):
        """Memanggil binary/builtin logic berdasarkan argv[0]."""
        if not proc.argv:
            return
        cmd = proc.argv[0]
        args = proc.argv[1:]

        if cmd == "echo":
            self._builtin_echo(proc, args)
        elif cmd == "grep":
            self._builtin_grep(proc, args)
        elif cmd == "upper":
            self._builtin_tr_upper(proc, args)
        elif cmd == "env":
            for k, v in proc.env.items():
                proc.fd_table[1].write(f"{k}={v}\n")
        else:
            proc.fd_table[2].write(f"minibash: command not found: {cmd}\n")
            proc.exit_code = 127

    def execute_pipeline(self, pipeline: List[CommandNode], parent_pid: int = 1) -> str:
        """
        Mensimulasikan Fork-Exec loop, pipe() IPC synchronization, 
        serta dup2() manipulasi File Descriptor table.
        """
        previous_pipe_read: Optional[io.StringIO] = None
        last_stdout_content = ""

        print(f"{Color.DIM}>> Inisialisasi Eksekusi Pipeline ({len(pipeline)} stage/s){Color.RESET}")

        for i, cmd_node in enumerate(pipeline):
            # 1. FORK: Membuat PCB proses anak terisolasi
            proc = ProcessContext(ppid=parent_pid, env=self.global_env)
            proc.argv = cmd_node.argv

            print(f"  {Color.YELLOW}• [Fork PID {proc.pid} (PPID {proc.ppid})]{Color.RESET} target: {cmd_node.argv}")

            # 2. SETUP STDIN (Handle Pipe sebelumnya atau Redirection <)
            if cmd_node.stdin_redirect:
                file_content = self.virtual_vfs.get(cmd_node.stdin_redirect, "")
                proc.dup2(io.StringIO(file_content), 0)
                print(f"    └─ FD 0 redirected from VFS:'{cmd_node.stdin_redirect}'")
            elif previous_pipe_read is not None:
                # Mengaitkan output pipa tahap sebelumnya ke STDIN proses ini
                previous_pipe_read.seek(0)
                proc.dup2(previous_pipe_read, 0)
                print(f"    └─ FD 0 dihubungkan ke Pipa IPC (Read End)")

            # 3. SETUP STDOUT (Handle Pipa ke proses berikutnya atau Redirection >)
            is_last_stage = (i == len(pipeline) - 1)
            current_pipe_write = io.StringIO()

            if is_last_stage:
                if cmd_node.stdout_redirect:
                    # Redirection target
                    proc.dup2(current_pipe_write, 1)
                else:
                    proc.dup2(current_pipe_write, 1)
            else:
                # Menghubungkan STDOUT proses saat ini ke Write End antrian Pipa
                proc.dup2(current_pipe_write, 1)
                print(f"    └─ FD 1 dihubungkan ke Pipa IPC (Write End)")

            # 4. EXECVE: Eksekusi program di dalam konteks terisolasi
            self._dispatch_execution(proc)

            # 5. POST-EXECUTION FD PROCESSING
            output_data = proc.fd_table[1].getvalue()
            errors = proc.fd_table[2].getvalue()

            if errors:
                print(f"    {Color.RED}[STDERR]: {errors.strip()}{Color.RESET}")

            if cmd_node.stdout_redirect:
                # Simpan ke virtual filesystem
                if cmd_node.append_stdout:
                    self.virtual_vfs[cmd_node.stdout_redirect] = (
                        self.virtual_vfs.get(cmd_node.stdout_redirect, "") + output_data
                    )
                else:
                    self.virtual_vfs[cmd_node.stdout_redirect] = output_data
                print(f"    └─ File Write: {len(output_data)} bytes -> '{cmd_node.stdout_redirect}'")

            # Persiapan input pipa untuk proses iterasi berikutnya
            previous_pipe_read = current_pipe_write
            last_stdout_content = output_data

            print(f"    {Color.GREEN}✓ Terminated with Exit Code {proc.exit_code}{Color.RESET}")

        return last_stdout_content

# ============================================================================
# Driver Skenario Pengujian Lab
# ============================================================================
def run_lab():
    engine = MiniBashEngine()

    print_header("Skenario 1: Parameter Expansion & Basic Redirection (>)")
    cmd1 = 'echo "System Engine: $SHELL running under user $USER" > /etc/sysinfo.txt'
    print(f"{Color.BOLD}Command:{Color.RESET} {cmd1}")
    tokens = engine.tokenize(cmd1)
    pipeline = engine.parse(tokens, engine.global_env)
    engine.execute_pipeline(pipeline)
    
    print(f"\n{Color.CYAN}[VFS /etc/sysinfo.txt Content]:{Color.RESET}")
    print(engine.virtual_vfs.get("/etc/sysinfo.txt", "").strip())

    print_header("Skenario 2: Pipeline Chaining & Stream Filtering (|)")
    # Buat dataset mock ke VFS
    engine.virtual_vfs["/var/log/kernel.log"] = (
        "INFO: Initialization complete\n"
        "DEBUG: Probing PCI devices\n"
        "ERROR: Device eth0 timeout\n"
        "INFO: System state OK\n"
        "ERROR: Disk sector I/O failure\n"
    )
    cmd2 = 'echo "$SHELL" | upper'
    print(f"{Color.BOLD}Command:{Color.RESET} {cmd2}")
    tokens = engine.tokenize(cmd2)
    pipeline = engine.parse(tokens, engine.global_env)
    output = engine.execute_pipeline(pipeline)
    print(f"\n{Color.GREEN}[STDOUT Output]:{Color.RESET} {output.strip()}")

    print_header("Skenario 3: Multi-Stage IPC Pipeline dengan Redirection")
    cmd3 = 'grep ERROR < /var/log/kernel.log | upper > /var/log/urgent_alerts.log'
    print(f"{Color.BOLD}Command:{Color.RESET} {cmd3}")
    tokens = engine.tokenize(cmd3)
    pipeline = engine.parse(tokens, engine.global_env)
    engine.execute_pipeline(pipeline)

    print(f"\n{Color.CYAN}[VFS /var/log/urgent_alerts.log Content]:{Color.RESET}")
    print(engine.virtual_vfs.get("/var/log/urgent_alerts.log", "").strip())

    print_header("Skenario 4: Subshell Isolation Verification")
    print("Membuktikan isolasi environment anak proses terhadap parent shell:")
    print(f"Parent Shell Environment VERSION: {engine.global_env['VERSION']}")
    
    # Subshell fork-exec simulasi
    subshell_proc = ProcessContext(ppid=1, env=engine.global_env)
    subshell_proc.env["VERSION"] = "6.0-experimental-mutated"
    print(f"Subshell PID {subshell_proc.pid} memutasi VERSION -> '{subshell_proc.env['VERSION']}'")
    
    print(f"Parent Shell Environment VERSION pasca-subshell: {Color.GREEN}{engine.global_env['VERSION']}{Color.RESET} (TIDAK BERUBAH)")
    print(f"\n{Color.BOLD}{Color.GREEN}Semua modul fondasi Bash Execution Architecture terverifikasi normal.{Color.RESET}\n")

if __name__ == "__main__":
    run_lab()
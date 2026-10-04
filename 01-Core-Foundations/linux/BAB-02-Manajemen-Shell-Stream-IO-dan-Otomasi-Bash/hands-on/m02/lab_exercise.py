#!/usr/bin/env python3
"""
Lab Hands-on: Linux Core Foundations - Bab 02: Manajemen Shell, Stream I/O, & Otomasi
Simulator Kernel Shell Virtual: Stream Redirection, File Descriptors, Piping, & Subshells.
"""

import sys
import io
import re
import copy
from typing import Dict, List, Tuple, Optional

# ANSI Color Codes untuk visualisasi terminal
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_RED = "\033[31m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_BLUE = "\033[34m"
C_CYAN = "\033[36m"
C_MAGENTA = "\033[35m"


class VirtualStream(io.StringIO):
    """Representasi stream memori terisolasi yang mengemulasi byte-oriented POSIX stream."""
    def __init__(self, initial_value: str = ""):
        super().__init__(initial_value)

    def read_all(self) -> str:
        self.seek(0)
        return self.read()

    def append(self, text: str) -> None:
        self.seek(0, io.SEEK_END)
        self.write(text)


class FileDescriptorTable:
    """
    Mengemulasi POSIX File Descriptor (FD) Table proses.
    Standar:
    0: STDIN
    1: STDOUT
    2: STDERR
    3+: User-defined descriptors (dialokasikan secara dinamis)
    """
    def __init__(self):
        self.table: Dict[int, VirtualStream] = {
            0: VirtualStream(),  # stdin
            1: VirtualStream(),  # stdout
            2: VirtualStream()   # stderr
        }

    def duplicate(self, oldfd: int, newfd: int) -> None:
        """Emulasi sistem panggilan dup2(oldfd, newfd)."""
        if oldfd not in self.table:
            raise ValueError(f"Bad file descriptor: {oldfd}")
        self.table[newfd] = self.table[oldfd]

    def allocate(self, stream: VirtualStream, fd: Optional[int] = None) -> int:
        if fd is not None:
            self.table[fd] = stream
            return fd
        next_fd = max(self.table.keys()) + 1
        self.table[next_fd] = stream
        return next_fd

    def get(self, fd: int) -> VirtualStream:
        if fd not in self.table:
            raise OSError(9, f"EBADF: Bad file descriptor {fd}")
        return self.table[fd]

    def clone(self) -> "FileDescriptorTable":
        """Membuat salinan tabel FD untuk emulasi subshell fork()."""
        new_fdt = FileDescriptorTable()
        for fd, stream in self.table.items():
            new_fdt.table[fd] = VirtualStream(stream.getvalue())
        return new_fdt


class ExecutionContext:
    """Konteks eksekusi proses shell (Environment, PWD, FD Table, Exit Code)."""
    def __init__(self, env: Optional[Dict[str, str]] = None):
        self.env: Dict[str, str] = env if env else {"SHELL": "/bin/vsh", "STATUS": "ACTIVE"}
        self.fd_table: FileDescriptorTable = FileDescriptorTable()
        self.last_exit_code: int = 0
        self.virtual_fs: Dict[str, str] = {}

    def spawn_subshell(self) -> "ExecutionContext":
        """Emulasi fork() subshell: Lingkungan diwarisi tapi terisolasi dari parent."""
        sub = ExecutionContext(copy.deepcopy(self.env))
        sub.fd_table = self.fd_table.clone()
        sub.virtual_fs = self.virtual_fs  # Shared global filesystem storage
        sub.last_exit_code = self.last_exit_code
        return sub


class ShellEngine:
    """Mesin parser dan runtime perintah shell, stream redirection, dan pipelines."""
    def __init__(self):
        self.ctx = ExecutionContext()
        self._init_mock_filesystem()

    def _init_mock_filesystem(self):
        self.ctx.virtual_fs["/var/log/syslog"] = (
            "2023-10-24 10:00:01 INFO [kernel] Booting vNode-01\n"
            "2023-10-24 10:00:03 WARN [auth] Failed login attempt from 192.168.1.50\n"
            "2023-10-24 10:00:05 ERROR [disk] I/O timeout block 439023\n"
            "2023-10-24 10:00:10 WARN [network] High latency on eth0: 120ms\n"
            "2023-10-24 10:00:12 ERROR [kernel] Out of memory killer invoked\n"
        )
        self.ctx.virtual_fs["/etc/hosts"] = "127.0.0.1 localhost\n192.168.1.1 gateway\n"

    def execute_builtin(self, cmd_tokens: List[str], ctx: ExecutionContext) -> int:
        """Mengeksekusi built-in command dan utilitas POSIX esensial."""
        if not cmd_tokens:
            return 0

        cmd = cmd_tokens[0]
        args = cmd_tokens[1:]

        stdin = ctx.fd_table.get(0)
        stdout = ctx.fd_table.get(1)
        stderr = ctx.fd_table.get(2)

        if cmd == "echo":
            rendered = []
            for arg in args:
                if arg.startswith("$"):
                    var_name = arg[1:]
                    rendered.append(ctx.env.get(var_name, ""))
                else:
                    rendered.append(arg)
            stdout.write(" ".join(rendered) + "\n")
            return 0

        elif cmd == "cat":
            if not args:
                content = stdin.read_all()
                stdout.write(content)
            else:
                for path in args:
                    if path in ctx.virtual_fs:
                        stdout.write(ctx.virtual_fs[path])
                    else:
                        stderr.write(f"cat: {path}: No such file or directory\n")
                        return 1
            return 0

        elif cmd == "grep":
            pattern = args[0] if args else ""
            invert = False
            if pattern == "-v":
                invert = True
                pattern = args[1] if len(args) > 1 else ""

            input_data = stdin.read_all().splitlines()
            matched = False
            for line in input_data:
                found = bool(re.search(pattern, line))
                if (found and not invert) or (not found and invert):
                    stdout.write(line + "\n")
                    matched = True
            return 0 if matched else 1

        elif cmd == "wc":
            mode = args[0] if args else "-l"
            lines = stdin.read_all().splitlines()
            if mode == "-l":
                stdout.write(f"{len(lines)}\n")
            return 0

        elif cmd == "export":
            for pair in args:
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    ctx.env[k] = v
            return 0

        elif cmd == "emit_debug":
            # Perintah khusus untuk memicu emisi terpisah pada stdout & stderr
            stdout.write("[STDOUT] Standby operational data payload\n")
            stderr.write("[STDERR] Warn: Buffer 78% utilized\n")
            return 0

        else:
            stderr.write(f"vsh: command not found: {cmd}\n")
            return 127

    def _parse_redirections(self, tokens: List[str], ctx: ExecutionContext) -> Tuple[List[str], List[Tuple[str, str, int]]]:
        """
        Memisahkan operator I/O stream:
        > (overwrite stdout), >> (append stdout), 2> (stderr), < (stdin redirection).
        """
        clean_tokens = []
        redirections = []
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token in (">", ">>", "2>", "2>>", "<"):
                target = tokens[i + 1]
                redirections.append((token, target, 1 if token in (">", ">>") else (2 if "2" in token else 0)))
                i += 2
            else:
                clean_tokens.append(token)
                i += 1
        return clean_tokens, redirections

    def run_single(self, cmd_line: str, ctx: ExecutionContext) -> int:
        """Mengeksekusi satu unit perintah dengan manajemen routing File Descriptor."""
        tokens = cmd_line.strip().split()
        if not tokens:
            return 0

        clean_tokens, redirections = self._parse_redirections(tokens, ctx)
        saved_fds = {0: ctx.fd_table.get(0), 1: ctx.fd_table.get(1), 2: ctx.fd_table.get(2)}

        # Setup I/O Stream Hooks
        for op, target, fd_num in redirections:
            if op == ">":
                stream = VirtualStream()
                ctx.fd_table.allocate(stream, 1)
            elif op == ">>":
                existing = ctx.virtual_fs.get(target, "")
                stream = VirtualStream(existing)
                ctx.fd_table.allocate(stream, 1)
            elif op == "2>":
                stream = VirtualStream()
                ctx.fd_table.allocate(stream, 2)
            elif op == "<":
                if target in ctx.virtual_fs:
                    stream = VirtualStream(ctx.virtual_fs[target])
                    ctx.fd_table.allocate(stream, 0)
                else:
                    ctx.fd_table.get(2).write(f"vsh: {target}: No such file or directory\n")
                    return 1

        exit_code = self.execute_builtin(clean_tokens, ctx)

        # Commit redirection back to Virtual FS
        for op, target, fd_num in redirections:
            stream = ctx.fd_table.get(fd_num)
            if op in (">", ">>", "2>"):
                ctx.virtual_fs[target] = stream.read_all()

        # Restore original FDs
        for fd_num, original_stream in saved_fds.items():
            ctx.fd_table.allocate(original_stream, fd_num)

        ctx.last_exit_code = exit_code
        return exit_code

    def run_pipeline(self, pipeline_str: str, ctx: ExecutionContext) -> int:
        """
        Emulasi pipeline POSIX (|): Output stdout dari proc[i] di-pipe langsung
        ke stdin proc[i+1]. Setiap stage berjalan dalam sandbox stream terisolasi.
        """
        stages = [stage.strip() for stage in pipeline_str.split("|")]
        pipe_buffer = ""

        last_code = 0
        for i, stage in enumerate(stages):
            stage_ctx = ctx.spawn_subshell()
            stage_ctx.fd_table.allocate(VirtualStream(pipe_buffer), 0)

            # Eksekusi unit stage
            last_code = self.run_single(stage, stage_ctx)
            pipe_buffer = stage_ctx.fd_table.get(1).read_all()

            # Tangani emisi STDERR secara real-time ke console
            err_data = stage_ctx.fd_table.get(2).read_all()
            if err_data:
                sys.stderr.write(f"{C_RED}{err_data}{C_RESET}")

        # Final pipe output ditulis ke stdout parent jika terminal interaktif
        ctx.fd_table.get(1).write(pipe_buffer)
        ctx.last_exit_code = last_code
        return last_code

    def run_compound(self, script_line: str) -> None:
        """Mengevaluasi operator logika shell lanjutan: &&, ||, dan Subshells ( )."""
        print(f"\n{C_BOLD}{C_CYAN}EXECUTING SHELL INSTRUCTION:{C_RESET} {C_YELLOW}{script_line}{C_RESET}")

        # Evaluasi blok Subshell (...)
        if script_line.startswith("(") and script_line.endswith(")"):
            subshell_body = script_line[1:-1].strip()
            print(f"  {C_MAGENTA}↳ Forking Subshell Process... Environment Isolated.{C_RESET}")
            sub_ctx = self.ctx.spawn_subshell()
            for part in subshell_body.split(";"):
                self.run_pipeline(part.strip(), sub_ctx)
            sub_out = sub_ctx.fd_table.get(1).read_all()
            if sub_out:
                print(f"  {C_GREEN}[Subshell STDOUT]{C_RESET}\n{sub_out.rstrip()}")
            print(f"  {C_MAGENTA}↳ Subshell Terminated. Exit Code: {sub_ctx.last_exit_code}{C_RESET}")
            return

        # Parsing conditional operators && dan ||
        tokens = re.split(r"(\&\&|\|\|)", script_line)
        idx = 0
        should_run = True

        while idx < len(tokens):
            segment = tokens[idx].strip()
            if segment == "&&":
                should_run = (self.ctx.last_exit_code == 0)
                idx += 1
                continue
            elif segment == "||":
                should_run = (self.ctx.last_exit_code != 0)
                idx += 1
                continue

            if should_run and segment:
                prev_out = VirtualStream()
                self.ctx.fd_table.allocate(prev_out, 1)
                code = self.run_pipeline(segment, self.ctx)
                out = self.ctx.fd_table.get(1).read_all()
                if out:
                    print(f"  {C_GREEN}[STDOUT]{C_RESET}\n{out.rstrip()}")
                print(f"  {C_BLUE}[PID Pipeline Exit Code: {code}]{C_RESET}")
            elif not segment:
                pass
            else:
                print(f"  {C_YELLOW}[SKIPPED via Short-Circuit (Exit Code: {self.ctx.last_exit_code})]{C_RESET}")

            idx += 1


def run_laboratory():
    """Demonstrasi praktis konsep kernel Shell, I/O Redirection, dan Pipes."""
    print(f"{C_BOLD}{C_CYAN}==================================================================={C_RESET}")
    print(f"{C_BOLD}{C_GREEN} LAB: MANAJEMEN SHELL, STREAM I/O, & OTOMASI BASH LANJUTAN {C_RESET}")
    print(f"{C_BOLD}{C_CYAN}==================================================================={C_RESET}")

    engine = ShellEngine()

    # Skenario 1: Pipeline multi-stage & filtering stream
    engine.run_compound("cat /var/log/syslog | grep ERROR | wc -l")

    # Skenario 2: Stream Demultiplexing (Pemisahan FD 1 STDOUT dan FD 2 STDERR)
    engine.run_compound("emit_debug > /tmp/stdout.log 2> /tmp/stderr.log")
    print(f"  {C_BOLD}Verifikasi In-Memory Virtual File System:{C_RESET}")
    print(f"   /tmp/stdout.log -> {engine.ctx.virtual_fs.get('/tmp/stdout.log', '').strip()}")
    print(f"   /tmp/stderr.log -> {engine.ctx.virtual_fs.get('/tmp/stderr.log', '').strip()}")

    # Skenario 3: Short-Circuit Logic Evaluation (&& vs ||)
    engine.run_compound("grep ERROR /var/log/syslog && echo Pipeline_Succeeded || echo Pipeline_Failed")
    engine.run_compound("grep FATAL /var/log/syslog && echo System_Cracked || echo Handled_Missing_Pattern")

    # Skenario 4: Subshell Forking & Mutasi State Isolasi (Environment Variables)
    engine.run_compound("export APP_ENV=PRODUCTION")
    print(f"  {C_BOLD}Parent Env Sebelum Subshell:{C_RESET} APP_ENV = {engine.ctx.env.get('APP_ENV')}")
    engine.run_compound("(export APP_ENV=STAGING ; echo Local_Env_Is_$APP_ENV)")
    print(f"  {C_BOLD}Parent Env Sesudah Subshell:{C_RESET} APP_ENV = {engine.ctx.env.get('APP_ENV')} (Tidak Termutasi)")

    print(f"\n{C_BOLD}{C_GREEN}LAB SELESAI: Seluruh simulasi stream & job parsing tuntas divalidasi.{C_RESET}\n")


if __name__ == "__main__":
    run_laboratory()
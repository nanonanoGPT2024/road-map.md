#!/usr/bin/env python3
"""
Lab Hands-on: Advanced Text Processing (Regex, Sed, & Awk Engine Simulation)
Category: 01-Core-Foundations | Chapter 06: Module 02 Deep Dive

Simulates the internals of Unix text processing engines:
1. Regex compiler and pattern space manager.
2. Stream Editor (Sed) cycle engine supporting addressing, substitution, and branching.
3. Awk pattern-action interpreter with record/field splitting ($0..$NF), 
   accumulator states, and BEGIN/END lifecycle hooks.
"""

import sys
import re
import time
from typing import List, Dict, Callable, Tuple, Any, Optional
from collections import defaultdict

# ANSI Terminal Formatting
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_BG_DARK = "\033[48;5;236m"

# Mock Access Log Data (Simulating raw /var/log/nginx/access.log)
RAW_STREAM_DATA = [
    '192.168.1.10 - admin [10/Oct/2023:13:55:36 +0000] "GET /api/v1/auth HTTP/1.1" 200 1024 "-" "Mozilla/5.0"',
    '10.0.0.5 - - [10/Oct/2023:13:55:37 +0000] "POST /api/v1/login HTTP/1.1" 401 256 "https://example.com" "curl/7.68.0"',
    '192.168.1.15 - dev [10/Oct/2023:13:55:38 +0000] "GET /metrics HTTP/1.1" 200 4096 "-" "Prometheus/2.25.0"',
    'UNKNOWN_CORRUPT_PACKET_DROPPED_LINE_INVALID',
    '172.16.0.2 - - [10/Oct/2023:13:55:40 +0000] "GET /static/app.js HTTP/1.1" 304 0 "https://example.com" "Mozilla/5.0"',
    '10.0.0.5 - - [10/Oct/2023:13:55:41 +0000] "POST /api/v1/login HTTP/1.1" 401 256 "https://example.com" "curl/7.68.0"',
    '10.0.0.5 - - [10/Oct/2023:13:55:42 +0000] "POST /api/v1/login HTTP/1.1" 200 512 "https://example.com" "curl/7.68.0"',
    '192.168.1.20 - ops [10/Oct/2023:13:55:43 +0000] "DELETE /api/v1/cache HTTP/1.1" 500 128 "-" "Python-requests/2.25.1"',
    '# DEBUG: Internal proxy latency: 12ms',
    '192.168.1.10 - admin [10/Oct/2023:13:55:45 +0000] "GET /api/v1/users HTTP/1.1" 200 8192 "-" "Mozilla/5.0"'
]


class SedEngine:
    """
    Simulates GNU Sed execution cycles.
    Maintains a Pattern Space and Hold Space, processing commands sequentially:
    - Line number or Regex Address matching
    - Substitute: s/regex/replacement/flags
    - Delete: d (clears pattern space and cycles)
    - Print: p
    """
    def __init__(self):
        self.rules: List[Dict[str, Any]] = []

    def add_substitution(self, address_pattern: Optional[str], search: str, 
                         replace: str, flags: str = "") -> "SedEngine":
        """Compiles and appends an 's' (substitute) command."""
        compiled_addr = re.compile(address_pattern) if address_pattern else None
        re_flags = re.IGNORECASE if "i" in flags else 0
        compiled_search = re.compile(search, re_flags)
        is_global = "g" in flags

        self.rules.append({
            "type": "substitute",
            "address": compiled_addr,
            "search": compiled_search,
            "replace": replace,
            "global": is_global
        })
        return self

    def add_delete(self, address_pattern: str) -> "SedEngine":
        """Compiles and appends a 'd' (delete) command."""
        compiled_addr = re.compile(address_pattern)
        self.rules.append({
            "type": "delete",
            "address": compiled_addr
        })
        return self

    def execute(self, stream: List[str]) -> List[str]:
        """Runs the Sed cycle: Read -> Pattern Space -> Rules -> Output."""
        output: List[str] = []

        for line_no, raw_line in enumerate(stream, start=1):
            pattern_space = raw_line
            deleted = False

            for rule in self.rules:
                addr = rule["address"]
                # Evaluate address criteria
                if addr and not addr.search(pattern_space):
                    continue

                if rule["type"] == "delete":
                    deleted = True
                    break  # Abort cycle immediately

                elif rule["type"] == "substitute":
                    count = 0 if rule["global"] else 1
                    pattern_space = rule["search"].sub(rule["replace"], pattern_space, count=count)

            if not deleted:
                output.append(pattern_space)

        return output


class AwkRecord:
    """Represents Awk runtime context for a single line ($0 to $NF)."""
    def __init__(self, raw: str, fs: str = r"\s+", nr: int = 0):
        self.NR = nr
        self.raw = raw
        # Tokenize preserving quoted strings or standard FS
        self.fields = [raw] + [f for f in re.split(fs, raw.strip()) if f]
        self.NF = len(self.fields) - 1

    def __getitem__(self, idx: int) -> str:
        if 0 <= idx < len(self.fields):
            return self.fields[idx]
        return ""


class AwkEngine:
    """
    Simulates Awk pattern-action interpreter.
    Features:
    - Custom FS (Field Separator)
    - BEGIN and END lifecycle blocks
    - Pattern matching predicates
    - Stateful memory / Associative arrays
    """
    def __init__(self, fs: str = r"\s+"):
        self.fs = fs
        self.begin_action: Optional[Callable[[Dict[str, Any]], None]] = None
        self.end_action: Optional[Callable[[Dict[str, Any]], None]] = None
        self.rules: List[Tuple[Callable[[AwkRecord], bool], Callable[[AwkRecord, Dict[str, Any]], None]]] = []
        self.state: Dict[str, Any] = defaultdict(int)

    def set_begin(self, func: Callable[[Dict[str, Any]], None]) -> "AwkEngine":
        self.begin_action = func
        return self

    def set_end(self, func: Callable[[Dict[str, Any]], None]) -> "AwkEngine":
        self.end_action = func
        return self

    def add_rule(self, pattern: Optional[Callable[[AwkRecord], bool]], 
                 action: Callable[[AwkRecord, Dict[str, Any]], None]) -> "AwkEngine":
        predicate = pattern if pattern else (lambda rec: True)
        self.rules.append((predicate, action))
        return self

    def execute(self, stream: List[str]):
        """Executes BEGIN block, line cycles, and END block."""
        if self.begin_action:
            self.begin_action(self.state)

        for nr, line in enumerate(stream, start=1):
            rec = AwkRecord(line, fs=self.fs, nr=nr)
            for predicate, action in self.rules:
                if predicate(rec):
                    action(rec, self.state)

        if self.end_action:
            self.end_action(self.state)


def section_header(title: str):
    print(f"\n{CLR_BOLD}{CLR_BLUE}=== {title} ==={CLR_RESET}")


def run_pipeline_demo():
    print(f"{CLR_BOLD}{CLR_CYAN}Starting Advanced Unix Text Processing Lab Engine{CLR_RESET}")
    print(f"Dataset Size: {len(RAW_STREAM_DATA)} records\n")

    # -------------------------------------------------------------
    # STAGE 1: SED STREAM TRANSFORMATION
    # Pipeline: sed '/^#/d; /UNKNOWN/d; s/192\.168\.[0-9]+\.[0-9]+/127.0.0.1/g'
    # -------------------------------------------------------------
    section_header("STAGE 1: Sed Engine Execution (Filter & Transform)")
    sed = SedEngine()
    # Rule 1: Delete comments starting with #
    sed.add_delete(address_pattern=r"^\s*#")
    # Rule 2: Delete corrupted lines
    sed.add_delete(address_pattern=r"UNKNOWN_CORRUPT")
    # Rule 3: Mask Private Subnet IPs to localhost loopback
    sed.add_substitution(
        address_pattern=None,
        search=r"192\.168\.\d+\.\d+",
        replace="127.0.0.1",
        flags="g"
    )

    t0 = time.perf_counter()
    sed_output = sed.execute(RAW_STREAM_DATA)
    sed_latency = (time.perf_counter() - t0) * 1000

    print(f"{CLR_YELLOW}[Sed Pipeline applied rules: delete comments, delete corrupt, mask IPs]{CLR_RESET}")
    for idx, out in enumerate(sed_output, 1):
        print(f"{CLR_BG_DARK}[Line {idx:02d}]{CLR_RESET} {out}")
    print(f"{CLR_GREEN}Sed Transformation Complete. Latency: {sed_latency:.4f} ms | Output records: {len(sed_output)}{CLR_RESET}")

    # -------------------------------------------------------------
    # STAGE 2: AWK ANALYTICS ENGINE
    # Pipeline: awk '{ endpoint=$7; status=$9; bytes=$10; ... } END { report() }'
    # -------------------------------------------------------------
    section_header("STAGE 2: Awk Pattern-Action Engine (Aggregation & Reporting)")

    awk = AwkEngine(fs=r"\s+")

    def awk_begin(state: Dict[str, Any]):
        state["total_bytes"] = 0
        state["total_requests"] = 0
        state["status_counts"] = defaultdict(int)
        state["ip_bandwidth"] = defaultdict(int)
        print(f"{CLR_MAGENTA}>>> AWK BEGIN BLOCK: State metrics tables initialized.{CLR_RESET}")

    def awk_process_record(rec: AwkRecord, state: Dict[str, Any]):
        # Standard combined log format index:
        # $1: Client IP
        # $7: URI Path
        # $9: HTTP Status Code
        # $10: Body Bytes Sent
        ip = rec[1]
        endpoint = rec[7]
        try:
            status = int(rec[9])
            bytes_sent = int(rec[10])
        except (ValueError, IndexError):
            return  # Skip unparseable structured records

        state["total_requests"] += 1
        state["total_bytes"] += bytes_sent
        state["status_counts"][status] += 1
        state["ip_bandwidth"][ip] += bytes_sent

    def awk_end(state: Dict[str, Any]):
        print(f"{CLR_MAGENTA}>>> AWK END BLOCK: Aggregating analytics matrix...{CLR_RESET}\n")
        print(f"{CLR_BOLD}HTTP Status Code Distribution:{CLR_RESET}")
        for code, count in sorted(state["status_counts"].items()):
            color = CLR_GREEN if code < 400 else CLR_RED
            print(f"  Status [{color}{code}{CLR_RESET}]: {count:4d} requests")

        print(f"\n{CLR_BOLD}Bandwidth Per Client IP:{CLR_RESET}")
        for client_ip, b_count in sorted(state["ip_bandwidth"].items(), key=lambda x: x[1], reverse=True):
            kb = b_count / 1024.0
            print(f"  Target: {CLR_CYAN}{client_ip:<16}{CLR_RESET} -> {kb:8.2f} KB ({b_count} bytes)")

        avg_payload = state["total_bytes"] / max(1, state["total_requests"])
        print(f"\n{CLR_BOLD}Summary Metrics:{CLR_RESET}")
        print(f"  Total Processed Requests : {state['total_requests']}")
        print(f"  Aggregated Data Volume   : {state['total_bytes']} bytes")
        print(f"  Mean Payload Density     : {avg_payload:.2f} bytes/req")

    awk.set_begin(awk_begin)
    # Match valid log lines with HTTP verbs: (GET|POST|DELETE|PUT)
    awk.add_rule(
        pattern=lambda r: bool(re.search(r'"(GET|POST|DELETE|PUT)\s+', r.raw)),
        action=awk_process_record
    )
    awk.set_end(awk_end)

    t1 = time.perf_counter()
    awk.execute(sed_output)
    awk_latency = (time.perf_counter() - t1) * 1000

    print(f"\n{CLR_GREEN}Awk Execution Complete. Latency: {awk_latency:.4f} ms{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}==============================================={CLR_RESET}")
    print(f"{CLR_BOLD}Pipeline Execution Pipeline: sed -> awk successfully terminated.{CLR_RESET}")


if __name__ == "__main__":
    run_pipeline_demo()
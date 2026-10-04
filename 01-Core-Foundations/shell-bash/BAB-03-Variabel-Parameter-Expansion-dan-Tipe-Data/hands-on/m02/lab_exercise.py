#!/usr/bin/env python3
"""
Lab Hands-on: Bash Parameter Expansion & Data Structures Engine
Kategori : 01-Core-Foundations
Topik    : Shell-Bash
Bab 03   : Variabel, Parameter Expansion, & Struktur Data (Modul 02 Deep Dive)

Deskripsi:
Script ini mengimplementasikan parser dan execution engine independen untuk
memodelkan semantik internal Bash dalam menangani Variable Expansion,
Parameter Transformations (${VAR:-default}, ${VAR#pattern}, ${VAR//search/replace},
${VAR^^}, dll.), serta struktur data Indexed Array dan Associative Array.
"""

import re
import fnmatch
import sys
from typing import Dict, Any, Union, List

# ANSI Escape Sequences untuk formatting output terminal
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class BashExecutionEnvironment:
    """
    Memodelkan internal state runtime environment Bash:
    Menyimpan scalar variables, indexed arrays, dan associative arrays.
    """
    def __init__(self):
        self.variables: Dict[str, str] = {}
        self.indexed_arrays: Dict[str, List[str]] = {}
        self.assoc_arrays: Dict[str, Dict[str, str]] = {}

    def set_scalar(self, name: str, value: str) -> None:
        self.variables[name] = str(value)

    def set_indexed_array(self, name: str, elements: List[str]) -> None:
        self.indexed_arrays[name] = [str(x) for x in elements]

    def set_assoc_array(self, name: str, mapping: Dict[str, str]) -> None:
        self.assoc_arrays[name] = {str(k): str(v) for k, v in mapping.items()}

    def get_var_value(self, var_name: str) -> Union[str, None]:
        return self.variables.get(var_name, None)


class BashExpansionEngine:
    """
    Engine parser dan evaluator parameter expansion dengan aturan POSIX & Bash 4+.
    Mendukung slice, default fallbacks, pattern removal, substring replacement,
    dan case conversions.
    """
    def __init__(self, env: BashExecutionEnvironment):
        self.env = env

    def _glob_to_regex(self, pattern: str) -> str:
        """Mengonversi glob pattern Bash (*, ?) ke Regex standard Python."""
        return fnmatch.translate(pattern)

    def evaluate(self, expr: str) -> str:
        """
        Tokenisasi ekspresi ${...} dan parsing operator ekspansi.
        """
        if not expr.startswith("${") or not expr.endswith("}"):
            raise ValueError(f"Sintaks tidak valid: {expr}. Harus berformat '${{...}}'")

        raw = expr[2:-1]

        # 1. Array Element or Array Length Operations: ${#arr[@]}, ${arr[idx]}, ${#arr[idx]}
        array_match = re.match(r'^(#?)([a-zA-Z_][a-zA-Z0-9_]*)\[([^\]]+)\]$', raw)
        if array_match:
            is_len, name, key = array_match.groups()
            return self._handle_array_access(name, key, bool(is_len))

        # 2. String Length: ${#var}
        if raw.startswith('#') and len(raw) > 1 and not any(op in raw for op in [':', '%', '#', '/', '^', ',']):
            var_name = raw[1:]
            val = self.env.get_var_value(var_name) or ""
            return str(len(val))

        # 3. Parameter Defaults / Fallbacks
        # ${var:-default}, ${var:=assign_default}, ${var:+alternate}, ${var:?error_msg}
        fallback_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*):([-+=?])(.*)$', raw)
        if fallback_match:
            var_name, op, param = fallback_match.groups()
            return self._handle_fallback_expansion(var_name, op, param)

        # 4. Substring Extraction / Slicing: ${var:offset}, ${var:offset:length}
        substr_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*):(-?\d+)(?::(-?\d+))?$', raw)
        if substr_match:
            var_name, offset_str, length_str = substr_match.groups()
            val = self.env.get_var_value(var_name) or ""
            offset = int(offset_str)
            if length_str is not None:
                length = int(length_str)
                return val[offset:offset + length] if length >= 0 else val[offset:length]
            return val[offset:]

        # 5. Pattern Replacement: ${var//search/replace} atau ${var/search/replace}
        replace_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)(/{1,2})([^/]+)(?:/(.*))?$', raw)
        if replace_match:
            var_name, slash_op, pattern, replacement = replace_match.groups()
            replacement = replacement or ""
            val = self.env.get_var_value(var_name) or ""
            regex = self._glob_to_regex(pattern).replace('\\Z', '')
            count = 0 if slash_op == '//' else 1
            return re.sub(regex, replacement, val, count=count)

        # 6. Prefix / Suffix Trimming: ${var#pattern}, ${var##pattern}, ${var%pattern}, ${var%%pattern}
        trim_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)(##?|%%?)(.*)$', raw)
        if trim_match:
            var_name, op, pattern = trim_match.groups()
            return self._handle_trimming(var_name, op, pattern)

        # 7. Case Modification: ${var^^}, ${var^}, ${var,,}, ${var,}
        case_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)(\^{1,2}|,{1,2})$', raw)
        if case_match:
            var_name, op = case_match.groups()
            val = self.env.get_var_value(var_name) or ""
            if op == '^^':
                return val.upper()
            elif op == '^':
                return val[0].upper() + val[1:] if val else ""
            elif op == ',,':
                return val.lower()
            elif op == ',':
                return val[0].lower() + val[1:] if val else ""

        # Default: Variable scalar lookup murni ${VAR}
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', raw):
            return self.env.get_var_value(raw) or ""

        return f"<UNSUPPORTED_SYNTAX: {expr}>"

    def _handle_fallback_expansion(self, var: str, op: str, arg: str) -> str:
        """Evaluasi operator default :- , := , :+ , :?"""
        val = self.env.get_var_value(var)
        is_set_and_non_null = val is not None and len(val) > 0

        if op == '-':  # Use default if unset or null
            return val if is_set_and_non_null else arg
        elif op == '=':  # Assign default if unset or null
            if not is_set_and_non_null:
                self.env.set_scalar(var, arg)
                return arg
            return val
        elif op == '+':  # Use alternate value if set and non-null
            return arg if is_set_and_non_null else ""
        elif op == '?':  # Throw error if unset or null
            if not is_set_and_non_null:
                err_msg = arg if arg else "parameter null or not set"
                raise RuntimeError(f"Bash Execution Error: ${{{var}:?{err_msg}}}")
            return val
        return ""

    def _handle_trimming(self, var: str, op: str, pattern: str) -> str:
        """Memproses prefix removal (#/##) dan suffix removal (%/%%)."""
        val = self.env.get_var_value(var) or ""
        rgx_pattern = fnmatch.translate(pattern)

        if op == '#':  # Non-greedy prefix
            for i in range(len(val) + 1):
                if re.fullmatch(fnmatch.translate(pattern), val[:i]):
                    return val[i:]
        elif op == '##':  # Greedy prefix
            for i in range(len(val), -1, -1):
                if re.fullmatch(fnmatch.translate(pattern), val[:i]):
                    return val[i:]
        elif op == '%':  # Non-greedy suffix
            for i in range(len(val), -1, -1):
                if re.fullmatch(fnmatch.translate(pattern), val[i:]):
                    return val[:i]
        elif op == '%%':  # Greedy suffix
            for i in range(0, len(val) + 1):
                if re.fullmatch(fnmatch.translate(pattern), val[i:]):
                    return val[:i]
        return val

    def _handle_array_access(self, name: str, key: str, is_len: bool) -> str:
        """Memproses penanganan indexed & associative array Bash."""
        if name in self.env.indexed_arrays:
            arr = self.env.indexed_arrays[name]
            if key in ('@', '*'):
                return str(len(arr)) if is_len else " ".join(arr)
            try:
                idx = int(key)
                element = arr[idx] if 0 <= idx < len(arr) else ""
                return str(len(element)) if is_len else element
            except ValueError:
                return ""
        elif name in self.env.assoc_arrays:
            assoc = self.env.assoc_arrays[name]
            if key in ('@', '*'):
                return str(len(assoc)) if is_len else " ".join(assoc.values())
            element = assoc.get(key, "")
            return str(len(element)) if is_len else element
        return ""


def print_header(title: str) -> None:
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.YELLOW}[TEST-CASE] {title}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}")


def execute_test(engine: BashExpansionEngine, expression: str, note: str = "") -> None:
    """Helper runner untuk mengeksekusi ekspresi dan mencetak log berwarna terstruktur."""
    try:
        result = engine.evaluate(expression)
        print(f"  {Colors.GREEN}►{Colors.RESET} Expr : {Colors.BOLD}{expression:<30}{Colors.RESET}"
              f" Result: {Colors.HEADER}'{result}'{Colors.RESET}"
              f" {Colors.BLUE}({note}){Colors.RESET}")
    except RuntimeError as err:
        print(f"  {Colors.RED}✖{Colors.RESET} Expr : {Colors.BOLD}{expression:<30}{Colors.RESET}"
              f" Result: {Colors.RED}{err}{Colors.RESET}")


def main() -> None:
    print(f"{Colors.BOLD}{Colors.HEADER}=== LAB SIMULASI: ENGINE PARAMETER EXPANSION BASH 4.X ==={Colors.RESET}")

    env = BashExecutionEnvironment()
    engine = BashExpansionEngine(env)

    # Inisialisasi Environment Variables
    env.set_scalar("FILENAME", "production_api_service_v2.tar.gz")
    env.set_scalar("APP_ENV", "")       # Empty/Null string
    # DB_USER dibiarkan unset
    env.set_scalar("PROMPT_NAME", "lead_system_engineer")
    env.set_scalar("RAW_PATH", "/var/log/audit/syslog.log")

    # Inisialisasi Struktur Data Bash
    # Indexed Array: declare -a SERVERS=("web-01" "web-02" "db-primary" "cache-redis")
    env.set_indexed_array("SERVERS", ["web-01", "web-02", "db-primary", "cache-redis"])

    # Associative Array: declare -A PORTS=([http]=80 [https]=443 [ssh]=22)
    env.set_assoc_array("PORTS", {"http": "80", "https": "443", "ssh": "22"})

    # Demo 1: Fallback Defaults
    print_header("1. Default / Fallback Expansion (:- , := , :+ , :?)")
    execute_test(engine, "${APP_ENV:-development}", "APP_ENV kosong, fallback ke 'development'")
    execute_test(engine, "${DB_USER:-postgres}", "DB_USER unset, fallback ke 'postgres'")
    execute_test(engine, "${DB_PASS:=secret_vault_pwd}", "DB_PASS unset, assign langsung ke environment")
    execute_test(engine, "${DB_PASS}", "Verifikasi DB_PASS tersimpan di environment")
    execute_test(engine, "${FILENAME:+FileConfigured}", "FILENAME ada isinya, tampilkan alternate")
    execute_test(engine, "${MISSING_KEY:?Fatal: Variable Missing}", "Memicu error pesan exit non-nol")

    # Demo 2: String Length & Substring Slicing
    print_header("2. String Length & Slicing (${#var}, ${var:offset:len})")
    execute_test(engine, "${#FILENAME}", "Menghitung total karakter string FILENAME")
    execute_test(engine, "${FILENAME:0:10}", "Slice karakter dari offset 0 sepanjang 10")
    execute_test(engine, "${FILENAME:11:11}", "Slice karakter dari offset 11 sepanjang 11")
    execute_test(engine, "${FILENAME:15}", "Slice dari offset 15 hingga akhir string")

    # Demo 3: Pattern Removal (Prefix & Suffix Trimming)
    print_header("3. Pattern Trimming (${var#pattern}, ${var##pattern}, ${var%pattern}, ${var%%pattern})")
    execute_test(engine, "${RAW_PATH#*/}", "Non-greedy prefix removal (menghapus komponen path pertama)")
    execute_test(engine, "${RAW_PATH##*/}", "Greedy prefix removal (ekuivalen dengan command basename)")
    execute_test(engine, "${FILENAME%.*}", "Non-greedy suffix removal (hapus ekstensi terakhir: .gz)")
    execute_test(engine, "${FILENAME%%.*}", "Greedy suffix removal (hapus semua ekstensi: .tar.gz)")

    # Demo 4: Substring Replacement
    print_header("4. Substring Search & Replace (${var/search/replace}, ${var//search/replace})")
    execute_test(engine, "${FILENAME/api/core_engine}", "First match replacement")
    execute_test(engine, "${FILENAME//_/-}", "Global match replacement (semua underscore jadi strip)")

    # Demo 5: Case Conversions
    print_header("5. Case Modification (${var^^}, ${var^}, ${var,,}, ${var,})")
    execute_test(engine, "${PROMPT_NAME^^}", "Semua huruf diubah menjadi UPPERCASE")
    execute_test(engine, "${PROMPT_NAME^}", "Hanya huruf pertama diubah menjadi UPPERCASE")
    env.set_scalar("SHOUTING", "PRODUCTION_FAILURE")
    execute_test(engine, "${SHOUTING,,}", "Semua huruf diubah menjadi lowercase")

    # Demo 6: Array Data Structures (Indexed & Associative)
    print_header("6. Struktur Data Array (Indexed & Associative Data Types)")
    execute_test(engine, "${SERVERS[0]}", "Akses elemen pertama indexed array")
    execute_test(engine, "${SERVERS[2]}", "Akses elemen ketiga indexed array")
    execute_test(engine, "${#SERVERS[@]}", "Total jumlah elemen dalam indexed array")
    execute_test(engine, "${#SERVERS[2]}", "Panjang string dari elemen SERVERS[2]")
    execute_test(engine, "${SERVERS[@]}", "Ekspansi seluruh elemen indexed array")
    execute_test(engine, "${PORTS[https]}", "Akses value associative array key 'https'")
    execute_test(engine, "${#PORTS[@]}", "Total key pada associative array PORTS")

    print(f"\n{Colors.BOLD}{Colors.GREEN}✔ Eksekusi simulasi parsing bash selesai tanpa anomali runtime.{Colors.RESET}\n")


if __name__ == "__main__":
    main()
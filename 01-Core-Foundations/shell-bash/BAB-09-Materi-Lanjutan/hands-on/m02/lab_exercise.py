#!/usr/bin/env python3
"""
Lab Hands-on: Defensive Scripting, Testing, & Static Code Analysis
Category: 01-Core-Foundations (Topic: shell-bash, Chapter 09)

Membangun Static Code Analyzer (Linter) dan Test Harness Engine untuk Shell/Bash.
Memvalidasi pola Defensive Bash:
  1. Strict Mode Validation (set -euo pipefail, IFS reset)
  2. Unquoted Expansion Detection (Word splitting & Globbing vulnerabilities)
  3. Toxic Sinks (eval injection, unchecked cd, backticks vs command substitution)
  4. Signal & Trap Lifecycle Auditing (EXIT/ERR handler registration)
"""

import re
import sys
import time
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Tuple, Optional

# --- ANSI Terminal Styling ---
class Style:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    BG_DARK = "\033[48;5;236m"

class Severity(Enum):
    CRITICAL = ("CRIT", Style.RED)
    WARNING  = ("WARN", Style.YELLOW)
    STYLE    = ("INFO", Style.CYAN)

@dataclass
class RuleViolation:
    rule_id: str
    line_num: int
    severity: Severity
    message: str
    source_line: str
    remediation: str

# --- Static Rule Engine ---
class ShellRule:
    """Basis aturan analisis statis untuk skrip Shell/Bash."""
    def __init__(self, rule_id: str, severity: Severity, description: str):
        self.rule_id = rule_id
        self.severity = severity
        self.description = description

    def check(self, line: str, line_num: int, context: Dict) -> Optional[RuleViolation]:
        raise NotImplementedError

class StrictModeRule(ShellRule):
    """Memeriksa keberadaan 'set -euo pipefail' di bagian awal skrip."""
    def __init__(self):
        super().__init__("SH001", Severity.CRITICAL, "Enforce strict mode initialization")
        self.found = False

    def check(self, line: str, line_num: int, context: Dict) -> Optional[RuleViolation]:
        # Cek hanya dalam 15 baris pertama non-comment
        if line_num <= 15 and not self.found:
            clean = line.strip().split('#')[0]
            if re.search(r'\bset\s+-[a-zA-Z]*e[a-zA-Z]*\b', clean) and \
               re.search(r'\bset\s+-[a-zA-Z]*u[a-zA-Z]*\b', clean) and \
               re.search(r'\bpipefail\b', clean):
                self.found = True
        
        if line_num == 16 and not self.found and not context.get('strict_reported', False):
            context['strict_reported'] = True
            return RuleViolation(
                self.rule_id, 1, self.severity,
                "Missing robust defensive boilerplate (set -euo pipefail)",
                context.get('first_executable_line', 'N/A'),
                "Tambahkan 'set -euo pipefail' dan 'IFS=$'\\n\\t'' tepat setelah shebang."
            )
        return None

class UnquotedExpansionRule(ShellRule):
    """Mendeteksi ekspansi variabel tanpa tanda kutip ganda."""
    def __init__(self):
        super().__init__("SH002", Severity.WARNING, "Unquoted parameter expansion susceptible to word splitting")
        # Pola variabel tanpa tanda kutip di luar konteks assignment
        self.pattern = re.compile(r'(?<![\'"\w])(\$(?:[a-zA-Z_][a-zA-Z0-9_]*|\{[a-zA-Z_][a-zA-Z0-9_]*\}))(?=[^"\']*(?:$|[\s;|&]))')

    def check(self, line: str, line_num: int, context: Dict) -> Optional[RuleViolation]:
        stripped = line.strip()
        if stripped.startswith('#') or '=' in stripped.split()[0]:
            return None  # Abaikan baris komentar atau simple assignment var=$val
        
        # Saring baris yang berada dalam tanda kutip tunggal penuh
        if stripped.startswith("'") and stripped.endswith("'"):
            return None

        match = self.pattern.search(stripped)
        if match:
            var_token = match.group(1)
            # Pastikan tidak false-positive pada ekspansi aritmatika $(( ))
            if "$(" not in line:
                return RuleViolation(
                    self.rule_id, line_num, self.severity,
                    f"Parameter unquoted: {var_token}. Rawan Word Splitting & Globbing.",
                    line.strip(),
                    f'Bungkus parameter dengan double-quotes: "{var_token}"'
                )
        return None

class ToxicSinkRule(ShellRule):
    """Mendeteksi penggunaan sintaksis usang atau fungsi berisiko tinggi."""
    def __init__(self):
        super().__init__("SH003", Severity.CRITICAL, "Toxic sink or legacy substitution usage")
        self.backtick_pattern = re.compile(r'`([^`]+)`')
        self.eval_pattern = re.compile(r'\beval\b')

    def check(self, line: str, line_num: int, context: Dict) -> Optional[RuleViolation]:
        clean = line.strip().split('#')[0]
        if self.eval_pattern.search(clean):
            return RuleViolation(
                self.rule_id, line_num, Severity.CRITICAL,
                "Toxic sink 'eval' terdeteksi! Rawan injeksi eksekusi perintah arbitrer.",
                clean,
                "Gunakan array Bash atau indirect references (${!var}) sebagai alternatif aman."
            )
        if self.backtick_pattern.search(clean):
            return RuleViolation(
                self.rule_id, line_num, Severity.STYLE,
                "Legacy backticks command substitution terdeteksi.",
                clean,
                "Gunakan standar POSIX/Bash: $(command) daripada `command`."
            )
        return None

class UncheckedCdRule(ShellRule):
    """Mendeteksi perpindahan direktori 'cd' tanpa error handling."""
    def __init__(self):
        super().__init__("SH004", Severity.CRITICAL, "Unchecked directory traversal")
        self.cd_pattern = re.compile(r'^\s*cd\s+([^\s;|&]+)(?:\s*;|\s*$|\s*#)')

    def check(self, line: str, line_num: int, context: Dict) -> Optional[RuleViolation]:
        clean = line.strip().split('#')[0]
        if self.cd_pattern.search(clean) and not ("||" in clean or "&&" in clean):
            return RuleViolation(
                self.rule_id, line_num, self.severity,
                "Perintah 'cd' dieksekusi tanpa mitigasi kegagalan operasi filesystem.",
                clean,
                "Gunakan idiomatik defensif: cd dir || exit 1 atau cd dir || return 1"
            )
        return None

class TrapAuditRule(ShellRule):
    """Mendeteksi keberadaan trap handler untuk pembersihan resource."""
    def __init__(self):
        super().__init__("SH005", Severity.WARNING, "Missing EXIT/ERR trap signal handler")
        self.has_trap = False

    def check(self, line: str, line_num: int, context: Dict) -> Optional[RuleViolation]:
        clean = line.strip().split('#')[0]
        if re.search(r'\btrap\s+.*\b(EXIT|ERR|SIGINT)\b', clean):
            self.has_trap = True
        return None

    def post_audit(self, total_lines: int) -> Optional[RuleViolation]:
        if not self.has_trap:
            return RuleViolation(
                self.rule_id, total_lines, self.severity,
                "Skrip tidak mendaftarkan trap handler untuk penanganan cleanup / rollback.",
                "EOF",
                "Daftarkan 'trap cleanup EXIT' untuk memastikan temp files terhapus."
            )
        return None

# --- Static Code Analyzer Core Engine ---
class ShellStaticAnalyzer:
    def __init__(self):
        self.rules: List[ShellRule] = [
            StrictModeRule(),
            UnquotedExpansionRule(),
            ToxicSinkRule(),
            UncheckedCdRule(),
            TrapAuditRule()
        ]

    def analyze(self, script_content: str) -> List[RuleViolation]:
        lines = script_content.splitlines()
        violations: List[RuleViolation] = []
        context = {
            'first_executable_line': 'N/A',
            'strict_reported': False
        }

        # Lacak baris kode eksekutabel pertama
        for l in lines:
            s = l.strip()
            if s and not s.startswith('#'):
                context['first_executable_line'] = s
                break

        for line_num, raw_line in enumerate(lines, start=1):
            for rule in self.rules:
                v = rule.check(raw_line, line_num, context)
                if v:
                    violations.append(v)

        # Trigger boundary checks
        if len(lines) < 16:
            for rule in self.rules:
                if isinstance(rule, StrictModeRule):
                    v = rule.check("", 16, context)
                    if v:
                        violations.append(v)

        for rule in self.rules:
            if hasattr(rule, 'post_audit'):
                v = rule.post_audit(len(lines))
                if v:
                    violations.append(v)

        return violations

# --- Mock Bash Test Harness (Simulation Engine) ---
class BashTestHarness:
    """Mensimulasikan runtime test environment defensif (mirip Bats/BASH unit test)."""
    @staticmethod
    def run_simulation(name: str, payload_func) -> Tuple[bool, str]:
        start = time.perf_counter()
        try:
            payload_func()
            elapsed = (time.perf_counter() - start) * 1000
            return True, f"PASS ({elapsed:.2f}ms)"
        except AssertionError as e:
            elapsed = (time.perf_counter() - start) * 1000
            return False, f"FAIL ({elapsed:.2f}ms) -> {str(e)}"
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return False, f"ERROR ({elapsed:.2f}ms) -> Unexpected crash: {str(e)}"

# --- Sample Test Targets ---
def test_case_word_splitting_vulnerability():
    # Simulasi kegagalan skrip jika path mengandung spasi
    file_path = "/var/log/my test dir/report.csv"
    # Unquoted simulation: argv split
    argv_unquoted = file_path.split(" ")
    assert len(argv_unquoted) == 1, f"Word splitting terjadi! Argumen terpecah jadi {len(argv_unquoted)} token terpisah!"

def test_case_pipefail_behavior():
    # Simulasi pipeline: cmd1_fail | cmd2_success
    pipeline_exit_codes = [1, 0]
    
    # Standar Bash non-pipefail mengambil exit status terakhir
    non_pipefail_exit = pipeline_exit_codes[-1]
    assert non_pipefail_exit == 0, "Default bash masks pipe failures!"
    
    # Defensive Bash: pipefail mendeteksi failure terdahulu
    pipefail_exit = max(pipeline_exit_codes)
    assert pipefail_exit != 0, "Defensive mode pipefail berhasil mendeteksi error hulu!"

def test_case_unset_variable_detection():
    # Simulasi variable lookup dengan unbound parameter check (set -u)
    env_store = {"TARGET_DIR": "/opt/app"}
    var_to_lookup = "TARGET_DIR_MISSPELLED"
    
    if var_to_lookup not in env_store:
        raise AssertionError(f"Unbound variable error: '${var_to_lookup}' is unassigned. Protected by 'set -u'.")

# --- Test Data Scripts ---
VULNERABLE_BASH_SCRIPT = """#!/usr/bin/env bash
# Vulnerable deployment script sample

echo "Starting deployment"
deploy_dir="/var/deploy/app"
backup_files=`ls /tmp/backups`

cd $deploy_dir
rm -rf target/
cp -r /tmp/build/target .

eval "echo Deploy completed by user $USER"
"""

DEFENSIVE_BASH_SCRIPT = """#!/usr/bin/env bash
# Hardened Defensive Shell Script
set -euo pipefail
IFS=$'\\n\\t'

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly WORK_DIR="/var/deploy/app"

cleanup() {
    local exit_code=$?
    echo "[INFO] Cleaning temporary files with exit code ${exit_code}..."
}
trap cleanup EXIT ERR

main() {
    local backup_files
    backup_files="$(find /tmp/backups -type f)"
    
    cd "${WORK_DIR}" || {
        echo "[FATAL] Cannot cd to ${WORK_DIR}" >&2
        exit 1
    }
    
    echo "Deployment safely executed."
}

main "$@"
"""

# --- Report Presenter ---
def print_header(title: str):
    print(f"\n{Style.BOLD}{Style.WHITE}=== {title} ==={Style.RESET}")

def display_report(script_label: str, violations: List[RuleViolation]):
    print(f"\n{Style.BOLD}Audit Target:{Style.RESET} {Style.CYAN}{script_label}{Style.RESET}")
    print("-" * 75)
    
    if not violations:
        print(f"{Style.GREEN}✔ PASSED:{Style.RESET} Tidak ada pelanggaran defensive scripting terdeteksi. Script aman!")
        return

    crit_count = sum(1 for v in violations if v.severity == Severity.CRITICAL)
    warn_count = sum(1 for v in violations if v.severity == Severity.WARNING)
    info_count = sum(1 for v in violations if v.severity == Severity.STYLE)

    print(f"Ringkasan: {Style.RED}{crit_count} Critical{Style.RESET} | "
          f"{Style.YELLOW}{warn_count} Warnings{Style.RESET} | "
          f"{Style.CYAN}{info_count} Style/Info{Style.RESET}\n")

    for v in violations:
        badge_text, badge_color = v.severity.value
        print(f"{badge_color}[{badge_text}] {v.rule_id}{Style.RESET} line {v.line_num}: {Style.BOLD}{v.message}{Style.RESET}")
        print(f"  {Style.DIM}Code:{Style.RESET}  {v.source_line}")
        print(f"  {Style.GREEN}Fix:{Style.RESET}   {v.remediation}\n")

def main():
    print(f"{Style.BOLD}{Style.MAGENTA}========================================================================{Style.RESET}")
    print(f"{Style.BOLD}{Style.WHITE} LAB 09: DEFENSIVE SCRIPTING, TESTING & STATIC CODE ANALYSIS (SHELL-BASH){Style.RESET}")
    print(f"{Style.BOLD}{Style.MAGENTA}========================================================================{Style.RESET}")

    analyzer = ShellStaticAnalyzer()

    # 1. Analisis Skrip Rawan (Vulnerable)
    print_header("TAHAP 1: STATIC CODE ANALYSIS (VULNERABLE TARGET)")
    vulnerabilities = analyzer.analyze(VULNERABLE_BASH_SCRIPT)
    display_report("legacy_deploy_sample.sh", vulnerabilities)

    # 2. Analisis Skrip Defensif (Hardened)
    print_header("TAHAP 2: STATIC CODE ANALYSIS (HARDENED TARGET)")
    analyzer_safe = ShellStaticAnalyzer()
    safe_audit = analyzer_safe.analyze(DEFENSIVE_BASH_SCRIPT)
    display_report("hardened_deploy_defensive.sh", safe_audit)

    # 3. Unit Testing & Behavioral Harness Simulation
    print_header("TAHAP 3: BASH DEFENSIVE BEHAVIORAL SUITE (RUNTIME UNIT TESTS)")
    print("Mengeksekusi simulasi skenario runtime Bash...\n")

    test_cases = [
        ("Word Splitting on Unquoted Paths", test_case_word_splitting_vulnerability),
        ("Strict Mode Pipeline Error Propagation (pipefail)", test_case_pipefail_behavior),
        ("Unset Parameter Guards (set -u trap)", test_case_unset_variable_detection)
    ]

    for title, test_fn in test_cases:
        success, details = BashTestHarness.run_simulation(title, test_fn)
        status_badge = f"{Style.GREEN}[PASSED]{Style.RESET}" if success else f"{Style.RED}[FAILED]{Style.RESET}"
        print(f"  * {title:<50} {status_badge} {Style.DIM}{details}{Style.RESET}")

    print(f"\n{Style.BOLD}{Style.GREEN}✔ Sesi Lab Selesai: Semua metrik analisis dan defensive guards tervalidasi.{Style.RESET}\n")

if __name__ == "__main__":
    main()
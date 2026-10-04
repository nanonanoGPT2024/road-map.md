#!/usr/bin/env python3
"""
Lab Exercise: Hands-on Text Processing Simulation (Grep, Sed, Awk)
BAB 06: Advanced Text Processing - Sed, Awk, Grep
Course: Shell & Bash Fundamentals

Simulasi interaktif konsep pipeline Unix text processing menggunakan Python 3 murni
dengan pewarnaan ANSI terminal dan demonstrasi step-by-step.
"""

import sys
import re
import time
from typing import List, Dict, Any, Tuple

# ================= ANSI Color Codes =================
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
BG_DARK = "\033[40m"

# ================= Sample Dataset (Nginx Access Log & System Metrics) =================
SAMPLE_LOGS: List[str] = [
    '192.168.1.10 - - [05/Oct/2026:10:00:15 +0700] "GET /api/v1/users HTTP/1.1" 200 4523 0.045',
    '192.168.1.25 - - [05/Oct/2026:10:00:16 +0700] "POST /api/v1/auth/login HTTP/1.1" 401 128 0.120',
    '10.0.0.5 - - [05/Oct/2026:10:00:18 +0700] "GET /index.html HTTP/1.1" 200 12540 0.012',
    '192.168.1.25 - - [05/Oct/2026:10:00:19 +0700] "POST /api/v1/auth/login HTTP/1.1" 200 512 0.230',
    '172.16.0.99 - - [05/Oct/2026:10:00:20 +0700] "GET /admin/dashboard HTTP/1.1" 403 89 0.005',
    '192.168.1.50 - - [05/Oct/2026:10:00:22 +0700] "GET /api/v1/orders HTTP/1.1" 500 245 1.450',
    '10.0.0.12 - - [05/Oct/2026:10:00:23 +0700] "GET /api/v1/orders HTTP/1.1" 200 8920 0.088',
    '192.168.1.50 - - [05/Oct/2026:10:00:25 +0700] "GET /static/app.js HTTP/1.1" 304 0 0.002',
    '172.16.0.88 - - [05/Oct/2026:10:00:27 +0700] "DELETE /api/v1/cache HTTP/1.1" 204 0 0.035',
    '192.168.1.10 - - [05/Oct/2026:10:00:30 +0700] "GET /api/v1/reports HTTP/1.1" 504 512 5.002',
]

CSV_METRICS: List[str] = [
    "server,cpu_pct,mem_mb,disk_pct,status",
    "prod-web-01,78.5,4096,65,healthy",
    "prod-web-02,94.2,7890,92,critical",
    "prod-api-01,45.0,2048,40,healthy",
    "prod-api-02,88.1,6144,85,warning",
    "prod-db-01,92.4,16384,78,critical",
    "prod-db-02,32.0,8192,55,healthy",
]


def print_banner() -> None:
    """Menampilkan banner header CLI."""
    print(f"{CYAN}{BOLD}{'=' * 75}{RESET}")
    print(f"{BG_BLUE}{WHITE}{BOLD}   LAB WORKSHOP: SIMULASI GREP, SED, & AWK (UNIX TEXT STREAM)            {RESET}")
    print(f"{CYAN}{BOLD}{'=' * 75}{RESET}")
    print(f"{DIM}Materi: BAB-06 Advanced Text Processing - Sed, Awk, Grep{RESET}\n")


# ================= 1. GREP ENGINE SIMULATION =================
def simulate_grep(lines: List[str], pattern: str, invert: bool = False, count_only: bool = False) -> None:
    """
    Simulasi grep:
    grep [-v] [-c] 'pattern'
    """
    cmd_str = f"grep {'-v ' if invert else ''}{'-c ' if count_only else ''}'{pattern}'"
    print(f"{YELLOW}{BOLD}[GREP SIMULATOR]{RESET} Running command: {CYAN}{cmd_str}{RESET}")
    print(f"{DIM}{'-' * 70}{RESET}")

    regex = re.compile(pattern)
    matched_lines: List[Tuple[int, str]] = []

    for idx, line in enumerate(lines, 1):
        has_match = bool(regex.search(line))
        is_selected = not has_match if invert else has_match
        if is_selected:
            matched_lines.append((idx, line))

    if count_only:
        print(f"{GREEN}{BOLD}Match Count:{RESET} {len(matched_lines)}")
        return

    for line_no, line in matched_lines:
        if invert:
            highlighted = f"{line}"
        else:
            # Highlight matching tokens with red bold background
            highlighted = regex.sub(lambda m: f"{RED}{BOLD}{m.group(0)}{RESET}", line)
        print(f"{DIM}{line_no:02d}:{RESET} {highlighted}")

    print(f"\n{GREEN}Total Selected Lines:{RESET} {len(matched_lines)} / {len(lines)}")


# ================= 2. SED ENGINE SIMULATION =================
def simulate_sed(lines: List[str], command_type: str, search_pattern: str, replacement: str = "") -> None:
    """
    Simulasi sed:
    s/old/new/g (substitute) atau /pattern/d (delete)
    """
    if command_type == "substitute":
        cmd_str = f"sed 's/{search_pattern}/{replacement}/g'"
    elif command_type == "delete":
        cmd_str = f"sed '/{search_pattern}/d'"
    else:
        cmd_str = "sed unknown"

    print(f"{MAGENTA}{BOLD}[SED SIMULATOR]{RESET} Running stream editor: {CYAN}{cmd_str}{RESET}")
    print(f"{DIM}{'-' * 70}{RESET}")

    regex = re.compile(search_pattern)
    result_stream: List[str] = []

    for idx, line in enumerate(lines, 1):
        if command_type == "delete":
            if regex.search(line):
                print(f"{RED}[DELETED LINE {idx:02d}]{RESET} {DIM}{line}{RESET}")
                continue
            result_stream.append(line)
            print(f"{DIM}{idx:02d}:{RESET} {line}")

        elif command_type == "substitute":
            if regex.search(line):
                modified = regex.sub(f"{GREEN}{BOLD}{replacement}{RESET}", line)
                print(f"{DIM}{idx:02d}:{RESET} {modified}")
                result_stream.append(regex.sub(replacement, line))
            else:
                print(f"{DIM}{idx:02d}:{RESET} {line}")
                result_stream.append(line)

    print(f"\n{GREEN}Stream processing selesai.{RESET} Total lines in output: {len(result_stream)}")


# ================= 3. AWK ENGINE SIMULATION =================
def simulate_awk_aggregation(csv_data: List[str], filter_col: str, threshold: float) -> None:
    """
    Simulasi awk conditional processing dan akumulator:
    awk -F',' '$2 > threshold { count++; sum+=$2; print } END { print count, sum/count }'
    """
    print(f"{BLUE}{BOLD}[AWK SIMULATOR]{RESET} Aggregation & Column Slicing")
    print(f"{CYAN}awk -F',' '${filter_col} > {threshold} {{ count++; print $1, ${filter_col}, $5 }} END {{ ... }}'{RESET}")
    print(f"{DIM}{'-' * 70}{RESET}")

    header = [h.strip() for h in csv_data[0].split(",")]
    col_idx = 1 if filter_col in ["2", "cpu_pct"] else 3

    print(f"{BOLD}{'SERVER NAME':<16} {'CPU/METRIC':<12} {'STATUS':<10}{RESET}")
    print(f"{DIM}{'-' * 40}{RESET}")

    count = 0
    total_val = 0.0

    for line in csv_data[1:]:
        fields = [f.strip() for f in line.split(",")]
        val = float(fields[col_idx])
        if val > threshold:
            count += 1
            total_val += val
            status_color = RED if fields[4] == "critical" else YELLOW
            print(f"{WHITE}{fields[0]:<16}{RESET} {CYAN}{val:>6.1f}%{RESET}     {status_color}{fields[4]:<10}{RESET}")

    avg_val = (total_val / count) if count > 0 else 0.0
    print(f"{DIM}{'-' * 40}{RESET}")
    print(f"{GREEN}{BOLD}[END BLOCK STATS]{RESET}")
    print(f"Matched Nodes : {count}")
    print(f"Average Metric: {avg_val:.2f}%")


# ================= 4. COMBINED PIPELINE CHALLENGE =================
def run_pipeline_demo() -> None:
    """
    Simulasi pipeline unix:
    cat logs | grep -v '304' | sed 's/HTTP\/1\.1//g' | awk '{print $1, $9, $NF}'
    """
    print(f"{GREEN}{BOLD}[UNIX PIPELINE COMBO]{RESET}")
    print(f"{YELLOW}cat access.log | grep -E ' (40[0-9]|50[0-9]) ' | awk '{{print $1, $7, $9}}'{RESET}")
    print(f"{DIM}Tujuan: Filter error log (status 4xx / 5xx) dan tampilkan IP + Endpoint + HTTP Code{RESET}")
    print(f"{DIM}{'-' * 70}{RESET}")

    err_regex = re.compile(r'\s(4\d{2}|5\d{2})\s')

    print(f"{BOLD}{'CLIENT IP':<18} {'STATUS':<8} {'ENDPOINT'}{RESET}")
    print(f"{DIM}{'-' * 60}{RESET}")

    for raw in SAMPLE_LOGS:
        match = err_regex.search(raw)
        if match:
            status_code = match.group(1)
            parts = raw.split('"')
            client_ip = raw.split()[0]
            request_part = parts[1] if len(parts) > 1 else ""
            endpoint = request_part.split()[1] if len(request_part.split()) > 1 else "-"

            code_color = RED if status_code.startswith("5") else YELLOW
            print(f"{CYAN}{client_ip:<18}{RESET} {code_color}{status_code:<8}{RESET} {WHITE}{endpoint}{RESET}")


# ================= 5. INTERACTIVE CLI LAB MENU =================
def main() -> None:
    print_banner()

    menu_options = {
        "1": "Simulasi Grep: Filter HTTP Status Error (regex matching)",
        "2": "Simulasi Grep: Invert match (-v) & Count (-c)",
        "3": "Simulasi Sed: Anonymize IP address (stream replace)",
        "4": "Simulasi Sed: Strip sensitive endpoints (pattern delete)",
        "5": "Simulasi Awk: Filter server CPU > 75% & Hitung Rata-rata",
        "6": "Simulasi Unix Pipeline (Grep + Sed + Awk)",
        "7": "Jalankan Semua Demonstrasi",
        "0": "Keluar",
    }

    while True:
        print(f"\n{BOLD}Pilih Modul Latihan:{RESET}")
        for key, desc in menu_options.items():
            print(f"  {CYAN}[{key}]{RESET} {desc}")

        try:
            choice = input(f"\n{GREEN}Masukkan opsi [0-7]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}Program dihentikan oleh user.{RESET}")
            sys.exit(0)

        print()

        if choice == "1":
            simulate_grep(SAMPLE_LOGS, pattern=r'" [45]\d{2} ')
        elif choice == "2":
            print(f"{BOLD}Step 2A: grep -v (exclude 200 OK){RESET}")
            simulate_grep(SAMPLE_LOGS, pattern=r' 200 ', invert=True)
            print(f"\n{BOLD}Step 2B: grep -c (hitung request ke /api/v1/auth){RESET}")
            simulate_grep(SAMPLE_LOGS, pattern=r'/auth/', count_only=True)
        elif choice == "3":
            simulate_sed(
                SAMPLE_LOGS,
                command_type="substitute",
                search_pattern=r'192\.168\.1\.\d+',
                replacement='10.10.10.xxx'
            )
        elif choice == "4":
            simulate_sed(
                SAMPLE_LOGS,
                command_type="delete",
                search_pattern=r'/admin|/cache'
            )
        elif choice == "5":
            simulate_awk_aggregation(CSV_METRICS, filter_col="cpu_pct", threshold=75.0)
        elif choice == "6":
            run_pipeline_demo()
        elif choice == "7":
            print(f"{YELLOW}--- Menjalankan Seluruh Modul Latihan ---{RESET}\n")
            simulate_grep(SAMPLE_LOGS, pattern=r'" [45]\d{2} ')
            time.sleep(0.5)
            print()
            simulate_sed(SAMPLE_LOGS, command_type="substitute", search_pattern=r'192\.168\.1\.\d+', replacement='10.10.10.xxx')
            time.sleep(0.5)
            print()
            simulate_awk_aggregation(CSV_METRICS, filter_col="cpu_pct", threshold=75.0)
            time.sleep(0.5)
            print()
            run_pipeline_demo()
        elif choice == "0":
            print(f"{GREEN}Lab selesai. Selamat belajar text processing!{RESET}")
            break
        else:
            print(f"{RED}Opsi tidak valid, silakan coba lagi.{RESET}")


if __name__ == "__main__":
    main()

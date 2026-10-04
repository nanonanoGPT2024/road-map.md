#!/usr/bin/env python3
"""
Lab Hands-on: Shell-Bash - Deep Dive Logika Kontrol, Arithmetic, & Evaluasi Kondisi
Modul: 01-Core-Foundations / Bab 04

Script ini memodelkan dan mengeksekusi mesin simulasi internal evaluasi kondisi Bash:
1. Perbedaan semantik '[' (POSIX test builtin) vs '[[' (Bash conditional compound keyword).
2. Semantik aritmatika Bash '(( ))' & '$(( ))' beserta konversi nilai ke exit status ($?).
3. Logika percabangan, short-circuit evaluasi (&& dan ||), dan pattern/regex matching.
"""

import sys
import re
import time
from typing import List, Dict, Tuple, Any, Optional

# ANSI Escape Codes untuk formatting terminal
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"


class BashExecutionError(Exception):
    """Exception khusus merepresentasikan error runtime Bash seperti 'unary operator expected'."""
    pass


class BashArithmeticContext:
    """
    Simulasi konteks evaluasi aritmatika Bash (( ... )).
    Aturan Bash:
    - Ekspresi bernilai integer bukan-nol menghasilkan exit status 0 (Success/True).
    - Ekspresi bernilai 0 menghasilkan exit status 1 (Failure/False).
    - Mendukung operator C-style standar: +, -, *, /, %, pre/post-increment, ternary.
    """
    def __init__(self, variables: Optional[Dict[str, int]] = None):
        self.vars: Dict[str, int] = variables if variables is not None else {}

    def eval_expr(self, expr: str) -> Tuple[int, int]:
        """
        Mengevaluasi ekspresi aritmatika string.
        Mengembalikan tuple: (hasil_kalkulasi, bash_exit_code)
        """
        clean_expr = expr.strip()
        
        # Resolusi substitusi variabel lokal
        tokens = re.split(r'(\b[a-zA-Z_][a-zA-Z0-9_]*\b)', clean_expr)
        resolved_tokens = []
        for token in tokens:
            if token.isidentifier():
                resolved_tokens.append(str(self.vars.get(token, 0)))
            else:
                resolved_tokens.append(token)
        
        resolved_expr = "".join(resolved_tokens)

        try:
            # Gunakan restricted environment untuk evaluasi matematis murni
            result = int(eval(resolved_expr, {"__builtins__": {}}, {}))
        except ZeroDivisionError:
            raise BashExecutionError("division by 0 (error token is \"0\")")
        except Exception as e:
            raise BashExecutionError(f"syntax error in arithmetic expression: {resolved_expr} ({e})")

        # Logika Inti Bash: Non-zero = Exit Code 0 (Success), Zero = Exit Code 1 (Fail)
        bash_exit_code = 0 if result != 0 else 1
        return result, bash_exit_code


class BashConditionalContext:
    """
    Simulasi evaluator kondisi Bash:
    - Klasik POSIX '[' / 'test': Sensitif terhadap unquoted variables (word splitting).
    - Modern Bash '[[': Aman terhadap empty strings, mendukung regex (=~) & glob (*).
    """

    @staticmethod
    def evaluate_posix_test(tokens: List[Optional[str]]) -> int:
        """
        Simulasi '[': Jika variabel kosong tidak di-quote, shell melakukan word-splitting
        dan menghapus token tersebut, memicu 'unary operator expected' atau 'too many arguments'.
        """
        # Filter token None yang merepresentasikan variabel tak di-quote yang kosong
        flattened: List[str] = [t for t in tokens if t is not None]

        arg_count = len(flattened)

        if arg_count == 0:
            return 1  # [ ] returns 1
        elif arg_count == 1:
            # [ string ] -> True jika string tidak kosong
            return 0 if flattened[0] != "" else 1
        elif arg_count == 2:
            op, val = flattened[0], flattened[1]
            if op == "-z":
                return 0 if len(val) == 0 else 1
            elif op == "-n":
                return 0 if len(val) > 0 else 1
            raise BashExecutionError(f"[: {op}: unary operator expected")
        elif arg_count == 3:
            left, op, right = flattened[0], flattened[1], flattened[2]
            if op in ("=", "=="):
                return 0 if left == right else 1
            elif op == "!=":
                return 0 if left != right else 1
            elif op == "-eq":
                return 0 if int(left) == int(right) else 1
            elif op == "-ne":
                return 0 if int(left) != int(right) else 1
            elif op == "-gt":
                return 0 if int(left) > int(right) else 1
            elif op == "-lt":
                return 0 if int(left) < int(right) else 1
            raise BashExecutionError(f"[: {op}: unknown operator")
        else:
            raise BashExecutionError(f"[: too many arguments (count: {arg_count})")

    @staticmethod
    def evaluate_bash_double_bracket(left: str, op: str, right: str) -> int:
        """
        Simulasi '[[': Menjamin argument preservation, mendukung regex operator '=~'
        dan wildcards matching '*'.
        """
        # Operator perbandingan string / regex
        if op in ("==", "="):
            # Simulasi glob pattern matching sederhana (* wildcard)
            pattern = "^" + re.escape(right).replace(r"\*", ".*") + "$"
            match = re.match(pattern, left)
            return 0 if match else 1
        elif op == "!=":
            pattern = "^" + re.escape(right).replace(r"\*", ".*") + "$"
            match = re.match(pattern, left)
            return 1 if match else 0
        elif op == "=~":
            # Extended regular expression matching
            try:
                match = re.search(right, left)
                return 0 if match is not None else 1
            except re.error as e:
                raise BashExecutionError(f"[[: invalid regular expression: {e}")
        elif op in ("-eq", "-ne", "-lt", "-le", "-gt", "-ge"):
            # Evaluasi integer aman
            il = int(left) if left.strip() else 0
            ir = int(right) if right.strip() else 0
            if op == "-eq": return 0 if il == ir else 1
            if op == "-ne": return 0 if il != ir else 1
            if op == "-lt": return 0 if il < ir else 1
            if op == "-le": return 0 if il <= ir else 1
            if op == "-gt": return 0 if il > ir else 1
            if op == "-ge": return 0 if il >= ir else 1
        raise BashExecutionError(f"[[: operator unsupported: {op}")


class PipelineFlowController:
    """
    Mensimulasikan eksekusi chaining pipeline Bash: 'CMD1 && CMD2 || CMD3'
    Menganalisis Short-Circuit Evaluation & Exit Codes ($?).
    """
    def __init__(self):
        self.last_exit_code = 0

    def run_chain(self, steps: List[Tuple[str, str, Any]]) -> None:
        """
        steps: list of tuples -> (conditional_gate: 'START'|'&&'|'||', label, callable)
        """
        print(f"{CLR_BOLD}Mengeksekusi Chaining Logic Flow...{CLR_RESET}")
        
        for gate, label, action in steps:
            execute = False
            if gate == "START":
                execute = True
            elif gate == "&&":
                execute = (self.last_exit_code == 0)
            elif gate == "||":
                execute = (self.last_exit_code != 0)

            status_str = f"GATE: {gate:<5} (Last $?={self.last_exit_code})"
            if execute:
                try:
                    self.last_exit_code = action()
                    result_color = CLR_GREEN if self.last_exit_code == 0 else CLR_RED
                    print(f"  {CLR_CYAN}[EXEC]{CLR_RESET}  {status_str} -> {label} | Exit: {result_color}{self.last_exit_code}{CLR_RESET}")
                except BashExecutionError as err:
                    self.last_exit_code = 2
                    print(f"  {CLR_RED}[CRASH]{CLR_RESET} {status_str} -> {label} | Bash Error: {err}")
            else:
                print(f"  {CLR_YELLOW}[SKIP]{CLR_RESET}  {status_str} -> {label} (Short-circuited)")


def print_header(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_BLUE}{'=' * 75}")
    print(f"  {title.upper()}")
    print(f"{'=' * 75}{CLR_RESET}\n")


def lab_test_posix_vs_modern():
    print_header("Test 1: POSIX '[' vs Modern Bash '[[' Variable Expansion Gotchas")
    
    empty_unquoted = None      # Representasi unquoted empty var: $EMPTY_VAR
    empty_quoted = ""          # Representasi quoted empty var: "$EMPTY_VAR"
    valid_string = "production.srv.internal"

    # Skenario 1: [ $EMPTY_VAR = "production" ] -> Shell expands to: [ = "production" ]
    print(f"{CLR_BOLD}Kasus 1: Evaluasi POSIX '[' tanpa quotes: [ $EMPTY_VAR = 'production' ]{CLR_RESET}")
    try:
        BashConditionalContext.evaluate_posix_test([empty_unquoted, "=", "production"])
        print(f"  {CLR_GREEN}Passed secara anomali.{CLR_RESET}")
    except BashExecutionError as e:
        print(f"  {CLR_RED}Expected Failure Tertangkap:{CLR_RESET} {e}")
        print(f"  {CLR_YELLOW}Penjelasan:{CLR_RESET} Word splitting menghapus variabel kosong, menggeser '=' ke posisi arg-1.\n")

    # Skenario 2: [ "$EMPTY_VAR" = "production" ] -> Shell expands to: [ "" = "production" ]
    print(f"{CLR_BOLD}Kasus 2: Evaluasi POSIX '[' dengan quotes: [ \"$EMPTY_VAR\" = 'production' ]{CLR_RESET}")
    rc = BashConditionalContext.evaluate_posix_test([empty_quoted, "=", "production"])
    status = f"{CLR_GREEN}False (Exit 1){CLR_RESET}" if rc == 1 else f"{CLR_RED}True (Exit 0){CLR_RESET}"
    print(f"  Hasil Evaluasi: {status} (Aman karena quotes menjaga token argv)\n")

    # Skenario 3: [[ $EMPTY_VAR == "production" ]] -> Compound keyword bash tidak melakukan word-splitting
    print(f"{CLR_BOLD}Kasus 3: Modern Double Bracket: [[ $EMPTY_VAR == 'production' ]]{CLR_RESET}")
    rc_double = BashConditionalContext.evaluate_bash_double_bracket("" if empty_unquoted is None else empty_unquoted, "==", "production")
    print(f"  Hasil Evaluasi: {CLR_GREEN}Exit code: {rc_double}{CLR_RESET} (Double bracket aman tanpa quoting internal)\n")

    # Skenario 4: Regex validation dengan [[ $HOST =~ pattern ]]
    print(f"{CLR_BOLD}Kasus 4: Pattern & Regex Evaluation pada '[[': [[ '{valid_string}' =~ ^[a-z]+\\.srv\\.[a-z]+$ ]]{CLR_RESET}")
    regex_pattern = r"^[a-z]+\.srv\.[a-z]+$"
    rc_regex = BashConditionalContext.evaluate_bash_double_bracket(valid_string, "=~", regex_pattern)
    print(f"  Regex Match Status: {'COCOK (0)' if rc_regex == 0 else 'GAGAL (1)'} -> Exit Status: {rc_regex}")


def lab_test_arithmetic_truthiness():
    print_header("Test 2: Aritmatika Bash (( ... )) dan Inversi Truthiness Exit Status")
    print(f"{CLR_YELLOW}ATURAN BASH:{CLR_RESET} Nilai Integer != 0 mengembalikan $? = 0 (Success/True)")
    print(f"             Nilai Integer == 0 mengembalikan $? = 1 (Failure/False)\n")

    engine = BashArithmeticContext({"CORE_COUNT": 8, "LOAD": 8, "MAX_CAP": 16})
    test_cases = [
        "CORE_COUNT * 2",
        "CORE_COUNT - LOAD",        # Bernilai 0 -> Harusnya Exit Status 1
        "(LOAD > 5) * 10",         # Boolean evaluation
        "MAX_CAP % 3",
        "100 / 0"                   # Runtime Division Error
    ]

    for expr in test_cases:
        try:
            val, rc = engine.eval_expr(expr)
            meaning = f"{CLR_GREEN}TRUE / SUCCESS{CLR_RESET}" if rc == 0 else f"{CLR_RED}FALSE / FAILURE{CLR_RESET}"
            print(f"  Ekspresi: {CLR_BOLD}(( {expr:<18} )){CLR_RESET} => Nilai Matematis: {val:<3} | Exit Code ($?): {rc} ({meaning})")
        except BashExecutionError as err:
            print(f"  Ekspresi: {CLR_BOLD}(( {expr:<18} )){CLR_RESET} => {CLR_RED}RUNTIME ERROR: {err}{CLR_RESET}")


def lab_test_pipeline_short_circuit():
    print_header("Test 3: Simulasi Control Flow Logic & Short-Circuit Chaining (&& vs ||)")
    
    controller = PipelineFlowController()
    arithmetic = BashArithmeticContext({"RETRY": 0, "THRESHOLD": 3})

    def step_check_prereq():
        print("    -> Mengecek ketersediaan node cluster...")
        return 0  # 0 = Success

    def step_failing_task():
        print("    -> Mencoba alokasi port resource (Simulasi Gagal: Port In Use)...")
        return 1  # 1 = Failure

    def step_calc_retry():
        val, rc = arithmetic.eval_expr("RETRY + 1")
        print(f"    -> Recovery Routine: incrementing retry counter...")
        return rc

    def step_final_success():
        print("    -> Fallback Service berhasil diaktifkan.")
        return 0

    def step_skipped():
        print("    -> Langkah ini tidak boleh terpanggil!")
        return 0

    pipeline: List[Tuple[str, str, Any]] = [
        ("START", "Prerequisite Check", step_check_prereq),
        ("&&",    "Main Port Allocation Task", step_failing_task),
        ("&&",    "Task Subsequent (Harus di-skip)", step_skipped),
        ("||",    "Trigger Fallback Error Recovery", step_calc_retry),
        ("&&",    "Verify Fallback Health", step_final_success)
    ]

    controller.run_chain(pipeline)


def main():
    start_time = time.time()
    print(f"{CLR_BOLD}{CLR_MAGENTA}===========================================================================")
    print("  SIMULATOR ENGINE KONTROL LOGIKA, KONDISI, & ARITMATIKA BASH")
    print(f"==========================================================================={CLR_RESET}")

    lab_test_posix_vs_modern()
    lab_test_arithmetic_truthiness()
    lab_test_pipeline_short_circuit()

    elapsed = (time.time() - start_time) * 1000
    print(f"\n{CLR_CYAN}Eksekusi lab selesai dalam {elapsed:.2f}ms tanpa dependensi eksternal.{CLR_RESET}")


if __name__ == "__main__":
    main()
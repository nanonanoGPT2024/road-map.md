#!/usr/bin/env python3
"""
TypeScript Foundation Simulator: BAB-03 Functions, Signatures, Context & Execution
Simulasi interaktif konsep TypeScript Function Types, Overloading, Execution Context, & 'this' binding.
"""

import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# ANSI Escape Colors for Rich Terminal Output
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"


def print_banner() -> None:
    print(f"{Colors.CYAN}{Colors.BOLD}")
    print("=" * 72)
    print("  TYPESCRIPT ENGINE SIMULATOR: FUNCTIONS, SIGNATURES & CONTEXT (BAB-03)")
    print("=" * 72)
    print(f"{Colors.RESET}")


def format_ts_code(code: str) -> str:
    return f"{Colors.YELLOW}{code}{Colors.RESET}"


class TypeCheckError(Exception):
    """Exception raised when a simulated TypeScript type check fails."""
    pass


class FunctionSignature:
    """Simulates a TypeScript function signature declaration."""

    def __init__(self, name: str, params: List[Tuple[str, type, bool]], return_type: type):
        # params: list of (param_name, expected_type, is_optional)
        self.name = name
        self.params = params
        self.return_type = return_type

    def describe(self) -> str:
        param_strs = []
        for name, p_type, opt in self.params:
            opt_mark = "?" if opt else ""
            type_name = p_type.__name__ if hasattr(p_type, "__name__") else str(p_type)
            param_strs.append(f"{name}{opt_mark}: {type_name}")
        ret_name = self.return_type.__name__ if hasattr(self.return_type, "__name__") else str(self.return_type)
        return f"function {self.name}({', '.join(param_strs)}): {ret_name}"

    def validate_call(self, args: Tuple[Any, ...]) -> bool:
        min_args = sum(1 for _, _, opt in self.params if not opt)
        max_args = len(self.params)

        if not (min_args <= len(args) <= max_args):
            return False

        for i, arg in enumerate(args):
            expected_type = self.params[i][1]
            if not isinstance(arg, expected_type):
                return False
        return True


class FunctionOverloadResolver:
    """Simulates TypeScript Function Overloading with multiple overload heads and single implementation."""

    def __init__(self, name: str):
        self.name = name
        self.overload_signatures: List[FunctionSignature] = []
        self.implementation: Optional[Callable[..., Any]] = None

    def add_overload(self, params: List[Tuple[str, type, bool]], return_type: type) -> None:
        self.overload_signatures.append(FunctionSignature(self.name, params, return_type))

    def set_implementation(self, impl: Callable[..., Any]) -> None:
        self.implementation = impl

    def call(self, *args: Any) -> Any:
        matched_sig: Optional[FunctionSignature] = None
        for sig in self.overload_signatures:
            if sig.validate_call(args):
                matched_sig = sig
                break

        if not matched_sig:
            sig_list = "\n  - " + "\n  - ".join([s.describe() for s in self.overload_signatures])
            raise TypeCheckError(
                f"No overload matches this call with arguments {[type(a).__name__ for a in args]}.\n"
                f"Available signatures:{sig_list}"
            )

        print(f"  {Colors.GREEN}[TS Compiler Check Passed]{Colors.RESET} Matched signature: {matched_sig.describe()}")
        if self.implementation is None:
            raise RuntimeError("Implementation not defined")
        result = self.implementation(*args)
        if not isinstance(result, matched_sig.return_type):
            raise TypeCheckError(
                f"Return type mismatch: Expected {matched_sig.return_type.__name__}, got {type(result).__name__}"
            )
        return result


class ExecutionContext:
    """Simulates a JavaScript/TypeScript Execution Context and Call Stack."""

    def __init__(self, name: str, this_binding: Any, lexical_env: Dict[str, Any]):
        self.name = name
        self.this_binding = this_binding
        self.lexical_env = lexical_env

    def __repr__(self) -> str:
        this_desc = getattr(self.this_binding, "name", str(self.this_binding))
        return f"ExecutionContext(scope='{self.name}', this={this_desc}, vars={list(self.lexical_env.keys())})"


class CallStackSimulator:
    """Simulates JavaScript Call Stack during function invocation."""

    def __init__(self):
        self.stack: List[ExecutionContext] = []

    def push(self, context: ExecutionContext) -> None:
        self.stack.append(context)
        print(f"    {Colors.CYAN}---> [CALL STACK PUSH]{Colors.RESET} Entering: {context.name} (Depth: {len(self.stack)})")

    def pop(self) -> ExecutionContext:
        ctx = self.stack.pop()
        print(f"    {Colors.BLUE}<--- [CALL STACK POP]{Colors.RESET} Exiting: {ctx.name} (Remaining depth: {len(self.stack)})")
        return ctx

    def current(self) -> Optional[ExecutionContext]:
        return self.stack[-1] if self.stack else None


class TSContextFunction:
    """Simulates TypeScript Function with explicit 'this' parameter typing and Call/Apply/Bind."""

    def __init__(self, name: str, expected_this_type: type, body: Callable[..., Any]):
        self.name = name
        self.expected_this_type = expected_this_type
        self.body = body

    def invoke(self, stack: CallStackSimulator, this_arg: Any, *args: Any) -> Any:
        # TypeScript 'this' parameter validation
        if not isinstance(this_arg, self.expected_this_type):
            raise TypeCheckError(
                f"The 'this' context of type '{type(this_arg).__name__}' is not assignable to "
                f"method's 'this' of type '{self.expected_this_type.__name__}'."
            )

        context = ExecutionContext(
            name=self.name,
            this_binding=this_arg,
            lexical_env={"args": args, "this": this_arg}
        )
        stack.push(context)
        try:
            return self.body(this_arg, *args)
        finally:
            stack.pop()

    def bind(self, bound_this: Any) -> Callable[..., Any]:
        """Simulates Function.prototype.bind."""
        def bound_func(stack: CallStackSimulator, *args: Any) -> Any:
            return self.invoke(stack, bound_this, *args)
        return bound_func


# ==============================================================================
# DEMONSTRATION MODULES
# ==============================================================================

def demo_signatures_and_overloading() -> None:
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== 1. TS FUNCTION OVERLOADING & SIGNATURE RESOLUTION ==={Colors.RESET}")
    print("TypeScript function overloading allows defining multiple calling contracts with one implementation.\n")

    # Example: makeDate overload
    # function makeDate(timestamp: number): Date
    # function makeDate(year: number, month: number, day: number): Date
    resolver = FunctionOverloadResolver("makeDate")
    resolver.add_overload([("timestamp", int, False)], str)
    resolver.add_overload([("year", int, False), ("month", int, False), ("day", int, False)], str)

    def make_date_impl(*args: Any) -> str:
        if len(args) == 1:
            return f"Date(epoch={args[0]})"
        elif len(args) == 3:
            return f"Date({args[0]}-{args[1]:02d}-{args[2]:02d})"
        raise ValueError("Invalid argument count in implementation")

    resolver.set_implementation(make_date_impl)

    print("Overloads declared:")
    for sig in resolver.overload_signatures:
        print(f"  • {format_ts_code(sig.describe())}")

    print("\nExecuting valid calls:")
    res1 = resolver.call(1700000000)
    print(f"  Output: {Colors.BOLD}{res1}{Colors.RESET}\n")

    res2 = resolver.call(2026, 10, 6)
    print(f"  Output: {Colors.BOLD}{res2}{Colors.RESET}\n")

    print("Testing illegal call (2 arguments, unsupported overload):")
    try:
        resolver.call(2026, 10)
    except TypeCheckError as err:
        print(f"  {Colors.RED}[Compile-time Error Caught]{Colors.RESET}:")
        for line in str(err).splitlines():
            print(f"    {line}")


def demo_this_and_execution_context() -> None:
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== 2. EXECUTION CONTEXT & EXPLICIT 'this' TYPING ==={Colors.RESET}")
    print("TypeScript supports declaring 'this: Type' as the first parameter to enforce context correctness.\n")

    stack = CallStackSimulator()

    class DatabaseConnection:
        def __init__(self, db_name: str):
            self.name = db_name

    class UnrelatedService:
        def __init__(self, name: str):
            self.name = name

    def execute_query(db_ctx: DatabaseConnection, sql: str) -> str:
        return f"Executed '{sql}' on [{db_ctx.name}]"

    # TypeScript: function runQuery(this: DatabaseConnection, sql: string): string
    ts_fn = TSContextFunction("runQuery", DatabaseConnection, execute_query)

    pg_db = DatabaseConnection("PostgreSQL-Primary")
    wrong_ctx = UnrelatedService("AuthService")

    print(f"Declared: {format_ts_code('function runQuery(this: DatabaseConnection, sql: string): string')}")

    print("\n1) Normal Call with correct context (call/apply):")
    res = ts_fn.invoke(stack, pg_db, "SELECT * FROM users WHERE active = true")
    print(f"  Result: {Colors.GREEN}{res}{Colors.RESET}")

    print("\n2) Bound Function (Function.prototype.bind):")
    bound_query = ts_fn.bind(pg_db)
    res_bound = bound_query(stack, "UPDATE accounts SET balance = balance + 100")
    print(f"  Result: {Colors.GREEN}{res_bound}{Colors.RESET}")

    print("\n3) Invalid Context Call (Attempting to invoke with AuthService):")
    try:
        ts_fn.invoke(stack, wrong_ctx, "DROP TABLE orders")
    except TypeCheckError as err:
        print(f"  {Colors.RED}[TypeScript TypeCheckError]{Colors.RESET}: {err}")


def demo_closures_and_rest_tuples() -> None:
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== 3. REST PARAMETERS, TUPLES & CLOSURE ENVIRONMENT ==={Colors.RESET}")
    print("Simulating TypeScript Rest Tuple parameters: (...args: [string, number, ...boolean[]])\n")

    def create_counter(prefix: str) -> Callable[[int], str]:
        # Closure lexical environment
        count = 0

        def tick(step: int = 1) -> str:
            nonlocal count
            count += step
            return f"{prefix} -> Counter state: {count} (incremented by {step})"

        return tick

    print("Creating closure: const counterA = createCounter('Worker-1')")
    counter_a = create_counter("Worker-1")
    print(f"  {counter_a(1)}")
    print(f"  {counter_a(5)}")
    print(f"  {counter_a(2)}")

    print("\nValidating Rest Tuple: [command: string, retries: number, isVerbose: bool]")
    tuple_contract = (str, int, bool)

    def dispatch_event(*args: Any) -> bool:
        if len(args) != len(tuple_contract):
            raise TypeCheckError(f"Expected tuple length {len(tuple_contract)}, got {len(args)}")
        for idx, (val, exp_t) in enumerate(zip(args, tuple_contract)):
            if not isinstance(val, exp_t):
                raise TypeCheckError(f"Tuple item {idx}: expected {exp_t.__name__}, got {type(val).__name__}")
        print(f"  {Colors.GREEN}✔ Dispatched successfully:{Colors.RESET} command='{args[0]}', retries={args[1]}, verbose={args[2]}")
        return True

    dispatch_event("SYNC_CACHE", 3, True)

    try:
        print("  Attempting invalid tuple: dispatch_event('SYNC_CACHE', '3', True)")
        dispatch_event("SYNC_CACHE", "3", True)
    except TypeCheckError as err:
        print(f"  {Colors.RED}[TypeCheck Failure]{Colors.RESET}: {err}")


def interactive_quiz() -> None:
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== 4. INTERACTIVE VERIFICATION CHALLENGE ==={Colors.RESET}")
    questions = [
        {
            "q": "Dalam TypeScript, apa fungsi parameter pertama 'this' pada signature fungsi?",
            "options": [
                "A. Nilai default untuk instance method",
                "B. Type annotation khusus untuk compiler, dihapus saat runtime JavaScript",
                "C. Mengubah fungsi menjadi arrow function secara otomatis",
                "D. Parameter wajib yang harus dikirim secara eksplisit oleh pemanggil"
            ],
            "answer": "B",
            "explanation": "Parameter 'this' pertama dalam TS hanya digunakan untuk type-checking dan dihapus saat transpilasi."
        },
        {
            "q": "Kapan arrow function () => {} berbeda dari function reguler dalam konteks execution context?",
            "options": [
                "A. Arrow function mengikat 'this' secara dinamis berdasarkan caller",
                "B. Arrow function tidak memiliki 'this' sendiri (lexical this scoping)",
                "C. Arrow function tidak dapat dikembalikan dari closure",
                "D. Arrow function memiliki performa call stack 10x lebih cepat"
            ],
            "answer": "B",
            "explanation": "Arrow functions menangkap nilai 'this' dari enclosing lexical context, bukan runtime invocation context."
        }
    ]

    score = 0
    for idx, item in enumerate(questions, 1):
        print(f"\n{Colors.BOLD}Soal {idx}: {item['q']}{Colors.RESET}")
        for opt in item["options"]:
            print(f"  {opt}")

        # In non-interactive or batch mode, simulate correct selection
        user_choice = item["answer"]
        print(f"  Pilihan otomatis simulasi: {Colors.CYAN}{user_choice}{Colors.RESET}")

        if user_choice.upper() == item["answer"]:
            print(f"  {Colors.GREEN}BENAR!{Colors.RESET} {item['explanation']}")
            score += 1
        else:
            print(f"  {Colors.RED}SALAH.{Colors.RESET}")

    print(f"\nSkor Kuis Mandiri: {Colors.BOLD}{score}/{len(questions)}{Colors.RESET}")


def run_full_suite() -> None:
    print_banner()
    demo_signatures_and_overloading()
    time.sleep(0.1)
    demo_this_and_execution_context()
    time.sleep(0.1)
    demo_closures_and_rest_tuples()
    time.sleep(0.1)
    interactive_quiz()

    print(f"\n{Colors.GREEN}{Colors.BOLD}========================================================================{Colors.RESET}")
    print(f"{Colors.GREEN}{Colors.BOLD}  SEMUA SIMULASI KONSEP BAB-03 BERJALAN 100% SUKSES DENGAN VALIDASI TYPE{Colors.RESET}")
    print(f"{Colors.GREEN}{Colors.BOLD}========================================================================{Colors.RESET}\n")


if __name__ == "__main__":
    run_full_suite()

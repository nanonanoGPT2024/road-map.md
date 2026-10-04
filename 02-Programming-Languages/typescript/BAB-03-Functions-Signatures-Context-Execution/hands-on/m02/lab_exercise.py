#!/usr/bin/env python3
"""
Lab Hands-on: TypeScript Functions, Signatures, & Context Execution Deep Dive
Category: 02-Programming-Languages | Chapter: 03 - Module 02

This script simulates TypeScript's internal function mechanics:
1. Static Overload Signature Resolution (tsc compile-time overload dispatch simulation).
2. Lexical vs Dynamic Context Execution (Arrow function closure vs standard `this` binding).
3. Explicit `this` parameter typing and runtime enforcement (TS `this: Context` syntax).
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple
import sys
import time

# ANSI Terminal Styling
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_RESET = "\033[0m"


class TypeScriptTypeError(Exception):
    """Raised when static signature or context verification fails."""
    pass


# ---------------------------------------------------------------------------
# Part 1: Type System Primitives & Overload Signature Matching Engine
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TSSignature:
    """Represents a declared TypeScript overload signature."""
    param_types: Tuple[type, ...]
    return_type: type
    explicit_this: Optional[type] = None

    def matches(self, this_arg: Any, args: Tuple[Any, ...]) -> bool:
        """Verifies argument length and runtime compatibility against signature."""
        if self.explicit_this:
            if this_arg is None or not isinstance(this_arg, self.explicit_this):
                return False
        if len(args) != len(self.param_types):
            return False
        for arg, expected_type in zip(args, self.param_types):
            if expected_type is not Any and not isinstance(arg, expected_type):
                return False
        return True


class TSFunctionOverloader:
    """
    Simulates TypeScript compile-time overload definitions mapped to a single 
    JavaScript implementation function.
    """
    def __init__(self, name: str):
        self.name = name
        self.overload_table: List[TSSignature] = []
        self._implementation: Optional[Callable] = None

    def overload(self, param_types: Tuple[type, ...], return_type: type, explicit_this: Optional[type] = None):
        """Registers a public signature interface (tsc ambient declaration)."""
        sig = TSSignature(param_types=param_types, return_type=return_type, explicit_this=explicit_this)
        self.overload_table.append(sig)
        return self

    def implement(self, fn: Callable):
        """Attaches the single unified implementation body."""
        self._implementation = fn
        return self

    def resolve_signature(self, this_ctx: Any, *args: Any) -> TSSignature:
        """
        TypeScript resolves overloads in declared order. The first matching
        signature wins. If none match, a compilation error occurs.
        """
        for sig in self.overload_table:
            if sig.matches(this_ctx, args):
                return sig
        
        arg_types = tuple(type(a).__name__ for a in args)
        this_type = type(this_ctx).__name__ if this_ctx is not None else "void"
        overload_desc = "\n  ".join(
            f"({', '.join(t.__name__ for t in s.param_types)}) -> {s.return_type.__name__}"
            f" [this: {s.explicit_this.__name__ if s.explicit_this else 'void'}]"
            for s in self.overload_table
        )
        raise TypeScriptTypeError(
            f"No overload matches call.\n"
            f"  Target: {self.name}(this: {this_type}, args: {arg_types})\n"
            f"  Available Overloads:\n  {overload_desc}"
        )

    def __call__(self, *args, **kwargs):
        raise TypeScriptTypeError("Cannot invoke directly without execution context. Use .call() or .bind().")

    def call(self, this_ctx: Any, *args: Any) -> Any:
        """Executes the function under strict signature verification."""
        matched_sig = self.resolve_signature(this_ctx, *args)
        if self._implementation is None:
            raise NotImplementedError(f"TS Implementation body missing for {self.name}")
        
        result = self._implementation(this_ctx, *args)
        if matched_sig.return_type is not Any and not isinstance(result, matched_sig.return_type):
            raise TypeScriptTypeError(
                f"Type '{type(result).__name__}' is not assignable to type '{matched_sig.return_type.__name__}'."
            )
        return result


# ---------------------------------------------------------------------------
# Part 2: Context Execution & 'this' Binding Simulation
# ---------------------------------------------------------------------------

class ExecutionScope:
    """Simulates ECMAScript/TypeScript lexical environment and 'this' scope."""
    def __init__(self, name: str, state: Dict[str, Any]):
        self.name = name
        self.state = state

    def __repr__(self):
        return f"Context<{self.name}: {self.state}>"


class TSCallableWrapper:
    """Wraps functions to model Function.prototype.bind and arrow function semantics."""
    def __init__(self, fn: Callable, is_arrow: bool = False, bound_this: Any = None):
        self._fn = fn
        self.is_arrow = is_arrow
        self.bound_this = bound_this

    def bind(self, target_ctx: Any) -> "TSCallableWrapper":
        """
        TypeScript/JS specification: Arrow functions retain their lexical 'this'
        and cannot be rebound via bind(), call(), or apply().
        """
        if self.is_arrow:
            # Arrow functions silently ignore re-binding of this
            return self
        return TSCallableWrapper(self._fn, is_arrow=False, bound_this=target_ctx)

    def invoke(self, dynamic_ctx: Any, *args: Any) -> Any:
        # Arrow functions completely ignore invocation-site context
        effective_this = self.bound_this if (self.is_arrow or self.bound_this is not None) else dynamic_ctx
        return self._fn(effective_this, *args)


# ---------------------------------------------------------------------------
# Part 3: Test Scenario Harness
# ---------------------------------------------------------------------------

def run_overload_demo():
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== SCENARIO 1: Compile-Time Signature Overloading ==={CLR_RESET}")
    
    # Declare function: makeDate(timestamp: int) -> str
    #                   makeDate(year: int, month: int, day: int) -> str
    make_date = TSFunctionOverloader("makeDate")
    make_date.overload((int,), str)
    make_date.overload((int, int, int), str)

    def make_date_impl(this_arg: Any, *args: Any) -> str:
        # Implementation signature: (this: void, ...args: number[]) => string
        if len(args) == 1:
            return f"Epoch Date: {time.ctime(args[0])}"
        elif len(args) == 3:
            return f"Calendar Date: {args[0]:04d}-{args[1]:02d}-{args[2]:02d}"
        raise ValueError("Invalid implementation path")

    make_date.implement(make_date_impl)

    # Valid Overload Calls
    res1 = make_date.call(None, 1700000000)
    print(f" {CLR_GREEN}✔{CLR_RESET} makeDate(1700000000) -> {CLR_YELLOW}'{res1}'{CLR_RESET}")

    res2 = make_date.call(None, 2026, 4, 15)
    print(f" {CLR_GREEN}✔{CLR_RESET} makeDate(2026, 4, 15)  -> {CLR_YELLOW}'{res2}'{CLR_RESET}")

    # Invalid Overload Call (Type Error at check-time)
    print(f" {CLR_DIM}Attempting invalid overload: makeDate(2026, \"April\"){CLR_RESET}")
    try:
        make_date.call(None, 2026, "April")
    except TypeScriptTypeError as err:
        print(f" {CLR_RED}✖ TypeScript Check Failed:{CLR_RESET}\n   {CLR_DIM}{err}{CLR_RESET}")


def run_explicit_this_demo():
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== SCENARIO 2: Explicit Context Verification ('this: Type') ==={CLR_RESET}")
    
    class DatabaseConnection:
        def __init__(self, dsn: str):
            self.dsn = dsn

    class UnrelatedService:
        pass

    # Declare: executeQuery(this: DatabaseConnection, sql: str) -> dict
    query_exec = TSFunctionOverloader("executeQuery")
    query_exec.overload((str,), dict, explicit_this=DatabaseConnection)

    def query_exec_impl(this_arg: DatabaseConnection, sql: str) -> dict:
        return {"connection": this_arg.dsn, "query": sql, "status": "200_OK"}

    query_exec.implement(query_exec_impl)

    db_ctx = DatabaseConnection("postgres://cluster-01.internal:5432/main")
    rogue_ctx = UnrelatedService()

    # Valid context call
    res = query_exec.call(db_ctx, "SELECT * FROM users WHERE active = true;")
    print(f" {CLR_GREEN}✔{CLR_RESET} Valid 'this' context supplied: {CLR_YELLOW}{res}{CLR_RESET}")

    # Illegal context call (simulating strict TS this checking)
    print(f" {CLR_DIM}Attempting call with void 'this'...{CLR_RESET}")
    try:
        query_exec.call(None, "DROP TABLE logs;")
    except TypeScriptTypeError as err:
        print(f" {CLR_RED}✖ Context Error:{CLR_RESET} Calling unattached method without required 'this: DatabaseConnection'")

    print(f" {CLR_DIM}Attempting call with incompatible 'UnrelatedService' context...{CLR_RESET}")
    try:
        query_exec.call(rogue_ctx, "SELECT 1;")
    except TypeScriptTypeError as err:
        print(f" {CLR_RED}✖ Incompatible Context Type:{CLR_RESET}\n   {CLR_DIM}{err.args[0].splitlines()[0]}{CLR_RESET}")


def run_lexical_context_demo():
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== SCENARIO 3: Lexical Context Preservation (Arrow vs Normal) ==={CLR_RESET}")

    global_scope = ExecutionScope("Global", {"auth": "guest"})
    auth_scope = ExecutionScope("AuthService", {"auth": "bearer-admin-token"})
    hacker_scope = ExecutionScope("Attacker", {"auth": "compromised"})

    # Standard TS Function: function getAuth(this: ExecutionScope) { return this.state['auth']; }
    def standard_fn(this_ctx: ExecutionScope) -> str:
        return this_ctx.state.get("auth", "none")

    # Arrow TS Function: const getAuthArrow = () => { return this.state['auth']; }
    # Lexically captured during declaration inside 'auth_scope'
    lexical_this = auth_scope
    def arrow_fn(_dynamic_ctx: Any) -> str:
        return lexical_this.state.get("auth", "none")

    std_wrapper = TSCallableWrapper(standard_fn, is_arrow=False)
    arrow_wrapper = TSCallableWrapper(arrow_fn, is_arrow=True, bound_this=lexical_this)

    print(f" 1. Standard Method Invocation (dynamic context dispatch):")
    res_std1 = std_wrapper.invoke(auth_scope)
    res_std2 = std_wrapper.invoke(hacker_scope)
    print(f"    - Under auth_scope:   {CLR_YELLOW}{res_std1}{CLR_RESET}")
    print(f"    - Under hacker_scope: {CLR_RED}{res_std2}{CLR_RESET} (dynamic 'this' hijacked)")

    print(f"\n 2. Arrow Function Invocation (lexically captured context):")
    res_arr1 = arrow_wrapper.invoke(hacker_scope)
    print(f"    - Under hacker_scope: {CLR_GREEN}{res_arr1}{CLR_RESET} (arrow retains captured lexical scope)")

    print(f"\n 3. Explicit Re-binding (.bind() attempt):")
    bound_std = std_wrapper.bind(global_scope)
    bound_arr = arrow_wrapper.bind(global_scope)
    print(f"    - Standard rebound to Global: {CLR_YELLOW}{bound_std.invoke(hacker_scope)}{CLR_RESET}")
    print(f"    - Arrow rebound to Global:    {CLR_GREEN}{bound_arr.invoke(hacker_scope)}{CLR_RESET} (bind() was ignored by Arrow)")


def main():
    print(f"{CLR_BOLD}TypeScript Runtime Engine Emulation{CLR_RESET}")
    print(f"Topic: Functions, Signatures, & Context Execution Deep Dive")
    print(f"{CLR_DIM}------------------------------------------------------------{CLR_RESET}")
    run_overload_demo()
    run_explicit_this_demo()
    run_lexical_context_demo()
    print(f"\n{CLR_BOLD}{CLR_GREEN}Lab Deep Dive Execution Complete.{CLR_RESET}\n")


if __name__ == "__main__":
    main()
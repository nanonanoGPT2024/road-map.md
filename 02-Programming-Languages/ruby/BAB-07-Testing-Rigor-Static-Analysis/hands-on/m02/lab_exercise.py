#!/usr/bin/env python3
"""
Lab Hands-on: Ruby Testing Rigor & Static Analysis (Module 02 Deep Dive)
Simulates core Ruby static analysis (RuboCop / Sorbet style) and mutation testing
(Mutant / RSpec style) using an AST-like tokenized engine in pure Python.
"""

import re
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Callable, Optional


# ==========================================
# ANSI Color Formatting Utilities
# ==========================================
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


def header(title: str) -> None:
    print(f"\n{Color.BOLD}{Color.CYAN}{'=' * 75}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN} [LAB] {title.upper()}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}{'=' * 75}{Color.RESET}")


# ==========================================
# Domain Models: Code & Offenses
# ==========================================
class Severity(Enum):
    INFO = "convention"
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


@dataclass
class Offense:
    cop_name: str
    severity: Severity
    line: int
    column: int
    message: str


@dataclass
class RubySource:
    filename: str
    lines: List[str]

    @property
    def raw_content(self) -> str:
        return "\n".join(self.lines)


# ==========================================
# Static Analysis Engine (Mini-RuboCop)
# ==========================================
class BaseCop:
    """Base class for Ruby linter cops enforcing static rules."""
    def __init__(self, name: str, severity: Severity):
        self.name = name
        self.severity = severity
        self.offenses: List[Offense] = []

    def clear(self):
        self.offenses.clear()

    def add_offense(self, line_num: int, col: int, message: str):
        self.offenses.append(Offense(self.name, self.severity, line_num, col, message))

    def inspect(self, source: RubySource):
        raise NotImplementedError


class FrozenStringLiteralCop(BaseCop):
    """Enforces presence of `# frozen_string_literal: true` at the magic comment line."""
    def __init__(self):
        super().__init__("Style/FrozenStringLiteralComment", Severity.INFO)

    def inspect(self, source: RubySource):
        if not source.lines:
            return
        first_line = source.lines[0].strip()
        if not re.match(r"^#\s*frozen_string_literal:\s*true", first_line):
            self.add_offense(1, 0, "Missing frozen string literal magic comment at top of file.")


class SecurityEvalCop(BaseCop):
    """Detects unsafe dynamic evaluation methods (eval, instance_eval, send with user inputs)."""
    def __init__(self):
        super().__init__("Security/Eval", Severity.ERROR)

    def inspect(self, source: RubySource):
        eval_pattern = re.compile(r"\b(eval|instance_eval|class_eval)\b")
        for idx, line in enumerate(source.lines, start=1):
            match = eval_pattern.search(line)
            if match and not line.strip().startswith("#"):
                self.add_offense(idx, match.start(), f"Unsafe execution primitive detected: '{match.group(0)}'.")


class MutableConstantCop(BaseCop):
    """Detects mutable structures (Array, Hash) assigned to Ruby constants without .freeze."""
    def __init__(self):
        super().__init__("Style/MutableConstant", Severity.WARNING)

    def inspect(self, source: RubySource):
        const_pattern = re.compile(r"^[A-Z][A-Z0-9_]*\s*=\s*(\[|\{).*")
        for idx, line in enumerate(source.lines, start=1):
            stripped = line.strip()
            if const_pattern.match(stripped) and not stripped.endswith(".freeze"):
                self.add_offense(idx, 0, "Freeze mutable objects assigned to constants to prevent mutation leaks.")


class CyclomaticComplexityCop(BaseCop):
    """Calculates approximate McCabe cyclomatic complexity per Ruby method."""
    def __init__(self, threshold: int = 4):
        super().__init__("Metrics/CyclomaticComplexity", Severity.WARNING)
        self.threshold = threshold

    def inspect(self, source: RubySource):
        branch_regex = re.compile(r"\b(if|unless|elsif|while|until|rescue|and|or|&&|\|\|)\b")
        current_method = None
        method_line = 0
        complexity = 1

        for idx, line in enumerate(source.lines, start=1):
            stripped = line.strip()
            def_match = re.match(r"^def\s+([a-zA-Z0-9_!?]+)", stripped)
            if def_match:
                current_method = def_match.group(1)
                method_line = idx
                complexity = 1
                continue

            if current_method:
                # Count branch decision points
                complexity += len(branch_regex.findall(stripped))
                if stripped == "end":
                    if complexity > self.threshold:
                        self.add_offense(
                            method_line,
                            0,
                            f"Cyclomatic complexity for `#{current_method}` is too high [{complexity}/{self.threshold}]."
                        )
                    current_method = None


class StaticAnalysisRunner:
    """Orchestrates RuboCop style lint checks across Ruby source codes."""
    def __init__(self):
        self.cops: List[BaseCop] = [
            FrozenStringLiteralCop(),
            SecurityEvalCop(),
            MutableConstantCop(),
            CyclomaticComplexityCop(threshold=3),
        ]

    def run(self, source: RubySource) -> List[Offense]:
        all_offenses = []
        for cop in self.cops:
            cop.clear()
            cop.inspect(source)
            all_offenses.extend(cop.offenses)
        return sorted(all_offenses, key=lambda x: (x.line, x.column))


# ==========================================
# Behavior-Driven Testing Simulator (RSpec)
# ==========================================
class ExpectationError(AssertionError):
    pass


class Expectation:
    def __init__(self, target: Any):
        self.target = target

    def to_eq(self, expected: Any):
        if self.target != expected:
            raise ExpectationError(f"Expected: {expected!r}, Got: {self.target!r}")

    def to_be_true(self):
        if self.target is not True:
            raise ExpectationError(f"Expected truthy/True, Got: {self.target!r}")

    def to_be_false(self):
        if self.target is not False:
            raise ExpectationError(f"Expected falsey/False, Got: {self.target!r}")


def expect(target: Any) -> Expectation:
    return Expectation(target)


class TestResult(Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"


@dataclass
class ExampleResult:
    description: str
    result: TestResult
    error_message: Optional[str] = None
    duration: float = 0.0


class RSpecRunner:
    """Simulates an RSpec test suite executing ruby logic contracts."""
    def __init__(self):
        self.examples: List[tuple[str, Callable]] = []

    def it(self, description: str, func: Callable):
        self.examples.append((description, func))

    def run(self, quiet: bool = False) -> List[ExampleResult]:
        results = []
        for desc, test_fn in self.examples:
            start_t = time.perf_counter()
            try:
                test_fn()
                elapsed = time.perf_counter() - start_t
                res = ExampleResult(description=desc, result=TestResult.PASSED, duration=elapsed)
            except Exception as e:
                elapsed = time.perf_counter() - start_t
                res = ExampleResult(description=desc, result=TestResult.FAILED, error_message=str(e), duration=elapsed)
            results.append(res)
            if not quiet:
                status_color = Color.GREEN if res.result == TestResult.PASSED else Color.RED
                print(f"  {status_color}•{Color.RESET} {desc} [{res.duration*1000:.2f}ms]")
                if res.error_message:
                    print(f"    {Color.RED}Assertion failed: {res.error_message}{Color.RESET}")
        return results


# ==========================================
# Mutation Testing Framework (Mutant Style)
# ==========================================
@dataclass
class Mutation:
    id: str
    description: str
    mutated_logic: Callable[[dict], Any]


class MutationTestingEngine:
    """
    Evaluates test rigor by injecting intentional semantic mutations into
    the application logic. If tests still pass, the mutant survived (bad rigor).
    If a test fails, the mutant was killed (strong rigor).
    """
    def __init__(self, test_suite_factory: Callable[[Callable], RSpecRunner]):
        self.test_suite_factory = test_suite_factory
        self.mutations: List[Mutation] = []

    def register_mutation(self, mutation_id: str, description: str, mutated_logic: Callable[[dict], Any]):
        self.mutations.append(Mutation(mutation_id, description, mutated_logic))

    def evaluate(self) -> Dict[str, Any]:
        total = len(self.mutations)
        killed = 0
        survived = 0
        details = []

        for mut in self.mutations:
            runner = self.test_suite_factory(mut.mutated_logic)
            results = runner.run(quiet=True)
            has_failed = any(r.result == TestResult.FAILED for r in results)

            if has_failed:
                killed += 1
                status = "KILLED"
                color = Color.GREEN
            else:
                survived += 1
                status = "SURVIVED"
                color = Color.RED

            details.append({"id": mut.id, "desc": mut.description, "status": status, "color": color})

        mutation_score = (killed / total * 100) if total > 0 else 0.0
        return {
            "total": total,
            "killed": killed,
            "survived": survived,
            "score": mutation_score,
            "details": details,
        }


# ==========================================
# Lab Execution Implementation
# ==========================================
def main():
    # -------------------------------------------------------------
    # 1. Static Code Analysis (RuboCop Demonstration)
    # -------------------------------------------------------------
    header("Stage 1: RuboCop Static Code Inspection")

    ruby_code_sample = [
        "# Missing magic comment on line 1",
        "ALLOWED_ROLES = ['admin', 'moderator', 'member']",  # Mutable Constant
        "",
        "class PermissionManager",
        "  def verify_access(user, action, resource, env)",
        "    if user.nil?",                                  # Branch 1
        "      return false",
        "    elsif user[:role] == 'admin'",                 # Branch 2
        "      return true",
        "    elsif user[:role] == 'moderator' && action != 'delete'", # Branch 3 & 4
        "      return true",
        "    else",
        "      eval(\"puts 'Audit: ' + action\")",          # Security/Eval
        "      return false",
        "    end",
        "  end",
        "end"
    ]

    source = RubySource("app/services/permission_manager.rb", ruby_code_sample)
    print(f"{Color.BOLD}Target File:{Color.RESET} {source.filename}")
    print(f"{Color.DIM}Source Lines: {len(source.lines)}{Color.RESET}\n")

    linter = StaticAnalysisRunner()
    offenses = linter.run(source)

    for off in offenses:
        sev_color = {
            Severity.INFO: Color.BLUE,
            Severity.WARNING: Color.YELLOW,
            Severity.ERROR: Color.RED,
            Severity.FATAL: Color.MAGENTA
        }.get(off.severity, Color.WHITE)

        print(f"  {Color.BOLD}{source.filename}:{off.line}:{off.column}{Color.RESET}: "
              f"{sev_color}{off.severity.value.upper()}{Color.RESET}: "
              f"[{off.cop_name}] {off.message}")
        print(f"    {Color.DIM}{source.lines[off.line - 1].strip()}{Color.RESET}")

    print(f"\n{Color.BOLD}Summary:{Color.RESET} {len(offenses)} offense(s) detected across 4 active cops.")

    # -------------------------------------------------------------
    # 2. RSpec Behavioral Unit Testing
    # -------------------------------------------------------------
    header("Stage 2: RSpec Suite Execution (Behavioral Rigor)")

    # Baseline Ruby method logic implemented in Python
    def baseline_permission_checker(user: Optional[dict], action: str, resource: str) -> bool:
        if user is None:
            return False
        if user.get("role") == "admin":
            return True
        if user.get("role") == "moderator" and action != "delete":
            return True
        return False

    def build_test_suite(logic_fn: Callable) -> RSpecRunner:
        spec = RSpecRunner()
        spec.it("denies access when user context is nil",
                lambda: expect(logic_fn(None, "read", "post")).to_be_false())
        spec.it("grants full permissions to admin role",
                lambda: expect(logic_fn({"role": "admin"}, "delete", "post")).to_be_true())
        spec.it("allows moderator to read resources",
                lambda: expect(logic_fn({"role": "moderator"}, "read", "post")).to_be_true())
        spec.it("denies delete operations for moderator role",
                lambda: expect(logic_fn({"role": "moderator"}, "delete", "post")).to_be_false())
        spec.it("denies access to general members for write operations",
                lambda: expect(logic_fn({"role": "member"}, "write", "post")).to_be_false())
        return spec

    print(f"{Color.BOLD}Running RSpec Specs against Baseline Logic:{Color.RESET}")
    base_suite = build_test_suite(baseline_permission_checker)
    suite_results = base_suite.run(quiet=False)
    all_passed = all(r.result == TestResult.PASSED for r in suite_results)

    print(f"\n{Color.BOLD}Suite Status:{Color.RESET} "
          f"{Color.GREEN if all_passed else Color.RED}"
          f"{sum(1 for r in suite_results if r.result == TestResult.PASSED)}/{len(suite_results)} Passed"
          f"{Color.RESET}")

    # -------------------------------------------------------------
    # 3. Mutation Testing Deep Dive (Mutant Engine Simulation)
    # -------------------------------------------------------------
    header("Stage 3: Mutation Testing (Measuring Test Suite Rigor)")

    mutation_engine = MutationTestingEngine(build_test_suite)

    # Mutant A: Invert nil guard condition
    def mutant_invert_nil(user: Optional[dict], action: str, resource: str) -> bool:
        if user is not None:  # Inverted check
            return False
        if user.get("role") == "admin":
            return True
        return False

    # Mutant B: Allow moderator to bypass delete guard
    def mutant_bypass_delete(user: Optional[dict], action: str, resource: str) -> bool:
        if user is None:
            return False
        if user.get("role") == "admin":
            return True
        if user.get("role") == "moderator":  # Dropped action != 'delete' condition
            return True
        return False

    # Mutant C: Constant True return (Stubbing bypass)
    def mutant_always_true(user: Optional[dict], action: str, resource: str) -> bool:
        return True

    # Mutant D: Subtly change member behavior (Uncovered edge case check)
    def mutant_allow_member_read(user: Optional[dict], action: str, resource: str) -> bool:
        if user is None:
            return False
        if user.get("role") == "admin":
            return True
        if user.get("role") == "moderator" and action != "delete":
            return True
        if user.get("role") == "member" and action == "read":  # Semantic injection
            return True
        return False

    mutation_engine.register_mutation("MUT_01", "Invert user.nil? guard to user.present?", mutant_invert_nil)
    mutation_engine.register_mutation("MUT_02", "Remove action != 'delete' check for moderator", mutant_bypass_delete)
    mutation_engine.register_mutation("MUT_03", "Replace method body with constant `true`", mutant_always_true)
    mutation_engine.register_mutation("MUT_04", "Authorize member for 'read' actions (Edge Case)", mutant_allow_member_read)

    eval_results = mutation_engine.evaluate()

    print(f"{'MUTATION ID':<12} {'DESCRIPTION':<50} {'RESULT'}")
    print("-" * 75)
    for item in eval_results["details"]:
        print(f"{item['id']:<12} {item['desc']:<50} {item['color']}{item['status']}{Color.RESET}")

    score = eval_results["score"]
    score_color = Color.GREEN if score >= 80.0 else (Color.YELLOW if score >= 60.0 else Color.RED)

    print("\n" + "=" * 75)
    print(f"{Color.BOLD}Mutation Coverage Score:{Color.RESET} {score_color}{score:.1f}%{Color.RESET} "
          f"({eval_results['killed']} killed, {eval_results['survived']} survived)")

    if eval_results["survived"] > 0:
        print(f"{Color.YELLOW}[!] Analysis Insight: Survived mutants identify blind spots in your test assertions.{Color.RESET}")
        print(f"    Add targeted RSpec examples for MUT_04 (`member read permission`) to achieve 100% rigor.")
    print("=" * 75)


if __name__ == "__main__":
    main()
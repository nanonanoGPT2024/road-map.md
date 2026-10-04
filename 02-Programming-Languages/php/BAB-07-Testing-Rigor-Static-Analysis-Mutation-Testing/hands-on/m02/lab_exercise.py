#!/usr/bin/env python3
"""
Lab: Deep Dive into Testing Rigor, Static Analysis & Mutation Testing (Infection PHP Architecture)
Category: 02-Programming-Languages | Topic: php | Chapter: 07

This script models the architectural pipeline of enterprise PHP QA engineering:
1. AST Static Analysis & Cyclomatic Complexity Metric Calculation (simulating PHPStan / Psalm).
2. Code Rule Linting & Nullability/Type Boundary Verification.
3. Infection-style Mutation Testing Engine:
   - Programmatic AST token mutation (Comparison, Logical, Arithmetic, Return mutations).
   - Test harness execution against mutants.
   - Calculation of Mutation Score Indicator (MSI), Killed Mutants, and Escaped Mutants.
"""

import sys
import time
from typing import Callable, Dict, List, Tuple, Any

# --- ANSI Terminal Color Palette ---
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[91m"
CLR_GREEN   = "\033[92m"
CLR_YELLOW  = "\033[93m"
CLR_BLUE    = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN    = "\033[96m"
CLR_WHITE   = "\033[97m"
CLR_GRAY    = "\033[90m"

# -----------------------------------------------------------------------------
# 1. Target Domain Code (Simulating PHP Business Logic)
# -----------------------------------------------------------------------------
PHP_SOURCE_CODE = """<?php
declare(strict_types=1);

namespace App\\Billing;

final class TieredDiscountCalculator
{
    /**
     * Calculates discount based on subtotal, VIP flag, and volume items.
     */
    public function calculate(float $subtotal, bool $isVip, int $itemCount): float
    {
        if ($subtotal <= 0.0 || $itemCount <= 0) {
            return 0.0;
        }

        $discount = 0.0;

        // Rule 1: VIP High Tier
        if ($isVip && $subtotal >= 100.0) {
            $discount = $subtotal * 0.20;
        } elseif ($subtotal >= 50.0) {
            $discount = $subtotal * 0.10;
        }

        // Rule 2: Volume items bonus
        if ($itemCount > 5) {
            $discount = $discount + 5.0;
        }

        return $discount;
    }
}
"""

# -----------------------------------------------------------------------------
# 2. Static Analysis & Complexity Engine (Simulating PHPStan / Psalm / PHPMD)
# -----------------------------------------------------------------------------
class StaticAnalysisEngine:
    """Performs lexical and structural checks on PHP token streams."""

    @staticmethod
    def analyze(source: str) -> Dict[str, Any]:
        lines = source.splitlines()
        complexity = 1  # Base cyclomatic complexity (M = E - N + 2P)
        branching_keywords = ["if", "elseif", "while", "for", "foreach", "case", "&&", "||", "??"]
        strict_types_declared = False
        findings = []

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if "declare(strict_types=1)" in stripped:
                strict_types_declared = True

            # Calculate cyclomatic complexity
            for kw in branching_keywords:
                # Basic token boundary check
                tokens = stripped.replace("(", " ").replace(")", " ").split()
                if kw in tokens:
                    complexity += 1

            # Rule check: Enforce floating-point literal formatting
            if "$discount = 0;" in stripped:
                findings.append((idx, "Style/TypeStrictness", "Implicit integer assigned to float $discount variable."))

        if not strict_types_declared:
            findings.append((1, "TypeSafety", "Missing 'declare(strict_types=1);' declaration."))

        return {
            "cyclomatic_complexity": complexity,
            "strict_types": strict_types_declared,
            "findings": findings,
            "lines_of_code": len(lines)
        }


# -----------------------------------------------------------------------------
# 3. Dynamic Execution & Mutation Engine (Simulating Infection PHP)
# -----------------------------------------------------------------------------

# Canonical reference execution function in Python matching the target PHP logic
def run_php_discount_logic(subtotal: float, is_vip: bool, item_count: int, overrides: Dict[str, Any] = None) -> float:
    """
    Simulates execution of TieredDiscountCalculator::calculate with optional
    mutations injected at runtime points.
    """
    ov = overrides or {}

    # Mutator Points:
    # M1: Subtotal <= 0.0 condition
    cond_subtotal = (subtotal < 0.0) if ov.get("M1_BOUNDARY") else (subtotal <= 0.0)
    # M2: itemCount <= 0 condition
    cond_items = (item_count < 0) if ov.get("M2_ITEMS_BOUNDARY") else (item_count <= 0)
    
    # M3: Logical OR mutation
    if ov.get("M3_OR_TO_AND"):
        exit_early = cond_subtotal and cond_items
    else:
        exit_early = cond_subtotal or cond_items

    if exit_early:
        return 0.0

    discount = 0.0

    # M4: Logical AND to OR mutation in VIP tier
    vip_cond = (is_vip or subtotal >= 100.0) if ov.get("M4_VIP_LOGIC") else (is_vip and subtotal >= 100.0)

    # M5: Comparison mutation (>= 100 to > 100)
    if ov.get("M5_VIP_THRESHOLD"):
        vip_cond = is_vip and (subtotal > 100.0)

    if vip_cond:
        # M6: Multiplier mutation (0.20 to 0.15)
        rate = 0.15 if ov.get("M6_VIP_RATE") else 0.20
        discount = subtotal * rate
    elif (subtotal > 50.0 if ov.get("M7_STANDARD_THRESHOLD") else subtotal >= 50.0):
        discount = subtotal * 0.10

    # M8: Volume condition (> 5 to >= 5)
    vol_cond = (item_count >= 5) if ov.get("M8_VOLUME_BOUNDARY") else (item_count > 5)
    if vol_cond:
        # M9: Arithmetic operator (+ to -)
        if ov.get("M9_BONUS_OPERATOR"):
            discount = discount - 5.0
        else:
            discount = discount + 5.0

    # M10: Return value mutation
    if ov.get("M10_RETURN_ZERO"):
        return 0.0

    return discount


# Test Suite Definition (PHPUnit style test cases)
TestCase = Tuple[str, float, bool, int, float]  # (name, subtotal, is_vip, item_count, expected)

# Intentionally calibrated test suite: Comprehensive on core cases, but has a blind spot on exact boundary
TEST_SUITE: List[TestCase] = [
    ("testSubtotalZeroReturnsZero", 0.0, False, 1, 0.0),
    ("testNegativeItemCountReturnsZero", 100.0, True, -1, 0.0),
    ("testVipHighTierDiscountApplied", 200.0, True, 2, 40.0),
    ("testStandardTierDiscountApplied", 80.0, False, 2, 8.0),
    ("testVolumeBonusAppliedForLargeCart", 100.0, False, 10, 15.0), # 10.0 (10%) + 5.0 bonus
    ("testVipWithVolumeBonus", 100.0, True, 6, 25.0),               # 20.0 (20%) + 5.0 bonus
]

def run_test_suite(mutations: Dict[str, Any] = None) -> Tuple[bool, str]:
    """Runs test suite against mutated code. Returns (passed, failure_reason)."""
    for name, subtotal, is_vip, items, expected in TEST_SUITE:
        actual = run_php_discount_logic(subtotal, is_vip, items, overrides=mutations)
        if abs(actual - expected) > 1e-6:
            return False, f"AssertionFailed in {name}: expected {expected}, got {actual}"
    return True, "All tests passed"


# -----------------------------------------------------------------------------
# 4. Mutation Testing Runner
# -----------------------------------------------------------------------------
MUTATION_CATALOG = [
    {
        "id": "M1",
        "name": "LessThanOrEqualTo_To_LessThan",
        "category": "Boundary Condition Mutator",
        "line": 13,
        "diff": "- if ($subtotal <= 0.0\n+ if ($subtotal < 0.0",
        "flags": {"M1_BOUNDARY": True}
    },
    {
        "id": "M2",
        "name": "ItemsLessThanOrEqualTo_To_LessThan",
        "category": "Boundary Condition Mutator",
        "line": 13,
        "diff": "- || $itemCount <= 0\n+ || $itemCount < 0",
        "flags": {"M2_ITEMS_BOUNDARY": True}
    },
    {
        "id": "M3",
        "name": "LogicalOr_To_LogicalAnd",
        "category": "Logical Operator Mutator",
        "line": 13,
        "diff": "- if ($subtotal <= 0.0 || $itemCount <= 0)\n+ if ($subtotal <= 0.0 && $itemCount <= 0)",
        "flags": {"M3_OR_TO_AND": True}
    },
    {
        "id": "M4",
        "name": "LogicalAnd_To_LogicalOr",
        "category": "Boolean Logic Mutator",
        "line": 21,
        "diff": "- if ($isVip && $subtotal >= 100.0)\n+ if ($isVip || $subtotal >= 100.0)",
        "flags": {"M4_VIP_LOGIC": True}
    },
    {
        "id": "M5",
        "name": "GreaterThanOrEqualTo_To_GreaterThan",
        "category": "Boundary Condition Mutator",
        "line": 21,
        "diff": "- $subtotal >= 100.0\n+ $subtotal > 100.0",
        "flags": {"M5_VIP_THRESHOLD": True}
    },
    {
        "id": "M6",
        "name": "FloatMultiplierReduction",
        "category": "Arithmetic Constant Mutator",
        "line": 22,
        "diff": "- $subtotal * 0.20;\n+ $subtotal * 0.15;",
        "flags": {"M6_VIP_RATE": True}
    },
    {
        "id": "M7",
        "name": "StandardTierBoundaryShift",
        "category": "Comparison Mutator",
        "line": 23,
        "diff": "- elseif ($subtotal >= 50.0)\n+ elseif ($subtotal > 50.0)",
        "flags": {"M7_STANDARD_THRESHOLD": True}
    },
    {
        "id": "M8",
        "name": "VolumeBonus_StrictGreater_To_GreaterOrEqual",
        "category": "Boundary Condition Mutator",
        "line": 28,
        "diff": "- if ($itemCount > 5)\n+ if ($itemCount >= 5)",
        "flags": {"M8_VOLUME_BOUNDARY": True}
    },
    {
        "id": "M9",
        "name": "Addition_To_Subtraction",
        "category": "Arithmetic Operator Mutator",
        "line": 29,
        "diff": "- $discount = $discount + 5.0;\n+ $discount = $discount - 5.0;",
        "flags": {"M9_BONUS_OPERATOR": True}
    },
    {
        "id": "M10",
        "name": "ReturnValue_To_Zero",
        "category": "Return Removal Mutator",
        "line": 32,
        "diff": "- return $discount;\n+ return 0.0;",
        "flags": {"M10_RETURN_ZERO": True}
    },
]


def print_banner():
    print(f"{CLR_BLUE}{CLR_BOLD}======================================================================{CLR_RESET}")
    print(f"{CLR_CYAN}{CLR_BOLD}   PHP QUALITY ASSURANCE HARNESS: STATIC ANALYSIS & MUTATION TESTING   {CLR_RESET}")
    print(f"{CLR_GRAY}   Inspired by PHPStan Level 9 / Psalm & Infection PHP Framework      {CLR_RESET}")
    print(f"{CLR_BLUE}{CLR_BOLD}======================================================================{CLR_RESET}\n")


def execute_static_analysis():
    print(f"{CLR_YELLOW}{CLR_BOLD}[PHASE 1] Static Code Analysis & AST Complexity Audit{CLR_RESET}")
    print(f"{CLR_GRAY}Analyzing App\\Billing\\TieredDiscountCalculator against strict typing rules...{CLR_RESET}")
    time.sleep(0.15)

    metrics = StaticAnalysisEngine.analyze(PHP_SOURCE_CODE)

    print(f"  • Lines of Code (LOC)      : {CLR_WHITE}{metrics['lines_of_code']}{CLR_RESET}")
    print(f"  • Strict Types Enforced    : {CLR_GREEN if metrics['strict_types'] else CLR_RED}{metrics['strict_types']}{CLR_RESET}")
    
    cc = metrics["cyclomatic_complexity"]
    cc_color = CLR_GREEN if cc <= 5 else (CLR_YELLOW if cc <= 10 else CLR_RED)
    print(f"  • Cyclomatic Complexity    : {cc_color}{cc}{CLR_RESET} (Optimal: <= 5)")

    if metrics["findings"]:
        print(f"\n  {CLR_RED}Static Analysis Violations:{CLR_RESET}")
        for line, rule, msg in metrics["findings"]:
            print(f"    Line {line:02d}: [{rule}] {msg}")
    else:
        print(f"  {CLR_GREEN}✔ No static typing or AST policy violations detected (Level 9 Clean).{CLR_RESET}\n")


def execute_mutation_testing():
    print(f"{CLR_YELLOW}{CLR_BOLD}[PHASE 2] Baselining Initial PHPUnit Test Suite{CLR_RESET}")
    initial_passed, reason = run_test_suite()
    if not initial_passed:
        print(f"  {CLR_RED}✖ Baseline tests failed! Cannot run mutation testing: {reason}{CLR_RESET}")
        sys.exit(1)
    print(f"  {CLR_GREEN}✔ Baseline suite passed: {len(TEST_SUITE)} tests green (100% Code Coverage achieved).{CLR_RESET}\n")

    print(f"{CLR_YELLOW}{CLR_BOLD}[PHASE 3] Generating & Executing Infection Mutants{CLR_RESET}")
    print(f"{CLR_GRAY}Iterating AST mutators against test harness...{CLR_RESET}\n")

    killed_count = 0
    escaped_count = 0
    escaped_mutants = []

    print(f"{'ID':<5} | {'Mutator Class':<40} | {'Status':<10} | {'Diagnostic Message'}")
    print("-" * 85)

    for m in MUTATION_CATALOG:
        time.sleep(0.08)  # Simulate execution latency
        passed, msg = run_test_suite(mutations=m["flags"])

        if not passed:
            # Mutant was KILLED (Test suite caught the defect) -> SUCCESS
            killed_count += 1
            status_badge = f"{CLR_GREEN}KILLED {CLR_RESET}"
            diag = f"{CLR_GRAY}{msg[:40]}...{CLR_RESET}"
        else:
            # Mutant ESCAPED (Code changed but tests still passed) -> WEAK TEST COVERAGE
            escaped_count += 1
            escaped_mutants.append(m)
            status_badge = f"{CLR_RED}ESCAPED{CLR_RESET}"
            diag = f"{CLR_YELLOW}Code modified, but 0 assertions caught the change!{CLR_RESET}"

        print(f"{m['id']:<5} | {m['name']:<40} | {status_badge} | {diag}")

    total_mutants = len(MUTATION_CATALOG)
    msi = (killed_count / total_mutants) * 100.0

    print("-" * 85)
    print(f"\n{CLR_YELLOW}{CLR_BOLD}[PHASE 4] Mutation Score Indicator (MSI) Metrics{CLR_RESET}")
    print(f"  • Total Mutants Generated : {total_mutants}")
    print(f"  • Mutants Killed          : {CLR_GREEN}{killed_count}{CLR_RESET}")
    print(f"  • Mutants Escaped         : {CLR_RED}{escaped_count}{CLR_RESET}")
    
    msi_color = CLR_GREEN if msi >= 80.0 else (CLR_YELLOW if msi >= 60.0 else CLR_RED)
    print(f"  • Mutation Score (MSI)    : {msi_color}{msi:.2f}%{CLR_RESET} (Infection Standard: >= 80.00%)\n")

    if escaped_mutants:
        print(f"{CLR_MAGENTA}{CLR_BOLD}Escaped Mutant Analysis (Blind Spots in Assertions):{CLR_RESET}")
        for em in escaped_mutants:
            print(f"  {CLR_RED}Mutant {em['id']} [{em['name']}]{CLR_RESET} at line {em['line']}:")
            for diff_line in em["diff"].splitlines():
                if diff_line.startswith("-"):
                    print(f"    {CLR_RED}{diff_line}{CLR_RESET}")
                elif diff_line.startswith("+"):
                    print(f"    {CLR_GREEN}{diff_line}{CLR_RESET}")
            print(f"    {CLR_CYAN}Recommendation:{CLR_RESET} Add test asserting exact condition boundary at line {em['line']}.\n")
    else:
        print(f"  {CLR_GREEN}✔ Perfect Test Rigor: 100% Mutation Score! All mutants caught.{CLR_RESET}\n")


def main():
    print_banner()
    execute_static_analysis()
    execute_mutation_testing()
    print(f"{CLR_BLUE}{CLR_BOLD}======================================================================{CLR_RESET}")
    print(f"{CLR_GREEN}Lab Execution Completed Successfully.{CLR_RESET}")


if __name__ == "__main__":
    main()
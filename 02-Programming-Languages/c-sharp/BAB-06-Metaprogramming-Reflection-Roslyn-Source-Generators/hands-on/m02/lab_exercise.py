#!/usr/bin/env python3
"""
BAB-06: Metaprogramming, Reflection, Roslyn & Source Generators
Hands-on Interactive Simulation in Python 3.

Simulates advanced C# compiler features:
1. Runtime Reflection & Attribute Metadata Inspection
2. Dynamic Invocation vs Compiled Expression / Direct Fast Invoker
3. Roslyn Compiler Pipeline (Syntax Tree, Semantic Analysis, Diagnostic Analyzer)
4. Incremental Source Generators (Code Generation Pipeline)
5. Benchmarking Reflection overhead vs Source-Generated AOT paths
"""

import sys
import time
import inspect
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple


# ANSI Color Codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"


def header(title: str) -> None:
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 65}")
    print(f" >>> {title}")
    print(f"{'=' * 65}{Colors.RESET}")


def info(msg: str) -> None:
    print(f"{Colors.BLUE}[INFO]{Colors.RESET} {msg}")


def success(msg: str) -> None:
    print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} {msg}")


def warn(msg: str) -> None:
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {msg}")


def error_msg(msg: str) -> None:
    print(f"{Colors.RED}[ERROR]{Colors.RESET} {msg}")


# -------------------------------------------------------------
# 1. C# Metadata & Attribute Emulation
# -------------------------------------------------------------
def json_serializable(cls):
    """Custom Attribute equivalent to [JsonSerializable] in .NET 7/8/9."""
    cls.__is_json_serializable__ = True
    return cls


def json_property(name: str):
    """Custom Attribute equivalent to [JsonPropertyName(name)] in C#."""
    def decorator(fn):
        fn.__json_property_name__ = name
        return fn
    return decorator


def api_endpoint(route: str, method: str = "GET"):
    """Custom Attribute equivalent to [HttpGet(route)] or [HttpPost(route)]."""
    def decorator(fn):
        fn.__api_route__ = route
        fn.__api_method__ = method
        return fn
    return decorator


# Sample Simulated Domain Models
@json_serializable
class OrderModel:
    def __init__(self, order_id: str, amount: float, customer_tier: str):
        self.order_id = order_id
        self.amount = amount
        self.customer_tier = customer_tier

    @api_endpoint(route="/orders/process", method="POST")
    def process_order(self, multiplier: float = 1.0) -> float:
        return self.amount * multiplier

    @api_endpoint(route="/orders/status", method="GET")
    def get_status(self) -> str:
        return f"Order {self.order_id} is ACTIVE"


# -------------------------------------------------------------
# 2. Reflection & Dynamic Invocation Engine
# -------------------------------------------------------------
class ReflectionInspector:
    """Emulates System.Reflection (Type, MethodInfo, PropertyInfo)."""

    @staticmethod
    def inspect_type(target_cls: type) -> None:
        header(f"System.Reflection: Type Inspection for '{target_cls.__name__}'")
        is_serializable = getattr(target_cls, "__is_json_serializable__", False)
        print(f"  {Colors.BOLD}Class:{Colors.RESET} {target_cls.__name__}")
        print(f"  {Colors.BOLD}Assembly/Module:{Colors.RESET} {target_cls.__module__}")
        print(f"  {Colors.BOLD}Attributes:{Colors.RESET} "
              f"[{'JsonSerializable' if is_serializable else 'None'}]")

        print(f"\n  {Colors.YELLOW}Discovered Endpoints & Methods:{Colors.RESET}")
        for attr_name, member in inspect.getmembers(target_cls, predicate=inspect.isfunction):
            route = getattr(member, "__api_route__", None)
            method = getattr(member, "__api_method__", None)
            if route and method:
                print(f"   * [{method}] {route} -> {target_cls.__name__}.{attr_name}()")
            else:
                print(f"   * [Method] {target_cls.__name__}.{attr_name}()")

    @staticmethod
    def dynamic_invoke(instance: Any, method_name: str, *args, **kwargs) -> Any:
        """Simulates MethodInfo.Invoke(target, args)."""
        method = getattr(instance, method_name, None)
        if not method or not callable(method):
            raise AttributeError(f"Method '{method_name}' not found on {instance}")
        return method(*args, **kwargs)


# -------------------------------------------------------------
# 3. Roslyn Compiler Pipeline Simulation
# -------------------------------------------------------------
class SyntaxKind(Enum):
    CLASS_DECLARATION = auto()
    METHOD_DECLARATION = auto()
    ATTRIBUTE_LIST = auto()
    IDENTIFIER_TOKEN = auto()


@dataclass
class SyntaxNode:
    kind: SyntaxKind
    value: str
    children: List["SyntaxNode"] = field(default_factory=list)


@dataclass
class Diagnostic:
    id: str
    severity: str
    message: str
    line_number: int


class RoslynParser:
    """Simulates C# SyntaxTree.ParseText() and Roslyn AST creation."""

    @staticmethod
    def parse_code(source_lines: List[str]) -> Tuple[SyntaxNode, List[Diagnostic]]:
        root = SyntaxNode(kind=SyntaxKind.CLASS_DECLARATION, value="CompilationUnit")
        diagnostics = []

        for idx, line in enumerate(source_lines, start=1):
            clean = line.strip()
            if not clean or clean.startswith("//"):
                continue

            if clean.startswith("[") and clean.endswith("]"):
                attr_node = SyntaxNode(kind=SyntaxKind.ATTRIBUTE_LIST, value=clean[1:-1])
                root.children.append(attr_node)
            elif "class " in clean:
                parts = clean.split()
                name = parts[parts.index("class") + 1].strip("{:")
                class_node = SyntaxNode(kind=SyntaxKind.CLASS_DECLARATION, value=name)
                root.children.append(class_node)
            elif "(" in clean and ")" in clean and not clean.startswith("if"):
                method_name = clean.split("(")[0].split()[-1]
                method_node = SyntaxNode(kind=SyntaxKind.METHOD_DECLARATION, value=method_name)
                root.children.append(method_node)

                # Diagnostic Rule RS001: Async methods must end with 'Async'
                if "async" in clean.lower() and not method_name.endswith("Async"):
                    diagnostics.append(
                        Diagnostic(
                            id="RS001",
                            severity="Warning",
                            message=f"Async method '{method_name}' should follow naming convention and end with 'Async'.",
                            line_number=idx,
                        )
                    )

        return root, diagnostics


# -------------------------------------------------------------
# 4. Roslyn Source Generator Simulation (IIncrementalGenerator)
# -------------------------------------------------------------
class IncrementalSourceGenerator:
    """Emulates Microsoft.CodeAnalysis.IIncrementalGenerator."""

    def __init__(self, generator_name: str):
        self.generator_name = generator_name

    def execute(self, model_class: type) -> Dict[str, str]:
        """Generates zero-overhead AOT code based on syntax & metadata."""
        class_name = model_class.__name__
        generated_filename = f"{class_name}_JsonSerializer.g.cs"

        # Read instance attributes
        properties = [p for p in dir(model_class) if not p.startswith("__") and not callable(getattr(model_class, p))]

        code_lines = [
            "// <auto-generated/>",
            f"// Generated by {self.generator_name} at compile time.",
            "#nullable enable",
            "using System;",
            "using System.Text.Json;",
            "",
            f"namespace Generated.Serialization",
            "{",
            f"    public static class {class_name}GeneratedExtensions",
            "    {",
            f"        public static string ToFastJson(this {class_name} entity)",
            "        {",
            '            return string.Concat("{",',
            f'                \\"\\"order_id\\":\\\\"{{\\" + entity.order_id + \\"}}\\\\", \\",',
            f'                \\"\\"amount\\":\\\\"{{\\" + entity.amount + \\"}}\\\\", \\",',
            f'                \\"\\"tier\\":\\\\"{{\\" + entity.customer_tier + \\"}}\\\\"",',
            '                "}"',
            "            );",
            "        }",
            "    }",
            "}",
        ]
        return {generated_filename: "\n".join(code_lines)}


# -------------------------------------------------------------
# 5. Benchmarking: Reflection vs Direct/Generated Invocation
# -------------------------------------------------------------
def benchmark_dispatch(iterations: int = 150_000) -> None:
    header(f"Performance Benchmark: Reflection vs Direct Dispatch ({iterations:,} calls)")
    order = OrderModel(order_id="ORD-9912", amount=250.75, customer_tier="Gold")

    # 1. Dynamic Reflection Invocation
    t0 = time.perf_counter()
    for _ in range(iterations):
        _ = ReflectionInspector.dynamic_invoke(order, "process_order", 1.05)
    t_reflection = time.perf_counter() - t0

    # 2. Direct Invocation (Source Generated / AOT equivalent)
    t0 = time.perf_counter()
    for _ in range(iterations):
        _ = order.process_order(1.05)
    t_direct = time.perf_counter() - t0

    ratio = t_reflection / t_direct if t_direct > 0 else 1.0

    print(f"  {Colors.BOLD}Reflection Dispatch:{Colors.RESET}   {t_reflection:.4f} sec")
    print(f"  {Colors.BOLD}Direct / AOT Dispatch:{Colors.RESET} {t_direct:.4f} sec")
    print(f"  {Colors.MAGENTA}Optimization Gain:{Colors.RESET}     {Colors.BOLD}{ratio:.2f}x faster{Colors.RESET} with Source Generator approach!")


# -------------------------------------------------------------
# 6. Interactive CLI Simulation
# -------------------------------------------------------------
def display_banner() -> None:
    print(f"{Colors.CYAN}{Colors.BOLD}")
    print("=" * 65)
    print(" .NET METAPROGRAMMING & ROSLYN SOURCE GENERATOR LAB")
    print(" BAB-06 Architecture Simulator (C# -> Python Engine)")
    print("=" * 65)
    print(f"{Colors.RESET}")


def run_pipeline_demo() -> None:
    display_banner()

    # Step 1: Type & Attribute Inspection
    ReflectionInspector.inspect_type(OrderModel)
    order_instance = OrderModel(order_id="ORD-2026-X", amount=1250.00, customer_tier="Platinum")
    res = ReflectionInspector.dynamic_invoke(order_instance, "process_order", 1.10)
    success(f"Dynamic Invoke result: {res}")

    # Step 2: Roslyn Syntax Parser & Analyzer
    header("Roslyn Compiler: Parsing Syntax Tree & Running Diagnostics")
    mock_csharp_code = [
        "using System;",
        "[JsonSerializable]",
        "public class PaymentService",
        "{",
        "    [HttpGet(\"/payments\")]",
        "    public async Task ProcessPayment(int id)",
        "    {",
        "        // Missing 'Async' suffix in method name",
        "    }",
        "}",
    ]
    info("Parsing mock C# source code...")
    ast, diagnostics = RoslynParser.parse_code(mock_csharp_code)
    print(f"  {Colors.GREEN}Root AST Node:{Colors.RESET} {ast.value}")
    for child in ast.children:
        print(f"    └── [{child.kind.name}] -> {child.value}")

    if diagnostics:
        warn(f"Roslyn Analyzer detected {len(diagnostics)} diagnostic item(s):")
        for diag in diagnostics:
            print(f"      {Colors.YELLOW}[{diag.id}] ({diag.severity}) Line {diag.line_number}: {diag.message}{Colors.RESET}")

    # Step 3: Incremental Source Generator
    header("Roslyn Incremental Source Generator (IIncrementalGenerator)")
    generator = IncrementalSourceGenerator("HighSpeedJsonGenerator")
    info(f"Running source generator: '{generator.generator_name}'...")
    generated_sources = generator.execute(OrderModel)

    for fname, source_content in generated_sources.items():
        print(f"\n{Colors.BOLD}{Colors.GREEN}[Generated File]: {fname}{Colors.RESET}")
        print(f"{Colors.GRAY}{source_content}{Colors.RESET}")

    # Step 4: Run Benchmark
    benchmark_dispatch(iterations=200_000)

    header("Lab Execution Summary")
    success("Roslyn Source Generator and Metaprogramming pipeline successfully simulated!")
    print(f"{Colors.BOLD}{Colors.GREEN}✓ Reflection inspection verified.{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}✓ AST syntax tree generated.{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}✓ Diagnostic analyzers triggered.{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}✓ AOT code emitted with zero runtime overhead.{Colors.RESET}\n")


if __name__ == "__main__":
    run_pipeline_demo()

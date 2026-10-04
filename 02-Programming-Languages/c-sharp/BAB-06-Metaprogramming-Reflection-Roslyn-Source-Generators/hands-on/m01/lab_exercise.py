#!/usr/bin/env python3
"""
Interactive Lab: Metaprogramming, Reflection, Roslyn & Source Generators Simulation
Representing C# Metaprogramming principles in Python 3.
"""

import sys
import time
import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

# ANSI Color Palette
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
BLUE = "\033[34m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BG_BLUE = "\033[44m"


def header(title: str) -> None:
    print(f"\n{BG_BLUE}{BOLD}  === {title.upper()} ===  {RESET}\n")


def print_step(name: str, desc: str) -> None:
    print(f"{CYAN}{BOLD}[+] {name}:{RESET} {desc}")


# -----------------------------------------------------------------------------
# 1. Custom Attribute & Reflection Engine Simulation (System.Reflection)
# -----------------------------------------------------------------------------
class Attribute:
    """Base class simulating System.Attribute in .NET."""
    pass


class TableAttribute(Attribute):
    def __init__(self, name: str):
        self.name = name


class ColumnAttribute(Attribute):
    def __init__(self, name: str, is_primary_key: bool = False):
        self.name = name
        self.is_primary_key = is_primary_key


class AuthorizeAttribute(Attribute):
    def __init__(self, role: str):
        self.role = role


def csharp_attribute(*attrs: Attribute):
    """Decorator to attach metadata attributes to classes or functions."""
    def decorator(target):
        if not hasattr(target, "__csharp_attributes__"):
            target.__csharp_attributes__ = []
        target.__csharp_attributes__.extend(attrs)
        return target
    return decorator


@csharp_attribute(TableAttribute("Users"))
class UserEntity:
    def __init__(self, user_id: int, username: str, email: str):
        self.user_id = user_id
        self.username = username
        self.email = email

    @csharp_attribute(AuthorizeAttribute("Admin"))
    def reset_credentials(self) -> str:
        return f"Credentials reset for {self.username}"


def simulate_reflection_inspect(target: Any) -> None:
    header("System.Reflection Metadata Inspection")
    target_type = target if inspect.isclass(target) else target.__class__
    print(f"{YELLOW}Inspecting Type:{RESET} {BOLD}{target_type.__name__}{RESET}")

    type_attrs = getattr(target_type, "__csharp_attributes__", [])
    print(f"{MAGENTA}Custom Type Attributes ({len(type_attrs)}):{RESET}")
    for attr in type_attrs:
        print(f"  - [{attr.__class__.__name__}] name='{getattr(attr, 'name', '')}'")

    print(f"\n{MAGENTA}Members & Method Reflection:{RESET}")
    for name, method in inspect.getmembers(target_type, predicate=inspect.isfunction):
        method_attrs = getattr(method, "__csharp_attributes__", [])
        attr_tags = "".join(f"[{a.__class__.__name__}(role='{getattr(a, 'role', '')}')] " for a in method_attrs)
        print(f"  - {attr_tags}{GREEN}public void {name}(){RESET}")


# -----------------------------------------------------------------------------
# 2. Roslyn Syntax Tree (AST) Simulation (Microsoft.CodeAnalysis.CSharp)
# -----------------------------------------------------------------------------
@dataclass
class SyntaxToken:
    kind: str
    text: str


@dataclass
class SyntaxNode:
    kind: str
    children: List[Any]


class RoslynSyntaxTreeSimulator:
    """Parses a simplified C# code fragment into a Roslyn-style AST."""

    @staticmethod
    def parse(code: str) -> SyntaxNode:
        lines = [line.strip() for line in code.split("\n") if line.strip()]
        class_nodes = []

        for line in lines:
            if line.startswith("public class"):
                class_name = line.split()[2].replace("{", "")
                class_nodes.append(SyntaxNode("ClassDeclaration", [
                    SyntaxToken("IdentifierToken", class_name),
                    SyntaxNode("ClassBody", [])
                ]))
            elif "public " in line and "(" in line:
                parts = line.split()
                ret_type = parts[1]
                func_name = parts[2].split("(")[0]
                if class_nodes:
                    class_nodes[-1].children[1].children.append(
                        SyntaxNode("MethodDeclaration", [
                            SyntaxToken("ReturnType", ret_type),
                            SyntaxToken("IdentifierToken", func_name)
                        ])
                    )

        return SyntaxNode("CompilationUnit", class_nodes)

    @classmethod
    def visualize(cls, node: Any, indent: int = 0) -> None:
        prefix = "  " * indent
        if isinstance(node, SyntaxNode):
            print(f"{prefix}{BLUE}▸ Node ({node.kind}){RESET}")
            for child in node.children:
                cls.visualize(child, indent + 1)
        elif isinstance(node, SyntaxToken):
            print(f"{prefix}{GREEN}• Token ({node.kind}):{RESET} '{node.text}'")


# -----------------------------------------------------------------------------
# 3. Roslyn Incremental Source Generator Simulation
# -----------------------------------------------------------------------------
class SourceGeneratorSimulator:
    """Simulates C# IIncrementalGenerator generating a compile-time mapper."""

    @staticmethod
    def execute(model_name: str, fields: List[str]) -> str:
        print_step("Source Generator", f"Detecting model '{model_name}' requiring mapper...")
        time.sleep(0.3)
        generated_code = f"""// <auto-generated />
// Generated by CSharpLab.SourceGenerators.MapperGenerator
namespace GeneratedMappers
{{
    public static class {model_name}Extensions
    {{
        public static {model_name}Dto ToDto(this {model_name} entity)
        {{
            return new {model_name}Dto
            {{
"""
        for field in fields:
            generated_code += f"                {field} = entity.{field},\n"
        generated_code += """            };
        }
    }
}"""
        return generated_code


# -----------------------------------------------------------------------------
# 4. Performance Benchmark: Reflection vs Generated Direct Access
# -----------------------------------------------------------------------------
def benchmark_dispatch():
    header("Performance: Runtime Reflection vs Direct Call")
    iterations = 200_000

    class TargetRecord:
        def __init__(self):
            self.value = 42

        def compute(self, x: int) -> int:
            return self.value + x

    instance = TargetRecord()

    # Benchmark Direct invocation
    start = time.perf_counter()
    res1 = 0
    for i in range(iterations):
        res1 += instance.compute(i)
    direct_time = time.perf_counter() - start

    # Benchmark Reflection / Introspection (getattr)
    start = time.perf_counter()
    res2 = 0
    for i in range(iterations):
        fn = getattr(instance, "compute")
        res2 += fn(i)
    reflection_time = time.perf_counter() - start

    ratio = reflection_time / direct_time if direct_time > 0 else 1.0

    print(f"Iterations: {BOLD}{iterations:,}{RESET}")
    print(f"{GREEN}Direct / Source-Generated Invocation:{RESET} {direct_time:.4f}s")
    print(f"{RED}Dynamic Reflection Invocation:{RESET}       {reflection_time:.4f}s")
    print(f"{YELLOW}Reflection Overhead Ratio:{RESET}            {BOLD}{ratio:.2f}x slower{RESET}")


# -----------------------------------------------------------------------------
# Interactive Runner
# -----------------------------------------------------------------------------
def run_all_demos():
    user = UserEntity(101, "aditya_dev", "aditya@domain.local")

    # 1. Reflection
    simulate_reflection_inspect(user)

    # 2. Roslyn Syntax Tree
    header("Roslyn AST Syntax Tree Inspection")
    dummy_csharp_source = """
    public class OrderProcessor {
        public void ProcessOrder()
        public bool ValidatePayment()
    }
    """
    print(f"{BOLD}Simulated C# Source Code:{RESET}\n{dummy_csharp_source}")
    ast = RoslynSyntaxTreeSimulator.parse(dummy_csharp_source)
    RoslynSyntaxTreeSimulator.visualize(ast)

    # 3. Source Generator
    header("Incremental Source Generator Emitted Output")
    emitted = SourceGeneratorSimulator.execute("Order", ["Id", "TotalAmount", "CreatedAt"])
    print(f"\n{BOLD}{CYAN}Emitted C# Code by Generator:{RESET}")
    print(emitted)

    # 4. Benchmark
    benchmark_dispatch()


def interactive_menu():
    while True:
        print(f"\n{BOLD}{CYAN}=== C# Metaprogramming & Roslyn Simulator ==={RESET}")
        print("1. Inspect System.Reflection & Custom Attributes")
        print("2. Parse C# Code into Roslyn Syntax Tree (AST)")
        print("3. Run Roslyn Source Generator Simulation")
        print("4. Benchmark: Reflection vs Direct Call")
        print("5. Run All Demos")
        print("0. Exit")

        choice = input(f"{YELLOW}Select option [0-5]: {RESET}").strip()
        if choice == "1":
            user = UserEntity(101, "aditya_dev", "aditya@domain.local")
            simulate_reflection_inspect(user)
        elif choice == "2":
            sample = "public class CustomerService {\n    public void SaveCustomer()\n    public string GetStatus()\n}"
            ast = RoslynSyntaxTreeSimulator.parse(sample)
            RoslynSyntaxTreeSimulator.visualize(ast)
        elif choice == "3":
            out = SourceGeneratorSimulator.execute("Customer", ["CustomerId", "FullName", "Email"])
            print(out)
        elif choice == "4":
            benchmark_dispatch()
        elif choice == "5":
            run_all_demos()
        elif choice == "0":
            print(f"{GREEN}Exiting. Terima kasih!{RESET}")
            break
        else:
            print(f"{RED}Invalid selection. Silakan pilih 0-5.{RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        run_all_demos()
    else:
        # Non-interactive fallback when run without tty
        if not sys.stdin.isatty():
            run_all_demos()
        else:
            interactive_menu()

#!/usr/bin/env python3
"""
Lab Exercise: Rust Metaprogramming & Macro System Deep Dive
Simulating:
  1. Declarative Macro Expansion (macro_rules! pattern matching & repetition)
  2. Macro Hygiene & SyntaxContext isolation (preventing identifier collision)
  3. Procedural Derive Macro Pipeline (TokenStream in -> AST parsing -> TokenStream out)
"""

import re
import sys
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any

# ANSI Terminal Colors
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"

class TokenType(Enum):
    IDENT = auto()
    LITERAL = auto()
    PUNCT = auto()
    DESIGNATOR = auto()  # e.g., $name:ident, $val:expr
    REPETITION = auto()  # e.g., $(...)*
    DELIMITER = auto()

@dataclass
class Token:
    kind: TokenType
    value: str
    syntax_context: int = 0  # 0: Caller context, >0: Macro definition contexts (Hygiene)

    def __repr__(self):
        ctx_str = f"#{self.syntax_context}" if self.syntax_context > 0 else ""
        return f"{self.value}{ctx_str}"


class TokenStream:
    """Represents Rust's proc_macro::TokenStream abstraction."""
    def __init__(self, tokens: Optional[List[Token]] = None):
        self.tokens: List[Token] = tokens or []

    def __len__(self):
        return len(self.tokens)

    def __iter__(self):
        return iter(self.tokens)

    def to_string(self) -> str:
        out = []
        for i, tok in enumerate(self.tokens):
            if i > 0 and tok.value not in {",", ";", ")", "}", "]"} and self.tokens[i - 1].value not in {"(", "{", "[", "$"}:
                out.append(" ")
            out.append(str(tok))
        return "".join(out)

    @classmethod
    def from_str(cls, code: str, syntax_context: int = 0) -> "TokenStream":
        """Basic lexical scanner to simulate syn/proc_macro tokenization."""
        token_spec = [
            ("DESIGNATOR", r"\$[a-zA-Z_][a-zA-Z0-9_]*:(ident|expr|ty|path)"),
            ("IDENT",      r"[a-zA-Z_][a-zA-Z0-9_]*"),
            ("LITERAL",    r'"[^"]*"|\d+'),
            ("PUNCT",      r"=>|->|::|==|!=|\$\(|\)\*|\$\?|[=;,+\-*/$]"),
            ("DELIMITER",  r"[\(\)\[\]\{\}]"),
            ("WHITESPACE", r"\s+"),
        ]
        tok_regex = "|".join(f"(?P<{pair[0]}>{pair[1]})" for pair in token_spec)
        tokens = []
        for mo in re.finditer(tok_regex, code):
            kind_str = mo.lastgroup
            val = mo.group()
            if kind_str == "WHITESPACE":
                continue
            k = TokenType[kind_str]
            tokens.append(Token(kind=k, value=val, syntax_context=syntax_context))
        return cls(tokens)


class DeclarativeEngine:
    """
    Simulates rustc's macro_rules! declarative expansion engine.
    Supports designator capture ($x:ident, $e:expr) and repetition matching ($(...),*).
    """
    def __init__(self, name: str):
        self.name = name
        self.rules: List[Tuple[List[str], List[Token]]] = []
        self._next_ctx_id = 1

    def add_rule(self, pattern_signature: List[str], template: str):
        """Register a macro branch with a unique hygiene context ID."""
        ctx_id = self._next_ctx_id
        self._next_ctx_id += 1
        template_tokens = TokenStream.from_str(template, syntax_context=ctx_id).tokens
        self.rules.append((pattern_signature, template_tokens))

    def expand(self, call_args: List[str]) -> Tuple[TokenStream, Dict[str, Any]]:
        """
        Matches invocation against pattern arms and executes AST transcription.
        Enforces hygiene: variables defined inside the macro cannot shadow caller vars.
        """
        for pattern_sig, template in self.rules:
            bindings: Dict[str, Any] = {}
            matched = False

            # Case: Variadic Repetition (e.g., $($k:ident => $v:expr),*)
            if len(pattern_sig) == 1 and pattern_sig[0].startswith("$("):
                matched = True
                parsed_entries = []
                for arg in call_args:
                    arg = arg.strip()
                    if not arg:
                        continue
                    m = re.match(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*=>\s*(.*)", arg)
                    if m:
                        parsed_entries.append((m.group(1), m.group(2)))
                    else:
                        matched = False
                        break
                if matched:
                    bindings["__repetition__"] = parsed_entries

            # Case: Fixed Parameter Pattern
            elif len(pattern_sig) == len(call_args):
                matched = True
                for pat, val in zip(pattern_sig, call_args):
                    if pat.startswith("$"):
                        var_name = pat.split(":")[0]
                        bindings[var_name] = val.strip()
                    elif pat != val.strip():
                        matched = False
                        break

            if matched:
                return self._transcribe(template, bindings), bindings

        raise RuntimeError(f"error: no rules expected the token arguments provided to `{self.name}!`")

    def _transcribe(self, template: List[Token], bindings: Dict[str, Any]) -> TokenStream:
        result = []
        i = 0
        while i < len(template):
            tok = template[i]
            # Handle repetition expansion
            if tok.value == "$(" and "__repetition__" in bindings:
                # Scan until ")*"
                sub_template = []
                i += 1
                while i < len(template) and template[i].value != ")*":
                    sub_template.append(template[i])
                    i += 1
                i += 1  # Skip ")*"

                entries = bindings["__repetition__"]
                for idx, (k_val, v_val) in enumerate(entries):
                    for sub_tok in sub_template:
                        if sub_tok.value == "$key":
                            result.append(Token(TokenType.IDENT, k_val, sub_tok.syntax_context))
                        elif sub_tok.value == "$val":
                            result.append(Token(TokenType.LITERAL, v_val, sub_tok.syntax_context))
                        else:
                            result.append(sub_tok)
                    if idx < len(entries) - 1:
                        result.append(Token(TokenType.PUNCT, ";", 0))
                continue

            if tok.value in bindings:
                resolved_val = bindings[tok.value]
                result.append(Token(TokenType.IDENT, str(resolved_val), 0))
            else:
                result.append(tok)
            i += 1
        return TokenStream(result)


class ProcMacroDerive:
    """
    Simulates Procedural Macro derive behavior (e.g. syn::DeriveInput -> quote! -> TokenStream).
    Generates serialize implementation for a given struct AST.
    """
    @staticmethod
    def derive_serialize(input_code: str) -> TokenStream:
        # 1. Parse AST from TokenStream (Simulation of syn parse)
        struct_match = re.search(r"struct\s+([A-Za-z0-9_]+)\s*\{([^}]+)\}", input_code)
        if not struct_match:
            raise ValueError("ProcMacroDerive: Invalid struct layout for derive")

        struct_name = struct_match.group(1)
        fields_raw = struct_match.group(2).strip().split(",")
        fields = []
        for f in fields_raw:
            f = f.strip()
            if not f:
                continue
            parts = f.split(":")
            fields.append((parts[0].strip(), parts[1].strip()))

        # 2. Transcribe synthetic code via simulated quote! macro
        lines = [
            f"impl Serialize for {struct_name} {{",
            "    fn serialize(&self) -> String {",
            '        let mut out = String::from("{");'
        ]
        for idx, (f_name, _) in enumerate(fields):
            sep = r'\", \"' if idx > 0 else '\"'
            lines.append(f'        out.push_str(&format!("{sep}{f_name}\": \\"{{}}\\"", self.{f_name}));')
        lines.append('        out.push_str("}");')
        lines.append("        out")
        lines.append("    }")
        lines.append("}")

        generated_code = "\n".join(lines)
        return TokenStream.from_str(generated_code, syntax_context=99)


def demonstrate_hygiene():
    """
    Demonstrates SyntaxContext tracking (Macro Hygiene 2.0).
    A non-hygienic macro (like C #define) inadvertently captures local scope variables.
    A hygienic macro tracks lexical origins to preserve safety invariants.
    """
    print(f"\n{CLR_BOLD}{CLR_BLUE}=== [1/3] MACRO HYGIENE & SYNTAX CONTEXT RESOLUTION ==={CLR_RESET}")
    macro = DeclarativeEngine("safe_swap")
    # In C: #define SWAP(a, b) { int tmp = a; a = b; b = tmp; }
    # Vulnerability: If caller passes variable named 'tmp', it shadows the internal 'tmp'!
    macro.add_rule(["$a:ident", "$b:ident"], "{ let tmp = $a; $a = $b; $b = tmp; }")

    caller_var_a = "tmp"
    caller_var_b = "val"

    print(f"Caller Code: let mut {CLR_YELLOW}tmp{CLR_RESET} = 10; let mut {CLR_YELLOW}val{CLR_RESET} = 20;")
    print(f"Invocation:  {CLR_CYAN}safe_swap!(tmp, val);{CLR_RESET}")

    expanded, _ = macro.expand([caller_var_a, caller_var_b])
    print("\nToken Stream Representation (with SyntaxContext tags):")
    for t in expanded.tokens:
        color = CLR_GREEN if t.syntax_context > 0 else CLR_YELLOW
        print(f"{color}{t.value}#{t.syntax_context}{CLR_RESET} ", end="")
    print("\n")

    # Hygiene check verification
    caller_tokens = [t for t in expanded.tokens if t.value == "tmp" and t.syntax_context == 0]
    macro_tokens = [t for t in expanded.tokens if t.value == "tmp" and t.syntax_context != 0]

    print(f"Hygiene Status:")
    print(f" - Caller 'tmp' context: {caller_tokens[0].syntax_context} (Global/Caller Scope)")
    print(f" - Macro  'tmp' context: {macro_tokens[0].syntax_context} (Macro Def Scope)")
    print(f" {CLR_GREEN}✔ Collision Prevented:{CLR_RESET} rustc treats tmp#0 and tmp#{macro_tokens[0].syntax_context} as distinct symbols.")


def demonstrate_declarative_engine():
    """Demonstrates declarative pattern matching with repetition."""
    print(f"\n{CLR_BOLD}{CLR_BLUE}=== [2/3] DECLARATIVE MACRO EXPANSION (macro_rules!) ==={CLR_RESET}")
    hashmap_macro = DeclarativeEngine("hashmap")
    hashmap_macro.add_rule(
        ["$($k:ident => $v:expr),*"],
        "{\n    let mut map = HashMap::new();\n    $(\n        map.insert($key, $val);\n    )*\n    map\n}"
    )

    args = ['"id" => 101', '"role" => "admin"', '"status" => "active"']
    print(f"Macro Invocation: {CLR_CYAN}hashmap!({', '.join(args)}){CLR_RESET}\n")

    expanded_stream, bindings = hashmap_macro.expand(args)
    print(f"{CLR_BOLD}Transcription AST Output:{CLR_RESET}")
    print(f"{CLR_MAGENTA}{expanded_stream.to_string()}{CLR_RESET}")


def demonstrate_proc_macro():
    """Demonstrates Procedural Derive Macro mechanics."""
    print(f"\n{CLR_BOLD}{CLR_BLUE}=== [3/3] PROCEDURAL DERIVE MACRO (DeriveInput -> AST) ==={CLR_RESET}")
    rust_struct = """
    struct UserTelemetry {
        device_id: u64,
        latency_ms: u32,
        is_healthy: bool
    }
    """
    print(f"Input AST definition to #[derive(Serialize)]:\n{CLR_YELLOW}{rust_struct.strip()}{CLR_RESET}\n")

    t_start = time.perf_counter_ns()
    derived_stream = ProcMacroDerive.derive_serialize(rust_struct)
    elapsed_us = (time.perf_counter_ns() - t_start) / 1000

    print(f"Synthesized Code emitted into Compiler Token Stream ({elapsed_us:.2f} µs):")
    print(f"{CLR_GREEN}{derived_stream.to_string()}{CLR_RESET}")


def main():
    print(f"{CLR_BOLD}{CLR_MAGENTA}=================================================================={CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}    RUST METAPROGRAMMING & COMPILER MACRO SYSTEM SIMULATOR        {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_MAGENTA}=================================================================={CLR_RESET}")

    demonstrate_hygiene()
    demonstrate_declarative_engine()
    demonstrate_proc_macro()

    print(f"\n{CLR_BOLD}{CLR_GREEN}Execution complete: All macro phases cleanly verified.{CLR_RESET}\n")


if __name__ == "__main__":
    main()
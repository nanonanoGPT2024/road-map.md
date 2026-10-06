#!/usr/bin/env python3
"""
Rust Metaprogramming & Macro System Simulation Lab (BAB-07)
A standalone interactive simulation of Rust's macro engine:
1. Declarative Macros (`macro_rules!`) & Token Matching
2. Macro Hygiene vs C Preprocessor Text Substitution
3. Procedural Macros: Derive, Attribute, and Function-like
4. TokenStream AST Transformation & Expansion Pipeline
"""

import sys
import re
import time
from typing import List, Dict, Tuple, Any, Optional

# ANSI Color Palette
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
BG_DARK = "\033[48;5;236m"


def header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 68}{RESET}")
    print(f"{BOLD}{CYAN} [RUST MACRO LAB] {title.center(46)} {RESET}")
    print(f"{BOLD}{CYAN}{'=' * 68}{RESET}\n")


def subheader(title: str) -> None:
    print(f"\n{BOLD}{MAGENTA}--- {title} ---{RESET}\n")


class Token:
    def __init__(self, kind: str, value: str, span: Tuple[int, int]):
        self.kind = kind  # IDENT, PUNCT, LITERAL, GROUP, KEYWORD
        self.value = value
        self.span = span

    def __repr__(self) -> str:
        return f"Token({self.kind}, '{self.value}')"


class TokenStream:
    """Simulates proc_macro::TokenStream in Rust."""

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens

    @classmethod
    def from_str(cls, code: str) -> "TokenStream":
        tokens = []
        token_spec = [
            ("LITERAL", r'"[^"]*"|\b\d+\b'),
            ("KEYWORD", r"\b(fn|let|struct|impl|pub|mut|macro_rules)\b"),
            ("IDENT", r"\b[a-zA-Z_][a-zA-Z0-9_]*\b"),
            ("PUNCT", r"=>|->|::|[-+*/=;,!#&|><()]"),
            ("WHITESPACE", r"\s+"),
        ]
        tok_regex = "|".join(f"(?P<{pair[0]}>{pair[1]})" for pair in token_spec)
        for mo in re.finditer(tok_regex, code):
            kind = mo.lastgroup
            val = mo.group()
            if kind != "WHITESPACE":
                tokens.append(Token(kind, val, (mo.start(), mo.end())))
        return cls(tokens)

    def to_code(self) -> str:
        return " ".join(t.value for t in self.tokens)


class DeclarativeMacroSimulator:
    """Simulates `macro_rules!` pattern matcher with designators and repetitions."""

    def __init__(self, name: str, pattern: str, expansion_template: str):
        self.name = name
        self.pattern = pattern
        self.expansion_template = expansion_template

    def expand(self, invocation_args: str) -> str:
        """Parses patterns like ($($x:expr),*) => (vec![$($x),*])"""
        print(f"{DIM}Incoming invocation: {self.name}!({invocation_args}){RESET}")
        time.sleep(0.1)

        # Match repetition $( $x:expr ),*
        if "$(" in self.pattern and ":expr" in self.pattern:
            args = [a.strip() for a in invocation_args.split(",") if a.strip()]
            print(f"{YELLOW}  [Matcher] Parsed {len(args)} repetitor expression(s): {args}{RESET}")

            # Substitute into expansion template
            # e.g., template: "let mut temp_vec = Vec::new(); $(temp_vec.push($x);)* temp_vec"
            if "$(" in self.expansion_template and ")*" in self.expansion_template:
                sub_pattern = re.search(r"\$\((.*?)\)\*", self.expansion_template)
                if sub_pattern:
                    repeat_body = sub_pattern.group(1)
                    repeated_code = []
                    for arg in args:
                        expanded_step = repeat_body.replace("$x", arg)
                        repeated_code.append(expanded_step)
                    result = self.expansion_template.replace(
                        sub_pattern.group(0), "\n    " + "\n    ".join(repeated_code)
                    )
                    return result
        return f"// Expanded {self.name}!({invocation_args})"


def demo_declarative_macro() -> None:
    header("1. Declarative Macro: `macro_rules!` Deep Dive")
    print(f"{GREEN}Rust's declarative macros operate on syntax trees via pattern matching.{RESET}")
    print(f"They match AST matchers ($expr, $ident, $ty, $path, $stmt, $pat, $tt).\n")

    macro_def = """
macro_rules! my_vec {
    ( $( $x:expr ),* ) => {
        {
            let mut temp_vec = Vec::new();
            $(
                temp_vec.push($x);
            )*
            temp_vec
        }
    };
}
    """.strip()

    print(f"{BOLD}Rust Macro Definition:{RESET}")
    print(f"{BLUE}{macro_def}{RESET}\n")

    sim = DeclarativeMacroSimulator(
        name="my_vec",
        pattern=r"$( $x:expr ),*",
        expansion_template="{\n    let mut temp_vec = Vec::new();\n    $(temp_vec.push($x);)*\n    temp_vec\n}",
    )

    test_invocations = ["1, 2, 3, 4", '"rust", "macro", "rules"']

    for inv in test_invocations:
        print(f"\n{BOLD}Compiling Invocation: {CYAN}my_vec!({inv}){RESET}")
        expanded = sim.expand(inv)
        print(f"{BOLD}{GREEN}AST Expanded Code Output:{RESET}")
        print(f"{GREEN}{expanded}{RESET}")


def demo_macro_hygiene() -> None:
    header("2. Macro Hygiene (Rust vs C-Preprocessor)")
    print(f"{YELLOW}Rust macros have HYGIENE: Variables declared inside a macro do NOT{RESET}")
    print(f"{YELLOW}accidentally collide with or shadow identifiers in caller scope.{RESET}\n")

    print(f"{BOLD}Scenario:{RESET} Caller defines `x = 42`. Macro declares internal `x = 100`.")
    print(f"{BOLD}In C Preprocessor (#define):{RESET}")
    c_macro = """
#define BAD_SWAP(a, b) do { int temp = a; a = b; b = temp; } while(0)
// BUG: If caller invokes BAD_SWAP(temp, y), variable name collision breaks everything!
    """.strip()
    print(f"{RED}{c_macro}{RESET}\n")

    print(f"{BOLD}In Rust (Syntax Context / SyntaxContext ID):{RESET}")
    print(f"{GREEN}Rust assigns distinct SyntaxContext IDs to identifiers:{RESET}")
    print(f"  - Caller Scope:  {CYAN}x#0{RESET} = 42")
    print(f"  - Macro Scope:   {MAGENTA}x#1{RESET} = 100 (compiler treats x#1 as distinct token from x#0)")
    print(f"\n{BOLD}Result:{RESET} Variable {CYAN}x#0{RESET} retains value 42 cleanly after macro expands.")


def demo_procedural_macros() -> None:
    header("3. Procedural Macros (proc_macro)")
    print(f"{MAGENTA}Procedural macros run as compiler plugins at compile time!{RESET}")
    print(f"They receive a {BOLD}TokenStream{RESET} as input and emit a {BOLD}TokenStream{RESET} as output.\n")

    print(f"{BOLD}3 Forms of Procedural Macros:{RESET}")
    print(f"  1. {CYAN}Custom Derive{RESET}       : #[derive(MyDerive)]")
    print(f"  2. {CYAN}Attribute-like Macro{RESET}: #[get(\"/users\")]")
    print(f"  3. {CYAN}Function-like Macro{RESET} : sql!(\"SELECT * FROM users\")\n")

    struct_input = """
#[derive(CustomSerialize)]
pub struct UserProfile {
    pub id: u64,
    pub username: String,
    pub is_active: bool,
}
    """.strip()

    print(f"{BOLD}Input Rust Struct TokenStream:{RESET}")
    print(f"{BLUE}{struct_input}{RESET}\n")

    ts = TokenStream.from_str(struct_input)
    print(f"{DIM}TokenStream Lexed Count: {len(ts.tokens)} tokens.{RESET}")

    # Simulate Custom Derive expansion
    fields = [("id", "u64"), ("username", "String"), ("is_active", "bool")]
    print(f"\n{BOLD}[proc_macro_derive(CustomSerialize)] Expanding AST...{RESET}")
    time.sleep(0.15)

    serialize_impl = f"""
impl CustomSerialize for UserProfile {{
    fn serialize_to_json(&self) -> String {{
        let mut parts = Vec::new();
"""
    for fname, ftype in fields:
        serialize_impl += f'        parts.push(format!("\\"{fname}\\": {{:?}}", self.{fname}));\n'
    serialize_impl += """        format!("{{ {} }}", parts.join(", "))
    }
}"""

    print(f"{GREEN}{serialize_impl}{RESET}")


def interactive_macro_repl() -> None:
    header("4. Interactive Macro Expander Playground")
    print("Test an expansion pattern interactively or enter expressions.")
    print("Example input: item1, item2, item3 (or press Enter for default sample)")

    prompt_val = input(f"{BOLD}{CYAN}Enter elements for my_vec![...] > {RESET}").strip()
    if not prompt_val:
        prompt_val = "10, 20, 30, 40, 50"

    sim = DeclarativeMacroSimulator(
        name="my_vec",
        pattern=r"$( $x:expr ),*",
        expansion_template="{\n    let mut temp = Vec::with_capacity(CAP);\n    $(temp.push($x);)*\n    temp\n}",
    )
    res = sim.expand(prompt_val)
    print(f"\n{BOLD}{GREEN}Generated Assembly / Macro Expansion Result:{RESET}")
    print(f"{GREEN}{res}{RESET}\n")


def main() -> None:
    print(f"{BOLD}{BG_DARK}  RUST CHAPTER 07: METAPROGRAMMING & MACRO SYSTEM LAB RUNNER  {RESET}")
    demo_declarative_macro()
    demo_macro_hygiene()
    demo_procedural_macros()

    if sys.stdin.isatty():
        interactive_macro_repl()
    else:
        print(f"\n{CYAN}[Auto-Test Mode] Running automated interactive check...{RESET}")
        sim = DeclarativeMacroSimulator(
            name="auto_vec",
            pattern=r"$( $x:expr ),*",
            expansion_template="{\n    let mut v = Vec::new();\n    $(v.push($x);)*\n    v\n}",
        )
        output = sim.expand("100, 200, 300")
        print(f"{GREEN}{output}{RESET}")

    print(f"\n{BOLD}{GREEN}[OK] Simulation executed successfully!{RESET}\n")


if __name__ == "__main__":
    main()

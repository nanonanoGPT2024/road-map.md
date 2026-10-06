#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Teknis Ruby Object Model & Metaprogramming
BAB-02: Deep Dive Object Oriented Design & Metaprogramming

Skrip ini mendemonstrasikan secara interaktif arsitektur internal Ruby:
1. Object Model & Method Lookup Chain (Ancestors & Modules)
2. Singleton Class (Eigenclass / Metaclass)
3. Dynamic Dispatch & method_missing (Ghost Methods)
4. Dynamic Method Definition (define_method & Open Classes)
5. Context Binding & DSL Execution (instance_eval pattern)
"""

import sys
import time
from typing import Any, Callable, Dict, List, Optional


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"


def header(title: str) -> None:
    print(f"\n{Colors.BG_BLUE}{Colors.WHITE}{Colors.BOLD} [DEMO] {title.upper()} {Colors.RESET}\n")


def log_step(name: str, detail: str) -> None:
    print(f"  {Colors.CYAN}▸{Colors.RESET} {Colors.BOLD}{name}{Colors.RESET}: {detail}")


def log_code(code: str) -> None:
    print(f"    {Colors.YELLOW}irb> {code}{Colors.RESET}")


def log_result(result: Any) -> None:
    print(f"    {Colors.GREEN}=> {result}{Colors.RESET}")


# ==============================================================================
# 1. SIMULASI OBJECT MODEL & ANCESTORS LOOKUP CHAIN
# ==============================================================================
class RubyModule:
    def __init__(self, name: str):
        self.name = name
        self.methods: Dict[str, Callable] = {}

    def define_func(self, name: str, func: Callable):
        self.methods[name] = func


class RubyClass(RubyModule):
    def __init__(self, name: str, superclass: Optional["RubyClass"] = None):
        super().__init__(name)
        self.superclass = superclass
        self.included_modules: List[RubyModule] = []

    def include_module(self, mod: RubyModule):
        # Ruby meletakkan module yang di-include tepat di atas class dalam chain ancestors
        self.included_modules.insert(0, mod)

    def ancestors(self) -> List[str]:
        chain = [self.name]
        for mod in self.included_modules:
            chain.append(f"Module({mod.name})")
        if self.superclass:
            chain.extend(self.superclass.ancestors())
        return chain

    def find_method(self, method_name: str) -> Optional[Callable]:
        if method_name in self.methods:
            return self.methods[method_name]
        for mod in self.included_modules:
            if method_name in mod.methods:
                return mod.methods[method_name]
        if self.superclass:
            return self.superclass.find_method(method_name)
        return None


class RubyObject:
    def __init__(self, ruby_class: RubyClass):
        self.ruby_class = ruby_class
        self.singleton_class: Optional[RubyClass] = None
        self.instance_vars: Dict[str, Any] = {}

    def get_singleton_class(self) -> RubyClass:
        if not self.singleton_class:
            # Singleton class mewarisi class asli objek
            self.singleton_class = RubyClass(f"#<Class:{hex(id(self))}>", self.ruby_class)
        return self.singleton_class

    def send(self, method_name: str, *args, **kwargs) -> Any:
        # Prioritas 1: Singleton class jika ada
        if self.singleton_class:
            func = self.singleton_class.find_method(method_name)
            if func:
                return func(self, *args, **kwargs)

        # Prioritas 2: Hierarchy normal (Class -> Modules -> Superclass)
        func = self.ruby_class.find_method(method_name)
        if func:
            return func(self, *args, **kwargs)

        # Prioritas 3: method_missing
        missing_handler = self.ruby_class.find_method("method_missing")
        if missing_handler:
            return missing_handler(self, method_name, *args, **kwargs)

        raise AttributeError(f"undefined method `{method_name}' for {self.ruby_class.name}")


# ==============================================================================
# DEMONSTRASI FITUR-FITUR INTI
# ==============================================================================
def demo_ancestors_lookup():
    header("1. Ruby Method Lookup Chain & Included Modules")
    print(f"{Colors.WHITE}Di Ruby, urutan pencarian method: Singleton -> Class -> Modules -> Superclass{Colors.RESET}\n")

    basic_obj = RubyClass("BasicObject")
    kernel_mod = RubyModule("Kernel")
    obj_class = RubyClass("Object", basic_obj)
    obj_class.include_module(kernel_mod)

    log_step("Base Hierarchy", "BasicObject <- Kernel (included in Object) <- Object")

    printable_mod = RubyModule("Printable")
    printable_mod.define_func("print_info", lambda self: f"Output dari Printable module: {self.instance_vars.get('title')}")

    doc_class = RubyClass("Document", obj_class)
    doc_class.include_module(printable_mod)
    doc_class.define_func("save", lambda self: "Dokumen berhasil disimpan ke disk.")

    log_step("Class Definition", "Document mewarisi Object dan meng-include Printable")
    log_code("Document.ancestors")
    log_result(" -> ".join(doc_class.ancestors()))

    doc = RubyObject(doc_class)
    doc.instance_vars["title"] = "Ruby Metaprogramming Deep Dive"

    log_code("doc.save")
    log_result(doc.send("save"))

    log_code("doc.print_info (resolving via included module)")
    log_result(doc.send("print_info"))


def demo_singleton_class():
    header("2. Singleton Classes (Eigenclass / Metaclass)")
    print(f"{Colors.WHITE}Menambahkan method khusus ke satu instance tertentu tanpa memengaruhi instance lain.{Colors.RESET}\n")

    person_class = RubyClass("Person")
    person_class.define_func("greet", lambda self: "Halo!")

    alice = RubyObject(person_class)
    bob = RubyObject(person_class)

    log_step("Instance Biasa", "Alice dan Bob berbagi definisi class Person")
    log_code("alice.greet")
    log_result(alice.send("greet"))
    log_code("bob.greet")
    log_result(bob.send("greet"))

    log_step("Mendefinisikan Singleton Method", "def alice.special_talent ... end")
    alice_eigen = alice.get_singleton_class()
    alice_eigen.define_func("special_talent", lambda self: "Alice bisa memprogram Metaprogramming Ruby dalam tidur!")

    log_code("alice.special_talent")
    log_result(alice.send("special_talent"))

    log_step("Verifikasi Isolasi", "Bob tidak memiliki method special_talent")
    try:
        bob.send("special_talent")
    except AttributeError as e:
        log_result(f"{Colors.RED}{e}{Colors.RESET}")


def demo_dynamic_dispatch_and_method_missing():
    header("3. Dynamic Dispatch & Ghost Methods (method_missing)")
    print(f"{Colors.WHITE}Menangkap pemanggilan method yang tidak didefinisikan secara eksplisit (Pola Active Record finder).{Colors.RESET}\n")

    record_class = RubyClass("DynamicRecord")
    database_table = [
        {"id": 1, "name": "Budi", "email": "budi@example.com", "role": "admin"},
        {"id": 2, "name": "Siti", "email": "siti@example.com", "role": "developer"},
    ]

    def dynamic_method_missing(self, method_name: str, *args, **kwargs):
        if method_name.startswith("find_by_"):
            column = method_name.replace("find_by_", "")
            val = args[0] if args else None
            log_step("Ghost Method Intercepted", f"`{method_name}` diterjemahkan ke query database: `{column} == '{val}'`")
            for row in database_table:
                if row.get(column) == val:
                    return f"Found Record: {row}"
            return "Record not found"
        raise AttributeError(f"undefined method `{method_name}'")

    record_class.define_func("method_missing", dynamic_method_missing)
    model = RubyObject(record_class)

    log_code("model.find_by_email('siti@example.com')")
    log_result(model.send("find_by_email", "siti@example.com"))

    log_code("model.find_by_role('admin')")
    log_result(model.send("find_by_role", "admin"))


def demo_open_classes_and_define_method():
    header("4. Open Classes (Monkey Patching) & define_method")
    print(f"{Colors.WHITE}Membuka kembali class yang sudah ada dan menambahkan fungsionalitas runtime.{Colors.RESET}\n")

    string_class = RubyClass("String")
    string_class.define_func("value", lambda self: self.instance_vars.get("raw", ""))

    s1 = RubyObject(string_class)
    s1.instance_vars["raw"] = "arsitektur ruby modern"

    log_step("Class String Asli", f"Data: '{s1.send('value')}'")

    log_step("Open Class Injection", "Membuka kembali class String dan inject helper `to_screaming_snake_case`")
    # Monkey patching / open class
    string_class.define_func(
        "to_screaming_snake_case",
        lambda self: self.instance_vars.get("raw", "").replace(" ", "_").upper()
    )

    log_code("s1.to_screaming_snake_case")
    log_result(s1.send("to_screaming_snake_case"))

    log_step("Dynamic define_method Loop", "Generate method getter/setter otomatis dari daftar atribut")
    attributes = ["title", "author", "price"]
    book_class = RubyClass("Book")

    for attr in attributes:
        # Meniru define_method Ruby
        getter_name = attr
        setter_name = f"set_{attr}"
        book_class.define_func(getter_name, (lambda a: lambda self: self.instance_vars.get(a))(attr))
        book_class.define_func(setter_name, (lambda a: lambda self, val: self.instance_vars.update({a: val}) or val)(attr))

    book = RubyObject(book_class)
    log_code("book.set_title('Metaprogramming Ruby 2')")
    book.send("set_title", "Metaprogramming Ruby 2")
    log_code("book.title")
    log_result(book.send("title"))


def demo_dsl_instance_eval():
    header("5. Context Binding & Clean DSL (instance_eval pattern)")
    print(f"{Colors.WHITE}Menjalankan block kode dalam konteks instance objek untuk syntax DSL deklaratif.{Colors.RESET}\n")

    class RouteBuilder:
        def __init__(self):
            self.routes: List[str] = []

        def get(self, path: str, handler: str):
            self.routes.append(f"GET    {path:<20} -> {handler}")

        def post(self, path: str, handler: str):
            self.routes.append(f"POST   {path:<20} -> {handler}")

        def delete(self, path: str, handler: str):
            self.routes.append(f"DELETE {path:<20} -> {handler}")

    # Simulasi instance_eval: mengeksekusi lambda dengan receiver 'self' yang diarahkan ke builder
    def draw_routes(dsl_block: Callable[[RouteBuilder], None]) -> List[str]:
        builder = RouteBuilder()
        dsl_block(builder)
        return builder.routes

    log_step("DSL Block Definition", "Sintaks gaya router Ruby on Rails / Sinatra")
    def routes_config(r: RouteBuilder):
        r.get("/users", "UsersController#index")
        r.post("/users", "UsersController#create")
        r.get("/users/:id", "UsersController#show")
        r.delete("/users/:id", "UsersController#destroy")

    compiled_routes = draw_routes(routes_config)
    print(f"{Colors.BOLD}{Colors.MAGENTA}  Tabel Routing Terbentuk via DSL:{Colors.RESET}")
    for route in compiled_routes:
        print(f"    {Colors.GREEN}✓{Colors.RESET} {route}")


def main():
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.WHITE} SIMULATOR INTI: RUBY OBJECT MODEL & METAPROGRAMMING (BAB 02){Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}")

    demo_ancestors_lookup()
    time.sleep(0.1)
    demo_singleton_class()
    time.sleep(0.1)
    demo_dynamic_dispatch_and_method_missing()
    time.sleep(0.1)
    demo_open_classes_and_define_method()
    time.sleep(0.1)
    demo_dsl_instance_eval()

    print(f"\n{Colors.BOLD}{Colors.GREEN}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN} ✓ Semua demonstrasi konsep inti Ruby selesai dengan sukses.{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}{'='*70}{Colors.RESET}\n")


if __name__ == "__main__":
    main()

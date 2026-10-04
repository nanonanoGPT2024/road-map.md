#!/usr/bin/env python3
"""
Lab: Deep-Dive Object-Oriented Design & Metaprogramming (Ruby Model Simulation)
Category: 02-Programming-Languages / Ruby / Chapter 02

This lab implements an execution engine that simulates Ruby's internal Object Model,
Ancestor Lookup Chain (including eigenclasses, include, prepend), dynamic dispatch
via `method_missing`, and DSL metaprogramming mechanics using pure Python 3.
"""

import sys
import time
from typing import Dict, List, Any, Optional, Callable

# --- ANSI Terminal Formatting ---
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"

def print_header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 75}{RESET}")
    print(f"{BOLD}{CYAN} [RUBY RUNTIME SIMULATION] {title.upper()}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 75}{RESET}")

def print_step(msg: str) -> None:
    print(f"{YELLOW}==>{RESET} {BOLD}{msg}{RESET}")

def print_success(msg: str) -> None:
    print(f"{GREEN} [OK] {msg}{RESET}")

def print_info(label: str, val: Any) -> None:
    print(f"  {BLUE}* {label}:{RESET} {val}")

# --- Ruby Object Model Simulation ---

class RubyModule:
    """Represents a Ruby Module capable of being included or prepended."""
    def __init__(self, name: str):
        self.name: str = name
        self.methods: Dict[str, Callable] = {}
        self.included_modules: List['RubyModule'] = []
        self.prepended_modules: List['RubyModule'] = []

    def define_method(self, name: str, func: Callable) -> None:
        """Ruby's Module#define_method equivalent."""
        self.methods[name] = func

    def include(self, mod: 'RubyModule') -> None:
        """Ruby's Module#include (appends behind current class in lookup)."""
        if mod not in self.included_modules:
            self.included_modules.append(mod)

    def prepend(self, mod: 'RubyModule') -> None:
        """Ruby's Module#prepend (intercepts calls before current class in lookup)."""
        if mod not in self.prepended_modules:
            self.prepended_modules.insert(0, mod)

    def __repr__(self) -> str:
        return f"#<Module:{self.name}>"


class RubyClass(RubyModule):
    """Represents a Ruby Class with single-inheritance and an Eigenclass."""
    def __init__(self, name: str, superclass: Optional['RubyClass'] = None):
        super().__init__(name)
        self.superclass: Optional['RubyClass'] = superclass
        self._eigenclass: Optional['RubyEigenclass'] = None

    @property
    def eigenclass(self) -> 'RubyEigenclass':
        """Metaclass / Singleton Class in Ruby."""
        if not self._eigenclass:
            self._eigenclass = RubyEigenclass(f"#<Class:{self.name}>", 
                                              superclass=self.superclass.eigenclass if self.superclass else None)
        return self._eigenclass

    def ancestors(self) -> List[RubyModule]:
        """Calculates Ruby Ancestor Lookup Path: Prepend -> Self -> Include -> Superclass ancestors."""
        chain: List[RubyModule] = []
        
        # 1. Prepended modules (executed before self)
        for mod in self.prepended_modules:
            for ancestor in mod.ancestors():
                if ancestor not in chain:
                    chain.append(ancestor)

        # 2. Self
        if self not in chain:
            chain.append(self)

        # 3. Included modules (executed after self)
        for mod in self.included_modules:
            for ancestor in mod.ancestors():
                if ancestor not in chain:
                    chain.append(ancestor)

        # 4. Superclass chain
        if self.superclass:
            for sup_ancestor in self.superclass.ancestors():
                if sup_ancestor not in chain:
                    chain.append(sup_ancestor)

        return chain

    def new_instance(self, *args, **kwargs) -> 'RubyObject':
        """Ruby Class#new instantiation hook."""
        instance = RubyObject(klass=self)
        if instance.respond_to("initialize"):
            instance.send("initialize", *args, **kwargs)
        return instance

    def __repr__(self) -> str:
        return f"#<Class:{self.name}>"


class RubyEigenclass(RubyClass):
    """Specialized Class for Singleton Methods."""
    def __init__(self, name: str, superclass: Optional['RubyClass'] = None):
        super().__init__(name, superclass)


class RubyObject:
    """Represents any instance of a Ruby class, supporting eigenclass and dynamic messaging."""
    def __init__(self, klass: RubyClass):
        self.klass: RubyClass = klass
        self._singleton_class: Optional['RubyEigenclass'] = None
        self.instance_variables: Dict[str, Any] = {}

    @property
    def singleton_class(self) -> RubyEigenclass:
        """Access or create object's eigenclass (class << self)."""
        if not self._singleton_class:
            self._singleton_class = RubyEigenclass(f"#<Class:#<{self.klass.name}:{id(self)}>>", 
                                                    superclass=self.klass)
        return self._singleton_class

    def instance_variable_set(self, var_name: str, val: Any) -> None:
        self.instance_variables[var_name] = val

    def instance_variable_get(self, var_name: str) -> Any:
        return self.instance_variables.get(var_name)

    def lookup_ancestors(self) -> List[RubyModule]:
        """Method lookup order for this specific object."""
        lookup_chain: List[RubyModule] = []
        if self._singleton_class:
            lookup_chain.extend(self._singleton_class.ancestors())
        else:
            lookup_chain.extend(self.klass.ancestors())
        return lookup_chain

    def respond_to(self, method_name: str) -> bool:
        """Determines if method exists in ancestor chain or method_missing is defined."""
        for ancestor in self.lookup_ancestors():
            if method_name in ancestor.methods:
                return True
        return False

    def send(self, method_name: str, *args, **kwargs) -> Any:
        """Ruby's Object#send message passing dispatch."""
        traversed: List[str] = []
        for ancestor in self.lookup_ancestors():
            traversed.append(ancestor.name)
            if method_name in ancestor.methods:
                # Method found along resolution path
                func = ancestor.methods[method_name]
                return func(self, *args, **kwargs)

        # Fallback to method_missing hook if present
        for ancestor in self.lookup_ancestors():
            if "method_missing" in ancestor.methods:
                mm_func = ancestor.methods["method_missing"]
                return mm_func(self, method_name, *args, **kwargs)

        raise AttributeError(f"NoMethodError: undefined method `{method_name}' for {self}."
                             f" Checked lookup path: {' -> '.join(traversed)}")

    def __repr__(self) -> str:
        return f"#<{self.klass.name}:{hex(id(self))}>"


# --- Simulation Components & Scenarios ---

def build_base_hierarchy():
    """Builds standard Ruby Kernel & BasicObject foundations."""
    basic_object = RubyClass("BasicObject", superclass=None)
    kernel_module = RubyModule("Kernel")
    
    # Kernel methods
    kernel_module.define_method("puts", lambda self, text: print(f"  {MAGENTA}[Kernel#puts]{RESET} {text}"))
    
    ruby_object = RubyClass("Object", superclass=basic_object)
    ruby_object.include(kernel_module)
    return basic_object, kernel_module, ruby_object


def run_ancestor_resolution_lab():
    print_header("Scenario 1: Ancestor Lookup Hierarchy (Prepend vs Include)")
    _, _, RubyBaseObject = build_base_hierarchy()

    # Define Classes and Modules
    person_cls = RubyClass("Person", superclass=RubyBaseObject)
    loggable_mod = RubyModule("Loggable")
    audit_mod = RubyModule("AuditTrail")

    # Define identical method across components to track precedence
    audit_mod.define_method("identify", lambda self: "Identified via [AuditTrail Module (Prepended)]")
    person_cls.define_method("identify", lambda self: "Identified via [Person Class (Self)]")
    loggable_mod.define_method("identify", lambda self: "Identified via [Loggable Module (Included)]")

    # Apply prepend and include
    person_cls.include(loggable_mod)
    person_cls.prepend(audit_mod)

    print_step("Inspecting Person ancestor hierarchy:")
    ancestors = person_cls.ancestors()
    for idx, anc in enumerate(ancestors):
        print_info(f"Depth {idx}", anc.name)

    print_step("Dispatching `identify` to Person instance:")
    user = person_cls.new_instance()
    result = user.send("identify")
    print_success(f"Resolution Result: {BOLD}{result}{RESET}")
    assert "AuditTrail" in result, "Prepend should have highest precedence over Class implementation!"


def run_eigenclass_singleton_lab():
    print_header("Scenario 2: Eigenclass (Singleton Class) Metaprogramming")
    _, _, RubyBaseObject = build_base_hierarchy()

    cat_cls = RubyClass("Cat", superclass=RubyBaseObject)
    cat_cls.define_method("speak", lambda self: "Meow!")

    felix = cat_cls.new_instance()
    garfield = cat_cls.new_instance()

    print_step("Baseline verification of uniform behavior:")
    print_info("felix.speak()", felix.send("speak"))
    print_info("garfield.speak()", garfield.send("speak"))

    print_step("Opening eigenclass (class << felix) to define singleton behavior...")
    # Inject method strictly into felix's singleton class
    felix.singleton_class.define_method("speak", lambda self: "Meow! But I am a special cat!")
    felix.singleton_class.define_method("fly", lambda self: "Look, I am flying!")

    print_info("felix.speak()", felix.send("speak"))
    print_info("garfield.speak()", garfield.send("speak"))
    print_info("felix.fly()", felix.send("fly"))

    # Assert garfield is unaffected
    try:
        garfield.send("fly")
        raise AssertionError("Garfield should not possess singleton methods of Felix!")
    except AttributeError:
        print_success("Metaclass isolation verified: garfield cannot execute `fly`.")


def run_method_missing_activerecord_lab():
    print_header("Scenario 3: ActiveRecord Dynamic Finder via `method_missing`")
    _, _, RubyBaseObject = build_base_hierarchy()

    # Mock Database record repository
    in_memory_db = [
        {"id": 1, "username": "alice_dev", "role": "admin", "active": True},
        {"id": 2, "username": "bob_ops", "role": "engineer", "active": True},
        {"id": 3, "username": "charlie", "role": "engineer", "active": False}
    ]

    active_record_base = RubyClass("ActiveRecord::Base", superclass=RubyBaseObject)

    def dynamic_method_missing(self, method_name: str, *args, **kwargs):
        """Simulates ActiveRecord's dynamic find_by_* query generation."""
        if method_name.startswith("find_by_"):
            attr_spec = method_name.replace("find_by_", "")
            attributes = attr_spec.split("_and_")
            
            if len(attributes) != len(args):
                raise ValueError(f"Argument count mismatch: expected {len(attributes)} got {len(args)}")

            print_info("Dynamic Query Dispatched", f"Finding by {attributes} with values {args}")
            # Filter DB
            for record in in_memory_db:
                matches = all(str(record.get(attr)) == str(val) for attr, val in zip(attributes, args))
                if matches:
                    return record
            return None
        raise AttributeError(f"NoMethodError: undefined method `{method_name}'")

    active_record_base.define_method("method_missing", dynamic_method_missing)

    user_model = RubyClass("User", superclass=active_record_base)
    user_repo = user_model.new_instance()

    print_step("Executing `find_by_username('bob_ops')` dynamically:")
    res1 = user_repo.send("find_by_username", "bob_ops")
    print_success(f"Record matched: {res1}")

    print_step("Executing multi-parameter `find_by_role_and_active('engineer', True)`:")
    res2 = user_repo.send("find_by_role_and_active", "engineer", True)
    print_success(f"Record matched: {res2}")

    print_step("Executing query for non-existent record:")
    res3 = user_repo.send("find_by_username", "ghost_user")
    print_info("Ghost search result", res3)
    assert res3 is None


def run_dsl_builder_lab():
    print_header("Scenario 4: Declarative Routing DSL via Metaprogramming")
    _, _, RubyBaseObject = build_base_hierarchy()

    # Route Drawer Class
    router_cls = RubyClass("Router", superclass=RubyBaseObject)

    def router_init(self):
        self.instance_variable_set("@routes", [])

    def router_draw(self, route_spec: str, to_handler: str):
        routes = self.instance_variable_get("@routes")
        routes.append({"route": route_spec, "target": to_handler})
        self.instance_variable_set("@routes", routes)

    def router_routes(self):
        return self.instance_variable_get("@routes")

    router_cls.define_method("initialize", router_init)
    router_cls.define_method("get", lambda self, path, to: router_draw(self, f"GET {path}", to))
    router_cls.define_method("post", lambda self, path, to: router_draw(self, f"POST {path}", to))
    router_cls.define_method("routes", router_routes)

    # Dynamic DSL Evaluation
    def draw_routes_dsl(builder_instance: RubyObject, config_instructions: List[tuple]):
        """Simulates Ruby's instance_eval block evaluation for DSL setup."""
        for verb, path, controller in config_instructions:
            builder_instance.send(verb, path, controller)

    router = router_cls.new_instance()
    dsl_instructions = [
        ("get", "/api/v1/health", "HealthCheckController#status"),
        ("get", "/users", "UsersController#index"),
        ("post", "/users", "UsersController#create"),
        ("post", "/login", "SessionsController#new")
    ]

    print_step("Compiling routing table using Declarative DSL mechanics...")
    start_t = time.perf_counter()
    draw_routes_dsl(router, dsl_instructions)
    duration = (time.perf_counter() - start_t) * 1000

    compiled_routes = router.send("routes")
    for r in compiled_routes:
        print_info("Mounted Route", f"{r['route']:<20} => {r['target']}")

    print_success(f"DSL evaluation completed in {duration:.4f} ms across {len(compiled_routes)} declarations.")


def main():
    print_header("Ruby Deep Dive: OOP & Metaprogramming Runtime Simulation")
    try:
        run_ancestor_resolution_lab()
        run_eigenclass_singleton_lab()
        run_method_missing_activerecord_lab()
        run_dsl_builder_lab()

        print(f"\n{BOLD}{GREEN}{'=' * 75}{RESET}")
        print(f"{BOLD}{GREEN} [SUMMARY] All Ruby Metaprogramming & OOD Subsystems Executed Successfully.{RESET}")
        print(f"{BOLD}{GREEN}{'=' * 75}{RESET}\n")
    except Exception as e:
        print(f"\n{BOLD}{RED}[FATAL RUNTIME ERROR]: {e}{RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
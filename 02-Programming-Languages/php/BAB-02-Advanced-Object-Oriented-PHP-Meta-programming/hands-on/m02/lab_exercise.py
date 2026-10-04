#!/usr/bin/env python3
"""
Lab Hands-on: Advanced Object-Oriented PHP & Meta-programming Engine Simulator
Focus: Trait Composition, Conflict Resolution, Magic Methods (__call, __get, __set),
       PHP 8 Attributes, and Reflection-based Dependency Injection Container.
"""

import sys
import inspect
from typing import Dict, Any, Callable, Type, get_type_hints

# Terminal ANSI Formatting Constants
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_MAGENTA = "\033[95m"


class Attribute:
    """Represents PHP 8 #[Attribute] metadata wrapper."""
    pass


class Inject(Attribute):
    """Custom PHP 8-style attribute to signal dependency injection."""
    def __init__(self, qualifier: str = None):
        self.qualifier = qualifier


class Route(Attribute):
    """Custom PHP 8-style attribute representing an HTTP endpoint routing."""
    def __init__(self, path: str, method: str = "GET"):
        self.path = path
        self.method = method.upper()


def php_attribute(attr_instance: Attribute):
    """Decorator to attach PHP 8 attributes directly to classes or methods."""
    def decorator(target):
        if not hasattr(target, "__php_attributes__"):
            target.__php_attributes__ = []
        target.__php_attributes__.append(attr_instance)
        return target
    return decorator


class TraitComposer:
    """
    Simulates PHP's horizontal method reuse (Traits) with explicit conflict 
    resolution rules: 'insteadof' precedence and 'as' alias mechanics.
    """
    @staticmethod
    def compose(target_cls: Type, traits: list, rules: Dict[str, Any] = None):
        rules = rules or {}
        insteadof_rules = rules.get("insteadof", {})
        alias_rules = rules.get("as", {})

        methods_to_apply = {}

        for trait in traits:
            for name, member in inspect.getmembers(trait, predicate=inspect.isfunction):
                if name.startswith("__"):
                    continue
                
                # Check conflict resolution (insteadof)
                if name in insteadof_rules:
                    preferred_trait = insteadof_rules[name]
                    if trait is not preferred_trait:
                        continue  # Skip shadowed trait method
                
                # Check alias (as)
                alias_name = alias_rules.get((trait, name), name)
                methods_to_apply[alias_name] = member

        for method_name, method_func in methods_to_apply.items():
            setattr(target_cls, method_name, method_func)
        
        return target_cls


class PHPObject:
    """
    Base object modeling Zend Engine meta-programming semantics:
    __get, __set, and __call intercepts dynamic runtime interaction.
    """
    def __init__(self):
        self._property_bag: Dict[str, Any] = {}

    def __getattr__(self, name: str):
        # Fallback to PHP __get magic method
        if hasattr(self, "__get"):
            return self.__get(name)
        raise AttributeError(f"Undefined property: {self.__class__.__name__}::${name}")

    def __setattr__(self, name: str, value: Any):
        # Bypass for internal mechanics
        if name in ("_property_bag",) or name.startswith("_"):
            super().__setattr__(name, value)
            return

        # Trigger PHP __set magic method if declared
        if hasattr(self, "__set"):
            self.__set(name, value)
        else:
            super().__setattr__(name, value)

    def __call__(self, method_name: str, *args, **kwargs):
        # Emulate PHP __call fallback for non-existent dynamic methods
        if hasattr(self, "__call"):
            return getattr(self, "__call")(method_name, list(args))
        raise AttributeError(f"Call to undefined method {self.__class__.__name__}::{method_name}()")


class PHPReflection:
    """
    Simulates PHP's Reflection API (ReflectionClass, ReflectionMethod).
    Extracts type hints, attributes, and dynamically instantiates objects.
    """
    @staticmethod
    def inspect_attributes(target: Any) -> list:
        return getattr(target, "__php_attributes__", [])

    @staticmethod
    def get_constructor_parameters(cls: Type) -> Dict[str, Type]:
        init = getattr(cls, "__init__", None)
        if not init or init is object.__init__:
            return {}
        hints = get_type_hints(init)
        hints.pop("return", None)
        return hints


class Container:
    """
    PSR-11 Inspired Dependency Injection Container featuring recursive 
    auto-wiring using simulated Reflection and Attribute checks.
    """
    def __init__(self):
        self._bindings: Dict[str, Any] = {}
        self._instances: Dict[str, Any] = {}

    def bind(self, abstract: str, concrete: Any):
        self._bindings[abstract] = concrete

    def singleton(self, abstract: str, concrete: Any):
        self._instances[abstract] = concrete

    def resolve(self, target: Any) -> Any:
        # Check singleton instances
        if isinstance(target, str) and target in self._instances:
            return self._instances[target]

        cls = self._bindings.get(target, target)
        if not inspect.isclass(cls):
            return cls

        # Inspect constructor through PHP-style Reflection
        dependencies = []
        hints = PHPReflection.get_constructor_parameters(cls)

        for param_name, param_type in hints.items():
            if param_type in self._instances:
                dependencies.append(self._instances[param_type])
            elif param_type in self._bindings:
                dependencies.append(self.resolve(param_type))
            else:
                # Attempt to autowire the class
                dependencies.append(self.resolve(param_type))

        instance = cls(*dependencies)
        return instance


# -------------------------------------------------------------
# Test Domain: Simulating PHP Services, Traits, and Controllers
# -------------------------------------------------------------

class LoggerTrait:
    def log(self, message: str):
        return f"[Trait::Logger] INFO: {message}"

    def render(self):
        return "Rendering output via LoggerTrait"


class OutputFormatterTrait:
    def format(self, message: str):
        return f"*** {message.upper()} ***"

    def render(self):
        return "Rendering output via OutputFormatterTrait"


class DatabaseDriver:
    def query(self, sql: str) -> str:
        return f"Executing SQL on engine: '{sql}'"


class UserRepository(PHPObject):
    def __init__(self, db: DatabaseDriver):
        super().__init__()
        self.db = db

    def __call(self, name: str, arguments: list):
        # PHP Dynamic Finder emulation (e.g. findByName, findByEmail)
        if name.startswith("findBy"):
            column = name[6:].lower()
            val = arguments[0] if arguments else "NULL"
            return self.db.query(f"SELECT * FROM users WHERE {column} = '{val}' LIMIT 1")
        raise AttributeError(f"Call to undefined method UserRepository::{name}()")


class BaseController(PHPObject):
    def __init__(self):
        super().__init__()

    def __set(self, name: str, value: Any):
        self._property_bag[name] = value

    def __get(self, name: str):
        if name in self._property_bag:
            return self._property_bag[name]
        return f"[Dynamic fallback for ${name}]"


class UserController(BaseController):
    def __init__(self, repo: UserRepository):
        super().__init__()
        self.repo = repo

    @php_attribute(Route("/api/users/profile", method="POST"))
    def update_profile(self, user_id: int):
        return f"User #{user_id} profile updated."


# Apply Traits with conflict resolution to UserController
# Conflict: both LoggerTrait and OutputFormatterTrait define `render()`
TraitComposer.compose(
    UserController,
    traits=[LoggerTrait, OutputFormatterTrait],
    rules={
        "insteadof": {"render": LoggerTrait},
        "as": {(OutputFormatterTrait, "render"): "renderFormatted"}
    }
)


def run_lab():
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}  ADVANCED OOP & META-PROGRAMMING: RUNTIME SIMULATOR (PHP EQUIVALENT) {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}\n")

    # 1. Dependency Injection Container & Auto-Wiring Simulation
    print(f"{CLR_BOLD}{CLR_YELLOW}[1] Initializing DI Container & Auto-Wiring Injection...{CLR_RESET}")
    container = Container()
    container.singleton(DatabaseDriver, DatabaseDriver())

    # UserController depends on UserRepository, which depends on DatabaseDriver
    controller = container.resolve(UserController)
    print(f" {CLR_GREEN}✔{CLR_RESET} Resolved instance graph: {CLR_MAGENTA}{controller.__class__.__name__}{CLR_RESET}")
    print(f"   -> Repository: {controller.repo.__class__.__name__}")
    print(f"   -> DB Driver:  {controller.repo.db.__class__.__name__}\n")

    # 2. Trait Composition & Conflict Resolution Demonstration
    print(f"{CLR_BOLD}{CLR_YELLOW}[2] Testing Trait Method Resolution & Aliasing...{CLR_RESET}")
    # Call LoggerTrait method
    log_res = controller.log("Controller dispatched successfully.")
    print(f"   LoggerTrait output    : {CLR_GREEN}{log_res}{CLR_RESET}")

    # Call conflicting method where LoggerTrait takes precedence
    resolved_render = controller.render()
    print(f"   Precedence resolved   : {CLR_CYAN}{resolved_render}{CLR_RESET} (LoggerTrait::insteadof)")

    # Call aliased method from OutputFormatterTrait
    aliased_render = controller.renderFormatted()
    print(f"   Aliased method call   : {CLR_CYAN}{aliased_render}{CLR_RESET} (OutputFormatterTrait::as)\n")

    # 3. Magic Methods (__call, __get, __set)
    print(f"{CLR_BOLD}{CLR_YELLOW}[3] Testing PHP Magic Interceptors (__set, __get, __call)...{CLR_RESET}")
    # __set magic interceptor
    controller.request_token = "sess_09af83bc7e"
    print(f"   Dynamic property set  : controller.request_token = '{controller.request_token}'")

    # __get fallback
    print(f"   Undefined property get: controller.non_existent -> {CLR_MAGENTA}{controller.non_existent}{CLR_RESET}")

    # __call dynamic dispatch
    query_result = controller.repo.findByEmail("lead_dev@enterprise.internal")
    print(f"   Dynamic __call router : {CLR_GREEN}{query_result}{CLR_RESET}\n")

    # 4. PHP 8 Attributes & Reflection Inspection
    print(f"{CLR_BOLD}{CLR_YELLOW}[4] Reflection API & PHP 8 Attributes Inspection...{CLR_RESET}")
    for method_name, method in inspect.getmembers(UserController, predicate=inspect.isfunction):
        attrs = PHPReflection.inspect_attributes(method)
        for attr in attrs:
            if isinstance(attr, Route):
                print(f"   Found Route Endpoint  : {CLR_BOLD}[{attr.method}]{CLR_RESET} {attr.path}")
                print(f"   Target Handler Action : {UserController.__name__}::{method_name}()")

    print(f"\n{CLR_BOLD}{CLR_GREEN}=== OOP & Meta-programming Execution Verified Without Errors ==={CLR_RESET}")


if __name__ == "__main__":
    run_lab()
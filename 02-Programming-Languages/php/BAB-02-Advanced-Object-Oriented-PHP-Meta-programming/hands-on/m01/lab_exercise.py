#!/usr/bin/env python3
"""
Lab Exercise: Advanced Object-Oriented PHP & Meta-programming Simulator
Simulates PHP 8.x OOP engine mechanics:
  1. PHP Magic Methods (__get, __set, __call, __callStatic, __invoke, __toString)
  2. Late Static Binding (LSB: self:: vs static::)
  3. Trait Composition & Collision Resolution (insteadof, as alias)
  4. PHP Reflection API & Attributes Engine
  5. Dynamic Proxy & Method Interception (AOP Middleware)
"""

import sys
import inspect
from typing import Any, Callable, Dict, List, Optional


class AnsiColor:
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
    print(f"\n{AnsiColor.BOLD}{AnsiColor.CYAN}{'=' * 65}{AnsiColor.RESET}")
    print(f"{AnsiColor.BOLD}{AnsiColor.YELLOW}  {title}{AnsiColor.RESET}")
    print(f"{AnsiColor.BOLD}{AnsiColor.CYAN}{'=' * 65}{AnsiColor.RESET}")


def info(msg: str) -> None:
    print(f" {AnsiColor.GREEN}✓{AnsiColor.RESET} {msg}")


def log_php(code: str, output: str) -> None:
    print(f"  {AnsiColor.MAGENTA}[PHP Synth]{AnsiColor.RESET} {AnsiColor.BOLD}{code}{AnsiColor.RESET}")
    print(f"  {AnsiColor.DIM}↳ Output:{AnsiColor.RESET} {output}")


# ==============================================================================
# 1. PHP Magic Methods Simulation (__get, __set, __call, __invoke, __toString)
# ==============================================================================
class PhpMagicModel:
    """Simulates PHP dynamic property and method overloading."""

    def __init__(self, table_name: str):
        self._table = table_name
        self._attributes: Dict[str, Any] = {}

    def __getattr__(self, name: str) -> Any:
        # Check dynamic properties (__get)
        if name in self._attributes:
            return self._attributes[name]
        # Emulates PHP __call($method, $arguments) for dynamic methods
        if name.startswith("find_by_") or name.startswith("get_"):
            def dynamic_method(*args: Any, **kwargs: Any) -> Any:
                return self.php_call(name, *args, **kwargs)
            return dynamic_method
        raise AttributeError(f"PHP Notice: Undefined property: ${name} via __get()")

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("_table", "_attributes"):
            super().__setattr__(name, value)
        else:
            # Emulates PHP __set($name, $value)
            self._attributes[name] = value

    def php_call(self, method_name: str, *args: Any) -> Any:
        # Emulates PHP __call($method, $arguments)
        if method_name.startswith("find_by_"):
            field = method_name.replace("find_by_", "")
            return f"SELECT * FROM `{self._table}` WHERE `{field}` = '{args[0]}'"
        raise AttributeError(f"PHP Fatal error: Call to undefined method {method_name}() via __call()")

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        # Emulates PHP __invoke($args)
        return f"Object({self._table}) invoked as Closure with args={args} via __invoke()"

    def __str__(self) -> str:
        # Emulates PHP __toString()
        props = ", ".join(f"{k}='{v}'" for k, v in self._attributes.items())
        return f"Object({self._table}) {{ {props} }}"


# ==============================================================================
# 2. Late Static Binding (LSB: self:: vs static::) Simulation
# ==============================================================================
class PhpBaseModel:
    model_name = "BaseModel"

    @classmethod
    def get_self_class(cls) -> str:
        # Emulates self::class (resolved at compile/definition scope)
        return PhpBaseModel.model_name

    @classmethod
    def get_static_class(cls) -> str:
        # Emulates static::class (resolved at runtime late static scope)
        return cls.model_name


class User(PhpBaseModel):
    model_name = "App\\Models\\User"


class AdminUser(User):
    model_name = "App\\Models\\AdminUser"


# ==============================================================================
# 3. Trait Composition & Conflict Resolution
# ==============================================================================
class LoggableTrait:
    def log(self, message: str) -> str:
        return f"[LoggableTrait::log] {message}"

    def status(self) -> str:
        return "LoggableTrait: STATUS_ACTIVE"


class AuditTrait:
    def audit(self, event: str) -> str:
        return f"[AuditTrait::audit] Recorded: {event}"

    def status(self) -> str:
        return "AuditTrait: AUDIT_STRICT"


class OrderService:
    """
    Simulates PHP trait composition with conflict resolution:
      use LoggableTrait, AuditTrait {
          AuditTrait::status insteadof LoggableTrait;
          LoggableTrait::status as logStatus;
      }
    """
    def __init__(self):
        self._loggable = LoggableTrait()
        self._audit = AuditTrait()

    def log(self, msg: str) -> str:
        return self._loggable.log(msg)

    def audit(self, event: str) -> str:
        return self._audit.audit(event)

    def status(self) -> str:
        # resolved conflict: AuditTrait::status insteadof LoggableTrait
        return self._audit.status()

    def log_status(self) -> str:
        # aliased method: LoggableTrait::status as logStatus
        return self._loggable.status()


# ==============================================================================
# 4. Reflection API & PHP 8 Attributes Simulator
# ==============================================================================
class RouteAttribute:
    def __init__(self, path: str, method: str = "GET"):
        self.path = path
        self.method = method


class ReflectionDemoController:
    """PHP Controller with attribute metadata."""

    @classmethod
    def index(cls) -> str:
        return "Controller Index Response"

    index.php_attributes = [RouteAttribute("/api/v1/users", "GET")]

    @classmethod
    def create(cls) -> str:
        return "Controller Created Response"

    create.php_attributes = [RouteAttribute("/api/v1/users", "POST")]


def simulate_php_reflection(target_cls: type) -> None:
    print(f"  {AnsiColor.BLUE}ReflectionClass: {target_cls.__name__}{AnsiColor.RESET}")
    for name, member in inspect.getmembers(target_cls):
        if hasattr(member, "php_attributes"):
            attrs: List[RouteAttribute] = getattr(member, "php_attributes")
            for attr in attrs:
                print(
                    f"    Method: {AnsiColor.BOLD}{name}(){AnsiColor.RESET} -> "
                    f"Attribute #[Route('{attr.path}', method: '{attr.method}')]"
                )


# ==============================================================================
# 5. Dynamic Proxy & Interceptor (AOP / Middleware in PHP)
# ==============================================================================
class PhpDynamicProxy:
    def __init__(self, target: Any, before: Callable, after: Callable):
        self._target = target
        self._before = before
        self._after = after

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._target, name)
        if callable(attr):
            def intercepted(*args: Any, **kwargs: Any) -> Any:
                self._before(name, args)
                result = attr(*args, **kwargs)
                self._after(name, result)
                return result
            return intercepted
        return attr


# ==============================================================================
# Interactive Runner & Verification Suite
# ==============================================================================
def demo_magic_methods() -> None:
    header("DEMO 1: PHP Magic Methods Overloading")
    model = PhpMagicModel("users")

    # __set
    model.username = "sora_developer"
    model.role = "SuperAdmin"
    log_php("$model->username = 'sora_developer'", f"Stored in dynamic array: {model.username}")
    log_php("$model->role = 'SuperAdmin'", f"Stored in dynamic array: {model.role}")

    # __call
    query = model.find_by_email("dev@hyperframes.ai")
    log_php("$model->findByEmail('dev@hyperframes.ai')", query)

    # __invoke
    invoked = model("payload_data", 42)
    log_php("$model('payload_data', 42)", invoked)

    # __toString
    log_php("(string)$model", str(model))
    info("Magic methods simulation completed successfully.")


def demo_late_static_binding() -> None:
    header("DEMO 2: Late Static Binding (self:: vs static::)")
    print(f"  Base Class: {PhpBaseModel.model_name}")
    print(f"  Child User: {User.model_name}")
    print(f"  Child AdminUser: {AdminUser.model_name}\n")

    log_php("AdminUser::getSelfClass()   [self::class]", AdminUser.get_self_class())
    log_php("AdminUser::getStaticClass() [static::class]", AdminUser.get_static_class())
    info("Late Static Binding demonstrates compile-time vs late runtime scope resolution.")


def demo_traits() -> None:
    header("DEMO 3: Trait Composition & Conflict Resolution (insteadof, as)")
    service = OrderService()
    log_php("$service->log('Processing ID #902')", service.log("Processing ID #902"))
    log_php("$service->audit('PaymentAuthorized')", service.audit("PaymentAuthorized"))
    log_php("$service->status() [insteadof applied]", service.status())
    log_php("$service->logStatus() [aliased method]", service.log_status())
    info("Trait method collision resolved identically to PHP engine rules.")


def demo_reflection_attributes() -> None:
    header("DEMO 4: PHP 8 Attributes & Reflection Engine")
    simulate_php_reflection(ReflectionDemoController)
    info("Extracted route metadata using programmatic class reflection.")


def demo_dynamic_proxy() -> None:
    header("DEMO 5: Dynamic Proxy & Method Interception (AOP)")
    service = OrderService()

    def before_hook(method: str, args: tuple) -> None:
        print(f"    {AnsiColor.YELLOW}[AOP Before]{AnsiColor.RESET} Intercepted call to '{method}()'")

    def after_hook(method: str, result: Any) -> None:
        print(f"    {AnsiColor.GREEN}[AOP After]{AnsiColor.RESET} Result returned: {result}")

    proxy = PhpDynamicProxy(service, before_hook, after_hook)
    proxy.audit("SecurityTokenRefresh")
    info("Dynamic proxy intercepted invocations cleanly.")


def run_all() -> None:
    demo_magic_methods()
    demo_late_static_binding()
    demo_traits()
    demo_reflection_attributes()
    demo_dynamic_proxy()
    header("LAB VALIDATION SUMMARY")
    print(f" {AnsiColor.GREEN}{AnsiColor.BOLD}All 5 Core OOP & Metaprogramming modules executed without errors.{AnsiColor.RESET}\n")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        run_all()
        return

    while True:
        header("PHP OOP & Metaprogramming Interactive Lab")
        print("  1. Run Magic Methods Simulation (__get, __set, __call, __toString)")
        print("  2. Run Late Static Binding (self:: vs static::)")
        print("  3. Run Trait Conflict Resolution (insteadof / as)")
        print("  4. Run Reflection API & Attributes Engine")
        print("  5. Run Dynamic Proxy / AOP Interception")
        print("  6. Run ALL Modules Sequentially")
        print("  0. Exit")
        print()

        try:
            choice = input(f"{AnsiColor.BOLD}Select menu [0-6]: {AnsiColor.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if choice == "1":
            demo_magic_methods()
        elif choice == "2":
            demo_late_static_binding()
        elif choice == "3":
            demo_traits()
        elif choice == "4":
            demo_reflection_attributes()
        elif choice == "5":
            demo_dynamic_proxy()
        elif choice == "6" or choice == "":
            run_all()
            break
        elif choice == "0":
            print("Exiting lab.")
            break
        else:
            print(f"{AnsiColor.RED}Invalid option selected.{AnsiColor.RESET}")


if __name__ == "__main__":
    main()

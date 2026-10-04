#!/usr/bin/env python3
"""
Lab Hands-on: Advanced Object Systems, Prototypes & Metaprogramming (JS Deep Dive)
Category: 02-Programming-Languages | Bab: 04 - Modul 02

Simulasi mesin objek ECMAScript:
1. Prototype Chain Lookup (Delegation Mechanism & 'this' late-binding)
2. Property Descriptors (writable, enumerable, configurable, getter/setter accessors)
3. ECMAScript Proxy & Reflect API Trap Engine
"""

import sys
import time
from typing import Any, Callable, Dict, Optional, List


# ANSI Color Codes untuk visualisasi terminal
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


class PropertyDescriptor:
    """Merepresentasikan struktur Property Descriptor internal V8/ECMAScript."""
    def __init__(
        self,
        value: Any = None,
        writable: bool = True,
        enumerable: bool = True,
        configurable: bool = True,
        getter: Optional[Callable[["JSObject"], Any]] = None,
        setter: Optional[Callable[["JSObject", Any], None]] = None,
    ):
        self.value = value
        self.writable = writable
        self.enumerable = enumerable
        self.configurable = configurable
        self.getter = getter
        self.setter = setter

    @property
    def is_accessor(self) -> bool:
        return self.getter is not None or self.setter is not None


class JSObject:
    """
    Simulasi objek ECMAScript dengan dukungan internal slot [[Prototype]],
    Property Storage, dynamic dispatch, dan method binding.
    """
    def __init__(self, prototype: Optional["JSObject"] = None, name: str = "Object"):
        self.name = name
        self.internal_prototype: Optional["JSObject"] = prototype
        self.properties: Dict[str, PropertyDescriptor] = {}

    def define_property(self, prop: str, descriptor: PropertyDescriptor) -> "JSObject":
        """Implementasi Object.defineProperty() dengan validasi invariant ECMAScript."""
        if prop in self.properties and not self.properties[prop].configurable:
            raise TypeError(f"Cannot redefine non-configurable property: '{prop}'")
        self.properties[prop] = descriptor
        return self

    def get(self, prop: str, receiver: Optional["JSObject"] = None) -> Any:
        """
        Algoritma [[Get]](P, Receiver) spesifikasi ECMAScript:
        Traverse prototype chain jika property tidak ditemukan di object lokal.
        """
        actual_receiver = receiver or self

        # 1. Cari pada instance lokal
        if prop in self.properties:
            desc = self.properties[prop]
            if desc.is_accessor:
                if desc.getter:
                    return desc.getter(actual_receiver)
                return None
            return desc.value

        # 2. Delegasi prototype chain traversal
        if self.internal_prototype is not None:
            return self.internal_prototype.get(prop, receiver=actual_receiver)

        return None

    def set(self, prop: str, value: Any, receiver: Optional["JSObject"] = None) -> bool:
        """
        Algoritma [[Set]](P, V, Receiver):
        Mengatur properti lokal (shadowing) atau memanggil setter di prototype chain.
        """
        actual_receiver = receiver or self

        # Cek apakah ada setter di prototype chain
        curr: Optional["JSObject"] = self
        while curr is not None:
            if prop in curr.properties:
                desc = curr.properties[prop]
                if desc.is_accessor:
                    if desc.setter:
                        desc.setter(actual_receiver, value)
                        return True
                    return False  # Getter-only property
                if not desc.writable and curr is actual_receiver:
                    raise TypeError(f"Cannot assign to read only property '{prop}'")
                break
            curr = curr.internal_prototype

        # Property Shadowing: Pasang langsung pada actual_receiver
        if prop in actual_receiver.properties:
            actual_receiver.properties[prop].value = value
        else:
            actual_receiver.define_property(
                prop, PropertyDescriptor(value=value, writable=True, enumerable=True, configurable=True)
            )
        return True

    def has(self, prop: str) -> bool:
        """Operator 'in' (algoritma [[HasProperty]])."""
        if prop in self.properties:
            return True
        if self.internal_prototype:
            return self.internal_prototype.has(prop)
        return False

    def own_keys(self) -> List[str]:
        """Object.getOwnPropertyNames() & Object.keys() filter."""
        return [k for k, v in self.properties.items() if v.enumerable]


class Reflect:
    """Simulasi static module ECMAScript 'Reflect'."""
    @staticmethod
    def get(target: JSObject, prop: str, receiver: Optional[JSObject] = None) -> Any:
        return target.get(prop, receiver or target)

    @staticmethod
    def set(target: JSObject, prop: str, value: Any, receiver: Optional[JSObject] = None) -> bool:
        return target.set(prop, value, receiver or target)

    @staticmethod
    def has(target: JSObject, prop: str) -> bool:
        return target.has(prop)


class JSProxy(JSObject):
    """
    Simulasi metaprogramming ECMAScript 'Proxy' object.
    Mencegat operasi fundamental (traps) sebelum mencapai target.
    """
    def __init__(self, target: JSObject, handler: Dict[str, Callable]):
        super().__init__(name=f"Proxy({target.name})")
        self.target = target
        self.handler = handler

    def get(self, prop: str, receiver: Optional[JSObject] = None) -> Any:
        if "get" in self.handler:
            return self.handler["get"](self.target, prop, receiver or self)
        return Reflect.get(self.target, prop, receiver or self)

    def set(self, prop: str, value: Any, receiver: Optional[JSObject] = None) -> bool:
        if "set" in self.handler:
            return self.handler["set"](self.target, prop, value, receiver or self)
        return Reflect.set(self.target, prop, value, receiver or self)

    def has(self, prop: str) -> bool:
        if "has" in self.handler:
            return self.handler["has"](self.target, prop)
        return Reflect.has(self.target, prop)


# ==============================================================================
# DEMONSTRASI & TEST LAB HARNESS
# ==============================================================================

def print_separator(title: str):
    print(f"\n{Colors.HEADER}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}[LAB MODULE 04] :: {title}{Colors.RESET}")
    print(f"{Colors.HEADER}{'='*60}{Colors.RESET}")


def demo_prototype_delegation():
    print_separator("1. Prototype Delegation Chain & Method Binding ('this')")

    # Object.prototype
    object_prototype = JSObject(name="Object.prototype")
    object_prototype.define_property(
        "toString",
        PropertyDescriptor(
            value=lambda this: f"[object {this.name}]",
            writable=True,
            enumerable=False,
            configurable=True,
        ),
    )

    # Human.prototype (mewarisi Object.prototype)
    human_prototype = JSObject(prototype=object_prototype, name="Human.prototype")
    human_prototype.define_property(
        "species",
        PropertyDescriptor(value="Homo sapiens", writable=False, enumerable=True, configurable=False),
    )
    human_prototype.define_property(
        "introduce",
        PropertyDescriptor(
            value=lambda this: f"Hi, I am {this.get('name')} of species {this.get('species')}",
            writable=True,
            enumerable=True,
            configurable=True,
        ),
    )

    # Instance: alice
    alice = JSObject(prototype=human_prototype, name="AliceInstance")
    alice.define_property("name", PropertyDescriptor(value="Alice", writable=True))

    print(f"{Colors.YELLOW}Resolving 'name' on alice:{Colors.RESET} {alice.get('name')}")
    print(f"{Colors.YELLOW}Resolving 'species' through chain:{Colors.RESET} {alice.get('species')}")

    # Invoke method 'introduce' dengan binding 'this' = alice
    intro_fn = alice.get("introduce")
    print(f"{Colors.GREEN}Executing alice.introduce():{Colors.RESET} \"{intro_fn(alice)}\"")

    # Property Shadowing
    print(f"\n{Colors.DIM}-- Shadowing 'species' pada instance alice --{Colors.RESET}")
    alice.set("species", "Cybernetic Organism")
    print(f"{Colors.YELLOW}alice.species (shadowed):{Colors.RESET} {alice.get('species')}")
    print(f"{Colors.YELLOW}human_prototype.species (intact):{Colors.RESET} {human_prototype.get('species')}")


def demo_property_descriptors():
    print_separator("2. Advanced Property Descriptors & Accessors")

    account = JSObject(name="BankAccount")
    
    # Internal backing field via closure
    balance_storage = {"val": 1000}

    # Getter & Setter dengan validasi ketat
    def balance_getter(this):
        print(f"  {Colors.DIM}[Audit] Accessing balance getter{Colors.RESET}")
        return balance_storage["val"]

    def balance_setter(this, new_val):
        print(f"  {Colors.DIM}[Audit] Attempting balance update to {new_val}{Colors.RESET}")
        if not isinstance(new_val, (int, float)) or new_val < 0:
            raise ValueError(f"Invalid transaction: amount {new_val} is illegal.")
        balance_storage["val"] = new_val

    account.define_property(
        "balance",
        PropertyDescriptor(
            getter=balance_getter,
            setter=balance_setter,
            enumerable=True,
            configurable=False,
        ),
    )

    # Read-only freeze-like property
    account.define_property(
        "accountNumber",
        PropertyDescriptor(value="ACC-998811", writable=False, enumerable=True, configurable=False),
    )

    print(f"Initial balance: {Colors.CYAN}{account.get('balance')}{Colors.RESET}")
    account.set("balance", 2500)
    print(f"Updated balance: {Colors.GREEN}{account.get('balance')}{Colors.RESET}")

    try:
        print("\nAttempting illegal withdrawal/assignment...")
        account.set("balance", -500)
    except ValueError as e:
        print(f"{Colors.RED}Intercepted Error:{Colors.RESET} {e}")

    try:
        print("\nAttempting write to read-only property 'accountNumber'...")
        account.set("accountNumber", "MODIFIED-VAL")
    except TypeError as e:
        print(f"{Colors.RED}Intercepted Error:{Colors.RESET} {e}")


def demo_metaprogramming_proxy():
    print_separator("3. Metaprogramming with Proxy Traps (Telemetri & Schema Validation)")

    target_user = JSObject(name="TargetUser")
    target_user.set("username", "neo_matrix")
    target_user.set("age", 28)

    # Log & Validate Traps
    def proxy_get_trap(target: JSObject, prop: str, receiver: JSObject) -> Any:
        print(f"{Colors.BLUE}[Proxy TRAP 'get']{Colors.RESET} Property read: '{prop}'")
        val = Reflect.get(target, prop, receiver)
        if val is None:
            print(f"  {Colors.YELLOW}-> Property '{prop}' does not exist! Returning dynamic mock.{Colors.RESET}")
            return f"VIRTUAL_{prop.upper()}"
        return val

    def proxy_set_trap(target: JSObject, prop: str, val: Any, receiver: JSObject) -> bool:
        print(f"{Colors.BLUE}[Proxy TRAP 'set']{Colors.RESET} Property write: '{prop}' = {val}")
        if prop == "age":
            if not isinstance(val, int) or val < 0 or val > 150:
                raise ValueError(f"Schema Violation: Age must be an integer between 0 and 150. Got '{val}'")
        return Reflect.set(target, prop, val, receiver)

    def proxy_has_trap(target: JSObject, prop: str) -> bool:
        print(f"{Colors.BLUE}[Proxy TRAP 'has']{Colors.RESET} Trap 'in' operator check for '{prop}'")
        if prop.startswith("_"):
            return False  # Hide private fields from 'in' checks
        return Reflect.has(target, prop)

    proxy_user = JSProxy(
        target=target_user,
        handler={
            "get": proxy_get_trap,
            "set": proxy_set_trap,
            "has": proxy_has_trap,
        },
    )

    # 1. Read properti yang ada
    print(f"proxy.username: {Colors.GREEN}{proxy_user.get('username')}{Colors.RESET}\n")

    # 2. Virtual property fallback
    print(f"proxy.unassigned_field: {Colors.GREEN}{proxy_user.get('unassigned_field')}{Colors.RESET}\n")

    # 3. Validasi skema dinamis
    proxy_user.set("age", 35)
    try:
        proxy_user.set("age", -10)
    except ValueError as e:
        print(f"{Colors.RED}Validation Failed:{Colors.RESET} {e}\n")

    # 4. Invariant masking ('has' trap)
    target_user.set("_internal_secret", "0xDEADC0DE")
    print(f"Check '_internal_secret' in proxy: {Colors.YELLOW}{proxy_user.has('_internal_secret')}{Colors.RESET}")
    print(f"Check 'username' in proxy: {Colors.YELLOW}{proxy_user.has('username')}{Colors.RESET}")


def main():
    start_time = time.perf_counter()
    print(f"{Colors.BOLD}{Colors.GREEN}Starting ECMAScript Advanced Object System Runtime Engine...{Colors.RESET}")

    demo_prototype_delegation()
    demo_property_descriptors()
    demo_metaprogramming_proxy()

    elapsed = (time.perf_counter() - start_time) * 1000
    print(f"\n{Colors.BOLD}{Colors.CYAN}Execution completed successfully in {elapsed:.2f} ms.{Colors.RESET}")


if __name__ == "__main__":
    main()

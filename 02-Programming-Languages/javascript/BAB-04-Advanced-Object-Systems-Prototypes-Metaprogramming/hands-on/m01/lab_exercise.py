#!/usr/bin/env python3
"""
Lab Exercise: JavaScript Advanced Object Systems, Prototypes & Metaprogramming Engine Simulation
Simulates ECMAScript specification mechanics:
- Property Descriptors (attributes: writable, enumerable, configurable, get/set)
- Prototype Chain Resolution ([[Prototype]] / __proto__ traversal & shadowing)
- ES6 Proxy Traps & Reflect Metaprogramming
"""

import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

# ANSI terminal color definitions
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"


class PropertyDescriptor:
    """Simulates ECMAScript Property Descriptor."""

    def __init__(
        self,
        value: Any = None,
        writable: bool = True,
        enumerable: bool = True,
        configurable: bool = True,
        getter: Optional[Callable[[], Any]] = None,
        setter: Optional[Callable[[Any], None]] = None,
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

    def __repr__(self) -> str:
        if self.is_accessor:
            return f"AccessorDescriptor(get={'fn' if self.getter else None}, set={'fn' if self.setter else None}, enum={self.enumerable}, conf={self.configurable})"
        return f"DataDescriptor(val={self.value!r}, write={self.writable}, enum={self.enumerable}, conf={self.configurable})"


class JSObject:
    """Simulates ECMAScript Ordinary Object with [[Prototype]] chain and Property Map."""

    def __init__(self, prototype: Optional["JSObject"] = None, name: str = "Object"):
        self.name = name
        self.prototype: Optional["JSObject"] = prototype
        self.properties: Dict[str, PropertyDescriptor] = {}

    def define_property(
        self,
        key: str,
        value: Any = None,
        writable: bool = True,
        enumerable: bool = True,
        configurable: bool = True,
        getter: Optional[Callable[[], Any]] = None,
        setter: Optional[Callable[[Any], None]] = None,
    ) -> "JSObject":
        """Simulates Object.defineProperty(obj, prop, descriptor)."""
        existing = self.properties.get(key)
        if existing and not existing.configurable:
            raise TypeError(f"TypeError: Cannot redefine non-configurable property '{key}' on {self.name}")

        self.properties[key] = PropertyDescriptor(
            value=value,
            writable=writable,
            enumerable=enumerable,
            configurable=configurable,
            getter=getter,
            setter=setter,
        )
        return self

    def get(self, key: str) -> Tuple[Any, List[str]]:
        """
        Simulates ECMAScript [[Get]](P, Receiver) with Prototype Chain walking.
        Returns (resolved_value, traversal_chain_path).
        """
        chain: List[str] = []
        curr: Optional["JSObject"] = self

        while curr is not None:
            chain.append(curr.name)
            if key in curr.properties:
                desc = curr.properties[key]
                if desc.is_accessor:
                    val = desc.getter() if desc.getter else None
                    return val, chain
                return desc.value, chain
            curr = curr.prototype

        return None, chain

    def set(self, key: str, value: Any) -> bool:
        """
        Simulates ECMAScript [[Set]](P, V, Receiver).
        Implements property shadowing and handles writable checks.
        """
        if key in self.properties:
            desc = self.properties[key]
            if desc.is_accessor:
                if not desc.setter:
                    raise TypeError(f"TypeError: Cannot set property '{key}' which has only a getter")
                desc.setter(value)
                return True
            if not desc.writable:
                raise TypeError(f"TypeError: Cannot assign to read-only property '{key}'")
            desc.value = value
            return True

        # Check prototype for inherited accessor or non-writable constraint
        curr = self.prototype
        while curr is not None:
            if key in curr.properties:
                proto_desc = curr.properties[key]
                if proto_desc.is_accessor:
                    if not proto_desc.setter:
                        raise TypeError(f"TypeError: Inherited property '{key}' is read-only accessor")
                    proto_desc.setter(value)
                    return True
                if not proto_desc.writable:
                    raise TypeError(f"TypeError: Cannot shadow non-writable inherited property '{key}'")
                break
            curr = curr.prototype

        # Shadow property on the instance itself
        self.properties[key] = PropertyDescriptor(value=value, writable=True, enumerable=True, configurable=True)
        return True

    def keys(self) -> List[str]:
        """Simulates Object.keys(obj) - only own and enumerable properties."""
        return [k for k, desc in self.properties.items() if desc.enumerable]


class JSProxy:
    """Simulates ES6 Proxy & Handler Traps."""

    def __init__(self, target: JSObject, handler: Dict[str, Callable]):
        self._target = target
        self._handler = handler

    def get(self, key: str) -> Any:
        if "get" in self._handler:
            return self._handler["get"](self._target, key, self)
        val, _ = self._target.get(key)
        return val

    def set(self, key: str, value: Any) -> bool:
        if "set" in self._handler:
            return self._handler["set"](self._target, key, value, self)
        return self._target.set(key, value)

    def has(self, key: str) -> bool:
        if "has" in self._handler:
            return self._handler["has"](self._target, key)
        val, _ = self._target.get(key)
        return val is not None


def run_lab_interactive() -> None:
    print(f"\n{BOLD}{CYAN}======================================================================{RESET}")
    print(f"{BOLD}{CYAN}  JavaScript Advanced Object Systems & Metaprogramming Lab (BAB-04)   {RESET}")
    print(f"{BOLD}{CYAN}======================================================================{RESET}\n")

    # -------------------------------------------------------------
    # Lab 1: Property Descriptors & Immutability Rules
    # -------------------------------------------------------------
    print(f"{BOLD}{YELLOW}[1] Property Descriptors & Immutability Simulation{RESET}")
    obj_root = JSObject(name="RootObject")

    obj_root.define_property("visible", value="Visible Value", enumerable=True, writable=True)
    obj_root.define_property("hiddenSecret", value=42, enumerable=False, writable=True)
    obj_root.define_property("frozenConst", value="IMMUTABLE", writable=False, configurable=False)

    print(f"  Object.keys(obj_root) -> {GREEN}{obj_root.keys()}{RESET} (hiddenSecret excluded because enumerable=False)")

    try:
        print("  Attempting: obj_root.frozenConst = 'MODIFIED'...")
        obj_root.set("frozenConst", "MODIFIED")
    except TypeError as e:
        print(f"  {RED}{e}{RESET}")

    # -------------------------------------------------------------
    # Lab 2: [[Prototype]] Chain Lookup & Shadowing Mechanics
    # -------------------------------------------------------------
    print(f"\n{BOLD}{YELLOW}[2] [[Prototype]] Chain Lookup & Property Shadowing{RESET}")

    proto_parent = JSObject(name="BasePrototype")
    proto_parent.define_property("coreEngine", value="V8-Simulator", writable=True)
    proto_parent.define_property("readOnlyProto", value="STRICT_BASE", writable=False)

    child_instance = JSObject(prototype=proto_parent, name="ChildInstance")
    child_instance.define_property("instanceId", value="inst_001", writable=True)

    val, chain = child_instance.get("coreEngine")
    print(f"  child.coreEngine -> '{GREEN}{val}{RESET}'")
    print(f"  Lookup Path -> {MAGENTA}{' -> '.join(chain)}{RESET}")

    print("  Shadowing 'coreEngine' on child instance...")
    child_instance.set("coreEngine", "SpiderMonkey-Simulator")
    val_child, chain_child = child_instance.get("coreEngine")
    val_parent, _ = proto_parent.get("coreEngine")

    print(f"  child.coreEngine after shadow  : '{GREEN}{val_child}{RESET}' (Found in: {chain_child[0]})")
    print(f"  parent.coreEngine intact state : '{BLUE}{val_parent}{RESET}'")

    try:
        print("  Attempting to shadow non-writable inherited property 'readOnlyProto'...")
        child_instance.set("readOnlyProto", "ILLEGAL_OVERRIDE")
    except TypeError as e:
        print(f"  {RED}{e}{RESET}")

    # -------------------------------------------------------------
    # Lab 3: Metaprogramming with Proxy & Traps
    # -------------------------------------------------------------
    print(f"\n{BOLD}{YELLOW}[3] ES6 Proxy Traps & Metaprogramming (Validation & Virtual Keys){RESET}")

    user_storage = JSObject(name="UserRecord")
    user_storage.define_property("age", 25)

    def proxy_get_trap(target: JSObject, key: str, receiver: Any) -> Any:
        print(f"    {MAGENTA}[Proxy Trap: [[Get]]] accessing property '{key}'{RESET}")
        if key == "virtualStatus":
            age, _ = target.get("age")
            return "Senior" if age and age >= 60 else "Adult"
        val, _ = target.get(key)
        return val

    def proxy_set_trap(target: JSObject, key: str, value: Any, receiver: Any) -> bool:
        print(f"    {MAGENTA}[Proxy Trap: [[Set]]] validating key '{key}' with value {value!r}{RESET}")
        if key == "age":
            if not isinstance(value, int) or value < 0:
                raise TypeError(f"ProxyValidationError: 'age' must be a positive integer, got {value!r}")
        return target.set(key, value)

    proxy_user = JSProxy(
        user_storage,
        handler={
            "get": proxy_get_trap,
            "set": proxy_set_trap,
        },
    )

    print(f"  Reading proxy.age: {GREEN}{proxy_user.get('age')}{RESET}")
    print(f"  Reading proxy.virtualStatus: {GREEN}{proxy_user.get('virtualStatus')}{RESET}")

    print("  Mutating proxy.age to 65...")
    proxy_user.set("age", 65)
    print(f"  Reading updated virtualStatus: {GREEN}{proxy_user.get('virtualStatus')}{RESET}")

    try:
        print("  Attempting invalid mutation: proxy.age = -10...")
        proxy_user.set("age", -10)
    except TypeError as e:
        print(f"  {RED}{e}{RESET}")

    print(f"\n{BOLD}{GREEN}✔ All JavaScript prototype & metaprogramming simulations completed successfully!{RESET}\n")


if __name__ == "__main__":
    run_lab_interactive()

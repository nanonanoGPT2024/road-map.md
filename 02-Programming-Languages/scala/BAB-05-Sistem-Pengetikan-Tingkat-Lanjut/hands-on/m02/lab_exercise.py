#!/usr/bin/env python3
"""
Lab Hands-on: Scala Advanced Type System Deep Dive Engine
Category: 02-Programming-Languages | Chapter 05: Sistem Pengetikan Tingkat Lanjut

Materi Inti yang Disimulasikan:
1. Variance Subtyping: Invariance [T], Covariance [+T], Contravariance [-T]
2. Path-Dependent Types: Tipe terikat pada instance spesifik (Outer#Inner)
3. Type Classes & Implicit Resolution: Ad-hoc polymorphism ala Scala 2/3
4. Higher-Kinded Types (HKT): Simulasi Functor F[_] abstraction
"""

import sys
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Generic, List, Optional, Tuple, Type, TypeVar
import uuid

# ==============================================================================
# Terminal Color Formatting (ANSI)
# ==============================================================================
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_MAGENTA = "\033[95m"
CLR_GRAY = "\033[90m"


def print_banner(title: str) -> None:
    print(f"\n{CLR_BOLD}{CLR_CYAN}{'='*80}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN} [SCALA ATS ENGINE] :: {title.upper()}{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}{'='*80}{CLR_RESET}")


def log_substep(status: bool, label: str, details: str = "") -> None:
    marker = f"{CLR_GREEN}✓ [PASS]{CLR_RESET}" if status else f"{CLR_RED}✗ [FAIL]{CLR_RESET}"
    det = f" -> {CLR_GRAY}{details}{CLR_RESET}" if details else ""
    print(f"  {marker} {CLR_BOLD}{label}{CLR_RESET}{det}")


# ==============================================================================
# 1. Variance Engine: Covariance (+T), Contravariance (-T), Invariance (T)
# ==============================================================================
# Simulasi hierarki tipe: Organism > Animal > Canine > Dog
class Organism: pass
class Animal(Organism): pass
class Canine(Animal): pass
class Dog(Canine): pass


class VarianceRule:
    INVARIANT = "INVARIANT [T]"
    COVARIANT = "COVARIANT [+T]"
    CONTRAVARIANT = "CONTRAVARIANT [-T]"


class TypeRelationshipEngine:
    """
    Memvalidasi aturan subtipe Liskov Substitution Principle (LSP)
    berdasarkan deklarasi variance anotasi Scala.
    """
    @staticmethod
    def is_subtype(sub: Type, super_: Type) -> bool:
        return issubclass(sub, super_)

    @classmethod
    def check_variance(cls, variance_mode: str, t_sub: Type, t_super: Type) -> bool:
        """
        Aturan Pengetikan Scala:
        - Covariant (+T):       Jika S <: T maka Container[S] <: Container[T]
        - Contravariant (-T):   Jika S <: T maka Container[T] <: Container[S]
        - Invariant (T):        Container[S] <: Container[T] HANYA JIKA S == T
        """
        is_direct_subtype = cls.is_subtype(t_sub, t_super)

        if variance_mode == VarianceRule.COVARIANT:
            # Mempertahankan arah relasi
            return is_direct_subtype
        elif variance_mode == VarianceRule.CONTRAVARIANT:
            # Membalik arah relasi
            return cls.is_subtype(t_super, t_sub)
        elif variance_mode == VarianceRule.INVARIANT:
            # Tepat sama
            return t_sub is t_super
        return False


# ==============================================================================
# 2. Path-Dependent Types Engine (Outer#Inner Simulation)
# ==============================================================================
class GraphNetwork:
    """
    Dalam Scala:
    class GraphNetwork {
      class Node(val id: String)
      def connect(a: Node, b: Node): Unit
    }
    Node dari instance 'g1' tidak kompatibel dengan tipe Node dari 'g2' (g1.Node != g2.Node).
    """
    def __init__(self, name: str):
        self.network_id = uuid.uuid4().hex[:8]
        self.name = name

    class Node:
        def __init__(self, owner_network_id: str, label: str):
            self.owner_network_id = owner_network_id
            self.label = label

        def __repr__(self) -> str:
            return f"Node({self.label}@{self.owner_network_id})"

    def create_node(self, label: str) -> "GraphNetwork.Node":
        return GraphNetwork.Node(self.network_id, label)

    def connect(self, n1: "GraphNetwork.Node", n2: "GraphNetwork.Node") -> Tuple[bool, str]:
        # Enforce Path-Dependent Typing: Both nodes must belong to this specific network instance
        if n1.owner_network_id != self.network_id or n2.owner_network_id != self.network_id:
            return False, (
                f"Type Mismatch! Expected Path: {self.name}#{self.network_id}.Node. "
                f"Got n1: {n1.owner_network_id}, n2: {n2.owner_network_id}"
            )
        return True, f"Connection established between {n1} and {n2} inside {self.name}."


# ==============================================================================
# 3. Type Classes & Implicit Resolution Simulation
# ==============================================================================
# Simulasi: trait Show[T] { def show(v: T): String }
T = TypeVar("T")


class Show(ABC, Generic[T]):
    @abstractmethod
    def show(self, value: T) -> str:
        pass


class ImplicitScope:
    """
    Simulasi Context Boundary & Implicit Resolver Scala.
    Menyelesaikan instance typeclass berdasarkan runtime metadata type tag.
    """
    def __init__(self) -> None:
        self._instances: Dict[Tuple[Type, Type], Any] = {}

    def register_instance(self, typeclass_cls: Type, target_type: Type, instance: Any) -> None:
        self._instances[(typeclass_cls, target_type)] = instance

    def resolve(self, typeclass_cls: Type, target_type: Type) -> Optional[Any]:
        # Exact match
        if (typeclass_cls, target_type) in self._instances:
            return self._instances[(typeclass_cls, target_type)]
        
        # Subtype lookup (polymorphic fallbacks)
        for (tc, registered_t), instance in self._instances.items():
            if tc == typeclass_cls and issubclass(target_type, registered_t):
                return instance
        return None


# Domain models for Type Classes
class MetricTelemetry:
    def __init__(self, key: str, value: float):
        self.key = key
        self.value = value


# Type Class Implementations
class IntShow(Show[int]):
    def show(self, value: int) -> str:
        return f"<PrimitiveInt:{value}>"


class StringShow(Show[str]):
    def show(self, value: str) -> str:
        return f'"{value}"'


class MetricShow(Show[MetricTelemetry]):
    def show(self, value: MetricTelemetry) -> str:
        return f"TelemetryRecord(metric={value.key}, val={value.value:.2f})"


def show_value(val: T, scope: ImplicitScope) -> str:
    """
    Simulasi Scala method signature:
    def showValue[T: Show](val: T)(implicit ev: Show[T]): String
    """
    target_type = type(val)
    tc_instance = scope.resolve(Show, target_type)
    if not tc_instance:
        raise TypeError(f"Implicit resolution error: No given instance of Show[{target_type.__name__}] found!")
    return tc_instance.show(val)


# ==============================================================================
# 4. Higher-Kinded Types (HKT): Functor F[_] Abstraction
# ==============================================================================
# F[_] direpresentasikan sebagai wrapper generic container
A = TypeVar("A")
B = TypeVar("B")


class Functor(ABC):
    """
    Simulasi Higher-Kinded Type:
    trait Functor[F[_]] {
      def map[A, B](fa: F[A])(f: A => B): F[B]
    }
    """
    @abstractmethod
    def map(self, fa: Any, func: Callable[[A], B]) -> Any:
        pass


class ListFunctor(Functor):
    def map(self, fa: List[A], func: Callable[[A], B]) -> List[B]:
        return [func(item) for item in fa]


class OptionFunctor(Functor):
    def map(self, fa: Optional[A], func: Callable[[A], B]) -> Optional[B]:
        if fa is None:
            return None
        return func(fa)


# ==============================================================================
# Main Orchestration & Validation Pipeline
# ==============================================================================
def main() -> None:
    print_banner("1. Simulasi Variance Subtyping [+T, -T, T]")
    print(f"Hierarki Tipe: {CLR_YELLOW}Organism <: Animal <: Canine <: Dog{CLR_RESET}\n")

    # Invariance check: Box[T]
    inv_pass = TypeRelationshipEngine.check_variance(VarianceRule.INVARIANT, Canine, Canine)
    inv_fail = TypeRelationshipEngine.check_variance(VarianceRule.INVARIANT, Dog, Canine)
    log_substep(inv_pass, "Invariant Check: Box[Canine] <: Box[Canine]", "Identical types allowed")
    log_substep(not inv_fail, "Invariant Reject: Box[Dog] </: Box[Canine]", "Strict invariance upheld")

    # Covariance check: Producer[+T]
    cov_pass = TypeRelationshipEngine.check_variance(VarianceRule.COVARIANT, Dog, Animal)
    cov_fail = TypeRelationshipEngine.check_variance(VarianceRule.COVARIANT, Animal, Dog)
    log_substep(cov_pass, "Covariant Check: Producer[Dog] <: Producer[Animal]", "Dog <: Animal implies Producer[Dog] <: Producer[Animal]")
    log_substep(not cov_fail, "Covariant Reject: Producer[Animal] </: Producer[Dog]", "Narrowing forbidden in covariant position")

    # Contravariance check: Serializer[-T]
    contra_pass = TypeRelationshipEngine.check_variance(VarianceRule.CONTRAVARIANT, Dog, Organism)
    contra_fail = TypeRelationshipEngine.check_variance(VarianceRule.CONTRAVARIANT, Organism, Dog)
    log_substep(contra_pass, "Contravariant Check: Consumer[Organism] <: Consumer[Dog]", "Consumer of generic can consume specialized")
    log_substep(not contra_fail, "Contravariant Reject: Consumer[Dog] </: Consumer[Organism]", "Specialized cannot consume generic")

    print_banner("2. Simulasi Path-Dependent Types (Outer.this.Inner)")
    net_alpha = GraphNetwork("ProductionMesh")
    net_beta = GraphNetwork("StagingMesh")

    node_a1 = net_alpha.create_node("Gateway-1")
    node_a2 = net_alpha.create_node("Worker-1")
    node_b1 = net_beta.create_node("RogueNode")

    print(f"  Membuat Node Path: {node_a1}")
    print(f"  Membuat Node Path: {node_a2}")
    print(f"  Membuat Node Path: {node_b1}\n")

    # Intra-network connection (Same path instance)
    valid_conn, msg1 = net_alpha.connect(node_a1, node_a2)
    log_substep(valid_conn, "Intra-Path Verification", msg1)

    # Cross-network connection (Different path instance - Compile/Verification error)
    invalid_conn, msg2 = net_alpha.connect(node_a1, node_b1)
    log_substep(not invalid_conn, "Path-Dependent Rejection", msg2)

    print_banner("3. Ad-hoc Polymorphism (Type Classes & Implicit Scope)")
    implicit_scope = ImplicitScope()
    implicit_scope.register_instance(Show, int, IntShow())
    implicit_scope.register_instance(Show, str, StringShow())
    implicit_scope.register_instance(Show, MetricTelemetry, MetricShow())

    payloads: List[Any] = [404, "Cluster-Leader-Active", MetricTelemetry("cpu_utilization", 88.423)]
    for item in payloads:
        rendered = show_value(item, implicit_scope)
        log_substep(True, f"Resolved Show[{type(item).__name__}]", rendered)

    # Test failure on missing implicit instance
    try:
        show_value(3.14159, implicit_scope)  # Float has no registered instance
        log_substep(False, "Missing Implicit", "Should fail")
    except TypeError as e:
        log_substep(True, "Implicit Resolution Guard", str(e))

    print_banner("4. Higher-Kinded Types (Functor F[_])")
    list_functor = ListFunctor()
    option_functor = OptionFunctor()

    raw_data: List[int] = [10, 20, 30]
    doubled_data = list_functor.map(raw_data, lambda x: x * 2)
    log_substep(doubled_data == [20, 40, 60], "ListFunctor F[List[Int]] -> F[List[Int]]", f"Result: {doubled_data}")

    opt_val: Optional[str] = "scala_advanced_engine"
    upper_opt = option_functor.map(opt_val, lambda s: s.upper())
    log_substep(upper_opt == "SCALA_ADVANCED_ENGINE", "OptionFunctor F[Option[String]]", f"Result: {upper_opt}")

    empty_opt: Optional[str] = None
    mapped_empty = option_functor.map(empty_opt, lambda s: s.upper())
    log_substep(mapped_empty is None, "OptionFunctor F[Option[None]]", f"Result: {mapped_empty}")

    print(f"\n{CLR_BOLD}{CLR_GREEN}>> Seluruh simulasi sistem pengetikan tingkat lanjut Scala berhasil dieksekusi.{CLR_RESET}\n")


if __name__ == "__main__":
    main()
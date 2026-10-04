#!/usr/bin/env python3
"""
Lab Hands-on: Scala Collections & Evaluation Strategies Deep Dive
Memodelkan Arsitektur Koleksi Scala:
1. Persistent Immutable Data Structures (Cons List & Structural Sharing)
2. Strict (Eager) Evaluation vs Scala View / Non-Strict (Lazy) Pipelines
3. Pipeline Fusion & Short-Circuit Optimization Metrics
"""

import time
import sys
from typing import Callable, Any, Generator, Optional

# --- ANSI Terminal Color Palette ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_RED = "\033[31m"
CLR_MAGENTA = "\033[35m"
CLR_BLUE = "\033[34m"

# ============================================================================
# 1. STRUCTURAL SHARING: Scala Immutable List (Cons / Nil Implementation)
# ============================================================================

class ScalaList:
    """Basis abstrak untuk sealed trait List[+A] Scala."""
    @property
    def is_empty(self) -> bool:
        raise NotImplementedError

    @property
    def head(self) -> Any:
        raise NotImplementedError

    @property
    def tail(self) -> 'ScalaList':
        raise NotImplementedError

    def cons(self, elem: Any) -> 'Cons':
        """Operator '::' (prepend) Scala: O(1) time & space."""
        return Cons(elem, self)

    def to_list(self) -> list:
        res = []
        curr = self
        while not curr.is_empty:
            res.append(curr.head)
            curr = curr.tail
        return res


class NilType(ScalaList):
    """Singleton case object Nil extends List[Nothing]."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NilType, cls).__new__(cls)
        return cls._instance

    @property
    def is_empty(self) -> bool:
        return True

    @property
    def head(self) -> Any:
        raise IndexError("head of empty list (Nil)")

    @property
    def tail(self) -> 'ScalaList':
        raise UnsupportedOperationException("tail of empty list (Nil)")

    def __repr__(self) -> str:
        return "Nil"


Nil = NilType()


class Cons(ScalaList):
    """case class ::[+A](head: A, tail: List[A]) extends List[A]."""
    __slots__ = ('_head', '_tail')

    def __init__(self, head: Any, tail: ScalaList):
        self._head = head
        self._tail = tail

    @property
    def is_empty(self) -> bool:
        return False

    @property
    def head(self) -> Any:
        return self._head

    @property
    def tail(self) -> ScalaList:
        return self._tail

    def __repr__(self) -> str:
        elems = []
        curr: ScalaList = self
        count = 0
        while not curr.is_empty and count < 8:
            elems.append(repr(curr.head))
            curr = curr.tail
            count += 1
        if not curr.is_empty:
            elems.append("...")
        return f"{' :: '.join(elems)} :: Nil"


# ============================================================================
# 2. INSTRUMENTATION & METRICS COLLECTOR
# ============================================================================

class PipelineMetrics:
    """Mengukur overhead komputasi antar strategi evaluasi."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.map_calls = 0
        self.filter_calls = 0
        self.intermediate_allocations = 0

    def trace_map(self, elem: Any) -> Any:
        self.map_calls += 1
        return elem

    def trace_filter(self, verdict: bool) -> bool:
        self.filter_calls += 1
        return verdict


metrics = PipelineMetrics()

# ============================================================================
# 3. EVALUATION STRATEGIES: Strict (Eager) vs Non-Strict (Scala View)
# ============================================================================

class StrictCollection:
    """
    Simulasi Evaluasi Strict (Eager) Scala Standar:
    Setiap tahap transformasi (map, filter) menghasilkan koleksi perantara baru
    secara penuh (all items dievaluasi sebelum tahap selanjutnya dimulai).
    """
    def __init__(self, data: list):
        self._data = data

    def map(self, f: Callable[[Any], Any]) -> 'StrictCollection':
        out = []
        for x in self._data:
            metrics.trace_map(x)
            out.append(f(x))
        metrics.intermediate_allocations += len(out)
        return StrictCollection(out)

    def filter(self, p: Callable[[Any], bool]) -> 'StrictCollection':
        out = []
        for x in self._data:
            if metrics.trace_filter(p(x)):
                out.append(x)
        metrics.intermediate_allocations += len(out)
        return StrictCollection(out)

    def take(self, n: int) -> list:
        return self._data[:n]


class ScalaView:
    """
    Simulasi Koleksi Non-Strict (Scala View / LazyList):
    Transformasi disusun ke dalam closure pipeline komposit. Tidak ada alokasi
    koleksi perantara, evaluasi bersifat demand-driven (short-circuiting).
    """
    def __init__(self, generator_factory: Callable[[], Generator[Any, None, None]]):
        self._gen_factory = generator_factory

    @classmethod
    def from_iterable(cls, iterable: Any) -> 'ScalaView':
        return cls(lambda: (x for x in iterable))

    def map(self, f: Callable[[Any], Any]) -> 'ScalaView':
        def _pipeline():
            for x in self._gen_factory():
                metrics.trace_map(x)
                yield f(x)
        return ScalaView(_pipeline)

    def filter(self, p: Callable[[Any], bool]) -> 'ScalaView':
        def _pipeline():
            for x in self._gen_factory():
                if metrics.trace_filter(p(x)):
                    yield x
        return ScalaView(_pipeline)

    def take(self, n: int) -> list:
        """Terminal consumer: Menggerakkan demand ke pipeline secara lazy."""
        res = []
        gen = self._gen_factory()
        for _ in range(n):
            try:
                res.append(next(gen))
            except StopIteration:
                break
        return res


# ============================================================================
# 4. EXPERIMENTAL TESTBED & BENCHMARKS
# ============================================================================

def demonstrate_structural_sharing():
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== 1. STRUCTURAL SHARING & PERSISTENT DATA STRUCTURE ==={CLR_RESET}")
    print("Membuktikan identitas memori node ekor (tail pointer identity):")

    # Inisialisasi basis list: common_tail = 3 :: 4 :: 5 :: Nil
    common_tail = Nil.cons(5).cons(4).cons(3)
    list_a = common_tail.cons(2).cons(1)  # 1 :: 2 :: common_tail
    list_b = common_tail.cons(99).cons(88) # 88 :: 99 :: common_tail

    print(f"List A: {CLR_GREEN}{list_a}{CLR_RESET}")
    print(f"List B: {CLR_YELLOW}{list_b}{CLR_RESET}")

    # Ekstraksi referensi tail bersarang
    tail_a = list_a.tail.tail
    tail_b = list_b.tail.tail

    print(f"Tail A pointer ID : {CLR_MAGENTA}{hex(id(tail_a))}{CLR_RESET}")
    print(f"Tail B pointer ID : {CLR_MAGENTA}{hex(id(tail_b))}{CLR_RESET}")

    shared = (tail_a is tail_b)
    print(f"Node Berbagi Memori (tail_a is tail_b): {CLR_BOLD}{CLR_GREEN if shared else CLR_RED}{shared}{CLR_RESET}")
    print("-> Scala merealisasikan efisiensi memori tanpa mutasi (Pure Functional Immutability).")


def run_pipeline_experiment(dataset_size: int, take_limit: int):
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== 2. STRICT EVALUATION VS SCALA VIEW (LAZY) BENCHMARK ==={CLR_RESET}")
    print(f"Dataset Size: {CLR_YELLOW}{dataset_size:,} elemen{CLR_RESET} | Ambil Demand: {CLR_YELLOW}{take_limit} elemen{CLR_RESET}")

    raw_data = list(range(1, dataset_size + 1))

    # Operasi transformator: CPU cost simulator
    def transform_op(x: int) -> int:
        return (x * 3) ^ 0x5A

    # Predikat filter: kelipatan 7
    def predicate_op(x: int) -> bool:
        return x % 7 == 0

    # --- Mode A: Strict Evaluation ---
    metrics.reset()
    start_strict = time.perf_counter()
    strict_engine = StrictCollection(raw_data)
    strict_res = strict_engine.map(transform_op).filter(predicate_op).take(take_limit)
    elapsed_strict = (time.perf_counter() - start_strict) * 1000.0

    strict_map_ops = metrics.map_calls
    strict_filter_ops = metrics.filter_calls
    strict_allocs = metrics.intermediate_allocations

    # --- Mode B: Scala View (Non-Strict / Lazy) ---
    metrics.reset()
    start_view = time.perf_counter()
    view_engine = ScalaView.from_iterable(raw_data)
    view_res = view_engine.map(transform_op).filter(predicate_op).take(take_limit)
    elapsed_view = (time.perf_counter() - start_view) * 1000.0

    view_map_ops = metrics.map_calls
    view_filter_ops = metrics.filter_calls
    view_allocs = metrics.intermediate_allocations

    # --- Output Validasi Kesetaraan ---
    assert strict_res == view_res, "Ketidakcocokan hasil antara Strict dan Lazy!"
    print(f"\nVerifikasi Output: {CLR_GREEN}MATCH OK{CLR_RESET} (Sample: {strict_res[:5]}...)")

    # --- Tabel Metrik Eksekusi ---
    print("\n" + "=" * 70)
    print(f"{'Metrik Eksekusi':<30} | {'Strict (Eager)':<18} | {'Scala View (Lazy)':<18}")
    print("-" * 70)
    print(f"{'Transformasi (map) calls':<30} | {strict_map_ops:<18,} | {view_map_ops:<18,}")
    print(f"{'Predikat (filter) calls':<30} | {strict_filter_ops:<18,} | {view_filter_ops:<18,}")
    print(f"{'Intermediate Allocations':<30} | {strict_allocs:<18,} | {view_allocs:<18,}")
    print(f"{'Elapsed Time (ms)':<30} | {elapsed_strict:<18.3f} | {elapsed_view:<18.3f}")
    print("=" * 70)

    # Analisis Keuntungan Efisiensi
    reduction_ops = ((strict_map_ops - view_map_ops) / strict_map_ops) * 100.0
    speedup = elapsed_strict / (elapsed_view if elapsed_view > 0 else 0.0001)

    print(f"\n{CLR_BOLD}Analisis Optimasi Arsitektural Scala:{CLR_RESET}")
    print(f"- Operasi transformasi dieliminasi: {CLR_GREEN}{reduction_ops:.2f}%{CLR_RESET}")
    print(f"- Percepatan Eksekusi (Speedup): {CLR_GREEN}{speedup:.2f}x{CLR_RESET}")
    print("- Karakteristik Evaluasi: Scala View menyatukan fungsi (Pipeline Fusion) dan")
    print("  menghentikan komputasi seketika setelah limit 'take' terpenuhi (Short-circuit).")


def demonstrate_infinite_stream():
    print(f"\n{CLR_BOLD}{CLR_CYAN}=== 3. INFINITE LAZY EVALUATION (LazyList Simulasi) ==={CLR_RESET}")
    print("Mengevaluasi deret Fibonacci tanpa batas dengan demand-driven pull:")

    def fibonacci_stream():
        a, b = 0, 1
        while True:
            yield a
            a, b = b, a + b

    # Membuat View atas stream tak berhingga
    fib_view = ScalaView(fibonacci_stream)
    
    # Ambil 12 bilangan pertama yang genap
    even_fibs = fib_view.filter(lambda x: x % 2 == 0).take(8)
    print(f"First 8 Even Fibonacci: {CLR_GREEN}{even_fibs}{CLR_RESET}")
    print("-> Pada evaluasi Strict, operasi ini akan menyebabkan Infinite Loop / OOM.")


# ============================================================================
# MAIN ENTRYPOINT
# ============================================================================

def main():
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}   LAB TEKNIS: SISTEM KOLEKSI SCALA & EVALUATION STRATEGIES (PYTHON)  {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}")

    demonstrate_structural_sharing()
    run_pipeline_experiment(dataset_size=100_000, take_limit=10)
    demonstrate_infinite_stream()

    print(f"\n{CLR_GREEN}{CLR_BOLD}[OK] Hands-on Simulasi Selesai dengan Berhasil.{CLR_RESET}\n")

if __name__ == "__main__":
    main()
labs/02-Programming-Languages/scala/03-OOP-&-Traits/lab_exercise.py
#!/usr/bin/env python3
"""
Scala OOP & Traits Deep Dive Lab (Python Simulator)
Simulates Scala's advanced object-oriented features:
1. Dynamic Trait Mixins with Linearization (C3 super-call resolution simulation)
2. Self-Type Annotations (Dependency Injection without heavy frameworks)
3. Abstract Types vs Path-Dependent Types
4. Object Equality vs Structural Equality (eq vs == simulation)
"""

import inspect
import time
from typing import Dict, Any, List, Type, TypeVar, Optional, Set

# ANSI Color Codes for clean, structured terminal output
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_CYAN = "\033[36m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_MAGENTA = "\033[35m"
C_BLUE = "\033[34m"

def print_section(title: str):
    print(f"\n{C_BOLD}{C_CYAN}{'=' * 75}{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}[SCALA ARCHITECTURE SIMULATION] {title.upper()}{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}{'=' * 75}{C_RESET}")

# -----------------------------------------------------------------------------
# Module 1: Trait Linearization & Stackable Modifications
# -----------------------------------------------------------------------------
# In Scala:
# class BaseQueue
# trait Incrementing extends BaseQueue
# trait Doubling extends BaseQueue
# trait Filtering extends BaseQueue
# class MyQueue extends BaseQueue with Doubling with Incrementing with Filtering
# Evaluation goes right-to-left in 'with', wrapping the stack via super calls.

class BaseQueue:
    def __init__(self):
        self.data: List[int] = []

    def put(self, x: int) -> None:
        self.data.append(x)

    def get(self) -> Optional[int]:
        return self.data.pop(0) if self.data else None

    def __repr__(self) -> str:
        return f"Queue({self.data})"

class Incrementing(BaseQueue):
    """Trait stackable modification: increments element before queueing."""
    def put(self, x: int) -> None:
        modified = x + 1
        print(f"  {C_BLUE}[Trait: Incrementing]{C_RESET} {x} -> {modified}")
        super().put(modified)

class Doubling(BaseQueue):
    """Trait stackable modification: doubles element before queueing."""
    def put(self, x: int) -> None:
        modified = x * 2
        print(f"  {C_MAGENTA}[Trait: Doubling]{C_RESET} {x} -> {modified}")
        super().put(modified)

class Filtering(BaseQueue):
    """Trait stackable modification: drops negative numbers."""
    def put(self, x: int) -> None:
        if x >= 0:
            print(f"  {C_GREEN}[Trait: Filtering]{C_RESET} {x} passes filter (>= 0)")
            super().put(x)
        else:
            print(f"  {C_RED}[Trait: Filtering]{C_RESET} {x} DROPPED (< 0)")

def explain_linearization(cls: Type) -> None:
    """Displays method resolution order (MRO) corresponding to Scala Linearization."""
    mro_names = [c.__name__ for c in cls.__mro__ if c is not object]
    print(f"{C_YELLOW}Linearization Hierarchy for {cls.__name__}:{C_RESET}")
    print(f"  {' -> '.join(mro_names)} -> AnyRef -> Any")

# -----------------------------------------------------------------------------
# Module 2: Cake Pattern & Self-Type Annotations (Dependency Injection)
# -----------------------------------------------------------------------------
# In Scala:
# trait DatabaseComponent { def db: Database }
# trait LoggerComponent { def logger: Logger }
# trait UserServiceComponent { this: DatabaseComponent with LoggerComponent => ... }

class ScalaSelfTypeViolationError(TypeError):
    """Raised when an object fails to meet its self-type contract."""
    pass

class TraitContractMeta(type):
    """
    Enforces self-type constraints at instantiation time.
    Ensures that any class using a trait declared with `_required_traits`
    inherits or mixes in all required traits.
    """
    def __call__(cls, *args, **kwargs):
        # Inspect MRO of the concrete class being instantiated
        ancestors: Set[Type] = set(cls.__mro__)
        for base in cls.__mro__:
            required: Set[Type] = getattr(base, "_required_traits", set())
            for req in required:
                if req not in ancestors:
                    raise ScalaSelfTypeViolationError(
                        f"Self-type violation: Class '{cls.__name__}' mixed with trait '{base.__name__}' "
                        f"requires self-type '{req.__name__}', but it is missing in the linearization hierarchy!"
                    )
        return super().__call__(*args, **kwargs)

# Trait definitions
class DatabaseComponent:
    def execute_query(self, sql: str) -> str:
        return f"OK: Executed '{sql}'"

class LoggerComponent:
    def log(self, level: str, msg: str) -> None:
        print(f"  {C_CYAN}[LOG::{level.upper()}]{C_RESET} {msg}")

class UserServiceTrait(metaclass=TraitContractMeta):
    """
    Simulates:
    trait UserServiceComponent {
      this: DatabaseComponent with LoggerComponent =>
      def authenticate(user: str): Boolean
    }
    """
    _required_traits: Set[Type] = {DatabaseComponent, LoggerComponent}

    def authenticate(self, username: str) -> bool:
        # Access self-type members safely
        # Note: Dynamic dispatch assumes 'self' satisfies the required traits
        self.log("INFO", f"Authenticating user '{username}'...") # type: ignore
        result = self.execute_query(f"SELECT * FROM users WHERE name='{username}'") # type: ignore
        self.log("INFO", f"Database response: {result}") # type: ignore
        return True

# Valid Cake Construction
class ProductionUserService(UserServiceTrait, DatabaseComponent, LoggerComponent):
    pass

# Invalid Construction (Missing LoggerComponent)
class BrokenUserService(UserServiceTrait, DatabaseComponent):
    pass

# -----------------------------------------------------------------------------
# Module 3: Path-Dependent Types Simulation
# -----------------------------------------------------------------------------
# In Scala:
# class Network {
#   class Member(val name: String)
#   def join(m: Member) = ...
# }
# val net1 = new Network; val net2 = new Network
# val m1 = new net1.Member("Alice")
# net2.join(m1) // Compile-time Type Error!

class Network:
    def __init__(self, name: str):
        self.name = name
        self.members: List['Network.Member'] = []

    def create_member(self, username: str) -> 'Network.Member':
        return Network.Member(self, username)

    def join(self, member: 'Network.Member') -> None:
        # Check path dependency: member must belong to THIS outer network instance
        if member.outer_network is not self:
            raise TypeError(
                f"Path-Dependent Type Mismatch!\n"
                f"  Found:    {member.outer_network.name}.Member ('{member.username}')\n"
                f"  Required: {self.name}.Member"
            )
        self.members.append(member)
        print(f"  {C_GREEN}Success:{C_RESET} '{member.username}' joined {self.name}")

    class Member:
        def __init__(self, outer_network: 'Network', username: str):
            self.outer_network = outer_network
            self.username = username

        def __repr__(self) -> str:
            return f"{self.outer_network.name}.Member({self.username})"

# -----------------------------------------------------------------------------
# Execution & Interactive Verification
# -----------------------------------------------------------------------------

def test_stackable_traits():
    print_section("1. Stackable Modifications & Linearization (MRO)")

    # Linearization order 1:
    # class QueueA extends BaseQueue with Incrementing with Doubling with Filtering
    # Python MRO: QueueA -> Filtering -> Doubling -> Incrementing -> BaseQueue
    class QueueA(Filtering, Doubling, Incrementing, BaseQueue):
        pass

    explain_linearization(QueueA)
    q_a = QueueA()
    print(f"\nPutting 3 into QueueA (Order: Filtering -> Doubling -> Incrementing):")
    q_a.put(3)
    print(f"Result in QueueA: {q_a.data}")

    print(f"\nPutting -1 into QueueA:")
    q_a.put(-1)
    print(f"Result in QueueA: {q_a.data}")

    # Linearization order 2 (Reversed traits):
    # class QueueB extends BaseQueue with Filtering with Doubling with Incrementing
    # Python MRO: QueueB -> Incrementing -> Doubling -> Filtering -> BaseQueue
    class QueueB(Incrementing, Doubling, Filtering, BaseQueue):
        pass

    print()
    explain_linearization(QueueB)
    q_b = QueueB()
    print(f"\nPutting -1 into QueueB (Order: Incrementing -> Doubling -> Filtering):")
    # -1 is filtered out immediately because Filtering is outermost!
    # Wait, in QueueB MRO: Incrementing runs first -> then Doubling -> then Filtering
    # Let's trace: Incrementing(-1) -> Doubling(0) -> Filtering(0) -> Passes!
    q_b.put(-1)
    print(f"Result in QueueB: {q_b.data}")

def test_self_types():
    print_section("2. Self-Type Annotations & Cake Pattern DI")
    print("Instantiating ProductionUserService (with all required traits):")
    try:
        service = ProductionUserService()
        service.authenticate("admin_scala")
        print(f"  {C_GREEN}Result:{C_RESET} ProductionUserService successfully satisfied self-types.")
    except Exception as e:
        print(f"  {C_RED}Failed:{C_RESET} {e}")

    print("\nAttempting to instantiate BrokenUserService (missing LoggerComponent):")
    try:
        broken = BrokenUserService()
        broken.authenticate("hacker")
    except ScalaSelfTypeViolationError as err:
        print(f"  {C_RED}[Enforced at runtime]:{C_RESET} {err}")

def test_path_dependent_types():
    print_section("3. Path-Dependent Types Simulation")
    prod_net = Network("ProdCluster")
    dev_net = Network("DevCluster")

    alice = prod_net.create_member("Alice")
    bob = dev_net.create_member("Bob")

    print(f"Created: {alice}")
    print(f"Created: {bob}")

    print(f"\nAttempting valid join: alice into prod_net:")
    prod_net.join(alice)

    print(f"\nAttempting path-dependent illegal join: bob (DevCluster) into prod_net:")
    try:
        prod_net.join(bob)
    except TypeError as e:
        print(f"  {C_RED}[Path-Dependent Error Caught]:{C_RESET}\n  {e}")

def main():
    start_time = time.time()
    print(f"{C_BOLD}{C_GREEN}SCALA 3 ADVANCED OOP & TRAITS SIMULATION INITIALIZED{C_RESET}")
    print(f"Host Engine: Python {inspect.sys.version.split()[0]} Standard Library")

    test_stackable_traits()
    test_self_types()
    test_path_dependent_types()

    elapsed = (time.time() - start_time) * 1000
    print_section("Benchmark & Completion")
    print(f"{C_GREEN}All modules executed successfully.{C_RESET} Elapsed time: {elapsed:.2f}ms\n")

if __name__ == "__main__":
    main()
labs/02-Programming-Languages/scala/02-Pattern-Matching-Deep-Dive/lab_exercise.py


    def __repr__(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}{self.path}"

class URLParser:
    """Scala Custom Extractor: object URLParser { def unapply(s: String) = ... }"""
    @staticmethod
    def unapply(raw: str) -> Optional[Tuple[str, str, int, str]]:
        # Regex: proto://host(:port)?(/path)?
        pattern = r"^(https?)://([a-zA-Z0-9.\-]+)(?::([0-9]+))?(/?.*)$"
        match = re.match(pattern, raw)
        if not match:
            return None
        proto, host, port_str, path = match.groups()
        port = int(port_str) if port_str else (443 if proto == "https" else 80)
        path = path if path else "/"
        return (proto, host, port, path)

class SecureDomain:
    """Scala Extractor for Pattern Guard / Sub-pattern extractor: def unapply(host: String)"""
    @staticmethod
    def unapply(host: str) -> bool:
        return host.endswith(".internal.net") or host.endswith(".company.com")


# ---------------------------------------------------------------------------
# Engine: AST Evaluator & Pattern Matcher
# ---------------------------------------------------------------------------

class ScalaEngine:
    def __init__(self):
        self.reduction_steps = 0

    def evaluate(self, expr: Expr) -> int:
        """
        Simulates Scala pattern matching with exhaustive structural decomposition
        and constant folding optimizations.
        """
        self.reduction_steps += 1
        
        # Match against Number
        if isinstance(expr, Number):
            return expr.value

        # Match against Add(Number(0), right) => Optimization: 0 + x = x
        if isinstance(expr, Add) and isinstance(expr.left, Number) and expr.left.value == 0:
            print(f"    {CLR_CYAN}[Opt: Zero Identity Left]{CLR_RESET} 0 + {expr.right} -> {expr.right}")
            return self.evaluate(expr.right)

        # Match against Add(left, Number(0)) => Optimization: x + 0 = x
        if isinstance(expr, Add) and isinstance(expr.right, Number) and expr.right.value == 0:
            print(f"    {CLR_CYAN}[Opt: Zero Identity Right]{CLR_RESET} {expr.left} + 0 -> {expr.left}")
            return self.evaluate(expr.left)

        # Match against Multiply(Number(0), _) => Optimization: 0 * x = 0
        if isinstance(expr, Multiply) and isinstance(expr.left, Number) and expr.left.value == 0:
            print(f"    {CLR_CYAN}[Opt: Zero Annihilation]{CLR_RESET} 0 * {expr.right} -> 0")
            return 0

        # Match against Multiply(Number(1), right) => Optimization: 1 * x = x
        if isinstance(expr, Multiply) and isinstance(expr.left, Number) and expr.left.value == 1:
            print(f"    {CLR_CYAN}[Opt: Multiplicative Identity]{CLR_RESET} 1 * {expr.right} -> {expr.right}")
            return self.evaluate(expr.right)

        # Standard Recursive Matches
        if isinstance(expr, Add):
            return self.evaluate(expr.left) + self.evaluate(expr.right)

        if isinstance(expr, Multiply):
            return self.evaluate(expr.left) * self.evaluate(expr.right)

        if isinstance(expr, Variable):
            raise RuntimeError(f"Unbound variable: {expr.name}")

        raise ValueError(f"MatchError: Unhandled case for {expr}")

    def route_request(self, raw_url: str) -> str:
        """
        Simulates Scala extractor unapply with pattern guards:
        raw_url match {
          case URLParser("https", host, 443, path) if SecureDomain.unapply(host) => ...
          case URLParser("http", host, _, _) => ...
          case _ => ...
        }
        """
        extracted = URLParser.unapply(raw_url)
        if extracted is not None:
            proto, host, port, path = extracted
            
            # Pattern Guard: Protocol must be https, domain must be internal/secure
            if proto == "https" and SecureDomain.unapply(host):
                return (f"{CLR_GREEN}SECURE_INTERNAL_GATEWAY{CLR_RESET} -> Route to RPC Mesh "
                        f"[Host: {host}, Port: {port}, Path: '{path}']")
            
            # Pattern Guard: Insecure HTTP
            if proto == "http":
                return (f"{CLR_RED}INSECURE_REJECTED{CLR_RESET} -> Rejecting plain HTTP "
                        f"[Host: {host}, Port: {port}]")

            # Fallback for standard HTTPS
            if proto == "https":
                return (f"{CLR_YELLOW}PUBLIC_DMZ_GATEWAY{CLR_RESET} -> Route to Public Edge "
                        f"[Host: {host}:{port}{path}]")

        return f"{CLR_RED}MALFORMED_URL_ERROR{CLR_RESET} -> MatchError on '{raw_url}'"


# ---------------------------------------------------------------------------
# Test Scenarios and Benchmark Execution
# ---------------------------------------------------------------------------

def run_ast_pattern_matching_lab():
    print(f"\n{CLR_BOLD}{CLR_BLUE}=== SCENARIO 1: Algebraic Data Type (Case Class) Pattern Matching & Simplification ==={CLR_RESET}")
    engine = ScalaEngine()

    # Construct AST: ((0 + 42) * 1) + (0 * 999)
    # Target simplified evaluation: 42 + 0 = 42
    ast = Add(
        Multiply(
            Add(Number(0), Number(42)),
            Number(1)
        ),
        Multiply(
            Number(0),
            Number(999)
        )
    )

    print(f"{CLR_YELLOW}Initial AST:{CLR_RESET} {ast}")
    print(f"{CLR_YELLOW}Evaluating with recursive structural matching & algebraic reductions...{CLR_RESET}")
    
    t0 = time.perf_counter()
    result = engine.evaluate(ast)
    t1 = time.perf_counter()

    print(f"{CLR_GREEN}[SUCCESS] Result:{CLR_RESET} {result}")
    print(f"Total Reductions / Match Steps: {engine.reduction_steps}")
    print(f"Eval Time: {(t1 - t0) * 1_000_000:.2f} µs\n")


def run_extractor_pattern_matching_lab():
    print(f"{CLR_BOLD}{CLR_BLUE}=== SCENARIO 2: Extractor Objects (`unapply`) with Pattern Guards ==={CLR_RESET}")
    engine = ScalaEngine()

    test_urls = [
        "https://auth.internal.net:8443/v1/tokens",
        "https://api.company.com/checkout",
        "http://legacy.billing.net/invoices",
        "https://external-partner.org/webhook",
        "ftp://invalid-protocol.net/data",
        "not-even-a-url"
    ]

    for url in test_urls:
        print(f"\nIncoming Request: {CLR_CYAN}{url}{CLR_RESET}")
        route_decision = engine.route_request(url)
        print(f"  Decision: {route_decision}")


def run_sealed_exhaustiveness_simulation():
    print(f"\n{CLR_BOLD}{CLR_BLUE}=== SCENARIO 3: Sealed Trait Exhaustiveness Checking Simulation ==={CLR_RESET}")
    
    known_expr_subtypes = {Number, Add, Multiply, Variable}
    
    # Simulate a compiler match check covering only a subset
    handled_types = {Number, Add}
    unhandled = known_expr_subtypes - handled_types

    print("Simulating Scala compiler analysis for sealed trait Expr hierarchy:")
    print(f"  All registered subtypes : {[t.__name__ for t in known_expr_subtypes]}")
    print(f"  Handled cases in match  : {[t.__name__ for t in handled_types]}")
    
    if unhandled:
        missing_names = ", ".join(t.__name__ for t in unhandled)
        print(f"  {CLR_YELLOW}[COMPILER WARNING] match may not be exhaustive!{CLR_RESET}")
        print(f"  It would fail on the following inputs: {CLR_RED}{missing_names}{CLR_RESET}")
    else:
        print(f"  {CLR_GREEN}[COMPILER CHECK PASS] Pattern match is exhaustive.{CLR_RESET}")


def main():
    print(f"{CLR_BOLD}Scala Pattern Matching & Extractor Architecture Hands-on Simulator{CLR_RESET}")
    print(f"PID: {os.getpid()} | Runtime: Python {sys.version.split()[0]} Standalone Standard Library")
    
    start_time = time.perf_counter()
    run_ast_pattern_matching_lab()
    run_extractor_pattern_matching_lab()
    run_sealed_exhaustiveness_simulation()
    end_time = time.perf_counter()

    print(f"\n{CLR_BOLD}{CLR_GREEN}=== All Pattern Matching Deep Dive Scenarios Completed in {(end_time - start_time)*1000:.2f} ms ==={CLR_RESET}")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Scala Pattern Matching Deep Dive - Standalone Lab Simulation
Simulates:
1. Sealed Trait / Case Class Algebraic Data Types (ADTs) & Recursive Deconstruction
2. Extractor Objects with Custom `unapply` Pattern Matching
3. Pattern Guards (`case ... if cond =>`)
4. Exhaustiveness Check Simulation and MatchError handling
"""

import os
import sys
import time
import re
from typing import Any, Tuple, Optional, List

# ANSI Color Codes for structured terminal output
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[31m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_BLUE    = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN    = "\033[36m"

# ---------------------------------------------------------------------------
# ADT Simulation: sealed trait Expr
# ---------------------------------------------------------------------------

class Expr:
    """Simulates: sealed trait Expr"""
    pass

class Number(Expr):
    """Simulates: case class Number(value: Int) extends Expr"""
    def __init__(self, value: int):
        self.value = value

    def __repr__(self) -> str:
        return f"Number({self.value})"

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Number) and self.value == other.value

class Add(Expr):
    """Simulates: case class Add(left: Expr, right: Expr) extends Expr"""
    def __init__(self, left: Expr, right: Expr):
        self.left = left
        self.right = right

    def __repr__(self) -> str:
        return f"Add({self.left}, {self.right})"

class Multiply(Expr):
    """Simulates: case class Multiply(left: Expr, right: Expr) extends Expr"""
    def __init__(self, left: Expr, right: Expr):
        self.left = left
        self.right = right

    def __repr__(self) -> str:
        return f"Multiply({self.left}, {self.right})"

class Variable(Expr):
    """Simulates: case class Variable(name: String) extends Expr"""
    def __init__(self, name: str):
        self.name = name

    def __repr__(self) -> str:
        return f"Variable({self.name})"


# ---------------------------------------------------------------------------
# Extractor Simulation: object URLParser { def unapply(...) }
# ---------------------------------------------------------------------------

class ParsedURL:
    def __init__(self, protocol: str, host: str, port: int, path: str):
        self.protocol = protocol
        self.host = host
        self.port = port
        self.path = pathlabs/02-Programming-Languages/scala/08-Type-Level-Programming/lab_exercise.py

        print(f"Matrix B ({B.rows.name}x{B.cols.name}) initialized.")

        print(f"\n{C_YELLOW}[TEST 1] Type-Safe Multiplication A x B:{C_RESET}")
        C = MatrixOps.multiply(A, B)
        print(f"{C_GREEN}Success! Produced Matrix C: {C}{C_RESET}")
        print(f"Data: {C.data}")

        # Invalid matrix for multiplication with A
        D = Matrix(Nat3, Nat1, [[1], [2], [3]])
        print(f"\nMatrix D ({D.rows.name}x{D.cols.name}) initialized.")
        print(f"\n{C_YELLOW}[TEST 2] Intentional Type Mismatch Multiplication A x D:{C_RESET}")
        try:
            MatrixOps.multiply(A, D)
        except TypeLevelCompileError as err:
            print(f"{C_RED}Type-Level Compilation Error Caught as Expected!{C_RESET}")
            print(f"  Error details: {err}")

    @staticmethod
    def run_heterogeneous_list_lab():
        print_header("2. Heterogeneous List (HList) and Type-Level Induction")

        # Construct HList: "Scala 3" :: 42 :: 3.14159 :: True :: HNil
        hlist = HCons("Scala 3", HCons(42, HCons(3.14159, HCons(True, HNil()))))

        print(f"Constructed HList: {C_CYAN}{hlist}{C_RESET}")
        print(f"Type Signature:   {C_CYAN}{hlist.type_signature()}{C_RESET}")
        print(f"Computed Length:  {C_CYAN}{hlist.length()}{C_RESET}")

        print(f"\n{C_YELLOW}[TEST 3] Type-Safe Index Access:{C_RESET}")
        val0 = HListIndexer.get(hlist, Nat0)
        print(f"  Index 0 -> Value: {val0} (Type: {type(val0).__name__})")

        val1 = HListIndexer.get(hlist, Nat1)
        print(f"  Index 1 -> Value: {val1} (Type: {type(val1).__name__})")

        val2 = HListIndexer.get(hlist, Nat2)
        print(f"  Index 2 -> Value: {val2} (Type: {type(val2).__name__})")

        print(f"\n{C_YELLOW}[TEST 4] Out-of-Bounds Induction Access:{C_RESET}")
        try:
            # Nat5 does not exist in 4-element HList
            HListIndexer.get(hlist, Succ(Nat3))
        except TypeLevelCompileError as err:
            print(f"{C_RED}Type-Level Bound Check Prevented Illegal Access:{C_RESET}")
            print(f"  Error details: {err}")


def main():
    start_time = time.perf_counter()
    print(f"{C_BOLD}{C_BLUE}Type-Level Programming Engine Initialized (Scala 3 / Shapeless Simulation){C_RESET}")
    print(f"Interpreter: Python {sys.version.split()[0]} Standard Library")

    LabRunner.run_peano_matrix_lab()
    LabRunner.run_heterogeneous_list_lab()

    elapsed = (time.perf_counter() - start_time) * 1000
    print(f"\n{C_GREEN}All Type-Level verifications completed successfully in {elapsed:.2f} ms.{C_RESET}\n")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Scala 08: Type-Level Programming & Dependent Types Deep Dive
A standalone simulator modeling:
1. Peano Numbers & Church Encodings for Compile-Time Dimension Verification
2. Type-Level Matrix Multiplication with Shape Inference
3. Heterogeneous Lists (HList inspired by Shapeless) with Induction-based Lookup
"""

import sys
import time
from typing import Generic, TypeVar, Any, Optional

# --- ANSI Terminal Color Palette ---
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_CYAN = "\033[36m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_MAGENTA = "\033[35m"
C_BLUE = "\033[34m"

def print_header(title: str):
    print(f"\n{C_BOLD}{C_MAGENTA}{'=' * 75}{C_RESET}")
    print(f"{C_BOLD}{C_MAGENTA}[SCALA TYPE-LEVEL SIMULATION] {title}{C_RESET}")
    print(f"{C_BOLD}{C_MAGENTA}{'=' * 75}{C_RESET}")


class TypeLevelCompileError(TypeError):
    """Simulates a Scala compile-time type mismatch / implicit resolution failure."""
    pass


# ============================================================================
# 1. Peano Number Type-Level Representation
# ============================================================================
# In Scala:
# sealed trait Nat
# class _0 extends Nat
# class Succ[N <: Nat] extends Nat

class Nat:
    """Type-level Natural Number base trait."""
    val: int = 0
    name: str = "_0"

class Zero(Nat):
    val: int = 0
    name: str = "_0"

class Succ(Nat):
    def __init__(self, prev: Nat):
        self.prev = prev
        self.val = prev.val + 1
        self.name = f"Succ[{prev.name}]"

    def __repr__(self):
        return self.name

# Helper instances representing phantom type witnesses
Nat0 = Zero()
Nat1 = Succ(Nat0)
Nat2 = Succ(Nat1)
Nat3 = Succ(Nat2)
Nat4 = Succ(Nat3)


# ============================================================================
# 2. Type-Level Dimensionally Checked Matrix
# ============================================================================
# In Scala 3:
# case class Matrix[R <: Nat, C <: Nat](data: List[List[Double]])(implicit r: ValueOf[R], c: ValueOf[C])

R = TypeVar("R", bound=Nat)
C = TypeVar("C", bound=Nat)
K = TypeVar("K", bound=Nat)

class Matrix(Generic[R, C]):
    def __init__(self, rows: R, cols: C, data: list[list[float]]):
        self.rows = rows
        self.cols = cols
        self.data = data
        
        # Verify runtime dimension matches type witness (like runtime assertion of phantom types)
        if len(data) != rows.val:
            raise TypeLevelCompileError(
                f"Row dimension mismatch: Type witness expected {rows.val}, runtime data had {len(data)}"
            )
        for row in data:
            if len(row) != cols.val:
                raise TypeLevelCompileError(
                    f"Col dimension mismatch: Type witness expected {cols.val}, runtime row had {len(row)}"
                )

    def __repr__(self):
        return f"Matrix[{self.rows.name}, {self.cols.name}] (Size: {self.rows.val}x{self.cols.val})"


class MatrixOps:
    """
    Simulates Scala Typeclass with implicit proof:
    def multiply[R <: Nat, K <: Nat, C <: Nat](a: Matrix[R, K], b: Matrix[K, C]): Matrix[R, C]
    """
    @staticmethod
    def multiply(a: Matrix[R, K], b: Matrix[K, C]) -> Matrix[R, C]:
        print(f"  {C_CYAN}[Type-Checker]{C_RESET} Proving dimension compatibility: A.cols ({a.cols.name}) =:= B.rows ({b.rows.name})")
        
        # Compile-time check simulation: A.cols type identity must match B.rows type identity
        if a.cols.val != b.rows.val:
            raise TypeLevelCompileError(
                f"\n  Cannot resolve implicit evidence: {a.cols.name} =:= {b.rows.name}\n"
                f"  Type mismatch in matrix multiplication:\n"
                f"    Matrix A: ({a.rows.val} x {a.cols.val}) [Col dimension: {a.cols.name}]\n"
                f"    Matrix B: ({b.rows.val} x {b.cols.val}) [Row dimension: {b.rows.name}]\n"
                f"  Inner dimensions must be identically typed at compile-time!"
            )

        print(f"  {C_GREEN}[Implicit Resolved]{C_RESET} Dimensions matched. Producing Matrix[{a.rows.name}, {b.cols.name}]")

        # Standard matrix dot product
        result_data = [[0.0 for _ in range(b.cols.val)] for _ in range(a.rows.val)]
        for i in range(a.rows.val):
            for j in range(b.cols.val):
                total = 0.0
                for k in range(a.cols.val):
                    total += a.data[i][k] * b.data[k][j]
                result_data[i][j] = total

        return Matrix(a.rows, b.cols, result_data)


# ============================================================================
# 3. Heterogeneous List (HList) and Type-Level Induction
# ============================================================================
# In Scala (Shapeless):
# sealed trait HList
# case class HCons[+H, +T <: HList](head: H, tail: T) extends HList
# case object HNil extends HList

class HList:
    """Base heterogeneous list trait."""
    def length(self) -> int:
        raise NotImplementedError

    def type_signature(self) -> str:
        raise NotImplementedError


class HNil(HList):
    """Empty HList."""
    def length(self) -> int:
        return 0

    def type_signature(self) -> str:
        return "HNil"

    def __repr__(self):
        return "HNil"


class HCons(HList):
    """Inductive HList node preserving explicit element types."""
    def __init__(self, head: Any, tail: HList):
        self.head = head
        self.tail = tail

    def length(self) -> int:
        return 1 + self.tail.length()

    def type_signature(self) -> str:
        head_type = type(self.head).__name__
        return f"{head_type} :: {self.tail.type_signature()}"

    def __repr__(self):
        return f"{repr(self.head)} :: {self.tail}"


class HListIndexer:
    """
    Simulates inductive implicit lookup (Aux pattern):
    trait At[L <: HList, N <: Nat] { type Out; def apply(l: L): Out }
    """
    @staticmethod
    def get(hlist: HList, index: Nat) -> Any:
        def inductive_step(curr: HList, remaining: int, target_name: str) -> Any:
            if isinstance(curr, HNil):
                raise TypeLevelCompileError(
                    f"IndexOutOfBounds at type-level: cannot prove index {target_name} in HList."
                )
            if remaining == 0:
                assert isinstance(curr, HCons)
                return curr.head
            assert isinstance(curr, HCons)
            return inductive_step(curr.tail, remaining - 1, target_name)

        return inductive_step(hlist, index.val, index.name)


# ============================================================================
# Lab Execution & Verification
# ============================================================================

class LabRunner:
    @staticmethod
    def run_peano_matrix_lab():
        print_header("1. Peano Number Type-Checking & Matrix Shape Safety")

        # Matrix A: 2x3 (Nat2 x Nat3)
        A = Matrix(Nat2, Nat3, [
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0]
        ])
        print(f"Matrix A ({A.rows.name}x{A.cols.name}) initialized.")

        # Matrix B: 3x2 (Nat3 x Nat2)
        B = Matrix(Nat3, Nat2, [
            [7.0, 8.0],
            [9.0, 1.0],
            [2.0, 3.0]
        ])labs/02-Programming-Languages/scala/09-Concurrent-Programming/lab_exercise.py
#!/usr/bin/env python3
"""
Scala Concurrent Programming Deep Dive:
Akka Actor Model, Message Dispatcher, Supervision & Future/Promise Execution Context
Standard Library Implementation (threading, queue, time, sys)
"""

import sys
import time
import threading
import queue
from typing import Callable, Any, Optional, Dict, List

# --- Terminal ANSI Color Constants ---
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[31m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_BLUE    = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN    = "\033[36m"

# ============================================================================
# 1. Scala Future and Promise Simulation (Execution Context)
# ============================================================================

class ExecutionContext:
    """
    Simulates Scala's `scala.concurrent.ExecutionContext`.
    Backed by a multi-worker daemon thread pool to process asynchronous tasks.
    """
    def __init__(self, num_threads: int = 4):
        self._work_queue: queue.Queue = queue.Queue()
        self._workers: List[threading.Thread] = []
        self._running = True

        for i in range(num_threads):
            t = threading.Thread(target=self._worker_loop, name=f"ExecutionContext-Worker-{i}", daemon=True)
            t.start()
            self._workers.append(t)

    def _worker_loop(self):
        while self._running:
            try:
                task = self._work_queue.get(timeout=0.1)
                task()
                self._work_queue.task_done()
            except queue.Empty:
                continue

    def execute(self, runnable: Callable[[], None]):
        self._work_queue.put(runnable)

    def shutdown(self):
        self._running = False


class ScalaFuture:
    """
    Simulates `scala.concurrent.Future[T]`.
    Represents a read-only handle to a value that may become available asynchronously.
    Supports callbacks and monadic composition simulation (map / flatMap).
    """
    def __init__(self, task: Callable[[], Any], ec: ExecutionContext):
        self._ec = ec
        self._value: Optional[Any] = None
        self._exception: Optional[Exception] = None
        self._is_completed = False
        self._callbacks: List[Callable[['ScalaFuture'], None]] = []
        self._lock = threading.Lock()

        # Enqueue execution onto the ExecutionContext
        self._ec.execute(lambda: self._run(task))

    def _run(self, task: Callable[[], Any]):
        try:
            val = task()
            with self._lock:
                self._value = val
                self._is_completed = True
        except Exception as ex:
            with self._lock:
                self._exception = ex
                self._is_completed = True

        # Trigger onComplete handlers
        with self._lock:
            callbacks = list(self._callbacks)
        for cb in callbacks:
            self._ec.execute(lambda c=cb: c(self))

    def on_complete(self, callback: Callable[['ScalaFuture'], None]):
        with self._lock:
            if self._is_completed:
                self._ec.execute(lambda: callback(self))
            else:
                self._callbacks.append(callback)

    def map(self, transform: Callable[[Any], Any]) -> 'ScalaFuture':
        """Simulates Future.map(f) via Promise/Deferred mechanics."""
        def transformed_task():
            # Block or wait until source is done
            while not self._is_completed:
                time.sleep(0.01)
            if self._exception:
                raise self._exception
            return transform(self._value)

        return ScalaFuture(transformed_task, self._ec)

    def value(self) -> Optional[Any]:
        with self._lock:
            return self._value


# ============================================================================
# 2. Akka Actor Model Architecture Simulation
# ============================================================================

class ActorRef:
    """Addressable handle to an Actor. Protects internal actor state from external direct access."""
    def __init__(self, actor: 'Actor', mailbox: queue.Queue):
        self._actor = actor
        self._mailbox = mailbox

    def tell(self, msg: Any, sender: Optional['ActorRef'] = None):
        """Scala '!' operator: Fire-and-forget asynchronous message dispatch."""
        self._mailbox.put((msg, sender))

    @property
    def path(self) -> str:
        return self._actor.name


class Actor:
    """
    Base Actor class modeled after `akka.actor.Actor`.
    Provides life-cycle hooks: preStart, postStop, and receive.
    """
    def __init__(self, name: str):
        self.name = name
        self.self: Optional[ActorRef] = None
        self.sender: Optional[ActorRef] = None

    def pre_start(self):
        """Lifecycle hook: Called during actor bootstrap."""
        pass

    def post_stop(self):
        """Lifecycle hook: Called when actor is stopped."""
        pass

    def receive(self, message: Any) -> None:
        """Pattern matching message receiver. To be implemented by concrete actors."""
        raise NotImplementedError


class ActorSystem:
    """
    Simulates `akka.actor.ActorSystem`.
    Responsible for actor lifecycle management, dispatching, and thread allocation.
    """
    def __init__(self, system_name: str):
        self.system_name = system_name
        self._actors: Dict[str, ActorRef] = {}
        self._running = True
        self._lock = threading.Lock()

    def actor_of(self, actor_factory: Callable[[], Actor], name: str) -> ActorRef:
        """Instantiates an actor, wraps it in ActorRef, and binds an event-loop thread."""
        with self._lock:
            actor = actor_factory()
            actor.name = f"akka://{self.system_name}/user/{name}"
            mailbox = queue.Queue()
            actor_ref = ActorRef(actor, mailbox)
            actor.self = actor_ref

            actor.pre_start()

            # Dedicated message pump thread per actor (simulating ActorCell processing)
            thread = threading.Thread(
                target=self._actor_loop,
                args=(actor, mailbox),
                name=f"Dispatcher-{name}",
                daemon=True
            )
            thread.start()

            self._actors[actor.name] = actor_ref
            return actor_ref

    def _actor_loop(self, actor: Actor, mailbox: queue.Queue):
        while self._running:
            try:
                msg, sender = mailbox.get(timeout=0.1)
                actor.sender = sender
                try:
                    actor.receive(msg)
                except Exception as err:
                    # Akka Supervision Strategy Simulation: Log and restart actor state
                    print(f"{CLR_RED}[SUPERVISOR]{CLR_RESET} Actor {actor.name} failed with: {err}. Applying Resume Strategy.")
                finally:
                    mailbox.task_done()
            except queue.Empty:
                continue

        actor.post_stop()

    def terminate(self):
        self._running = False


# ============================================================================
# 3. Practical Concrete Actors & Telemetry Pipeline
# ============================================================================

class WorkMessage:
    def __init__(self, task_id: int, payload: str):
        self.task_id = task_id
        self.payload = payload


class WorkCompleted:
    def __init__(self, task_id: int, result: str):
        self.task_id = task_id
        self.result = result


class WorkerActor(Actor):
    """Processes computational tasks asynchronously."""
    def receive(self, message: Any):
        if isinstance(message, WorkMessage):
            # Simulate work execution
            time.sleep(0.05)
            if message.payload == "MALFORMED":
                raise ValueError(f"Corrupt payload detected in task #{message.task_id}!")

            processed = f"PROCESSED[{message.payload.upper()}]"
            print(f"  {CLR_CYAN}[Worker]{CLR_RESET} Completed task #{message.task_id} -> {processed}")
            if self.sender:
                self.sender.tell(WorkCompleted(message.task_id, processed), sender=self.self)
        else:
            print(f"  {CLR_YELLOW}[Worker]{CLR_RESET} Unknown message received: {message}")


class MasterActor(Actor):
    """Aggregates results and coordinates workers."""
    def __init__(self, name: str, expected_tasks: int):
        super().__init__(name)
        self.expected_tasks = expected_tasks
        self.completed_count = 0

    def receive(self, message: Any):
        if isinstance(message, WorkCompleted):
            self.completed_count += 1
            print(f"  {CLR_GREEN}[Master]{CLR_RESET} Received Task #{message.task_id} completion. Progress: {self.completed_count}/{self.expected_tasks}")
            if self.completed_count >= self.expected_tasks:
                print(f"  {CLR_BOLD}{CLR_GREEN}[Master] All planned work batches successfully resolved!{CLR_RESET}")


# ============================================================================
# 4. Hands-on Execution Scenario
# ============================================================================

def main():
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}   SCALA CONCURRENCY DEEP DIVE: AKKA ACTORS & FUTURES PIPELINE        {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_BLUE}======================================================================{CLR_RESET}")

    # --- Phase 1: ExecutionContext and Monadic Futures ---
    print(f"\n{CLR_BOLD}{CLR_MAGENTA}--- PHASE 1: ExecutionContext & Monadic Future Pipeline ---{CLR_RESET}")
    ec = ExecutionContext(num_threads=2)

    def fetch_user_data() -> int:
        print(f"  {CLR_YELLOW}[Future-1]{CLR_RESET} Fetching raw telemetry metric from remote partition...")
        time.sleep(0.1)
        return 42

    fut1 = ScalaFuture(fetch_user_data, ec)
    # Map operation transforms future lazily
    fut2 = fut1.map(lambda x: x * 10).map(lambda x: f"TelemetryScore={x}")

    done_event = threading.Event()

    def future_callback(f: ScalaFuture):
        print(f"  {CLR_GREEN}[Future-Completed]{CLR_RESET} Monadic chain final output: {CLR_BOLD}{f.value()}{CLR_RESET}")
        done_event.set()

    fut2.on_complete(future_callback)
    done_event.wait(timeout=2.0)

    # --- Phase 2: Akka Actor Messaging & Fault Tolerance ---
    print(f"\n{CLR_BOLD}{CLR_MAGENTA}--- PHASE 2: Akka Actor System & Supervision (OneForOne Resume) ---{CLR_RESET}")
    system = ActorSystem("ClusterSystem")

    master = system.actor_of(lambda: MasterActor("masterCoordinator", expected_tasks=3), "master")
    worker = system.actor_of(lambda: WorkerActor("computeWorker"), "worker")

    time.sleep(0.05)

    print(f"Dispatching valid tasks and a deliberate failure task to test Actor Resilience...")
    worker.tell(WorkMessage(1, "payload_alpha"), sender=master)
    # This message simulates unexpected failure:
    worker.tell(WorkMessage(2, "MALFORMED"), sender=master)
    # Valid tasks continue processing because supervisor resumes:
    worker.tell(WorkMessage(3, "payload_beta"), sender=master)
    worker.tell(WorkMessage(4, "payload_gamma"), sender=master)

    # Allow time for asynchronous message delivery & processing
    time.
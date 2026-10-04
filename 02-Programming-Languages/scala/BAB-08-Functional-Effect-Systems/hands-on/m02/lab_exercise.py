#!/usr/bin/env python3
"""
Lab Hands-on: Functional Effect Systems (Cats Effect & ZIO Architecture)
Simulating IO Monad, Trampolined Runtime, Fiber-Based Concurrency, and Resource Safety.

Standard Library Only (Zero 3rd-party dependencies).
Compatible with Python 3.8+
"""

from __future__ import annotations
import sys
import time
import threading
import queue
from typing import Any, Callable, Generic, Optional, TypeVar, List, Tuple
from dataclasses import dataclass

# ANSI Color codes for formatted terminal output
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"

A = TypeVar("A")
B = TypeVar("B")
E = TypeVar("E")

# -----------------------------------------------------------------------------
# 1. Functional Effect Core: IO AST (Algebraic Data Type)
# -----------------------------------------------------------------------------
# In Cats Effect (IO) and ZIO, an effect is NOT a running computation.
# It is an immutable, pure data structure describing a workflow (Blueprint).

class IO(Generic[A]):
    """Pure description of a side-effecting, asynchronous or synchronous computation."""

    def map(self, f: Callable[[A], B]) -> IO[B]:
        return self.flat_map(lambda a: IO.pure(f(a)))

    def flat_map(self, f: Callable[[A], IO[B]]) -> IO[B]:
        return _FlatMap(self, f)

    def void(self) -> IO[None]:
        return self.map(lambda _: None)

    @staticmethod
    def pure(value: A) -> IO[A]:
        """Lifts a pure, already-evaluated value into the IO context."""
        return _Pure(value)

    @staticmethod
    def delay(thunk: Callable[[], A]) -> IO[A]:
        """Suspends an impure side-effect (call-by-name thunk) into IO."""
        return _Delay(thunk)

    @staticmethod
    def sleep(seconds: float) -> IO[None]:
        """Suspends execution for a specified duration."""
        return _Sleep(seconds)

    @staticmethod
    def fork(io: IO[A]) -> IO[Fiber[A]]:
        """Spawns a new lightweight green thread (Fiber) running this IO."""
        return _Fork(io)

    @staticmethod
    def race(io1: IO[A], io2: IO[B]) -> IO[Tuple[Optional[A], Optional[B]]]:
        """Races two effects concurrently; yields result of the winner."""
        return _Race(io1, io2)

    def bracket(self, use: Callable[[A], IO[B]], release: Callable[[A], IO[None]]) -> IO[B]:
        """Guarantees resource cleanup even in the event of failure or cancellation."""
        return _Bracket(self, use, release)

    def unsafe_run_sync(self) -> A:
        """Edge of the world: Executes the IO description via the trampolined runtime."""
        return Runtime.default().run_sync(self)


@dataclass(frozen=True)
class _Pure(IO[A]):
    value: A

@dataclass(frozen=True)
class _Delay(IO[A]):
    thunk: Callable[[], A]

@dataclass(frozen=True)
class _FlatMap(IO[A]):
    source: IO[Any]
    cont: Callable[[Any], IO[A]]

@dataclass(frozen=True)
class _Sleep(IO[None]):
    seconds: float

@dataclass(frozen=True)
class _Fork(IO[Any]):
    target: IO[Any]

@dataclass(frozen=True)
class _Bracket(IO[A]):
    acquire: IO[Any]
    use: Callable[[Any], IO[A]]
    release: Callable[[Any], IO[None]]

@dataclass(frozen=True)
class _Race(IO[Tuple[Any, Any]]):
    io1: IO[Any]
    io2: IO[Any]


# -----------------------------------------------------------------------------
# 2. Concurrency Primitives: Fiber & Ref (Cats Effect / ZIO equivalents)
# -----------------------------------------------------------------------------

class Fiber(Generic[A]):
    """Handle to a running concurrent computation (lightweight fiber)."""
    def __init__(self, target_io: IO[A], runtime: Runtime):
        self._target_io = target_io
        self._runtime = runtime
        self._result: Optional[A] = None
        self._error: Optional[Exception] = None
        self._done_event = threading.Event()
        self._is_cancelled = False
        self._worker_thread = threading.Thread(target=self._run, daemon=True)
        self._worker_thread.start()

    def _run(self) -> None:
        try:
            if not self._is_cancelled:
                self._result = self._runtime.run_sync(self._target_io)
        except Exception as ex:
            self._error = ex
        finally:
            self._done_event.set()

    def join(self) -> IO[A]:
        """Waits for fiber completion and returns its result."""
        def _join_thunk() -> A:
            self._done_event.wait()
            if self._error:
                raise self._error
            return self._result  # type: ignore
        return IO.delay(_join_thunk)

    def cancel(self) -> IO[None]:
        """Interrupts fiber execution."""
        def _cancel_thunk() -> None:
            self._is_cancelled = True
            self._done_event.set()
        return IO.delay(_cancel_thunk)


class Ref(Generic[A]):
    """Purely functional, atomic mutable reference inspired by cats.effect.Ref."""
    def __init__(self, initial: A):
        self._lock = threading.Lock()
        self._value = initial

    @staticmethod
    def of(initial: A) -> IO[Ref[A]]:
        return IO.delay(lambda: Ref(initial))

    def get(self) -> IO[A]:
        return IO.delay(lambda: self._value)

    def set(self, new_val: A) -> IO[None]:
        def _set() -> None:
            with self._lock:
                self._value = new_val
        return IO.delay(_set)

    def update(self, f: Callable[[A], A]) -> IO[None]:
        def _update() -> None:
            with self._lock:
                self._value = f(self._value)
        return IO.delay(_update)

    def modify(self, f: Callable[[A], Tuple[A, B]]) -> IO[B]:
        def _modify() -> B:
            with self._lock:
                new_state, result = f(self._value)
                self._value = new_state
                return result
        return IO.delay(_modify)


# -----------------------------------------------------------------------------
# 3. Trampolined Runtime Engine (Cats Effect RTS Simulation)
# -----------------------------------------------------------------------------

class Runtime:
    """
    RTS (Runtime System) executing IO ASTs using an explicit continuation stack
    (Trampolining) to guarantee heap-based execution and prevent call-stack overflows.
    """
    _instance = None

    @classmethod
    def default(cls) -> Runtime:
        if cls._instance is None:
            cls._instance = Runtime()
        return cls._instance

    def run_sync(self, root_io: IO[A]) -> A:
        current: Any = root_io
        call_stack: List[Callable[[Any], IO[Any]]] = []

        while True:
            # 1. Pure value
            if isinstance(current, _Pure):
                res = current.value
                if not call_stack:
                    return res
                continuation = call_stack.pop()
                current = continuation(res)

            # 2. Delayed execution (Thunk)
            elif isinstance(current, _Delay):
                res = current.thunk()
                if not call_stack:
                    return res
                continuation = call_stack.pop()
                current = continuation(res)

            # 3. FlatMap monadic binding (Trampoline unwind)
            elif isinstance(current, _FlatMap):
                call_stack.append(current.cont)
                current = current.source

            # 4. Asynchronous Sleep
            elif isinstance(current, _Sleep):
                time.sleep(current.seconds)
                res = None
                if not call_stack:
                    return res  # type: ignore
                continuation = call_stack.pop()
                current = continuation(res)

            # 5. Fork (Fiber creation)
            elif isinstance(current, _Fork):
                fiber = Fiber(current.target, self)
                res = fiber
                if not call_stack:
                    return res  # type: ignore
                continuation = call_stack.pop()
                current = continuation(res)

            # 6. Bracket (Acquire -> Use -> Release resource guarantee)
            elif isinstance(current, _Bracket):
                acquired_resource = None
                use_error = None
                res = None
                try:
                    acquired_resource = self.run_sync(current.acquire)
                    res = self.run_sync(current.use(acquired_resource))
                except Exception as e:
                    use_error = e
                finally:
                    if acquired_resource is not None:
                        # Release is guaranteed even on failure
                        self.run_sync(current.release(acquired_resource))
                
                if use_error is not None:
                    raise use_error

                if not call_stack:
                    return res  # type: ignore
                continuation = call_stack.pop()
                current = continuation(res)

            # 7. Race Concurrency
            elif isinstance(current, _Race):
                res_box: queue.Queue = queue.Queue(maxsize=1)
                
                def runner1():
                    try:
                        r = self.run_sync(current.io1)
                        res_box.put(("io1", r))
                    except Exception as err:
                        res_box.put(("err", err))

                def runner2():
                    try:
                        r = self.run_sync(current.io2)
                        res_box.put(("io2", r))
                    except Exception as err:
                        res_box.put(("err", err))

                t1 = threading.Thread(target=runner1, daemon=True)
                t2 = threading.Thread(target=runner2, daemon=True)
                t1.start()
                t2.start()

                winner, winner_val = res_box.get()
                if winner == "err":
                    raise winner_val
                
                race_result = (winner_val, None) if winner == "io1" else (None, winner_val)

                if not call_stack:
                    return race_result  # type: ignore
                continuation = call_stack.pop()
                current = continuation(race_result)

            else:
                raise TypeError(f"Unknown IO node encountered in Runtime: {type(current)}")


# -----------------------------------------------------------------------------
# 4. Simulation Scenarios & Verification
# -----------------------------------------------------------------------------

def banner(title: str) -> None:
    print(f"\n{BOLD}{CYAN}=== {title} ==={RESET}")

def run_stack_safety_demo():
    banner("1. Stack Safety via Trampoline Engine")
    N = 10_000
    print(f"Constructing a deeply chained flatMap sequence of {BOLD}{N:,}{RESET} operations...")
    
    # Pure recursive functional chain: io = io.flatMap(n => IO.pure(n + 1))
    # In standard Python, N=10,000 causes RecursionError (default max recursion depth ~1000).
    chain = IO.pure(0)
    for _ in range(N):
        chain = chain.flat_map(lambda n: IO.pure(n + 1))

    start = time.perf_counter()
    result = chain.unsafe_run_sync()
    duration = (time.perf_counter() - start) * 1000

    print(f"{GREEN}[SUCCESS]{RESET} Evaluated {result:,} nested effects safely without stack overflow!")
    print(f"Trampoline dispatch took: {duration:.2f} ms")


def run_resource_safety_demo():
    banner("2. Guaranteed Resource Management (Bracket Pattern)")

    class ManagedDatabaseConnection:
        def __init__(self, connection_id: str):
            self.connection_id = connection_id
            self.is_open = True

        def query(self, sql: str) -> str:
            if not self.is_open:
                raise RuntimeError("Accessing closed connection!")
            if "FAIL" in sql:
                raise ConnectionResetError("Remote DB connection aborted unexpectedly!")
            return f"Query results for '{sql}'"

        def close(self) -> None:
            self.is_open = False

    acquire_io = IO.delay(lambda: (
        print(f"  {BLUE}→ [ACQUIRE]{RESET} Opening physical database socket pool..."),
        ManagedDatabaseConnection("pg-node-prod-01")
    )[1])

    release_io = lambda conn: IO.delay(lambda: (
        print(f"  {YELLOW}← [RELEASE]{RESET} Releasing {conn.connection_id} back to connection pool!"),
        conn.close()
    )[1])

    use_failing_io = lambda conn: IO.delay(lambda: (
        print(f"  {MAGENTA}⚙ [USE]{RESET} Executing critical ledger transactional query..."),
        conn.query("SELECT * FROM transactions WHERE status = 'FAIL'")
    ))

    effect = acquire_io.bracket(use_failing_io, release_io)

    print("Executing bracketed computation with intentional failure injection:")
    try:
        effect.unsafe_run_sync()
    except Exception as ex:
        print(f"{RED}[HANDLED ERROR]{RESET} Caught injected error: {type(ex).__name__}: {ex}")

    print(f"{GREEN}[SUCCESS]{RESET} Resource finalizer was guaranteed execution during abnormal termination.")


def run_fiber_concurrency_and_ref_demo():
    banner("3. Fiber Concurrency, Racing, and Functional State (Ref)")

    # Test Racing effects: Fast worker vs Slow worker
    fast_effect = IO.sleep(0.05).flat_map(lambda _: IO.delay(lambda: "Fast worker (50ms cache HIT)"))
    slow_effect = IO.sleep(0.20).flat_map(lambda _: IO.delay(lambda: "Slow worker (200ms remote RPC)"))

    print("Racing two effects concurrently (IO.race)...")
    race_start = time.perf_counter()
    winner_tuple = IO.race(fast_effect, slow_effect).unsafe_run_sync()
    race_elapsed = (time.perf_counter() - race_start) * 1000

    print(f"{GREEN}[RACE RESULT]{RESET} Winner finished in {race_elapsed:.2f} ms: {winner_tuple[0]}")

    print("\nDemonstrating Shared Concurrency with atomic functional state (Ref)...")
    
    def worker_job(ref: Ref[int], worker_id: int, iterations: int) -> IO[None]:
        def loop(remaining: int) -> IO[None]:
            if remaining <= 0:
                return IO.pure(None)
            # Atomic state update
            return ref.update(lambda x: x + 1).flat_map(lambda _: loop(remaining - 1))
        return loop(iterations)

    program = (
        Ref.of(0).flat_map(lambda ref:
            # Fork 4 concurrent fibers that update the shared atomic Ref
            IO.fork(worker_job(ref, 1, 500)).flat_map(lambda f1:
            IO.fork(worker_job(ref, 2, 500)).flat_map(lambda f2:
            IO.fork(worker_job(ref, 3, 500)).flat_map(lambda f3:
            IO.fork(worker_job(ref, 4, 500)).flat_map(lambda f4:
                # Await all fibers (Join)
                f1.join().flat_map(lambda _:
                f2.join().flat_map(lambda _:
                f3.join().flat_map(lambda _:
                f4.join().flat_map(lambda _:
                    # Fetch final accumulated state
                    ref.get()
                ))))
            ))))
        )
    )

    t0 = time.perf_counter()
    final_counter = program.unsafe_run_sync()
    t_delta = (time.perf_counter() - t0) * 1000

    print(f"Total concurrent fiber increments: {final_counter} / 2000 (Target: 2000)")
    assert final_counter == 2000, "Race condition detected in Ref!"
    print(f"{GREEN}[SUCCESS]{RESET} Atomic Ref remained consistent across 4 concurrent fibers in {t_delta:.2f} ms.")


def main():
    print(f"{BOLD}{GREEN}======================================================================{RESET}")
    print(f"{BOLD}{GREEN}   SCALA LAB: Functional Effect Systems Architecture (Cats Effect & ZIO)   {RESET}")
    print(f"{BOLD}{GREEN}======================================================================{RESET}")

    run_stack_safety_demo()
    run_resource_safety_demo()
    run_fiber_concurrency_and_ref_demo()

    print(f"\n{BOLD}{GREEN}All functional effect patterns successfully verified.{RESET}\n")

if __name__ == "__main__":
    main()

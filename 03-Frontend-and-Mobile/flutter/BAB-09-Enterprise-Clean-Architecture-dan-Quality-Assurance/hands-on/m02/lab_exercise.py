#!/usr/bin/env python3
"""
Lab Hands-on: Flutter Enterprise Clean Architecture & Quality Assurance (Deep Dive)
Simulasi komprehensif implementasi Clean Architecture (Domain, Data, Presentation/BLoC)
disertai Result/Either monad pattern, In-Memory Caching dengan TTL, serta Automated Test Suite.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar, Optional, List, Dict, Any, Callable
import time
import json

# ==============================================================================
# ANSI Color Palette for Enterprise Console Output
# ==============================================================================
class Palette:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"

# ==============================================================================
# CORE / FUNCTIONAL PROGRAMMING ERROR HANDLING (fpdart / dartz simulation)
# ==============================================================================
L = TypeVar('L')
R = TypeVar('R')

class Either(Generic[L, R]):
    """Representasi monad Either (Left: Failure, Right: Success)."""
    def __init__(self, left: Optional[L] = None, right: Optional[R] = None):
        self._left = left
        self._right = right
        self._is_right = right is not None or (left is None and right is None)

    @classmethod
    def left(cls, failure: L) -> 'Either[L, R]':
        return cls(left=failure, right=None)

    @classmethod
    def right(cls, value: R) -> 'Either[L, R]':
        return cls(left=None, right=value)

    def is_right(self) -> bool:
        return self._is_right

    def fold(self, on_left: Callable[[L], Any], on_right: Callable[[R], Any]) -> Any:
        return on_right(self._right) if self._is_right else on_left(self._left)

# Domain Failures
@dataclass(frozen=True)
class Failure:
    message: str

class ServerFailure(Failure):
    pass

class CacheFailure(Failure):
    pass

class NetworkConnectionFailure(Failure):
    pass

# ==============================================================================
# DOMAIN LAYER (Entities, Use Cases, Repository Contracts)
# ==============================================================================
@dataclass(frozen=True)
class UserEntity:
    """Enterprise Domain Entity (Plain Old Dart/Python Object - Immutable)."""
    id: str
    email: str
    tier: str
    is_active: bool

class UserRepository(ABC):
    """Abstract Repository Contract (DIP - Dependency Inversion Principle)."""
    @abstractmethod
    def get_user_profile(self, user_id: str, force_refresh: bool = False) -> Either[Failure, UserEntity]:
        pass

class GetUserProfileUseCase:
    """Encapsulates business workflow logic (Clean Architecture UseCase)."""
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def execute(self, user_id: str, force_refresh: bool = False) -> Either[Failure, UserEntity]:
        if not user_id.strip():
            return Either.left(Failure("Validation Error: User ID cannot be empty."))
        return self.repository.get_user_profile(user_id, force_refresh=force_refresh)

# ==============================================================================
# DATA LAYER (Data Transfer Models, Data Sources, Repository Implementation)
# ==============================================================================
class UserModel(UserEntity):
    """Data transfer object dengan serialisasi JSON & mapping ke Entity."""
    def to_json(self) -> str:
        return json.dumps({
            "id": self.id,
            "email": self.email,
            "tier": self.tier,
            "is_active": self.is_active
        })

    @classmethod
    def from_json(cls, payload: Dict[str, Any]) -> 'UserModel':
        return cls(
            id=payload["id"],
            email=payload["email"],
            tier=payload.get("tier", "standard"),
            is_active=payload.get("is_active", True)
        )

class RemoteDataSource(ABC):
    @abstractmethod
    def fetch_user_from_api(self, user_id: str) -> UserModel:
        pass

class LocalDataSource(ABC):
    @abstractmethod
    def get_cached_user(self, user_id: str) -> Optional[UserModel]:
        pass

    @abstractmethod
    def cache_user(self, user: UserModel) -> None:
        pass

class InMemoryLocalDataSource(LocalDataSource):
    """Simulasi Hive / SharedPreferences caching dengan metadata TTL (Time-To-Live)."""
    def __init__(self, ttl_seconds: float = 2.0):
        self.cache_store: Dict[str, tuple[float, UserModel]] = {}
        self.ttl = ttl_seconds

    def get_cached_user(self, user_id: str) -> Optional[UserModel]:
        if user_id in self.cache_store:
            timestamp, model = self.cache_store[user_id]
            if (time.time() - timestamp) <= self.ttl:
                return model
            del self.cache_store[user_id]  # Cache expired
        return None

    def cache_user(self, user: UserModel) -> None:
        self.cache_store[user.id] = (time.time(), user)

class MockRemoteDataSource(RemoteDataSource):
    """Simulasi Remote REST API client dengan latency dan failure injection."""
    def __init__(self, should_fail: bool = False, network_down: bool = False):
        self.should_fail = should_fail
        self.network_down = network_down
        self.network_call_count = 0
        self.database_mock = {
            "USR-101": {"id": "USR-101", "email": "dev.lead@enterprise.org", "tier": "platinum", "is_active": True},
            "USR-102": {"id": "USR-102", "email": "qa.engineer@enterprise.org", "tier": "gold", "is_active": False}
        }

    def fetch_user_from_api(self, user_id: str) -> UserModel:
        self.network_call_count += 1
        time.sleep(0.04)  # Simulate network latency

        if self.network_down:
            raise ConnectionError("Host unreachable: No route to host.")
        if self.should_fail or user_id not in self.database_mock:
            raise RuntimeError(f"HTTP 404: Record for {user_id} not found.")

        return UserModel.from_json(self.database_mock[user_id])

class UserRepositoryImpl(UserRepository):
    """Implementasi Single Source of Truth dengan strategi Offline-First Caching."""
    def __init__(self, remote_data_source: RemoteDataSource, local_data_source: LocalDataSource):
        self.remote = remote_data_source
        self.local = local_data_source

    def get_user_profile(self, user_id: str, force_refresh: bool = False) -> Either[Failure, UserEntity]:
        # 1. Coba baca dari Cache jika tidak dipaksa refresh
        if not force_refresh:
            cached_data = self.local.get_cached_user(user_id)
            if cached_data:
                return Either.right(cached_data)

        # 2. Tarik dari Remote API
        try:
            remote_data = self.remote.fetch_user_from_api(user_id)
            self.local.cache_user(remote_data)
            return Either.right(remote_data)
        except ConnectionError as ce:
            # Fallback jika jaringan mati namun data kedaluwarsa masih ada
            return Either.left(NetworkConnectionFailure(str(ce)))
        except RuntimeError as re:
            return Either.left(ServerFailure(str(re)))
        except Exception as e:
            return Either.left(Failure(f"Unexpected Exception: {e}"))

# ==============================================================================
# PRESENTATION LAYER (BLoC State Management Simulation)
# ==============================================================================
class UserState(ABC):
    pass

class UserInitial(UserState):
    def __repr__(self): return "UserInitial()"

class UserLoading(UserState):
    def __repr__(self): return "UserLoading()"

class UserLoaded(UserState):
    def __init__(self, user: UserEntity):
        self.user = user
    def __repr__(self): return f"UserLoaded(id={self.user.id}, tier={self.user.tier})"

class UserError(UserState):
    def __init__(self, message: str):
        self.message = message
    def __repr__(self): return f"UserError('{self.message}')"

class UserBloc:
    """Simulasi flutter_bloc pattern: Dispatches Events -> Emits States Stream."""
    def __init__(self, get_user_use_case: GetUserProfileUseCase):
        self.use_case = get_user_use_case
        self.state: UserState = UserInitial()
        self.state_history: List[UserState] = [self.state]

    def _emit(self, next_state: UserState):
        self.state = next_state
        self.state_history.append(next_state)

    def dispatch_fetch_user(self, user_id: str, force_refresh: bool = False):
        self._emit(UserLoading())
        result = self.use_case.execute(user_id, force_refresh)
        result.fold(
            on_left=lambda failure: self._emit(UserError(failure.message)),
            on_right=lambda entity: self._emit(UserLoaded(entity))
        )

# ==============================================================================
# QUALITY ASSURANCE / TEST RUNNER HARNESS
# ==============================================================================
class TestSuite:
    """Automated Unit & Contract Test Harness untuk Arsitektur Enterprise."""
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def assert_true(self, condition: bool, test_name: str, details: str = ""):
        if condition:
            self.passed += 1
            print(f"  {Palette.GREEN}✔ PASS{Palette.RESET} : {test_name}")
        else:
            self.failed += 1
            print(f"  {Palette.RED}✘ FAIL{Palette.RESET} : {test_name} -> {details}")

    def run_all(self):
        print(f"\n{Palette.BOLD}{Palette.CYAN}======================================================================{Palette.RESET}")
        print(f"{Palette.BOLD}{Palette.CYAN} EXECUTING QA AUTOMATED TEST SUITE (Clean Arch & BLoC Verification) {Palette.RESET}")
        print(f"{Palette.BOLD}{Palette.CYAN}======================================================================{Palette.RESET}\n")

        # Test Case 1: Repository Offline-First Strategy
        local_ds = InMemoryLocalDataSource(ttl_seconds=1.0)
        remote_ds = MockRemoteDataSource()
        repo = UserRepositoryImpl(remote_ds, local_ds)

        # Call 1: Fetches remote
        res1 = repo.get_user_profile("USR-101")
        self.assert_true(res1.is_right(), "First call should fetch remote and return Right(UserEntity)")
        self.assert_true(remote_ds.network_call_count == 1, "Remote data source hit counter should increment to 1")

        # Call 2: Must hit local cache
        res2 = repo.get_user_profile("USR-101")
        self.assert_true(res2.is_right(), "Second call should return cached Right(UserEntity)")
        self.assert_true(remote_ds.network_call_count == 1, "Cache hit must prevent remote network roundtrip")

        # Test Case 2: TTL Invalidation
        time.sleep(1.05)  # Wait for cache expiration
        res3 = repo.get_user_profile("USR-101")
        self.assert_true(remote_ds.network_call_count == 2, "Expired cache triggers fresh remote API retrieval")

        # Test Case 3: Network Failure Isolation
        faulty_remote = MockRemoteDataSource(network_down=True)
        faulty_repo = UserRepositoryImpl(faulty_remote, InMemoryLocalDataSource())
        failure_res = faulty_repo.get_user_profile("USR-101")
        self.assert_true(not failure_res.is_right(), "Network outage should return Either.Left(Failure)")
        failure_res.fold(
            on_left=lambda f: self.assert_true(isinstance(f, NetworkConnectionFailure), "Expected NetworkConnectionFailure instance"),
            on_right=lambda r: None
        )

        # Test Case 4: Presentation BLoC State Emission Lifecycle
        use_case = GetUserProfileUseCase(repo)
        bloc = UserBloc(use_case)
        bloc.dispatch_fetch_user("USR-102")

        history_types = [type(s) for s in bloc.state_history]
        expected_sequence = [UserInitial, UserLoading, UserLoaded]
        self.assert_true(history_types == expected_sequence, f"BLoC state progression must match {expected_sequence}")

        # Test Case 5: BLoC Error Handling Lifecycle
        bloc.dispatch_fetch_user("USR-INVALID-999")
        self.assert_true(isinstance(bloc.state, UserError), "Dispatching invalid user id emits UserError state")

        # Summary
        total = self.passed + self.failed
        print(f"\n{Palette.BOLD}Test Execution Summary:{Palette.RESET}")
        print(f"Total: {total} | {Palette.GREEN}Passed: {self.passed}{Palette.RESET} | {Palette.RED}Failed: {self.failed}{Palette.RESET}")
        if self.failed == 0:
            print(f"{Palette.BOLD}{Palette.GREEN}>>> ALL ARCHITECTURAL ASSERTIONS SATISFIED <<<{Palette.RESET}\n")

# ==============================================================================
# MAIN ENTRYPOINT & LIVE DEMONSTRATION
# ==============================================================================
def main():
    print(f"{Palette.BOLD}{Palette.MAGENTA}[Flutter Enterprise Lab] Clean Architecture + QA Pipeline Ready{Palette.RESET}")

    # 1. Run Automated Verification Tests
    qa_runner = TestSuite()
    qa_runner.run_all()

    # 2. Live Runtime Interactive Simulation
    print(f"{Palette.BOLD}{Palette.YELLOW}--- LIVE RUNTIME WORKFLOW SIMULATION ---{Palette.RESET}")
    local_source = InMemoryLocalDataSource(ttl_seconds=3.0)
    remote_source = MockRemoteDataSource()
    repository = UserRepositoryImpl(remote_source, local_source)
    use_case = GetUserProfileUseCase(repository)
    bloc = UserBloc(use_case)

    print(f"[{Palette.BLUE}BLoC Initial State{Palette.RESET}]: {bloc.state}")

    print(f"\nDispatching: Event -> FetchUser('USR-101') [Network Call]")
    bloc.dispatch_fetch_user("USR-101")
    print(f"[{Palette.BLUE}BLoC Final State{Palette.RESET}]: {bloc.state}")

    print(f"\nDispatching: Event -> FetchUser('USR-101') [Cache Hit, Zero Latency]")
    bloc.dispatch_fetch_user("USR-101")
    print(f"[{Palette.BLUE}BLoC Final State{Palette.RESET}]: {bloc.state}")

    print(f"\nDispatching: Event -> FetchUser('USR-101', force_refresh=True)")
    bloc.dispatch_fetch_user("USR-101", force_refresh=True)
    print(f"[{Palette.BLUE}BLoC Final State{Palette.RESET}]: {bloc.state}")

    print(f"\nComplete State Transition Pipeline Record:")
    for idx, st in enumerate(bloc.state_history):
        print(f"  Step {idx:02d}: {Palette.CYAN}{st}{Palette.RESET}")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Lab Exercise: Enterprise Clean Architecture & Quality Assurance in Flutter (Simulation)
BAB-09: Enterprise Clean Architecture dan Quality Assurance
"""

import sys
import time
import json
from dataclasses import dataclass
from typing import Generic, TypeVar, Optional, List, Dict, Any, Callable

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"

# ============================================================================
# CORE / FUNCTIONAL PROGRAMMING UTILS (Either Pattern / Result Type)
# ============================================================================
T = TypeVar('T')
E = TypeVar('E')

class Either(Generic[E, T]):
    """Functional Result container: Left(Failure) or Right(Success)"""
    def __init__(self, left: Optional[E] = None, right: Optional[T] = None, is_right: bool = True):
        self._left = left
        self._right = right
        self._is_right = is_right

    @classmethod
    def left(cls, failure: E) -> 'Either[E, T]':
        return cls(left=failure, right=None, is_right=False)

    @classmethod
    def right(cls, value: T) -> 'Either[E, T]':
        return cls(left=None, right=value, is_right=True)

    def is_right(self) -> bool:
        return self._is_right

    def is_left(self) -> bool:
        return not self._is_right

    def fold(self, on_left: Callable[[E], Any], on_right: Callable[[T], Any]) -> Any:
        if self._is_right:
            return on_right(self._right)  # type: ignore
        return on_left(self._left)  # type: ignore

@dataclass(frozen=True)
class Failure:
    message: str
    code: int

class ServerFailure(Failure):
    pass

class CacheFailure(Failure):
    pass

class NetworkFailure(Failure):
    pass

# ============================================================================
# DOMAIN LAYER (Entities, Repository Interfaces, Use Cases)
# ============================================================================
@dataclass(frozen=True)
class UserAccount:
    """Core Domain Entity: Pure business model independent of database/UI"""
    id: str
    name: str
    tier: str
    balance: float

class UserRepository:
    """Repository Contract Interface (Dependency Inversion Principle)"""
    def get_user(self, user_id: str, force_refresh: bool = False) -> Either[Failure, UserAccount]:
        raise NotImplementedError()

    def update_balance(self, user_id: str, delta: float) -> Either[Failure, UserAccount]:
        raise NotImplementedError()

class GetUserProfileUseCase:
    """Business Use Case: orchestrates retrieving verified user profiles"""
    def __init__(self, repository: UserRepository):
        self._repository = repository

    def execute(self, user_id: str, force_refresh: bool = False) -> Either[Failure, UserAccount]:
        if not user_id or len(user_id.strip()) == 0:
            return Either.left(Failure("User ID cannot be empty", 400))
        return self._repository.get_user(user_id, force_refresh)

# ============================================================================
# DATA LAYER (Models/DTOs, Data Sources, Repository Implementation)
# ============================================================================
class UserModel(UserAccount):
    """Data Transfer Object (DTO) extending Domain Entity with serialization"""
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'UserModel':
        return cls(
            id=data["id"],
            name=data["name"],
            tier=data.get("tier", "standard"),
            balance=float(data.get("balance", 0.0))
        )

    def to_json(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "tier": self.tier,
            "balance": self.balance
        }

class RemoteDataSource:
    """Simulates remote REST API client (e.g. Dio in Flutter)"""
    def __init__(self, simulate_network_fail: bool = False):
        self.simulate_network_fail = simulate_network_fail
        self._db: Dict[str, Dict[str, Any]] = {
            "usr_101": {"id": "usr_101", "name": "Budi Santoso", "tier": "Enterprise VIP", "balance": 14500000.0},
            "usr_102": {"id": "usr_102", "name": "Siti Nurhaliza", "tier": "Gold Partner", "balance": 8250000.0}
        }

    def fetch_user_json(self, user_id: str) -> Dict[str, Any]:
        if self.simulate_network_fail:
            raise ConnectionError("503 Service Unavailable: Remote Gateway Timeout")
        if user_id in self._db:
            return self._db[user_id]
        raise LookupError(f"User '{user_id}' not found on remote server (404)")

class LocalDataSource:
    """Simulates local offline storage (e.g. Hive / Isar / SQLite in Flutter)"""
    def __init__(self):
        self._cache: Dict[str, str] = {}

    def cache_user(self, user_model: UserModel) -> None:
        self._cache[user_model.id] = json.dumps(user_model.to_json())

    def get_cached_user(self, user_id: str) -> Optional[UserModel]:
        raw = self._cache.get(user_id)
        if raw:
            return UserModel.from_json(json.loads(raw))
        return None

    def clear(self) -> None:
        self._cache.clear()

class UserRepositoryImpl(UserRepository):
    """Concrete Repository: coordinates Local and Remote Data Sources"""
    def __init__(self, remote_ds: RemoteDataSource, local_ds: LocalDataSource):
        self.remote_ds = remote_ds
        self.local_ds = local_ds

    def get_user(self, user_id: str, force_refresh: bool = False) -> Either[Failure, UserAccount]:
        # 1. Offline-First check if not forcing refresh
        if not force_refresh:
            cached = self.local_ds.get_cached_user(user_id)
            if cached:
                return Either.right(cached)

        # 2. Remote Fetch
        try:
            raw_data = self.remote_ds.fetch_user_json(user_id)
            model = UserModel.from_json(raw_data)
            # Sync to local cache
            self.local_ds.cache_user(model)
            return Either.right(model)
        except ConnectionError as ce:
            # Fallback to cache if available during network degradation
            cached_fallback = self.local_ds.get_cached_user(user_id)
            if cached_fallback:
                return Either.right(cached_fallback)
            return Either.left(NetworkFailure(str(ce), 503))
        except LookupError as le:
            return Either.left(ServerFailure(str(le), 404))
        except Exception as e:
            return Either.left(Failure(f"Unexpected data exception: {e}", 500))

    def update_balance(self, user_id: str, delta: float) -> Either[Failure, UserAccount]:
        cached = self.local_ds.get_cached_user(user_id)
        if not cached:
            return Either.left(CacheFailure("Cannot mutate uncached user offline", 404))
        updated = UserModel(
            id=cached.id,
            name=cached.name,
            tier=cached.tier,
            balance=cached.balance + delta
        )
        self.local_ds.cache_user(updated)
        return Either.right(updated)

# ============================================================================
# PRESENTATION LAYER (Bloc / State Management Pattern)
# ============================================================================
@dataclass(frozen=True)
class ProfileState:
    name: str

class ProfileInitialState(ProfileState):
    def __init__(self):
        super().__init__("ProfileInitial")

class ProfileLoadingState(ProfileState):
    def __init__(self):
        super().__init__("ProfileLoading")

class ProfileLoadedState(ProfileState):
    def __init__(self, user: UserAccount, source: str):
        super().__init__("ProfileLoaded")
        self.user = user
        self.source = source

class ProfileErrorState(ProfileState):
    def __init__(self, message: str, code: int):
        super().__init__("ProfileError")
        self.message = message
        self.code = code

class ProfileBloc:
    """Presentation Controller: Emits deterministic states in response to events"""
    def __init__(self, get_profile_use_case: GetUserProfileUseCase, local_ds: LocalDataSource):
        self.use_case = get_profile_use_case
        self.local_ds = local_ds
        self.state: ProfileState = ProfileInitialState()
        self.state_history: List[ProfileState] = [self.state]

    def _emit(self, new_state: ProfileState) -> None:
        self.state = new_state
        self.state_history.append(new_state)

    def fetch_profile_event(self, user_id: str, force_refresh: bool = False) -> None:
        self._emit(ProfileLoadingState())
        is_in_cache = self.local_ds.get_cached_user(user_id) is not None
        source_label = "Local Cache (Offline Store)" if (is_in_cache and not force_refresh) else "Remote REST API"

        result = self.use_case.execute(user_id, force_refresh)
        result.fold(
            on_left=lambda failure: self._emit(ProfileErrorState(failure.message, failure.code)),
            on_right=lambda user: self._emit(ProfileLoadedState(user, source_label))
        )

# ============================================================================
# QUALITY ASSURANCE (Automated Unit Testing & Clean Architecture Audit)
# ============================================================================
class QualityAssuranceRunner:
    """Verifies architectural invariants and contract behaviors"""
    @staticmethod
    def run_tests() -> None:
        print(f"\n{BOLD}{CYAN}=== RUNNING QUALITY ASSURANCE & ARCHITECTURE SUITE ==={RESET}")
        tests = [
            ("Test 1: UseCase rejects empty user ID", QualityAssuranceRunner._test_empty_user_id),
            ("Test 2: Remote fetch caches data locally", QualityAssuranceRunner._test_caching_behavior),
            ("Test 3: Network failure returns fallback cache if present", QualityAssuranceRunner._test_network_fallback),
            ("Test 4: Bloc follows Initial -> Loading -> Loaded transition", QualityAssuranceRunner._test_bloc_lifecycle),
        ]
        passed = 0
        for name, test_fn in tests:
            try:
                test_fn()
                print(f"  {GREEN}✔ PASS{RESET} : {name}")
                passed += 1
            except AssertionError as err:
                print(f"  {RED}✘ FAIL{RESET} : {name} -> {err}")
            except Exception as ex:
                print(f"  {RED}✘ ERROR{RESET}: {name} -> {ex}")

        print(f"\nAudit Summary: {passed}/{len(tests)} tests passed successfully.\n")

    @staticmethod
    def _test_empty_user_id():
        remote = RemoteDataSource()
        local = LocalDataSource()
        repo = UserRepositoryImpl(remote, local)
        use_case = GetUserProfileUseCase(repo)
        result = use_case.execute("   ")
        assert result.is_left(), "UseCase should return Left(Failure) for empty string"

    @staticmethod
    def _test_caching_behavior():
        remote = RemoteDataSource()
        local = LocalDataSource()
        repo = UserRepositoryImpl(remote, local)
        assert local.get_cached_user("usr_101") is None, "Cache must be empty initially"
        repo.get_user("usr_101", force_refresh=True)
        cached = local.get_cached_user("usr_101")
        assert cached is not None and cached.id == "usr_101", "User must be cached after remote fetch"

    @staticmethod
    def _test_network_fallback():
        remote = RemoteDataSource(simulate_network_fail=True)
        local = LocalDataSource()
        local.cache_user(UserModel(id="usr_999", name="Offline User", tier="Bronze", balance=100.0))
        repo = UserRepositoryImpl(remote, local)
        result = repo.get_user("usr_999")
        assert result.is_right(), "Should fallback to cache during network failure"

    @staticmethod
    def _test_bloc_lifecycle():
        remote = RemoteDataSource()
        local = LocalDataSource()
        repo = UserRepositoryImpl(remote, local)
        use_case = GetUserProfileUseCase(repo)
        bloc = ProfileBloc(use_case, local)
        bloc.fetch_profile_event("usr_101")
        history_names = [s.name for s in bloc.state_history]
        assert history_names == ["ProfileInitial", "ProfileLoading", "ProfileLoaded"], f"Invalid state cycle: {history_names}"

# ============================================================================
# INTERACTIVE CLI RUNNER
# ============================================================================
def render_header() -> None:
    print(f"{BOLD}{BLUE}==================================================================={RESET}")
    print(f"{BOLD}{CYAN}  FLUTTER ENTERPRISE CLEAN ARCHITECTURE & QA SIMULATOR (BAB-09){RESET}")
    print(f"{BOLD}{BLUE}==================================================================={RESET}")
    print(f"Layers simulated: {MAGENTA}Presentation (Bloc){RESET} -> {CYAN}Domain (UseCase/Entity){RESET} -> {YELLOW}Data (Repo/DataSource){RESET}")

def main() -> None:
    local_ds = LocalDataSource()
    remote_ds = RemoteDataSource(simulate_network_fail=False)
    repo = UserRepositoryImpl(remote_ds, local_ds)
    use_case = GetUserProfileUseCase(repo)
    bloc = ProfileBloc(use_case, local_ds)

    render_header()

    while True:
        print(f"\n{BOLD}Pilih Opsi Simulasi:{RESET}")
        print("1. [Remote Flow] Fetch User Profile (usr_101) dari Remote & Cache")
        print("2. [Cache Hit] Fetch User Profile (usr_101) dari Offline Cache")
        print("3. [QA Fault Injection] Toggle Simulasi Gangguan Jaringan (Network Failure)")
        print("4. [State Inspection] Lihat Riwayat State Transitions di Presentation Layer")
        print("5. [Run Automated Tests] Eksekusi Full Quality Assurance Test Suite")
        print("6. [Reset Cache] Bersihkan Penyimpanan Lokal")
        print("0. Keluar")

        choice = input(f"\n{BOLD}{GREEN}Masukkan pilihan (0-6): {RESET}").strip()

        if choice == "1":
            print(f"\n{CYAN}>>> Triggering Bloc Event: FetchProfileEvent('usr_101', force_refresh=True)...{RESET}")
            time.sleep(0.3)
            bloc.fetch_profile_event("usr_101", force_refresh=True)
            if isinstance(bloc.state, ProfileLoadedState):
                u = bloc.state.user
                print(f"{GREEN}✔ Success! Source: {bloc.state.source}{RESET}")
                print(f"  ID: {u.id} | Name: {u.name} | Tier: {u.tier} | Balance: Rp {u.balance:,.2f}")
            elif isinstance(bloc.state, ProfileErrorState):
                print(f"{RED}✘ Error Code {bloc.state.code}: {bloc.state.message}{RESET}")

        elif choice == "2":
            print(f"\n{CYAN}>>> Triggering Bloc Event: FetchProfileEvent('usr_101', force_refresh=False)...{RESET}")
            time.sleep(0.2)
            bloc.fetch_profile_event("usr_101", force_refresh=False)
            if isinstance(bloc.state, ProfileLoadedState):
                u = bloc.state.user
                print(f"{GREEN}✔ Loaded! Source: {bloc.state.source}{RESET}")
                print(f"  ID: {u.id} | Name: {u.name} | Tier: {u.tier} | Balance: Rp {u.balance:,.2f}")
            elif isinstance(bloc.state, ProfileErrorState):
                print(f"{RED}✘ Error Code {bloc.state.code}: {bloc.state.message}{RESET}")

        elif choice == "3":
            remote_ds.simulate_network_fail = not remote_ds.simulate_network_fail
            status_text = f"{RED}ACTIVE (Network Fail){RESET}" if remote_ds.simulate_network_fail else f"{GREEN}INACTIVE (Normal 200 OK){RESET}"
            print(f"\nStatus Gangguan Jaringan: {status_text}")

        elif choice == "4":
            print(f"\n{YELLOW}--- State Transition Log in Bloc ---{RESET}")
            for idx, st in enumerate(bloc.state_history, start=1):
                extra = ""
                if isinstance(st, ProfileLoadedState):
                    extra = f" (User: {st.user.name}, Source: {st.source})"
                elif isinstance(st, ProfileErrorState):
                    extra = f" (Error: {st.message})"
                print(f"  Step {idx}: {BOLD}{st.name}{RESET}{extra}")

        elif choice == "5":
            QualityAssuranceRunner.run_tests()

        elif choice == "6":
            local_ds.clear()
            print(f"{YELLOW}Local cache telah dikosongkan.{RESET}")

        elif choice == "0":
            print(f"\n{GREEN}Selesai. Clean Architecture & QA simulation terminated cleanly.{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid. Silakan coba lagi.{RESET}")

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print(f"\n{YELLOW}Simulasi dihentikan pengguna.{RESET}")
        sys.exit(0)

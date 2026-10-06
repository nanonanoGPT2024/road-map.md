#!/usr/bin/env python3
"""
Simulasi Teknis Interaktif: Arsitektur Android Modern (UDF, ViewModel, Repository, StateFlow)
BAB-03: Arsitektur Android Modern
"""

import sys
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Generic, List, Optional, TypeVar


# --- ANSI Colors for Terminal UI ---
class Color:
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


T = TypeVar("T")


# --- State Holder: StateFlow Simulation ---
class StateFlow(Generic[T]):
    """Simulasi StateFlow di Kotlin Coroutines: Hot stream dengan nilai terkini."""

    def __init__(self, initial_value: T):
        self._value: T = initial_value
        self._subscribers: List[Callable[[T], None]] = []

    @property
    def value(self) -> T:
        return self._value

    def emit(self, new_value: T) -> None:
        if self._value != new_value:
            self._value = new_value
            for subscriber in self._subscribers:
                subscriber(new_value)

    def collect(self, collector: Callable[[T], None]) -> None:
        self._subscribers.append(collector)
        collector(self._value)


# --- Data Layer Entities & Models ---
@dataclass(frozen=True)
class UserEntity:
    id: int
    name: str
    tier: str
    synced_at: float


class DataSourceStatus(Enum):
    ONLINE = auto()
    OFFLINE = auto()
    ERROR = auto()


# Local DataSource (Room DB Mock)
class LocalUserDataSource:
    def __init__(self) -> None:
        self._db: dict[int, UserEntity] = {
            1: UserEntity(id=1, name="Budi Santoso (Cached)", tier="Standard", synced_at=time.time() - 3600)
        }

    def get_user(self, user_id: int) -> Optional[UserEntity]:
        return self._db.get(user_id)

    def save_user(self, user: UserEntity) -> None:
        self._db[user.id] = user


# Remote DataSource (Retrofit Network Mock)
class RemoteUserDataSource:
    def __init__(self) -> None:
        self.network_status = DataSourceStatus.ONLINE

    def fetch_user_api(self, user_id: int) -> UserEntity:
        if self.network_status == DataSourceStatus.OFFLINE:
            raise ConnectionError("No network connection (simulated)")
        if self.network_status == DataSourceStatus.ERROR:
            raise RuntimeError("HTTP 500: Internal Server Error")
        return UserEntity(
            id=user_id,
            name="Budi Santoso (Live API)",
            tier="Android Architect",
            synced_at=time.time(),
        )


# Repository Pattern: Single Source of Truth
class UserRepository:
    def __init__(self, local_ds: LocalUserDataSource, remote_ds: RemoteUserDataSource) -> None:
        self.local = local_ds
        self.remote = remote_ds

    def get_user_stream(self, user_id: int, force_refresh: bool = False) -> tuple[Optional[UserEntity], str]:
        """Offline-first strategy: Return cache first, refresh from remote if requested."""
        cached = self.local.get_user(user_id)
        if not force_refresh and cached:
            return cached, "LOCAL_CACHE"

        try:
            remote_data = self.remote.fetch_user_api(user_id)
            self.local.save_user(remote_data)
            return remote_data, "REMOTE_NETWORK"
        except Exception as e:
            if cached:
                return cached, f"CACHE_FALLBACK (Error: {str(e)})"
            raise e


# --- Domain Layer: Use Case ---
class GetUserProfileUseCase:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def execute(self, user_id: int, refresh: bool) -> tuple[UserEntity, str]:
        data, source = self.repository.get_user_stream(user_id, force_refresh=refresh)
        if not data:
            raise ValueError(f"User with ID {user_id} not found.")
        return data, source


# --- UI Layer: UI State & UI Events ---
class UiStatus(Enum):
    IDLE = auto()
    LOADING = auto()
    SUCCESS = auto()
    ERROR = auto()


@dataclass(frozen=True)
class ProfileUiState:
    status: UiStatus = UiStatus.IDLE
    user: Optional[UserEntity] = None
    error_message: Optional[str] = None
    data_source: str = "NONE"


# UI Events (Intent / User Action)
class ProfileUiEvent:
    class RefreshRequested:
        def __init__(self, user_id: int = 1):
            self.user_id = user_id

    class LoadCacheRequested:
        def __init__(self, user_id: int = 1):
            self.user_id = user_id

    class ToggleNetworkMode:
        def __init__(self, status: DataSourceStatus):
            self.status = status


# ViewModel: State Holder
class ProfileViewModel:
    def __init__(self, use_case: GetUserProfileUseCase, remote_ds: RemoteUserDataSource) -> None:
        self.use_case = use_case
        self.remote_ds = remote_ds
        self._ui_state: StateFlow[ProfileUiState] = StateFlow(ProfileUiState())

    @property
    def ui_state(self) -> StateFlow[ProfileUiState]:
        return self._ui_state

    def on_event(self, event: object) -> None:
        """Unidirectional Data Flow: UI Event -> ViewModel Logic -> New UI State"""
        if isinstance(event, ProfileUiEvent.LoadCacheRequested):
            self._load_profile(event.user_id, refresh=False)
        elif isinstance(event, ProfileUiEvent.RefreshRequested):
            self._load_profile(event.user_id, refresh=True)
        elif isinstance(event, ProfileUiEvent.ToggleNetworkMode):
            self.remote_ds.network_status = event.status

    def _load_profile(self, user_id: int, refresh: bool) -> None:
        current = self._ui_state.value
        self._ui_state.emit(ProfileUiState(status=UiStatus.LOADING, user=current.user, data_source=current.data_source))
        try:
            user, source = self.use_case.execute(user_id, refresh=refresh)
            self._ui_state.emit(ProfileUiState(status=UiStatus.SUCCESS, user=user, data_source=source))
        except Exception as err:
            self._ui_state.emit(ProfileUiState(status=UiStatus.ERROR, error_message=str(err), user=current.user))


# --- Terminal UI Renderer ---
class TerminalUiRenderer:
    def __init__(self, view_model: ProfileViewModel) -> None:
        self.vm = view_model
        self.history: List[str] = []
        self.vm.ui_state.collect(self.render_state_change)

    def render_state_change(self, state: ProfileUiState) -> None:
        timestamp = time.strftime("%H:%M:%S")
        status_color = {
            UiStatus.IDLE: Color.WHITE,
            UiStatus.LOADING: Color.YELLOW,
            UiStatus.SUCCESS: Color.GREEN,
            UiStatus.ERROR: Color.RED,
        }.get(state.status, Color.WHITE)

        log = f"[{timestamp}] State: {status_color}{state.status.name}{Color.RESET} | Source: {Color.CYAN}{state.data_source}{Color.RESET}"
        if state.user:
            log += f" | User: {state.user.name} ({state.user.tier})"
        if state.error_message:
            log += f" | Error: {Color.RED}{state.error_message}{Color.RESET}"
        self.history.append(log)

    def print_dashboard(self) -> None:
        print("\n" + "=" * 70)
        print(f"{Color.BOLD}{Color.CYAN}  SIMULASI ARSITEKTUR ANDROID MODERN (MAD - UDF PIPELINE){Color.RESET}")
        print("=" * 70)
        state = self.vm.ui_state.value
        print(f"Current UI State : {Color.BOLD}{state.status.name}{Color.RESET}")
        print(f"Active Source    : {Color.MAGENTA}{state.data_source}{Color.RESET}")
        if state.user:
            print(f"Loaded User      : {Color.GREEN}{state.user.name}{Color.RESET} (ID: {state.user.id}, Tier: {state.user.tier})")
        else:
            print(f"Loaded User      : {Color.DIM}None{Color.RESET}")

        network_badge = {
            DataSourceStatus.ONLINE: f"{Color.GREEN}[ONLINE]{Color.RESET}",
            DataSourceStatus.OFFLINE: f"{Color.YELLOW}[OFFLINE]{Color.RESET}",
            DataSourceStatus.ERROR: f"{Color.RED}[HTTP 500]{Color.RESET}",
        }.get(self.vm.remote_ds.network_status, "UNKNOWN")
        print(f"Network Status   : {network_badge}")
        print("-" * 70)
        print(f"{Color.BOLD}StateFlow Emission Log (Last 4 events):{Color.RESET}")
        for entry in self.history[-4:]:
            print(f"  * {entry}")
        print("=" * 70)


def run_automated_test_suite(vm: ProfileViewModel) -> bool:
    print(f"\n{Color.YELLOW}[TEST SUITE] Menjalankan verifikasi otomatis UDF & Repository...{Color.RESET}")
    # Test 1: Load cache
    vm.on_event(ProfileUiEvent.LoadCacheRequested(1))
    assert vm.ui_state.value.status == UiStatus.SUCCESS, "Test 1 Gagal: Status harus SUCCESS"
    assert "LOCAL_CACHE" in vm.ui_state.value.data_source, "Test 1 Gagal: Sumber harus cache"

    # Test 2: Refresh online
    vm.on_event(ProfileUiEvent.ToggleNetworkMode(DataSourceStatus.ONLINE))
    vm.on_event(ProfileUiEvent.RefreshRequested(1))
    assert vm.ui_state.value.status == UiStatus.SUCCESS, "Test 2 Gagal: Status harus SUCCESS"
    assert vm.ui_state.value.data_source == "REMOTE_NETWORK", "Test 2 Gagal: Sumber harus remote"

    # Test 3: Offline fallback
    vm.on_event(ProfileUiEvent.ToggleNetworkMode(DataSourceStatus.OFFLINE))
    vm.on_event(ProfileUiEvent.RefreshRequested(1))
    assert vm.ui_state.value.status == UiStatus.SUCCESS, "Test 3 Gagal: Harus fallback ke cache"
    assert "CACHE_FALLBACK" in vm.ui_state.value.data_source, "Test 3 Gagal: Label harus cache fallback"

    print(f"{Color.GREEN}[PASS] Semua 3 test verifikasi arsitektur lolos 100%!{Color.RESET}\n")
    return True


def main() -> None:
    # Dependency Injection Container setup
    local_ds = LocalUserDataSource()
    remote_ds = RemoteUserDataSource()
    repo = UserRepository(local_ds=local_ds, remote_ds=remote_ds)
    use_case = GetUserProfileUseCase(repository=repo)
    vm = ProfileViewModel(use_case=use_case, remote_ds=remote_ds)
    ui = TerminalUiRenderer(view_model=vm)

    # Initial view load
    vm.on_event(ProfileUiEvent.LoadCacheRequested(1))

    # Interactive Loop
    while True:
        ui.print_dashboard()
        print(f"{Color.BOLD}Menu Simulasi:{Color.RESET}")
        print("  [1] UI Event: Fetch User Profile dari Local Cache")
        print("  [2] UI Event: Force Refresh dari Remote API (Network)")
        print("  [3] Toggle Network -> ONLINE")
        print("  [4] Toggle Network -> OFFLINE (Simulasi Mode Pesawat/No Signal)")
        print("  [5] Toggle Network -> HTTP 500 SERVER ERROR")
        print("  [6] Jalankan Automated UDF & Architecture Test Suite")
        print("  [0] Keluar")

        try:
            choice = input(f"\n{Color.CYAN}Pilih opsi [0-6]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nKeluar...")
            break

        if choice == "1":
            vm.on_event(ProfileUiEvent.LoadCacheRequested(1))
        elif choice == "2":
            vm.on_event(ProfileUiEvent.RefreshRequested(1))
        elif choice == "3":
            vm.on_event(ProfileUiEvent.ToggleNetworkMode(DataSourceStatus.ONLINE))
            print(f"{Color.GREEN}Mode jaringan diset: ONLINE{Color.RESET}")
        elif choice == "4":
            vm.on_event(ProfileUiEvent.ToggleNetworkMode(DataSourceStatus.OFFLINE))
            print(f"{Color.YELLOW}Mode jaringan diset: OFFLINE{Color.RESET}")
        elif choice == "5":
            vm.on_event(ProfileUiEvent.ToggleNetworkMode(DataSourceStatus.ERROR))
            print(f"{Color.RED}Mode jaringan diset: HTTP 500 ERROR{Color.RESET}")
        elif choice == "6":
            run_automated_test_suite(vm)
        elif choice == "0":
            print(f"{Color.GREEN}Selesai. Selamat belajar Arsitektur Android Modern!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid.{Color.RESET}")
        time.sleep(0.5)


if __name__ == "__main__":
    main()

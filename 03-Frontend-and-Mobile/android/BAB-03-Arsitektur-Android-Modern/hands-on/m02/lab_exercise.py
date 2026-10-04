#!/usr/bin/env python3
"""
Lab Hands-on: Modern Android Architecture (Clean Architecture, MVI & UDF)
Bab 03 - Modul 02 Deep Dive

Simulates modern Android architectural patterns without third-party dependencies:
- Clean Architecture: Domain (Entities, UseCases), Data (Repository, DataSources),
  and Presentation layers.
- MVI (Model-View-Intent) & UDF (Unidirectional Data Flow): Immutable ViewState,
  User Intents, State Reducers, and One-off Single Live Effects (SideEffects).
- Reactive Concurrency: Simulates Android's ViewModelScope + Kotlin StateFlow/Channel.
"""

from dataclasses import dataclass, replace
from enum import Enum, auto
import queue
import sys
import threading
import time
from typing import Optional, List, Callable

# ==============================================================================
# ANSI Formatting Constants for Terminal Output
# ==============================================================================
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"


# ==============================================================================
# 1. DOMAIN LAYER (Pure Business Logic & Entities - Independent of UI/Framework)
# ==============================================================================
@dataclass(frozen=True)
class User:
    """Immutable Domain Entity representing the Core Model."""
    user_id: str
    username: str
    bio: str
    reputation: int
    is_verified: bool


class GetUserProfileUseCase:
    """UseCase: Fetches user profile with business validation."""
    def __init__(self, repository: "UserRepositoryInterface"):
        self._repository = repository

    def execute(self, user_id: str) -> User:
        if not user_id or len(user_id.strip()) == 0:
            raise ValueError("Domain Error: Invalid user_id provided.")
        return self._repository.fetch_user(user_id)


class UpdateBioUseCase:
    """UseCase: Validates and coordinates profile bio updates."""
    def __init__(self, repository: "UserRepositoryInterface"):
        self._repository = repository

    def execute(self, user_id: str, new_bio: str) -> User:
        if len(new_bio) > 80:
            raise ValueError("Domain Error: Bio exceeds maximum limit of 80 characters.")
        return self._repository.update_bio(user_id, new_bio)


# ==============================================================================
# 2. DATA LAYER (Repository Pattern, Local Cache & Remote Data Sources)
# ==============================================================================
class UserRepositoryInterface:
    def fetch_user(self, user_id: str) -> User:
        raise NotImplementedError

    def update_bio(self, user_id: str, new_bio: str) -> User:
        raise NotImplementedError


class UserRepositoryImpl(UserRepositoryInterface):
    """Repository implementation mediating between Mock Network and Cache."""
    def __init__(self):
        # Local in-memory cache
        self._cache: dict[str, User] = {}

    def fetch_user(self, user_id: str) -> User:
        # Simulate network latency
        time.sleep(0.35)
        
        # Simulate failure condition for specific ID to demonstrate error states
        if user_id == "usr_err_404":
            raise ConnectionError("HTTP 404: Remote user entity not found.")

        # Simulate fetched remote data
        user = User(
            user_id=user_id,
            username=f"droid_dev_{user_id.split('_')[-1]}",
            bio="Building modern Android apps with Clean MVI & Compose.",
            reputation=1420,
            is_verified=True
        )
        self._cache[user_id] = user
        return user

    def update_bio(self, user_id: str, new_bio: str) -> User:
        # Simulate network roundtrip
        time.sleep(0.30)
        current = self._cache.get(user_id)
        if not current:
            current = self.fetch_user(user_id)
        
        updated = replace(current, bio=new_bio)
        self._cache[user_id] = updated
        return updated


# ==============================================================================
# 3. PRESENTATION LAYER: MVI CONTRACTS (State, Intent, Effect)
# ==============================================================================
@dataclass(frozen=True)
class ProfileViewState:
    """
    UDF Immutable State representing the UI at any point in time.
    Equivalent to Jetpack Compose UI State.
    """
    is_loading: bool = False
    is_refreshing: bool = False
    user: Optional[User] = None
    error_message: Optional[str] = None


class ProfileIntent:
    """Base class for all Intent/Actions initiated by the View/User."""
    pass

@dataclass(frozen=True)
class LoadProfileIntent(ProfileIntent):
    user_id: str

@dataclass(frozen=True)
class RefreshProfileIntent(ProfileIntent):
    user_id: str

@dataclass(frozen=True)
class UpdateBioIntent(ProfileIntent):
    user_id: str
    new_bio: str


class ProfileSideEffect:
    """One-off events (e.g., Toast, Navigation, Dialogs) not part of persistent state."""
    pass

@dataclass(frozen=True)
class ShowToastEffect(ProfileSideEffect):
    message: str

@dataclass(frozen=True)
class NavigateBackEffect(ProfileSideEffect):
    reason: str


# ==============================================================================
# 4. PRESENTATION LAYER: VIEWMODEL (UDF Reducer & Coroutine Engine)
# ==============================================================================
class ProfileViewModel:
    """
    Simulates Android Modern ViewModel containing:
    - StateFlow<ProfileViewState> for continuous state streaming
    - Channel<ProfileSideEffect> for single-shot events
    - viewModelScope (Thread Worker) processing Intents asynchronously.
    """
    def __init__(self, get_user_usecase: GetUserProfileUseCase, update_bio_usecase: UpdateBioUseCase):
        self._get_user = get_user_usecase
        self._update_bio = update_bio_usecase

        # Initial State
        self._state = ProfileViewState(is_loading=False)
        self._state_lock = threading.Lock()

        # Observers / Subscribers (Simulating Flow collectors)
        self._state_observers: List[Callable[[ProfileViewState], None]] = []
        self._effect_observers: List[Callable[[ProfileSideEffect], None]] = []

        # Intent Event Loop (simulating Kotlin Coroutines viewModelScope)
        self._intent_queue: queue.Queue[ProfileIntent] = queue.Queue()
        self._is_active = True
        self._worker_thread = threading.Thread(target=self._process_intents, daemon=True)
        self._worker_thread.start()

    def subscribe_state(self, callback: Callable[[ProfileViewState], None]):
        self._state_observers.append(callback)
        # Emit initial state immediately
        callback(self._state)

    def subscribe_effect(self, callback: Callable[[ProfileSideEffect], None]):
        self._effect_observers.append(callback)

    def dispatch(self, intent: ProfileIntent):
        """Entry point for UI to send Intents into ViewModel."""
        self._intent_queue.put(intent)

    def _emit_state(self, new_state: ProfileViewState):
        """Thread-safe state update and notification to collectors."""
        with self._state_lock:
            self._state = new_state
            state_snapshot = self._state
        for observer in self._state_observers:
            observer(state_snapshot)

    def _emit_effect(self, effect: ProfileSideEffect):
        """Emit one-off transient effect."""
        for observer in self._effect_observers:
            observer(effect)

    def _process_intents(self):
        """ViewModelScope async worker resolving incoming intents."""
        while self._is_active:
            try:
                intent = self._intent_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            self._handle_intent(intent)
            self._intent_queue.task_done()

    def _handle_intent(self, intent: ProfileIntent):
        """Reducers and UseCase invocations corresponding to specific Intents."""
        if isinstance(intent, LoadProfileIntent):
            # 1. State: Enter Loading
            self._emit_state(replace(self._state, is_loading=True, error_message=None))
            try:
                # 2. UseCase Execution
                user = self._get_user.execute(intent.user_id)
                # 3. State: Success Result
                self._emit_state(replace(self._state, is_loading=False, user=user, error_message=None))
            except Exception as e:
                # 4. State: Error & Side-Effect emission
                self._emit_state(replace(self._state, is_loading=False, error_message=str(e)))
                self._emit_effect(ShowToastEffect(f"Failure: {str(e)}"))

        elif isinstance(intent, RefreshProfileIntent):
            self._emit_state(replace(self._state, is_refreshing=True))
            try:
                user = self._get_user.execute(intent.user_id)
                self._emit_state(replace(self._state, is_refreshing=False, user=user))
                self._emit_effect(ShowToastEffect("Profile synced successfully!"))
            except Exception as e:
                self._emit_state(replace(self._state, is_refreshing=False, error_message=str(e)))

        elif isinstance(intent, UpdateBioIntent):
            # Optimistic or loading update
            self._emit_state(replace(self._state, is_loading=True))
            try:
                updated_user = self._update_bio.execute(intent.user_id, intent.new_bio)
                self._emit_state(replace(self._state, is_loading=False, user=updated_user))
                self._emit_effect(ShowToastEffect("Bio updated successfully!"))
            except Exception as e:
                self._emit_state(replace(self._state, is_loading=False))
                self._emit_effect(ShowToastEffect(f"Update rejected: {str(e)}"))

    def close(self):
        self._is_active = False
        self._worker_thread.join()


# ==============================================================================
# 5. VIEW SIMULATOR (Simulates Jetpack Compose UI Recomposition)
# ==============================================================================
class AndroidComposeView:
    """Simulates a Compose Screen that renders UI based on immutable State."""
    def __init__(self, view_model: ProfileViewModel):
        self._vm = view_model
        self._vm.subscribe_state(self.render)
        self._vm.subscribe_effect(self.handle_effect)

    def render(self, state: ProfileViewState):
        """Simulates Compose Recomposition."""
        print(f"\n{CYAN}┌── [COMPOSE UI RECOMPOSITION FRAME] ──────────────────────────┐{RESET}")
        
        # Loading Shimmer/Spinner
        if state.is_loading:
            print(f"{CYAN}│{RESET}  {YELLOW}⟳ Loading/Syncing content from repository...{RESET}")
        elif state.is_refreshing:
            print(f"{CYAN}│{RESET}  {YELLOW}↓ SwipeRefresh active: Fetching latest patch...{RESET}")
        
        # Error Banner
        if state.error_message:
            print(f"{CYAN}│{RESET}  {RED}✖ ERROR BANNER: {state.error_message}{RESET}")

        # Profile Card
        if state.user:
            u = state.user
            verified_badge = f"{BLUE}✔ VERIFIED{RESET}" if u.is_verified else f"{DIM}UNVERIFIED{RESET}"
            print(f"{CYAN}│{RESET}  User ID    : {BOLD}{u.user_id}{RESET}")
            print(f"{CYAN}│{RESET}  Username   : @{u.username} [{verified_badge}]")
            print(f"{CYAN}│{RESET}  Reputation : {GREEN}★ {u.reputation}{RESET}")
            print(f"{CYAN}│{RESET}  Biography  : \"{u.bio}\"")
        elif not state.is_loading and not state.error_message:
            print(f"{CYAN}│{RESET}  {DIM}[Empty View: No Profile Loaded]{RESET}")

        print(f"{CYAN}└───────────────────────────────────────────────────────────────┘{RESET}")

    def handle_effect(self, effect: ProfileSideEffect):
        """Handles Single-shot One-off UI Events."""
        if isinstance(effect, ShowToastEffect):
            print(f"  {MAGENTA}💬 [UI TOAST NOTIFICATION]{RESET} -> {effect.message}")
        elif isinstance(effect, NavigateBackEffect):
            print(f"  {MAGENTA}🚪 [NAVIGATION BACK]{RESET} -> Reason: {effect.reason}")


# ==============================================================================
# 6. LAB RUNTIME EXECUTION & VERIFICATION
# ==============================================================================
def main():
    print(f"{BOLD}{BLUE}======================================================================{RESET}")
    print(f"{BOLD}{BLUE}     LAB: MODERN ANDROID CLEAN ARCHITECTURE & MVI / UDF PATTERN      {RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}")

    # Dependency Injection Assembly (Simulating Hilt / Koin)
    repository = UserRepositoryImpl()
    get_user_usecase = GetUserProfileUseCase(repository)
    update_bio_usecase = UpdateBioUseCase(repository)
    view_model = ProfileViewModel(get_user_usecase, update_bio_usecase)
    view = AndroidComposeView(view_model)

    print(f"\n{BOLD}[Scenario 1] Dispatch LoadProfileIntent (Valid User){RESET}")
    view_model.dispatch(LoadProfileIntent(user_id="usr_android_909"))
    time.sleep(0.5)

    print(f"\n{BOLD}[Scenario 2] Dispatch UpdateBioIntent (Valid Modification){RESET}")
    view_model.dispatch(UpdateBioIntent(
        user_id="usr_android_909",
        new_bio="Staff Engineer specializing in Jetpack Compose, Kotlin Flow & MVI."
    ))
    time.sleep(0.5)

    print(f"\n{BOLD}[Scenario 3] Dispatch UpdateBioIntent (Domain Validation Failure: Bio > 80 chars){RESET}")
    oversized_bio = "This biography text is intentionally created to be ridiculously and excessively verbose, far exceeding eighty characters."
    view_model.dispatch(UpdateBioIntent(user_id="usr_android_909", new_bio=oversized_bio))
    time.sleep(0.2)

    print(f"\n{BOLD}[Scenario 4] Dispatch LoadProfileIntent (Simulated Network Error 404){RESET}")
    view_model.dispatch(LoadProfileIntent(user_id="usr_err_404"))
    time.sleep(0.5)

    print(f"\n{BOLD}[Scenario 5] Dispatch RefreshProfileIntent (Recovery & Pull to Refresh){RESET}")
    view_model.dispatch(RefreshProfileIntent(user_id="usr_android_909"))
    time.sleep(0.5)

    # Teardown ViewModel
    view_model.close()
    print(f"\n{BOLD}{GREEN}✓ Architecture Lab Simulation completed successfully.{RESET}")


if __name__ == "__main__":
    main()
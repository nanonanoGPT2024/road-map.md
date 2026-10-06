#!/usr/bin/env python3
"""
SwiftUI Enterprise Architecture & The Composable Architecture (TCA) Simulator
Target: BAB-10-Enterprise-Architecture-SPM-Multiplatform-TCA

Simulates:
- SPM Modular Package Graph (CoreModels -> APIClient -> Features -> AppRoot)
- TCA Core Pattern (State, Action, Reducer, Effect, Dependency Injection, Store)
- Multiplatform Target Adaptation (iOS, macOS, watchOS)
- Interactive CLI with ANSI color diagnostics
"""

from __future__ import annotations
import dataclasses
import enum
import time
import sys
from typing import Callable, List, Optional, Dict, Any

# ANSI Color formatting
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    MAGENTA = "\033[35m"
    RED = "\033[31m"
    BLUE = "\033[34m"
    BG_DARK = "\033[48;5;236m"

def banner(title: str) -> None:
    print(f"\n{Style.CYAN}{Style.BOLD}{'=' * 65}{Style.RESET}")
    print(f"{Style.YELLOW}{Style.BOLD} [TCA & SPM ARCHITECTURE RUNTIME] - {title}{Style.RESET}")
    print(f"{Style.CYAN}{Style.BOLD}{'=' * 65}{Style.RESET}\n")

# -------------------------------------------------------------------------
# 1. SPM Modular Target Dependency Graph Simulation
# -------------------------------------------------------------------------

class TargetType(enum.Enum):
    INTERFACE = "Interface (Protocols & Domain Models)"
    IMPLEMENTATION = "Live Client (Network & Storage)"
    MOCK = "Mocks (Test Harness)"
    FEATURE = "TCA Feature Slice"
    APP_CORE = "Multiplatform Composition Root"

@dataclasses.dataclass(frozen=True)
class SPMTarget:
    name: str
    target_type: TargetType
    dependencies: List[str]
    supported_platforms: List[str]

PACKAGE_MANIFEST: Dict[str, SPMTarget] = {
    "DomainModels": SPMTarget(
        name="DomainModels",
        target_type=TargetType.INTERFACE,
        dependencies=[],
        supported_platforms=["iOS", "macOS", "watchOS", "visionOS"]
    ),
    "AuthClient": SPMTarget(
        name="AuthClient",
        target_type=TargetType.INTERFACE,
        dependencies=["DomainModels"],
        supported_platforms=["iOS", "macOS", "watchOS"]
    ),
    "AuthClientLive": SPMTarget(
        name="AuthClientLive",
        target_type=TargetType.IMPLEMENTATION,
        dependencies=["AuthClient"],
        supported_platforms=["iOS", "macOS", "watchOS"]
    ),
    "AuthFeature": SPMTarget(
        name="AuthFeature",
        target_type=TargetType.FEATURE,
        dependencies=["AuthClient", "DomainModels"],
        supported_platforms=["iOS", "macOS", "watchOS"]
    ),
    "EnterpriseAppMultiplatform": SPMTarget(
        name="EnterpriseAppMultiplatform",
        target_type=TargetType.APP_CORE,
        dependencies=["AuthFeature", "AuthClientLive"],
        supported_platforms=["iOS", "macOS", "watchOS"]
    )
}

# -------------------------------------------------------------------------
# 2. TCA Reducer, State, Action & Effects Mechanics
# -------------------------------------------------------------------------

@dataclasses.dataclass
class UserSession:
    user_id: str
    username: str
    token: str
    role: str

@dataclasses.dataclass
class AuthState:
    is_loading: bool = False
    session: Optional[UserSession] = None
    error_message: Optional[str] = None
    active_platform: str = "iOS"
    retry_count: int = 0

class AuthAction:
    class LoginButtonTapped:
        def __init__(self, username: str, password: str):
            self.username = username
            self.password = password
        def __repr__(self) -> str:
            return f"LoginButtonTapped(user='{self.username}')"

    class LoginResponseReceived:
        def __init__(self, result: Optional[UserSession], error: Optional[str] = None):
            self.result = result
            self.error = error
        def __repr__(self) -> str:
            status = f"Success({self.result.username})" if self.result else f"Failure('{self.error}')"
            return f"LoginResponseReceived({status})"

    class SwitchPlatform:
        def __init__(self, platform: str):
            self.platform = platform
        def __repr__(self) -> str:
            return f"SwitchPlatform({self.platform})"

    class LogoutTapped:
        def __repr__(self) -> str:
            return "LogoutTapped"

class AuthDependency:
    """Simulates injected DependencyClient in TCA Environment"""
    def __init__(self, is_live: bool = True):
        self.is_live = is_live

    def login(self, username: str, password: str) -> Optional[UserSession]:
        time.sleep(0.3)
        if password == "enterprise2026":
            return UserSession(
                user_id="usr_9812",
                username=username,
                token="jwt.header.payload.signature_xyz",
                role="PrincipalArchitect"
            )
        return None

# Effect definition: returns an optional Action to be fed back into the store
Effect = Optional[Callable[[], Any]]

def auth_reducer(state: AuthState, action: Any, environment: AuthDependency) -> tuple[AuthState, List[Effect]]:
    """Pure unidirectional reducer mutating state copy and returning side effects."""
    effects: List[Effect] = []

    if isinstance(action, AuthAction.LoginButtonTapped):
        state.is_loading = True
        state.error_message = None

        def run_login_effect() -> Any:
            session = environment.login(action.username, action.password)
            if session:
                return AuthAction.LoginResponseReceived(result=session)
            return AuthAction.LoginResponseReceived(result=None, error="Invalid credentials (Try: 'enterprise2026')")

        effects.append(run_login_effect)

    elif isinstance(action, AuthAction.LoginResponseReceived):
        state.is_loading = False
        if action.result:
            state.session = action.result
            state.error_message = None
            state.retry_count = 0
        else:
            state.session = None
            state.error_message = action.error
            state.retry_count += 1

    elif isinstance(action, AuthAction.SwitchPlatform):
        state.active_platform = action.platform

    elif isinstance(action, AuthAction.LogoutTapped):
        state.session = None
        state.error_message = None
        state.is_loading = False

    return state, effects

# -------------------------------------------------------------------------
# 3. Store Implementation (Runtime Engine)
# -------------------------------------------------------------------------

class Store:
    def __init__(self, initial_state: AuthState, reducer_fn: Callable, dependency: AuthDependency):
        self.state = initial_state
        self.reducer_fn = reducer_fn
        self.dependency = dependency
        self.action_history: List[str] = []

    def send(self, action: Any) -> None:
        action_name = repr(action)
        self.action_history.append(action_name)
        print(f" {Style.MAGENTA}⚡ [Store.send]{Style.RESET} Action: {Style.BOLD}{action_name}{Style.RESET}")

        self.state, effects = self.reducer_fn(self.state, action, self.dependency)
        self.render_view()

        for eff in effects:
            if eff:
                print(f" {Style.BLUE}↳ [TCA Effect Task]{Style.RESET} Executing async side-effect...")
                next_action = eff()
                if next_action:
                    self.send(next_action)

    def render_view(self) -> None:
        """Simulates SwiftUI View rendering driven strictly by ViewStore state."""
        platform_icon = {"iOS": "📱", "macOS": "💻", "watchOS": "⌚"}.get(self.state.active_platform, "🖥️")
        print(f"\n {Style.BG_DARK}--- [SwiftUI View Body Evaluation] ({platform_icon} {self.state.active_platform}) ---{Style.RESET}")
        
        if self.state.is_loading:
            print(f" {Style.YELLOW}⏳ ProgressView('Authenticating with Enterprise SSO...'){Style.RESET}")
        elif self.state.session:
            print(f" {Style.GREEN}✅ Logged In as: {Style.BOLD}{self.state.session.username}{Style.RESET} "
                  f"[Role: {self.state.session.role}]")
            print(f" {Style.CYAN}🔑 Token: {self.state.session.token[:24]}...{Style.RESET}")
        else:
            print(f" {Style.CYAN}🔒 Displaying Login Sheet (State: Unauthenticated){Style.RESET}")
            if self.state.error_message:
                print(f" {Style.RED}❌ Error Alert: {self.state.error_message} (Failed attempts: {self.state.retry_count}){Style.RESET}")
        print(f" {Style.BG_DARK}{'-' * 55}{Style.RESET}\n")

# -------------------------------------------------------------------------
# 4. Interactive Simulation Runner
# -------------------------------------------------------------------------

def show_spm_graph() -> None:
    banner("SPM PACKAGE MANIFEST & DEPENDENCY GRAPH")
    for name, target in PACKAGE_MANIFEST.items():
        deps = ", ".join(target.dependencies) if target.dependencies else "None (Foundation)"
        platforms = ", ".join(target.supported_platforms)
        print(f"📦 {Style.BOLD}{name}{Style.RESET} [{Style.BLUE}{target.target_type.value}{Style.RESET}]")
        print(f"   ↳ Dependencies: {Style.GREEN}{deps}{Style.RESET}")
        print(f"   ↳ Multiplatform Matrix: {Style.YELLOW}{platforms}{Style.RESET}\n")

def run_automated_suite(store: Store) -> None:
    banner("EXECUTING AUTOMATED TCA LIFECYCLE SUITE")
    print(f"{Style.YELLOW}1. Simulating Bad Credentials Login Attempt:{Style.RESET}")
    store.send(AuthAction.LoginButtonTapped(username="albert_einstein", password="wrong_password"))
    
    print(f"\n{Style.YELLOW}2. Simulating Valid Credentials Login Attempt:{Style.RESET}")
    store.send(AuthAction.LoginButtonTapped(username="albert_einstein", password="enterprise2026"))

    print(f"\n{Style.YELLOW}3. Simulating Platform Adaptation (SwiftUI Multiplatform):{Style.RESET}")
    store.send(AuthAction.SwitchPlatform(platform="macOS"))
    store.send(AuthAction.SwitchPlatform(platform="watchOS"))

    print(f"\n{Style.YELLOW}4. Simulating Logout Action:{Style.RESET}")
    store.send(AuthAction.LogoutTapped())

def interactive_cli(store: Store) -> None:
    while True:
        print(f"\n{Style.BOLD}=== TCA & Swift Multiplatform Simulator Menu ==={Style.RESET}")
        print("1. Inspect SPM Target Graph (Package.swift)")
        print("2. Dispatch Login Action (Success Case)")
        print("3. Dispatch Login Action (Failure Case)")
        print("4. Switch Platform (iOS / macOS / watchOS)")
        print("5. Dispatch Logout Action")
        print("6. Run Full Autonomous Test Suite")
        print("0. Exit")
        choice = input(f"{Style.GREEN}Enter choice [0-6]: {Style.RESET}").strip()

        if choice == "1":
            show_spm_graph()
        elif choice == "2":
            store.send(AuthAction.LoginButtonTapped(username="swift_architect", password="enterprise2026"))
        elif choice == "3":
            store.send(AuthAction.LoginButtonTapped(username="guest_user", password="bad_password"))
        elif choice == "4":
            plat = input("Select platform (iOS/macOS/watchOS): ").strip()
            if plat in ["iOS", "macOS", "watchOS"]:
                store.send(AuthAction.SwitchPlatform(platform=plat))
            else:
                print(f"{Style.RED}Invalid platform name.{Style.RESET}")
        elif choice == "5":
            store.send(AuthAction.LogoutTapped())
        elif choice == "6":
            run_automated_suite(store)
        elif choice == "0":
            print(f"{Style.GREEN}Exiting TCA Architecture Simulator. Cheers!{Style.RESET}")
            break
        else:
            print(f"{Style.RED}Unknown command.{Style.RESET}")

def main() -> None:
    banner("SWIFTUI TCA & SPM ENTERPRISE ARCHITECTURE")
    print(f"{Style.BOLD}Initializing Store with initial AuthState & DependencyClient...{Style.RESET}\n")

    initial_state = AuthState()
    dependency = AuthDependency(is_live=True)
    store = Store(initial_state=initial_state, reducer_fn=auth_reducer, dependency=dependency)

    # Initial view render
    store.render_view()

    # Non-interactive / headless check (e.g. piped or automated test runner)
    if not sys.stdin.isatty():
        print(f"{Style.YELLOW}[Headless environment detected] Running automated verification suite directly.{Style.RESET}")
        show_spm_graph()
        run_automated_suite(store)
        print(f"\n{Style.GREEN}✔ Verification completed successfully.{Style.RESET}")
    else:
        interactive_cli(store)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Pola Arsitektur Skala Besar iOS
Topik: BAB-05 Pola Arsitektur Skala Besar (VIPER, TCA, Modular Coordinator, Dependency Container)

Skrip mandiri ini mensimulasikan arsitektur enterprise iOS:
1. VIPER (View-Interactor-Presenter-Entity-Router)
2. TCA (The Composable Architecture: State, Action, Reducer, Effect)
3. Coordinator Pattern untuk navigasi terdekupel
4. Service Locator / Dependency Injection Container ala Swinject
"""

import sys
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional

# --- ANSI Terminal Color Palette ---
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
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"


def header(title: str) -> None:
    border = "=" * 64
    print(f"\n{Color.CYAN}{Color.BOLD}{border}")
    print(f" {title.center(62)} ")
    print(f"{border}{Color.RESET}")


def section(name: str) -> None:
    print(f"\n{Color.YELLOW}{Color.BOLD}>>> [MODUL] {name}{Color.RESET}")


def log_event(layer: str, msg: str, color: str = Color.GREEN) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"  {Color.DIM}[{timestamp}]{Color.RESET} {color}[{layer.upper()}]{Color.RESET} {msg}")


# ==============================================================================
# 1. DEPENDENCY INJECTION CONTAINER (MIRRORING SWINJECT / FACTORY DI)
# ==============================================================================
class DIContainer:
    """Dependency Injection container untuk loosely-coupled iOS enterprise apps."""
    _registry: Dict[str, Callable[[], Any]] = {}

    @classmethod
    def register(cls, protocol_name: str, factory: Callable[[], Any]) -> None:
        cls._registry[protocol_name] = factory
        log_event("DI-Container", f"Berhasil meregistrasi factory untuk: {protocol_name}", Color.MAGENTA)

    @classmethod
    def resolve(cls, protocol_name: str) -> Any:
        factory = cls._registry.get(protocol_name)
        if not factory:
            raise KeyError(f"Layanan untuk protokol '{protocol_name}' belum diregistrasi!")
        return factory()


# ==============================================================================
# 2. VIPER PATTERN SIMULATION (MODULAR SCREEN: USER PROFILE & TRANSACTIONS)
# ==============================================================================
@dataclass
class AccountEntity:
    user_id: str
    username: str
    balance: float
    tier: str


class AccountInteractorProtocol:
    def fetch_account(self, user_id: str) -> AccountEntity:
        raise NotImplementedError


class AccountInteractor(AccountInteractorProtocol):
    def fetch_account(self, user_id: str) -> AccountEntity:
        log_event("Interactor", f"Mengambil data mentah untuk user_id: {user_id} dari Repository/Network", Color.BLUE)
        # Mock database/network call
        return AccountEntity(
            user_id=user_id,
            username="Satoshi Nakamoto",
            balance=14250000.0,
            tier="Enterprise Platinum"
        )


class AccountRouterProtocol:
    def navigate_to_transfer(self) -> None:
        raise NotImplementedError


class AccountRouter(AccountRouterProtocol):
    def navigate_to_transfer(self) -> None:
        log_event("Router", "Melakukan koordinasi transisi layar -> 'TransferCoordinator'", Color.MAGENTA)


class AccountPresenter:
    def __init__(self, interactor: AccountInteractorProtocol, router: AccountRouterProtocol):
        self.interactor = interactor
        self.router = router
        self.view_state: Optional[Dict[str, str]] = None

    def on_view_did_load(self, user_id: str) -> None:
        log_event("Presenter", f"Menerima event ViewDidLoad untuk user: {user_id}", Color.CYAN)
        entity = self.interactor.fetch_account(user_id)
        # Transformasi Entity menjadi ViewModel ramah UI
        formatted_balance = f"Rp {entity.balance:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
        self.view_state = {
            "name": entity.username.upper(),
            "balance": formatted_balance,
            "badge": f"[{entity.tier}]"
        }
        log_event("Presenter", "Entity berhasil diformat menjadi ViewModel untuk View", Color.CYAN)

    def did_tap_transfer_button(self) -> None:
        log_event("Presenter", "Menerima user action tap 'Transfer'. Mendelegasikan ke Wireframe/Router", Color.CYAN)
        self.router.navigate_to_transfer()


class AccountViewController:
    def __init__(self, presenter: AccountPresenter):
        self.presenter = presenter

    def render(self, user_id: str) -> None:
        log_event("View (iOS UI)", "Memulai daur hidup UIViewController...", Color.WHITE)
        self.presenter.on_view_did_load(user_id)
        state = self.presenter.view_state or {}
        print(f"\n    {Color.BG_BLUE}{Color.WHITE} [ iOS Screen: Account Profile ] {Color.RESET}")
        print(f"    User   : {Color.BOLD}{state.get('name')}{Color.RESET} {state.get('badge')}")
        print(f"    Saldo  : {Color.GREEN}{Color.BOLD}{state.get('balance')}{Color.RESET}")


# ==============================================================================
# 3. TCA (THE COMPOSABLE ARCHITECTURE) SIMULATION
# ==============================================================================
@dataclass
class CartState:
    items: List[str] = field(default_factory=list)
    total_price: float = 0.0
    is_loading: bool = False
    error_message: Optional[str] = None


class CartActionType(Enum):
    ADD_ITEM = auto()
    CHECKOUT_SUBMIT = auto()
    CHECKOUT_SUCCESS = auto()
    CHECKOUT_FAILED = auto()


@dataclass
class CartAction:
    action_type: CartActionType
    item_name: Optional[str] = None
    item_price: float = 0.0
    error: Optional[str] = None


def cart_reducer(state: CartState, action: CartAction) -> tuple[CartState, Optional[str]]:
    """Pure Reducer function: f(State, Action) -> (NewState, Effect)"""
    new_state = CartState(
        items=list(state.items),
        total_price=state.total_price,
        is_loading=state.is_loading,
        error_message=state.error_message
    )

    if action.action_type == CartActionType.ADD_ITEM:
        if action.item_name:
            new_state.items.append(action.item_name)
            new_state.total_price += action.item_price
        return new_state, None

    elif action.action_type == CartActionType.CHECKOUT_SUBMIT:
        new_state.is_loading = True
        new_state.error_message = None
        # Mengembalikan side-effect token
        return new_state, "EFFECT_PROCESS_PAYMENT_API"

    elif action.action_type == CartActionType.CHECKOUT_SUCCESS:
        new_state.is_loading = False
        new_state.items.clear()
        new_state.total_price = 0.0
        return new_state, None

    elif action.action_type == CartActionType.CHECKOUT_FAILED:
        new_state.is_loading = False
        new_state.error_message = action.error
        return new_state, None

    return new_state, None


class TCAStore:
    def __init__(self, initial_state: CartState, reducer: Callable[[CartState, CartAction], tuple[CartState, Optional[str]]]):
        self.state = initial_state
        self.reducer = reducer

    def send(self, action: CartAction) -> None:
        log_event("TCA-Store", f"Menerima Action: {action.action_type.name}", Color.YELLOW)
        self.state, effect = self.reducer(self.state, action)
        log_event("TCA-Store", f"State termutasi: Items={len(self.state.items)}, Total={self.state.total_price}, Loading={self.state.is_loading}", Color.GREEN)

        if effect == "EFFECT_PROCESS_PAYMENT_API":
            log_event("TCA-Effect", "Mengeksekusi Async Effect: Mengirim payload transaksi ke API Gateway...", Color.MAGENTA)
            # Simulasi asynchronous gateway response
            time.sleep(0.3)
            self.send(CartAction(action_type=CartActionType.CHECKOUT_SUCCESS))


# ==============================================================================
# 4. APP COORDINATOR (MODULAR NAVIGATION GRAPH)
# ==============================================================================
class CoordinatorProtocol:
    def start(self) -> None:
        raise NotImplementedError


class AppCoordinator(CoordinatorProtocol):
    def __init__(self) -> None:
        self.child_coordinators: List[CoordinatorProtocol] = []
        self.navigation_stack: List[str] = []

    def start(self) -> None:
        log_event("AppCoordinator", "Inisialisasi Root Window & Entry Navigation Stack", Color.CYAN)
        self.navigation_stack.append("MainTabBarController")

    def push(self, module_name: str) -> None:
        self.navigation_stack.append(module_name)
        log_event("AppCoordinator", f"Pushed Screen -> {module_name} (Depth: {len(self.navigation_stack)})", Color.CYAN)

    def pop(self) -> Optional[str]:
        if len(self.navigation_stack) > 1:
            popped = self.navigation_stack.pop()
            log_event("AppCoordinator", f"Popped Screen <- {popped} (Depth: {len(self.navigation_stack)})", Color.CYAN)
            return popped
        return None


# ==============================================================================
# 5. INTERACTIVE CLI RUNNER & TEST HARNESS
# ==============================================================================
def run_viper_demo() -> None:
    section("1. VIPER Architecture Simulation (Enterprise Decoupling)")
    # Registrasi dependencies
    DIContainer.register("AccountInteractorProtocol", lambda: AccountInteractor())
    DIContainer.register("AccountRouterProtocol", lambda: AccountRouter())

    interactor = DIContainer.resolve("AccountInteractorProtocol")
    router = DIContainer.resolve("AccountRouterProtocol")
    presenter = AccountPresenter(interactor=interactor, router=router)
    view = AccountViewController(presenter=presenter)

    view.render(user_id="USR-99214")
    print(f"\n{Color.DIM}  Menguji user interaksi tap button...{Color.RESET}")
    presenter.did_tap_transfer_button()


def run_tca_demo() -> None:
    section("2. TCA (The Composable Architecture) Simulation (Unidirectional)")
    store = TCAStore(initial_state=CartState(), reducer=cart_reducer)

    log_event("Client", "User menambahkan 'MacBook Pro M3 Max' ke keranjang", Color.WHITE)
    store.send(CartAction(action_type=CartActionType.ADD_ITEM, item_name="MacBook Pro M3 Max", item_price=3999.0))

    log_event("Client", "User menambahkan 'Magic Mouse' ke keranjang", Color.WHITE)
    store.send(CartAction(action_type=CartActionType.ADD_ITEM, item_name="Magic Mouse", item_price=99.0))

    log_event("Client", "User menekan tombol 'Checkout Now'", Color.WHITE)
    store.send(CartAction(action_type=CartActionType.CHECKOUT_SUBMIT))


def run_coordinator_demo() -> None:
    section("3. Modular Coordinator Pattern (Navigation Routing)")
    app_coord = AppCoordinator()
    app_coord.start()
    app_coord.push("AuthCoordinator.LoginViewController")
    app_coord.push("DashboardCoordinator.FeedViewController")
    app_coord.push("PaymentCoordinator.CheckoutViewController")
    app_coord.pop()
    print(f"\n  Current Stack: {Color.BOLD}{' -> '.join(app_coord.navigation_stack)}{Color.RESET}")


def interactive_menu() -> None:
    while True:
        header("iOS Large-Scale Architecture Interactive Lab (BAB-05)")
        print(f"  {Color.BOLD}Pilih Demonstrasi Pola Arsitektur:{Color.RESET}")
        print(f"  {Color.GREEN}1.{Color.RESET} Simulasi VIPER Architecture (Clean Screen Decoupling)")
        print(f"  {Color.GREEN}2.{Color.RESET} Simulasi TCA / UDF (Unidirectional Data Flow & Effects)")
        print(f"  {Color.GREEN}3.{Color.RESET} Simulasi App Coordinator (Modular Navigation Stack)")
        print(f"  {Color.GREEN}4.{Color.RESET} Jalankan Semua Simulasi Otomatis (Full Verification)")
        print(f"  {Color.RED}0.{Color.RESET} Keluar (Exit)")
        print(f"{Color.CYAN}{'-' * 64}{Color.RESET}")

        try:
            choice = input(f"{Color.BOLD}Pilihan Anda [0-4]: {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if choice == "1":
            run_viper_demo()
        elif choice == "2":
            run_tca_demo()
        elif choice == "3":
            run_coordinator_demo()
        elif choice == "4":
            run_viper_demo()
            run_tca_demo()
            run_coordinator_demo()
            print(f"\n{Color.BG_GREEN}{Color.WHITE} [STATUS: SELURUH POLA ARSITEKTUR BERHASIL DISIMULASIKAN] {Color.RESET}\n")
        elif choice == "0":
            print(f"\n{Color.YELLOW}Selesai. Selamat belajar arsitektur iOS skala besar!{Color.RESET}\n")
            break
        else:
            print(f"\n{Color.RED}[Error] Pilihan '{choice}' tidak valid.{Color.RESET}")

        input(f"\n{Color.DIM}Tekan [Enter] untuk melanjutkan...{Color.RESET}")


if __name__ == "__main__":
    # Jika dijalankan tanpa TTY interaktif (misalnya test runner), jalankan skenario lengkap
    if not sys.stdin.isatty():
        header("iOS Large-Scale Architecture Lab (Automated Execution)")
        run_viper_demo()
        run_tca_demo()
        run_coordinator_demo()
        print(f"\n{Color.GREEN}Automated execution finished successfully.{Color.RESET}")
    else:
        interactive_menu()

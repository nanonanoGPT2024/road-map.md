#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Arsitektur UI Imperatif & Pola Klasik UIKit
BAB-03: Arsitektur UI Imperatif dan Pola Klasik UIKit (iOS Core)

Topik Simulasi:
1. UIView Hierarchy & Geometry (Frame, Bounds, View Tree)
2. UIViewController Lifecycle State Machine (loadView s/d viewDidDisappear)
3. Target-Action & Responder Chain Event Propagation
4. Delegation & DataSource Pattern (UITableView Protocol Architecture)
"""

from typing import Any, Callable, Dict, List, Optional
import sys
import time

# --- ANSI Terminal Color Palette ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_WHITE = "\033[37m"
CLR_BG_BLUE = "\033[44m"


def print_header(title: str) -> None:
    print(f"\n{CLR_BG_BLUE}{CLR_WHITE}{CLR_BOLD}  === {title.upper()} ===  {CLR_RESET}\n")


def log_lifecycle(event: str, desc: str) -> None:
    print(f"{CLR_MAGENTA}[LIFECYCLE]{CLR_RESET} {CLR_BOLD}{event:<22}{CLR_RESET} -> {CLR_CYAN}{desc}{CLR_RESET}")


# ==============================================================================
# 1. UIResponder & Responder Chain
# ==============================================================================
class UIResponder:
    def __init__(self, name: str) -> None:
        self.name = name
        self.next_responder: Optional["UIResponder"] = None

    def touches_began(self, event: Dict[str, Any]) -> None:
        if self.next_responder:
            print(f"  {CLR_YELLOW}↳ Responder Chain:{CLR_RESET} Passing touch from {CLR_BOLD}{self.name}{CLR_RESET} to {CLR_BOLD}{self.next_responder.name}{CLR_RESET}")
            self.next_responder.touches_began(event)
        else:
            print(f"  {CLR_RED}✖ Event unhandled:{CLR_RESET} Ujung Responder Chain tercapai di {self.name}")


# ==============================================================================
# 2. UIView & Layout Engine (Frame, Bounds, Subviews)
# ==============================================================================
class CGRect:
    def __init__(self, x: float, y: float, width: float, height: float) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def __repr__(self) -> str:
        return f"({self.x:.1f}, {self.y:.1f}, {self.width:.1f}x{self.height:.1f})"


class UIView(UIResponder):
    def __init__(self, name: str, frame: CGRect) -> None:
        super().__init__(name)
        self.frame = frame
        self.bounds = CGRect(0, 0, frame.width, frame.height)
        self.superview: Optional["UIView"] = None
        self.subviews: List["UIView"] = []
        self.background_color: str = "Clear"
        self.is_user_interaction_enabled: bool = True

    def add_subview(self, child: "UIView") -> None:
        child.superview = self
        child.next_responder = self
        self.subviews.append(child)
        print(f"  {CLR_GREEN}✓ Subview Added:{CLR_RESET} '{child.name}' ditambahkan ke dalam '{self.name}' (Superview)")

    def layout_subviews(self) -> None:
        print(f"  {CLR_BLUE}⚙ layoutSubviews:{CLR_RESET} Menghitung ulang geometri layout untuk '{self.name}' dan {len(self.subviews)} subviews.")
        for sub in self.subviews:
            sub.layout_subviews()

    def print_view_tree(self, level: int = 0) -> None:
        indent = "  " * level
        marker = "└── " if level > 0 else "■ "
        print(f"{indent}{CLR_GREEN}{marker}{self.name}{CLR_RESET} [frame: {self.frame}, bounds: {self.bounds}, bg: {self.background_color}]")
        for sub in self.subviews:
            sub.print_view_tree(level + 1)


class UIButton(UIView):
    def __init__(self, name: str, frame: CGRect, title: str) -> None:
        super().__init__(name, frame)
        self.title = title
        self.target: Optional[Any] = None
        self.action: Optional[Callable[[], None]] = None

    def add_target(self, target: Any, action: Callable[[], None]) -> None:
        self.target = target
        self.action = action
        print(f"  {CLR_GREEN}✓ Target-Action Wired:{CLR_RESET} Button '{self.title}' -> Target: {target.__class__.__name__}, Action: {action.__name__}")

    def send_action(self) -> None:
        print(f"\n{CLR_BOLD}[Touch Event]{CLR_RESET} Tombol '{self.title}' ditekan!")
        if self.action:
            print(f"  {CLR_CYAN}⚡ Dispatching Target-Action:{CLR_RESET} Memanggil action {self.action.__name__}() pada target...")
            self.action()
        else:
            print(f"  {CLR_YELLOW}⚠ Tidak ada action target:{CLR_RESET} Mencoba responder chain fallback...")
            self.touches_began({"type": "touch_up_inside", "source": self.name})


# ==============================================================================
# 3. UIViewController & Lifecycle Engine
# ==============================================================================
class UIViewController(UIResponder):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self._view: Optional[UIView] = None
        self.is_view_loaded: bool = False

    @property
    def view(self) -> UIView:
        if self._view is None:
            self.load_view()
            self.view_did_load()
        return self._view

    @view.setter
    def view(self, new_view: UIView) -> None:
        self._view = new_view
        new_view.next_responder = self

    def load_view(self) -> None:
        log_lifecycle("loadView", f"Membuat root view hirarki imperatif secara programmatic untuk {self.name}")
        root_view = UIView(f"{self.name}.RootView", CGRect(0, 0, 393, 852))
        root_view.background_color = "SystemBackground"
        self.view = root_view
        self.is_view_loaded = True

    def view_did_load(self) -> None:
        log_lifecycle("viewDidLoad", "Root view sudah selesai dimuat ke memori. Setup inisial komponen & constraints.")

    def view_will_appear(self, animated: bool = True) -> None:
        log_lifecycle("viewWillAppear", f"View siap ditampilkan ke layar kaca (animated={animated}). Refresh data.")

    def view_is_appearing(self) -> None:
        log_lifecycle("viewIsAppearing", "iOS 17+ Modern Lifecycle: Geometri view dan traits sedang transisi aktif.")

    def view_did_appear(self, animated: bool = True) -> None:
        log_lifecycle("viewDidAppear", f"View sekarang sepenuhnya terlihat oleh user (animated={animated}). Start timers/analytics.")

    def view_will_disappear(self, animated: bool = True) -> None:
        log_lifecycle("viewWillDisappear", f"View akan segera meninggalkan layar (animated={animated}). Pause animasi.")

    def view_did_disappear(self, animated: bool = True) -> None:
        log_lifecycle("viewDidDisappear", f"View telah ditutup/tersembunyi (animated={animated}). Hentikan resource berat.")


# ==============================================================================
# 4. Delegation & DataSource Protocol Simulator (UITableView Pattern)
# ==============================================================================
class UITableViewDataSource:
    def number_of_rows(self, section: int) -> int:
        raise NotImplementedError

    def cell_for_row_at(self, row: int) -> str:
        raise NotImplementedError


class UITableViewDelegate:
    def did_select_row_at(self, row: int) -> None:
        raise NotImplementedError


class UITableView(UIView):
    def __init__(self, name: str, frame: CGRect) -> None:
        super().__init__(name, frame)
        self.data_source: Optional[UITableViewDataSource] = None
        self.delegate: Optional[UITableViewDelegate] = None

    def reload_data(self) -> None:
        print(f"\n{CLR_BLUE}[UITableView: {self.name}] reloadData() dipicu...{CLR_RESET}")
        if not self.data_source:
            print(f"  {CLR_RED}✖ Error:{CLR_RESET} DataSource nil! Tidak dapat merender tabel.")
            return

        total_rows = self.data_source.number_of_rows(0)
        print(f"  {CLR_CYAN}Query DataSource:{CLR_RESET} Terdeteksi {total_rows} baris sel.")
        for row_idx in range(total_rows):
            cell_text = self.data_source.cell_for_row_at(row_idx)
            print(f"    ├─ Row [{row_idx}]: {CLR_BOLD}{cell_text}{CLR_RESET}")
        print("  └─ Render siklus sel selesai.")

    def simulate_user_tap_row(self, row_idx: int) -> None:
        print(f"\n{CLR_BOLD}[User Interaction]{CLR_RESET} Tap pada baris ke-{row_idx}")
        if self.delegate:
            print(f"  {CLR_MAGENTA}Delegate Callback:{CLR_RESET} Mengirimkan didSelectRowAt({row_idx}) ke Delegate...")
            self.delegate.did_select_row_at(row_idx)
        else:
            print(f"  {CLR_YELLOW}⚠ Delegate nil:{CLR_RESET} Event selection diabaikan.")


# ==============================================================================
# 5. Konkret Implementasi: FeedViewController (MVC Classic iOS)
# ==============================================================================
class FeedViewController(UIViewController, UITableViewDataSource, UITableViewDelegate):
    def __init__(self) -> None:
        super().__init__("FeedViewController")
        self.articles = [
            "Membedah Memori Manual ARC vs AutoReleasePool",
            "AutoLayout Constraints VFL vs NSLayoutAnchor",
            "Deep Dive UIViewController Transitions & Coordinators",
        ]
        self.table_view: Optional[UITableView] = None
        self.refresh_button: Optional[UIButton] = None

    def view_did_load(self) -> None:
        super().view_did_load()

        # Inisialisasi Subviews secara imperatif
        print(f"  {CLR_BOLD}[FeedViewController Setup]{CLR_RESET} Merangkai arsitektur imperatif subviews...")
        self.table_view = UITableView("ArticleTableView", CGRect(0, 50, 393, 700))
        self.table_view.data_source = self
        self.table_view.delegate = self
        self.view.add_subview(self.table_view)

        # Inisialisasi Tombol dengan Target-Action
        self.refresh_button = UIButton("RefreshBtn", CGRect(20, 760, 353, 50), "Muat Ulang Berita")
        self.refresh_button.add_target(self, self.handle_refresh_action)
        self.view.add_subview(self.refresh_button)

    # Action Handler
    def handle_refresh_action(self) -> None:
        print(f"  {CLR_GREEN}★ Action Handled!{CLR_RESET} FeedViewController.handle_refresh_action() dieksekusi.")
        self.articles.append(f"Artikel Baru #{len(self.articles) + 1} (Fetched via Action)")
        if self.table_view:
            self.table_view.reload_data()

    # UITableViewDataSource Implementation
    def number_of_rows(self, section: int) -> int:
        return len(self.articles)

    def cell_for_row_at(self, row: int) -> str:
        return f"Cell -> {self.articles[row]}"

    # UITableViewDelegate Implementation
    def did_select_row_at(self, row: int) -> None:
        print(f"  {CLR_GREEN}★ Navigation Triggered:{CLR_RESET} Membuka detail untuk: '{self.articles[row]}'")


# ==============================================================================
# 6. Interactive Terminal Demonstration Pipeline
# ==============================================================================
def run_simulation() -> None:
    print(f"{CLR_BOLD}{CLR_GREEN}")
    print("==================================================================")
    print("  SIMULASI ARSITEKTUR UI IMPERATIF & POLA KLASIK UIKIT (PYTHON 3) ")
    print("==================================================================")
    print(f"{CLR_RESET}")

    # Step 1: Inisialisasi & Siklus Hidup ViewController
    print_header("Skenario 1: UIViewController Lifecycle Push Sequence")
    vc = FeedViewController()

    print(f"{CLR_DIM}Mengakses properti vc.view memicu loadView() secara lazy...{CLR_RESET}")
    _ = vc.view  # Trigger loadView & viewDidLoad

    time.sleep(0.1)
    vc.view_will_appear(animated=True)
    vc.view_is_appearing()
    vc.view.layout_subviews()
    vc.view_did_appear(animated=True)

    # Step 2: Inspeksi Visual Hirarki View Tree
    print_header("Skenario 2: Inspeksi Hirarki View Tree (Visual Inspection)")
    vc.view.print_view_tree()

    # Step 3: UITableView DataSource & Delegate Pattern
    print_header("Skenario 3: UITableView DataSource & Delegate Pattern")
    if vc.table_view:
        vc.table_view.reload_data()
        vc.table_view.simulate_user_tap_row(1)

    # Step 4: Target-Action & Responder Chain Event
    print_header("Skenario 4: Target-Action Event & Responder Chain")
    if vc.refresh_button:
        vc.refresh_button.send_action()

    # Step 5: Lifecycle Pop / Dismissal
    print_header("Skenario 5: UIViewController Dismissal Sequence")
    vc.view_will_disappear(animated=True)
    vc.view_did_disappear(animated=True)

    print(f"\n{CLR_GREEN}{CLR_BOLD}✔ SELURUH SIKLUS SIMULASI UIKIT BERHASIL DIEKSEKUSI SEMPURNA!{CLR_RESET}\n")


if __name__ == "__main__":
    run_simulation()

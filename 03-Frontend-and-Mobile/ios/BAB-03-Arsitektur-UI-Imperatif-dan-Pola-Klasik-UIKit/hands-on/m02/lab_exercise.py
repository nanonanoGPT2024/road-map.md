#!/usr/bin/env python3
"""
Lab Hands-on: Imperative UI Architecture & Classic UIKit Patterns Simulation
Topic: iOS (03-Frontend-and-Mobile) - Chapter 03, Module 02 Deep Dive

This lab models core imperative UIKit mechanisms in pure Python:
1. UIViewController Lifecycle State Machine (loadView -> didDisappear)
2. View Hierarchy & Layout Passes (setNeedsLayout -> layoutSubviews)
3. UITableView Reusable Cell Queue Pattern (dequeueReusableCell / prepareForReuse)
4. Target-Action Responder Pattern (UIControl event dispatch)
5. Delegate Pattern with protocol-like decoupled callbacks
"""

from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
import time
import sys


# --- ANSI Colors for Terminal UI ---
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


@dataclass
class CGRect:
    x: float
    y: float
    width: float
    height: float

    def __repr__(self):
        return f"({self.x:.1f}, {self.y:.1f}, {self.width:.1f}x{self.height:.1f})"


@dataclass(frozen=True)
class IndexPath:
    section: int
    row: int


# --- UIKit Core Simulation: Views & Controls ---

class UIView:
    """Simulates a base UIView with hierarchy and deferred layout engine."""
    def __init__(self, frame: CGRect = CGRect(0, 0, 0, 0)):
        self.frame = frame
        self.subviews: List['UIView'] = []
        self.superview: Optional['UIView'] = None
        self._needs_layout = True

    def addSubview(self, subview: 'UIView') -> None:
        subview.superview = self
        self.subviews.append(subview)
        self.setNeedsLayout()

    def setNeedsLayout(self) -> None:
        self._needs_layout = True
        if self.superview:
            self.superview.setNeedsLayout()

    def layoutIfNeeded(self) -> None:
        if self._needs_layout:
            self.layoutSubviews()
            self._needs_layout = False
            for subview in self.subviews:
                subview.layoutIfNeeded()

    def layoutSubviews(self) -> None:
        """Subclasses override this to position subviews imperatively."""
        pass


class UIControl(UIView):
    """Simulates UIKit Target-Action pattern for user interactions."""
    TOUCH_UP_INSIDE = "touchUpInside"

    def __init__(self, frame: CGRect = CGRect(0, 0, 0, 0)):
        super().__init__(frame)
        self._targets: Dict[str, List[tuple]] = {self.TOUCH_UP_INSIDE: []}

    def addTarget(self, target: Any, action: Callable, event: str = TOUCH_UP_INSIDE) -> None:
        if event in self._targets:
            self._targets[event].append((target, action))

    def sendActions(self, event: str) -> None:
        print(f"  {Colors.CYAN}[UIControl Event]{Colors.RESET} Event '{event}' triggered on {self.__class__.__name__}")
        for target, action in self._targets.get(event, []):
            action(target, self)


class UIButton(UIControl):
    def __init__(self, frame: CGRect = CGRect(0, 0, 100, 30), title: str = "Button"):
        super().__init__(frame)
        self.title = title

    def __repr__(self):
        return f"<UIButton title='{self.title}' frame={self.frame}>"


# --- Reusable TableView Cell Pattern ---

class UITableViewCell(UIView):
    """Simulates UITableViewCell lifecycle with reuse identifiers and prepareForReuse."""
    def __init__(self, reuseIdentifier: str):
        super().__init__(CGRect(0, 0, 320, 44))
        self.reuseIdentifier = reuseIdentifier
        self.textLabel: str = ""
        self.selected: bool = False
        self.allocation_id: int = id(self) % 10000

    def prepareForReuse(self) -> None:
        """Reset cell state before being returned by dequeueReusableCell."""
        self.textLabel = ""
        self.selected = False

    def __repr__(self):
        return f"<Cell #{self.allocation_id} id='{self.reuseIdentifier}' text='{self.textLabel}'>"


class UITableView(UIView):
    """
    Simulates UITableView:
    - DataSource & Delegate protocol decoupled bindings.
    - O(1) cell reuse pool using deque to prevent runaway memory usage.
    """
    def __init__(self, frame: CGRect):
        super().__init__(frame)
        self.dataSource = None  # Expected to implement numberOfRows and cellForRowAt
        self.delegate = None    # Expected to implement didSelectRowAt
        self._reusePool: Dict[str, deque] = {}
        self._allocated_cells_count: int = 0
        self._dequeued_reused_count: int = 0
        self.visibleCells: List[UITableViewCell] = []
        self.contentOffsetY: float = 0.0

    def register(self, cell_class: type, reuseIdentifier: str) -> None:
        self._reusePool[reuseIdentifier] = deque()
        self._cell_class = cell_class

    def dequeueReusableCell(self, identifier: str) -> UITableViewCell:
        pool = self._reusePool.get(identifier)
        if pool and len(pool) > 0:
            cell = pool.popleft()
            cell.prepareForReuse()
            self._dequeued_reused_count += 1
            print(f"    {Colors.GREEN}[Reuse Pool]{Colors.RESET} Recycled existing Cell #{cell.allocation_id}")
            return cell
        
        # Cache miss: Instantiate new cell
        self._allocated_cells_count += 1
        new_cell = self._cell_class(identifier)
        print(f"    {Colors.YELLOW}[Reuse Pool]{Colors.RESET} Allocating NEW Cell #{new_cell.allocation_id}")
        return new_cell

    def layoutSubviews(self) -> None:
        super().layoutSubviews()
        self.reloadData()

    def reloadData(self) -> None:
        if not self.dataSource:
            return
        
        # Enqueue old visible cells back into reuse pool
        for cell in self.visibleCells:
            self._reusePool[cell.reuseIdentifier].append(cell)
        self.visibleCells.clear()

        # Render viewport (Simulating 4 items fitting inside the current viewport frame)
        rows_per_screen = int(self.frame.height // 44)
        total_rows = self.dataSource.numberOfRowsInSection(self, 0)
        
        start_row = int(self.contentOffsetY // 44)
        end_row = min(total_rows, start_row + rows_per_screen)

        for row in range(start_row, end_row):
            indexPath = IndexPath(section=0, row=row)
            cell = self.dataSource.cellForRowAt(self, indexPath)
            cell.frame = CGRect(0, row * 44, self.frame.width, 44)
            self.visibleCells.append(cell)

    def scrollTo(self, offsetY: float) -> None:
        print(f"\n{Colors.BOLD}>> Scrolling TableView offset to Y={offsetY:.1f}{Colors.RESET}")
        self.contentOffsetY = offsetY
        self.reloadData()


# --- UIViewController & Lifecycle Simulation ---

class UIViewController:
    """Simulates UIViewController life-cycle callbacks and view management."""
    def __init__(self):
        self._view: Optional[UIView] = None
        self.isViewLoaded: bool = False
        self.title: str = self.__class__.__name__

    @property
    def view(self) -> UIView:
        if self._view is None:
            self._lifecycle_loadView()
        return self._view

    def _lifecycle_loadView(self) -> None:
        print(f"{Colors.BLUE}[Lifecycle]{Colors.RESET} {self.title} -> loadView()")
        self.loadView()
        self.isViewLoaded = True
        print(f"{Colors.BLUE}[Lifecycle]{Colors.RESET} {self.title} -> viewDidLoad()")
        self.viewDidLoad()

    def loadView(self) -> None:
        """Create root view container."""
        self._view = UIView(CGRect(0, 0, 375, 667))

    def viewDidLoad(self) -> None:
        """Hook for post-initialization configuration."""
        pass

    def viewWillAppear(self, animated: bool = True) -> None:
        print(f"{Colors.BLUE}[Lifecycle]{Colors.RESET} {self.title} -> viewWillAppear(animated={animated})")

    def viewDidAppear(self, animated: bool = True) -> None:
        print(f"{Colors.BLUE}[Lifecycle]{Colors.RESET} {self.title} -> viewDidAppear(animated={animated})")

    def viewWillDisappear(self, animated: bool = True) -> None:
        print(f"{Colors.BLUE}[Lifecycle]{Colors.RESET} {self.title} -> viewWillDisappear(animated={animated})")

    def viewDidDisappear(self, animated: bool = True) -> None:
        print(f"{Colors.BLUE}[Lifecycle]{Colors.RESET} {self.title} -> viewDidDisappear(animated={animated})")


# --- Concrete Implementation: UsersListViewController ---

class UsersListViewController(UIViewController):
    CELL_ID = "UserCellIdentifier"

    def __init__(self, dataset_size: int = 50):
        super().__init__()
        self.dataset = [f"User Record #{i:03d} (UUID-{hash(str(i)) % 10000:04d})" for i in range(dataset_size)]
        self.tableView: Optional[UITableView] = None
        self.refreshButton: Optional[UIButton] = None

    def viewDidLoad(self) -> None:
        super().viewDidLoad()
        
        # Imperative UI Assembly: Add TableView
        self.tableView = UITableView(CGRect(0, 50, 375, 176))  # 176px = exactly 4 cells visible (4 * 44px)
        self.tableView.register(UITableViewCell, self.CELL_ID)
        self.tableView.dataSource = self
        self.tableView.delegate = self
        self.view.addSubview(self.tableView)

        # Imperative UI Assembly: Add Action Button
        self.refreshButton = UIButton(CGRect(10, 10, 120, 30), title="Purge Cache")
        self.refreshButton.addTarget(self, UsersListViewController.handleButtonTap, UIControl.TOUCH_UP_INSIDE)
        self.view.addSubview(self.refreshButton)

    def handleButtonTap(self, sender: UIControl) -> None:
        print(f"{Colors.HEADER}[Target-Action Handler]{Colors.RESET} Action invoked on controller by {sender}")
        print(f"{Colors.HEADER}[Target-Action Handler]{Colors.RESET} Executing imperative data reload...")
        if self.tableView:
            self.tableView.reloadData()

    # --- UITableViewDataSource Protocols ---
    def numberOfRowsInSection(self, tableView: UITableView, section: int) -> int:
        return len(self.dataset)

    def cellForRowAt(self, tableView: UITableView, indexPath: IndexPath) -> UITableViewCell:
        cell = tableView.dequeueReusableCell(self.CELL_ID)
        cell.textLabel = self.dataset[indexPath.row]
        return cell

    # --- UITableViewDelegate Protocols ---
    def didSelectRowAt(self, tableView: UITableView, indexPath: IndexPath) -> None:
        print(f"  {Colors.BOLD}[Delegate Callback]{Colors.RESET} Row selected: {indexPath.row} -> {self.dataset[indexPath.row]}")


# --- Test Execution & Benchmark Runner ---

def run_lab():
    print(f"{Colors.BOLD}{Colors.HEADER}=== UIKit Architecture & Classic Patterns Deep Dive ==={Colors.RESET}\n")

    # 1. UIViewController Lifecycle Transitions
    print(f"{Colors.BOLD}Stage 1: Controller Lifecycle Initialization{Colors.RESET}")
    vc = UsersListViewController(dataset_size=20)
    
    # Trigger view instantiation
    _ = vc.view
    vc.viewWillAppear(animated=False)
    vc.view.layoutIfNeeded()
    vc.viewDidAppear(animated=False)

    # 2. Inspect Initial Rendering & Cell Pool Metrics
    print(f"\n{Colors.BOLD}Stage 2: Initial Viewport Inspection (Capacity: 4 Cells){Colors.RESET}")
    for cell in vc.tableView.visibleCells:
        print(f"  Visible: {cell}")
    
    # 3. Simulate Interactive User Scrolling (Triggering Cell Recycling)
    print(f"\n{Colors.BOLD}Stage 3: Simulating Fast Scrolling (Testing Reuse Pool Efficiency){Colors.RESET}")
    # Scroll down 4 rows
    vc.tableView.scrollTo(offsetY=176.0)
    # Scroll down another 4 rows
    vc.tableView.scrollTo(offsetY=352.0)
    
    print(f"\n  Final Visible Cells in viewport:")
    for cell in vc.tableView.visibleCells:
        print(f"  Visible: {cell}")

    # 4. Target-Action Event Dispatch Simulation
    print(f"\n{Colors.BOLD}Stage 4: Simulating Target-Action UI Event Dispatch{Colors.RESET}")
    vc.refreshButton.sendActions(UIControl.TOUCH_UP_INSIDE)

    # 5. Delegate Callback Simulation
    print(f"\n{Colors.BOLD}Stage 5: Simulating Delegate Intercept{Colors.RESET}")
    vc.didSelectRowAt(vc.tableView, IndexPath(section=0, row=9))

    # 6. Lifecycle Teardown
    print(f"\n{Colors.BOLD}Stage 6: View Lifecycle Teardown{Colors.RESET}")
    vc.viewWillDisappear(animated=True)
    vc.viewDidDisappear(animated=True)

    # Summary Statistics
    total_allocations = vc.tableView._allocated_cells_count
    total_reuses = vc.tableView._dequeued_reused_count
    total_requests = total_allocations + total_reuses
    efficiency = (total_reuses / total_requests) * 100 if total_requests > 0 else 0

    print(f"\n{Colors.BOLD}{Colors.HEADER}=== UIKit Cell Recycling Telemetry ==={Colors.RESET}")
    print(f"Total Visible Viewport Capacity : 4 cells")
    print(f"Dataset Size                   : {len(vc.dataset)} rows")
    print(f"Total Cell Allocations (Heap)  : {Colors.YELLOW}{total_allocations}{Colors.RESET}")
    print(f"Total Dequeue Reuses (Cache)   : {Colors.GREEN}{total_reuses}{Colors.RESET}")
    print(f"Memory Reuse Efficiency Rate   : {Colors.CYAN}{efficiency:.2f}%{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}[✓] Lab verification completed successfully.{Colors.RESET}\n")


if __name__ == "__main__":
    run_lab()

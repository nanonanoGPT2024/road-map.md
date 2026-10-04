#!/usr/bin/env python3
import time
import sys

class FiberNode:
    def __init__(self, name, node_type="Component", state=None):
        self.name = name
        self.type = node_type
        self.state = state or {}
        self.child = None
        self.sibling = None
        self.parent = None
        self.alternate = None
        self.effect_tag = None # e.g., 'PLACEMENT', 'UPDATE'

    def __repr__(self):
        return f"<FiberNode {self.name} ({self.type})>"

class ReactFiberSimulator:
    def __init__(self):
        self.next_unit_of_work = None
        self.wip_root = None
        self.current_root = None
        self.deadline = 0

    def request_idle_callback_simulation(self):
        """Simulate browser's requestIdleCallback giving us a deadline."""
        self.deadline = time.time() + 0.05 # 50ms deadline per frame
        
    def render(self, root_node):
        print(f"\n[\033[94mINFO\033[0m] Starting Render Phase for: {root_node.name}")
        self.wip_root = FiberNode(root_node.name, root_node.type)
        self.wip_root.alternate = self.current_root
        self.next_unit_of_work = self.wip_root
        
        # Build the initial mock fiber tree manually for this simulation
        self._build_mock_tree(self.wip_root)
        
        self.work_loop()

    def _build_mock_tree(self, root_fiber):
        # Tree Structure:
        # AppRoot
        # ├── Header
        # │   └── Logo
        # ├── Main
        # │   ├── Article
        # │   └── Sidebar
        # └── Footer
        
        header = FiberNode("Header")
        logo = FiberNode("Logo", "DOM")
        main = FiberNode("Main")
        article = FiberNode("Article", "DOM")
        sidebar = FiberNode("Sidebar", "DOM")
        footer = FiberNode("Footer")

        # Establish links (Linked List structure instead of deep tree)
        root_fiber.child = header
        header.parent = root_fiber
        header.sibling = main
        main.parent = root_fiber
        main.sibling = footer
        footer.parent = root_fiber

        header.child = logo
        logo.parent = header

        main.child = article
        article.parent = main
        article.sibling = sidebar
        sidebar.parent = main

    def work_loop(self):
        self.request_idle_callback_simulation()
        
        print("\n[\033[93mWORK LOOP\033[0m] Commencing interruptible work loop...")
        
        while self.next_unit_of_work is not None:
            # Check deadline
            if time.time() >= self.deadline:
                print("[\033[91mYIELD\033[0m] Deadline reached! Yielding to main thread...")
                time.sleep(0.1) # Simulate yielding back to browser main thread
                self.request_idle_callback_simulation() # get next frame
                
            self.next_unit_of_work = self.perform_unit_of_work(self.next_unit_of_work)

        print("\n[\033[92mCOMPLETE\033[0m] Render Phase Complete.")
        self.commit_root()

    def perform_unit_of_work(self, fiber):
        print(f"  \033[96m-> Working on:\033[0m {fiber.name}")
        time.sleep(0.02) # Simulate CPU intensive reconciliation work
        
        # In a real engine, we'd reconcile children here
        # For simulation, we already built the mock tree.
        # We just set an effect tag for DOM modifications later
        fiber.effect_tag = 'PLACEMENT'
        
        # Return next unit of work (Depth-first traversal)
        if fiber.child:
            return fiber.child
        
        next_fiber = fiber
        while next_fiber is not None:
            if next_fiber.sibling:
                return next_fiber.sibling
            next_fiber = next_fiber.parent
            
        return None

    def commit_root(self):
        print("\n[\033[94mINFO\033[0m] Starting Commit Phase (Uninterruptible)...")
        # Commit phase is not interruptible, applies changes to actual DOM
        self.commit_work(self.wip_root.child)
        self.current_root = self.wip_root
        self.wip_root = None
        print("[\033[92mSUCCESS\033[0m] Commit Phase Complete. Changes applied to Real DOM.")

    def commit_work(self, fiber):
        if not fiber:
            return
            
        if fiber.effect_tag == 'PLACEMENT':
            print(f"  \033[95m[DOM]\033[0m Appending {fiber.name} to DOM...")
            time.sleep(0.01) # Simulate DOM manipulation delay
            
        self.commit_work(fiber.child)
        self.commit_work(fiber.sibling)

def main():
    print("="*60)
    print("\033[1mReact Fiber Engine Simulator\033[0m".center(68))
    print("="*60)
    print("\nThis script simulates the interruptible Fiber Work Loop architecture.")
    print("It demonstrates how a deep component tree is processed in chunks")
    print("using a linked list structure (child, sibling, parent) to allow")
    print("yielding to the main thread.\n")
    
    app_root = FiberNode("AppRoot")
    simulator = ReactFiberSimulator()
    simulator.render(app_root)

if __name__ == "__main__":
    main()

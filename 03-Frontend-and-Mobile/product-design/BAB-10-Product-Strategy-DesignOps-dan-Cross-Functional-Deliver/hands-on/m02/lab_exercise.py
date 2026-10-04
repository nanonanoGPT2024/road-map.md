import sys
import time
import json
import threading
from collections import defaultdict

# ANSI Colors for terminal
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

class DesignOpsSimulator:
    def __init__(self):
        self.components = {}
        self.handoff_queue = []
        self.stats = defaultdict(int)
        
    def add_component(self, name, designer, complexity):
        self.components[name] = {
            "designer": designer,
            "complexity": complexity,
            "status": "Draft",
            "engineer_assigned": None,
            "issues": []
        }
        print(f"{Colors.OKCYAN}[DesignOps] Component '{name}' created by {designer} (Complexity: {complexity}){Colors.ENDC}")

    def update_status(self, name, status):
        if name in self.components:
            self.components[name]["status"] = status
            print(f"{Colors.OKBLUE}[DesignOps] '{name}' status updated to: {status}{Colors.ENDC}")
            if status == "Ready for Handoff":
                self.handoff_queue.append(name)
        else:
            print(f"{Colors.FAIL}[Error] Component {name} not found.{Colors.ENDC}")

    def simulate_cross_functional_review(self, name):
        print(f"\n{Colors.HEADER}--- Starting Cross-Functional Review for '{name}' ---{Colors.ENDC}")
        comp = self.components.get(name)
        if not comp:
            return
            
        time.sleep(0.5)
        print(f"{Colors.WARNING}[Product Manager] Checking requirements alignment...{Colors.ENDC}")
        time.sleep(0.5)
        print(f"{Colors.WARNING}[Lead Engineer] Checking technical feasibility...{Colors.ENDC}")
        
        if comp["complexity"] > 5:
            comp["issues"].append("Complexity too high, needs breakdown.")
            self.update_status(name, "Needs Revision")
            print(f"{Colors.FAIL}[Review Failed] {name} has issues: {comp['issues']}{Colors.ENDC}")
        else:
            print(f"{Colors.OKGREEN}[Review Passed] {name} is approved by PM and Tech.{Colors.ENDC}")
            self.update_status(name, "Ready for Handoff")

    def process_handoff(self, engineer_pool):
        print(f"\n{Colors.HEADER}--- Processing Design Handoff Queue ---{Colors.ENDC}")
        while self.handoff_queue:
            comp_name = self.handoff_queue.pop(0)
            if not engineer_pool:
                print(f"{Colors.FAIL}No engineers available for {comp_name}. Bottleneck detected!{Colors.ENDC}")
                self.stats["bottlenecks"] += 1
                break
                
            engineer = engineer_pool.pop(0)
            self.components[comp_name]["engineer_assigned"] = engineer
            self.components[comp_name]["status"] = "In Development"
            print(f"{Colors.OKGREEN}[Handoff] '{comp_name}' handed off to {engineer}.{Colors.ENDC}")
            self.stats["successful_handoffs"] += 1
            time.sleep(0.5)

    def print_dashboard(self):
        print(f"\n{Colors.BOLD}{Colors.HEADER}=== DesignOps Dashboard ==={Colors.ENDC}")
        print(json.dumps(self.components, indent=2))
        print(f"\n{Colors.OKCYAN}Metrics:{Colors.ENDC}")
        print(f" - Successful Handoffs: {self.stats['successful_handoffs']}")
        print(f" - Bottlenecks: {self.stats['bottlenecks']}")
        print("===========================\n")

def main():
    print(f"{Colors.BOLD}Initializing DesignOps & Cross-Functional Simulator...{Colors.ENDC}\n")
    
    sim = DesignOpsSimulator()
    engineers = ["Alice (Eng)", "Bob (Eng)"]
    
    # 1. Component Creation phase (Design)
    sim.add_component("Button-Primary", "Charlie (UX)", 3)
    sim.add_component("Complex-Data-Grid", "Diana (UX)", 8)
    sim.add_component("Navigation-Bar", "Charlie (UX)", 4)
    
    time.sleep(0.5)
    
    # 2. Status update & Review phase (Cross-functional)
    sim.update_status("Button-Primary", "In Review")
    sim.simulate_cross_functional_review("Button-Primary")
    
    sim.update_status("Complex-Data-Grid", "In Review")
    sim.simulate_cross_functional_review("Complex-Data-Grid")
    
    sim.update_status("Navigation-Bar", "In Review")
    sim.simulate_cross_functional_review("Navigation-Bar")
    
    time.sleep(0.5)
    
    # 3. Handoff Phase (DesignOps)
    sim.process_handoff(engineers)
    
    # 4. Reporting
    sim.print_dashboard()
    
    print(f"{Colors.BOLD}Simulation Complete.{Colors.ENDC}")

if __name__ == "__main__":
    main()

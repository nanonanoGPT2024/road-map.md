#!/usr/bin/env python3
"""
Lab Exercise: Product Strategy, DesignOps, and Cross-Functional Delivery
BAB 10: Product Strategy, DesignOps, dan Cross-Functional Deliver
"""

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict

# ANSI Color Codes
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"
CLR_WHITE = "\033[97m"

class StrategicPillar(Enum):
    ACTIVATION = "Core User Activation & Onboarding"
    RETENTION = "Feature Stickiness & Workflow Retention"
    MONETIZATION = "Self-Serve Expansion & Conversion"
    SCALABILITY = "Design System Governance & Tech Debt"

class HandoffStatus(Enum):
    DRAFT = "Draft (In Exploration)"
    READY_FOR_SPEC = "Design Specs Frozen"
    IN_DEV_SPRINT = "Active Engineering Implementation"
    DESIGN_QA = "Cross-Functional QA & Polish"
    SHIPPED = "Production Deployed & Monitored"

@dataclass
class DesignTokenHealth:
    token_parity_percent: float
    hardcoded_values_count: int
    wcag_aaa_contrast_pass: bool
    figma_to_code_synced: bool

@dataclass
class Initiative:
    id: str
    name: str
    pillar: StrategicPillar
    reach: int          # Users impacted / quarter
    impact: float       # 0.5 (low), 1.0 (medium), 2.0 (high), 3.0 (massive)
    confidence: float   # 0.5 (low data), 0.8 (some evidence), 1.0 (high certainty)
    effort: int         # Person-weeks across Design & Eng
    design_health: DesignTokenHealth
    handoff_stage: HandoffStatus = HandoffStatus.DRAFT

    @property
    def rice_score(self) -> float:
        if self.effort <= 0:
            return 0.0
        return (self.reach * self.impact * self.confidence) / self.effort

    @property
    def design_ops_readiness(self) -> float:
        score = 0.0
        if self.design_health.token_parity_percent >= 90.0:
            score += 35.0
        else:
            score += (self.design_health.token_parity_percent / 100.0) * 35.0
        
        if self.design_health.hardcoded_values_count == 0:
            score += 25.0
        elif self.design_health.hardcoded_values_count < 5:
            score += 15.0

        if self.design_health.wcag_aaa_contrast_pass:
            score += 20.0
        if self.design_health.figma_to_code_synced:
            score += 20.0

        return round(score, 1)

class ProductStrategySimulator:
    def __init__(self):
        self.north_star_metric = "Weekly Active Workflows Completed (WAWC)"
        self.initiatives: List[Initiative] = []
        self._seed_sample_data()

    def _seed_sample_data(self):
        self.initiatives = [
            Initiative(
                id="INIT-101",
                name="Zero-Friction Workspace Onboarding",
                pillar=StrategicPillar.ACTIVATION,
                reach=12000,
                impact=2.0,
                confidence=0.8,
                effort=4,
                design_health=DesignTokenHealth(
                    token_parity_percent=95.0,
                    hardcoded_values_count=0,
                    wcag_aaa_contrast_pass=True,
                    figma_to_code_synced=True
                ),
                handoff_stage=HandoffStatus.READY_FOR_SPEC
            ),
            Initiative(
                id="INIT-102",
                name="Unified Multi-Brand Design System Tokens",
                pillar=StrategicPillar.SCALABILITY,
                reach=35000,
                impact=3.0,
                confidence=1.0,
                effort=8,
                design_health=DesignTokenHealth(
                    token_parity_percent=88.5,
                    hardcoded_values_count=6,
                    wcag_aaa_contrast_pass=True,
                    figma_to_code_synced=False
                ),
                handoff_stage=HandoffStatus.IN_DEV_SPRINT
            ),
            Initiative(
                id="INIT-103",
                name="Quick Checkout & Plan Upgrade Flow",
                pillar=StrategicPillar.MONETIZATION,
                reach=8500,
                impact=3.0,
                confidence=0.7,
                effort=6,
                design_health=DesignTokenHealth(
                    token_parity_percent=72.0,
                    hardcoded_values_count=14,
                    wcag_aaa_contrast_pass=False,
                    figma_to_code_synced=False
                ),
                handoff_stage=HandoffStatus.DRAFT
            ),
            Initiative(
                id="INIT-104",
                name="Collaborative Canvas Comments & Reactions",
                pillar=StrategicPillar.RETENTION,
                reach=18000,
                impact=2.0,
                confidence=0.9,
                effort=5,
                design_health=DesignTokenHealth(
                    token_parity_percent=98.0,
                    hardcoded_values_count=1,
                    wcag_aaa_contrast_pass=True,
                    figma_to_code_synced=True
                ),
                handoff_stage=HandoffStatus.DESIGN_QA
            ),
        ]

    def display_header(self):
        print(f"\n{CLR_BLUE}{'='*78}{CLR_RESET}")
        print(f"{CLR_BOLD}{CLR_CYAN}  PRODUCT STRATEGY & DESIGNOPS INTERACTIVE SIMULATION WORKBENCH{CLR_RESET}")
        print(f"{CLR_WHITE}  North Star Metric: {CLR_YELLOW}{self.north_star_metric}{CLR_RESET}")
        print(f"{CLR_BLUE}{'='*78}{CLR_RESET}")

    def run_strategic_prioritization(self):
        print(f"\n{CLR_BOLD}{CLR_WHITE}--- [1] RICE Strategic Prioritization Matrix ---{CLR_RESET}")
        print(f"{'ID':<10} {'Initiative Name':<34} {'Pillar':<14} {'RICE Score':<12} {'Rank':<6}")
        print(f"{'-'*78}")

        sorted_initiatives = sorted(self.initiatives, key=lambda x: x.rice_score, reverse=True)
        for rank, init in enumerate(sorted_initiatives, start=1):
            score_color = CLR_GREEN if init.rice_score >= 4000 else CLR_YELLOW
            print(f"{init.id:<10} {init.name[:32]:<34} {init.pillar.name:<14} "
                  f"{score_color}{init.rice_score:>9.1f}{CLR_RESET}   #{rank}")

    def run_designops_audit(self):
        print(f"\n{CLR_BOLD}{CLR_WHITE}--- [2] DesignOps Pipeline & Token Health Gate ---{CLR_RESET}")
        print(f"{'ID':<10} {'Token Parity':<14} {'Hardcoded CSS':<15} {'Figma Sync':<12} {'Ops Readiness':<15} {'Gate':<10}")
        print(f"{'-'*78}")

        for init in self.initiatives:
            readiness = init.design_ops_readiness
            gate_pass = readiness >= 80.0
            gate_label = f"{CLR_GREEN}PASSED{CLR_RESET}" if gate_pass else f"{CLR_RED}BLOCKED{CLR_RESET}"
            token_str = f"{init.design_health.token_parity_percent:.1f}%"
            sync_str = "SYNCED" if init.design_health.figma_to_code_synced else "DESYNC"
            sync_color = CLR_GREEN if init.design_health.figma_to_code_synced else CLR_RED

            print(f"{init.id:<10} {token_str:<14} {init.design_health.hardcoded_values_count:<15} "
                  f"{sync_color}{sync_str:<12}{CLR_RESET} {readiness:>5.1f}%          {gate_label}")

    def run_cross_functional_handoff_simulation(self):
        print(f"\n{CLR_BOLD}{CLR_WHITE}--- [3] Tri-Party Cross-Functional Handoff & Design QA Sign-off ---{CLR_RESET}")
        print(f"{CLR_CYAN}Reviewers: Product Manager (PM), Lead Product Designer (PD), Tech Lead (TL){CLR_RESET}\n")

        for init in self.initiatives:
            print(f"Checking initiative {CLR_BOLD}{init.id}{CLR_RESET} ({init.name}):")
            time.sleep(0.15)
            
            # Sign-off evaluation
            pm_approved = init.rice_score > 3000
            pd_approved = init.design_ops_readiness >= 75.0
            tl_approved = init.design_health.hardcoded_values_count <= 5 and init.effort <= 6

            pm_badge = f"{CLR_GREEN}✓ PM Approval{CLR_RESET}" if pm_approved else f"{CLR_RED}✗ PM Pivot Needed{CLR_RESET}"
            pd_badge = f"{CLR_GREEN}✓ PD Token Spec{CLR_RESET}" if pd_approved else f"{CLR_RED}✗ PD Design Debt{CLR_RESET}"
            tl_badge = f"{CLR_GREEN}✓ TL Feasible{CLR_RESET}" if tl_approved else f"{CLR_YELLOW}⚠ TL High Complexity{CLR_RESET}"

            print(f"  Stage: {CLR_MAGENTA}{init.handoff_stage.value}{CLR_RESET}")
            print(f"  Review Signatures: [{pm_badge}] [{pd_badge}] [{tl_badge}]")

            if pm_approved and pd_approved and tl_approved:
                print(f"  {CLR_GREEN}▶ STATUS: Greenlit for Production Deployment Sprint!{CLR_RESET}\n")
            else:
                print(f"  {CLR_YELLOW}▶ STATUS: Held in Cross-Functional Alignment Review.{CLR_RESET}\n")

    def run_interactive_menu(self):
        self.display_header()
        
        # If in automated environment or non-tty, run full report
        if not sys.stdin.isatty():
            print(f"{CLR_YELLOW}Non-interactive terminal detected. Running automated full suite...{CLR_RESET}")
            self.run_strategic_prioritization()
            self.run_designops_audit()
            self.run_cross_functional_handoff_simulation()
            print(f"{CLR_GREEN}Simulation complete successfully.{CLR_RESET}\n")
            return

        while True:
            print(f"{CLR_BOLD}Interactive Modes:{CLR_RESET}")
            print("  1. Evaluate Strategic Prioritization (RICE Engine)")
            print("  2. Run DesignOps Governance & Token Health Gates")
            print("  3. Simulate Tri-Party Cross-Functional Handoff & QA")
            print("  4. Execute Full Delivery Lifecycle Benchmark")
            print("  5. Exit")
            
            try:
                choice = input(f"{CLR_CYAN}Select option [1-5]: {CLR_RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{CLR_YELLOW}Exiting simulation.{CLR_RESET}")
                break

            if choice == "1":
                self.run_strategic_prioritization()
            elif choice == "2":
                self.run_designops_audit()
            elif choice == "3":
                self.run_cross_functional_handoff_simulation()
            elif choice == "4":
                self.run_strategic_prioritization()
                self.run_designops_audit()
                self.run_cross_functional_handoff_simulation()
            elif choice == "5":
                print(f"{CLR_GREEN}Exiting. Product strategy simulation session closed.{CLR_RESET}")
                break
            else:
                print(f"{CLR_RED}Invalid option selected. Please choose between 1 and 5.{CLR_RESET}")
            print("-" * 78)

def main():
    simulator = ProductStrategySimulator()
    simulator.run_interactive_menu()

if __name__ == "__main__":
    main()

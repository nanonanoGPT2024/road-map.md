#!/usr/bin/env python3
"""
Lab Exercise: Design System Governance, Telemetry & Multi-Brand Scaling Simulator
BAB 10: Governance, Telemetry, and Scaling Across Organizations

Simulates:
1. Component & Token Telemetry Tracking (Adoption Rate, Detachment Ratio, Drift).
2. RFC Governance Lifecycle & Breaking Change Blast Radius Analysis.
3. Multi-Brand Token Theme Parity & Compliance Auditing across Teams/Repos.
"""

import sys
import time
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Set

# Terminal ANSI Styling
class Style:
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
    BG_MAGENTA = "\033[45m"


class RFCStatus(Enum):
    PROPOSED = "PROPOSED"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    DEPRECATED = "DEPRECATED"
    SUNSET = "SUNSET"


@dataclass
class RFCRecord:
    rfc_id: str
    title: str
    target_component: str
    status: RFCStatus
    is_breaking: bool
    replacement_guideline: str
    affected_repos: List[str] = field(default_factory=list)


@dataclass
class TelemetryEntry:
    repo_name: str
    team_name: str
    component_name: str
    version_used: str
    import_count: int
    detachment_count: int
    hardcoded_overrides: int


@dataclass
class BrandTheme:
    brand_id: str
    tokens: Dict[str, str]


class DesignSystemGovernanceTelemetrySystem:
    def __init__(self):
        self.rfcs: Dict[str, RFCRecord] = {}
        self.telemetry_data: List[TelemetryEntry] = []
        self.brand_themes: Dict[str, BrandTheme] = {}
        self._seed_initial_state()

    def _seed_initial_state(self):
        # 1. Initial RFCs
        self.rfcs["RFC-101"] = RFCRecord(
            rfc_id="RFC-101",
            title="Deprecate Legacy v1.x FlatButton in favor of DS Button v3",
            target_component="FlatButton",
            status=RFCStatus.DEPRECATED,
            is_breaking=True,
            replacement_guideline="Migrate to `@ds/core/Button` with variant='flat'",
            affected_repos=["checkout-web", "merchant-portal", "mobile-seller"]
        )
        self.rfcs["RFC-102"] = RFCRecord(
            rfc_id="RFC-102",
            title="Introduce Adaptive Elevation Tokens for Multi-Brand Dark Mode",
            target_component="ElevationTokens",
            status=RFCStatus.APPROVED,
            is_breaking=False,
            replacement_guideline="Update `@ds/tokens` to >= 3.2.0 and use `ds.elevation.surface`",
            affected_repos=["search-service-ui", "checkout-web", "customer-dashboard"]
        )

        # 2. Seed Telemetry (Simulated AST parser ingestion from remote git repos)
        self.telemetry_data = [
            TelemetryEntry("checkout-web", "Checkout Squad", "FlatButton", "1.4.2", 48, 12, 19),
            TelemetryEntry("checkout-web", "Checkout Squad", "Button", "3.1.0", 112, 2, 4),
            TelemetryEntry("checkout-web", "Checkout Squad", "InputText", "3.0.1", 35, 1, 0),
            TelemetryEntry("merchant-portal", "B2B Core", "FlatButton", "1.2.0", 86, 28, 42),
            TelemetryEntry("merchant-portal", "B2B Core", "DataGrid", "2.8.0", 14, 0, 5),
            TelemetryEntry("search-service-ui", "Discovery Team", "Button", "3.2.0", 65, 0, 1),
            TelemetryEntry("search-service-ui", "Discovery Team", "SearchAutoComplete", "3.2.0", 22, 1, 3),
            TelemetryEntry("mobile-seller", "Omnichannel", "FlatButton", "1.5.0", 30, 9, 14),
            TelemetryEntry("customer-dashboard", "Growth Squad", "Button", "3.2.0", 94, 3, 2),
        ]

        # 3. Seed Multi-Brand Token Systems
        self.brand_themes["brand-fintech"] = BrandTheme(
            brand_id="FinTech Pro",
            tokens={
                "color.primary": "#0A2540",
                "color.accent": "#00D4B2",
                "radius.sm": "4px",
                "radius.md": "8px",
                "font.family": "Inter, sans-serif"
            }
        )
        self.brand_themes["brand-retail"] = BrandTheme(
            brand_id="Retail Pulse",
            tokens={
                "color.primary": "#E60023",
                "color.accent": "#FFD700",
                "radius.sm": "12px",
                "radius.md": "20px",
                "font.family": "Poppins, sans-serif"
            }
        )

    def print_header(self, title: str):
        print(f"\n{Style.BG_BLUE}{Style.WHITE}{Style.BOLD} === {title} === {Style.RESET}\n")

    def run_telemetry_scan(self):
        self.print_header("REAL-TIME DESIGN SYSTEM TELEMETRY INGESTION")
        print(f"{Style.CYAN}[INFO]{Style.RESET} Querying telemetry logs from connected repositories...\n")
        time.sleep(0.3)

        total_imports = sum(e.import_count for e in self.telemetry_data)
        total_detachments = sum(e.detachment_count for e in self.telemetry_data)
        total_overrides = sum(e.hardcoded_overrides for e in self.telemetry_data)

        print(f"{Style.BOLD}{'Repository':<22} | {'Team':<18} | {'Component':<18} | {'Ver':<8} | {'Imports':<8} | {'Detached':<8} | {'Overrides':<8}{Style.RESET}")
        print("-" * 105)

        for entry in self.telemetry_data:
            c_color = Style.RED if entry.component_name == "FlatButton" else Style.GREEN
            det_color = Style.RED if entry.detachment_count > 10 else Style.YELLOW if entry.detachment_count > 0 else Style.GREEN
            print(f"{entry.repo_name:<22} | {entry.team_name:<18} | {c_color}{entry.component_name:<18}{Style.RESET} | {entry.version_used:<8} | {entry.import_count:<8} | {det_color}{entry.detachment_count:<8}{Style.RESET} | {entry.hardcoded_overrides:<8}")

        print("-" * 105)
        print(f"{Style.BOLD}Total Component Instances:{Style.RESET} {total_imports}")
        detachment_rate = (total_detachments / total_imports * 100) if total_imports else 0.0
        drift_rate = (total_overrides / total_imports * 100) if total_imports else 0.0

        det_style = Style.GREEN if detachment_rate < 5 else (Style.YELLOW if detachment_rate < 15 else Style.RED)
        print(f"{Style.BOLD}System Detachment Rate:{Style.RESET} {det_style}{detachment_rate:.2f}%{Style.RESET} (Target < 5.0%)")
        print(f"{Style.BOLD}Token Override / Drift Rate:{Style.RESET} {Style.YELLOW}{drift_rate:.2f}%{Style.RESET}")

    def evaluate_rfc_governance(self):
        self.print_header("RFC GOVERNANCE & DEPRECATION IMPACT ANALYSIS")
        print(f"{Style.MAGENTA}[REGISTRY]{Style.RESET} Registered RFC Proposals and Migration Gates:\n")

        for rfc_id, rfc in self.rfcs.items():
            status_color = Style.GREEN if rfc.status == RFCStatus.APPROVED else (Style.YELLOW if rfc.status == RFCStatus.DEPRECATED else Style.CYAN)
            breaking_badge = f"{Style.RED}[BREAKING]{Style.RESET}" if rfc.is_breaking else f"{Style.GREEN}[NON-BREAKING]{Style.RESET}"
            
            print(f"• {Style.BOLD}{rfc.rfc_id}: {rfc.title}{Style.RESET}")
            print(f"  Target: {rfc.target_component} | Status: {status_color}{rfc.status.value}{Style.RESET} | Severity: {breaking_badge}")
            print(f"  Migration Action: {Style.DIM}{rfc.replacement_guideline}{Style.RESET}")
            
            # Calculate blast radius from telemetry
            impacted_instances = [e for e in self.telemetry_data if e.component_name == rfc.target_component]
            affected_repos = {e.repo_name for e in impacted_instances}
            total_affected_instances = sum(e.import_count for e in impacted_instances)
            
            print(f"  {Style.BOLD}Blast Radius:{Style.RESET} {len(affected_repos)} repos affected ({total_affected_instances} active call sites)")
            if affected_repos:
                print(f"  Affected Repositories: {Style.RED}{', '.join(affected_repos)}{Style.RESET}")
            print()

    def audit_multibrand_tokens(self):
        self.print_header("MULTI-BRAND TOKEN PARITY & SCALING AUDIT")
        print(f"{Style.CYAN}[INFO]{Style.RESET} Comparing token trees across configured organization brands:\n")

        all_keys: Set[str] = set()
        for b in self.brand_themes.values():
            all_keys.update(b.tokens.keys())

        header = f"{Style.BOLD}{'Token Designator':<25}"
        for b_key in self.brand_themes.keys():
            header += f" | {b_key:<18}"
        header += f" | {'Parity Check':<15}{Style.RESET}"
        print(header)
        print("-" * 75)

        for token in sorted(all_keys):
            row = f"{token:<25}"
            is_complete = True
            for b_id, b_data in self.brand_themes.items():
                val = b_data.tokens.get(token)
                if val:
                    row += f" | {val:<18}"
                else:
                    is_complete = False
                    row += f" | {Style.RED}{'MISSING':<18}{Style.RESET}"
            status = f"{Style.GREEN}OK{Style.RESET}" if is_complete else f"{Style.RED}DRIFT{Style.RESET}"
            row += f" | {status:<15}"
            print(row)

        print("-" * 75)
        print(f"{Style.GREEN}✓ All core token contracts valid for automated build pipelines.{Style.RESET}")

    def submit_interactive_rfc(self):
        self.print_header("INTERACTIVE RFC SUBMISSION PORTAL")
        print(f"{Style.CYAN}Submit an architectural proposal or deprecation request:{Style.RESET}")
        
        rfc_id = f"RFC-{len(self.rfcs) + 101}"
        title = input(f"{Style.BOLD}Enter RFC Title: {Style.RESET}").strip()
        if not title:
            title = "Proposed System Design System Evolution"

        component = input(f"{Style.BOLD}Target Component / Token Category: {Style.RESET}").strip()
        if not component:
            component = "CardContainer"

        breaking_in = input(f"{Style.BOLD}Is this a Breaking Change? (y/n): {Style.RESET}").strip().lower()
        is_breaking = breaking_in.startswith('y')

        guideline = input(f"{Style.BOLD}Migration Guide / Replacement Directive: {Style.RESET}").strip()
        if not guideline:
            guideline = "Upgrade to standard package namespace and run codemod `npx @ds/codemod-v3`"

        # Register RFC
        new_rfc = RFCRecord(
            rfc_id=rfc_id,
            title=title,
            target_component=component,
            status=RFCStatus.PROPOSED,
            is_breaking=is_breaking,
            replacement_guideline=guideline,
            affected_repos=[e.repo_name for e in self.telemetry_data if e.component_name == component]
        )
        self.rfcs[rfc_id] = new_rfc

        print(f"\n{Style.GREEN}✓ {rfc_id} registered successfully with status {new_rfc.status.value}!{Style.RESET}")
        print(f"Policy Engine: Telemetry scanning detected {len(new_rfc.affected_repos)} immediately impacted codebase(s).")


def run_demo_mode(system: DesignSystemGovernanceTelemetrySystem):
    """Automated demonstration mode for non-interactive runners or fast CI checks."""
    print(f"\n{Style.BOLD}{Style.WHITE}{Style.BG_MAGENTA} --- AUTO-RUN TELEMETRY & GOVERNANCE PIPELINE --- {Style.RESET}\n")
    system.run_telemetry_scan()
    time.sleep(0.2)
    system.evaluate_rfc_governance()
    time.sleep(0.2)
    system.audit_multibrand_tokens()
    print(f"\n{Style.GREEN}{Style.BOLD}✓ Full Design System Governance Simulation Completed Successfully!{Style.RESET}\n")


def main():
    system = DesignSystemGovernanceTelemetrySystem()

    # Detect if terminal is interactive or run in automated mode
    if len(sys.argv) > 1 and sys.argv[1] in ("--demo", "-d", "--automated") or not sys.stdin.isatty():
        run_demo_mode(system)
        return

    while True:
        print("\n" + "=" * 60)
        print(f"{Style.BOLD}{Style.CYAN}DESIGN SYSTEM GOVERNANCE & TELEMETRY CLI (BAB 10){Style.RESET}")
        print("=" * 60)
        print(" [1] Run Organization Telemetry Ingestion & Adoption Scan")
        print(" [2] Inspect RFC Governance Registry & Deprecation Blast Radius")
        print(" [3] Audit Multi-Brand Token Theme Parity & Scaling")
        print(" [4] Propose New Governance RFC (Interactive Portal)")
        print(" [5] Execute Full Automated Suite (Demo Run)")
        print(" [0] Exit Simulator")
        print("-" * 60)

        choice = input(f"{Style.BOLD}Select an operation (0-5): {Style.RESET}").strip()

        if choice == "1":
            system.run_telemetry_scan()
        elif choice == "2":
            system.evaluate_rfc_governance()
        elif choice == "3":
            system.audit_multibrand_tokens()
        elif choice == "4":
            system.submit_interactive_rfc()
        elif choice == "5":
            run_demo_mode(system)
        elif choice == "0":
            print(f"\n{Style.GREEN}Shutting down Governance & Telemetry Simulator. Goodbye!{Style.RESET}\n")
            break
        else:
            print(f"{Style.RED}Invalid selection. Please choose an option between 0 and 5.{Style.RESET}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Lab Exercise: Next.js E2E Testing Strategy & CI/CD Pipeline Simulation
Bab 09: Strategi Pengujian End-to-End dan Automasi CI/CD
"""

import os
import sys
import time
import random
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional

# ANSI Color Codes
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    DIM = "\033[2m"

class TestStatus(Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    RETRY = "RETRYING"
    SKIPPED = "SKIPPED"

@dataclass
class E2ETestCase:
    name: str
    route: str
    action_description: str
    target_selector: str
    expected_state: str
    mock_api: bool = False
    flaky_rate: float = 0.0
    status: TestStatus = TestStatus.SKIPPED
    duration_ms: int = 0
    trace_artifact: Optional[str] = None

@dataclass
class CIPipelineStage:
    name: str
    command: str
    timeout_sec: int
    parallel_jobs: int = 1
    artifacts: List[str] = field(default_factory=list)

class NextjsE2ESimulator:
    def __init__(self):
        self.app_name = "nextjs-enterprise-portal"
        self.version = "14.2.5 (App Router)"
        self.playwright_workers = 4
        self.ci_commit_sha = "9f8b2a1"

    def print_header(self, title: str):
        print(f"\n{Color.CYAN}{Color.BOLD}{'=' * 65}")
        print(f" {title.center(63)} ")
        print(f"{'=' * 65}{Color.RESET}\n")

    def run_e2e_suite(self, enable_mocking: bool = True):
        self.print_header("PLAYWRIGHT E2E TEST RUNNER (App Router)")
        print(f"{Color.DIM}[Config] Playwright v1.45.0 | Workers: {self.playwright_workers} | BaseURL: http://localhost:3000{Color.RESET}")
        print(f"{Color.DIM}[Environment] NEXT_PUBLIC_API_MOCK={'ENABLED' if enable_mocking else 'DISABLED'}{Color.RESET}\n")

        test_cases = [
            E2ETestCase(
                name="auth/login.spec.ts: Valid Credential Redirect",
                route="/login",
                action_description="Fill email, password, submit form and verify session cookie",
                target_selector="button[data-testid='submit-login']",
                expected_state="URL redirects to /dashboard with session token",
                mock_api=enable_mocking,
                flaky_rate=0.05
            ),
            E2ETestCase(
                name="dashboard/server-components.spec.ts: Hydration & SSR Data",
                route="/dashboard",
                action_description="Evaluate React Server Component streaming payload (RSC)",
                target_selector="div#analytics-summary-card",
                expected_state="Suspense fallback swaps to populated metrics table",
                mock_api=enable_mocking,
                flaky_rate=0.10
            ),
            E2ETestCase(
                name="api/checkout.spec.ts: Route Handler Network Mocking",
                route="/cart/checkout",
                action_description="Intercept page.route('**/api/payment') with 200 OK fixture",
                target_selector="button[data-testid='confirm-payment']",
                expected_state="Display confirmation modal and clear localStorage cart",
                mock_api=enable_mocking,
                flaky_rate=0.0
            ),
            E2ETestCase(
                name="i18n/locale-switch.spec.ts: Dynamic Middleware Routing",
                route="/id/products/item-42",
                action_description="Switch language selector to 'en-US' and verify URL rewritten",
                target_selector="select#locale-picker",
                expected_state="NextResponse.rewrite preserves query params and metadata",
                mock_api=enable_mocking,
                flaky_rate=0.0
            )
        ]

        passed = 0
        failed = 0

        for test in test_cases:
            print(f"  {Color.BOLD}RUNNING:{Color.RESET} {Color.CYAN}{test.name}{Color.RESET}")
            print(f"    {Color.DIM}Target:{Color.RESET} {test.route} | {Color.DIM}Action:{Color.RESET} {test.action_description}")
            time.sleep(0.35)

            # Determine pass/fail based on flaky_rate
            is_failure = random.random() < test.flaky_rate
            duration = random.randint(180, 850)
            test.duration_ms = duration

            if not is_failure:
                test.status = TestStatus.PASSED
                passed += 1
                status_badge = f"{Color.GREEN}[PASSED]{Color.RESET}"
            else:
                test.status = TestStatus.FAILED
                failed += 1
                test.trace_artifact = f"traces/{test.name.split(':')[0]}-failure.zip"
                status_badge = f"{Color.RED}[FAILED]{Color.RESET}"

            print(f"    {status_badge} Execution: {duration}ms | Expected: {test.expected_state}")
            if test.trace_artifact:
                print(f"    {Color.YELLOW}Artifact Captured:{Color.RESET} {test.trace_artifact} (Playwright Trace Viewer)")
            print()

        summary_color = Color.GREEN if failed == 0 else Color.RED
        print(f"{summary_color}{Color.BOLD}Test Results: {passed} passed, {failed} failed in {sum(t.duration_ms for t in test_cases)}ms{Color.RESET}\n")

    def run_ci_cd_pipeline(self):
        self.print_header(f"GITHUB ACTIONS CI/CD WORKFLOW: [Run #{random.randint(100, 999)} - Commit {self.ci_commit_sha}]")
        
        stages = [
            CIPipelineStage(
                name="1. Static Analysis & Lint",
                command="next lint && biome check --diagnostic-level=error",
                timeout_sec=60
            ),
            CIPipelineStage(
                name="2. TypeScript Strict Type-Check",
                command="tsc --noEmit --project tsconfig.json",
                timeout_sec=90
            ),
            CIPipelineStage(
                name="3. Unit & Component Tests (Vitest + RTL)",
                command="vitest run --coverage --threads=true",
                timeout_sec=120,
                artifacts=["coverage/lcov.info"]
            ),
            CIPipelineStage(
                name="4. Next.js Production Build",
                command="next build (Turbopack standalone output)",
                timeout_sec=180,
                artifacts=[".next/standalone", ".next/static"]
            ),
            CIPipelineStage(
                name="5. Matrix E2E Sharding (Playwright)",
                command="playwright test --shard=1/2 & playwright test --shard=2/2",
                timeout_sec=300,
                parallel_jobs=2,
                artifacts=["playwright-report/index.html"]
            ),
            CIPipelineStage(
                name="6. Preview Deployment Gatekeeper",
                command="vercel deploy --prebuilt --token=$VERCEL_TOKEN",
                timeout_sec=120,
                artifacts=["https://enterprise-portal-git-feat-pr-92.vercel.app"]
            )
        ]

        total_elapsed = 0
        for idx, stage in enumerate(stages, 1):
            print(f"{Color.BOLD}[Job {idx}/{len(stages)}] {stage.name}{Color.RESET}")
            print(f"  {Color.DIM}$ {stage.command}{Color.RESET}")
            step_duration = random.randint(3, 8)
            time.sleep(0.4)
            total_elapsed += step_duration

            print(f"  {Color.GREEN}✓ Completed in {step_duration}s{Color.RESET}")
            if stage.parallel_jobs > 1:
                print(f"    {Color.MAGENTA}↳ Parallelism: Executed across {stage.parallel_jobs} matrix runners{Color.RESET}")
            if stage.artifacts:
                for art in stage.artifacts:
                    print(f"    {Color.CYAN}↳ Uploaded Artifact:{Color.RESET} {art}")
            print()

        print(f"{Color.GREEN}{Color.BOLD}✔ CI/CD Workflow Succeeded! Total Build Time: {total_elapsed}s{Color.RESET}\n")

    def simulate_flaky_retry(self):
        self.print_header("FLAKY TEST SELF-HEALING & RETRY MECHANISM")
        print(f"{Color.YELLOW}Simulating transient network jitter on Next.js Server Action invocation...{Color.RESET}\n")

        test_name = "orders/server-action-checkout.spec.ts"
        attempts = 3
        current_attempt = 1
        success = False

        while current_attempt <= attempts:
            print(f"Attempt #{current_attempt}/{attempts} for {Color.CYAN}{test_name}{Color.RESET}:")
            time.sleep(0.4)
            
            # First attempt fails, subsequent attempt heals
            if current_attempt < 2:
                print(f"  {Color.RED}✖ Error: Timeout 5000ms exceeded while waiting for Server Action response{Color.RESET}")
                print(f"  {Color.YELLOW}↳ Playwright automatic retry triggered (retry #{current_attempt})...{Color.RESET}\n")
                current_attempt += 1
            else:
                print(f"  {Color.GREEN}✔ Target locator resolved: confirmation badge visible in DOM [320ms]{Color.RESET}")
                print(f"  {Color.GREEN}↳ Test Passed on retry attempt #{current_attempt}!{Color.RESET}\n")
                success = True
                break

        if success:
            print(f"{Color.CYAN}{Color.BOLD}[Quarantine Advisory]: Marked test as FLAKY in CI metadata.{Color.RESET}")
            print(f"{Color.DIM}Trace uploaded to Playwright Trace Viewer for root-cause inspection.{Color.RESET}\n")

    def run_interactive_menu(self):
        while True:
            self.print_header("NEXT.JS E2E TESTING & CI/CD PIPELINE LAB")
            print(f"1. Run Playwright E2E Suite (Mocked App Router API Routes)")
            print(f"2. Run Playwright E2E Suite (Un-mocked / Real Backend Latency)")
            print(f"3. Simulate GitHub Actions Matrix Pipeline (Lint -> Build -> Sharded E2E -> Deploy)")
            print(f"4. Demonstrate Flaky Test Auto-Retry & Trace Capture")
            print(f"5. Run Full CI/CD Smoke & Quality Gate Check")
            print(f"6. Exit")
            print(f"{'-' * 65}")

            if not sys.stdin.isatty():
                # Non-interactive mode (e.g. headless CI check)
                print(f"{Color.YELLOW}[Non-interactive detected] Running Automated Smoke Check...{Color.RESET}")
                self.run_e2e_suite(enable_mocking=True)
                self.run_ci_cd_pipeline()
                self.simulate_flaky_retry()
                print(f"{Color.GREEN}Automated execution finished successfully.{Color.RESET}")
                break

            choice = input(f"{Color.BOLD}Select an option (1-6): {Color.RESET}").strip()
            if choice == "1":
                self.run_e2e_suite(enable_mocking=True)
            elif choice == "2":
                self.run_e2e_suite(enable_mocking=False)
            elif choice == "3":
                self.run_ci_cd_pipeline()
            elif choice == "4":
                self.simulate_flaky_retry()
            elif choice == "5":
                self.run_e2e_suite(enable_mocking=True)
                self.run_ci_cd_pipeline()
                self.simulate_flaky_retry()
            elif choice == "6":
                print(f"\n{Color.CYAN}Exiting Lab Exercise. Happy testing!{Color.RESET}\n")
                break
            else:
                print(f"{Color.RED}Invalid selection. Please choose 1-6.{Color.RESET}")

if __name__ == "__main__":
    simulator = NextjsE2ESimulator()
    simulator.run_interactive_menu()

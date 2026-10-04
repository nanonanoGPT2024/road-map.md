#!/usr/bin/env python3
"""
Lab Exercise M02: AWS Telemetry, Observability, and Cloud FinOps Simulator
BAB-09-Telemetry-Observability-Cloud-FinOps

A comprehensive, self-contained interactive production simulator demonstrating:
- Embedded Metric Format (EMF) & CloudWatch Custom Metrics ingestion
- Distributed Tracing & AWS X-Ray tail-based sampling
- FinOps Cost Allocation, Compute Optimizer recommendations, and Unit Economics
- Automated anomaly detection & Budget circuit-breaker remediation
"""

import sys
import time
import json
import random
import math
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

# ANSI Color Codes for Rich Terminal Display
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
BG_DARK = "\033[40m"


def header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 75}{RESET}")
    print(f"{BOLD}{CYAN}>>> {title.center(67)} <<<{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 75}{RESET}\n")


def status_badge(status: str) -> str:
    if status in ("OK", "OPTIMAL", "HEALTHY", "SAVED"):
        return f"{GREEN}[{status}]{RESET}"
    if status in ("WARN", "OVERSIZED", "NEAR_BUDGET"):
        return f"{YELLOW}[{status}]{RESET}"
    return f"{RED}[{status}]{RESET}"


@dataclass
class ServiceTraceSegment:
    segment_id: str
    service_name: str
    start_time: float
    end_time: float
    duration_ms: float
    http_status: int
    fault: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EC2ResourceProfile:
    instance_id: str
    instance_type: str
    vcpus: int
    memory_gib: float
    monthly_cost_usd: float
    avg_cpu_utilization: float
    avg_memory_utilization: float
    recommended_type: str
    projected_monthly_cost: float


class TelemetryFinOpsSimulator:
    def __init__(self):
        self.monthly_budget_usd = 2500.0
        self.current_spend_usd = 2145.50
        self.unit_cost_target_per_order = 0.045
        self.total_orders_processed = 58240
        self.instances: List[EC2ResourceProfile] = [
            EC2ResourceProfile("i-0a89d91f2c", "c5.4xlarge", 16, 32.0, 496.40, 14.2, 22.0, "c5.xlarge", 124.10),
            EC2ResourceProfile("i-07bb53c48e", "r5.2xlarge", 8, 64.0, 367.92, 11.5, 31.5, "r5.large", 91.98),
            EC2ResourceProfile("i-031f41da02", "m5.large", 2, 8.0, 69.35, 78.4, 82.1, "m5.large", 69.35),
            EC2ResourceProfile("i-0fa820e176", "t3.medium", 2, 4.0, 30.36, 42.0, 58.0, "t3.medium", 30.36),
            EC2ResourceProfile("i-0e994cb310", "c5.2xlarge", 8, 16.0, 248.20, 8.1, 18.4, "t4g.xlarge", 97.82),
        ]

    def emit_emf_metric_sample(self) -> None:
        header("1. Ingestion: CloudWatch Embedded Metric Format (EMF)")
        print(f"{DIM}Generating high-resolution JSON log event adhering to CloudWatch EMF spec...{RESET}\n")

        latency = round(random.uniform(42.5, 385.0), 2)
        status_code = random.choice([200, 200, 200, 201, 204, 400, 503])
        orders = random.randint(1, 8)
        cost_allocation_tag = random.choice(["Team-Checkout", "Team-Catalog", "Team-Payments"])

        emf_payload = {
            "_aws": {
                "Timestamp": int(time.time() * 1000),
                "CloudWatchMetrics": [
                    {
                        "Namespace": "Production/ECommerce",
                        "Dimensions": [["Environment", "CostCenter", "Service"]],
                        "Metrics": [
                            {"Name": "OrderProcessingLatency", "Unit": "Milliseconds"},
                            {"Name": "OrderCount", "Unit": "Count"},
                            {"Name": "EstimatedTransactionCostUSD", "Unit": "None"},
                        ],
                    }
                ],
            },
            "Environment": "production-us-east-1",
            "CostCenter": cost_allocation_tag,
            "Service": "CheckoutService",
            "RequestId": f"req-{random.randint(100000, 999999)}",
            "StatusCode": status_code,
            "OrderProcessingLatency": latency,
            "OrderCount": orders,
            "EstimatedTransactionCostUSD": round(orders * 0.038, 4),
        }

        formatted_json = json.dumps(emf_payload, indent=2)
        print(f"{BOLD}{GREEN}[EMF LOG PAYLOAD DISPATCHED]{RESET}")
        print(f"{WHITE}{formatted_json}{RESET}\n")

        print(f"{BOLD}Telemetry Engine Parser:{RESET}")
        print(f" -> Dimension Key : {MAGENTA}Environment=production-us-east-1, CostCenter={cost_allocation_tag}{RESET}")
        print(f" -> High-Res Metric: {YELLOW}Latency = {latency} ms{RESET} | Count = {orders}")
        if latency > 300:
            print(f" -> {RED}[ALARM TRIGGERED] Metric Breached Dynamic Anomaly Threshold (>300ms){RESET}")
        else:
            print(f" -> {GREEN}[HEALTHY] Latency metric within SLA 99.9 percentile bounds.{RESET}")

    def simulate_distributed_trace(self) -> None:
        header("2. Distributed Tracing: AWS X-Ray Trace Graph & Tail-Sampling")
        print(f"{DIM}Simulating multi-tier microservice call with tail-based sampling...{RESET}\n")

        now = time.time()
        trace_id = f"1-{hex(int(now))[2:]}-{hex(random.getrandbits(96))[2:]}"
        print(f"{BOLD}Trace ID: {WHITE}{trace_id}{RESET}\n")

        tiers = [
            ("API-Gateway", 12.4, 200, False),
            ("CheckoutLambda", 85.2, 200, False),
            ("OrderService-ECS", 145.8, 200, False),
            ("PaymentGateway-Adapter", 220.6, 504 if random.random() < 0.35 else 200, False),
            ("DynamoDB-OrderTable", 18.1, 200, False),
        ]

        total_latency = 0.0
        has_error = False

        print(f"{BOLD}{'SERVICE':<25} | {'LATENCY':<12} | {'HTTP':<8} | {'TIMELINE VISUALIZATION'}{RESET}")
        print("-" * 75)

        for name, base_lat, code, fault in tiers:
            jitter = round(base_lat + random.uniform(-5.0, 25.0), 1)
            total_latency += jitter
            is_fault = (code >= 500)
            if is_fault:
                has_error = True

            bar_len = int(jitter / 15)
            bar_color = RED if is_fault else (YELLOW if jitter > 100 else GREEN)
            bar_graph = f"{bar_color}{'#' * max(1, bar_len)}{RESET}"

            badge = f"{RED}{code}{RESET}" if is_fault else f"{GREEN}{code}{RESET}"
            print(f"{CYAN}{name:<25}{RESET} | {jitter:>8.1f} ms | {badge:<8} | {bar_graph}")

        print("-" * 75)
        print(f"{BOLD}Total End-to-End Latency: {total_latency:.1f} ms{RESET}")

        if has_error:
            print(f"{RED}[TAIL SAMPLING DECISION]: KEEP (Error status captured in downstream Payment Gateway){RESET}")
            print(f"{YELLOW}Root Cause Analysis: DynamoDB writes queued; downstream partner payment gateway timed out.{RESET}")
        else:
            sample_rate = 0.05
            print(f"{GREEN}[TAIL SAMPLING DECISION]: 200 OK - Indexed under 5% normal traffic reservoir sampling.{RESET}")

    def run_finops_assessment(self) -> None:
        header("3. Cloud FinOps: AWS Compute Optimizer & Unit Economics")
        print(f"{BOLD}Current Monthly AWS Budget:{RESET} ${self.monthly_budget_usd:.2f}")
        print(f"{BOLD}MTD Actual Spend           :{RESET} ${self.current_spend_usd:.2f} ({round((self.current_spend_usd/self.monthly_budget_usd)*100, 1)}% consumed)")
        print(f"{BOLD}Unit Economics (Cost/Order):{RESET} ${self.current_spend_usd / self.total_orders_processed:.4f} (Target: ${self.unit_cost_target_per_order:.4f})\n")

        print(f"{BOLD}{'INSTANCE ID':<13} | {'CURRENT':<12} | {'CPU%':<7} | {'MEM%':<7} | {'MONTHLY':<9} | {'RECOMMENDED':<12} | {'NEW COST':<9} | {'ACTION'}{RESET}")
        print("-" * 92)

        total_savings = 0.0
        for inst in self.instances:
            savings = inst.monthly_cost_usd - inst.projected_monthly_cost
            if savings > 0:
                action = f"{YELLOW}DOWNSIZE{RESET}"
                total_savings += savings
            else:
                action = f"{GREEN}OPTIMAL{RESET}"

            print(
                f"{WHITE}{inst.instance_id:<13}{RESET} | "
                f"{CYAN}{inst.instance_type:<12}{RESET} | "
                f"{inst.avg_cpu_utilization:>5.1f}% | "
                f"{inst.avg_memory_utilization:>5.1f}% | "
                f"${inst.monthly_cost_usd:>7.2f} | "
                f"{MAGENTA}{inst.recommended_type:<12}{RESET} | "
                f"${inst.projected_monthly_cost:>7.2f} | "
                f"{action}"
            )

        print("-" * 92)
        new_projected_spend = self.current_spend_usd - total_savings
        new_unit_cost = new_projected_spend / self.total_orders_processed
        print(f"{BOLD}{GREEN}FinOps Compute Optimization Summary:{RESET}")
        print(f" -> Total Actionable Monthly Savings : {BOLD}{GREEN}${total_savings:.2f}{RESET}")
        print(f" -> Projected Monthly Run-rate       : ${new_projected_spend:.2f} ({round((new_projected_spend/self.monthly_budget_usd)*100, 1)}% of budget)")
        print(f" -> Optimized Unit Cost per Order    : ${new_unit_cost:.4f} "
              f"({GREEN}SURPASSES TARGET!{RESET} by {round((self.unit_cost_target_per_order - new_unit_cost)/self.unit_cost_target_per_order * 100, 1)}%)\n")

    def simulate_anomaly_and_remediation(self) -> None:
        header("4. FinOps Auto-Remediation & CloudWatch Composite Alarm")
        print(f"{DIM}Injecting cost anomaly: Rogue runaway batch process detected in Auto-Scaling Group...{RESET}\n")

        print(f"[{time.strftime('%X')}] {YELLOW}[ALARM: CloudWatch Anomaly Detection]{RESET} Metric 'DailyCostUsd' exceeds expected 3-sigma band.")
        print(f"[{time.strftime('%X')}] {RED}[CRITICAL: AWS Budgets Alert]{RESET} Forecasted spend exceeds 105% threshold ($2,625.00).")
        print(f"[{time.strftime('%X')}] {CYAN}[SNS EventBridge Trigger]{RESET} Initiating Event-Driven FinOps Circuit Breaker Lambda...")

        time.sleep(0.8)
        print(f"[{time.strftime('%X')}] {MAGENTA}[EXECUTION]:{RESET} Terminating 2 unattached EBS volumes and switching 3 idle dev instances to STOPPED.")
        print(f"[{time.strftime('%X')}] {MAGENTA}[EXECUTION]:{RESET} Purchasing Savings Plans coverage for baseline c5 compute tier.")
        time.sleep(0.6)

        print(f"[{time.strftime('%X')}] {GREEN}[RESOLVED]:{RESET} Run-rate normalized. Cost anomaly mitigated without customer impact.\n")

    def interactive_menu(self) -> None:
        while True:
            print(f"\n{BOLD}{BG_DARK}{WHITE}  AWS TELEMETRY, OBSERVABILITY & FINOPS CONTROL PLANE  {RESET}")
            print("1. Ingest CloudWatch High-Resolution EMF Log Metric")
            print("2. Run Distributed Trace Analysis & Tail Sampling (AWS X-Ray)")
            print("3. Execute Compute Optimizer & FinOps Unit Economics Audit")
            print("4. Trigger Automated Cost Anomaly Circuit Breaker")
            print("5. Run Full Telemetry & FinOps Production Simulation")
            print("6. Exit Control Plane")

            try:
                choice = input(f"\n{BOLD}{CYAN}Select an action [1-6]: {RESET}").strip()
            except (KeyboardInterrupt, EOFError):
                print(f"\n{YELLOW}Terminating simulator session.{RESET}")
                break

            if choice == "1":
                self.emit_emf_metric_sample()
            elif choice == "2":
                self.simulate_distributed_trace()
            elif choice == "3":
                self.run_finops_assessment()
            elif choice == "4":
                self.simulate_anomaly_and_remediation()
            elif choice == "5":
                self.emit_emf_metric_sample()
                time.sleep(0.5)
                self.simulate_distributed_trace()
                time.sleep(0.5)
                self.run_finops_assessment()
                time.sleep(0.5)
                self.simulate_anomaly_and_remediation()
            elif choice == "6":
                print(f"{GREEN}Exiting. Telemetry & FinOps state preserved.{RESET}")
                break
            else:
                print(f"{RED}Invalid option selected. Please choose between 1 and 6.{RESET}")


if __name__ == "__main__":
    app = TelemetryFinOpsSimulator()
    if len(sys.argv) > 1 and sys.argv[1] == "--non-interactive":
        # Automated self-check mode for pipelines / tests
        app.emit_emf_metric_sample()
        app.simulate_distributed_trace()
        app.run_finops_assessment()
        app.simulate_anomaly_and_remediation()
    else:
        app.interactive_menu()

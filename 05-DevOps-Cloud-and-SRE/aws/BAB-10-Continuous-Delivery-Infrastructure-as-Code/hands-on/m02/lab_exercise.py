#!/usr/bin/env python3
"""
Lab Exercise M02: Advanced AWS Continuous Delivery & Infrastructure as Code (IaC) Simulation
BAB 10: Continuous Delivery & Infrastructure as Code

Features:
- AWS CodePipeline multi-stage progression (Source -> Build/Test -> IaC Diff/Changeset -> Canary Deploy -> Production Approval)
- IaC ChangeSet generator & drift detection simulation (CloudFormation / Terraform state engine)
- Weighted Canary Release simulation with ALB & CloudWatch synthetic alarms
- Automated Rollback triggering on SLO breach (P99 latency / 5xx error spikes)
- Interactive CLI with ANSI terminal visualization
"""

import sys
import time
import random
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict

# ANSI Terminal Colors
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
    BG_RED = "\033[41m"

class PipelineStatus(Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"

@dataclass
class StackResource:
    logical_id: str
    resource_type: str
    action: str  # Add, Modify, Destroy
    replacement: bool = False

@dataclass
class DeploymentMetric:
    step_percent: int
    error_rate: float
    p99_latency_ms: float
    healthy_host_count: int

class CDPipelineSimulator:
    def __init__(self, app_name: str = "prod-payment-service", version: str = "v2.4.0"):
        self.app_name = app_name
        self.version = version
        self.current_live_version = "v2.3.9"
        self.commit_sha = f"{random.getrandbits(28):07x}"
        self.stack_name = f"arn:aws:cloudformation:us-east-1:123456789012:stack/{app_name}-stack"
        self.pipeline_name = f"{app_name}-cicd-pipeline"
        
        self.changeset: List[StackResource] = [
            StackResource("PaymentApiALBListenerRule", "AWS::ElasticLoadBalancingV2::ListenerRule", "Modify"),
            StackResource("PaymentCanaryTargetGroup", "AWS::ElasticLoadBalancingV2::TargetGroup", "Add"),
            StackResource("PaymentEcsTaskDef", "AWS::ECS::TaskDefinition", "Modify", replacement=True),
            StackResource("PaymentServiceP99Alarm", "AWS::CloudWatch::Alarm", "Add"),
            StackResource("PaymentAppAutoscalingPolicy", "AWS::ApplicationAutoScaling::ScalingPolicy", "Modify"),
        ]

    def banner(self):
        print(f"{Color.CYAN}{'='*78}{Color.RESET}")
        print(f"{Color.BOLD}{Color.WHITE} [AWS CI/CD & IaC] Advanced Production Pipeline & Canary Deployment Engine{Color.RESET}")
        print(f"{Color.CYAN}{'='*78}{Color.RESET}")
        print(f" Target Application : {Color.BOLD}{self.app_name}{Color.RESET}")
        print(f" Target Version     : {Color.GREEN}{self.version}{Color.RESET} (from {Color.YELLOW}{self.current_live_version}{Color.RESET})")
        print(f" Commit SHA         : {Color.MAGENTA}{self.commit_sha}{Color.RESET}")
        print(f" AWS Region / Stack : us-east-1 / {self.stack_name}")
        print(f"{Color.CYAN}{'-'*78}{Color.RESET}\n")

    def stage_log(self, stage: str, msg: str, color=Color.BLUE):
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{Color.DIM}{timestamp}{Color.RESET}] {color}{Color.BOLD}[{stage:^16}]{Color.RESET} {msg}")

    def run_source_stage(self) -> bool:
        self.stage_log("Source", "Polling CodeCommit / GitHub Enterprise Webhook...", Color.CYAN)
        time.sleep(0.4)
        self.stage_log("Source", f"Artifact cloned: s3://artifacts-bucket/{self.app_name}/{self.commit_sha}.zip", Color.CYAN)
        self.stage_log("Source", "Triggered CodePipeline ID: 9f43c41a-e8d1-4db5-94bb-188829bf40cd", Color.GREEN)
        return True

    def run_build_and_unit_test(self) -> bool:
        self.stage_log("CodeBuild", "Provisioning build container (aws/codebuild/amazonlinux2-x86_64-standard:5.0)...", Color.BLUE)
        time.sleep(0.5)
        self.stage_log("CodeBuild", "Running Linting, Trivy Container Scan, and Unit Tests...", Color.BLUE)
        time.sleep(0.6)
        print(f"   {Color.GREEN}✔{Color.RESET} Security scan: 0 critical vulnerabilities found.")
        print(f"   {Color.GREEN}✔{Color.RESET} Unit tests: 148 passed, 0 failed, 100% test assertion.")
        print(f"   {Color.GREEN}✔{Color.RESET} Image pushed to ECR: 123456789012.dkr.ecr.us-east-1.amazonaws.com/{self.app_name}:{self.version}")
        return True

    def run_iac_diff_and_changeset(self) -> bool:
        self.stage_log("IaC Changeset", "Executing CloudFormation CreateChangeSet (CDK Synth / Cfn diff)...", Color.YELLOW)
        time.sleep(0.5)
        print(f"\n{Color.BOLD}CloudFormation ChangeSet Summary (Review Action Prior to Deployment):{Color.RESET}")
        print(f"{Color.DIM}{'-'*78}{Color.RESET}")
        print(f" {'Action':<10} | {'Logical ID':<30} | {'Type':<30} | {'Replacement':<6}")
        print(f"{Color.DIM}{'-'*78}{Color.RESET}")
        for r in self.changeset:
            action_color = Color.GREEN if r.action == "Add" else (Color.YELLOW if r.action == "Modify" else Color.RED)
            repl_str = f"{Color.RED}True{Color.RESET}" if r.replacement else "False"
            print(f" {action_color}{r.action:<10}{Color.RESET} | {r.logical_id:<30} | {r.resource_type:<30} | {repl_str}")
        print(f"{Color.DIM}{'-'*78}{Color.RESET}\n")
        self.stage_log("IaC Changeset", "ChangeSet created successfully with 0 destructive deletes.", Color.GREEN)
        return True

    def check_iac_drift(self):
        self.stage_log("Drift Detection", "Auditing live AWS resources against CloudFormation Template...", Color.MAGENTA)
        time.sleep(0.6)
        drift_found = random.choice([False, False, True])
        if drift_found:
            print(f"   {Color.YELLOW}⚠ WARNING: Infrastructure Drift Detected!{Color.RESET}")
            print(f"   - Resource: PaymentAppAutoscalingPolicy (Live: Min=4, Expected: Min=2)")
            print(f"   - Remediation: Pipeline will apply declarative GitOps baseline state.")
        else:
            print(f"   {Color.GREEN}✔ IN-SYNC:{Color.RESET} No external manual drift discovered.")

    def run_canary_deployment(self, simulate_failure: bool = False) -> bool:
        self.stage_log("Deploy", "Starting CodeDeploy Linear/Canary Routing Strategy...", Color.MAGENTA)
        canary_steps = [10, 25, 50, 100]
        
        for step in canary_steps:
            print(f"\n{Color.BOLD}{Color.BG_BLUE}[ TRAFFIC SHIFT: {step}% to {self.version} | {100-step}% to {self.current_live_version} ]{Color.RESET}")
            self.stage_log("ALB Weights", f"Adjusting Listener weights: Canary={step}%, Production={100-step}%", Color.CYAN)
            time.sleep(0.5)

            # Generate synthetic metrics
            if simulate_failure and step >= 25:
                error_rate = random.uniform(5.5, 9.8)
                latency = random.uniform(850.0, 1400.0)
                healthy_hosts = 2
            else:
                error_rate = random.uniform(0.01, 0.25)
                latency = random.uniform(45.0, 120.0)
                healthy_hosts = 6

            print(f"   ↳ {Color.WHITE}Metrics (CloudWatch):{Color.RESET} 5xx Error Rate={error_rate:.2f}%, P99 Latency={latency:.1f}ms, Healthy Hosts={healthy_hosts}/6")
            
            # Alarm evaluation
            if error_rate > 5.0 or latency > 500.0:
                print(f"   {Color.BG_RED}{Color.BOLD} 🚨 ALARM TRIGGERED: PaymentServiceP99Alarm in ALARM state! 🚨 {Color.RESET}")
                self.stage_log("Rollback", "Triggering CloudWatch Automated Rollback hook...", Color.RED)
                time.sleep(0.8)
                self.execute_automated_rollback()
                return False
            else:
                print(f"   {Color.GREEN}✔ Health Check Passed:{Color.RESET} Synthetic heartbeat check returned HTTP 200.")
                time.sleep(0.4)

        self.stage_log("Deploy", f"100% traffic shifted to {self.version}. Terminating old target group tasks...", Color.GREEN)
        return True

    def execute_automated_rollback(self):
        print(f"\n{Color.YELLOW}{'!'*78}{Color.RESET}")
        print(f"{Color.BOLD}{Color.RED}[AUTOMATED ROLLBACK ACTIVATED]{Color.RESET}")
        print(f" Reverting ALB weighted routing: 100% traffic routed back to {self.current_live_version}")
        print(f" CloudFormation executing: ROLLBACK_IN_PROGRESS on {self.stack_name}")
        time.sleep(0.6)
        print(f" De-registering canary tasks for {self.version}...")
        print(f"{Color.GREEN}✔ Rollback Complete: Service restored to healthy baseline {self.current_live_version}. Zero Downtime.{Color.RESET}")
        print(f"{Color.YELLOW}{'!'*78}{Color.RESET}\n")

    def run_full_pipeline(self, simulate_failure: bool = False):
        self.banner()
        self.stage_log("Pipeline", f"Initiating execution for commit {self.commit_sha}", Color.WHITE)
        time.sleep(0.3)
        
        if not self.run_source_stage():
            return
        if not self.run_build_and_unit_test():
            return
        if not self.run_iac_diff_and_changeset():
            return
        self.check_iac_drift()

        print(f"\n{Color.YELLOW}[Pipeline Gate: Production Canary Deployment Pre-flight]{Color.RESET}")
        success = self.run_canary_deployment(simulate_failure=simulate_failure)
        
        print(f"\n{Color.CYAN}{'='*78}{Color.RESET}")
        if success:
            print(f"{Color.BOLD}{Color.GREEN}🎉 PIPELINE SUCCEEDED: Deployment of {self.version} completed successfully!{Color.RESET}")
            print(f" Live Target Group: {self.app_name}-tg-prod (Healthy: 6/6)")
        else:
            print(f"{Color.BOLD}{Color.RED}❌ PIPELINE FAILED: Canary deployment failed health check & rolled back safely.{Color.RESET}")
            print(f" SRE Notification sent to SNS topic: arn:aws:sns:us-east-1:123456789012:sre-pagers")
        print(f"{Color.CYAN}{'='*78}{Color.RESET}\n")

def interactive_menu():
    simulator = CDPipelineSimulator()
    while True:
        print(f"{Color.BOLD}--- AWS Continuous Delivery & IaC Production Simulator ---{Color.RESET}")
        print("1) Run Standard Green Deployment (100% Success Path)")
        print("2) Run Failure & Automated Rollback Simulation (CloudWatch Alarm Trigger)")
        print("3) Inspect CloudFormation Template & Drift Diagnostics")
        print("4) Exit")
        choice = input(f"{Color.CYAN}Select option (1-4): {Color.RESET}").strip()

        if choice == "1":
            sim = CDPipelineSimulator(version="v2.4.0")
            sim.run_full_pipeline(simulate_failure=False)
        elif choice == "2":
            sim = CDPipelineSimulator(version="v2.4.1-rc.bad")
            sim.run_full_pipeline(simulate_failure=True)
        elif choice == "3":
            sim = CDPipelineSimulator()
            sim.banner()
            sim.run_iac_diff_and_changeset()
            sim.check_iac_drift()
        elif choice == "4":
            print(f"{Color.GREEN}Exiting AWS CI/CD Lab Exercise. Keep practicing!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Invalid choice. Please select 1, 2, 3, or 4.{Color.RESET}\n")

if __name__ == "__main__":
    interactive_menu()

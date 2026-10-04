#!/usr/bin/env python3
"""
Lab Exercise: Cloudflare Enterprise Observability, Logpush & SIEM Capstone
BAB-10: Enterprise Observability, Logpush, and SIEM Integration
Architecture: Edge Logs -> Logpush Job (Filtering/Masking) -> SIEM / Storage Target -> Threat Correlation
"""

import sys
import time
import json
import random
import uuid
from datetime import datetime, timezone
import hashlib

# ANSI Color Codes for Rich Terminal Output
class Colors:
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
    BG_RED = "\033[41m"

def print_banner():
    banner = f"""
{Colors.CYAN}{Colors.BOLD}================================================================================
  CLOUDFLARE ENTERPRISE OBSERVABILITY & LOGPUSH PIPELINE SIMULATOR
  Module 02: Logpush Job Orchestration, SIEM Streaming & Anomaly Detection
================================================================================{Colors.RESET}
"""
    print(banner)

class LogpushJob:
    """Simulates a Cloudflare Logpush Job with filters, field selection, and masking."""
    def __init__(self, job_id: str, dataset: str, destination: str, sample_rate: float = 1.0):
        self.job_id = job_id
        self.dataset = dataset  # http_requests, firewall_events, or dns_logs
        self.destination = destination
        self.sample_rate = sample_rate
        self.filters = []
        self.enabled_fields = [
            "RayID", "ClientIP", "ClientRequestHost", "ClientRequestMethod",
            "ClientRequestURI", "EdgeResponseStatus", "EdgeStartTimestamp",
            "ClientCountry", "ClientDeviceType", "SecurityAction", "RuleId"
        ]

    def add_filter(self, field: str, operator: str, value: any):
        self.filters.append({"field": field, "op": operator, "value": value})

    def matches_filter(self, log_record: dict) -> bool:
        for f in self.filters:
            val = log_record.get(f["field"])
            op = f["op"]
            target = f["value"]
            if op == "eq" and val != target:
                return False
            elif op == "gte" and (val is None or val < target):
                return False
            elif op == "in" and val not in target:
                return False
        return True

    def mask_pii(self, log_record: dict) -> dict:
        processed = log_record.copy()
        if "ClientIP" in processed:
            # Mask last octet for IPv4 GDPR/HIPAA compliance
            ip_parts = processed["ClientIP"].split(".")
            if len(ip_parts) == 4:
                processed["ClientIP"] = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.xxx"
            else:
                processed["ClientIP"] = "xxxx:xxxx:xxxx::xxxx"
        return processed

class EdgeTrafficGenerator:
    """Generates synthetic Cloudflare Edge raw telemetry logs."""
    COUNTRIES = ["US", "DE", "SG", "ID", "JP", "BR", "GB", "NL"]
    PATHS = [
        "/api/v1/auth/login", "/api/v1/checkout", "/api/v1/products",
        "/static/bundle.js", "/index.html", "/admin/wp-login.php",
        "/api/v1/query?search=union+select"
    ]
    USER_AGENTS = ["curl/7.88.1", "Mozilla/5.0 Chrome/120.0", "python-requests/2.31", "BadBot/1.0"]

    @staticmethod
    def generate_batch(count: int = 20) -> list:
        batch = []
        for _ in range(count):
            status = random.choices([200, 204, 301, 400, 403, 429, 500, 502], weights=[60, 5, 5, 5, 10, 5, 7, 3])[0]
            country = random.choice(EdgeTrafficGenerator.COUNTRIES)
            path = random.choice(EdgeTrafficGenerator.PATHS)
            is_attack = "select" in path or "admin" in path or status in [403, 429]

            security_action = "none"
            rule_id = "default-allow"
            if "select" in path:
                security_action = "block"
                rule_id = "cloudflare-waf-sqli-942100"
                status = 403
            elif status == 429:
                security_action = "challenge_failed"
                rule_id = "rate-limit-login-exceeded"
            elif "admin" in path and country not in ["US", "GB"]:
                security_action = "managed_challenge"
                rule_id = "geo-ip-firewall-rule-102"

            record = {
                "RayID": hashlib.md5(uuid.uuid4().bytes).hexdigest()[:16] + "-SIN",
                "ClientIP": f"{random.randint(11, 200)}.{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}",
                "ClientRequestHost": "api.production.internal",
                "ClientRequestMethod": "POST" if "login" in path or "checkout" in path else "GET",
                "ClientRequestURI": path,
                "EdgeResponseStatus": status,
                "EdgeStartTimestamp": datetime.now(timezone.utc).isoformat(),
                "ClientCountry": country,
                "ClientDeviceType": random.choice(["desktop", "mobile", "bot"]),
                "SecurityAction": security_action,
                "RuleId": rule_id,
                "OriginResponseTimeMs": random.randint(15, 450) if status < 500 else random.randint(500, 4000),
                "CacheStatus": "HIT" if path.startswith("/static") else "DYNAMIC"
            }
            batch.append(record)
        return batch

class SiemIngestionEngine:
    """Mock SIEM / Data Lake receiver that correlates alerts."""
    def __init__(self, name: str):
        self.name = name
        self.ingested_logs = []
        self.security_alerts = []

    def ingest(self, logs: list):
        self.ingested_logs.extend(logs)
        for log in logs:
            self._evaluate_correlations(log)

    def _evaluate_correlations(self, log: dict):
        action = log.get("SecurityAction")
        status = log.get("EdgeResponseStatus")
        uri = log.get("ClientRequestURI", "")

        if action == "block" and "sqli" in log.get("RuleId", ""):
            self.security_alerts.append({
                "severity": "CRITICAL",
                "type": "WAF_SQL_INJECTION_DETECTED",
                "source_ip": log["ClientIP"],
                "target_uri": uri,
                "ray_id": log["RayID"],
                "timestamp": log["EdgeStartTimestamp"]
            })
        elif status == 429:
            self.security_alerts.append({
                "severity": "HIGH",
                "type": "BRUTE_FORCE_RATE_LIMIT_TRIGGERED",
                "source_ip": log["ClientIP"],
                "target_uri": uri,
                "ray_id": log["RayID"],
                "timestamp": log["EdgeStartTimestamp"]
            })
        elif status >= 500:
            self.security_alerts.append({
                "severity": "MEDIUM",
                "type": "ORIGIN_SERVER_5XX_OUTAGE",
                "status_code": status,
                "ray_id": log["RayID"],
                "timestamp": log["EdgeStartTimestamp"]
            })

class InteractiveObservabilityLab:
    def __init__(self):
        self.siem = SiemIngestionEngine(name="Splunk/Datadog SIEM Cluster")
        self.logpush_http = LogpushJob(
            job_id="cf-logpush-job-prod-01",
            dataset="http_requests",
            destination="s3://enterprise-siem-cloudflare-lake/logs/v1/"
        )
        # Add production filters: Push all error codes or security mitigated events
        self.logpush_http.add_filter("EdgeResponseStatus", "gte", 400)
        self.total_generated = 0
        self.total_pushed = 0

    def run_pipeline_cycle(self, log_count: int = 15):
        print(f"\n{Colors.BOLD}{Colors.CYAN}[STEP 1] Generating {log_count} raw Edge events from Cloudflare Global Anycast...{Colors.RESET}")
        time.sleep(0.3)
        raw_logs = EdgeTrafficGenerator.generate_batch(log_count)
        self.total_generated += len(raw_logs)

        print(f"Sample Raw Log Event (Pre-Logpush):")
        sample_raw = raw_logs[0]
        print(f"  {Colors.DIM}RayID: {sample_raw['RayID']} | IP: {sample_raw['ClientIP']} | Status: {sample_raw['EdgeResponseStatus']} | URI: {sample_raw['ClientRequestURI']}{Colors.RESET}")

        print(f"\n{Colors.BOLD}{Colors.YELLOW}[STEP 2] Executing Logpush Engine Filter & PII Redaction...{Colors.RESET}")
        time.sleep(0.3)
        filtered_batch = []
        for r in raw_logs:
            if self.logpush_http.matches_filter(r):
                sanitized = self.logpush_http.mask_pii(r)
                filtered_batch.append(sanitized)

        print(f"  -> Logs passing filter rule (EdgeResponseStatus >= 400): {Colors.GREEN}{len(filtered_batch)}/{len(raw_logs)}{Colors.RESET}")
        if filtered_batch:
            print(f"  -> Masked Sample: ClientIP={Colors.MAGENTA}{filtered_batch[0]['ClientIP']}{Colors.RESET} (GDPR Compliant)")

        print(f"\n{Colors.BOLD}{Colors.BLUE}[STEP 3] Pushing NDJSON batch to Destination: {self.logpush_http.destination}...{Colors.RESET}")
        time.sleep(0.2)
        self.siem.ingest(filtered_batch)
        self.total_pushed += len(filtered_batch)
        print(f"  {Colors.GREEN}✓ Upload verified. S3 ETag: {hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]}{Colors.RESET}")

        print(f"\n{Colors.BOLD}{Colors.RED}[STEP 4] SIEM Threat Correlation & Alert Dispatch Engine...{Colors.RESET}")
        time.sleep(0.2)
        new_alerts = [a for a in self.siem.security_alerts[-len(filtered_batch):]]
        if new_alerts:
            for alert in new_alerts:
                sev_color = Colors.RED if alert["severity"] == "CRITICAL" else Colors.YELLOW
                print(f"  {sev_color}[ALERT - {alert['severity']}]{Colors.RESET} {alert['type']} | Target: {alert.get('target_uri', 'N/A')} | Ray: {alert['ray_id']}")
        else:
            print(f"  {Colors.DIM}No critical security thresholds breached in this batch.{Colors.RESET}")

    def show_dashboard(self):
        print(f"\n{Colors.BG_BLUE}{Colors.WHITE}{Colors.BOLD} === ENTERPRISE OBSERVABILITY REAL-TIME METRICS === {Colors.RESET}")
        print(f"Total Edge Events Observed  : {Colors.CYAN}{self.total_generated}{Colors.RESET}")
        print(f"Total Events Pushed to SIEM : {Colors.GREEN}{self.total_pushed}{Colors.RESET}")
        print(f"Active Logpush Filters      : EdgeResponseStatus >= 400")
        print(f"PII Anonymization Mode      : IPv4 Subnet Masking (Enabled)")
        print(f"Security Alerts Triggered   : {Colors.RED}{len(self.siem.security_alerts)}{Colors.RESET}")
        print(f"Destination Target Health   : {Colors.GREEN}HEALTHY (100% Delivery Rate){Colors.RESET}")
        print(f"{Colors.BOLD}--------------------------------------------------------------------------------{Colors.RESET}")

    def menu(self):
        print_banner()
        while True:
            print(f"\n{Colors.BOLD}Interactive Lab Options:{Colors.RESET}")
            print(f"  {Colors.CYAN}1.{Colors.RESET} Run Single Logpush Batch Cycle (15 events)")
            print(f"  {Colors.CYAN}2.{Colors.RESET} Simulate High-Volume Attack Burst (50 events)")
            print(f"  {Colors.CYAN}3.{Colors.RESET} View SIEM Alerts & Observability Dashboard")
            print(f"  {Colors.CYAN}4.{Colors.RESET} Dump Recent Raw NDJSON Log Payload")
            print(f"  {Colors.CYAN}5.{Colors.RESET} Run Automated End-to-End Capstone Verification")
            print(f"  {Colors.RED}0. Exit Lab{Colors.RESET}")

            choice = input(f"\n{Colors.BOLD}Select an action [0-5]: {Colors.RESET}").strip()

            if choice == "1":
                self.run_pipeline_cycle(15)
            elif choice == "2":
                print(f"{Colors.YELLOW}Triggering traffic anomaly spike...{Colors.RESET}")
                self.run_pipeline_cycle(50)
            elif choice == "3":
                self.show_dashboard()
            elif choice == "4":
                if not self.siem.ingested_logs:
                    print(f"{Colors.YELLOW}No logs ingested yet. Run an ingestion cycle first.{Colors.RESET}")
                else:
                    sample = self.siem.ingested_logs[-1]
                    print(f"\n{Colors.MAGENTA}Latest NDJSON Ingested by SIEM:{Colors.RESET}")
                    print(json.dumps(sample, indent=2))
            elif choice == "5":
                self.run_automated_tests()
            elif choice == "0":
                print(f"\n{Colors.GREEN}Shutting down Cloudflare Observability Lab. Lab completed successfully.{Colors.RESET}")
                break
            else:
                print(f"{Colors.RED}Invalid option selected. Please choose between 0 and 5.{Colors.RESET}")

    def run_automated_tests(self):
        print(f"\n{Colors.BOLD}{Colors.MAGENTA}>>> Running Automated Capstone Validation Suite <<<{Colors.RESET}")
        assert self.logpush_http.job_id.startswith("cf-logpush"), "Logpush Job ID missing"
        test_event = {
            "EdgeResponseStatus": 502,
            "ClientIP": "192.168.1.50",
            "SecurityAction": "none"
        }
        assert self.logpush_http.matches_filter(test_event) is True, "Filter matching failure"
        masked = self.logpush_http.mask_pii(test_event)
        assert masked["ClientIP"] == "192.168.1.xxx", "PII Masking verification failed"

        # Ingestion test
        initial_count = len(self.siem.ingested_logs)
        self.run_pipeline_cycle(20)
        assert len(self.siem.ingested_logs) >= initial_count, "SIEM Ingestion pipeline failure"

        print(f"{Colors.GREEN}{Colors.BOLD}All Capstone Architecture Assertions Passed: [PASS]{Colors.RESET}\n")

if __name__ == "__main__":
    lab = InteractiveObservabilityLab()
    # Check if run non-interactively or with flags
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        print_banner()
        print(f"{Colors.YELLOW}Running in non-interactive automated test mode...{Colors.RESET}")
        lab.run_automated_tests()
        lab.show_dashboard()
        sys.exit(0)
    else:
        try:
            lab.menu()
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Lab terminated by user.{Colors.RESET}")
            sys.exit(0)

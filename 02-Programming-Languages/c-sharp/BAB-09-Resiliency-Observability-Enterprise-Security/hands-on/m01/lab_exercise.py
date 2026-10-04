#!/usr/bin/env python3
"""
Lab Exercise: C# .NET Resiliency, Observability & Enterprise Security Simulator
Chapter: BAB-09-Resiliency-Observability-Enterprise-Security (Modul 01)
Simulates Polly Circuit Breaker, OpenTelemetry Tracing/Metrics, and Claims-Based Security in Python 3.
"""

import base64
import dataclasses
import enum
import hashlib
import hmac
import json
import random
import sys
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

# --- ANSI Terminal Color Palette ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"
CLR_WHITE = "\033[97m"
CLR_BG_DARK = "\033[40m"


def print_banner(title: str) -> None:
    line = "=" * 70
    print(f"\n{CLR_CYAN}{CLR_BOLD}{line}")
    print(f" [*] .NET ENTERPRISE LAB: {title.upper()}")
    print(f"{line}{CLR_RESET}\n")


def print_success(msg: str) -> None:
    print(f"{CLR_GREEN}{CLR_BOLD}[OK]{CLR_RESET} {msg}")


def print_warn(msg: str) -> None:
    print(f"{CLR_YELLOW}{CLR_BOLD}[WARN]{CLR_RESET} {msg}")


def print_error(msg: str) -> None:
    print(f"{CLR_RED}{CLR_BOLD}[FAIL]{CLR_RESET} {msg}")


def print_info(msg: str) -> None:
    print(f"{CLR_BLUE}{CLR_BOLD}[INFO]{CLR_RESET} {msg}")


def print_trace(msg: str) -> None:
    print(f"{CLR_MAGENTA}{CLR_DIM}[TRACE]{CLR_RESET} {msg}")


# =====================================================================
# 1. RESILIENCY PIPELINE (Simulating Polly CircuitBreaker & Retry)
# =====================================================================
class CircuitState(enum.Enum):
    CLOSED = "Closed (Normal Traffic Allowed)"
    OPEN = "Open (Fail-Fast Active)"
    HALF_OPEN = "Half-Open (Testing Probe Requests)"


class CircuitBreakerOpenException(Exception):
    pass


class PollyResiliencePipeline:
    def __init__(
        self,
        failure_threshold: int = 3,
        break_duration_sec: float = 3.0,
        max_retries: int = 2,
        initial_backoff_sec: float = 0.2,
    ):
        self.failure_threshold = failure_threshold
        self.break_duration_sec = break_duration_sec
        self.max_retries = max_retries
        self.initial_backoff_sec = initial_backoff_sec

        self.state: CircuitState = CircuitState.CLOSED
        self.failure_count: int = 0
        self.last_state_change: float = time.time()
        self.success_count_half_open: int = 0

    def _evaluate_state(self) -> None:
        now = time.time()
        if self.state == CircuitState.OPEN:
            elapsed = now - self.last_state_change
            if elapsed >= self.break_duration_sec:
                self.state = CircuitState.HALF_OPEN
                self.success_count_half_open = 0
                self.last_state_change = now
                print_warn(f"Polly: Transitioning from OPEN -> HALF-OPEN after {elapsed:.1f}s cooldown.")

    def execute(self, action: Callable[[], Any], fallback: Optional[Callable[[], Any]] = None) -> Any:
        self._evaluate_state()

        if self.state == CircuitState.OPEN:
            print_error("Polly: Short-circuit triggered! Circuit is OPEN. Rejecting call immediately.")
            if fallback:
                print_info("Polly: Executing Fallback strategy.")
                return fallback()
            raise CircuitBreakerOpenException("Circuit breaker is OPEN. Request rejected without calling downstream.")

        attempt = 0
        while attempt <= self.max_retries:
            try:
                attempt += 1
                result = action()
                self._on_success()
                return result
            except Exception as ex:
                print_warn(f"Polly Retry: Attempt {attempt}/{self.max_retries + 1} failed: {ex}")
                if attempt > self.max_retries:
                    self._on_failure()
                    if fallback:
                        print_info("Polly: All retries exhausted. Invoking fallback delegate.")
                        return fallback()
                    raise ex
                backoff = self.initial_backoff_sec * (2 ** (attempt - 1)) + random.uniform(0.01, 0.05)
                print_trace(f"Polly: Sleeping for {backoff:.2f}s with jitter before next retry...")
                time.sleep(backoff)

    def _on_success(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self.success_count_half_open += 1
            print_success(f"Polly Probe Success ({self.success_count_half_open}/2 probes required).")
            if self.success_count_half_open >= 2:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.last_state_change = time.time()
                print_success("Polly: System stabilized! Transitioning HALF-OPEN -> CLOSED.")
        else:
            self.failure_count = 0

    def _on_failure(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.last_state_change = time.time()
            print_error("Polly Probe Failed in HALF-OPEN! Re-opening circuit immediately.")
        elif self.state == CircuitState.CLOSED:
            self.failure_count += 1
            print_warn(f"Polly: Failure recorded ({self.failure_count}/{self.failure_threshold}).")
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self.last_state_change = time.time()
                print_error(f"Polly: Threshold breached! Transitioning CLOSED -> OPEN for {self.break_duration_sec}s.")


# =====================================================================
# 2. OBSERVABILITY (OpenTelemetry ActivitySource & Meter Simulation)
# =====================================================================
@dataclasses.dataclass
class ActivitySpan:
    trace_id: str
    span_id: str
    operation_name: str
    parent_span_id: Optional[str]
    start_time: float
    duration_ms: float = 0.0
    tags: Dict[str, str] = dataclasses.field(default_factory=dict)
    events: List[str] = dataclasses.field(default_factory=list)


class OpenTelemetryDiagnostics:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.request_counter: int = 0
        self.error_counter: int = 0
        self.spans: List[ActivitySpan] = []

    def start_activity(
        self, operation: str, parent: Optional[ActivitySpan] = None, tags: Optional[Dict[str, str]] = None
    ) -> ActivitySpan:
        trace_id = parent.trace_id if parent else uuid.uuid4().hex
        span_id = uuid.uuid4().hex[:16]
        span = ActivitySpan(
            trace_id=trace_id,
            span_id=span_id,
            operation_name=operation,
            parent_span_id=parent.span_id if parent else None,
            start_time=time.time(),
            tags=tags or {},
        )
        span.tags["service.name"] = self.service_name
        self.request_counter += 1
        print_trace(f"OTel Span Start: [{operation}] TraceId={trace_id[:8]}... SpanId={span_id}")
        return span

    def record_event(self, span: ActivitySpan, event_name: str) -> None:
        timestamp_offset = round((time.time() - span.start_time) * 1000, 2)
        span.events.append(f"+{timestamp_offset}ms: {event_name}")
        print_trace(f"OTel Event [{span.operation_name}]: {event_name}")

    def stop_activity(self, span: ActivitySpan, is_error: bool = False) -> None:
        span.duration_ms = round((time.time() - span.start_time) * 1000, 2)
        if is_error:
            self.error_counter += 1
            span.tags["otel.status_code"] = "ERROR"
        else:
            span.tags["otel.status_code"] = "OK"
        self.spans.append(span)
        print_trace(
            f"OTel Span Stop: [{span.operation_name}] took {span.duration_ms}ms "
            f"Status={span.tags['otel.status_code']}"
        )

    def print_metrics_summary(self) -> None:
        print_info(
            f"Metrics Meter: {self.service_name} | Total Requests={self.request_counter} | Errors={self.error_counter}"
        )


# =====================================================================
# 3. ENTERPRISE SECURITY (Claims-Based JWT Verification Simulation)
# =====================================================================
class EnterpriseSecurityAuthority:
    def __init__(self, secret_key: str = "EnterpriseDotNetSuperSecret2026!Key"):
        self.secret_key = secret_key

    def issue_jwt(self, subject: str, role: str, scopes: List[str], expires_in_sec: int = 60) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        now = int(time.time())
        payload = {
            "iss": "https://auth.enterprise.internal",
            "aud": "api://core-services",
            "sub": subject,
            "role": role,
            "scope": " ".join(scopes),
            "iat": now,
            "exp": now + expires_in_sec,
        }

        b64_header = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        b64_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        signing_input = f"{b64_header}.{b64_payload}".encode()
        signature = hmac.new(self.secret_key.encode(), signing_input, hashlib.sha256).digest()
        b64_sig = base64.urlsafe_b64encode(signature).decode().rstrip("=")

        return f"{b64_header}.{b64_payload}.{b64_sig}"

    def validate_and_extract_claims(self, token: str) -> Dict[str, Any]:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Malformed JWT structure. Expected 3 segments.")

        b64_header, b64_payload, b64_sig = parts
        signing_input = f"{b64_header}.{b64_payload}".encode()
        expected_sig = hmac.new(self.secret_key.encode(), signing_input, hashlib.sha256).digest()
        actual_sig = base64.urlsafe_b64decode(b64_sig + "==")

        if not hmac.compare_digest(expected_sig, actual_sig):
            raise PermissionError("SecurityException: Cryptographic signature mismatch!")

        payload_bytes = base64.urlsafe_b64decode(b64_payload + "==")
        claims = json.loads(payload_bytes.decode())

        if time.time() > claims.get("exp", 0):
            raise PermissionError("SecurityException: JWT security token has expired!")

        return claims

    def authorize_claims(self, claims: Dict[str, Any], required_role: str, required_scope: str) -> None:
        user_role = claims.get("role")
        user_scopes = claims.get("scope", "").split()

        if user_role != required_role:
            raise PermissionError(
                f"Forbidden: Missing required role '{required_role}'. Current role is '{user_role}'."
            )
        if required_scope not in user_scopes:
            raise PermissionError(
                f"Forbidden: Missing required scope '{required_scope}'. Current scopes: {user_scopes}"
            )


# =====================================================================
# 4. INTERACTIVE SIMULATION LAB WORKFLOWS
# =====================================================================
def demo_resilience_circuit_breaker() -> None:
    print_banner("1. Polly Resiliency (Circuit Breaker & Exponential Retry)")
    pipeline = PollyResiliencePipeline(failure_threshold=3, break_duration_sec=3.0, max_retries=2)

    failure_countdown = 3

    def unreliable_remote_api() -> str:
        nonlocal failure_countdown
        if failure_countdown > 0:
            failure_countdown -= 1
            raise ConnectionResetError("Remote HTTP 503 Service Unavailable (Network Transient Failure)")
        return "HTTP 200 OK: Data Payload Received"

    def cache_fallback() -> str:
        return "Cache Hit: Degraded Stale Cache Data (Resilience Fallback)"

    print_info("Simulating consecutive calls to a degrading remote downstream service...")
    for round_num in range(1, 7):
        print(f"\n{CLR_WHITE}{CLR_BOLD}--- Client Request #{round_num} (Circuit State: {pipeline.state.value}) ---{CLR_RESET}")
        try:
            res = pipeline.execute(unreliable_remote_api, fallback=cache_fallback)
            print_success(f"Client Result: {res}")
        except Exception as e:
            print_error(f"Client Caught Exception: {e}")
        time.sleep(0.4)

    print_info("\nWaiting 3.2 seconds for Polly break duration cooldown...")
    time.sleep(3.2)

    print(f"\n{CLR_WHITE}{CLR_BOLD}--- Client Request #7 after cooldown ---{CLR_RESET}")
    res = pipeline.execute(unreliable_remote_api, fallback=cache_fallback)
    print_success(f"Client Result: {res}")


def demo_observability_tracing() -> None:
    print_banner("2. OpenTelemetry Tracing & Distributed Context Propagation")
    otel = OpenTelemetryDiagnostics("PaymentGateway.Service")

    parent_span = otel.start_activity(
        "ExecutePaymentTransaction", tags={"user.tier": "Enterprise", "http.method": "POST"}
    )
    time.sleep(0.08)
    otel.record_event(parent_span, "Validating payment credentials")

    # Child Span 1
    child_span_fraud = otel.start_activity("FraudDetectionCheck", parent=parent_span, tags={"fraud.model": "v3.1"})
    time.sleep(0.05)
    otel.record_event(child_span_fraud, "Risk score evaluated: 0.04 (Clean)")
    otel.stop_activity(child_span_fraud)

    # Child Span 2
    child_span_db = otel.start_activity(
        "PersistLedgerEntry", parent=parent_span, tags={"db.system": "SqlServer", "db.name": "LedgerDb"}
    )
    time.sleep(0.06)
    otel.record_event(child_span_db, "Committed transaction isolation level Snapshot")
    otel.stop_activity(child_span_db)

    otel.stop_activity(parent_span)

    print("\n" + CLR_CYAN + "Recorded OpenTelemetry Spans Tree:" + CLR_RESET)
    for sp in otel.spans:
        parent_info = f"Parent={sp.parent_span_id}" if sp.parent_span_id else "ROOT SPAN"
        print(
            f" - {CLR_YELLOW}[{sp.operation_name}]{CLR_RESET} "
            f"Duration={sp.duration_ms}ms | {parent_info} | Tags={sp.tags}"
        )
        for ev in sp.events:
            print(f"    * {CLR_DIM}{ev}{CLR_RESET}")

    otel.print_metrics_summary()


def demo_enterprise_security() -> None:
    print_banner("3. Enterprise Security: Claims-Based Token Authorization")
    auth_srv = EnterpriseSecurityAuthority()

    print_info("Issuing JWT for user 'alice@corp.internal' with role 'PlatformEngineer' and scopes ['read', 'write:deploy']...")
    valid_token = auth_srv.issue_jwt(
        subject="alice@corp.internal",
        role="PlatformEngineer",
        scopes=["read", "write:deploy"],
        expires_in_sec=10,
    )
    print(f"{CLR_DIM}JWT Token: {valid_token[:35]}...{valid_token[-20:]}{CLR_RESET}")

    print("\n[Scenario A] Validating valid token with authorized claims:")
    claims = auth_srv.validate_and_extract_claims(valid_token)
    print_success(f"Signature verified. Subject: {claims['sub']}, Role: {claims['role']}")
    auth_srv.authorize_claims(claims, required_role="PlatformEngineer", required_scope="write:deploy")
    print_success("Access Granted to restricted endpoint /api/v1/deployments")

    print("\n[Scenario B] Tampering token signature:")
    tampered_token = valid_token[:-4] + "ABCD"
    try:
        auth_srv.validate_and_extract_claims(tampered_token)
    except PermissionError as ex:
        print_error(f"Security Alert caught: {ex}")

    print("\n[Scenario C] Checking insufficient permission scope:")
    try:
        auth_srv.authorize_claims(claims, required_role="PlatformEngineer", required_scope="admin:cluster_destroy")
    except PermissionError as ex:
        print_error(f"RBAC Enforcement caught: {ex}")


def demo_integrated_architecture() -> None:
    print_banner("4. Integrated End-to-End Enterprise Scenario")
    print_info("Executing request through Security -> Polly Pipeline -> OpenTelemetry Tracing...")

    auth_srv = EnterpriseSecurityAuthority()
    otel = OpenTelemetryDiagnostics("SecureBilling.Microservice")
    pipeline = PollyResiliencePipeline(failure_threshold=2, break_duration_sec=2.0, max_retries=1)

    token = auth_srv.issue_jwt(subject="bob@fintech.internal", role="FinanceAuditor", scopes=["read:reports"])

    root_span = otel.start_activity("HandleInvoiceRequest", tags={"client.id": "portal-web"})

    try:
        otel.record_event(root_span, "Extracting and verifying Bearer token")
        claims = auth_srv.validate_and_extract_claims(token)
        auth_srv.authorize_claims(claims, required_role="FinanceAuditor", required_scope="read:reports")
        otel.record_event(root_span, "Security authorization verified")

        def call_downstream_invoice_engine() -> str:
            sub_span = otel.start_activity("RemoteBillingEngineCall", parent=root_span)
            time.sleep(0.05)
            otel.stop_activity(sub_span)
            return "Invoice #88391: AUDIT OK"

        result = pipeline.execute(call_downstream_invoice_engine)
        print_success(f"Integrated Pipeline Result: {result}")
        otel.stop_activity(root_span, is_error=False)

    except Exception as ex:
        otel.stop_activity(root_span, is_error=True)
        print_error(f"Integrated flow failed: {ex}")

    otel.print_metrics_summary()


def interactive_menu() -> None:
    while True:
        print("\n" + "=" * 60)
        print(f"{CLR_BOLD}{CLR_CYAN}C# .NET Enterprise Architecture Lab Menu:{CLR_RESET}")
        print("  1. Run Polly Resiliency Simulation (Circuit Breaker & Retry)")
        print("  2. Run OpenTelemetry Observability (Spans & Tracing)")
        print("  3. Run Enterprise Security (Claims & Signature Auth)")
        print("  4. Run Full Integrated Enterprise Request Demo")
        print("  5. Run All Demonstrations Sequentially")
        print("  6. Exit")
        print("=" * 60)

        try:
            choice = input(f"{CLR_YELLOW}Select option [1-6]: {CLR_RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            sys.exit(0)

        if choice == "1":
            demo_resilience_circuit_breaker()
        elif choice == "2":
            demo_observability_tracing()
        elif choice == "3":
            demo_enterprise_security()
        elif choice == "4":
            demo_integrated_architecture()
        elif choice == "5":
            demo_resilience_circuit_breaker()
            demo_observability_tracing()
            demo_enterprise_security()
            demo_integrated_architecture()
        elif choice == "6":
            print_success("Exiting Lab Simulation. Goodbye!")
            sys.exit(0)
        else:
            print_error("Invalid option. Please choose between 1 and 6.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        # Non-interactive automated execution for tests/CI
        demo_resilience_circuit_breaker()
        demo_observability_tracing()
        demo_enterprise_security()
        demo_integrated_architecture()
        print_success("Automated test completed successfully.")
    else:
        interactive_menu()

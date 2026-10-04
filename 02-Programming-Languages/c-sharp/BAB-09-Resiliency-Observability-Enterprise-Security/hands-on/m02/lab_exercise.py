#!/usr/bin/env python3
"""
Lab Hands-on: C# Chapter 09 - Resiliency, Observability & Enterprise Security
Topic: Deep Dive into .NET Enterprise Patterns (Polly, OpenTelemetry, Claims-Based Security)

This script simulates:
1. Enterprise Security: Claims-based token verification via HMAC-SHA256 (mirroring ASP.NET Core Authentication).
2. Observability: W3C Distributed Tracing propagation (mirroring System.Diagnostics.Activity / OpenTelemetry).
3. Resiliency: Polly v8 style Pipeline combining Exponential Backoff with Jitter and a Finite-State Circuit Breaker.
"""

import hmac
import hashlib
import json
import base64
import time
import random
import uuid
from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, Any, Dict, List, Optional

# --- ANSI Formatting Constants ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"
CLR_MAGENTA = "\033[95m"

# =====================================================================
# 1. ENTERPRISE SECURITY: Claims-Based Token Verification
# Mirroring: Microsoft.AspNetCore.Authentication.JwtBearer & ClaimsPrincipal
# =====================================================================

class SecurityTokenService:
    """Simulates ASP.NET Core JWT validation and ClaimsPrincipal extraction."""
    def __init__(self, secret_key: str):
        self._secret = secret_key.encode('utf-8')

    def generate_token(self, sub: str, roles: List[str], scopes: List[str]) -> str:
        header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).rstrip(b'=').decode()
        payload_data = {
            "sub": sub,
            "roles": roles,
            "scopes": scopes,
            "exp": int(time.time()) + 300
        }
        payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).rstrip(b'=').decode()
        signature_raw = hmac.new(self._secret, f"{header}.{payload}".encode(), hashlib.sha256).digest()
        signature = base64.urlsafe_b64encode(signature_raw).rstrip(b'=').decode()
        return f"{header}.{payload}.{signature}"

    def validate_and_extract_claims(self, token: str) -> Dict[str, Any]:
        parts = token.split('.')
        if len(parts) != 3:
            raise ValueError("Malformed JWT structure.")
        
        header_b64, payload_b64, sig_b64 = parts
        expected_sig = base64.urlsafe_b64encode(
            hmac.new(self._secret, f"{header_b64}.{payload_b64}".encode(), hashlib.sha256).digest()
        ).rstrip(b'=').decode()
        
        if not hmac.compare_digest(sig_b64, expected_sig):
            raise PermissionError("Tampered or invalid token signature.")

        # Decode payload padding properly
        rem = len(payload_b64) % 4
        if rem > 0:
            payload_b64 += '=' * (4 - rem)
        claims = json.loads(base64.urlsafe_b64decode(payload_b64).decode())
        
        if claims.get("exp", 0) < int(time.time()):
            raise PermissionError("Security token has expired.")
        return claims

# =====================================================================
# 2. OBSERVABILITY: Distributed Tracing & Structured Logging
# Mirroring: System.Diagnostics.Activity & OpenTelemetry .NET SDK
# =====================================================================

@dataclass
class ActivityContext:
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    parent_span_id: Optional[str] = None

class EnterpriseDiagnostics:
    @staticmethod
    def log_event(level: str, message: str, ctx: ActivityContext, tags: Optional[Dict[str, Any]] = None):
        colors = {
            "INFO": CLR_CYAN,
            "WARN": CLR_YELLOW,
            "ERROR": CLR_RED,
            "SUCCESS": CLR_GREEN
        }
        color = colors.get(level, CLR_RESET)
        payload = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,
            "traceId": ctx.trace_id,
            "spanId": ctx.span_id,
            "message": message,
            "tags": tags or {}
        }
        print(f"{color}[{payload['level']}] [{payload['traceId'][:8]}...{payload['spanId'][:6]}]{CLR_RESET} "
              f"{message} {CLR_BOLD}{tags if tags else ''}{CLR_RESET}")

# =====================================================================
# 3. RESILIENCY: Polly-style Circuit Breaker & Retry with Jitter
# Mirroring: Polly.CircuitBreaker & Polly.Retry in .NET 8 ResiliencePipeline
# =====================================================================

class CircuitState(Enum):
    CLOSED = "CLOSED"       # Normal operation; traffic flows freely
    OPEN = "OPEN"           # Broken; fail-fast immediately
    HALF_OPEN = "HALF_OPEN" # Canary testing downstream service

class CircuitBreakerOpenException(Exception):
    pass

class CircuitBreakerPolicy:
    def __init__(self, failure_threshold: int = 2, recovery_time_sec: float = 2.0):
        self.failure_threshold = failure_threshold
        self.recovery_time_sec = recovery_time_sec
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    def record_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            self.failure_count = 0

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

    def pre_execution_check(self):
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_time_sec:
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpenException("Circuit is OPEN. Fast-failing downstream request.")

class ResiliencePipeline:
    """Orchestrates Polly-like execution: Retry + Circuit Breaker."""
    def __init__(self, circuit_breaker: CircuitBreakerPolicy, max_retries: int = 2, base_delay: float = 0.2):
        self.cb = circuit_breaker
        self.max_retries = max_retries
        self.base_delay = base_delay

    def execute(self, action: Callable[..., Any], ctx: ActivityContext, *args, **kwargs) -> Any:
        attempts = 0
        while True:
            attempts += 1
            self.cb.pre_execution_check()
            try:
                EnterpriseDiagnostics.log_event("INFO", f"Executing pipeline attempt #{attempts}", ctx, {"cb_state": self.cb.state.value})
                result = action(*args, **kwargs)
                self.cb.record_success()
                return result
            except CircuitBreakerOpenException:
                EnterpriseDiagnostics.log_event("WARN", "Execution halted by Circuit Breaker barrier.", ctx)
                raise
            except Exception as ex:
                self.cb.record_failure()
                EnterpriseDiagnostics.log_event("ERROR", f"Execution faulted: {str(ex)}", ctx, {"cb_state": self.cb.state.value, "attempt": attempts})
                if attempts > self.max_retries:
                    raise
                # Exponential backoff with Full Jitter: Sleep = rand(0, base_delay * 2^attempt)
                delay = random.uniform(0, self.base_delay * (2 ** (attempts - 1)))
                EnterpriseDiagnostics.log_event("WARN", f"Backoff sleep before retry: {delay:.3f}s", ctx)
                time.sleep(delay)

# =====================================================================
# SIMULATED DOMAIN: Protected Payment Microservice Core
# =====================================================================

class DownstreamBankGateway:
    """Simulates an unstable remote payment clearance provider."""
    def __init__(self):
        self.fault_trigger_count = 0

    def process_settlement(self, amount: float) -> str:
        self.fault_trigger_count += 1
        # Simulates outage for requests 2, 3, 4
        if 2 <= self.fault_trigger_count <= 4:
            raise ConnectionResetError("Remote bank connection reset by peer (HTTP 503).")
        return f"TXN-{uuid.uuid4().hex[:8].upper()}-AMT-{amount:.2f}"

def payment_dispatch_endpoint(token: str, amount: float, auth_service: SecurityTokenService,
                              pipeline: ResiliencePipeline, gateway: DownstreamBankGateway,
                              root_ctx: ActivityContext):
    """Encapsulates authorization, diagnostics, and resilient service invocation."""
    child_ctx = ActivityContext(trace_id=root_ctx.trace_id, parent_span_id=root_ctx.span_id)
    
    EnterpriseDiagnostics.log_event("INFO", "Validating Claims & Scopes...", child_ctx)
    try:
        claims = auth_service.validate_and_extract_claims(token)
        if "payment:process" not in claims.get("scopes", []):
            raise PermissionError("Forbidden: Principal lacks 'payment:process' scope.")
        EnterpriseDiagnostics.log_event("SUCCESS", f"Authorized: Subject '{claims['sub']}' confirmed.", child_ctx)
    except Exception as ex:
        EnterpriseDiagnostics.log_event("ERROR", f"Security rejection: {str(ex)}", child_ctx)
        return

    try:
        receipt = pipeline.execute(gateway.process_settlement, child_ctx, amount=amount)
        EnterpriseDiagnostics.log_event("SUCCESS", f"Payment settled successfully! Receipt: {receipt}", child_ctx)
    except Exception as ex:
        EnterpriseDiagnostics.log_event("ERROR", f"Dispatched payment failed: {str(ex)}", child_ctx)

# =====================================================================
# DEMONSTRATION WORKFLOW
# =====================================================================

if __name__ == "__main__":
    print(f"{CLR_BOLD}{CLR_MAGENTA}======================================================================")
    print(" .NET ENTERPRISE PATTERNS LAB: RESILIENCY, OBSERVABILITY & SECURITY")
    print(f"======================================================================{CLR_RESET}\n")

    auth_svc = SecurityTokenService(secret_key="EnterpriseSuperSecretSigningKey2024!")
    cb = CircuitBreakerPolicy(failure_threshold=2, recovery_time_sec=1.5)
    pipeline = ResiliencePipeline(circuit_breaker=cb, max_retries=2, base_delay=0.1)
    gateway = DownstreamBankGateway()

    # 1. Issue Valid & Invalid Tokens
    valid_token = auth_svc.generate_token(sub="srv-order-svc", roles=["Worker"], scopes=["payment:process"])
    unauthorized_token = auth_svc.generate_token(sub="guest-user", roles=["Guest"], scopes=["read:catalog"])

    print(f"{CLR_BOLD}--> Scenario A: Unauthorized Request Security Gate{CLR_RESET}")
    root_trace = ActivityContext()
    payment_dispatch_endpoint(unauthorized_token, 50.0, auth_svc, pipeline, gateway, root_trace)

    print(f"\n{CLR_BOLD}--> Scenario B: Healthy Request Settlement{CLR_RESET}")
    payment_dispatch_endpoint(valid_token, 100.0, auth_svc, pipeline, gateway, root_trace)

    print(f"\n{CLR_BOLD}--> Scenario C: Downstream Failure Cascade & Circuit Breaker Trip{CLR_RESET}")
    for i in range(1, 4):
        print(f"\n--- Batch Dispatch Call #{i} ---")
        call_ctx = ActivityContext(trace_id=root_trace.trace_id)
        payment_dispatch_endpoint(valid_token, 150.0 + i, auth_svc, pipeline, gateway, call_ctx)

    print(f"\n{CLR_BOLD}--> Scenario D: Recovery Window (Cool-down for Circuit Breaker probe){CLR_RESET}")
    print(f"{CLR_YELLOW}Sleeping 1.6s for breaker recovery duration window...{CLR_RESET}")
    time.sleep(1.6)

    print(f"\n--- Canary Call (Probing in HALF-OPEN state) ---")
    canary_ctx = ActivityContext(trace_id=root_trace.trace_id)
    payment_dispatch_endpoint(valid_token, 250.0, auth_svc, pipeline, gateway, canary_ctx)

    print(f"\n{CLR_BOLD}{CLR_GREEN}======================================================================")
    print(" LAB VERIFICATION COMPLETED: PIPELINE DEMONSTRATED ENTERPRISE FIDELITY")
    print(f"======================================================================{CLR_RESET}")
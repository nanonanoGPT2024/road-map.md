#!/usr/bin/env python3
"""
Lab Hands-on: ASP.NET Core Architecture Deep Dive
Bab 06: Validation, Error Handling, & Fault Tolerance (Polly Simulation)

Deskripsi:
Script ini mensimulasikan mekanisme inti runtime ASP.NET Core:
1. Model Validation & ModelStateDictionary (mirip DataAnnotations / FluentValidation)
2. Global Exception Handling Middleware yang memformat error ke RFC 7807 ProblemDetails
3. Fault Tolerance Pipeline (Polly-like): Circuit Breaker & Exponential Backoff Retry
"""

import time
import json
import uuid
import random
from enum import Enum
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field

# --- ANSI Formatting Helper ---
class TerminalColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"

# --- 1. MODEL VALIDATION ENGINE (ASP.NET Core ModelState) ---

class ValidationResult:
    def __init__(self, is_valid: bool, error_message: str = ""):
        self.is_valid = is_valid
        self.error_message = error_message


class ValidatorRule:
    """Basis aturan validasi deklaratif mirip DataAnnotations."""
    def validate(self, field_name: str, value: Any) -> Optional[str]:
        raise NotImplementedError


class RequiredAttribute(ValidatorRule):
    def validate(self, field_name: str, value: Any) -> Optional[str]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return f"The {field_name} field is required."
        return None


class RangeAttribute(ValidatorRule):
    def __init__(self, min_val: float, max_val: float):
        self.min_val = min_val
        self.max_val = max_val

    def validate(self, field_name: str, value: Any) -> Optional[str]:
        if value is not None and not (self.min_val <= value <= self.max_val):
            return f"The field {field_name} must be between {self.min_val} and {self.max_val}."
        return None


class EmailAddressAttribute(ValidatorRule):
    def validate(self, field_name: str, value: Any) -> Optional[str]:
        if value and ("@" not in value or "." not in value.split("@")[-1]):
            return f"The field {field_name} is not a valid e-mail address."
        return None


@dataclass
class ModelStateDictionary:
    """Menyimpan error per properti seperti ModelState ASP.NET Core."""
    errors: Dict[str, List[str]] = field(default_factory=dict)

    def add_error(self, key: str, error: str):
        if key not in self.errors:
            self.errors[key] = []
        self.errors[key].append(error)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


def validate_object(model: Any, rules: Dict[str, List[ValidatorRule]]) -> ModelStateDictionary:
    """Melakukan eksekusi validator pada Data Transfer Object (DTO)."""
    model_state = ModelStateDictionary()
    for field_name, rule_list in rules.items():
        value = getattr(model, field_name, None)
        for rule in rule_list:
            error = rule.validate(field_name, value)
            if error:
                model_state.add_error(field_name, error)
    return model_state


# --- 2. ERROR HANDLING & RFC 7807 PROBLEM DETAILS ---

@dataclass
class ProblemDetails:
    """Representasi payload standar RFC 7807 (ProblemDetails / ValidationProblemDetails)."""
    type_uri: str
    title: str
    status: int
    detail: str
    instance: str
    extensions: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        payload = {
            "type": self.type_uri,
            "title": self.title,
            "status": self.status,
            "detail": self.detail,
            "instance": self.instance,
            **self.extensions
        }
        return json.dumps(payload, indent=2)


class HttpContext:
    def __init__(self, path: str, method: str):
        self.trace_id = str(uuid.uuid4())
        self.path = path
        self.method = method
        self.response_status = 200
        self.response_body = ""


def exception_handler_middleware(context: HttpContext, next_action: Callable[[], None]):
    """Simulasi UseExceptionHandler() middleware di ASP.NET Core pipeline."""
    try:
        next_action()
    except ValueError as ex:
        # Client Error / Domain Validation Failure
        context.response_status = 400
        problem = ProblemDetails(
            type_uri="https://tools.ietf.org/html/rfc7231#section-6.5.1",
            title="Bad Request / Domain Invariant Violated",
            status=400,
            detail=str(ex),
            instance=context.path,
            extensions={"traceId": context.trace_id}
        )
        context.response_body = problem.to_json()
    except Exception as ex:
        # Unhandled Internal Server Error
        context.response_status = 500
        problem = ProblemDetails(
            type_uri="https://tools.ietf.org/html/rfc7231#section-6.6.1",
            title="An error occurred while processing your request.",
            status=500,
            detail="Internal execution fault encountered.",
            instance=context.path,
            extensions={"traceId": context.trace_id, "exception": str(ex)}
        )
        context.response_body = problem.to_json()


# --- 3. FAULT TOLERANCE: POLLY-LIKE RESILIENCE PIPELINE ---

class CircuitState(Enum):
    CLOSED = "CLOSED"       # Normal operational state
    OPEN = "OPEN"           # Failing, short-circuit all requests
    HALF_OPEN = "HALF_OPEN" # Probing downstream health


class CircuitBreakerOpenException(Exception):
    pass


class CircuitBreakerPolicy:
    """Implementasi Finite State Machine Circuit Breaker mirip Polly."""
    def __init__(self, failure_threshold: int = 3, recovery_time_seconds: float = 1.0):
        self.failure_threshold = failure_threshold
        self.recovery_time_seconds = recovery_time_seconds
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_state_change = time.time()

    def execute(self, action: Callable[..., Any], *args, **kwargs) -> Any:
        current_time = time.time()

        # Transisi dari OPEN ke HALF_OPEN saat durasi timeout cooldown terlampaui
        if self.state == CircuitState.OPEN:
            if current_time - self.last_state_change >= self.recovery_time_seconds:
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = current_time
                print(f"  {TerminalColor.YELLOW}[CircuitBreaker] Transition: OPEN -> HALF_OPEN (Probing candidate request){TerminalColor.RESET}")
            else:
                raise CircuitBreakerOpenException("Circuit is OPEN. Fast-failing downstream call.")

        try:
            result = action(*args, **kwargs)
            # Jika berhasil di state HALF_OPEN, kembalikan ke CLOSED
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.last_state_change = time.time()
                print(f"  {TerminalColor.GREEN}[CircuitBreaker] Transition: HALF_OPEN -> CLOSED (System recovered){TerminalColor.RESET}")
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0
            return result

        except Exception as ex:
            self.failure_count += 1
            print(f"  {TerminalColor.RED}[CircuitBreaker] Captured failure #{self.failure_count}: {ex}{TerminalColor.RESET}")
            
            if self.state == CircuitState.HALF_OPEN:
                # Probe gagal, langsung kembali ke OPEN
                self.state = CircuitState.OPEN
                self.last_state_change = time.time()
                print(f"  {TerminalColor.RED}[CircuitBreaker] Probe Failed! Transition: HALF_OPEN -> OPEN{TerminalColor.RESET}")
            elif self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self.last_state_change = time.time()
                print(f"  {TerminalColor.RED}[CircuitBreaker] Threshold reached ({self.failure_threshold})! Transition: CLOSED -> OPEN{TerminalColor.RESET}")
            raise ex


class RetryPolicy:
    """Implementasi Retry Policy dengan Exponential Backoff & Full Jitter."""
    def __init__(self, max_retries: int = 3, base_delay: float = 0.05):
        self.max_retries = max_retries
        self.base_delay = base_delay

    def execute(self, action: Callable[..., Any], *args, **kwargs) -> Any:
        attempt = 0
        while True:
            try:
                return action(*args, **kwargs)
            except CircuitBreakerOpenException:
                # Jangan retry jika sirkuit memang terbuka (hindari hammering)
                raise
            except Exception as ex:
                attempt += 1
                if attempt > self.max_retries:
                    print(f"  {TerminalColor.RED}[RetryPolicy] Exhausted all {self.max_retries} attempts.{TerminalColor.RESET}")
                    raise ex
                
                # Exponential backoff: base * 2^(attempt-1) + jitter
                delay = (self.base_delay * (2 ** (attempt - 1))) + random.uniform(0, 0.02)
                print(f"  {TerminalColor.YELLOW}[RetryPolicy] Attempt {attempt} failed: {ex}. Retrying in {delay*1000:.1f}ms...{TerminalColor.RESET}")
                time.sleep(delay)


# --- 4. TEST HARNESS & DEMONSTRATION WORKFLOWS ---

@dataclass
class CreateUserDto:
    username: str
    email: str
    age: int


class UnstablePaymentGateway:
    """Mock Microservice eksternal yang memiliki kegagalan transien."""
    def __init__(self):
        self.call_count = 0
        self.should_fail = True

    def charge(self, amount: float) -> str:
        self.call_count += 1
        if self.should_fail:
            raise ConnectionResetError(f"Remote gateway socket reset (Call #{self.call_count})")
        return f"CHARGE_OK_REF_{self.call_count}"


def main():
    print(f"{TerminalColor.BOLD}{TerminalColor.CYAN}=== ASP.NET CORE: VALIDATION, ERROR HANDLING & FAULT TOLERANCE ==={TerminalColor.RESET}\n")

    # -------------------------------------------------------------
    # DEMO 1: Model Validation & ProblemDetails (RFC 7807)
    # -------------------------------------------------------------
    print(f"{TerminalColor.BOLD}[1] Model Validation Pipeline (DataAnnotations Simulation){TerminalColor.RESET}")
    
    rules = {
        "username": [RequiredAttribute()],
        "email": [RequiredAttribute(), EmailAddressAttribute()],
        "age": [RequiredAttribute(), RangeAttribute(18, 99)]
    }

    invalid_dto = CreateUserDto(username="", email="invalid-email-format", age=15)
    model_state = validate_object(invalid_dto, rules)

    if not model_state.is_valid:
        print(f"{TerminalColor.YELLOW}ModelState.IsValid == False. Generating ValidationProblemDetails...{TerminalColor.RESET}")
        validation_problem = ProblemDetails(
            type_uri="https://tools.ietf.org/html/rfc7231#section-6.5.1",
            title="One or more validation errors occurred.",
            status=400,
            detail="See the errors property for details.",
            instance="/api/v1/users",
            extensions={"errors": model_state.errors, "traceId": str(uuid.uuid4())}
        )
        print(f"{TerminalColor.RED}{validation_problem.to_json()}{TerminalColor.RESET}\n")

    # -------------------------------------------------------------
    # DEMO 2: Global Exception Handling Middleware
    # -------------------------------------------------------------
    print(f"{TerminalColor.BOLD}[2] Global Exception Handling Middleware (RFC 7807 Unhandled Exception){TerminalColor.RESET}")
    context = HttpContext(path="/api/v1/orders/checkout", method="POST")

    def problematic_endpoint():
        # Mensimulasikan domain bug tak tertangani
        raise ZeroDivisionError("Decimal calculation overflow in discount computation engine")

    exception_handler_middleware(context, problematic_endpoint)
    print(f"HTTP Status: {TerminalColor.BOLD}{context.response_status}{TerminalColor.RESET}")
    print(f"Response Payload:\n{TerminalColor.MAGENTA}{context.response_body}{TerminalColor.RESET}\n")

    # -------------------------------------------------------------
    # DEMO 3: Fault Tolerance (Polly Resilience Pipeline)
    # -------------------------------------------------------------
    print(f"{TerminalColor.BOLD}[3] Fault Tolerance: Polly Pipeline (Retry + Circuit Breaker){TerminalColor.RESET}")

    circuit_breaker = CircuitBreakerPolicy(failure_threshold=2, recovery_time_seconds=0.25)
    retry_policy = RetryPolicy(max_retries=2, base_delay=0.03)
    gateway = UnstablePaymentGateway()

    def resilient_call():
        return retry_policy.execute(lambda: circuit_breaker.execute(gateway.charge, 99.99))

    # Fase 1: Kegagalan Transien memicu Retries hingga Circuit Breaker Trip
    print(f"{TerminalColor.CYAN}--- Step 3A: Mengirim request saat downstream down (Memicu Retry & Circuit Breaker) ---{TerminalColor.RESET}")
    for i in range(1, 3):
        print(f"\nRequest Batch #{i}:")
        try:
            resilient_call()
        except Exception as e:
            print(f"  {TerminalColor.RED}=> Request #{i} aborted: {type(e).__name__} ({e}){TerminalColor.RESET}")

    # Fase 2: Circuit Breaker aktif (Fast Fail)
    print(f"\n{TerminalColor.CYAN}--- Step 3B: Mengirim request saat sirkuit OPEN (Fast Failure tanpa Retry) ---{TerminalColor.RESET}")
    try:
        resilient_call()
    except CircuitBreakerOpenException as cbe:
        print(f"  {TerminalColor.RED}=> Fast Fail Terbukti: {cbe}{TerminalColor.RESET}")

    # Fase 3: Pemulihan Downstream & Half-Open Transition
    print(f"\n{TerminalColor.CYAN}--- Step 3C: Menunggu Recovery Timeout ({circuit_breaker.recovery_time_seconds}s) & Downstream Healing ---{TerminalColor.RESET}")
    time.sleep(circuit_breaker.recovery_time_seconds + 0.05)
    gateway.should_fail = False  # Downstream service kembali online

    try:
        response = resilient_call()
        print(f"  {TerminalColor.GREEN}=> Request Sukses Pasca Pemulihan! Hasil: {response}{TerminalColor.RESET}")
    except Exception as e:
        print(f"  {TerminalColor.RED}=> Gagal tak terduga: {e}{TerminalColor.RESET}")

    print(f"\n{TerminalColor.BOLD}{TerminalColor.GREEN}=== SIMULASI SELESAI DENGAN SUKSES ==={TerminalColor.RESET}")


if __name__ == "__main__":
    main()
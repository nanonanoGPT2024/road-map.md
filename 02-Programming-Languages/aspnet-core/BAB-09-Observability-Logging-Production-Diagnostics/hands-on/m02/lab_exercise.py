#!/usr/bin/env python3
"""
Lab Hands-on: ASP.NET Core Observability, Logging, & Production Diagnostics Deep Dive
Simulates ASP.NET Core's diagnostic subsystem:
 - ActivitySource & Activity (System.Diagnostics / OpenTelemetry tracing)
 - ILogger<T> with Scope hierarchy, semantic tokens, and TraceContext propagation
 - System.Diagnostics.Metrics (Meters, Counters, and Histograms)
 - Diagnostic Middleware pipeline handling concurrent synthetic web requests
"""

import sys
import time
import uuid
import random
import threading
from typing import Dict, Any, List, Optional

# --- ANSI Color Codes for Diagnostic Console Formatting ---
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_DIM     = "\033[2m"
CLR_DEBUG   = "\033[36m"    # Cyan
CLR_INFO    = "\033[32m"    # Green
CLR_WARN    = "\033[33m"    # Yellow
CLR_ERROR   = "\033[31m"    # Red
CLR_TRACE   = "\033[35m"    # Magenta
CLR_METRIC  = "\033[34m"    # Blue


# ============================================================================
# 1. DISTRIBUTED TRACING ENGINE (System.Diagnostics.Activity / OpenTelemetry)
# ============================================================================

_trace_context = threading.local()

class Activity:
    """Represents an execution span in ASP.NET Core (System.Diagnostics.Activity)."""
    def __init__(self, operation_name: str, parent: Optional['Activity'] = None):
        self.operation_name = operation_name
        self.parent_id = parent.span_id if parent else None
        self.trace_id = parent.trace_id if parent else uuid.uuid4().hex[:16]
        self.span_id = uuid.uuid4().hex[:8]
        self.tags: Dict[str, Any] = {}
        self.start_time: float = 0.0
        self.duration_ms: float = 0.0
        self.status: str = "Unset"

    def set_tag(self, key: str, value: Any) -> 'Activity':
        self.tags[key] = value
        return self

    def set_status(self, status: str) -> 'Activity':
        self.status = status
        return self

    def __enter__(self) -> 'Activity':
        if not hasattr(_trace_context, 'stack'):
            _trace_context.stack = []
        _trace_context.stack.append(self)
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (time.perf_counter() - self.start_time) * 1000.0
        if exc_type is not None:
            self.status = "Error"
            self.set_tag("otel.status_code", "ERROR")
            self.set_tag("exception.message", str(exc_val))
        else:
            if self.status == "Unset":
                self.status = "Ok"
        if hasattr(_trace_context, 'stack') and _trace_context.stack:
            _trace_context.stack.pop()

    @staticmethod
    def current() -> Optional['Activity']:
        stack = getattr(_trace_context, 'stack', None)
        return stack[-1] if stack else None


class ActivitySource:
    """Emulates System.Diagnostics.ActivitySource for emitting trace spans."""
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version

    def start_activity(self, name: str) -> Activity:
        parent = Activity.current()
        return Activity(name, parent=parent)


# ============================================================================
# 2. METRICS SUBSYSTEM (System.Diagnostics.Metrics)
# ============================================================================

class Counter:
    """Thread-safe monotonic counter."""
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self._values: Dict[str, int] = {}
        self._lock = threading.Lock()

    def add(self, delta: int, tags: Dict[str, str]):
        tag_key = tuple(sorted(tags.items()))
        with self._lock:
            self._values[tag_key] = self._values.get(tag_key, 0) + delta

    def snapshot(self) -> Dict[tuple, int]:
        with self._lock:
            return dict(self._values)


class Histogram:
    """Emulates distribution tracking (e.g. latency percentiles)."""
    def __init__(self, name: str, unit: str):
        self.name = name
        self.unit = unit
        self._samples: List[float] = []
        self._lock = threading.Lock()

    def record(self, value: float):
        with self._lock:
            self._samples.append(value)

    def stats(self) -> Dict[str, float]:
        with self._lock:
            if not self._samples:
                return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "count": 0}
            sorted_s = sorted(self._samples)
            n = len(sorted_s)
            p50 = sorted_s[int(0.50 * n)]
            p95 = sorted_s[min(int(0.95 * n), n - 1)]
            p99 = sorted_s[min(int(0.99 * n), n - 1)]
            return {"p50": p50, "p95": p95, "p99": p99, "count": n}


class Meter:
    def __init__(self, name: str):
        self.name = name
        self.counters: Dict[str, Counter] = {}
        self.histograms: Dict[str, Histogram] = {}

    def create_counter(self, name: str, description: str = "") -> Counter:
        cnt = Counter(name, description)
        self.counters[name] = cnt
        return cnt

    def create_histogram(self, name: str, unit: str = "ms") -> Histogram:
        hist = Histogram(name, unit)
        self.histograms[name] = hist
        return hist


# ============================================================================
# 3. STRUCTURED LOGGING SUBSYSTEM (Microsoft.Extensions.Logging)
# ============================================================================

_scope_context = threading.local()

class LogScope:
    def __init__(self, scope_state: Dict[str, Any]):
        self.scope_state = scope_state

    def __enter__(self):
        if not hasattr(_scope_context, 'scopes'):
            _scope_context.scopes = []
        _scope_context.scopes.append(self.scope_state)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(_scope_context, 'scopes') and _scope_context.scopes:
            _scope_context.scopes.pop()


class ILogger:
    """Simulates Microsoft.Extensions.Logging.ILogger with scopes & semantic parsing."""
    _io_lock = threading.Lock()

    def __init__(self, category_name: str):
        self.category = category_name

    def begin_scope(self, state: Dict[str, Any]) -> LogScope:
        return LogScope(state)

    def _log(self, level: str, color: str, message_template: str, **kwargs):
        active_activity = Activity.current()
        trace_id = active_activity.trace_id if active_activity else "0000000000000000"
        span_id = active_activity.span_id if active_activity else "00000000"

        # Merge lexical scopes
        merged_scope = {}
        if hasattr(_scope_context, 'scopes'):
            for s in _scope_context.scopes:
                merged_scope.update(s)
        merged_scope.update(kwargs)

        formatted_msg = message_template.format(**kwargs) if kwargs else message_template

        timestamp = time.strftime("%H:%M:%S")
        thread_id = threading.get_ident() % 1000

        with self._io_lock:
            # Emulate ASP.NET Core Structured Console Log
            sys.stdout.write(
                f"{CLR_DIM}{timestamp}{CLR_RESET} "
                f"[{color}{level:<5}{CLR_RESET}] "
                f"{CLR_DIM}[TID:{thread_id:03d}]{CLR_RESET} "
                f"{CLR_BOLD}{self.category}{CLR_RESET}: {formatted_msg}\n"
            )
            # Render Distributed TraceContext & Scopes
            scope_repr = ", ".join(f"{k}={v}" for k, v in merged_scope.items())
            sys.stdout.write(
                f"       {CLR_TRACE}TraceId:{trace_id}{CLR_RESET} "
                f"{CLR_TRACE}SpanId:{span_id}{CLR_RESET} "
                f"{CLR_DIM}Scope: [{scope_repr}]{CLR_RESET}\n"
            )
            sys.stdout.flush()

    def debug(self, msg: str, **kwargs): self._log("DEBUG", CLR_DEBUG, msg, **kwargs)
    def info(self, msg: str, **kwargs):  self._log("INFO", CLR_INFO, msg, **kwargs)
    def warn(self, msg: str, **kwargs):  self._log("WARN", CLR_WARN, msg, **kwargs)
    def error(self, msg: str, **kwargs): self._log("FAIL", CLR_ERROR, msg, **kwargs)


# ============================================================================
# 4. APPLICATION SERVICES & MIDDLEWARE SIMULATION
# ============================================================================

app_meter = Meter("ECommerce.WebPipeline")
http_req_counter = app_meter.create_counter("http.server.request.count")
http_req_duration = app_meter.create_histogram("http.server.request.duration", unit="ms")
inventory_meter = app_meter.create_counter("ecommerce.inventory.reservations")

app_activity_source = ActivitySource("ECommerce.PaymentApp")

class InventoryRepository:
    def __init__(self):
        self.logger = ILogger("ECommerce.Data.InventoryRepository")

    def check_and_reserve(self, sku: str, quantity: int) -> bool:
        with app_activity_source.start_activity("Database.ExecuteQuery") as act:
            act.set_tag("db.system", "postgresql").set_tag("db.statement", "SELECT & LOCK FROM inventory")
            time.sleep(random.uniform(0.010, 0.030))  # 10-30ms DB latency

            if sku == "SKU-OUT-OF-STOCK":
                self.logger.warn("Inventory check failed for {sku}. Stock zero.", sku=sku)
                act.set_tag("inventory.success", False)
                return False

            inventory_meter.add(quantity, {"sku": sku, "status": "reserved"})
            self.logger.debug("Reserved {qty} units of SKU {sku}.", qty=quantity, sku=sku)
            act.set_tag("inventory.success", True)
            return True


class PaymentGatewayClient:
    def __init__(self):
        self.logger = ILogger("ECommerce.External.PaymentGateway")

    def charge(self, amount: float, account_id: str) -> str:
        with app_activity_source.start_activity("HttpOut.PaymentGateway.Charge") as act:
            act.set_tag("http.method", "POST").set_tag("peer.service", "api.stripe-mock.internal")
            time.sleep(random.uniform(0.025, 0.060))  # Network latency

            if account_id == "ACC-FAULTY":
                act.set_status("Error")
                self.logger.error("Remote gateway rejected transaction for {acc}", acc=account_id)
                raise ConnectionResetError("Remote server closed connection unexpectedly")

            tx_id = f"tx_{uuid.uuid4().hex[:10]}"
            self.logger.info("Charge successful. TxRef={tx} for {amt:.2f} USD", tx=tx_id, amt=amount)
            return tx_id


class OrderController:
    """Controller simulating an ASP.NET Core Endpoint."""
    def __init__(self):
        self.logger = ILogger("ECommerce.Controllers.OrderController")
        self.inventory = InventoryRepository()
        self.payments = PaymentGatewayClient()

    def checkout(self, customer_id: str, sku: str, amount: float) -> Dict[str, Any]:
        with app_activity_source.start_activity("OrderController/Checkout") as act:
            act.set_tag("app.customer_id", customer_id)
            act.set_tag("app.sku", sku)

            self.logger.info("Executing checkout for Customer={cust}", cust=customer_id)

            if not self.inventory.check_and_reserve(sku, 1):
                return {"success": False, "reason": "InsufficientInventory"}

            tx_id = self.payments.charge(amount, customer_id)
            return {"success": True, "transaction_id": tx_id}


def diagnostic_http_middleware(customer_id: str, sku: str, amount: float, req_idx: int):
    """Emulates ASP.NET Core Diagnostics Pipeline & Middleware stack."""
    controller = OrderController()
    logger = ILogger("Microsoft.AspNetCore.Hosting.Diagnostics")

    with app_activity_source.start_activity("HTTP POST /api/orders/checkout") as root_activity:
        root_activity.set_tag("http.method", "POST")
        root_activity.set_tag("http.route", "/api/orders/checkout")
        root_activity.set_tag("request.index", req_idx)

        t_start = time.perf_counter()
        status_code = 200

        # Scope correlation: correlation ID and User context
        correlation_id = f"req-{uuid.uuid4().hex[:6]}"
        with logger.begin_scope({"CorrelationId": correlation_id, "User": customer_id}):
            logger.info("Request started: POST /api/orders/checkout")
            try:
                result = controller.checkout(customer_id, sku, amount)
                if not result.get("success"):
                    status_code = 409  # Conflict
            except Exception as ex:
                status_code = 500
                logger.error("Unhandled exception processing request: {err}", err=str(ex))
            finally:
                elapsed_ms = (time.perf_counter() - t_start) * 1000.0
                http_req_duration.record(elapsed_ms)
                http_req_counter.add(1, {"http.status_code": str(status_code), "endpoint": "checkout"})

                root_activity.set_tag("http.status_code", status_code)
                logger.info("Request finished in {duration:.2f}ms - Status {status}",
                            duration=elapsed_ms, status=status_code)


# ============================================================================
# 5. LAB BENCHMARK & DIAGNOSTIC RUNNER
# ============================================================================

def main():
    print(f"\n{CLR_BOLD}{CLR_TRACE}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_TRACE}  ASP.NET Core Observability & Diagnostics: Live Runtime Simulation  {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_TRACE}======================================================================{CLR_RESET}\n")

    # Define synthetic concurrent workloads
    requests_payload = [
        ("CUST-001", "SKU-LAPTOP-X", 1299.99),
        ("CUST-002", "SKU-OUT-OF-STOCK", 49.99),
        ("ACC-FAULTY", "SKU-MOUSE-G", 29.50),
        ("CUST-004", "SKU-KEYBOARD-M", 89.00),
        ("CUST-005", "SKU-MONITOR-4K", 450.00),
    ]

    threads = []
    print(f"{CLR_BOLD}[1] Spawning Multi-Threaded HTTP Pipeline Worker Execution...{CLR_RESET}\n")

    for i, payload in enumerate(requests_payload):
        t = threading.Thread(
            target=diagnostic_http_middleware,
            args=(payload[0], payload[1], payload[2], i + 1),
            name=f"Worker-{i+1}"
        )
        threads.append(t)
        t.start()
        time.sleep(0.015)  # Slight stagger to demonstrate interleaving

    for t in threads:
        t.join()

    # Metrics Aggregation and Reporting
    print(f"\n{CLR_BOLD}{CLR_METRIC}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_METRIC}  DIAGNOSTICS & TELEMETRY SUMMARY (OpenTelemetry / Prometheus Export) {CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_METRIC}======================================================================{CLR_RESET}\n")

    print(f"{CLR_BOLD}>> Meter: {app_meter.name}{CLR_RESET}")

    # Counter Metrics
    for name, counter in app_meter.counters.items():
        print(f"\n  Metric (Counter): {CLR_INFO}{name}{CLR_RESET}")
        print(f"  Description: {counter.description}")
        snap = counter.snapshot()
        for tags, count in snap.items():
            formatted_tags = "{" + ", ".join(f"{k}=\"{v}\"" for k, v in tags) + "}"
            print(f"    {formatted_tags} -> {CLR_BOLD}{count}{CLR_RESET}")

    # Histogram Metrics
    for name, hist in app_meter.histograms.items():
        stats = hist.stats()
        print(f"\n  Metric (Histogram): {CLR_INFO}{name}{CLR_RESET} ({hist.unit})")
        print(f"    Count Recorded: {stats['count']}")
        print(f"    p50 (Median)  : {stats['p50']:.2f} ms")
        print(f"    p95           : {stats['p95']:.2f} ms")
        print(f"    p99           : {stats['p99']:.2f} ms")

    print(f"\n{CLR_BOLD}{CLR_INFO}[SUCCESS]{CLR_RESET} Telemetry capture, distributed trace tree, and structured logs complete.\n")


if __name__ == "__main__":
    main()
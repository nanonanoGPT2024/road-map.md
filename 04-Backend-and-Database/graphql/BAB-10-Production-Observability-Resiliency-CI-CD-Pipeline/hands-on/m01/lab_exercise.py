#!/usr/bin/env python3
"""
Lab Exercise: Production Observability, Resiliency, & CI/CD Pipeline Simulation
BAB-10 GraphQL Production Architecture Foundation
================================================================================
Simulasi teknis mandiri:
1. Schema Breaking Change Checker (CI/CD Inspector)
2. Query Complexity & Depth Limiter (Resiliency Gate)
3. Subgraph Circuit Breaker (Resilient Resolver Execution)
4. OpenTelemetry Tracing & Field-level Metrics Collector (Observability)
"""

import sys
import time
import json
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

# ANSI Color formatting
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    DIM     = "\033[2m"

# -----------------------------------------------------------------------------
# 1. CI/CD: SCHEMA REGISTRY & BREAKING CHANGE DETECTION
# -----------------------------------------------------------------------------
class ChangeType(Enum):
    SAFE = "NON_BREAKING"
    BREAKING = "BREAKING_CHANGE"

@dataclass
class SchemaChange:
    field: str
    change_type: ChangeType
    description: str

class SchemaInspector:
    """Simulasi linting & schema diff ala Rover / GraphQL-Inspector pada CI/CD"""
    @staticmethod
    def compare_schemas(old_schema: Dict[str, List[str]], new_schema: Dict[str, List[str]]) -> List[SchemaChange]:
        changes = []
        for type_name, old_fields in old_schema.items():
            if type_name not in new_schema:
                changes.append(SchemaChange(
                    field=type_name,
                    change_type=ChangeType.BREAKING,
                    description=f"Type '{type_name}' was removed from schema."
                ))
                continue
            
            new_fields = new_schema[type_name]
            for f in old_fields:
                if f not in new_fields:
                    changes.append(SchemaChange(
                        field=f"{type_name}.{f}",
                        change_type=ChangeType.BREAKING,
                        description=f"Field '{f}' removed from type '{type_name}'."
                    ))
            
            for f in new_fields:
                if f not in old_fields:
                    changes.append(SchemaChange(
                        field=f"{type_name}.{f}",
                        change_type=ChangeType.SAFE,
                        description=f"Field '{f}' added to type '{type_name}'."
                    ))
        return changes

# -----------------------------------------------------------------------------
# 2. RESILIENCY: QUERY COMPLEXITY & DEPTH ANALYZER
# -----------------------------------------------------------------------------
class QueryGuard:
    """Mencegah serangan DDoS / nesting queries ekstrem melalui static analysis"""
    def __init__(self, max_depth: int = 4, max_complexity: int = 100):
        self.max_depth = max_depth
        self.max_complexity = max_complexity

    def analyze(self, query_ast: Dict[str, Any], current_depth: int = 1) -> Tuple[int, int]:
        depth = current_depth
        complexity = 1
        
        for k, sub_tree in query_ast.items():
            if isinstance(sub_tree, dict):
                sub_depth, sub_comp = self.analyze(sub_tree, current_depth + 1)
                depth = max(depth, sub_depth)
                complexity += sub_comp + 2
            else:
                complexity += 1
                
        return depth, complexity

# -----------------------------------------------------------------------------
# 3. RESILIENCY: CIRCUIT BREAKER PATTERN
# -----------------------------------------------------------------------------
class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreaker:
    """Melindungi gateway dari upstream downstream cascading failure"""
    def __init__(self, failure_threshold: int = 3, recovery_time: float = 2.0):
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_timestamp = 0.0

    def can_execute(self) -> bool:
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_timestamp > self.recovery_time:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        return True

    def record_success(self):
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_timestamp = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

# -----------------------------------------------------------------------------
# 4. OBSERVABILITY: TRACING & METRICS COLLECTOR
# -----------------------------------------------------------------------------
@dataclass
class TraceSpan:
    name: str
    duration_ms: float
    status: str
    attributes: Dict[str, Any] = field(default_factory=dict)

class ObservabilityCollector:
    """Telemetry collector mirip OpenTelemetry & Apollo Studio Metrics"""
    def __init__(self):
        self.spans: List[TraceSpan] = []
        self.field_latencies: Dict[str, List[float]] = {}
        self.error_count: int = 0
        self.success_count: int = 0

    def record_span(self, name: str, duration_ms: float, status: str, attributes: Optional[Dict[str, Any]] = None):
        span = TraceSpan(name, duration_ms, status, attributes or {})
        self.spans.append(span)
        if name not in self.field_latencies:
            self.field_latencies[name] = []
        self.field_latencies[name].append(duration_ms)
        if status == "OK":
            self.success_count += 1
        else:
            self.error_count += 1

    def print_telemetry_dashboard(self):
        print(f"\n{C.BOLD}{C.CYAN}┌─────────────────────────────────────────────────────────────┐{C.RESET}")
        print(f"{C.BOLD}{C.CYAN}│             GRAPHQL OBSERVABILITY DASHBOARD                 │{C.RESET}")
        print(f"{C.BOLD}{C.CYAN}└─────────────────────────────────────────────────────────────┘{C.RESET}")
        
        total_reqs = self.success_count + self.error_count
        err_rate = (self.error_count / total_reqs * 100) if total_reqs > 0 else 0.0
        
        print(f" {C.WHITE}Total Invocations :{C.RESET} {total_reqs}")
        print(f" {C.GREEN}Success Count     :{C.RESET} {self.success_count}")
        print(f" {C.RED}Error Count       :{C.RESET} {self.error_count} ({err_rate:.1f}%)")
        print(f"\n {C.BOLD}{C.YELLOW}Field Resolver Latency (p50/avg ms):{C.RESET}")
        for field_name, latencies in self.field_latencies.items():
            avg_lat = sum(latencies) / len(latencies)
            max_lat = max(latencies)
            status_color = C.GREEN if avg_lat < 40 else (C.YELLOW if avg_lat < 80 else C.RED)
            print(f"  • {field_name:<28}: avg={status_color}{avg_lat:5.1f}ms{C.RESET} (max={max_lat:5.1f}ms, calls={len(latencies)})")

# -----------------------------------------------------------------------------
# GRAPHQL RUNTIME ENGINE SIMULATION
# -----------------------------------------------------------------------------
class ResilientGraphQLServer:
    def __init__(self):
        self.guard = QueryGuard(max_depth=3, max_complexity=15)
        self.order_circuit = CircuitBreaker(failure_threshold=2, recovery_time=1.5)
        self.telemetry = ObservabilityCollector()
        
        # Microservice simulated data
        self.db_users = {"u1": {"id": "u1", "name": "Budi Santoso", "email": "budi@example.com"}}
        self.db_orders = {"u1": [{"id": "ord_99", "amount": 450000, "status": "COMPLETED"}]}

    def execute_query(self, query_name: str, query_ast: Dict[str, Any], simulate_downstream_failure: bool = False) -> Dict[str, Any]:
        print(f"\n{C.BOLD}{C.MAGENTA}>>> Menerima Query:{C.RESET} {C.BOLD}{query_name}{C.RESET}")
        start_time = time.time()
        
        # Phase 1: Static Resiliency Analysis
        depth, complexity = self.guard.analyze(query_ast)
        print(f"  {C.CYAN}[Static Guard]{C.RESET} Depth: {depth}/{self.guard.max_depth} | Complexity: {complexity}/{self.guard.max_complexity}")
        
        if depth > self.guard.max_depth:
            err_msg = f"Query rejected: Depth {depth} exceeds limit {self.guard.max_depth}!"
            print(f"  {C.RED}✗ {err_msg}{C.RESET}")
            self.telemetry.record_span(f"Query:{query_name}", (time.time() - start_time) * 1000, "ERROR_DEPTH_EXCEEDED")
            return {"errors": [{"message": err_msg}]}
            
        if complexity > self.guard.max_complexity:
            err_msg = f"Query rejected: Complexity {complexity} exceeds limit {self.guard.max_complexity}!"
            print(f"  {C.RED}✗ {err_msg}{C.RESET}")
            self.telemetry.record_span(f"Query:{query_name}", (time.time() - start_time) * 1000, "ERROR_COMPLEXITY_EXCEEDED")
            return {"errors": [{"message": err_msg}]}

        # Phase 2: Resolvers Execution with Tracing & Circuit Breaker
        response_data: Dict[str, Any] = {}
        
        # Resolver User
        t0 = time.time()
        time.sleep(0.015)  # 15ms db query simulation
        response_data["user"] = {"id": "u1", "name": "Budi Santoso"}
        dur_user = (time.time() - t0) * 1000
        self.telemetry.record_span("Query.user", dur_user, "OK")
        print(f"  {C.GREEN}✓ Resolving 'Query.user'{C.RESET} in {dur_user:.1f}ms")

        # Nested Resolver Orders (Dependent on Downstream Order Microservice)
        if "user" in query_ast and "orders" in query_ast["user"]:
            t_ord = time.time()
            if not self.order_circuit.can_execute():
                print(f"  {C.YELLOW}⚠ Circuit Breaker OPEN untuk 'Order-Service'! Graceful fallback diaktifkan.{C.RESET}")
                response_data["user"]["orders"] = None  # Graceful partial degradation
                dur_ord = (time.time() - t_ord) * 1000
                self.telemetry.record_span("User.orders", dur_ord, "CIRCUIT_OPEN_FALLBACK")
            else:
                if simulate_downstream_failure:
                    time.sleep(0.05)
                    self.order_circuit.record_failure()
                    dur_ord = (time.time() - t_ord) * 1000
                    print(f"  {C.RED}✗ Downstream 'Order-Service' timeout/500! (Failures: {self.order_circuit.failure_count}){C.RESET}")
                    self.telemetry.record_span("User.orders", dur_ord, "ERROR_UPSTREAM_TIMEOUT")
                    response_data["user"]["orders"] = None
                else:
                    time.sleep(0.025)  # 25ms resolver time
                    self.order_circuit.record_success()
                    response_data["user"]["orders"] = self.db_orders.get("u1", [])
                    dur_ord = (time.time() - t_ord) * 1000
                    self.telemetry.record_span("User.orders", dur_ord, "OK")
                    print(f"  {C.GREEN}✓ Resolving 'User.orders'{C.RESET} in {dur_ord:.1f}ms")

        total_duration = (time.time() - start_time) * 1000
        self.telemetry.record_span(f"Query:{query_name}", total_duration, "OK")
        print(f"  {C.CYAN}Total Execution Time:{C.RESET} {total_duration:.1f}ms")
        return {"data": response_data}

# -----------------------------------------------------------------------------
# MAIN CLI INTERACTIVE LAB
# -----------------------------------------------------------------------------
def run_lab():
    print(f"{C.BOLD}{C.BLUE}================================================================={C.RESET}")
    print(f"{C.BOLD}{C.WHITE}  GRAPHQL PRODUCTION LAB: OBSERVABILITY, RESILIENCY & CI/CD       {C.RESET}")
    print(f"{C.BOLD}{C.BLUE}================================================================={C.RESET}")

    # Step 1: CI/CD Pipeline Schema Linting Simulation
    print(f"\n{C.BOLD}{C.YELLOW}[STAGE 1: CI/CD AUTOMATED SCHEMA INSPECTOR CHECK]{C.RESET}")
    v1_schema = {
        "User": ["id", "name", "email", "phoneNumber"],
        "Order": ["id", "totalAmount"]
    }
    v2_schema_candidate = {
        "User": ["id", "fullName", "email"],  # 'name' removed (breaking), 'phoneNumber' removed (breaking)
        "Order": ["id", "totalAmount", "status"]  # 'status' added (safe)
    }

    print(f"Memeriksa PR: {C.WHITE}feat/update-user-fields -> main{C.RESET}...")
    diff_report = SchemaInspector.compare_schemas(v1_schema, v2_schema_candidate)
    has_breaking = False
    for change in diff_report:
        if change.change_type == ChangeType.BREAKING:
            has_breaking = True
            print(f" {C.RED}[CI/CD BLOCKED]{C.RESET} {change.field}: {change.description}")
        else:
            print(f" {C.GREEN}[CI/CD PASSED]{C.RESET}  {change.field}: {change.description}")

    if has_breaking:
        print(f"  {C.BOLD}{C.RED}==> Status CI/CD: Pipeline FAILED. Breaking changes terdeteksi tanpa deprecation!{C.RESET}")
    else:
        print(f"  {C.BOLD}{C.GREEN}==> Status CI/CD: Pipeline PASSED. Schema kompatibel.{C.RESET}")

    # Step 2: Runtime Resiliency & Query Protection
    print(f"\n{C.BOLD}{C.YELLOW}[STAGE 2: RUNTIME RESILIENCY & OBSERVABILITY TESTING]{C.RESET}")
    server = ResilientGraphQLServer()

    # Query 1: Valid Normal Query
    q1 = {"user": {"id": True, "name": True, "orders": {"id": True}}}
    server.execute_query("GetUserDataWithOrders", q1, simulate_downstream_failure=False)

    # Query 2: Deep nested malicious query (DDoS attempt)
    q2 = {
        "user": {
            "orders": {
                "user": {
                    "orders": {
                        "user": True
                    }
                }
            }
        }
    }
    server.execute_query("MaliciousDeepNestedQuery", q2)

    # Query 3: Downstream Service Intermittent Errors -> Triggering Circuit Breaker
    print(f"\n{C.DIM}--- Menstimulasikan 3 Kegagalan Beruntun pada Subgraph Downstream ---{C.RESET}")
    server.execute_query("GetUserDataOrders_Fail1", q1, simulate_downstream_failure=True)
    server.execute_query("GetUserDataOrders_Fail2", q1, simulate_downstream_failure=True)
    
    # Query 4: Permintaan berikutnya saat Circuit Breaker telah OPEN
    print(f"\n{C.DIM}--- Request saat Circuit Breaker Aktif (Melindungi Gateway) ---{C.RESET}")
    server.execute_query("GetUserDataOrders_AfterTrip", q1, simulate_downstream_failure=False)

    # Step 3: Observability Metrics Dashboard
    server.telemetry.print_telemetry_dashboard()

    print(f"\n{C.BOLD}{C.GREEN}✔ Selesai: Simulasi Observability, Resiliency, dan CI/CD GraphQL Berhasil!{C.RESET}\n")

if __name__ == "__main__":
    run_lab()

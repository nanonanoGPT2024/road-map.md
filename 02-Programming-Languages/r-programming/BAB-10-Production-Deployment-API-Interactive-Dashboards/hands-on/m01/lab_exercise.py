#!/usr/bin/env python3
"""
Lab Exercise M01: Production Deployment, API, & Interactive Dashboards (R Paradigm Simulation)
BAB-10: R Plumber REST API & Shiny Reactive Engine Architecture Simulator

This script provides an interactive CLI and architectural simulation of:
1. R Plumber API routing, decorators/roxygen tags (@get, @post, @filter), and OpenAPI serialization.
2. Shiny Reactive Dependency Graph (ReactiveVal, ReactiveExpr, Observer, Flush cycle).
3. Production Microservice Container Lifecycle (Health checks, Concurrency load test, Latency metric).
"""

import sys
import time
import json
import random
from typing import Callable, Dict, List, Any, Set
from dataclasses import dataclass, field

# ANSI Terminal Styling
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_RED = "\033[31m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_BLUE = "\033[34m"
C_MAGENTA = "\033[35m"
C_CYAN = "\033[36m"
C_BG_BLUE = "\033[44m"


def print_banner():
    banner = f"""{C_CYAN}{C_BOLD}
================================================================================
   R PRODUCTION RUNTIME & DASHBOARD ARCHITECTURE SIMULATOR
   Module: BAB-10 Production Deployment, Plumber API & Shiny Reactivity
================================================================================{C_RESET}"""
    print(banner)


# ------------------------------------------------------------------------------
# 1. R PLUMBER API ENGINE SIMULATION
# ------------------------------------------------------------------------------
@dataclass
class PlumberEndpoint:
    path: str
    method: str
    handler: Callable
    description: str


class PlumberRouter:
    """Simulates R Plumber API router with filters and roxygen-style routing."""
    def __init__(self, service_name: str = "R-Model-Service"):
        self.service_name = service_name
        self.endpoints: List[PlumberEndpoint] = []
        self.filters: List[Callable] = []

    def filter(self, fn: Callable):
        self.filters.append(fn)
        return fn

    def register(self, method: str, path: str, description: str):
        def decorator(fn: Callable):
            self.endpoints.append(PlumberEndpoint(path, method.upper(), fn, description))
            return fn
        return decorator

    def handle_request(self, method: str, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        # Filter pipeline
        context = {"method": method.upper(), "path": path, "params": params, "status": 200}
        for flt in self.filters:
            proceed = flt(context)
            if not proceed:
                return {"status": context.get("status", 403), "error": "Filtered / Unauthorized"}

        for ep in self.endpoints:
            if ep.method == method.upper() and ep.path == path:
                try:
                    result = ep.handler(params)
                    return {"status": 200, "data": result, "path": path}
                except Exception as e:
                    return {"status": 500, "error": str(e), "path": path}

        return {"status": 404, "error": f"Endpoint not found: {method.upper()} {path}"}

    def print_openapi_spec(self):
        print(f"\n{C_MAGENTA}{C_BOLD}=== OpenAPI / Swagger Specification (R Plumber Equivalent) ==={C_RESET}")
        spec = {
            "openapi": "3.0.0",
            "info": {"title": self.service_name, "version": "1.0.0"},
            "paths": {}
        }
        for ep in self.endpoints:
            if ep.path not in spec["paths"]:
                spec["paths"][ep.path] = {}
            spec["paths"][ep.path][ep.method.lower()] = {
                "summary": ep.description,
                "responses": {"200": {"description": "Successful operation"}}
            }
        print(f"{C_DIM}{json.dumps(spec, indent=2)}{C_RESET}")


# ------------------------------------------------------------------------------
# 2. SHINY REACTIVE ENGINE SIMULATION
# ------------------------------------------------------------------------------
class ReactiveContext:
    active_observer: Any = None


class ReactiveVal:
    """Simulates R Shiny reactiveVal() state container."""
    def __init__(self, initial_value: Any, name: str = "state"):
        self._value = initial_value
        self.name = name
        self._observers: Set["Observer"] = set()

    def get(self) -> Any:
        if ReactiveContext.active_observer is not None:
            self._observers.add(ReactiveContext.active_observer)
        return self._value

    def set(self, new_value: Any):
        if self._value != new_value:
            self._value = new_value
            self.notify()

    def notify(self):
        # In Shiny, invalidation marks downstream nodes dirty
        for obs in list(self._observers):
            obs.invalidate()


class ReactiveExpr:
    """Simulates R Shiny reactive() expression caching."""
    def __init__(self, calc_fn: Callable, name: str = "expr"):
        self.calc_fn = calc_fn
        self.name = name
        self._cached_value: Any = None
        self._is_clean = False
        self._observers: Set["Observer"] = set()

    def get(self) -> Any:
        if ReactiveContext.active_observer is not None:
            self._observers.add(ReactiveContext.active_observer)

        if not self._is_clean:
            old_ctx = ReactiveContext.active_observer
            # Self as observer to inputs
            proxy_obs = Observer(self._invalidate, name=f"proxy_{self.name}")
            ReactiveContext.active_observer = proxy_obs
            self._cached_value = self.calc_fn()
            ReactiveContext.active_observer = old_ctx
            self._is_clean = True
        return self._cached_value

    def _invalidate(self):
        self._is_clean = False
        for obs in list(self._observers):
            obs.invalidate()


class Observer:
    """Simulates R Shiny observe() / observeEvent() reactive consumer."""
    def __init__(self, callback: Callable, name: str = "observer"):
        self.callback = callback
        self.name = name

    def invalidate(self):
        self.run()

    def run(self):
        old_ctx = ReactiveContext.active_observer
        ReactiveContext.active_observer = self
        try:
            self.callback()
        finally:
            ReactiveContext.active_observer = old_ctx


# ------------------------------------------------------------------------------
# 3. INTERACTIVE SIMULATION ROUTINES
# ------------------------------------------------------------------------------
def run_plumber_simulation():
    print(f"\n{C_BLUE}{C_BOLD}[1] Initializing R Plumber REST API Router Engine...{C_RESET}")
    router = PlumberRouter("R-Predictive-Engine-API")

    # Plumber @filter logger
    @router.filter
    def auth_and_log(ctx: Dict[str, Any]) -> bool:
        auth_header = ctx["params"].get("token", "anon")
        print(f"  {C_YELLOW}[Plumber Filter]{C_RESET} Request to {C_BOLD}{ctx['path']}{C_RESET} | Auth: {auth_header}")
        return True

    # Plumber @get /health
    @router.register("GET", "/health", "Healthcheck and container status")
    def health(params):
        return {"status": "UP", "runtime": "R 4.3.2", "memory_mb": round(random.uniform(120, 240), 2)}

    # Plumber @post /predict
    @router.register("POST", "/predict", "Run linear regression inference on input covariates")
    def predict(params):
        features = params.get("features", [1.0, 2.0, 3.0])
        # Simple simulated weights: Y = 2.5 + sum(x_i * 1.8)
        intercept = 2.5
        prediction = intercept + sum(x * 1.8 for x in features)
        return {
            "features_received": features,
            "prediction": round(prediction, 4),
            "model_version": "v2.1.0-prod"
        }

    # Print OpenAPI schema
    router.print_openapi_spec()

    # Simulate dispatch
    print(f"\n{C_CYAN}--- Executing Simulated HTTP Inbound Requests ---{C_RESET}")
    req1 = router.handle_request("GET", "/health", {"token": "bearer-xyz"})
    print(f"  {C_GREEN}<- Response (GET /health):{C_RESET} {json.dumps(req1)}")

    time.sleep(0.3)
    sample_feat = [round(random.uniform(0.5, 5.0), 2) for _ in range(3)]
    req2 = router.handle_request("POST", "/predict", {"features": sample_feat, "token": "bearer-xyz"})
    print(f"  {C_GREEN}<- Response (POST /predict):{C_RESET} {json.dumps(req2)}")


def run_shiny_simulation():
    print(f"\n{C_BLUE}{C_BOLD}[2] Initializing R Shiny Reactive Dependency Graph...{C_RESET}")
    
    # 1. Reactive Sources (Inputs)
    slider_input = ReactiveVal(10, name="input$sample_size")
    multiplier_input = ReactiveVal(1.5, name="input$scale_factor")

    # 2. Reactive Conductor (Intermediate calculation)
    def compute_summary():
        n = slider_input.get()
        factor = multiplier_input.get()
        print(f"    {C_MAGENTA}[Shiny Reactive Calc]{C_RESET} Recomputing cached summary for n={n}, factor={factor}...")
        return {"n": n, "scaled_sum": round(n * factor * 10.25, 2)}

    calc_summary = ReactiveExpr(compute_summary, name="data_summary()")

    # 3. Reactive Endpoints (UI Output Renderers)
    def render_dashboard_widget():
        res = calc_summary.get()
        print(f"  {C_GREEN}>>> [UI renderTable()]{C_RESET} Rendered Output Widget: N={res['n']} | Scaled Metric={res['scaled_sum']}")

    Observer(render_dashboard_widget, name="output$summary_table")

    # Initial flush
    print(f"{C_DIM}Initial State Render Cycle:{C_RESET}")
    render_dashboard_widget()

    # Dynamic Updates
    print(f"\n{C_CYAN}--- Simulating User Interacting with Shiny UI Slider ---{C_RESET}")
    print(f"{C_YELLOW}Event:{C_RESET} User slides sample size from 10 -> 25")
    slider_input.set(25)

    time.sleep(0.3)
    print(f"{C_YELLOW}Event:{C_RESET} User adjusts multiplier from 1.5 -> 3.0")
    multiplier_input.set(3.0)


def run_production_stress_test():
    print(f"\n{C_BLUE}{C_BOLD}[3] Simulating Production Deployment & Load Concurrency...{C_RESET}")
    print(f"  {C_DIM}Target: Dockerized R Plumber Process (Single-threaded R worker simulation){C_RESET}")

    requests_count = 15
    latencies = []

    print(f"\n  {'REQ ID':<8} | {'PAYLOAD':<12} | {'SIM LATENCY':<15} | {'STATUS'}")
    print("  " + "-" * 50)

    for i in range(1, requests_count + 1):
        sim_latency = round(random.uniform(15.2, 85.7), 2)
        latencies.append(sim_latency)
        status_color = C_GREEN if sim_latency < 60.0 else C_YELLOW
        status_text = "200 OK" if sim_latency < 75.0 else "200 OK (Slow Queue)"
        print(f"  #{i:<7} | p_{i:<10} | {sim_latency:>6.2f} ms       | {status_color}{status_text}{C_RESET}")
        time.sleep(0.04)

    avg_lat = sum(latencies) / len(latencies)
    p95_lat = sorted(latencies)[int(len(latencies) * 0.95)]

    print(f"\n{C_CYAN}{C_BOLD}=== Deployment Performance Summary ==={C_RESET}")
    print(f"  Total Inbound Transactions: {requests_count}")
    print(f"  Mean Request Latency      : {C_BOLD}{avg_lat:.2f} ms{C_RESET}")
    print(f"  P95 Latency               : {C_BOLD}{p95_lat:.2f} ms{C_RESET}")
    print(f"  Container Healthcheck     : {C_GREEN}PASSED (HTTP 200 /health){C_RESET}")


def interactive_menu():
    print_banner()
    while True:
        print(f"\n{C_BOLD}Available Laboratory Modules:{C_RESET}")
        print(f"  {C_CYAN}[1]{C_RESET} Plumber REST API Engine (Routing & OpenAPI Spec)")
        print(f"  {C_CYAN}[2]{C_RESET} Shiny Reactive Invalidation Graph Simulation")
        print(f"  {C_CYAN}[3]{C_RESET} Containerized Production Load & Concurrency Benchmark")
        print(f"  {C_CYAN}[4]{C_RESET} Run Complete Automated Verification Suite")
        print(f"  {C_RED}[q]{C_RESET} Exit")

        try:
            choice = input(f"\n{C_BOLD}Select an option [1-4, q]: {C_RESET}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{C_YELLOW}Exiting lab exercise session.{C_RESET}")
            break

        if choice == "1":
            run_plumber_simulation()
        elif choice == "2":
            run_shiny_simulation()
        elif choice == "3":
            run_production_stress_test()
        elif choice == "4":
            run_plumber_simulation()
            run_shiny_simulation()
            run_production_stress_test()
            print(f"\n{C_GREEN}{C_BOLD}All production & reactive architecture modules executed successfully!{C_RESET}")
        elif choice == "q":
            print(f"{C_YELLOW}Session terminated.{C_RESET}")
            break
        else:
            print(f"{C_RED}Invalid option selected. Please try again.{C_RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        print_banner()
        run_plumber_simulation()
        run_shiny_simulation()
        run_production_stress_test()
    else:
        interactive_menu()

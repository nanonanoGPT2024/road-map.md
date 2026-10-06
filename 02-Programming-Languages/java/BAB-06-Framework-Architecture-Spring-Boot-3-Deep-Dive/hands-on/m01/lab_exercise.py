#!/usr/bin/env python3
"""
Lab Exercise M01: Spring Boot 3 Architectural Mechanics Simulation
Modul: BAB-06 Framework Architecture Spring Boot 3 Deep Dive

Simulasi teknis interaktif berbasis terminal (ANSI Colors):
1. Inversion of Control (IoC) Container & Dependency Injection Engine
2. Conditional Auto-Configuration Pipeline (@ConditionalOnMissingBean / Property)
3. DispatcherServlet HTTP Request Processing Pipeline & Middleware
4. Spring Boot 3 Observability (Micrometer Observation API & Health Actuator)
"""

import sys
import time
import inspect
from typing import Dict, Any, Callable, List, Optional
from dataclasses import dataclass, field
from enum import Enum


# ==========================================
# Terminal ANSI Color & Formatting Constants
# ==========================================
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"


def print_banner(text: str):
    width = 75
    border = "=" * width
    print(f"\n{Colors.CYAN}{Colors.BOLD}{border}")
    print(f" {text}".center(width))
    print(f"{border}{Colors.RESET}\n")


def print_step(step_num: int, title: str):
    print(f"{Colors.BOLD}{Colors.YELLOW}[PHASE {step_num}] {title}{Colors.RESET}")


def log_info(module: str, msg: str):
    print(f"{Colors.GREEN}[INFO]{Colors.RESET} {Colors.MAGENTA}[{module}]{Colors.RESET} {msg}")


def log_debug(module: str, msg: str):
    print(f"{Colors.DIM}[DEBUG]{Colors.RESET} {Colors.BLUE}[{module}]{Colors.RESET} {msg}")


def log_warn(module: str, msg: str):
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {Colors.MAGENTA}[{module}]{Colors.RESET} {msg}")


def log_error(module: str, msg: str):
    print(f"{Colors.RED}[ERROR]{Colors.RESET} {Colors.MAGENTA}[{module}]{Colors.RESET} {msg}")


# ==========================================
# 1. IoC Container & Bean Registry Engine
# ==========================================
class BeanScope(Enum):
    SINGLETON = "SINGLETON"
    PROTOTYPE = "PROTOTYPE"


@dataclass
class BeanDefinition:
    name: str
    bean_class: type
    scope: BeanScope = BeanScope.SINGLETON
    instance: Optional[Any] = None
    factory: Optional[Callable[[], Any]] = None
    dependencies: List[str] = field(default_factory=list)


class SimpleApplicationContext:
    """Simulates Spring Boot's ConfigurableApplicationContext & BeanFactory."""

    def __init__(self):
        self._registry: Dict[str, BeanDefinition] = {}
        self._singletons: Dict[str, Any] = {}
        self._conditions: Dict[str, Callable[[], bool]] = {}

    def register_condition(self, bean_name: str, predicate: Callable[[], bool]):
        self._conditions[bean_name] = predicate

    def register_bean_definition(
        self,
        name: str,
        bean_class: type,
        scope: BeanScope = BeanScope.SINGLETON,
        factory: Optional[Callable[[], Any]] = None,
    ):
        params = list(inspect.signature(bean_class.__init__).parameters.keys())[1:]
        self._registry[name] = BeanDefinition(
            name=name,
            bean_class=bean_class,
            scope=scope,
            factory=factory,
            dependencies=params,
        )
        log_debug("ApplicationContext", f"Registered BeanDefinition: {name} (Scope: {scope.value})")

    def get_bean(self, name: str) -> Any:
        if name not in self._registry:
            raise KeyError(f"NoSuchBeanDefinitionException: No bean named '{name}' is defined")

        definition = self._registry[name]

        # Check conditional registration
        if name in self._conditions and not self._conditions[name]():
            raise RuntimeError(f"BeanCreationException: ConditionalOnProperty matched false for '{name}'")

        if definition.scope == BeanScope.SINGLETON:
            if name in self._singletons:
                return self._singletons[name]
            instance = self._create_bean_instance(definition)
            self._singletons[name] = instance
            return instance
        else:
            return self._create_bean_instance(definition)

    def _create_bean_instance(self, defn: BeanDefinition) -> Any:
        log_info("BeanFactory", f"Instantiating bean [{defn.name}] via Constructor Injection...")
        if defn.factory:
            return defn.factory()

        resolved_deps = {}
        for dep in defn.dependencies:
            log_debug("DependencyResolver", f"Resolving constructor parameter '{dep}' for bean [{defn.name}]")
            # Look up dependency by matching name or type
            matched_bean_name = None
            for reg_name in self._registry:
                if reg_name.lower() in dep.lower() or dep.lower() in reg_name.lower():
                    matched_bean_name = reg_name
                    break

            if not matched_bean_name:
                raise RuntimeError(f"UnsatisfiedDependencyException: No qualifying bean found for '{dep}'")

            resolved_deps[dep] = self.get_bean(matched_bean_name)

        instance = defn.bean_class(**resolved_deps)
        log_info("BeanFactory", f"Successfully initialized bean instance: {defn.name} -> {instance}")
        return instance

    def refresh(self):
        log_info("ApplicationContext", "Refreshing ApplicationContext: Pre-instantiating singletons...")
        for name, defn in self._registry.items():
            if defn.scope == BeanScope.SINGLETON:
                # Evaluate conditions
                if name in self._conditions and not self._conditions[name]():
                    log_warn("ConditionEvaluationReport", f"Skipping bean '{name}' due to negative condition match.")
                    continue
                self.get_bean(name)
        log_info("ApplicationContext", f"ApplicationContext active. Total singletons: {len(self._singletons)}")


# ==========================================
# 2. Simulated Domain Components
# ==========================================
class PaymentGateway:
    def process_charge(self, amount: float) -> str:
        return f"Charged ${amount:.2f} via Default Mock Gateway"


class StripePaymentGateway(PaymentGateway):
    def process_charge(self, amount: float) -> str:
        return f"Charged ${amount:.2f} via Production Stripe API v3"


class OrderRepository:
    def __init__(self):
        self._db = {}

    def save(self, order_id: str, amount: float):
        self._db[order_id] = amount
        return f"Order {order_id} stored in database"


class OrderService:
    def __init__(self, payment_gateway: PaymentGateway, order_repository: OrderRepository):
        self.gateway = payment_gateway
        self.repository = order_repository

    def create_order(self, order_id: str, amount: float) -> Dict[str, Any]:
        charge_result = self.gateway.process_charge(amount)
        save_result = self.repository.save(order_id, amount)
        return {
            "orderId": order_id,
            "amount": amount,
            "payment": charge_result,
            "persistence": save_result,
            "status": "COMPLETED",
        }


# ==========================================
# 3. DispatcherServlet & Web Request Pipeline
# ==========================================
@dataclass
class HttpRequest:
    method: str
    path: str
    body: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class HttpResponse:
    status_code: int
    body: Any
    headers: Dict[str, str] = field(default_factory=dict)


class HandlerInterceptor:
    def pre_handle(self, req: HttpRequest) -> bool:
        return True

    def post_handle(self, req: HttpRequest, res: HttpResponse):
        pass


class LoggingInterceptor(HandlerInterceptor):
    def pre_handle(self, req: HttpRequest) -> bool:
        log_info("DispatcherServlet", f"--> Incoming HTTP {req.method} {req.path}")
        return True

    def post_handle(self, req: HttpRequest, res: HttpResponse):
        status_color = Colors.GREEN if res.status_code == 200 else Colors.RED
        log_info("DispatcherServlet", f"<-- Completed with Status {status_color}{res.status_code}{Colors.RESET}")


class DispatcherServlet:
    """Simulates Spring MVC DispatcherServlet routing & handler mapping."""

    def __init__(self, ctx: SimpleApplicationContext):
        self.ctx = ctx
        self.handlers: Dict[str, Callable[[HttpRequest], HttpResponse]] = {}
        self.interceptors: List[HandlerInterceptor] = [LoggingInterceptor()]

    def register_endpoint(self, path: str, handler: Callable[[HttpRequest], HttpResponse]):
        self.handlers[path] = handler
        log_debug("RequestMappingHandlerMapping", f"Mapped URL path [{path}] onto handler method")

    def service(self, req: HttpRequest) -> HttpResponse:
        for interceptor in self.interceptors:
            if not interceptor.pre_handle(req):
                return HttpResponse(403, {"error": "Request rejected by interceptor"})

        if req.path not in self.handlers:
            res = HttpResponse(404, {"error": "Not Found", "path": req.path})
        else:
            handler = self.handlers[req.path]
            try:
                res = handler(req)
            except Exception as e:
                res = HttpResponse(500, {"error": "InternalServerError", "message": str(e)})

        for interceptor in reversed(self.interceptors):
            interceptor.post_handle(req, res)

        return res


# ==========================================
# 4. Spring Boot 3 Observation & Actuator
# ==========================================
class MicrometerObservationRegistry:
    """Simulates Spring Boot 3 Micrometer Observation Registry for Tracing & Metrics."""

    def __init__(self):
        self.metrics: Dict[str, int] = {}
        self.trace_spans: List[Dict[str, Any]] = []

    def record_observation(self, name: str, execution_time_ms: float, tags: Dict[str, str]):
        self.metrics[name] = self.metrics.get(name, 0) + 1
        span = {
            "observation": name,
            "durationMs": execution_time_ms,
            "tags": tags,
            "timestamp": time.time(),
        }
        self.trace_spans.append(span)
        log_info(
            "ObservationRegistry",
            f"Observation recorded: '{name}' duration={execution_time_ms:.2f}ms tags={tags}",
        )


# ==========================================
# Interactive Lab Workflows
# ==========================================
def run_ioc_demo():
    print_step(1, "IoC Container Initialization & Constructor Injection")
    ctx = SimpleApplicationContext()

    # Register Beans
    ctx.register_bean_definition("payment_gateway", StripePaymentGateway)
    ctx.register_bean_definition("order_repository", OrderRepository)
    ctx.register_bean_definition("order_service", OrderService)

    ctx.refresh()

    print(f"\n{Colors.BOLD}Resolving OrderService bean from ApplicationContext...{Colors.RESET}")
    order_svc: OrderService = ctx.get_bean("order_service")
    result = order_svc.create_order("ORD-9801", 149.99)

    print(f"{Colors.CYAN}Execution Result:{Colors.RESET}")
    for k, v in result.items():
        print(f"  {Colors.BOLD}{k}:{Colors.RESET} {v}")


def run_conditional_autoconfig_demo():
    print_step(2, "Spring Boot Auto-Configuration & @Conditional Evaluation")
    ctx = SimpleApplicationContext()

    config_property_enabled = False
    log_info("Environment", f"spring.payment.stripe.enabled = {config_property_enabled}")

    # Conditional Bean Definitions
    ctx.register_bean_definition("stripe_gateway", StripePaymentGateway)
    ctx.register_condition("stripe_gateway", lambda: config_property_enabled)

    # Fallback Bean simulating @ConditionalOnMissingBean
    ctx.register_bean_definition("payment_gateway", PaymentGateway)
    ctx.register_bean_definition("order_repository", OrderRepository)
    ctx.register_bean_definition("order_service", OrderService)

    ctx.refresh()

    order_svc: OrderService = ctx.get_bean("order_service")
    result = order_svc.create_order("ORD-AUTOCONFIG-01", 75.00)
    print(f"{Colors.GREEN}Active Payment Gateway used: {order_svc.gateway.__class__.__name__}{Colors.RESET}")
    print(f"Payload: {result}")


def run_dispatcher_servlet_demo():
    print_step(3, "Spring Boot 3 DispatcherServlet Request Handling & Actuator")
    ctx = SimpleApplicationContext()
    ctx.register_bean_definition("payment_gateway", StripePaymentGateway)
    ctx.register_bean_definition("order_repository", OrderRepository)
    ctx.register_bean_definition("order_service", OrderService)
    ctx.refresh()

    order_svc: OrderService = ctx.get_bean("order_service")
    obs_registry = MicrometerObservationRegistry()

    dispatcher = DispatcherServlet(ctx)

    # Endpoint: POST /api/v1/orders
    def handle_create_order(req: HttpRequest) -> HttpResponse:
        start_t = time.perf_counter()
        body = req.body
        res = order_svc.create_order(body.get("orderId", "UNK"), body.get("amount", 0.0))
        elapsed = (time.perf_counter() - start_t) * 1000
        obs_registry.record_observation("http.server.requests", elapsed, {"uri": req.path, "status": "200"})
        return HttpResponse(200, res)

    # Endpoint: GET /actuator/health (Spring Boot Actuator)
    def handle_health(req: HttpRequest) -> HttpResponse:
        health_payload = {
            "status": "UP",
            "components": {
                "db": {"status": "UP", "details": {"database": "PostgreSQL 16", "validationQuery": "isValid()"}},
                "diskSpace": {"status": "UP", "details": {"total": 512000000000, "free": 320000000000}},
            },
        }
        return HttpResponse(200, health_payload)

    dispatcher.register_endpoint("/api/v1/orders", handle_create_order)
    dispatcher.register_endpoint("/actuator/health", handle_health)

    print(f"\n{Colors.BOLD}Dispatching Request 1: POST /api/v1/orders{Colors.RESET}")
    req1 = HttpRequest("POST", "/api/v1/orders", body={"orderId": "ORD-BOOT3-77", "amount": 299.50})
    res1 = dispatcher.service(req1)
    print(f"Response Body: {res1.body}")

    print(f"\n{Colors.BOLD}Dispatching Request 2: GET /actuator/health{Colors.RESET}")
    req2 = HttpRequest("GET", "/actuator/health")
    res2 = dispatcher.service(req2)
    print(f"Actuator Health Status: {res2.body}")


def main_interactive_menu():
    print_banner("SPRING BOOT 3 ARCHITECTURE & RUNTIME MECHANICS LAB")
    print(f"{Colors.WHITE}Welcome to the interactive architectural lab for Spring Boot 3 Deep Dive.{Colors.RESET}")
    print(f"{Colors.DIM}This simulation exercises IoC Container, Dependency Injection, DispatcherServlet,{Colors.RESET}")
    print(f"{Colors.DIM}Condition evaluation, and Micrometer Observation telemetry.{Colors.RESET}\n")

    while True:
        print(f"\n{Colors.CYAN}{Colors.BOLD}--- SELECT SIMULATION MODE ---{Colors.RESET}")
        print("  1. Run Phase 1: IoC Container & Constructor Dependency Injection")
        print("  2. Run Phase 2: Conditional Auto-Configuration Engine")
        print("  3. Run Phase 3: DispatcherServlet HTTP Lifecycle & Actuator Health")
        print("  4. Execute Full Architecture Pipeline Suite")
        print("  5. Exit")

        choice = input(f"\n{Colors.YELLOW}Enter selection (1-5) [Default: 4]: {Colors.RESET}").strip()
        if not choice:
            choice = "4"

        print("\n" + "-" * 75)
        if choice == "1":
            run_ioc_demo()
        elif choice == "2":
            run_conditional_autoconfig_demo()
        elif choice == "3":
            run_dispatcher_servlet_demo()
        elif choice == "4":
            run_ioc_demo()
            time.sleep(0.5)
            run_conditional_autoconfig_demo()
            time.sleep(0.5)
            run_dispatcher_servlet_demo()
            print(f"\n{Colors.BG_GREEN}{Colors.BOLD} ALL ARCHITECTURAL SIMULATION TESTS PASSED {Colors.RESET}\n")
            break
        elif choice == "5" or choice.lower() in ["exit", "q"]:
            print(f"{Colors.GREEN}Exiting lab exercise. Happy learning!{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Invalid option selected. Please choose between 1 and 5.{Colors.RESET}")


if __name__ == "__main__":
    try:
        main_interactive_menu()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Simulation interrupted by user.{Colors.RESET}")
        sys.exit(0)

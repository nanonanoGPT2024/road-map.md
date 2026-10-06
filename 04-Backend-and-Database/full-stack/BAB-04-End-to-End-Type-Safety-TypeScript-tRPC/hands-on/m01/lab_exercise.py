#!/usr/bin/env python3
"""
Lab Exercise M01: End-to-End Type Safety Simulation (TypeScript + tRPC Concept)
BAB-04: End-to-End Type Safety TypeScript & tRPC

Simulasi teknis konsep fondasi tRPC pada arsitektur full-stack:
- Type Inference & Static Contract sharing (Server -> Client tanpa codegen)
- Input Validation (Zod equivalent runtime parser)
- Middleware & Context Pipeline (Authentication & Session Injection)
- Procedures (Query & Mutation)
- Proxy Client Caller dengan Runtime Type Contract Validation
"""

import sys
import json
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum


# ==============================================================================
# 1. ANSI Terminal Styling Utilities
# ==============================================================================
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
    BG_MAGENTA = "\033[45m"


def header(title: str) -> None:
    print(f"\n{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} {title} {Color.RESET}")
    print(f"{Color.CYAN}{'=' * 65}{Color.RESET}")


def subheader(title: str) -> None:
    print(f"\n{Color.MAGENTA}{Color.BOLD}>>> {title}{Color.RESET}")


def log_success(msg: str) -> None:
    print(f"  {Color.GREEN}✔ [OK]{Color.RESET} {msg}")


def log_error(msg: str) -> None:
    print(f"  {Color.RED}✖ [FAIL]{Color.RESET} {msg}")


def log_info(label: str, val: Any) -> None:
    print(f"  {Color.CYAN}ℹ [{label}]:{Color.RESET} {val}")


# ==============================================================================
# 2. Schema Validation Layer (Simulating Zod)
# ==============================================================================
class ValidationError(Exception):
    def __init__(self, issues: List[str]):
        super().__init__("; ".join(issues))
        self.issues = issues


class BaseSchema:
    def parse(self, value: Any) -> Any:
        raise NotImplementedError


class StringSchema(BaseSchema):
    def __init__(self, min_len: int = 0, email: bool = False):
        self.min_len = min_len
        self.email = email

    def parse(self, value: Any) -> str:
        if not isinstance(value, str):
            raise ValidationError([f"Expected string, received {type(value).__name__}"])
        if len(value) < self.min_len:
            raise ValidationError([f"String must contain at least {self.min_len} character(s)"])
        if self.email and ("@" not in value or "." not in value):
            raise ValidationError([f"Invalid email address format: '{value}'"])
        return value


class NumberSchema(BaseSchema):
    def __init__(self, positive: bool = False):
        self.positive = positive

    def parse(self, value: Any) -> int:
        if not isinstance(value, (int, float)):
            raise ValidationError([f"Expected number, received {type(value).__name__}"])
        if self.positive and value <= 0:
            raise ValidationError(["Number must be positive (> 0)"])
        return int(value)


class ObjectSchema(BaseSchema):
    def __init__(self, shape: Dict[str, BaseSchema]):
        self.shape = shape

    def parse(self, value: Any) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise ValidationError([f"Expected object/dict, received {type(value).__name__}"])
        result = {}
        issues = []
        for key, schema in self.shape.items():
            if key not in value:
                issues.append(f"Missing required field: '{key}'")
                continue
            try:
                result[key] = schema.parse(value[key])
            except ValidationError as err:
                for issue in err.issues:
                    issues.append(f"field '{key}': {issue}")
        if issues:
            raise ValidationError(issues)
        return result


class z:
    """Zod namespace builder helper."""
    @staticmethod
    def string(min_len: int = 0, email: bool = False) -> StringSchema:
        return StringSchema(min_len=min_len, email=email)

    @staticmethod
    def number(positive: bool = False) -> NumberSchema:
        return NumberSchema(positive=positive)

    @staticmethod
    def object(shape: Dict[str, BaseSchema]) -> ObjectSchema:
        return ObjectSchema(shape)


# ==============================================================================
# 3. tRPC Core: Context, Errors, and Procedure Types
# ==============================================================================
class TRPCErrorCode(Enum):
    BAD_REQUEST = "BAD_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"


class TRPCError(Exception):
    def __init__(self, code: TRPCErrorCode, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class TRPCContext:
    session_user: Optional[Dict[str, Any]] = None
    req_id: str = field(default_factory=lambda: f"req_{int(time.time()*1000)%100000}")


class ProcedureType(Enum):
    QUERY = "query"
    MUTATION = "mutation"


class Procedure:
    def __init__(
        self,
        proc_type: ProcedureType,
        input_schema: Optional[BaseSchema] = None,
        middlewares: Optional[List[Callable]] = None,
        resolver: Optional[Callable] = None,
    ):
        self.proc_type = proc_type
        self.input_schema = input_schema
        self.middlewares = middlewares or []
        self.resolver = resolver

    def execute(self, ctx: TRPCContext, raw_input: Any) -> Any:
        # 1. Run Input Validation via Schema (Zod)
        parsed_input = raw_input
        if self.input_schema:
            try:
                parsed_input = self.input_schema.parse(raw_input)
            except ValidationError as ve:
                raise TRPCError(
                    TRPCErrorCode.BAD_REQUEST,
                    f"Zod Validation Failed: {ve}"
                )

        # 2. Execute Middlewares
        for mw in self.middlewares:
            ctx = mw(ctx, parsed_input)

        # 3. Execute Resolver
        if not self.resolver:
            raise TRPCError(TRPCErrorCode.INTERNAL_SERVER_ERROR, "No resolver defined.")
        return self.resolver(ctx=ctx, input_data=parsed_input)


# ==============================================================================
# 4. Procedure Builders & Router Definition
# ==============================================================================
class ProcedureBuilder:
    def __init__(self, middlewares: Optional[List[Callable]] = None, input_schema: Optional[BaseSchema] = None):
        self._middlewares = middlewares or []
        self._input_schema = input_schema

    def input(self, schema: BaseSchema) -> "ProcedureBuilder":
        return ProcedureBuilder(self._middlewares, schema)

    def use(self, middleware: Callable) -> "ProcedureBuilder":
        return ProcedureBuilder(self._middlewares + [middleware], self._input_schema)

    def query(self, resolver: Callable) -> Procedure:
        return Procedure(
            proc_type=ProcedureType.QUERY,
            input_schema=self._input_schema,
            middlewares=self._middlewares,
            resolver=resolver,
        )

    def mutation(self, resolver: Callable) -> Procedure:
        return Procedure(
            proc_type=ProcedureType.MUTATION,
            input_schema=self._input_schema,
            middlewares=self._middlewares,
            resolver=resolver,
        )


def enforce_auth_middleware(ctx: TRPCContext, raw_input: Any) -> TRPCContext:
    if not ctx.session_user:
        raise TRPCError(
            TRPCErrorCode.UNAUTHORIZED,
            "You must be authenticated to execute this procedure."
        )
    return ctx


# Root builders
public_procedure = ProcedureBuilder()
protected_procedure = ProcedureBuilder().use(enforce_auth_middleware)


class TRPCRouter:
    def __init__(self, routes: Dict[str, Any]):
        self.routes = routes

    def resolve(self, path: str) -> Procedure:
        parts = path.split(".")
        curr: Any = self.routes
        for part in parts:
            if isinstance(curr, dict) and part in curr:
                curr = curr[part]
            else:
                raise TRPCError(
                    TRPCErrorCode.NOT_FOUND,
                    f"Procedure '{path}' does not exist on AppRouter."
                )
        if not isinstance(curr, Procedure):
            raise TRPCError(
                TRPCErrorCode.NOT_FOUND,
                f"Path '{path}' is a sub-router, not an executable procedure."
            )
        return curr


# ==============================================================================
# 5. Application Router Implementation (Server-Side)
# ==============================================================================
# Mock In-Memory Database
USER_DB: Dict[str, Dict[str, Any]] = {
    "usr_01": {"id": "usr_01", "name": "Budi Santoso", "email": "budi@example.com", "role": "admin"},
    "usr_02": {"id": "usr_02", "name": "Siti Aminah", "email": "siti@example.com", "role": "developer"},
}

app_router = TRPCRouter({
    "user": {
        # Query: Fetch user by ID (public)
        "getById": public_procedure
            .input(z.object({"id": z.string(min_len=3)}))
            .query(lambda ctx, input_data: (
                USER_DB.get(input_data["id"])
                or (_ for _ in ()).throw(
                    TRPCError(TRPCErrorCode.NOT_FOUND, f"User {input_data['id']} not found")
                )
            )),

        # Query: List all users (protected: admin/member only)
        "list": protected_procedure
            .query(lambda ctx, input_data: list(USER_DB.values())),

        # Mutation: Create new user (protected)
        "create": protected_procedure
            .input(z.object({
                "name": z.string(min_len=3),
                "email": z.string(email=True),
            }))
            .mutation(lambda ctx, input_data: (
                new_id := f"usr_{len(USER_DB) + 1:02d}",
                USER_DB.update({
                    new_id: {
                        "id": new_id,
                        "name": input_data["name"],
                        "email": input_data["email"],
                        "role": "user",
                        "createdBy": ctx.session_user["name"],
                    }
                }),
                USER_DB[new_id]
            )[-1]),
    }
})


# ==============================================================================
# 6. Type-Safe Client Proxy Implementation (Client-Side)
# ==============================================================================
class TRPCClient:
    """
    Simulates `createTRPCClient<AppRouter>({})`.
    In TypeScript, AppRouter type provides full compile-time autocomplete and type checking.
    Here we simulate runtime RPC dispatch and client-side contract checks.
    """
    def __init__(self, server_router: TRPCRouter, context_provider: Callable[[], TRPCContext]):
        self.router = server_router
        self.context_provider = context_provider

    def call(self, path: str, input_payload: Any = None) -> Any:
        ctx = self.context_provider()
        proc = self.router.resolve(path)
        return proc.execute(ctx, input_payload)


# ==============================================================================
# 7. Interactive Test Suite & Lab Demonstrations
# ==============================================================================
def run_simulation() -> None:
    header("LAB EXERCISE: END-TO-END TYPE SAFETY WITH tRPC ARCHITECTURE")
    print(f"{Color.DIM}Simulating TypeScript Compile-Time Contracts & Zod Runtime Boundary{Color.RESET}\n")

    current_session: Dict[str, Optional[Dict[str, Any]]] = {"user": None}

    def client_context_factory() -> TRPCContext:
        return TRPCContext(session_user=current_session["user"])

    trpc = TRPCClient(app_router, client_context_factory)

    # --------------------------------------------------------------------------
    # Scenario 1: Public Query with Valid Input
    # --------------------------------------------------------------------------
    subheader("1. Public Query: trpc.user.getById.query({ id: 'usr_01' })")
    try:
        res = trpc.call("user.getById", {"id": "usr_01"})
        log_success("Query resolved with exact inferred return type:")
        print(f"     {Color.YELLOW}{json.dumps(res, indent=2)}{Color.RESET}")
    except TRPCError as e:
        log_error(f"Unexpected error: {e.code.value} - {e.message}")

    # --------------------------------------------------------------------------
    # Scenario 2: Zod Input Validation Rejection (Bad Request)
    # --------------------------------------------------------------------------
    subheader("2. Input Validation Failure: trpc.user.getById.query({ id: 'x' })")
    try:
        trpc.call("user.getById", {"id": "x"})
        log_error("Failed: Should have been rejected by schema validation!")
    except TRPCError as e:
        log_success(f"Type Boundary Guarded! [HTTP 400 Equivalent]")
        log_info("Code", e.code.value)
        log_info("Message", e.message)

    # --------------------------------------------------------------------------
    # Scenario 3: Protected Procedure Rejection (Unauthorized)
    # --------------------------------------------------------------------------
    subheader("3. Protected Guard: trpc.user.list.query() without Session")
    try:
        trpc.call("user.list")
        log_error("Failed: Unauthenticated call should be forbidden!")
    except TRPCError as e:
        log_success(f"Middleware Pipeline Activated! [HTTP 401 Equivalent]")
        log_info("Code", e.code.value)
        log_info("Message", e.message)

    # --------------------------------------------------------------------------
    # Scenario 4: Authentication & Protected Query
    # --------------------------------------------------------------------------
    subheader("4. Establishing Session & Executing Protected Procedure")
    current_session["user"] = {"id": "adm_99", "name": "System Administrator", "role": "admin"}
    log_info("Active Session", current_session["user"]["name"])

    try:
        user_list = trpc.call("user.list")
        log_success(f"Fetched {len(user_list)} records securely via protected procedure:")
        for u in user_list:
            print(f"     - [{u['id']}] {u['name']} ({u['email']}) -> {u['role']}")
    except TRPCError as e:
        log_error(f"Failed: {e.message}")

    # --------------------------------------------------------------------------
    # Scenario 5: Protected Mutation with Strict Zod Object Schema
    # --------------------------------------------------------------------------
    subheader("5. Mutation Execution: trpc.user.create.mutate(...)")
    invalid_payload = {"name": "Jo", "email": "invalid-email-string"}
    print(f"  Attempting mutation with invalid payload: {invalid_payload}")
    try:
        trpc.call("user.create", invalid_payload)
        log_error("Mutation should fail on validation!")
    except TRPCError as e:
        log_success(f"Validation Guarded:")
        print(f"     {Color.RED}{e.message}{Color.RESET}")

    valid_payload = {"name": "Dewi Sartika", "email": "dewi@example.com"}
    print(f"\n  Attempting mutation with valid payload: {valid_payload}")
    try:
        new_user = trpc.call("user.create", valid_payload)
        log_success("User created successfully via Type-Safe Mutation:")
        print(f"     {Color.GREEN}{json.dumps(new_user, indent=2)}{Color.RESET}")
    except TRPCError as e:
        log_error(f"Failed to create user: {e.message}")

    # --------------------------------------------------------------------------
    # Scenario 6: Non-existent Procedure (Route Level Type-Safety)
    # --------------------------------------------------------------------------
    subheader("6. Route Mismatch Detection: trpc.analytics.getStats.query()")
    try:
        trpc.call("analytics.getStats")
        log_error("Route should not exist!")
    except TRPCError as e:
        log_success("Router correctly flagged unmatched procedure:")
        log_info("Code", e.code.value)
        log_info("Message", e.message)

    # --------------------------------------------------------------------------
    # Summary Table
    # --------------------------------------------------------------------------
    header("SUMMARY: THE TRPC & END-TO-END TYPE-SAFETY ADVANTAGE")
    summary_items = [
        ("No Code Generation", "Server export type AppRouter diimpor langsung oleh client tsconfig."),
        ("Zod Schema Guard", "Runtime validation otomatis menyinkronkan types TypeScript & data wire."),
        ("Context & Middleware", "Pipeline autentikasi context-aware menjamin keamanan di level resolver."),
        ("Compile-Time Catch", "Perubahan nama endpoint atau tipe data langsung merah di editor IDE."),
    ]
    for key, desc in summary_items:
        print(f"  {Color.BOLD}{Color.CYAN}• {key:<22}:{Color.RESET} {desc}")
    print(f"\n{Color.GREEN}{Color.BOLD}✓ Semua verifikasi simulasi type-safety berhasil dijalankan tanpa error.{Color.RESET}\n")


if __name__ == "__main__":
    run_simulation()

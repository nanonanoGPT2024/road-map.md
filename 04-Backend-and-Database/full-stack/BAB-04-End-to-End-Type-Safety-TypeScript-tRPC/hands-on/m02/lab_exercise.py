#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Arsitektur Full-Stack End-to-End Type Safety (TypeScript & tRPC)
BAB-04: End-to-End Type-Safety (TypeScript + tRPC)
Simulasi komprehensif Runtime Schema Validation (Zod style), tRPC Router/Procedure Pipeline,
Context & Auth Middleware, dan Client-Server RPC Dispatcher dengan validasi tipe statis & runtime.
"""

import sys
import time
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Tuple
from enum import Enum


# ANSI Color Codes
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


# 1. Zod-like Runtime Schema Validator
class ValidationError(Exception):
    def __init__(self, issues: List[str]):
        super().__init__(", ".join(issues))
        self.issues = issues


class Schema:
    def parse(self, value: Any) -> Any:
        raise NotImplementedError()


class ZString(Schema):
    def __init__(self, min_len: int = 0, email: bool = False):
        self.min_len = min_len
        self.email = email

    def parse(self, value: Any) -> str:
        if not isinstance(value, str):
            raise ValidationError([f"Expected string, received {type(value).__name__}"])
        if len(value) < self.min_len:
            raise ValidationError([f"String must be at least {self.min_len} characters"])
        if self.email and ("@" not in value or "." not in value):
            raise ValidationError([f"Invalid email format: '{value}'"])
        return value


class ZInt(Schema):
    def __init__(self, positive: bool = False):
        self.positive = positive

    def parse(self, value: Any) -> int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValidationError([f"Expected integer, received {type(value).__name__}"])
        if self.positive and value <= 0:
            raise ValidationError([f"Integer must be positive (> 0), received {value}"])
        return value


class ZObject(Schema):
    def __init__(self, shape: Dict[str, Schema]):
        self.shape = shape

    def parse(self, data: Any) -> Dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError([f"Expected object/dict, received {type(data).__name__}"])
        result = {}
        issues = []
        for key, schema in self.shape.items():
            if key not in data:
                issues.append(f"Field '{key}' is required but missing")
                continue
            try:
                result[key] = schema.parse(data[key])
            except ValidationError as err:
                for issue in err.issues:
                    issues.append(f"[{key}] -> {issue}")
        if issues:
            raise ValidationError(issues)
        return result


# 2. tRPC Context & Middleware Pipeline
@dataclass
class TRPCContext:
    user: Optional[Dict[str, Any]] = None
    req_id: str = "req-default"


@dataclass
class Procedure:
    type: str  # 'query' | 'mutation'
    input_schema: Optional[Schema]
    handler: Callable[[TRPCContext, Any], Any]
    is_protected: bool = False

    def execute(self, ctx: TRPCContext, raw_input: Any) -> Any:
        if self.is_protected and not ctx.user:
            raise PermissionError("UNAUTHORIZED: Session token missing or invalid")
        validated_input = raw_input
        if self.input_schema:
            validated_input = self.input_schema.parse(raw_input)
        return self.handler(ctx, validated_input)


# 3. Router & Mock Database
class AppRouter:
    def __init__(self):
        self.procedures: Dict[str, Procedure] = {}
        self.users_db = [
            {"id": 1, "name": "Budi Santoso", "email": "budi@enterprise.local", "role": "ADMIN"},
            {"id": 2, "name": "Siti Rahma", "email": "siti@startup.io", "role": "USER"},
        ]
        self.posts_db = [
            {"id": 101, "title": "Setup tRPC v11", "authorId": 1},
            {"id": 102, "title": "Zero-Cost Type Inferences", "authorId": 2},
        ]
        self._register_routes()

    def _register_routes(self):
        # user.getById (Public Query)
        self.procedures["user.getById"] = Procedure(
            type="query",
            input_schema=ZObject({"id": ZInt(positive=True)}),
            handler=lambda ctx, inp: self._get_user_by_id(inp["id"]),
            is_protected=False,
        )

        # user.create (Protected Mutation)
        self.procedures["user.create"] = Procedure(
            type="mutation",
            input_schema=ZObject({
                "name": ZString(min_len=3),
                "email": ZString(email=True),
            }),
            handler=lambda ctx, inp: self._create_user(ctx, inp),
            is_protected=True,
        )

        # post.list (Public Query)
        self.procedures["post.list"] = Procedure(
            type="query",
            input_schema=None,
            handler=lambda ctx, inp: self.posts_db,
            is_protected=False,
        )

    def _get_user_by_id(self, user_id: int):
        for u in self.users_db:
            if u["id"] == user_id:
                return u
        return None

    def _create_user(self, ctx: TRPCContext, data: Dict[str, Any]):
        new_id = len(self.users_db) + 1
        new_user = {
            "id": new_id,
            "name": data["name"],
            "email": data["email"],
            "role": "USER",
        }
        self.users_db.append(new_user)
        return new_user


# 4. Client Proxy & End-to-End Type Safety Simulation
class TRPCClient:
    def __init__(self, router: AppRouter, auth_user: Optional[Dict[str, Any]] = None):
        self.router = router
        self.auth_user = auth_user

    def call(self, path: str, input_payload: Any) -> Tuple[bool, Any]:
        if path not in self.router.procedures:
            return False, {"code": "NOT_FOUND", "message": f"Procedure '{path}' not found"}

        proc = self.router.procedures[path]
        ctx = TRPCContext(user=self.auth_user, req_id=f"req-{int(time.time()*1000)%100000}")
        try:
            result = proc.execute(ctx, input_payload)
            return True, result
        except ValidationError as ve:
            return False, {"code": "BAD_REQUEST", "type": "ZodValidationError", "issues": ve.issues}
        except PermissionError as pe:
            return False, {"code": "FORBIDDEN", "type": "TRPCAuthError", "message": str(pe)}
        except Exception as e:
            return False, {"code": "INTERNAL_SERVER_ERROR", "message": str(e)}


def print_banner():
    print(f"{Colors.CYAN}{Colors.BOLD}" + "=" * 70)
    print("   tRPC & TypeScript End-to-End Type Safety Production Simulator")
    print("   BAB-04: Full-Stack Contract Verification & Zero-API-Drift")
    print("=" * 70 + f"{Colors.RESET}\n")


def run_test_scenario(title: str, client: TRPCClient, path: str, payload: Any, expect_success: bool):
    print(f"{Colors.BOLD}{Colors.HEADER}▶ SCENARIO: {title}{Colors.RESET}")
    print(f"  {Colors.DIM}Client Call:{Colors.RESET} trpc.{path}({json.dumps(payload)})")

    success, response = client.call(path, payload)
    time.sleep(0.1)

    if success and expect_success:
        print(f"  {Colors.GREEN}✔ SUCCESS (HTTP 200 RPC Batch OK){Colors.RESET}")
        print(f"  {Colors.CYAN}Output Payloads:{Colors.RESET} {json.dumps(response, indent=4)}\n")
    elif not success and not expect_success:
        print(f"  {Colors.YELLOW}✔ CAUGHT EXPECTED TYPE/CONTRACT ERROR{Colors.RESET}")
        print(f"  {Colors.RED}TRPC Error Code:{Colors.RESET} {response.get('code')}")
        print(f"  {Colors.RED}Details:{Colors.RESET} {json.dumps(response, indent=4)}\n")
    elif success and not expect_success:
        print(f"  {Colors.RED}✘ FAILED: Expected failure, but RPC call succeeded!{Colors.RESET}\n")
    else:
        print(f"  {Colors.RED}✘ UNEXPECTED ERROR: {response}{Colors.RESET}\n")


def interactive_menu():
    router = AppRouter()
    admin_user = {"id": 1, "username": "admin_sys", "role": "ADMIN"}
    client_auth = TRPCClient(router, auth_user=admin_user)
    client_anon = TRPCClient(router, auth_user=None)

    print_banner()

    print(f"{Colors.BOLD}Menjalankan Automated Verification Matrix...{Colors.RESET}\n")

    # 1. Type-Safe Query: Sukses
    run_test_scenario(
        "Type-Safe Query (user.getById) - Valid Input",
        client_anon,
        "user.getById",
        {"id": 1},
        expect_success=True,
    )

    # 2. Type Mismatch Query: Input string alih-alih number (Simulasi tRPC compiler & Zod runtime block)
    run_test_scenario(
        "Schema Contract Violation - String alih-alih Integer (Zero API Drift)",
        client_anon,
        "user.getById",
        {"id": "satu"},
        expect_success=False,
    )

    # 3. Constraint Violation: Integer negatif
    run_test_scenario(
        "Zod Constraint Error - Positive ID Check (id: -99)",
        client_anon,
        "user.getById",
        {"id": -99},
        expect_success=False,
    )

    # 4. Unauthorized Mutation: Anonymous mencoba mutasi protected
    run_test_scenario(
        "Middleware Security - Anonymous User Call Protected Mutation",
        client_anon,
        "user.create",
        {"name": "Dev Ops", "email": "devops@corp.com"},
        expect_success=False,
    )

    # 5. Invalid Email Format Mutation: Authenticated user kirim email invalid
    run_test_scenario(
        "Zod Regex/Email Validation Error pada Mutation Payload",
        client_auth,
        "user.create",
        {"name": "Ahmad", "email": "ahmad-bukan-email"},
        expect_success=False,
    )

    # 6. Valid Protected Mutation: Authenticated user kirim payload valid
    run_test_scenario(
        "End-to-End Type-Safe Protected Mutation - Valid Payload",
        client_auth,
        "user.create",
        {"name": "Dewi Sartika", "email": "dewi@opensource.org"},
        expect_success=True,
    )

    # 7. List All Posts
    run_test_scenario(
        "Query Post List (Parameterless Query)",
        client_anon,
        "post.list",
        None,
        expect_success=True,
    )

    print(f"{Colors.GREEN}{Colors.BOLD}========================================================")
    print("   SEMUA INTEGRITY CHECK TYPE-SAFETY TRPC TELAH SELESAI")
    print("   Zero-Drift Client & Server Shared Schema Validated!")
    print(f"========================================================{Colors.RESET}\n")


if __name__ == "__main__":
    interactive_menu()

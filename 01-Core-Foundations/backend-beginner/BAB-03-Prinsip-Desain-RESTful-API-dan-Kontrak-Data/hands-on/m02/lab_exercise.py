#!/usr/bin/env python3
"""
Lab Hands-on: Deep Dive Kontrak Data & Prinsip Desain RESTful API
Kategori : 01-Core-Foundations
Bab      : 03 - Prinsip Desain RESTful API & Kontrak Data (Modul 02)

Deskripsi:
Script ini mengimplementasikan kernel RESTful dispatching engine mandiri (tanpa framework
eksternal) yang mensimulasikan protokol HTTP lengkap:
1. Data Contract Enforcement & Schema Validation (tipe data, format, boundary).
2. Standar RFC 7807 (Problem Details for HTTP APIs) untuk error reporting.
3. Arsitektur Idempotensi & Concurrency Control menggunakan ETag (Entity Tag) dan If-Match.
4. Level 3 Richardson Maturity Model (HATEOAS - Hypermedia as the Engine of Application State).
5. Dynamic Path Parameter Matching & HTTP Verb Dispatching (GET, POST, PUT, PATCH, DELETE).
"""

import copy
import datetime
import hashlib
import json
import re
import sys
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

# ==============================================================================
# 0. ANSI Color System untuk Terminal Output Informatif
# ==============================================================================
class TermColor:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    GRAY    = "\033[90m"

def colorize_status(code: int) -> str:
    if 200 <= code < 300:
        return f"{TermColor.GREEN}{code} OK{TermColor.RESET}"
    elif 300 <= code < 400:
        return f"{TermColor.CYAN}{code} REDIRECT{TermColor.RESET}"
    elif 400 <= code < 500:
        return f"{TermColor.YELLOW}{code} CLIENT ERROR{TermColor.RESET}"
    else:
        return f"{TermColor.RED}{code} SERVER ERROR{TermColor.RESET}"


# ==============================================================================
# 1. HTTP Abstraction & RFC 7807 Problem Details
# ==============================================================================
class HTTPRequest:
    def __init__(self, method: str, path: str, headers: Dict[str, str] = None, body: Any = None):
        self.method = method.upper()
        self.path = path
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.body = body

class HTTPResponse:
    def __init__(self, status_code: int, body: Any = None, headers: Dict[str, str] = None):
        self.status_code = status_code
        self.headers = headers or {}
        self.body = body
        if "content-type" not in [k.lower() for k in self.headers]:
            self.headers["Content-Type"] = "application/json"

    def render(self) -> str:
        payload = json.dumps(self.body, indent=2) if self.body is not None else "<No Body Content>"
        raw_headers = "\n".join([f"  {k}: {v}" for k, v in self.headers.items()])
        return (
            f"Status: {colorize_status(self.status_code)}\n"
            f"Headers:\n{TermColor.GRAY}{raw_headers}{TermColor.RESET}\n"
            f"Payload:\n{TermColor.CYAN}{payload}{TermColor.RESET}"
        )

class ProblemDetails:
    """Implementasi kepatuhan spesifikasi RFC 7807 (Problem Details for HTTP APIs)."""
    @staticmethod
    def build(status: int, title: str, detail: str, instance: str, errors: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        doc = {
            "type": f"https://api.example.com/errors/rfc7807/{status}",
            "title": title,
            "status": status,
            "detail": detail,
            "instance": instance,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        if errors:
            doc["invalid_params"] = errors
        return doc


# ==============================================================================
# 2. Schema Validation Engine (Data Contract)
# ==============================================================================
class Field:
    def __init__(self, data_type: type, required: bool = True, min_val: Any = None,
                 max_val: Any = None, regex_pattern: str = None):
        self.data_type = data_type
        self.required = required
        self.min_val = min_val
        self.max_val = max_val
        self.regex_pattern = re.compile(regex_pattern) if regex_pattern else None

    def validate(self, field_name: str, value: Any) -> Optional[Dict[str, str]]:
        if value is None:
            if self.required:
                return {"name": field_name, "reason": "Field ini bersifat wajib (mandatory)."}
            return None

        if not isinstance(value, self.data_type):
            return {
                "name": field_name,
                "reason": f"Tipe data tidak valid. Diharapkan {self.data_type.__name__}, diterima {type(value).__name__}."
            }

        if self.data_type in (int, float):
            if self.min_val is not None and value < self.min_val:
                return {"name": field_name, "reason": f"Nilai minimum yang diizinkan adalah {self.min_val}."}
            if self.max_val is not None and value > self.max_val:
                return {"name": field_name, "reason": f"Nilai maksimum yang diizinkan adalah {self.max_val}."}

        if self.data_type is str:
            if self.min_val is not None and len(value) < self.min_val:
                return {"name": field_name, "reason": f"Panjang karakter minimal adalah {self.min_val}."}
            if self.max_val is not None and len(value) > self.max_val:
                return {"name": field_name, "reason": f"Panjang karakter maksimal adalah {self.max_val}."}
            if self.regex_pattern and not self.regex_pattern.match(value):
                return {"name": field_name, "reason": "Nilai tidak memenuhi format regular expression yang valid."}

        return None

class DataContract:
    def __init__(self, schema: Dict[str, Field]):
        self.schema = schema

    def validate(self, payload: Dict[str, Any], partial: bool = False) -> List[Dict[str, str]]:
        errors = []
        if not isinstance(payload, dict):
            return [{"name": "body", "reason": "Payload HTTP body harus berbentuk objek JSON (dictionary)."}]

        for field_name, rules in self.schema.items():
            if field_name not in payload:
                if rules.required and not partial:
                    errors.append({"name": field_name, "reason": "Field ini bersifat wajib tetapi tidak ditemukan."})
            else:
                err = rules.validate(field_name, payload[field_name])
                if err:
                    errors.append(err)

        # Cek unexpected fields (mencegah mass-assignment vulnerability)
        for key in payload.keys():
            if key not in self.schema:
                errors.append({"name": key, "reason": "Properti tidak dikenal dalam kontrak data API ini."})

        return errors


# ==============================================================================
# 3. Domain Model, HATEOAS Generator, & In-Memory Store
# ==============================================================================
class ProductRepository:
    """Store in-memory yang mengelola persistensi dan komputasi ETag."""
    def __init__(self):
        self._storage: Dict[str, Dict[str, Any]] = {}

    def compute_etag(self, resource: Dict[str, Any]) -> str:
        """Menghasilkan ETag berbasis kriptografi representasi JSON entitas."""
        payload_repr = json.dumps(resource, sort_keys=True)
        digest = hashlib.sha1(payload_repr.encode('utf-8')).hexdigest()
        return f'"{digest[:12]}"'

    def save(self, resource_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self._storage[resource_id] = copy.deepcopy(data)
        return self._storage[resource_id]

    def find_by_id(self, resource_id: str) -> Optional[Dict[str, Any]]:
        if resource_id in self._storage:
            return copy.deepcopy(self._storage[resource_id])
        return None

    def delete(self, resource_id: str) -> bool:
        if resource_id in self._storage:
            del self._storage[resource_id]
            return True
        return False


def build_hateoas_links(base_path: str, resource_id: str) -> Dict[str, Dict[str, str]]:
    """Membangun Hypermedia links sesuai prinsip HATEOAS (Level 3 REST)."""
    return {
        "self": {"href": f"{base_path}/{resource_id}", "method": "GET"},
        "update_replace": {"href": f"{base_path}/{resource_id}", "method": "PUT"},
        "update_partial": {"href": f"{base_path}/{resource_id}", "method": "PATCH"},
        "delete": {"href": f"{base_path}/{resource_id}", "method": "DELETE"},
        "collection": {"href": base_path, "method": "GET"}
    }


# ==============================================================================
# 4. REST Router & Controller Handlers
# ==============================================================================
product_contract = DataContract({
    "sku": Field(str, required=True, regex_pattern=r"^[A-Z]{3}-\d{4}$"),
    "name": Field(str, required=True, min_val=3, max_val=50),
    "price": Field((int, float), required=True, min_val=0.01),
    "stock": Field(int, required=True, min_val=0, max_val=10000),
    "category": Field(str, required=False, min_val=2, max_val=30)
})

repo = ProductRepository()

class ProductController:
    BASE_PATH = "/api/v1/products"

    @classmethod
    def create_product(cls, req: HTTPRequest, **kwargs) -> HTTPResponse:
        errors = product_contract.validate(req.body)
        if errors:
            problem = ProblemDetails.build(
                status=422,
                title="Unprocessable Entity",
                detail="Payload gagal melewati validasi kontrak data.",
                instance=req.path,
                errors=errors
            )
            return HTTPResponse(422, problem)

        resource_id = str(uuid.uuid4())[:8]
        entity = {
            "id": resource_id,
            "sku": req.body["sku"],
            "name": req.body["name"],
            "price": req.body["price"],
            "stock": req.body["stock"],
            "category": req.body.get("category", "Uncategorized"),
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        saved = repo.save(resource_id, entity)
        etag = repo.compute_etag(saved)

        response_body = copy.deepcopy(saved)
        response_body["_links"] = build_hateoas_links(cls.BASE_PATH, resource_id)

        headers = {
            "Location": f"{cls.BASE_PATH}/{resource_id}",
            "ETag": etag
        }
        return HTTPResponse(201, response_body, headers)

    @classmethod
    def get_product(cls, req: HTTPRequest, **kwargs) -> HTTPResponse:
        resource_id = kwargs.get("id")
        entity = repo.find_by_id(resource_id)
        if not entity:
            return HTTPResponse(404, ProblemDetails.build(
                404, "Not Found", f"Resource dengan ID '{resource_id}' tidak ditemukan.", req.path
            ))

        etag = repo.compute_etag(entity)
        # HTTP Conditional Request Handling (304 Not Modified)
        client_inm = req.headers.get("if-none-match")
        if client_inm and client_inm == etag:
            return HTTPResponse(304, None, {"ETag": etag})

        entity["_links"] = build_hateoas_links(cls.BASE_PATH, resource_id)
        return HTTPResponse(200, entity, {"ETag": etag})

    @classmethod
    def update_product_put(cls, req: HTTPRequest, **kwargs) -> HTTPResponse:
        """Operasi Idempoten PUT: Menggantikan representasi resource secara utuh."""
        resource_id = kwargs.get("id")
        existing = repo.find_by_id(resource_id)
        if not existing:
            return HTTPResponse(404, ProblemDetails.build(404, "Not Found", "Resource tidak ditemukan.", req.path))

        # Concurrency check (Optimistic Locking via ETag)
        current_etag = repo.compute_etag(existing)
        if_match = req.headers.get("if-match")
        if if_match and if_match != current_etag:
            return HTTPResponse(412, ProblemDetails.build(
                412, "Precondition Failed",
                "ETag lokal Anda sudah usang (stale). Ambil state terbaru sebelum memperbarui data.",
                req.path
            ))

        errors = product_contract.validate(req.body, partial=False)
        if errors:
            return HTTPResponse(422, ProblemDetails.build(422, "Unprocessable Entity", "Kontrak invalid.", req.path, errors))

        # Replacement utuh, preserve id & created_at
        existing.update({
            "sku": req.body["sku"],
            "name": req.body["name"],
            "price": req.body["price"],
            "stock": req.body["stock"],
            "category": req.body.get("category", "Uncategorized")
        })
        updated = repo.save(resource_id, existing)
        new_etag = repo.compute_etag(updated)

        updated["_links"] = build_hateoas_links(cls.BASE_PATH, resource_id)
        return HTTPResponse(200, updated, {"ETag": new_etag})

    @classmethod
    def patch_product(cls, req: HTTPRequest, **kwargs) -> HTTPResponse:
        """Operasi Non-Idempoten/Partial PATCH: Memodifikasi sebagian field."""
        resource_id = kwargs.get("id")
        existing = repo.find_by_id(resource_id)
        if not existing:
            return HTTPResponse(404, ProblemDetails.build(404, "Not Found", "Resource tidak ditemukan.", req.path))

        errors = product_contract.validate(req.body, partial=True)
        if errors:
            return HTTPResponse(422, ProblemDetails.build(422, "Unprocessable Entity", "Validasi parsial gagal.", req.path, errors))

        for k, v in req.body.items():
            existing[k] = v

        updated = repo.save(resource_id, existing)
        new_etag = repo.compute_etag(updated)
        updated["_links"] = build_hateoas_links(cls.BASE_PATH, resource_id)
        return HTTPResponse(200, updated, {"ETag": new_etag})

    @classmethod
    def delete_product(cls, req: HTTPRequest, **kwargs) -> HTTPResponse:
        resource_id = kwargs.get("id")
        deleted = repo.delete(resource_id)
        if not deleted:
            return HTTPResponse(404, ProblemDetails.build(404, "Not Found", "Resource tidak ditemukan.", req.path))
        # 204 No Content untuk penghapusan sukses tanpa return body
        return HTTPResponse(204, None)


# ==============================================================================
# 5. Core REST Dispatcher Engine
# ==============================================================================
class RESTDispatcher:
    def __init__(self):
        # Format: (Method, Regex Pattern, Handler Callable)
        self.routes: List[Tuple[str, re.Pattern, Callable]] = []

    def register(self, method: str, path_pattern: str, handler: Callable):
        regex_path = re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", r"(?P<\1>[^/]+)", path_pattern)
        compiled = re.compile(f"^{regex_path}$")
        self.routes.append((method.upper(), compiled, handler))

    def dispatch(self, request: HTTPRequest) -> HTTPResponse:
        allowed_methods = []
        for method, regex, handler in self.routes:
            match = regex.match(request.path)
            if match:
                allowed_methods.append(method)
                if method == request.method:
                    params = match.groupdict()
                    return handler(request, **params)

        if allowed_methods:
            # URI ditemukan tetapi HTTP Verb tidak cocok -> 405 Method Not Allowed
            headers = {"Allow": ", ".join(set(allowed_methods))}
            return HTTPResponse(405, ProblemDetails.build(
                405, "Method Not Allowed",
                f"Metode {request.method} tidak diizinkan pada endpoint {request.path}.",
                request.path
            ), headers)

        return HTTPResponse(404, ProblemDetails.build(
            404, "Not Found", f"Endpoint target {request.path} tidak terdaftar.", request.path
        ))


# ==============================================================================
# 6. Test Suite & Simulation Execution
# ==============================================================================
def run_simulation():
    dispatcher = RESTDispatcher()
    base_endpoint = "/api/v1/products"

    dispatcher.register("POST",   base_endpoint,           ProductController.create_product)
    dispatcher.register("GET",    f"{base_endpoint}/{{id}}", ProductController.get_product)
    dispatcher.register("PUT",    f"{base_endpoint}/{{id}}", ProductController.update_product_put)
    dispatcher.register("PATCH",  f"{base_endpoint}/{{id}}", ProductController.patch_product)
    dispatcher.register("DELETE", f"{base_endpoint}/{{id}}", ProductController.delete_product)

    print(f"{TermColor.BOLD}{TermColor.MAGENTA}=== SIMULATOR PROTOKOL RESTful & DATA CONTRACT ENFORCEMENT ==={TermColor.RESET}\n")

    # TEST CASE 1: Validasi Kontrak Data Gagal (RFC 7807 422 Unprocessable Entity)
    print(f"{TermColor.BOLD}Test Case 1: Kontrak Data Gagal (Malformed SKU & Type Mismatch){TermColor.RESET}")
    invalid_req = HTTPRequest(
        method="POST",
        path=base_endpoint,
        body={"sku": "invalid-sku-format", "name": "AB", "price": -50.0, "stock": "bukan_angka"}
    )
    res1 = dispatcher.dispatch(invalid_req)
    print(res1.render())
    print("-" * 75)

    # TEST CASE 2: Pembuatan Resource Sukses (201 Created + ETag + HATEOAS)
    print(f"\n{TermColor.BOLD}Test Case 2: Sukses Membuat Resource (201 Created){TermColor.RESET}")
    valid_req = HTTPRequest(
        method="POST",
        path=base_endpoint,
        body={"sku": "ELC-9012", "name": "Mechanical Keyboard RGB", "price": 89.99, "stock": 40, "category": "Electronics"}
    )
    res2 = dispatcher.dispatch(valid_req)
    print(res2.render())
    created_id = res2.body["id"]
    current_etag = res2.headers["ETag"]
    print("-" * 75)

    # TEST CASE 3: Conditional GET (304 Not Modified menggunakan If-None-Match)
    print(f"\n{TermColor.BOLD}Test Case 3: Conditional GET - ETag Validasi Integritas Cache (304 Not Modified){TermColor.RESET}")
    cached_get = HTTPRequest(
        method="GET",
        path=f"{base_endpoint}/{created_id}",
        headers={"If-None-Match": current_etag}
    )
    res3 = dispatcher.dispatch(cached_get)
    print(res3.render())
    print("-" * 75)

    # TEST CASE 4: Concurrency Conflict - Stale ETag (412 Precondition Failed)
    print(f"\n{TermColor.BOLD}Test Case 4: Optimistic Concurrency Control (412 Precondition Failed){TermColor.RESET}")
    stale_put = HTTPRequest(
        method="PUT",
        path=f"{base_endpoint}/{created_id}",
        headers={"If-Match": '"stale-etag-999"'},
        body={"sku": "ELC-9012", "name": "Mechanical Keyboard RGB", "price": 99.99, "stock": 35}
    )
    res4 = dispatcher.dispatch(stale_put)
    print(res4.render())
    print("-" * 75)

    # TEST CASE 5: Sukses PUT Idempoten dengan Matching ETag
    print(f"\n{TermColor.BOLD}Test Case 5: Operasi PUT Sukses dengan Valid If-Match (200 OK){TermColor.RESET}")
    valid_put = HTTPRequest(
        method="PUT",
        path=f"{base_endpoint}/{created_id}",
        headers={"If-Match": current_etag},
        body={"sku": "ELC-9012", "name": "Mechanical Keyboard RGB Pro Edition", "price": 105.00, "stock": 30}
    )
    res5 = dispatcher.dispatch(valid_put)
    print(res5.render())
    new_etag = res5.headers["ETag"]
    print("-" * 75)

    # TEST CASE 6: Partial Update via PATCH
    print(f"\n{TermColor.BOLD}Test Case 6: Partial Update dengan PATCH (Modifikasi Kolom 'stock' saja){TermColor.RESET}")
    patch_req = HTTPRequest(
        method="PATCH",
        path=f"{base_endpoint}/{created_id}",
        body={"stock": 15}
    )
    res6 = dispatcher.dispatch(patch_req)
    print(res6.render())
    print("-" * 75)

    # TEST CASE 7: 405 Method Not Allowed Simulation
    print(f"\n{TermColor.BOLD}Test Case 7: Pengecekan HTTP Verbs Negatif (405 Method Not Allowed){TermColor.RESET}")
    bad_verb = HTTPRequest(method="PUT", path=base_endpoint, body={})
    res7 = dispatcher.dispatch(bad_verb)
    print(res7.render())
    print("-" * 75)

    # TEST CASE 8: DELETE Resource (204 No Content) disusul GET (404 Not Found)
    print(f"\n{TermColor.BOLD}Test Case 8: Penghapusan Entitas (204 No Content) & Verifikasi Pasca-Hapus (404){TermColor.RESET}")
    del_req = HTTPRequest(method="DELETE", path=f"{base_endpoint}/{created_id}")
    res8 = dispatcher.dispatch(del_req)
    print(res8.render())

    print(f"\nVerifikasi pembuktian status resource pasca-hapus:")
    get_deleted = HTTPRequest(method="GET", path=f"{base_endpoint}/{created_id}")
    res9 = dispatcher.dispatch(get_deleted)
    print(res9.render())
    print("-" * 75)

    print(f"{TermColor.GREEN}{TermColor.BOLD}Lab Eksplorasi Selesai: Seluruh siklus hidup kontrak data RESTful berhasil disimulasikan.{TermColor.RESET}")


if __name__ == "__main__":
    run_simulation()

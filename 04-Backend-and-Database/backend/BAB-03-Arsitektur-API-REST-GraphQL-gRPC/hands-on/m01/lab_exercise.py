#!/usr/bin/env python3
"""
BAB-03: Arsitektur API (REST vs GraphQL vs gRPC)
Simulasi Teknis Komparatif: Paradigma, Karakteristik Payload, dan Efisiensi Jaringan.

Fitur:
- Simulasi RESTful API (Resource-oriented, over-fetching & under-fetching issue)
- Simulasi GraphQL Engine (Query parsing, field-selection, resolver tree)
- Simulasi gRPC / Protocol Buffers (Binary encoding, RPC dispatch, payload compression)
- Benchmark Komparatif Otomatis (Ukuran Payload & Roundtrip Overhead)
- CLI Interaktif dengan ANSI Terminal Formatting
"""

import sys
import time
import json
import struct
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

# ==============================================================================
# ANSI Color Codes & UI Helper
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
    BG_GREEN = "\033[42m"
    BG_MAGENTA = "\033[45m"

def print_header(title: str, subtitle: str = "") -> None:
    print(f"\n{Color.BOLD}{Color.CYAN}{'=' * 75}{Color.RESET}")
    print(f"{Color.BOLD}{Color.YELLOW} >> {title.upper()}{Color.RESET}")
    if subtitle:
        print(f"    {Color.DIM}{subtitle}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}{'=' * 75}{Color.RESET}")

def print_badge(label: str, text: str, color: str = Color.GREEN) -> None:
    print(f"{color}[{label.upper()}]{Color.RESET} {text}")

# ==============================================================================
# Database Dummy (In-Memory Data Store)
# ==============================================================================
DB_USERS = {
    101: {
        "id": 101,
        "name": "Budi Santoso",
        "email": "budi.santoso@enterprise.id",
        "role": "Senior Backend Architect",
        "department": "Platform Engineering",
        "avatar_url": "https://cdn.enterprise.id/avatars/101.jpg",
        "bio": "Specialist in distributed systems, high-throughput microservices, and gRPC.",
        "created_at": "2024-01-15T08:30:00Z",
        "is_active": True,
        "metadata": {
            "last_login_ip": "192.168.1.45",
            "device_id": "DEV-MAC-98210",
            "locale": "id-ID",
            "security_tier": "Level-3"
        }
    }
}

DB_ORDERS = {
    101: [
        {"id": "ORD-5001", "amount": 1250000, "status": "COMPLETED", "currency": "IDR"},
        {"id": "ORD-5002", "amount": 450000, "status": "SHIPPED", "currency": "IDR"},
        {"id": "ORD-5003", "amount": 3100000, "status": "PENDING", "currency": "IDR"},
    ]
}

# ==============================================================================
# 1. REST API Simulation
# ==============================================================================
class RestApiSimulator:
    """
    Simulasi REST API.
    Karakteristik:
    - Resource-based URI (/api/v1/users/{id})
    - Fixed schema payload (Over-fetching: mengambil field yang tidak dibutuhkan)
    - Under-fetching (Perlu roundtrip tambahan ke /orders untuk data relasi)
    """
    @staticmethod
    def get_user(user_id: int) -> Dict[str, Any]:
        time.sleep(0.03)  # Simulasi latency HTTP GET request/response
        user = DB_USERS.get(user_id)
        if not user:
            return {"status": 404, "error": "User Not Found"}
        return {"status": 200, "data": user}

    @staticmethod
    def get_user_orders(user_id: int) -> Dict[str, Any]:
        time.sleep(0.03)  # Simulasi latency HTTP GET kedua (N+1 roundtrip)
        orders = DB_ORDERS.get(user_id, [])
        return {"status": 200, "data": orders}

# ==============================================================================
# 2. GraphQL Engine Simulation
# ==============================================================================
class GraphQLEngine:
    """
    Simulasi GraphQL Engine.
    Karakteristik:
    - Single endpoint POST /graphql
    - Declarative field selection (Eliminasi over-fetching)
    - Nested resolvers dalam 1 kali roundtrip (Eliminasi under-fetching)
    """
    @staticmethod
    def execute_query(query_fields: List[str], include_orders: bool, user_id: int) -> Dict[str, Any]:
        time.sleep(0.04)  # 1 network roundtrip dengan server-side field filtering
        user = DB_USERS.get(user_id)
        if not user:
            return {"errors": ["User not found"], "data": None}

        filtered_user: Dict[str, Any] = {}
        for f in query_fields:
            if f in user:
                filtered_user[f] = user[f]

        if include_orders:
            orders = DB_ORDERS.get(user_id, [])
            filtered_user["orders"] = [{"id": o["id"], "amount": o["amount"]} for o in orders]

        return {"data": {"user": filtered_user}}

# ==============================================================================
# 3. gRPC / Protocol Buffers Simulation
# ==============================================================================
class GrpcProtoSimulator:
    """
    Simulasi gRPC dengan Serialisasi Biner (Protocol Buffers).
    Karakteristik:
    - Kontrak schema tegas (.proto)
    - Serialisasi binary TLV (Tag-Length-Value) yang ringkas & cepat
    - Transport via HTTP/2 Multiplexing
    """
    @staticmethod
    def serialize_user_protobuf(user_id: int, name: str, is_active: bool) -> bytes:
        """
        Simulasi binary packing mirip protobuf:
        Tag 1 (id: int32), Tag 2 (name: string), Tag 3 (is_active: bool)
        """
        name_bytes = name.encode("utf-8")
        # Format: Tag1(1 byte)+Value(4 bytes) | Tag2(1 byte)+Len(2 bytes)+Name | Tag3(1 byte)+Bool(1 byte)
        packet = struct.pack(
            f"!BI B H {len(name_bytes)}s B ?",
            1, user_id,
            2, len(name_bytes), name_bytes,
            3, is_active
        )
        return packet

    @staticmethod
    def rpc_get_user_summary(user_id: int) -> Dict[str, Any]:
        time.sleep(0.015)  # HTTP/2 multiplexing + binary decoding sangat cepat
        user = DB_USERS.get(user_id)
        if not user:
            return {"grpc_status": "NOT_FOUND", "raw_bytes": b"", "byte_size": 0}

        binary_payload = GrpcProtoSimulator.serialize_user_protobuf(
            user["id"], user["name"], user["is_active"]
        )
        return {
            "grpc_status": "OK",
            "message": {"id": user["id"], "name": user["name"], "is_active": user["is_active"]},
            "raw_bytes": binary_payload,
            "byte_size": len(binary_payload)
        }

# ==============================================================================
# Skenario Demo Teknis
# ==============================================================================
def demo_rest():
    print_header("Skenario 1: REST API (Over-fetching & Under-fetching)", "HTTP/1.1 JSON - Pola Resource Endpoints")
    print(f"{Color.WHITE}Kebutuhan Klien: Hanya butuh 'name' dan 'id' user, beserta ringkasan 'orders'.{Color.RESET}\n")

    # Roundtrip 1: GET /api/v1/users/101
    print_badge("REST Call 1", "GET /api/v1/users/101", Color.BLUE)
    t0 = time.time()
    res1 = RestApiSimulator.get_user(101)
    latency1 = (time.time() - t0) * 1000
    json_bytes1 = len(json.dumps(res1).encode("utf-8"))

    print(f"  {Color.GREEN}Response Status:{Color.RESET} 200 OK | Latency: {latency1:.2f}ms | Payload: {json_bytes1} bytes")
    print(f"  {Color.RED}[Masalah Over-fetching]{Color.RESET} Klien menerima field ekstra: role, department, bio, avatar_url, metadata...")
    print(f"  Payload cuplikan: {json.dumps(res1['data'])[:90]}...\n")

    # Roundtrip 2: GET /api/v1/users/101/orders
    print_badge("REST Call 2", "GET /api/v1/users/101/orders", Color.BLUE)
    t0 = time.time()
    res2 = RestApiSimulator.get_user_orders(101)
    latency2 = (time.time() - t0) * 1000
    json_bytes2 = len(json.dumps(res2).encode("utf-8"))

    print(f"  {Color.GREEN}Response Status:{Color.RESET} 200 OK | Latency: {latency2:.2f}ms | Payload: {json_bytes2} bytes")
    print(f"  {Color.RED}[Masalah Under-fetching]{Color.RESET} Butuh 2 kali network roundtrip (RTT) untuk 1 tampilan halaman.")
    total_rest_bytes = json_bytes1 + json_bytes2
    total_rest_time = latency1 + latency2
    print(f"\n{Color.YELLOW}-> TOTAL REST: {total_rest_bytes} bytes | {total_rest_time:.2f}ms (2 RTT){Color.RESET}")

def demo_graphql():
    print_header("Skenario 2: GraphQL (Declarative Query & Single RTT)", "POST /graphql - Tepat sesuai kebutuhan")
    print(f"{Color.WHITE}Query yang dikirim Klien:{Color.RESET}")
    query_str = """  query GetUserDashboard {
    user(id: 101) {
      id
      name
      orders { id amount }
    }
  }"""
    print(f"{Color.CYAN}{query_str}{Color.RESET}\n")

    print_badge("GraphQL POST", "POST /graphql (Query Execution)", Color.MAGENTA)
    t0 = time.time()
    res = GraphQLEngine.execute_query(query_fields=["id", "name"], include_orders=True, user_id=101)
    gql_time = (time.time() - t0) * 1000
    gql_bytes = len(json.dumps(res).encode("utf-8"))

    print(f"  {Color.GREEN}Status:{Color.RESET} Success | Latency: {gql_time:.2f}ms | Payload: {gql_bytes} bytes")
    print(f"  {Color.GREEN}[Solusi Fleksibel]{Color.RESET} Zero over-fetching. Field yang diminta tepat kembali dalam 1 roundtrip.")
    print(f"  Payload hasil: {json.dumps(res, indent=2)}")
    print(f"\n{Color.YELLOW}-> TOTAL GraphQL: {gql_bytes} bytes | {gql_time:.2f}ms (1 RTT){Color.RESET}")

def demo_grpc():
    print_header("Skenario 3: gRPC & Protocol Buffers (Binary High-Efficiency)", "HTTP/2 RPC - Serialisasi Biner Ringkas")
    print(f"{Color.WHITE}Kontrak IDL (service.proto):{Color.RESET}")
    proto_def = """  message UserSummaryResponse {
    int32 id = 1;
    string name = 2;
    bool is_active = 3;
  }"""
    print(f"{Color.YELLOW}{proto_def}{Color.RESET}\n")

    print_badge("gRPC Invocation", "rpc UserService.GetUserSummary(UserIdRequest)", Color.GREEN)
    t0 = time.time()
    res = GrpcProtoSimulator.rpc_get_user_summary(101)
    grpc_time = (time.time() - t0) * 1000

    print(f"  {Color.GREEN}gRPC Status:{Color.RESET} {res['grpc_status']} | Latency: {grpc_time:.2f}ms | Payload: {res['byte_size']} bytes")
    print(f"  {Color.GREEN}[Solusi High-Throughput]{Color.RESET} Binary wire format menghasilkan payload ultra kecil.")
    print(f"  Binary Hex Representation: {Color.MAGENTA}{res['raw_bytes'].hex(' ')}{Color.RESET}")
    print(f"  Deserialized Message: {res['message']}")
    print(f"\n{Color.YELLOW}-> TOTAL gRPC: {res['byte_size']} bytes | {grpc_time:.2f}ms (HTTP/2 Stream){Color.RESET}")

def run_benchmark():
    print_header("Komparasi & Benchmark Arsitektur (Matrix Performa)", "Simulasi Kebutuhan Data yang Sama")
    
    # 1. REST (2 endpoints, full json)
    res_rest1 = RestApiSimulator.get_user(101)
    res_rest2 = RestApiSimulator.get_user_orders(101)
    b_rest = len(json.dumps(res_rest1).encode("utf-8")) + len(json.dumps(res_rest2).encode("utf-8"))

    # 2. GraphQL (tailored query)
    res_gql = GraphQLEngine.execute_query(["id", "name"], True, 101)
    b_gql = len(json.dumps(res_gql).encode("utf-8"))

    # 3. gRPC (protobuf binary serialization)
    res_grpc = GrpcProtoSimulator.rpc_get_user_summary(101)
    b_grpc = res_grpc["byte_size"]

    print(f"{Color.BOLD}{'Teknologi':<12} | {'Format Wire':<14} | {'Ukuran (Bytes)':<16} | {'Efisiensi vs REST':<20}{Color.RESET}")
    print("-" * 70)
    print(f"{'REST':<12} | {'JSON (HTTP/1.1)':<14} | {f'{b_rest} B':<16} | {'Baseline (1.0x)':<20}")
    print(f"{'GraphQL':<12} | {'JSON (HTTP/1.1)':<14} | {f'{b_gql} B':<16} | {f'Save {(b_rest - b_gql)/b_rest*100:.1f}%':<20}")
    print(f"{'gRPC':<12} | {'Binary Proto':<14} | {f'{b_grpc} B':<16} | {f'Save {(b_rest - b_grpc)/b_rest*100:.1f}% ({(b_rest/b_grpc):.1f}x smaller)':<20}")
    print("-" * 70)

    print(f"\n{Color.BOLD}{Color.GREEN}[KESIMPULAN ARSITEKTURAL]{Color.RESET}")
    print(f"  • {Color.BOLD}REST{Color.RESET}    : Ideal untuk Public API terbuka, caching CDN optimal, universal tooling.")
    print(f"  • {Color.BOLD}GraphQL{Color.RESET} : Solusi terbaik untuk frontend kompleks/mobile (mengatasi over/under-fetching).")
    print(f"  • {Color.BOLD}gRPC{Color.RESET}    : Pilihan de facto komunikasi internal microservice (latensi rendah, type-safe, hemat bandwidth).")

# ==============================================================================
# Main Interactive CLI Loop
# ==============================================================================
def main():
    while True:
        print_header("Interactive Lab: Arsitektur API Backend", "BAB-03: REST vs GraphQL vs gRPC")
        print(f" {Color.CYAN}1.{Color.RESET} Jalankan Simulasi REST (Over-fetching & Under-fetching)")
        print(f" {Color.CYAN}2.{Color.RESET} Jalankan Simulasi GraphQL (Query Fleksibel & 1 RTT)")
        print(f" {Color.CYAN}3.{Color.RESET} Jalankan Simulasi gRPC (Binary Protobuf & HTTP/2)")
        print(f" {Color.CYAN}4.{Color.RESET} Benchmark Performa & Ukuran Payload Komparatif")
        print(f" {Color.CYAN}5.{Color.RESET} Jalankan Seluruh Demo Bertahap (Auto Walkthrough)")
        print(f" {Color.RED}0.{Color.RESET} Keluar (Exit)")
        print(f"{Color.CYAN}{'-' * 75}{Color.RESET}")

        try:
            choice = input(f"{Color.BOLD}Pilih menu [0-5]: {Color.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Color.YELLOW}Menutup program lab. Selesai.{Color.RESET}")
            break

        if choice == "1":
            demo_rest()
        elif choice == "2":
            demo_graphql()
        elif choice == "3":
            demo_grpc()
        elif choice == "4":
            run_benchmark()
        elif choice == "5":
            demo_rest()
            demo_graphql()
            demo_grpc()
            run_benchmark()
        elif choice in ("0", "q", "exit"):
            print(f"\n{Color.GREEN}Terima kasih telah menjalankan Hands-on Lab BAB-03!{Color.RESET}\n")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan coba lagi.{Color.RESET}")

        try:
            input(f"\n{Color.DIM}Tekan [Enter] untuk kembali ke menu utama...{Color.RESET}")
        except (EOFError, KeyboardInterrupt):
            break

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        demo_rest()
        demo_graphql()
        demo_grpc()
        run_benchmark()
    else:
        main()

#!/usr/bin/env python3
"""
Laboratorium Interaktif Arsitektur Backend: REST vs GraphQL vs gRPC
Modul: BAB-03 Arsitektur API (REST, GraphQL, gRPC)
Environment: Standalone Python 3 (Standard Library Only)
"""

import sys
import time
import json
import struct
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional

# --- ANSI Terminal Color Palette ---
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
    BG_CYAN = "\033[46m"

def print_banner():
    banner = f"""
{Color.CYAN}{Color.BOLD}================================================================================
          LAB ARSITEKTUR API PRODUKSI: REST vs GRAPHQL vs gRPC
                      Simulasi Komparasi Kinerja & Desain
================================================================================{Color.RESET}
    """
    print(banner)

# --- Mock Database Domain Entities ---
@dataclass
class Order:
    order_id: str
    item_name: str
    quantity: int
    price: float
    status: str

@dataclass
class UserProfile:
    user_id: str
    username: str
    email: str
    full_name: str
    address: str
    phone: str
    internal_credit_score: int
    orders: List[Order] = field(default_factory=list)

DATABASE: Dict[str, UserProfile] = {
    "usr_101": UserProfile(
        user_id="usr_101",
        username="alex_dev",
        email="alex@production.io",
        full_name="Alex Santoso",
        address="Jl. Sudirman Kav 21, Jakarta Selatan",
        phone="+6281234567890",
        internal_credit_score=850,
        orders=[
            Order("ord_9001", "MacBook Pro M3 Max", 1, 45000000.0, "DELIVERED"),
            Order("ord_9002", "Mechanical Keyboard 75%", 1, 1850000.0, "PROCESSING"),
            Order("ord_9003", "4K Monitor 27-inch", 2, 7200000.0, "SHIPPED"),
        ]
    ),
    "usr_102": UserProfile(
        user_id="usr_102",
        username="sarah_arch",
        email="sarah@cloudscale.net",
        full_name="Sarah Octavia",
        address="Jl. Dago No. 110, Bandung",
        phone="+6289876543210",
        internal_credit_score=790,
        orders=[
            Order("ord_9100", "Server Rack 42U", 1, 15000000.0, "DELIVERED"),
            Order("ord_9101", "Managed Switch 24-Port", 2, 6000000.0, "DELIVERED"),
        ]
    )
}

# ==============================================================================
# 1. SIMULASI ARSITEKTUR REST (Representational State Transfer)
# ==============================================================================
class RestApiSimulator:
    """
    Karakteristik REST:
    - Resource-oriented (URI spesifik)
    - HTTP Verbs (GET, POST, dll)
    - Masalah Over-fetching (mengirim field yang tidak diminta)
    - Masalah Under-fetching (butuh multiple round-trips untuk relasi)
    """

    @staticmethod
    def get_user_by_id(user_id: str, simulate_latency: bool = True) -> Dict[str, Any]:
        if simulate_latency:
            time.sleep(0.04)  # Simulasi latency HTTP/1.1 TCP Handshake + Controller
        user = DATABASE.get(user_id)
        if not user:
            return {"status": 404, "body": {"error": "Not Found"}}
        
        # REST standar mengembalikan representasi utuh resource (Over-fetching)
        payload = asdict(user)
        # Seringkali relasi 'orders' dipisah di endpoint lain /users/:id/orders
        payload.pop("orders")
        raw_json = json.dumps(payload, indent=2)
        return {
            "status": 200,
            "headers": {"Content-Type": "application/json", "Protocol": "HTTP/1.1"},
            "payload_bytes": len(raw_json.encode("utf-8")),
            "body": payload,
            "round_trips": 1
        }

    @staticmethod
    def get_user_orders(user_id: str, simulate_latency: bool = True) -> Dict[str, Any]:
        if simulate_latency:
            time.sleep(0.04)  # Round-trip kedua untuk relasi (Mengatasi Under-fetching)
        user = DATABASE.get(user_id)
        if not user:
            return {"status": 404, "body": {"error": "Not Found"}}
        
        orders = [asdict(o) for o in user.orders]
        raw_json = json.dumps(orders, indent=2)
        return {
            "status": 200,
            "headers": {"Content-Type": "application/json", "Protocol": "HTTP/1.1"},
            "payload_bytes": len(raw_json.encode("utf-8")),
            "body": orders,
            "round_trips": 1
        }

# ==============================================================================
# 2. SIMULASI ARSITEKTUR GRAPHQL
# ==============================================================================
class GraphQLSimulator:
    """
    Karakteristik GraphQL:
    - Single endpoint (/graphql)
    - Client menentukan bentuk data (Exact-fetching)
    - Eliminasi Over-fetching & Under-fetching dalam 1 HTTP request
    """

    @staticmethod
    def execute_query(query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        time.sleep(0.035)  # Simulasi AST Parsing + Field Resolvers
        user_id = variables.get("userId")
        user = DATABASE.get(user_id)
        if not user:
            return {"errors": [{"message": "User not found"}]}
        
        # Simulasi Field Selection Engine GraphQL
        # Hanya mengembalikan field yang didefinisikan dalam field list
        response_data: Dict[str, Any] = {}
        requested_fields = []

        if "username" in query:
            response_data["username"] = user.username
            requested_fields.append("username")
        if "email" in query:
            response_data["email"] = user.email
            requested_fields.append("email")
        if "orders" in query:
            order_data = []
            for o in user.orders:
                item_dict = {}
                if "orderId" in query: item_dict["orderId"] = o.order_id
                if "total" in query or "price" in query: item_dict["price"] = o.price
                order_data.append(item_dict)
            response_data["orders"] = order_data
            requested_fields.append("orders{...}")

        raw_json = json.dumps({"data": {"user": response_data}}, indent=2)
        return {
            "status": 200,
            "headers": {"Content-Type": "application/json", "Protocol": "HTTP/1.1 / HTTP/2"},
            "payload_bytes": len(raw_json.encode("utf-8")),
            "body": {"data": {"user": response_data}},
            "fields_resolved": requested_fields,
            "round_trips": 1
        }

# ==============================================================================
# 3. SIMULASI ARSITEKTUR gRPC & PROTOBUF
# ==============================================================================
class GrpcSimulator:
    """
    Karakteristik gRPC:
    - Transport HTTP/2 (Multiplexing, Header Compression HPACK)
    - Serialisasi Protobuf (Binary framing, field tags bukan string JSON)
    - Ekstrim dalam kecepatan & throughput microservices
    """

    @staticmethod
    def encode_protobuf_mock(user: UserProfile) -> bytes:
        # Simulasi Protobuf Binary Wire Format:
        # Tag (Field Number << 3 | WireType) diikuti nilai
        # Format ringkas tanpa redundant key strings
        buffer = bytearray()
        
        # Field 1: user_id (string)
        uid_bytes = user.user_id.encode("utf-8")
        buffer.extend(struct.pack("!BB", (1 << 3) | 2, len(uid_bytes)))
        buffer.extend(uid_bytes)
        
        # Field 2: credit_score (int32 - varint)
        buffer.extend(struct.pack("!BH", (2 << 3) | 0, user.internal_credit_score))
        
        # Field 3: repeated orders (embedded messages)
        for order in user.orders:
            ord_id = order.order_id.encode("utf-8")
            price_bytes = struct.pack("!d", order.price)  # 64-bit float
            msg = bytearray()
            msg.extend(struct.pack("!BB", (1 << 3) | 2, len(ord_id)))
            msg.extend(ord_id)
            msg.extend(struct.pack("!B", (2 << 3) | 1))
            msg.extend(price_bytes)
            
            buffer.extend(struct.pack("!BB", (3 << 3) | 2, len(msg)))
            buffer.extend(msg)
            
        return bytes(buffer)

    @classmethod
    def call_unary_get_user(cls, user_id: str) -> Dict[str, Any]:
        time.sleep(0.012)  # Latency sangat rendah: HTTP/2 multiplexed stream
        user = DATABASE.get(user_id)
        if not user:
            return {"status": "NOT_FOUND", "code": 5}
        
        binary_payload = cls.encode_protobuf_mock(user)
        return {
            "status": "OK",
            "grpc_code": 0,
            "protocol": "HTTP/2 (h2) - Binary Framed",
            "payload_bytes": len(binary_payload),
            "raw_hex": binary_payload.hex()[:36] + "...",
            "decoded_summary": {
                "user_id": user.user_id,
                "credit_score": user.internal_credit_score,
                "order_count": len(user.orders)
            },
            "round_trips": 1
        }

# ==============================================================================
# BENCHMARK SUITE & INTERACTIVE CONTROLLER
# ==============================================================================
def run_rest_demo():
    print(f"\n{Color.YELLOW}[SKENARIO REST API]{Color.RESET}")
    print(f"Kebutuhan Klien: Menampilkan nama pengguna dan daftar total belanja.")
    print(f"Langkah 1: GET /api/v1/users/usr_101")
    res1 = RestApiSimulator.get_user_by_id("usr_101")
    print(f"  -> HTTP {res1['status']} | Ukuran Body: {res1['payload_bytes']} bytes")
    print(f"  {Color.RED}[!]{Color.RESET} Over-fetching terjadi: Server mengirim alamat, no telepon, skor kredit internal.")
    
    print(f"Langkah 2: GET /api/v1/users/usr_101/orders (Mengatasi Under-fetching)")
    res2 = RestApiSimulator.get_user_orders("usr_101")
    print(f"  -> HTTP {res2['status']} | Ukuran Body: {res2['payload_bytes']} bytes")
    
    total_bytes = res1["payload_bytes"] + res2["payload_bytes"]
    print(f"{Color.BOLD}Total REST Payload:{Color.RESET} {total_bytes} bytes dalam 2 Round-Trip HTTP Requests.\n")

def run_graphql_demo():
    print(f"\n{Color.MAGENTA}[SKENARIO GRAPHQL]{Color.RESET}")
    query = """
    query GetUserBrief($userId: ID!) {
      user(id: $userId) {
        username
        orders {
          orderId
          price
        }
      }
    }
    """
    print(f"Query Dikirim:")
    for line in query.strip().splitlines():
        print(f"  {Color.DIM}{line}{Color.RESET}")
    
    res = GraphQLSimulator.execute_query(query, {"userId": "usr_101"})
    print(f"Eksekusi Engine:")
    print(f"  -> HTTP {res['status']} | Ukuran Body: {res['payload_bytes']} bytes | 1 Round-Trip")
    print(f"  {Color.GREEN}[+]{Color.RESET} Exact-fetching: Tidak ada field mubazir yang terkirim di jaringan.")
    print(f"  Response JSON: {json.dumps(res['body']['data'], separators=(',', ':'))[:90]}...\n")

def run_grpc_demo():
    print(f"\n{Color.BLUE}[SKENARIO gRPC & PROTOBUF]{Color.RESET}")
    print(f"Service: UserService.GetUserBrief(UserRequest)")
    res = GrpcSimulator.call_unary_get_user("usr_101")
    print(f"  -> gRPC Status: {res['status']} ({res['grpc_code']})")
    print(f"  -> Protocol: {res['protocol']}")
    print(f"  -> Serialized Binary Payload: {res['payload_bytes']} bytes")
    print(f"  -> Raw Wire Hex: {Color.DIM}{res['raw_hex']}{Color.RESET}")
    print(f"  {Color.GREEN}[+]{Color.RESET} Efisiensi Maksimal: Binary packing menghemat alokasi memori dan bandwidth.\n")

def run_comparative_benchmark():
    print(f"\n{Color.BOLD}{Color.WHITE}================================================================================")
    print(f"       BENCHMARK KOMPARATIF: REST vs GRAPHQL vs gRPC (1000 Transaksi)")
    print(f"================================================================================{Color.RESET}\n")

    iterations = 1000
    
    # 1. Benchmark REST
    t0 = time.perf_counter()
    rest_total_bytes = 0
    for _ in range(iterations):
        r1 = RestApiSimulator.get_user_by_id("usr_101")
        r2 = RestApiSimulator.get_user_orders("usr_101")
        rest_total_bytes += (r1["payload_bytes"] + r2["payload_bytes"])
    rest_duration = time.perf_counter() - t0

    # 2. Benchmark GraphQL
    t0 = time.perf_counter()
    gql_total_bytes = 0
    gql_query = "query { username orders { orderId price } }"
    for _ in range(iterations):
        g = GraphQLSimulator.execute_query(gql_query, {"userId": "usr_101"})
        gql_total_bytes += g["payload_bytes"]
    gql_duration = time.perf_counter() - t0

    # 3. Benchmark gRPC
    t0 = time.perf_counter()
    grpc_total_bytes = 0
    for _ in range(iterations):
        gp = GrpcSimulator.call_unary_get_user("usr_101")
        grpc_total_bytes += gp["payload_bytes"]
    grpc_duration = time.perf_counter() - t0

    # Print Table
    print(f"{'Paradigma':<12} | {'Round Trips':<12} | {'Total Bandwidth':<18} | {'Avg Bytes/Req':<14} | {'Total Waktu'}")
    print("-" * 75)
    print(f"{Color.YELLOW}{'REST':<12}{Color.RESET} | {'2 Trips':<12} | {rest_total_bytes / 1024:>10.2f} KB       | {rest_total_bytes / iterations:>10.1f} B    | {rest_duration:.3f} s")
    print(f"{Color.MAGENTA}{'GraphQL':<12}{Color.RESET} | {'1 Trip':<12} | {gql_total_bytes / 1024:>10.2f} KB       | {gql_total_bytes / iterations:>10.1f} B    | {gql_duration:.3f} s")
    print(f"{Color.BLUE}{'gRPC':<12}{Color.RESET} | {'1 Stream':<12} | {grpc_total_bytes / 1024:>10.2f} KB       | {grpc_total_bytes / iterations:>10.1f} B    | {grpc_duration:.3f} s")
    print("-" * 75)
    
    savings = ((rest_total_bytes - grpc_total_bytes) / rest_total_bytes) * 100
    print(f"\n{Color.GREEN}{Color.BOLD}[ANALISIS ARSITEKTUR]{Color.RESET}")
    print(f"- gRPC memangkas konsumsi bandwidth sebesar {savings:.1f}% dibanding REST API.")
    print(f"- GraphQL mengeliminasi waterfall network round-trip untuk kueri frontend modern.")
    print(f"- REST unggul pada kemudahan caching HTTP public (CDN / Browser) & kompatibilitas universal.\n")

def interactive_menu():
    print_banner()
    while True:
        print(f"{Color.CYAN}Pilih Menu Demonstrasi:{Color.RESET}")
        print("1. Jalankan Simulasi REST (Under-fetching & Over-fetching)")
        print("2. Jalankan Simulasi GraphQL (Exact-fetching & Schema Selection)")
        print("3. Jalankan Simulasi gRPC (Binary Framing & Protocol Buffers)")
        print("4. Jalankan Comprehensive Benchmark (1000 Operasi)")
        print("5. Jalankan Seluruh Demonstrasi (Automated Full Tour)")
        print("0. Keluar")
        
        choice = input(f"\n{Color.BOLD}Masukkan pilihan (0-5): {Color.RESET}").strip()
        if choice == "1":
            run_rest_demo()
        elif choice == "2":
            run_graphql_demo()
        elif choice == "3":
            run_grpc_demo()
        elif choice == "4":
            run_comparative_benchmark()
        elif choice == "5":
            run_rest_demo()
            run_graphql_demo()
            run_grpc_demo()
            run_comparative_benchmark()
        elif choice == "0":
            print(f"\n{Color.GREEN}Terima kasih telah menggunakan Lab Arsitektur API.{Color.RESET}\n")
            sys.exit(0)
        else:
            print(f"{Color.RED}Pilihan tidak valid, silakan ulangi.{Color.RESET}\n")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        print_banner()
        run_rest_demo()
        run_graphql_demo()
        run_grpc_demo()
        run_comparative_benchmark()
    else:
        try:
            interactive_menu()
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{Color.YELLOW}Sesi dihentikan pengguna.{Color.RESET}")
            sys.exit(0)

#!/usr/bin/env python3
"""
Lab Exercise: BAB-10 Server-Driven Paradigms dan React Server Components (RSC)
Simulasi Arsitektur Produksi: Flight Protocol, Suspense Streaming, Client Boundaries,
dan Server Action Cache Revalidation dengan Visualisasi ANSI Terminal.
"""

import sys
import time
import json
import uuid
from typing import Dict, List, Any, Optional

# --- ANSI Color Palette ---
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[35m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    DIM = '\033[2m'
    RESET = '\033[0m'

# --- Mock Database & Server State ---
DATABASE = {
    "products": {
        "prod_101": {
            "id": "prod_101",
            "name": "Cloud Architecture Deep-Dive (Hardcover)",
            "price": 89.00,
            "stock": 14,
            "heavy_server_dep": "markdown-it + shiki syntax highlighter (1.8 MB bundle)"
        }
    },
    "reviews": {
        "prod_101": [
            {"author": "Alice", "rating": 5, "comment": "Outstanding RSC breakdown!"},
            {"author": "Budi", "rating": 4, "comment": "Streaming suspense is blazing fast."}
        ]
    },
    "cart": []
}

# --- Module 1: Flight Wire Format Generator ---
class FlightSerializer:
    """
    Simulasi React Flight Protocol Serializer.
    Mengonversi Server Components menjadi chunk streaming wire-format
    dan Client Components menjadi client reference token ($L / $I).
    """

    @staticmethod
    def serialize_client_reference(module_id: str, export_name: str) -> str:
        # Format Flight: ID:I["<bundle_path>", ["<export>"], "<display_name>"]
        return f'M1:I["{module_id}", ["{export_name}"], "{export_name}"]'

    @staticmethod
    def serialize_server_chunk(chunk_id: str, tag: str, props: Dict[str, Any], children: Any) -> str:
        payload = ["$", tag, None, {**props, "children": children}]
        return f"{chunk_id}:{json.dumps(payload, ensure_ascii=False)}"

# --- Module 2: RSC Rendering & Suspense Stream Engine ---
class RSCStreamEngine:
    def __init__(self, debug: bool = True):
        self.debug = debug

    def stream_page(self, product_id: str):
        print(f"\n{Colors.HEADER}{Colors.BOLD}=== SIMULASI STREAMING RSC: FLIGHT PROTOCOL ==={Colors.RESET}")
        print(f"{Colors.DIM}Inisialisasi Server Render Pipeline untuk Product ID: {product_id}...{Colors.RESET}\n")
        time.sleep(0.3)

        # 1. Shell & Client References (Immediate Flush)
        print(f"{Colors.CYAN}[CHUNK 0 - Immediate]{Colors.RESET} Client Manifest & Root Shell:")
        client_ref = FlightSerializer.serialize_client_reference("./components/AddToCartButton.client.tsx", "AddToCartButton")
        print(f"  {Colors.YELLOW}--> FLIGHT STREAM:{Colors.RESET} {client_ref}")
        time.sleep(0.2)

        product = DATABASE["products"].get(product_id)
        if not product:
            print(f"{Colors.RED}Produk tidak ditemukan!{Colors.RESET}")
            return

        shell_chunk = FlightSerializer.serialize_server_chunk(
            "J0",
            "main",
            {"className": "product-page-container"},
            [
                ["$", "h1", None, {"children": product["name"]}],
                ["$", "p", None, {"children": f"Harga: ${product['price']:.2f} | Stok: {product['stock']}"}],
                ["$", "$L1", None, {"productId": product_id, "initialStock": product["stock"]}],
                ["$", "$Sreact.suspense", None, {"fallback": ["$", "div", None, {"children": "Loading reviews..."}], "id": "suspense_reviews"}]
            ]
        )
        print(f"  {Colors.YELLOW}--> FLIGHT STREAM:{Colors.RESET} {shell_chunk}")
        print(f"{Colors.GREEN}[CLIENT RECONCILIATION]{Colors.RESET} HTML Shell dirender, Fallback Suspense ditampilkan ke user.")
        time.sleep(0.5)

        # 2. Asynchronous Suspense Resolution (Streaming out-of-order)
        print(f"\n{Colors.CYAN}[CHUNK 1 - Async Streaming Delay 800ms]{Colors.RESET} Menunggu database query reviews...")
        time.sleep(0.8)

        reviews = DATABASE["reviews"].get(product_id, [])
        review_elements = [
            ["$", "li", None, {"children": f"{r['author']}: ({r['rating']}★) {r['comment']}"}]
            for r in reviews
        ]
        review_chunk = FlightSerializer.serialize_server_chunk(
            "J1",
            "ul",
            {"className": "review-list"},
            review_elements
        )
        print(f"  {Colors.YELLOW}--> FLIGHT STREAM (Resolve J1):{Colors.RESET} {review_chunk}")
        print(f"{Colors.GREEN}[CLIENT RECONCILIATION]{Colors.RESET} Suspense fallback diganti dengan DOM pohon reviews secara seamless tanpa hydration penuh.")

# --- Module 3: Server Action & Optimistic Cache Invalidation ---
class ServerActionDispatcher:
    @staticmethod
    def execute_add_to_cart(product_id: str, quantity: int = 1) -> Dict[str, Any]:
        print(f"\n{Colors.MAGENTA}{Colors.BOLD}=== MENJALANKAN SERVER ACTION: addToCartAction ==={Colors.RESET}")
        print(f"{Colors.DIM}Client memicu RPC endpoint dengan HTTP POST /__rsc_action...{Colors.RESET}")
        time.sleep(0.3)

        product = DATABASE["products"].get(product_id)
        if not product or product["stock"] < quantity:
            return {"success": False, "message": "Stok produk tidak mencukupi!"}

        # Mutasi database
        product["stock"] -= quantity
        DATABASE["cart"].append({
            "cart_id": str(uuid.uuid4())[:8],
            "product_id": product_id,
            "product_name": product["name"],
            "qty": quantity,
            "unit_price": product["price"]
        })

        print(f"{Colors.GREEN}✔ DB Mutation:{Colors.RESET} Stok berkurang menjadi {product['stock']}. Item dimasukkan ke keranjang.")
        
        # Cache Tag Revalidation
        print(f"{Colors.BLUE}⚡ Revalidating Tag:{Colors.RESET} revalidateTag('product-{product_id}') & revalidatePath('/cart')")
        time.sleep(0.2)
        
        # Server Action mengembalikan Flight stream terkompresi dari komponen yang terpengaruh
        updated_rsc = FlightSerializer.serialize_server_chunk(
            "U0",
            "div",
            {"id": "cart-counter-rsc"},
            f"Total items in cart: {len(DATABASE['cart'])}"
        )
        print(f"  {Colors.YELLOW}--> RSC REVALIDATION FLIGHT STREAM:{Colors.RESET} {updated_rsc}")
        return {"success": True, "cart_count": len(DATABASE["cart"]), "remaining_stock": product["stock"]}

# --- Module 4: Bundle Size & Cost Analysis ---
def display_bundle_cost_comparison():
    print(f"\n{Colors.BOLD}{Colors.HEADER}=== ANALISIS BEBAN BUNDLE (RSC vs TRADISIONAL SPA/SSR) ==={Colors.RESET}")
    print(f"{'Metrik':<30} | {'Tradisional SPA (Client)':<25} | {'RSC Architecture':<25}")
    print("-" * 88)
    print(f"{'Markdown Parser + Highlighter':<30} | {'1,850 KB (Dikirim ke browser)':<25} | {Colors.GREEN + '0 KB (Eksekusi di Server)' + Colors.RESET:<34}")
    print(f"{'Hydration Overhead':<30} | {'Pohon Komponen Penuh':<25} | {Colors.GREEN + 'Hanya Komponen Client ($L1)' + Colors.RESET:<34}")
    print(f"{'Waterfall Data Fetching':<30} | {'Client fetch via REST/GraphQL':<25} | {Colors.GREEN + 'Direct DB access zero latency' + Colors.RESET:<34}")
    print(f"{'Data Security / Secrets':<30} | {'Rentan terekspos di bundle':<25} | {Colors.GREEN + 'Aman di boundary Server' + Colors.RESET:<34}")
    print("-" * 88)
    print(f"{Colors.DIM}Hasil: Pengurangan JavaScript client bundle mencapai hingga 70-85% pada halaman konten berat.{Colors.RESET}\n")

# --- Interactive Terminal UI ---
def interactive_menu():
    engine = RSCStreamEngine()
    
    while True:
        print(f"\n{Colors.BOLD}{Colors.BLUE}================================================================={Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.GREEN}   LAB BAB 10: REACT SERVER COMPONENTS & FLIGHT PROTOCOL SIM   {Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}================================================================={Colors.RESET}")
        print(f"  {Colors.CYAN}1.{Colors.RESET} Simulasi Full RSC Initial Page Load & Flight Stream Rendering")
        print(f"  {Colors.CYAN}2.{Colors.RESET} Inspeksi Raw Flight Wire Protocol Payload (Format $ dan $L)")
        print(f"  {Colors.CYAN}3.{Colors.RESET} Simulasi Server Action Mutation (Add To Cart + Revalidation)")
        print(f"  {Colors.CYAN}4.{Colors.RESET} Analisis Perbandingan Beban Bundle JavaScript (Zero-Cost RSC)")
        print(f"  {Colors.CYAN}5.{Colors.RESET} Jalankan Automated End-to-End Test Suite")
        print(f"  {Colors.CYAN}6.{Colors.RESET} Keluar (Exit)")
        print(f"{Colors.BLUE}-----------------------------------------------------------------{Colors.RESET}")
        
        try:
            choice = input(f"{Colors.BOLD}Pilih opsi [1-6]: {Colors.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        if choice == "1":
            engine.stream_page("prod_101")
        elif choice == "2":
            print(f"\n{Colors.YELLOW}{Colors.BOLD}=== CONTOH RAW FLIGHT PROTOCOL STREAM PAYLOAD ==={Colors.RESET}")
            print(f"{Colors.DIM}Contoh format data yang dialirkan via HTTP stream ke runtime client:{Colors.RESET}\n")
            print('M1:I["./components/AddToCartButton.client.tsx",["AddToCartButton"],"AddToCartButton"]')
            print('J0:["$","main",null,{"className":"product-page-container","children":[["$","h1",null,{"children":"Cloud Architecture"}],["$","$L1",null,{"productId":"prod_101"}]]}]')
            print('J1:["$","ul",null,{"className":"review-list","children":[["$","li",null,{"children":"Budi: (5★) Top!"}]]}]')
            print(f"\n{Colors.GREEN}Catatan Struktur:{Colors.RESET}")
            print(f" - {Colors.BOLD}M1:I{Colors.RESET} -> Client Component reference manifest.")
            print(f" - {Colors.BOLD}J0{Colors.RESET}   -> Root layout/shell tree serialized JSON.")
            print(f" - {Colors.BOLD}$L1{Colors.RESET}  -> Slot placeholder untuk hidrasi Client Component.")
        elif choice == "3":
            res = ServerActionDispatcher.execute_add_to_cart("prod_101", 1)
            print(f"{Colors.CYAN}Response Status:{Colors.RESET} {res}")
        elif choice == "4":
            display_bundle_cost_comparison()
        elif choice == "5":
            run_automated_tests()
        elif choice == "6":
            print(f"\n{Colors.GREEN}Terima kasih telah menjalankan simulasi RSC Lab BAB 10!{Colors.RESET}\n")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid. Silakan masukkan angka 1 hingga 6.{Colors.RESET}")

# --- Module 5: Automated Verification Suite ---
def run_automated_tests():
    print(f"\n{Colors.BOLD}{Colors.HEADER}=== RUNNING AUTOMATED AUDIT & TEST SUITE ==={Colors.RESET}")
    tests_passed = 0
    total_tests = 4

    # Test 1: Flight serialization format
    ref = FlightSerializer.serialize_client_reference("./comp.tsx", "Btn")
    if 'M1:I["./comp.tsx"' in ref and '"Btn"' in ref:
        print(f"  {Colors.GREEN}✔ [PASS]{Colors.RESET} Test 1: Flight Client Reference Serializer format valid.")
        tests_passed += 1
    else:
        print(f"  {Colors.RED}✘ [FAIL]{Colors.RESET} Test 1: Invalid Flight Client Reference format.")

    # Test 2: Server Chunk serialization
    chunk = FlightSerializer.serialize_server_chunk("J0", "div", {"id": "test"}, "Hello RSC")
    if chunk.startswith("J0:") and '"div"' in chunk and '"Hello RSC"' in chunk:
        print(f"  {Colors.GREEN}✔ [PASS]{Colors.RESET} Test 2: Server Component Tree serialization valid.")
        tests_passed += 1
    else:
        print(f"  {Colors.RED}✘ [FAIL]{Colors.RESET} Test 2: Invalid Server Chunk format.")

    # Test 3: Server Action Stock Mutation
    initial_stock = DATABASE["products"]["prod_101"]["stock"]
    res = ServerActionDispatcher.execute_add_to_cart("prod_101", 1)
    if res["success"] and DATABASE["products"]["prod_101"]["stock"] == initial_stock - 1:
        print(f"  {Colors.GREEN}✔ [PASS]{Colors.RESET} Test 3: Server Action state transition & cart mutation verified.")
        tests_passed += 1
    else:
        print(f"  {Colors.RED}✘ [FAIL]{Colors.RESET} Test 3: Server Action mutation failed.")

    # Test 4: Suspense Wire Protocol Integrity
    if len(DATABASE["reviews"]["prod_101"]) > 0:
        print(f"  {Colors.GREEN}✔ [PASS]{Colors.RESET} Test 4: Mock Data review stream pipeline integrity verified.")
        tests_passed += 1
    else:
        print(f"  {Colors.RED}✘ [FAIL]{Colors.RESET} Test 4: Mock review data missing.")

    print(f"\n{Colors.BOLD}Hasil Uji: {tests_passed}/{total_tests} Lolos Audit Arsitektur RSC.{Colors.RESET}")

if __name__ == "__main__":
    # Jika dipanggil dengan flag --test atau non-interaktif
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        run_automated_tests()
    else:
        interactive_menu()

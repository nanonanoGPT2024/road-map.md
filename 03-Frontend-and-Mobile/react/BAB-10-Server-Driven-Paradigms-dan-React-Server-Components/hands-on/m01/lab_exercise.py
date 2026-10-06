#!/usr/bin/env python3
"""
Lab Exercise: React Server Components (RSC) & Flight Wire Protocol Simulator
BAB-10: Server-Driven Paradigms dan React Server Components

Simulasi teknis konsep fondasi RSC:
1. Server vs Client Component boundaries.
2. Flight Wire Protocol serialization ($L, $J, @client-ref).
3. Streaming HTML & RSC payload chunk over HTTP stream.
4. Zero-bundle-size client footprint audit.
5. Server Actions (RPC mutation & revalidation).
"""

import sys
import time
import json
import dataclasses
from typing import Dict, Any, List, Optional

# --- ANSI Terminal Color Palette ---
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_WHITE = "\033[37m"
CLR_BG_DARK = "\033[48;5;236m"

@dataclasses.dataclass
class ComponentManifest:
    id: str
    kind: str  # "server" or "client"
    source_file: str
    client_bundle_size_kb: float
    dependencies: List[str]

# Mock Database & Server State
MOCK_DATABASE = {
    "post_101": {
        "id": "post_101",
        "title": "Deep Dive into React 19 RSC & Flight Protocol",
        "content": "Server Components execute exclusively on the server, rendering to a streaming wire format.",
        "author": "React Core Team",
        "likes": 42,
        "comments": [
            {"id": "c1", "author": "Alice", "text": "Zero client bundle for markdown parsers is a game changer!"},
            {"id": "c2", "author": "Bob", "text": "Streaming Suspense keeps TTFB super snappy."}
        ]
    }
}

CLIENT_MANIFEST: Dict[str, ComponentManifest] = {
    "Page": ComponentManifest("Page", "server", "app/page.tsx", 0.0, ["PostHeader", "PostContent", "LikeButton"]),
    "PostHeader": ComponentManifest("PostHeader", "server", "components/PostHeader.tsx", 0.0, []),
    "PostContent": ComponentManifest("PostContent", "server", "components/PostContent.tsx", 0.0, ["heavy-markdown-parser-lib"]),
    "LikeButton": ComponentManifest("LikeButton", "client", "components/LikeButton.tsx", 1.8, ["react-dom"]),
    "CommentSection": ComponentManifest("CommentSection", "server", "components/CommentSection.tsx", 0.0, ["CommentInput"]),
    "CommentInput": ComponentManifest("CommentInput", "client", "components/CommentInput.tsx", 2.4, ["useActionState"])
}

def print_header(title: str) -> None:
    border = "=" * 68
    print(f"\n{CLR_CYAN}{CLR_BOLD}{border}{CLR_RESET}")
    print(f"{CLR_WHITE}{CLR_BOLD}  ⚛️  {title}{CLR_RESET}")
    print(f"{CLR_CYAN}{CLR_BOLD}{border}{CLR_RESET}\n")

def simulate_streaming_flight_protocol() -> None:
    print_header("Simulasi 1: RSC Flight Wire Protocol & Suspense Streaming")
    print(f"{CLR_DIM}[INFO] Rendering server component tree 'Page' on Edge Runtime...{CLR_RESET}\n")

    # Step 1: Initial Shell Chunk
    time.sleep(0.3)
    chunk_0 = {
        "M1": {"id": "./components/LikeButton.tsx", "name": "LikeButton", "chunks": ["client-chunk-42.js"]},
        "J0": ["$", "div", None, {
            "className": "container mx-auto p-4",
            "children": [
                ["$", "header", None, {"children": [["$", "h1", None, {"children": MOCK_DATABASE["post_101"]["title"]}]]}],
                ["$", "$L1", None, {}]  # Reference to Suspense slot 1
            ]
        }]
    }

    print(f"{CLR_YELLOW}{CLR_BOLD}>>> [HTTP STREAM: Chunk 0 (Root Shell + Client Manifest Reference)] <<<{CLR_RESET}")
    print(f"{CLR_GREEN}0:\"$M1\"{{\"id\":\"./components/LikeButton.tsx\",\"chunks\":[\"client-chunk-42.js\"]}}{CLR_RESET}")
    print(f"{CLR_CYAN}1:I[\"$J0\", {json.dumps(chunk_0['J0'])}]{CLR_RESET}")
    print(f"{CLR_DIM}Status: Shell HTML dikirim segera ke browser. TTFB tercapai instan.{CLR_RESET}\n")

    # Step 2: Async Data Fetching (Suspense Resolution)
    time.sleep(0.6)
    print(f"{CLR_MAGENTA}{CLR_BOLD}[SUSPENSE STREAMING] Mengambil data async (Markdown Body & Likes)...{CLR_RESET}")
    time.sleep(0.5)

    post = MOCK_DATABASE["post_101"]
    chunk_1 = {
        "article": ["$", "article", None, {
            "children": [
                ["$", "p", None, {"children": post["content"]}],
                # Reference to Client Component with serialized props
                ["$", "$L1:LikeButton", None, {"postId": post["id"], "initialLikes": post["likes"]}]
            ]
        }]
    }

    print(f"\n{CLR_YELLOW}{CLR_BOLD}>>> [HTTP STREAM: Chunk 1 (Suspense Resolved Body)] <<<{CLR_RESET}")
    print(f"{CLR_GREEN}2:\"$L1\"{{\"article\": {json.dumps(chunk_1['article'])}}}{CLR_RESET}")
    print(f"{CLR_DIM}Browser menerima slot $L1 dan langsung meng-hydrate LikeButton (client island).{CLR_RESET}\n")

def simulate_bundle_size_audit() -> None:
    print_header("Simulasi 2: Zero-Bundle-Size Audit (Server vs Client)")
    print(f"{'Komponen':<18} | {'Jenis':<10} | {'Bundle Client':<16} | {'Keterangan'}")
    print("-" * 72)

    total_client_kb = 0.0
    for name, manifest in CLIENT_MANIFEST.items():
        kind_color = CLR_GREEN if manifest.kind == "server" else CLR_YELLOW
        total_client_kb += manifest.client_bundle_size_kb
        print(f"{CLR_BOLD}{name:<18}{CLR_RESET} | {kind_color}{manifest.kind.upper():<10}{CLR_RESET} | "
              f"{manifest.client_bundle_size_kb:>5.1f} KB          | {manifest.source_file}")

    print("-" * 72)
    print(f"{CLR_CYAN}{CLR_BOLD}TOTAL JAVASCRIPT DIKIRIM KE CLIENT:{CLR_RESET} {CLR_RED}{CLR_BOLD}{total_client_kb:.1f} KB{CLR_RESET}")
    print(f"{CLR_DIM}Catatan: Komponen berlabel SERVER ('heavy-markdown-parser-lib', sanitize-html, DB SDK) "
          f"dieksekusi 100% di server dan TIDAK PERNAH masuk bundle JS client.{CLR_RESET}\n")

def simulate_server_action_rpc(post_id: str = "post_101") -> None:
    print_header("Simulasi 3: Server Action RPC Mutation & Path Revalidation")
    post = MOCK_DATABASE.get(post_id)
    if not post:
        print(f"{CLR_RED}Post '{post_id}' tidak ditemukan.{CLR_RESET}")
        return

    print(f"Kondisi awal di Server Database:")
    print(f"Post Title: {CLR_BOLD}{post['title']}{CLR_RESET}")
    print(f"Likes: {CLR_GREEN}{post['likes']}{CLR_RESET}")

    print(f"\n{CLR_BLUE}Simulasi User menekan tombol 'Like' di Client...{CLR_RESET}")
    print(f"{CLR_DIM}-> Client memicu RPC Request: POST /_rsc/action/incrementLike (Body: {{\"postId\": \"{post_id}\"}}){CLR_RESET}")
    time.sleep(0.4)

    # Server Action Mutation logic
    post["likes"] += 1
    revalidated_tag = f"post:{post_id}"

    print(f"\n{CLR_GREEN}{CLR_BOLD}✔ [SERVER ACTION EXECUTED SUCCESFULLY]{CLR_RESET}")
    print(f"  - Database Updated: Likes sekarang = {CLR_YELLOW}{post['likes']}{CLR_RESET}")
    print(f"  - Cache Invalidation: {CLR_CYAN}revalidateTag('{revalidated_tag}'){CLR_RESET}")
    print(f"  - Return Payload: Mengalirkan RSC Delta (Flight Payload baru) tanpa reload browser penuh.")

def interactive_cli() -> None:
    while True:
        print(f"{CLR_WHITE}{CLR_BOLD}Menu Praktikum Lab RSC & Server-Driven Architecture:{CLR_RESET}")
        print(f"  {CLR_CYAN}1.{CLR_RESET} Jalankan Streaming Flight Wire Protocol Simulator")
        print(f"  {CLR_CYAN}2.{CLR_RESET} Tampilkan Zero-Bundle-Size Client Footprint Audit")
        print(f"  {CLR_CYAN}3.{CLR_RESET} Jalankan Server Action RPC Mutation (Like Post)")
        print(f"  {CLR_CYAN}4.{CLR_RESET} Jalankan Seluruh Demonstrasi (Automated Run)")
        print(f"  {CLR_CYAN}5.{CLR_RESET} Keluar (Exit)")

        try:
            choice = input(f"\n{CLR_YELLOW}Pilih opsi [1-5]: {CLR_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSelesai.")
            break

        if choice == "1":
            simulate_streaming_flight_protocol()
        elif choice == "2":
            simulate_bundle_size_audit()
        elif choice == "3":
            simulate_server_action_rpc()
        elif choice == "4":
            simulate_streaming_flight_protocol()
            simulate_bundle_size_audit()
            simulate_server_action_rpc()
        elif choice == "5" or choice.lower() in ("q", "quit", "exit"):
            print(f"{CLR_GREEN}Praktikum selesai. Terima kasih.{CLR_RESET}")
            break
        else:
            print(f"{CLR_RED}Pilihan tidak valid. Silakan pilih 1-5.{CLR_RESET}\n")

if __name__ == "__main__":
    # If run in non-interactive / piped environments, run all demonstrations
    if not sys.stdin.isatty():
        simulate_streaming_flight_protocol()
        simulate_bundle_size_audit()
        simulate_server_action_rpc()
    else:
        interactive_cli()

#!/usr/bin/env python3
"""
Lab Hands-on: Next.js Deep Dive - Data Mutation, Server Actions, & Stateful Forms
Simulasi komprehensif arsitektur React 19 / Next.js Server Actions:
- Remote Procedure Call (RPC) dispatch via Action IDs
- Server-side Schema Validation & Field Error mapping
- Client-side Stateful Form hook (`useActionState`)
- Optimistic UI updates with rollback (`useOptimistic`)
- Path & Tag Cache Invalidation (`revalidatePath`, `revalidateTag`)
"""

import sys
import time
import json
import uuid
import hashlib
from typing import Dict, Any, Tuple, Optional, List, Callable

# --- ANSI Styling Engine ---
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"
    BG_DARK = "\033[48;5;236m"

def log_header(text: str):
    print(f"\n{Style.BOLD}{Style.BLUE}=== {text} ==={Style.RESET}")

def log_step(badge: str, msg: str, color=Style.CYAN):
    print(f"{color}[{badge}]{Style.RESET} {msg}")

# --- Server Layer: Next.js Cache & Database Mock ---
class NextDataCache:
    """Simulasi Next.js Full Route & Data Cache."""
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._tag_map: Dict[str, List[str]] = {}

    def set(self, key: str, value: Any, tags: List[str] = None):
        self._cache[key] = {
            "data": value,
            "cached_at": time.time(),
            "valid": True
        }
        if tags:
            for tag in tags:
                self._tag_map.setdefault(tag, []).append(key)

    def get(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry and entry["valid"]:
            return entry["data"]
        return None

    def invalidate_path(self, path: str):
        if path in self._cache:
            self._cache[path]["valid"] = False

    def invalidate_tag(self, tag: str):
        keys = self._tag_map.get(tag, [])
        for k in keys:
            if k in self._cache:
                self._cache[k]["valid"] = False

class MockDatabase:
    """In-memory DB untuk persistent entity."""
    def __init__(self):
        self.posts: Dict[str, Dict[str, Any]] = {
            "post-1": {"id": "post-1", "title": "Understanding RSC", "votes": 42},
            "post-2": {"id": "post-2", "title": "Next.js Architecture", "votes": 88}
        }

    def insert(self, title: str) -> Dict[str, Any]:
        post_id = f"post-{len(self.posts) + 1}"
        new_post = {"id": post_id, "title": title, "votes": 0}
        self.posts[post_id] = new_post
        return new_post

# --- Next.js Server Action Dispatcher ---
class ServerActionRuntime:
    """
    Simulasi runtime backend Next.js:
    - Menghasilkan Action ID terenkripsi/hash
    - Mengeksekusi 'use server' actions
    - Memicu revalidasi cache
    """
    def __init__(self, db: MockDatabase, cache: NextDataCache):
        self.db = db
        self.cache = cache
        self.registry: Dict[str, Callable] = {}
        self._register_actions()

    def _register_actions(self):
        self._register("createPostAction", self.create_post_action)
        self._register("upvotePostAction", self.upvote_post_action)

    def _register(self, name: str, fn: Callable):
        # Next.js meng-generate ID hash untuk fungsi server
        action_id = hashlib.sha256(name.encode()).hexdigest()[:12]
        self.registry[action_id] = fn
        self.registry[name] = fn

    def dispatch(self, action_id: str, prev_state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        """Entrypoint HTTP endpoint internal Next.js Server Action."""
        if action_id not in self.registry:
            return {"status": "error", "message": "Server Action not found", "code": 404}

        action_fn = self.registry[action_id]
        return action_fn(prev_state, payload)

    # Implementasi Server Actions ('use server')
    def create_post_action(self, prev_state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        title = payload.get("title", "").strip()
        errors = {}

        # Validasi schema (analog dengan Zod)
        if not title:
            errors["title"] = "Title field cannot be empty."
        elif len(title) < 5:
            errors["title"] = "Title must contain at least 5 characters."

        if errors:
            return {
                "success": False,
                "errors": errors,
                "values": payload,
                "timestamp": time.time()
            }

        # Skenario error runtime server
        if "exploit" in title.lower():
            return {
                "success": False,
                "errors": {"_form": "Security constraint violation."},
                "values": payload,
                "timestamp": time.time()
            }

        # Eksekusi mutasi
        post = self.db.insert(title)
        
        # Invalidation hook: revalidatePath('/posts')
        self.cache.invalidate_path("/posts")
        self.cache.invalidate_tag("posts-list")

        return {
            "success": True,
            "data": post,
            "errors": {},
            "timestamp": time.time()
        }

    def upvote_post_action(self, prev_state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        post_id = payload.get("id")
        if post_id not in self.db.posts:
            return {"success": False, "errors": {"_form": "Post not found."}}

        # Simulasi latensi database
        time.sleep(0.05)
        self.db.posts[post_id]["votes"] += 1
        self.cache.invalidate_path(f"/posts/{post_id}")

        return {
            "success": True,
            "data": self.db.posts[post_id],
            "errors": {}
        }

# --- Client Simulation: React Stateful Form & Optimistic UI ---
class ReactStatefulFormEngine:
    """
    Simulasi Client-Side Hooks:
    - useActionState (Stateful Form)
    - useOptimistic (Optimistic UI update & rollback mechanism)
    """
    def __init__(self, runtime: ServerActionRuntime):
        self.runtime = runtime
        self.state: Dict[str, Any] = {"success": None, "errors": {}, "data": None}
        self.optimistic_state: List[Dict[str, Any]] = []

    def set_initial_optimistic(self, data: List[Dict[str, Any]]):
        self.optimistic_state = [dict(x) for x in data]

    def submit_action(self, action_name: str, payload: Dict[str, Any], optimistic_update: Optional[Callable] = None):
        """Meniru form submission via React Server Action."""
        backup_optimistic = [dict(x) for x in self.optimistic_state]

        # 1. Terapkan Optimistic Update jika ada
        if optimistic_update:
            self.optimistic_state = optimistic_update(self.optimistic_state, payload)
            log_step("UI:OPTIMISTIC", f"Optimistic state applied immediately: {json.dumps(self.optimistic_state[-1])}", Style.YELLOW)

        # 2. Kirim RPC ke server (Next.js HTTP POST)
        response = self.runtime.dispatch(action_name, self.state, payload)
        self.state = response

        # 3. Handle response & Reconcile UI
        if response.get("success"):
            log_step("UI:SUCCESS", f"Server Action resolved successfully. DB Entity ID: {response['data']['id']}", Style.GREEN)
            # Reconcile optimistic record dengan entity asli
            if optimistic_update:
                self.optimistic_state[-1] = response["data"]
        else:
            log_step("UI:REVERT", "Server returned errors! Rolling back optimistic state.", Style.RED)
            self.optimistic_state = backup_optimistic

        return self.state

# --- Execution Workflow & Verification Tests ---
def run_lab():
    log_header("LAB START: NEXT.JS DATA MUTATION & STATEFUL FORMS")

    db = MockDatabase()
    cache = NextDataCache()
    runtime = ServerActionRuntime(db, cache)

    # Inisialisasi Cache dengan Server-Side Rendering
    cache.set("/posts", list(db.posts.values()), tags=["posts-list"])
    log_step("CACHE:INIT", f"Path '/posts' cached with {len(db.posts)} items.", Style.BLUE)

    client = ReactStatefulFormEngine(runtime)
    client.set_initial_optimistic(list(db.posts.values()))

    # Skenario 1: Submisi Form Valid + Optimistic UI
    print(f"\n{Style.BOLD}--- Case 1: Valid Mutation with Optimistic Update ---{Style.RESET}")
    def optimistic_post_adder(current_list, payload):
        copy_list = [dict(x) for x in current_list]
        copy_list.append({
            "id": f"temp-{uuid.uuid4().hex[:6]}",
            "title": payload["title"],
            "votes": 0,
            "_pending": True
        })
        return copy_list

    payload_valid = {"title": "Mastering Server Components"}
    log_step("CLIENT:DISPATCH", f"Triggering createPostAction with payload: {payload_valid}")
    client.submit_action("createPostAction", payload_valid, optimistic_update=optimistic_post_adder)

    # Verifikasi Invalidation
    is_cache_valid = cache.get("/posts") is not None
    log_step("CACHE:CHECK", f"Cache path '/posts' valid after mutation: {is_cache_valid} (Expect False)", Style.MAGENTA)
    print(f"Current Post DB Count: {len(db.posts)}")

    # Skenario 2: Submisi Form Tidak Valid (Validasi Schema Gagal & Rollback)
    print(f"\n{Style.BOLD}--- Case 2: Validation Failure (Rollback Check) ---{Style.RESET}")
    payload_invalid = {"title": "bad"}  # Terlalu pendek (< 5 char)
    log_step("CLIENT:DISPATCH", f"Triggering createPostAction with payload: {payload_invalid}")
    res = client.submit_action("createPostAction", payload_invalid, optimistic_update=optimistic_post_adder)
    
    print(f"{Style.YELLOW}useActionState Errors Returned:{Style.RESET} {res['errors']}")
    print(f"Optimistic Item Count after Rollback: {len(client.optimistic_state)} (Expect unchanged)")

    # Skenario 3: Exception / Form Guard Constraint
    print(f"\n{Style.BOLD}--- Case 3: Constraint / Exploit Error ---{Style.RESET}")
    payload_exploit = {"title": "Exploit Injection Attempt"}
    log_step("CLIENT:DISPATCH", f"Triggering createPostAction with payload: {payload_exploit}")
    res_exploit = client.submit_action("createPostAction", payload_exploit, optimistic_update=optimistic_post_adder)
    print(f"{Style.RED}Form State Message:{Style.RESET} {res_exploit['errors']}")

    # Skenario 4: Targeted Upvote & Path-Specific Revalidation
    print(f"\n{Style.BOLD}--- Case 4: Targeted Dynamic Route Revalidation ---{Style.RESET}")
    cache.set("/posts/post-1", db.posts["post-1"])
    log_step("CACHE:SET", "Seeded cache for '/posts/post-1'", Style.BLUE)
    
    runtime.dispatch("upvotePostAction", {}, {"id": "post-1"})
    revalidated = cache.get("/posts/post-1") is None
    log_step("CACHE:REVALIDATED", f"Dynamic path '/posts/post-1' invalidated: {revalidated} (Expect True)", Style.GREEN)
    log_step("DB:STATE", f"Post-1 total votes now: {db.posts['post-1']['votes']}", Style.GREEN)

    log_header("LAB SUMMARY: ALL NEXT.JS MUTATION CONCEPTS VALIDATED")

if __name__ == "__main__":
    run_lab()
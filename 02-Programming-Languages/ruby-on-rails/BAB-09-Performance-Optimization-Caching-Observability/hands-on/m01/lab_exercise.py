#!/usr/bin/env python3
"""
Hands-on Lab Exercise: Rails Performance Optimization, Caching & Observability Simulation
Topic: BAB-09 Performance Optimization, Caching & Observability (Ruby on Rails Concept Simulator)

Features Simulated:
1. ActiveSupport::Notifications (Instrumentation & Event Bus)
2. N+1 Query Problem vs. Eager Loading (Preload/Includes)
3. Multi-tier & Russian Doll Caching (Fragment Caching with Timestamps & Digest Keys)
4. Cache Store (In-Memory Redis-like LRU / Key-Value Store with TTL & Hit/Miss Telemetry)
5. Request Latency & Performance Metrics Reporter
"""

import time
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Any

# ANSI Color formatting
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"


def header(title: str) -> None:
    print(f"\n{BOLD}{BG_BLUE}{WHITE} === {title} === {RESET}\n")


def info(msg: str) -> None:
    print(f"{CYAN}[INFO]{RESET} {msg}")


def success(msg: str) -> None:
    print(f"{GREEN}[SUCCESS]{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[WARN]{RESET} {msg}")


def sql_log(query: str, duration_ms: float) -> None:
    color = RED if duration_ms > 20 else YELLOW
    print(f"  {MAGENTA}SQL ({duration_ms:.2f}ms){RESET} {color}{query}{RESET}")


# ---------------------------------------------------------------------------
# 1. Observability: ActiveSupport::Notifications Simulator
# ---------------------------------------------------------------------------
class ActiveSupportNotifications:
    """Simulates Rails ActiveSupport::Notifications pub-sub event bus."""

    def __init__(self):
        self.subscribers: Dict[str, List[Callable[[str, float, float, Dict[str, Any]], None]]] = {}

    def subscribe(self, pattern: str, callback: Callable[[str, float, float, Dict[str, Any]], None]) -> None:
        self.subscribers.setdefault(pattern, []).append(callback)

    def instrument(self, event_name: str, payload: Dict[str, Any] = None):
        """Context manager simulating ActiveSupport::Notifications.instrument."""
        if payload is None:
            payload = {}

        class Instrumenter:
            def __init__(self, bus: ActiveSupportNotifications, name: str, data: Dict[str, Any]):
                self.bus = bus
                self.name = name
                self.payload = data
                self.start_time = 0.0

            def __enter__(self):
                self.start_time = time.perf_counter()
                return self.payload

            def __exit__(self, exc_type, exc_val, exc_tb):
                finish_time = time.perf_counter()
                for pattern, cbs in self.bus.subscribers.items():
                    if pattern == self.name or pattern == "*":
                        for cb in cbs:
                            cb(self.name, self.start_time, finish_time, self.payload)

        return Instrumenter(self, event_name, payload)


# Global event bus
notifier = ActiveSupportNotifications()


# ---------------------------------------------------------------------------
# 2. Storage & Low-Level Caching: Rails.cache Simulation
# ---------------------------------------------------------------------------
@dataclass
class CacheEntry:
    value: Any
    created_at: float
    ttl_seconds: Optional[float] = None

    def is_expired(self) -> bool:
        if self.ttl_seconds is None:
            return False
        return (time.time() - self.created_at) > self.ttl_seconds


class RailsCacheStore:
    """Simulates Rails.cache (e.g. RedisCacheStore or MemoryStore)."""

    def __init__(self):
        self.store: Dict[str, CacheEntry] = {}
        self.stats = {"hits": 0, "misses": 0, "writes": 0}

    def fetch(self, key: str, expires_in: Optional[float] = None, block: Optional[Callable[[], Any]] = None) -> Any:
        with notifier.instrument("cache.read", {"key": key}) as payload:
            entry = self.store.get(key)
            if entry and not entry.is_expired():
                self.stats["hits"] += 1
                payload["hit"] = True
                return entry.value

            self.stats["misses"] += 1
            payload["hit"] = False

        if block is None:
            return None

        val = block()
        self.write(key, val, expires_in=expires_in)
        return val

    def write(self, key: str, value: Any, expires_in: Optional[float] = None) -> None:
        with notifier.instrument("cache.write", {"key": key, "expires_in": expires_in}):
            self.store[key] = CacheEntry(value=value, created_at=time.time(), ttl_seconds=expires_in)
            self.stats["writes"] += 1

    def delete(self, key: str) -> None:
        self.store.pop(key, None)

    def clear(self) -> None:
        self.store.clear()
        self.stats = {"hits": 0, "misses": 0, "writes": 0}


cache = RailsCacheStore()


# ---------------------------------------------------------------------------
# 3. Domain Models & Database Simulation
# ---------------------------------------------------------------------------
@dataclass
class Comment:
    id: int
    article_id: int
    content: str
    author: str
    updated_at: str

    def cache_key(self) -> str:
        digest = hashlib.md5(f"{self.content}-{self.author}".encode()).hexdigest()[:8]
        return f"views/comments/{self.id}-{self.updated_at}-{digest}"


@dataclass
class Article:
    id: int
    title: str
    author: str
    updated_at: str
    comments: List[Comment] = field(default_factory=list)

    def cache_key(self) -> str:
        # Cache Key based on updated_at and record ID
        digest = hashlib.md5(f"{self.title}-{self.author}".encode()).hexdigest()[:8]
        return f"views/articles/{self.id}-{self.updated_at}-{digest}"


# Mock Database
MOCK_ARTICLES_DB = [
    {"id": 1, "title": "Scaling Ruby on Rails in 2026", "author": "DHH", "updated_at": "2026-03-01T10:00:00Z"},
    {"id": 2, "title": "Solid Queue & Solid Cache Deep-Dive", "author": "Kasper", "updated_at": "2026-03-02T12:30:00Z"},
    {"id": 3, "title": "Mastering Russian Doll Caching", "author": "Eileen", "updated_at": "2026-03-03T15:00:00Z"},
]

MOCK_COMMENTS_DB = [
    {"id": 101, "article_id": 1, "content": "Awesome read!", "author": "Alice", "updated_at": "2026-03-01T11:00:00Z"},
    {"id": 102, "article_id": 1, "content": "Very relevant for 2026.", "author": "Bob", "updated_at": "2026-03-01T11:20:00Z"},
    {"id": 103, "article_id": 2, "content": "Bye bye Redis?", "author": "Charlie", "updated_at": "2026-03-02T13:00:00Z"},
    {"id": 104, "article_id": 3, "content": "Russian doll caching saved our latency.", "author": "Dave", "updated_at": "2026-03-03T15:10:00Z"},
    {"id": 105, "article_id": 3, "content": "Touch: true is key!", "author": "Eve", "updated_at": "2026-03-03T15:45:00Z"},
]


class DatabaseSession:
    def __init__(self):
        self.query_count = 0

    def query_articles(self) -> List[Article]:
        self.query_count += 1
        with notifier.instrument("sql.active_record", {"sql": "SELECT * FROM articles"}):
            time.sleep(0.015)  # simulate 15ms DB roundtrip
            return [Article(**row) for row in MOCK_ARTICLES_DB]

    def query_comments_for_article(self, article_id: int) -> List[Comment]:
        self.query_count += 1
        sql = f"SELECT * FROM comments WHERE article_id = {article_id}"
        with notifier.instrument("sql.active_record", {"sql": sql}):
            time.sleep(0.012)  # simulate 12ms DB roundtrip per query
            rows = [c for c in MOCK_COMMENTS_DB if c["article_id"] == article_id]
            return [Comment(**c) for c in rows]

    def query_comments_for_articles(self, article_ids: List[int]) -> List[Comment]:
        self.query_count += 1
        id_list = ", ".join(map(str, article_ids))
        sql = f"SELECT * FROM comments WHERE article_id IN ({id_list})"
        with notifier.instrument("sql.active_record", {"sql": sql}):
            time.sleep(0.018)  # simulate batch 18ms DB roundtrip
            rows = [c for c in MOCK_COMMENTS_DB if c["article_id"] in article_ids]
            return [Comment(**c) for c in rows]


# ---------------------------------------------------------------------------
# 4. Telemetry Subscriber Setup
# ---------------------------------------------------------------------------
def setup_subscribers():
    def log_sql(event_name, start, finish, payload):
        dur = (finish - start) * 1000
        sql_log(payload.get("sql", "UNKNOWN"), dur)

    def log_cache(event_name, start, finish, payload):
        dur = (finish - start) * 1000
        key = payload.get("key", "")
        if event_name == "cache.read":
            status = f"{GREEN}HIT{RESET}" if payload.get("hit") else f"{RED}MISS{RESET}"
            print(f"  {BLUE}Rails.cache ({dur:.2f}ms){RESET} READ [{status}] -> {key}")
        elif event_name == "cache.write":
            print(f"  {BLUE}Rails.cache ({dur:.2f}ms){RESET} WRITE -> {key}")

    notifier.subscribe("sql.active_record", log_sql)
    notifier.subscribe("cache.read", log_cache)
    notifier.subscribe("cache.write", log_cache)


# ---------------------------------------------------------------------------
# 5. Core Labs: N+1 vs Includes & Russian Doll Caching
# ---------------------------------------------------------------------------
def run_naive_n_plus_one_demo(db: DatabaseSession):
    header("SCENARIO 1: The Classic N+1 Query Problem (Article.all)")
    info("Simulating: ArticlesController#index WITHOUT eager loading:")
    info("Code: @articles = Article.all; @articles.each { |a| a.comments.each ... }")

    db.query_count = 0
    t0 = time.perf_counter()

    # 1 query for articles
    articles = db.query_articles()
    # N queries for comments (one per article)
    for art in articles:
        art.comments = db.query_comments_for_article(art.id)

    elapsed_ms = (time.perf_counter() - t0) * 1000
    print(f"\n{BOLD}Result Summary:{RESET}")
    print(f" - Total DB Queries Issued: {RED}{db.query_count}{RESET} (1 + {len(articles)} queries)")
    print(f" - Wall Time: {RED}{elapsed_ms:.2f}ms{RESET}")
    warn("Notice how query count scales linearly with the number of articles!")


def run_eager_loading_demo(db: DatabaseSession):
    header("SCENARIO 2: Eager Loading Optimization (Article.includes(:comments))")
    info("Simulating: ArticlesController#index WITH Article.includes(:comments)")
    info("Preloads associations using two queries total, regardless of dataset size.")

    db.query_count = 0
    t0 = time.perf_counter()

    # 1. Fetch articles
    articles = db.query_articles()
    art_ids = [a.id for a in articles]

    # 2. Fetch all comments in 1 single IN query
    all_comments = db.query_comments_for_articles(art_ids)

    # In-memory mapping
    comments_by_article: Dict[int, List[Comment]] = {}
    for c in all_comments:
        comments_by_article.setdefault(c.article_id, []).append(c)

    for art in articles:
        art.comments = comments_by_article.get(art.id, [])

    elapsed_ms = (time.perf_counter() - t0) * 1000
    print(f"\n{BOLD}Result Summary:{RESET}")
    print(f" - Total DB Queries Issued: {GREEN}{db.query_count}{RESET} (Constant: 2 queries)")
    print(f" - Wall Time: {GREEN}{elapsed_ms:.2f}ms{RESET}")
    success("Eager loading avoided N+1 queries!")


def render_russian_doll_view(articles: List[Article]) -> str:
    """Simulates Rails ERB template with nested fragment caching (Russian Doll)."""
    output_html = []

    for art in articles:
        art_key = art.cache_key()

        def render_article():
            rendered_comments = []
            for comment in art.comments:
                cmt_key = comment.cache_key()

                def render_comment():
                    return f"<div class='comment'><b>{comment.author}:</b> {comment.content}</div>"

                rendered_comments.append(cache.fetch(cmt_key, block=render_comment))

            return (
                f"<article id='{art.id}'>\n"
                f"  <h2>{art.title}</h2>\n"
                f"  <p>Author: {art.author}</p>\n"
                f"  <div class='comments'>\n"
                f"    " + "\n    ".join(rendered_comments) + "\n"
                f"  </div>\n"
                f"</article>"
            )

        article_html = cache.fetch(art_key, block=render_article)
        output_html.append(article_html)

    return "\n".join(output_html)


def run_russian_doll_caching_demo(db: DatabaseSession):
    header("SCENARIO 3: Russian Doll Caching & Fragment Revalidation")
    info("Simulating nested view fragment caching with auto-invalidating keys.")

    # Prepare data using eager loading
    articles = db.query_articles()
    comments = db.query_comments_for_articles([a.id for a in articles])
    c_map = {}
    for c in comments:
        c_map.setdefault(c.article_id, []).append(c)
    for a in articles:
        a.comments = c_map.get(a.id, [])

    print(f"\n{BOLD}--- Iteration 1: Cold Cache (Miss Everywhere) ---{RESET}")
    cache.clear()
    t0 = time.perf_counter()
    html_1 = render_russian_doll_view(articles)
    t1 = (time.perf_counter() - t0) * 1000
    print(f"Render time: {YELLOW}{t1:.2f}ms{RESET}, Hits: {cache.stats['hits']}, Misses: {cache.stats['misses']}")

    print(f"\n{BOLD}--- Iteration 2: Warm Cache (Outer Article Key Hits Immediately) ---{RESET}")
    t0 = time.perf_counter()
    html_2 = render_russian_doll_view(articles)
    t2 = (time.perf_counter() - t0) * 1000
    print(f"Render time: {GREEN}{t2:.2f}ms{RESET}, Hits: {cache.stats['hits']}, Misses: {cache.stats['misses']}")
    success(f"Warm render was {t1 / max(t2, 0.0001):.1f}x faster due to outer cache hit!")

    print(f"\n{BOLD}--- Iteration 3: Partial Invalidation ('touch: true' propagation) ---{RESET}")
    info("Simulate user editing Comment #101: updating timestamp and article's updated_at.")
    # Comment 101 updated, touches article 1
    articles[0].comments[0].content = "Awesome read! [EDITED by Author]"
    articles[0].comments[0].updated_at = "2026-03-06T12:00:00Z"
    articles[0].updated_at = "2026-03-06T12:00:00Z"  # touch: true propagated to Article

    t0 = time.perf_counter()
    html_3 = render_russian_doll_view(articles)
    t3 = (time.perf_counter() - t0) * 1000

    print(f"Render time: {CYAN}{t3:.2f}ms{RESET}, Hits: {cache.stats['hits']}, Misses: {cache.stats['misses']}")
    info("Outer Article 1 cache invalidated; Comment 101 re-rendered, but Comment 102 was a CACHE HIT!")


def run_benchmark_comparison(db: DatabaseSession):
    header("SCENARIO 4: End-to-End Performance & Throughput Benchmark")
    iterations = 20
    info(f"Running simulation across {iterations} simulated web requests...")

    # Mode A: Uncached with N+1
    t0 = time.perf_counter()
    for _ in range(iterations):
        arts = db.query_articles()
        for a in arts:
            a.comments = db.query_comments_for_article(a.id)
    n1_time = (time.perf_counter() - t0) * 1000

    # Mode B: Preloaded + Russian Doll Cached
    cache.clear()
    t0 = time.perf_counter()
    # First warmup
    arts = db.query_articles()
    cmts = db.query_comments_for_articles([a.id for a in arts])
    c_map = {}
    for c in cmts:
        c_map.setdefault(c.article_id, []).append(c)
    for a in arts:
        a.comments = c_map.get(a.id, [])
    render_russian_doll_view(arts)

    # Cached loop
    for _ in range(iterations):
        render_russian_doll_view(arts)
    cached_time = (time.perf_counter() - t0) * 1000

    print(f"\n{BOLD}=== Benchmark Results ({iterations} requests) ==={RESET}")
    print(f"  {RED}Uncached N+1 Approach :{RESET} {n1_time:.2f} ms ({n1_time/iterations:.2f} ms/req)")
    print(f"  {GREEN}Cached Russian Doll   :{RESET} {cached_time:.2f} ms ({cached_time/iterations:.2f} ms/req)")
    speedup = n1_time / max(cached_time, 0.001)
    print(f"  {BOLD}{MAGENTA}Throughput Multiplier :{RESET} {BOLD}{GREEN}{speedup:.2f}x Faster{RESET}")


# ---------------------------------------------------------------------------
# Interactive Menu Runner
# ---------------------------------------------------------------------------
def main():
    setup_subscribers()
    db = DatabaseSession()

    banner = f"""
{BOLD}{CYAN}======================================================================
  Ruby on Rails: Performance Optimization, Caching & Observability
  Hands-on Interactive Concept Laboratory (Terminal Edition)
======================================================================{RESET}
  {WHITE}Simulating ActiveSupport::Notifications, N+1 detection,
  Eager Loading (:includes), Low-Level & Russian Doll Caching.{RESET}
"""
    print(banner)

    while True:
        print(f"\n{BOLD}Pilih Skenario Percobaan:{RESET}")
        print("  1. Simulasi N+1 Query Problem (Unoptimized)")
        print("  2. Simulasi Eager Loading (includes / preload)")
        print("  3. Simulasi Russian Doll Caching & Invalidation (touch: true)")
        print("  4. Benchmark Komparasi Latensi (N+1 vs Russian Doll)")
        print("  5. Jalankan Semua Skenario Berurutan")
        print("  0. Keluar")

        try:
            choice = input(f"\n{CYAN}Masukkan nomor opsi [0-5]: {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        if choice == "1":
            run_naive_n_plus_one_demo(db)
        elif choice == "2":
            run_eager_loading_demo(db)
        elif choice == "3":
            run_russian_doll_caching_demo(db)
        elif choice == "4":
            run_benchmark_comparison(db)
        elif choice == "5":
            run_naive_n_plus_one_demo(db)
            run_eager_loading_demo(db)
            run_russian_doll_caching_demo(db)
            run_benchmark_comparison(db)
        elif choice in ("0", "exit", "quit", "q"):
            print(f"{GREEN}Lab selesai. Selamat belajar optimasi Rails!{RESET}")
            break
        else:
            print(f"{RED}Pilihan tidak valid, silakan ulangi.{RESET}")


if __name__ == "__main__":
    main()

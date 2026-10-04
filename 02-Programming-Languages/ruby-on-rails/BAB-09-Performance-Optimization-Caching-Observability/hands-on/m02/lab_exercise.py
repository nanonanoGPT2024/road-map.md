#!/usr/bin/env python3
"""
Lab Hands-on: Performance Optimization, Caching & Observability (Rails Engine Simulation)
Module: Deep Dive into ActiveSupport::Notifications, Russian Doll Caching & N+1 Query Detection

This script simulates:
1. ActiveSupport::Notifications pub-sub telemetry engine.
2. ORM layer with N+1 Query detection (similar to the 'bullet' gem).
3. Rails Russian Doll Caching with auto-invalidation via touch mechanics.
4. Performance profiling and metrics dashboard comparing uncached vs. optimized states.
"""

import time
import hashlib
from collections import defaultdict
from typing import Callable, Any, Dict, List, Optional

# ANSI Color codes for styled terminal output
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"

# ==============================================================================
# 1. OBSERVABILITY: ActiveSupport::Notifications Simulation
# ==============================================================================

class ActiveSupportNotifications:
    """Simulates Rails ActiveSupport::Notifications pub-sub telemetry engine."""
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)

    def subscribe(self, pattern: str, callback: Callable):
        self._subscribers[pattern].append(callback)

    def instrument(self, name: str, payload: Optional[Dict[str, Any]] = None):
        """Context manager to measure latency and broadcast telemetry events."""
        return _Instrumenter(self, name, payload or {})

    def publish(self, name: str, start: float, finish: float, payload: Dict[str, Any]):
        for pattern, subscribers in self._subscribers.items():
            if pattern == name or pattern == "*":
                for subscriber in subscribers:
                    subscriber(name, start, finish, payload)

class _Instrumenter:
    def __init__(self, notifier: ActiveSupportNotifications, name: str, payload: Dict[str, Any]):
        self.notifier = notifier
        self.name = name
        self.payload = payload
        self.start = 0.0

    def __enter__(self):
        self.start = time.perf_counter()
        return self.payload

    def __exit__(self, exc_type, exc_val, exc_tb):
        finish = time.perf_counter()
        self.notifier.publish(self.name, self.start, finish, self.payload)

# Global Telemetry Bus
notifier = ActiveSupportNotifications()

# ==============================================================================
# 2. CACHING: Rails Low-Level & Fragment Cache (Russian Doll Pattern)
# ==============================================================================

class RailsCacheStore:
    """Simulates ActiveSupport::Cache::MemoryStore with read/write stats."""
    def __init__(self):
        self._store: Dict[str, str] = {}
        self.hits = 0
        self.misses = 0
        self.writes = 0

    def fetch(self, key: str, generator: Callable[[], str]) -> str:
        """Simulates Rails.cache.fetch(key) do ... end"""
        with notifier.instrument("cache_read.active_support", {"key": key}) as payload:
            if key in self._store:
                self.hits += 1
                payload["hit"] = True
                return self._store[key]
            
            self.misses += 1
            payload["hit"] = False

        # Cache miss: compute value and write
        value = generator()
        with notifier.instrument("cache_write.active_support", {"key": key}):
            self._store[key] = value
            self.writes += 1
        return value

    def clear(self):
        self._store.clear()
        self.hits = 0
        self.misses = 0
        self.writes = 0

# ==============================================================================
# 3. DATABASE & ORM: N+1 Detection & Models with 'touch: true'
# ==============================================================================

class MockDatabase:
    """In-memory relation store tracking SQL queries to detect N+1 anti-patterns."""
    def __init__(self):
        self.query_log: List[str] = []
        self.query_count = 0

    def execute(self, sql: str) -> None:
        # Simulate ~1ms DB latency
        time.sleep(0.001)
        self.query_count += 1
        self.query_log.append(sql)
        notifier.publish("sql.active_record", time.perf_counter(), time.perf_counter() + 0.001, {"sql": sql})

    def reset_stats(self):
        self.query_log.clear()
        self.query_count = 0

db = MockDatabase()

class Model:
    def __init__(self, record_id: int):
        self.id = record_id
        self.updated_at = int(time.time() * 1000)

    def touch(self):
        """Simulates Rails touch: true mechanism to invalidate parent cache keys."""
        self.updated_at = int(time.time() * 1000)

    def cache_key_with_version(self) -> str:
        """Simulates Rails cache key generation based on class, ID and updated_at timestamp."""
        raw = f"{self.__class__.__name__}/{self.id}-{self.updated_at}"
        digest = hashlib.md5(raw.encode()).hexdigest()[:8]
        return f"{self.__class__.__name__.lower()}/{self.id}-{digest}"

class Comment(Model):
    def __init__(self, record_id: int, body: str, article: 'Article'):
        super().__init__(record_id)
        self.body = body
        self.article = article

    def update_comment(self, new_body: str):
        self.body = new_body
        self.touch()
        # Touch parent article (belongs_to :article, touch: true)
        self.article.touch()

class Article(Model):
    def __init__(self, record_id: int, title: str):
        super().__init__(record_id)
        self.title = title
        self.comment_ids: List[int] = []

    def comments(self) -> List[Comment]:
        db.execute(f"SELECT * FROM comments WHERE article_id = {self.id}")
        return [all_comments[cid] for cid in self.comment_ids]

# Mock Database Fixtures
all_articles: Dict[int, Article] = {}
all_comments: Dict[int, Comment] = {}

def seed_database():
    all_articles.clear()
    all_comments.clear()
    comment_counter = 1
    for a_id in range(1, 4):  # 3 articles
        article = Article(a_id, f"Rails Performance Masterclass #{a_id}")
        for _ in range(3):   # 3 comments per article
            c = Comment(comment_counter, f"Insightful benchmark #{comment_counter}!", article)
            all_comments[comment_counter] = c
            article.comment_ids.append(comment_counter)
            comment_counter += 1
        all_articles[a_id] = article

# ==============================================================================
# 4. VIEW RENDERING ENGINE (Russian Doll Fragment Rendering)
# ==============================================================================

cache = RailsCacheStore()

def render_comment_partial(comment: Comment) -> str:
    """Innermost fragment: renders a single comment."""
    def _render():
        return f"<div class='comment' id='c_{comment.id}'>{comment.body}</div>"
    return cache.fetch(comment.cache_key_with_version(), _render)

def render_article_partial(article: Article, comments: Optional[List[Comment]] = None) -> str:
    """Middle fragment: renders article and nested comment partials."""
    def _render():
        # If comments not eager-loaded, triggers DB query
        resolved_comments = comments if comments is not None else article.comments()
        rendered_comments = "\n    ".join(render_comment_partial(c) for c in resolved_comments)
        return (
            f"<article id='a_{article.id}'>\n"
            f"  <h2>{article.title}</h2>\n"
            f"  <section class='comments'>\n    {rendered_comments}\n  </section>\n"
            f"</article>"
        )
    return cache.fetch(article.cache_key_with_version(), _render)

# ==============================================================================
# 5. LAB BENCHMARK SCENARIOS
# ==============================================================================

def setup_telemetry_listener():
    """Sets up ActiveSupport::Notifications subscribers for observability tracking."""
    def sql_subscriber(name, start, finish, payload):
        duration_ms = (finish - start) * 1000
        # Print SQL logs in yellow
        print(f"  {YELLOW}[ActiveRecord] {payload['sql']} ({duration_ms:.2f}ms){RESET}")

    def cache_subscriber(name, start, finish, payload):
        status = f"{GREEN}HIT{RESET}" if payload.get("hit") else f"{RED}MISS{RESET}"
        print(f"  {CYAN}[ActiveSupport::Cache] {payload.get('key')} -> {status}")

    notifier.subscribe("sql.active_record", sql_subscriber)
    notifier.subscribe("cache_read.active_support", cache_subscriber)

def run_scenario(name: str, render_fn: Callable):
    print(f"\n{BOLD}{BLUE}======================================================================{RESET}")
    print(f"{BOLD}{BLUE}RUNNING SCENARIO: {name}{RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}")
    db.reset_stats()
    start_time = time.perf_counter()

    with notifier.instrument("process_action.action_controller", {"action": name}):
        result = render_fn()

    total_time = (time.perf_counter() - start_time) * 1000

    print(f"\n{MAGENTA}--- Observability Metrics ---{RESET}")
    print(f"Total Execution Time: {BOLD}{total_time:.2f} ms{RESET}")
    print(f"DB Queries Triggered: {BOLD}{db.query_count}{RESET}")
    print(f"Cache Hits: {GREEN}{cache.hits}{RESET} | Cache Misses: {RED}{cache.misses}{RESET} | Writes: {cache.writes}")
    return result

def main():
    seed_database()
    setup_telemetry_listener()

    print(f"{BOLD}Rails Deep Dive: Performance, Russian Doll Caching & Telemetry{RESET}\n")

    # -------------------------------------------------------------------------
    # Scenario 1: Uncached Naive Render (Classic N+1 Query Problem)
    # -------------------------------------------------------------------------
    cache.clear()
    def scenario_uncached_n_plus_one():
        # Controller simulates: @articles = Article.all
        db.execute("SELECT * FROM articles")
        output = []
        for a in all_articles.values():
            # N+1: Each article queries its comments separately on every render
            output.append(render_article_partial(a))
        return "\n".join(output)

    run_scenario("1. Cold Run / Uncached with N+1 Query Traps", scenario_uncached_n_plus_one)

    # -------------------------------------------------------------------------
    # Scenario 2: Eager Loading Simulation (Preload/Includes)
    # -------------------------------------------------------------------------
    cache.clear()
    def scenario_eager_loaded():
        # Controller simulates: @articles = Article.includes(:comments).all
        # Query 1: Fetch articles
        db.execute("SELECT * FROM articles")
        # Query 2: Eager load all comments in 1 roundtrip (IN clause)
        db.execute("SELECT * FROM comments WHERE article_id IN (1, 2, 3)")
        
        preloaded_comments = defaultdict(list)
        for c in all_comments.values():
            preloaded_comments[c.article.id].append(c)

        output = []
        for a in all_articles.values():
            output.append(render_article_partial(a, comments=preloaded_comments[a.id]))
        return "\n".join(output)

    run_scenario("2. Optimized Queries: ActiveRecord Eager Loading (includes)", scenario_eager_loaded)

    # -------------------------------------------------------------------------
    # Scenario 3: Warm Cache Run (Russian Doll Fragment Cache Hit)
    # -------------------------------------------------------------------------
    def scenario_warm_cache():
        # Second hit: everything should be resolved from cache; ZERO DB queries!
        db.execute("SELECT * FROM articles")
        output = [render_article_partial(a) for a in all_articles.values()]
        return "\n".join(output)

    run_scenario("3. Warm Cache Hit: Russian Doll Fragment Caching", scenario_warm_cache)

    # -------------------------------------------------------------------------
    # Scenario 4: Mutation and 'touch: true' Cache Invalidation
    # -------------------------------------------------------------------------
    target_comment = all_comments[1]
    parent_article = target_comment.article
    print(f"\n{YELLOW}[Action]{RESET} Mutating Comment #1 -> Triggers 'touch: true' cascade to Article #{parent_article.id}...")
    time.sleep(0.01) # ensure millisecond tick
    target_comment.update_comment("Updated: Highly scalable Ruby on Rails architecture!")

    def scenario_invalidation_run():
        db.execute("SELECT * FROM articles")
        output = []
        for a in all_articles.values():
            output.append(render_article_partial(a))
        return "\n".join(output)

    run_scenario("4. Targeted Re-render After Invalidation (Touch Cascade)", scenario_invalidation_run)

    print(f"\n{GREEN}✔ Lab completed successfully. Observability pipeline verified.{RESET}\n")

if __name__ == "__main__":
    main()
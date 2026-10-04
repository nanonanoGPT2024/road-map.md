#!/usr/bin/env python3
"""
Lab Exercise: Data Modeling & Active Record Mastery Deep Dive
Topic: Rails Active Record Pattern, Dirty Tracking, Lifecycle Callbacks, & N+1 Query Resolution.

This lab simulates core architectural components of Rails' ActiveRecord:
1. In-Memory Relational Engine & SQL Query Logger (Tracking query count & latency).
2. Callback Lifecycle Pipeline (before_validation, before_save, after_commit).
3. Dirty Tracking System (detecting changed attributes prior to persistence).
4. Association Preloading & Eager Loading (demonstrating and resolving the N+1 problem).
"""

import time
import copy
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# ANSI Terminal Styling
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_CYAN = "\033[36m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_BLUE = "\033[34m"
C_MAGENTA = "\033[35m"

# ==============================================================================
# 1. DATABASE & QUERY LOGGER SIMULATION
# ==============================================================================
class DatabaseEngine:
    """Simulates an underlying RDBMS engine with query tracking and latency overhead."""
    def __init__(self):
        self.tables: Dict[str, Dict[int, Dict[str, Any]]] = {}
        self.query_log: List[str] = []
        self.query_count: int = 0
        self.total_simulated_latency: float = 0.0

    def execute_sql(self, sql: str, simulated_latency_ms: float = 2.5) -> None:
        """Logs simulated SQL execution and accumulates query overhead."""
        self.query_count += 1
        self.total_simulated_latency += simulated_latency_ms
        self.query_log.append(sql)
        time.sleep(simulated_latency_ms / 1000.0)

    def reset_metrics(self) -> None:
        self.query_log.clear()
        self.query_count = 0
        self.total_simulated_latency = 0.0

DB = DatabaseEngine()

# ==============================================================================
# 2. ACTIVE RECORD CORE ENGINE
# ==============================================================================
class ActiveRecordBase:
    """
    Emulates Ruby on Rails ActiveRecord::Base:
    - Attribute dirty tracking
    - Lifecycle callbacks pipeline
    - Validation engine
    """
    table_name: str = ""
    _callbacks: Dict[str, List[Callable]] = {
        "before_validation": [],
        "before_save": [],
        "after_save": [],
        "after_commit": []
    }

    def __init__(self, **attributes):
        self.id: Optional[int] = attributes.get("id")
        self._attributes: Dict[str, Any] = {}
        self._original_attributes: Dict[str, Any] = {}
        self._errors: List[str] = []
        self._is_persisted: bool = False

        for k, v in attributes.items():
            self._attributes[k] = v
            self._original_attributes[k] = copy.deepcopy(v)

        if self.id is not None:
            self._is_persisted = True

    def __getattr__(self, name: str) -> Any:
        if name in self._attributes:
            return self._attributes[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        # Internal fields bypass attribute tracking
        if name in ("_attributes", "_original_attributes", "_errors", "_is_persisted", "id"):
            super().__setattr__(name, value)
        else:
            if "_attributes" in self.__dict__:
                self._attributes[name] = value
            else:
                super().__setattr__(name, value)

    # --- Dirty Tracking Module ---
    def is_dirty(self) -> bool:
        """Determines if any attribute was altered since initialization or last save."""
        return self._attributes != self._original_attributes

    def changed_attributes(self) -> Dict[str, Tuple[Any, Any]]:
        """Returns dict of field: (old_value, new_value) for all modified attributes."""
        changes = {}
        all_keys = set(self._attributes.keys()).union(set(self._original_attributes.keys()))
        for key in all_keys:
            old_val = self._original_attributes.get(key)
            new_val = self._attributes.get(key)
            if old_val != new_val:
                changes[key] = (old_val, new_val)
        return changes

    # --- Callback & Lifecycle Engine ---
    @classmethod
    def register_callback(cls, hook_type: str, callback: Callable):
        if hook_type not in cls._callbacks:
            cls._callbacks[hook_type] = []
        cls._callbacks[hook_type].append(callback)

    def _run_callbacks(self, hook_type: str) -> bool:
        """Runs registered callbacks; halts lifecycle if a callback returns False."""
        callbacks = self._callbacks.get(hook_type, [])
        for cb in callbacks:
            result = cb(self)
            if result is False:
                return False
        return True

    def validate(self) -> bool:
        """Overridable validation logic."""
        return len(self._errors) == 0

    def save(self) -> bool:
        """Simulates full Rails transaction lifecycle: validation -> save -> commit."""
        if not self._run_callbacks("before_validation"):
            return False

        if not self.validate():
            return False

        if not self.is_dirty() and self._is_persisted:
            return True  # No-op if record not dirty

        if not self._run_callbacks("before_save"):
            return False

        # Persist to database
        if self.id is None:
            # INSERT
            new_id = (max(DB.tables[self.table_name].keys()) + 1) if DB.tables[self.table_name] else 1
            self.id = new_id
            self._attributes["id"] = new_id
            DB.tables[self.table_name][self.id] = copy.deepcopy(self._attributes)
            DB.execute_sql(f"INSERT INTO {self.table_name} ({', '.join(self._attributes.keys())}) VALUES (...)")
        else:
            # UPDATE
            DB.tables[self.table_name][self.id] = copy.deepcopy(self._attributes)
            changes = [f"{k}='{v}'" for k, v in self._attributes.items() if k != "id"]
            DB.execute_sql(f"UPDATE {self.table_name} SET {', '.join(changes)} WHERE id = {self.id}")

        self._is_persisted = True
        self._original_attributes = copy.deepcopy(self._attributes)

        self._run_callbacks("after_save")
        self._run_callbacks("after_commit")
        return True


# ==============================================================================
# 3. CONCRETE DOMAIN MODELS (Authors, Posts, Comments)
# ==============================================================================
class Author(ActiveRecordBase):
    table_name = "authors"

    def posts(self, eager_loaded_records: Optional[List['Post']] = None) -> List['Post']:
        """Demonstrates lazy-loading vs eager-loaded retrieval."""
        if eager_loaded_records is not None:
            return eager_loaded_records

        # Standard Lazy Query (N+1 source)
        DB.execute_sql(f"SELECT * FROM posts WHERE author_id = {self.id}")
        raw_rows = [row for row in DB.tables["posts"].values() if row.get("author_id") == self.id]
        return [Post(**row) for row in raw_rows]


class Post(ActiveRecordBase):
    table_name = "posts"

    def comments(self, eager_loaded_records: Optional[List['Comment']] = None) -> List['Comment']:
        """Comments relationship traversal."""
        if eager_loaded_records is not None:
            return eager_loaded_records

        DB.execute_sql(f"SELECT * FROM comments WHERE post_id = {self.id}")
        raw_rows = [row for row in DB.tables["comments"].values() if row.get("post_id") == self.id]
        return [Comment(**row) for row in raw_rows]


class Comment(ActiveRecordBase):
    table_name = "comments"


# ==============================================================================
# 4. ACTIVE RECORD QUERY RELATION & EAGER LOADING SIMULATOR
# ==============================================================================
class ActiveRecordRelation:
    """Simulates Rails ActiveRecord::Relation supporting .where() and .includes()."""
    def __init__(self, model_class: type):
        self.model_class = model_class
        self.preloads: Set[str] = set()

    def includes(self, *associations: str) -> 'ActiveRecordRelation':
        """Enables eager loading for specified associations, replicating Rails preload."""
        new_rel = copy.copy(self)
        new_rel.preloads = set(associations)
        return new_rel

    def all(self) -> List[Any]:
        table_name = self.model_class.table_name
        DB.execute_sql(f"SELECT * FROM {table_name}")
        records = [self.model_class(**data) for data in DB.tables[table_name].values()]

        # Resolve Eager Loading if requested
        if "posts" in self.preloads and self.model_class is Author:
            author_ids = [r.id for r in records]
            if author_ids:
                in_clause = ", ".join(map(str, author_ids))
                DB.execute_sql(f"SELECT * FROM posts WHERE author_id IN ({in_clause})")
                
                # Fetch all posts in bulk and group by author_id
                posts_by_author: Dict[int, List[Post]] = {aid: [] for aid in author_ids}
                for row in DB.tables["posts"].values():
                    if row.get("author_id") in posts_by_author:
                        posts_by_author[row["author_id"]].append(Post(**row))

                # If comments are also requested in preloads:
                if "comments" in self.preloads:
                    all_posts = [p for p_list in posts_by_author.values() for p in p_list]
                    post_ids = [p.id for p in all_posts]
                    if post_ids:
                        p_clause = ", ".join(map(str, post_ids))
                        DB.execute_sql(f"SELECT * FROM comments WHERE post_id IN ({p_clause})")
                        comments_by_post: Dict[int, List[Comment]] = {pid: [] for pid in post_ids}
                        for crow in DB.tables["comments"].values():
                            if crow.get("post_id") in comments_by_post:
                                comments_by_post[crow["post_id"]].append(Comment(**crow))
                        
                        # Attach eager comments to post instances
                        for p in all_posts:
                            p._preloaded_comments = comments_by_post.get(p.id, [])

                # Attach eager posts to author instances
                for a in records:
                    a._preloaded_posts = posts_by_author.get(a.id, [])

        return records


# ==============================================================================
# 5. LAB BENCHMARKS & EXPERIMENT ORCHESTRATION
# ==============================================================================
def setup_seed_data(author_count: int = 5, posts_per_author: int = 3, comments_per_post: int = 2):
    """Initializes simulated database tables with hierarchical data."""
    DB.tables["authors"] = {}
    DB.tables["posts"] = {}
    DB.tables["comments"] = {}

    post_seq = 1
    comment_seq = 1

    for a_id in range(1, author_count + 1):
        DB.tables["authors"][a_id] = {
            "id": a_id,
            "name": f"Author_{a_id}",
            "email": f"author_{a_id}@rails-mastery.io"
        }
        for _ in range(posts_per_author):
            p_id = post_seq
            post_seq += 1
            DB.tables["posts"][p_id] = {
                "id": p_id,
                "author_id": a_id,
                "title": f"Deep Dive into Rails #{p_id}",
                "published": True
            }
            for _ in range(comments_per_post):
                c_id = comment_seq
                comment_seq += 1
                DB.tables["comments"][c_id] = {
                    "id": c_id,
                    "post_id": p_id,
                    "body": f"Insightful commentary #{c_id} for post #{p_id}"
                }


def run_lazy_loading_experiment():
    """Scenario 1: Simulating classic N+1 queries (Lazy Loading)."""
    print(f"\n{C_BOLD}{C_RED}[SCENARIO 1] Naive Traversal (N+1 Query Explosion){C_RESET}")
    DB.reset_metrics()
    start_wall_time = time.perf_counter()

    authors = ActiveRecordRelation(Author).all()
    total_comments_retrieved = 0

    for author in authors:
        posts = author.posts()  # Fires query per author
        for post in posts:
            comments = post.comments()  # Fires query per post
            total_comments_retrieved += len(comments)

    elapsed_wall_time = (time.perf_counter() - start_wall_time) * 1000

    print(f"  Processed {len(authors)} authors and {total_comments_retrieved} comments.")
    print(f"  -> Total Database Queries : {C_BOLD}{C_RED}{DB.query_count}{C_RESET}")
    print(f"  -> Simulated DB Latency   : {C_BOLD}{DB.total_simulated_latency:.2f} ms{C_RESET}")
    print(f"  -> Total Wall Clock Time  : {C_BOLD}{elapsed_wall_time:.2f} ms{C_RESET}")


def run_eager_loading_experiment():
    """Scenario 2: Simulating Active Record .includes() (Preloading)."""
    print(f"\n{C_BOLD}{C_GREEN}[SCENARIO 2] Eager Loading with .includes(:posts, :comments){C_RESET}")
    DB.reset_metrics()
    start_wall_time = time.perf_counter()

    authors = ActiveRecordRelation(Author).includes("posts", "comments").all()
    total_comments_retrieved = 0

    for author in authors:
        posts = getattr(author, "_preloaded_posts", author.posts())
        for post in posts:
            comments = getattr(post, "_preloaded_comments", post.comments())
            total_comments_retrieved += len(comments)

    elapsed_wall_time = (time.perf_counter() - start_wall_time) * 1000

    print(f"  Processed {len(authors)} authors and {total_comments_retrieved} comments.")
    print(f"  -> Total Database Queries : {C_BOLD}{C_GREEN}{DB.query_count}{C_RESET}")
    print(f"  -> Simulated DB Latency   : {C_BOLD}{DB.total_simulated_latency:.2f} ms{C_RESET}")
    print(f"  -> Total Wall Clock Time  : {C_BOLD}{elapsed_wall_time:.2f} ms{C_RESET}")


def run_dirty_tracking_and_callbacks_demo():
    """Scenario 3: Demonstrating Active Record dirty state and callback chain."""
    print(f"\n{C_BOLD}{C_MAGENTA}[SCENARIO 3] Dirty Tracking & Callback Pipeline Demonstration{C_RESET}")

    # Register lifecycle callbacks
    def audit_before_save(record: ActiveRecordBase):
        print(f"    {C_CYAN}CALLBACK [before_save]{C_RESET}: Modifying timestamp and validating dirty state.")
        record.updated_at = int(time.time())

    def audit_after_commit(record: ActiveRecordBase):
        print(f"    {C_CYAN}CALLBACK [after_commit]{C_RESET}: Event published to Redis/EventBus for ID: {record.id}")

    Author.register_callback("before_save", audit_before_save)
    Author.register_callback("after_commit", audit_after_commit)

    print(f"  1. Instantiating Author(id=1, name='Original Name')...")
    author = Author(id=1, name="Original Name", email="original@domain.com")
    print(f"     Dirty state initially: {author.is_dirty()} | Changes: {author.changed_attributes()}")

    print(f"\n  2. Mutating attribute author.name = 'DHH (Altered)'...")
    author.name = "DHH (Altered)"
    print(f"     Dirty state after mutate: {C_YELLOW}{author.is_dirty()}{C_RESET}")
    print(f"     Changes recorded: {C_YELLOW}{author.changed_attributes()}{C_RESET}")

    print(f"\n  3. Triggering author.save()...")
    DB.reset_metrics()
    success = author.save()
    print(f"     Persisted successfully: {success}")
    print(f"     Dirty state post-save: {C_GREEN}{author.is_dirty()}{C_RESET}")
    print(f"     Query Executed: {C_BLUE}{DB.query_log[-1] if DB.query_log else 'None'}{C_RESET}")


# ==============================================================================
# MAIN LAB ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    print(f"{C_BOLD}{C_CYAN}======================================================================{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}   ACTIVE RECORD MASTERY DEEP DIVE: INTERNALS & PERFORMANCE LAB      {C_RESET}")
    print(f"{C_BOLD}{C_CYAN}======================================================================{C_RESET}")

    setup_seed_data(author_count=6, posts_per_author=4, comments_per_post=3)
    
    # 1. N+1 vs Preload Demonstration
    run_lazy_loading_experiment()
    run_eager_loading_experiment()

    # 2. Dirty Tracking and Callback Lifecycle
    run_dirty_tracking_and_callbacks_demo()

    print(f"\n{C_BOLD}{C_CYAN}======================================================================{C_RESET}")
    print(f"{C_BOLD}{C_GREEN}LAB COMPLETE: Active Record mechanics successfully analyzed.{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}======================================================================{C_RESET}\n")
    sys.exit(0) if "sys" in locals() else None
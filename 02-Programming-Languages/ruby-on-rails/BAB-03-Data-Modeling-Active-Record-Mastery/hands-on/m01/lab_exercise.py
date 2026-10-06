#!/usr/bin/env python3
"""
ActiveRecord Mastery Lab Simulation (Ruby on Rails Core Concepts)
Hands-on Technical Simulation for BAB-03: Data Modeling & Active Record Mastery
"""

import sys
import time
from typing import Any, Callable, Dict, List, Optional


class ANSI:
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


def log_sql(query: str) -> None:
    print(f"  {ANSI.MAGENTA}DEBUG [ActiveRecord::Base SQL]{ANSI.RESET} {ANSI.CYAN}{query}{ANSI.RESET}")


class ValidationError(Exception):
    pass


class RecordNotFound(Exception):
    pass


class Relation:
    def __init__(self, model_cls: type, records: List[Dict[str, Any]]):
        self.model_cls = model_cls
        self.records = records
        self._where_clauses: List[Callable[[Dict[str, Any]], bool]] = []
        self._order_by: Optional[str] = None
        self._limit_count: Optional[int] = None

    def where(self, **kwargs) -> "Relation":
        new_rel = self._clone()
        for k, v in kwargs.items():
            new_rel._where_clauses.append(lambda r, key=k, val=v: r.get(key) == val)
        return new_rel

    def order(self, field: str) -> "Relation":
        new_rel = self._clone()
        new_rel._order_by = field
        return new_rel

    def limit(self, count: int) -> "Relation":
        new_rel = self._clone()
        new_rel._limit_count = count
        return new_rel

    def _execute(self) -> List[Any]:
        log_sql(f"SELECT * FROM {self.model_cls.table_name} WHERE <clauses> ORDER BY {self._order_by or 'id'}")
        results = self.records
        for clause in self._where_clauses:
            results = [r for r in results if clause(r)]
        if self._order_by:
            reverse = self._order_by.endswith(" DESC")
            field = self._order_by.replace(" DESC", "").strip()
            results = sorted(results, key=lambda r: r.get(field, 0), reverse=reverse)
        if self._limit_count is not None:
            results = results[:self._limit_count]
        return [self.model_cls(**r) for r in results]

    def count(self) -> int:
        return len(self._execute())

    def first(self) -> Optional[Any]:
        res = self.limit(1)._execute()
        return res[0] if res else None

    def to_a(self) -> List[Any]:
        return self._execute()

    def _clone(self) -> "Relation":
        rel = Relation(self.model_cls, self.records)
        rel._where_clauses = list(self._where_clauses)
        rel._order_by = self._order_by
        rel._limit_count = self._limit_count
        return rel


class ActiveRecordBase:
    table_name = "records"
    _storage: List[Dict[str, Any]] = []
    _next_id: int = 1

    def __init__(self, **attributes):
        self.attributes: Dict[str, Any] = attributes
        self.errors: Dict[str, List[str]] = {}
        if "id" not in self.attributes:
            self.attributes["id"] = None

    def __getattr__(self, name: str) -> Any:
        if name in self.attributes:
            return self.attributes[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("attributes", "errors"):
            super().__setattr__(name, value)
        else:
            if "attributes" in self.__dict__ and name in self.attributes:
                self.attributes[name] = value
            else:
                super().__setattr__(name, value)

    @classmethod
    def all(cls) -> Relation:
        return Relation(cls, cls._storage)

    @classmethod
    def where(cls, **kwargs) -> Relation:
        return cls.all().where(**kwargs)

    @classmethod
    def find(cls, record_id: int) -> Any:
        log_sql(f"SELECT * FROM {cls.table_name} WHERE id = {record_id} LIMIT 1")
        for rec in cls._storage:
            if rec.get("id") == record_id:
                return cls(**rec)
        raise RecordNotFound(f"Couldn't find {cls.__name__} with 'id'={record_id}")

    @classmethod
    def create(cls, **attributes) -> Any:
        instance = cls(**attributes)
        instance.save()
        return instance

    def before_validation(self) -> None:
        pass

    def validate(self) -> None:
        pass

    def after_validation(self) -> None:
        pass

    def before_save(self) -> None:
        pass

    def after_save(self) -> None:
        pass

    def is_valid(self) -> bool:
        self.errors = {}
        self.before_validation()
        self.validate()
        self.after_validation()
        return len(self.errors) == 0

    def save(self) -> bool:
        if not self.is_valid():
            return False

        self.before_save()
        if self.attributes.get("id") is None:
            self.attributes["id"] = self.__class__._next_id
            self.__class__._next_id += 1
            log_sql(f"INSERT INTO {self.table_name} (id, ...) VALUES ({self.attributes['id']}, ...)")
            self.__class__._storage.append(dict(self.attributes))
        else:
            log_sql(f"UPDATE {self.table_name} SET ... WHERE id = {self.attributes['id']}")
            for idx, item in enumerate(self.__class__._storage):
                if item["id"] == self.attributes["id"]:
                    self.__class__._storage[idx] = dict(self.attributes)
                    break
        self.after_save()
        return True


class User(ActiveRecordBase):
    table_name = "users"
    _storage = []
    _next_id = 1

    def before_validation(self) -> None:
        if "email" in self.attributes and self.attributes["email"]:
            self.attributes["email"] = self.attributes["email"].strip().lower()

    def validate(self) -> None:
        email = self.attributes.get("email")
        name = self.attributes.get("name")

        if not name:
            self.errors.setdefault("name", []).append("can't be blank")
        if not email:
            self.errors.setdefault("email", []).append("can't be blank")
        elif "@" not in email:
            self.errors.setdefault("email", []).append("is invalid")

        # Uniqueness validation
        for rec in self._storage:
            if rec.get("email") == email and rec.get("id") != self.attributes.get("id"):
                self.errors.setdefault("email", []).append("has already been taken")
                break

    def articles(self) -> Relation:
        # has_many :articles
        return Article.where(user_id=self.id)


class Article(ActiveRecordBase):
    table_name = "articles"
    _storage = []
    _next_id = 1

    def validate(self) -> None:
        title = self.attributes.get("title")
        status = self.attributes.get("status")

        if not title:
            self.errors.setdefault("title", []).append("can't be blank")
        if status not in ("draft", "published", "archived"):
            self.errors.setdefault("status", []).append("is not included in the list")

    def user(self) -> User:
        # belongs_to :user
        return User.find(self.user_id)

    @classmethod
    def published(cls) -> Relation:
        # Scope: scope :published, -> { where(status: 'published') }
        return cls.where(status="published")


def section_header(title: str, step: int) -> None:
    print(f"\n{ANSI.BOLD}{ANSI.BG_BLUE}{ANSI.WHITE} STEP {step} {ANSI.RESET} {ANSI.BOLD}{ANSI.YELLOW}>>> {title} <<<{ANSI.RESET}")
    print(f"{ANSI.DIM}{'=' * 65}{ANSI.RESET}")


def interactive_prompt(prompt_text: str = "Tekan [ENTER] untuk melanjutkan...") -> None:
    print(f"\n{ANSI.BOLD}{ANSI.WHITE}[?] {prompt_text}{ANSI.RESET}", end="", flush=True)
    input()


def simulate_n_plus_one_issue() -> None:
    print(f"\n{ANSI.RED}[!] Simulasi Masalah N+1 Queries:{ANSI.RESET}")
    print(f"{ANSI.DIM}Query mengambil seluruh artikel, kemudian iterasi memanggil `article.user` satu per satu:{ANSI.RESET}")
    articles = Article.all().to_a()
    for art in articles:
        author = art.user()
        print(f"  • Artikel: '{art.title}' ditulis oleh: {ANSI.GREEN}{author.name}{ANSI.RESET}")


def simulate_eager_loading() -> None:
    print(f"\n{ANSI.GREEN}[✓] Solusi Eager Loading (Active Record `includes(:user)`):{ANSI.RESET}")
    print(f"{ANSI.DIM}1. Query Articles, 2. Query IN (IDs user) sekaligus:{ANSI.RESET}")
    log_sql("SELECT * FROM articles")
    articles = Article.all().to_a()
    user_ids = list({a.user_id for a in articles})
    log_sql(f"SELECT * FROM users WHERE id IN ({', '.join(map(str, user_ids))})")

    users_map = {u.id: u for u in [User.find(uid) for uid in user_ids]}
    for art in articles:
        author = users_map[art.user_id]
        print(f"  • (Preloaded) '{art.title}' - Author: {ANSI.GREEN}{author.name}{ANSI.RESET}")


def main() -> None:
    print(f"{ANSI.BOLD}{ANSI.CYAN}")
    print(r"""
    ===============================================================
       ACTIVE RECORD ORM MASTERY SIMULATOR (Ruby on Rails Engine)
    ===============================================================
    """)
    print(f"{ANSI.RESET}{ANSI.WHITE}Simulasi interaktif konsep fundamental ActiveRecord Rails.")
    print(f"Fitur: Migrations, Validations, Lifecycle Callbacks, Associations, Scopes, & N+1 Prevention.{ANSI.RESET}\n")

    time.sleep(0.5)

    # STEP 1: VALIDATION & CALLBACKS
    section_header("LIFECYCLE CALLBACKS & ACTIVE RECORD VALIDATION", 1)
    print(f"{ANSI.WHITE}Mencoba membuat record invalid (email tanpa '@', name kosong)...{ANSI.RESET}")

    bad_user = User(name="", email="john_invalid")
    if not bad_user.save():
        print(f"{ANSI.RED}[GAGAL DISIMPAN] Validasi ActiveRecord menolak input:{ANSI.RESET}")
        for attr, errs in bad_user.errors.items():
            print(f"  ❌ {ANSI.YELLOW}{attr}{ANSI.RESET}: {', '.join(errs)}")

    print(f"\n{ANSI.WHITE}Membuat valid user dengan callback `before_validation` normalisasi huruf kecil:{ANSI.RESET}")
    valid_user_1 = User.create(name="Ruby Dev", email="  RUBY.ENGINEER@EXAMPLE.COM  ")
    valid_user_2 = User.create(name="Garry Tan", email="garry@ycombinator.com")

    print(f"{ANSI.GREEN}✓ User 1 tersimpan! Normalisasi email:{ANSI.RESET} {valid_user_1.email} (ID: {valid_user_1.id})")
    print(f"{ANSI.GREEN}✓ User 2 tersimpan! Normalisasi email:{ANSI.RESET} {valid_user_2.email} (ID: {valid_user_2.id})")

    interactive_prompt()

    # STEP 2: ASSOCIATIONS (has_many & belongs_to)
    section_header("ASSOCIATIONS: has_many & belongs_to", 2)
    print(f"{ANSI.WHITE}Menambahkan artikel yang berelasi dengan User ID {valid_user_1.id} & {valid_user_2.id}...{ANSI.RESET}")

    Article.create(title="Mastering Ruby Metaprogramming", status="published", user_id=valid_user_1.id)
    Article.create(title="Draft: Inside Turbo & Stimulus", status="draft", user_id=valid_user_1.id)
    Article.create(title="Building Scalable Startups with Rails", status="published", user_id=valid_user_2.id)

    print(f"\n{ANSI.CYAN}Mengambil artikel milik '{valid_user_1.name}' via association `user.articles`:{ANSI.RESET}")
    user_articles = valid_user_1.articles().to_a()
    for art in user_articles:
        print(f"  -> [{art.status.upper()}] {art.title} (ID: {art.id})")

    interactive_prompt()

    # STEP 3: SCOPES & LAZY QUERY EVALUATION
    section_header("ACTIVE RECORD SCOPES & LAZY RELATION CHAINING", 3)
    print(f"{ANSI.WHITE}Memanggil Scope `Article.published.order('id DESC').limit(1)`...{ANSI.RESET}")
    print(f"{ANSI.DIM}(Perhatikan SQL log saat method di-chaining vs saat dievaluasi){ANSI.RESET}")

    rel = Article.published().order("id DESC").limit(1)
    print(f"{ANSI.YELLOW}[INFO] Objek Relation terbentuk tanpa query langsung.{ANSI.RESET}")
    print(f"{ANSI.YELLOW}[INFO] Menjalankan evaluasi (.to_a()):{ANSI.RESET}")
    published_latest = rel.to_a()

    for item in published_latest:
        print(f"  🌟 Top Published Article: '{item.title}' (Author User ID: {item.user_id})")

    interactive_prompt()

    # STEP 4: N+1 QUERIES AND EAGER LOADING
    section_header("PERFORMANCE: N+1 QUERY DETECTION & EAGER LOADING", 4)
    simulate_n_plus_one_issue()
    print("-" * 50)
    simulate_eager_loading()

    # SUMMARY
    print(f"\n{ANSI.BOLD}{ANSI.GREEN}==============================================================={ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.GREEN}   LAB SIMULASI ACTIVE RECORD BERHASIL DISELESAIKAN (100% OK) {ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.GREEN}==============================================================={ANSI.RESET}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{ANSI.RED}Lab dihentikan pengguna.{ANSI.RESET}")
        sys.exit(0)

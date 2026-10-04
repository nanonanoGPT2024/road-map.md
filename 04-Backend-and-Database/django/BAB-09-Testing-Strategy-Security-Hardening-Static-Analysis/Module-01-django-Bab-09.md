# Bab 09 Module 01: Testing Strategy, Security Hardening, & Static Analysis

---

## 01: Identitas Modul

* **Track**: Backend and Database Engineering
* **Kategori**: 04-Backend-and-Database
* **Framework**: Django 5.x / Python 3.12+
* **Level**: Advanced / Production-Grade
* **Prasyarat**: Pemahaman mendalam terkait Django ORM, REST Framework, Middleware Architecture, dan Docker.
* **Estimasi Waktu Baca/Praktek**: 180 Menit

---

## 02: Learning Objectives

1. Mampu merancang piramida pengujian komprehensif menggunakan `pytest-django`, `Factory Boy`, `Coverage.py`, dan teknik deterministic mocking.
2. Mampu menerapkan *Defensive Security Controls* pada lapisan konfigurasi Django, Content Security Policy (CSP), Cross-Site Scripting (XSS), SQL Injection (SQLi), dan Cross-Site Request Forgery (CSRF).
3. Mampu mengintegrasikan *Static Application Security Testing* (SAST) dan *type checking* ketat menggunakan `mypy` (django-stubs), `ruff`, `bandit`, dan `pip-audit`.
4. Mampu menyusun pipeline *Continuous Integration* (CI) otomatis yang memberlakukan *zero-tolerance policy* terhadap regresi fungsional, kerentanan dependensi, dan degradasi tipe data.

---

## 03: Concept Map Diagram ASCII

```text
+-----------------------------------------------------------------------------------+
|                        DJANGO QUALITY ASSURANCE & DEFENSE                         |
+-----------------------------------------------------------------------------------+
                                          |
         +--------------------------------+--------------------------------+
         |                                |                                |
         v                                v                                v
+------------------+            +------------------+            +------------------+
|  STATIC ANALYSIS |            | TESTING STRATEGY |            | SECURITY DEFENSE |
|  & TYPE CHECKING |            |  (Pytest/Piramid)|            |  (OWASP / CSP)   |
+------------------+            +------------------+            +------------------+
| - Ruff (Linting) |            | - Unit Tests     |            | - Strict Headers |
| - Mypy (Stubs)   |            | - API Tests      |            | - CSP Nonces     |
| - Bandit (AST)   |            | - Factories      |            | - Auth Throttling|
| - Pip-audit (CVE)|            | - DB Isolation   |            | - CSRF & Encrypt |
+------------------+            +------------------+            +------------------+
         |                                |                                |
         +--------------------------------+--------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                    SECURE CI/CD PIPELINE (Deterministic Gate)                     |
+-----------------------------------------------------------------------------------+
```

---

## 04: Mengapa Relevan

Dalam ekosistem *mission-critical enterprise*, stabilitas dan keamanan aplikasi web tidak dapat diverifikasi secara manual. Kesalahan kecil seperti ketiadaan sanitasi input, konfigurasi header CORS/CSP yang terlalu permisif, atau penggunaan dynamic query ORM (`.extra()` / raw SQL string concatenation) dapat berujung pada eksfiltrasi data skala besar. 

Modul ini membekali Principal Engineer dengan metodologi pengujian modern (*fast-feedback testing*), *static type safety* pada Python yang bersifat dinamis, dan hardening tingkat kernel-aplikasi guna memenuhi standar industri perbankan dan enterprise (PCI-DSS, ISO 27001, OWASP ASVS).

---

## 05: Anatomi Konsep Inti

### 1. Pytest Engine Architecture
Pengujian modern pada Django meninggalkan modul bawaan `unittest` dan beralih ke `pytest-django`. Pytest menyediakan mekanisme *dependency injection* berbasis *fixtures*, manajemen transaksi database yang granular (`db`, `transactional_db`), dan paralelisasi uji (*pytest-xdist*) tanpa overhead instansiasi TestCase yang lambat.

### 2. Static Typing via Django-Stubs
Python bukan bahasa bertipe statis pada runtime. `mypy` yang diperluas oleh plugin `django-stubs` menganalisis *Abstract Syntax Tree* (AST) untuk memastikan *type-safety* pada Model Fields, QuerySets, Managers, dan Request-Response cycle secara deterministik sebelum kode masuk tahap build.

### 3. Content Security Policy (CSP) & HTTP Defenses
CSP Level 3 memitigasi eksekusi XSS dengan menolak eksekusi inline script yang tidak memiliki cryptographic *nonce* atau *hash*. Modul `django-csp` mengelola state nonce per-request, yang diintegrasikan bersama header protektif: `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, dan `Cross-Origin-Opener-Policy`.

---

## 06: Panduan Implementasi Step-by-Step

### Langkah 1: Inisialisasi Tooling Dependencies
Definisikan dependensi inti pada file konfigurasi modern (`pyproject.toml`):

```toml
[tool.poetry.group.dev.dependencies]
pytest = "^8.1.1"
pytest-django = "^4.8.0"
pytest-xdist = "^3.5.0"
pytest-cov = "^5.0.0"
factory-boy = "^3.3.0"
mypy = "^1.9.0"
django-stubs = {extras = ["compatible-mypy"], version = "^4.2.7"}
ruff = "^0.3.4"
bandit = {extras = ["toml"], version = "^1.7.8"}
pip-audit = "^2.7.2"
django-csp = "^3.7"
```

### Langkah 2: Konfigurasi Pytest (`pytest.ini` / `pyproject.toml`)
```ini
[pytest]
DJANGO_SETTINGS_MODULE = core.settings.test
python_files = tests.py test_*.py *_tests.py
addopts = 
    --strict-markers
    --strict-config
    --reuse-db
    -v
    --cov=.
    --cov-report=term-missing:skip-covered
    --cov-fail-under=85
markers =
    unit: Fast isolated unit tests.
    integration: Database and integration tests.
    security: Specific security validation tests.
```

---

## 07: Contoh Kasus Sederhana

Implementasi pengujian model mutasi akun saldo secara atomic tanpa *race condition*:

```python
# accounts/models.py
from decimal import Decimal
from django.db import models, transaction
from django.core.exceptions import ValidationError

class Account(models.Model):
    account_number = models.CharField(max_length=20, unique=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    def deposit(self, amount: Decimal) -> None:
        if amount <= Decimal("0.00"):
            raise ValidationError("Jumlah deposit harus positif.")
        with transaction.atomic():
            account = Account.objects.select_for_update().get(pk=self.pk)
            account.balance += amount
            account.save()
            self.balance = account.balance

# tests/test_simple_account.py
import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from accounts.models import Account

@pytest.mark.django_db
def test_account_deposit_success():
    acc = Account.objects.create(account_number="ACC-1001", balance=Decimal("50.00"))
    acc.deposit(Decimal("25.00"))
    assert acc.balance == Decimal("75.00")

@pytest.mark.django_db
def test_account_deposit_invalid_amount():
    acc = Account.objects.create(account_number="ACC-1002", balance=Decimal("50.00"))
    with pytest.raises(ValidationError):
        acc.deposit(Decimal("-10.00"))
```

---

## 08: Implementasi Production-Grade Lengkap Kode

Berikut adalah implementasi sistem transfer saldo multi-akun dengan proteksi audit log, factory fixtures, API endpoints, dan security headers.

### 1. Model & Engine Layer (`banking/models.py`)
```python
import uuid
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction


class LedgerEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    source_account = models.ForeignKey(
        "BankAccount", related_name="debit_entries", on_delete=models.PROTECT
    )
    destination_account = models.ForeignKey(
        "BankAccount", related_name="credit_entries", on_delete=models.PROTECT
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        indexes = [
            models.Index(fields=["source_account", "destination_account"]),
        ]


class BankAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    account_number = models.CharField(max_length=32, unique=True, db_index=True)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    is_active = models.BooleanField(default=True)

    def execute_transfer(self, destination: "BankAccount", amount: Decimal) -> LedgerEntry:
        if amount <= Decimal("0.00"):
            raise ValidationError("Jumlah transfer tidak valid.")
        if not self.is_active or not destination.is_active:
            raise ValidationError("Salah satu atau kedua akun tidak aktif.")
        if self.pk == destination.pk:
            raise ValidationError("Akun asal dan tujuan tidak boleh sama.")

        # Menghindari Deadlock: Lock baris berdasarkan urutan Primary Key
        first_id, second_id = (
            (self.pk, destination.pk) if self.pk < destination.pk else (destination.pk, self.pk)
        )

        with transaction.atomic():
            first_acc = BankAccount.objects.select_for_update().get(pk=first_id)
            second_acc = BankAccount.objects.select_for_update().get(pk=second_id)

            sender = first_acc if self.pk == first_acc.pk else second_acc
            receiver = destination if destination.pk == second_acc.pk else first_acc

            if sender.balance < amount:
                raise ValidationError("Saldo tidak mencukupi.")

            sender.balance -= amount
            receiver.balance += amount

            sender.save(update_fields=["balance"])
            receiver.save(update_fields=["balance"])

            ledger = LedgerEntry.objects.create(
                source_account=sender, destination_account=receiver, amount=amount
            )

            # Update in-memory reference
            self.balance = sender.balance
            destination.balance = receiver.balance

            return ledger
```

### 2. Factory Boy Mock Setup (`tests/factories.py`)
```python
from decimal import Decimal
import factory
from django.contrib.auth import get_user_model
from banking.models import BankAccount

User = get_user_model()

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@infra.security.corp")
    is_active = True

class BankAccountFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BankAccount

    user = factory.SubFactory(UserFactory)
    account_number = factory.Sequence(lambda n: f"ACC-ID-{n:08d}")
    balance = Decimal("10000.00")
    is_active = True
```

### 3. Production Hardening Pytest Suite (`tests/test_banking_engine.py`)
```python
import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from banking.models import BankAccount, LedgerEntry
from tests.factories import BankAccountFactory

@pytest.mark.django_db(transaction=True)
class TestBankingEngine:
    def test_concurrent_transfer_execution_integrity(self):
        source = BankAccountFactory(balance=Decimal("5000.00"))
        dest = BankAccountFactory(balance=Decimal("1000.00"))
        transfer_amount = Decimal("1500.00")

        ledger = source.execute_transfer(dest, transfer_amount)

        source.refresh_from_db()
        dest.refresh_from_db()

        assert source.balance == Decimal("3500.00")
        assert dest.balance == Decimal("2500.00")
        assert ledger.amount == transfer_amount
        assert LedgerEntry.objects.filter(id=ledger.id).exists()

    def test_insufficient_balance_rejection(self):
        source = BankAccountFactory(balance=Decimal("100.00"))
        dest = BankAccountFactory(balance=Decimal("500.00"))

        with pytest.raises(ValidationError, match="Saldo tidak mencukupi."):
            source.execute_transfer(dest, Decimal("200.00"))

        source.refresh_from_db()
        dest.refresh_from_db()
        assert source.balance == Decimal("100.00")
        assert dest.balance == Decimal("500.00")
```

---

## 09: Diagram Alur Kerja ASCII

Mekanisme validasi Static Analysis, Unit Testing, dan Security Gate pada CI Workflow:

```text
[ Developer Git Push ]
          │
          ▼
┌─────────────────────────────────────────────────────────┐
│              STAGE 1: STATIC CODE GATES                 │
│  ├─ Ruff (Fast Lint & Format Check)                    │
│  ├─ Mypy --strict (Type checking AST)                  │
│  └─ Bandit -r (AST Static Security Scanner)            │
└─────────────────────────┬───────────────────────────────┘
                          │ Pass
                          ▼
┌─────────────────────────────────────────────────────────┐
│            STAGE 2: DEPENDENCY AUDIT                    │
│  └─ pip-audit (CVE Database Synchronization)            │
└─────────────────────────┬───────────────────────────────┘
                          │ Pass
                          ▼
┌─────────────────────────────────────────────────────────┐
│            STAGE 3: ISOLATED TEST MATRIX                │
│  ├─ pytest -n auto --reuse-db (Parallel Execution)     │
│  ├─ pytest-cov (Coverage >= 85% Check)                  │
│  └─ Security Headers / XSS / Injections Assertion       │
└─────────────────────────┬───────────────────────────────┘
                          │ Pass
                          ▼
              [ Artifact Deployment Ready ]
```

---

## 10: Analisis Trade-offs

| Pendekatan | Keuntungan | Kerugian / Trade-off | Mitigasi |
| :--- | :--- | :--- | :--- |
| **Strict Mypy (`django-stubs`)** | Menghilangkan runtime `AttributeError` & `TypeError` secara definitif sebelum deployment. | *Development velocity* awal melambat; penulisan generics/QuerySets menjadi sangat verbose. | Gunakan type aliases dan utility generic models khusus. |
| **Factory Boy vs Raw Fixtures** | Data uji bersifat dinamis, decoupled dari skema dump JSON yang mudah stale/usang. | Overhead kalkulasi pembuatan object di memori sedikit lebih lambat dibanding SQL dump raw. | Terapkan `factory.build()` jika persistensi database tidak mutlak diperlukan. |
| **Pemberlakuan CSP Nonce Level 3** | Mengeliminasi vektor serangan XSS tipe Reflected dan Stored secara drastis. | Memblokir seluruh legacy scripts, eval(), dan inline dynamic styles pihak ketiga. | Gunakan reporting-only mode (`CSP_REPORT_ONLY = True`) pada fase observasi staging. |

---

## 11: Best Practices & Antipatterns

### Best Practices
* **Zero-Mocking Database Policy pada Core Logic**: Gunakan DB isolation (`@pytest.mark.django_db`) berbasis transaksi rollback alih-alih meng-mock ORM queryset secara manual.
* **Deterministic Test State**: Hindari penggunaan library `datetime.now()` secara langsung di dalam test tanpa *freeze gun* (`pytest-freezegun` / `time-machine`).
* **Shift-Left Security Scanner**: Integrasikan Bandit dan Ruff sebagai *pre-commit hook* lokal guna mendeteksi celah sebelum sinkronisasi git remote.

### Antipatterns (Jangan Dilakukan)
```python
# ANTI-PATTERN 1: SQL Injection via .extra() atau raw string formatting
BankAccount.objects.extra(where=[f"account_number = '{user_input}'"])  # BERBAHAYA!

# ANTI-PATTERN 2: Menggunakan unittest TestCase default Django untuk unit tests
from django.test import TestCase
class SlowTest(TestCase): # Menjalankan skrip flush database penuh di tiap test class
    pass

# ANTI-PATTERN 3: Mematikan proteksi host
ALLOWED_HOSTS = ['*']  # Membuka celah Host Header Injection
```

---

## 12: Security Hardening (Zero-Trust Configuration)

Konfigurasi kernel settings Django (`core/settings/security.py`) untuk implementasi *Strict Defenses*:

```python
# SECURE TRANSPORT & COOKIES
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000  # 1 Year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Strict"

# CONTENT SECURITY POLICY (django-csp)
CSP_DEFAULT_SRC = ("'none'",)
CSP_SCRIPT_SRC = ("'self'",)
CSP_CONNECT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'",)
CSP_FONT_SRC = ("'self'",)
CSP_IMG_SRC = ("'self'", "data:")
CSP_INCLUDE_NONCE_IN = ["script-src", "style-src"]

# BROWSER ISOLATION HEADERS
SECURE_BROWSER_XSS_FILTER = False # Deprecated on modern browsers; substituted by CSP
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
```

---

## 13: Observabilitas & Debugging

Gunakan custom middleware untuk mengidentifikasi dan mencatat query database yang bermasalah (*N+1 problem*) selama *automated test execution* atau fase debugging:

```python
# core/middleware/query_budget.py
import logging
from django.db import connection
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger("security.performance")

class QueryBudgetMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        initial_queries = len(connection.queries)
        response = self.get_response(request)
        final_queries = len(connection.queries)
        total_queries = final_queries - initial_queries

        if total_queries > 20: # Threshold threshold limit
            logger.warning(
                "Excessive DB Queries detected! Path: %s, Query Count: %d",
                request.path,
                total_queries
            )
            response["X-Query-Budget-Alert"] = f"Exceeded: {total_queries} queries"
        return response
```

---

## 14: Benchmarking & Performance

Optimalkan eksekusi pengujian massal menggunakan paralelisasi worker berbasis logical CPU cores:

```bash
# Eksekusi serial standar
pytest
# Output: 450 passed in 48.32s

# Eksekusi paralel terdistribusi dengan SQLite In-Memory Template DB
pytest -n auto --dist=loadfile --reuse-db
# Output: 450 passed in 8.15s (Peningkatan kecepatan ~590%)
```

Pencegahan regresi performa query via snapshot assertion:
```python
@pytest.mark.django_db
def test_bank_account_list_query_budget(django_assert_num_queries, client):
    BankAccountFactory.create_batch(50)
    with django_assert_num_queries(1): # Memastikan tidak ada N+1 query
        client.get("/api/v1/accounts/")
```

---

## 15: Hands-on Lab Mini-Project

### Setup File Linting & Security Gate (`pyproject.toml`)

```toml
[tool.ruff]
line-length = 100
target-version = "py312"
select = [
    "F",    # Pyflakes
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "I",    # isort
    "B",    # flake8-bugbear
    "S",    # flake8-bandit (Security)
    "UP",   # pyupgrade
    "DJ",   # flake8-django
]
ignore = ["S101"] # Izinkan assert di unit test

[tool.mypy]
python_version = "3.12"
plugins = ["mypy_django_plugin.main"]
strict = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.django-stubs]
django_settings_module = "core.settings.test"

[tool.bandit]
exclude_dirs = ["tests", "venv", ".venv"]
skips = ["B101"]
```

---

## 16: Automated Testing & Verification

Berikut adalah rancangan pipeline Continuous Integration otomatis yang mencakup seluruh lifecycle analisis dan pengujian (`.github/workflows/ci.yml`):

```yaml
name: CI Quality & Security Pipeline

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]

jobs:
  static-security-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install ruff mypy django-stubs bandit pip-audit

      - name: Run Ruff Linter & Format Check
        run: ruff check . && ruff format --check .

      - name: Static Type Checking with Mypy
        run: mypy .

      - name: Security Static Scan with Bandit
        run: bandit -c pyproject.toml -r .

      - name: Audit Third-party Dependencies
        run: pip-audit --strict

  test-suite:
    needs: static-security-audit
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: test_db
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4
      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install App Dependencies
        run: |
          pip install -r requirements/test.txt

      - name: Run Pytest with Coverage Gate
        env:
          DATABASE_URL: postgres://test_user:test_password@localhost:5432/test_db
          DJANGO_SETTINGS_MODULE: core.settings.test
        run: |
          pytest -n auto --cov=. --cov-fail-under=85
```

---

## 17: Troubleshooting Guide

| Gejala Masalah | Akar Penyebab (Root Cause) | Resolusi Teknis |
| :--- | :--- | :--- |
| `mypy` error: *Signature incompatible with supertype* saat override `save()` model. | Django model generic method membutuhkan `*args` dan `**kwargs` lengkap atau type annotating custom kwargs. | Ubah deklarasi menjadi: `def save(self, *args: Any, **kwargs: Any) -> None:`. |
| Error `TransactionManagementError` pada Pytest saat memakai threading/celery. | Database runner default membungkus test di single rollback transaction. | Tambahkan marker `@pytest.mark.django_db(transaction=True)` pada class/fungsi test terkait. |
| Bandit mendeteksi issue `B608: Hardcoded SQL string`. | String formatting manual (`%` atau `f""`) terdeteksi pada argument query method ORM. | Gunakan Django ORM Expression API (`F()`, `Q()`, Subquery) atau parameterized raw SQL (`.raw(query, [params])`). |

---

## 18: Checklist Produksi

- [ ] **Static Analysis Zero Exit Code**: `ruff check`, `mypy --strict`, dan `bandit -r` lulus evaluasi dengan 0 error/warning.
- [ ] **Dependency Cleanliness**: `pip-audit` tidak menemukan celah CVE berstatus HIGH/CRITICAL pada *runtime lockfile*.
- [ ] **Test Coverage Enforcement**: Cakupan pengujian unit dan integrasi `>= 85%`.
- [ ] **Hardened Settings Active**: Seluruh variable `SECURE_*` dan `django-csp` aktif pada file environment target.
- [ ] **Database Concurrency Protection**: Penggunaan `select_for_update()` diterapkan pada seluruh mutasi data saldo/inventori kritis untuk mencegah race condition.
- [ ] **Secrets Segregation**: Tidak ada API Key, SECRET_KEY, atau credential database yang ter-commit ke version control repository.

---

## 19: Ringkasan Eksekutif

Modern software quality assurance untuk Django menuntut orkestrasi tools otomatis yang ketat:
1. **Pytest** dan **Factory Boy** mempercepat cycle testing sekaligus memfasilitasi pengujian skenario konkurensi kompleks secara deterministik.
2. **Mypy** bersama **Django-Stubs** mengubah Python menjadi lingkungan yang memiliki type-safety ketat, meminimalkan error fatal runtime.
3. **Hardening OWASP** dan konfigurasi headers (HSTS, CSP Nonces) memastikan sistem memiliki perlindungan berlapis terhadap serangan injeksi dan pencurian kredensial.
4. **Automated CI Gates** bertindak sebagai benteng pertahanan terakhir yang memastikan tidak ada kode cacat fungsional atau bermasalah secara keamanan yang dapat lolos ke server produksi.

---

## 20: Referensi & Bacaan Lanjutan

* Django Software Foundation. *Security in Django*. [https://docs.djangoproject.com/en/5.0/topics/security/](https://docs.djangoproject.com/en/5.0/topics/security/)
* Pytest-Django Documentation. *Writing tests for Django applications*. [https://pytest-django.readthedocs.io/](https://pytest-django.readthedocs.io/)
* OWASP Foundation. *Django Security Cheat Sheet*. [https://cheatsheetseries.owasp.org/](https://cheatsheetseries.owasp.org/)
* TypedDjango. *django-stubs: Official PEP-484 typing stubs for Django*. [https://github.com/typeddjango/django-stubs](https://github.com/typeddjango/django-stubs)
* Mozilla Developer Network (MDN). *Content Security Policy (CSP) Guide*. [https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP](https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP)
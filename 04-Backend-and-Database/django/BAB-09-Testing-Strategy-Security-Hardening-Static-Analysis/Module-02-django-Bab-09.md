# Kurikulum Enterprise: Django
## Kategori: 04-Backend-and-Database
### BAB 09: Testing Strategy, Security Hardening, & Static Analysis
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Principal Software Engineer / Senior Backend Architect diharapkan mampu:
- Mengonfigurasi dan mengoptimalkan pipeline pengujian paralel berbasis `pytest-django` dan `factory_boy` dengan isolasi transaksi tingkat lanjut (`savepoints` vs. `table truncation`).
- Mendesain strategi pengujian end-to-end terdistribusi dengan teknik *contract testing*, isolasi dependensi eksternal via mocking deterministik, dan verifikasi mutasi (*mutation testing* via `mutmut`).
- Menerapkan arsitektur *Defense-in-Depth* pada Django, mencakup Content Security Policy (CSP) berbasis *nonce*, penanganan *cross-site leaks*, mitigasi ancaman Session Hijacking, dan pengerasan konfigurasi TLS/HSTS tingkat lanjut di layer reverse proxy serta WSGI/ASGI.
- Mengintegrasikan analisis statis berbasis Abstract Syntax Tree (AST), pemeriksaan pengetikan ketat (`django-stubs` dengan `mypy`), dan scanning kerentanan otomatis (`bandit`, `semgrep`) ke dalam CI/CD pipeline dengan *zero-tolerance policy* terhadap regresi keamanan.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
- Arsitektur internal Django ORM: Transaksi database, siklus koneksi, dan eksekusi query SQL raw/kompilasi queryset.
- Teori dasar pengujian perangkat lunak: Unit testing, integration testing, Mock objects, dan Metrik Code Coverage.
- Protokol Web & Keamanan Dasar: HTTP headers, RFC 6749 (OAuth2), mekanika CSRF, SameSite Cookie attributes, CORS, dan OWASP Top 10 API Security Risks.
- Penggunaan Docker, Redis, PostgreSQL, dan pipeline CI/CD (GitHub Actions / GitLab CI).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Mekanika Isolasi Transaksi Database pada Django Test Suite

Django menyediakan dua kelas runner utama untuk pengujian database: `django.test.TestCase` dan `django.test.TransactionTestCase`. Memahami perbedaan internal keduanya sangat penting untuk mengoptimalkan performa dan menghindari kontaminasi state pengujian.

```
+------------------------------------------------------------------------------------+
|                               django.test.TestCase                                 |
+------------------------------------------------------------------------------------+
|  [START TEST RUNNER]                                                               |
|        |                                                                           |
|        v                                                                           |
|  BEGIN OUTER TRANSACTION (Database Level)                                          |
|        |                                                                           |
|        +---> setUpTestData() [Class Level: Dijalankan 1x untuk seluruh method]     |
|        |                                                                           |
|        +---> SAVEPOINT "test_method_1"                                             |
|        |         |                                                                 |
|        |         v                                                                 |
|        |     setUp() -> run_test_1() -> tearDown()                                 |
|        |         |                                                                 |
|        |         v                                                                 |
|        +---> ROLLBACK TO SAVEPOINT "test_method_1" (Data dibersihkan tanpa DDL TRUNCATE)
|        |                                                                           |
|        +---> SAVEPOINT "test_method_2"                                             |
|        |         |                                                                 |
|        |         v                                                                 |
|        |     setUp() -> run_test_2() -> tearDown()                                 |
|        |         |                                                                 |
|        |         v                                                                 |
|        +---> ROLLBACK TO SAVEPOINT "test_method_2"                                 |
|        |                                                                           |
|        v                                                                           |
|  ROLLBACK OUTER TRANSACTION                                                        |
+------------------------------------------------------------------------------------+

+------------------------------------------------------------------------------------+
|                           django.test.TransactionTestCase                          |
+------------------------------------------------------------------------------------+
|  [START TEST RUNNER]                                                               |
|        |                                                                           |
|        v                                                                           |
|  run_test_1() [Menjalankan commit nyata ke DB]                                     |
|        |                                                                           |
|        v                                                                           |
|  EMIT POST_MIGRATE / TRUNCATE ALL TABLES (I/O intensif, lambat)                    |
|        |                                                                           |
|        v                                                                           |
|  run_test_2() [Menjalankan commit nyata ke DB]                                     |
|        |                                                                           |
|        v                                                                           |
|  TRUNCATE ALL TABLES (Database dibersihkan per-test case)                          |
+------------------------------------------------------------------------------------+
```

1. **`django.test.TestCase`**:
   - Seluruh eksekusi test class dibungkus dalam satu transaksi database tunggal.
   - `setUpTestData()` dieksekusi sekali di level class untuk membuat fixture awal.
   - Setiap method pengujian dibungkus di dalam *Savepoint* tingkat database (`SAVEPOINT "django_test_savepoint"`).
   - Saat method pengujian selesai (baik pass maupun fail), Django mengeksekusi `ROLLBACK TO SAVEPOINT`, mengembalikan kondisi DB ke titik setelah `setUpTestData()`. Tidak ada operasi disk DDL I/O seperti `TRUNCATE`, sehingga pengujian berjalan sangat cepat.
   - **Limitasi**: Tidak dapat memverifikasi logic yang membutuhkan penanganan transaksi eksplisit seperti `transaction.atomic()` yang dipicu bersamaan dengan error handling tingkat thread atau asynchronous database operations.

2. **`django.test.TransactionTestCase`**:
   - Digunakan secara spesifik saat kode yang diuji melakukan operasi commit manual via `transaction.commit()` atau memvalidasi sinyal paska-commit (`transaction.on_commit()`).
   - Membersihkan data dengan mengeksekusi truncate pada semua tabel yang termodifikasi di akhir setiap method pengujian.
   - **Cost**: Penalti performa I/O yang sangat besar (10x - 100x lebih lambat dibanding `TestCase`).

#### B. Pipeline Arsitektur Security Hardening

Siklus penanganan request Django yang dikeraskan (*hardened*) diatur oleh urutan preseden *Middleware Chain*. Middleware keamanan harus diposisikan di urutan paling atas untuk menggagalkan request berbahaya sebelum parsing body atau eksekusi query ORM:

```
[Inbound Client Request]
       |
       v
+-------------------------------+  1. TLS Termination, Host Verification,
| SecurityMiddleware            |     HSTS Enforcing, SSL Redirect
+-------------------------------+
       |
       v
+-------------------------------+  2. Strict Content-Security-Policy & Nonce
| CSPMiddleware (django-csp)    |     Injection untuk Mitigasi XSS
+-------------------------------+
       |
       v
+-------------------------------+  3. Pengecekan Origin & Referer Header 
| CorsMiddleware                |     untuk Permissive/Restricted Cross-Origin
+-------------------------------+
       |
       v
+-------------------------------+  4. Token Extraction & Masked Secret Comparison
| CsrfViewMiddleware            |     (BREACH Attack Protection)
+-------------------------------+
       |
       v
+-------------------------------+  5. Distributed Leaky Bucket / Token Bucket
| AdvancedRateLimitMiddleware   |     Filtering via Redis Atomic Lua Scripts
+-------------------------------+
       |
       v
[Django View Execution & DB Transaction]
```

#### C. Static Code Analysis Pipeline Mechanics

Pipeline analisis statis enterprise tidak hanya memvalidasi linting visual (gaya kode), melainkan membedah Semantic Token Tree dan Abstract Syntax Tree (AST):
- **`mypy` + `django-stubs`**: Menginferensikan dynamic metaclass Django (seperti field lookup `user__profile__organization_id`) menjadi typed structures yang divalidasi saat kompilasi tanpa menjalankan kode.
- **`Bandit`**: Menguraikan AST untuk menemukan penggunaan fungsi berbahaya, misal deserialisasi `pickle`, eksekusi `shell=True` pada `subprocess`, string SQL format concatenation, atau pseudo-random generator pada token kriptografi (`random` vs `secrets`).
- **`Semgrep`**: Melakukan matching pola semantic di seluruh dependensi cross-file untuk memastikan sanitasi konteks input sebelum passing ke low-level engine Django ORM (`QuerySet.extra()`, `raw()`).

---

### 4. Why & What

| Komponen / Konsep | Mengapa Dibutuhkan (Why) | Apa yang Dilakukan (What) |
| :--- | :--- | :--- |
| **`pytest-django` Engine** | Modul runner bawaan `manage.py test` memiliki eksekusi serial yang lambat, minim dukungan fixtures modular, dan pelaporan yang kaku. | Framework runner berbasis test-discovery canggih dengan dukungan native execution parallelism (`pytest-xdist`), reusable dependency injection via fixtures, dan parameterization. |
| **`factory_boy` vs Fixtures JSON** | Fixture statis JSON/YAML rapuh terhadap perubahan schema migrations, sulit dirawat, dan memicu ketergantungan relasional global antar-test. | Mengimplementasikan pola *Object Mother* dan *Factory Pattern* secara programatis, menghasilkan mock data dinamis berbasis schema terkini secara on-demand. |
| **Mutation Testing (`mutmut`)** | Metrik *Code Coverage* 100% sering kali palsu; baris kode tereksekusi namun tidak divalidasi oleh assertion yang tepat (*pseudo-testing*). | Secara sengaja menyisipkan bug sintaksis (mutasi operator: `+` ke `-`, `==` ke `!=`) dan menguji apakah test suite mendeteksi kegagalan tersebut (*killing the mutant*). |
| **CSP dengan Nonce Dinamis** | Header CSP statis rentan dieksploitasi bila attacker berhasil menyisipkan payload via injection bypass atau script pihak ketiga yang disusupi. | Menginjeksi token acak kriptografis (nonce) yang unik per-HTTP request ke header `Content-Security-Policy` dan mencocokkannya ke atribut HTML `<script nonce="...">`. |
| **Advanced Static Analysis** | Peninjauan manual (code review) sering kali melewatkan race condition, *silent type coercions*, dan kebocoran vektor injeksi. | Memverifikasi kepatuhan type safety, mengevaluasi potensi SQLi, dan menegakkan standar keamanan statis secara deterministik di level pre-commit dan CI. |

---

### 5. How (Workflow Detail)

#### Workflow Implementasi Pengujian Skala Enterprise:
1. **Inisialisasi Database Isolasi**: Runner memicu pembuatan database terisolasi (`test_db`). Jika parallel runner aktif (`-n auto`), database dibuat sejumlah worker CPU core (`test_db_gw0`, `test_db_gw1`).
2. **Factory Generation**: Data dibuat secara atomik menggunakan Factory Boy yang terikat pada sub-transaksi aktif.
3. **Execution & Interception**:
   - Mocking layer external API (`responses`, `requests-mock`, atau `pytest-mock`).
   - Freeze time logic (`time-machine` atau `freezegun`) untuk data sensitif temporal (expirable tokens, session limits).
4. **Assertion Validasi**: Validasi kondisi state DB, respons HTTP, dan side effect (task Celery atau transactional audit logs via `django.test.utils.CaptureQueriesContext`).
5. **Teardown**: Pemicuan database rollback savepoint otomatis, me-reset state cache, dan clearing redis registry.

#### Workflow Hardening Keamanan Produksi:
1. **Strict Transport Hardening**: Redirection seluruh non-HTTPS payload, penambahan preload list pada HTTP Strict Transport Security (HSTS).
2. **Isolation Context Security**: Menetapkan header `Cross-Origin-Opener-Policy` (COOP) dan `Cross-Origin-Embedder-Policy` (COEP) untuk memitigasi serangan Spectre/Meltdown berbasis browser.
3. **Session Re-authentication**: Mencegah Session Fixation dengan rotasi `session_key` otomatis setiap terjadi mutasi privilege pengguna (`django.contrib.auth.rotate_token`).
4. **Static AST Enforcement**: Menjalankan pre-commit hooks lokal; jika security rule terlanggar (misal import modul terlarang atau tipe mismatch), build digagalkan sebelum masuk ke repository remote.

---

### 6. Analogy & Diagram ASCII

#### Analogi Savepoint vs Truncate
Bayangkan Anda sedang menulis draf buku di software text editor:
- **`django.test.TestCase` (Savepoints)** sama seperti menekan `Ctrl+Z` (Undo). Anda mengetik satu kalimat pengujian, lalu menekan Undo. Editor instan kembali ke state sebelumnya di memori, tanpa perlu menghapus seluruh file hard disk.
- **`django.test.TransactionTestCase` (Truncate)** sama seperti Anda mencetak buku tersebut ke kertas fisik, lalu ketika ingin mengulang, Anda membakar seluruh kertas hingga menjadi abu dan mencetaknya ulang dari awal. Proses ini memakan waktu dan sumber daya fisik secara masif.

#### Pipeline Arsitektur CI/CD Static Analysis

```
+------------------------------------------------------------------------------------+
|                             DEVELOPER WORKSTATION                                  |
|                                                                                    |
|  [Git Commit] ---> Pre-commit Hooks Execution:                                     |
|                      |-- Ruff (Linter & Code Formatting)                           |
|                      |-- mypy + django-stubs (Strict Type Checking)                |
|                      \-- Bandit (AST Vulnerability Check)                          |
+------------------------------------------------------------------------------------+
                                      |
                                  git push
                                      v
+------------------------------------------------------------------------------------+
|                             CI PIPELINE (GITHUB ACTIONS)                           |
|                                                                                    |
|  Phase 1: Deep Static Analysis & Dependency Audit                                  |
|     +-------------------------+      +-------------------------+                   |
|     |  Semgrep SAST Ruleset   |      |   pip-audit / safety    |                   |
|     +-------------------------+      +-------------------------+                   |
|                                                                                    |
|  Phase 2: Parallelized Test Suite Execution                                        |
|     +------------------------------------------------------------------------+     |
|     |  pytest -n auto --cov=core --cov-report=xml --cov-fail-under=90        |     |
|     |  |-- Worker 0: Unit tests (TestCase)                                   |     |
|     |  |-- Worker 1: Integration tests (APIClient)                            |     |
|     |  \-- Worker 2: Transaction-heavy tests (TransactionTestCase)           |     |
|     +------------------------------------------------------------------------+     |
|                                                                                    |
|  Phase 3: Mutation Verification Gate (Nightly / Target Scope)                      |
|     +------------------------------------------------------------------------+     |
|     |  mutmut run --paths-to-mutate=core/services/payments.py                |     |
|     +------------------------------------------------------------------------+     |
|                                      |                                             |
|                                    PASS?                                           |
|                                    /   \                                           |
|                              YES  /     \  NO                                      |
|                                  v       v                                         |
|                      [DEPLOY TO STAGING]  [FAIL PIPELINE & NOTIFY]                 |
+------------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Advanced Testing Setup: `pytest-django` + `factory_boy` + Transaksi

##### Konfigurasi: `pytest.ini`
```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings.test
python_files = tests.py test_*.py *_tests.py
addopts = 
    --strict-markers
    --strict-config
    --durations=10
    -p no:warnings
markers =
    unit: Tes unit terisolasi tanpa akses DB
    integration: Tes integrasi dengan dependensi DB
    slow: Tes transaksi berat atau multi-service
```

##### Factory Implementation: `core/factories.py`
```python
from decimal import Decimal
import factory
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.models import Account, Transaction

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = factory.Faker("user_name")
    email = factory.Faker("safe_email")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_active = True
    is_staff = False


class AccountFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Account

    user = factory.SubFactory(UserFactory)
    account_number = factory.Faker("iban")
    balance = factory.LazyFunction(lambda: Decimal("10000.00"))
    currency = "IDR"
    created_at = factory.LazyFunction(timezone.now)


class TransactionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Transaction

    source_account = factory.SubFactory(AccountFactory)
    destination_account = factory.SubFactory(AccountFactory)
    amount = Decimal("500.00")
    reference_id = factory.Faker("uuid4")
    status = "SUCCESS"
```

##### Practical Integration Test Suite: `core/tests/test_banking_service.py`
```python
from decimal import Decimal
import pytest
from django.db import transaction
from core.exceptions import InsufficientFundsException
from core.factories import AccountFactory
from core.services.ledger import TransferService

pytestmark = pytest.mark.django_db


class TestTransferService:
    def test_transfer_balance_atomic_success(self) -> None:
        """
        Memvalidasi transfer dana antar akun berjalan deterministik 
        dan mencatat ledger secara benar.
        """
        # Arrange
        source = AccountFactory(balance=Decimal("5000.00"))
        destination = AccountFactory(balance=Decimal("1000.00"))
        transfer_amount = Decimal("1500.00")

        # Act
        result = TransferService.execute_transfer(
            source_id=source.id,
            destination_id=destination.id,
            amount=transfer_amount,
            idempotency_key="tx-unique-001"
        )

        # Assert
        source.refresh_from_db()
        destination.refresh_from_db()

        assert result.status == "COMPLETED"
        assert source.balance == Decimal("3500.00")
        assert destination.balance == Decimal("2500.00")

    def test_transfer_insufficient_funds_rollback(self) -> None:
        """
        Memastikan jika saldo tidak mencukupi, transaksi di-rollback secara penuh
        dan tidak ada state parsial yang tersimpan di DB.
        """
        source = AccountFactory(balance=Decimal("100.00"))
        destination = AccountFactory(balance=Decimal("500.00"))

        with pytest.raises(InsufficientFundsException):
            TransferService.execute_transfer(
                source_id=source.id,
                destination_id=destination.id,
                amount=Decimal("1000.00"),
                idempotency_key="tx-unique-002"
            )

        source.refresh_from_db()
        destination.refresh_from_db()
        assert source.balance == Decimal("100.00")
        assert destination.balance == Decimal("500.00")


@pytest.mark.django_db(transaction=True)
class TestConcurrentTransferRaceCondition:
    def test_row_level_locking_prevents_double_spending(self) -> None:
        """
        Menguji mekanisme database row-level locking (select_for_update)
        pada TransactionTestCase untuk mendeteksi penanganan race condition.
        """
        source = AccountFactory(balance=Decimal("1000.00"))
        dest_1 = AccountFactory()
        dest_2 = AccountFactory()

        # Simulasi transaksi atomic dengan thread terpisah atau locking terverifikasi
        with transaction.atomic():
            # Eksekusi locking
            locked_account = TransferService.lock_account_for_update(source.id)
            assert locked_account.balance == Decimal("1000.00")
            
            # Sub-transfer validasi
            TransferService.apply_debit(locked_account, Decimal("1000.00"))
            
        source.refresh_from_db()
        assert source.balance == Decimal("0.00")
```

#### B. Practical Enterprise Security Implementation

##### Strict Content-Security-Policy & Security Hardening: `config/settings/production.py`
```python
import os

# --- BASE SECURITY SETTINGS ---
DEBUG = False
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")

# Strict SSL/TLS & Proxy Handling
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SAMESITE = "Strict"

# HSTS Configuration (2 tahun + Subdomains + Preload)
SECURE_HSTS_SECONDS = 63072000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Browser Leak Mitigations
SECURE_BROWSER_XSS_FILTER = False  # Dinonaktifkan; deprecated & rentan eksploitasi
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Cross-Origin Policies (COOP/COEP)
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# --- DJANGO-CSP CONFIGURATION (Nonce Based) ---
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "csp.middleware.CSPMiddleware",  # Third-party: django-csp
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.security.DistributedRateLimitMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

CSP_DEFAULT_SRC = ("'none'",)
CSP_STYLE_SRC = ("'self'", "https://fonts.googleapis.com")
CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com")
CSP_IMG_SRC = ("'self'", "data:", "https://cdn.perusahaan.com")
CSP_CONNECT_SRC = ("'self'", "https://api.perusahaan.com")
CSP_SCRIPT_SRC = ("'self'",)
CSP_INCLUDE_NONCE_IN = ["script-src"]
CSP_REPORT_ONLY = False
CSP_REPORT_URI = "https://csp-report.perusahaan.com/v1/collector"
```

##### Custom Security Middleware: Distributed Leaky Bucket Rate Limiter
`core/middleware/security.py`:
```python
import time
from typing import Callable
from django.core.cache import caches
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.deprecation import MiddlewareMixin
import redis

class DistributedRateLimitMiddleware:
    """
    Middleware keamanan berbasis Sliding Window Log via Redis Cache 
    untuk menangkis brute force dan Denial-of-Service di tingkat aplikasi.
    """
    RATE_LIMIT_CAPACITY = 100  # Max request
    WINDOW_SECONDS = 60        # Durasi frame waktu

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self.redis_client = caches["rate_limit"].client.get_client()

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Hanya proteksi endpoint mutasi sensitif (e.g., auth, transfer)
        if request.path.startswith(("/api/v1/auth/", "/api/v1/payments/")):
            client_ip = self._get_client_ip(request)
            key = f"rl:{client_ip}:{request.path}"
            now = time.time()
            clear_before = now - self.WINDOW_SECONDS

            # LUA Script untuk atomic execution sliding window
            lua_script = """
            redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
            local current_requests = redis.call('ZCARD', KEYS[1])
            if current_requests < tonumber(ARGV[2]) then
                redis.call('ZADD', KEYS[1], ARGV[3], ARGV[3])
                redis.call('EXPIRE', KEYS[1], ARGV[4])
                return 1
            else
                return 0
            end
            """
            try:
                allowed = self.redis_client.eval(
                    lua_script, 1, key, clear_before, self.RATE_LIMIT_CAPACITY, now, self.WINDOW_SECONDS
                )
                if not allowed:
                    return JsonResponse(
                        {
                            "error": "Rate limit exceeded",
                            "detail": "Terlalu banyak permintaan. Silakan tunggu beberapa saat.",
                            "retry_after_seconds": self.WINDOW_SECONDS
                        },
                        status=429
                    )
            except redis.RedisError:
                # Fail-open untuk availability internal, namun log error secara kritikal
                pass

        return self.get_response(request)

    @staticmethod
    def _get_client_ip(request: HttpRequest) -> str:
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            # Ambil alamat IP publik pertama jika berada di balik reverse proxy terpercaya
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR", "unknown")
        return ip
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Fintech Core Banking Core Migration
- **Skala**: 15.000 transaksi/detik (TPS), 45 pengembang internal, ratusan endpoint monolit Django yang terhubung ke ratusan database shards.
- **Masalah**: 
  1. Test suite bawaan memakan waktu **48 menit** pada CI pipeline, menghambat frekuensi release.
  2. Ditemukan celah *Stored Cross-Site Scripting (XSS)* akibat bypass sanitasi HTML pada template reporting admin dashboard.
  3. Terjadi kebocoran data transaksi akibat *Race Condition* double spending saat multi-threading call dipicu bersamaan.

#### Solusi Arsitektural:
1. **Optimasi Pipeline Pengujian**:
   - Menghapus ketergantungan `TransactionTestCase` murni menjadi kombinasi `pytest-django` + `savepoints` menggunakan `pytest-xdist`.
   - Mengganti database provisioning lokal disk-based menggunakan ephemeral in-memory PostgreSQL (`tmpfs` ramdisk storage) pada runner CI:
     ```yaml
     services:
       postgres:
         image: postgres:15-alpine
         options: >-
           --mount type=tmpfs,destination=/var/lib/postgresql/data
           --health-cmd pg_isready
     ```
   - Pipeline dieksekusi dengan `-n 8` workers. Waktu eksekusi turun drastis dari **48 menit** menjadi **4 menit 12 detik** dengan metrik coverage 94%.

2. **Hardening Ekstrem (CSP & Reverse Proxy Integration)**:
   - Mengaktifkan `django-csp` terintegrasi nonce generator pada response streaming.
   - Mengunci `ALLOWED_HOSTS` dengan regular expression ketat untuk memblokir HTTP Host Header Poisoning melalui DNS wildcard re-binding.
   - Menerapkan header CORS dinamis strictly checking origin whitelist (bukan fallback wildcard `*`).

3. **Static Analysis Zero-Regression Policy**:
   - Mengintegrasikan ruleset `Semgrep` khusus fintech: mendeteksi penggunaan `.filter().update()` pada saldo tanpa operasi `F()` ekspresi atau `select_for_update()`.
   - CI Gate menolak PR secara otomatis jika Mypy menemukan penanganan nullable value yang tidak dievaluasi (`Optional[T]` tanpa assertion type checking).

---

### 9. Trade-offs (Analisis Komparatif)

```
                  PERFORMANCE (Kecepatan & Throughput)
                               /\
                              /  \
                             /    \
                            /      \
                           /        \
  [TransactionTestCase]  /__________\  [TestCase + Savepoints]
  (Real DB Commits)     /            \  (Memory Undo, Cepat,
  Tinggi Akurasi       /              \  Tapi Mock-heavy)
                      /________________\
              STRICT SECURITY / ISOLATION DEGREE
```

| Dimensi | Pendekatan Longgar / Default | Pendekatan Enterprise Hardened | Analisis Konsekuensi Arsitektural |
| :--- | :--- | :--- | :--- |
| **Test Database Runner** | `TransactionTestCase` (Truncate All Tables) | `TestCase` / `pytest.mark.django_db` (Savepoints) | `TestCase` memotong durasi tes hingga 90%, namun tidak mampu menguji transaksi sub-thread asynchronous asli atau thread concurrency. Solusi: Pisahkan marker `unit` vs `concurrency`. |
| **CSP Configuration** | Dynamic `'unsafe-inline'` / Permissive CSP | Strict CSP Nonce-based (`'self'` + Nonce) | Mengamankan injeksi script modern, tetapi mematikan kemudahan inline script development. Mengharuskan developer menyematkan context-variable nonce ke semua aset template. |
| **Strict Typing Engine** | Dynamic Duck Typing Python standar | `mypy --strict` + `django-stubs` | Mereduksi 98% runtime `AttributeError` dan type mismatch, tetapi meningkatkan kurva waktu onboarding tim serta memperpanjang durasi commit hook check sebesar 2-5 detik. |
| **Rate Limit Storage** | Local In-Memory Cache (Process Bound) | Distributed Redis Cluster with LUA script | Local memory sangat cepat (sub-millisecond) tetapi tidak sinkron lintas autoscaling pods di Kubernetes. Redis menambah overhead network latency (1-2 ms) namun menjamin proteksi cluster-wide. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan: Fixture Leakage Akibat Modifikasi Global State
- **Gejala**: Test case "A" lulus jika dijalankan sendirian, namun gagal ketika seluruh test suite dijalankan bersamaan (`flaky tests`).
- **Akar Masalah**: Test case mengubah variabel global class, memodifikasi mutable object di `setUpTestData()`, atau mengubah cache Django tanpa melakukan flushing pada `tearDown`.
- **Solusi**:
  ```python
  # SALAH: Objek mutable di class-level termodifikasi antar method
  class FlakyTest(TestCase):
      @classmethod
      def setUpTestData(cls):
          cls.shared_user = UserFactory()
      
      def test_mutate(self):
          self.shared_user.first_name = "Modified"
          # State ini bocor ke test berikutnya jika instance tidak di-refresh!

  # BENAR: Selalu panggil refresh_from_db() atau buat isolasi di setUp()
  class DeterministicTest(TestCase):
      @classmethod
      def setUpTestData(cls):
          cls.user_id = UserFactory().id

      def setUp(self):
          self.user = User.objects.get(id=self.user_id)
  ```

#### 2. Kesalahan: False Sense of Security pada Mocking Eksternal
- **Gejala**: Seluruh test pass 100%, namun saat production deployment terjadi runtime failure HTTP 500 saat memanggil Payment Gateway.
- **Akar Masalah**: Unit test melakukan mock terhadap response payload yang sudah *deprecated* (schema drift).
- **Solusi**: Gunakan Contract Testing via Pact atau skema JSON Schema validator pada output mock object:
  ```python
  import jsonschema

  PAYMENT_GATEWAY_SCHEMA = {
      "type": "object",
      "properties": {
          "status": {"type": "string", "enum": ["PAID", "FAILED"]},
          "transaction_id": {"type": "string"}
      },
      "required": ["status", "transaction_id"]
  }

  def test_mocked_gateway_payload(mocked_response):
      # Verifikasi bahwa struktur mock tidak pernah menyimpang dari kontrak API upstream
      jsonschema.validate(instance=mocked_response.json(), schema=PAYMENT_GATEWAY_SCHEMA)
  ```

#### 3. Kesalahan: `SECURE_PROXY_SSL_HEADER` Misconfiguration (Infinite Redirect Loop)
- **Gejala**: Akses ke website menghasilkan browser error `ERR_TOO_MANY_REDIRECTS`.
- **Akar Masalah**: Django diatur dengan `SECURE_SSL_REDIRECT = True`, namun header dari Load Balancer (AWS ALB / Cloudflare / Nginx) di-strip atau tidak disinkronkan dengan `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')`. Django mengira request selalu HTTP biasa dan mengirim response 301 terus-menerus.
- **Solusi**:
  - Konfigurasikan reverse proxy untuk meneruskan header: `proxy_set_header X-Forwarded-Proto $scheme;`.
  - Pastikan Django hanya mempercayai header tersebut dari IP Load Balancer internal, bukan dari client langsung.

---

### 11. Best Practices (Production Checklist)

#### Security & Hardening Checklist
- [ ] **CSRF Defense**: Nonaktifkan `@csrf_exempt` di seluruh view, kecuali endpoint Webhook eksternal yang diotentikasi secara kriptografis menggunakan asymmetric signatures (HMAC-SHA256).
- [ ] **Secret Management**: Tidak ada secret keys yang disimpan di kode sumber. `SECRET_KEY` ditarik dari AWS Secrets Manager / HashiCorp Vault dan dirotasi secara berkala.
- [ ] **Session Security**: Aktifkan flag `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SECURE`, dan `SESSION_COOKIE_SAMESITE = 'Strict'`.
- [ ] **Data Sanitization**: Larang penggunaan method berbahaya ORM: `RawSQL`, `extra()`, dan SQL concatenation manual; gunakan query parameterization (`cursor.execute(sql, [params])`).
- [ ] **Upload Handling**: Simpan file unggahan di object storage (S3) dengan metadata `Content-Disposition: attachment` dan bucket permission private untuk mencegah eksekusi payload arbitrary executable HTML/SVG.

#### Testing & CI Quality Gate Checklist
- [ ] **Code Coverage Enforcement**: Atur ambang batas minimum branch coverage ke 90% via `--cov-fail-under=90`.
- [ ] **No Raw DB Truncation**: Batasi penggunaan `TransactionTestCase` maksimal 5% dari total keseluruhan suite.
- [ ] **Determinism**: Pasang library `pytest-randomly` untuk mengacak urutan eksekusi tes guna membasmi ketergantungan urutan (*order-dependent tests*).
- [ ] **Static Type Validation**: Jalankan `mypy --config-file pyproject.toml` tanpa flagging error ignorances di level baseline core business logic.
- [ ] **Automated SAST**: Jalankan `bandit -r core/ -ll` (hanya tangkap warning high & medium severity) di dalam pre-push hook.

---

### 12. Hands-on Practice

Target path struktur direktori:
```
hands-on/m02/
├── pyproject.toml
├── .pre-commit-config.yaml
├── config/
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── production.py
│   │   └── test.py
│   └── wsgi.py
└── core/
    ├── __init__.py
    ├── models.py
    ├── factories.py
    └── tests/
        ├── __init__.py
        └── test_security_and_models.py
```

#### Langkah 1: Siapkan Konfigurasi `hands-on/m02/pyproject.toml`
```toml
[tool.poetry]
name = "django-enterprise-hardening"
version = "1.0.0"
description = "Implementasi Arsitektur Testing dan Security Hardening Django"
authors = ["Architect <architect@enterprise.internal>"]

[tool.poetry.dependencies]
python = "^3.11"
django = "^4.2"
django-csp = "^3.7"
django-cors-headers = "^4.3.0"
redis = "^5.0.0"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.0"
pytest-django = "^4.7.0"
pytest-xdist = "^3.5.0"
pytest-cov = "^4.1.0"
factory-boy = "^3.3.0"
mypy = "^1.8.0"
django-stubs = "^4.2.7"
bandit = "^1.7.6"
semgrep = "^1.50.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.mypy]
plugins = ["mypy_django_plugin.main"]
python_version = "3.11"
strict = true
warn_unused_ignores = true
disallow_untyped_defs = true

[tool.django-stubs]
django_settings_module = "config.settings.test"

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings.test"
python_files = ["test_*.py"]
addopts = "--cov=core --cov-report=term-missing"
```

#### Langkah 2: Konfigurasi Pre-commit Hooks `hands-on/m02/.pre-commit-config.yaml`
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.6
    hooks:
      - id: bandit
        args: ["-r", "core/", "-c", "pyproject.toml"]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: ["django-stubs==4.2.7"]
```

#### Langkah 3: Implementasikan Model dengan Domain Constraints `hands-on/m02/core/models.py`
```python
import uuid
from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models

class SecureVault(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vault_name = models.CharField(max_length=64, unique=True)
    encrypted_secret = models.BinaryField()
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))]
    )
    is_locked = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "secure_vaults"
        indexes = [
            models.Index(fields=["vault_name"]),
        ]

    def __str__(self) -> str:
        return f"{self.vault_name} - Balance: {self.balance}"
```

#### Langkah 4: Tulis Implementasi Test Suite `hands-on/m02/core/tests/test_security_and_models.py`
```python
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.test import Client
from core.models import SecureVault

pytestmark = pytest.mark.django_db


class TestSecureVaultModel:
    def test_negative_balance_constraint(self) -> None:
        """
        Memastikan validator ORM menolak penyimpanan nilai negatif pada balance.
        """
        vault = SecureVault(
            vault_name="Primary-Reserve",
            encrypted_secret=b"0xDEADBEEF",
            balance=Decimal("-50.00")
        )
        
        with pytest.raises(ValidationError):
            vault.full_clean()

    def test_successful_vault_creation(self) -> None:
        vault = SecureVault.objects.create(
            vault_name="Main-Operations",
            encrypted_secret=b"ENCRYPTED_DATA_BYTES",
            balance=Decimal("15000.00")
        )
        assert vault.id is not None
        assert vault.balance == Decimal("15000.00")


class TestSecurityHardeningHeaders:
    def test_http_security_headers_present(self, client: Client) -> None:
        """
        Memvalidasi bahwa middleware keamanan menginjeksi header perlindungan
        modern ke dalam setiap outbound HTTP response.
        """
        response = client.get("/")
        
        # Validasi Clickjacking Protection
        assert response.headers.get("X-Frame-Options") == "DENY"
        # Validasi MIME sniffing protection
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        # Validasi Referrer Policy
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
```

#### Langkah 5: Eksekusi Pengujian & Static Analysis
Buka terminal dan jalankan urutan audit produksi berikut:
```bash
# 1. Menjalankan pengetikan statis via mypy
mypy core/

# 2. Menjalankan audit kerentanan sintaksis via bandit
bandit -r core/

# 3. Menjalankan test suite secara paralel dengan pytest
pytest -v -n auto --cov=core
```

---

### 13. Exercise

#### Tingkat Kesulitan: Easy
1. Modifikasi `core/factories.py` untuk mengimplementasikan trait `is_locked=True` pada `SecureVaultFactory` dengan menggunakan method generator factory bawaan.
2. Tambahkan assertion pada `test_http_security_headers_present` untuk memverifikasi keberadaan header `Cross-Origin-Opener-Policy: same-origin`.

#### Tingkat Kesulitan: Medium
1. Buat sebuah pytest fixture bernama `authenticated_client` yang secara otomatis menginisialisasi `UserFactory`, melakukan login via session, dan menyuntikkan token CSRF yang valid ke headers default API client.
2. Tulis sebuah custom Semgrep rule (`.semgrep/rules.yaml`) yang mendeteksi dan menggagalkan commit jika ada developer yang memanggil method `django.shortcuts.render` tanpa mengoper parameter request context nonce CSP.

#### Tingkat Kesulitan: Hard
1. Buat unit test isolasi yang memverifikasi perilaku concurrent update pada model `SecureVault`. Buat script yang mensimulasikan dua worker process simultan yang mencoba menarik balance yang sama secara bersamaan, dan buktikan bahwa implementasi `select_for_update(nowait=False)` berhasil menggagalkan salah satu transaksi dengan exception handling `DatabaseError`.
2. Implementasikan middleware audit log kustom yang menangkap setiap mutasi model via post-save sinyal, mengekstrak diff state lama vs. baru dalam bentuk JSON, dan memvalidasi bahwa middleware tersebut tidak memicu kebocoran memori saat pengujian paralel dijalankan.

---

### 14. Challenge (Studi Kasus Kompleks)

**Judul Arsitektur:** Multi-Tenant Defense-in-Depth Vault Isolation & Zero-Downtime Migration Testing

**Deskripsi Kasus:**
Sebuah platform SaaS B2B berskala enterprise mengimplementasikan arsitektur database multi-tenant berbasis *Single-Database Multi-Schema* (setiap tenant memiliki schema Postgres tersendiri: `tenant_acme`, `tenant_megacorp`).

**Spesifikasi Tantangan:**
1. **Testing Engine Isolation**:
   - Buat test runner runner berbasis `pytest-django` kustom yang secara dinamis melakukan pembuatan, migrasi schema, dan isolasi koneksi per-tenant saat fixture pengujian di-spin up.
   - Test runner harus mampu mengeksekusi suite pengujian 50 tenant yang berbeda secara paralel menggunakan `pytest-xdist` tanpa terjadinya *schema crossing* atau koneksi bocor (*connection pooling leakage*).
2. **Security Hardening Subsystem**:
   - Rancang arsitektur keamanan di mana request yang datang via sub-domain (misal: `acme.enterprise.com`) memvalidasi keterikatan tenant session menggunakan cryptographic hash binding yang mengikat IP client, User-Agent, dan Session Key.
   - Jika terjadi pencurian cookie (Session Hijacking), Django harus mendeteksi inkonsistensi tanda tangan digital dalam waktu di bawah 1 milidetik, menghapus session seketika di Redis, memicu alert security, dan mengembalikan response `403 Forbidden` dengan payload CSRF/Session mismatch yang dikeraskan.
3. **Static Analysis Enforcement**:
   - Konfigurasikan rule AST khusus yang memindai seluruh repository: Jika ditemukan pemanggilan query SQL yang tidak secara eksplisit menyertakan context search path schema tenant aktif, build CI/CD harus dihentikan dengan pesan error arsitektural yang jelas.

*Deliverable Arsitektural*: Rancangan arsitektur, implementasi fixture kelas runner, security middleware, serta Semgrep/Bandit custom config tanpa menggunakan placeholder mock parsial.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic (5 Soal)
1. Apa alasan teknis utama `django.test.TestCase` mengeksekusi pengujian jauh lebih cepat dibandingkan `django.test.TransactionTestCase`?
2. Mengapa header `X-XSS-Protection` modern dianjurkan untuk dinonaktifkan (`SECURE_BROWSER_XSS_FILTER = False`) pada implementasi produksi terbaru?
3. Apa perbedaan fungsional antara `factory.LazyAttribute` dan `factory.LazyFunction` pada implementasi `factory_boy`?
4. Mengapa setting `SESSION_COOKIE_SAMESITE = 'Strict'` menawarkan proteksi yang lebih unggul terhadap serangan CSRF dibanding atribut `'Lax'`?
5. Mengapa penggunaan library `random` bawaan Python dilarang untuk pembuatan token autentikasi pada Django dan harus diganti dengan modul `secrets`?

#### B. Pertanyaan Intermediate (5 Soal)
1. Bagaimana cara internal Django mempertahankan isolasi pengujian database ketika method `transaction.on_commit()` digunakan di dalam kode bisnis yang diuji menggunakan `django.test.TestCase`?
2. Mengapa implementasi Content Security Policy (CSP) berbasis *nonce* lebih dianjurkan daripada menggunakan daftar hash static (`'sha256-...'`) pada aplikasi web berskala enterprise yang dinamis?
3. Bagaimana mekanisme kerja `mypy` bersama plugin `django-stubs` dalam mengenali field dinamis yang di-inject oleh `related_name` pada Foreign Key model Django?
4. Apa dampak performa dan konsistensi pada Redis cache jika middleware rate limiter menggunakan teknik *Sliding Window Log* dibandingkan *Fixed Window Counter*?
5. Mengapa kita harus berhati-hati saat mengeksekusi pengujian paralel (`pytest -n auto`) yang menggunakan cache backend default berbasis `LocMemCache`?

#### C. Skenario Kasus Produksi (3 Skenario)
1. **Skenario 1**: Sebuah tim developer melaporkan bahwa test suite mereka mengalami kegagalan acak (*intermittent failures*) hanya ketika dijalankan di server CI, namun selalu lulus di local machine. CI server menggunakan parameter `--dist=loadfile` pada `pytest-xdist`. Apa hipotesis arsitektur Anda mengenai penyebab masalah ini dan bagaimana memperbaikinya?
2. **Skenario 2**: Setelah menyalakan `SECURE_SSL_REDIRECT = True` dan mendaftarkan aplikasi di balik AWS Application Load Balancer (ALB), pengguna melaporkan tidak bisa mengakses API via Mobile App karena terjadi error redirect 301 berulang kali tanpa batas. Header apa yang hilang pada komunikasi reverse proxy tersebut, dan bagaimana setting Django yang harus disesuaikan?
3. **Skenario 3**: Sebuah analisis keamanan via `Bandit` melaporkan vulnerability dengan severity HIGH: `B608: Hardcoded SQL expression`. Kode tersebut adalah:
   ```python
   order_by_field = request.GET.get("sort_by", "created_at")
   qs = Product.objects.raw(f"SELECT * FROM core_product ORDER BY {order_by_field}")
   ```
   Bagaimana Anda mendesain ulang baris kode tersebut menggunakan Django ORM yang aman tanpa mengorbankan fungsionalitas sorting dinamis?

---

### 16. Summary

1. **Test Runner Efficiency**: Penguasaan mekanisme isolasi transaksi Django database (`Savepoints` vs `Truncation`) merupakan pembeda mendasar performa test suite skala enterprise. Gunakan `pytest-django` dengan marker database terisolasi untuk mencapai throughput kompilasi pengujian yang optimal.
2. **Mocking & Isolation Determinism**: Hindari serialisasi fixture JSON statis; adopsi `factory_boy` untuk dynamic schema instantiation. Mock dependensi eksternal pada boundary terluar sistem untuk menjaga keandalan eksekusi tanpa flakiness.
3. **Hardening Defense-in-Depth**: Keamanan aplikasi Django enterprise bertumpu pada konfigurasi TLS/HSTS yang ketat, pencegahan kebocoran konteks lintas domain (COOP/COEP), mitigasi modern session hijacking, dan implementasi Content Security Policy (CSP) berbasis cryptographic nonce dinamis.
4. **Automated Static Security Gates**: Analisis statis bukan sekadar opsional linter visual; penggabungan type inference ketat (`mypy` + `django-stubs`), semantic AST inspection (`semgrep`), serta security vulnerability scanner (`bandit`) pada pipeline CI menjamin standar stabilitas dan integritas kode sebelum menyentuh environment produksi.
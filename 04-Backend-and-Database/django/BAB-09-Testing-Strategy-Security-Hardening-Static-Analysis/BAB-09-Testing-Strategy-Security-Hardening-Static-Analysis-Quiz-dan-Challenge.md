# BAB-09-Testing-Strategy-Security-Hardening-Static-Analysis: Quiz, Challenge, & Knowledge Check

Dokumen evaluasi mandiri ini dirancang untuk menguji penguasaan konsep, metodologi arsitektural, dan implementasi praktis seputar pengujian piranti lunak (*unit*, *integration*, *mocking*), pengerasan keamanan sistem (*security hardening*), dan analisis statis kode (*static code analysis*) pada ekosistem Django tingkat lanjut.

---

## Bagian 1: 5 Basic Questions

### Pertanyaan 1: Perbedaan Fundamental `TestCase`, `TransactionTestCase`, dan `SimpleTestCase`
Jelaskan perbedaan mekanisme eksekusi database dan siklus isolasi transaksi antara `django.test.SimpleTestCase`, `django.test.TestCase`, dan `django.test.TransactionTestCase`. Kapan masing-masing kelas pengujian tersebut harus digunakan?

<details>
<summary>Jawaban & Pembahasan Teknis</summary>

* **`SimpleTestCase`**:
  * **Mekanisme**: Tidak mengizinkan interaksi database sama sekali. Jika ada query ORM yang dieksekusi, Django akan memicu error `DatabaseQueriesBlockedError`.
  * **Use Case**: Pengujian unit murni yang independen dari database, seperti form validation logic, utility functions, custom template tags, custom serializer validation tanpa query DB, atau custom middleware logika murni.
* **`TestCase`**:
  * **Mekanisme**: Membungkus setiap metode pengujian (`test_*`) di dalam blok transaksi atomik tingkat basis data (`SAVEPOINT` / `atomic`). Saat pengujian selesai, dilakukan `ROLLBACK` ke titik awal tanpa melakukan truncating atau flushing tabel.
  * **Use Case**: Standar pengujian integrasi Django sehari-hari karena eksekusinya sangat cepat (*performance-efficient*) dan menjamin isolasi data antar-tes.
* **`TransactionTestCase`**:
  * **Mekanisme**: Mereset database dengan cara melakukan `TRUNCATE` atau `FLUSH` terhadap semua tabel setelah pengujian selesai dijalankan, bukan via `ROLLBACK`.
  * **Use Case**: Wajib digunakan ketika menguji kode yang bergantung langsung pada commit transaksi nyata (misalnya pengujian `transaction.on_commit()`, verifikasi level isolasi database `SELECT FOR UPDATE`, atau pengujian *concurrency multi-threading* di mana worker terpisah harus membaca baris yang sudah di-commit). Kelemahannya adalah eksekusi jauh lebih lambat dibanding `TestCase`.
</details>

---

### Pertanyaan 2: Evaluasi Keamanan Perintah `python manage.py check --deploy`
Apa fungsi dari flag `--deploy` pada perintah audit Django bawaan `manage.py check`, dan sebutkan minimal 4 setting keamanan kritikal di `settings.py` yang divalidasi oleh command ini sebelum rilis ke production!

<details>
<summary>Jawaban & Pembahasan Teknis</summary>

Flag `--deploy` mengaktifkan sekumpulan *security deployment checks* bawaan (`django.core.checks.security`) untuk memvalidasi konfigurasi aplikasi terhadap celah keamanan operasional production. 

Empat setting kritikal yang divalidasi meliputi:
1. `DEBUG = False`: Memastikan stack trace, environment variables, dan query SQL tidak bocor ke publik saat terjadi unhandled 500 error.
2. `SECURE_SSL_REDIRECT = True`: Memaksa semua request HTTP dialihkan ke koneksi HTTPS terenkripsi.
3. `SESSION_COOKIE_SECURE = True` & `CSRF_COOKIE_SECURE = True`: Memastikan browser hanya mengirimkan cookie session dan token CSRF melalui channel HTTPS dengan flag `Secure`.
4. `SECURE_HSTS_SECONDS`: Menginstruksikan browser melalui header `Strict-Transport-Security` agar selalu terhubung via HTTPS selama durasi waktu tertentu guna memitigasi serangan *SSL-stripping Man-in-the-Middle (MitM)*.
</details>

---

### Pertanyaan 3: Peran AST Security Scanner (Bandit) dalam Pipeline Python
Apa itu Bandit, bagaimana cara kerjanya mendeteksi celah keamanan pada kode Python, dan berikan contoh temuan kode yang langsung memicu status *High Severity / Confidence* pada Bandit!

<details>
<summary>Jawaban & Pembahasan Teknis</summary>

* **Cara Kerja**: Bandit adalah tool Static Application Security Testing (SAST) khusus Python. Bandit membaca kode sumber, mem-parsing-nya menjadi Abstract Syntax Tree (AST), lalu menjalankan modul plugin pengujian pada setiap AST node untuk mendeteksi pola celah keamanan tanpa mengeksekusi kode (*non-runtime analysis*).
* **Contoh Temuan Kritis**:
  * Penggunaan modul desentralisasi tidak aman seperti `pickle.loads()` (berisiko *Arbitrary Remote Code Execution*).
  * Pemanggilan shell injection rentan melalui `subprocess.Popen(..., shell=True)` atau `os.system()`.
  * Penggunaan fungsi hashing lemah untuk kredensial seperti `hashlib.md5()` atau `hashlib.sha1()`.
  * Penggunaan hardcoded credential, secret key, atau API token di dalam script.
  * SQL injection melalui query raw concatenation seperti `cursor.execute(f"SELECT * FROM users WHERE id = {user_input}")`.
</details>

---

### Pertanyaan 4: Mengapa Menggunakan `factory-boy` Lebih Baik daripada Django Fixtures (`.json`/`.yaml`)?
Dalam arsitektur test suite skala besar, mengapa Django Fixtures berbasis JSON/YAML dianggap sebagai *anti-pattern*, dan apa keunggulan penggunaan `factory_boy`?

<details>
<summary>Jawaban & Pembahasan Teknis</summary>

* **Kelemahan Django JSON/YAML Fixtures**:
  * **Brittle & High Maintenance**: Skema database yang berubah (penambahan kolom `NOT NULL`, foreign key baru, relasi Many-to-Many) akan merusak seluruh file fixture manual.
  * **Hardcoded ID Conflicts**: Pembuatan primary key hardcoded kerap memicu tabrakan data (*integrity constraint violation*).
  * **Slow I/O**: Membaca file disk dan deserialisasi JSON secara masif memperlambat suite pengujian.
* **Keunggulan `factory-boy`**:
  * **Dynamic & Declarative**: Mendefinisikan blueprint objek model secara dinamis menggunakan Python code murni.
  * **Faker Integration**: Mengintegrasikan `Faker` untuk menghasilkan data acak realistis (`email`, `uuid`, `address`).
  * **Relationship Handling**: Mendukung pembuatan relasi otomatis (`SubFactory`, `RelatedFactory`, `post_generation`).
  * **Lazy Attributes & Sequences**: Menyediakan ID atau username sekuensial yang unik secara otomatis (`Sequence(lambda n: f"user_{n}@example.com")`).
</details>

---

### Pertanyaan 5: Manfaat dan Konfigurasi `django-stubs` pada `mypy`
Mengapa `mypy` standar tidak dapat memahami Model, Manager, dan QuerySet Django secara *out-of-the-box*, dan solusi apa yang disediakan oleh `django-stubs`?

<details>
<summary>Jawaban & Pembahasan Teknis</summary>

* **Masalah**: Django banyak memanfaatkan metaprogramming dinamis (`ModelBase`, *metaclass magic*) saat menginisialisasi field, relasi reverse foreign key (`_set`), dan query method chaining. `mypy` secara default menganggap atribut dinamis ini tidak ada atau bertipe `Any`, sehingga memunculkan ribuan false positive atau kehilangan tipe statis yang ketat.
* **Solusi**: `django-stubs` menyediakan tipe stub (`.pyi`) resmi dan plugin compiler khusus untuk `mypy` yang mampu menginterpretasikan struktur model, generic QuerySet, parameter form, dan typing ORM Django secara presisi sesuai context `settings.py`.
</details>

---

## Bagian 2: 5 Intermediate Questions

### Pertanyaan 6: Mitigasi Insecure Direct Object References (IDOR) & Query Injection pada Raw SQL
Perhatikan cuplikan method Django view berikut:
```python
def get_user_invoice(request, invoice_id):
    query = f"SELECT * FROM billing_invoice WHERE id = '{invoice_id}' AND is_deleted = false"
    with connection.cursor() as cursor:
        cursor.execute(query)
        row = cursor.fetchone()
    return JsonResponse({"data": row})
```
Sebutkan dua kerentanan keamanan utama pada kode di atas dan tuliskan refactoring idiomatis Django ORM yang aman!

<details>
<summary>Jawaban & Pembahasan Teknis</summary>

* **Kerentanan Keamanan**:
  1. **SQL Injection (SQLi)**: Penggunaan Python f-string untuk merangkai string SQL mentah memungkinkan penyerang menyuntikkan payload (misal: `' OR '1'='1`). Parameter binding tidak digunakan.
  2. **Insecure Direct Object References (IDOR)**: Endpoint tidak memverifikasi apakah `invoice_id` tersebut dimiliki oleh user yang sedang login (`request.user`), sehingga user sembarang dapat membaca invoice milik pengguna lain.
* **Refactoring Aman Menggunakan Django ORM**:
```python
from django.http import JsonResponse, Http404
from django.contrib.auth.decorators import login_required
from .models import Invoice

@login_required
def get_user_invoice(request, invoice_id):
    # Enforce object-level access control & parameter binding via ORM
    try:
        invoice = Invoice.objects.filter(
            id=invoice_id,
            user=request.user,
            is_deleted=False
        ).values("id", "amount", "status", "created_at").get()
    except Invoice.DoesNotExist:
        raise Http404("Invoice tidak ditemukan atau Anda tidak memiliki akses.")

    return JsonResponse({"data": invoice})
```
</details>

---

### Pertanyaan 7: Perbedaan `mock.patch` vs `responses` vs `pytest-mock` dalam Pengujian Integrasi API Eksternal
Kapan kita harus menggunakan `unittest.mock.patch`, library `responses`, atau `pytest-mock` (`mocker`) saat menguji modul Django yang memanggil REST API pihak ketiga (misalnya gateway pembayaran Midtrans/Stripe)? Apa bahaya *over-mocking*?

<details>
<summary>Jawaban & Pembahasan Teknis</summary>

* **`unittest.mock.patch` & `pytest-mock` (`mocker`)**:
  * Bekerja di tingkat runtime Python function/method interception (misal: mem-patch fungsi `requests.post` atau method class payment service).
  * Rentan terhadap perubahan internal interface jika kode service di-refactor.
* **`responses`**:
  * Bekerja pada layer soket transport HTTP adapter library `requests`. Kode aplikasi tetap memanggil library `requests` secara riil, namun paket jaringan di-intercept sebelum keluar ke network.
  * Jauh lebih superior untuk menguji third-party REST client karena memvalidasi URL endpoint, HTTP verb, query params, headers, dan status code secara realistis.
* **Bahaya Over-Mocking**:
  * Terjadi *tautological tests* (tes hanya menguji apakah mock dipanggil, bukan apakah logika bisnis bekerja).
  * False positive: Tes berhasil lulus padahal signature API eksternal telah berubah atau payload JSON salah format.

</details>

---

### Pertanyaan 8: Strategi Content Security Policy (CSP) dan Sanitasi XSS di Template Django
Bagaimana Django menangani auto-escaping konteks HTML, kapan kerentanan Cross-Site Scripting (XSS) tetap dapat terjadi di Django template, dan bagaimana peranan header `Content-Security-Policy` via `django-csp`?

<details>
<summary>Jawaban & Pembahasan Teknis</summary>

* **Auto-Escaping Django**:
  * Mesin template Django otomatis meng-escape karakter `<, >, &, ', "` menjadi entity HTML (misal `<script>` diubah menjadi `&lt;script&gt;`).
* **Celah XSS yang Kerap Lolos**:
  1. Penggunaan filter `|safe` atau tag `{% autoescape off %}` pada input yang berasal dari user yang tidak disanitasi menggunakan library semacam `bleach` / `nh3`.
  2. Injeksi konteks atribut JavaScript: `<a href="{{ user_provided_url }}">` dapat dieksploitasi dengan payload `javascript:alert(1)`.
  3. Konteks inline script JSON: `<script>var config = {{ user_json|safe }};</script>` (dapat ditutup paksa dengan `</script><script>...`). Solusi yang benar: `{{ user_json|json_script:"config-data" }}`.
* **Peran `django-csp`**:
  * Mengirimkan HTTP header `Content-Security-Policy`. Membatasi domain asal eksekusi script (`script-src 'self' https://trusted.cdn.com`), melarang inline scripts tanpa nonce (`script-src 'nonce-...'`), dan mematikan fungsi berbahaya seperti `eval()`.
</details>

---

### Pertanyaan 9: Isolasi Cache dan Background Task (Celery) pada Test Suite
Bagaimana cara mengisolasi Redis Cache dan Celery asynchronous task saat menjalankan test suite Django agar tidak mencemari infrastruktur nyata dan tidak menimbulkan *flaky tests*?

<details>
<summary>Jawaban & Pembahasan Teknis</summary>

1. **Isolasi Cache**:
   * Gunakan `LocMemCache` atau `DummyCache` di environment testing (`settings_test.py`):
     ```python
     CACHES = {
         "default": {
             "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
             "LOCATION": "unique-snowflake-testing",
         }
     }
     ```
   * Manfaatkan helper method `cache.clear()` pada teardown pengujian jika diperlukan.
2. **Isolasi Celery Task**:
   * Aktifkan setting `CELERY_TASK_ALWAYS_EAGER = True` dan `CELERY_TASK_EAGER_PROPAGATES = True`. Dengan setting ini, task Celery dieksekusi secara sinkron (*blocking*) di proses yang sama dengan test runner.
   * Alternatifnya, gunakan mock/spy pada method `.delay()` atau `.apply_async()` untuk memverifikasi payload task tanpa mengeksekusi worker logic ketika menguji controller layer.
</details>

---

### Pertanyaan 10: Analisis Dependensi Rentan dengan `pip-audit` / `safety`
Bagaimana mengintegrasikan audit keamanan supply-chain ke dalam CI/CD pipeline Django dan bagaimana menangani status *known vulnerabilities* pada paket transitive dependency?

<details>
<summary>Jawaban & Pembahasan Teknis</summary>

* **Integrasi CI/CD Pipeline**:
  * Jalankan `pip-audit` secara terjadwal atau pada setiap pull request:
    ```bash
    pip-audit -r requirements/production.txt --desc on --strict
    ```
  * `pip-audit` memeriksa hash dan versi pustaka terhadap database kerentanan PyPA Advisory Database dan OSV (Open Source Vulnerabilities).
* **Penanganan Transitive Dependency**:
  1. Identifikasi dependency tree dengan `pipdeptree -p <nama_paket>`.
  2. Naikkan versi direct dependency induk yang memanggil sub-dependency rentan tersebut.
  3. Jika dependensi induk belum merilis patch, kunci sub-dependency tersebut pada versi aman di `requirements.txt` atau gunakan mekanisme *constraint file* (`pip install -c constraints.txt`).
  4. Bila tidak tersedia patch, lakukan audit manual apakah endpoint/fitur rentan dari pustaka tersebut benar-benar terekspos di aplikasi, kemudian gunakan file ignore/whitelist disertai dokumentasi mitigasi resmi (*accepted risk* dengan expiry date).
</details>

---

## Bagian 3: 3 Skenario Kasus Nyata Produksi

### Skenario 1: Flaky Integration Test Akibat Transaction Rollback & Celery `transaction.on_commit`
* **Kasus**:
  Tim backend membuat fitur pendaftaran pengguna yang mengirimkan email verifikasi asynchronously setelah transaksi database tersimpan rapi:
  ```python
  # services.py
  from django.db import transaction
  from .models import User
  from .tasks import send_verification_email_task

  def register_user(email, password):
      with transaction.atomic():
          user = User.objects.create_user(email=email, password=password)
          transaction.on_commit(lambda: send_verification_email_task.delay(user.id))
      return user
  ```
  Ketika tim menjalankan unit test menggunakan standar `django.test.TestCase`:
  ```python
  class UserRegistrationTest(TestCase):
      @patch("services.send_verification_email_task.delay")
      def test_registration_triggers_email(self, mock_task):
          user = register_user("test@example.com", "Secret123!")
          mock_task.assert_called_once_with(user.id)
  ```
  Test runner selalu menghasilkan assertion failure: `AssertionError: Expected 'delay' to be called once. Called 0 times.`

* **Analisis Akar Masalah**:
  Kelas `TestCase` membungkus seluruh body pengujian ke dalam satu transaksi besar yang **tidak pernah di-commit secara fisik**, melainkan di-rollback saat test selesai. Akibatnya, callback di dalam `transaction.on_commit(...)` tidak pernah dieksekusi oleh Django test runner.

* **Solusi Perbaikan**:
  1. Ubah basis kelas test menjadi `TransactionTestCase` jika ingin menguji siklus commit riil:
     ```python
     class UserRegistrationTest(TransactionTestCase):
         @patch("services.send_verification_email_task.delay")
         def test_registration_triggers_email(self, mock_task):
             user = register_user("test@example.com", "Secret123!")
             mock_task.assert_called_once_with(user.id)
     ```
  2. Atau gunakan context manager `captureOnCommitCallbacks` bawaan Django (tersedia sejak Django 3.2+) agar tetap dapat berjalan cepat di dalam `TestCase`:
     ```python
     class UserRegistrationFastTest(TestCase):
         @patch("services.send_verification_email_task.delay")
         def test_registration_triggers_email(self, mock_task):
             with self.captureOnCommitCallbacks(execute=True):
                 user = register_user("test@example.com", "Secret123!")
             mock_task.assert_called_once_with(user.id)
     ```

---

### Skenario 2: Kebocoran Data Multi-Tenant Akibat N+1 Testing Blindspot & Kurangnya Assertions
* **Kasus**:
  Pada aplikasi Multi-Tenant SaaS, setiap tenant memiliki data `Order`. Pengembang membuat endpoint listing:
  ```python
  # views.py
  class OrderListView(generics.ListAPIView):
      serializer_class = OrderSerializer
      permission_classes = [IsAuthenticated]

      def get_queryset(self):
          # BUG: Lupa memfilter tenant dari request.user
          return Order.objects.all()
  ```
  Pengujian yang dibuat sebelumnya lolos 100% (*green*) karena di test suite hanya ada 1 tenant yang dibuat di fixture:
  ```python
  def test_list_orders(client, user):
      client.force_login(user)
      response = client.get("/api/v1/orders/")
      assert response.status_code == 200
      assert len(response.data) == 1
  ```
  Di production, Tenant B dapat melihat seluruh data riwayat pesanan milik Tenant A.

* **Analisis Akar Masalah**:
  * Test case menderita cacat desain *Boundary Isolation Blindspot*: data pengujian hanya berisi data milik entitas penguji sendiri.
  * Tidak ada pengujian berbasis skenario multi-tenant yang memverifikasi isolasi silang (*cross-tenant leakage*).

* **Solusi Perbaikan**:
  Buat test suite yang menginisialisasi minimal dua tenant terpisah dan verifikasi bahwa data tenant lain tidak pernah bocor:
  ```python
  import pytest
  from rest_framework import status

  @pytest.mark.django_db
  def test_cross_tenant_data_isolation(api_client, tenant_factory, user_factory, order_factory):
      # Arrange: Dua tenant terpisah dengan datanya masing-masing
      tenant_a = tenant_factory(name="Company A")
      user_a = user_factory(tenant=tenant_a)
      order_a = order_factory(tenant=tenant_a, total_amount=100_000)

      tenant_b = tenant_factory(name="Company B")
      user_b = user_factory(tenant=tenant_b)
      order_b = order_factory(tenant=tenant_b, total_amount=500_000)

      # Act: Login sebagai user dari Tenant A
      api_client.force_authenticate(user=user_a)
      response = api_client.get("/api/v1/orders/")

      # Assert: Verifikasi strictly hanya data Tenant A yang kembali
      assert response.status_code == status.HTTP_200_OK
      returned_order_ids = [item["id"] for item in response.data["results"]]
      
      assert order_a.id in returned_order_ids
      assert order_b.id not in returned_order_ids, "CRITICAL: Kebocoran data antar-tenant terdeteksi!"
  ```

---

### Skenario 3: Penetrasi Host Header Injection Akibat Kesalahan Konfigurasi `ALLOWED_HOSTS`
* **Kasus**:
  Sebuah startup e-commerce mengonfigurasi setting berikut untuk mempermudah testing di staging:
  ```python
  # settings.py
  ALLOWED_HOSTS = ["*"]
  ```
  Aplikasi memiliki fitur reset password yang menghasilkan link reset menggunakan `request.build_absolute_uri()`:
  ```python
  def send_password_reset(request, user):
      token = generate_reset_token(user)
      reset_url = request.build_absolute_uri(f"/reset-password/?token={token}")
      send_email(user.email, f"Klik link untuk reset password: {reset_url}")
  ```
  Seorang peretas mengirimkan HTTP request ke server dengan memanipulasi header:
  ```http
  POST /api/password-reset/ HTTP/1.1
  Host: evil-attacker-server.com
  Content-Type: application/json

  {"email": "victim@company.com"}
  ```
  Korban menerima email resmi yang tautannya mengarah ke `https://evil-attacker-server.com/reset-password/?token=...`. Begitu korban mengklik link tersebut, token reset dicuri oleh attacker.

* **Analisis Akar Masalah**:
  * Penggunaan wildcard `ALLOWED_HOSTS = ["*"]` di production mematikan proteksi Host Header Validation Django.
  * Pemanggilan `request.build_absolute_uri()` secara implisit membaca isi header `Host` dari request mentah.

* **Solusi Perbaikan**:
  1. Kunci `ALLOWED_HOSTS` secara ketat ke domain resmi:
     ```python
     ALLOWED_HOSTS = [
         "api.company.com",
         "dashboard.company.com",
     ]
     ```
  2. Jangan mengandalkan `Host` header dinamis untuk pembuatan tautan kritikal yang berurusan dengan kredensial/token autentikasi. Tentukan domain dasar dari environment settings yang terpercaya:
     ```python
     from django.conf import settings
     from urllib.parse import urljoin

     def send_password_reset(user):
         token = generate_reset_token(user)
         reset_url = urljoin(settings.FRONTEND_BASE_URL, f"/reset-password/?token={token}")
         send_email(user.email, f"Klik link untuk reset password: {reset_url}")
     ```
  3. Buat security test otomatis untuk memastikan manipulasi Host header memicu respon HTTP 400 Bad Request:
     ```python
     def test_suspicious_host_header_blocked(client):
         response = client.get("/api/health/", HTTP_HOST="evil-attacker-server.com")
         assert response.status_code == 400
     ```

---

## Bagian 4: Practical Chapter Challenge

### Tantangan Praktis: Membangun CI/CD Quality Gate & Hardening Script

Anda diminta mengonfigurasi arsitektur proteksi mutu dan keamanan menyeluruh pada proyek Django. Lengkapi spesifikasi berikut:

#### 1. Spesifikasi Tooling & Standard
Konfigurasikan pipeline yang menjalankan 4 tahap gatekeeper otomatis:
1. **Linter & Formatter**: `ruff` (mencakup rules `E`, `F`, `B`, `S`).
2. **Type Checking**: `mypy` dengan plugin `django-stubs`.
3. **Security AST Scanner**: `bandit` mengecualikan folder `tests/`.
4. **Test Suite**: `pytest` dengan coverage threshold minimal 85% menggunakan `pytest-cov`.

#### 2. Implementasi File Konfigurasi

**File 1: `pyproject.toml` (Konfigurasi Terpusat Tooling)**
```toml
[tool.ruff]
line-length = 88
target-version = "py311"
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "B",   # flake8-bugbear
    "S",   # flake8-bandit (security checks)
    "I",   # isort
]
ignore = [
    "S101", # allow assert statements in tests
]

[tool.ruff.per-file-ignores]
"tests/*" = ["S101", "S105", "S106"]

[tool.mypy]
python_version = "3.11"
plugins = ["mypy_django_plugin.main"]
strict = true
warn_unused_ignores = true
disallow_untyped_defs = true

[tool.django-stubs]
django_settings_module = "core.settings.test"

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "core.settings.test"
python_files = ["test_*.py", "*_test.py"]
addopts = "--strict-markers -ra -vv --cov=. --cov-report=term-missing --cov-fail-under=85"
markers = [
    "integration: marks integration tests",
    "unit: marks unit tests",
]
```

**File 2: `.github/workflows/ci-quality-gate.yml` (Automated Pipeline)**
```yaml
name: Django Security & Quality Assurance Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  quality-gate:
    name: Code Quality, Type Safety, and Security Audit
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15-alpine
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
      - name: Checkout Code
        uses: actions/checkout@v3

      - name: Set up Python 3.11
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements/dev.txt

      - name: Step 1 - Static Security Scan (Bandit)
        run: |
          bandit -r . -x ./tests,./venv -ll

      - name: Step 2 - Linting and Code Analysis (Ruff)
        run: |
          ruff check .

      - name: Step 3 - Static Type Analysis (Mypy)
        run: |
          mypy .

      - name: Step 4 - Vulnerability Dependency Audit
        run: |
          pip-audit --desc on

      - name: Step 5 - Django Security Deployment Check
        env:
          DJANGO_SETTINGS_MODULE: core.settings.production
          SECRET_KEY: dummy-key-strictly-for-static-deployment-check-evaluation
        run: |
          python manage.py check --deploy --fail-level WARNING

      - name: Step 6 - Run Pytest Suite with Coverage Gate
        env:
          DATABASE_URL: postgres://test_user:test_password@localhost:5432/test_db
        run: |
          pytest
```

---

## Bagian 5: Checklist Pemahaman

Gunakan tabel kendali mutu berikut untuk memverifikasi kesiapan pengujian dan pengerasan sistem sebelum merilis fitur ke lingkungan produksi:

| No | Area / Aspek | Kriteria Verifikasi Teknis | Status (`[x]`/`[ ]`) |
|---|---|---|:---:|
| 1 | **Test Suite Isolation** | Setiap test tidak meninggalkan data artefak di DB nyata dan tidak saling bergantung pada urutan eksekusi (*order-independent*). | [ ] |
| 2 | **External Network Mocking** | Seluruh panggilan HTTP eksternal (Stripe, Midtrans, Mailgun, dll.) terisolasi menggunakan `responses` atau `mocker` tanpa kebocoran network nyata. | [ ] |
| 3 | **Database Deployment Check** | Perintah `python manage.py check --deploy` berjalan di pipeline CI tanpa menghasilkan peringatan (*warning/error*). | [ ] |
| 4 | **Cookie & Session Hardening** | Pengaturan `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`, dan `SameSite=Lax/Strict` aktif di production. | [ ] |
| 5 | **Header Security (HSTS & CSP)** | Header `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, dan Content-Security-Policy (CSP) terkonfigurasi. | [ ] |
| 6 | **Static Code Analysis (SAST)** | Analisis statis `bandit` dan `ruff` lulus 100% tanpa celah *High/Medium severity* yang diabaikan tanpa justifikasi resmi. | [ ] |
| 7 | **Strict Static Typing** | File kritis (`views`, `services`, `selectors`, `models`) lolos validasi `mypy` dengan `django-stubs` tanpa error tipe. | [ ] |
| 8 | **Supply-Chain Audit** | Dependensi aplikasi dipindai menggunakan `pip-audit` dan bebas dari CVE berbahaya pada database PyPA/OSV. | [ ] |
| 9 | **Asynchronous Task Safety** | Pengujian async Celery task yang bergantung pada database transaksi diverifikasi via `captureOnCommitCallbacks` atau `TransactionTestCase`. | [ ] |
| 10 | **Access Control (IDOR/Tenant)** | Endpoint detail data memiliki pengujian penolakan akses lintas pengguna / lintas tenant dengan ekspektasi HTTP 403 atau HTTP 404. | [ ] |

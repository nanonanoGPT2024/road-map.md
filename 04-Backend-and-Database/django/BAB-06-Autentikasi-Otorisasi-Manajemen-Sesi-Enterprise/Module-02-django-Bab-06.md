# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Kategori: 04-Backend-and-Database
### Topik: Django
#### BAB 06: Autentikasi, Otorisasi, & Manajemen Sesi Enterprise
##### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis & Merekayasa Arsitektur Otentikasi Django**: Mengonstruksi pipeline otentikasi kustom bertingkat (*multi-backend*) dengan mekanisme *failover*, mitigasi *timing attacks*, dan integrasi federasi identitas (OIDC/SAML).
- **Mengimplementasikan Model Akses Lanjutan (ABAC & ReBAC)**: Melampaui kapabilitas RBAC (*Role-Based Access Control*) bawaan Django menggunakan *Custom Authentication & Authorization Backends* berbasis atribut dinamis (*Attribute-Based Access Control*) dan relasi objek (*Relation-Based Access Control*).
- **Mendesain Manajemen Sesi Terdistribusi**: Mengonfigurasi dan mengoptimasi *distributed stateful session storage* menggunakan Redis Cluster/Sentinel, menangani *race conditions* saat konkurensi tinggi, serta menegakkan kebijakan *concurrent login limit* dan *session fixation protection*.
- **Menerapkan Proteksi Kriptografi Modern**: Mengonfigurasi algoritma hashing *state-of-the-art* (Argon2id), pipeline Multi-Factor Authentication (TOTP & WebAuthn/Passkeys), dan enkripsi data sensitif pengguna *at-rest*.
- **Mengaudit & Menjamin Kepatuhan Regulasi**: Membangun subsistem *audit logging* berbasis Django Signals & Middleware non-blocking untuk memenuhi kepatuhan standar industri (SOC2 Type II, PCI-DSS v4.0, dan ISO 27001).

---

### 2. Prerequisites
- Pemahaman mendalam mengenai arsitektur internal Django (Request/Response lifecycle, Middleware chains, Signals, ORM).
- Penguasaan Modul 01 (Fundamental User Model, Basic Django Auth, dan Form Handling).
- Pemahaman jaringan: HTTP/HTTPS protocol state, Cookies, TLS termination, Reverse Proxies (Nginx/Envoy).
- Pengalaman operasional dengan Redis (in-memory data store, Redis data types, clustering, Sentinel).
- Pengetahuan kriptografi praktis: Symmetric/Asymmetric encryption, Cryptographic Hashing Functions (Argon2, PBKDF2, bcrypt), HMAC, CSPRNG.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Internal Authentication Pipeline & Django Auth Backends
Siklus otentikasi Django tidak terikat pada satu tabel database. Saat fungsi `django.contrib.auth.authenticate(request, **credentials)` dipanggil, eksekusi berjalan melalui pipeline berikut:

```
[Incoming Request]
        │
        ▼
authenticate(request, **credentials)
        │
        ├─► Loop settings.AUTHENTICATION_BACKENDS
        │     │
        │     ├─► Backend 1: LDAP/Enterprise IdP Backend
        │     │     ├─ Valid? ──► Return User Instance ──► [Halt Loop & Cache Backend Path]
        │     │     └─ Invalid/Exception (PermissionDenied vs None)
        │     │
        │     ├─► Backend 2: Custom Multi-Factor/Argon2 User Backend
        │     │     ├─ Valid? ──► Return User Instance ──► [Halt Loop & Cache Backend Path]
        │     │     └─ Returns None
        │     │
        │     └─► Backend N: Fallback DB ModelBackend
        │
        ▼
   [Return None] -> Authentication Failed
```

- **Penyimpanan Metadata Backend**: Ketika user berhasil diotentikasi dan login via `django.contrib.auth.login(request, user, backend=None)`, Django mencatat jalur Python backend yang sukses ke dalam session:
  - `request.session['_auth_user_id'] = user.get_session_auth_hash()`
  - `request.session['_auth_user_backend'] = backend_path`
  - `request.session['_auth_user_hash'] = user.get_session_auth_hash()`
- **Validasi Session Integrity via `AuthenticationMiddleware`**: Pada setiap request masuk, `AuthenticationMiddleware` mengekstrak `_auth_user_id` dan `_auth_user_hash`. Fungsi `get_user(request)` memeriksa apakah hash password saat ini masih cocok dengan yang tersimpan di sesi melalui `user.get_session_auth_hash()`. Jika password diubah di perangkat lain, session hash berubah secara deterministik, sehingga seluruh sesi aktif lainnya invalidated secara instan (*session revoking*).

#### B. Mekanisme Session Storage: Stateful Distributed Engine
Secara default, Django menyediakan `django.contrib.sessions.backends.db` yang menyimpan payload JSON terenkripsi/tersandi di tabel relational database. Pada arsitektur enterprise dengan jutaan concurrent users:
1. **DB Bottleneck**: Write query terjadi setiap session di-update (`django_session` table contention & bloat).
2. **Distributed Cache Backend**: Solusi enterprise menggunakan `django.contrib.sessions.backends.cache` atau `cached_db`.
3. **Session Race Conditions**: Saat *single page application* (SPA) atau mobile app menembakkan 5 HTTP requests asinkron secara paralel, Django session engine default membaca sesi secara konkuren. Request terakhir yang selesai memproses akan menimpa seluruh state session (*lost update problem*). Engine enterprise harus menerapkan locking (optimistic concurrency atau distributed locking berbasis Redis Redlock) atau mendesain session bersifat *immutable after login*.

#### C. Password Hashing Internals (Argon2id vs PBKDF2)
Django menggunakan sistem *password hasher pluggable*. Arsitektur enkripsi password Django diatur dalam format string:
```
<algorithm>$<iterations/memory_cost>$<salt>$<hash>
```
Secara default, Django menggunakan `PBKDF2PasswordHasher` (SHA256). Namun, PBKDF2 rentan terhadap akselerasi serangan perangkat keras (GPU/ASIC/FPGA) karena kebutuhan memorinya sangat rendah ($O(1)$ memory complexity).
Argon2 (pemenang Password Hashing Competition) varian **Argon2id** adalah standar industri saat ini:
- Menggabungkan resistansi serangan *side-channel cache-timing* (Argon2i) dan *time-memory trade-off cracking* (Argon2d).
- Mengonfigurasi parameter *time cost* ($t$), *memory cost* ($m$, e.g., 64 MiB), dan *parallelism* ($p$, jumlah threads CPU).

---

### 4. Why & What

| Dimensi | Default Django Implementation | Enterprise Production Architecture |
| :--- | :--- | :--- |
| **User Identity** | Auto-incrementing BigAutoField `id`, username-based | UUIDv4 / ULID (Pencegahan ID Insecure Direct Object References), Case-Insensitive Email primary, Multi-tenant Isolation |
| **Permissions** | Flat RBAC (`Permission` model terikat pada `ContentType`) | ABAC / ReBAC Dinamis (Policy engine terintegrasi context runtime: IP, geo-location, department, resource ownership) |
| **Session State** | RDBMS Table (`django_session`), uncompressed text | Redis Cluster dengan Sentinel Failover, compressed msgpack payload, atomic updates |
| **Credential Storage**| PBKDF2 (CPU-bound saja) | Argon2id (Memory-hard + CPU-hard) dengan rotasi otomatis saat parameter biaya dinaikkan |
| **Concurrency** | Session overwrite tak terbatas per user | Single Session Policy / Dynamic Concurrent Session Limiting via centralized distributed tracking |
| **Compliance** | Tidak ada audit trail bawaan | Audit logs immutable terstruktur (JSON) ditransmisikan ke SIEM (Elasticsearch/Datadog) |

---

### 5. How (Workflow Detail)

#### Workflow: Dynamic Attribute-Based Authorization (ABAC)
```
[Client Request: PATCH /api/v1/settlement/10982]
                     │
                     ▼
             [Django Middleware]
                     │ (Inject request.user, device_fingerprint, IP)
                     ▼
          [View / API ViewSet Layer]
                     │
                     ▼
    [Permission Evaluation: request.user.has_perm()]
                     │
                     ▼
     [EnterpriseDynamicABACBackend.has_perm()]
                     │
      ┌──────────────┴────────────────────────┐
      ▼                                       ▼
1. Fetch Context:                      2. Fetch Target Object:
   - User Role: Regional Finance          - Settlement 10982
   - Risk Score: Low                      - Status: Pending
   - Current GeoIP: ID                    - Settlement Amount: $500,000
   - Auth Time: < 15 mins ago             - Region: ID-JKT
      │                                       │
      └──────────────┬────────────────────────┘
                     │
                     ▼
         [Policy Engine Validation]
         - Is User.Region == Object.Region? -> True
         - Is User.Role == "Regional Finance"? -> True
         - Is Object.Amount <= User.ApprovalLimit ($1,000,000)? -> True
         - Is MFA Verified in this session? -> True
                     │
        ┌────────────┴────────────┐
       YES                        NO
        │                         │
        ▼                         ▼
   [HTTP 200/204]           [HTTP 403 Forbidden]
        │                         │
        └────────────┬────────────┘
                     ▼
          [Security Event Emitted]
   (Log to SIEM: AuthZ Success/Failure with metadata)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Paspor Diplomatik & Sistem Otentikasi Enterprise
- **Model Django Bawaan (Default)**: Tiket kertas taman hiburan. Siapa pun yang memegang tiket boleh masuk wahana A, B, C. Jika tiket sobek atau dicuri, tidak ada pengecekan sidik jari; nomor tiket berurutan (1, 2, 3) sehingga orang luar tahu berapa pengunjung yang datang.
- **Enterprise Architecture**: Paspor Diplomatik Elektronik dengan RFID dan Biometrik Terpusat.
  - **Identitas (UUIDv4/Argon2id)**: Microchip paspor terenkripsi anti-pemalsuan kriptografis.
  - **Redis Sessions**: Sistem pelacakan gerbang perbatasan *real-time*. Jika pemegang paspor terdeteksi masuk di Tokyo, sesi lama di New York langsung dihentikan oleh konsulat secara instan.
  - **ABAC/ReBAC**: Izin diplomatik masuk ruangan tertentu bukan sekadar membawa cap "Staff", melainkan dievaluasi saat itu juga: "Apakah diplomat ini membawa berkas misi negara X, masuk pada jam kerja yang ditentukan, dan didampingi petugas berwenang?"

#### Diagram Arsitektur Session & Auth Engine Terdistribusi
```
                     +----------------------------+
                     |        HAProxy / AWS ALB   | (TLS Termination, IP Injection)
                     +--------------+-------------+
                                    |
            +-----------------------+-----------------------+
            |                                               |
            v                                               v
+-----------------------+                       +-----------------------+
|  Django App Node 01   |                       |  Django App Node 02   |
|  - Custom User Model  |                       |  - Custom User Model  |
|  - Multi-Auth Backend |                       |  - Multi-Auth Backend |
|  - Custom Authz Engine|                       |  - Custom Authz Engine|
+-----------+-----------+                       +-----------+-----------+
            |                                               |
            +-----------------------+-----------------------+
                                    |
            +-----------------------+-----------------------+
            |                                               |
            v                                               v
+-------------------------------+               +-------------------------------+
|  Redis Sentinel / Cluster     |               |   PostgreSQL Master-Replica   |
|  (Session Engine & Tokens)    |               |   (ACID Data Store, Relational|
|                               |               |    Entities & Strict Schemas) |
|  Key: session:session_key     |               |                               |
|  Val: Compressed Msgpack      |               |  - accounts_customuser        |
|  TTL: Auto Sliding Expiration |               |  - audit_securityauditlog     |
|                               |               |  - org_departments            |
+-------------------------------+               +-------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Custom User Model dengan Hardened Enterprise Security
File: `core/accounts/models.py`

```python
import uuid
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


class EnterpriseUserManager(BaseUserManager):
    def create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError("Kredensial wajib: Alamat email harus disertakan.")
        
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser harus memiliki status is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser harus memiliki status is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class EnterpriseUser(AbstractBaseUser, PermissionsMixin):
    """
    Model pengguna enterprise:
    - UUIDv4 Primary Key untuk mencegah Enumeration Attacks.
    - Normalized Case-Insensitive Email sebagai unique identifier.
    - Tracking perubahan keamanan (password_changed_at, failed_login_attempts).
    - Hardened flag logic.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(
        unique=True,
        db_index=True,
        max_length=255,
        error_messages={"unique": "Pengguna dengan email ini telah terdaftar."},
    )
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    
    is_active = models.BooleanField(
        default=True,
        help_text="Tentukan apakah akun ini aktif. Cabut alih-alih menghapus akun.",
    )
    is_staff = models.BooleanField(
        default=False,
        help_text="Menentukan apakah pengguna dapat mengakses antarmuka administrasi.",
    )
    
    # Audit & Security Attributes
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    lockout_until = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(default=timezone.now)
    require_password_change = models.BooleanField(default=False)
    
    # Metadata Relasional Organisasi (Untuk ABAC)
    department_code = models.CharField(
        max_length=32,
        blank=True,
        validators=[RegexValidator(r"^[A-Z0-9_-]+$")],
        db_index=True,
    )
    clearance_level = models.PositiveSmallIntegerField(
        default=1,
        help_text="Level otorisasi: 1 (Internal), 2 (Confidential), 3 (Restricted), 4 (Top Secret)",
    )

    date_joined = models.DateTimeField(default=timezone.now)

    objects = EnterpriseUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "accounts_enterprise_user"
        indexes = [
            models.Index(fields=["email", "is_active"]),
            models.Index(fields=["department_code", "clearance_level"]),
        ]

    def __str__(self) -> str:
        return f"{self.email} ({self.id})"

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email).lower()

    def set_password(self, raw_password: str | None) -> None:
        super().set_password(raw_password)
        self.password_changed_at = timezone.now()
        self.failed_login_attempts = 0
```

#### B. Implementasi Custom ABAC Authentication & Authorization Backend
File: `core/auth/backends.py`

```python
import hmac
import logging
from typing import Any
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import PermissionDenied
from django.utils import timezone

logger = logging.getLogger("security.auth")
UserModel = get_user_model()


class EnterpriseABACBackend(ModelBackend):
    """
    Otorisasi lanjutan berbasis atribut (ABAC):
    Mengevaluasi permission berdasarkan Subject, Action, Resource, and Context.
    """

    def authenticate(self, request, username=None, password=None, **kwargs) -> Any:
        email = kwargs.get("email", username)
        if not email or not password:
            return None

        email = UserModel.objects.normalize_email(email).lower()

        try:
            user = UserModel.objects.get(email=email)
        except UserModel.DoesNotExist:
            # Timing attack mitigation: Jalankan hash hashing dummy agar durasi konstan
            UserModel().set_password(password)
            logger.warning(f"Auth failed: Identitas tidak ditemukan [{email}]")
            return None

        # Evaluasi Lockout State
        if user.lockout_until and user.lockout_until > timezone.now():
            logger.warning(f"Auth blocked: Akun terkunci [{email}]")
            raise PermissionDenied("Akun Anda sementara terkunci karena pelanggaran keamanan.")

        if not user.is_active:
            logger.warning(f"Auth rejected: Akun non-aktif [{email}]")
            return None

        if user.check_password(password):
            if user.failed_login_attempts > 0:
                user.failed_login_attempts = 0
                user.save(update_fields=["failed_login_attempts"])
            return user
        else:
            # Handle Failed Attempt Counter
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.lockout_until = timezone.now() + timezone.timedelta(minutes=15)
                logger.critical(f"Account Locked out: [{email}] - 5 failed attempts reached.")
            user.save(update_fields=["failed_login_attempts", "lockout_until"])
            return None

    def has_perm(self, user_obj, perm: str, obj: Any = None) -> bool:
        """
        Policy Decision Point (PDP) untuk otorisasi fine-grained.
        Syntax: perm = "app_label.action_resource"
        Misal: "settlements.approve_transaction"
        """
        if not user_obj.is_authenticated or not user_obj.is_active:
            return False

        # Superuser bypass
        if user_obj.is_superuser:
            return True

        # Validasi Object-Level ABAC
        if obj is not None:
            return self._evaluate_object_policy(user_obj, perm, obj)

        # Fallback ke verifikasi peran statis standar
        return super().has_perm(user_obj, perm, obj=None)

    def _evaluate_object_policy(self, user: Any, perm: str, resource: Any) -> bool:
        """
        Evaluasi runtime kontekstual terhadap atribut user vs objek.
        """
        if perm == "finance.approve_settlement":
            # Aturan 1: Departemen harus selaras
            if getattr(resource, "department_code", None) != user.department_code:
                return False
            
            # Aturan 2: Clearance Level harus mencukupi untuk nominal tinggi
            settlement_amount = getattr(resource, "amount", 0)
            if settlement_amount > 100_000_000: # Di atas 100 juta butuh Level 3+
                if user.clearance_level < 3:
                    return False
            
            # Aturan 3: Separation of Duty (Pencipta dilarang menyetujui transaksinya sendiri)
            if getattr(resource, "created_by_id", None) == user.id:
                logger.warning(f"Separation of Duty Violation: User {user.id} mencoba approve transaksi milik sendiri {resource.id}")
                return False

            return True

        return False
```

#### C. Redis Stateful Session Backend dengan Sliding Expiration & Concurrency Safeguard
File: `core/sessions/backends.py`

```python
import msgpack
from django.conf import settings
from django.contrib.sessions.backends.base import CreateError, SessionBase
from django.core.cache import caches

class EnterpriseRedisSession(SessionBase):
    """
    Session storage backend menggunakan Redis terdistribusi
    dengan serialisasi performa tinggi (msgpack) dan penanganan atomisitas.
    """
    def __init__(self, session_key=None):
        self._cache = caches[getattr(settings, "SESSION_CACHE_ALIAS", "session")]
        super().__init__(session_key)

    def encode(self, session_dict: dict) -> str:
        # Msgpack serialisasi biner, jauh lebih ringkas dan cepat dibanding standar JSON string
        return msgpack.packb(session_dict, use_bin_type=True).hex()

    def decode(self, session_data: str) -> dict:
        try:
            raw_bytes = bytes.fromhex(session_data)
            return msgpack.unpackb(raw_bytes, raw=False)
        except Exception:
            return {}

    def load(self):
        session_data = self._cache.get(self._get_redis_key(self.session_key))
        if session_data is None:
            self._session_key = None
            return {}
        return self.decode(session_data)

    def exists(self, session_key: str) -> bool:
        return self._cache.has_key(self._get_redis_key(session_key))

    def create(self):
        while True:
            self._session_key = self._new_session_key()
            try:
                self.save(must_create=True)
            except CreateError:
                continue
            self.modified = False
            return

    def save(self, must_create: bool = False):
        if self.session_key is None:
            return self.create()
        
        redis_key = self._get_redis_key(self.session_key)
        data = self.encode(self._get_session(no_load=must_create))
        expire_seconds = self.get_expiry_age()

        if must_create:
            # Gunakan add() cache (Redis SETNX) untuk menghindari tabrakan konkurensi pembuatan sesi
            created = self._cache.add(redis_key, data, timeout=expire_seconds)
            if not created:
                raise CreateError
        else:
            self._cache.set(redis_key, data, timeout=expire_seconds)

    def delete(self, session_key=None):
        if session_key is None:
            if self.session_key is None:
                return
            session_key = self.session_key
        self._cache.delete(self._get_redis_key(session_key))

    @staticmethod
    def _get_redis_key(session_key: str) -> str:
        return f"sess:{session_key}"
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Insiden Concurrency Session Hijacking & Bypass Approval pada Mega-Fintech
* **Entitas**: Payment Gateway Skala Nasional (Volume: 12.000 Request/detik).
* **Insiden (Vulnerability)**:
  Auditor SOC2 menemukan celah kritikal:
  1. Default Django Session menggunakan relational DB tanpa Distributed Locking.
  2. Saat token admin dicuri, penyerang mengirimkan ratusan request simultan ke endpoint `/disbursement/approve/`. Django membaca state user dari DB secara asynchronously tanpa row-locking, mengeksekusi multiple disbursement dengan otorisasi tunggal, melipatgandakan *payout limit*.
  3. Sistem tidak memiliki mekanisme *Concurrent Login Invalidation*, sehingga user internal yang login dari IP luar negeri dapat beroperasi bersamaan dengan sesi sah di kantor pusat.
* **Solusi Arsitektural Terpasang**:
  1. Migrasi session layer ke **Redis Sentinel Cluster** dengan implementasi *Atomic Session Tokens*.
  2. Injeksi **Distributed Session Device Limiter Middleware**: Menggunakan Redis Sorted Sets (`ZADD`, `ZREMRANGEBYSCORE`) untuk melacak sesi per `user_id`. Jika sesi baru tercipta melebihi threshold ($N=1$), sesi sebelumnya diputus seketika via event signaling.
  3. Konversi Otorisasi menjadi **Context-Aware Zero-Trust ABAC Backend** yang memeriksa IP origin (via Trusted Proxy CIDR verification) dan Hardware MFA timestamp (< 5 menit untuk aksi berisiko finansial).

---

### 9. Trade-offs

```
                       [Enterprise Authentication Architecture]
                                          |
        +---------------------------------+---------------------------------+
        |                                                                   |
        v                                                                   v
 [Strict Stateful Sessions]                                         [Stateless Token / JWT]
  - Session tersimpan di Redis Central                               - Self-contained payload
  - Instantly revocable (Kepatuhan Finansial)                        - Sulit di-revoke instan tanpa blacklist
  - Butuh Network I/O ke Redis setiap hit                            - Sangat efisien, Zero Redis Lookup
  - Scale limit: Memori Redis & Network Pipe                         - Rentan stale permissions & token bloat
        |                                                                   |
        +---------------------------------+---------------------------------+
                                          |
                                          v
                              [Hybrid Enterprise Choice]
            - JWT singkat (TTL: 5-15 menit) untuk stateless API read-heavy
            - Redis Stateful Session terpusat untuk sensitive web transaction & financial mutation
```

| Parameter | PBKDF2 (Default) | Argon2id (Enterprise Recom.) | Redis Stateful Session | Stateless JWT Auth |
| :--- | :--- | :--- | :--- | :--- |
| **CPU Footprint** | Rendah - Menengah | Sangat Terkontrol | Minimal | Sangat Rendah |
| **Memory Footprint**| Sangat Rendah | Sangat Tinggi (Memori-hard) | Bergantung Concurrent Users | Hampir Nol (Client-side) |
| **Revocation Speed**| N/A | N/A | Sub-milidetik ($O(1)$) | Terhambat polling cache |
| **Network Overhead**| Nol | Nol | 1-2 ms (Redis roundtrip) | Nol (Payload pada Header) |
| **Scalability Limit**| CPU Bound | CPU & Memory Bound | Memory cluster bound | Horizontally limitless |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Insecure Deserialization pada Session Engine
* **Penyebab**: Menggunakan `pickle` sebagai session serializer di Django klasik.
* **Gejala**: Eksploitasi Remote Code Execution (RCE) jika Redis session storage berhasil di-infiltrasi melalui *Redis Unauthorized Access*.
* **Solusi**: Wajib menggunakan `django.contrib.sessions.serializers.JSONSerializer` atau serialisasi aman biner seperti `msgpack`. Jangan gunakan `pickle`.

#### 2. Spoofing IP akibat Misconfigured `SECURE_PROXY_SSL_HEADER` & `REMOTE_ADDR`
* **Penyebab**: Membaca `request.META['HTTP_X_FORWARDED_FOR']` secara mentah untuk memvalidasi IP policy pada ABAC. Penyerang menginjeksi header HTTP palsu: `X-Forwarded-For: 127.0.0.1`.
* **Gejala**: Bypass filter IP internal.
* **Solusi**: Pastikan reverse proxy (Nginx/Cloudflare) melakukan stripping header secara ketat dan gunakan library tepercaya seperti `django-ipware` dengan parsing list IP tepercaya (*trusted proxies CIDR*).

#### 3. N+1 Queries Saat Verifikasi User Permissions
* **Penyebab**: Pengecekan `request.user.has_perm()` memicu query ke tabel `auth_permission`, `auth_group_permissions`, dan tabel bridge berulang kali.
* **Gejala**: Latensi endpoint melonjak dari 15ms menjadi 250ms saat loop pengecekan hak akses objek koleksi besar.
* **Solusi**: Terapkan permission caching pada instance user (`prefetch_related('groups__permissions', 'user_permissions')`) atau tangani policy caching di layer Redis.

---

### 11. Best Practices (Production Checklist)

- [ ] **Hash Algorithm**: Gunakan `Argon2PasswordHasher` sebagai pilihan pertama di `settings.PASSWORD_HASHERS`.
- [ ] **Cookie Security Flags**:
  - `SESSION_COOKIE_SECURE = True`
  - `SESSION_COOKIE_HTTPONLY = True`
  - `SESSION_COOKIE_SAMESITE = 'Lax'` (atau `'Strict'` untuk aplikasi non-SSO)
  - `SESSION_COOKIE_AGE = 28800` (8 jam maksimal untuk operasional enterprise)
  - `SESSION_SAVE_EVERY_REQUEST = True` (Mendukung sliding-expiration terkontrol)
- [ ] **Session Engine**: Arahkan `SESSION_ENGINE` ke Redis Cache backend dengan *connection pooling* via `django-redis`.
- [ ] **Password Validation**: Terapkan `MinimumLengthValidator(12)`, `CommonPasswordValidator`, `NumericPasswordValidator`, dan custom validator untuk kompleksitas entropy (zxcvbn).
- [ ] **Timing Attack Immunity**: Pastikan seluruh pengecekan token, password, atau credential verification memakai fungsi pembanding konstan waktu seperti `hmac.compare_digest()`.
- [ ] **Identity Masking**: Mengonfigurasi `request.session.cycle_key()` pasca otentikasi berhasil untuk mencegah serangan *Session Fixation*.

---

### 12. Hands-on Practice

Buat skenario lab mandiri di path `hands-on/m02/`.

#### Langkah 1: Persiapan Environment & Instalasi Dependensi
```bash
mkdir -p hands-on/m02 && cd hands-on/m02
python3 -m venv venv
source venv/bin/activate
pip install django django-redis argon2-cffi msgpack
django-admin startproject enterprise_auth .
mkdir -p apps/security
```

#### Langkah 2: Setup Redis & Security Settings
Buka `enterprise_auth/settings.py` dan sesuaikan parameter berikut:

```python
import os

AUTH_USER_MODEL = "security.EnterpriseUser"

AUTHENTICATION_BACKENDS = [
    "apps.security.backends.EnterpriseABACBackend",
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

CACHES = {
    "default": {
        "BACKEND": "django-redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django-redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {"max_connections": 100},
        },
    },
    "session": {
        "BACKEND": "django-redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/2",
        "OPTIONS": {
            "CLIENT_CLASS": "django-redis.client.DefaultClient",
        },
    },
}

SESSION_ENGINE = "apps.security.session_backend.EnterpriseRedisSession"
SESSION_CACHE_ALIAS = "session"
SESSION_COOKIE_SECURE = False  # Set True di production dengan HTTPS
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
```

#### Langkah 3: Implementasi Single Device Session Tracker Middleware
Buat file `apps/security/middleware.py`:

```python
import json
from django.core.cache import caches
from django.contrib.auth import logout
from django.http import JsonResponse

class EnforceSingleSessionMiddleware:
    """
    Memastikan satu pengguna hanya memiliki satu sesi aktif.
    Sesi lama akan dibatalkan seketika saat login dari device baru terdeteksi.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.cache = caches["session"]

    def __call__(self, request):
        if request.user.is_authenticated:
            user_session_tracker_key = f"user_active_sess:{request.user.id}"
            current_session_key = request.session.session_key
            
            stored_session_key = self.cache.get(user_session_tracker_key)
            
            if stored_session_key is None:
                # Sesi pertama dicatat
                self.cache.set(user_session_tracker_key, current_session_key, timeout=28800)
            elif stored_session_key != current_session_key:
                # Terdeteksi login di tempat lain: Hancurkan sesi saat ini
                logout(request)
                return JsonResponse(
                    {
                        "error": "SECURITY_SESSION_REVOKED",
                        "message": "Sesi Anda telah berakhir karena akun terdeteksi login pada perangkat lain."
                    },
                    status=401
                )

        return self.get_response(request)
```

Tambahkan `apps.security.middleware.EnforceSingleSessionMiddleware` pada list `MIDDLEWARE` setelah `AuthenticationMiddleware`.

---

### 13. Exercise

#### Level: Easy
1. Ubah konfigurasi hasher Django agar parameter `memory_cost` Argon2id dinaikkan menjadi 128 MiB (131072 KiB) dan `time_cost` = 4. Lakukan verifikasi runtime menggunakan shell.
2. Buat unit-test sederhana untuk memastikan user yang di-instansiasi via factory tidak menyimpan plain-text password ke database.

#### Level: Medium
1. Implementasikan sebuah model `Resource` (misal: `FinancialDocument`) dan perluas method `EnterpriseABACBackend.has_perm()` untuk menangani permission `finance.view_restricted_document`. Dokumen hanya boleh dibaca jika:
   - Level clearance user >= Level clearance dokumen.
   - Status dokumen bukan "ARCHIVED".
   - Akses dilakukan pada rentang jam 08:00 - 18:00 UTC (Time-of-day dynamic constraint).

#### Level: Hard
1. Buat mekanisme **Session Invalidation Fan-Out**: Ketika user mengganti password melalui API, buat Custom Signal Receiver yang mencari seluruh session keys yang terafiliasi dengan user id tersebut di Redis (menggunakan Redis Set indexing), kemudian menghapus seluruh keys tersebut secara atomic menggunakan Redis Pipeline.

---

### 14. Challenge

**Skenario**:
Anda merancang arsitektur keamanan untuk sistem Core Banking yang beroperasi di 3 region geografis (Multi-Region Active-Active). Jaringan antar-region memiliki latensi replikasi data database relational sekitar 800ms, namun Redis In-Memory Sync memiliki latensi hanya 40ms.

**Kebutuhan Teknis**:
1. Rancang arsitektur otentikasi hybrid yang menghentikan risiko **Replay Attack** dan **Privilege Escalation Race Condition**. Jika seorang pegawai di-suspend di Region A, aksesnya harus ditolak di Region B dan C dalam waktu kurang dari 100ms.
2. Default Django ORM model checks `request.user.is_active` membaca dari DB replica lokal yang memiliki delay 800ms.
3. Rancang middleware dan Redis cache invalidation protocol yang membypass delay DB replication ini tanpa membebani Primary DB Master secara langsung dengan query berulang dari seluruh region. Dokumentasikan format struktur data Redis dan logic alurnya secara mendalam.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Konsep Dasar (Basic)
1. **Mengapa `AbstractUser` lebih jarang digunakan pada aplikasi enterprise dibanding `AbstractBaseUser`?**
   - *Jawaban*: `AbstractUser` membawa serta opini skema bawaan Django (seperti kolom `username`, form handling kaku, serta ID integer), sedangkan `AbstractBaseUser` memberikan fleksibilitas penuh untuk mengganti identifier utama (misal: Case-insensitive Email, UUIDv4), membuang kolom yang tidak perlu, dan memegang kendali penuh atas indeks skema.
2. **Kapan fungsi `request.session.cycle_key()` wajib dipanggil secara manual?**
   - *Jawaban*: Dipanggil saat terjadi eskalasi status autentikasi (misalnya dari anonim/guest menjadi authenticated, atau setelah verifikasi langkah MFA kedua) untuk mencegah serangan *Session Fixation*.
3. **Apa arti nilai return `None` pada custom Django Authentication Backend?**
   - *Jawaban*: `None` menandakan bahwa backend tersebut tidak dapat mengautentikasi kredensial yang diberikan dan mengizinkan Django untuk melanjutkan iterasi ke authentication backend berikutnya di dalam list `AUTHENTICATION_BACKENDS`.
4. **Mengapa algoritma PBKDF2 dianggap kurang tahan dibanding Argon2id terhadap serangan brute-force modern?**
   - *Jawaban*: Karena PBKDF2 adalah algoritma *CPU-hard* murni dengan kebutuhan memori statis yang sangat kecil, sehingga penyerang dapat memanfaatkan chip ASIC atau GPU paralel berskala masif untuk menghitung miliaran kombinasi secara murah. Argon2id dirancang *Memory-hard*, memaksa penyerang mengalokasikan RAM fisik nyata untuk setiap tebakan komputasi.
5. **Apa fungsi dari atribut `_auth_user_hash` di dalam session Django?**
   - *Jawaban*: Menyimpan representasi hash HMAC dari password pengguna. Digunakan oleh `AuthenticationMiddleware` untuk memverifikasi keabsahan sesi secara dinamis; jika password pengguna diubah, seluruh sesi lama otomatis menjadi tidak valid karena hash-nya tidak cocok.

#### Bagian 2: Analisis Menengah (Intermediate)
6. **Apa bahaya keamanan mengembalikan `PermissionDenied` vs `None` pada method `authenticate()`?**
   - *Jawaban*: Mengangkat eksepsi `PermissionDenied` akan langsung menghentikan evaluasi backend berikutnya dan mengembalikan HTTP 403 Forbidden. Jika disalahgunakan pada multi-backend auth, backend sekunder yang sah tidak akan pernah dieksekusi. Namun jika akun teridentifikasi disusupi/terkunci permanen, `PermissionDenied` penting untuk memblokir fallback backend.
7. **Bagaimana cara mencegah race condition pada session Django ketika client mengirimkan multiple concurrent requests?**
   - *Jawaban*: Menggunakan Session Backend terdistribusi yang mendukung distributed locks (misal: Redis lock / Redlock) saat write session, atau dengan mendesain state session bersifat *read-only* setelah proses login, serta menyimpan data transaksional ke database/cache terpisah alih-alih meletakkannya di `request.session`.
8. **Mengapa kita tidak boleh menggunakan method `user.save()` biasa di dalam signal `post_save` untuk meng-update metadata login user?**
   - *Jawaban*: Memanggil `user.save()` tanpa filter di dalam `post_save` akan memicu infinite recursion loop, memicu signal berulang kali hingga batas call stack terlampaui (*RecursionError*). Update metadata wajib menggunakan parameter `update_fields` terarah atau menggunakan `User.objects.filter(pk=user.pk).update(...)`.
9. **Jelaskan perbedaan mendasar RBAC bawaan Django dengan ABAC dalam evaluasi objek!**
   - *Jawaban*: RBAC Django mengevaluasi relasi statis: `User -> Groups -> Permission` (apakah user memiliki hak edit?). ABAC mengevaluasi hak akses secara dinamis pada saat runtime dengan memperhitungkan metadata Subject (Role, Clearance), Resource (Owner, Status, Nominal), Action, dan Environment Context (Waktu, Lokasi IP, Skor Risiko Perangkat).
10. **Apa implikasi performa dari pengaturan `SESSION_SAVE_EVERY_REQUEST = True` pada Redis Cluster?**
    - *Jawaban*: Implikasinya adalah setiap request HTTP (termasuk static asset jika tertangani oleh pipeline Django) akan menghasilkan network write I/O ke Redis untuk memperbarui TTL sesi. Pada traffic tinggi, ini memicu peningkatan utilisasi bandwidth dan CPU Redis. Solusinya adalah memisahkan serving static files dan menggunakan sliding-expiration berbasis throttling/interval (misal: refresh TTL hanya jika sisa waktu < 50%).

#### Bagian 3: Skenario Kasus Produksi (Production Scenarios)
11. **Skenario 1**: *Sebuah institusi fintech mengalami lonjakan latency API hingga 4 detik saat jam pasar dibuka. Hasil profiler menunjukkan 70% waktu habis di method `authenticate()`. Setelah dicegah, ternyata terdapat serangan brute-force besar-besaran terhadap endpoint login yang membanjiri CPU dengan hashing Argon2id.*
    - **Solusi Arsitektural**: Terapkan *Pre-authentication Rate Limiting* di edge/API Gateway (Nginx/Cloudflare) berbasis IP dan username. Gunakan in-memory cache (Redis) untuk menerapkan leaky-bucket counter sebelum fungsi `authenticate()` dipanggil. Jika sebuah username gagal login 3 kali, tolak request secara instan (HTTP 429) tanpa menyentuh CPU untuk perhitungan hash kriptografis Argon2id.

12. **Skenario 2**: *Sebuah platform multi-tenant kesehatan (HIPAA compliant) mendapati bahwa dokter di Rumah Sakit A dapat membaca data pasien di Rumah Sakit B melalui celah IDOR via endpoint API `/api/records/<uuid>/` meskipun menggunakan decorator standar `@permission_required('records.view_record')`.*
    - **Analisis & Remedi**: Decorator standar `@permission_required` hanya memeriksa otorisasi global tingkat model (apakah dokter memiliki peran membaca tabel rekam medis), bukan otorisasi tingkat baris/objek. Remedi: Implementasikan Custom Authorization Backend (ReBAC/ABAC) yang menolak akses jika `patient.hospital_id != request.user.hospital_id`, serta gantikan decorator standar dengan method evaluasi eksplisit: `request.user.has_perm('records.view_record', obj=record)`.

13. **Skenario 3**: *Setelah user mengganti password di portal web, mobile app mereka masih tetap dapat melakukan transaksi finansial selama 2 jam ke depan karena mobile app menggunakan access token stateless (JWT) berdurasi 2 jam.*
    - **Mitigasi**: Implementasikan mekanisme *Token Blacklisting & Session Hash Validation*. Saat password diganti, generate `password_changed_at` baru dan simpan ke Redis `user_revocation_timestamp:{user_id}`. Buat authentication middleware pada API Gateway atau Django yang memvalidasi klaim `iat` (issued-at) pada payload JWT terhadap nilai timestamp pembatalan di Redis. Jika `iat` < `revocation_timestamp`, batalkan token seketika (HTTP 401).

---

### 16. Summary

1. **Otorisasi Terintegrasi**: Mengamankan arsitektur Django skala enterprise menuntut pergeseran dari sekadar model bawaan (RBAC kaku) menuju model otorisasi dinamis kontekstual (**ABAC/ReBAC**) yang mengevaluasi parameter runtime, kepemilikan objek, dan segregasi tugas (*Separation of Duties*).
2. **State Management Terdistribusi**: Penggunaan default database session backend tidak dapat bertahan pada traffic konkuren tinggi. **Redis Cluster/Sentinel** yang dioptimasi dengan serialisasi hemat ukuran (`msgpack`) dan penanganan *race-condition* memberikan performa berlatensi rendah sekaligus kemampuan pembatalan sesi secara terpusat (*Instant Revocation*).
3. **Kriptografi Defensif**: Penggunaan algoritma *Memory-hard* seperti **Argon2id** dan pengamanan data identitas menggunakan format **UUIDv4** memberikan postur pertahanan berlapis dari ancaman *offline brute-force attack* dan enumerasi sumber daya (*IDOR*).
4. **Zero-Trust Session Control**: Pengendalian integritas sesi mutlak dipertahankan dengan mekanisme pelacakan sesi tunggal/terbatas (*Single Session Policy*), sliding expiration aman, serta invalidasi seketika menggunakan hash sinkronisasi saat parameter keamanan pengguna berubah.
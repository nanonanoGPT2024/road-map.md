# Bab 06 Module 01: Autentikasi, Otorisasi, & Manajemen Sesi Enterprise

---

## 01. Identitas Modul
* **Track:** Backend & Database Systems
* **Framework:** Django 5.x LTS / Python 3.12+
* **Topik:** Enterprise Authentication, Role-Based Access Control (RBAC), Session Engineering, Security Hardening
* **Prasyarat:** Pemahaman mendalam tentang HTTP Protocol, Django ORM, Relational Database Modeling, Middleware Lifecycle, dan REST/Template Patterns.
* **Tingkat Kesulitan:** Advanced / Production-Grade
* **Alokasi Waktu:** 8 - 10 Jam Pembelajaran Mandiri & Implementasi Lab

---

## 02. Learning Objectives
1. **Mengonstruksi Custom User Model** menggunakan `AbstractBaseUser` dan `PermissionsMixin` yang mendukung identitas multifaktor, audit trail, soft-delete, dan performa indeks optimal.
2. **Mengembangkan Hybrid Authentication Backend** yang mendukung resolusi identitas dinamis (Email, Username, SSO/SAML, LDAP) dengan proteksi mitigasi *timing attacks*.
3. **Mendesain Granular Role-Based Access Control (RBAC)** dan Policy-Based Access Control (PBAC) menggunakan kombinasi Model-Level Permissions, Django Groups, dan Object-Level Permission evaluators.
4. **Mengonfigurasi dan Memitigasi Session Store Enterprise** berbasis Redis Cache-Backed Session dengan perlindungan Session Fixation, Session Hijacking, dan implementasi rotasi sesi otomatis.
5. **Mengimplementasikan Enterprise Security Middleware** untuk memitigasi brute-force via exponential backoff rate limiting, concurrent session enforcement, dan deteksi anomali IP/User-Agent.

---

## 03. Concept Map Diagram (ASCII)

```
+-----------------------------------------------------------------------------------------------+
|                                      HTTP REQUEST PIPELINE                                    |
+-----------------------------------------------------------------------------------------------+
                                                |
                                                v
+-----------------------------------------------------------------------------------------------+
| [1] Security & Session Middleware                                                             |
|     +--> SessionMiddleware: Load & Decrypt Session ID from Encrypted/Signed Cookie            |
|     +--> RateLimitMiddleware: Redis Sliding Window Token Bucket (IP + Fingerprint)             |
|     +--> AuthenticationMiddleware: Lazy Resolution of request.user (LazyObject)               |
+-----------------------------------------------------------------------------------------------+
                                                |
                                                v
+-----------------------------------------------------------------------------------------------+
| [2] Enterprise Authentication Engine                                                          |
|     +--> Custom User Model (`EnterpriseUser`) via `AUTH_USER_MODEL`                            |
|     +--> Multi-Backend Dispatcher (ModelBackend, SAMLBackend, LDAPBackend)                    |
|     +--> Password Hashing Engine: Argon2id (Primary) -> Scrypt -> PBKDF2 (Fallback/Upgrade)   |
|     +--> Multi-Factor Challenge Validator (TOTP / FIDO2 WebAuthn Token)                       |
+-----------------------------------------------------------------------------------------------+
                                                |
                                                v
+-----------------------------------------------------------------------------------------------+
| [3] Enterprise Authorization Matrix (RBAC & PBAC)                                             |
|     +--> Group-Role Mapping (Django Groups + Custom Role Hierarchy)                           |
|     +--> Explicit Permissions Engine (`django.contrib.auth.models.Permission`)                |
|     +--> Object-Level Permission Checker (`django-guardian` / Custom Queryset Filter)         |
|     +--> Enterprise Policy Decorators (`@role_required`, `@enforce_mfa`, `@audit_trigger`)    |
+-----------------------------------------------------------------------------------------------+
                                                |
                                                v
+-----------------------------------------------------------------------------------------------+
| [4] State & Persistence Layer                                                                 |
|     +--> Redis Cluster: In-Memory Encrypted Session Storage + Concurrency Control Keys        |
|     +--> PostgreSQL: Master-Replica Sharded User Table + Partitioned Audit Logs Table         |
+-----------------------------------------------------------------------------------------------+
```

---

## 04. Mengapa Relevan

Dalam ekosistem aplikasi enterprise modern, implementasi autentikasi *out-of-the-box* Django standar (berbasis `django.contrib.auth.models.User` default dan session engine database mentah) menghadirkan celah keamanan, skalabilitas, dan fleksibilitas struktural yang signifikan:

1. **Skalabilitas Model Data:** Mengganti `User` model bawaan di tengah siklus hidup produksi adalah salah satu refactoring paling destruktif di Django karena ketergantungan relasional foreign key dari sistem pihak ketiga dan migrations internal. Menyiapkan model kustom sejak awal adalah keharusan mutlak.
2. **Kinerja Session Store:** Penggunaan database relasional standar untuk session storage (`django.contrib.sessions.backends.db`) menimbulkan bottleneck I/O write/read tinggi pada database utama. Redis cached-session tiering mengatasi latency dan konkurensi skala jutaan transaksi per detik.
3. **Kepatuhan Regulasi & Keamanan:** Standar enterprise seperti SOC2, ISO 27001, HIPAA, dan PCI-DSS mewajibkan kontrol granular atas lifecycle sesi: *concurrent session invalidation*, *mandatory password rotative hashing* (Argon2id), pembatasan jejak login gagal, serta audit trail komprehensif pada level object-action.

---

## 05. Anatomi Konsep Inti

```
+-----------------------------------------------------------------------------------------+
|                                    ANATOMI SESI & USER                                  |
+-----------------------------------------------------------------------------------------+
| [EnterpriseUser Model]                                                                  |
|   - id: UUIDv4 (Primary Key, High Entropy)                                              |
|   - email: CICharField (Unique, B-Tree Index)                                            |
|   - password: Hash String ($argon2id$v=19$m=65536,t=3,p=4$...)                          |
|   - is_mfa_enabled: Boolean                                                             |
|   - failed_login_attempts: SmallInteger                                                 |
|   - lockout_until: DateTimeWithZone                                                     |
|   - password_changed_at: DateTimeWithZone                                               |
|                                                                                         |
| [Session Store Payload (Redis Key: "enterprise:session:<session_key>")]                  |
|   - _auth_user_id: "e4eaaaf2-a142-11ee-8c90-0242ac120002"                               |
|   - _auth_user_backend: "apps.core.auth.backends.EnterpriseAuthenticationBackend"       |
|   - _auth_user_hash: "3b08e2... (HMAC of user password field for auto-invalidation)"     |
|   - ip_address: "198.51.100.42"                                                         |
|   - user_agent: "Mozilla/5.0 (X11; Linux x86_64)..."                                    |
|   - session_created_at: 1703600000                                                      |
|   - last_activity: 1703600320                                                           |
+-----------------------------------------------------------------------------------------+
```

### 1. Custom User Architecture
* `AbstractBaseUser`: Menyediakan implementasi inti autentikasi (password hashing, tracking token sesi). Tidak membawa skema bawaan field non-esensial, memberikan kontrol absolut atas skema tabel.
* `PermissionsMixin`: Menginjeksi relasi grup dan sistem permission standar Django (`groups`, `user_permissions`, `is_superuser`), menjaga interoperabilitas dengan Django Admin dan `@permission_required`.

### 2. Authentication Backends Lifecycle
Resolusi `authenticate(request, **credentials)` berjalan secara sekuensial melalui `AUTHENTICATION_BACKENDS`. Backend wajib mengembalikan *User instance* jika validasi berhasil atau `None` jika gagal/menolak memproses, tanpa melempar fatal exception (agar backend berikutnya dapat dieksekusi).

### 3. Session & Cache Layering
* `CachedStore` Django menggunakan pola *Write-Through Cache*. Data sesi ditulis ke Redis dan di-persist ke PostgreSQL secara asinkron atau langsung (tergantung backend), menyediakan durabilitas tinggi dan *sub-millisecond retrieval*.
* `SESSION_ENGINE = "django.contrib.sessions.backends.cache"` mengeksekusi I/O murni dalam memori tanpa dependensi database relasional, ideal untuk sistem high-throughput.

---

## 06. Panduan Implementasi Step-by-Step

### Langkah 1: Pengaturan Environment & Dependensi
Instal dependensi kriptografi performa tinggi dan driver Redis:
```bash
pip install argon2-cffi redis django-redis
```

### Langkah 2: Menentukan Setting Keamanan Password Hashers
Konfigurasikan algoritma password hashing pada `settings.py` untuk memprioritaskan Argon2id (pemenang Password Hashing Competition):
```python
# settings.py
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

ARGON2_HASHER = {
    'time_cost': 3,
    'memory_cost': 65536,  # 64 MiB
    'parallelism': 4,
}
```

### Langkah 3: Konfigurasi Session Engine Redis
```python
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {"max_connections": 100, "retry_on_timeout": True},
            "IGNORE_EXCEPTIONS": False,
        }
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = 'Strict'
SESSION_COOKIE_AGE = 28800  # 8 Jam
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True
```

---

## 07. Contoh Kasus Sederhana

Berikut implementasi custom user model dasar dengan autentikasi berbasis email yang sudah mematuhi standar dasar decoupling:

```python
# accounts/models.py
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
import uuid

class SimpleUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

class SimpleUser(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = SimpleUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email
```

---

## 08. Implementasi Production-Grade Lengkap Kode

Berikut arsitektur autentikasi modular *full enterprise*, mencakup Custom Model, Dynamic Backend, Concurrent Session Control, dan Granular RBAC Evaluator.

### 1. `apps/users/models.py`
```python
import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

class EnterpriseUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('Email wajib diisi.'))
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verified', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(email, password, **extra_fields)


class EnterpriseUser(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_('email address'), unique=True, max_length=255, db_index=True)
    first_name = models.CharField(_('first name'), max_length=150, blank=True)
    last_name = models.CharField(_('last name'), max_length=150, blank=True)
    
    # State tracking & Compliance
    is_active = models.BooleanField(_('active'), default=True)
    is_staff = models.BooleanField(_('staff status'), default=False)
    is_verified = models.BooleanField(_('verified identity'), default=False)
    
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(default=timezone.now)
    last_activity_ip = models.GenericIPAddressField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = EnterpriseUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        db_table = 'enterprise_auth_users'
        verbose_name = _('Enterprise User')
        verbose_name_plural = _('Enterprise Users')
        indexes = [
            models.Index(fields=['email', 'is_active']),
            models.Index(fields=['locked_until']),
        ]

    def clean(self):
        super().clean()
        self.email = self.email.lower()

    def is_locked(self) -> bool:
        if self.locked_until and self.locked_until > timezone.now():
            return True
        return False

    def reset_failed_attempts(self):
        if self.failed_login_attempts > 0 or self.locked_until is not None:
            self.failed_login_attempts = 0
            self.locked_until = None
            self.save(update
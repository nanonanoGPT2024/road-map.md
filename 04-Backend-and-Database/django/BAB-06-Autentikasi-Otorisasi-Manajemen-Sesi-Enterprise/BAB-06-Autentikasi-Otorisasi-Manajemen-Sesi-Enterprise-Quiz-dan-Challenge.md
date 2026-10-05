# BAB-06-Autentikasi-Otorisasi-Manajemen-Sesi-Enterprise: Quiz, Challenge, & Knowledge Check

Uji kompetensi teknis dan pemahaman arsitektur keamanan Django tingkat enterprise. Modul evaluasi ini mencakup Custom User Model, Role-Based Access Control (RBAC), Object-Level Permissions, manajemen sesi terdistribusi (Redis session cache), mitigasi session hijacking, proteksi brute-force, serta integrasi multi-factor authentication (MFA/TOTP).

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1: Perbedaan `AbstractUser` vs `AbstractBaseUser`
**Pertanyaan:**
Kapan arsitektur enterprise sebaiknya memilih inheritansi dari `AbstractBaseUser` daripada `AbstractUser`, dan apa konsekuensi struktural terhadap model Django bawaan?

- A. `AbstractUser` dipilih jika ingin mengganti tipe primary key menjadi UUID tanpa mengubah field `username`.
- B. `AbstractBaseUser` dipilih jika arsitektur memerlukan kontrol penuh atas field autentikasi (misal: hanya menggunakan `email` tanpa kolom `username`), di mana developer harus mengimplementasikan atribut `USERNAME_FIELD`, `REQUIRED_FIELDS`, dan `BaseUserManager` kustom.
- C. `AbstractUser` menghapus seluruh integrasi permission bawaan (`PermissionsMixin`), sehingga tidak cocok untuk sistem berbasis RBAC.
- D. `AbstractBaseUser` otomatis menyertakan field `first_name`, `last_name`, `email`, dan `is_staff`.

**Kunci Jawaban:** **B**

**Pembahasan Mendalam:**
`AbstractUser` menyediakan implementasi lengkap user Django standar (termasuk `username`, `first_name`, `last_name`, `email`, `is_staff`, `is_active`, dan `date_joined`). Jika enterprise menginginkan skema autentikasi non-konvensional sejak awal (misalnya email-only authentication tanpa `username`), `AbstractBaseUser` adalah pondasi minimal yang hanya menyediakan hashing password (`password`), pencatatan login terakhir (`last_login`), serta interface dasar autentikasi. Namun, mewarisi `AbstractBaseUser` mewajibkan developer mendefinisikan `USERNAME_FIELD`, `REQUIRED_FIELDS`, dan mengaitkan custom `UserManager` yang mewarisi `BaseUserManager` (dengan metode `create_user` dan `create_superuser`).

---

### Soal 2: Flag Keamanan Session Cookie
**Pertanyaan:**
Dalam deployment production multi-domain atau microservice yang dilindungi HTTPS dan reverse proxy (Nginx/Cloudflare), kombinasi konfigurasi Django session cookie manakah yang wajib diaktifkan untuk mencegah pencurian token sesi via XSS dan Network Sniffing?

- A. `SESSION_COOKIE_HTTPONLY = False` dan `SESSION_COOKIE_SECURE = False`
- B. `SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_SECURE = True`, dan `SESSION_COOKIE_SAMESITE = 'Lax'` (atau `'Strict'`)
- C. `SESSION_COOKIE_DOMAIN = '*'` dan `SESSION_COOKIE_AGE = 31536000`
- D. `SESSION_EXPIRE_AT_BROWSER_CLOSE = False` dan `SESSION_SAVE_EVERY_REQUEST = True`

**Kunci Jawaban:** **B**

**Pembahasan Mendalam:**
- `SESSION_COOKIE_HTTPONLY = True`: Menginstruksikan browser agar cookie sesi tidak dapat diakses melalui JavaScript (`document.cookie`), memitigasi risiko pencurian sesi saat terjadi serangan Cross-Site Scripting (XSS).
- `SESSION_COOKIE_SECURE = True`: Memastikan cookie hanya dikirimkan melalui koneksi terenkripsi HTTPS, mencegah sniffing paket di jaringan publik (Man-in-the-Middle/MitM).
- `SESSION_COOKIE_SAMESITE = 'Lax'` atau `'Strict'`: Membatasi pengiriman cookie pada cross-site requests, melindungi aplikasi dari serangan Cross-Site Request Forgery (CSRF).

---

### Soal 3: Siklus Hidup dan Invalidasi Sesi pada Password Change
**Pertanyaan:**
Mengapa setelah pengguna berhasil memperbarui password mereka, fungsi `update_session_auth_hash(request, user)` harus dipanggil secara eksplisit di view?

- A. Untuk mengenkripsi ulang password di database menggunakan algoritma PBKDF2/Argon2.
- B. Untuk mencegah pengguna logout secara otomatis akibat rotasi session auth hash yang digunakan Django untuk memvalidasi integritas sesi.
- C. Untuk membersihkan seluruh data di cache Redis yang berelasi dengan user ID.
- D. Untuk mengirimkan email notifikasi rotasi kredensial kepada user secara asynchronous.

**Kunci Jawaban:** **B**

**Pembahasan Mendalam:**
Django menyimpan representasi hash dari password pengguna di dalam session data (melalui `_auth_user_hash`). Middleware `AuthenticationMiddleware` memverifikasi hash ini di setiap request. Saat password diganti, hash password user di database berubah. Jika `update_session_auth_hash(request, user)` tidak dipanggil, sesi user saat ini akan dianggap invalid pada request berikutnya dan user langsung tertendang keluar (logged out). Fungsi ini merotasi session auth hash pada request aktif tanpa menghancurkan sesi yang sedang berjalan.

---

### Soal 4: Mekanisme Custom Authentication Backend
**Pertanyaan:**
Perhatikan urutan tuple `AUTHENTICATION_BACKENDS` berikut:
```python
AUTHENTICATION_BACKENDS = [
    'core.backends.LDAPAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]
```
Bagaimana alur evaluasi Django saat fungsi `authenticate(request, username=None, password=None)` dieksekusi?

- A. Django mengeksekusi kedua backend secara paralel, dan jika salah satu berhasil, user yang dikembalikan digabungkan (merge permissions).
- B. Django mengeksekusi `LDAPAuthBackend` terlebih dahulu; jika mengembalikan instance `User`, proses berhenti dan autentikasi sukses. Jika mengembalikan `None`, Django melanjutkan evaluasi ke `ModelBackend`.
- C. Jika `LDAPAuthBackend` melempar `PermissionDenied`, Django tetap melanjutkan ke `ModelBackend`.
- D. `ModelBackend` selalu diprioritaskan terlepas dari urutan array konfigurasi.

**Kunci Jawaban:** **B**

**Pembahasan Mendalam:**
Django mengevaluasi `AUTHENTICATION_BACKENDS` secara berurutan (short-circuit evaluation). Metode `authenticate()` dipanggil pada backend pertama. Jika backend mengembalikan objek `User`, loop berhenti dan user dianggap terautentikasi. Jika backend mengembalikan `None`, Django beralih ke backend berikutnya. Pengecualian penting: jika backend melempar exception `django.core.exceptions.PermissionDenied`, Django langsung menghentikan evaluasi seluruh backend berikutnya dan menganggap autentikasi gagal total.

---

### Soal 5: Batasan Model Permission Bawaan Django
**Pertanyaan:**
Apa keterbatasan utama sistem permission bawaan Django (`django.contrib.auth.models.Permission`) dalam konteks aplikasi Multi-Tenant atau Document Management System (DMS)?

- A. Django tidak mendukung permission kustom pada `Meta.permissions`.
- B. Permission bawaan hanya beroperasi pada tingkat model/tabel (model-level permissions), bukan pada instance objek individual (object-level permissions/row-level security).
- C. Permission bawaan tidak dapat dihubungkan ke `Group`.
- D. Django permissions mengharuskan penggunaan database NoSQL untuk dynamic roles.

**Kunci Jawaban:** **B**

**Pembahasan Mendalam:**
Secara default, Django auth permissions hanya memeriksa apakah seorang user memiliki izin umum terhadap entitas model (misal: `app.change_invoice`). Sistem ini tidak mengetahui apakah user X boleh mengubah *Invoice #1001* milik Tenant A atau tidak. Untuk kebutuhan izin per-objek (object-level / row-level security), enterprise harus mengimplementasikan Custom Authentication/Authorization Backend (metode `has_perm(user, perm, obj)`) atau mengadopsi library seperti `django-guardian` / PostgreSQL Row-Level Security (RLS).

---

## Bagian 2: Intermediate Questions (5 Soal Analisis Kode)

### Soal 6: Analisis Kerentanan Session Hijacking via Session Fixation
**Perhatikan potongan kode autentikasi berikut:**
```python
from django.contrib.auth import authenticate
from django.http import JsonResponse

def custom_login_view(request):
    username = request.POST.get('username')
    password = request.POST.get('password')
    user = authenticate(request, username=username, password=password)
    
    if user is not None and user.is_active:
        # Developer mengikat ID user ke sesi manual
        request.session['_auth_user_id'] = str(user.pk)
        request.session['is_authenticated'] = True
        return JsonResponse({"status": "success", "message": "Logged in"})
    
    return JsonResponse({"status": "failed"}, status=401)
```
**Pertanyaan:**
Identifikasi kerentanan fatal pada implementasi di atas dan bagaimana cara memperbaikinya sesuai kaidah keamanan Django!

**Jawaban & Analisis Teknis:**
1. **Kerentanan Fatal:** Terjadi celah **Session Fixation**. Dengan menetapkan key sesi secara manual tanpa memanggil `django.contrib.auth.login(request, user)`, Django tidak merotasi session key (`request.session.cycle_key()`). Jika penyerang telah menyisipkan session key tertentu ke browser korban sebelum login (misal melalui XSS atau subdomain cookie tossing), penyerang tetap dapat menggunakan session ID yang sama setelah korban terautentikasi.
2. **Ketiadaan Session Auth Hash:** Sesi tidak mencatat `_auth_user_hash` dan `_auth_user_backend`, sehingga mekanisme invalidasi sesi saat perubahan password tidak berfungsi.
3. **Solusi Standar:**
```python
from django.contrib.auth import authenticate, login
from django.views.decorators.http import require_POST

@require_POST
def secure_login_view(request):
    username = request.POST.get('username')
    password = request.POST.get('password')
    user = authenticate(request, username=username, password=password)
    
    if user is not None:
        if not user.is_active:
            return JsonResponse({"error": "Akun dinonaktifkan"}, status=403)
        
        # login() otomatis memanggil request.session.cycle_key()
        # dan menyematkan _auth_user_hash, _auth_user_id, _auth_user_backend
        login(request, user)
        return JsonResponse({"status": "success"})
        
    return JsonResponse({"error": "Kredensial tidak valid"}, status=401)
```

---

### Soal 7: Optimasi N+1 Queries pada Pengecekan RBAC Massal
**Perhatikan view berikut yang merender dashboard dengan otorisasi:**
```python
def project_list_view(request):
    projects = Project.objects.filter(is_active=True)
    accessible_projects = []
    
    for project in projects:
        # has_perm memeriksa object-level permissions via custom backend
        if request.user.has_perm('projects.view_project', project):
            accessible_projects.append(project)
            
    return render(request, 'dashboard/projects.html', {'projects': accessible_projects})
```
**Pertanyaan:**
Jika terdapat 500 project, kode di atas menyebabkan masalah N+1 query yang masif. Bagaimana arsitektur querying yang benar untuk menyelesaikan validasi hak akses ini langsung di tingkat database?

**Jawaban & Analisis Teknis:**
Pengecekan otorisasi dalam loop Python menyebabkan pemanggilan database berulang kali untuk setiap objek. Solusi enterprise yang benar adalah memfilter objek langsung pada level SQL query menggunakan `Q` object, subquery, atau model relasional membership:

```python
from django.db.models import Q

def optimized_project_list_view(request):
    user = request.user
    
    if user.is_superuser:
        projects = Project.objects.filter(is_active=True)
    else:
        # Evaluasi RBAC langsung di database engine dalam 1 query tunggal
        projects = Project.objects.filter(
            is_active=True
        ).filter(
            Q(owner=user) |
            Q(memberships__user=user, memberships__role__permissions__codename='view_project') |
            Q(department__in=user.departments.all())
        ).select_related('owner', 'department').distinct()
        
    return render(request, 'dashboard/projects.html', {'projects': projects})
```

---

### Soal 8: Konfigurasi Redis Cache Session Backend dengan High Availability
**Perhatikan snippet konfigurasi `settings.py` berikut:**
```python
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "sessions"

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
    },
    "sessions": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://10.0.1.50:6379/2",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            # PARAMETER KRITIS
        }
    }
}
```
**Pertanyaan:**
Apa risiko menggunakan engine `django.contrib.sessions.backends.cache` murni di lingkungan enterprise, dan opsi konfigurasi apa yang menjamin persistensi data serta ketahanan terhadap kegagalan Redis?

**Jawaban & Analisis Teknis:**
1. **Risiko Cache Murni (`backends.cache`):** Jika instance Redis mengalami restart, kehabisan memori (OOM dengan policy `allkeys-lru`), atau mengalami crash jaringan, seluruh sesi pengguna aktif akan hilang seketika (seluruh user di-logout paksa).
2. **Solusi Arsitektur Enterprise:**
   - Gunakan `django.contrib.sessions.backends.cached_db`. Backend ini menulis data sesi ke cache Redis untuk performa pembacaan sangat tinggi ($O(1)$), sekaligus melakukan write-through ke database relasional (PostgreSQL) sebagai cold storage fallback.
   - Konfigurasi Redis connection pool dengan Redis Sentinel atau AWS ElastiCache Replication Group:
   ```python
   SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
   
   # Opsi ketahanan django-redis
   CACHES["sessions"]["OPTIONS"].update({
       "SOCKET_CONNECT_TIMEOUT": 3,
       "SOCKET_TIMEOUT": 3,
       "RETRY_ON_TIMEOUT": True,
       "IGNORE_EXCEPTIONS": True, # Jika Redis down, django-redis fallback/bypass tanpa crash 500
   })
   ```

---

### Soal 9: Custom Backend untuk Audit Trail dan Device Fingerprinting
**Pertanyaan:**
Buatlah kerangka Custom Authentication Backend yang memvalidasi kredensial pengguna, memeriksa status two-factor authentication, dan mencatat device fingerprint (User-Agent, IP address) ke tabel audit log setiap kali autentikasi berhasil atau gagal.

**Jawaban & Implementasi Kode:**
```python
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.models import SecurityAuditLog

User = get_user_model()

class EnterpriseAuditAuthBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        ip_address = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown') if request else 'CLI'

        try:
            user = User.objects.get_by_natural_key(username)
        except User.DoesNotExist:
            # Tetap jalankan password hasher dummy untuk memitigasi User Enumeration Timing Attack
            User().set_password(password)
            self._log_attempt(None, username, ip_address, user_agent, success=False, reason="USER_NOT_FOUND")
            return None

        if user.check_password(password):
            if not self.user_can_authenticate(user):
                self._log_attempt(user, username, ip_address, user_agent, success=False, reason="ACCOUNT_DISABLED")
                return None
                
            # Autentikasi primer sukses
            self._log_attempt(user, username, ip_address, user_agent, success=True, reason="CREDENTIALS_VALID")
            return user
        else:
            self._log_attempt(user, username, ip_address, user_agent, success=False, reason="INVALID_PASSWORD")
            return None

    def _get_client_ip(self, request):
        if not request:
            return '127.0.0.1'
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'Unknown')

    def _log_attempt(self, user, username, ip, ua, success, reason):
        SecurityAuditLog.objects.create(
            user=user,
            attempted_username=username,
            ip_address=ip,
            user_agent=ua,
            is_successful=success,
            failure_reason=reason,
            timestamp=timezone.now()
        )
```

---

### Soal 10: Race Condition pada Concurrency Session Limiting
**Pertanyaan:**
Sebuah aplikasi perbankan membatasi sesi login: satu user hanya boleh memiliki maksimal 1 sesi aktif. Developer menggunakan sinyal `user_logged_in` untuk menghapus sesi lama:
```python
from django.contrib.auth.signals import user_logged_in
from django.contrib.sessions.models import Session
from django.dispatch import receiver

@receiver(user_logged_in)
def enforce_single_session(sender, request, user, **kwargs):
    # Mengambil semua sesi dan mencari yang memiliki user_id sama
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        data = session.get_decoded()
        if data.get('_auth_user_id') == str(user.pk) and session.session_key != request.session.session_key:
            session.delete()
```
Apa kelemahan fatal kode di atas terhadap performa dan race condition pada beban tinggi (high concurrency)?

**Jawaban & Analisis Teknis:**
1. **Full Table Scan ($O(N)$ Disaster):** Tabel `django_session` mengenkripsi/meng-encode isi data sesi. Menjalankan `session.get_decoded()` di dalam loop Python memaksa aplikasi melakukan parsing seluruh sesi aktif di database. Jika terdapat 100.000 sesi aktif, login akan memakan waktu puluhan detik dan melumpuhkan database CPU.
2. **Race Condition:** Jika user melakukan login dari 2 perangkat secara bersamaan (milidetik yang sama), kedua request dapat membaca daftar sesi sebelum sesi baru dihapus, menyebabkan kedua sesi tetap aktif.
3. **Solusi Enterprise:** Gunakan pemetaan eksplisit relasi User-to-Session di Redis atau tabel relasional `UserActiveSession(user_id, session_key, last_activity)` dengan transaction locking (`select_for_update`) atau operasi atomik Redis:
```python
# Solusi via Redis Key-Value Mapping:
# Key: f"user_session:{user.id}", Value: current_session_key
import redis
r = redis.Redis(host='localhost', port=6379, db=2)

def set_exclusive_session(user_id, new_session_key):
    pipe = r.pipeline()
    key = f"user_session:{user_id}"
    old_session_key = r.get(key)
    
    if old_session_key:
        # Hapus sesi lama langsung dari session store
        r.delete(f":1:django.contrib.sessions.cache{old_session_key.decode()}")
        
    r.set(key, new_session_key, ex=86400)
    pipe.execute()
```

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Kasus)

### Skenario 1: Serangan Credential Stuffing & DDoS pada Endpoint `/api/v1/auth/login/`
**Konteks Masalah:**
Sebuah platform fintech mengalami lonjakan trafik anomali: 15.000 request per menit menuju endpoint login dengan IP address yang terdistribusi luas (botnet perumahan). Akibatnya, CPU database PostgreSQL melonjak ke 100% karena proses hashing password PBKDF2 (`django.contrib.auth.hashers.PBKDF2PasswordHasher` dengan 720.000 iterasi) yang memakan resource komputasi sangat intensif.

**Analisis Akar Masalah (Root Cause):**
1. PBKDF2 sengaja didesain lambat secara komputasi untuk mencegah offline brute force. Namun, jika request masuk tanpa rate limit pada perimeter awal, eksekusi hashing di aplikasi backend menimbulkan Denial of Service (DoS) lokal pada thread/worker Gunicorn.
2. Mekanisme rate limiting standar berbasis single-IP gagal karena penyerang merotasi ribuan proxy IP (residential botnet).

**Arsitektur Solusi & Mitigasi:**
1. **Layer 1 (WAF / Edge Protection):** Aktifkan Cloudflare Managed Challenge (Turnstile) atau AWS WAF Rate-based Rule khusus path `/api/v1/auth/login/`.
2. **Layer 2 (Application IP & Username Rate Limiting):** Terapkan modul `django-axes` atau Redis Token Bucket dual-key limiter (limit per IP dan limit per target username):
```python
# middleware/rate_limit.py
import redis
from django.http import JsonResponse
from django.core.cache import caches

redis_client = caches['sessions'].client.get_client()

def check_login_rate_limit(username, ip_address):
    user_key = f"rl:user:{username}"
    ip_key = f"rl:ip:{ip_address}"
    
    # Maksimal 5 percobaan per username dalam 15 menit
    user_attempts = redis_client.incr(user_key)
    if user_attempts == 1:
        redis_client.expire(user_key, 900)
    if user_attempts > 5:
        return False, "Akun terkunci sementara karena terlalu banyak percobaan gagal."

    # Maksimal 50 percobaan per IP dalam 15 menit
    ip_attempts = redis_client.incr(ip_key)
    if ip_attempts == 1:
        redis_client.expire(ip_key, 900)
    if ip_attempts > 50:
        return False, "Terlalu banyak request dari alamat IP ini."

    return True, None
```
3. **Layer 3 (Asynchronous Circuit Breaker):** Jika CPU utilization server aplikasi melampaui 80%, tolak request login non-prioritas dengan HTTP status 429 Too Many Requests sebelum masuk ke loop `check_password()`.

---

### Skenario 2: Token Desynchronization pada Lingkungan Multi-Server Zero-Downtime Deployment
**Konteks Masalah:**
Aplikasi e-commerce enterprise memiliki 8 node server Django di balik Application Load Balancer (ALB). Sesi disimpan menggunakan `django.contrib.sessions.backends.db` (database PostgreSQL). Saat proses rolling update release v2.4.0 berlangsung, pengguna aktif tiba-tiba mengalami logout mendadak secara berkala saat berpindah halaman (intermittent 401/403 session dropped).

**Analisis Akar Masalah (Root Cause):**
1. Pada release v2.4.0, developer menambahkan field baru ke custom user model dan memodifikasi `SECRET_KEY` pada file `.env` baru di node server yang diperbarui terlebih dahulu.
2. Ketika request user dialihkan oleh ALB antara node v2.3.0 (server lama) dan node v2.4.0 (server baru), enkripsi/tanda tangan HMAC session cookie menjadi tidak cocok karena perbedaan `SECRET_KEY` antar instans.
3. Ketiadaan *Session Affinity* (Sticky Sessions) pada ALB memperparah keadaan karena browser mengirimkan cookie yang ditandatangani `SECRET_KEY_A` ke server dengan `SECRET_KEY_B`.

**Arsitektur Solusi & Mitigasi:**
1. **Standardisasi Secrets Management:** Gunakan centralized vault (seperti AWS Secrets Manager, HashiCorp Vault) untuk mendistribusikan `SECRET_KEY` seragam ke seluruh container/instance sebelum rolling deployment dimulai.
2. **Rotasi SECRET_KEY Bertahap (`SECRET_KEY_FALLBACKS`):** Manfaatkan fitur Django 4.0+ `SECRET_KEY_FALLBACKS`:
```python
# settings.py
SECRET_KEY = os.environ.get('CURRENT_SECRET_KEY')
SECRET_KEY_FALLBACKS = [
    os.environ.get('PREVIOUS_SECRET_KEY'), # Menerima session yang ditandatangani key lama
]
```
3. **Session Cache Storage Berkelanjutan:** Migrasikan penyimpanan sesi dari PostgreSQL ke Redis Cluster terpisah dari instance app lifecyle, sehingga reload app server tidak mengganggu integritas data sesi.

---

### Skenario 3: Privilege Escalation melalui Deserialisasi State Sesi Tidak Aman
**Konteks Masalah:**
Sistem internal enterprise menggunakan serializer sesi kustom untuk menyimpan role dan objek izin pengguna:
```python
# settings.py
SESSION_SERIALIZER = 'django.contrib.sessions.serializers.PickleSerializer'
```
Auditor keamanan eksternal menemukan bahwa attacker yang berhasil mencuri `SECRET_KEY` dapat mengeksekusi Remote Code Execution (RCE) atau melakukan manipulasi role menjadi superuser dengan memalsukan isi session cookie.

**Analisis Akar Masalah (Root Cause):**
`PickleSerializer` mengeksekusi arbitrary object deserialization melalui modul bawaan Python `pickle`. Jika secret key bocor atau terjadi kelemahan cryptographic verification, muatan berbahaya (`__reduce__` exploit payload) di dalam cookie akan dieksekusi oleh interpreter Python saat sesi di-decode.

**Arsitektur Solusi & Mitigasi:**
1. **Wajib Menggunakan JSONSerializer:** Gunakan `django.contrib.sessions.serializers.JSONSerializer` yang hanya membaca tipe data primitif (dict, list, int, string):
```python
SESSION_SERIALIZER = 'django.contrib.sessions.serializers.JSONSerializer'
```
2. **Larangan Menyimpan State Izin di Sesi:** Jangan pernah menyimpan objek permission mentah di dalam session data (`request.session['role'] = 'ADMIN'`). Sesi hanya boleh menyimpan ID identitas (`_auth_user_id`), sedangkan pemeriksaan izin wajib selalu dievaluasi secara dinamis terhadap database atau cache permission yang terisolasi.
3. **Rotasi Segera SECRET_KEY:** Jika terindikasi kompromi, jalankan emergency key rotation dan invalidasi seluruh sesi aktif di database/Redis.

---

## Bagian 4: Practical Chapter Challenge

### Tantangan: Membangun Enterprise-Grade RBAC & Session Security Framework

**Deskripsi Tugas:**
Anda ditugaskan merancang modul autentikasi dan manajemen sesi enterprise untuk sistem ERP finansial yang memenuhi standar keamanan perbankan.

#### Spesifikasi Kebutuhan Teknis:

1. **Custom User Model (`EnterpriseUser`):**
   - Inherit dari `AbstractBaseUser` dan `PermissionsMixin`.
   - Primary key menggunakan `UUIDField`.
   - Autentikasi utama menggunakan field `email` (case-insensitive & unique).
   - Memiliki field: `employee_id` (CharField, unique), `is_staff` (BooleanField), `is_active` (BooleanField), `is_mfa_enabled` (BooleanField), `failed_login_attempts` (PositiveIntegerField), `locked_until` (DateTimeField, nullable).
   - Custom `EnterpriseUserManager` yang menangani `create_user` dan `create_superuser`.

2. **Custom RBAC & Dynamic Permission Middleware:**
   - Buat decorator `@require_role_permission(permission_codename)` yang memeriksa apakah user memiliki hak akses melalui Group atau Role hierarchy.
   - Buat middleware `EnforceSessionSecurityMiddleware` yang memverifikasi:
     - IP Address dan User-Agent client tidak berubah selama sesi berlangsung (mencegah pencurian session cookie). Jika berubah, hancurkan sesi (`request.session.flush()`) dan kembalikan respon HTTP 403 Forbidden.
     - Timeout inaktivitas absolut: jika request terakhir > 30 menit lalu, sesi kadaluarsa.

3. **Rate Limiting & Account Lockout Logic:**
   - Jika user salah memasukkan password sebanyak 5 kali berturut-turut, akun otomatis dikunci selama 30 menit (`locked_until`).

---

### Solusi Referensi Implementasi:

#### 1. Custom User Model (`accounts/models.py`)
```python
import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone

class EnterpriseUserManager(BaseUserManager):
    def create_user(self, email, employee_id, password=None, **extra_fields):
        if not email:
            raise ValueError('Email wajib disertakan.')
        if not employee_id:
            raise ValueError('Employee ID wajib disertakan.')
            
        email = self.normalize_email(email).lower()
        user = self.model(email=email, employee_id=employee_id, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, employee_id, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser harus memiliki is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser harus memiliki is_superuser=True.')

        return self.create_user(email, employee_id, password, **extra_fields)

class EnterpriseUser(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    employee_id = models.CharField(max_length=20, unique=True, db_index=True)
    full_name = models.CharField(max_length=150)
    
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_mfa_enabled = models.BooleanField(default=False)
    
    failed_login_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    
    date_joined = models.DateTimeField(default=timezone.now)

    objects = EnterpriseUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['employee_id', 'full_name']

    def is_locked(self):
        if self.locked_until and self.locked_until > timezone.now():
            return True
        return False

    def reset_lockout(self):
        self.failed_login_attempts = 0
        self.locked_until = None
        self.save(update_fields=['failed_login_attempts', 'locked_until'])

    def register_failed_attempt(self):
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.locked_until = timezone.now() + timezone.timedelta(minutes=30)
        self.save(update_fields=['failed_login_attempts', 'locked_until'])
```

#### 2. Session Integrity Middleware (`security/middleware.py`)
```python
import hashlib
from django.utils import timezone
from django.http import HttpResponseForbidden

class EnforceSessionSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # 1. Validasi IP dan User Agent Fingerprint
            current_ip = self._get_client_ip(request)
            current_ua = request.META.get('HTTP_USER_AGENT', 'Unknown')
            expected_fingerprint = hashlib.sha256(f"{current_ip}|{current_ua}".encode()).hexdigest()
            
            saved_fingerprint = request.session.get('_sec_fingerprint')
            if not saved_fingerprint:
                request.session['_sec_fingerprint'] = expected_fingerprint
            elif saved_fingerprint != expected_fingerprint:
                # Terindikasi session hijacking / pemindahan cookie ke browser lain
                request.session.flush()
                return HttpResponseForbidden("Sesi dibatalkan karena anomali lingkungan koneksi (IP/Perangkat berubah).")

            # 2. Inactivity Timeout (30 Menit)
            now = timezone.now().timestamp()
            last_activity = request.session.get('_last_activity', now)
            if now - last_activity > 1800:
                request.session.flush()
                return HttpResponseForbidden("Sesi Anda telah kadaluarsa karena tidak ada aktivitas selama 30 menit.")
            
            request.session['_last_activity'] = now

        response = self.get_response(request)
        return response

    def _get_client_ip(self, request):
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '127.0.0.1')
```

#### 3. Role-Based Access Control Decorator (`security/decorators.py`)
```python
from functools import wraps
from django.core.exceptions import PermissionDenied

def require_role_permission(permission_codename):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied("Autentikasi diperlukan.")
            
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
                
            # Periksa permission melalui Groups dan direct permissions
            if request.user.has_perm(permission_codename):
                return view_func(request, *args, **kwargs)
                
            raise PermissionDenied(f"Akses ditolak: Anda tidak memiliki permission [{permission_codename}].")
        return _wrapped_view
    return decorator
```

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan daftar periksa berikut untuk mengevaluasi kesiapan arsitektur autentikasi & otorisasi enterprise Anda sebelum rilis production:

| Area Evaluasi | Kriteria Keamanan & Arsitektur | Status Mandiri |
| :--- | :--- | :---: |
| **Model Identitas** | Model pengguna mewarisi `AbstractBaseUser` + `PermissionsMixin` dengan Primary Key UUID dan indeks tepat. | [ ] |
| **Session Cookie Security** | `SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_SECURE = True`, `SESSION_COOKIE_SAMESITE = 'Lax'/'Strict'` terpasang aktif. | [ ] |
| **Pencegahan Session Hijacking** | Fingerprinting IP dan User-Agent divalidasi pada setiap request berotentikasi di layer middleware. | [ ] |
| **Anti Session Fixation** | Fungsi `django.contrib.auth.login()` digunakan sehingga `request.session.cycle_key()` tereksekusi otomatis. | [ ] |
| **Invalidasi Sesi Kredensial** | `update_session_auth_hash(request, user)` dipanggil setiap kali terjadi pembaruan password pengguna. | [ ] |
| **Backend & Storage Sesi** | Session storage menggunakan Redis dengan failover `cached_db` (bukan pure file atau memory backend). | [ ] |
| **Proteksi Brute-Force** | Account lockout diterapkan setelah 5 kegagalan beruntun, serta dilengkapi rate-limiter IP pada WAF/Nginx. | [ ] |
| **Efisiensi Otorisasi** | Pengecekan izin data massal dilakukan di level SQL query (`Q` filter/subquery), bukan iterasi Python $O(N)$. | [ ] |
| **Audit & Logging** | Setiap event autentikasi (login sukses, gagal, ganti password, logout) tercatat di database audit terpisah. | [ ] |
| **Pencegahan Timing Attack** | Fungsi pengecekan user tidak membocorkan keberadaan username (menjalankan dummy hasher jika user not found). | [ ] |

#!/usr/bin/env python3
"""
Lab Hands-on: Go (Golang) Runtime Deep Dive Simulation
Topic: Bab 01 - Modul 02: Goroutines, GMP Scheduler & CSP Channels

Simulasi mendalam arsitektur internal runtime Go:
1. Model GMP (Goroutine, Machine/OS-Thread, Processor/Context).
2. Work-Stealing Algorithm dan Go Runtime 61-tick Global Queue Check.
3. CSP (Communicating Sequential Processes) Primitive: Go Channel (Buffered & Unbuffered).
"""

import sys
import time
import threading
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# ANSI Color Codes untuk Visualisasi Terminal
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_CYAN = "\033[36m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_MAGENTA = "\033[35m"
CLR_RED = "\033[31m"


class GoChannelClosedException(Exception):
    """Exception saat operasi read/write pada closed channel."""
    pass


class GoChannel:
    """
    Simulasi CSP Channel Go dengan semantik Synchronous (unbuffered, cap=0)
    atau Asynchronous (buffered, cap > 0).
    """
    def __init__(self, capacity: int = 0):
        self.capacity = capacity
        self.buffer = deque()
        self.closed = False
        self.lock = threading.Condition()

    def send(self, value: Any, gid: int):
        """Kirim data ke channel (mirip sintaks: ch <- val)."""
        with self.lock:
            if self.closed:
                raise GoChannelClosedException("panic: send on closed channel")
            
            # Jika buffered dan penuh, atau unbuffered (cap=0) tanpa receiver
            while len(self.buffer) >= (self.capacity if self.capacity > 0 else 1) and not self.closed:
                self.lock.wait()

            if self.closed:
                raise GoChannelClosedException("panic: send on closed channel")

            self.buffer.append(value)
            self.lock.notify_all()

    def recv(self, gid: int) -> tuple[Any, bool]:
        """Terima data dari channel (mirip sintaks: val, ok := <-ch)."""
        with self.lock:
            while len(self.buffer) == 0 and not self.closed:
                self.lock.wait()

            if len(self.buffer) == 0 and self.closed:
                return None, False

            val = self.buffer.popleft()
            self.lock.notify_all()
            return val, True

    def close(self):
        """Tutup channel (mirip sintaks: close(ch))."""
        with self.lock:
            self.closed = True
            self.lock.notify_all()


@dataclass
class Goroutine:
    """Representasi 'G' dalam Go Runtime scheduler."""
    gid: int
    fn: Callable
    args: tuple = field(default_factory=tuple)
    state: str = "Gidle"  # Grunnable, Grunning, Gwaiting, Gdead


class Processor:
    """Representasi 'P' (Logical Processor / Execution Context)."""
    def __init__(self, pid: int, max_lq_len: int = 256):
        self.pid = pid
        self.local_queue: deque[Goroutine] = deque(maxlen=max_lq_len)
        self.sched_tick: int = 0
        self.lock = threading.Lock()


class GMPScheduler:
    """
    Simulasi Go GMP Scheduler:
    - GOMAXPROCS Logical Processors (P)
    - OS Threads (M)
    - Global Run Queue (GRQ) & Local Run Queues (LRQ)
    - Work-Stealing Algorithm saat LRQ kosong
    - 61-tick fairness rule untuk mencegah starvation pada GRQ
    """
    def __init__(self, gomaxprocs: int = 2):
        self.gomaxprocs = gomaxprocs
        self.processors = [Processor(pid=i) for i in range(gomaxprocs)]
        self.global_queue: deque[Goroutine] = deque()
        self.g_counter = 0
        self.g_lock = threading.Lock()
        self.running = True
        self.threads = []

    def spawn(self, fn: Callable, *args) -> int:
        """Membuat Goroutine baru (mirip sintaks: go func())."""
        with self.g_lock:
            self.g_counter += 1
            gid = self.g_counter

        g = Goroutine(gid=gid, fn=fn, args=args, state="Grunnable")
        
        # Masukkan ke Local Run Queue dari processor target secara Round-Robin
        target_p = self.processors[gid % self.gomaxprocs]
        with target_p.lock:
            if len(target_p.local_queue) < target_p.local_queue.maxlen:
                target_p.local_queue.append(g)
            else:
                # Jika LRQ penuh, kirim ke Global Run Queue
                self.global_queue.append(g)

        print(f"{CLR_DIM}[Runtime]{CLR_RESET} Spawned G#{g.gid} -> Dispatched to P#{target_p.pid}")
        return gid

    def _find_runnable(self, p: Processor) -> Optional[Goroutine]:
        """Algoritma runtime findrunnable(): P mencari G yang siap dieksekusi."""
        p.sched_tick += 1

        # Go Scheduler Rule: Setiap 61 tick, cek Global Queue demi fairness
        if p.sched_tick % 61 == 0 and self.global_queue:
            with self.g_lock:
                if self.global_queue:
                    g = self.global_queue.popleft()
                    return g

        # 1. Cek Local Run Queue sendiri
        with p.lock:
            if p.local_queue:
                return p.local_queue.popleft()

        # 2. Cek Global Run Queue
        with self.g_lock:
            if self.global_queue:
                return self.global_queue.popleft()

        # 3. Work-Stealing: Curi separuh task dari P lain
        other_processors = [other for other in self.processors if other.pid != p.pid]
        random.shuffle(other_processors)
        for victim in other_processors:
            with victim.lock:
                half = len(victim.local_queue) // 2
                if half > 0:
                    stolen = [victim.local_queue.popleft() for _ in range(half)]
                    with p.lock:
                        for g in stolen[1:]:
                            p.local_queue.append(g)
                    print(f"{CLR_MAGENTA}[Work-Steal]{CLR_RESET} P#{p.pid} mencuri {half} tasks dari P#{victim.pid}!")
                    return stolen[0]

        return None

    def _m_worker(self, m_id: int, p: Processor):
        """Loop eksekusi thread mesin OS (M) terikat ke Processor (P)."""
        while self.running:
            g = self._find_runnable(p)
            if g:
                g.state = "Grunning"
                try:
                    # Eksekusi fungsi Goroutine
                    g.fn(*g.args)
                except Exception as e:
                    print(f"{CLR_RED}[Panic] G#{g.gid} crash: {e}{CLR_RESET}")
                finally:
                    g.state = "Gdead"
            else:
                time.sleep(0.01)

    def start(self):
        """Membuka pool thread OS (M) sesuai GOMAXPROCS."""
        for p in self.processors:
            t = threading.Thread(target=self._m_worker, args=(p.pid, p), daemon=True)
            self.threads.append(t)
            t.start()
        print(f"{CLR_CYAN}{CLR_BOLD}[GMP Init]{CLR_RESET} Runtime berjalan: {self.gomaxprocs} Logical Processors (P) siap.")

    def stop(self):
        """Hentikan runtime scheduler."""
        self.running = False


# ==============================================================================
# Workload Simulasi: Producer-Consumer Pipeline Menggunakan CSP & Channels
# ==============================================================================

def worker_producer(ch: GoChannel, batch_size: int):
    """Goroutine Produsen: Memproduksi data dan mengirim lewat Channel."""
    for i in range(1, batch_size + 1):
        payload = f"packet-{i}"
        time.sleep(random.uniform(0.02, 0.05))
        ch.send(payload, gid=threading.get_native_id())
        print(f"  {CLR_GREEN}→ [Send]{CLR_RESET} {payload} terkirim ke channel.")
    ch.close()
    print(f"  {CLR_YELLOW}[Producer Done]{CLR_RESET} Channel ditutup secara aman.")


def worker_consumer(worker_id: int, ch: GoChannel, done_ch: GoChannel):
    """Goroutine Konsumen: Menerima data dari Channel (Multiplexing)."""
    while True:
        val, ok = ch.recv(gid=threading.get_native_id())
        if not ok:
            print(f"  {CLR_DIM}← [Recv]{CLR_RESET} Worker-{worker_id}: Channel drained (ok=false).")
            break
        print(f"  {CLR_CYAN}← [Recv]{CLR_RESET} Worker-{worker_id} memproses: {CLR_BOLD}{val}{CLR_RESET}")
        time.sleep(random.uniform(0.03, 0.06))
    done_ch.send(f"Worker-{worker_id}-finished", gid=threading.get_native_id())


def main():
    print(f"{CLR_BOLD}============================================================{CLR_RESET}")
    print(f"{CLR_BOLD} LAB HANDS-ON: GO RUNTIME (GMP & CSP CHANNELS) SIMULATION   {CLR_RESET}")
    print(f"{CLR_BOLD}============================================================{CLR_RESET}")

    # Set GOMAXPROCS = 2
    scheduler = GMPScheduler(gomaxprocs=2)
    scheduler.start()

    # Buat CSP Buffered Channel (Buffer size = 3) dan Done Channel
    data_stream = GoChannel(capacity=3)
    done_stream = GoChannel(capacity=2)

    total_items = 8
    num_consumers = 2

    print(f"\n{CLR_YELLOW}[Pipeline]{CLR_RESET} Menginisialisasi 1 Producer dan {num_consumers} Consumers...")
    # Spawn Producer Goroutine
    scheduler.spawn(worker_producer, data_stream, total_items)

    # Spawn Consumer Goroutines
    for c_id in range(1, num_consumers + 1):
        scheduler.spawn(worker_consumer, c_id, data_stream, done_stream)

    # Sinkronisasi Induk: Tunggu kedua consumer selesai via done_stream
    finished = 0
    while finished < num_consumers:
        msg, ok = done_stream.recv(gid=0)
        if ok:
            finished += 1
            print(f"{CLR_GREEN}✔ [Sync]{CLR_RESET} Notifikasi selesai: {msg} ({finished}/{num_consumers})")

    # Uji Skenario Work-Stealing Ekstrem
    print(f"\n{CLR_YELLOW}[Scheduler Test]{CLR_RESET} Membanjiri P0 untuk memicu Work-Stealing ke P1...")
    
    def compute_heavy(n):
        time.sleep(0.02)

    # Lempar 10 Goroutine instan
    for i in range(10):
        scheduler.spawn(compute_heavy, i)

    # Biarkan scheduler menyelesaikan task
    time.sleep(0.4)
    scheduler.stop()

    print(f"\n{CLR_BOLD}============================================================{CLR_RESET}")
    print(f"{CLR_GREEN}Lab Eksplorasi Go Runtime Selesai dengan Sukses.{CLR_RESET}")
    print(f"{CLR_BOLD}============================================================{CLR_RESET}")


if __name__ == "__main__":
    main()
docs/gcp/modules/09_module.md
# Modul 09: Identity and Security (IAM, Secrets, KMS)

## 1. Arsitektur IAM & Hierarki Resource Google Cloud
Model keamanan Google Cloud beroperasi berdasarkan prinsip **least privilege** yang terstruktur mengikuti hierarki resource:
```
Organization (example.com)
  └── Folder (Core-Engineering)
        └── Project (prod-microservices-101)
              └── Resource (GCS Bucket, Compute Instance, GKE Cluster)
```

Policy yang diterapkan pada node yang lebih tinggi diwariskan (**inherited**) ke seluruh resource di bawahnya secara mutlak. Suatu izin eksplisit di tingkat *Organization* tidak dapat dicabut (*override*) di tingkat *Project* atau *Resource*, melainkan bersifat *additive* (union dari seluruh policy yang berlaku).

### Struktur IAM Policy Binding
IAM Policy direpresentasikan dalam bentuk representasi JSON/YAML yang mengikat (`bindings`) himpunan **identitas** (`members`) dengan **Role** tertentu:
```json
{
  "bindings": [
    {
      "role": "roles/storage.objectViewer",
      "members": [
        "user:lead-dev@example.com",
        "serviceAccount:sa-data-pipeline@prod-microservices-101.iam.gserviceaccount.com"
      ],
      "condition": {
        "title": "Working Hours Only",
        "expression": "request.time.getHours('Asia/Jakarta') >= 9 && request.time.getHours('Asia/Jakarta') < 18"
      }
    }
  ],
  "etag": "BwW1d+qB+x0=",
  "version": 3
}
```

### Tipologi Identitas (Principal Types)
*   `user:` Alamat Google Workspace atau Gmail individual.
*   `serviceAccount:` Akun non-manusia yang digunakan oleh workload untuk melakukan autentikasi otomatis.
*   `group:` Google Group (`devops@example.com`). Penggunaan grup merupakan *best practice* untuk mempermudah onboarding/offboarding tanpa memodifikasi binding resource secara langsung.
*   `domain:` Seluruh entitas di dalam domain Google Workspace/Cloud Identity (`example.com`).

---

## 2. Service Accounts, Token Exchange, dan Workload Identity Federation

### Mekanisme Internal Autentikasi Service Account
Secara native, Service Account memiliki pasangan kunci publik/privat (Google-managed atau User-managed). 

Pada User-managed keys (JSON service account key file), workload menandatangani **JSON Web Signature (JWS)** secara lokal dan mengirimkannya ke endpoint token Google Cloud (`https://oauth2.googleapis.com/token`) untuk ditukarkan dengan **OAuth 2.0 Short-Lived Access Token** (masa aktif default: 3600 detik / 1 jam):

```mermaid
sequenceDiagram
    autonumber
    participant App as External Workload
    participant OAuth as Google OAuth 2.0 API
    participant Resource as Cloud Storage API
    
    App->>App: Buat & tanda tangani JWS (RS256) menggunakan Private Key
    App->>OAuth: POST /token (grant_type=assertion)
    OAuth->>OAuth: Validasi signature & izin Service Account
    OAuth-->>App: Return Short-lived Access Token (Bearer)
    App->>Resource: GET /b/my-bucket/o/data (Authorization: Bearer <token>)
    Resource-->>App: 200 OK (Data Stream)
```

> **Security Alert:** User-managed Service Account Key files merupakan vektor kebocoran kredensial paling rentan (sering terunggah ke repo publik atau hardcoded pada CI/CD). Hindari penggunaan key file ini pada infrastruktur modern.

### Workload Identity Federation (WIF)
Workload Identity Federation mengeliminasi kebutuhan service account key file untuk workload yang berjalan di luar Google Cloud (GitHub Actions, AWS, Azure, on-premises k8s):

```mermaid
sequenceDiagram
    autonumber
    participant GH as GitHub Actions CI
    participant STS as GCP Security Token Service (STS)
    participant IAM as GCP Cloud IAM (Service Account)
    participant API as GCP Target API
    
    GH->>GH: Eksekusi job & minta OpenID Connect (OIDC) Token dari GitHub OIDC Provider
    GH->>STS: POST /v1/token (Tukar GitHub OIDC Token dengan GCP Federated Token)
    STS->>STS: Validasi Issuer, Audience, & Claim Mapping
    STS-->>GH: Return Federated Access Token (Federated Principal)
    GH->>IAM: POST generateAccessToken (Assume GCP Service Account via Federated Token)
    IAM-->>GH: Return Short-Lived GCP Access Token (Lifetime: 15-60m)
    GH->>API: Akses API (Cloud Storage, Deploy Cloud Run, dll)
```

#### Alur Pertukaran Token WIF:
1. Workload eksternal (misal: GitHub Actions) meminta OIDC token ke penyedianya sendiri (`id.token` dari GitHub OIDC).
2. OIDC token dikirimkan ke **Security Token Service (STS)** Google Cloud.
3. STS memvalidasi OIDC token via endpoint `.well-known/openid-configuration` milik eksternal provider.
4. STS mengonversi token eksternal menjadi Google Federated Token.
5. Workload memanggil `iamcredentials.googleapis.com:generateAccessToken` untuk meng-impersonasi Service Account GCP target, menggunakan izin `roles/iam.workloadIdentityUser`.

---

## 3. Secret Manager vs Cloud KMS: Perbandingan Teknis Mendalam

| Dimensi Arsitektur | Google Secret Manager | Cloud Key Management Service (KMS) |
| :--- | :--- | :--- |
| **Tujuan Utama** | Penyimpanan, versioning, dan retrieval data sensitif teks/biner berukuran kecil (< 64 KiB). | Manajemen siklus hidup cryptographic keys untuk enkripsi/dekripsi data (Envelope Encryption). |
| **Payload yang Ditangani** | String/binary langsung (DB Passwords, API Keys, TLS Private Keys). | Plaintext yang akan dienkripsi / Ciphertext yang didekripsi; KMS *tidak menyimpan* data Anda. |
| **Audit Trails** | Mencatat setiap pemanggilan `AccessSecretVersion` via Cloud Audit Logs. | Mencatat setiap operasi kriptografis (`Encrypt`, `Decrypt`, `AsymmetricSign`) via Cloud Audit Logs. |
| **Batas Ukuran** | Maksimal 64 KiB per secret version. | Enkripsi langsung maksimal 64 KiB (direkomendasikan untuk Data Encryption Keys (DEK)). |
| **Rotasi Otomatis** | Mendukung jadwal rotasi yang mengirim notifikasi via Pub/Sub ke Cloud Functions/Cloud Run. | Rotasi otomatis terjadwal untuk symmetric keys secara internal (key versioning otomatis). |
| **Hardware Security Module** | Penyimpanan software-encrypted secara default (dapat di-backing oleh CMEK KMS). | Mendukung level Software, Cloud HSM (FIPS 140-2 Level 3), dan External Key Manager (EKM). |

---

## 4. Mekanisme Envelope Encryption dengan Cloud KMS
Ketika Anda harus mengenkripsi payload berukuran besar (misal: file 100 GB pada disk atau database), mengenkripsi data tersebut secara langsung melalui KMS API tidak efisien dan melanggar throughput quota. Pola yang digunakan adalah **Envelope Encryption**:

```mermaid
graph TD
    subgraph Data Layer
        P[Plaintext Data]
        DEK[Local DEK: AES-256 Bit Key]
        ENC_DATA[Encrypted Data Block]
    end
    
    subgraph Google Cloud KMS
        KEK[Key Encryption Key: KEK]
    end
    
    subgraph Encrypted Envelope on Disk
        ENC_DEK[Encrypted DEK]
        STORED_ENC[Stored Encrypted Data]
    end

    %% Enkripsi Data
    DEK -->|1. Enkripsi secara lokal| P
    P -->|Hasil Enkripsi| ENC_DATA
    ENC_DATA --> STORED_ENC

    %% Enkripsi Kunci
    DEK -->|2. Kirim Plaintext DEK via gRPC| KEK
    KEK -->|3. Enkripsi DEK menggunakan KEK| KEK
    KEK -->|4. Return Encrypted DEK| ENC_DEK
```

### Prosedur Dekripsi:
1. Workload membaca `Encrypted DEK` dan `Stored Encrypted Data` dari storage.
2. Workload mengirimkan `Encrypted DEK` ke Cloud KMS API (`projects/.../cryptoKeys/...:decrypt`).
3. Cloud KMS membuka dekripsi `Encrypted DEK` menggunakan **KEK** (yang tidak pernah meninggalkan KMS HSM boundary) dan mengembalikan **Plaintext DEK**.
4. Workload menggunakan `Plaintext DEK` untuk mendekripsi data secara lokal di RAM, kemudian segera menghapus Plaintext DEK dari memori.

---

## 5. Implementasi CLI: End-to-End IAM, Secrets, dan KMS

Jalankan perintah berikut pada terminal Cloud Shell atau terminal lokal dengan autentikasi `gcloud`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Definisi Environment Variable
export PROJECT_ID=$(gcloud config get-value project)
export REGION="asia-southeast2"
export SA_NAME="sa-app-backend"
export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
export KEYRING_NAME="app-security-keyring"
export KMS_KEY_NAME="envelope-kek"
export SECRET_NAME="database-master-credentials"

echo "Configuring Project: ${PROJECT_ID} in ${REGION}"

# 2. Pembuatan Dedicated Service Account
gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="App Backend Microservice SA" \
    --description="Digunakan oleh internal engine untuk dekripsi KMS dan pembacaan Secrets"

# 3. Setup Cloud KMS (KeyRing dan Key KEK)
gcloud kms keyrings create "${KEYRING_NAME}" \
    --location="${REGION}"

gcloud kms keys create "${KMS_KEY_NAME}" \
    --keyring="${KEYRING_NAME}" \
    --location="${REGION}" \
    --purpose="encryption" \
    --rotation-period="7776000s" \
    --next-rotation-time="$(date -u -v+90d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '+90 days' +%Y-%m-%dT%H:%M:%SZ)"

# 4. Setup Secret Manager
gcloud secrets create "${SECRET_NAME}" \
    --replication-policy="automatic"

echo -n "SuperSecretDBPassword_$(openssl rand -hex 16)" | \
    gcloud secrets versions add "${SECRET_NAME}" --data-file=-

# 5. Konfigurasi Granular IAM Roles (Least Privilege)
# Service Account HANYA dapat membaca secret version tersebut (Secret Accessor)
gcloud secrets add-iam-policy-binding "${SECRET_NAME}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None

# Service Account HANYA dapat melakukan dekripsi menggunakan KMS Key (CryptoKey Decrypter)
gcloud kms keys add-iam-policy-binding "${KMS_KEY_NAME}" \
    --keyring="${KEYRING_NAME}" \
    --location="${REGION}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/cloudkms.cryptoKeyDecrypter"

echo "Konfigurasi IAM, KMS, dan Secret Manager selesai."
```

---

## 6. Hands-On Lab: Python Engine untuk KMS Envelope Encryption & Secret Resolution

Lab hands-on berikut mengimplementasikan proses runtime:
1. Melakukan autentikasi menggunakan Application Default Credentials (ADC) atau Service Account Impersonation.
2. Mengambil database credentials secara real-time dari Secret Manager.
3. Melakukan **Envelope Encryption** pada file data lokal:
   - Membuat symmetric Data Encryption Key (DEK) 256-bit secara lokal menggunakan `cryptography.hazmat`.
   - Mengenkripsi DEK menggunakan Google Cloud KMS (KEK).
   - Mengenkripsi file payload menggunakan DEK terenkripsi (AES-256-GCM).
   - Mendekripsi envelope kembali menjadi plaintext untuk verifikasi integritas cryptographic hash.

### Setup Dependensi Lingkungan
```bash
pip install google-cloud-secretmanager google-cloud-kms cryptography
```

### Eksekusi Kode (`secure_runtime.py`)
#!/usr/bin/env python3
"""
Modul 09: Identity and Security Lab
Mengimplementasikan Secret Manager retrieval dan Envelope Encryption dengan Cloud KMS.
"""

import os
import sys
import base64
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from google.cloud import secretmanager_v1 as secretmanager
from google.cloud import kms_v1 as kms

# Konfigurasi Parameter
PROJECT_ID = os.getenv("PROJECT_ID", "my-gcp-project-id")
LOCATION = "asia-southeast2"
KEYRING_NAME = "app-security-keyring"
KEY_NAME = "envelope-kek"
SECRET_ID = "database-master-credentials"


def fetch_secret(project_id: str, secret_id: str, version: str = "latest") -> str:
    """Mengambil plaintext secret dari Google Secret Manager."""
    print(f"[*] Mengambil secret: {secret_id} (versi: {version})...")
    client = secretmanager.SecretManagerServiceClient()
    secret_path = client.secret_version_path(project_id, secret_id, version)

    try:
        response = client.access_secret_version(name=secret_path)
        payload = response.payload.data.decode("UTF-8")
        print(f"[+] Secret berhasil diambil via Secret Manager.")
        return payload
    except Exception as e:
        print(f"[-] Gagal mengambil secret: {e}", file=sys.stderr)
        raise


class KMSEnvelopeEngine:
    """Mesin Envelope Encryption menggunakan Cloud KMS KEK dan AES-GCM-256 Local DEK."""

    def __init__(self, project_id: str, location: str, keyring: str, key_name: str):
        self.kms_client = kms.KeyManagementServiceClient()
        self.key_path = self.kms_client.crypto_key_path(project_id, location, keyring, key_name)

    def encrypt_data(self, plaintext_bytes: bytes) -> tuple[bytes, bytes, bytes]:
        """
        1. Generate DEK 256-bit lokal.
        2. Enkripsi plaintext_bytes dengan DEK menggunakan AES-GCM.
        3. Enkripsi DEK menggunakan KMS KEK.
        
        Return: (encrypted_dek, iv/nonce, ciphertext)
        """
        print("[*] Memulai Envelope Encryption...")
        
        # 1. Generate Plaintext DEK lokal (AES-256 = 32 bytes)
        dek_plaintext = AESGCM.generate_key(bit_length=256)
        
        # 2. Enkripsi Data Payload dengan Plaintext DEK
        aesgcm = AESGCM(dek_plaintext)
        nonce = os.urandom(12)  # Standard 96-bit nonce untuk AES-GCM
        ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, None)
        print(f"[+] Payload terenkripsi secara lokal ({len(ciphertext)} bytes).")

        # 3. Enkripsi DEK dengan Cloud KMS KEK
        kms_response = self.kms_client.encrypt(
            request={
                "name": self.key_path,
                "plaintext": dek_plaintext
            }
        )
        encrypted_dek = kms_response.ciphertext
        print(f"[+] DEK berhasil diamankan oleh Cloud KMS ({len(encrypted_dek)} bytes).")

        # Zeroize Plaintext DEK dari memori
        dek_plaintext = b"\x00" * 32
        del dek_plaintext

        return encrypted_dek, nonce, ciphertext

    def decrypt_data(self, encrypted_dek: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
        """
        1. Dekripsi encrypted_dek via Cloud KMS KEK.
        2. Dekripsi ciphertext lokal menggunakan DEK yang didapat.
        """
        print("[*] Memulai Envelope Decryption...")

        # 1. Dekripsi DEK via Cloud KMS
        kms_response = self.kms_client.decrypt(
            request={
                "name": self.key_path,
                "ciphertext": encrypted_dek
            }
        )
        decrypted_dek = kms_response.plaintext
        print("[+] DEK berhasil didekripsi oleh Cloud KMS.")

        # 2. Dekripsi Payload lokal menggunakan decrypted_dek
        aesgcm = AESGCM(decrypted_dek)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        print("[+] Payload berhasil dikembalikan ke plaintext.")

        # Zeroize decrypted DEK
        decrypted_dek = b"\x00" * 32
        del decrypted_dek

        return plaintext


def main():
    if PROJECT_ID == "my-gcp-project-id":
        print("[-] Set environment variable PROJECT_ID sebelum menjalankan skrip.", file=sys.stderr)
        sys.exit(1)

    # 1. Eksekusi Pengambilan Secret
    try:
        db_credential = fetch_secret(PROJECT_ID, SECRET_ID)
        # Menghindari print raw password, cetak hash untuk validasi integritas
        cred_hash = hashlib.sha256(db_credential.encode()).hexdigest()
        print(f"[*] Validasi Secret SHA-256: {cred_hash}")
    except Exception:
        print("[-] Lewati pengambilan secret, pastikan resource sudah dibuat via CLI.")

    # 2. Eksekusi Envelope Encryption
    envelope = KMSEnvelopeEngine(PROJECT_ID, LOCATION, KEYRING_NAME, KEY_NAME)

    raw_payload = b"CRITICAL_FINANCIAL_TRANSACTION_PAYLOAD_DETERMINISTIC_VERIFICATION"
    print(f"[*] Raw Payload: {raw_payload.decode()}")

    # Enkripsi
    encrypted_dek, nonce, ciphertext = envelope.encrypt_data(raw_payload)
    print(f"[*] Encrypted Payload (Hex): {ciphertext.hex()[:64]}...")
    print(f"[*] Encrypted DEK (Base64): {base64.b64encode(encrypted_dek).decode()[:32]}...")

    # Dekripsi
    decrypted_payload = envelope.decrypt_data(encrypted_dek, nonce, ciphertext)
    print(f"[+] Decrypted Payload: {decrypted_payload.decode()}")

    # Audit Check
    assert decrypted_payload == raw_payload, "Kriptografis Gagal: Integritas payload tidak cocok!"
    print("[SUCCESS] Verifikasi Integritas Envelope Encryption Berhasil 100%.")


if __name__ == "__main__":
    main()
```

---

## 7. Verifikasi dan Audit Keamanan

### Verifikasi Audit Log Akses Secret dan KMS
Setiap kali Service Account mengakses Secret Manager atau memanggil operasi dekripsi KMS, Google Cloud merekam aktivitas tersebut pada **Cloud Audit Logs (Data Access Logs)**.

Jalankan filter audit berikut untuk memeriksa jejak forensik:
```bash
gcloud logging read '
  resource.type=("cloudkms_cryptokey" OR "secretmanager.googleapis.com/Secret")
  AND protoPayload.authenticationInfo.principalEmail="'"${SA_EMAIL}"'"
' --limit=10 --format="table(timestamp, protoPayload.methodName, protoPayload.resourceName)"
```

Output yang diharapkan mencerminkan pemanggilan API secara transparan:
```
TIMESTAMP                METHOD_NAME                               RESOURCE_NAME
2023-10-27T10:15:32.00Z  AccessSecretVersion                       projects/.../secrets/database-master-credentials/versions/latest
2023-10-27T10:15:35.00Z  cloudkms.v1.KeyManagementService.Decrypt  projects/.../locations/asia-southeast2/keyRings/.../cryptoKeys/envelope-kek
```

---

## 8. Best Practices Checklist untuk Production

1. **Prinsip Non-Privileged Default**:
   - Nonaktifkan pembuatan otomatis Default Compute Service Account dengan hak `Editor` melalui Organization Policy: `constraints/compute.defaultServiceAccount = DENIED`.
2. **Key Rotation & Lifecycle Policy**:
   - Wajibkan rotasi kunci KMS otomatis setiap 90 hari.
   - Jangan pernah menghapus Key Ring/Key (KMS keys bersifat immutable dan tidak dapat dihapus, hanya dapat di-*destroy* versinya untuk mencegah insiden data tak terpulihkan).
3. **Secret Immutability & Audit**:
   - Konfigurasi Secret Manager payload destruction scheduling jika secret memiliki masa berlaku terbatas.
   - Aktifkan `DATA_READ` dan `DATA_WRITE` Audit Logging pada Secret Manager dan KMS API (secara default `DATA_READ` dinonaktifkan untuk menghemat biaya logging).
4. **Zero User-Managed SA Keys**:
   - Terapkan Organization Policy `constraints/iam.disableServiceAccountKeyCreation` untuk memblokir pembuatan file JSON SA Key di seluruh organisasi.
   - Migrasikan seluruh workload hybrid/multi-cloud ke **Workload Identity Federation**.

---

## 9. Pembersihan Resource (Clean-up)

Hapus resource yang telah dibuat untuk menghindari pembengkakan biaya cloud:

```bash
# 1. Hapus Secret Manager Secret
gcloud secrets delete "${SECRET_NAME}" --quiet

# 2. Hancurkan versi KMS Key (Catatan: KeyRing dan Key metadata tetap ada namun versi tidak aktif)
gcloud kms keys versions destroy 1 \
    --key="${KMS_KEY_NAME}" \
    --keyring="${KEYRING_NAME}" \
    --location="${REGION}" --quiet

# 3. Hapus Service Account
gcloud iam service-accounts delete "${SA_EMAIL}" --quiet

echo "Pembersihan resource selesai."
```

---

## 10. Referensi Tambahan
*   [Google Cloud IAM Conditions Documentation](https://cloud.google.com/iam/docs/conditions-overview)
*   [Workload Identity Federation with GitHub Actions](https://cloud.google.com/iam/docs/workload-identity-federation-with-other-providers)
*   [Cloud KMS Envelope Encryption Pattern](https://cloud.google.com/kms/docs/envelope-encryption)
*   [Secret Manager Best Practices](https://cloud.google.com/secret-manager/docs/best-practices)
<!-- GITHUB_LAB_PREVIEW_START -->
## Hands-on Lab: GCP Identity, IAM, Secrets & Envelope KMS Engine

Script lab mandiri untuk menguji konsep pada modul ini dapat ditemukan di repositori GitHub:

- **File:** `labs/gcp/09_module.py`
- **Format:** Python 3 (Executable & Self-contained)

### Cara Menjalankan:
```bash
python3 labs/gcp/09_module.py
```
<!-- GITHUB_LAB_PREVIEW_END -->
labs/ansible/01_module.py

        print(f"Task: {task.name}")
        for host in hosts:
            res = self.execute_task_on_host(host, task)
            host_results[host.name].append(res)
            
            # Print execution result
            if res.failed:
                status_str = f"{ANSI_RED}FAILED{ANSI_RESET}"
            elif res.changed:
                status_str = f"{ANSI_YELLOW}CHANGED{ANSI_RESET}"
            else:
                status_str = f"{ANSI_GREEN}OK{ANSI_RESET}"
            
            msg = res.diff.get("msg", "")
            print(f"  [{host.name}] => {status_str}: {msg}")

        # Summary of the play
        print(f"\n{ANSI_BOLD}PLAY RECAP *********************************************************************{ANSI_RESET}")
        for host in hosts:
            res_list = host_results[host.name]
            ok_cnt = sum(1 for r in res_list if not r.failed and not r.changed)
            chg_cnt = sum(1 for r in res_list if r.changed and not r.failed)
            fail_cnt = sum(1 for r in res_list if r.failed)
            
            recap_str = f"ok={ok_cnt}    changed={chg_cnt}    failed={fail_cnt}"
            color = ANSI_RED if fail_cnt > 0 else (ANSI_YELLOW if chg_cnt > 0 else ANSI_GREEN)
            print(f"{host.name.ljust(20)} : {color}{recap_str}{ANSI_RESET}")


# ==============================================================================
# Skenario Demonstrasi Idempotensi dan State Convergence
# ==============================================================================
def main():
    print(f"{ANSI_BOLD}{ANSI_CYAN}=== ANSIBLE ARCHITECTURE & IDEMPOTENCY ENGINE DEMO ==={ANSI_RESET}\n")

    # 1. Setup Inventory
    inventory = Inventory()
    inventory.add_host("web-prod-01.internal", "webservers", {
        "installed_packages": {"bash": "5.1", "curl": "7.81"},
        "files": {
            "/etc/motd": {
                "content": "Old message of the day",
                "checksum": hashlib.sha256(b"Old message of the day").hexdigest(),
                "owner": "root",
                "mode": "0644"
            }
        },
        "services": {
            "nginx": {"state": "stopped"}
        }
    })
    inventory.add_host("web-prod-02.internal", "webservers", {
        "installed_packages": {"bash": "5.1", "nginx": "1.18.0"},
        "files": {
            "/etc/motd": {
                "content": "Welcome to Production Web Server!\n",
                "checksum": hashlib.sha256(b"Welcome to Production Web Server!\n").hexdigest(),
                "owner": "root",
                "mode": "0644"
            }
        },
        "services": {
            "nginx": {"state": "running"}
        }
    })

    # 2. Definisikan Tasks Playbook
    motd_content = "Welcome to Production Web Server!\n"
    tasks = [
        Task(
            name="Ensure nginx package is installed",
            module="package",
            args={"name": "nginx", "state": "present"}
        ),
        Task(
            name="Deploy standard /etc/motd configuration",
            module="copy",
            args={
                "dest": "/etc/motd",
                "content": motd_content,
                "owner": "root",
                "mode": "0644"
            }
        ),
        Task(
            name="Ensure nginx service is actively running",
            module="service",
            args={"name": "nginx", "state": "started"}
        )
    ]

    engine = PlaybookEngine(inventory)

    # 3. Jalankan Eksekusi Pertama (State Drift Convergence)
    print(f"{ANSI_CYAN}--> TAHAP 1: Eksekusi Playbook Pertama (Konvergensi Desired State){ANSI_RESET}")
    engine.run_play("webservers", tasks)

    # 4. Jalankan Eksekusi Kedua (Uji Idempotensi)
    print(f"\n{ANSI_CYAN}--> TAHAP 2: Eksekusi Playbook Kedua (Verifikasi Idempotensi - Harus 0 Changed){ANSI_RESET}")
    engine.run_play("webservers", tasks)

    print(f"\n{ANSI_GREEN}{ANSI_BOLD}Simulasi selesai: Konsep declarative architecture dan idempotency berhasil divalidasi.{ANSI_RESET}")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Ansible Architecture & Idempotency Simulation Engine
Lab Hands-on: Bab 01 - Modul 01: Architecture, Inventory, and Concepts
Kategori: 07-DevOps-IaC

Script ini memodelkan cara kerja inti Ansible Engine tanpa dependensi eksternal:
- Dynamic/Static Inventory parsing dan grouping.
- Task execution loop berbasis module abstraction.
- Sifat Idempotensi: Membandingkan 'Current State' vs 'Desired State'.
- Status pelaporan standar Ansible: OK (hijau), CHANGED (kuning), FAILED (merah).
"""

import sys
import json
import hashlib
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

# ANSI Colors untuk representasi output persis Ansible CLI
ANSI_RESET = "\033[0m"
ANSI_RED = "\033[31m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_CYAN = "\033[36m"
ANSI_BOLD = "\033[1m"


# ==============================================================================
# Model Domain Data
# ==============================================================================
@dataclass
class Host:
    name: str
    groups: List[str] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    # State internal host (simulasi memory target node)
    system_state: Dict[str, Any] = field(default_factory=lambda: {
        "installed_packages": {},
        "files": {},
        "services": {}
    })


@dataclass
class Task:
    name: str
    module: str
    args: Dict[str, Any]


@dataclass
class TaskResult:
    host: str
    changed: bool
    failed: bool
    diff: Dict[str, Any]
    invocation: Dict[str, Any]


# ==============================================================================
# Simulasi Inventory Engine
# ==============================================================================
class Inventory:
    """Mengelola kumpulan host dan group."""
    def __init__(self):
        self.hosts: Dict[str, Host] = {}
        self.groups: Dict[str, List[str]] = {"all": []}

    def add_host(self, host_name: str, group: str = "all", initial_state: Optional[Dict] = None):
        if host_name not in self.hosts:
            h = Host(name=host_name)
            if initial_state:
                h.system_state.update(initial_state)
            self.hosts[host_name] = h

        if group not in self.groups:
            self.groups[group] = []
        if host_name not in self.groups[group]:
            self.groups[group].append(host_name)
        if host_name not in self.groups["all"]:
            self.groups["all"].append(host_name)

    def get_hosts_for_pattern(self, pattern: str) -> List[Host]:
        if pattern == "all":
            return list(self.hosts.values())
        if pattern in self.groups:
            return [self.hosts[h] for h in self.groups[pattern]]
        if pattern in self.hosts:
            return [self.hosts[pattern]]
        return []


# ==============================================================================
# Ansible Core Modules Mock (Prinsip Idempotensi)
# ==============================================================================
class ModuleExecutor:
    """
    Mengimplementasikan logika state-checking sebelum menerapkan perubahan
    (Declarative vs Imperative).
    """

    @staticmethod
    def module_package(host: Host, args: Dict[str, Any]) -> TaskResult:
        pkg_name = args.get("name")
        desired_state = args.get("state", "present")
        installed = host.system_state["installed_packages"]

        is_installed = pkg_name in installed

        if desired_state == "present":
            if is_installed:
                # State sudah sesuai, tidak ada perubahan (OK)
                return TaskResult(host.name, changed=False, failed=False, diff={}, invocation=args)
            else:
                # State berubah: Install package (CHANGED)
                installed[pkg_name] = "1.0.0"
                return TaskResult(
                    host.name, changed=True, failed=False,
                    diff={"before": "absent", "after": "installed version 1.0.0"},
                    invocation=args
                )
        elif desired_state == "absent":
            if not is_installed:
                return TaskResult(host.name, changed=False, failed=False, diff={}, invocation=args)
            else:
                del installed[pkg_name]
                return TaskResult(
                    host.name, changed=True, failed=False,
                    diff={"before": "installed", "after": "absent"},
                    invocation=args
                )

        return TaskResult(host.name, changed=False, failed=True, diff={"error": f"Invalid state: {desired_state}"}, invocation=args)

    @staticmethod
    def module_copy(host: Host, args: Dict[str, Any]) -> TaskResult:
        dest = args.get("dest")
        content = args.get("content", "")
        owner = args.get("owner", "root")
        mode = args.get("mode", "0644")

        new_checksum = hashlib.sha256(content.encode()).hexdigest()
        files = host.system_state["files"]

        if dest in files:
            current = files[dest]
            # Bandingkan metadata & content checksum
            if current["checksum"] == new_checksum and current["owner"] == owner and current["mode"] == mode:
                return TaskResult(host.name, changed=False, failed=False, diff={}, invocation=args)

        # File belum ada atau checksum/metadata berbeda
        files[dest] = {
            "content": content,
            "checksum": new_checksum,
            "owner": owner,
            "mode": mode
        }
        return TaskResult(
            host.name, changed=True, failed=False,
            diff={"path": dest, "action": "updated/created", "checksum": new_checksum[:8]},
            invocation=args
        )

    @staticmethod
    def module_service(host: Host, args: Dict[str, Any]) -> TaskResult:
        service_name = args.get("name")
        desired_state = args.get("state", "started")
        services = host.system_state["services"]

        current_state = services.get(service_name, {}).get("state", "stopped")

        if current_state == desired_state:
            return TaskResult(host.name, changed=False, failed=False, diff={}, invocation=args)

        services[service_name] = {"state": desired_state}
        return TaskResult(
            host.name, changed=True, failed=False,
            diff={"service": service_name, "before": current_state, "after": desired_state},
            invocation=args
        )


# ==============================================================================
# Playbook Execution Engine
# ==============================================================================
class PlaybookEngine:
    def __init__(self, inventory: Inventory):
        self.inventory = inventory
        self.modules = {
            "package": ModuleExecutor.module_package,
            "copy": ModuleExecutor.module_copy,
            "service": ModuleExecutor.module_service
        }

    def execute_task_on_host(self, host: Host, task: Task) -> TaskResult:
        module_func = self.modules.get(task.module)
        if not module_func:
            return TaskResult(host.name, changed=False, failed=True, diff={"error": f"Module {task.module} not found"}, invocation=task.args)
        return module_func(host, task.args)

    def run_play(self, target_pattern: str, tasks: List[Task]):
        hosts = self.inventory.get_hosts_for_pattern(target_pattern)
        print(f"\n{ANSI_BOLD}PLAY [{target_pattern}] ********************************************************************{ANSI_RESET}")
        
        host_results: Dict[str, List[TaskResult]] = {h.name: [] for h in hosts}

        for task in tasks:
            print(f"\n{ANSI_BOLD}TASK [{task.name}] ***************************************************************{ANSI_RESET}")
            for host in hosts:
                res = self.execute_task_on_host(host, task)
                host_results[host.name].append(res)
                
                # Print execution result
                if res.failed:
                    status_str = f"{ANSI_RED}FAILED{ANSI_RESET}"
                elif res.changed:
                    status_str = f"{ANSI_YELLOW}CHANGED{ANSI_RESET}"
                else:
                    status_str = f"{ANSI_GREEN}OK{ANSI_RESET}"
                
                print(f"{status_str}: [{host.name}] => {json.dumps(res.diff) if res.diff else 'state converged'}")

        # Summary of the play
        print(f"\n{ANSI_BOLD}PLAY RECAP *********************************************************************{ANSI_RESET}")
        for host in hosts:
            res_list = host_results[host.name]
            ok_cnt = sum(1 for r in res_list if not r.failed and not r.changed)
            chg_cnt = sum(1 for r in res_list if r.changed and not r.failed)
            fail_cnt = sum(1 for r in res_list if r.failed)
            
            recap_str = f"ok={ok_cnt}    changed={chg_cnt}    failed={fail_cnt}"
            color = ANSI_RED if fail_cnt > 0 else (ANSI_YELLOW if chg_cnt > 0 else ANSI_GREEN)
            print(f"{host.name.ljust(20)} : {color}{recap_str}{ANSI_RESET}")


# ==============================================================================
# Skenario Demonstrasi Idempotensi dan State Convergence
# ==============================================================================
def main():
    print(f"{ANSI_BOLD}{ANSI_CYAN}=== ANSIBLE ARCHITECTURE & IDEMPOTENCY ENGINE DEMO ==={ANSI_RESET}\n")

    # 1. Setup Inventory
    inventory = Inventory()
    inventory.add_host("web-prod-01.internal", "webservers", {
        "installed_packages": {"bash": "5.1", "curl": "7.81"},
        "files": {
            "/etc/motd": {
                "content": "Old message of the day",
                "checksum": hashlib.sha256(b"Old message of the day").hexdigest(),
                "owner": "root",
                "mode": "0644"
            }
        },
        "services": {
            "nginx": {"state": "stopped"}
        }
    })
    inventory.add_host("web-prod-02.internal", "webservers", {
        "installed_packages": {"bash": "5.1", "nginx": "1.18.0"},
        "files": {
            "/etc/motd": {
                "content": "Welcome to Production Web Server!\n",
                "checksum": hashlib.sha256(b"Welcome to Production Web Server!\n").hexdigest(),
                "owner": "root",
                "mode": "0644"
            }
        },
        "services": {
            "nginx": {"state": "running"}
        }
    })

    # 2. Definisikan Tasks Playbook
    motd_content = "Welcome to Production Web Server!\n"
    tasks = [
        Task(
            name="Ensure nginx package is installed",
            module="package",
            args={"name": "nginx", "state": "present"}
        ),
        Task(
            name="Deploy standard /etc/motd configuration",
            module="copy",
            args={
                "dest": "/etc/motd",
                "content": motd_content,
                "owner": "root",
                "mode": "0644"
            }
        ),
        Task(
            name="Ensure nginx service is actively running",
            module="service",
            args={"name": "nginx", "state": "started"}
        )
    ]

    engine = PlaybookEngine(inventory)

    # 3. Jalankan Eksekusi Pertama (State Drift Convergence)
    print(f"{ANSI_CYAN}--> TAHAP 1: Eksekusi Playbook Pertama (Konvergensi Desired State){ANSI_RESET}")
    engine.run_play("webservers", tasks)

    # 4. Jalankan Eksekusi Kedua (Uji Idempotensi)
    print(f"\n{ANSI_CYAN}--> TAHAP 2: Eksekusi Playbook Kedua (Verifikasi Idempotensi - Harus 0 Changed){ANSI_RESET}")
    engine.run_play("webservers", tasks)

    print(f"\n{ANSI_GREEN}{ANSI_BOLD}Simulasi selesai: Konsep declarative architecture dan idempotency berhasil divalidasi.{ANSI_RESET}")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Ansible Architecture & Idempotency Simulation Engine
Lab Hands-on: Bab 01 - Modul 01: Architecture, Inventory, and Concepts
Kategori: 07-DevOps-IaC

Script ini memodelkan cara kerja inti Ansible Engine tanpa dependensi eksternal:
- Dynamic/Static Inventory parsing dan grouping.
- Task execution loop berbasis module abstraction.
- Sifat Idempotensi: Membandingkan 'Current State' vs 'Desired State'.
- Status pelaporan standar Ansible: OK (hijau), CHANGED (kuning), FAILED (merah).
"""

import sys
import json
import hashlib
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

# ANSI Colors untuk representasi output persis Ansible CLI
ANSI_RESET = "\033[0m"
ANSI_RED = "\033[31m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_CYAN = "\033[36m"
ANSI_BOLD = "\033[1m"


# ==============================================================================
# Model Domain Data
# ==============================================================================
@dataclass
class Host:
    name: str
    groups: List[str] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    # State internal host (simulasi memory target node)
    system_state: Dict[str, Any] = field(default_factory=lambda: {
        "installed_packages": {},
        "files": {},
        "services": {}
    })


@dataclass
class Task:
    name: str
    module: str
    args: Dict[str, Any]


@dataclass
class TaskResult:
    host: str
    changed: bool
    failed: bool
    diff: Dict[str, Any]
    invocation: Dict[str, Any]


# ==============================================================================
# Simulasi Inventory Engine
# ==============================================================================
class Inventory:
    """Mengelola kumpulan host dan group."""
    def __init__(self):
        self.hosts: Dict[str, Host] = {}
        self.groups: Dict[str, List[str]] = {"all": []}

    def add_host(self, host_name: str, group: str = "all", initial_state: Optional[Dict] = None):
        if host_name not in self.hosts:
            h = Host(name=host_name)
            if initial_state:
                h.system_state.update(initial_state)
            self.hosts[host_name] = h

        if group not in self.groups:
            self.groups[group] = []
        if host_name not in self.groups[group]:
            self.groups[group].append(host_name)
        if host_name not in self.groups["all"]:
            self.groups["all"].append(host_name)

    def get_hosts_for_pattern(self, pattern: str) -> List[Host]:
        if pattern == "all":
            return list(self.hosts.values())
        if pattern in self.groups:
            return [self.hosts[h] for h in self.groups[pattern]]
        if pattern in self.hosts:
            return [self.hosts[pattern]]
        return []


# ==============================================================================
# Ansible Core Modules Mock (Prinsip Idempotensi)
# ==============================================================================
class ModuleExecutor:
    """
    Mengimplementasikan logika state-checking sebelum menerapkan perubahan
    (Declarative vs Imperative).
    """

    @staticmethod
    def module_package(host: Host, args: Dict[str, Any]) -> TaskResult:
        pkg_name = args.get("name")
        desired_state = args.get("state", "present")
        installed = host.system_state["installed_packages"]

        is_installed = pkg_name in installed

        if desired_state == "present":
            if is_installed:
                # State sudah sesuai, tidak ada perubahan (OK)
                return TaskResult(host.name, changed=False, failed=False, diff={"msg": f"Package {pkg_name} already present"}, invocation=args)
            else:
                # State berubah: Install package (CHANGED)
                installed[pkg_name] = "1.0.0"
                return TaskResult(
                    host.name, changed=True, failed=False,
                    diff={"msg": f"Package {pkg_name} installed (1.0.0)"},
                    invocation=args
                )
        elif desired_state == "absent":
            if not is_installed:
                return TaskResult(host.name, changed=False, failed=False, diff={"msg": f"Package {pkg_name} already absent"}, invocation=args)
            else:
                del installed[pkg_name]
                return TaskResult(
                    host.name, changed=True, failed=False,
                    diff={"msg": f"Package {pkg_name} removed"},
                    invocation=args
                )

        return TaskResult(host.name, changed=False, failed=True, diff={"msg": f"Invalid state: {desired_state}"}, invocation=args)

    @staticmethod
    def module_copy(host: Host, args: Dict[str, Any]) -> TaskResult:
        dest = args.get("dest")
        content = args.get("content", "")
        owner = args.get("owner", "root")
        mode = args.get("mode", "0644")

        new_checksum = hashlib.sha256(content.encode()).hexdigest()
        files = host.system_state["files"]

        if dest in files:
            current = files[dest]
            # Bandingkan metadata & content checksum
            if current["checksum"] == new_checksum and current["owner"] == owner and current["mode"] == mode:
                return TaskResult(host.name, changed=False, failed=False, diff={"msg": f"{dest} checksum matches"}, invocation=args)

        # File belum ada atau checksum/metadata berbeda
        files[dest] = {
            "content": content,
            "checksum": new_checksum,
            "owner": owner,
            "mode": mode
        }
        return TaskResult(
            host.name, changed=True, failed=False,
            diff={"msg": f"File {dest} updated/created (checksum: {new_checksum[:8]})"},
            invocation=args
        )

    @staticmethod
    def module_service(host: Host, args: Dict[str, Any]) -> TaskResult:
        service_name = args.get("name")
        desired_state = args.get("state", "started")
        services = host.system_state["services"]

        current_state = services.get(service_name, {}).get("state", "stopped")

        if current_state == desired_state:
            return TaskResult(host.name, changed=False, failed=False, diff={"msg": f"Service {service_name} already {desired_state}"}, invocation=args)

        services[service_name] = {"state": desired_state}
        return TaskResult(
            host.name, changed=True, failed=False,
            diff={"msg": f"Service {service_name} state changed: {current_state} -> {desired_state}"},
            invocation=args
        )


# ==============================================================================
# Playbook Execution Engine
# ==============================================================================
class PlaybookEngine:
    def __init__(self, inventory: Inventory):
        self.inventory = inventory
        self.modules = {
            "package": ModuleExecutor.module_package,
            "copy": ModuleExecutor.module_copy,
            "service": ModuleExecutor.module_service
        }

    def execute_task_on_host(self, host: Host, task: Task) -> TaskResult:
        module_func = self.modules.get(task.module)
        if not module_func:
            return TaskResult(host.name, changed=False, failed=True, diff={"msg": f"Module {task.module} not found"}, invocation=task.args)
        return module_func(host, task.args)

    def run_play(self, target_pattern: str, tasks: List[Task]):
        hosts = self.inventory.get_hosts_for_pattern(target_pattern)
        print(f"\n{ANSI_BOLD}PLAY [{target_pattern}] ********************************************************************{ANSI_RESET}")
        
        host_results: Dict[str, List[TaskResult]] = {h.name: [] for h in hosts}

        for task in tasks:
            print(f"\n{ANSI_BOLD}TASK [{task.name}] ***************************************************************{ANSI_RESET}")
            for host in hosts:
                res = self.execute_task_on_host(host, task)
                host_results[host.name].append(res)
                
                # Print execution result
                if res.failed:
                    status_str = f"{ANSI_RED}FAILED{ANSI_RESET}"
                elif res.changed:
                    status_str = f"{ANSI_YELLOW}CHANGED{ANSI_RESET}"
                else:
                    status_str = f"{ANSI_GREEN}OK{ANSI_RESET}"
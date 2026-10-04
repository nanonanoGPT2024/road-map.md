# Module 01: Secret Management Terpusat dengan HashiCorp Vault & Dynamic Secrets

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
- Memahami risiko fundamental dari *hardcoded credentials*, *sprawl* rahasia, dan keterbatasan Kubernetes Secret default.
- Menguasai arsitektur inti **HashiCorp Vault**: *Storage Engine*, *Barrier Encryption*, *Authentication Methods*, dan *Secret Engines*.
- Mengimplementasikan **KV (Key-Value) Version 2 Secret Engine** dengan versioning dan *soft delete*.
- Memahami dan mengonfigurasi **Dynamic Secrets**: kredensial database ephemeral yang dibuat sesuai permintaan (*just-in-time*) dengan masa aktif (*Time-to-Live / TTL*) otomatis.
- Mengintegrasikan Vault dengan Kubernetes menggunakan **Vault Agent Sidecar Injector** dan **Kubernetes ServiceAccount Authentication**.
- Menerapkan rotasi rahasia (*secret rotation*) dan pencabutan akses darurat (*emergency revocation*).

---

## 2. Prerequisite
- Memahami konsep dasar kriptografi: Enkripsi Simetris (AES-256), Asimetris (RSA/ECC), dan Hashing (BAB 02).
- Memahami Kubernetes ServiceAccount, ConfigMaps, dan Secrets (BAB 04).
- Memahami siklus hidup runtime container dan sidecar pattern (BAB 03 & BAB 04).

---

## 3. Concept
Dalam ekosistem cloud modern, aplikasi membutuhkan ratusan informasi sensitif (*secrets*): password database, API keys pihak ketiga, sertifikat TLS, dan SSH private keys. Menyimpan kredensial ini di file `.env`, variabel CI/CD, atau Kubernetes Secret (yang secara default hanya di-encode Base64 tanpa enkripsi at-rest) menimbulkan risiko kebocoran data (*secret sprawl*).

**HashiCorp Vault** adalah sistem manajemen rahasia terpusat berstandar enterprise. Seluruh rahasia yang masuk ke Vault dienkripsi menggunakan algoritma AES-256-GCM (*encryption barrier*). Tidak ada seorang pun—bahkan administrator database atau sistem operasi—yang dapat membaca rahasia tersebut tanpa token autentikasi yang sah dengan kebijakan akses berbasis *Least Privilege*.

```
                ┌──────────────────────────────────────────────────────────┐
                │                  HASHICORP VAULT CORE                    │
                └──────────────────────────────────────────────────────────┘

 [ Kubernetes Pod ] ──(K8s ServiceAccount Token)──> [ Vault Auth Method ]
         │                                                   │
         │                                                   ▼ (Verify with K8s API)
         │                                           [ Issue Vault Token ]
         │                                                   │
         │                                                   ▼ (Check Policies)
         │ <──(Dynamic DB Creds: user_xyz / pass_123)─────── [ Secret Engine: Database ]
         │    (TTL: 1 hour, Auto-Revoke)                             │
         │                                                           ▼
         │                                              [ PostgreSQL / MySQL Cluster ]
         │                                              (Vault creates ephemeral user)
```

---

## 4. Why?
1. **Eliminasi Static Secrets**: Kredensial statis (seperti password database `db_admin:Secret2024!` yang tidak pernah diganti selama 3 tahun) adalah mimpi buruk keamanan. Jika satu developer keluar atau laptop terinfeksi, seluruh database terancam. Vault menggantinya dengan **Dynamic Secrets**: setiap pod mendapatkan username/password acak unik yang otomatis hangus setelah 1 jam.
2. **Audit Logging Komprehensif**: Vault mencatat setiap aksi: siapa yang membaca rahasia, kapan, dari IP mana, dan menggunakan token apa. Setiap request meninggalkan jejak forensik tak terbantahkan.
3. **Encryption as a Service (Transit Engine)**: Developer tidak perlu mengimplementasikan library kriptografi rumit di aplikasi. Cukup kirim plaintext via API ke Vault Transit Engine, dan Vault mengembalikan ciphertext terenkripsi (*Zero-Knowledge App Architecture*).

---

## 5. What?
Komponen inti dalam arsitektur HashiCorp Vault:
- **Storage Backend**: Media penyimpanan terenkripsi tempat ciphertext disimpan (Consul, Integrated Raft Storage, AWS S3). Storage backend tidak memegang kunci pembuka enkripsi.
- **Unseal Keys & Shamir's Secret Sharing**: Saat Vault di-restart, Vault berada dalam status *Sealed* (terkunci rapat). Master key dipecah menjadi beberapa bagian (misal 5 bagian dengan threshold 3). Tiga pemegang kunci harus memasukkan pecahan kunci mereka untuk membongkar master key dan membuka *Barrier*.
- **Auth Methods**: Mekanisme pembuktian identitas (Kubernetes SA Token, AWS IAM, GitHub OAuth, AppRole untuk CI/CD).
- **Secret Engines**: Plugin pengelola rahasia (KV v2, Database, AWS, PKI untuk sertifikat TLS otomatis, Transit).
- **Token & Lease**: Setiap rahasia yang dikeluarkan memiliki *Lease ID* dan *TTL* (durasi sewa). Jika lease tidak diperpanjang (*renewed*), rahasia akan dihapus otomatis dari target database.

---

## 6. How?
Alur kerja Dynamic Database Secrets:
1. **Konfigurasi Engine**: DevOps mendaftarkan plugin database PostgreSQL ke Vault dan memberikan kredensial root Vault ke DB.
2. **Role Creation**: DevOps membuat role `app-readonly` dengan template SQL:
   ```sql
   CREATE USER "{{name}}" WITH PASSWORD '{{password}}' VALID UNTIL '{{expiration}}';
   GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{{name}}";
   ```
3. **Pod Request**: Aplikasi microservice melakukan HTTP GET ke `/v1/database/creds/app-readonly` dengan menyertakan Vault Token miliknya.
4. **Just-In-Time Generation**: Vault secara dinamis membuat user unik baru di PostgreSQL (misal `v-token-app-re-a84f9`), menghasilkan password acak 24 karakter, dan mengembalikannya ke aplikasi beserta `lease_duration: 3600` (1 jam).
5. **Auto-Revocation**: Jika setelah 1 jam aplikasi tidak memperbarui lease (atau pod dimatikan), Vault secara otomatis mengeksekusi `DROP USER` di database PostgreSQL.

---

## 7. Analogy
Bayangkan **HashiCorp Vault** seperti **Resepsionis Kartu Kunci Hotel Digital**:
- Hotel tidak pernah memberikan kunci besi permanen yang berlaku selamanya kepada tamu.
- Saat Anda check-in (**Autentikasi**), resepsionis memeriksa KTP Anda (**Policy**) dan memprogram kartu kunci magnetik digital (**Dynamic Secret & Lease**).
- Kartu kunci tersebut hanya bisa membuka kamar Anda sendiri (**Least Privilege**) dan secara otomatis mati tidak bisa digunakan lagi pada pukul 12:00 siang saat waktu check-out tiba (**TTL Expiration & Revocation**).

---

## 8. Diagram
```
+-----------------------------------------------------------------------------------+
|               VAULT AGENT SIDECAR INJECTION IN KUBERNETES                         |
+-----------------------------------------------------------------------------------+

 [ Kubernetes Pod: payment-api ]
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │                                                                             │
 │  ┌───────────────────────────────┐     ┌─────────────────────────────────┐  │
 │  │ Vault Agent Sidecar Container │     │ Main App Container              │  │
 │  │                               │     │ (Node.js / Go / Python)         │  │
 │  │ 1. Read K8s SA Token          │     │                                 │  │
 │  │ 2. Login to Vault API         │     │ 4. Read Credentials             │  │
 │  │ 3. Fetch Secret from KV/DB    │     │    from local file              │  │
 │  │    & render template          │     │    (/vault/secrets/database)    │  │
 │  │    to shared in-memory volume │     │                                 │  │
 │  └───────────────┬───────────────┘     └────────────────▲────────────────┘  │
 │                  │                                      │                   │
 │                  └───────────── Shared Memory ──────────┘                   │
 │                                (emptyDir: medium=Memory)                    │
 └──────────────────────────────────────┬──────────────────────────────────────┘
                                        │
                         mTLS API Call  │  /v1/auth/kubernetes/login
                                        ▼
                           [ HashiCorp Vault Server ]
```

---

## 9. Simple Example: Interaksi Vault CLI (KV Engine v2)
Perintah interaksi dasar dengan Vault CLI:

```bash
# 1. Menulis rahasia baru (Key-Value)
vault kv put secret/payment-gateway \
  api_key="pk_live_9941a82fce" \
  webhook_secret="whsec_8841a0e"

# 2. Membaca rahasia
vault kv get secret/payment-gateway

# 3. Menulis versi kedua (mengubah salah satu kunci)
vault kv put secret/payment-gateway \
  api_key="pk_live_new_credential_2026" \
  webhook_secret="whsec_8841a0e"

# 4. Membaca versi spesifik (Rollback / Audit)
vault kv get -version=1 secret/payment-gateway
```

---

## 10. Practical Example: Vault Agent Sidecar Injector di K8s
Menyematkan anotasi pada Pod Deployment agar Vault Agent secara otomatis menginjeksi rahasia ke `/vault/secrets/config.env`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  namespace: production
spec:
  replicas: 3
  template:
    metadata:
      labels:
        app: order-service
      annotations:
        # Mengaktifkan Vault Agent Mutating Webhook
        vault.hashicorp.com/agent-inject: 'true'
        vault.hashicorp.com/role: 'order-service-role'
        vault.hashicorp.com/agent-inject-secret-config.env: 'secret/data/production/order-service'
        # Template format file output (dijadikan environment file)
        vault.hashicorp.com/agent-inject-template-config.env: |
          {{- with secret "secret/data/production/order-service" -}}
          export DB_PASSWORD="{{ .Data.data.db_password }}"
          export STRIPE_API_KEY="{{ .Data.data.stripe_key }}"
          {{- end -}}
    spec:
      serviceAccountName: order-service-sa
      containers:
        - name: order-service
          image: myregistry.io/order-service:v1.2.0
          command: ['/bin/sh', '-c']
          args: ['. /vault/secrets/config.env && ./app-binary']
```

---

## 11. Real World Example: Mencegah Kebocoran Database Akibat Ransomware Internal
Pada sebuah institusi keuangan:
- **Insiden Masa Lalu**: Kredensial root database bocor di commit history Git publik, mengakibatkan penyerang mengekstraksi tabel nasabah dan meminta tebusan.
- **Implementasi Vault**:
  1. Kredensial root database hanya dipegang oleh Vault dan tidak pernah diketahui oleh developer mana pun.
  2. Seluruh microservices menggunakan **Dynamic Secrets** dengan TTL 30 menit.
  3. Setiap instance pod memiliki kredensial database unik.
- **Hasil**: Ketika satu pod terkompromi melalui celah remote code execution (RCE), penyerang hanya mendapatkan user database ephemeral yang dibatasi izinnya hanya pada tabel pesanan. Ketika pod di-restart oleh sistem deteksi intrusi, lease user tersebut langsung dicabut (*revoked*) oleh Vault dalam 1 detik, memutus akses penyerang secara permanen.

---

## 12. Trade-offs

| Aspek | Kubernetes Secret Biasa | HashiCorp Vault |
|---|---|---|
| **Enkripsi At-Rest** | Lemah (Default Base64 di etcd tanpa KMS provider) | Sangat Kuat (AES-256-GCM via Barrier) |
| **Tipe Kredensial** | Statis (Harus diupdate dan di-restart manual) | Dinamis (TTL, auto-renew, auto-revoke) |
| **Audit Log** | Terbatas pada Kubernetes API server audit | Rinci (Mencatat identitas dan field yang diakses) |
| **Kompleksitas Operasional** | Nol (Bawaan native Kubernetes) | Menengah-Tinggi (Unsealing, Raft cluster HA, Agent) |
| **Rotasi Rahasia** | Manual & Rentan Downtime | Otomatis tanpa perlu me-restart container |

---

## 13. When To Use
- Aplikasi skala produksi dengan persyaratan regulasi ketat (Fintech, Healthcare, Perbankan, E-commerce).
- Sistem microservices multi-cloud di mana kredensial harus dibagikan secara aman melintasi AWS, GCP, dan on-premise datacenter.
- Mengelola sertifikat TLS internal otomatis (PKI Engine) yang kedaluwarsa dalam rentang hari untuk zero-trust mTLS.

---

## 14. When NOT To Use
- Lingkungan prototype awal / hackathon dengan developer tunggal (cukup gunakan environment variable terisolasi).
- Aplikasi sederhana tanpa database atau dependensi pihak ketiga.

---

## 15. Common Mistakes
1. **Menyimpan Root Token di Production**: Menggunakan `root_token` yang dihasilkan saat inisialisasi Vault untuk operasional sehari-hari. Root token harus segera dicabut (*revoked*) setelah konfigurasi awal selesai.
2. **Menyimpan Unseal Keys di Server yang Sama**: Menyimpan unseal key Shamir di file teks di server Vault itu sendiri. Jika server dibobol, penyerang langsung dapat membuka seluruh brankas rahasia. Gunakan **Cloud Auto-Unseal** (AWS KMS, GCP KMS, Azure Key Vault).
3. **Mengabaikan Token TTL**: Menyetel TTL token menjadi tak terhingga (`infinite`). Selalu tetapkan batas sewa maksimal (*maximum TTL*) untuk membatasi jendela eksploitasi jika token bocor.

---

## 16. Best Practices
### Must Have
- Aktifkan **Cloud Auto-Unseal** (KMS) untuk cluster produksi agar node dapat pulih otomatis saat reboot tanpa intervensi manual manusia.
- Pasang cluster Vault dalam mode High Availability (minimal 3 node dengan Raft Storage).
- Terapkan kebijakan akses *Least Privilege* menggunakan HCL Policies: batasi aplikasi hanya boleh membaca (`read`) path direktori spesifik mereka.

### Recommended
- Gunakan Vault Agent Sidecar Injector agar aplikasi Anda tidak perlu memanggil Vault API secara langsung (decoupling logika bisnis dari secret management).
- Konfigurasikan Audit Device ke stream terisolasi (misal `/var/log/vault/audit.log` yang diteruskan ke Loki/SIEM).

### Advanced
- Gabungkan Vault dengan SPIFFE/SPIRE untuk autentikasi identitas mTLS berbasis kriptografi perangkat keras tanpa token statis.

---

## 17. Troubleshooting
- **Masalah**: Vault Server terkunci dan tidak melayani API (`status 503: Vault is sealed`).
  - *Penyebab*: Server baru saja direstart atau node kehilangan quorum Raft.
  - *Solusi*: Masukkan 3 pecahan unseal key via `vault operator unseal`, atau periksa koneksi jaringan ke Cloud KMS provider jika menggunakan auto-unseal.
- **Masalah**: Vault Agent sidecar gagal login: `permission denied` pada Kubernetes auth method.
  - *Solusi*: Verifikasi bahwa ServiceAccount name, namespace, dan bound role di Vault sudah cocok 100%, serta token reviewer JWT memiliki izin `system:auth-delegator`.

---

## 18. Exercise
1. Tulis HCL policy Vault yang hanya mengizinkan operasi `read` dan `list` pada path `secret/data/production/billing/*` dan melarang operasi `delete`.
2. Simulasikan skenario pencabutan kredensial darurat: cabut seluruh lease aktif yang terkait dengan role database tertentu menggunakan perintah `vault lease revoke -prefix`.

---

## 19. Challenge
Rancang pipeline manajemen rahasia end-to-end:
- Setup Vault KV v2 engine untuk environment staging dan prod.
- Konfigurasikan Kubernetes Auth Method di namespace `payments`.
- Tulis manifest Deployment dengan Vault Agent Injector template yang me-render file koneksi database terformat JSON di memori RAM pod (`tmpfs`).
- Buktikan bahwa ketika password di Vault diubah, file rahasia di dalam pod terupdate otomatis tanpa restart container.

---

## 20. Summary
- **HashiCorp Vault** adalah standar industri untuk manajemen rahasia terpusat dengan enkripsi *barrier* AES-256.
- **KV v2 Engine** menyediakan versioning dan rollback rahasia yang aman.
- **Dynamic Secrets** menciptakan kredensial ephemeral dengan TTL yang di-revoke otomatis, mengeliminasi risiko credential sprawl.
- **Vault Agent Injector** memungkinkan pod Kubernetes mengonsumsi rahasia tanpa modifikasi kode aplikasi.

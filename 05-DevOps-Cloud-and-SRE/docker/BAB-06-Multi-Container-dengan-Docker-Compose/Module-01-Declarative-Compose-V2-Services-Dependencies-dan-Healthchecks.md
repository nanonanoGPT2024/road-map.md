# Module 01: Declarative Compose V2, Services, Dependencies, & Healthchecks

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
- Memahami evolusi spesifikasi **Docker Compose V2** (berbasis Go native `docker compose` tanpa tanda strip `-`) dibanding legacy Python V1 (`docker-compose`).
- Menulis file orkestrasi deklaratif standar industri **`compose.yaml`** yang mencakup `services`, `networks`, dan `volumes`.
- Mengontrol urutan startup dan kesiapan layanan (*startup ordering*) menggunakan **`depends_on` dengan `condition: service_healthy`**.
- Mencegah fenomena kegagalan *race condition* saat aplikasi web mencoba menyambung ke database yang belum selesai inisialisasi.
- Mengelola variabel konfigurasi dinamis menggunakan file `.env`, `env_file`, dan sintaks ekspansi variabel `${VAR:-default}`.

---

## 2. Prerequisite
- Memahami konsep container lifecycle, healthchecks, dan restart policies (BAB 02 Module 02).
- Memahami konsep Named Volumes dan User-Defined Bridge networks (BAB 04 & BAB 05).
- Pengetahuan dasar tentang sintaks format data YAML (indentasi spasi, list, key-value mapping).

---

## 3. Concept
Menjalankan arsitektur microservices dengan mengetik perintah `docker run` individual satu per satu di terminal sangat rawan kesalahan manusia (*human error*), sulit didokumentasikan, dan tidak dapat direproduksi secara instan oleh anggota tim lain.

**Docker Compose V2** adalah alat orkestrasi deklaratif resmi untuk mendefinisikan dan menjalankan aplikasi multi-container dalam satu file konfigurasi terpusat: **`compose.yaml`**. Cukup dengan satu perintah tunggal:
`docker compose up -d`
Docker Engine akan secara otomatis membuat jaringan terisolasi khusus, membuat volume persisten, membangun image, dan menyalakan seluruh container sesuai urutan dependensi yang benar.

```
       DOCKER COMPOSE ORCHESTRATION PIPELINE
 ┌─────────────────────────────────────────────────────────────┐
 │ compose.yaml (Declarative Blueprint)                        │
 │  services:                                                  │
 │    postgres: (healthcheck: pg_isready)                      │
 │    api: (depends_on: { postgres: { condition: healthy } }) │
 │    nginx: (ports: 80:80)                                    │
 └──────────────────────────────┬──────────────────────────────┘
                                │ docker compose up -d
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ DOCKER ENGINE RUNTIME ENVIRONMENT                           │
 │                                                             │
 │  Network: <project>_default (Automatic Bridge + DNS)        │
 │  Volume:  <project>_pgdata  (Automatic Named Volume)        │
 │                                                             │
 │  Execution Order:                                           │
 │   1. Start postgres ──> wait for HEALTHY                    │
 │   2. Start api      ──> connects via 'postgres:5432'        │
 │   3. Start nginx    ──> proxies to 'api:3000'               │
 └─────────────────────────────────────────────────────────────┘
```

---

## 4. Why?
1. **Pemberantasan Masalah Startup Race Condition**: Perintah legacy `depends_on: [db]` hanya menunggu container database *berjalan* (proses PID 1 aktif), bukan menunggu database *siap menerima koneksi*. PostgreSQL membutuhkan 5-15 detik untuk inisialisasi tabel disk. Tanpa `condition: service_healthy`, aplikasi API akan langsung crash saat booting karena database menolak koneksi socket TCP.
2. **Reproducibility Instan untuk Tim**: Developer baru yang baru bergabung ke tim cukup menjalankan `git clone` dan `docker compose up`, dan seluruh ekosistem (Frontend, Backend API, Redis Cache, Postgres DB, Mock S3) langsung siap berjalan di laptop mereka dalam 2 menit.
3. **Pemberian Nama Jaringan Otomatis**: Compose secara otomatis membuat custom bridge network terisolasi dan mendaftarkan setiap nama service sebagai hostname DNS, mengeliminasi kebutuhan pembuatan network manual via CLI.

---

## 5. What?
### Struktur Hirarki File `compose.yaml`:
- **`services`**: Blok pendefinisian container workload aplikasi (nama service menjadi hostname DNS internal).
- **`networks`**: Deklarasi jaringan kustom yang menghubungkan antar-service. Jika tidak didefinisikan, Compose membuat default bridge `<project_name>_default`.
- **`volumes`**: Deklarasi Named Volumes yang persisten di host.
- **`secrets`**: Injeksi file rahasia (password DB, SSL certs) ke dalam mount `/run/secrets/`.
- **`configs`**: Injeksi file konfigurasi statis (seperti `nginx.conf`) ke container.

### Perbedaan Perintah: Docker Compose V1 vs V2:

| Aspek | Compose V1 (Legacy) | Compose V2 (Modern Standard) |
|---|---|---|
| **Binary CLI** | `docker-compose` (Terpisah, ditulis di Python) | `docker compose` (Sub-command native di Go) |
| **Nama File Standar** | `docker-compose.yml` | **`compose.yaml`** (atau `compose.yml`) |
| **Kecepatan Eksekusi** | Lambat (Overhead Python runtime) | Cepat (Binary Go langsung panggil Docker API) |
| **Dukungan Spesifikasi** | Terkunci di versi format `version: '3.8'` | **Compose Specification** modern tanpa atribut `version` |

---

## 6. How?
### Mengonfigurasi `depends_on` dengan Healthcheck Synchronization:
Contoh pola arsitektur yang menjamin API baru berjalan setelah database PostgreSQL 100% siap melayani query:

```yaml
services:
  database:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: app_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: supersecretpassword
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d app_db"]
      interval: 5s
      timeout: 3s
      retries: 5
      start_period: 5s

  api-backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgres://postgres:supersecretpassword@database:5432/app_db
    ports:
      - "3000:3000"
    depends_on:
      database:
        condition: service_healthy # Menunggu probe database return 0!
        restart: true

volumes:
  pgdata:
```

---

## 7. Analogy
Bayangkan **Docker Compose dengan Condition Healthcheck** seperti **Persiapan Panggung Konser Musik Rock**:
- **Database** adalah **Teknisi Sound System**: Mereka harus menyalakan genset, mencolokkan kabel speaker, dan menyetel mixer audio (**Database Booting & Initialization**).
- **API Backend** adalah **Gitaris dan Vokalis Band Rock**: Jika vokalis naik panggung dan langsung berteriak di depan mikrofon yang kabelnya belum dicolokkan ke amplifier (**Race Condition Crash**), penonton tidak akan mendengar suara apa pun dan konser kacau.
- Dengan **`condition: service_healthy`**, vokalis dengan sabar menunggu di belakang panggung hingga teknisi sound menaikkan jempol tanda mikrofon sudah aktif (**Healthcheck OK**), baru kemudian melangkah ke panggung untuk mulai bernyanyi.

---

## 8. Diagram
```
+-----------------------------------------------------------------------------------+
|               COMPOSE V2 STARTUP ORDERING (CONDITION: SERVICE_HEALTHY)            |
+-----------------------------------------------------------------------------------+

 [ docker compose up -d ]
             │
             ▼
 1. Create Network: finbank_default & Volume: finbank_pgdata
             │
             ▼
 2. Start Service: 'database' (postgres:16)
    ↳ State: Running (health: starting)
             │
             ├──> [ Service 'api-backend' is WAITING... ]
             │      (Docker Engine holds container execution!)
             │
             ▼ (Healthcheck probe: pg_isready succeeds)
 3. Database State transitions to: [ HEALTHY ]
             │
             ▼ (Condition satisfied!)
 4. Start Service: 'api-backend'
    ↳ Connects immediately to postgres:5432 with ZERO socket errors!
```

---

## 9. Simple Example: Perintah CLI Docker Compose V2 Esensial
Daftar perintah yang paling sering digunakan sehari-hari:

```bash
# 1. Menyalakan seluruh layanan di background dan build jika image belum ada
docker compose up -d --build

# 2. Melihat status seluruh service beserta status healthcheck-nya
docker compose ps

# 3. Melihat streaming log gabungan dari seluruh service
docker compose logs -f --tail 50

# 4. Melihat log hanya dari satu service spesifik
docker compose logs -f api-backend

# 5. Mengeksekusi perintah di dalam salah satu service
docker compose exec database psql -U postgres -d app_db

# 6. Menghentikan seluruh service tanpa menghapus volume
docker compose down

# 7. Menghancurkan seluruh service BESERTA Named Volumes-nya (Pembersihan total)
docker compose down -v
```

---

## 10. Practical Example: Manajemen Variabel Lingkungan (`.env`)
File `.env` di direktori yang sama dengan `compose.yaml`:

```ini
# Konfigurasi Database
DB_NAME=production_store
DB_USER=store_admin
DB_PASSWORD=VerySecureSecretPassword2026!
DB_PORT=5432

# Konfigurasi Aplikasi
APP_PORT=8080
LOG_LEVEL=info
```

File `compose.yaml` yang menggunakan ekspansi variabel:

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - store_db_data:/var/lib/postgresql/data

  api:
    image: my-store-api:latest
    ports:
      - "${APP_PORT:-3000}:3000" # Fallback ke 3000 jika APP_PORT tidak diset
    environment:
      DATABASE_URL: postgres://${DB_USER}:${DB_PASSWORD}@db:${DB_PORT}/${DB_NAME}
      LOG_LEVEL: ${LOG_LEVEL:-debug}
    depends_on:
      db:
        condition: service_healthy

volumes:
  store_db_data:
```

---

## 11. Real World Example: Meniadakan Insiden CI/CD Flaky Test
Sebuah tim pengembang menjalankan integration test end-to-end (E2E) di pipeline GitHub Actions:
- **Masalah Awal**: Sekitar 35% pengujian otomatis gagal acak (*flaky*) dengan error `ECONNREFUSED 127.0.0.1:5432`. Pipeline menggunakan `docker compose up -d` dengan `depends_on: [db]`. Script test berjalan terlalu cepat sebelum database PostgreSQL selesai membuat tabel awal.
- **Solusi dengan `condition: service_healthy`**:
  Tim menambahkan blok `healthcheck: test: ["CMD", "pg_isready"]` pada service database dan menyetel `condition: service_healthy` pada service test runner.
- **Hasil**: Tingkat kegagalan flaky test turun menjadi **0%**. Pipeline pengujian menjadi 100% deterministik dan stabil.

---

## 12. Trade-offs

| Aspek | Script Bash `docker run` Manual | Docker Compose V2 |
|---|---|---|
| **Keterbacaan Arsitektur** | Sangat Buruk (Tercecer di script shell panjang) | Sangat Rapi (Terdokumentasi deklaratif di YAML) |
| **Manajemen Dependensi Startup**| Manual (Harus tulis loop bash `sleep` & `nc`) | Otomatis via `condition: service_healthy` |
| **Siklus Pembersihan** | Rumit (Harus hapus container, net, vol satu-satu) | Satu Perintah (`docker compose down -v`) |
| **Skalabilitas Multi-Node** | Terbatas pada single host | Terbatas pada single host (Butuh K8s untuk multi-node) |

---

## 13. When To Use
- Lingkungan pengembangan lokal (Local Dev) untuk menjalankan seluruh ekosistem aplikasi di mesin developer.
- Menjalankan lingkungan pengujian otomatis (Integration & E2E Testing) di pipeline CI/CD.
- Server produksi mandiri (*Single-Node Production VPS*) untuk aplikasi skala kecil hingga menengah.

---

## 14. When NOT To Use
- Jangan gunakan Docker Compose untuk orkestrasi cluster produksi multi-node berkapasitas ribuan container dengan auto-scaling horizontal dinamis lintas-datacenter (Gunakan **Kubernetes**).

---

## 15. Common Mistakes
1. **Menggunakan `depends_on` Tanpa `condition`**: Menggunakan sintaks sederhana `depends_on: - db` dan berharap aplikasi menunggu database siap. Docker hanya menunggu container DB start, bukan siap melayani traffic! Selalu gunakan format object dengan `condition: service_healthy`.
2. **Melakukan Commit File `.env` Berisi Password ke Git**: Mengunggah file `.env` produksi ke repositori publik GitHub. Selalu masukkan `.env` ke `.gitignore` dan sediakan file `.env.example` sebagai template kosong.
3. **Menggunakan Atribut Usang `version: '3.8'`**: Menuliskan atribut `version` di baris pertama `compose.yaml`. Pada spesifikasi Compose modern (Compose Spec V2), atribut `version` sudah usang (*deprecated*) dan tidak lagi diperlukan.

---

## 16. Best Practices
### Must Have
- Gunakan nama file resmi **`compose.yaml`** (sesuai standar Compose Specification modern).
- Wajib sertakan `healthcheck` pada service database/cache dan gunakan `condition: service_healthy` pada service yang bergantung padanya.
- Jangan hardcode kredensial di dalam file `compose.yaml`; gunakan variabel lingkungan `${VAR}`.

### Recommended
- Pasang batas resource (`deploy.resources.limits`) untuk membatasi konsumsi memori dan CPU service.
- Gunakan `restart: unless-stopped` untuk seluruh service yang harus aktif 24/7.

### Advanced
- Gabungkan dengan Docker Compose Watch (`develop.watch`) di Compose v2.22+ untuk sinkronisasi otomatis file kode lokal langsung ke container tanpa rebuild image saat koding.

---

## 17. Troubleshooting
- **Masalah**: `dependency failed to start: service "database" is unhealthy`.
  - *Penyebab*: Perintah probe di `healthcheck` database gagal terus-menerus melebihi batas `retries` (misal username/password salah atau port belum listen).
  - *Solusi*: Jalankan `docker compose logs database` untuk melihat penyebab kegagalan internal database.
- **Masalah**: Perubahan di file `.env` tidak tercermin di container.
  - *Solusi*: Matikan dan nyalakan ulang dengan `docker compose down && docker compose up -d` (jangan hanya `restart`).

---

## 18. Exercise
1. Tulis file `compose.yaml` yang menghubungkan Redis dan aplikasi Node.js. Konfigurasikan healthcheck pada Redis menggunakan perintah `redis-cli ping` dan pastikan Node.js hanya start setelah Redis sehat!
2. Buat file `.env` yang mendefinisikan port aplikasi dan buktikan dengan perintah `docker compose config` bahwa substitusi variabel berhasil diproses dengan benar.

---

## 19. Challenge
Rancang arsitektur microservices 3-layanan dengan Docker Compose:
- Service 1: PostgreSQL dengan Named Volume dan Healthcheck `pg_isready`.
- Service 2: Backend REST API yang menunggu PostgreSQL sehat sebelum booting.
- Service 3: Nginx Reverse Proxy yang mengekspos port 80 ke host dan mem-forward traffic ke Backend API.
- Buktikan bahwa urutan start berjalan 100% deterministik dan zero-downtime saat dieksekusi dengan `docker compose up -d`.

---

## 20. Summary
- **Docker Compose V2** (`docker compose`) adalah standar orkestrasi deklaratif modern berbasis Go.
- File **`compose.yaml`** menyatukan definisi services, networks, dan volumes dalam satu file terpusat.
- **`depends_on` dengan `condition: service_healthy`** mengeliminasi *race condition* startup antara aplikasi dan database.
- Substitusi variabel lingkungan via `.env` menjaga keamanan kredensial dan fleksibilitas konfigurasi multi-environment.

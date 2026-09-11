# Module 02: Multi-Environment Compose, Overrides, & Profiles

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
- Menguasai strategi pewarisan dan penggabungan (*inheritance & layering*) file konfigurasi: **`compose.yaml` + `compose.override.yaml`**.
- Memisahkan konfigurasi lingkungan secara terstruktur: **Development (`compose.dev.yaml`)**, **Staging**, dan **Production (`compose.prod.yaml`)** tanpa duplikasi kode (*DRY - Don't Repeat Yourself*).
- Mengatur layanan opsional sesuai kebutuhan menggunakan **Docker Compose Profiles** (misal mengaktifkan service Prometheus/Grafana atau Swagger UI hanya saat flag `--profile monitoring` dipanggil).
- Mengelola rahasia (*Docker Compose Secrets*) dan konfigurasi statis (*Configs*) tanpa membeberkan plaintext password di dalam file YAML.
- Memvalidasi hasil penggabungan file multi-compose menggunakan perintah `docker compose config`.

---

## 2. Prerequisite
- Memahami konsep dasar Docker Compose V2, services, networks, dan volumes (BAB 06 Module 01).
- Memahami perbedaan lingkungan Local Development (butuh bind mounts, hot-reload, debugger) vs Production (butuh immutable image, restart policy, resource limits).
- Pengetahuan dasar tentang teknik deep merge struktur data dictionary/mapping.

---

## 3. Concept
Dalam siklus hidup software nyata, sebuah aplikasi berjalan di beberapa lingkungan dengan kebutuhan konfigurasi yang bertolak belakang:
- **Local Dev**: Butuh bind mount folder lokal ke container untuk hot-reload, port debugging terbuka (port 9229), database dengan data dummy lokal, dan logging level `debug`.
- **Production**: Dilarang menggunakan bind mount, image harus immutable dari container registry, port internal tidak boleh diekspos langsung ke publik, restart policy wajib `always/unless-stopped`, dan resource CPU/RAM dibatasi ketat.

Menduplikasi seluruh file `compose.yaml` menjadi 3 file terpisah yang berdiri sendiri adalah anti-pattern yang berbahaya karena perubahan variabel atau penambahan service baru di satu file sering lupa disalin ke file lainnya.

Docker Compose memecahkan masalah ini melalui dua fitur canggih:
1. **Compose Overrides**: Menggabungkan file dasar (`compose.yaml`) dengan file varian lingkungan (`compose.prod.yaml`) melalui aturan *deep merge*.
2. **Compose Profiles**: Mengelompokkan service ke dalam kategori profil tertentu, sehingga service penunjang (seperti pgAdmin, Mock Server, atau Grafana) tidak memakan RAM laptop kecuali dipanggil secara eksplisit.

```
       DOCKER COMPOSE FILE MERGING (HIERARCHY)
 ┌─────────────────────────────────────────────────────────────┐
 │ BASE SPECIFICATION: compose.yaml                            │
 │  - Defines core architecture: api, postgres, redis          │
 │  - Defines networks & volume names                          │
 └──────────────────────────────┬──────────────────────────────┘
                                │
               ┌────────────────┴────────────────┐
               ▼ Merged via CLI Flag             ▼
 ┌──────────────────────────────┐ ┌──────────────────────────────┐
 │ DEV: compose.override.yaml   │ │ PROD: compose.prod.yaml      │
 │  - Bind Mounts (hot-reload)  │ │  - Image tags from ECR       │
 │  - Exposes port 5432 to host │ │  - Resource limits (2GB RAM) │
 │  - Environment: DEBUG=true   │ │  - Restart: unless-stopped   │
 └──────────────────────────────┘ └──────────────────────────────┘
```

---

## 4. Why?
1. **Prinsip DRY (Don't Repeat Yourself)**: Anda hanya mendefinisikan nama service, network, dan volume satu kali di file basis. File override hanya memuat beberapa baris perubahan spesifik.
2. **Efisiensi RAM Laptop Developer via Profiles**: Di proyek besar dengan 15 microservices, menjalankan seluruh service sekaligus akan membuat laptop developer hang kehabisan RAM. Dengan *Profiles*, developer frontend hanya menjalankan service web dan mock API (`docker compose --profile frontend up`), sementara developer data analytics mengaktifkan profil data pipeline.
3. **Pemberian Konfigurasi Tanpa Menghancurkan Default**: Secara default, jika Anda mengetik `docker compose up`, Docker Compose otomatis mencari dan menggabungkan `compose.yaml` dengan `compose.override.yaml` (sangat nyaman untuk developer lokal tanpa perlu mengetik flag panjang).

---

## 5. What?
### Aturan Penggabungan (*Merging Rules*) Compose:
- **Nilai Tunggal (Scalar: string, number, boolean)**: Nilai di file override akan **menimpa (*overwrite*)** nilai di file base (misal `image: my-app:dev` ditimpa menjadi `image: my-app:v1.4.0`).
- **Array / List (ports, expose)**: Elemen list baru akan **digabungkan (*concatenated*)**.
- **Mapping / Dictionary (environment, labels)**: Key baru akan ditambahkan; jika ada key yang sama, nilainya akan ditimpa oleh file override.

### Perintah CLI untuk Multi-Compose & Profiles:
```bash
# Menggabungkan base compose dengan konfigurasi production
docker compose -f compose.yaml -f compose.prod.yaml up -d

# Menjalankan service utama BESERTA service berprofil 'monitoring'
docker compose --profile monitoring up -d

# Memeriksa hasil deep merge akhir dalam format YAML valid
docker compose -f compose.yaml -f compose.prod.yaml config
```

---

## 6. How?
### Implementasi Arsitektur Multi-Environment:

#### 1. File Basis Bersama (`compose.yaml`):
```yaml
services:
  database:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: main_db
      POSTGRES_USER: admin
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U admin -d main_db"]
      interval: 5s
      timeout: 3s
      retries: 5

  backend-api:
    build:
      context: ./backend
    environment:
      DB_HOST: database
    depends_on:
      database:
        condition: service_healthy

volumes:
  pg_data:
```

#### 2. File Override Lokal Development (`compose.override.yaml`):
```yaml
services:
  backend-api:
    # Pasang bind mount agar perubahan kode langsung ter-reload
    volumes:
      - ./backend:/usr/src/app
    ports:
      - "3000:3000"
    environment:
      NODE_ENV: development
      LOG_LEVEL: debug

  # Service tambahan hanya untuk developer (pgAdmin UI)
  pgadmin:
    image: dpage/pgadmin4:latest
    ports:
      - "5050:80"
    environment:
      PGADMIN_DEFAULT_EMAIL: dev@local.net
      PGADMIN_DEFAULT_PASSWORD: admin
    profiles:
      - tools # Hanya aktif jika flag --profile tools dipanggil!
```

#### 3. File Khusus Produksi (`compose.prod.yaml`):
```yaml
services:
  backend-api:
    # Di produksi: gunakan image immutable yang sudah diuji dari registry
    image: myregistry.io/finbank/backend-api:v2.1.0
    restart: unless-stopped
    ports:
      - "127.0.0.1:3000:3000" # Hanya buka di localhost
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 1024M
    environment:
      NODE_ENV: production
      LOG_LEVEL: error

  database:
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 2048M
```

---

## 7. Analogy
Bayangkan **Compose Overrides & Profiles** seperti **Membeli Mobil Baru dengan Paket Opsi Aksesori**:
- **`compose.yaml` (Base)** adalah Mobil Standar Pabrik: Rangka besi, 4 roda, mesin, setir, dan transmisi transmisi gigi (Sama untuk semua pembeli).
- **`compose.override.yaml` (Dev)** adalah Paket Pengemudi Pemula: Dilengkapi kamera mundur tambahan, stiker latihan mengemudi, dan kursi tambahan untuk instruktur (**Hot-reload, pgAdmin, debug port**).
- **`compose.prod.yaml` (Prod)** adalah Paket Balap Resmi: Kursi instruktur dilepas, ban diganti ban balap tahan panas, dan dipasang batas kecepatan otomatis (*speed governor*) (**Resource limits, restart policy, production image**).
- **`--profile`** adalah Lampu Kabut atau Derek Trailer Gandeng: Hanya dipasang dan dinyalakan saat Anda benar-benar membutuhkannya di jalanan berkabut (**On-demand monitoring / debug tools**).

---

## 8. Diagram
```
+-----------------------------------------------------------------------------------+
|               DOCKER COMPOSE PROFILES SELECTIVE ACTIVATION                        |
+-----------------------------------------------------------------------------------+

 Default Execution:
 $ docker compose up -d
         │
         ├──> [ Service: database ] ────> STARTED (Core Service)
         ├──> [ Service: backend-api ] ─> STARTED (Core Service)
         │
         ├──> [ Service: prometheus ] ──> SKIPPED (Profile: 'monitoring')
         └──> [ Service: pgadmin ] ─────> SKIPPED (Profile: 'tools')

 Execution with Profile Flag:
 $ docker compose --profile monitoring up -d
         │
         ├──> [ Service: database ] ────> STARTED
         ├──> [ Service: backend-api ] ─> STARTED
         └──> [ Service: prometheus ] ──> STARTED! (Active for metric scraping)
```

---

## 9. Simple Example: Sintaks Profiles di `compose.yaml`
Menugaskan layanan ke dalam profil tertentu:

```yaml
services:
  web:
    image: nginx:alpine
    ports:
      - "80:80"

  # Layanan pengujian beban hanya aktif saat profile 'perf' dipanggil
  load-tester:
    image: grafana/k6:latest
    profiles:
      - perf
    command: ["run", "/scripts/test.js"]

  # Layanan UI mailhog untuk test email lokal
  mailhog:
    image: mailhog/mailhog:latest
    ports:
      - "8025:8025"
    profiles:
      - dev-tools
```

---

## 10. Practical Example: Menggunakan Docker Compose Secrets
Mencegah penyimpanan password plain text di dalam file YAML:

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: app
      POSTGRES_USER: admin
      POSTGRES_PASSWORD_FILE: /run/secrets/db_root_password
    secrets:
      - db_root_password

secrets:
  db_root_password:
    file: ./secrets/db_password.txt # File teks di host dengan permission 600
```

Di dalam container, Docker me-mount file rahasia tersebut ke filesystem in-memory (`tmpfs`) pada path `/run/secrets/db_root_password` sehingga aman dari inspeksi environment variable biasa!

---

## 11. Real World Example: Efisiensi Resource Staging Multi-Tenant dengan Profiles
Sebuah perusahaan e-commerce menjalankan server staging tunggal untuk 5 tim fitur independen:
- **Masalah**: Menjalankan seluruh 24 microservices secara permanen membutuhkan server dengan RAM 128GB seharga $800/bulan. Sebagian besar service analitik dan ekspor laporan hanya dipakai 2 kali seminggu saat tim QA melakukan pengujian.
- **Solusi Menggunakan Compose Profiles**:
  DevOps mengelompokkan microservices ke dalam profil:
  - `core` (Auth, API, DB - selalu aktif, butuh RAM 16GB).
  - `analytics` (Worker, Kafka, Clickhouse - hanya aktif saat pengujian analitik).
  - `billing` (Payment simulator, Stripe mock).
- **Hasil**: Server staging dipangkas menjadi instance 32GB RAM ($220/bulan - hemat 72%), dan tim QA menyalakan profil analitik secara on-demand via bot Slack: `docker compose --profile analytics up -d`.

---

## 12. Trade-offs

| Aspek | File Compose Tunggal Raksasa | Modular Overrides & Profiles |
|---|---|---|
| **Jumlah File** | Hanya 1 file | 2 - 4 file terstruktur |
| **Kesiapan Produksi** | Buruk (Banyak hacky flag dev terbawa ke prod) | Sangat Bersih (Prod terisolasi dari dev config) |
| **Konsumsi RAM Developer** | Tinggi (Semua service dipaksa jalan) | Rendah (Service pendukung dimatikan via profile) |
| **Verifikasi Konfigurasi** | Cukup baca satu file | Butuh `docker compose config` untuk inspeksi |

---

## 13. When To Use
- Proyek tim yang dijalankan di mesin developer lokal sekaligus di server staging/produksi.
- Arsitektur dengan service pendukung (Prometheus, Grafana, MailHog, Jaeger, Swagger UI, LocalStack) yang hanya diperlukan pada skenario tertentu.

---

## 14. When NOT To Use
- Jangan gunakan `compose.override.yaml` di server produksi tanpa sengaja (pastikan file override otomatis tidak ikut ter-deploy ke folder produksi server, atau panggil `-f compose.yaml -f compose.prod.yaml` secara eksplisit).

---

## 15. Common Mistakes
1. **Lupa Bahwa `compose.override.yaml` Dimuat Otomatis**: Menjalankan `docker compose up` di server produksi di mana file `compose.override.yaml` (yang berisi bind mount folder dev) masih ada di direktori. Docker akan me-merge file tersebut secara otomatis! Di produksi, selalu panggil file spesifik: `docker compose -f compose.yaml -f compose.prod.yaml up -d`.
2. **Duplikasi Konfigurasi Port di Overrides**: Menentukan port `"80:80"` di file base dan `"8080:80"` di file override. Karena port adalah list/array, Compose akan menggabungkan keduanya dan mencoba membuka kedua port sekaligus! Definisikan port hanya di file varian jika nomor port berbeda.
3. **Mengabaikan `docker compose config`**: Melakukan deployment ke produksi tanpa pernah menguji apakah sintaks gabungan YAML valid. Selalu jalankan `docker compose -f compose.yaml -f compose.prod.yaml config` untuk memeriksa hasil akhir.

---

## 16. Best Practices
### Must Have
- Pisahkan konfigurasi sensitif atau variabel dinamis menggunakan file `.env` terpisah per lingkungan (`.env.development`, `.env.production`).
- Gunakan Docker Secrets untuk password database di lingkungan produksi.
- Selalu jalankan `docker compose config` di pipeline CI sebelum melakukan deployment.

### Recommended
- Gunakan profil `--profile debug` atau `--profile tools` untuk mematikan database GUI (seperti Adminer / pgAdmin) secara default.
- Tambahkan komentar yang jelas di bagian atas file override untuk menjelaskan tujuannya.

### Advanced
- Gabungkan dengan Docker Compose Extension fields (`x-logging: &default-logging`) untuk menerapkan template logging seragam ke puluhan service tanpa copy-paste.

---

## 17. Troubleshooting
- **Masalah**: `service "pgadmin" is not running` setelah `docker compose up -d`.
  - *Penyebab*: Service `pgadmin` diberi atribut `profiles: [tools]` sehingga sengaja dilewati oleh perintah default.
  - *Solusi*: Nyalakan dengan flag profil: `docker compose --profile tools up -d`.
- **Masalah**: Port conflict saat menjalankan environment staging dan dev di host yang sama.
  - *Solusi*: Tentukan nama project yang berbeda: `docker compose -p project-staging up -d` dan petakan ke nomor port host yang berbeda via variabel lingkungan `${APP_PORT}`.

---

## 18. Exercise
1. Tulis file `compose.yaml` dasar dengan service web Nginx. Buat file `compose.dev.yaml` yang menambahkan bind mount ke folder lokal dan `compose.prod.yaml` yang membatasi memori 128MB. Gunakan `docker compose -f ... config` untuk melihat perbedaan hasil deep merge kedua lingkungan!
2. Tambahkan service Redis dengan `profiles: ["cache"]`. Buktikan bahwa Redis tidak ikut berjalan saat Anda mengetik `docker compose up -d` biasa, namun berjalan saat Anda mengetik `docker compose --profile cache up -d`!

---

## 19. Challenge
Rancang arsitektur Multi-Environment Enterprise:
- `compose.yaml` (Base): Database Postgres dan API Backend.
- `compose.override.yaml` (Dev): Menambahkan live-reload volume, port debug, dan MailHog untuk mock email.
- `compose.prod.yaml` (Prod): Memasang image tag semver resmi, healthcheck, restart policy `unless-stopped`, dan alokasi resource Cgroups keras.
- `compose.monitoring.yaml` (Opsional Profile): Prometheus dan Grafana yang hanya aktif saat tim SRE memanggil `--profile ops`.
- Buktikan validitas penggabungan seluruh skenario di atas.

---

## 20. Summary
- **Compose Overrides** memungkinkan pemisahan konfigurasi dev dan prod secara bersih dengan mematuhi prinsip DRY.
- **Compose Profiles** menghemat sumber daya sistem dengan menjalankan service penunjang (monitoring, GUI database) secara selektif sesuai kebutuhan.
- Penggunaan **Docker Secrets** mengamankan kredensial produksi tanpa meninggalkan jejak plaintext di riwayat repositori kode.

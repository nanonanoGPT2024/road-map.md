# Module 02: Performance Profiling, cAdvisor, Prometheus, dan OOM Exit Codes

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
1. Memantau resource consumption container secara real-time menggunakan `docker stats` CLI dan memahami metrik CPU, Memory, Network I/O, serta Block I/O.
2. Mengintegrasikan Google cAdvisor (Container Advisor) untuk mengekspos metrik level cgroups ke Prometheus dan memvisualisasikannya di dashboard Grafana.
3. Membaca dan menafsirkan kode keluar kontainer (**Linux Exit Codes**): Exit Code 0, 1, 126, 127, 137, dan 143.
4. Mendiagnosa dan mengatasi insiden **Linux OOM Killer (Out Of Memory)** dengan memvalidasi flag `.State.OOMKilled` via `docker inspect`.
5. Mengatur rasio memory container cgroups secara harmonis dengan runtime heap size (Node.js `--max-old-space-size`, JVM `-Xmx`, Go `GOMEMLIMIT`).

---

## 2. Prerequisite
- Memahami konsep Linux Cgroups v2 ([BAB 01 Module 02](../BAB-01-Fondasi-dan-Arsitektur-Docker/Module-02-Linux-Namespaces-Cgroups-v2-Storage-Driver-OverlayFS.md)).
- Memahami resource constraints (`deploy.resources.limits`) ([BAB 02 Module 02](../BAB-02-Container-Lifecycle-dan-CLI-Mastery/Module-02-Healthchecks-Restart-Policies-dan-Resource-Constraints.md)).
- Pemahaman dasar sinyal Linux POSIX (`SIGTERM` = 15, `SIGKILL` = 9).

---

## 3. Concept
Dalam ekosistem container, isolasi resource dijalankan oleh subsistem kernel Linux bernama **Control Groups (cgroups)**. Ketika sebuah container berjalan melampaui batas memori yang ditentukan (`--memory` atau `mem_limit`), kernel Linux mengaktifkan mekanisme proteksi agresif yang disebut **OOM Killer (Out Of Memory Killer)**.

OOM Killer bertugas mencegah seluruh server host mengalami *kernel panic* dengan cara mengirimkan sinyal pemusnahan paksa `SIGKILL` (Sinyal 9) ke proses di dalam container yang melanggar kuota. Di Docker, peristiwa ini ditandai dengan **Exit Code 137** (128 + 9).

Untuk mencegah crash tiba-tiba di production, sistem observability modern menggabungkan **cAdvisor** (agen pengumpul metrik container dari cgroups) dengan **Prometheus** (time-series database) untuk memberikan peringatan dini (alerting) sebelum batas memori terlampaui.

---

## 4. Why?
1. **Mencegah "Mystery Restarts" di Production**: Mengapa container sering restart sendiri tanpa pesan error di log aplikasi? OOM Killer mematikan proses seketika tanpa sempat menulis stack trace!
2. **Kapasitas Perencanaan (Capacity Planning)**: Mengetahui rata-rata dan *peak* konsumsi RAM/CPU mencegah alokasi berlebih (pemborosan biaya cloud) atau alokasi terlalu sedikit (rawan crash).
3. **Penyelarasan Runtime Heap**: Garbage-collected languages (Java, Node.js, Go) tidak selalu mengetahui batasan cgroups container secara otomatis, yang kerap memicu OOM Killer jika heap size dibiarkan default.

---

## 5. What?
### Kamus Lengkap Docker Container Exit Codes:

| Exit Code | Nama / Sinyal | Makna Teknis | Penyebab Umum |
|---|---|---|---|
| **0** | Success | Proses utama (PID 1) selesai secara normal. | Script batch atau job migrasi database selesai dengan sukses. |
| **1** | General Error | Aplikasi melempar uncaught exception atau `exit(1)`. | Bug sintaks, syntax error, unhandled promise rejection. |
| **126** | Command Cannot Execute | File ditemukan tetapi tidak memiliki izin eksekusi (`chmod +x`). | Entrypoint script lupa di-`chmod +x` di dalam Dockerfile. |
| **127** | Command Not Found | Executable atau command tidak ditemukan di `$PATH`. | Salah ketik nama binary, atau binary dinamis kehilangan shared library (`glibc` vs `musl`). |
| **137** | **SIGKILL (128 + 9)** | Proses dibunuh paksa seketika. | **1. Linux OOM Killer** (alokasi memori melebihi limit cgroups).<br>2. Perintah `docker kill` atau `docker stop` setelah timeout 10 detik. |
| **143** | **SIGTERM (128 + 15)** | Proses menerima sinyal terminasi sopan. | Container dihentikan normal via `docker stop`, orchestrator melakukan rolling update. |

---

## 6. How? Alur Kerja OOM Killer dan cAdvisor Metrics

```text
               +---------------------------------------------------+
               |             Host Kernel Memory Controller         |
               |        (cgroups v2: /sys/fs/cgroup/memory)        |
               +---------------------------------------------------+
                                         |
                       +-----------------+-----------------+
                       |                                   |
                       v (Alokasi RAM Aman)                v (Alokasi Melebihi Batas)
         +----------------------------+      +-------------------------------+
         | Memory Usage < Limit       |      | Memory Usage > Limit (512MB)  |
         | Container beroperasi normal|      | Kernel OOM-Killer Terpicu!    |
         +----------------------------+      +-------------------------------+
                       |                                   |
                       v                                   v
         +----------------------------+      +-------------------------------+
         |  cAdvisor Scrapes cgroups  |      | Kernel kirim SIGKILL (Code 9) |
         |  Exposes metrics to :8080  |      | Container Exit Code: 137      |
         +----------------------------+      | State.OOMKilled: TRUE         |
                       |                     +-------------------------------+
                       v
         +----------------------------+
         | Prometheus Scrape Engine   |
         | PromQL Alert:              |
         | container_memory_usage > 90|
         +----------------------------+
                       |
                       v
         +----------------------------+
         | Grafana Observability Dash |
         +----------------------------+
```

---

## 7. Analogy
Bayangkan cgroups limit adalah ukuran jaket pelampung di sebuah kapal.
- Jika beban berat Anda masih sesuai daya apung jaket, Anda berenang aman.
- Namun jika Anda membawa beban melebihi daya apung maksimum, penjaga pantai (OOM Killer) tidak punya pilihan selain memutus tali beban Anda secara paksa seketika agar kapal induk tidak ikut tenggelam.
- cAdvisor adalah pengukur sensor tekanan air yang terus-menerus memantau apakah Anda mulai tenggelam sebelum tali diputus.

---

## 8. Diagram: Mengapa Node.js/JVM Kerap Terkena OOM di Docker

```text
Kasus Masalah: Heap Runtime > Limit Cgroups
+-------------------------------------------------------------------------+
| Host Server RAM: 16 GB                                                  |
|   +-------------------------------------------------------------------+ |
|   | Container Docker (Limit Cgroups: --memory=512m)                   | |
|   |   +-------------------------------------------------------------+ | |
|   |   | Node.js / Java Runtime                                      | | |
|   |   | Mengira RAM tersedia adalah 16 GB (Host Memory)!            | | |
|   |   | V8 Heap mencoba mengalokasikan RAM hingga 2 GB              | | |
|   |   +-------------------------------------------------------------+ | |
|   |              |                                                    | |
|   |              x ---> CRASH! Alokasi mencapai 513MB                 | |
|   |                     Kernel OOM Killer mengirim SIGKILL (Code 137) | |
|   +-------------------------------------------------------------------+ |
+-------------------------------------------------------------------------+
```

---

## 9. Simple Example: Membaca Metrik via `docker stats`
Gunakan perintah bawaan CLI Docker untuk memantau penggunaan resource secara langsung di terminal:

```bash
# Pantau semua container yang aktif
docker stats

# Format output hanya untuk nama, CPU%, dan Memory usage
docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}"

# Snapshot satu kali tanpa streaming (berguna untuk script alerting bash)
docker stats --no-stream
```

---

## 10. Practical Example: Stack Observability Lengkap (cAdvisor + Prometheus)

File deklarasi `docker-compose.monitoring.yml`:

```yaml
version: '3.8'

services:
  cadvisor:
    image: gcr.io/cadvisor/cadvisor:v0.47.2
    container_name: monitoring-cadvisor
    privileged: true
    devices:
      - /dev/kmsg:/dev/kmsg
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
      - /dev/disk/:/dev/disk:ro
    ports:
      - "8080:8080"
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:v2.48.0
    container_name: monitoring-prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.retention.time=15d'
    restart: unless-stopped
```

Konfigurasi `prometheus.yml`:
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']
```

---

## 11. Real World Example: Diagnosa Investigasi OOM Killer di Production
Ketika sebuah pod atau container microservice mati mendadak, lakukan investigasi forensik berikut:

```bash
# 1. Cek status container dan Exit Code
docker ps -a --filter "name=payment-service" --format "table {{.ID}}\t{{.Status}}\t{{.State}}"

# 2. Periksa apakah container terbunuh oleh OOM Killer
docker inspect payment-service --format 'OOMKilled: {{.State.OOMKilled}} | ExitCode: {{.State.ExitCode}}'
# Output jika OOM: OOMKilled: true | ExitCode: 137

# 3. Periksa log kernel host Linux (dmesg)
sudo dmesg -T | grep -i -E "oom-killer|out of memory|killed process"
# Output sampel kernel:
# [Fri Sep 11 14:22:01 2026] Memory cgroup out of memory: Killed process 14201 (node) total-vm:1048576kB, anon-rss:524288kB
```

---

## 12. Trade-offs: Monitoring Approaches

| Pendekatan | Overhead CPU/RAM | Granularitas Metrik | Kompleksitas Setup |
|---|---|---|---|
| `docker stats` CLI | Mendekati 0% | Sangat Rendah (Real-time snapshot only) | 0 konfigurasi |
| Google cAdvisor Standalone | Rendah (~1-2% CPU) | Sangat Tinggi (Per-container cgroup data) | Sangat Rendah (1 Container) |
| Prometheus + cAdvisor + Grafana | Sedang (~200MB RAM) | Lengkap (Historical time-series, PromQL, Alerting) | Menengah (Multi-container stack) |
| APM Agent (Datadog / NewRelic) | Sedang - Tinggi | Luar biasa lengkap (Metrics + Distributed Traces) | Tinggi & Berbayar |

---

## 13. When To Use
- Gunakan **cAdvisor + Prometheus** di seluruh node host Docker standalone yang melayani traffic produksi.
- Selalu selaraskan limit memori container cgroups dengan batasan heap internal aplikasi.
- Selalu periksa `.State.OOMKilled` segera setelah container mati dengan Exit Code 137.

---

## 14. When NOT To Use
- Jangan jalankan cAdvisor di lingkungan production tanpa membatasi metrik atau storage Prometheus, karena metrik churn dari ephemeral container yang sering hidup-mati dapat membebani database time-series.

---

## 15. Common Mistakes
1. **Mengabaikan Node.js V8 Memory Limit**: Menetapkan `--memory=512m` pada container, namun tidak menyetel `NODE_OPTIONS="--max-old-space-size=400"`. Garbage collector Node.js baru akan jalan saat heap mencapai ~1.4GB, sehingga OOM Killer membunuh container sebelum GC sempat berjalan!
2. **Mengira Exit Code 137 Selalu OOM**: Exit Code 137 juga terjadi jika Anda menjalankan `docker stop` dan aplikasi Anda tidak merespons `SIGTERM` dalam 10 detik sehingga Docker mengirimkan `SIGKILL`. Selalu validasi dengan field `{{.State.OOMKilled}}`.
3. **Lupa memberi izin eksekusi (`chmod +x`)** pada script `entrypoint.sh`, menghasilkan Exit Code 126.

---

## 16. Best Practices
### Must Have
- Untuk Node.js: Atur `--max-old-space-size` bernilai 75-80% dari memory limit cgroups container:
  ```dockerfile
  ENV NODE_OPTIONS="--max-old-space-size=384"
  ```
- Untuk Java/JVM: Gunakan OpenJDK 17+ dengan flag cgroups-aware:
  ```dockerfile
  CMD ["java", "-XX:InitialRAMPercentage=40.0", "-XX:MaxRAMPercentage=75.0", "-jar", "app.jar"]
  ```

### Recommended
- Buat Prometheus AlertRule untuk mendeteksi container dengan penggunaan memory > 85% dari kuota limit secara terus-menerus selama lebih dari 3 menit.
- Terapkan Graceful Shutdown handling di aplikasi Anda agar merespons `SIGTERM` (Exit Code 143) dalam waktu kurang dari 5 detik.

### Advanced
- Konfigurasikan memory swap ratio (`--memory-swap`) secara ketat di lingkungan latensi rendah untuk mencegah thrashing disk I/O swapping.

---

## 17. Troubleshooting Guide
### Problem: Node.js Container Restart Tanpa Ada Error Log Apapun
- **Gejala**: Log aplikasi berhenti di tengah request berat, lalu container langsung restart.
- **Penyebab**: Memory Leak atau processing payload raksasa memicu OOM Killer.
- **Langkah Solusi**:
  1. Jalankan `docker inspect <container> --format '{{.State.OOMKilled}}'`. Jika bernilai `true`, problem 100% adalah OOM.
  2. Tambahkan alokasi memory limit di Compose file:
     ```yaml
     deploy:
       resources:
         limits:
           memory: 1024M
     ```
  3. Profiling memory leak menggunakan Chrome DevTools / heapdump di development.

---

## 18. Exercises
### Level: Easy
1. Jalankan container yang sengaja keluar dengan kode error:
   `docker run --rm alpine sh -c "exit 1"`
   Periksa exit code-nya di terminal dengan `echo $?` (Linux/Mac) atau `$LASTEXITCODE` (PowerShell).
2. Jalankan container dengan binary yang tidak ada:
   `docker run --rm alpine nonexistent_command`
   Verifikasi bahwa exit code yang dihasilkan adalah **127**.

### Level: Medium
1. Jalankan container Alpine dengan batasan memory ketat 50MB:
   `docker run -d --name oom-lab --memory=50m alpine sh -c "python3 -c 'a = [1] * 100000000'"`
2. Periksa status dan kode keluar container tersebut setelah crash.
3. Gunakan `docker inspect oom-lab --format '{{.State.OOMKilled}}'` untuk mengonfirmasi bahwa pemicunya adalah OOM Killer.

### Level: Hard
1. Buat Docker Compose yang menyertakan service aplikasi dan cAdvisor.
2. Buka dashboard web cAdvisor di `http://localhost:8080` dan amati grafik pemakaian memori `working_set` vs `limit`.

---

## 19. Challenge
Tuliskan automated bash/node script watchdog yang berjalan sebagai cron/daemon di host:
- Memeriksa seluruh container Docker setiap 30 detik.
- Jika menemukan container yang exit dengan `OOMKilled: true`, script otomatis:
  1. Mencatat nama container, exit code, dan waktu kejadian ke file log audit `/var/log/docker-oom-audit.log`.
  2. Mengirimkan notifikasi alert (simulasi webhook).

---

## 20. Summary
- **Exit Code** adalah kunci tercepat untuk mengetahui penyebab kematian container: 0 (Normal), 1 (Bug App), 126/127 (Exec error), 137 (OOM / SIGKILL), 143 (SIGTERM).
- **Linux OOM Killer** secara agresif mematikan container yang melampaui alokasi cgroups memory untuk melindungi integritas host.
- Memastikan runtime heap (JVM `-XX:MaxRAMPercentage`, Node.js `--max-old-space-size`) dibatasi di bawah limit cgroups adalah mitigasi utama terhadap Exit Code 137.
- **cAdvisor dan Prometheus** menyediakan visibilitas historis terhadap metrik pemakaian resource container.

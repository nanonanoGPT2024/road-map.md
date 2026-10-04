# Module 01: Docker Logging Drivers, Log Rotation, dan Log Shippers

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
1. Memahami arsitektur penanganan log pada Docker Engine dari `stdout`/`stderr` proses container hingga disk host atau remote collector.
2. Mengonfigurasi berbagai Docker Logging Drivers: `json-file`, `local`, `syslog`, `journald`, dan `fluentd`.
3. Mengatasi risiko disk overflow (disk space exhaustion) dengan menerapkan strategi **Log Rotation** (`max-size` dan `max-file`) baik secara global di `daemon.json` maupun per-container.
4. Memahami mode buffering logging: `mode=blocking` vs `mode=non-blocking` (`max-buffer-size`) dan dampaknya terhadap latency aplikasi.
5. Mengintegrasikan centralized log shipper (seperti Promtail/Loki atau Fluent Bit) untuk agregasi log production.

---

## 2. Prerequisite
- Memahami konsep Container Lifecycle dan CLI Docker dasar ([BAB 02 Module 01](../BAB-02-Container-Lifecycle-dan-CLI-Mastery/Module-01-Siklus-Hidup-Container-State-Machine-dan-CLI-Esensial.md)).
- Memahami konfigurasi Docker Compose V2 ([BAB 06](../BAB-06-Multi-Container-dengan-Docker-Compose/)).
- Pemahaman dasar Linux standard streams: Standard Output (`stdout`, FD 1) dan Standard Error (`stderr`, FD 2).

---

## 3. Concept
Secara default, container mengikuti prinsip *The Twelve-Factor App* (Prinsip XI: Logs): sebuah container tidak boleh memikirkan pengelolaan routing atau penyimpanan file log-nya sendiri. Aplikasi di dalam container cukup menuliskan event log secara streaming ke `stdout` dan `stderr`.

Docker Daemon mengintercept stream output tersebut melalui container runtime (`containerd` / shim) dan meneruskannya ke **Logging Driver** yang aktif. Secara default, Docker menggunakan driver `json-file` (atau `local` pada instalasi terbaru). Setiap baris log dibungkus dalam format JSON bersama timestamp dan stream origin, lalu ditulis ke file di `/var/lib/docker/containers/<container-id>/<container-id>-json.log`.

Jika log rotation tidak diaktifkan, file JSON ini akan terus tumbuh tanpa batas hingga menghabiskan seluruh sisa kapasitas hard disk host, yang pada akhirnya dapat melumpuhkan seluruh sistem operasi host!

---

## 4. Why?
Mengapa pengelolaan logging driver sangat krusial?
1. **Mencegah "Host Out of Disk" Fatal Crash**: File log yang tidak dirotasi dapat mencapai puluhan hingga ratusan gigabyte, menyebabkan Linux kernel menolak alokasi disk baru dan memicu crash database/aplikasi host.
2. **Backpressure & Latency Isolation**: Driver logging dengan mode `blocking` dapat menahan thread eksekusi aplikasi jika disk I/O sedang lambat. Memahami `mode=non-blocking` mencegah throughput bottleneck.
3. **Observabilitas Terpusat (Centralized Logging)**: Di lingkungan production multi-node, mengakses log satu per satu via `docker logs` tidak praktis. Log harus di-stream secara real-time ke agregator (Elasticsearch, Grafana Loki, Datadog).

---

## 5. What?
### Spektrum Docker Logging Drivers:

| Driver | Deskripsi | Kelebihan | Kekurangan |
|---|---|---|---|
| `json-file` | Driver default lawas; log disimpan dalam format baris JSON di disk lokal. | Kompatibel penuh dengan `docker logs`. | Ukuran membengkak cepat jika tanpa rotasi; parsing JSON memakan CPU. |
| `local` | Driver default modern (disarankan Docker); menggunakan format biner internal terkompresi. | Otomatis log rotation default (100MB x 5 file), hemat disk & CPU. | Hanya bisa dibaca oleh daemon lokal via `docker logs`. |
| `syslog` | Mengirim stream log ke service Syslog daemon lokal atau remote syslog server RFC 5424. | Standar industri OS Linux, mudah diintegrasikan dengan SIEM. | Tidak mendukung `docker logs` lokal jika dikirim ke remote. |
| `journald` | Menulis stream log langsung ke `systemd-journald`. | Terintegrasi dengan logging sistem operasi Linux modern. | Terbatas pada OS yang menjalankan systemd. |
| `fluentd` / `gelf` | Mengirim log langsung ke collector (Fluentd/Fluent Bit atau Graylog) via TCP/UDP socket. | Langsung terpusat tanpa menulis file lokal ke disk host. | Jika collector down dan mode blocking, container bisa macet. |

---

## 6. How? Arsitektur Logging Docker Engine

```text
  +-------------------------------------------------------------+
  |                   Container Namespace                       |
  |  App (Node.js/Go) -> process stdout (FD 1) & stderr (FD 2)  |
  +-------------------------------------------------------------+
                                |
                                v (FIFO pipe)
  +-------------------------------------------------------------+
  |              containerd-shim / containerd                   |
  +-------------------------------------------------------------+
                                |
                                v
  +-------------------------------------------------------------+
  |                     Docker Daemon                           |
  |                                                             |
  |   Logging Driver Engine:                                    |
  |   +-------------------+      +--------------------------+   |
  |   | mode: blocking    | ATAU | mode: non-blocking       |   |
  |   | (Sync backpressure|      | (Ring buffer in-memory)  |   |
  |   +-------------------+      +--------------------------+   |
  |             |                             |                 |
  |             +--------------+--------------+                 |
  |                            |                                |
  |                            v                                |
  |       +-----------------------------------------+           |
  |       |        Active Logging Driver            |           |
  |       |  - json-file (max-size: 10m, max-file:3)|           |
  |       |  - local                                |           |
  |       |  - fluentd / syslog                     |           |
  +-------+-----------------------------------------+-----------+
                               |
               +---------------+---------------+
               |                               |
               v                               v
    /var/lib/docker/containers/...    Remote Collector / Loki
```

---

## 7. Analogy
Bayangkan container Anda adalah seorang kasir toko yang mencetak struk transaksi (log).
- **Tanpa Log Rotation (`json-file` default)**: Kasir terus mencetak struk dan membiarkannya menumpuk di lantai toko. Lama-kelamaan struk memenuhi seluruh ruangan toko hingga kasir dan pembeli tidak bisa bergerak lagi (Disk Full).
- **Dengan Log Rotation (`max-size=10m, max-file=3`)**: Kasir memasukkan struk ke tempat sampah khusus yang hanya muat 10 meter kertas struk. Ketika penuh, tempat sampah paling lama dibuang dan diganti dengan yang baru, dengan maksimal hanya menyimpan 3 tempat sampah. Ruangan toko selalu bersih dan terjaga.
- **Mode Non-Blocking**: Jika mesin pembuangan struk sedang sibuk, kasir tetap melayani pembeli berikutnya tanpa menunggu mesin selesai, menaruh struk sementara di keranjang penyangga (buffer).

---

## 8. Diagram: Blocking vs Non-Blocking Logging Mode

```text
Mode: BLOCKING (Default)
App Process (stdout) ---> [ Docker Logging Driver ] ---> [ Slow Disk / Remote Collector ]
(Jika disk/network lag, aplikasi TERHENTI / BLOCKED menunggu proses tulis selesai!)

Mode: NON-BLOCKING (Direkomendasikan untuk High-Throughput)
App Process (stdout) ---> [ In-Memory Ring Buffer ] ---> [ Background Worker ] ---> [ Disk/Network ]
(Aplikasi langsung return 0ms! Jika buffer penuh, log tertua di-drop demi menjaga stabilitas app)
```

---

## 9. Simple Example: Konfigurasi Log Rotation Global
Untuk mencegah disk overflow di seluruh server, konfigurasikan `daemon.json` di `/etc/docker/daemon.json`:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3",
    "mode": "non-blocking",
    "max-buffer-size": "4m"
  }
}
```
*Terapkan konfigurasi dengan me-reload daemon*:
```bash
sudo systemctl reload docker
```

---

## 10. Practical Example: Konfigurasi Logging di Docker Compose
Anda dapat mengesampingkan (override) setting logging per-service secara deklaratif:

```yaml
version: '3.8'

services:
  payment-api:
    image: mycompany/payment-api:v1.2.0
    restart: unless-stopped
    ports:
      - "8080:8080"
    logging:
      driver: "json-file"
      options:
        max-size: "20m"
        max-file: "5"
        mode: "non-blocking"
        max-buffer-size": "2m"
        labels: "production,fintech"
        tag: "{{.ImageName}}/{{.Name}}/{{.ID}}"

  high-throughput-worker:
    image: mycompany/event-worker:v1.0.0
    restart: always
    logging:
      driver: "local"
      options:
        max-size: "50m"
        max-file: "3"
        compress: "true"
```

---

## 11. Real World Example: Arsitektur Production Promtail + Grafana Loki
Di lingkungan production modern, log dikumpulkan oleh **Promtail** (agen ringan dari Grafana) yang membaca file log Docker di host dan meneruskannya ke **Grafana Loki**:

```yaml
# docker-compose.logging.yml
version: '3.8'

services:
  loki:
    image: grafana/loki:2.9.2
    ports:
      - "3100:3100"
    command: -config.file=/etc/loki/local-config.yaml

  promtail:
    image: grafana/promtail:2.9.2
    volumes:
      # Mount direktori container log dari host
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./promtail-config.yaml:/etc/promtail/config.yaml:ro
    command: -config.file=/etc/promtail/config.yaml

  grafana:
    image: grafana/grafana:10.2.0
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

---

## 12. Trade-offs: Driver Matrix

| Opsi Driver | Kompatibilitas `docker logs` | Ketahanan terhadap Crash | Efisiensi Disk Host | Latency Overhead |
|---|---|---|---|---|
| `json-file` (unlimited) | Sangat Baik | Sangat Buruk (Disk Overflow) | Terburuk | Sedang |
| `json-file` (rotasi) | Sangat Baik | Sangat Baik | Baik | Sedang |
| `local` (rotasi + kompresi) | Sangat Baik | Sempurna | Terbaik (Biner) | Sangat Rendah |
| `fluentd` / `syslog` | Tidak Bisa (Remote Only) | Tergantung Collector | Sempurna (No local disk) | Sangat Rendah (Non-blocking) |

---

## 13. When To Use
- **Gunakan driver `local`**: Untuk node standalone, server development, atau micro-instance di mana Anda ingin jaminan log terkompresi otomatis tanpa membebani storage.
- **Gunakan driver `json-file` dengan rotasi eksplisit**: Jika Anda masih bergantung pada tool log parser konvensional (Promtail/Filebeat) yang membaca path `/var/lib/docker/containers/*/*-json.log`.
- **Gunakan `mode: non-blocking`**: Pada service yang memproses traffic tinggi (high-throughput API, payment gateway, streaming) agar proses I/O log tidak pernah memblokir thread HTTP event-loop.

---

## 14. When NOT To Use
- **Jangan gunakan driver non-lokal (seperti `awslogs`, `syslog`, `fluentd`) tanpa buffer non-blocking**: Jika jaringan ke AWS CloudWatch atau remote Fluentd putus dan mode tetap `blocking`, seluruh container akan macet (freeze) karena buffer pipe tersumbat!
- **Jangan biarkan `json-file` tanpa parameter `max-size` di server mana pun**: Ini adalah kesalahan nomor satu penyebab downtime server Docker di industri.

---

## 15. Common Mistakes
1. **Mengabaikan ukuran log default `json-file`**: Banyak tim baru menyadari masalah ini ketika database Postgres host menolak penulisan disk karena disk host 100% penuh oleh file log Docker.
2. **Menulis file log ke dalam filesystem container internal**: Aplikasi yang menulis ke `/var/log/app.log` di dalam container membuat layer read-write container membengkak dan log tidak terbaca oleh `docker logs`.
3. **Menggunakan `mode=blocking` dengan remote logging**: Mengakibatkan timeout request HTTP jika endpoint logging remote mengalami lonjakan latensi.

---

## 16. Best Practices
### Must Have
- Terapkan konfigurasi global di `/etc/docker/daemon.json` dengan batasan `max-size: "10m"` dan `max-file: "3"`.
- Pastikan semua container menulis log HANYA ke `stdout` (FD 1) dan `stderr` (FD 2).

### Recommended
- Gunakan `mode: "non-blocking"` dengan `max-buffer-size: "4m"` untuk aplikasi web API yang sensitif terhadap latensi.
- Berikan format log terstruktur (**Structured JSON Logging**) langsung dari aplikasi Anda (`{"level":"info","msg":"User logged in","userId":123}`) agar mudah difilter oleh Loki/Elasticsearch.

### Advanced
- Konfigurasikan dynamic logging labels (`labels` atau `env`) pada Docker daemon untuk secara otomatis menambahkan metadata lingkungan (`environment=production`, `service_name=auth`) ke setiap baris log.

---

## 17. Troubleshooting Guide
### Problem 1: Hard disk host 100% full karena log container raksasa
- **Gejala**: `no space left on device`, Docker engine tidak bisa memunculkan container baru.
- **Diagnosa**:
  ```bash
  # Cari file json.log terbesar di sistem
  du -ah /var/lib/docker/containers/ | grep -E '\.log$' | sort -rh | head -n 10
  ```
- **Solusi Darurat**:
  Truncate file log yang membengkak tanpa me-restart container (menghapus file langsung via `rm` dapat menyebabkan descriptor file bocor):
  ```bash
  # Truncate isi file menjadi 0 byte dengan aman
  truncate -s 0 /var/lib/docker/containers/<container-id>/<container-id>-json.log
  ```
  Kemudian segera pasang `max-size` dan `max-file` di Compose file atau daemon.json.

### Problem 2: `docker logs` lambat merespon atau memakan CPU tinggi
- **Penyebab**: File log berukuran gigabyte tanpa rotasi sedang dibaca dan diparsing seluruhnya oleh daemon.
- **Solusi**: Gunakan flag filter `--tail` atau `--since`:
  ```bash
  docker logs --tail 100 -f <container_name>
  docker logs --since 10m <container_name>
  ```

---

## 18. Exercises
### Level: Easy
1. Jalankan container Alpine yang menghasilkan log setiap detik:
   `docker run -d --name log-test alpine sh -c "while true; do echo Log at \$(date); sleep 1; done"`
2. Periksa output log menggunakan `docker logs -f log-test`.
3. Batasi output log hanya untuk 5 baris terakhir menggunakan flag `--tail 5`.

### Level: Medium
1. Jalankan container dengan parameter log rotation eksplisit:
   `docker run -d --name rot-test --log-opt max-size=1k --log-opt max-file=3 alpine sh -c "while true; do echo 'Simulasi pesan log berukuran panjang untuk rotasi cepat'; sleep 0.1; done"`
2. Amati bagaimana Docker membuat file cadangan log (`.1`, `.2`) di direktori `/var/lib/docker/containers/`.

### Level: Hard
1. Buat stack Docker Compose yang menjalankan service API dan Promtail.
2. Konfigurasikan Promtail untuk mem-parse JSON log dari Docker container dan mengekstrak field log level (`INFO`, `WARN`, `ERROR`).

---

## 19. Challenge
Rancang arsitektur logging zero-loss vs low-latency untuk sistem transaksi perbankan:
- Service Transaksi Finansial menuntut log tidak boleh hilang sama sekali (Audit Trail compliance).
- Service Notifikasi Promo menuntut latency minimal dan toleran jika ada pesan log non-kritis yang ter-drop saat traffic spike.
Tuliskan konfigurasi driver, mode (`blocking` vs `non-blocking`), dan buffering untuk masing-masing service dalam satu file `docker-compose.yml`.

---

## 20. Summary
- Docker mengintercept stream `stdout` dan `stderr` lalu menyalurkannya melalui **Logging Drivers**.
- Driver default `json-file` tanpa rotasi merupakan risiko operasional terbesar yang dapat menghabiskan disk host.
- Selalu batasi log dengan `max-size` dan `max-file` baik di level global daemon maupun service compose.
- Gunakan `mode: non-blocking` untuk aplikasi high-throughput guna mengisolasi latency aplikasi dari proses I/O penulisan log.

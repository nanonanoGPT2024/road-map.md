# Module 02: Reverse Proxy & Web Server Hardening (Nginx & Envoy)

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar akan mampu:
1. Membedakan arsitektur *Forward Proxy* vs *Reverse Proxy* dan perannya sebagai gerbang depan (*edge ingress*).
2. Mengonfigurasi **Nginx** untuk load balancing (Round Robin, Least Connections, IP Hash), SSL Termination, dan caching statis.
3. Menerapkan penguatan keamanan (*Security Hardening*): Header keamanan (HSTS, CSP), mitigasi Slowloris / DDoS (Rate Limiting), dan menyembunyikan identitas versi server.
4. Memahami evolusi modern reverse proxy menuju **Envoy Proxy** (Service Mesh data plane & dynamic configuration via gRPC/xDS).

---

## 2. Prerequisite
- Memahami protokol TCP, DNS, dan enkripsi TLS dari [BAB 02 Module 01](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-02-Jaringan-Protokol-dan-Web-Servers/Module-01-Jaringan-Komputer-OSI-TCP-DNS-TLS.md).
- Mengetahui struktur request HTTP/1.1 dan HTTP/2 (Headers, Status Codes, Body).

---

## 3. Concept
Aplikasi backend (seperti Node.js Express, Python FastAPI, atau Go Gin) tidak dirancang untuk langsung terekspos ke internet publik tanpa perlindungan:
- Mereka rentan kehabisan thread akibat serangan koneksi lambat (*Slowloris*).
- Menangani terminasi enkripsi TLS di dalam kode aplikasi membebani CPU runtime.
- Mereka tidak memiliki mekanisme caching respon atau kompresi gzip/brotli bawaan yang secepat engine C/C++.

Di sinilah peran **Reverse Proxy**:
Sebuah server perantara yang berada di depan upstream backend. Client luar internet berkomunikasi dengan Reverse Proxy (misal Nginx atau Envoy), lalu proxy meneruskan request ke upstream server di jaringan privat (VPC / Docker network) secara efisien dan aman.

---

## 4. Why?
Mengapa Reverse Proxy mutlak diperlukan di arsitektur produksi?
1. **SSL/TLS Offloading (Termination)**: Beban kriptografi enkripsi/dekripsi ditangani terpusat oleh Nginx menggunakan akselerasi hardware, sehingga server backend murni fokus pada logika bisnis.
2. **High Availability & Load Balancing**: Jika salah satu instance backend mati, proxy otomatis mengalihkan traffic ke instance lain tanpa downtime (*Zero-Downtime Healthcheck*).
3. **Perlindungan Keamanan (Shielding)**: IP address server database dan backend tersembunyi sepenuhnya dari internet; proxy menyaring serangan SQL injection, bad bots, dan rate-limit IP mencurigakan.

---

## 5. What?
Komponen penting dalam arsitektur Nginx & Envoy:
- **Upstream Block**: Definisi kumpulan server backend tujuan beserta bobot (*weight*) dan algoritma load balancing.
- **Location Matching**: Blok perutean URL path (`location /api/ { proxy_pass ...; }`).
- **Rate Limiting Zones**: Membatasi jumlah request per detik per client IP menggunakan algoritma *Leaky Bucket* / *Token Bucket* (`limit_req_zone`).
- **Buffer & Timeout Directives**: Melindungi backend dari request payload raksasa atau koneksi gantung (`proxy_read_timeout`, `client_max_body_size`).

---

## 6. How?
Alur pemrosesan request pada Nginx Reverse Proxy:

```text
[ Internet Client: https://app.example.com/api/v1/orders ]
                              │
                              ▼
            [ Nginx Reverse Proxy (:443) ]
  - 1. TLS Termination (Dekripsi HTTPS -> HTTP)
  - 2. Security Filtering (Cek Rate Limit IP)
  - 3. Path Matching: /api/ -> Forward ke Upstream Pool
                              │
            ┌─────────────────┴─────────────────┐
            │ Load Balancing: Least Connections │
            ▼                                   ▼
[ Backend Node 1 (10.0.1.10:3000) ]   [ Backend Node 2 (10.0.1.11:3000) ]
```

---

## 7. Analogy
Bayangkan **Reverse Proxy** seperti **Resepsionis & Petugas Keamanan di Lobi Gedung Korporat**:
- Tamu luar (Client Internet) tidak boleh langsung masuk ke ruang kerja staf teknis (Backend Servers).
- Tamu wajib lapor ke Resepsionis (Reverse Proxy).
- Petugas memeriksa identitas tamu, menyaring orang jahat (Security Filtering / Rate Limit), mengambil mantel tebal tamu (SSL Termination), lalu mengarahkan tamu ke ruangan konsultan yang sedang kosong (Load Balancing).

---

## 8. Diagram
```text
+---------------------+
|   Internet Client   |
+---------------------+
           |
           | HTTPS:443 (Encrypted)
           v
+-------------------------------------------------------------+
|                     NGINX REVERSE PROXY                     |
|  - SSL Termination: Let's Encrypt Cert                      |
|  - Rate Limit: 10 req/sec per IP                            |
|  - Security Headers: HSTS, X-Frame-Options                  |
|  - Static Assets Cache: /static/* (Expires 30d)             |
+-------------------------------------------------------------+
           |                                  |
           | HTTP:3000 (Private)              | HTTP:3000 (Private)
           v                                  v
+-----------------------+          +-----------------------+
| Upstream Worker 01    |          | Upstream Worker 02    |
| 10.0.1.5:3000         |          | 10.0.1.6:3000         |
+-----------------------+          +-----------------------+
```

---

## 9. Simple Example
Konfigurasi Nginx produksi yang aman (`/etc/nginx/sites-available/app.conf`):

```nginx
upstream backend_cluster {
    least_conn;
    server 10.0.1.10:3000 max_fails=3 fail_timeout=10s;
    server 10.0.1.11:3000 max_fails=3 fail_timeout=10s;
    keepalive 32;
}

# Rate limit zone: 10 MB memori untuk menyimpan IP, maks 10 req/detik
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

server {
    listen 80;
    server_name app.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name app.example.com;

    # SSL Config
    ssl_certificate /etc/letsencrypt/live/app.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    # Security Hardening Headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
    server_tokens off; # Sembunyikan versi Nginx

    location / {
        limit_req zone=api_limit burst=20 nodelay;

        proxy_pass http://backend_cluster;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 10. Practical Example
Simulasi implementasi Reverse Proxy & Load Balancer sederhana di Node.js:

```javascript
const http = require('http');

const BACKENDS = [
  { host: '127.0.0.1', port: 3001, activeConnections: 0 },
  { host: '127.0.0.1', port: 3002, activeConnections: 0 }
];

function getLeastConnectionBackend() {
  return BACKENDS.reduce((prev, curr) => curr.activeConnections < prev.activeConnections ? curr : prev);
}

const proxy = http.createServer((req, res) => {
  const target = getLeastConnectionBackend();
  target.activeConnections++;

  const proxyReq = http.request({
    host: target.host,
    port: target.port,
    method: req.method,
    path: req.url,
    headers: { ...req.headers, 'x-forwarded-for': req.socket.remoteAddress }
  }, (proxyRes) => {
    target.activeConnections--;
    res.writeHead(proxyRes.statusCode, proxyRes.headers);
    proxyRes.pipe(res);
  });

  proxyReq.on('error', () => {
    target.activeConnections--;
    res.writeHead(502, { 'Content-Type': 'text/plain' });
    res.end('Bad Gateway: Upstream failure');
  });

  req.pipe(proxyReq);
});
```

---

## 11. Real World Example
### Kasus: Flash Sale DDoS vs Token Bucket Rate Limiting
1. Situs e-commerce diserang bot scalper yang mengirim 50.000 request checkout per detik dari botnet terdistribusi.
2. Nginx dikonfigurasi dengan:
   ```nginx
   limit_req_zone $binary_remote_addr zone=checkout:10m rate=2r/s;
   limit_req_status 429;
   ```
3. Nginx menahan lonjakan di layer terluar, mengembalikan status `HTTP 429 Too Many Requests` dalam waktu < 1 ms tanpa membebani server database.
4. Database production tetap stabil pada utilisasi CPU 40% dan pelanggan asli berhasil melakukan transaksi normal.

---

## 12. Trade-offs
| Komponen | Nginx | Envoy Proxy |
|---|---|---|
| **Model Konfigurasi** | Konfigurasi statis file (reload via `nginx -s reload`) | Konfigurasi dinamis via gRPC API (xDS APIs) tanpa reload |
| **Arsitektur Threading** | Event-driven multi-process | Multi-threaded asynchronous event-loop |
| **Observabilitas Bawaan** | Access log teks (perlu exporter pihak ketiga untuk Prometheus) | Metrik Prometheus & tracing Jaeger/Zipkin bawaan |
| **Kesesuaian** | Traditional web servers, Edge reverse proxy, VM | Kubernetes Ingress, Service Mesh (Istio), gRPC proxying |

---

## 13. When To Use
- Gunakan **Nginx**: Untuk edge reverse proxy umum, serving asset statis, SSL termination sederhana, dan server monolitik/VM.
- Gunakan **Envoy**: Untuk infrastruktur microservices skala besar di Kubernetes, perutean traffic gRPC, dan kebutuhan dynamic hot-reloading konfigurasi.

---

## 14. When NOT To Use
- Jangan membebani reverse proxy dengan komputasi logika bisnis berat (parsing JWT kompleks atau database querying); serahkan komputasi ke upstream backend service.

---

## 15. Common Mistakes
1. **Lupa Mengirim Header `X-Forwarded-For`**: Upstream backend membaca semua request berasal dari IP `127.0.0.1` (IP proxy), membuat audit log dan geolocation client menjadi tidak valid.
2. **`server_tokens on;`**: Membiarkan banner versi Nginx muncul (`Nginx/1.18.0 (Ubuntu)`), memudahkan peretas mencari celah CVE spesifik.
3. **Mengabaikan `keepalive` pada Upstream**: Membuka koneksi TCP baru untuk setiap request ke upstream, memicu kehabisan socket port (*socket exhaustion* / TIME_WAIT spike).

---

## 16. Best Practices
### Must Have
- Tambahkan `server_tokens off;` untuk menyembunyikan versi web server.
- Teruskan header IP asli client: `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`.
- Pasang `limit_req` rate limiting pada endpoint sensitif (seperti `/api/login` atau `/checkout`).

### Recommended
- Konfigurasikan `keepalive 32;` pada blok upstream untuk me-reuse koneksi TCP ke backend.
- Aktifkan `gzip` atau `brotli` compression untuk asset teks (JSON, HTML, CSS, JS) di atas 1KB.

### Avoid / Overengineering
- Jangan melakukan caching dinamis data user sensitif (seperti `/api/profile`) di Nginx cache tanpa header `Cache-Control: private`.

---

## 17. Troubleshooting
| Gejala | Kemungkinan Penyebab | Solusi |
|---|---|---|
| Browser menampilkan `502 Bad Gateway` | Upstream backend mati atau salah port di `proxy_pass` | Periksa status aplikasi backend (`systemctl status app`) dan port listening (`ss -tulpn`) |
| Browser menampilkan `504 Gateway Timeout` | Upstream backend membutuhkan waktu pemrosesan lebih lama dari `proxy_read_timeout` (default: 60s) | Naikkan `proxy_read_timeout` atau optimasi query database yang lambat |
| Nginx error log memuat `worker_connections are not enough` | Batas koneksi per worker process terlalu kecil | Naikkan `worker_connections 2048;` dan sesuaikan `ulimit -n` sistem |

---

## 18. Exercise
1. Tulis blok konfigurasi Nginx `upstream` yang menggunakan algoritma `least_conn` dengan 3 server backend.
2. Konfigurasikan rate limit Nginx yang membatasi 5 request per detik dengan burst 10 request.

---

## 19. Challenge
Rancang arsitektur simulasi **Dynamic Reverse Proxy & Load Balancer**:
- Mendukung algoritma load balancing Round-Robin dan Least-Connections.
- Memiliki fitur *Passive Health Check*: Jika salah satu backend gagal merespons (HTTP 5xx), tandai sebagai *unhealthy* dan alihkan request berikutnya ke server sehat.

---

## 20. Summary
- Reverse Proxy melindungi backend, mengoptimalkan resource via SSL termination, dan membagi beban kerja secara cerdas.
- Nginx unggul dalam kestabilan dan kemudahan konfigurasi statis, sementara Envoy menjadi standar arsitektur service mesh modern di Kubernetes.
- Modul praktikum lab dapat dijalankan langsung di [hands-on/m02/nginx_reverse_proxy_sim.js](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-02-Jaringan-Protokol-dan-Web-Servers/hands-on/m02/nginx_reverse_proxy_sim.js).

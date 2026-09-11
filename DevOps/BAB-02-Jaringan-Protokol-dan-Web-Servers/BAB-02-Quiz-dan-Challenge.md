# BAB 02: Quiz, Challenge, & Knowledge Check
**Jaringan, Protokol Internet, & Web Servers**

---

## 1. Basic Questions (5 Soal)
1. Pada layer model OSI keberapakah protokol IP (Internet Protocol) dan TCP beroperasi?
2. Jelaskan urutan pertukaran pesan pada proses pembentukan koneksi *TCP 3-Way Handshake*!
3. Apa fungsi dari record DNS tipe `A`, `CNAME`, dan `MX`?
4. Apa perbedaan utama antara *Forward Proxy* (proxy depan) dan *Reverse Proxy* (proxy balik)?
5. Mengapa parameter `server_tokens off;` di Nginx disarankan selalu diaktifkan pada server produksi?

---

## 2. Intermediate Questions (5 Soal)
6. Apa yang dimaksud dengan *SSL/TLS Offloading (Termination)* pada Nginx, dan apa manfaatnya bagi performa server backend?
7. Mengapa pengaturan DNS TTL (*Time-to-Live*) yang terlalu lama (misal 86.400 detik) dapat membahayakan saat terjadi situasi darurat *Disaster Recovery*?
8. Bagaimana cara kerja algoritma load balancing *Least Connections* dibandingkan dengan *Round Robin*? Pada skenario seperti apa *Least Connections* lebih unggul?
9. Apa fungsi dari header HTTP `X-Forwarded-For` dan `X-Forwarded-Proto` yang disuntikkan oleh Reverse Proxy ke upstream backend?
10. Mengapa Envoy Proxy menjadi pilihan standar sebagai *Data Plane* di ekosistem Kubernetes Service Mesh (seperti Istio) dibandingkan Nginx tradisional?

---

## 3. Scenario-Based Questions (3 Soal)

### Skenario A: The Flash Sale 504 Gateway Timeout
Saat flash sale dimulai, ribuan pembeli mengakses halaman checkout. Nginx tiba-tiba mengembalikan error `HTTP 504 Gateway Timeout`. Saat diperiksa, CPU server Nginx hanya 15%, namun server backend database mengalami antrean query lambat selama 70 detik.
- *Pertanyaan:* Mengapa Nginx memunculkan status 504 alih-alih 502, dan penyesuaian parameter timeout serta connection pooling apa yang harus dilakukan di level Nginx?

### Skenario B: The Spoofed Client IP Security Hole
Aplikasi pembayaran Anda menggunakan client IP untuk membatasi akses admin (`if (req.ip !== '203.0.113.1') forbid()`). Namun, aplikasi membaca header `X-Forwarded-For` tanpa memverifikasi apakah request melewati trusted proxy Nginx terlebih dahulu.
- *Pertanyaan:* Bagaimana penyerang dapat memalsukan IP mereka (*IP spoofing*), dan bagaimana konfigurasi modul `real_ip` di Nginx untuk mengamankan pembacaan IP client?

### Skenario C: The Expired Wildcard TLS Disaster
Sebuah perusahaan menggunakan sertifikat SSL wildcard `*.company.com`. Suatu hari sertifikat kedaluwarsa. Setelah sertifikat baru diunggah ke Nginx, beberapa pengguna mobile di Android versi lama tetap gagal terkoneksi dengan pesan `Untrusted Root Certificate Authority`.
- *Pertanyaan:* Mengapa sertifikat perantara (*Intermediate CA / Certificate Chain bundle*) wajib disertakan dalam file `fullchain.pem` di Nginx?

---

## 4. Chapter Challenge
**Tantangan Praktis: The Hardened Zero-Trust Reverse Proxy**
Rancang sebuah konfigurasi Nginx lengkap yang:
1. Mengarahkan seluruh traffic HTTP (port 80) secara otomatis ke HTTPS (port 443) dengan kode 301 Permanent Redirect.
2. Membagi beban kerja ke 3 backend server menggunakan algoritma `least_conn`.
3. Membatasi rate request pada endpoint `/api/v1/auth` maksimal 5 request per detik per client IP.
4. Menyuntikkan security headers: `Strict-Transport-Security`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`.
5. Menangani halaman error kustom yang rapi saat upstream mengalami error `502` atau `504`.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur OSI 7-Layer vs TCP/IP 4-Layer.
- [ ] Mekanisme TCP Handshake, Retransmission, dan Flow Control.
- [ ] Alur resolusi DNS dari recursive resolver hingga authoritative nameserver.
- [ ] Proses pertukaran kunci kriptografi TLS 1.3 dan validasi sertifikat X.509.
- [ ] Peran Reverse Proxy dalam SSL termination, rate limiting, dan load balancing.

### Saya tidak perlu menghafal:
- [ ] Ratusan cipher suite heksadesimal kuno (cukup gunakan konfigurasi rekomendasi Mozilla SSL Generator).
- [ ] Seluruh nomor port IANA (cukup pahami port standar: 22, 53, 80, 443, 3306, 5432, 6379).

### Saya harus bisa melakukan:
- [ ] Melakukan troubleshooting konektivitas jaringan menggunakan `dig`, `nc`, `curl -Iv`, dan `ss`.
- [ ] Menulis konfigurasi Nginx reverse proxy yang aman dan tahan banting.
- [ ] Mengonfigurasi rate limiting untuk melindungi backend dari lonjakan request berlebih.

---
*Ketik **LANJUT** untuk berpindah ke BAB 03: Containerization dengan Docker Modern.*

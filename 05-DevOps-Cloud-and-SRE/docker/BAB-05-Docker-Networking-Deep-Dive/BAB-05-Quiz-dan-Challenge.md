# BAB 05 — Quiz, Challenge, & Knowledge Check: Docker Networking Deep Dive

## A. Quiz Evaluasi Pemahaman

### Bagian 1: Soal Tingkat Dasar (Basic)
1. Sebutkan dan jelaskan fungsi dari 4 Network Drivers bawaan Docker: `bridge`, `host`, `none`, dan `overlay`!
2. Mengapa perintah `ping <container_name>` gagal saat dijalankan di antara dua container yang berada di **Default Bridge (`docker0`)**?
3. Pada alamat IP berapakah server **Docker Embedded DNS** beroperasi di dalam User-Defined Bridge network?
4. Apa perbedaan antara mempublikasikan port dengan `-p 8080:80` dan `-p 127.0.0.1:8080:80`?
5. Mengapa container yang menggunakan driver `--network host` mengabaikan flag publikasi port `-p`?

### Bagian 2: Soal Tingkat Menengah (Intermediate)
6. Jelaskan bagaimana kernel Linux dan tabel `iptables` rantai `DOCKER` melakukan translasi alamat tujuan (*Destination NAT / DNAT*) saat paket dari internet masuk ke port yang dipublikasikan!
7. Mengapa aturan firewall host Ubuntu (seperti UFW) secara default dapat ter-bypass ketika port container dipublikasikan dengan Docker?
8. Bagaimana konsep *Dual-Homed Container* (menghubungkan satu container ke dua jaringan berbeda) memungkinkan arsitektur API Gateway yang aman?
9. Apa perbedaan teknis antara driver `bridge` dan driver `macvlan` dalam hal bagaimana container terlihat di router jaringan fisik LAN?
10. Bagaimana cara kerja fitur *Network Aliasing* (`--alias`) dalam memberikan nama domain alternatif untuk satu container yang sama?

### Bagian 3: Pertanyaan Skenario Nyata (Scenario-Based)
11. **Skenario 1**: Sebuah tim WebRTC streaming video mengeluh bahwa server mengalami packet loss 12% dan latensi melonjak tinggi saat menangani 5.000 streaming video di atas Docker default bridge. Network driver apa yang harus digunakan untuk mengeliminasi overhead NAT dan bagaimana konfigurasinya?
12. **Skenario 2**: Sebuah aplikasi WordPress dan database MySQL dijalankan di server yang sama. Karena developer tidak membuat custom network, kedua container berjalan di default bridge. Tiba-tiba saat WordPress di-restart, koneksi database terputus karena IP container MySQL berubah dari `172.17.0.3` menjadi `172.17.0.4`. Bagaimana Anda mendesain solusi permanen menggunakan User-Defined Bridge?
13. **Skenario 3**: Sebuah audit penetrasi keamanan menemukan bahwa port database PostgreSQL produksi (port 5432) dapat diakses langsung oleh hacker dari internet publik, padahal firewall UFW host disetel `ufw default deny incoming`. Jelaskan mengapa hal ini terjadi dan bagaimana perintah `docker run` yang aman seharusnya ditulis!

---

## B. Practical Chapter Challenge: Zero-Trust 3-Tier Network Isolation

### Deskripsi Skenario
Rancang topologi jaringan microservices multi-tier yang aman untuk platform perbankan digital.

### Persyaratan Implementasi:
1. **Penyediaan Dua Jaringan Terisolasi**:
   - Jaringan `public-ingress-net` (Subnet: `172.25.1.0/24`).
   - Jaringan `secure-backend-net` (Subnet: `172.25.2.0/24`).
2. **Topologi Layanan**:
   - **Service Web Ingress (`web-nginx`)**: Hanya terhubung ke `public-ingress-net`, mengekspos port 80 ke publik.
   - **Service API Gateway (`core-api`)**: Terhubung ke KEDUA jaringan (`public-ingress-net` dan `secure-backend-net`) sebagai perantara yang sah.
   - **Service Database (`vault-postgres`)**: Hanya terhubung ke `secure-backend-net`, tanpa port yang diekspos ke host atau publik.
3. **Verifikasi Resolusi DNS & Isolasi**:
   - Buktikan bahwa `web-nginx` dapat me-resolve dan memanggil `core-api` menggunakan nama hostname DNS internal.
   - Buktikan bahwa `core-api` dapat me-resolve dan mengakses `vault-postgres` menggunakan alias `db`.
   - Buktikan secara empiris bahwa `web-nginx` **TIDAK BISA** melakukan ping atau membuka koneksi socket apa pun ke `vault-postgres`.

---

## C. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Arsitektur 5 Docker Network Drivers (Bridge, Host, None, Macvlan, Overlay).
- [ ] Peran virtual switch `docker0` dan pasangan `veth pair`.
- [ ] Mekanisme translasi iptables DNAT dan bypass firewall UFW.
- [ ] Perbedaan esensial Default Bridge vs User-Defined Bridge.
- [ ] Cara kerja Docker Embedded DNS di `127.0.0.11`.

### Saya Tidak Perlu Menghafal:
- [ ] Seluruh puluhan parameter konfigurasi BGP/EVPN routing driver Overlay.
- [ ] Sintaks kode biner dari frame paket ethernet 802.1q.

### Saya Harus Bisa Melakukan:
- [ ] Membuat custom network dengan `docker network create`.
- [ ] Menghubungkan container yang sedang aktif ke jaringan baru via `docker network connect`.
- [ ] Menginspeksi IP dan DNS resolver container menggunakan `docker network inspect`.
- [ ] Mempublikasikan port secara aman hanya ke antarmuka loopback `127.0.0.1`.

```text
Checklist Kesiapan BAB 05:
[ ] Memahami arsitektur Docker networking
[ ] Menjalankan hands-on network drivers & iptables m01
[ ] Menjalankan hands-on embedded DNS & segmentation m02
[ ] Mampu menjawab seluruh pertanyaan Quiz dan Skenario
```

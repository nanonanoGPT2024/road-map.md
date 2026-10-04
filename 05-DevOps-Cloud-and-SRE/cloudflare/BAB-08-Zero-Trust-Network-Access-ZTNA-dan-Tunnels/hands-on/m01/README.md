# Panduan Praktikum Mandiri Bab 08: Cloudflare Zero Trust Network Access (ZTNA) & Tunnels

Panduan ini mendampingi skrip simulasi dan menyediakan prosedur hands-on langsung untuk membangun arsitektur ZTNA menggunakan **Cloudflare Tunnel (`cloudflared`)**, **Cloudflare Access**, dan **Secure Web Gateway (SWG)**.

---

## 1. Menjalankan Skrip Verifikasi & Simulator
Skrip Python `cloudflared_tunnel_setup_sim.py` dirancang tanpa dependensi eksternal untuk menguji pemahaman Anda terhadap arsitektur token validation, device posture, and SWG filtering.

### Langkah Eksekusi:
```bash
cd hands-on/m01/
python3 cloudflared_tunnel_setup_sim.py
```

### Apa yang divalidasi oleh skrip:
1. Sintaks ingress file konfigurasi `cloudflared` (memastikan keberadaan catch-all rule).
2. Verifikasi kriptografis token `Cf-Access-Jwt-Assertion` (HMAC SHA-256).
3. Evaluasi Device Posture (memvalidasi flag BitLocker/FileVault dan WARP).
4. Gateway DNS Filtering simulator terhadap domain berbahaya (Phishing/Malware).
5. Mock HTTP Origin guard yang menolak setiap akses tanpa tanda tangan valid Cloudflare.

---

## 2. Lab Produksi Nyata: Konfigurasi Cloudflare Tunnel Outbound-Only

Jika Anda memiliki domain aktif di Cloudflare, ikuti langkah berikut pada Linux Server Anda (Ubuntu/Debian):

### Langkah 1: Instalasi `cloudflared`
```bash
# Tambahkan repo resmi Cloudflare
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null

echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflared.list

sudo apt-get update && sudo apt-get install -y cloudflared
```

### Langkah 2: Autentikasi dan Pembuatan Tunnel
```bash
# Login ke Cloudflare (akan membuka browser atau memberikan link otorisasi)
cloudflared tunnel login

# Buat tunnel baru
cloudflared tunnel create lab-tunnel-sre
```
*Catat UUID tunnel dan lokasi file JSON kredensial yang dihasilkan (misal: `/home/user/.cloudflared/<UUID>.json`).*

### Langkah 3: Konfigurasi File Ingress
Pindahkan kredensial ke `/etc/cloudflared/` dan buat file `/etc/cloudflared/config.yml`:

```bash
sudo mkdir -p /etc/cloudflared
sudo cp ~/.cloudflared/<UUID>.json /etc/cloudflared/
```

Buat file `/etc/cloudflared/config.yml`:
```yaml
tunnel: <GANTI_DENGAN_UUID_TUNNEL_ANDA>
credentials-file: /etc/cloudflared/<GANTI_DENGAN_UUID_TUNNEL_ANDA>.json
protocol: quic

ingress:
  - hostname: internal-app.domainanda.com
    service: http://127.0.0.1:8080
  - service: http_status:404
```

### Langkah 4: Rute DNS dan Jalankan Daemon
```bash
# Buat DNS CNAME di edge Cloudflare
cloudflared tunnel route dns lab-tunnel-sre internal-app.domainanda.com

# Pasang service systemd dan jalankan
sudo cloudflared service install
sudo systemctl start cloudflared
sudo systemctl status cloudflared
```

---

## 3. Konfigurasi Access Policy pada Dashboard Zero Trust

1. Buka **Cloudflare One Dashboard** (`https://one.dash.cloudflare.com/`).
2. Masuk ke menu **Access** -> **Applications** -> Klik **Add an application**.
3. Pilih tipe **Self-hosted**.
4. Isi data aplikasi:
   - Application name: `Internal Dev Portal`
   - Application domain: `internal-app.domainanda.com`
5. Tentukan Access Policy:
   - Rule Action: `Allow`
   - Rule Name: `Engineering Team Only`
   - Include: Selector `Emails` -> Masukkan email Anda.
6. (Opsional) Tambahkan Device Posture Check pada tab **Require**:
   - Memerlukan `WARP` client terpasang.
7. Simpan aplikasi.

---

## 4. Pengujian Akses dan Verifikasi Firewall

1. Buka browser pada mode Incognito, akses `https://internal-app.domainanda.com`.
2. Anda akan otomatis diredireksi ke Cloudflare Access Screen.
3. Masukkan email Anda dan input OTP 6-digit yang dikirimkan.
4. Setelah terverifikasi, halaman aplikasi lokal pada port `8080` Anda akan terbuka secara sempurna.
5. **Verifikasi Keamanan Firewall**:
   - Periksa firewall origin server Anda: Tidak ada port inbound (port 80/443/8080) yang dibuka untuk IP publik.
   - Semua koneksi berjalan aman melalui tunnel terenkripsi keluar (*outbound QUIC*).
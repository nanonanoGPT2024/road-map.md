# Panduan Lab Hands-on: Bab 02 - SSL/TLS, Origin CA, & mTLS Simulator

## Deskripsi Lab
Lab mandiri ini memvalidasi konsep mekanika negosiasi TLS antara **Cloudflare Edge** dan **Origin Infrastructure** secara mendalam tanpa membutuhkan akun Cloudflare aktif. 

Dengan menjalankan script simulasi `mtls_origin_handshake_sim.py`, Anda akan:
1. Membangun infrastruktur Public Key Infrastructure (PKI) privat di memory secara otomatis.
2. Membuktikan secara nyata mengapa mode **Full (Non-Strict)** menimbulkan risiko keamanan kritis *Man-in-the-Middle (MitM)*.
3. Memverifikasi bagaimana **Full (Strict)** memvalidasi rantai sertifikat X.509 dan Subject Alternative Name (SAN).
4. Mengamati proses otentikasi dua arah **mTLS / Authenticated Origin Pulls (AOP)** menolak koneksi tidak sah di layer transport.

---

## Prasyarat Lingkungan
- Sistem Operasi: Linux, macOS, atau WSL2 (Windows Subsystem for Linux).
- Python 3.9 atau lebih baru.
- Library `cryptography`:
  ```bash
  pip install cryptography
  ```

---

## Langkah Menjalankan Hands-on

### 1. Masuk ke Direktori Hands-on
```bash
cd hands-on/m01
```

### 2. Berikan Izin Eksekusi pada Skrip Simulator
```bash
chmod +x mtls_origin_handshake_sim.py
```

### 3. Eksekusi Simulator
```bash
python3 mtls_origin_handshake_sim.py
```

---

## Analisis Hasil Output Laboratorium

Saat skrip dieksekusi, perhatikan 4 skenario pembuktian berikut:

### Skenario 1: Full (Strict) Mode vs Untrusted Rogue Origin
- **Kondisi**: Edge diatur ke mode `STRICT`, origin menggunakan sertifikat yang ditandatangani oleh Rogue CA yang tidak dikenal.
- **Hasil**: Handshake ditolak seketika oleh Edge.
- **Kesimpulan**: Muncul kegagalan verifikasi sertifikat yang merepresentasikan **Cloudflare Error 526: Invalid SSL Certificate**.

### Skenario 2: Full (Non-Strict) Mode vs Untrusted Rogue Origin
- **Kondisi**: Edge diatur ke mode `FULL`, origin menggunakan sertifikat palsu.
- **Hasil**: Kone
# Panduan Hands-On Lab: Protokol Jaringan Terdistribusi & Keandalan (SRE)

Dokumen ini menyediakan panduan praktis untuk menjalankan simulasi protokol keandalan sistem terdistribusi, memverifikasi status socket jaringan di kernel Linux, serta mengamati optimasi latensi menggunakan kombinasi pola Circuit Breaker, Full Jitter Backoff, dan Request Hedging.

---

## 1. Persiapan Lingkungan (Environment Prerequisites)
- Sistem Operasi: Linux (Ubuntu 20.04/22.04 LTS direkomendasikan) atau macOS.
- Python: Versi `3.10` atau lebih baru.
- Network Utilities: `iproute2` (`ss`), `sysctl`, `curl`.

Pastikan Python terpasang:
```bash
python3 --version
```

---

## 2. Struktur File Lab
```
hands-on/m01/
├── README.md                          # Panduan eksekusi
└── circuit_breaker_backoff_sim.py     # Simulator Circuit Breaker, Jitter, & Hedging
```

---

## 3. Langkah Demi Langkah Eksekusi Lab

### Langkah 3.1: Menjalankan Simulator Protokol Keandalan
Jalankan skrip simulator Python untuk mengamati bagaimana Request Hedging dan Circuit Breaker secara langsung mereduksi tail latency ($p99$):

```bash
cd hands-on/m01
python3 circuit_breaker_backoff_sim.py
```

**Ekspektasi Output**:
Skrip akan mencetak perbandingan metrik antara pemanggilan tanpa proteksi (*Baseline*) vs. pemanggilan dengan proteksi *Resilient Pattern*. Anda akan melihat $p99$ terpangkas secara signifikan karena request spekulatif (hedged request) berhasil menyelamatkan request yang terkena latency spike (300-600ms).

---

### Langkah 3.2: Praktik Kernel Tuning TCP di Linux (Opsional / Root Required)
Jika Anda memiliki akses `sudo` pada node Linux atau cloud VM, Anda dapat memeriksa dan mengonfigurasi TCP Congestion Control ke BBR.

1. **Periksa algoritma yang aktif saat ini**:
   ```bash
   sysctl net.ipv4.tcp_congestion_control
   sysctl net.core.default_qdisc
   ```

2. **Periksa modul kernel BBR**:
   ```bash
   lsmod | grep bbr
   # Jika belum termuat:
   sudo modprobe tcp_bbr
   ```

3. **Ubah ke BBR secara temporer**:
   ```bash
   sudo sysctl -w net.core.default_qdisc=fq
   sudo sysctl -w net.ipv4.tcp_congestion_control=bbr
   ```

4. **Verifikasi status koneksi aktif**:
   ```bash
   # Tampilkan detail internal TCP socket termasuk status congestion window (cwnd) dan bbr
   ss -tin '( dport = :https or sport = :https )' | head -n 20
   ```

---

### Langkah 3.3: Mendiagnosis Socket Leaks (`TIME_WAIT` & `CLOSE_WAIT`)
Simulasikan observasi socket state menggunakan command Linux native:

```bash
# Menghitung socket berdasarkan status koneksi
ss -ant | awk '{print $1}' | sort | uniq -c | sort -nr

# Memeriksa batas ephemeral port range
sysctl net.ipv4.ip_local_port_range

# Memeriksa konfigurasi TCP Keepalive saat ini
sysctl net.ipv4.tcp_keepalive_time
sysctl net.ipv4.tcp_keepalive_intvl
sysctl net.ipv4.tcp_keepalive_probes
```

---

## 4. Analisis Hasil Simulasi & Tindak Lanjut

Amati metrik yang keluar dari skrip:
1. **Sukses Rate**: Evaluasi apakah Circuit Breaker mencegah kegagalan kaskade saat downstream melempar exception berulang.
2. **P99 Latency Reduction**: Amati bagaimana porsi request yang masuk kategori `HEDGED_REPLICA` memotong antrean latensi buruk tanpa menunggu timeout penuh selesai.
3. **Analisis Beban Tambahan**: Diskusikan trade-off CPU dan bandwidth tambahan yang dikonsumsi oleh request hedged terhadap reduksi SLA $p99$ yang didapatkan.
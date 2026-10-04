# Panduan Lab Hands-on: Global Traffic Steering & Argo Simulation

## Deskripsi Lab
Lab mandiri ini memvalidasi pemahaman algoritma dan logika operasional dari **Cloudflare Global Load Balancer (GLB)**, **Active Health Monitors**, **Session Affinity**, dan **Argo Smart Routing** melalui simulasi executable mandiri berbasis Python murni (tanpa dependensi eksternal).

---

## Prasyarat Lingkungan
- Komputer / Mesin Linux, macOS, atau Windows Subsystem for Linux (WSL).
- Python 3.9 atau versi yang lebih tinggi (`python3 --version`).

---

## Struktur File Lab
```
hands-on/m01/
├── README.md                    # Dokumen panduan instruksi eksekusi ini
└── global_load_balancer_sim.py  # Script simulasi arsitektur GLB & Argo
```

---

## Skenario yang Diuji dalam Simulasi

1. **Dynamic Latency Steering**:
   Edge Colo di Jakarta (`ID_JKT`) menghitung estimasi Round Trip Time (RTT) ke berbagai pool regional dan memilih pool tercepat secara dinamis (`APAC-Primary-Pool` dengan latency ~10ms via Argo dibanding `US-East-Pool` dengan latency ~147ms).
2. **Session Affinity (Cookie-Based)**:
   Request pertama klien menghasilkan cookie token session (`CFLB`). Request berikutnya yang membawa token tersebut dipastikan mendarat ke origin backend yang identik.
3. **Active Health Monitoring & Threshold Consensus**:
   Simulator mengirim probe HTTP sintetis. Origin ditandai `UNHEALTHY` hanya jika kegagalan terjadi beruntun mencapai ambang batas (`consecutive_fails_threshold = 2`), mencegah insiden akibat *flapping*.
4. **Dynamic Failover**:
   Ketika seluruh origin di kolam utama (APAC) tumbang, traffic dialihkan secara transparan ke pool regional alternatif (`US-East-Pool`).
5. **Disaster Fallback Pool Trigger**:
   Ketika seluruh infrastruktur global utama tumbang, load balancer otomatis mengarahkan koneksi ke Fallback Maintenance Pool statis.

---

## Langkah-Langkah Eksekusi

### 1. Masuk ke Direktori Lab
```bash
cd hands-on/m01
```

### 2. Berikan Izin Eksekusi pada Skrip
```bash
chmod +x global_load_balancer_sim.py
```

### 3. Jalankan Simulator
```bash
python3 global_load_balancer_sim.py
```

---

## Eksperimen Mandiri (Code Challenge)

Buka file `global_load_balancer_sim.py` dan lakukan modifikasi berikut untuk memperdalam pemahaman:

1. **Ubah Kebijakan Steering ke Geo-Steering**:
   Ganti parameter inisialisasi simulator:
   ```python
   glb = CloudflareGLBSimulator(steering_policy="geo")
   glb.map_geo_country("ID", ["pool_apac", "pool_us"])
   ```
   Amati perbedaan rute sebelum dan sesudah modifikasi.

2. **Uji Efek Penonaktifan Argo Smart Routing**:
   Ubah flag `self.argo_enabled = False` di dalam konstruktor. Jalankan kembali script dan amati kenaikan RTT latency dari setiap skenario.

3. **Simulasikan Origin Drain Mode**:
   Ubah status origin tertentu menjadi `origin.drain_mode = True`. Buktikan bahwa klien yang telah memegang cookie session lama masih dapat mengakses origin tersebut, sedangkan klien baru dialihkan ke origin pendampingnya.
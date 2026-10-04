# Panduan Hands-On Lab: Telemetri, Metric Math, dan FinOps Guardrails

Panduan praktikum mandiri ini dirancang untuk mendemonstrasikan implementasi nyata konsep observabilitas tingkat lanjut (High-Resolution Metrics, Injeksi Anomali, dan Metric Math) serta implementasi guardrail infrastruktur dan estimasi biaya terotomatisasi (*FinOps Shift-Left*).

---

## 1. Persiapan Lingkungan (Prerequisites)

Pastikan workstation Anda telah terpasang:
1. **Python v3.9+** dan package manager `pip`.
2. **AWS CLI v2** terkonfigurasi dengan kredensial aktif (`aws sts get-caller-identity`).
3. **Terraform v1.5+**.
4. **Infracost CLI** (opsional untuk modul FinOps Shift-Left). Pasang via:
   ```bash
   brew install infracost # macOS
   # atau
   curl -fsSL https://raw.githubusercontent.com/infracost/infracost/master/scripts/install.sh | sh
   ```

---

## 2. Struktur Direktori Hands-On

```
hands-on/m01/
├── README.md
├── cloudwatch_metric_anomaly_sim.py
└── terraform/
    └── main.tf
```

---

## 3. Langkah Demi Langkah Hands-On

### Langkah 1: Persiapan Virtual Environment Python
Buka terminal dan navigasikan ke direktori hands-on:
```bash
cd hands-on/m01
python3 -m venv venv
source venv/bin/activate
pip install boto3
```

### Langkah 2: Eksekusi Simulasi Pengiriman Metrik & Injeksi Anomali
Jalankan skrip simulator untuk mempublikasikan metrik sintetik dengan resolusi tinggi (High-Resolution Metric 1 detik) ke CloudWatch. Skrip ini secara otomatis menyuntikkan lonjakan kegagalan HTTP 5XX pada 40%-60% linimasa simulasi:
```bash
python3 cloudwatch_metric_anomaly_sim.py --duration 5 --namespace "Enterprise/FinTechPlatform" --region "ap-southeast-1"
```

Output terminal akan mencetak pergerakan request, anomali yang disuntikkan, dan langsung mengevaluasi formula **Metric Math** `(m2 / m1) * 100` untuk membuktikan kalkulasi persentase error secara real-time.

### Langkah 3: Verifikasi via CloudWatch Console
1. Buka **AWS Management Console** -> **CloudWatch** -> **All Metrics**.
2. Pilih namespace kustom `Enterprise/FinTechPlatform`.
3. Klik dimensi `ServiceName, Environment`.
4. Centang metrik `RequestCount` dan `HTTPCode_Target_5XX_Count`.
5. Buka tab **Graphed metrics**, tambahkan **Math expression** -> **Start with empty expression**, lalu masukkan:
   ```
   (m2 / m1) * 100
   ```
6. Amati bagaimana grafik secara akurat menunjukkan lonjakan persentase kegagalan (SLO breach) di atas ambang 5%.

---

## 4. Hands-on FinOps: Shift-Left Cost Analysis Menggunakan
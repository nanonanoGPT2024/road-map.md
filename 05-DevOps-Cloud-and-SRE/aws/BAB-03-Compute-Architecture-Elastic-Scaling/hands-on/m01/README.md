# Panduan Hands-On Lab: Compute Architecture & Elastic Scaling

## Deskripsi Laboratorium
Hands-on lab ini memandu Anda dalam merancang, men-deploy, dan memverifikasi arsitektur komputasi elastis berstandar enterprise:
1. Menyiapkan **Launch Template** berbasis silikon **AWS Graviton (ARM64)** dengan enkripsi EBS GP3 dan pembatasan **IMDSv2**.
2. Mengonfigurasi **Auto Scaling Group (ASG)** dengan kebijakan alokasi **Mixed Instances** (`price-capacity-optimized`) yang memadukan On-Demand dan Spot Instances.
3. Menguji eksekusi simulasi script **ASG Lifecycle Hook & Spot Interruption Handler** untuk menjamin *zero-downtime draining*.

---

## Prasyarat Lingkungan
- Akun AWS aktif dengan hak akses administratif IAM untuk EC2, Auto Scaling, dan SSM.
- AWS CLI v2 terkonfigurasi pada mesin lokal Anda (`aws configure`).
- Terraform CLI (v1.5.0+) terinstall.
- Python 3.9+ terinstall.

---

## Langkah 1: Pengujian Lokal Skrip Draining Lifecycle

Sebelum men-deploy ke cloud, uji coba alur simulasi penanganan sinyal *graceful connection draining* menggunakan skrip simulasi Python.

1. Buka terminal dan arahkan ke direktori hands-on:
   ```bash
   cd hands-on/m01/
   ```

2. Jalankan skrip `asg_lifecycle_simulation.py`:
   ```bash
   python3 asg_lifecycle_simulation.py
   ```

3. **Verifikasi Output**:
   Perhatikan log yang dihasilkan:
   - Skrip mendeteksi lingkungan mock lokal.
   - Melakukan heartbeat monitoring antrean tugas.
   - Menangkap trigger shutdown.
   - Menjalankan tahapan `DRAINING: Menyelesaikan active in-flight request(s)`.
   - Mengirimkan sinyal mock `CompleteLifecycleAction` dengan status `CONTINUE`.

4. **Uji Penghentian via Sinyal POSIX (SIGTERM)**:
   Jalankan script di background, kemudian kirim sinyal `kill -15`:
   ```bash
   python3 asg_lifecycle_simulation.py &
   PID=$!
   sleep 4
   kill -15 $PID
   wait $PID
   ```
   *Amati bahwa skrip tidak mati seketika, melainkan menyelesaikan drain task terlebih dahulu.*

---

## Langkah 2: Deploy Infrastruktur dengan Terraform

Gunakan kode Terraform dari Modul 01 (Seksi 10) untuk men-deploy armada komputasi nyata:

1. Buat file `main.tf` di direktori kerja Anda dan tempelkan blok kode HCL dari **Seksi 10: Practical Example** pada modul pembelajaran.
2. Inisialisasi Terraform:
   ```bash
   terraform init
   ```
3. Lakukan validasi sintaks:
   ```bash
   terraform validate
   ```
4. Terapkan konfigurasi ke AWS:
   ```bash
   terraform apply -auto-approve
   ```

---

## Langkah 3: Verifikasi Arsitektur Silikon & Hardening IMDSv2

Setelah instans berhasil diluncurkan oleh ASG:

1. Ambil daftar instance ID yang berjalan di ASG:
   ```bash
   INSTANCE_ID=$(aws autoscaling describe-auto-scaling-instances \
     --query "AutoScalingInstances[0].InstanceId" \
     --output text)
   echo "Target Instance ID: ${INSTANCE_ID}"
   ```

2. Akses instans melalui **AWS Systems Manager Session Manager** (tanpa SSH, tanpa public IP):
   ```bash
   aws ssm start-session --target $INSTANCE_ID
   ```

3. Di dalam shell Session Manager, verifikasi mikroarsitektur prosesor **Graviton ARM**:
   ```bash
   uname -m
   # Output wajib: aarch64

   lscpu
   # Periksa Model Name: Neoverse-V1 / Neoverse-N1 (Graviton)
   ```

4. Verifikasi bahwa **IMDSv1 telah diblokir** dan **IMDSv2 dipaksakan**:
   ```bash
   # Uji IMDSv1 (Harus menghasilkan HTTP 401 Unauthorized)
   curl -s -i "http://169.254.169.254/latest/meta-data/"
   
   # Uji IMDSv2 (Harus berhasil dengan token)
   TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60")
   curl -s -H "X-aws-ec2-metadata-token: $TOKEN" "http://169.254.169.254/latest/meta-data/instance-id"
   ```

5. Keluar dari sesi SSM:
   ```bash
   exit
   ```

---

## Langkah 4: Uji Coba ASG Terminating Lifecycle Hook

Uji apakah ASG menunggu proses draining sebelum mematikan instans fisik:

1. Hentikan salah satu instans secara sengaja untuk memicu Lifecycle Hook:
   ```bash
   aws autoscaling terminate-instance-in-auto-scaling-group \
     --instance-id $INSTANCE_ID \
     --no-should-decrement-desired-capacity
   ```

2. Periksa status transisi instans pada ASG:
   ```bash
   aws autoscaling describe-auto-scaling-instances \
     --instance-ids $INSTANCE_ID \
     --query "AutoScalingInstances[0].LifecycleState"
   ```
   *Status akan tertahan pada `Terminating:Wait` selama durasi timeout hook (300 detik), memberi waktu daemon untuk menguras koneksi.*

3. Kirimkan sinyal *complete action* secara manual jika aplikasi telah selesai:
   ```bash
   aws autoscaling complete-lifecycle-action \
     --lifecycle-hook-name graceful-shutdown-hook \
     --auto-scaling-group-name $(aws autoscaling describe-auto-scaling-instances --instance-ids $INSTANCE_ID --query "AutoScalingInstances[0].AutoScalingGroupName" --output text) \
     --instance-id $INSTANCE_ID \
     --lifecycle-action-result CONTINUE
   ```

4. Periksa kembali status instans; instans akan segera berpindah ke status `Terminated`.

---

## Langkah 5: Pembersihan Sumber Daya (Teardown)

Selalu bersihkan infrastruktur cloud setelah pengujian selesai untuk mencegah akumulasi biaya:

```bash
terraform destroy -auto-approve
```
Pastikan seluruh instans EC2 dan Auto Scaling Groups telah terhapus seutuhnya.
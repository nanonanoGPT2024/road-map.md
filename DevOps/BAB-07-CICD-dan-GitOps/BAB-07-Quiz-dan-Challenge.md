# BAB 07 — Quiz, Challenge, & Knowledge Check: CI/CD & GitOps

## A. Quiz Evaluasi Pemahaman

### Bagian 1: Soal Tingkat Dasar (Basic)
1. Apa perbedaan mendasar antara Continuous Integration (CI), Continuous Delivery (CD), dan Continuous Deployment?
2. Mengapa push-based CI/CD (di mana GitHub Actions runner memegang file kubeconfig) dianggap memiliki attack surface keamanan yang lebih tinggi dibandingkan pull-based GitOps?
3. Dalam GitHub Actions, apa perbedaan antara `action`, `step`, `job`, dan `workflow`?
4. Apa fungsi atribut `prune: true` dalam spesifikasi Application ArgoCD?
5. Mengapa caching layer (misal Docker layer caching atau npm cache) sangat krusial dalam pipeline CI/CD?

### Bagian 2: Soal Tingkat Menengah (Intermediate)
6. Jelaskan bagaimana mekanisme auto-healing ArgoCD bekerja ketika seorang insinyur secara manual melakukan perintah `kubectl scale deployment web --replicas=10` di cluster produksi.
7. Mengapa menyimpan password database plain text di repositori Git manifest Kubernetes dilarang keras, dan instrumen apa yang digunakan di ekosistem GitOps untuk mengatasinya?
8. Bagaimana strategi **Canary Deployment** meminimalkan blast radius risiko kegagalan rilis dibanding metode rolling update tradisional Kubernetes?
9. Apa fungsi file lock (`package-lock.json`, `poetry.lock`, `go.sum`) dalam pipeline CI, dan apa risikonya jika pipeline menggunakan `npm install` alih-alih `npm ci`?
10. Bagaimana cara kerja webhook dari GitHub ke ArgoCD untuk mempercepat rekonsiliasi state tanpa harus menunggu interval polling default (3 menit)?

### Bagian 3: Pertanyaan Skenario Nyata (Scenario-Based)
11. **Skenario 1**: Sebuah tim e-commerce merilis versi baru layanan Checkout menggunakan Argo Rollouts. Pada tahap traffic 20%, metrik Prometheus menunjukkan lonjakan HTTP 500 error dari 0.01% menjadi 4.5%. Jelaskan secara teknis rantai peristiwa yang terjadi pada controller Argo Rollouts, Ingress/Service Mesh, dan pods aplikasi!
12. **Skenario 2**: Pipeline CI GitHub Actions Anda tiba-tiba melambat drastis dari 3 menit menjadi 25 menit setelah tim menambahkan 5 microservices baru ke monorepo. Jelaskan rencana diagnostik dan 4 teknik optimasi konkret untuk mengembalikan durasi pipeline ke bawah 4 menit!
13. **Skenario 3**: Sebuah commit berbahaya diselundupkan ke branch `main` repositori manifest GitOps yang mengubah image database menjadi image penambang kripto. Jika Anda adalah DevSecOps Architect, pertahanan berlapis (*defense-in-depth*) apa yang harus diterapkan sebelum manifest tersebut dapat di-deploy oleh ArgoCD?

---

## B. Practical Chapter Challenge: Production-Grade CI/CD & GitOps Pipeline

### Deskripsi Skenario
Anda diminta merancang arsitektur pipeline otomatisasi pengiriman software untuk platform perbankan digital.

### Persyaratan Implementasi:
1. **GitHub Actions Workflow (`.github/workflows/ci.yml`)**:
   - Menjalankan Linting, Unit Testing dengan Code Coverage threshold minimal 80%.
   - Menjalankan Trivy container vulnerability scanner (blokir build jika ada CVE level `CRITICAL`).
   - Build multi-platform Docker container image dan sign dengan Cosign.
   - Mengupdate tag image di repositori konfigurasi GitOps secara terprogram (bot commit).
2. **ArgoCD Declarative Application (`application.yaml`)**:
   - Konfigurasikan aplikasi yang memonitor repo k8s-manifests dengan kebijakan `automated` sync, `selfHeal: true`, dan `prune: true`.
3. **Argo Rollout Canary Definition (`rollout.yaml`)**:
   - Definisikan strategi canary dengan 4 tahapan: 10% (pause 5m), 25% (pause 5m), 50% (pause 10m), 100%.
   - Pasang `AnalysisTemplate` yang mengukur `success-rate` HTTP traffic minimal 99.5%.

---

## C. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Siklus penuh CI/CD: Trigger -> Lint -> Test -> Security Scan -> Build -> Artifact Registry -> Deploy -> Verify.
- [ ] Arsitektur internal ArgoCD: Application Controller, Repo Server, API Server.
- [ ] Perbedaan esensial Pull-based vs Push-based deployment topology.
- [ ] Strategi deployment: Recreate, RollingUpdate, Blue/Green, Canary Rollout.

### Saya Tidak Perlu Menghafal:
- [ ] Seluruh sintaks ekspresi if/context GitHub Actions (cukup baca dokumentasi `actions/checkout`, `actions/cache`).
- [ ] Seluruh field CRD Argo Rollouts secara detail di luar spec `canary` dan `analysis`.

### Saya Harus Bisa Melakukan:
- [ ] Membuat file `.github/workflows/` dengan matrix build dan caching yang optimal.
- [ ] Menulis manifest deklaratif ArgoCD Application dan menguji rekonsiliasi drift.
- [ ] Mengonfigurasi automated rollback berbasis metrik kegagalan di Kubernetes.

```text
Checklist Kesiapan BAB 07:
[ ] Memahami konsep CI/CD dan filosofi GitOps
[ ] Menjalankan hands-on pipeline simulator m01
[ ] Menjalankan hands-on ArgoCD reconciler & canary simulator m02
[ ] Mampu menjawab seluruh pertanyaan Quiz dan Skenario
```

# BAB 08: CI/CD/CT Automation for Machine Learning
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis dan Mengimplementasikan Arsitektur MLOps Level 2 (Google Maturity Model)**: Mengintegrasikan otomatisasi penuh pada siklus Continuous Integration (CI), Continuous Delivery (CD), dan Continuous Training (CT).
2. **Membangun Pipeline Continuous Training (CT) Event-Driven**: Mengorkestrasi pipeline retraining otomatis berbasis trigger (drift metrik, ketersediaan data baru, performa degradasi) menggunakan Argo Workflows atau Kubeflow Pipelines.
3. **Mengembangkan Automated Quality & Safety Gates**: Mengimplementasikan pengujian deterministik dan non-deterministik mencakup *data validation*, *model bias/fairness check*, *adversarial robustness*, dan *latency SLA benchmarking*.
4. **Menerapkan Strategi Deployment Progresif (Canary & Shadow/Dark Traffic)**: Mengonfigurasi Service Mesh (Istio) dan KServe/Seldon Core untuk evaluasi model baru di lingkungan produksi tanpa risiko regresi bisnis.
5. **Mendesain Mekanisme Automated Rollback & Self-Healing**: Mengonfigurasi observabilitas metrik produksi secara real-time yang memicu rollback otomatis via GitOps (ArgoCD) jika terjadi pelanggaran threshold statistik atau SLA inferensi.

---

### 2. Prerequisite
Peserta wajib memiliki pemahaman mendalam dan pengalaman praktis pada:
- **MLOps Fundamental**: Pelacakan eksperimen (*experiment tracking*), Model Registry (MLflow), dan Feature Store (Feast).
- **Containerization & Orchestration**: Docker multi-stage builds, Kubernetes (Deployments, Services, CRDs, Horizontal Pod Autoscaler).
- **Infrastructure as Code & GitOps**: Konsep GitOps dasar, ArgoCD, dan declarative manifest (Kustomize/Helm).
- **Statistika Inferensial & Monitoring**: Kolmogorov-Smirnov Test, Population Stability Index (PSI), Jensen-Shannon Divergence untuk deteksi data dan concept drift.
- **Bahasa Pemrograman**: Python 3.10+ tingkat lanjut (Object-Oriented Programming, AsyncIO, Typing) dan Bash scripting.

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi CI/CD konvensional pada rekayasa perangkat lunak hanya berfokus pada dua artefak: **Kode** dan **Konfigurasi**. Pada Machine Learning Engineering, terdapat artefak ketiga yang dinamis: **Data**. Perubahan performa sistem di produksi sering kali bukan disebabkan oleh *bug* pada kode, melainkan degradasi distribusi data (*data drift*) atau pergeseran hubungan antara fitur dan target (*concept drift*).

Oleh karena itu, arsitektur produksi membutuhkan tiga pilar otomasi:

```
+-------------------------------------------------------------------------+
|                              MLOps Level 2                              |
+-------------------+--------------------+--------------------------------+
| Continuous        | Continuous         | Continuous                     |
| Integration (CI)  | Delivery (CD)      | Training (CT)                  |
+-------------------+--------------------+--------------------------------+
| - Linting & Type  | - GitOps Manifest  | - Drift-triggered execution    |
| - Unit Testing    | - Progressive Roll | - Automated Data Validation    |
| - Pipeline Test   | - Canary / Shadow  | - Distributed Training Run     |
| - Container Build | - Auto-Rollback    | - Model Evaluation vs Baseline |
+-------------------+--------------------+--------------------------------+
```

#### Komponen Internal Arsitektur Produksi

```
[Production Traffic] ---> [Istio Ingress Gateway]
                                |
             +------------------+------------------+
             | (90% Traffic)                       | (10% Canary / Shadow)
             v                                     v
     [Model Service v1]                   [Model Service v2]
             |                                     |
             +------------------+------------------+
                                |
                                v
                     [Kafka / Event Stream]
                                |
          +---------------------+---------------------+
          |                                           |
          v                                           v
[Prometheus / Evidently Service]             [Object Storage / Lake]
 (Metrik: P99, Drift PSI > 0.25)                      |
          |                                           |
          v (Alert / Webhook)                         v
[Argo Events / EventSource] -------------> [Argo Workflows: CT Pipeline]
                                                      |
                                                      v
                                            [MLflow Model Registry]
                                                      |
                                            (PR to Git Repository)
                                                      |
                                                      v
                                             [ArgoCD Sync to K8s]
```

1. **Trigger Layer (Argo Events & Prometheus Alertmanager)**: 
   - Memonitor event berbasis metrik (misal: metrik PSI > 0.25 selama 3 jam, atau F1-score harian turun di bawah 0.85) atau event berbasis data (partisi data baru di S3/GCS).
   - Mengirim payload JSON ke *EventBus* untuk memicu eksekusi *Workflow*.
2. **Orchestration Layer (Kubeflow Pipelines / Argo Workflows)**:
   - Menjalankan Directed Acyclic Graph (DAG) di dalam isolated Kubernetes pods.
   - Mengambil data tervalidasi dari Feature Store, mengeksekusi *distributed hyperparameter tuning*, dan melakukan *cross-validation*.
3. **Automated Quality Gate (Candidate vs. Champion Evaluation)**:
   - Model baru (*Candidate*) tidak diizinkan masuk ke *Model Registry* berstatus `Staging` kecuali lolos evaluasi ketat:
     - **Performance Gate**: $\text{Metric}_{\text{Candidate}} > \text{Metric}_{\text{Champion}} + \epsilon$.
     - **Robustness Gate**: Evaluasi performa pada *edge-cases* dan *data perturbation test*.
     - **Latency Gate**: P99 inferensi $\le X \text{ ms}$ pada batch payload tertentu.
4. **GitOps CD Layer (ArgoCD & KServe)**:
   - Model yang lolos uji dipromosikan ke Model Registry. Sebuah bot otomatis membuat *Pull Request* ke repositori konfigurasi GitOps untuk memperbarui digest image model dan URI artefak.
   - ArgoCD mendeteksi perubahan state pada Git, menerapkan manifest ke cluster, dan menginstruksikan KServe untuk melakukan *Canary Deployment* bertahap (10% -> 50% -> 100%).

---

### 4. Why & What

| Dimensi | Software Engineering Tradisional (CI/CD) | Machine Learning Engineering (CI/CD/CT) |
| :--- | :--- | :--- |
| **Pemicu Iterasi** | Perubahan kode sumber (*code commit* / *tag*). | Perubahan kode, perubahan skema/distribusi data, atau degradasi performa model di produksi. |
| **Artefak Output** | Biner, library, atau image kontainer statis. | Pipeline kode, metadata pelatihan, bobot model (*model weights*), dan metrik evaluasi. |
| **Validasi / Pengujian** | Unit test, integration test, load test deterministik. | Unit/Integration test + Data schema validation + Statistical model performance checks + Bias/Fairness audit. |
| **Downtime & Degradasi** | Umumnya disebabkan oleh *unhandled exception*, *memory leak*, atau kegagalan infrastruktur (*hard failure*). | Sering kali terjadi *silent failure*: API berstatus HTTP 200 OK dengan latensi rendah, namun prediksi yang dihasilkan salah akibat *concept drift*. |
| **Siklus Hidup** | Bangun sekali, jalankan di mana saja (*build once, deploy anywhere*). | Memerlukan *Continuous Training* secara konstan karena masa pakai (*half-life*) model dibatasi oleh perubahan dinamika dunia nyata. |

---

### 5. How (Workflow Detail)

Alur kerja end-to-end produksi beroperasi melalui fase-fase berikut:

1. **Fase Development & CI (Code Level)**:
   - Developer melakukan *push* kode training pipeline atau model architecture ke repositori Git.
   - **CI Pipeline Engine** (GitHub Actions / GitLab CI) mengeksekusi:
     - Pemeriksaan statis: `ruff`, `flake8`, `mypy`.
     - Pengujian unit: `pytest` untuk modular data transform logic.
     - Integration test: Pipeline dijalankan pada *dummy dataset* mini (100 baris) untuk memastikan tidak terjadi runtime crash (*smoke test*).
     - Jika lolos, container image untuk pipeline diekspor ke Container Registry (misal: ECR/GCR).

2. **Fase Continuous Training (CT Engine)**:
   - Terpicu secara terjadwal (CRON) atau event-driven (drift alert).
   - Pod orchestrator menarik data mentah dari Feature Store / Data Lake.
   - **Data Validation Step**: Menjalankan *Great Expectations* untuk memverifikasi rentang nilai, kelengkapan (*null-rate*), dan tipe data.
   - **Training Step**: Melatih model pada kluster GPU/CPU terdistribusi.
   - **Evaluation Step**: Menguji model terhadap test set *hold-out* dan *adversarial dataset*.
   - **Gate Check**: Script evaluasi membandingkan model baru dengan *production champion*. Jika skor model baru melampaui baseline, artefak di-push ke Model Registry dan ditandai sebagai `Candidate`.

3. **Fase Continuous Delivery (CD via GitOps)**:
   - CI/CD worker memperbarui tag rilis model pada repositori GitOps (menyimpan konfigurasi declarative Kubernetes).
   - ArgoCD mendeteksi Git drift dan menerapkan manifes KServe/Istio ke cluster Kubernetes.
   - **Progressive Canary**:
     - 10% trafik diarahkan ke model kandidat.
     - Prometheus mengumpulkan metrik error rate (5xx), latensi P95/P99, serta metrik bisnis real-time.
     - Jika metrik stabil selama interval observasi (misal: 30 menit), trafik dinaikkan secara bertahap: 25% -> 50% -> 100%.
   - **Auto-Rollback Trigger**:
     - Jika Prometheus mendeteksi kenaikan error rate (> 1%) atau degradasi metrik model, ArgoCD/KServe secara instan membalikkan rute trafik 100% kembali ke model *champion* sebelumnya.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Pabrik Pemurnian Air Otomatis
Bayangkan software konvensional sebagai pabrik pembotolan: pipa dan mesin dipasang sekali; selama mesin tidak rusak secara mekanis, botol akan terisi air dengan benar. 

Machine Learning seperti membangun pabrik pemurnian air di dekat sungai yang dinamis. Kualitas air sungai (data) berubah-ubah saat musim hujan atau limbah masuk (*data drift*). 
- **CI** adalah pengujian integritas mekanik mesin penyaring air.
- **CT** adalah sistem sensor kimia yang mendeteksi perubahan komposisi air sungai dan secara otomatis mengubah racikan filter/dosis klorin agar air keluaran tetap steril.
- **CD** adalah katup pembagi yang mengalirkan 5% air hasil racikan filter baru ke laboratorium penguji (*canary*) sebelum dialirkan ke seluruh instalasi pipa air minum kota.

#### Diagram ASCII Alur Kerja Eksekusi CI/CD/CT

```
+-----------------------------------------------------------------------------------+
|                        1. CONTINUOUS INTEGRATION (CI)                             |
|  [Dev Commit] ---> [Lint/Test] ---> [Build Image] ---> [Push Image to Registry]   |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                        2. CONTINUOUS TRAINING (CT)                                |
|  [Trigger: Drift/Cron]                                                            |
|         |                                                                         |
|         v                                                                         |
|  [Data Validation] ---> [Distributed Train] ---> [Model Evaluation vs Champion]   |
|                                                              |                    |
|                                                  (Pass Safety Gate?)              |
|                                                  /                \               |
|                                            [YES]                   [NO]           |
|                                              |                       |            |
|                                              v                       v            |
|                                    [Register Model]           [Halt Pipeline]     |
|                                    [Auto PR to GitOps]        [Send Slack Alert]  |
+----------------------------------------------+------------------------------------+
                                               |
                                               v
+-----------------------------------------------------------------------------------+
|                        3. CONTINUOUS DELIVERY (CD)                                |
|  [ArgoCD Sync] ---> Deploy Canary Pods (KServe)                                   |
|                             |                                                     |
|                             v                                                     |
|                [Traffic Split: 90/10]                                             |
|                             |                                                     |
|                   (Check Production SLA)                                          |
|                   /                    \                                          |
|            [Unhealthy]               [Healthy]                                    |
|                 |                        |                                        |
|                 v                        v                                        |
|      [Instant Rollback 100%]     [Promote to 100%]                                |
+-----------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Practical Example 1: GitHub Actions CI Pipeline dengan Model Gate Logic (`.github/workflows/ci.yml`)

Pipeline ini memvalidasi kode, menjalankan pengujian unit, melatih model benchmark cepat, dan memvalidasi apakah model memenuhi ambang batas minimum sebelum build container diperbolehkan.

```yaml
name: Model-Engine-CI

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]

jobs:
  code-quality-and-unit-tests:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.10"
          cache: "pip"

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install ruff pytest great_expectations scikit-learn joblib

      - name: Lint and Static Code Analysis
        run: |
          ruff check .
          ruff format --check .

      - name: Run Unit Tests
        run: |
          pytest tests/unit/ -v --junitxml=reports/junit-unit.xml

  model-validation-gate:
    needs: code-quality-and-unit-tests
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.10"
          cache: "pip"

      - name: Install Dependencies
        run: |
          pip install -r requirements.txt

      - name: Execute Smoke-Train & Quality Assertion Gate
        run: |
          python scripts/ci_evaluate_gate.py \
            --test-data-path tests/fixtures/golden_testset.csv \
            --min-f1-threshold 0.82 \
            --max-p99-latency-ms 20.0
```

#### B. Practical Example 2: Skrip Model Quality & Safety Evaluation Gate (`scripts/ci_evaluate_gate.py`)

Skrip ini dieksekusi di dalam CI untuk mencegah model yang mengalami regresi akurasi atau pelanggaran latensi lolos ke proses CD.

```python
#!/usr/bin/env python3
import argparse
import sys
import time
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score
from joblib import load

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automated ML CI Gate Evaluation.")
    parser.add_argument("--test-data-path", type=str, required=True, help="Path ke golden validation dataset")
    parser.add_argument("--min-f1-threshold", type=float, default=0.80, help="Skor F1 minimal")
    parser.add_argument("--max-p99-latency-ms", type=float, default=25.0, help="Batas maksimum latensi P99 dalam milidetik")
    return parser.parse_args()

def evaluate_safety_and_performance(data_path: str, min_f1: float, max_latency_ms: float) -> None:
    print(f"[*] Memulai verifikasi model gate menggunakan data: {data_path}")
    
    # 1. Load Artefak Model dan Data
    try:
        model = load("artifacts/model.joblib")
        df = pd.read_csv(data_path)
    except FileNotFoundError as err:
        print(f"[!] Critical Error: Artefak tidak ditemukan - {err}")
        sys.exit(1)
        
    X_test = df.drop(columns=["target"])
    y_test = df["target"]

    # 2. Performance Verification (F1-Score)
    y_pred = model.predict(X_test)
    calculated_f1 = f1_score(y_test, y_pred, average="macro")
    print(f"[*] Evaluasi F1-Score: {calculated_f1:.4f} (Ambang Batas Minimum: {min_f1})")

    if calculated_f1 < min_f1:
        print(f"[FAILED] Model ditolak: F1 {calculated_f1:.4f} di bawah batas {min_f1}")
        sys.exit(1)

    # 3. Latency Verification (Benchmarking P99 single inference)
    latencies = []
    # Warmup
    for _ in range(10):
        _ = model.predict(X_test.iloc[[0]])

    # Benchmark run
    for idx in range(min(500, len(X_test))):
        sample = X_test.iloc[[idx]]
        t0 = time.perf_counter()
        _ = model.predict(sample)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)

    p99_latency = np.percentile(latencies, 99)
    print(f"[*] Evaluasi Latensi P99: {p99_latency:.2f} ms (Batas Maksimum: {max_latency_ms} ms)")

    if p99_latency > max_latency_ms:
        print(f"[FAILED] Model ditolak: Latensi P99 {p99_latency:.2f} ms melebihi batas {max_latency_ms} ms")
        sys.exit(1)

    print("[SUCCESS] Seluruh Quality Gates terpenuhi. Model valid untuk tahap rilis CD.")

if __name__ == "__main__":
    args = parse_args()
    evaluate_safety_and_performance(args.test_data_path, args.min_f1_threshold, args.max_p99_latency_ms)
```

#### C. Practical Example 3: Argo Workflows CT Declarative Manifest (`ct-workflow.yaml`)

Manifest ini mendefinisikan pipeline retraining otomatis end-to-end yang dijalankan di dalam kluster Kubernetes saat terpicu drift event.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: continuous-training-pipeline-
  namespace: mlops-pipelines
spec:
  entrypoint: training-dag
  volumeClaimTemplates:
    - metadata:
        name: workdir
      spec:
        accessModes: [ "ReadWriteOnce" ]
        resources:
          requests:
            storage: 10Gi
  templates:
    - name: training-dag
      dag:
        tasks:
          - name: validate-data
            template: data-validation-step
          - name: train-model
            depends: "validate-data"
            template: model-training-step
          - name: evaluate-and-register
            depends: "train-model"
            template: model-eval-register-step

    - name: data-validation-step
      container:
        image: python:3.10-slim
        command: [sh, -c]
        args: ["pip install great_expectations pandas && python -c 'print(\"Validating current data partition...\")'"]

    - name: model-training-step
      container:
        image: python:3.10-slim
        volumeMounts:
          - name: workdir
            mountPath: /mnt/data
        command: [sh, -c]
        args:
          - |
            pip install scikit-learn joblib pandas numpy
            python -c '
            import joblib
            from sklearn.ensemble import GradientBoostingClassifier
            from sklearn.datasets import make_classification
            
            X, y = make_classification(n_samples=5000, n_features=20, random_state=42)
            clf = GradientBoostingClassifier()
            clf.fit(X, y)
            joblib.dump(clf, "/mnt/data/candidate_model.joblib")
            print("Model berhasil dilatih dan disimpan ke shared workspace.")
            '

    - name: model-eval-register-step
      container:
        image: python:3.10-slim
        volumeMounts:
          - name: workdir
            mountPath: /mnt/data
        command: [sh, -c]
        args:
          - |
            python -c '
            import os
            if os.path.exists("/mnt/data/candidate_model.joblib"):
                print("Evaluasi model sukses: Metrik model baru melampaui Champion. Mendaftarkan ke MLflow Registry.")
            else:
                raise SystemExit("Artefak model tidak ditemukan!")
            '
```

#### D. Practical Example 4: Declarative Canary Deployment via KServe / Istio (`canary-inference.yaml`)

Manifest Kubernetes untuk membagi lalu lintas inferensi antara model *Champion* (v1) dan model *Candidate* (v2).

```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: fraud-detection-service
  namespace: mlops-serving
  annotations:
    serving.kserve.io/enable-prometheus-scraping: "true"
spec:
  predictor:
    canaryTrafficPercent: 10
    model:
      modelFormat:
        name: sklearn
      storageUri: "s3://production-ml-models/fraud/v1/"
      resources:
        limits:
          cpu: "2"
          memory: 4Gi
        requests:
          cpu: "1"
          memory: 2Gi
    canary:
      modelFormat:
        name: sklearn
      storageUri: "s3://production-ml-models/fraud/v2/"
      resources:
        limits:
          cpu: "2"
          memory: 4Gi
        requests:
          cpu: "1"
          memory: 2Gi
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Sebuah platform fintech unicorn memproses rata-rata **45.000 transaksi per detik (RPS)** pada puncak beban. Model *Real-time Fraud Detection* harus memprediksi probabilitas kecurangan dalam batas latensi **SLA P99 < 15 milidetik**.

#### Masalah Produksi
Pola transaksi penipuan berubah secara radikal selama kampanye belanja nasional (misal: 11.11 / 12.12). Model statis mengalami penurunan *Recall* dari **0.91** menjadi **0.67** dalam kurun waktu 4 jam akibat *adversarial concept drift* (para pelaku fraud mengubah metode pencucian uang). Pipeline rilis manual membutuhkan waktu minimal 2 hari untuk retraining dan verifikasi, mengakibatkan kerugian finansial diperkirakan mencapai ratusan ribu dolar per jam.

#### Solusi Arsitektur
Diterapkan arsitektur **Level-2 Automated Closed-Loop MLOps**:
1. **Streaming Drift Monitoring**: Layanan analitik streaming membaca event inferensi dari Apache Kafka. Menggunakan algoritma *Streaming Kolmogorov-Smirnov* dan *Population Stability Index (PSI)*, sistem menghitung drift skor setiap jendela 15 menit.
2. **Dynamic Event-Driven CT Pipeline**:
   - Jika `PSI > 0.2` pada 3 fitur prediktif utama, webhook memicu *Argo Events*.
   - Argo Workflows menjalankan retraining secara terdistribusi pada cluster Kubernetes (menggunakan data 48 jam terakhir dari Snowflake & Feast).
3. **Automated Testing Gates**:
   - Model baru wajib melalui serangkaian uji:
     - Dataset stress-test (100.000 vektor sintetis) dalam waktu kurang dari 3 menit.
     - Bias check terhadap demografi pengguna untuk mencegah false-positive berlebih.
     - Latency benchmark di staging mirror cluster.
4. **GitOps Canary Deployment**:
   - GitOps Controller (ArgoCD) memperbarui `InferenceService` KServe dengan konfigurasi Canary 5%.
   - Prometheus memantau rasio HTTP 5xx dan *Business Fraud False-Positive Rate (FPR)*.
   - Analisis otomatis via script Argo Rollouts Analysis mengevaluasi metrik tiap 10 menit. Jika FPR canary tidak melebihi baseline model v1, rute diperluas bertahap: 5% -> 25% -> 100% dalam waktu total 60 menit.

#### Hasil Terukur
- **Mean Time to Retrain & Deploy (MTTR)** turun dari **48 jam** menjadi **38 menit** tanpa intervensi manual.
- *Recall* fraud detection tetap stabil di kisaran **0.89 - 0.93** selama event kampanye puncak.
- Nol downtime (*zero-downtime deployment*) dengan degradasi latensi P99 terkendali di bawah **12.4 ms**.

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Kerugian / Risiko | Biaya & Kompleksitas | Rekomendasi Penggunaan |
| :--- | :--- | :--- | :--- | :--- |
| **Scheduled Batch Retraining (Cron-based)** | Sangat mudah diimplementasikan; beban komputasi terprediksi dan dapat dijalankan di jam non-sibuk. | Rentan terlambat menangani drift tiba-tiba; pemborosan biaya komputasi jika data belum berubah signifikan. | **Rendah**: Cukup menggunakan CronJob Kubernetes atau Cloud Scheduler. | Masalah bisnis dengan data yang berubah lambat (churn prediksi bulanan, estimasi LTV). |
| **Event-Driven Retraining (Drift-triggered)** | Sangat responsif terhadap perubahan perilaku pasar; efisien secara siklus hidup model. | Rentan memicu retraining beruntun (*flapping*) jika threshold drift terlalu sensitif; debugging pipeline lebih kompleks. | **Tinggi**: Membutuhkan monitoring drift streaming dan event-broker infrastruktur yang persisten. | FinTech fraud, dynamic pricing, recommendation click-through-rate (CTR). |
| **Shadow / Dark Traffic Deployment** | Keamanan maksimal: trafik nyata diduplikasi ke model baru tanpa memengaruhi respon pengguna akhir sama sekali. | Menggandakan konsumsi resource komputasi inferensi (2x CPU/GPU); tidak bisa mengukur metrik aksi bisnis (hanya metrik teknis). | **Sedang ke Tinggi**: Beban biaya komputasi meningkat drastis selama periode pengujian. | Model berisiko tinggi di mana kegagalan prediksi berakibat fatal pada kepatuhan regulasi atau finansial. |
| **Canary Deployment** | Menguji performa teknis sekaligus dampak bisnis riil pada persentase user kecil; efisien dalam konsumsi resource. | Sebagian kecil user (misal 5%) terpapar langsung pada potensi prediksi buruk model baru. | **Sedang**: Membutuhkan Service Mesh (Istio/Linkerd) dan traffic router pintar. | Sistem e-commerce, consumer-facing SaaS applications. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Silent Data-Distribution Drift Rollout
- **Kasus**: Pipeline CI/CD berhasil melakukan deploy model baru karena semua *unit test* dan *linting* lolos, tetapi model gagal total di produksi karena urutan kolom fitur pada inference payload berbeda dengan data pelatihan.
- **Root Cause**: Tidak adanya validasi skema data tegas (*contract testing*) antara Feature Store dan payload inferensi.
- **Solusi**: Integrasikan *Pydantic* atau *Pandera* validation gate pada lapisan CI dan pada awal pipeline inferensi.
```python
from pandera import Column, DataFrameSchema, Check

inference_schema = DataFrameSchema({
    "user_age": Column(int, Check.in_range(18, 100)),
    "transaction_amount": Column(float, Check.greater_than_or_equal_to(0.0)),
    "device_risk_score": Column(float, Check.in_range(0.0, 1.0)),
})
# Validasi sebelum masuk prediksi
validated_df = inference_schema.validate(input_df)
```

#### 2. Training-Serving Skew Akibat Leakage Waktu (Time-Travel Leakage)
- **Kasus**: Model retraining baru menunjukkan performa AUC-ROC 0.99 di CT pipeline, tetapi anjlok ke 0.55 sesaat setelah masuk produksi.
- **Root Cause**: Pipeline ekstraksi data untuk CT menggabungkan fitur agregat yang dihitung menggunakan data masa depan (*data leakage*) yang belum tersedia saat inferensi real-time terjadi.
- **Solusi**: Terapkan *Point-in-Time Correctness* menggunakan Feature Store (seperti Feast atau Hopsworks) saat membuat historical training slice.

#### 3. Pod OOMKilled Saat Distributed Evaluation
- **Kasus**: Pod evaluasi model mati tiba-tiba dengan status `ExitCode: 137` (OOMKilled) di tengah eksekusi matrix perbandingan model.
- **Root Cause**: Memuat seluruh dataset evaluasi hold-out ke dalam RAM untuk menghitung ROC curve atau confusion matrix.
- **Solusi**: Gunakan pemrosesan chunking atau library evaluasi out-of-core:
```bash
# Debug pod Kubernetes
kubectl describe pod <evaluation-pod-name> -n mlops-pipelines
# Solusi manifest: Naikkan memory limits dan gunakan chunking
```

#### 4. Flapping Auto-Retraining (Feedback Loop Explosion)
- **Kasus**: Model retraining otomatis berjalan setiap 20 menit terus-menerus tanpa henti.
- **Root Cause**: Ambang batas (threshold) drift diset terlalu rendah atau target label dihitung berdasarkan prediksi model itu sendiri tanpa human-in-the-loop atau ground-truth yang terverifikasi.
- **Solusi**: Tambahkan *cooldown period* (misal: minimal jeda 6 jam antar-retraining) dan terapkan metrik drift berbasis multi-window comparison.

---

### 11. Best Practices (Production Checklist)

#### Pre-commit & CI Checklist
- [ ] Kode terformat dan lolos linter (`ruff check .` dan `black --check .`).
- [ ] Tipe data tervalidasi menggunakan `mypy`.
- [ ] Unit testing mencakup validasi bentuk (*tensor/dataframe shape*), nilai *NaN/null*, dan *extreme out-of-range inputs*.
- [ ] CI pipeline menjalankan evaluasi model berbasis *golden testset* statis dan menegakkan batas minimum metrik performa.
- [ ] Container image dibangun menggunakan teknik *multi-stage build* untuk meminimalkan attack surface dan ukuran image.

#### Continuous Training (CT) Checklist
- [ ] Input data diverifikasi terhadap *data contract schema* sebelum proses training dimulai.
- [ ] Feature store digunakan dengan jaminan *point-in-time correctness*.
- [ ] Seluruh parameter, bobot, lingkungan OS, library dependency, dan dataset checksum dicatat secara persisten ke Model Registry (MLflow/W&B).
- [ ] Model baru wajib mengalahkan performa *Production Champion* minimal sebesar margin signifikansi statistik ($\Delta > \epsilon$).
- [ ] Uji bias dan fairness dijalankan untuk memastikan metrik tidak timpang antar-subkelompok demografis.

#### Continuous Delivery (CD) & Serving Checklist
- [ ] Konfigurasi deployment sepenuhnya deklaratif dan dikelola di bawah kontrol versi Git (prinsip GitOps).
- [ ] Strategi rilis menggunakan mekanisme bertahap (*Canary*) atau *Shadow Deployment*; direct-to-production deployment dilarang keras.
- [ ] Kebijakan rollback otomatis terdefinisi secara jelas berbasis Prometheus Query (latensi, 5xx error rate, drift metric).
- [ ] Model serving pod memiliki konfigurasi *Horizontal Pod Autoscaler* (HPA) yang terkalibrasi dengan metrik latensi atau GPU duty-cycle.
- [ ] Tersedia endpoint `/healthz` (liveness) dan `/readyz` (readiness) yang memverifikasi kesiapan bobot model di memori sebelum pod menerima beban trafik.

---

### 12. Hands-on Practice

Dalam sesi praktikum ini, Anda akan membangun pipeline pengujian model otomatis terisolasi yang berfungsi sebagai gerbang CI/CD, menguji performa, mendeteksi drift, dan menentukan status kelayakan promosi model secara terprogram.

#### Struktur Direktori Proyek
Pastikan direktori lokal Anda tersusun sebagai berikut di `hands-on/m02/`:
```text
hands-on/m02/
├── artifacts/
│   └── (model.joblib akan di-generate di sini)
├── data/
│   ├── baseline_train.csv
│   └── incoming_eval.csv
├── src/
│   ├── __init__.py
│   ├── train.py
│   └── validator.py
├── tests/
│   └── test_model_pipeline.py
└── requirements.txt
```

#### Langkah 1: Persiapan Environment
Buat virtual environment dan install dependencies. Simpan pada `hands-on/m02/requirements.txt`:
```text
scikit-learn==1.3.2
pandas==2.1.4
numpy==1.26.2
scipy==1.11.4
joblib==1.3.2
pytest==7.4.3
```

Jalankan perintah bash:
```bash
cd hands-on/m02/
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
mkdir -p artifacts data src tests
```

#### Langkah 2: Buat Modul Data Sintetis dan Training (`src/train.py`)
Skrip ini menghasilkan dataset baseline dan melatih model regresi logistik dasar.

```python
# hands-on/m02/src/train.py
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from joblib import dump

def generate_and_train():
    np.random.seed(42)
    # 1. Generate Baseline Data
    n_samples = 2000
    x1 = np.random.normal(loc=0.0, scale=1.0, size=n_samples)
    x2 = np.random.normal(loc=5.0, scale=2.0, size=n_samples)
    logits = 1.5 * x1 - 0.8 * x2 + np.random.normal(scale=0.5, size=n_samples)
    y = (logits > 0).astype(int)

    train_df = pd.DataFrame({"feature_1": x1, "feature_2": x2, "target": y})
    train_df.to_csv("data/baseline_train.csv", index=False)

    # 2. Train Model
    model = LogisticRegression()
    model.fit(train_df[["feature_1", "feature_2"]], train_df["target"])
    dump(model, "artifacts/model.joblib")
    print("[*] Model dan baseline data berhasil di-generate.")

    # 3. Generate Incoming Evaluation Data dengan Drift Buatan
    # Fitur 1 mengalami mean shift signifikan
    x1_drift = np.random.normal(loc=1.8, scale=1.2, size=500)
    x2_drift = np.random.normal(loc=5.0, scale=2.0, size=500)
    y_drift = (1.5 * x1_drift - 0.8 * x2_drift + np.random.normal(scale=0.5, size=500) > 0).astype(int)
    
    eval_df = pd.DataFrame({"feature_1": x1_drift, "feature_2": x2_drift, "target": y_drift})
    eval_df.to_csv("data/incoming_eval.csv", index=False)
    print("[*] Data incoming evaluation (dengan drift) berhasil dibuat.")

if __name__ == "__main__":
    generate_and_train()
```

Jalankan skrip generator:
```bash
python src/train.py
```

#### Langkah 3: Implementasi Modul Statistical Drift Detection (`src/validator.py`)
Implementasikan deteksi drift menggunakan Kolmogorov-Smirnov Test untuk fitur numerik kontinu.

```python
# hands-on/m02/src/validator.py
import pandas as pd
from scipy.stats import ks_2samp
from typing import Dict, Tuple

def check_feature_drift(
    baseline_path: str, incoming_path: str, alpha: float = 0.05
) -> Dict[str, Tuple[float, bool]]:
    """
    Melakukan Kolmogorov-Smirnov 2-sample test antara baseline dan incoming dataset.
    True = Terjadi Drift secara statistik signifikan (p-value < alpha).
    """
    df_base = pd.read_csv(baseline_path)
    df_in = pd.read_csv(incoming_path)

    drift_report = {}
    features = [col for col in df_base.columns if col != "target"]

    for col in features:
        stat, p_value = ks_2samp(df_base[col], df_in[col])
        is_drift = p_value < alpha
        drift_report[col] = (float(p_value), is_drift)

    return drift_report

if __name__ == "__main__":
    report = check_feature_drift("data/baseline_train.csv", "data/incoming_eval.csv")
    for feat, (pval, drifted) in report.items():
        print(f"Fitur: {feat:<12} | P-Value: {pval:.6f} | Drift Detected: {drifted}")
```

#### Langkah 4: Buat Automation Test Suite untuk CI Engine (`tests/test_model_pipeline.py`)

Skrip ini akan bertindak sebagai runner validasi di CI runner.

```python
# hands-on/m02/tests/test_model_pipeline.py
import pytest
import pandas as pd
from joblib import load
from sklearn.metrics import accuracy_score
from src.validator import check_feature_drift

@pytest.fixture
def loaded_artifacts():
    model = load("artifacts/model.joblib")
    incoming_df = pd.read_csv("data/incoming_eval.csv")
    return model, incoming_df

def test_model_accuracy_gate(loaded_artifacts):
    model, df = loaded_artifacts
    X = df[["feature_1", "feature_2"]]
    y = df["target"]
    
    preds = model.predict(X)
    acc = accuracy_score(y, preds)
    
    print(f"\n[Test Metrik] Akurasi pada data evaluasi baru: {acc:.4f}")
    # Gerbang penolakan: Akurasi minimal 0.70
    assert acc >= 0.70, f"Akurasi model {acc:.4f} di bawah SLA minimum 0.70!"

def test_data_drift_bounds():
    drift_results = check_feature_drift(
        "data/baseline_train.csv", 
        "data/incoming_eval.csv", 
        alpha=0.01
    )
    # Validasi bahwa pipeline mampu mengidentifikasi drift yang disuntikkan pada feature_1
    assert drift_results["feature_1"][1] is True, "Drift pada feature_1 gagal terdeteksi oleh validator!"
```

#### Langkah 5: Eksekusi Test Runner
Jalankan pengujian secara komprehensif:
```bash
pytest -v -s tests/test_model_pipeline.py
```
*Amati hasil test: pytest harus mengonfirmasi bahwa evaluasi model memenuhi batasan minimum akurasi sekaligus menandai adanya drift statistik pada dataset incoming.*

---

### 13. Exercise

#### Level Easy
1. Modifikasi file `src/validator.py` agar mengembalikan rata-rata selisih absolut (*absolute mean difference*) dari tiap fitur selain p-value KS.
2. Tambahkan unit test baru di `tests/test_model_pipeline.py` yang memvalidasi bahwa model tidak menghasilkan prediksi nilai tunggal konstan (misal: semua output bernilai 1 atau semua bernilai 0) pada dataset evaluasi.

#### Level Medium
1. Buat skrip Python `scripts/promote_model.py` yang mensimulasikan pembaruan declarative GitOps. Jika pengujian pytest berhasil 100%, skrip akan membaca template YAML Kubernetes deployment, mengganti nilai tag environment `MODEL_VERSION` dari `v1` menjadi `v2`, lalu menyimpannya ke file baru `k8s/release.yaml`.
2. Tambahkan pemeriksaan latensi inferensi batch ke dalam `tests/test_model_pipeline.py`: pipeline pengujian harus gagal jika pemrosesan 500 baris data inferensi membutuhkan waktu lebih dari 100 milidetik.

#### Level Hard
1. Bangun pipeline validasi shadow traffic simulator:
   - Buat skrip multiproses asynchronous menggunakan `aiohttp` atau `concurrent.futures`.
   - Skrip membaca `data/incoming_eval.csv`, mengirimkan request inferensi secara konkuren ke dua mock server (Model A dan Model B).
   - Skrip membandingkan respons dari kedua model, mencatat persentase diskrepansi prediksi (*prediction discrepancy percentage*), dan secara otomatis memicu sinyal abort jika diskrepansi melebihi 15% pada 1.000 request pertama.

---

### 14. Challenge

#### Skenario Kasus Kompleks: High-Throughput E-Commerce Multi-Armed Bandit Rollout
Perusahaan ritel online global meluncurkan algoritma Contextual Multi-Armed Bandit (MAB) baru untuk personalisasi halaman checkout. Sistem memproses **10.000 RPS**. 

Anda ditugaskan merancang arsitektur automation CI/CD/CT terpadu dengan spesifikasi berikut:
1. **Zero Cold-Start Failure**: Model bandit baru tidak memiliki bobot eksplorasi di awal. Anda harus merancang arsitektur *Warm-up CD* di mana model baru menerima replikasi trafik bayangan (*dark traffic*) selama 2 jam sebelum dialirkan ke trafik nyata.
2. **Dynamic Concept Drift CT Feedback Loop**: Sistem harus mampu menghitung metrik *Click-Through-Rate (CTR)* secara streaming menggunakan windowing 10 menit. Jika moving-average CTR turun lebih dari 10% dibanding model lama:
   - Sistem seketika menghentikan canary deployment secara otomatis tanpa intervensi manusia (*Auto-rollback*).
   - Membuka tiket insiden otomatis di sistem monitoring (Jira/Slack) dengan payload berisi log statistik snapshot drift.
   - Memicu pipeline CT darurat yang mengambil data cold data storage 7 hari ke belakang untuk melatih ulang fallback model berbasis XGBoost deterministik.

**Tugas Anda**: Buat rancangan spesifikasi arsitektur teknis lengkap (dokumen desain teknis), termasuk:
- Arsitektur diagram komponen Kubernetes (KServe, Pod, Service Mesh, Kafka, Prometheus).
- Spesifikasi metrik monitoring dan logika Prometheus Alerting Rule (PromQL).
- Flowchart penanganan kegagalan (*failure recovery flowchart*).
- Manifes declaratif Argo Rollouts AnalysisTemplate untuk automasi gate Canary.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic (5 Soal)
1. Apa perbedaan paling mendasar antara *Artifact* yang dihasilkan oleh CI pada Software Engineering tradisional dibandingkan CI/CD pada Machine Learning?
2. Mengapa pengujian unit (*unit testing*) kode saja tidak cukup untuk menjamin keandalan sistem Machine Learning di lingkungan produksi?
3. Sebutkan dua jenis data drift monitoring test statistik yang umum digunakan pada pipeline CT otomatis!
4. Apa fungsi dari status *readiness probe* pada container inferensi model di Kubernetes?
5. Jelaskan apa yang dimaksud dengan *Shadow Deployment* (*Dark Traffic*) dalam konteks perilisan model!

#### B. Pertanyaan Intermediate (5 Soal)
1. Mengapa penggunaan metrik statistik seperti p-value dari Kolmogorov-Smirnov test terkadang menghasilkan *false alarm* pada dataset berukuran masif ($N > 1.000.000$)? Metrik apa yang lebih tepat digunakan sebagai alternatif?
2. Bagaimana mekanisme GitOps (seperti ArgoCD) mendeteksi dan memperbaiki *out-of-sync condition* pada deployment model di kluster Kubernetes?
3. Apa risiko utama dari mengizinkan pipeline Continuous Training (CT) melakukan otomatisasi deploy 100% langsung ke produksi tanpa melalui Canary Stage?
4. Jelaskan skenario di mana model machine learning lulus semua pengujian akurasi di CI gate, tetapi menyebabkan kegagalan sistematis saat menerima beban trafik produksi nyata!
5. Bagaimana cara kerja konsep *Point-in-Time Correctness* pada Feature Store dalam mencegah bias selama pipeline Continuous Training berlangsung?

#### C. Skenario Kasus Produksi (3 Soal)
1. **Skenario Kasus 1**: Sistem deteksi anomali pada sensor IoT pabrik baru saja diperbarui melalui pipeline CI/CD otomatis. Tepat setelah canary traffic dinaikkan ke 20%, latensi P99 inference server melonjak dari 15ms menjadi 450ms, menyebabkan antrean message di Apache Kafka meluap. Namun, metrik akurasi model v2 di staging sebelumnya sangat memuaskan. Langkah mitigasi arsitektural instan apa yang harus dieksekusi oleh pipeline otomatis, dan apa potensi akar penyebab teknisnya?
2. **Skenario Kasus 2**: Pipeline CT Anda dikonfigurasi untuk retraining otomatis setiap kali terjadi drift pada data transaksi retail. Suatu hari, sistem mengalami fenomena *flapping* di mana model di-retrain dan di-deploy ulang setiap 30 menit sebanyak 12 kali berturut-turut, menyebabkan lonjakan tagihan komputasi cloud GPU yang sangat drastis. Investigasi menunjukkan performa model justru makin memburuk di tiap iterasi. Jelaskan apa yang sedang terjadi pada ekosistem data tersebut dan bagaimana cara menghentikannya secara permanen!
3. **Skenario Kasus 3**: Anda adalah Lead MLOps Engineer di perbankan. Auditor regulasi keuangan mewajibkan sistem agar setiap model yang di-deploy via automated CD dapat direproduksi secara bit-by-bit identik (*deterministic reproducibility*), bahkan jika model tersebut di-retrain 2 tahun setelah rilis pertamanya. Rancang arsitektur metadata dan storage tracking yang harus disertakan dalam artefak GitOps Anda untuk memenuhi kepatuhan regulasi ini!

---

### Kunci Jawaban Quiz

#### Jawaban Basic
1. CI tradisional menghasilkan binary terkompilasi atau container image yang perilakunya sepenuhnya ditentukan oleh kode statis. CI/CD ML menghasilkan kombinasi kode pipeline, metadata pelatihan, bobot model numerik (*weights*), serta dependensi terhadap snapshot data tertentu yang bersifat non-deterministik.
2. Karena unit test hanya memeriksa kebenaran fungsional logika sintaks program (misal: fungsi transformasi tidak crash saat menerima array). Unit test tidak dapat mendeteksi degradasi performa matematis, kebocoran data (*data leakage*), bias populasi, atau regresi akurasi akibat perubahan distribusi data input dunia nyata.
3. Kolmogorov-Smirnov (KS) Test dan Population Stability Index (PSI) (atau Jensen-Shannon Divergence).
4. Readiness probe memastikan bahwa traffic inferensi tidak akan dialirkan ke pod model baru sebelum container selesai memuat seluruh bobot model (*model weights*) yang besar dari disk/storage ke dalam memori RAM/VRAM GPU.
5. Metode deployment di mana trafik nyata dari pengguna diduplikasi (forked) dan dikirim ke model baru secara paralel tanpa mengembalikan hasil prediksi model baru tersebut ke pengguna, bertujuan murni untuk menguji performa teknis dan stabilitas model baru di lingkungan produksi aktual secara aman.

#### Jawaban Intermediate
1. Pada sampel data yang sangat besar ($N > 10^6$), uji KS menjadi sangat sensitif; perbedaan distribusi yang teramat kecil dan tidak memiliki relevansi praktis terhadap performa model akan tetap menghasilkan p-value mendekati 0.0 (*false alarm*). Alternatif yang lebih tepat adalah menggunakan metrik ukuran efek (*effect size*) seperti Population Stability Index (PSI) atau Wasserstein Distance / Earth Mover's Distance.
2. ArgoCD secara berkala membandingkan *Desired State* yang tersimpan di repositori Git (berisi manifes Kubernetes) dengan *Live State* di dalam kluster. Jika terjadi deviasi (misal konfigurasi pod diubah secara manual di cluster, atau ada commit baru pada Git), status menjadi `OutOfSync`. ArgoCD kemudian dapat memicu proses reconcilation otomatis (`Sync`) untuk menimpa live state agar identik dengan manifest di Git.
3. Risiko *Silent Business Failure*. Model baru mungkin tidak memicu error teknis (HTTP 200 OK), tetapi prediksi yang bias atau salah dapat langsung menghancurkan metrik bisnis riil (misal: false-positive fraud melonjak drastis, memblokir puluhan ribu kartu kredit nasabah sah secara serentak).
4. Skenario umum: Model baru mengimpor library komputasi yang tidak teroptimasi untuk arsitektur CPU target, atau model memiliki kompleksitas arsitektur yang menyebabkan *memory consumption* meledak saat menangani ukuran batch inferensi dinamis yang besar, memicu CPU throttling atau OOM (Out Of Memory) di bawah beban konkurensi tinggi.
5. *Point-in-Time Correctness* memastikan bahwa proses join antara entity keys dan fitur historical hanya menggunakan data fitur yang tercatat sebelum *timestamp* peristiwa itu terjadi (observation timestamp), bukan data masa kini, sehingga mengeliminasi *data leakage* (mengintip masa depan) pada tahap feature engineering.

#### Jawaban Kasus Produksi
1. **Mitigasi Instan**: Controller Canary/Service Mesh (Istio/KServe) harus segera memicu automated rollback 100% traffic ke model v1, serta mengirim sinyal throttling ke Kafka consumer group. 
   **Akar Masalah Teknis**: Kemungkinan besar model v2 menggunakan arsitektur atau dependensi yang melakukan operasi blocking I/O pada threadpool inferensi, fitur input mengalami dimensionalitas meledak (misal: *high-cardinality one-hot encoding* yang tidak terduga pada traffic riil), atau pod canary kekurangan alokasi resource vCPU/RAM sehingga runtime engine (misal: ONNX Runtime / Triton) mengalami thread starvation.
2. **Diagnosa Masalah**: Terjadi *Feedback Loop Contamination* (atau *Model Autophagy*). Prediksi model yang bias di produksi secara tidak sengaja masuk kembali ke dalam training data lake sebagai data training baru tanpa adanya label verifikasi independen (ground-truth). Model melatih dirinya sendiri dari output prediksinya yang rusak. 
   **Solusi Permanen**: 
   - Hentikan trigger retraining darurat dan tetapkan *circuit-breaker cooldown* (misal maksimal 1 run per hari).
   - Isolasi data inferensi: data training hanya boleh bersumber dari data yang telah divalidasi oleh ground-truth label aktual (misal hasil verifikasi manual manusia / konfirmasi settlement perbankan).
   - Ubah trigger retraining dari *data drift* menjadi kombinasi *data drift AND business metric drop* (misal: conversion rate turun secara signifikan).
3. **Arsitektur Kepatuhan Regulasi**:
   - **Immutable Code & Environment**: Docker image di-freeze menggunakan SHA256 content-addressable digests (bukan tag mutabel seperti `:v2` atau `:latest`).
   - **Data Versioning (DVC/Delta Lake/Feast)**: Commit GitOps wajib menyimpan metadata hash commit Git, hash ID partisi dataset spesifik (misal S3 commit ID/Delta Table Version 142), dan random seed generator.
   - **Model Lineage Manifest**: Simpan file `provenance.json` di dalam repositori GitOps yang memetakan: `Git Commit Source Code` + `Exact Data Snapshot ID` + `Environment Container Digest` + `MLflow Run UUID`. Setiap retraining menghasilkan commit baru yang merekam keempat elemen tersebut secara atomik.

---

### 16. Summary

Implementasi MLOps lanjutan pada level enterprise beroperasi melampaui automasi kode biasa. Continuous Integration (CI) bertanggung jawab memvalidasi integritas kode, kestabilan skema, dan performa minimal model pada *golden dataset*. Continuous Training (CT) menghadirkan elastisitas adaptif melalui orchestrator terisolasi (Argo Workflows/Kubeflow) yang merespons event statistik data dan drift tanpa campur tangan teknisi secara manual. 

Terakhir, Continuous Delivery (CD) yang dioperasikan dengan prinsip GitOps dan Service Mesh (KServe/Istio) memastikan penerapan model ke produksi berjalan dengan risiko minimum melalui *progressive traffic shifting* (Canary/Shadow) yang terikat langsung pada metrik SLA teknis dan kesehatan bisnis. Fondasi otomasi CI/CD/CT yang matang mengubah machine learning dari sekadar eksperimen laboratorium menjadi komponen infrastruktur software yang deterministik, terpantau, dan dapat diandalkan dalam skala produksi masif.
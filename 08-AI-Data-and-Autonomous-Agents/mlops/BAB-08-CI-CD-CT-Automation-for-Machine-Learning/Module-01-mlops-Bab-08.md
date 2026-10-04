# Bab 08: CI/CD/CT Automation for Machine Learning — Module 01

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis Perbedaan Fundamental CI/CD Tradisional vs CI/CD/CT MLOps**: Mengidentifikasi keunikan siklus hidup Machine Learning yang melibatkan tiga dimensi dinamis: *Code*, *Data*, dan *Model Artifact*.
2. **Merancang Pipeline Continuous Integration (CI) untuk Machine Learning**: Membangun pengujian otomatis yang mencakup *data integrity checks*, *data drift sanity tests*, *unit testing logic pre-processing*, dan *model evaluation assertions*.
3. **Mengonstruksi Continuous Training (CT) Automation Engine**: Mengembangkan subsistem orkestrasi yang memicu pelatihan ulang (*retraining*) secara terprogram berbasis ambang batas degradasi metrik (*performance/data drift trigger*), jadwal periodik, maupun ketersediaan partisi data baru.
4. **Menerapkan Continuous Delivery (CD) & Progressive Deployment Strategy**: Mengimplementasikan *model promotion gate* terotomatisasi ke Model Registry serta mekanisme *Canary* atau *Shadow Deployment* untuk meluncurkan model baru tanpa *downtime*.
5. **Mendeteksi dan Memitigasi Kegagalan Sistematis CT**: Mengisolasi anomali seperti *feedback loop bias*, *training-serving skew*, dan *catastrophic forgetting* melalui *fallback automated gates*.

---

## 2. Concept Overview

Sistem perangkat lunak tradisional mengandalkan premis deterministik: kode yang identik dieksekusi terhadap lingkungan terisolasi akan menghasilkan *output* yang terprediksi. CI/CD klasik berfokus pada validasi sintaks, kompilasi, *unit testing*, integrasi sistem, dan penyebaran artefak biner (*container image*, executable).

Dalam Machine Learning, performa sistem ditentukan oleh konvergensi antara **Kode**, **Data**, dan **Model**:

$$\text{Perilaku Sistem} = f(\text{Source Code}, \text{Hyperparameters}, \text{Training Dataset})$$

Perubahan pada distribusi data tanpa adanya perubahan pada satu baris kode pun dapat menurunkan performa inferensi di lingkungan produksi. Konsekuensinya, paradigma automasi harus diperluas menjadi **CI/CD/CT**:

```
+-------------------------------------------------------------------------------+
|                       TRIPOD SIKLUS HIDUP MLOps                               |
+-------------------------------------------------------------------------------+
|                                                                               |
|       [ SOURCE CODE ] --------------> ( Continuous Integration - CI )         |
|              |                        - Unit, Integration & Pipeline Testing  |
|              v                                                                |
|       [ DATASET PIPELINE ] ---------> ( Continuous Training - CT )            |
|              |                        - Drift Triggers & Training Run         |
|              v                                                                |
|       [ MODEL ARTIFACT ] -----------> ( Continuous Delivery - CD )            |
|                                       - Registry Validation, Shadow/Canary    |
+-------------------------------------------------------------------------------+
```

*   **Continuous Integration (CI):** Menguji kode sumber ML, pipeline ekstraksi fitur, skrip pelatihan, skema data masuk, dan *drift assertion*. Artefak keluaran berupa paket kode yang teruji dan *container images*.
*   **Continuous Training (CT):** Mengorkestrasi eksekusi pipeline pelatihan ulang secara otomatis saat model mengalami degradasi performa atau data baru memenuhi volume tertentu, menghasilkan artefak model terdaftar (*registered model*).
*   **Continuous Delivery (CD):** Melakukan validasi performa model kandidat (*challenger*) terhadap model produksi aktif (*champion*), mengevaluasi batasan latensi, dan merilis inferensi ke lingkungan *staging* atau *production* secara bertahap.

---

## 3. Why It Matters

Dalam lanskap enterprise, deployment model secara manual (menggunakan notebook ad-hoc, penyalinan file `.pkl` via SFTP, atau reload server manual) memicu serangkaian kegagalan sistemik:

1. **Model Decay Tanpa Pengawasan**: Tanpa CT, sistem deteksi *fraud* atau sistem rekomendasi e-commerce kehilangan akurasi dalam hitungan hari akibat pergeseran perilaku pengguna (*concept drift*). 
2. **Reproducibility Gap**: Model produksi yang dilatih di laptop engineer sering kali tidak dapat direplikasi saat terjadi audit atau investigasi bug karena hilangnya pelacakan versi data (*data lineage*) dan *seed dependencies*.
3. **Downtime & Regresi Saat Rilis**: Penggantian model tanpa uji komparatif langsung (*challenger vs champion baseline*) dapat memunculkan lonjakan latensi inferensi dari 15ms ke 500ms, memicu kegagalan *cascading* pada microservices upstream.
4. **Compliance & Audit Trails**: Di sektor teregulasi (perbankan, kesehatan), setiap model yang dideploy wajib memiliki silsilah yang jelas: commit hash kode git, hash data latih, metrik evaluasi offline, dan riwayat persetujuan otomatis.

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan end-to-end arsitektur pipeline CI/CD/CT yang beroperasi secara decoupling berbasis event dan monitoring:

```
[ Developer ] ----> Push Code ----+
                                  |
                                  v
                    +-----------------------------+
                    |        CI PIPELINE          |
                    | 1. Linting & Formatting     |
                    | 2. Unit Test Logic          |
                    | 3. Contract & Schema Tests  |
                    | 4. Build Training Container |
                    +--------------+--------------+
                                   |
                             (Publish Image)
                                   |
                                   v
+------------------+      +------------------+      +------------------+
| Scheduled Cron   | ---> |                  | <--- |  Data Arrival    |
| (e.g. Weekly)    |      |   ORCHESTRATOR   |      |  (S3 / BigQuery) |
+------------------+      |  (Argo / Kubeflow|      +------------------+
| Drift Detection  | ---> |   / Airflow)     |
| Alert (Webhook)  |      +--------+---------+
+------------------+               |
                             (Triggers CT)
                                   |
                                   v
                    +-----------------------------+
                    |        CT PIPELINE          |
                    | 1. Data Ingestion & Split   |
                    | 2. Data Validation (GreatEx)|
                    | 3. Distributed Training     |
                    | 4. Evaluation vs Threshold  |
                    | 5. Register Candidate Model |
                    +--------------+--------------+
                                   |
                               (Artifact)
                                   |
                                   v
+----------------------------------------------------------------------+
|                           CD PIPELINE                                |
|                                                                      |
|  +--------------------+     Fail      +----------------------------+ |
|  | Challenger Model   | ------------> | Reject & Alert Team        | |
|  | vs Champion Gate   |               +----------------------------+ |
|  +---------+----------+                                              |
|            | Pass                                                    |
|            v                                                         |
|  +-----------------------------------------------------------------+ |
|  | Progressive Rollout (Canary / Shadow / Blue-Green Deployment)   | |
|  +---------------------------------+-------------------------------+ |
+------------------------------------|---------------------------------+
                                     |
                                     v
                        +--------------------------+
                        | Model Serving Cluster    |
                        | (Triton / TorchServe /   |
                        |  FastAPI + KServe)       |
                        +------------+-------------+
                                     |
                             (Inference Logs)
                                     v
                        +--------------------------+
                        | Drift & Metrics Monitor  |
                        | (Evidently / Prometheus) |
                        +--------------------------+
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 CI untuk ML: Data, Code, dan Pipeline Testing
Pipeline CI untuk ML wajib mengisolasi kesalahan logika sebelum proses komputasi berat dimulai:
*   **Unit Testing Preprocessing**: Menguji fungsi transformasi (imputasi, skalarisasi, *encoding*) dengan *mock synthetic dataset*.
*   **Schema & Integrity Assertions**: Memverifikasi bahwa data masukan memiliki kolom, tipe data, rentang nilai (misal: age > 0), dan rasio null yang berada di bawah toleransi batas kritis.
*   **Pipeline Dry-Run**: Mengeksekusi pelatihan selama 1 *epoch* pada subset data mini (100 baris) untuk memastikan tidak terjadi kebocoran memori (*OOM*), *tensor shape mismatch*, atau kegagalan penulisan artefak.

### 5.2 CT: Automated Trigger Mechanics
Pipeline Continuous Training tidak boleh berjalan secara statis belaka. CT diaktifkan melalui tiga mekanisme pemicu (*triggers*):
1.  **Event-Driven (Data Arrival)**: Webhook/Event notification saat data partisi harian/mingguan baru berhasil mendarat di Object Storage (S3/GCS).
2.  **Metric Degradation (Model/Data Drift)**: Deteksi pergeseran statistik antara data inferensi dan data latih menggunakan metrik:
    *   *Population Stability Index (PSI)*: $\text{PSI} > 0.25$ menandakan pergeseran signifikan.
    *   *Kolmogorov-Smirnov (KS) Test* atau *Wasserstein Distance* untuk fitur numerik berkelanjutan ($p\text{-value} < 0.05$).
3.  **Scheduled Cron**: Menghindari *data staleness* pada domain dengan dinamika tren musiman (misal: retraining mingguan setiap Minggu malam).

### 5.3 CD: Progressive Delivery & Quality Gates
Model tidak boleh dideploy langsung menggantikan model aktif tanpa melewati *Quality Gate*:
*   **Evaluation Gate**: Model kandidat harus melampaui performa model juara (*champion*) pada dataset evaluasi terstandarisasi (*Golden Dataset*) dan *Holdout Dataset* terbaru:
    $$\text{Metric}_{\text{Challenger}} > \text{Metric}_{\text{Champion}} + \epsilon$$
*   **Latency Gate**: P99 inferensi model kandidat diuji dengan *load testing* terotomatisasi; jika melampaui batas SLA (misal: > 50ms), rilis digagalkan otomatis.
*   **Shadow Deployment**: Model baru menerima traffic produksi paralel tanpa memproses respons ke pengguna akhir. Memvalidasi kestabilan I/O sistem pada kondisi riil.
*   **Canary Rollout**: Membuka traffic riil secara bertahap ($5\% \rightarrow 25\% \rightarrow 50\% \rightarrow 100\%$) dengan observabilitas metrik error rate secara real-time.

---

## 6. Production-Ready Code Implementation

Berikut adalah implementasi sistem CI/CD/CT terpadu yang memuat:
1. **Drift-Trigger Worker**: Memeriksa drift data produksi dan memicu pipeline via webhook.
2. **Strict Evaluation Gate**: Membandingkan model kandidat vs champion sebelum promosi.
3. **CI/CD Pipeline Definition (GitHub Actions)**: Otomatisasi pengujian, pelatihan, dan pendaftaran model.

### 6.1 Drift Detection Trigger Service (`drift_monitor.py`)

```python
"""
drift_monitor.py
Komponen monitoring yang mengevaluasi Population Stability Index (PSI)
dan memicu pemicu CT jika terdeteksi data drift melampaui ambang batas.
"""

from typing import Dict, Tuple
import logging
import numpy as np
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("DriftMonitor")


class DriftDetector:
    def __init__(self, psi_threshold: float = 0.25) -> None:
        self.psi_threshold = psi_threshold

    def calculate_psi(
        self, baseline: np.ndarray, target: np.ndarray, num_buckets: int = 10
    ) -> float:
        """
        Menghitung Population Stability Index (PSI) antara dua distribusi.
        PSI = sum((Actual% - Expected%) * ln(Actual% / Expected%))
        """
        if len(baseline) == 0 or len(target) == 0:
            raise ValueError("Array data tidak boleh kosong.")

        # Tentukan bucket dari data baseline
        quantiles = np.linspace(0, 100, num_buckets + 1)
        bucket_limits = np.percentile(baseline, quantiles)
        bucket_limits[0] = -np.inf
        bucket_limits[-1] = np.inf

        # Frekuensi bucket
        baseline_counts, _ = np.histogram(baseline, bins=bucket_limits)
        target_counts, _ = np.histogram(target, bins=bucket_limits)

        # Ubah ke persentase dengan Laplace smoothing untuk menghindari deviasi pembagian nol
        epsilon = 1e-4
        baseline_pct = (baseline_counts + epsilon) / (len(baseline) + (epsilon * num_buckets))
        target_pct = (target_counts + epsilon) / (len(target) + (epsilon * num_buckets))

        psi_val = np.sum((target_pct - baseline_pct) * np.log(target_pct / baseline_pct))
        return float(psi_val)

    def evaluate_features_drift(
        self, baseline_data: Dict[str, np.ndarray], current_data: Dict[str, np.ndarray]
    ) -> Tuple[bool, Dict[str, float]]:
        """
        Mengevaluasi seluruh fitur. Mengembalikan flag re-train dan detail skor PSI.
        """
        drift_results: Dict[str, float] = {}
        trigger_retraining = False

        for feature_name, base_vals in baseline_data.items():
            if feature_name not in current_data:
                logger.warning(f"Fitur '{feature_name}' hilang di data monitoring!")
                continue

            psi_score = self.calculate_psi(base_vals, current_data[feature_name])
            drift_results[feature_name] = psi_score
            logger.info(f"Fitur: {feature_name} | PSI: {psi_score:.4f}")

            if psi_score >= self.psi_threshold:
                logger.warning(
                    f"Drift terdeteksi pada fitur '{feature_name}' (PSI: {psi_score:.4f} >= {self.psi_threshold})"
                )
                trigger_retraining = True

        return trigger_retraining, drift_results

    def trigger_ct_pipeline(self, dispatch_url: str, token: str, payload: dict) -> bool:
        """
        Memicu pipeline CT eksternal via GitHub Repository Dispatch atau Webhook Orchestrator.
        """
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(dispatch_url, json=payload, headers=headers, timeout=10)
            if response.status_code in [200, 204]:
                logger.info("Pipeline CT berhasil dipicu.")
                return True
            else:
                logger.error(
                    f"Gagal memicu CT: Status {response.status_code} - {response.text}"
                )
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Pengecualian jaringan saat menghubungi orkestrator: {str(e)}")
            return False


if __name__ == "__main__":
    np.random.seed(42)
    # Baseline: Distribusi normal standar
    baseline_feature_a = np.random.normal(loc=0.0, scale=1.0, size=5000)
    # Target: Terjadi distribusi shift signifikan (mean bergeser ke 1.2)
    current_feature_a = np.random.normal(loc=1.2, scale=1.2, size=5000)

    detector = DriftDetector(psi_threshold=0.25)
    should_retrain, report = detector.evaluate_features_drift(
        baseline_data={"feature_a": baseline_feature_a},
        current_data={"feature_a": current_feature_a},
    )

    if should_retrain:
        logger.info("Ambang batas dilampaui. Mengirim sinyal pemicu Continuous Training.")
        # Simulasi eksekusi trigger
        # detector.trigger_ct_pipeline(...)
```

---

### 6.2 Strict Evaluation & Promotion Gate (`model_evaluator.py`)

```python
"""
model_evaluator.py
Memvalidasi metrik model kandidat (Challenger) terhadap model produksi (Champion).
Mengintegrasikan pengujian performa prediksi dan latensi inferensi.
"""

from typing import Dict, Any, NamedTuple
import json
import logging
import time
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ModelEvaluator")


class EvaluationMetrics(NamedTuple):
    accuracy: float
    f1_score: float
    p99_latency_ms: float


class ModelGateChecker:
    def __init__(
        self,
        min_f1_gain: float = 0.01,
        max_p99_latency_ms: float = 50.0,
    ) -> None:
        self.min_f1_gain = min_f1_gain
        self.max_p99_latency_ms = max_p99_latency_ms

    def measure_inference_latency(
        self, model_stub: Any, sample_inputs: np.ndarray, iterations: int = 200
    ) -> float:
        """
        Mengukur latensi P99 dari pemanggilan model secara berulang.
        """
        latencies = []
        for _ in range(iterations):
            idx = np.random.randint(0, len(sample_inputs))
            payload = sample_inputs[idx : idx + 1]
            t0 = time.perf_counter()
            _ = model_stub(payload)  # Panggilan fungsi inferensi
            latencies.append((time.perf_counter() - t0) * 1000.0)

        return float(np.percentile(latencies, 99))

    def evaluate_promotion(
        self, champion: EvaluationMetrics, challenger: EvaluationMetrics
    ) -> Tuple[bool, str]:
        """
        Mengevaluasi apakah model Challenger berhak menggantikan Champion.
        """
        # Latency Hard Gate
        if challenger.p99_latency_ms > self.max_p99_latency_ms:
            reason = (
                f"REJECTED: P99 Latency Challenger ({challenger.p99_latency_ms:.2f}ms) "
                f"melampaui batas SLA ({self.max_p99_latency_ms:.2f}ms)."
            )
            return False, reason

        # F1 Score Degradation/Improvement Gate
        f1_difference = challenger.f1_score - champion.f1_score
        if f1_difference < self.min_f1_gain:
            reason = (
                f"REJECTED: Margin perbaikan F1 ({f1_difference:+.4f}) "
                f"di bawah syarat minimum gain ({self.min_f1_gain:+.4f})."
            )
            return False, reason

        # Accuracy Regression Check
        if challenger.accuracy < champion.accuracy:
            reason = (
                f"REJECTED: Terjadi regresi akurasi global: "
                f"Challenger ({challenger.accuracy:.4f}) < Champion ({champion.accuracy:.4f})."
            )
            return False, reason

        return True, "PROMOTED: Model Challenger memenuhi seluruh kriteria kelayakan operasional."


if __name__ == "__main__":
    champion_perf = EvaluationMetrics(accuracy=0.912, f1_score=0.885, p99_latency_ms=22.4)
    challenger_perf = EvaluationMetrics(accuracy=0.925, f1_score=0.902, p99_latency_ms=28.1)

    gate = ModelGateChecker(min_f1_gain=0.01, max_p99_latency_ms=50.0)
    passed, reason = gate.evaluate_promotion(champion=champion_perf, challenger=challenger_perf)

    output_decision = {
        "status": "APPROVED" if passed else "REJECTED",
        "reason": reason,
        "champion_metrics": champion_perf._asdict(),
        "challenger_metrics": challenger_perf._asdict(),
    }

    print(json.dumps(output_decision, indent=2))
    if not passed:
        exit(1)
```

---

### 6.3 GitHub Actions Workflow: End-to-End CI/CT/CD (`.github/workflows/ml_lifecycle.yml`)

```yaml
name: Production ML CI/CD/CT Pipeline

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]
  repository_dispatch:
    types: [ trigger-training-drift, trigger-scheduled-retrain ]

env:
  PYTHON_VERSION: "3.10"
  MODEL_NAME: "fraud_detector"

jobs:
  continuous-integration:
    name: Code & Preprocessing Validation
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: "pip"

      - name: Install Linting and Testing Tools
        run: |
          python -m pip install --upgrade pip
          pip install flake8 pytest pytest-cov pandera pydantic

      - name: Run Code Linting & Static Analysis
        run: |
          # Hentikan eksekusi jika terjadi syntax error atau variabel undefined
          flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
          flake8 . --count --exit-zero --max-complexity=10 --max-line-length=100

      - name: Run Schema Contracts & Unit Tests
        run: |
          pytest tests/unit/ -v --cov=src/ --cov-report=term-missing

  continuous-training:
    name: Pipeline Execution & Training
    needs: continuous-integration
    if: github.event_name == 'repository_dispatch' || github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install Pipeline Dependencies
        run: |
          pip install -r requirements-training.txt

      - name: Execute Training Run
        run: |
          # Menjalankan skrip training yang mengintegrasikan DVC dan MLflow
          python src/train.py --output-dir models/candidate

      - name: Evaluate Model Gate
        run: |
          python src/model_evaluator.py

      - name: Upload Candidate Model Artifact
        uses: actions/upload-artifact@v4
        with:
          name: candidate-model
          path: models/candidate/
          retention-days: 7

  continuous-delivery:
    name: Model Promotion & Deploy Trigger
    needs: continuous-training
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Download Candidate Model
        uses: actions/download-artifact@v4
        with:
          name: candidate-model
          path: candidate/

      - name: Log into Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and Push Inference Container
        run: |
          IMAGE_TAG="ghcr.io/${{ github.repository }}/${{ env.MODEL_NAME }}:${{ github.sha }}"
          docker build -t $IMAGE_TAG -f docker/serving.Dockerfile .
          docker push $IMAGE_TAG

      - name: Trigger GitOps Deploy (Canary Rollout)
        run: |
          echo "Memperbarui manifest ArgoCD / Kustomize untuk memicu Canary Deployment."
          # Mengirim patch commit ke repositori GitOps deployment terpisah
```

---

## 7. Edge Cases & Failure Modes

Dalam automasi CI/CD/CT tingkat produksi, serangkaian skenario ekstrem (*edge cases*) dapat melumpuhkan pipeline jika tidak diantisipasi:

1. **The Poisoned Loop (Automated Bad Data Ingestion)**:
   *   *Kegagalan*: Sumber data upstream mengalami kerusakan formatting atau diinjeksi anomali massal. Pipeline CT langsung terpicu, melatih model dengan data cacat, dan jika evaluation gate tidak mencakup baseline statis (*golden baseline*), model cacat dapat lolos rilis.
   *   *Mitigasi*: Wajib menyertakan *Data Pre-validation Gate* (misal: Great Expectations) yang memverifikasi volume baris, batas null, dan uji integritas sebelum pipeline training diizinkan membaca data.
2. **Feedback Loop Bias (Self-Fulfilling Prophecy)**:
   *   *Kegagalan*: Model menyaring item tertentu (misalnya, fraud blocking agresif). Data transaksi yang masuk untuk siklus retraining berikutnya hanya mencakup transaksi yang diizinkan model sebelumnya. Model melatih ulang dirinya sendiri pada data yang bias.
   *   *Mitigasi*: Sisipkan persentase kecil traffic eksplorasi (*epsilon-greedy*) yang tidak dipengaruhi filter model untuk mengumpulkan data riil tak terdistorsi.
3. **Training Divergence & Silent Degradation**:
   *   *Kegagalan*: Konvergensi model gagal (misal: NaN loss pada neural network atau *exploding gradient*), menghasilkan model yang memprediksi satu kelas konstan.
   *   *Mitigasi*: Pengujian *Invariance* dan *Directional Expectations* (CheckList testing). Verifikasi bahwa akurasi kelas minoritas tidak anjlok ke 0% meskipun metrik agregat global terlihat dapat diterima.
4. **Race Condition pada Trigger Orkestrasi CT**:
   *   *Kegagalan*: Trigger data-arrival dan drift alert terpicu bersamaan, memicu dua pipeline training paralel yang memperebutkan GPU cluster yang sama dan memicu kegagalan alokasi memori (*OOM*).
   *   *Mitigasi*: Definisikan *Concurrency Policy: Forbid* pada scheduler (Argo/Airflow) agar antrean berikutnya ditahan (*queue*) atau dibatalkan (*skip*).

---

## 8. Trade-offs & Alternatif Solusi

| Dimensi Pendekatan | Pipeline Berbasis CI/CD Engine (GitHub Actions / GitLab CI) | Kubernetes-Native Workflow (Argo Workflows / Kubeflow) | Dedicated ML Orchestrator (SageMaker / Vertex AI) |
| :--- | :--- | :--- | :--- |
| **Kelebihan** | - Mudah disetup jika codebase ada di VCS.<br>- Tidak butuh cluster k8s tambahan.<br>- Pengalaman pengembang terpadu. | - Native container orchestration.<br>- Resource dynamic scheduling (GPU/vCPU).<br>- Skalabilitas masif tak terbatas. | - Fully managed, zero cluster maintenance.<br>- Integrasi built-in model registry & endpoint monitoring. |
| **Kelemahan** | - Keterbatasan runner compute (sulit multi-GPU node).<br>- Tidak optimal untuk pipeline berdurasi berjam-jam/berhari-hari. | - Operasional maintenance cluster K8s kompleks.<br>- Biaya infrastruktur awal tinggi. | - Vendor lock-in yang tinggi.<br>- Biaya komputasi per jam lebih mahal ketimbang self-hosted. |
| **Use Case Terbaik** | Tim kecil-menengah, model tabular ringan (XGBoost, Sklearn), inferensi CPU. | Tim enterprise dengan infrastruktur internal, distributed deep learning, data volume terabyte. | Tim yang ingin fokus penuh ke pemodelan tanpa beban maintain infrastruktur cluster internal. |

### Strategi Deployment: Canary vs Shadow vs Blue-Green

*   **Shadow Deployment**: Sangat aman untuk risiko operasional tinggi (sektor finansial/medis), karena pengguna riil tidak pernah terekspos respons model challenger. *Trade-off*: Menggandakan biaya komputasi inferensi serving.
*   **Canary Deployment**: Efisien biaya dan memvalidasi respons aktual dari live user. *Trade-off*: Pengguna canary berpotensi terpapar inferensi keliru jika gate monitoring terlambat melakukan rollback otomatis.
*   **Blue-Green Deployment**: Pengalihan seketika (*instant switch*), memudahkan rollback dalam hitungan milidetik. *Trade-off*: Tidak menguji perilaku model di bawah distribusi traffic riil yang parsial.

---

## 9. Best Practices & Standar Industri

1. **GitOps sebagai Single Source of Truth**:
   * Simpan seluruh spesifikasi deployment, threshold evaluasi, dan definisi pipeline dalam repository Git yang terversi. Promosi model ke produksi dieksekusi via Git commit yang memperbarui tag digest artefak model.
2. **Immutable Model Artifacts & Strict Lineage**:
   * Jangan pernah menimpa artefak model (`latest` tag anti-pattern). Gunakan *semantic versioning* atau *Git commit SHA* yang dipetakan ke *DVC Commit Hash* data latih dan *MLflow Run ID*.
3. **Decouple Training Execution from Serving**:
   * Format pipeline ekspor model wajib menggunakan representasi terbuka berkinerja tinggi seperti **ONNX**, **TorchScript**, atau runtime **Triton Model Configuration** guna menghindari ketergantungan runtime training Python di pod serving.
4. **Golden Dataset Regression Baseline**:
   * Pertahankan subset data evaluasi statis yang dikurasi manusia (*golden test suite*) yang mencakup skenario kritis atau *edge cases* historis. Model challenger **wajib** lulus 100% pada subset ini terlepas dari keunggulan metrik statistik pada data dinamis.
5. **Circuit Breakers & Automated Rollback**:
   * Pasang metrik prometheus pada level microservice: jika inferensi mengembalikan error HTTP 5xx > 1% atau inferensi rata-rata > 100ms selama jendela observasi 5 menit pada fase Canary, orkestrator deployment wajib memicu rollback instan ke model Champion.

---

## 10. Hands-on Lab Exercise: Membangun CI/CD/CT Automation Loop

### Skenario Lab
Anda bertugas membangun pipeline terotomatisasi untuk model pendeteksi anomali transaksi:
1. Menyiapkan assertion testing untuk memvalidasi kualitas data.
2. Mengeksekusi Continuous Training jika terjadi drift sintetis.
3. Melakukan evaluasi otomatis dan promosi model kandidat.

### Langkah 1: Struktur Proyek
Buat struktur direktori berikut di lingkungan lokal Anda:

```bash
mkdir -p mlops_cicd_lab/{src,tests,data,models}
cd mlops_cicd_lab
```

### Langkah 2: Dependensi Proyek
Buat file `requirements.txt`:

```text
numpy>=1.23.0
scikit-learn>=1.2.0
pandera>=0.15.0
pytest>=7.2.0
requests>=2.28.0
```

Pasang ke virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Langkah 3: Menulis Kontrak Validasi Data (`src/data_contract.py`)
Gunakan Pandera untuk memastikan skema masukan valid sebelum proses CT dijalankan:

```python
import pandera as pa
from pandera.typing import Series
import pandas as pd

class TransactionSchema(pa.DataFrameModel):
    transaction_id: Series[str] = pa.Field(nullable=False, unique=True)
    amount: Series[float] = pa.Field(ge=0.0, le=1_000_000.0)
    user_age: Series[int] = pa.Field(ge=18, le=120)
    is_foreign: Series[int] = pa.Field(isin=[0, 1])

    class Config:
        strict = True
        coerce = True

def validate_dataframe(df: pd.DataFrame) -> bool:
    try:
        TransactionSchema.validate(df)
        return True
    except pa.errors.SchemaError as err:
        print(f"Data Schema Validation Failed: {err}")
        return False
```

### Langkah 4: Menulis Unit Test CI (`tests/test_pipeline.py`)

```python
import pytest
import pandas as pd
from src.data_contract import validate_dataframe

def test_data_contract_valid():
    valid_data = pd.DataFrame({
        "transaction_id": ["tx_001", "tx_002"],
        "amount": [150.50, 99.00],
        "user_age": [25, 45],
        "is_foreign": [0, 1]
    })
    assert validate_dataframe(valid_data) is True

def test_data_contract_invalid_amount():
    invalid_data = pd.DataFrame({
        "transaction_id": ["tx_003"],
        "amount": [-50.0], # Amount negatif tidak valid
        "user_age": [30],
        "is_foreign": [0]
    })
    assert validate_dataframe(invalid_data) is False
```

Jalankan pengujian CI lokal:
```bash
pytest tests/ -v
```

### Langkah 5: Skrip Simulasi Siklus Penuh (`run_lab.py`)
Simulasikan interaksi deteksi drift, eksekusi CT, dan gate evaluasi:

```python
import numpy as np
import pandas as pd
from src.data_contract import validate_dataframe

def simulate_pipeline():
    print("[1] Memvalidasi Integritas Data Masuk...")
    raw_data = pd.DataFrame({
        "transaction_id": [f"tx_{i}" for i in range(100)],
        "amount": np.random.uniform(10.0, 500.0, size=100),
        "user_age": np.random.randint(18, 70, size=100),
        "is_foreign": np.random.choice([0, 1], size=100)
    })
    
    if not validate_dataframe(raw_data):
        print("CI Gate Gagal: Data tidak valid.")
        return

    print("Data lolos validasi skema.")
    
    print("\n[2] Mengevaluasi Data Drift (Simulasi)...")
    baseline_amounts = np.random.normal(100, 20, 1000)
    incoming_amounts = np.random.normal(180, 50, 1000) # Terjadi drift signifikan
    
    # Hitung rasio perbedaan mean sederhana sebagai sinyal
    shift_ratio = abs(np.mean(incoming_amounts) - np.mean(baseline_amounts)) / np.mean(baseline_amounts)
    print(f"Pergeseran Data: {shift_ratio:.2%}")
    
    if shift_ratio > 0.30:
        print("Sinyal CT Aktif: Drift melampaui batas toleransi 30%. Memulai training ulang...")
        # Simulasi CT Training
        print("Melatih model challenger pada data partisi baru...")
        challenger_acc = 0.94
        champion_acc = 0.89
        
        print("\n[3] Model Gate Evaluation...")
        if challenger_acc > champion_acc:
            print(f"PROMOSI BERHASIL: Challenger ({challenger_acc}) > Champion ({champion_acc}).")
            print("Memicu deployment canary...")
        else:
            print("REJECTED: Challenger tidak menunjukkan peningkatan metrik.")
    else:
        print("Data stabil. Model retraining ditangguhkan.")

if __name__ == "__main__":
    simulate_pipeline()
```

Jalankan simulasi:
```bash
python run_lab.py
```

### Verifikasi Hasil Lab
1. Semua pengujian di langkah 4 berstatus `PASSED`.
2. Pada simulasi langkah 5, data diverifikasi berhasil memicu proses CT akibat kalkulasi `shift_ratio` di atas batas toleransi.
3. Model challenger secara otomatis dipromosikan ke tahap canary deployment karena melampaui metrik evaluasi champion.
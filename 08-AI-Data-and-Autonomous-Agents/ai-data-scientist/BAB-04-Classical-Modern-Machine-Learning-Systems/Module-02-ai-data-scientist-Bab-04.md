# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 04: Classical & Modern Machine Learning Systems**  
**Jalur: AI Data Scientist (08-AI-Data-and-Autonomous-Agents)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta enterprise diharapkan mampu:
- **Merancang & Mengimplementasikan Arsitektur Inferensi Ultra-Low Latency:** Mentransformasikan model berbasis ensemble pohon (*tree-based ensembles* seperti XGBoost/LightGBM) dari runtime Python standar menjadi representasi biner terkompilasi (*native C shared library* / ONNX / Treelite) untuk mencapai *throughput* tinggi dengan latensi $p99 < 10\text{ ms}$.
- **Mengembangkan Pipa Transformasi Fitur Nir-Bocor (*Leak-Free Production Feature Pipelines*):** Membangun transformer kustom yang kompatibel dengan Scikit-Learn API menggunakan teknik *out-of-fold target encoding*, *vectorized missing value handling*, dan *point-in-time correctness*.
- **Mengintegrasikan Dual-Layer Feature Store:** Menghubungkan *offline feature store* (berbasis Parquet/DuckDB) untuk komputasi fitur analitis skala besar dengan *online feature store* (berbasis Redis) untuk *low-latency key-value lookup* saat waktu inferensi.
- **Mendeteksi & Memitigasi Degradasi Model Secara Real-Time:** Mengimplementasikan mesin deteksi pergeseran data (*data drift*) dan pergeseran konsep (*concept drift*) menggunakan metrik statistik *Population Stability Index* (PSI) dan uji dua sampel Kolmogorov-Smirnov (KS-test) pada aliran data produksi.

---

## 2. Prerequisite

Sebelum memulai modul ini, Anda wajib menguasai:
- **Arsitektur Internal Tree Ensembles:** Memahami formulasi matematis split criterion, regresi gradien tingkat kedua (metode Newton-Raphson pada XGBoost), serta penalti regularisasi L1/L2 ($\alpha, \lambda$).
- **Python Systems Programming:** Pemahaman mendalam mengenai manipulasi memori (*zero-copy buffer* via Apache Arrow), GIL (*Global Interpreter Lock*), serta integrasi C-types/Cython.
- **Containerization & Network Protocol:** Konfigurasi Docker, RPC (gRPC vs REST), dan mekanisme *caching* in-memory (Redis).
- **Statistika Inferensial Lanjutan:** Distribusi probabilitas empiris, divergensi Kullback-Leibler (KL), Wasserstein Distance, dan pengujian hipotesis non-parametrik.

---

## 3. Concept & Internal Architecture

Dalam rekayasa sistem *machine learning* skala *enterprise*, kesenjangan terbesar bukan terletak pada optimasi fungsi objektif (*loss function*), melainkan pada transisi dari model prototipe eksperimental menuju artefak produksi yang deterministik, terukur, dan berlatensi rendah.

```
                         ARSITEKTUR END-TO-END SISTEM PRODUKSI ML
                         
+-------------------+      Point-in-Time Join     +------------------------+
|  Historical Data  | --------------------------> |  Offline Feature Store |
|  (Data Lakehouse) |                             |     (DuckDB/Parquet)   |
+-------------------+                             +------------------------+
                                                              |
                                                              v
+-------------------+      Native Serialization   +------------------------+
|  LightGBM/XGBoost | --------------------------> |   Treelite Compiler    |
|   Training Engine |                             |   (C-Code Generation)  |
+-------------------+                             +------------------------+
                                                              |
                                                              v Compiled Shared Lib (.so)
+--------------------------------------------------------------------------+
|                        LOW-LATENCY SERVING RUNTIME                       |
|                                                                          |
|                     Client Request (Payload JSON/gRPC)                   |
|                                      |                                   |
|                                      v                                   |
|    +-------------------+    Feature Hydration    +------------------+    |
|    | Inference Gateway | <====================== |  Online Feature  |    |
|    | (FastAPI/C++ Core)|                         |  Store (Redis)   |    |
|    +-------------------+                         +------------------+    |
|              |                                                           |
|              v Zero-Copy Memory View                                     |
|    +-------------------+                                                 |
|    | Treelite / C-API  | ===> SIMD Matrix Instruction (Tree Traversal)   |
|    +-------------------+                                                 |
|              |                                                           |
|              v Model Prediction (Probability / Score)                    |
|    +-------------------+                                                 |
|    |  Telemetry Queue  |                                                 |
|    +-------------------+                                                 |
+--------------|-----------------------------------------------------------+
               |
               v Async Stream (Kafka)
+--------------------------------------------------------------------------+
|                       MONITORING & DRIFT DETECTOR                        |
|                                                                          |
|   +---------------------+   Stat Window (KS/PSI)   +-----------------+   |
|   | Drift Engine Worker | =======================> | Prometheus /    |   |
|   | (Evidently/Custom)  |                          | Alertmanager    |   |
|   +---------------------+                          +-----------------+   |
+--------------------------------------------------------------------------+
```

### Mekanisme Split: Exact Greedy vs Histogram-Based

Algoritma boosting klasik (seperti GBM standar) mengandalkan pencarian ambang (*threshold*) terbaik dengan metode *Exact Greedy*, yang mengurutkan semua fitur kontinu pada setiap iterasi:

$$\text{Kompleksitas Waktu} = \mathcal{O}(d \cdot n \log n)$$

di mana $d$ adalah jumlah fitur dan $n$ adalah jumlah sampel data.

Implementasi modern (LightGBM dan XGBoost `tree_method='hist'`) menggunakan diskretisasi berbasis histogram. Nilai-nilai kontinu dipetakan ke dalam $K$ *bins* diskret (biasanya $K = 256$, memungkinkannya disimpan dalam integer `uint8` 1-byte). Kompleksitas tereduksi menjadi:

$$\text{Kompleksitas Waktu} = \mathcal{O}(d \cdot n) + \mathcal{O}(d \cdot K)$$

Pengurangan footprint memori dan pemanfaatan cache CPU L1/L2 dari pendekatan histogram ini meningkatkan kecepatan komputasi secara signifikan. Selain itu, LightGBM mengintroduksi:
1. **GOSS (Gradient-based One-Side Sampling):** Mengabaikan sampel data dengan gradien kecil (sudah konvergen) dan memprioritaskan sampel dengan gradien besar untuk mempercepat pencarian split tanpa merusak distribusi sampling secara drastis melalui kompensasi bobot:
   $$\tilde{g}_i = \frac{1 - a}{b} g_i \quad \text{untuk data dengan gradien kecil}$$
2. **EFB (Exclusive Feature Bundling):** Menggabungkan fitur-fitur yang saling eksklusif (*sparse* dan jarang bernilai non-zero secara bersamaan) ke dalam satu *bin* tunggal untuk mereduksi dimensi $d$.

### Mengapa Runtime Python Lambat untuk Evaluasi Pohon Ensembel?

Secara default, inferensi menggunakan API Scikit-Learn atau XGBoost Python melibatkan:
1. **Pointer Chasing Overhead:** Struktur data pohon diimplementasikan sebagai pointer rekursif ke node anak (*left child* / *right child*). Hal ini menyebabkan *cache miss* masif pada CPU karena lokasi memori node pohon terdistribusi secara acak.
2. **Branch Misprediction:** Percabangan logika kondisional if-else kontinu pada kedalaman pohon tinggi menggagalkan instruksi *speculative execution* pada CPU modern.
3. **Interpreter Overhead:** Translasi tipe data antara Python Object, Numpy C-Buffer, dan C++ engine internal menimbulkan biaya marshal/unmarshal yang tidak dapat diabaikan pada *traffic* ratusan ribu transaksi per detik.

Solusi arsitektur produksi adalah mengompilasi representasi pohon keputusan langsung menjadi representasi linear biner atau kode C murni menggunakan **Treelite** atau **ONNX Runtime**, yang memanfaatkan *loop unrolling*, eliminasi *dynamic branch*, serta instruksi vektor SIMD (AVX-512).

---

## 4. Why & What

| Dimensi | Pendekatan Prototipe (Notebook/Monolitik) | Pendekatan Produksi Lanjutan |
| :--- | :--- | :--- |
| **Pipeline Transformasi** | `df.apply()`, `pandas.get_dummies()` di memori secara ad-hoc | Scikit-learn Pipeline kustom berbasis C-extension/Numpy, *serializable*, deterministik |
| **Penyimpanan Fitur** | File CSV statis, query SQL ad-hoc langsung ke replica DB | Dual-Layer Feature Store (Parquet/DuckDB untuk analitis; Redis untuk serving real-time) |
| **Runtime Inferensi** | `model.predict(df)` dalam worker WSGI Flask/FastAPI biasa | Model terkompilasi biner C (`.so`) via Treelite / TensorRT / Triton Inference Server |
| **Validasi Skema & Data** | Validasi manual atau nihil | Kontrak skema ketat menggunakan Pydantic V2 / Arrow Schema, validasi tipe level byte |
| **Deteksi Degradasi** | Pengecekan manual mingguan/bulanan saat metrik bisnis turun | Stream-based drift detection engine (PSI, KS-Test, JS Divergence) via Prometheus alerts |

---

## 5. How (Workflow Detail)

Alur kerja arsitektur ML produksi dirancang melalui tahapan siklus hidup berikut:

```
[Feature Engineering Pipeline]
               |
               v
[Point-in-Time Offline Join (Mencegah Target Leakage)]
               |
               v
[Histogram-Based GBDT Distributed Training]
               |
               v
[Model Pruning & Compilation (Treelite -> libmodel.so)]
               |
               v
[Integration Test: Output Parity & Latency Profiling]
               |
               v
[Artifact Registry Deployment (MinIO/S3)]
               |
               +-----------------------------------+
               |                                   |
               v                                   v
[Inference Service (FastAPI + C Engine)]   [Dual-Write Stream Monitoring]
               |                                   |
               v                                   v
[Hydrate Fitur Real-Time dari Redis]       [Sliding Window Drift Compute]
```

1. **Definisi Transformasi Stateful:** Semua operasi pra-pemrosesan (normalisasi, *target encoding*, imputasi) harus mengisolasi fase `fit()` (hanya membaca data pelatihan) dari fase `transform()` (menerapkan parameter tersimpan pada data validasi/inferensi).
2. **Kompilasi Model Tree ke Native Code:**
   Model LightGBM/XGBoost dikonversi menjadi berkas representasi intermediate Treelite, kemudian dikompilasi oleh compiler C (`clang`/`gcc`) menggunakan flag optimasi tinggi (`-O3 -mavx2 -fPIC`) menjadi *shared library* (`.so` / `.dll`).
3. **Serving via Zero-Copy Memory Interface:**
   API server mengekstrak fitur mentah dari request, mengambil riwayat fitur agregasi dari Redis menggunakan koneksi pooling non-blocking, membentuk *flat memory buffer*, dan mengeksekusi inferensi melalui *C-types binding* ke shared library yang telah dimuat di memori.
4. **Asynchronous Drift Observation:**
   Data inferensi beserta prediksinya dialirkan secara asinkron ke message broker (Kafka). Layanan konsumen menghitung metrik statistik menggunakan *sliding window* dan membandingkannya terhadap distribusi referensi saat model dilatih (*baseline*).

---

## 6. Analogy & Diagram ASCII

### Analogi Percabangan Logika
Bayangkan sebuah dokumen investigasi manual dengan 1.000 halaman pertanyaan bercabang ("Jika A > 5 buka hal 12, jika tidak buka hal 45"). Seorang kurir (CPU) harus berlari bolak-balik mengambil buku baru di rak yang jauh setiap kali membaca halaman baru (**Pointer Chasing & Cache Miss**). 

Proses kompilasi Treelite bertindak layaknya mencetak ulang seluruh buku investigasi tersebut menjadi satu lembar sirkuit elektronik terpadu (*printed circuit board*). Seluruh pertanyaan dikonversi menjadi kabel terpatri yang dieksekusi seketika menggunakan aliran listrik secara paralel (**SIMD Execution & Linear Instruction Array**).

```
Tree Traversal Konvensional (Python Engine):
[Node 0] ---> (Memory Pointer Heap Address: 0x7ffd1)
                 |
                 +---> [Node Left]  (Heap: 0x3fa02) [CACHE MISS!]
                 +---> [Node Right] (Heap: 0x9be41) [CACHE MISS!]

Terkompilasi (Treelite Linear Instruction Array):
Memory Buffer Kontigu: [Reg0 > 1.25 ? Reg1 : Reg2][Reg3 > 0.5 ? Reg4 : Reg5]...
(Diproses langsung di CPU Cache L1/Register tanpa dereferensi pointer dinamis)
```

---

## 7. Implementasi Kode

Berikut adalah implementasi end-to-end yang mencakup:
1. Custom Scikit-learn Pipeline Transformer: Out-of-Fold Target Encoder yang kebal dari *leakage*.
2. Script Pelatihan LightGBM.
3. Kompilasi ke Native C Shared Library via Treelite.
4. Engine Evaluasi Inferensi Berkecepatan Tinggi.

### A. Custom Transformer: Out-of-Fold Target Encoder

Simpan pada file: `hands-on/m02/transformers.py`

```python
"""
Module: transformers.py
Deskripsi: Leakage-Free Out-of-Fold Target Encoder untuk produksi.
Mematuhi standar BaseEstimator dan TransformerMixin dari Scikit-Learn.
"""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.model_selection import KFold


class OutOfFoldTargetEncoder(BaseEstimator, TransformerMixin):
    """
    Target Encoder menggunakan validasi silang (K-Fold) saat fitting
    untuk mencegah target leakage pada data tabular berdimensi tinggi.
    Menerapkan smoothing empiris Bayesian (m-estimate).
    """

    def __init__(
        self,
        categorical_features: List[str],
        target_column: str,
        n_splits: int = 5,
        smooth: float = 10.0,
        random_state: int = 42,
    ) -> None:
        self.categorical_features = categorical_features
        self.target_column = target_column
        self.n_splits = n_splits
        self.smooth = smooth
        self.random_state = random_state
        self.global_mean_: float = 0.0
        self.encoding_maps_: Dict[str, Dict[str, float]] = {}

    def fit(self, X: pd.DataFrame, y: Optional[pd.Series] = None) -> "OutOfFoldTargetEncoder":
        """
        Menghitung mapping mean target per kategori secara global.
        Parameter y dapat diekstrak langsung jika digabungkan dalam X atau dioper terpisah.
        """
        if y is None:
            if self.target_column not in X.columns:
                raise ValueError(f"Kolom target {self.target_column} tidak ditemukan dalam input data.")
            y_series = X[self.target_column]
            X_in = X.drop(columns=[self.target_column])
        else:
            y_series = pd.Series(y) if not isinstance(y, pd.Series) else y
            X_in = X.copy()

        self.global_mean_ = float(y_series.mean())
        self.encoding_maps_ = {}

        for col in self.categorical_features:
            if col not in X_in.columns:
                raise KeyError(f"Fitur {col} tidak ada pada DataFrame.")

            # Perhitungan smoothing m-estimate: (count * mean + smooth * global_mean) / (count + smooth)
            stats = y_series.groupby(X_in[col]).agg(["count", "mean"])
            smoothed = (stats["count"] * stats["mean"] + self.smooth * self.global_mean_) / (
                stats["count"] + self.smooth
            )
            self.encoding_maps_[col] = smoothed.to_dict()

        return self

    def fit_transform(self, X: pd.DataFrame, y: Optional[pd.Series] = None) -> pd.DataFrame:
        """
        Menghitung encoding menggunakan K-Fold out-of-fold strategy
        khusus untuk data pelatihan untuk mencegah data target merembes ke fitur.
        """
        if y is None:
            if self.target_column not in X.columns:
                raise ValueError(f"Target {self.target_column} harus tersedia di X.")
            y_series = X[self.target_column]
            X_in = X.drop(columns=[self.target_column])
        else:
            y_series = pd.Series(y) if not isinstance(y, pd.Series) else y
            X_in = X.copy()

        self.global_mean_ = float(y_series.mean())
        self.encoding_maps_ = {}
        X_out = X_in.copy()

        # Inisialisasi kolom target encoding dengan NaN
        for col in self.categorical_features:
            X_out[f"{col}_encoded"] = np.nan

        kf = KFold(n_splits=self.n_splits, shuffle=True, random_state=self.random_state)

        for train_idx, val_idx in kf.split(X_in):
            X_tr, y_tr = X_in.iloc[train_idx], y_series.iloc[train_idx]
            X_va = X_in.iloc[val_idx]

            for col in self.categorical_features:
                stats = y_tr.groupby(X_tr[col]).agg(["count", "mean"])
                smoothed = (stats["count"] * stats["mean"] + self.smooth * self.global_mean_) / (
                    stats["count"] + self.smooth
                )
                mapping = smoothed.to_dict()
                X_out.iloc[val_idx, X_out.columns.get_loc(f"{col}_encoded")] = (
                    X_va[col].map(mapping).fillna(self.global_mean_)
                )

        # Simpan pemetaan global untuk inferensi masa depan
        for col in self.categorical_features:
            stats = y_series.groupby(X_in[col]).agg(["count", "mean"])
            smoothed = (stats["count"] * stats["mean"] + self.smooth * self.global_mean_) / (
                stats["count"] + self.smooth
            )
            self.encoding_maps_[col] = smoothed.to_dict()

        return X_out

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Menerapkan mapping global pada data inference (Test/Validation/Production).
        Nilai unseen categories otomatis diisi oleh global_mean_.
        """
        X_out = X.copy()
        for col in self.categorical_features:
            if col not in X_out.columns:
                raise KeyError(f"Fitur {col} hilang pada inference request.")
            encoded_col = f"{col}_encoded"
            mapping = self.encoding_maps_.get(col, {})
            X_out[encoded_col] = X_out[col].map(mapping).fillna(self.global_mean_)
        return X_out
```

### B. Pipeline Training & Native C Compilation Engine

Simpan pada file: `hands-on/m02/train_and_compile.py`

```python
"""
Module: train_and_compile.py
Deskripsi: Melatih model LightGBM dan mengompilasinya menjadi C Native Shared Library via Treelite.
"""

import os
import shutil
import subprocess
import lightgbm as lgb
import numpy as np
import pandas as pd
import treelite
import treelite_runtime
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split
from transformers import OutOfFoldTargetEncoder

ARTIFACT_DIR = "./artifact"
os.makedirs(ARTIFACT_DIR, exist_ok=True)

def generate_synthetic_data():
    """Membuat synthetic dataset dengan categorical dan continuous features."""
    X_num, y = make_classification(
        n_samples=100_000,
        n_features=10,
        n_informative=8,
        n_redundant=2,
        random_state=42
    )
    df = pd.DataFrame(X_num, columns=[f"num_{i}" for i in range(10)])
    
    # Tambahkan fitur kategorikal dengan kardinalitas beragam
    cities = ["Jakarta", "Surabaya", "Bandung", "Medan", "Semarang"]
    devices = ["iOS", "Android", "Web"]
    
    np.random.seed(42)
    df["city"] = np.random.choice(cities, size=len(df), p=[0.4, 0.2, 0.15, 0.15, 0.1])
    df["device"] = np.random.choice(devices, size=len(df), p=[0.3, 0.6, 0.1])
    df["target"] = y
    return df

def main():
    print("[1] Mempersiapkan data dan melakukan rekayasa fitur...")
    df = generate_synthetic_data()
    
    train_df, test_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df["target"])
    
    cat_cols = ["city", "device"]
    encoder = OutOfFoldTargetEncoder(categorical_features=cat_cols, target_column="target")
    
    # Fit & Transform Train Data (Leak-free)
    train_encoded = encoder.fit_transform(train_df)
    
    # Transform Test Data
    test_encoded = encoder.transform(test_df.drop(columns=["target"]))
    test_encoded["target"] = test_df["target"].values
    
    feature_cols = [f"num_{i}" for i in range(10)] + [f"{c}_encoded" for c in cat_cols]
    
    X_train = train_encoded[feature_cols].values.astype(np.float32)
    y_train = train_encoded["target"].values.astype(np.int32)
    X_test = test_encoded[feature_cols].values.astype(np.float32)
    y_test = test_encoded["target"].values.astype(np.int32)
    
    print("[2] Melatih model LightGBM dengan Histogram-based splitting...")
    train_data = lgb.Dataset(X_train, label=y_train, free_raw_data=False)
    
    params = {
        "objective": "binary",
        "metric": "binary_logloss",
        "boosting_type": "gbdt",
        "num_leaves": 31,
        "learning_rate": 0.05,
        "feature_fraction": 0.8,
        "verbose": -1,
        "n_jobs": 4
    }
    
    bst = lgb.train(params, train_data, num_boost_round=100)
    
    lgb_model_path = os.path.join(ARTIFACT_DIR, "model.txt")
    bst.save_model(lgb_model_path)
    print(f"Model LightGBM tersimpan di: {lgb_model_path}")
    
    print("[3] Mengompilasi model LightGBM ke C-Source Code menggunakan Treelite...")
    # Import model lgb ke Treelite
    tl_model = treelite.Model.load(lgb_model_path, model_format="lightgbm")
    
    # Generate source package (kode C)
    c_source_dir = os.path.join(ARTIFACT_DIR, "treelite_c_src")
    if os.path.exists(c_source_dir):
        shutil.rmtree(c_source_dir)
        
    tl_model.compile(
        dirpath=c_source_dir,
        params={"parallel_comp": 4, "quantize": 1},
        verbose=True
    )
    print(f"Kode C model ter-generate di folder: {c_source_dir}")
    
    print("[4] Melakukan kompilasi shared library (.so) menggunakan GCC...")
    shared_lib_path = os.path.join(ARTIFACT_DIR, "model_compiled.so")
    
    # Jalankan gcc untuk mengompilasi kode C Treelite menjadi native .so
    compile_cmd = [
        "gcc", "-O3", "-shared", "-fPIC", "-std=c99",
        f"-I{c_source_dir}",
        "-o", shared_lib_path
    ]
    
    # Ambil semua file .c yang di-generate
    c_files = [os.path.join(c_source_dir, f) for f in os.listdir(c_source_dir) if f.endswith(".c")]
    compile_cmd.extend(c_files)
    
    res = subprocess.run(compile_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Gagal mengompilasi library C:\n{res.stderr}")
        
    print(f"SUKSES: Shared library C berhasil di-generate di: {shared_lib_path}")
    
    # Validasi Parity Hasil Prediksi
    print("[5] Memvalidasi paritas output antara LightGBM Python API vs Treelite Shared Lib...")
    sample_batch = X_test[:1000]
    
    # Prediksi LightGBM
    preds_lgb = bst.predict(sample_batch)
    
    # Prediksi Treelite Engine
    predictor = treelite_runtime.Predictor(shared_lib_path, nthread=1)
    dmat = treelite_runtime.DMatrix(sample_batch)
    preds_tl = predictor.predict(dmat)
    
    # Flatten array jika bentuknya 2D
    preds_tl = preds_tl.flatten()
    
    # Ukur mean squared deviation
    diff = np.max(np.abs(preds_lgb - preds_tl))
    print(f"Maksimum Deviasi Numerik Antara Implementasi: {diff:.8e}")
    assert diff < 1e-5, "Gawat: Terjadi deviasi numerik signifikan antara LightGBM dan Treelite C Engine!"
    print("Validasi Paritas: LOLOS (Identik secara matematis).")

if __name__ == "__main__":
    main()
```

### C. Low-Latency Serving API Engine

Simpan pada file: `hands-on/m02/server.py`

```python
"""
Module: server.py
Deskripsi: High-Performance Inference Server menggunakan FastAPI dan Treelite Runtime.
Mendukung feature ingestion dan zero-copy matrix initialization.
"""

import os
import time
from typing import List
import numpy as np
import treelite_runtime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

SHARED_LIB_PATH = "./artifact/model_compiled.so"

if not os.path.exists(SHARED_LIB_PATH):
    raise FileNotFoundError(f"Shared library {SHARED_LIB_PATH} tidak ditemukan. Jalankan train_and_compile.py terlebih dahulu.")

# Inisialisasi Treelite Engine secara Singleton saat startup
predictor = treelite_runtime.Predictor(SHARED_LIB_PATH, nthread=4)

app = FastAPI(
    title="Ultra-Low-Latency Tree Inference API",
    description="Engine inferensi model ensemble terkompilasi native C.",
    version="1.0.0"
)

class InferenceRequest(BaseModel):
    # Representasi vektor 12 fitur (10 numerik + 2 encoded categoricals)
    features: List[List[float]] = Field(
        ..., 
        example=[[0.1, -1.2, 0.45, 1.1, -0.3, 0.0, 0.8, -0.2, 1.5, -0.9, 0.48, 0.52]]
    )

class InferenceResponse(BaseModel):
    predictions: List[float]
    latency_microseconds: float
    throughput_qps: float

@app.post("/predict", response_model=InferenceResponse)
async def predict_batch(payload: InferenceRequest):
    t_start = time.perf_counter_ns()
    
    try:
        # Konversi payload langsung ke Contiguous C-Order Numpy Array (float32)
        matrix_input = np.ascontiguousarray(payload.features, dtype=np.float32)
        
        if matrix_input.shape[1] != 12:
            raise HTTPException(
                status_code=400, 
                detail=f"Ekspektasi fitur adalah 12, diterima {matrix_input.shape[1]}."
            )
            
        # Bentuk low-overhead memory wrapper Treelite
        dmat = treelite_runtime.DMatrix(matrix_input)
        raw_predictions = predictor.predict(dmat)
        
        # Format flattened output
        scores = raw_predictions.flatten().tolist()
        
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
        
    t_end = time.perf_counter_ns()
    latency_us = (t_end - t_start) / 1000.0
    latency_sec = latency_us / 1e6
    throughput = len(payload.features) / latency_sec if latency_sec > 0 else 0.0

    return InferenceResponse(
        predictions=scores,
        latency_microseconds=latency_us,
        throughput_qps=throughput
    )

@app.get("/health")
def healthcheck():
    return {"status": "ONLINE", "runtime": "Treelite-C-Native"}
```

---

## 8. Real World Case Study: Arsitektur Deteksi Fraud FinTech Skala 35.000 TPS

### Konteks Bisnis
Sebuah bank digital memproses hingga **35.000 transaksi pembayaran per detik (TPS)** pada jam sibuk. Regulasi kepatuhan mewajibkan evaluasi risiko fraud diselesaikan dalam alokasi SLA jaringan maksimal **15 milidetik**. Model yang digunakan adalah ensemble 300 pohon keputusan dengan kedalaman maksimal 8.

```
Incoming Card Transaction
           | (JSON Payload)
           v
[API Gateway: Envoy Proxy]
           |
           +-------------------------------------------------------+
           | Parallel Feature Request                              |
           v                                                       v
[In-Memory Redis Cluster]                               [Payload Feature Extraction]
(Ambil 128 Profil Fitur:                                (Ekstrak 16 Fitur Transaksi:
 Rata-rata trx 1 jam, IP velocity)                       nominal, geolokasi, merchant)
           |                                                       |
           +---------------------------+---------------------------+
                                       |
                                       v Hydration via Shared C-Memory
                       [Go / C++ Application Worker]
                                       |
                                       v Invocation via FFI
                      [Treelite Native Shared Library]
                                       |
                                       v Scoring (< 1.8 ms)
                               [Risk Score: 0.892]
                                       |
                                       +---> [Action: BLOCK TRANSACTION]
                                       |
                                       v Zero-Drop Event Logging
                       [Kafka Stream: topic-model-telemetry]
                                       |
                                       v Windowing
                         [Evidently / PSI Monitor Engine]
```

### Bottleneck yang Ditemukan pada Arsitektur Generasi Pertama (V1)
- Model disajikan via Flask + standard Scikit-Learn API wrapper.
- Latensi per request $p95 = 48\text{ ms}$, $p99 = 112\text{ ms}$.
- Sistem sering mengalami kegagalan *cascading timeout* akibat mekanisme Python GIL ketika volume request melonjak.

### Solusi Arsitektur Produksi (V2)
1. **Model Compilation:** Model LightGBM dikompilasi menggunakan Treelite dan di-*link* secara native ke microservice inferensi via FFI (*Foreign Function Interface*).
2. **Network Feature Hydration:** Fitur profil pengguna dikompresi menggunakan representasi MessagePack dan disimpan dalam memori RAM Redis Cluster. Latensi pembacaan fitur dibatasi maksimal $3\text{ ms}$ menggunakan *pipelined MGET*.
3. **Hasil Performa:** Latensi evaluasi model murni turun dari $22\text{ ms}$ menjadi **$0.8\text{ ms}$** pada mesin 8-core CPU. Latensi end-to-end $p99$ berhasil ditekan ke angka **$6.4\text{ ms}$**, dengan kemampuan menyerap *peak traffic* hingga 40.000 TPS secara konsisten.

---

## 9. Trade-offs

Setiap keputusan arsitektur sistem ML melibatkan kompromi teknis yang harus dipertimbangkan secara matang:

| Pendekatan Arsitektur | Keuntungan | Biaya / Trade-off |
| :--- | :--- | :--- |
| **Treelite Native Compiled Library (`.so`)** | Kecepatan inferensi maksimal; SIMD CPU optimization; independen dari runtime Python | Proses deployment CI/CD lebih kompleks; ukuran artefak biner membengkak secara eksponensial seiring kedalaman pohon |
| **Histogram Bins Rendah ($K = 64$)** | Penggunaan cache CPU optimal; kecepatan training meningkat hingga 3x lipat | Sedikit degradasi presisi split pada fitur kontinu yang memiliki ekor distribusi panjang (*fat-tailed distribution*) |
| **Out-of-Fold Target Encoding** | Menghilangkan kebocoran data (*zero target leakage*); mampu menangani kardinalitas ekstrem | Waktu komputasi training meningkat linear dengan faktor $K$-Splits; kompleksitas tracking artefak encoder |
| **Online Feature Store (Redis In-Memory)** | Latensi baca sub-milidetik ($< 2\text{ ms}$) via clustered keyspace | Biaya infrastruktur RAM sangat tinggi dibandingkan disk-based database; butuh sinkronisasi data kontinu dari offline lakehouse |

---

## 10. Common Mistakes & Troubleshooting

### 1. Data Leakage pada Target Encoding
* **Gejala:** Metrik ROC-AUC pada data cross-validation mencapai `0.99`, namun performa anjlok ke `0.65` di lingkungan produksi.
* **Akar Masalah:** Fungsi `fit_transform()` dieksekusi secara serentak ke seluruh dataset sebelum pemisahan train/test, atau transformasi dilakukan tanpa mekanisme cross-validation (*out-of-fold*).
* **Solusi:** Gunakan selalu isolasi strict fold menggunakan modul seperti `OutOfFoldTargetEncoder` di atas. Jangan pernah membiarkan data target fold evaluasi terbaca saat menghitung rerata grup kategori.

### 2. Mismatch Format/Tipe Data Fitur (*Silent Casting*)
* **Gejala:** Model inferensi memberikan skor probabilitas seragam atau performa tidak menentu, tanpa mengeluarkan pesan galat sistem.
* **Akar Masalah:** Perbedaan susunan (*ordering*) kolom matriks antara saat fitting dan transform, atau konversi nilai float implisit ke int yang menyebabkan pembulatan data presisi tinggi.
* **Solusi:** Terapkan skema kontrak data yang ketat. Kunci urutan fitur secara eksplisit dalam kode dan validasi representasi biner input (`float32` vs `float64`) menggunakan Pydantic/Numpy assertion:
  ```python
  assert matrix.dtype == np.float32, "Input matrix harus memiliki tipe float32"
  ```

### 3. Binary Bloat & Memory Faults pada Model Terkompilasi
* **Gejala:** Compiler GCC mengalami kegagalan *out-of-memory* (OOM) atau *segmentation fault* saat mengompilasi model Treelite dengan jumlah pohon $> 2.000$ dan kedalaman $> 12$.
* **Akar Masalah:** File source code C yang dihasilkan Treelite menghasilkan satu fungsi logika tunggal yang terlalu masif, melebihi batas instruksi lompatan (*branch instruction limit*) compiler.
* **Solusi:** Aktifkan parameter `parallel_comp` pada Treelite untuk memecah pohon ke dalam beberapa modul file C yang lebih kecil, serta batasi kompleksitas pohon pelatihan (`max_depth <= 8`, `num_leaves <= 63`).

---

## 11. Best Practices (Production Checklist)

- [ ] **Deterministik & Reusable Transformer:** Semua pipeline transformasi disimpan sebagai satu kesatuan artefak terversi (*serialized model object*) bersama model inferensi.
- [ ] **Pengecekan Keselarasan Paritas:** Jalankan test keselarasan otomatis minimal 10.000 sampel data antara API Python standar dan engine terkompilasi (Treelite/ONNX). Deviasi maksimal yang diizinkan adalah $|y_{\text{lgb}} - y_{\text{compiled}}| < 10^{-5}$.
- [ ] **Validasi Skema Zero-Tolerance:** Skema input diverifikasi di layer gateway menggunakan representasi tipe data biner.
- [ ] **Penyimpanan State Encoder Statis:** Nilai agregasi historis disimpan dalam dictionary global yang kebal terhadap missing key (*default fallback ke global prior*).
- [ ] **Automated Fallback Engine:** Sediakan jalur inferensi cadangan (*shadow python runtime*) jika shared library C mengalami crash tak terduga (*memory corruption protection*).
- [ ] **Sliding-Window Drift Instrumentation:** Pasang *telemetry interceptor* untuk mengukur skor PSI dan uji statistik KS secara berkala setiap batch inferensi mencapai ukuran sampel yang ditentukan.

---

## 12. Hands-on Practice

Lakukan langkah-langkah praktikum berikut untuk menguji performa inferensi langsung di mesin Anda.

### Persiapan Direktori & Dependensi
```bash
mkdir -p hands-on/m02/artifact
cd hands-on/m02
python3 -m venv venv
source venv/bin/activate

# Instalasi paket esensial
pip install lightgbm==4.3.0 treelite==4.3.0 treelite-runtime==4.3.0 \
            scikit-learn==1.4.2 pandas==2.2.2 fastapi==0.110.0 \
            uvicorn==0.29.0 httpx==0.27.0
```

### Langkah 1: Jalankan Pelatihan dan Kompilasi
Simpan script `transformers.py` dan `train_and_compile.py` yang tertera pada Seksi 7, kemudian eksekusi:
```bash
python train_and_compile.py
```
*Output yang diharapkan:* Muncul berkas `model.txt`, folder source code C, dan biner `model_compiled.so` di dalam direktori `artifact/`.

### Langkah 2: Jalankan Inference Microservice
Simpan script `server.py` pada Seksi 7, lalu jalankan microservice menggunakan Uvicorn:
```bash
uvicorn server:app --host 0.0.0.0 --port 8000 --workers 2
```

### Langkah 3: Benchmark Performa Latensi & Throughput
Buka terminal baru, buat skrip benchmark sederhana `benchmark.py`:

```python
# hands-on/m02/benchmark.py
import time
import httpx
import numpy as np

# Siapkan 500 baris payload simulasi
np.random.seed(1337)
simulated_batch = np.random.randn(500, 12).astype(float).tolist()

payload = {"features": simulated_batch}

print("Memulai stress testing...")
latencies = []

with httpx.Client(base_url="http://localhost:8000") as client:
    # Warmup
    for _ in range(10):
        client.post("/predict", json=payload)
        
    # Execution
    for _ in range(100):
        t0 = time.perf_counter()
        resp = client.post("/predict", json=payload)
        t1 = time.perf_counter()
        assert resp.status_code == 200
        latencies.append((t1 - t0) * 1000.0) # Milidetik

print(f"Hasil Benchmark Batch 500 Baris (100 Iterasi):")
print(f"Latency Mean : {np.mean(latencies):.2f} ms")
print(f"Latency P50  : {np.percentile(latencies, 50):.2f} ms")
print(f"Latency P99  : {np.percentile(latencies, 99):.2f} ms")
```

Jalankan pengujian:
```bash
python benchmark.py
```

---

## 13. Exercise

### Level Easy
Modifikasi transformer `OutOfFoldTargetEncoder` di `transformers.py` agar mampu menerima parameter `fill_value_strategy` yang menyediakan opsi fallback: menggunakan `global_mean` atau menggunakan nilai `median` dari target. Uji coba fungsionalitasnya dengan unit test berbasis `pytest`.

### Level Medium
Bangun sistem deteksi drift menggunakan metode metrik **Population Stability Index (PSI)**. Buatlah script `drift_detector.py` yang membaca dua array Numpy: data baseline pelatihan dan data batch inferensi produksi. Sistem harus menghasilkan status peringatan otomatis:
- $\text{PSI} < 0.1$: Stabil (Tidak ada aksi)
- $0.1 \le \text{PSI} \le 0.2$: Pergeseran Moderat (Kirim peringatan Slack/Log)
- $\text{PSI} > 0.2$: Pergeseran Signifikan (Trigger retrain model)

### Level Hard
Kembangkan custom ONNX pipeline export yang mengemas `Scikit-Learn Standard Scaler` dan `XGBoost Classifier` ke dalam satu graph file terintegrasi `model.onnx`. Eksekusi inferensi menggunakan engine `onnxruntime` dan buktikan bahwa tidak ada transisi data ke runtime Python antar tahap ekstraksi fitur hingga kalkulasi probabilitas akhir.

---

## 14. Challenge: Sub-5ms Fraud Detection Engine Under Flash Sale Traffic

### Deskripsi Masalah
Platform e-commerce Anda akan melangsungkan kampanye promo kilat (*Flash Sale*). Pola transaksi pada periode ini menunjukkan anomali masif: volume transaksi melonjak 20 kali lipat, namun rasio perilaku belanja (*buyer behavior*) bergeser secara radikal (frekuensi checkout per menit melesat, metode pembayaran terpusat pada satu payment gateway).

### Instruksi Penugasan
Rancang arsitektur sistem inferensi yang mampu:
1. Menjaga latensi inferensi SLA $p99 < 5\text{ ms}$ pada throughput $50.000\text{ TPS}$.
2. Mengintegrasikan mekanisme dynamic fall-back: jika antrean fitur real-time di Redis terhambat (latensi fetch $> 2\text{ ms}$), sistem inferensi secara adaptif beralih ke model berbasis *lightweight offline imputation* tanpa memutus request.
3. Mendeteksi pergeseran distribusi fitur *transaction_amount* secara streaming menggunakan algoritma *Kolmogorov-Smirnov Test* berbasis sliding window berukuran 10.000 sampel data.
4. Tuliskan analisis arsitektur teknis Anda dalam format markdown dokumen spesifikasi sistem rekayasa perangkat lunak produksi lengkap dengan diagram komponen dan mitigasi resiko kegagalan sistem.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)
1. Apa keunggulan fundamental metode *Histogram-based Splitting* dibandingkan *Exact Greedy* pada model pohon boosting?
   - A. Menghasilkan tree dengan kedalaman yang tak terbatas.
   - B. Mengurangi kompleksitas waktu pencarian split dari sorting kontinu $\mathcal{O}(d \cdot n \log n)$ menjadi $\mathcal{O}(d \cdot n)$ melalui pengelompokan bin diskret.
   - C. Menghilangkan kebutuhan untuk melakukan proses evaluasi gradien tingkat kedua.
   - D. Memastikan model tidak pernah mengalami overfitting pada data tabular.

2. Mengapa target encoding naif (menghitung mean target secara global langsung pada seluruh dataset) dilarang dalam rekayasa fitur produksi?
   - A. Menghabiskan kapasitas memori secara berlebihan.
   - B. Menyebabkan inferensi berjalan lambat pada CPU.
   - C. Mengakibatkan *Target Leakage* yang memberikan estimasi performa optimis palsu saat validasi.
   - D. Menghasilkan representasi kategori bernilai floating point ganda.

3. Apa penyebab utama tingginya latensi inferensi saat mengevaluasi model ensemble pohon besar menggunakan interpretor Python native?
   - A. Resolusi waktu CPU yang tidak sinkron.
   - B. Masalah *cache miss* CPU akibat dereferensi pointer dinamis secara acak serta overhead runtime interpreter.
   - C. Algoritma pohon tidak dapat diproses secara paralel.
   - D. File model selalu dimuat ulang dari hard disk setiap kali fungsi predict dipanggil.

4. Bagaimana cara kerja optimasi kompilasi Treelite pada model pohon keputusan?
   - A. Mengonversi struktur pohon menjadi deep neural network.
   - B. Mengompresi file model menggunakan algoritma GZIP.
   - C. Mengompilasi alur keputusan hierarkis menjadi instruksi biner C terstruktur datar (*flat instruction*) dengan memanfaatkan vektorisasi SIMD.
   - D. Mengubah semua data kontinu menjadi representasi integer 8-bit secara permanen.

5. Dalam monitoring stabilitas model, nilai Population Stability Index (PSI) sebesar 0.25 mengindikasikan:
   - A. Distribusi data sangat stabil dan tidak membutuhkan tindakan apapun.
   - B. Terjadi pergeseran populasi yang signifikan (*Significant Drift*) yang mengharuskan retraining atau investigasi model.
   - C. Akurasi model meningkat secara otomatis.
   - D. Model kehilangan kemampuan untuk memproses matriks sparse.

### Bagian 2: Intermediate (Analisis Singkat)
1. Jelaskan bagaimana mekanisme GOSS (*Gradient-based One-Side Sampling*) pada LightGBM menentukan data sampel mana yang dipertahankan dan mana yang dibuang saat komputasi kalkulasi gradien split!
2. Terangkan perbedaan mendasar fungsionalitas antara *Online Feature Store* dan *Offline Feature Store* dalam arsitektur Machine Learning enterprise!
3. Mengapa kompilasi model berbasis pohon dengan Treelite terkadang memicu kegagalan kompilasi C compiler saat nilai parameter `max_depth` disetel terlalu tinggi ($> 15$)?
4. Jelaskan mengapa metrik *Kolmogorov-Smirnov (KS) Test* lebih dipilih untuk mendeteksi drift pada fitur numerik kontinu dibandingkan menggunakan uji *Chi-Square*!
5. Bagaimana prinsip isolasi matematika *m-estimate smoothing* pada target encoder mencegah bias observasi pada kategori yang memiliki kemunculan data sangat langka (*rare categories*)?

### Bagian 3: Skenario Kasus Produksi
1. **Analisis Akar Masalah (Root Cause Analysis):**  
   Tim data science meluncurkan model LightGBM baru ke staging environment. Seluruh payload pengujian berhasil dieksekusi dengan benar. Namun, saat diarahkan ke traffic produksi 10%, utilisasi memori (RAM) pada container serving mendadak naik drastis dari 400MB ke 14GB dalam kurun waktu 15 menit, hingga container terminated (OOMKilled).  
   *Pertanyaan:* Berdasarkan karakteristik dynamic matrix allocation dan scoping di Scikit-Learn/Pandas/C-API, analisislah kemungkinan sumber kebocoran memori (*memory leak*) tersebut dan rancang solusinya!

2. **Mitigasi Cold-Start Feature Store:**  
   Layanan inferensi real-time bergantung pada fitur agregasi 30-hari dari Redis. Jika terjadi insiden Redis Cluster failure dan failover node baru aktif tanpa cold-data hydration, latensi transaksi melonjak tajam karena aplikasi fallback querying ke relational database analytics.  
   *Pertanyaan:* Rancang skema mitigasi arsitektur lapis ganda (*multi-tier resilience*) agar sistem inferensi tetap mampu melayani transaksi di bawah 10ms tanpa membebani primary transactional database!

3. **Silent Failure Mode Detection:**  
   Model scoring kredit menghasilkan prediksi normal tanpa error code (HTTP 200 OK), dengan rata-rata probabilitas default stabil pada angka 0.05. Namun, seminggu kemudian ditemukan bahwa data pipeline dari rekanan pihak ketiga mengalami perubahan format timestamp yang menyebabkan semua input fitur deret waktu diisi oleh nilai default `0.0`.  
   *Pertanyaan:* Mengapa drift detector berbasis output prediksi (*target prediction drift*) gagal menangkap insiden ini, dan rancang sistem observabilitas komprehensif apa yang seharusnya dipasang untuk mendeteksi kegagalan data input secara instan (*input-data drift*)!

---

## Kunci Jawaban & Panduan Evaluasi

### Bagian 1: Basic
1. **B** — Histogram memetakan nilai kontinu ke dalam $K$ bins diskret, memangkas waktu kalkulasi split secara signifikan.
2. **C** — Target encoding naif membocorkan label target ke dalam matriks fitur, menyebabkan estimasi validasi overoptimistis (*leakage*).
3. **B** — Pointer chasing pada heap memory menimbulkan CPU cache thrashing dan branch misprediction.
4. **C** — Treelite mengonversi logika percabangan kondisional pohon menjadi instruksi C flat native berkecepatan tinggi.
5. **B** — Aturan umum PSI: $\ge 0.2$ menunjukkan pergeseran populasi signifikan (*significant shift*).

### Bagian 2: Intermediate
1. **Mekanisme GOSS:** GOSS mengurutkan sampel berdasarkan nilai absolut gradiennya. Mengambil $a \times 100\%$ data dengan gradien terbesar (error tinggi), dan mengambil sampel acak sebesar $b \times 100\%$ dari data bergradien kecil. Gradien dari data kecil tersebut dikalikan faktor skala $\frac{1-a}{b}$ untuk menjaga distribusi estimasi gradien total tetap tidak bias (*unbiased*).
2. **Online vs Offline Feature Store:** Offline store berfokus pada volume tinggi, eksekusi query analitik masif (*point-in-time join* historis), dan toleran terhadap latensi tinggi (DuckDB/Parquet/BigQuery). Online store dioptimalkan untuk pembacaan acak tingkat tinggi (*random key-value read*) dengan latensi sub-milidetik per item untuk kebutuhan hidrasi inferensi real-time (Redis/DynamoDB).
3. **Penyebab Gagal Kompilasi Treelite:** Pohon yang sangat dalam menghasilkan pohon keputusan dengan node berjumlah eksponensial ($2^{\text{depth}}$). Hal ini menyebabkan ukuran fungsi bahasa C membengkak menjadi jutaan baris kode kondisional dalam satu blok fungsi yang melampaui alokasi batas memori internal compiler dalam menangani *Abstract Syntax Tree* (AST) serta batas offset instruksi instruksi assembler jump (`jmp`).
4. **KS-Test vs Chi-Square:** KS-Test adalah pengujian non-parametrik yang didesain secara khusus untuk distribusi kontinu dengan mengevaluasi deviasi absolut maksimum pada *Empirical Cumulative Distribution Functions* (ECDF). Sedangkan Chi-Square mengharuskan proses diskretisasi/binning artifisial yang rentan mengaburkan karakteristik bentuk kontinu ekor distribusi.
5. **Prinsip M-Estimate Smoothing:** Menggabungkan rata-rata target grup lokal dengan rata-rata target global (*prior*) yang dikontrol parameter regularisasi bobot $m$. Jika kemunculan data kategori sedikit ($count \approx 0$), rumus didominasi oleh nilai global prior. Seiring bertambahnya data sampel kategori tersebut, pengaruh nilai lokal secara bertahap mengambil alih.

### Bagian 3: Skenario Kasus Produksi
1. **Akar Masalah OOM & Solusi:**
   * *Akar Masalah:* Akumulasi pembentukan objek DataFrame Pandas atau array Numpy di dalam scope endpoint loop tanpa dereferensi pembersihan memori, atau penggunaan C-wrapper (seperti pembentukan struct DMatrix pada Treelite/XGBoost) tanpa pemanggilan fungsi destruktor memory native (`treelite_runtime.DMatrix.free` atau `del dmat`). Hal ini menyebabkan alokasi heap memori internal C++ tidak dikembalikan ke sistem operasi (bypassing Python Garbage Collector).
   * *Solusi:* Lakukan instansiasi memori secara pre-allocated buffer atau reusable memory array, pastikan memori dibungkus dalam *context manager*, dan trigger manual dereference atau gunakan C-FFI zero-copy buffer view langsung dari stream raw bytes request.
2. **Mitigasi Resilience Feature Store:**
   * Terapkan strategi arsitektur **Local In-Memory Cache Tier** (L1 Cache menggunakan LRU Cache berbasis Shared Memory seperti Apache Arrow Plasma atau memory map di dalam worker process inference) yang menyimpan nilai profil fitur paling aktif (Top 10%).
   * Gunakan format statis *Embedded Default Profiles* jika cache L1 dan Redis L2 miss, yang mengembalikan rata-rata statistik agregasi global segmen pengguna tersebut tanpa melakukan *live querying* ke database analitik historis.
3. **Observabilitas Silent Failure:**
   * *Akar Masalah:* Nilai prediksi agregat bisa tampak normal jika output model secara agregat kebetulan menghasilkan baseline score rata-rata akibat input terimputasi nilai statis nol. Monitoring output (*Prediction Drift*) tidak melihat deviasi jika probabilitas rata-rata populasi secara kebetulan mirip dengan prior probability training baseline.
   * *Solusi Arsitektur:* Observabilitas wajib mencakup **Dual-Axis Monitoring**:
     1. Monitor statistik input secara granular (*Input Feature Drift*) menggunakan uji KS per fitur numerik kontinu dan Jensen-Shannon Divergence pada fitur kategorikal.
     2. Monitor **Feature Completeness Metric** (rasio persentase nilai null/default zero) pada payload sebelum masuk ke model serving via Prometheus metrics exporter. Alarm otomatis akan berbunyi seketika metrik *zero-imputation rate* pada fitur deret waktu melebihi ambang batas toleransi (misal: $> 5\%$).

---

## 16. Summary

Mengembangkan sistem Machine Learning berstandar *enterprise* menuntut pergeseran paradigma dari sekadar eksplorasi pemodelan statistika menjadi perancangan arsitektur rekayasa perangkat lunak berkinerja tinggi. 

Penerapan *Histogram-based GBDT* yang dikombinasikan dengan teknik pra-pemrosesan yang bebas dari kebocoran data (*Leak-Free Transformers*) memberikan fondasi estimasi prediktif yang kuat. Melalui kompilasi native biner (*Treelite C Shared Library Compilation*), latensi komputasi inferensi pohon keputusan dapat ditekan hingga sub-milidetik, mengeliminasi bottleneck struktural pada interpreter Python standar. 

Sistem produksi modern harus ditopang oleh keandalan infrastruktur hidrasi data lapis ganda (*Dual-Layer Feature Store*) serta mesin observabilitas berkelanjutan yang memonitor divergensi statistik secara streaming. Dengan menyatukan optimasi komputasi tingkat rendah, validasi data deterministik, dan instrumentasi drift real-time, sistem ML dapat beroperasi secara tangguh (*resilient*), terukur (*scalable*), dan konsisten dalam memproses beban kerja intensif enterprise.
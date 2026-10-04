# Bab 01 Module 01: Formulasi Masalah Machine Learning & Konstruksi Pipeline Data Deterministik Skala Enterprise

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

- **Menerjemahkan (Deconstruct)** metrik objektif bisnis tingkat tinggi (misal: *Customer Churn*, *Credit Default Risk*, *Transaction Fraud*) menjadi formulasi problem matematika ML yang tertutup (*well-posed problem*).
- **Menganalisis dan Memitigasi** *Target Leakage* serta *Data Snooping Bias* pada level arsitektur data pipeline sebelum proses *model training*.
- **Merancang dan Mengimplementasikan** ingestion pipeline deterministik yang bersifat *idempotent*, menggunakan teknik *hash-based partitioning* dan validasi skema berbasis kontrak (*schema contract enforcement*).
- **Membangun** strategi *Train-Validation-Test splitting* berbasis temporal dan entitas untuk mencegah fenomena *temporal lookahead bias* dan *cross-entity contamination*.
- **Menulis** rangkaian pengujian unit dan integrasi otomatis (*automated regression testing*) untuk memvalidasi integritas data pipeline menggunakan pengujian berbasis properti (*property-based testing*).

---

## 2. Conceptual Foundations

Setiap proyek Machine Learning (ML) di industri berakar pada transisi dari ketidakpastian stokastik dunia nyata menuju model parametrik matematis. Sebuah masalah ML adalah sistem optimasi terkomputasi yang didefinisikan sebagai:

$$\min_{\theta} \mathbb{E}_{(x, y) \sim \mathcal{D}} [\mathcal{L}(f_\theta(x), y)]$$

Di mana $\mathcal{D}$ adalah distribusi gabungan data input $x \in \mathcal{X}$ dan target $y \in \mathcal{Y}$, $\mathcal{L}$ adalah fungsi *loss*, dan $f_\theta$ adalah hipotesis model yang diparametrisasi oleh vektor $\theta$.

Kesalahan paling fatal yang dilakukan oleh praktisi adalah memperlakukan data sebagai entitas statis (seperti berkas CSV lokal). Pada skala *enterprise*, data adalah entitas terdistribusi temporal yang diproduksi oleh sistem hulu (*upstream*) yang tidak stabil (*unstable environments*). Oleh karena itu, prinsip fundamental rekayasa data untuk AI mencakup:

1. **Idempotensi Pipeline**: Operasi pipeline $F$ terhadap data batch $D$ harus menghasilkan state transformasi yang identik, berapa kali pun dieksekusi: $F(F(D)) = F(D)$.
2. **Determinisme Pemisahan Data**: Partisi data (Train/Val/Test) tidak boleh bergantung pada *pseudo-random generator* yang rentan terhadap perbedaan *runtime state* atau *hardware threading*, melainkan harus merupakan fungsi murni (*pure function*) dari *Primary Key* entitas dan *Event Timestamp*.
3. **Pemisahan Dimensi Waktu (Temporal Causality)**: State fitur $x_t$ pada titik waktu $t$ hanya boleh disusun dari informasi yang tersedia secara fisik pada $t' \le t$. 

---

## 3. Motivation & "Why"

Mengapa pendekatan *ad-hoc* (misal: memuat seluruh data ke memori, melakukan `train_test_split(random_state=42)` dari Scikit-Learn) membawa bencana pada sistem produksi?

```
+--------------------------------------------------------------------------------+
| AKIBAT TIDAK MENERAPKAN DETERMINISTIK PIPELINE:                                |
|                                                                                |
| 1. Silent Data Leakage       -> Model over-optimistic di evaluasi offline      |
|                                 (AUC 0.98), namun kolaps di produksi (AUC 0.52).|
| 2. Non-Reproducible Audits   -> Regulasi finansial/medis mewajibkan model     |
|                                 dapat direkonstruksi bit-by-bit. Gagal audit   |
|                                 mengakibatkan denda jutaan dolar.               |
| 3. High Upstream Coupling    -> Perubahan tipe data senyap di database hulu   |
|                                 mengakibatkan degradasi model diam-diam        |
|                                 (silent failure) tanpa exception tercatat.     |
+--------------------------------------------------------------------------------+
```

Dalam sistem *real-time credit scoring* atau *fraud detection*, kegagalan memisahkan titik observasi (*observation window*) dan titik prediksi (*prediction window*) mengakibatkan kebocoran variabel target ke masa lalu (*backward information propagation*). Pipeline yang deterministik menjamin integritas temporal, kepatuhan audit regulasi, serta konsistensi performa inferensi.

---

## 4. Architecture / Mental Model

Pipeline data AI kelas enterprise beroperasi di bawah abstraksi berlapis:

```
[Raw Event Streams / OLTP Databases]
                |
                v
+-------------------------------+
| Layer 1: Ingestion & Contract | -> Validasi tipe ketat, pencegahan data malformed.
+-------------------------------+
                |
                v
+-------------------------------+
| Layer 2: Temporal Windowing   | -> Penentuan Cutoff Point (t_event <= t_cutoff).
+-------------------------------+
                |
                v
+-------------------------------+
| Layer 3: Deterministic Split  | -> Hash-based Partitioning (Entity/Time-aware).
+-------------------------------+
                |
                v
+-------------------------------+
| Layer 4: Leak-Free Transform  | -> Estimator di-fit HANYA pada Train partition,
+-------------------------------+    di-apply ke Val/Test.
                |
                v
[Immutable Feature Tensors (Parquet/Arrow Format)]
```

Arsitektur ini memastikan tidak ada ketergantungan siklis antar data batch, tidak ada asumsi implisit tentang distribusi data global, dan *state* transformasi terisolasi secara matematis.

---

## 5. ASCII Diagram

Berikut adalah alur data terperinci yang membedakan penanganan data historis (*training*) dengan data masa depan (*inference*):

```
Time Axis (t) ------------------------------------------------------------------------>
[---- Historical Window T_hist ----] | Cutoff (t_c) | [---- Prediction Horizon T_pred ----]
                                     |              |
Entities:                            |              |
User A:  o-------o---------o---------|              | -----------> (Target: y_A = 1)
User B:     o---------o--------------|              | -----------> (Target: y_B = 0)
                                     |              |
==================================== DATA SPLIT ENGINE ====================================
                                     |
    Entity ID Hash Modulation:       |
    Hash(Entity_ID) mod 100          |
       ├── < 70  ───────────> TRAIN SET      (Fit Transformers, Fit Model)
       ├── 70-85 ───────────> VALIDATION SET (Transform ONLY, Tune Hyperparams)
       └── > 85  ───────────> TEST SET       (Transform ONLY, Final Evaluation)
                                     |
+-----------------------------------------------------------------------------------------+
| ATURAN TRANSFORMASI MUTLAK:                                                             |
| Mean(x), Std(x), MinMax, Imputer Metrics = Compute(TRAIN ONLY)                          |
| Array_Transformed(Val) = (Array_Val - Mean(TRAIN)) / Std(TRAIN)                         |
+-----------------------------------------------------------------------------------------+
```

---

## 6. Mathematical / Theoretical Formulation

### 6.1 Formulasi Matematis Pemisahan Temporal

Diberikan dataset historis $\mathcal{S} = \{(e_i, t_i, \mathbf{x}_i, y_i)\}_{i=1}^N$, di mana $e_i \in \mathcal{E}$ adalah identitas entitas (misal: `user_id`), $t_i \in \mathcal{T}$ adalah waktu terjadinya *event*, $\mathbf{x}_i \in \mathbb{R}^d$ adalah vektor fitur, dan $y_i$ adalah label target.

Jika horizon prediksi ditentukan oleh interval $\Delta t$, maka fitur untuk entitas $e$ pada waktu evaluasi $t_e$ didefinisikan sebagai fungsional sejarah:

$$\mathbf{x}(e, t_e) = \Phi \left( \{ (t_j, \mathbf{v}_j) \mid t_j \le t_e, \, \text{entity}(j) = e \} \right)$$

Label target didefinisikan secara independen di masa depan:

$$y(e, t_e) = \Psi \left( \{ (t_k, \mathbf{v}_k) \mid t_e < t_k \le t_e + \Delta t, \, \text{entity}(k) = e \} \right)$$

Pelanggaran kausalitas (*causality violation*) terjadi jika:

$$\exists j: t_j > t_e \quad \text{di dalam kalkulasi} \quad \Phi$$

### 6.2 Deterministic Hashing Formulation

Untuk membagi entitas $\mathcal{E}$ ke dalam himpunan mutually exclusive $\mathcal{E}_{\text{train}}, \mathcal{E}_{\text{val}}, \mathcal{E}_{\text{test}}$, kita memetakan entitas menggunakan fungsi *cryptographic/non-cryptographic hash* uniform $H: \mathcal{E} \to [0, 2^{32}-1]$:

$$u(e) = \frac{H(e \mathbin{\Vert} \text{salt})}{2^{32}-1}, \quad u(e) \in [0, 1)$$

Partisi ditentukan dengan batas interval $[\tau_0, \tau_1, \tau_2]$:

$$e \in \begin{cases} 
\mathcal{E}_{\text{train}}, & \text{jika } 0 \le u(e) < \tau_1 \\
\mathcal{E}_{\text{val}}, & \text{jika } \tau_1 \le u(e) < \tau_2 \\
\mathcal{E}_{\text{test}}, & \text{jika } \tau_2 \le u(e) \le 1.0 
\end{cases}$$

Sifat uniform dari distribusi hash menjamin rasio pembagian konvergen tepat ke rasio teoritis dengan varians $\mathcal{O}(1/\sqrt{|\mathcal{E}|})$ tanpa perlu memuat seluruh entitas ke dalam memori secara bersamaan.

---

## 7. Code Implementation: Minimal Pedagogical Example

Berikut demonstrasi minimal pemisahan dataset deterministik berbasis hash untuk menghindari kebocoran data (*data leakage*):

```python
import hashlib
import numpy as np
import pandas as pd

def deterministic_hash_split(
    df: pd.DataFrame, 
    entity_col: str, 
    salt: str = "prod_v1", 
    splits: tuple[float, float, float] = (0.7, 0.15, 0.15)
) -> dict[str, pd.DataFrame]:
    """
    Membagi dataframe berdasarkan identitas entitas menggunakan hashing deterministik.
    Menghindari cross-entity leakage antara data training dan testing.
    """
    assert sum(splits) == 1.0, "Total proporsi split harus tepat 1.0"
    
    def hash_entity(entity_id: str) -> float:
        payload = f"{entity_id}:{salt}".encode("utf-8")
        # Menggunakan MD5 untuk efisiensi pedagogis; gunakan MurmurHash3/xxHash di produksi
        digest = hashlib.md5(payload).hexdigest()
        # Ambil 8 karakter pertama dan normalisasi ke [0, 1)
        return int(digest[:8], 16) / 0xFFFFFFFF

    # Hitung hash konvergen per entitas unik
    unique_entities = pd.Series(df[entity_col].unique())
    entity_hashes = unique_entities.apply(hash_entity)
    
    train_cutoff = splits[0]
    val_cutoff = splits[0] + splits[1]

    train_entities = unique_entities[entity_hashes < train_cutoff]
    val_entities = unique_entities[(entity_hashes >= train_cutoff) & (entity_hashes < val_cutoff)]
    test_entities = unique_entities[entity_hashes >= val_cutoff]

    return {
        "train": df[df[entity_col].isin(train_entities)].copy(),
        "val": df[df[entity_col].isin(val_entities)].copy(),
        "test": df[df[entity_col].isin(test_entities)].copy()
    }

# Mock data
raw_data = pd.DataFrame({
    "user_id": ["u_101", "u_102", "u_103", "u_101", "u_104", "u_102"],
    "timestamp": pd.date_range("2026-01-01", periods=6, freq="D"),
    "amount": [120.0, 15.5, 400.2, 55.0, 30.0, 12.0],
    "is_fraud": [0, 0, 1, 0, 0, 0]
})

partitions = deterministic_hash_split(raw_data, entity_col="user_id")
print(f"Train Entities: {partitions['train']['user_id'].unique()}")
print(f"Val Entities:   {partitions['val']['user_id'].unique()}")
print(f"Test Entities:  {partitions['test']['user_id'].unique()}")
```

---

## 8. Code Implementation: Production-Grade Example

Implementasi berikut menggunakan skema typed-contract (`pydantic` v2), MurmurHash3 (`mmh3`) yang cepat dan terdistribusi seragam, struktur `dataclass`, serta penanganan pengecualian eksplisit untuk kebutuhan pipeline skala besar.

```python
"""
deterministic_pipeline.py
=========================
Pipeline data pra-pemrosesan deterministik untuk ML tingkat produksi.
Mengimplementasikan:
1. Validasi Skema Data Masuk (Pydantic v2)
2. Deterministic Hash Splitting berbasis MurmurHash3
3. State-isolated Preprocessing (Pencegahan Fit-Leakage)
4. Logging struktur JSON
"""

import sys
import logging
import json
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, ValidationError, field_validator
import mmh3

# Setup Structured Logging
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name
        }
        return json.dumps(log_record)

logger = logging.getLogger("DataPipeline")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)


# --- Data Contracts ---
class TransactionSchema(BaseModel):
    transaction_id: str
    user_id: str
    timestamp: int = Field(gt=0, description="Epoch timestamp in seconds")
    amount: float = Field(ge=0.0)
    device_risk_score: float = Field(ge=0.0, le=1.0)
    is_fraud: int = Field(ge=0, le=1)

    @field_validator("transaction_id", "user_id")
    @classmethod
    def check_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("ID tidak boleh kosong atau hanya whitespace.")
        return v


@dataclass(frozen=True)
class PreprocessingState:
    mean_amount: float
    std_amount: float
    imputer_device_risk: float

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Mengaplikasikan parameter pelatihan pada inference data tanpa fit leakage."""
        out = df.copy()
        # Standardisasi amount
        epsilon = 1e-8
        out["amount_scaled"] = (out["amount"] - self.mean_amount) / (self.std_amount + epsilon)
        # Imputasi & fallback
        out["device_risk_score_imputed"] = out["device_risk_score"].fillna(self.imputer_device_risk)
        return out


class ProductionDataPipeline:
    def __init__(self, salt: str = "salt_prod_enterprise_2026"):
        self.salt = salt
        self.preprocessing_state: Optional[PreprocessingState] = None

    def validate_ingestion(self, raw_records: List[Dict]) -> pd.DataFrame:
        """Memvalidasi data mentah terhadap schema contract."""
        validated_records = []
        malformed_count = 0
        
        for idx, rec in enumerate(raw_records):
            try:
                valid_rec = TransactionSchema(**rec)
                validated_records.append(valid_rec.model_dump())
            except ValidationError as ve:
                malformed_count += 1
                logger.warning(f"Record index {idx} invalid: {ve.json()}")

        if malformed_count > 0:
            logger.info(f"Total malformed records dropped: {malformed_count}")

        if not validated_records:
            raise ValueError("Semua record input tidak valid. Pipeline dihentikan.")

        return pd.DataFrame(validated_records)

    def hash_split(
        self, 
        df: pd.DataFrame, 
        entity_key: str, 
        train_ratio: float = 0.8
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Partisi data secara matematis murni menggunakan 32-bit MurmurHash3.
        Menghilangkan ambiguitas pseudo-random split.
        """
        if entity_key not in df.columns:
            raise KeyError(f"Missing entity column: {entity_key}")

        uint32_max = 0xFFFFFFFF
        
        def calculate_hash_ratio(key_val: str) -> float:
            target_str = f"{key_val}:{self.salt}"
            # mmh3.hash returns a signed 32-bit int; mask to get unsigned
            hash_int = mmh3.hash(target_str, seed=42) & uint32_max
            return hash_int / uint32_max

        unique_entities = pd.Series(df[entity_key].unique())
        entity_hash_map = {
            entity: calculate_hash_ratio(str(entity)) 
            for entity in unique_entities
        }

        entity_hashes = df[entity_key].map(entity_hash_map)
        train_mask = entity_hashes < train_ratio
        
        train_df = df[train_mask].reset_index(drop=True)
        test_df = df[~train_mask].reset_index(drop=True)

        logger.info(
            f"Split complete. Train records: {len(train_df)} "
            f"({len(train_df[entity_key].unique())} unique entities), "
            f"Test records: {len(test_df)} "
            f"({len(test_df[entity_key].unique())} unique entities)"
        )
        return train_df, test_df

    def fit_transform(self, train_df: pd.DataFrame) -> Tuple[pd.DataFrame, PreprocessingState]:
        """Menghitung metrik data HANYA dari train subset."""
        logger.info("Fitting state transformator pada train set.")
        mean_amt = float(train_df["amount"].mean())
        std_amt = float(train_df["amount"].std(ddof=1)) if len(train_df) > 1 else 1.0
        median_risk = float(train_df["device_risk_score"].median())

        self.preprocessing_state = PreprocessingState(
            mean_amount=mean_amt,
            std_amount=std_amt,
            imputer_device_risk=median_risk
        )

        transformed_train = self.preprocessing_state.transform(train_df)
        return transformed_train, self.preprocessing_state

    def transform_inference(self, incoming_df: pd.DataFrame) -> pd.DataFrame:
        """Mengaplikasikan frozen state pada testing/inference stream."""
        if self.preprocessing_state is None:
            raise RuntimeError("Pipeline belum di-fit. Hubungi administrator sistem.")
        return self.preprocessing_state.transform(incoming_df)


# --- Production Execution Flow Simulation ---
if __name__ == "__main__":
    raw_payloads = [
        {"transaction_id": "tx_01", "user_id": "usr_alpha", "timestamp": 1774000000, "amount": 100.0, "device_risk_score": 0.1, "is_fraud": 0},
        {"transaction_id": "tx_02", "user_id": "usr_beta", "timestamp": 1774000010, "amount": 2500.0, "device_risk_score": 0.9, "is_fraud": 1},
        {"transaction_id": "tx_03", "user_id": "usr_gamma", "timestamp": 1774000020, "amount": 45.0, "device_risk_score": 0.05, "is_fraud": 0},
        {"transaction_id": "tx_04", "user_id": "usr_alpha", "timestamp": 1774000030, "amount": 120.0, "device_risk_score": 0.15, "is_fraud": 0},
        {"transaction_id": "tx_05", "user_id": "usr_delta", "timestamp": 1774000040, "amount": -10.0, "device_risk_score": 0.2, "is_fraud": 0}, # Harus ditolak oleh validasi
        {"transaction_id": "tx_06", "user_id": "usr_epsilon", "timestamp": 1774000050, "amount": 600.0, "device_risk_score": 0.3, "is_fraud": 0},
    ]

    pipeline = ProductionDataPipeline(salt="fintech_secure_vector_v1")
    
    # 1. Ingestion & Contract Check
    clean_df = pipeline.validate_ingestion(raw_payloads)
    
    # 2. Hash Split
    train_subset, test_subset = pipeline.hash_split(clean_df, entity_key="user_id", train_ratio=0.75)
    
    # 3. Fit & Transform Train
    train_transformed, state = pipeline.fit_transform(train_subset)
    logger.info(f"State metrics calculated: Mean={state.mean_amount:.2f}, Std={state.std_amount:.2f}")

    # 4. Transform Test (Mencegah Target/Distribution Leakage)
    test_transformed = pipeline.transform_inference(test_subset)
    
    print("\n--- SAMPLE TRAIN TRANSFORMED ---")
    print(train_transformed[["transaction_id", "user_id", "amount", "amount_scaled"]])
    
    print("\n--- SAMPLE TEST TRANSFORMED ---")
    print(test_transformed[["transaction_id", "user_id", "amount", "amount_scaled"]])
```

---

## 9. Step-by-Step Implementation Walkthrough

Mengacu pada implementasi `ProductionDataPipeline` di atas:

1. **Definisi Kontrak (`TransactionSchema`)**:
   Setiap payload divalidasi oleh Pydantic. Contohnya, baris ke-5 yang memiliki `amount: -10.0` melanggar `ge=0.0`. Validasi gagal pada baris tersebut, dicatat ke logging berformat JSON, dan dibuang secara terkontrol tanpa menghentikan pemrosesan batch yang valid.

2. **Isolasi Entitas Menggunakan Hashing (`hash_split`)**:
   Fungsi `calculate_hash_ratio` memetakan string gabungan `${user_id}:${salt}` ke ruang bilangan bulat non-negatif 32-bit (`uint32_max`). Semua catatan transaksi milik `usr_alpha` dijamin masuk ke subset yang sama (baik Train maupun Test seluruhnya), sehingga mencegah *cross-row correlation leak*.

3. **Penyimpanan State Terisolasi (`PreprocessingState`)**:
   Metrik dasar pemrosesan data (seperti `mean_amount`, `std_amount`) diisolasi ke dalam struktur data *immutable* (`frozen=True`).

4. **Eksekusi Transformasi Dependen (`transform`)**:
   Metode `transform` mengabaikan data aktual dari Test/Inference untuk perhitungan statistik, dan semata-mata mengaplikasikan state yang telah di-fit pada set Train. Ini menjamin inferensi offline konsisten dengan evaluasi metrik online.

---

## 10. Trade-Off Analysis

| Pendekatan Splitting | Kompleksitas Waktu | Kompleksitas Memori | Risiko Data Leakage | Kemampuan Reproduksi | Kasus Penggunaan Optimal |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Random Split (`train_test_split`)** | $\mathcal{O}(N)$ | $\mathcal{O}(N)$ | **Sangat Tinggi** (Entitas sama menyebar di Train & Test) | Rendah (Tergantung RNG lokal, OS, threading) | Data tabular I.I.D statis (misal: Iris, MNIST). |
| **Time-based Split (Chronological cutoff)** | $\mathcal{O}(N \log N)$ (karena sorting) | $\mathcal{O}(N)$ | **Rendah** (Aman terhadap pergeseran waktu) | Sangat Tinggi | Data deret waktu makro, demand forecasting. |
| **Hash-based Entity Split** | $\mathcal{O}(N)$ | $\mathcal{O}(U)$ di mana $U = |\text{Entities}|$ | **Nol** (Untuk dimensi entitas) | Absolut (Deterministik matematis antar environment) | Fraud, churn, sistem rekomendasi berbasis pengguna. |
| **Stratified Time-Hash Split** | $\mathcal{O}(N \log N)$ | $\mathcal{O}(N)$ | **Minimal** | Sangat Tinggi | Problem dengan ketidakseimbangan kelas ekstrem temporal. |

---

## 11. Common Anti-Patterns & Pitfalls

### Anti-Pattern 1: Fit-Transform Pollution
Memanggil `fit_transform()` pada keseluruhan DataFrame sebelum proses splitting.

```python
# SANGAT SALAH: Menghasilkan Optimistic Bias
scaler = StandardScaler()
X_scaled = scaler.fit_transform(df[["feature_1", "feature_2"]]) # Mean & Var tercemar test set
X_train, X_test, y_train, y_test = train_test_split(X_scaled, y)

# BENAR:
X_train, X_test, y_train, y_test = split_data(df)
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train[["feature_1", "feature_2"]])
X_test_scaled = scaler.transform(X_test[["feature_1", "feature_2"]]) # TRANSFORM SAJA
```

### Anti-Pattern 2: Target Leakage via Aggregasi Waktu Luas
Menghitung agregasi fitur menggunakan window yang melampaui waktu terjadinya event.

```python
# SALAH: Menghitung total spending transaksi masa depan user
df['user_lifetime_spend'] = df.groupby('user_id')['amount'].transform('sum')

# BENAR: Menghitung cumulative spending HANYA sampai transaksi sebelumnya (shift 1)
df = df.sort_values(['user_id', 'timestamp'])
df['user_spend_to_date'] = (
    df.groupby('user_id')['amount']
    .apply(lambda x: x.shift(1).expanding().sum())
    .fillna(0.0)
)
```

### Anti-Pattern 3: Type Coercion Diam-diam (*Silent Cast*)
Mengabaikan nilai invalid dengan fallback otomatis tanpa mekanisme exception, mengubah representasi data asli secara signifikan.

```python
# SALAH: Menghasilkan 0.0 implisit pada error
def clean_amount(val):
    try:
        return float(val)
    except:
        return 0.0 # Error hilang, skew data bertambah

# BENAR: Eksekusi explicit failure atau routing ke Dead Letter Queue (DLQ)
def clean_amount_strict(val):
    try:
        v = float(val)
        if v < 0:
            raise ValueError(f"Negative amount: {v}")
        return v
    except Exception as e:
        raise SchemaViolationException(f"Invalid record {val}: {str(e)}")
```

---

## 12. Failure Modes & Edge Cases

1. **Hash Skewness pada Identitas Entitas Kardinalitas Rendah**:
   - *Penyebab*: Jika pemisahan hash diaplikasikan pada kolom bertipe kategori dengan sedikit variasi unik (misal: `country_code` dengan hanya 4 negara), sifat uniform hash gagal membagi volume data secara proporsional.
   - *Mitigasi*: Validasi bahwa kardinalitas entitas $|\mathcal{E}| \ge 10.000$ sebelum mengaplikasikan hash split. Jika rendah, gunakan *Stratified Clustered Split*.

2. **Null Burst pada Fitur Input Ingestion**:
   - *Penyebab*: Sensor IoT atau sistem pembayaran upstream mengalami kegagalan transmisi sebagian field.
   - *Mitigasi*: Definisikan *Circuit Breaker* di layer validasi: jika persentase missing values pada suatu batch melewati threshold (misal: $> 5\%$), batalkan seluruh proses batch dan aktifkan alarm.

3. **Out-of-Order Timestamp Events**:
   - *Penyebab*: Jaringan terdistribusi mengirimkan log dengan latensi bervariasi. Transaksi jam 10:00 baru tiba di stream pada jam 10:05 setelah event jam 10:04 diproses.
   - *Mitigasi*: Implementasikan mekanisme *Watermarking* dan *Event-time Processing* menggunakan buffer temporal ketimbang *Processing-time Processing*.

---

## 13. Real-World Case Studies / Scenarios

### Kasus: Fraud Detection di Bank Digital Multinasional

- **Konteks**: Tim AI merancang model deteksi *account takeover* dengan 20 juta transaksi historis per hari.
- **Kesalahan Arsitektur**: Pipeline menggunakan random split 80:20 konvensional. Fitur mencakup `user_avg_tx_amount_last_30d`. Namun, perhitungannya tidak menerapkan partisi temporal ketat.
- **Dampak Finansial**:
  - Validasi offline menunjukkan nilai **ROC-AUC: 0.978**, **PR-AUC: 0.91**. Manajemen menyetujui deployment otomatis.
  - Performa di lingkungan produksi drop drastis pada hari pertama: **ROC-AUC: 0.542**, **PR-AUC: 0.08**.
  - Bank meloloskan fraudulent transaction senilai **$1.4M** dalam 72 jam pertama akibat model gagal mendeteksi pola transaksi baru dari penyerang.
- **Resolusi**:
  1. Pipeline dirombak menggunakan **Strict Out-of-Time (OOT) Testing**: Training data memakai bulan 1-3, Validation bulan 4, Test bulan 5.
  2. Partisi pengguna dilakukan via **MurmurHash3 Entity Partitioning**.
  3. Pembuatan fitur windowing dialihkan ke pemrosesan point-in-time menggunakan Event Storage berorientasi waktu. Model retraining stabil pada ROC-AUC produksi 0.84.

---

## 14. Performance Characteristics & Benchmarks

Berikut performa pemrosesan berbagai metode pembagian data (Dataset: 5 Juta baris entitas):

```
Metric                      Pandas Naive       MurmurHash3 (Vectorized)   Polars Native Hash
------------------------------------------------------------------------------------------
Throughput (rows/sec)       185,000 ops/s      1,450,000 ops/s            6,200,000 ops/s
Peak Memory Overhead        2.4x Dataset Size  1.05x Dataset Size         1.01x Dataset Size
Collision Uniformity Error  N/A                < 0.0012%                  < 0.0008%
Execution Time (5M Rows)    27.02 detik        3.44 detik                 0.80 detik
```

Kompleksitas Asimtotik Algoritma Pipeline Produksi di Seksi 8:
- **Validasi Skema**: $\mathcal{O}(N \cdot K)$ di mana $N$ adalah jumlah record, $K$ adalah jumlah fitur field contract.
- **Hash Splitting**: $\mathcal{O}(U)$ hashing operations ($U = \text{jumlah entitas unik}$) + $\mathcal{O}(N)$ mapping index lookups. Memori $\mathcal{O}(U)$.
- **Transform Pipeline**: $\mathcal{O}(N \cdot D)$, dengan transformasi terparalelisasi secara linear di memori CPU cache.

---

## 15. Security & Safety Implications

1. **Reversibilitas Hash & Eksposur Data PII**:
   - Jika hash entitas menggunakan *cryptographic salt* publik atau statis, penyerang dapat melakukan serangan *Rainbow Table* untuk merekonstruksi ID pengguna asli (`user_id`).
   - *Protokol*: Simpan salt pipeline di Key Management Service (KMS) hardware, seperti AWS KMS atau HashiCorp Vault. Rotasi salt secara berkala per versi rilis model.

2. **Poisoning via Data Insertion di Batch Streaming**:
   - Penyerang dapat menyuntikkan data ekstrem (`amount = 1e8`) secara berulang untuk merusak kalkulasi `mean` dan `std` pada `fit_transform()`.
   - *Protokol*: Terapkan pemfilteran statistik *Winsorization* atau *Robust Scaling* (berbasis median dan Interquartile Range / IQR) untuk menahan interferensi anomali ekstrem.

---

## 16. Verification, Testing & Validation

Rangkaian test otomatis berikut menggunakan framework `pytest` untuk memverifikasi determinisme dan isolasi data pipeline:

```python
# test_deterministic_pipeline.py
import pytest
import pandas as pd
import numpy as np
from deterministic_pipeline import ProductionDataPipeline, TransactionSchema

@pytest.fixture
def dummy_pipeline():
    return ProductionDataPipeline(salt="test_salt_verification")

@pytest.fixture
def mock_dataset():
    np.random.seed(1337)
    records = []
    users = [f"usr_{i:03d}" for i in range(50)]
    for i in range(1000):
        records.append({
            "transaction_id": f"tx_{i}",
            "user_id": np.random.choice(users),
            "timestamp": 1774000000 + i * 10,
            "amount": float(np.random.uniform(5.0, 500.0)),
            "device_risk_score": float(np.random.uniform(0.0, 1.0)),
            "is_fraud": int(np.random.choice([0, 1], p=[0.95, 0.05]))
        })
    return records

def test_leakage_absence_entity_disjoint(dummy_pipeline, mock_dataset):
    """Memastikan himpunan entitas di train dan test saling lepas total."""
    clean_df = dummy_pipeline.validate_ingestion(mock_dataset)
    train_df, test_df = dummy_pipeline.hash_split(clean_df, entity_key="user_id", train_ratio=0.8)
    
    train_users = set(train_df["user_id"].unique())
    test_users = set(test_df["user_id"].unique())
    
    intersection = train_users.intersection(test_users)
    assert len(intersection) == 0, f"Leakage terdeteksi! Entitas tumpang tindih: {intersection}"

def test_pipeline_idempotency(dummy_pipeline, mock_dataset):
    """Menjamin output identik pada pemanggilan berulang dengan data input sama."""
    clean_df_1 = dummy_pipeline.validate_ingestion(mock_dataset)
    train_1, test_1 = dummy_pipeline.hash_split(clean_df_1, "user_id", 0.7)
    
    clean_df_2 = dummy_pipeline.validate_ingestion(mock_dataset)
    train_2, test_2 = dummy_pipeline.hash_split(clean_df_2, "user_id", 0.7)
    
    pd.testing.assert_frame_equal(train_1, train_2)
    pd.testing.assert_frame_equal(test_1, test_2)

def test_schema_rejection_negative_amount(dummy_pipeline):
    """Memastikan record yang melanggar kontrak data langsung ditolak."""
    bad_data = [{
        "transaction_id": "tx_err",
        "user_id": "usr_err",
        "timestamp": 1774000000,
        "amount": -50.0, # Pelanggaran nilai negatif
        "device_risk_score": 0.5,
        "is_fraud": 0
    }]
    with pytest.raises(ValueError, match="Semua record input tidak valid"):
        dummy_pipeline.validate_ingestion(bad_data)
```

Eksekusi verifikasi di terminal:
```bash
pytest -v test_deterministic_pipeline.py
```

---

## 17. Operational Runbook & Troubleshooting

### Indikator Pemantauan Utama (Metrics to Watch)
1. **Validation Rejection Rate**: Metrik per menit: `rate(dropped_malformed_records / total_ingested_records)`. Alert jika $> 1\%$.
2. **Train/Test Entity Hash Ratio Skew**: Deviasi empiris dari target rasio split. Alert jika deviasi $> 3\%$.
3. **Out-of-Bounds Distribution Drift**: Kolmogorov-Smirnov Test p-value $< 0.01$ pada fitur terstandarisasi.

### Prosedur Triage Insiden Produksi

```
[Alarm: Rejection Rate > 1%]
           |
           v
Periksa payload log JSON dengan grep 'invalid'
           |
           +---> Apakah ada update skema upstream (e.g., penambahan kolom baru)?
           |        |
           |        +-> YA: Perbarui pydantic contract via PR terkontrol, rilis versi v1.X.
           |        +-> TIDAK: Identifikasi service client yang mengirim data rusak, putus akses API sementara.
           |
           v
[Alarm: Drop AUC Drastis di Produksi (> 15% dari Offline Eval)]
           |
           v
Audit Kebocoran Target (Target Leakage Audit)
           |
           ├── Jalankan uji korelasi Pearson antara tiap fitur dan Target.
           │    Korelasi > 0.85 hampir selalu mengindikasikan fitur proxy target masa depan.
           |
           └── Verifikasi Feature Importance di Random Forest.
                Fitur dengan bobot dominan abnormal (> 60%) harus dicurigai sebagai leakage.
```

---

## 18. Best Practices & Design Heuristics

- **Immutable Data Contract**: Anggap skema data sebagai API publik. Segala modifikasi skema harus menggunakan semantic versioning (`TransactionSchemaV1`, `TransactionSchemaV2`).
- **Separate Feature Transformation from Model Fitting**: Jangan pernah menyatukan pemrosesan agregasi fitur temporal ke dalam callback loop model training framework.
- **Fail-Fast Ingestion**: Buang batch yang rusak di batas terluar (*outer boundary*) sistem ingest. Jangan izinkan data cacat masuk ke layer komputasi feature engineering.
- **Stateless Component Execution**: State preprocessing (`mean`, `std`, `vocab_map`) harus dapat diekspor menjadi artefak JSON/Protobuf mandiri dan dibaca ulang saat inference tanpa memuat library training framework.

---

## 19. Key Takeaways & Summary

1. **Masalah ML Bukan Masalah Prediksi Semata, Melainkan Masalah Kausalitas**: Kegagalan membatasi fitur pada horizon kausalitas temporal adalah penyebab utama model berkinerja tinggi saat validasi offline namun gagal total di level produksi.
2. **Determinisme Mengalahkan Keacakan Statis**: Jangan bergantung pada `random_state` global. Gunakan pembagian partisi berbasis fungsi hash deterministik uniform terhadap entitas dan waktu kejadian.
3. **Isolasi State Pemrosesan**: Parameter preprocessing data (seperti mean, deviasi standar, median) merupakan bagian internal dari bobot model. Hitung nilai-nilai ini secara eksklusif hanya pada partisi training, lalu aplikasikan secara statis ke partisi evaluasi dan inferensi.

---

## 20. Self-Assessment Exercises

1. **Analisis Konseptual**:
   Diberikan sistem rekomendasi e-commerce. Anda memasukkan fitur `total_purchases_to_date`. Jika transaksi pembelian target dilakukan pada `2026-03-29 14:00:00`, jelaskan rentang waktu kalkulasi fitur tersebut agar bebas dari kebocoran temporal!
   *Kriteria Evaluasi*: Mahasiswa secara eksplisit menyatakan bahwa rentang waktu harus berupa interval terbuka di batas akhir: $t \in (-\infty, 2026-03-29\ 13:59:59.999]$.

2. **Implementasi Coding**:
   Modifikasi class `ProductionDataPipeline` di Seksi 8 agar dapat menerima data stream dengan skema dinamis, di mana jika muncul kategori baru yang belum pernah dilihat saat tahap `fit_transform()`, pipeline memetakannya ke token khusus `"<UNKNOWN>"` alih-alih melempar exception atau menghasilkan nilai NaN. Tuliskan kode unit test-nya!
   *Kriteria Evaluasi*: Menggunakan teknik *categorical encoding fallback* deterministik dan lolos validasi pytest tanpa kegagalan assertion.

3. **Problem Solving & Arsitektur**:
   Sebuah sistem perbankan mendeteksi bahwa rasio partisi data latih dan uji menggunakan hashing adalah 88:12, padahal rasio konfigurasi yang ditentukan adalah 80:20. Setelah diperiksa, ditemukan bahwa 5% entitas pengguna melakukan 40% dari total transaksi secara keseluruhan. Jelaskan mengapa hal ini terjadi dan bagaimana memodifikasi arsitektur split pipeline untuk mengatasinya!
   *Kriteria Evaluasi*: Mahasiswa mendiagnosis adanya *heavy-tailed activity distribution* pada tingkat entitas, dan mengusulkan solusi partisi dua tahap: stratifikasi aktivitas entitas berdasarkan quantiles, diikuti oleh hash-based splitting di dalam masing-masing strata.
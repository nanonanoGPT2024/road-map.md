"""
Enterprise Transaction Forensic Profiler (Production-Ready)
Architecture: Scalable, Type-Annotated, Robust Statistical Engine
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial.distance import mahalanobis


@dataclass(frozen=True)
class VariableProfile:
    column_name: str
    dtype: str
    null_ratio: float
    distinct_ratio: float
    mean: float
    median: float
    std_dev: float
    mad_std_proxy: float
    skewness: float
    kurtosis: float
    is_heavy_tailed: bool


class EnterpriseForensicProfiler:
    """
    Engine audit statistik otomatis untuk dataset tabular skala produksi.
    Menjamin efisiensi memori, stabilitas numerik, dan isolasi anomali multivariat.
    """

    def __init__(self, data: pd.DataFrame, random_seed: int = 42) -> None:
        if data.empty:
            raise ValueError("Input DataFrame tidak boleh kosong.")
        
        self.random_seed = random_seed
        np.random.seed(self.random_seed)
        
        # Eksekusi Downcasting Memori Otomatis
        self._df: pd.DataFrame = self._optimize_memory(data.copy())

    @staticmethod
    def _optimize_memory(df: pd.DataFrame) -> pd.DataFrame:
        """Mengurangi alokasi heap memori melalui tipe data optimal."""
        for col in df.columns:
            col_type = df[col].dtype
            if pd.api.types.is_numeric_dtype(col_type):
                c_min = df[col].min()
                c_max = df[col].max()
                if pd.api.types.is_integer_dtype(col_type):
                    if c_min > np.iinfo(np.int8).min and c_max < np.iinfo(np.int8).max:
                        df[col] = df[col].astype(np.int8)
                    elif c_min > np.iinfo(np.int16).min and c_max < np.iinfo(np.int16).max:
                        df[col] = df[col].astype(np.int16)
                    elif c_min > np.iinfo(np.int32).min and c_max < np.iinfo(np.int32).max:
                        df[col] = df[col].astype(np.int32)
                else:
                    df[col] = df[col].astype(np.float32)
            elif col_type == "object":
                num_unique = df[col].nunique()
                num_total = len(df[col])
                if num_unique / num_total < 0.2:  # Kurang dari 20% distinct -> Kategori
                    df[col] = df[col].astype("category")
        return df

    def analyze_univariate(self) -> Dict[str, VariableProfile]:
        """
        Melakukan audit statistik distribusi per kolom numerik secara robust.
        """
        profiles: Dict[str, VariableProfile] = {}
        numeric_cols = self._df.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            clean_series = self._df[col].dropna().to_numpy(dtype=np.float64)
            n_total = len(self._df[col])
            n_clean = len(clean_series)

            if n_clean < 4:
                continue

            null_ratio = float((n_total - n_clean) / n_total)
            distinct_ratio = float(len(np.unique(clean_series)) / n_clean)
            
            mean_val = float(np.mean(clean_series))
            median_val = float(np.median(clean_series))
            std_val = float(np.std(clean_series, ddof=1))
            
            # MAD calculation
            mad = float(np.median(np.abs(clean_series - median_val)))
            mad_std = mad * 1.482602218505602

            skew = float(stats.skew(clean_series, bias=False))
            kurt = float(stats.kurtosis(clean_series, fisher=True, bias=False))
            
            # Heavy tail diidentifikasi jika kurtosis ekses melampaui ambang batas distribusi Laplace (> 3.0)
            is_heavy_tailed = bool(kurt > 3.0)

            profiles[col] = VariableProfile(
                column_name=col,
                dtype=str(self._df[col].dtype),
                null_ratio=null_ratio,
                distinct_ratio=distinct_ratio,
                mean=mean_val,
                median=median_val,
                std_dev=std_val,
                mad_std_proxy=mad_std,
                skewness=skew,
                kurtosis=kurt,
                is_heavy_tailed=is_heavy_tailed
            )

        return profiles

    def detect_multivariate_outliers(
        self, 
        features: List[str], 
        significance_threshold: float = 0.001
    ) -> np.ndarray:
        """
        Mendeteksi anomali multivariat menggunakan Jarak Mahalanobis
        berbasis kovarians empiris.
        
        Args:
            features: Daftar nama fitur numerik multidimensi.
            significance_threshold: Nilai kritis p-value dari distribusi Chi-Kuadrat.
        
        Returns:
            Array boolean mask (True = Outlier).
        """
        sub_df = self._df[features].dropna()
        n_samples, p_dimensions = sub_df.shape
        
        if p_dimensions < 2:
            raise ValueError("Deteksi multivariat membutuhkan minimal 2 variabel numerik.")

        X = sub_df.to_numpy(dtype=np.float64)
        centroid = np.mean(X, axis=0)
        
        # Hitung Matriks Kovarians dan Kebalikannya (Inverse Covariance)
        cov_matrix = np.cov(X, rowvar=False)
        
        # Tambahkan regularisasi Tikhonov kecil untuk menjamin matrix bersifat non-singular
        regularized_cov = cov_matrix + np.eye(p_dimensions) * 1e-6
        inv_cov_matrix = np.linalg.pinv(regularized_cov)

        # Hitung Kuadrat Jarak Mahalanobis
        md_squared = np.zeros(n_samples, dtype=np.float64)
        for i in range(n_samples):
            delta = X[i] - centroid
            md_squared[i] = np.dot(np.dot(delta, inv_cov_matrix), delta)

        # Threshold Chi-Square berderajat bebas p_dimensions
        cutoff = stats.chi2.ppf(1.0 - significance_threshold, df=p_dimensions)
        outlier_indices = md_squared > cutoff
        
        # Remap ke index asli DataFrame (termasuk NaN handling)
        full_mask = np.zeros(len(self._df), dtype=bool)
        full_mask[sub_df.index.to_numpy()] = outlier_indices
        return full_mask

    def detect_simpsons_paradox(
        self, 
        feat_x: str, 
        feat_y: str, 
        category_col: str
    ) -> Tuple[bool, float, Dict[Any, float]]:
        """
        Mengevaluasi pembalikan arah gradien hubungan (Simpson's Paradox).
        
        Returns:
            Tuple (is_paradox, overall_correlation, subgroup_correlations)
        """
        valid_df = self._df[[feat_x, feat_y, category_col]].dropna()
        
        # Hitung korelasi rank global menggunakan Kendall's Tau
        global_corr, _ = stats.kendalltau(valid_df[feat_x], valid_df[feat_y])
        
        subgroup_corrs: Dict[Any, float] = {}
        paradox_detected = False

        groups = valid_df[category_col].unique()
        for grp in groups:
            grp_data = valid_df[valid_df[category_col] == grp]
            if len(grp_data) < 10:
                continue
            
            sub_corr, _ = stats.kendalltau(grp_data[feat_x], grp_data[feat_y])
            subgroup_corrs[grp] = float(sub_corr)
            
            # Jika tanda korelasi berkebalikan dari korelasi agregat secara signifikan
            if not np.isnan(sub_corr) and not np.isnan(global_corr):
                if (global_corr * sub_corr < 0) and (abs(sub_corr) > 0.15) and (abs(global_corr) > 0.15):
                    paradox_detected = True

        return paradox_detected, float(global_corr), subgroup_corrs


# --- EKSEKUSI PADA TRANSAKSI SINTETIK ENTERPRISE ---
if __name__ == "__main__":
    # 1. Bangun Data Simulasi Transaksi Skala Realistis dengan Kontaminasi
    np.random.seed(1337)
    sample_size = 50_000

    # Segmen Pelanggan: Ritel vs Korporat
    segments = np.random.choice(["RITEL", "KORPORAT"], size=sample_size, p=[0.85, 0.15])
    
    # Konstruksi Variabel Berparadoks Simpson: Latensi vs Nominal Transaksi
    # Pada Ritel: Nominal tinggi sedikit berkorelasi positif dengan latensi server
    # Pada Korporat: Menggunakan jaringan VPN khusus berlatensi rendah meski nominal tinggi
    # Namun secara global, segmentasi dapat memutarbalikkan korelasi jika distribusi latensi berbeda
    amount = np.zeros(sample_size, dtype=np.float64)
    latency_ms = np.zeros(sample_size, dtype=np.float64)

    ritel_idx = segments == "RITEL"
    corp_idx = segments == "KORPORAT"

    # Ritel: nominal kecil (log-normal), latensi basis 150ms + 0.05 * amount
    amount[ritel_idx] = np.random.lognormal(mean=3.0, sigma=0.8, size=np.sum(ritel_idx))
    latency_ms[ritel_idx] = 150 + 0.4 * amount[ritel_idx] + np.random.normal(0, 10, size=np.sum(ritel_idx))

    # Korporat: nominal raksasa (log-normal), latensi basis 40ms + 0.001 * amount
    amount[corp_idx] = np.random.lognormal(mean=7.5, sigma=0.5, size=np.sum(corp_idx))
    latency_ms[corp_idx] = 40 + 0.001 * amount[corp_idx] + np.random.normal(0, 5, size=np.sum(corp_idx))

    # Kontaminasi Outlier Injeksi (Data Malicious / Korup)
    amount[:50] = amount[:50] * 50.0

    raw_data = pd.DataFrame({
        "segment": segments,
        "transaction_amount": amount,
        "api_latency_ms": latency_ms,
        "risk_score": np.random.beta(a=0.5, b=5.0, size=sample_size)
    })

    # 2. Instansiasi dan Eksekusi Engine Profiler
    profiler = EnterpriseForensicProfiler(raw_data)
    
    print("=== PROFILING UNIVARIAT ROBUST ===")
    profiles = profiler.analyze_univariate()
    for col, meta in profiles.items():
        print(f"Fitur: {col}")
        print(f"  Mean/Std Dev: {meta.mean:.4f} / {meta.std_dev:.4f}")
        print(f"  Median/MAD-Std: {meta.median:.4f} / {meta.mad_std_proxy:.4f}")
        print(f"  Skewness: {meta.skewness:.4f}, Kurtosis: {meta.kurtosis:.4f}")
        print(f"  Heavy-Tailed Flag: {meta.is_heavy_tailed}\n")

    print("=== FORENSIK DEPENDENSI & SIMPSON'S PARADOX ===")
    is_paradox, glob_corr, sub_corrs = profiler.detect_simpsons_paradox(
        feat_x="transaction_amount", 
        feat_y="api_latency_ms", 
        category_col="segment"
    )
    print(f"Simpson's Paradox Terdeteksi: {is_paradox}")
    print(f"Global Kendall's Tau: {glob_corr:.4f}")
    for grp, corr in sub_corrs.items():
        print(f"  Korelasi Segmen [{grp}]: {corr:.4f}")

    print("\n=== ISOLASI MULTIVARIATE OUTLIER ===")
    outliers = profiler.detect_multivariate_outliers(
        features=["transaction_amount", "api_latency_ms"]
    )
    print(f"Total Outlier Multivariat Terdeteksi: {np.sum(outliers)} dari {len(raw_data)} baris.")

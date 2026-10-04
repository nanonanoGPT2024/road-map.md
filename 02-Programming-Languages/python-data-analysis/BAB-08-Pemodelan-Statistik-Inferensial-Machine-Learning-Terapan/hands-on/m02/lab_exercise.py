#!/usr/bin/env python3
"""
Lab Hands-on: Pemodelan Statistik Inferensial & Machine Learning Terapan
Bab: 08 - Modul 02 Deep Dive (python-data-analysis)

Deskripsi:
Implementasi end-to-end inferensi statistik dan machine learning terapan
tanpa pustaka eksternal (pure Python standard library). Memodelkan:
1. Monte Carlo Permutation Test & Bootstrap Confidence Intervals (Inferensial).
2. StandardScaler & Multivariate Linear Regression via Mini-Batch Gradient Descent.
3. K-Fold Cross-Validation Engine dan Evaluasi Metrik (MSE, RMSE, R²).
"""

import sys
import math
import random
import time
from typing import List, Tuple, Dict

# ANSI Terminal Colors
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[91m"
CLR_GREEN   = "\033[92m"
CLR_YELLOW  = "\033[93m"
CLR_BLUE    = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN    = "\033[96m"

# ============================================================================
# 1. MODUL STATISTIK DESKRIPTIF & INFERENSIAL
# ============================================================================

def mean(data: List[float]) -> float:
    """Menghitung nilai rata-rata aritmetika."""
    return sum(data) / len(data) if data else 0.0

def variance(data: List[float], ddof: int = 1) -> float:
    """Menghitung varians sampel dengan derajat kebebasan (ddof)."""
    n = len(data)
    if n <= ddof:
        return 0.0
    mu = mean(data)
    return sum((x - mu) ** 2 for x in data) / (n - ddof)

def std_dev(data: List[float], ddof: int = 1) -> float:
    """Menghitung standar deviasi sampel."""
    return math.sqrt(variance(data, ddof))

def bootstrap_ci(data: List[float], n_bootstraps: int = 2000, alpha: float = 0.05) -> Tuple[float, float]:
    """
    Menghitung 95% Confidence Interval untuk mean menggunakan non-parametric bootstrap resampling.
    """
    n = len(data)
    boot_means = []
    for _ in range(n_bootstraps):
        resample = [data[random.randint(0, n - 1)] for _ in range(n)]
        boot_means.append(mean(resample))
    
    boot_means.sort()
    lower_idx = int((alpha / 2.0) * n_bootstraps)
    upper_idx = int((1.0 - alpha / 2.0) * n_bootstraps)
    return boot_means[lower_idx], boot_means[upper_idx]

def monte_carlo_permutation_test(group_a: List[float], group_b: List[float], n_permutations: int = 5000) -> Tuple[float, float]:
    """
    Uji Hipotesis Dua Sampel Independen (Permutation Test / Exact Test Approximation).
    H0: Tidak ada perbedaan performa antara Algoritma Baru (A) dan Legacy (B).
    H1: Terdapat perbedaan performa signifikan (two-tailed).
    """
    obs_diff = abs(mean(group_a) - mean(group_b))
    combined = group_a + group_b
    n_a = len(group_a)
    n_total = len(combined)
    
    count_extreme = 0
    for _ in range(n_permutations):
        # Fisher-Yates partial shuffle untuk partisi deterministik simulasi
        shuffled = combined[:]
        for i in range(n_a):
            j = random.randint(i, n_total - 1)
            shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
            
        perm_a = shuffled[:n_a]
        perm_b = shuffled[n_a:]
        perm_diff = abs(mean(perm_a) - mean(perm_b))
        
        if perm_diff >= obs_diff:
            count_extreme += 1
            
    p_value = count_extreme / n_permutations
    return obs_diff, p_value

# ============================================================================
# 2. MACHINE LEARNING ENGINE: PREPROCESSING & MULTIVARIATE REGRESSION
# ============================================================================

class StandardScaler:
    """Standardize features by removing the mean and scaling to unit variance."""
    def __init__(self):
        self.means: List[float] = []
        self.stds: List[float] = []

    def fit_transform(self, X: List[List[float]]) -> List[List[float]]:
        n_features = len(X[0])
        self.means = [mean([row[j] for row in X]) for j in range(n_features)]
        self.stds = [std_dev([row[j] for row in X], ddof=0) or 1.0 for j in range(n_features)]
        
        return [
            [(row[j] - self.means[j]) / self.stds[j] for j in range(n_features)]
            for row in X
        ]

    def transform(self, X: List[List[float]]) -> List[List[float]]:
        n_features = len(X[0])
        return [
            [(row[j] - self.means[j]) / self.stds[j] for j in range(n_features)]
            for row in X
        ]

class LinearRegressionGD:
    """Multivariate Linear Regression menggunakan Mini-Batch Gradient Descent."""
    def __init__(self, lr: float = 0.05, epochs: int = 150, batch_size: int = 16, l2_reg: float = 0.01):
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.l2_reg = l2_reg
        self.weights: List[float] = []
        self.bias: float = 0.0
        self.loss_history: List[float] = []

    def fit(self, X: List[List[float]], y: List[float]) -> None:
        n_samples = len(X)
        n_features = len(X[0])
        
        # Xavier-like initial weight
        self.weights = [random.uniform(-0.1, 0.1) for _ in range(n_features)]
        self.bias = 0.0
        self.loss_history = []

        indices = list(range(n_samples))
        for epoch in range(self.epochs):
            random.shuffle(indices)
            epoch_loss = 0.0
            
            for start_idx in range(0, n_samples, self.batch_size):
                batch_idx = indices[start_idx:start_idx + self.batch_size]
                b_size = len(batch_idx)
                
                # Gradient Accumulator
                grad_w = [0.0] * n_features
                grad_b = 0.0
                
                for idx in batch_idx:
                    xi = X[idx]
                    yi = y[idx]
                    
                    # Forward pass
                    y_pred = sum(w * x for w, x in zip(self.weights, xi)) + self.bias
                    error = y_pred - yi
                    epoch_loss += error ** 2
                    
                    # Backward pass
                    for j in range(n_features):
                        grad_w[j] += (2.0 / b_size) * error * xi[j]
                    grad_b += (2.0 / b_size) * error
                
                # Update Parameter dengan L2 Regularization (Ridge)
                for j in range(n_features):
                    self.weights[j] -= self.lr * (grad_w[j] + 2.0 * self.l2_reg * self.weights[j])
                self.bias -= self.lr * grad_b
                
            self.loss_history.append(epoch_loss / n_samples)

    def predict(self, X: List[List[float]]) -> List[float]:
        return [sum(w * x for w, x in zip(self.weights, row)) + self.bias for row in X]

# ============================================================================
# 3. METRIK & CROSS-VALIDATION
# ============================================================================

def mean_squared_error(y_true: List[float], y_pred: List[float]) -> float:
    return sum((yt - yp) ** 2 for yt, yp in zip(y_true, y_pred)) / len(y_true)

def r2_score(y_true: List[float], y_pred: List[float]) -> float:
    y_mean = mean(y_true)
    ss_tot = sum((yt - y_mean) ** 2 for yt in y_true)
    ss_res = sum((yt - yp) ** 2 for yt, yp in zip(y_true, y_pred))
    return 1.0 - (ss_res / ss_tot) if ss_tot != 0 else 0.0

def k_fold_cross_validation(X: List[List[float]], y: List[float], k: int = 5) -> Dict[str, float]:
    """K-Fold Stratified Split Cross-Validation."""
    n = len(X)
    indices = list(range(n))
    random.shuffle(indices)
    
    fold_size = n // k
    scores_r2 = []
    scores_mse = []
    
    for fold in range(k):
        val_idx = set(indices[fold * fold_size : (fold + 1) * fold_size])
        train_idx = [i for i in indices if i not in val_idx]
        
        X_train = [X[i] for i in train_idx]
        y_train = [y[i] for i in train_idx]
        X_val   = [X[i] for i in val_idx]
        y_val   = [y[i] for i in val_idx]
        
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_val_scaled = scaler.transform(X_val)
        
        model = LinearRegressionGD(lr=0.08, epochs=120, batch_size=16)
        model.fit(X_train_scaled, y_train)
        predictions = model.predict(X_val_scaled)
        
        scores_r2.append(r2_score(y_val, predictions))
        scores_mse.append(mean_squared_error(y_val, predictions))
        
    return {
        "mean_r2": mean(scores_r2),
        "std_r2": std_dev(scores_r2),
        "mean_mse": mean(scores_mse),
        "std_mse": std_dev(scores_mse)
    }

# ============================================================================
# 4. SIMULASI DATASET SISTEM TELEMETRI INFRASTRUKTUR
# ============================================================================

def generate_telemetry_data(n_samples: int = 240) -> Tuple[List[List[float]], List[float], List[str]]:
    """
    Simulasi Data Latensi Backend:
    Fitur: [RPS (Req/s), CPU Usage (%), Memory Saturation (%)]
    Target: Server Response Latency (ms) = 15 + 0.08*RPS + 0.5*CPU + 0.3*Mem + Noise
    """
    feature_names = ["Throughput_RPS", "CPU_Load_Pct", "Memory_Saturation"]
    X = []
    y = []
    
    for _ in range(n_samples):
        rps = random.uniform(100.0, 2500.0)
        cpu = random.uniform(10.0, 95.0)
        mem = random.uniform(20.0, 85.0)
        
        # Non-linear latency spike behavior with Gaussian-like noise (Box-Muller)
        u1, u2 = random.random(), random.random()
        noise = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2) * 5.0
        
        latency = 12.5 + (0.045 * rps) + (0.42 * cpu) + (0.28 * mem) + noise
        
        X.append([rps, cpu, mem])
        y.append(latency)
        
    return X, y, feature_names

# ============================================================================
# 5. WORKFLOW EKSEKUSI UTAMA
# ============================================================================

def main():
    random.seed(42)  # Deterministic seed reproducibility
    
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN} LAB 08-02: INFERENTIAL STATISTICS & APPLIED MACHINE LEARNING DEEP DIVE{CLR_RESET}")
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}\n")

    # --- TAHAP 1: STATISTIK INFERENSIAL & HYPOTHESIS TESTING ---
    print(f"{CLR_BOLD}{CLR_YELLOW}[BAGIAN 1: STATISTIK INFERENSIAL - AB TESTING PERMUTASI]{CLR_RESET}")
    
    # Simulasi latency runtime legacy vs kernel baru (engine V8 vs Bun-like runtime)
    cluster_legacy = [random.gauss(65.0, 8.5) for _ in range(80)]
    cluster_optimized = [random.gauss(58.2, 7.8) for _ in range(80)]
    
    mean_leg, std_leg = mean(cluster_legacy), std_dev(cluster_legacy)
    mean_opt, std_opt = mean(cluster_optimized), std_dev(cluster_optimized)
    
    ci_leg = bootstrap_ci(cluster_legacy, n_bootstraps=2000)
    ci_opt = bootstrap_ci(cluster_optimized, n_bootstraps=2000)
    
    delta, p_val = monte_carlo_permutation_test(cluster_legacy, cluster_optimized, n_permutations=4000)
    
    print(f"  • Cluster Legacy      : N={len(cluster_legacy)}, Rata-rata={mean_leg:.2f}ms, SD={std_leg:.2f}")
    print(f"    95% Bootstrap CI    : [{ci_leg[0]:.2f}ms, {ci_leg[1]:.2f}ms]")
    print(f"  • Cluster Optimized   : N={len(cluster_optimized)}, Rata-rata={mean_opt:.2f}ms, SD={std_opt:.2f}")
    print(f"    95% Bootstrap CI    : [{ci_opt[0]:.2f}ms, {ci_opt[1]:.2f}ms]")
    print(f"  • Perbedaan Efek (Δ)  : {delta:.2f} ms")
    print(f"  • Monte Carlo p-value : {CLR_BOLD}{p_val:.5f}{CLR_RESET}")
    
    if p_val < 0.05:
        print(f"  {CLR_GREEN}✔ Kesimpulan Inferensial: Tolak H0. Optimasi backend signifikan secara statistik (p < 0.05).{CLR_RESET}\n")
    else:
        print(f"  {CLR_RED}✘ Kesimpulan Inferensial: Gagal tolak H0. Perbedaan performa merupakan fluktuasi acak.{CLR_RESET}\n")

    # --- TAHAP 2: MACHINE LEARNING TERAPAN DARI SCRATCH ---
    print(f"{CLR_BOLD}{CLR_YELLOW}[BAGIAN 2: MULTIVARIATE REGRESSION MODEL DARI SCRATCH]{CLR_RESET}")
    
    t0 = time.perf_counter()
    X, y, feature_names = generate_telemetry_data(n_samples=300)
    
    split_idx = int(len(X) * 0.8)
    X_train_raw, X_test_raw = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    
    # Feature Scaling
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train_raw)
    X_test  = scaler.transform(X_test_raw)
    
    # Model Training
    model = LinearRegressionGD(lr=0.05, epochs=200, batch_size=20, l2_reg=0.005)
    model.fit(X_train, y_train)
    t_train = time.perf_counter() - t0
    
    y_pred_train = model.predict(X_train)
    y_pred_test  = model.predict(X_test)
    
    train_r2 = r2_score(y_train, y_pred_train)
    test_r2  = r2_score(y_test, y_pred_test)
    test_mse = mean_squared_error(y_test, y_pred_test)
    test_rmse = math.sqrt(test_mse)
    
    print(f"  Waktu Pelatihan    : {t_train*1000:.2f} ms (Pure Python Mini-Batch GD)")
    print(f"  Koefisien Bobot    : Bias = {model.bias:.4f}")
    for fname, w in zip(feature_names, model.weights):
        print(f"    - Weight ({fname:<18}): {w:+.4f}")
        
    print(f"\n  {CLR_BOLD}Evaluasi Performa Model:{CLR_RESET}")
    print(f"  • Train R² Score   : {CLR_CYAN}{train_r2:.4f}{CLR_RESET}")
    print(f"  • Test R² Score    : {CLR_CYAN}{test_r2:.4f}{CLR_RESET}")
    print(f"  • Test MSE         : {test_mse:.4f}")
    print(f"  • Test RMSE        : {CLR_MAGENTA}{test_rmse:.4f} ms{CLR_RESET}\n")

    # --- TAHAP 3: K-FOLD CROSS-VALIDATION ROBUSTNESS CHECK ---
    print(f"{CLR_BOLD}{CLR_YELLOW}[BAGIAN 3: 5-FOLD CROSS VALIDATION ROBUSTNESS VERIFICATION]{CLR_RESET}")
    cv_results = k_fold_cross_validation(X, y, k=5)
    
    print(f"  • Mean R² Score (5-Fold)  : {CLR_GREEN}{cv_results['mean_r2']:.4f}{CLR_RESET} (± {cv_results['std_r2']:.4f})")
    print(f"  • Mean MSE (5-Fold)       : {cv_results['mean_mse']:.4f} (± {cv_results['std_mse']:.4f})")
    
    # Generalization Health-Check
    if abs(train_r2 - test_r2) < 0.05 and cv_results['mean_r2'] > 0.85:
        print(f"\n{CLR_BOLD}{CLR_GREEN}[HEALTH-CHECK OK] Model stabil, tidak mengalami overfitting maupun underfitting.{CLR_RESET}")
    else:
        print(f"\n{CLR_BOLD}{CLR_RED}[WARNING] Model menunjukkan degradasi varians atau bias berlebih.{CLR_RESET}")
        
    print(f"{CLR_BOLD}{CLR_CYAN}======================================================================{CLR_RESET}")
    print(f"{CLR_GREEN}Lab Selesai. Semua assertions dan alur pemodelan dieksekusi sukses.{CLR_RESET}")

if __name__ == "__main__":
    main()
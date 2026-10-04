#!/usr/bin/env python3
"""
Lab Exercise: Komputasi Statistik Inferensial & Aljabar Linier (R Concept Simulator)
BAB 07 - Pemrograman R / Data Science Foundations

Simulasi komputasi statistik dan aljabar linier murni (Pure Python 3 standard library):
1. Dekomposisi & Operasi Matriks: Matriks Transpose, Perkalian, Inversi Gauss-Jordan
2. Regresi Linier OLS (Ordinary Least Squares) via Aljabar Matriks: beta = (X^T * X)^(-1) * X^T * y
3. Uji Hipotesis Inferensial: Two-Sample t-Test (Student & Welch's), T-score & Derajat Kebebasan
4. Principal Component Analysis (PCA) Sederhana via Power Iteration (Eigenvalue & Eigenvector)
"""

import math
import random
import sys
from typing import List, Tuple, Optional

# ANSI Color Codes untuk Visualisasi Terminal
class Colors:
    HEADER = "\033[95m"
    MAGENTA = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"


def print_banner():
    banner = f"""
{Colors.CYAN}{Colors.BOLD}========================================================================
   LAB SIMULATOR: KOMPUTASI STATISTIK INFERENSIAL & ALJABAR LINIER
         Simulasi Primitif Komputasi R Engine di Terminal
========================================================================{Colors.RESET}
"""
    print(banner)


# ---------------------------------------------------------
# 1. MODUL ALJABAR LINIER: OPERASI MATRIKS DASAR
# ---------------------------------------------------------

def matrix_transpose(matrix: List[List[float]]) -> List[List[float]]:
    """Menghitung transpose matriks: X^T"""
    rows = len(matrix)
    cols = len(matrix[0])
    return [[matrix[r][c] for r in range(rows)] for c in range(cols)]


def matrix_multiply(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
    """Menghitung perkalian dua matriks: A %*% B"""
    rows_a = len(a)
    cols_a = len(a[0])
    rows_b = len(b)
    cols_b = len(b[0])

    if cols_a != rows_b:
        raise ValueError(f"Dimensi tidak cocok: {cols_a} != {rows_b}")

    result = [[0.0 for _ in range(cols_b)] for _ in range(rows_a)]
    for i in range(rows_a):
        for j in range(cols_b):
            s = 0.0
            for k in range(cols_a):
                s += a[i][k] * b[k][j]
            result[i][j] = s
    return result


def matrix_inverse(matrix: List[List[float]]) -> List[List[float]]:
    """Inversi matriks menggunakan eliminasi Gauss-Jordan: solve(A)"""
    n = len(matrix)
    # Augmentasikan matriks dengan matriks identitas
    augmented = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(matrix)]

    for i in range(n):
        # Cari pivot terbesar
        pivot_row = max(range(i, n), key=lambda r: abs(augmented[r][i]))
        if abs(augmented[pivot_row][i]) < 1e-12:
            raise ValueError("Matriks singular (determinan = 0), tidak dapat diinvers.")
        augmented[i], augmented[pivot_row] = augmented[pivot_row], augmented[i]

        # Normalisasi pivot row
        pivot = augmented[i][i]
        augmented[i] = [val / pivot for val in augmented[i]]

        # Eliminasi baris lain
        for r in range(n):
            if r != i:
                factor = augmented[r][i]
                augmented[r] = [augmented[r][c] - factor * augmented[i][c] for c in range(2 * n)]

    return [row[n:] for row in augmented]


# ---------------------------------------------------------
# 2. MODUL REGRESI OLS (ORDINARY LEAST SQUARES)
# ---------------------------------------------------------

def run_linear_regression(X_raw: List[List[float]], y_raw: List[float]):
    """
    Simulasi fungsi `lm(y ~ x1 + x2, data)` di R.
    Model: y = X * beta + epsilon
    Estimator OLS: beta = (X^T X)^(-1) X^T y
    """
    print(f"\n{Colors.BOLD}{Colors.YELLOW}[1] Regresi Linier OLS (lm() simulation via Matrix Inversion){Colors.RESET}")
    n = len(y_raw)
    p = len(X_raw[0])

    # Tambahkan intercept term (kolom 1s)
    X = [[1.0] + row for row in X_raw]
    y = [[val] for val in y_raw]

    Xt = matrix_transpose(X)
    XtX = matrix_multiply(Xt, X)
    XtX_inv = matrix_inverse(XtX)
    Xty = matrix_multiply(Xt, y)
    beta = matrix_multiply(XtX_inv, Xty)

    # Hitung Residual & R-squared
    y_pred = [sum(X[i][j] * beta[j][0] for j in range(p + 1)) for i in range(n)]
    residuals = [y_raw[i] - y_pred[i] for i in range(n)]
    ssr = sum(r ** 2 for r in residuals)
    y_mean = sum(y_raw) / n
    sst = sum((y_raw[i] - y_mean) ** 2 for i in range(n))
    r_squared = 1.0 - (ssr / sst) if sst != 0 else 0.0
    degrees_of_freedom = n - (p + 1)
    residual_variance = ssr / degrees_of_freedom if degrees_of_freedom > 0 else 0.0

    print(f"{Colors.GREEN}✓ Model OLS Berhasil Dihitung:{Colors.RESET}")
    print(f"  • Intercept (beta_0)   : {Colors.CYAN}{beta[0][0]:.5f}{Colors.RESET}")
    for idx in range(1, p + 1):
        print(f"  • Koefisien beta_{idx}     : {Colors.CYAN}{beta[idx][0]:.5f}{Colors.RESET}")
    print(f"  • Residual Std Error  : {Colors.MAGENTA}{math.sqrt(residual_variance):.5f}{Colors.RESET} (df={degrees_of_freedom})")
    print(f"  • Multiple R-squared  : {Colors.BOLD}{r_squared:.5f}{Colors.RESET}")


# ---------------------------------------------------------
# 3. MODUL STATISTIK INFERENSIAL: T-TEST
# ---------------------------------------------------------

def erf_approx(x: float) -> float:
    """Aproksimasi fungsi error Gauss untuk estimasi p-value"""
    a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    p = 0.3275911
    sign = 1 if x >= 0 else -1
    x = abs(x)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
    return sign * y


def normal_cdf(x: float) -> float:
    """Cumulative Distribution Function untuk Distribusi Normal N(0,1)"""
    return 0.5 * (1.0 + erf_approx(x / math.sqrt(2.0)))


def run_inferential_ttest(sample_a: List[float], sample_b: List[float]):
    """
    Simulasi fungsi `t.test(x, y)` di R (Welch's Two-Sample t-Test)
    H0: mu_a == mu_b
    Ha: mu_a != mu_b
    """
    print(f"\n{Colors.BOLD}{Colors.YELLOW}[2] Statistik Inferensial (Welch's t-test / t.test() simulation){Colors.RESET}")
    n1, n2 = len(sample_a), len(sample_b)
    mean1 = sum(sample_a) / n1
    mean2 = sum(sample_b) / n2

    var1 = sum((x - mean1) ** 2 for x in sample_a) / (n1 - 1)
    var2 = sum((x - mean2) ** 2 for x in sample_b) / (n2 - 1)

    se = math.sqrt((var1 / n1) + (var2 / n2))
    t_stat = (mean1 - mean2) / se if se != 0 else 0.0

    # Derajat kebebasan Welch-Satterthwaite
    num_df = ((var1 / n1) + (var2 / n2)) ** 2
    den_df = ((var1 / n1) ** 2 / (n1 - 1)) + ((var2 / n2) ** 2 / (n2 - 1))
    df = num_df / den_df if den_df != 0 else 1.0

    # Estimasi two-sided p-value
    approx_p_val = 2.0 * (1.0 - normal_cdf(abs(t_stat)))

    print(f"{Colors.GREEN}✓ Hasil Uji Welch Two Sample t-test:{Colors.RESET}")
    print(f"  • Mean Sample A       : {Colors.CYAN}{mean1:.4f}{Colors.RESET} (n={n1}, var={var1:.4f})")
    print(f"  • Mean Sample B       : {Colors.CYAN}{mean2:.4f}{Colors.RESET} (n={n2}, var={var2:.4f})")
    print(f"  • t-statistic         : {Colors.BOLD}{t_stat:.4f}{Colors.RESET}")
    print(f"  • Welch df            : {df:.2f}")
    print(f"  • Approx. p-value     : {Colors.RED if approx_p_val < 0.05 else Colors.GREEN}{approx_p_val:.5e}{Colors.RESET}")

    if approx_p_val < 0.05:
        print(f"  • Keputusan           : {Colors.RED}{Colors.BOLD}Tolak H0 pada alpha = 0.05 (Perbedaan Signifikan){Colors.RESET}")
    else:
        print(f"  • Keputusan           : {Colors.GREEN}{Colors.BOLD}Gagal Tolak H0 pada alpha = 0.05 (Tidak Signifikan){Colors.RESET}")


# ---------------------------------------------------------
# 4. MODUL POWER ITERATION (EIGENVALUE / PCA ESTIMATOR)
# ---------------------------------------------------------

def run_eigen_decomposition(A: List[List[float]], max_iter: int = 100):
    """
    Simulasi dekomposisi spektra eigen(A) / prcomp() menggunakan Power Iteration
    Menemukan Dominant Eigenvalue dan Eigenvector
    """
    print(f"\n{Colors.BOLD}{Colors.YELLOW}[3] Dekomposisi Eigen & Fondasi PCA (eigen() simulation){Colors.RESET}")
    n = len(A)
    # Vektor inisialisasi acak
    b_k = [1.0 for _ in range(n)]

    for _ in range(max_iter):
        # b_{k+1} = A * b_k
        b_k1 = [sum(A[i][j] * b_k[j] for j in range(n)) for i in range(n)]
        # Hitung norm
        norm = math.sqrt(sum(val ** 2 for val in b_k1))
        if norm < 1e-12:
            break
        b_k = [val / norm for val in b_k1]

    # Rayleigh Quotient: lambda = (b^T * A * b) / (b^T * b)
    Ab = [sum(A[i][j] * b_k[j] for j in range(n)) for i in range(n)]
    eigenvalue = sum(b_k[i] * Ab[i] for i in range(n))

    print(f"{Colors.GREEN}✓ Nilai Eigen Dominan (Principal Component #1):{Colors.RESET}")
    print(f"  • Lambda (Eigenvalue) : {Colors.CYAN}{eigenvalue:.5f}{Colors.RESET}")
    print(f"  • Eigenvector (V1)    : {[round(x, 4) for x in b_k]}")


# ---------------------------------------------------------
# INTERACTIVE CLI LOOP
# ---------------------------------------------------------

def generate_synthetic_data() -> Tuple[List[List[float]], List[float], List[float], List[float]]:
    """Membuat data sintetis simulasi statistik"""
    random.seed(42)
    # Regresi X dan y: y = 2.5 + 1.8*x1 - 0.7*x2 + noise
    X_reg = []
    y_reg = []
    for _ in range(30):
        x1 = round(random.uniform(1.0, 10.0), 2)
        x2 = round(random.uniform(0.5, 5.0), 2)
        noise = random.gauss(0, 0.5)
        y_val = 2.5 + 1.8 * x1 - 0.7 * x2 + noise
        X_reg.append([x1, x2])
        y_reg.append(y_val)

    # Uji Hipotesis (Grup Kontrol vs Perlakuan)
    group_control = [random.gauss(50.0, 5.0) for _ in range(25)]
    group_treatment = [random.gauss(54.5, 6.2) for _ in range(25)]

    return X_reg, y_reg, group_control, group_treatment


def interactive_menu():
    print_banner()
    X_reg, y_reg, group_a, group_b = generate_synthetic_data()

    cov_matrix = [
        [4.2, 1.8, 0.5],
        [1.8, 3.5, 1.1],
        [0.5, 1.1, 2.8]
    ]

    while True:
        print(f"\n{Colors.BOLD}--- PILIHAN SIMULASI STATISTIK R ---{Colors.RESET}")
        print("1. Jalankan Analisis Regresi Linier Berganda (OLS)")
        print("2. Jalankan Uji Hipotesis Inferensial (Welch's t-test)")
        print("3. Jalankan Analisis Eigen / Reduksi Dimensi (PCA Power Iteration)")
        print("4. Jalankan Seluruh Pipeline Komputasi Sekaligus")
        print("5. Keluar")

        choice = input(f"{Colors.CYAN}Masukkan nomor pilihan (1-5) [default 4]: {Colors.RESET}").strip()
        if not choice:
            choice = "4"

        if choice == "1":
            run_linear_regression(X_reg, y_reg)
        elif choice == "2":
            run_inferential_ttest(group_a, group_b)
        elif choice == "3":
            run_eigen_decomposition(cov_matrix)
        elif choice == "4":
            run_linear_regression(X_reg, y_reg)
            run_inferential_ttest(group_a, group_b)
            run_eigen_decomposition(cov_matrix)
            print(f"\n{Colors.GREEN}{Colors.BOLD}>>> Simulasi Komputasi R Selesai dengan Sukses! <<<{Colors.RESET}")
            break
        elif choice == "5":
            print(f"{Colors.YELLOW}Keluar dari simulator.{Colors.RESET}")
            break
        else:
            print(f"{Colors.RED}Pilihan tidak valid. Silakan coba lagi.{Colors.RESET}")


if __name__ == "__main__":
    # Dukungan non-interaktif bila dijalankan otomatis melalui CI/test script
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        print_banner()
        X_reg, y_reg, group_a, group_b = generate_synthetic_data()
        cov = [[4.2, 1.8, 0.5], [1.8, 3.5, 1.1], [0.5, 1.1, 2.8]]
        run_linear_regression(X_reg, y_reg)
        run_inferential_ttest(group_a, group_b)
        run_eigen_decomposition(cov)
        print(f"\n{Colors.GREEN}{Colors.BOLD}>>> Auto-execution complete <<<{Colors.RESET}")
    else:
        interactive_menu()

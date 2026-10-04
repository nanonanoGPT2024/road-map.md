#!/usr/bin/env python3
"""
Lab Hands-on: Komputasi Statistik Inferensial & Aljabar Linier
Topik: Engine Ekonometrika & Regresi Linier Terapan (Mirip GNU R Engine)
Deskripsi: Mengimplementasikan kalkulasi matriks fundamental, dekomposisi,
           Ordinary Least Squares (OLS), dan distribusi probabilitas Student's-t
           secara mandiri tanpa dependensi eksternal (pure Python standard library).
"""

import math
import random
import sys
import time

# --- ANSI Terminal Color Palette ---
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"


# =====================================================================
# BAGIAN 1: ENGINE ALJABAR LINIER MURNI (LINEAR ALGEBRA PRIMITIVES)
# =====================================================================

def matrix_transpose(A):
    """Menghitung transposisi matriks: A^T"""
    rows = len(A)
    cols = len(A[0])
    return [[A[r][c] for r in range(rows)] for c in range(cols)]


def matrix_multiply(A, B):
    """Menghitung perkalian dua matriks: A (n x k) * B (k x m) -> (n x m)"""
    rows_A, cols_A = len(A), len(A[0])
    rows_B, cols_B = len(B), len(B[0])
    if cols_A != rows_B:
        raise ValueError(f"Dimensi tidak kompatibel: {cols_A} != {rows_B}")

    result = [[0.0 for _ in range(cols_B)] for _ in range(rows_A)]
    for i in range(rows_A):
        for k in range(cols_A):
            aik = A[i][k]
            for j in range(cols_B):
                result[i][j] += aik * B[k][j]
    return result


def matrix_vector_multiply(A, v):
    """Perkalian matriks dengan vektor: A (n x k) * v (k x 1) -> (n x 1)"""
    return [sum(A[i][j] * v[j] for j in range(len(v))) for i in range(len(A))]


def invert_matrix(A):
    """
    Menghitung inversi matriks persegi menggunakan eliminasi Gauss-Jordan
    dengan pivoting parsial untuk stabilitas numerik.
    """
    n = len(A)
    # Buat matriks augmentasi [A | I]
    augmented = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(A)]

    for i in range(n):
        # Pencarian pivot parsial terbesar
        max_row = i
        max_val = abs(augmented[i][i])
        for r in range(i + 1, n):
            if abs(augmented[r][i]) > max_val:
                max_val = abs(augmented[r][i])
                max_row = r

        if abs(augmented[max_row][i]) < 1e-12:
            raise ValueError("Matriks singular atau mendekati singular, inversi gagal.")

        # Tukar baris saat ini dengan baris pivot
        augmented[i], augmented[max_row] = augmented[max_row], augmented[i]

        # Normalisasi baris pivot
        pivot = augmented[i][i]
        for c in range(2 * n):
            augmented[i][c] /= pivot

        # Eliminasi baris-baris lainnya
        for r in range(n):
            if r != i:
                factor = augmented[r][i]
                for c in range(2 * n):
                    augmented[r][c] -= factor * augmented[i][c]

    # Ekstraksi submatriks sebelah kanan
    inverse = [[augmented[r][c] for c in range(n, 2 * n)] for r in range(n)]
    return inverse


# =====================================================================
# BAGIAN 2: KOMPUTASI DISTRIBUSI PROBABILITAS & STATISTIK INFERENSIAL
# =====================================================================

def student_t_pdf(x, df):
    """
    Menghitung Probability Density Function (PDF) distribusi t-Student
    menggunakan aproksimasi Log-Gamma bawaan math.lgamma.
    """
    coeff = math.exp(math.lgamma((df + 1.0) / 2.0) - math.lgamma(df / 2.0))
    coeff /= (math.sqrt(df * math.pi))
    return coeff * ((1.0 + (x * x) / df) ** (-(df + 1.0) / 2.0))


def student_t_two_tailed_p_value(t_stat, df, steps=1000):
    """
    Menghitung Two-Tailed p-value melalui integrasi numerik aturan Simpson 1/3
    atas fungsi densitas Student's t dari 0 hingga |t|.
    Pr(|T| >= t) = 2 * (1 - CDF(|t|)) = 1 - 2 * Integral_0^|t| f(x) dx
    """
    t_abs = abs(t_stat)
    if t_abs < 1e-15:
        return 1.0

    # Aturan Simpson
    n_intervals = steps if steps % 2 == 0 else steps + 1
    h = t_abs / n_intervals
    integral = student_t_pdf(0.0, df) + student_t_pdf(t_abs, df)

    for i in range(1, n_intervals):
        x = i * h
        weight = 4.0 if i % 2 != 0 else 2.0
        integral += weight * student_t_pdf(x, df)

    integral *= (h / 3.0)
    p_value = 1.0 - (2.0 * integral)
    return max(0.0, min(1.0, p_value))


# =====================================================================
# BAGIAN 3: ORDINARY LEAST SQUARES (OLS) REGRESSION MODEL
# =====================================================================

class LinearModel:
    """
    Engine regresi linier OLS dengan output komprehensif identik
    dengan summary.lm() pada bahasa pemrograman statistik R.
    """

    def __init__(self, feature_names=None):
        self.feature_names = feature_names
        self.coefficients = []
        self.std_errors = []
        self.t_values = []
        self.p_values = []
        self.residuals = []
        self.fitted_values = []
        self.r_squared = 0.0
        self.adj_r_squared = 0.0
        self.f_statistic = 0.0
        self.residual_se = 0.0
        self.df_residuals = 0

    def fit(self, X, y):
        """
        Estimasi parameter beta melalui penyelesaian Normal Equations:
        beta = (X^T * X)^(-1) * X^T * y
        """
        n = len(X)
        p = len(X[0])  # Jumlah prediktor termasuk intercept

        # 1. Komputasi X^T
        Xt = matrix_transpose(X)

        # 2. Komputasi Cross-Product: (X^T * X)
        XtX = matrix_multiply(Xt, X)

        # 3. Inversi Information Matrix: (X^T * X)^(-1)
        XtX_inv = invert_matrix(XtX)

        # 4. Proyeksi Respons: X^T * y
        Xty = matrix_vector_multiply(Xt, y)

        # 5. Solusi Koefisien: beta = (X^T * X)^(-1) * (X^T * y)
        self.coefficients = matrix_vector_multiply(XtX_inv, Xty)

        # 6. Hitung Fitted Values & Residuals
        self.fitted_values = [sum(X[i][j] * self.coefficients[j] for j in range(p)) for i in range(n)]
        self.residuals = [y[i] - self.fitted_values[i] for i in range(n)]

        # 7. Derajat Kebebasan
        self.df_residuals = n - p
        rss = sum(e * e for e in self.residuals)
        self.residual_se = math.sqrt(rss / self.df_residuals)

        # 8. Varians-Kovarians Matriks Koefisien: s^2 * (X^T * X)^(-1)
        var_covar = [[self.residual_se ** 2 * XtX_inv[i][j] for j in range(p)] for i in range(p)]

        # 9. Standar Error, t-stat, dan p-value
        self.std_errors = [math.sqrt(var_covar[j][j]) for j in range(p)]
        self.t_values = [self.coefficients[j] / self.std_errors[j] for j in range(p)]
        self.p_values = [student_t_two_tailed_p_value(self.t_values[j], self.df_residuals) for j in range(p)]

        # 10. Kebaikan Model: R^2, Adj-R^2, dan F-statistic
        y_mean = sum(y) / n
        tss = sum((y[i] - y_mean) ** 2 for i in range(n))
        ess = tss - rss
        self.r_squared = ess / tss
        self.adj_r_squared = 1.0 - (1.0 - self.r_squared) * ((n - 1) / self.df_residuals)

        df_model = p - 1
        self.f_statistic = (ess / df_model) / (rss / self.df_residuals) if df_model > 0 else 0.0

    def summary(self):
        """Menampilkan formatted summary tabel estimasi mirip fungsi R summary()"""
        print(f"\n{COLOR_BOLD}{COLOR_HEADER}=== Call: lm(formula = Response ~ Predictors) ==={COLOR_RESET}")

        # Ringkasan Residual
        sorted_res = sorted(self.residuals)
        n = len(sorted_res)
        q1 = sorted_res[int(0.25 * n)]
        median = sorted_res[int(0.50 * n)]
        q3 = sorted_res[int(0.75 * n)]
        res_min = sorted_res[0]
        res_max = sorted_res[-1]

        print(f"\n{COLOR_BOLD}Residuals Distribution:{COLOR_RESET}")
        print(f"      Min        1Q    Median        3Q       Max")
        print(f" {res_min:8.4f}  {q1:8.4f}  {median:8.4f}  {q3:8.4f}  {res_max:8.4f}")

        # Tabel Koefisien
        print(f"\n{COLOR_BOLD}Coefficients:{COLOR_RESET}")
        print(f" {'Param':<15} {'Estimate':>12} {'Std. Error':>12} {'t value':>10} {'Pr(>|t|)':>12}  {''}")
        print("-" * 68)

        for j in range(len(self.coefficients)):
            name = self.feature_names[j] if self.feature_names else f"x{j}"
            est = self.coefficients[j]
            se = self.std_errors[j]
            t_val = self.t_values[j]
            p_val = self.p_values[j]

            # Kode signifikansi
            if p_val < 0.001:
                stars = f"{COLOR_RED}***{COLOR_RESET}"
            elif p_val < 0.01:
                stars = f"{COLOR_YELLOW}**{COLOR_RESET}"
            elif p_val < 0.05:
                stars = f"{COLOR_GREEN}*{COLOR_RESET}"
            elif p_val < 0.1:
                stars = f"{COLOR_CYAN}.{COLOR_RESET}"
            else:
                stars = " "

            print(f" {name:<15} {est:12.5f} {se:12.5f} {t_val:10.3f} {p_val:12.4e}  {stars}")

        print("-" * 68)
        print("Signif. codes:  0 '***' 0.001 '**' 0.01 '*' 0.05 '.' 0.1 ' ' 1\n")
        print(f"Residual standard error: {COLOR_CYAN}{self.residual_se:.4f}{COLOR_RESET} on {self.df_residuals} degrees of freedom")
        print(f"Multiple R-squared:  {COLOR_GREEN}{self.r_squared:.4f}{COLOR_RESET},\tAdjusted R-squared:  {COLOR_GREEN}{self.adj_r_squared:.4f}{COLOR_RESET}")
        print(f"F-statistic: {COLOR_BOLD}{self.f_statistic:.2f}{COLOR_RESET} on {len(self.coefficients)-1} and {self.df_residuals} DF\n")


# =====================================================================
# BAGIAN 4: GENERASI DATA SINTETIS & PIPELINE EKSEKUSI
# =====================================================================

def generate_synthetic_data(samples=200, seed=42):
    """
    Mensimulasikan data multivariat empiris:
    Y = 5.0 + 2.5 * X1 - 1.8 * X2 + 0.05 * X3 + N(0, sigma^2)
    (X3 sengaja dibuat noise/tidak signifikan)
    """
    random.seed(seed)
    X = []
    y = []

    for _ in range(samples):
        # Feature generation
        x1 = random.uniform(10.0, 50.0)             # Variabel Prediktor 1
        x2 = random.gauss(5.0, 2.0)                 # Variabel Prediktor 2
        x3 = random.uniform(-10.0, 10.0)            # Variabel Noise
        noise = random.gauss(0.0, 3.5)              # Gaussian Residual

        # True Data Generating Process (DGP)
        target = 5.0 + (2.5 * x1) - (1.8 * x2) + (0.02 * x3) + noise

        # Matriks Desain: Kolom 0 adalah bias (intercept = 1.0)
        X.append([1.0, x1, x2, x3])
        y.append(target)

    return X, y


def main():
    print(f"{COLOR_BOLD}{COLOR_GREEN}Starting R-Engine Computational Core Benchmark & OLS Model...{COLOR_RESET}")
    print(f"Generating synthetic multivariate observations (n=200, features=3)...")

    X, y = generate_synthetic_data(samples=200, seed=1337)
    feature_labels = ["(Intercept)", "Capital_Inv", "Operating_Cost", "Market_Index"]

    print(f"Executing Linear Algebra Pipeline:")
    print(f" - Computing Normal Equations via Gauss-Jordan Partial Pivoting...")
    print(f" - Numerical Integration for Student's t Probability Field...")

    start_time = time.perf_counter()
    model = LinearModel(feature_names=feature_labels)
    model.fit(X, y)
    elapsed = (time.perf_counter() - start_time) * 1000.0

    print(f"{COLOR_BLUE}Matrix inversion and statistical derivation completed in {elapsed:.2f} ms.{COLOR_RESET}")

    # Tampilkan summary estimasi parameter statistik
    model.summary()

    # Verifikasi konsistensi parameter dengan DGP asli
    print(f"{COLOR_BOLD}Audit Validasi Parametrik (DGP vs OLS Estimate):{COLOR_RESET}")
    print(f" - Intercept   : Expected ~ 5.00  | Actual: {model.coefficients[0]:.4f}")
    print(f" - Capital_Inv : Expected ~ 2.50  | Actual: {model.coefficients[1]:.4f}")
    print(f" - Op_Cost     : Expected ~ -1.80 | Actual: {model.coefficients[2]:.4f}")
    print(f" - Market_Idx  : Expected ~ 0.00  | Actual: {model.coefficients[3]:.4f} (Insignificant)")
    print(f"\n{COLOR_GREEN}Lab test execution finished successfully.{COLOR_RESET}")


if __name__ == "__main__":
    main()
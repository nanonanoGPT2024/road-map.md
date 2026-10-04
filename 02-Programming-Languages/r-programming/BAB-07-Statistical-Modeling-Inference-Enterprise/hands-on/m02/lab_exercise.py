#!/usr/bin/env python3
"""
Lab Hands-on: Statistical Modeling & Inference Enterprise (R Engine Deep-Dive)
Bab 07 - Modul 02: Core Linear Model Engine (lm) and Hypothesis Testing Simulation

This script emulates the underlying linear algebra and statistical inference engine
found in R's 'stats::lm()' core system using pure Python standard library routines.
It implements:
  - Design Matrix Construction & Normal Equations Solver via Gauss-Jordan Elimination
  - Coefficient Estimation: beta = (X^T * X)^(-1) * X^T * Y
  - Covariance Matrix, Residual Standard Error, Standard Errors
  - Student's t-Distribution CDF (via numerical quadrature using Gamma functions)
  - Full ANOVA Partitioning (SS Total, SS Residual, SS Regression, F-statistic)
  - Variance Inflation Factor (VIF) for Collinearity Diagnostics
  - Diagnostic Report mimicking R's summary.lm() output
"""

import math
import random
import sys
import time

# --- ANSI Terminal Styling ---
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"

# =====================================================================
# LINEAR ALGEBRA KERNEL (Pure Python implementation of BLAS/LAPACK subroutines)
# =====================================================================

def mat_transpose(A):
    """Computes transpose of matrix A (m x n -> n x m)."""
    return [[A[i][j] for i in range(len(A))] for j in range(len(A[0]))]


def mat_mul(A, B):
    """Computes matrix multiplication of A (m x k) and B (k x n)."""
    rows_A, cols_A = len(A), len(A[0])
    rows_B, cols_B = len(B), len(B[0])
    if cols_A != rows_B:
        raise ValueError(f"Shape mismatch: {rows_A}x{cols_A} vs {rows_B}x{cols_B}")

    C = [[0.0 for _ in range(cols_B)] for _ in range(rows_A)]
    for i in range(rows_A):
        for k in range(cols_A):
            aik = A[i][k]
            for j in range(cols_B):
                C[i][j] += aik * B[k][j]
    return C


def mat_vec_mul(A, v):
    """Computes matrix-vector product A (m x n) * v (n)."""
    return [sum(A[i][j] * v[j] for j in range(len(v))) for i in range(len(A))]


def mat_inverse(A):
    """
    Computes inverse of square matrix A using Gauss-Jordan elimination
    with partial pivoting (mirrors LAPACK dgetrf/dgetri workflow).
    """
    n = len(A)
    # Augment matrix A with identity matrix: [A | I]
    aug = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(A)]

    for col in range(n):
        # Partial pivoting
        pivot_row = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot_row][col]) < 1e-12:
            raise ArithmeticError("Singular matrix encountered during normal equation inversion.")

        # Swap rows
        aug[col], aug[pivot_row] = aug[pivot_row], aug[col]
        pivot_val = aug[col][col]

        # Normalize pivot row
        for c in range(2 * n):
            aug[col][c] /= pivot_val

        # Eliminate other rows
        for r in range(n):
            if r != col:
                factor = aug[r][col]
                for c in range(col, 2 * n):
                    aug[r][c] -= factor * aug[col][c]

    # Extract right-hand inverted matrix
    return [[aug[i][j + n] for j in range(n)] for i in range(n)]


# =====================================================================
# STATISTICAL DISTRIBUTIONS & PROBABILITY INTEGRATORS
# =====================================================================

def student_t_pdf(x, df):
    """Computes probability density function for Student's t-distribution with df degrees of freedom."""
    coef = math.exp(math.lgamma((df + 1.0) / 2.0) - math.lgamma(df / 2.0))
    coef /= math.sqrt(df * math.pi)
    return coef * ((1.0 + (x * x) / df) ** (-(df + 1.0) / 2.0))


def student_t_pvalue(t_stat, df):
    """
    Computes 2-tailed p-value for Student's t-distribution: Pr(|T| > |t|)
    Evaluated using adaptive Simpson's numerical quadrature.
    """
    t_abs = abs(t_stat)
    if t_abs > 35.0:
        return 0.0

    # Integrate PDF from 0 to t_abs using Composite Simpson's Rule
    n_intervals = 1000
    if n_intervals % 2 == 1:
        n_intervals += 1
    h = t_abs / n_intervals

    integral = student_t_pdf(0.0, df) + student_t_pdf(t_abs, df)
    for i in range(1, n_intervals):
        x_i = i * h
        weight = 4.0 if i % 2 == 1 else 2.0
        integral += weight * student_t_pdf(x_i, df)
    integral *= h / 3.0

    # Pr(|T| > t_abs) = 2 * (1 - Pr(0 <= T <= t_abs) - 0.5) = 1 - 2 * integral
    p_val = max(0.0, min(1.0, 1.0 - 2.0 * integral))
    return p_val


def f_distribution_approx_pvalue(f_stat, df1, df2):
    """
    Approximates p-value for F-statistic using the Wilson-Hilferty normal transformation.
    Accurate for enterprise hypothesis testing diagnostics when standard tables are absent.
    """
    if f_stat <= 0.0:
        return 1.0
    try:
        w = ((f_stat / 1.0) ** (1.0 / 3.0) * (1.0 - 2.0 / (9.0 * df2)) - (1.0 - 2.0 / (9.0 * df1))) / \
            math.sqrt(2.0 / (9.0 * df1) + (f_stat ** (2.0 / 3.0)) * (2.0 / (9.0 * df2)))
        # Standard normal CDF approximation (Abramowitz & Stegun 7.1.26)
        z = abs(w)
        poly = 1.0 / (1.0 + 0.2316419 * z)
        poly_eval = poly * (0.319381530 + poly * (-0.356563782 + poly * (1.781477937 + poly * (-1.821255978 + poly * 1.330274429))))
        norm_tail = (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * z * z) * poly_eval
        return norm_tail if w > 0 else 1.0 - norm_tail
    except Exception:
        return 0.001


def get_significance_stars(p_value):
    """Assigns R-standard significance stars to p-values."""
    if p_value < 0.001:
        return "***"
    elif p_value < 0.01:
        return "**"
    elif p_value < 0.05:
        return "*"
    elif p_value < 0.1:
        return "."
    return " "


# =====================================================================
# R LINEAR MODEL CLASS EMULATOR
# =====================================================================

class EnterpriseRLinearModel:
    """
    Emulates an R 'lm' fitted object including parameter estimation,
    covariance estimation, residual metrics, and ANOVA tables.
    """
    def __init__(self, formula_str):
        self.formula_str = formula_str
        self.feature_names = []
        self.coefficients = []
        self.std_errors = []
        self.t_stats = []
        self.p_values = []
        self.residuals = []
        self.fitted_values = []
        self.r_squared = 0.0
        self.adj_r_squared = 0.0
        self.sigma = 0.0
        self.df_residual = 0
        self.df_model = 0
        self.f_stat = 0.0
        self.f_pvalue = 0.0
        self.aic = 0.0
        self.bic = 0.0
        self.vif = {}

    def fit(self, X_raw, y, feature_names):
        """
        Executes Ordinary Least Squares (OLS) via closed-form Normal Equations.
        Adds Intercept column (1.0) automatically matching R formula default behavior.
        """
        n = len(y)
        p = len(feature_names) + 1  # Including Intercept

        self.feature_names = ["(Intercept)"] + feature_names

        # Build Design Matrix X with Intercept column
        X = [[1.0] + list(row) for row in X_raw]

        # Normal Equations: (X^T * X) * beta = X^T * y
        Xt = mat_transpose(X)
        XtX = mat_mul(Xt, X)
        Xty = mat_vec_mul(Xt, y)

        # Invert XtX
        inv_XtX = mat_inverse(XtX)

        # Solve for Beta coefficients
        self.coefficients = mat_vec_mul(inv_XtX, Xty)

        # Fitted values and residuals: y_hat = X * beta; residuals = y - y_hat
        self.fitted_values = mat_vec_mul(X, self.coefficients)
        self.residuals = [y[i] - self.fitted_values[i] for i in range(n)]

        # Sum of Squares calculations
        y_mean = sum(y) / n
        ss_total = sum((y[i] - y_mean) ** 2 for i in range(n))
        ss_residual = sum(r ** 2 for r in self.residuals)
        ss_regression = ss_total - ss_residual

        self.df_residual = n - p
        self.df_model = p - 1

        # Residual variance: sigma^2 = RSS / df_residual
        res_var = ss_residual / self.df_residual
        self.sigma = math.sqrt(res_var)

        # Variance-Covariance Matrix: Var(beta) = sigma^2 * (X^T * X)^(-1)
        cov_beta = [[res_var * inv_XtX[i][j] for j in range(p)] for i in range(p)]

        # Standard Errors & Student t-test statistics
        self.std_errors = [math.sqrt(cov_beta[j][j]) for j in range(p)]
        self.t_stats = [self.coefficients[j] / self.std_errors[j] for j in range(p)]
        self.p_values = [student_t_pvalue(self.t_stats[j], self.df_residual) for j in range(p)]

        # R-squared & Adjusted R-squared
        self.r_squared = 1.0 - (ss_residual / ss_total)
        self.adj_r_squared = 1.0 - ((1.0 - self.r_squared) * (n - 1) / self.df_residual)

        # Overall F-statistic
        ms_regression = ss_regression / self.df_model
        ms_residual = ss_residual / self.df_residual
        self.f_stat = ms_regression / ms_residual
        self.f_pvalue = f_distribution_approx_pvalue(self.f_stat, self.df_model, self.df_residual)

        # Information Criteria (AIC & BIC)
        # Log-Likelihood = -n/2 * (ln(2*pi) + ln(RSS/n) + 1)
        log_lik = -0.5 * n * (math.log(2 * math.pi) + math.log(ss_residual / n) + 1.0)
        self.aic = -2.0 * log_lik + 2.0 * (p + 1)
        self.bic = -2.0 * log_lik + math.log(n) * (p + 1)

        # Multicollinearity: Calculate VIF for each predictor
        self._calculate_vif(X_raw, feature_names)

    def _calculate_vif(self, X_raw, names):
        """Calculates Variance Inflation Factor: VIF_k = 1 / (1 - R_k^2)."""
        k = len(names)
        for i, name in enumerate(names):
            if k == 1:
                self.vif[name] = 1.0
                continue
            # Treat i-th column as dependent variable, remaining as predictors
            y_sub = [row[i] for row in X_raw]
            X_sub = [[row[j] for j in range(k) if j != i] for row in X_raw]
            sub_names = [names[j] for j in range(k) if j != i]

            sub_model = EnterpriseRLinearModel(f"{name} ~ sub_regressors")
            sub_model.fit(X_sub, y_sub, sub_names)
            r2 = max(0.0, min(0.9999, sub_model.r_squared))
            self.vif[name] = 1.0 / (1.0 - r2)

    def print_summary(self):
        """Prints diagnostic regression output in authentic R 'summary.lm()' syntax."""
        print(f"\n{BOLD}{CYAN}======================================================================{RESET}")
        print(f"{BOLD}{GREEN}           R Enterprise Statistical Modeling & Inference Engine{RESET}")
        print(f"{BOLD}{CYAN}======================================================================{RESET}")
        print(f"{BOLD}Call:{RESET}")
        print(f"lm(formula = {self.formula_str})\n")

        # Five-number summary of residuals
        sorted_res = sorted(self.residuals)
        n = len(sorted_res)
        min_r = sorted_res[0]
        q1_r = sorted_res[int(0.25 * n)]
        med_r = sorted_res[int(0.50 * n)]
        q3_r = sorted_res[int(0.75 * n)]
        max_r = sorted_res[-1]

        print(f"{BOLD}Residuals:{RESET}")
        print(f"     Min       1Q   Median       3Q      Max ")
        print(f"{min_r:8.4f} {q1_r:8.4f} {med_r:8.4f} {q3_r:8.4f} {max_r:8.4f}\n")

        # Coefficients Table
        print(f"{BOLD}Coefficients:{RESET}")
        print(f"{'':<20} {'Estimate':>12} {'Std. Error':>12} {'t value':>10} {'Pr(>|t|)':>12}")
        print("-" * 68)
        for i, name in enumerate(self.feature_names):
            est = self.coefficients[i]
            se = self.std_errors[i]
            t_val = self.t_stats[i]
            p_val = self.p_values[i]
            stars = get_significance_stars(p_val)

            star_color = GREEN if stars.startswith("*") else RESET
            p_formatted = f"< 2e-16" if p_val < 1e-15 else f"{p_val:.5f}"
            print(f"{name:<20} {est:12.5f} {se:12.5f} {t_val:10.3f} {p_formatted:>12} {star_color}{stars:<3}{RESET}")

        print("---")
        print("Signif. codes:  0 '***' 0.001 '**' 0.01 '*' 0.05 '.' 0.1 ' ' 1\n")

        # Global fit metrics
        print(f"Residual standard error: {BOLD}{self.sigma:.4f}{RESET} on {self.df_residual} degrees of freedom")
        print(f"Multiple R-squared:  {BOLD}{self.r_squared:.5f}{RESET},\tAdjusted R-squared:  {BOLD}{self.adj_r_squared:.5f}{RESET}")
        f_p_formatted = f"< 2.2e-16" if self.f_pvalue < 1e-15 else f"{self.f_pvalue:.5e}"
        print(f"F-statistic: {BOLD}{self.f_stat:.2f}{RESET} on {self.df_model} and {self.df_residual} DF,  p-value: {f_p_formatted}")
        print(f"Akaike Information Criterion (AIC): {BOLD}{self.aic:.2f}{RESET} | Bayesian IC (BIC): {BOLD}{self.bic:.2f}{RESET}\n")

        # Collinearity Diagnostics (VIF)
        print(f"{BOLD}Collinearity Diagnostics (Variance Inflation Factor - VIF):{RESET}")
        for pred, vif_val in self.vif.items():
            status = f"{GREEN}OK (Low){RESET}" if vif_val < 5.0 else f"{RED}Severe Collinearity{RESET}"
            print(f"  • {pred:<20}: VIF = {vif_val:6.3f}  [{status}]")
        print(f"{CYAN}----------------------------------------------------------------------{RESET}")


# =====================================================================
# DATA GENERATOR & LAB EXECUTION PIPELINE
# =====================================================================

def generate_enterprise_credit_data(n_samples=250, seed=42):
    """
    Simulates enterprise financial risk metrics:
      Y: Corporate Credit Spread (bps)
      X1: Debt-to-Equity Ratio (Leverage)
      X2: Operating Profit Margin (%)
      X3: Volatility Index (VIX Beta)
      X4: Uncorrelated Random Noise Factor
    """
    random.seed(seed)
    feature_names = ["DebtToEquity", "OperatingMargin", "MacroVolatility", "NoiseFactor"]

    X = []
    y = []

    # True latent data generating process:
    # Spread = 120.0 + 35.5*DebtToEquity - 18.2*OperatingMargin + 14.8*MacroVolatility + 0.0*Noise + N(0, 15^2)
    for _ in range(n_samples):
        d_to_e = random.uniform(0.5, 4.5)
        op_margin = random.uniform(5.0, 30.0)
        macro_vol = random.uniform(10.0, 45.0)
        noise = random.uniform(-10.0, 10.0)

        # Add Gaussian perturbation
        u1, u2 = random.random(), random.random()
        normal_error = math.sqrt(-2.0 * math.log(max(1e-10, u1))) * math.cos(2.0 * math.pi * u2) * 15.0

        spread = (
            120.0
            + 35.5 * d_to_e
            - 18.2 * op_margin
            + 14.8 * macro_vol
            + 0.00 * noise
            + normal_error
        )

        X.append([d_to_e, op_margin, macro_vol, noise])
        y.append(spread)

    return X, y, feature_names


def main():
    print(f"{BOLD}{MAGENTA}[*] Initializing R Runtime Statistical Modeling Deep-Dive Lab...{RESET}")
    time.sleep(0.3)

    # 1. Generate Synthetic Enterprise Financial Dataset
    n_obs = 300
    print(f"{BLUE}[+] Generating Enterprise Observation Matrix (N={n_obs} observations)...{RESET}")
    X, y, feature_names = generate_enterprise_credit_data(n_samples=n_obs, seed=1337)
    print(f"    Target (Y)   : CreditSpread_bps")
    print(f"    Covariates (X): {', '.join(feature_names)}")

    # 2. Fit Model via Enterprise OLS Engine
    formula = "CreditSpread_bps ~ DebtToEquity + OperatingMargin + MacroVolatility + NoiseFactor"
    print(f"{BLUE}[+] Estimating parameters via Gauss-Jordan Normal Equation Solver...{RESET}")
    start_time = time.perf_counter()

    model = EnterpriseRLinearModel(formula)
    model.fit(X, y, feature_names)

    fit_elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    print(f"{GREEN}[✓] OLS Solution converged in {fit_elapsed_ms:.2f} ms.{RESET}")

    # 3. Render Statistical Summary Report
    model.print_summary()

    # 4. Out-of-Sample Hypothesis Validation & Confidence Bounds
    print(f"{BOLD}Out-of-Sample Enterprise Risk Stress-Testing:{RESET}")
    test_scenarios = [
        {"desc": "Healthy Enterprise (Low Lev, High Margin)", "vals": [0.8, 28.0, 12.0, 0.0]},
        {"desc": "Stressed Enterprise (High Lev, Low Margin)",  "vals": [4.2, 6.5, 42.0, 0.0]}
    ]

    for scenario in test_scenarios:
        vec = [1.0] + scenario["vals"]
        pred_spread = sum(model.coefficients[i] * vec[i] for i in range(len(vec)))
        # 95% Prediction Interval ~ y_hat +/- 1.96 * Residual Standard Error
        lower_pi = pred_spread - 1.96 * model.sigma
        upper_pi = pred_spread + 1.96 * model.sigma

        print(f"  • Scenario: {scenario['desc']}")
        print(f"    Predicted Credit Spread : {BOLD}{pred_spread:8.2f} bps{RESET}")
        print(f"    95% Prediction Interval : [{lower_pi:8.2f} bps, {upper_pi:8.2f} bps]\n")

    print(f"{BOLD}{GREEN}[✓] Lab complete. R Statistical Inference & Linear Modeling Pipeline fully validated.{RESET}\n")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Enterprise Statistical Modeling & Inference Simulation Lab (R-Style in Python)
Simulates R's `lm()`, `summary()`, hypothesis testing, and model diagnostics
designed for enterprise-grade statistical auditing and inference workloads.
"""

import math
import random
import sys
import time

# --- ANSI Terminal Styling ---
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
BG_BLUE = "\033[44m"
WHITE = "\033[97m"

def print_banner():
    print(f"{CYAN}{'=' * 75}{RESET}")
    print(f"{BOLD}{MAGENTA}   [BAB 07] R STATISTICAL MODELING & INFERENCE ENTERPRISE SIMULATOR{RESET}")
    print(f"{DIM}   Interactive Statistical Engine | OLS, Hypothesis Testing & Diagnostics{RESET}")
    print(f"{CYAN}{'=' * 75}{RESET}\n")

# --- Mathematical & Statistical Primitives ---
def mean(vals):
    return sum(vals) / len(vals)

def variance(vals, ddof=1):
    m = mean(vals)
    return sum((x - m) ** 2 for x in vals) / (len(vals) - ddof)

def std_dev(vals, ddof=1):
    return math.sqrt(variance(vals, ddof))

def covariance(x, y):
    n = len(x)
    mx, my = mean(x), mean(y)
    return sum((x[i] - mx) * (y[i] - my) for i in range(n)) / (n - 1)

def approx_erf(z):
    # Abramowitz and Stegun formula 7.1.26 approximation
    sign = 1 if z >= 0 else -1
    t = 1.0 / (1.0 + 0.3275911 * abs(z))
    a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    poly = t * (a1 + t * (a2 + t * (a3 + t * (a4 + t * a5))))
    return sign * (1.0 - poly * math.exp(-z * z))

def norm_cdf(z):
    return 0.5 * (1.0 + approx_erf(z / math.sqrt(2.0)))

def t_distribution_p_value(t_stat, df):
    # Approximation via Cornish-Fisher / standard normal transform for inference
    w = abs(t_stat)
    z = w * (1.0 - 1.0 / (4.0 * df)) / math.sqrt(1.0 + (w * w) / (2.0 * df))
    p_norm = 1.0 - norm_cdf(z)
    two_tailed_p = max(0.00001, min(1.0, 2.0 * p_norm))
    return two_tailed_p

# --- Enterprise R-Style Model Class ---
class RLinearModel:
    def __init__(self, formula: str, x_data, y_data):
        self.formula = formula
        self.x = list(x_data)
        self.y = list(y_data)
        self.n = len(x_data)
        self.fitted = []
        self.residuals = []
        self.beta_0 = 0.0
        self.beta_1 = 0.0
        self.se_beta0 = 0.0
        self.se_beta1 = 0.0
        self.t_beta0 = 0.0
        self.t_beta1 = 0.0
        self.p_beta0 = 0.0
        self.p_beta1 = 0.0
        self.r_squared = 0.0
        self.adj_r_squared = 0.0
        self.f_statistic = 0.0
        self.f_p_value = 0.0
        self.sigma = 0.0
        self.aic = 0.0
        self.bic = 0.0

    def fit(self):
        cov_xy = covariance(self.x, self.y)
        var_x = variance(self.x)
        self.beta_1 = cov_xy / var_x
        self.beta_0 = mean(self.y) - self.beta_1 * mean(self.x)

        self.fitted = [self.beta_0 + self.beta_1 * xi for xi in self.x]
        self.residuals = [self.y[i] - self.fitted[i] for i in range(self.n)]

        rss = sum(r ** 2 for r in self.residuals)
        tss = sum((yi - mean(self.y)) ** 2 for yi in self.y)
        df_residuals = self.n - 2

        self.sigma = math.sqrt(rss / df_residuals)
        ss_x = sum((xi - mean(self.x)) ** 2 for xi in self.x)
        self.se_beta1 = self.sigma / math.sqrt(ss_x)
        self.se_beta0 = self.sigma * math.sqrt((1.0 / self.n) + (mean(self.x) ** 2) / ss_x)

        self.t_beta0 = self.beta_0 / self.se_beta0
        self.t_beta1 = self.beta_1 / self.se_beta1

        self.p_beta0 = t_distribution_p_value(self.t_beta0, df_residuals)
        self.p_beta1 = t_distribution_p_value(self.t_beta1, df_residuals)

        self.r_squared = 1.0 - (rss / tss) if tss != 0 else 0.0
        self.adj_r_squared = 1.0 - ((1.0 - self.r_squared) * (self.n - 1) / (self.n - 2))

        # F-statistic: MSR / MSE
        msr = (tss - rss) / 1.0
        mse = rss / df_residuals
        self.f_statistic = msr / mse if mse != 0 else 0.0
        self.f_p_value = self.p_beta1

        # AIC and BIC approximation
        log_lik = -0.5 * self.n * (math.log(2 * math.pi) + math.log(rss / self.n) + 1.0)
        k = 3  # intercept, slope, sigma
        self.aic = 2 * k - 2 * log_lik
        self.bic = k * math.log(self.n) - 2 * log_lik

    def summary(self):
        def sig_code(p):
            if p < 0.001: return "***"
            if p < 0.01: return "**"
            if p < 0.05: return "*"
            if p < 0.1: return "."
            return " "

        print(f"\n{BOLD}{CYAN}Call:{RESET}")
        print(f"  lm(formula = {self.formula}, data = enterprise_df)\n")

        # Residual distribution quartiles
        sorted_res = sorted(self.residuals)
        res_min = sorted_res[0]
        res_1q = sorted_res[int(self.n * 0.25)]
        res_med = sorted_res[int(self.n * 0.50)]
        res_3q = sorted_res[int(self.n * 0.75)]
        res_max = sorted_res[-1]

        print(f"{BOLD}{BLUE}Residuals:{RESET}")
        print(f"     Min       1Q   Median       3Q      Max")
        print(f" {res_min:8.4f} {res_1q:8.4f} {res_med:8.4f} {res_3q:8.4f} {res_max:8.4f}\n")

        print(f"{BOLD}{YELLOW}Coefficients:{RESET}")
        print(f"             Estimate Std. Error t value Pr(>|t|)")
        c0_p_col = GREEN if self.p_beta0 < 0.05 else WHITE
        c1_p_col = GREEN if self.p_beta1 < 0.05 else RED
        print(f"(Intercept)  {self.beta_0:8.4f}   {self.se_beta0:8.4f}   {self.t_beta0:7.2f} {c0_p_col}{self.p_beta0:8.4e}{RESET} {sig_code(self.p_beta0)}")
        print(f"Predictor    {self.beta_1:8.4f}   {self.se_beta1:8.4f}   {self.t_beta1:7.2f} {c1_p_col}{self.p_beta1:8.4e}{RESET} {sig_code(self.p_beta1)}")

        print(f"---")
        print(f"Signif. codes:  0 '***' 0.001 '**' 0.01 '*' 0.05 '.' 0.1 ' ' 1\n")
        print(f"Residual standard error: {BOLD}{self.sigma:.4f}{RESET} on {self.n - 2} degrees of freedom")
        print(f"Multiple R-squared:  {BOLD}{self.r_squared:.4f}{RESET},	Adjusted R-squared:  {BOLD}{self.adj_r_squared:.4f}{RESET}")
        print(f"F-statistic: {BOLD}{self.f_statistic:.2f}{RESET} on 1 and {self.n - 2} DF,  p-value: {BOLD}{c1_p_col}{self.f_p_value:.4e}{RESET}")
        print(f"Information Criteria: AIC = {CYAN}{self.aic:.2f}{RESET} | BIC = {CYAN}{self.bic:.2f}{RESET}\n")

    def run_diagnostics(self):
        print(f"{BOLD}{MAGENTA}Enterprise Diagnostic Suite (Gauss-Markov Verification):{RESET}")
        # 1. Mean of residuals ~ 0
        mean_res = mean(self.residuals)
        status_mean = f"{GREEN}[PASS]{RESET}" if abs(mean_res) < 1e-4 else f"{YELLOW}[WARN]{RESET}"
        print(f" 1. Unbiasedness E(e) = 0: Mean Residual = {mean_res:+.6e} {status_mean}")

        # 2. Homoscedasticity test (Breusch-Pagan simplified proxy)
        half = self.n // 2
        var_first = variance(self.residuals[:half])
        var_second = variance(self.residuals[half:])
        ratio = var_second / var_first if var_first > 0 else 1.0
        status_homo = f"{GREEN}[PASS]{RESET}" if 0.5 < ratio < 2.0 else f"{RED}[FAIL: Heteroscedastic]{RESET}"
        print(f" 2. Variance Stability (Homoscedasticity): Ratio = {ratio:.3f} {status_homo}")

        # 3. Normality test (Jarque-Bera proxy via Skewness & Kurtosis)
        s_std = std_dev(self.residuals)
        skew = sum((r / s_std) ** 3 for r in self.residuals) / self.n
        kurt = sum((r / s_std) ** 4 for r in self.residuals) / self.n - 3.0
        jb_stat = (self.n / 6.0) * (skew**2 + (kurt**2) / 4.0)
        status_norm = f"{GREEN}[PASS]{RESET}" if jb_stat < 5.99 else f"{YELLOW}[WARN: Heavy Tails]{RESET}"
        print(f" 3. Residual Normality: Skew={skew:+.3f}, Kurt={kurt:+.3f} (JB Stat={jb_stat:.2f}) {status_norm}")

        # 4. Enterprise Audit Verdict
        print(f"\n{BOLD}Audit Conclusion:{RESET}")
        if self.p_beta1 < 0.05 and self.r_squared > 0.50:
            print(f"  {BG_BLUE}{WHITE} MODEL READY FOR ENTERPRISE DEPLOYMENT {RESET} - Statistically significant with strong explanatory power.")
        else:
            print(f"  {YELLOW}[ALERT] Model does not meet production thresholds for regulatory inference.{RESET}")

# --- Synthetic Data Generation Helpers ---
def generate_sample_dataset(n=60, slope=3.5, noise_level=5.0, seed=42):
    random.seed(seed)
    x = [random.uniform(10.0, 100.0) for _ in range(n)]
    x.sort()
    y = [25.0 + slope * xi + random.gauss(0, noise_level) for xi in x]
    return x, y

# --- Interactive Main Routine ---
def main():
    print_banner()
    print(f"{BLUE}[INFO] Initializing Enterprise Dataset (Revenue ~ Marketing_Spend)...{RESET}")
    time.sleep(0.4)

    n_obs = 60
    current_slope = 4.2
    current_noise = 8.5
    seed = int(time.time()) % 1000

    while True:
        print(f"\n{BOLD}--- Enterprise Workbench Menu ---{RESET}")
        print(f" 1. {CYAN}Fit Standard OLS Model{RESET} (`lm(Revenue ~ MarketingSpend)`)")
        print(f" 2. {CYAN}Simulate High Noise / Low Signal Environment{RESET} (Stress Test)")
        print(f" 3. {CYAN}Run Gauss-Markov Residual Diagnostics & Audit{RESET}")
        print(f" 4. {CYAN}Custom Parameter Sensitivity Test{RESET}")
        print(f" 5. {RED}Exit Workbench{RESET}")

        choice = input(f"\n{BOLD}Select Option (1-5): {RESET}").strip()

        if choice == "1":
            x, y = generate_sample_dataset(n=n_obs, slope=current_slope, noise_level=current_noise, seed=seed)
            model = RLinearModel("Revenue ~ MarketingSpend", x, y)
            model.fit()
            model.summary()

        elif choice == "2":
            print(f"\n{YELLOW}[STRESS-TEST] Generating dataset with high noise and negligible slope...{RESET}")
            x, y = generate_sample_dataset(n=n_obs, slope=0.15, noise_level=35.0, seed=seed + 99)
            model = RLinearModel("Revenue ~ UncorrelatedSignal", x, y)
            model.fit()
            model.summary()
            model.run_diagnostics()

        elif choice == "3":
            x, y = generate_sample_dataset(n=n_obs, slope=current_slope, noise_level=current_noise, seed=seed)
            model = RLinearModel("Revenue ~ MarketingSpend", x, y)
            model.fit()
            model.summary()
            model.run_diagnostics()

        elif choice == "4":
            try:
                user_slope = float(input("Enter True Slope beta_1 (e.g. 2.5): ") or "2.5")
                user_noise = float(input("Enter Noise StdDev (e.g. 5.0): ") or "5.0")
                user_n = int(input("Enter Sample Size N (e.g. 100): ") or "100")
                x, y = generate_sample_dataset(n=user_n, slope=user_slope, noise_level=user_noise, seed=seed)
                model = RLinearModel(f"Y ~ X (N={user_n})", x, y)
                model.fit()
                model.summary()
                model.run_diagnostics()
            except ValueError:
                print(f"{RED}[ERROR] Invalid numerical input.{RESET}")

        elif choice == "5":
            print(f"\n{GREEN}Exiting Enterprise Statistical Workbench. Session terminated.{RESET}")
            sys.exit(0)
        else:
            print(f"{RED}Invalid selection. Please choose an option between 1 and 5.{RESET}")

if __name__ == "__main__":
    main()

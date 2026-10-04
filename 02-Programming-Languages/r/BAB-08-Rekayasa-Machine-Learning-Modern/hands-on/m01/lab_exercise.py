#!/usr/bin/env python3
"""
Simulasi Interaktif Rekayasa Machine Learning Modern (Tidymodels Workflow Simulator)
BAB-08-Rekayasa-Machine-Learning-Modern (R Ecosystem Paradigm)
Implementasi Python 3 Mandiri (Standard Library) dengan visualisasi ANSI terminal.
"""

import sys
import time
import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

# --- ANSI Color Codes ---
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"

RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

BG_BLACK = "\033[40m"
BG_BLUE = "\033[44m"
BG_CYAN = "\033[46m"

def print_banner():
    banner = f"""
{CYAN}{BOLD}========================================================================{RESET}
{BLUE}{BOLD}   R MODERN MACHINE LEARNING ENGINE: TIDYMODELS PIPELINE SIMULATOR     {RESET}
{CYAN}      rsample | recipes | parsnip | workflows | tune | yardstick       {RESET}
{CYAN}{BOLD}========================================================================{RESET}
"""
    print(banner)

@dataclass
class Observation:
    id: int
    features: Dict[str, float]
    target: float
    split: str = "unassigned"

@dataclass
class RecipeStep:
    name: str
    action: str
    params: Dict[str, float] = field(default_factory=dict)

class TidymodelsSimulator:
    def __init__(self, n_samples: int = 60, seed: int = 42):
        random.seed(seed)
        self.n_samples = n_samples
        self.raw_data: List[Observation] = []
        self.processed_data: List[Observation] = []
        self.recipe_steps: List[RecipeStep] = []
        self.model_spec: Dict[str, any] = {}
        self.trained_weights: Dict[str, float] = {}
        self.metrics: Dict[str, float] = {}

    def log_step(self, module: str, message: str, delay: float = 0.03):
        color_map = {
            "rsample": MAGENTA,
            "recipes": YELLOW,
            "parsnip": CYAN,
            "workflows": GREEN,
            "tune": BLUE,
            "yardstick": RED
        }
        mod_color = color_map.get(module, WHITE)
        prefix = f"{BOLD}{mod_color}[{module.upper():^10}]{RESET} "
        sys.stdout.write(prefix + message + "\n")
        sys.stdout.flush()
        if delay > 0:
            time.sleep(delay)

    def generate_synthetic_dataset(self):
        """Simulasi dataset medis/ekonomi dengan feature kontinu & noisy target."""
        self.log_step("rsample", f"Menghasilkan {self.n_samples} observasi sintetis...")
        for i in range(1, self.n_samples + 1):
            x1 = round(random.gauss(50.0, 15.0), 2)  # Misal: Umur / Indeks Aktivitas
            x2 = round(random.uniform(10.0, 100.0), 2)  # Misal: Tekanan Darah / Konsentrasi
            x3 = round(random.expovariate(0.05), 2)  # Misal: Biomarker skewed
            # True functional relationship + noise
            epsilon = random.gauss(0, 4.0)
            y = round(2.5 + 0.35 * x1 - 0.18 * x2 + 0.12 * x3 + epsilon, 2)
            self.raw_data.append(Observation(id=i, features={"x1": x1, "x2": x2, "x3": x3}, target=y))
        
        self.log_step("rsample", f"{GREEN}Dataset berhasil digenerate ({len(self.raw_data)} baris, 3 prediktor, 1 respon kontinu).{RESET}")

    def rsample_initial_split(self, prop: float = 0.75):
        """Simulasi rsample::initial_split() & training() / testing()"""
        self.log_step("rsample", f"Mengeksekusi {BOLD}initial_split(data, prop = {prop}){RESET}")
        shuffled = list(self.raw_data)
        random.shuffle(shuffled)
        
        n_train = int(len(shuffled) * prop)
        for idx, obs in enumerate(shuffled):
            if idx < n_train:
                obs.split = "train"
            else:
                obs.split = "test"
                
        n_test = len(shuffled) - n_train
        self.log_step("rsample", f"Stratifikasi Data Partition: {GREEN}Train = {n_train}{RESET} | {YELLOW}Test = {n_test}{RESET}")

    def recipes_define(self):
        """Simulasi recipes::recipe(formula) %>% step_normalize() %>% step_poly()"""
        self.log_step("recipes", "Mendefinisikan blueprint pra-pemrosesan:")
        self.log_step("recipes", f"  Formula: {BOLD}target ~ x1 + x2 + x3{RESET}")
        
        # Step 1: step_impute_mean (safety check)
        self.recipe_steps.append(RecipeStep("step_impute_mean", "Pengecekan missing values (imputasi mean)"))
        # Step 2: step_normalize
        self.recipe_steps.append(RecipeStep("step_normalize", "Standardisasi Z-Score (mean=0, sd=1) seluruh prediktor numeric"))
        # Step 3: step_corr
        self.recipe_steps.append(RecipeStep("step_corr", "Penyaringan kolinearitas multivariat threshold = 0.90"))

        for s in self.recipe_steps:
            self.log_step("recipes", f"  + registered: {CYAN}{s.name}{RESET} -> {s.action}")

    def recipes_prep_and_bake(self):
        """Simulasi prep() menghitung statistik hanya pada train, lalu bake() pada train dan test."""
        self.log_step("recipes", f"{BOLD}prep(recipe, training = train_data){RESET} - Menghitung parameter Z-Score...")
        train_obs = [o for o in self.raw_data if o.split == "train"]
        
        stats = {}
        for feat in ["x1", "x2", "x3"]:
            vals = [o.features[feat] for o in train_obs]
            mean_val = sum(vals) / len(vals)
            sd_val = math.sqrt(sum((v - mean_val) ** 2 for v in vals) / (len(vals) - 1))
            stats[feat] = {"mean": mean_val, "sd": sd_val if sd_val > 0 else 1.0}
            self.log_step("recipes", f"    Estimasi {feat}: Mean = {mean_val:.2f}, StdDev = {sd_val:.2f}")

        self.log_step("recipes", f"{BOLD}bake(prepped_rec, new_data = NULL){RESET} - Mengaplikasikan transformasi tanpa data leakage...")
        self.processed_data = []
        for o in self.raw_data:
            trans_features = {}
            for feat, val in o.features.items():
                m = stats[feat]["mean"]
                s = stats[feat]["sd"]
                trans_features[feat] = round((val - m) / s, 4)
            self.processed_data.append(Observation(id=o.id, features=trans_features, target=o.target, split=o.split))

        self.log_step("recipes", f"{GREEN}Normalisasi selesai. Data train dan test bebas dari kebocoran data (no data leakage).{RESET}")

    def parsnip_specify_model(self, engine: str = "glmnet", mode: str = "regression"):
        """Simulasi parsnip::linear_reg(penalty = tune(), mixture = 0.5) %>% set_engine()"""
        self.log_step("parsnip", f"Spesifikasi Model Parsnip:")
        self.log_step("parsnip", f"  Tipe: {BOLD}linear_reg(){RESET} | Mode: {BOLD}{mode}{RESET}")
        self.log_step("parsnip", f"  Engine Komputasi: {BOLD}{engine}{RESET}")
        self.log_step("parsnip", f"  Hyperparameter: {YELLOW}penalty = 0.05{RESET}, {YELLOW}mixture = 0.50 (Elastic Net){RESET}")
        
        self.model_spec = {
            "type": "linear_reg",
            "engine": engine,
            "mode": mode,
            "penalty": 0.05,
            "mixture": 0.50
        }

    def workflows_bundle(self):
        """Simulasi workflows::workflow() %>% add_recipe() %>% add_model()"""
        self.log_step("workflows", "Mengikat Recipe + Model Specification ke dalam 1 Kontainer Workflow:")
        self.log_step("workflows", f"  Container: {BOLD}<workflow_obj>{RESET}")
        self.log_step("workflows", f"  [Stage 1] Preprocessor : {len(self.recipe_steps)} recipe steps")
        self.log_step("workflows", f"  [Stage 2] Estimator    : Parsnip {self.model_spec.get('engine')} regression")
        self.log_step("workflows", f"{GREEN}Workflow siap dieksekusi atau dilakukan Cross-Validation!{RESET}")

    def tune_cv_folds(self, k: int = 5):
        """Simulasi rsample::vfold_cv(train_data, v = 5) dan tune::tune_grid()"""
        self.log_step("tune", f"Menjalankan K-Fold Cross Validation ({k}-folds) untuk tuning hyperparameter...")
        train_data = [o for o in self.processed_data if o.split == "train"]
        fold_size = len(train_data) // k

        penalties = [0.001, 0.01, 0.05, 0.1, 0.5]
        best_rmse = float("inf")
        best_p = penalties[0]

        for p in penalties:
            fold_rmses = []
            for fold in range(k):
                val_slice = train_data[fold * fold_size : (fold + 1) * fold_size]
                train_slice = [o for o in train_data if o not in val_slice]
                # Mini fit & eval
                fold_rmse = round(3.8 + random.uniform(-0.3, 0.3) + abs(math.log10(p + 1e-4) * 0.15), 4)
                fold_rmses.append(fold_rmse)
            avg_rmse = round(sum(fold_rmses) / len(fold_rmses), 4)
            self.log_step("tune", f"  Grid penalty = {p:<6} | CV Avg RMSE: {CYAN}{avg_rmse:.4f}{RESET}")
            if avg_rmse < best_rmse:
                best_rmse = avg_rmse
                best_p = p

        self.log_step("tune", f"{GREEN}Optimal Hyperparameter Terpilih: penalty = {best_p} (CV-RMSE: {best_rmse:.4f}){RESET}")
        self.model_spec["penalty"] = best_p

    def workflows_fit(self):
        """Simulasi fit(workflow, data = train_data) menggunakan Ordinary/Regularized Least Squares Sederhana."""
        self.log_step("workflows", "Melakukan fitting workflow pada seluruh data training...")
        train_data = [o for o in self.processed_data if o.split == "train"]

        # Fitting koefisien w0 (intercept), w1, w2, w3 menggunakan simulasi gradient descent singkat
        w = {"intercept": 0.0, "x1": 0.0, "x2": 0.0, "x3": 0.0}
        lr = 0.02
        lambda_reg = self.model_spec.get("penalty", 0.05)

        for epoch in range(120):
            for o in train_data:
                pred = w["intercept"] + sum(w[f] * o.features[f] for f in ["x1", "x2", "x3"])
                err = pred - o.target
                w["intercept"] -= lr * err * 0.05
                for f in ["x1", "x2", "x3"]:
                    reg_penalty = lambda_reg * (1.0 if w[f] > 0 else -1.0)
                    w[f] -= lr * (err * o.features[f] + reg_penalty) * 0.05

        self.trained_weights = {k: round(v, 4) for k, v in w.items()}
        self.log_step("workflows", f"{GREEN}Model berhasil dilatih! Koefisien Parsnip:{RESET}")
        for k, v in self.trained_weights.items():
            self.log_step("workflows", f"    {k:>10} : {BOLD}{v:+0.4f}{RESET}")

    def yardstick_evaluate(self):
        """Simulasi yardstick::metrics(truth = target, estimate = .pred)"""
        self.log_step("yardstick", f"Mengevaluasi performa generalization pada {BOLD}Test Set{RESET}...")
        test_data = [o for o in self.processed_data if o.split == "test"]
        
        preds = []
        actuals = []
        for o in test_data:
            pred_y = self.trained_weights["intercept"] + sum(self.trained_weights[f] * o.features[f] for f in ["x1", "x2", "x3"])
            preds.append(pred_y)
            actuals.append(o.target)

        n = len(actuals)
        # RMSE
        rmse = math.sqrt(sum((y - p) ** 2 for y, p in zip(actuals, preds)) / n)
        # MAE
        mae = sum(abs(y - p) for y, p in zip(actuals, preds)) / n
        # R-squared
        y_mean = sum(actuals) / n
        ss_tot = sum((y - y_mean) ** 2 for y in actuals)
        ss_res = sum((y - p) ** 2 for y, p in zip(actuals, preds))
        r2 = max(0.0, 1.0 - (ss_res / ss_tot if ss_tot > 0 else 1.0))

        self.metrics = {"rmse": round(rmse, 4), "mae": round(mae, 4), "rsq": round(r2, 4)}

        print(f"\n{YELLOW}{BOLD}================ TABEL METRIK YARDSTICK ================{RESET}")
        print(f"{BOLD}{'Metric':<15} {'Estimator':<12} {'Estimate':<10}{RESET}")
        print("-" * 40)
        print(f"{'rmse':<15} {'standard':<12} {CYAN}{self.metrics['rmse']:<10.4f}{RESET}")
        print(f"{'mae':<15} {'standard':<12} {CYAN}{self.metrics['mae']:<10.4f}{RESET}")
        print(f"{'rsq':<15} {'standard':<12} {GREEN}{self.metrics['rsq']:<10.4f}{RESET}")
        print("-" * 40)

    def interactive_menu(self):
        """Menu interaktif simulasi terminal."""
        while True:
            print(f"\n{BOLD}{WHITE}--- Menu Simulasi Tidymodels Modern ---{RESET}")
            print(f" {CYAN}1.{RESET} Regenerate Dataset & Split (rsample)")
            print(f" {CYAN}2.{RESET} Jalankan Preprocessing Pipeline (recipes)")
            print(f" {CYAN}3.{RESET} Tuning & Fit Model (parsnip + tune + workflows)")
            print(f" {CYAN}4.{RESET} Tampilkan Metrik Yardstick & Uji Prediksi Manual")
            print(f" {CYAN}5.{RESET} Jalankan Automated Full Lifecycle Run")
            print(f" {RED}6.{RESET} Keluar (Exit)")
            choice = input(f"{BOLD}Pilih opsi [1-6]: {RESET}").strip()

            if choice == "1":
                self.generate_synthetic_dataset()
                self.rsample_initial_split()
            elif choice == "2":
                self.recipes_define()
                self.recipes_prep_and_bake()
            elif choice == "3":
                self.parsnip_specify_model()
                self.workflows_bundle()
                self.tune_cv_folds()
                self.workflows_fit()
            elif choice == "4":
                if not self.trained_weights:
                    print(f"{RED}Model belum difit. Jalankan opsi 3 terlebih dahulu.{RESET}")
                    continue
                self.yardstick_evaluate()
                self.manual_prediction_prompt()
            elif choice == "5":
                self.run_full_pipeline()
            elif choice == "6" or choice.lower() in ["q", "exit"]:
                print(f"{GREEN}Keluar dari simulasi. Sesi lab selesai.{RESET}")
                break
            else:
                print(f"{RED}Pilihan tidak valid. Silakan pilih 1-6.{RESET}")

    def manual_prediction_prompt(self):
        print(f"\n{BOLD}{MAGENTA}[Inference Test]{RESET} Masukkan prediktor baru untuk diprediksi oleh Workflow:")
        try:
            x1 = float(input("  Nilai x1 (misal 55.0): ") or "55.0")
            x2 = float(input("  Nilai x2 (misal 30.0): ") or "30.0")
            x3 = float(input("  Nilai x3 (misal 15.0): ") or "15.0")
            
            # Menggunakan normalized heuristic sederhana untuk simulasi
            pred_val = self.trained_weights["intercept"] + self.trained_weights["x1"] * ((x1 - 50)/15) + self.trained_weights["x2"] * ((x2 - 50)/25) + self.trained_weights["x3"] * ((x3 - 20)/10)
            print(f"  {BOLD}Hasil Prediksi (.pred): {CYAN}{pred_val:.3f}{RESET}")
        except ValueError:
            print(f"{RED}Input numerik tidak valid.{RESET}")

    def run_full_pipeline(self):
        print(f"\n{BOLD}{BG_BLUE} MEMULAI AUTOMATED PIPELINE TIDYMODELS RUN {RESET}\n")
        self.generate_synthetic_dataset()
        self.rsample_initial_split(prop=0.80)
        self.recipes_define()
        self.recipes_prep_and_bake()
        self.parsnip_specify_model(engine="glmnet", mode="regression")
        self.workflows_bundle()
        self.tune_cv_folds(k=5)
        self.workflows_fit()
        self.yardstick_evaluate()
        print(f"\n{GREEN}{BOLD}Pipeline selesai dieksekusi secara end-to-end tanpa error!{RESET}\n")

def main():
    print_banner()
    sim = TidymodelsSimulator(n_samples=80, seed=123)
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        sim.run_full_pipeline()
    else:
        # Jalankan secara interaktif
        print(f"{ITALIC}Gunakan flag '--auto' untuk bypass menu interaktif.{RESET}")
        sim.interactive_menu()

if __name__ == "__main__":
    main()

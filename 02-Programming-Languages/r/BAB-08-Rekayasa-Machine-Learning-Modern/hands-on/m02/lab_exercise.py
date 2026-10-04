#!/usr/bin/env python3
"""
Lab Hands-on: Rekayasa Machine Learning Modern (Tidymodels Ecosystem Deep Dive)
Topik: Implementasi Paradigma Modular Tidymodels (rsample, recipes, parsnip, yardstick, workflows)
Kategori: 02-Programming-Languages / r / Bab 08

Skrip ini mereplikasi arsitektur filosofis dari ekosistem R 'tidymodels' secara murni
menggunakan pustaka standar Python 3 (Object-Oriented & Functional):
  1. rsample   : Stratified / V-Fold Cross-Validation splits (Analysis/Assessment sets).
  2. recipes   : Deklaratif feature engineering pipeline (step_center, step_scale, prep, bake).
  3. parsnip   : Abstraksi unified model specification terpisah dari computational engine.
  4. workflows : Penggabungan resep preprocessing dan model spec dalam satu pipeline terpadu.
  5. yardstick : Metrik evaluasi konsisten (RMSE, MAE, R-squared).
  6. tune      : Grid-search cross-validation runner untuk optimasi hyperparameter.
"""

import sys
import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Any, Optional, Callable

# ============================================================================
# ANSI Color Formatting Helper
# ============================================================================
class ConsoleStyle:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

    @classmethod
    def badge(cls, text: str, color: str) -> str:
        return f"{color}{cls.BOLD}[{text}]{cls.RESET}"

# ============================================================================
# 1. RSAMPLE: Resampling & Splitting Architecture
# ============================================================================
@dataclass
class Split:
    """Mewakili split tunggal: data analysis (train) dan assessment (test)."""
    analysis_indices: List[int]
    assessment_indices: List[int]
    full_data: List[Dict[str, float]]

    def analysis(self) -> List[Dict[str, float]]:
        return [self.full_data[i] for i in self.analysis_indices]

    def assessment(self) -> List[Dict[str, float]]:
        return [self.full_data[i] for i in self.assessment_indices]


def initial_split(data: List[Dict[str, float]], prop: float = 0.8, seed: int = 42) -> Split:
    """Membagi dataset menjadi initial training set dan testing set."""
    rng = random.Random(seed)
    indices = list(range(len(data)))
    rng.shuffle(indices)
    split_point = int(len(data) * prop)
    return Split(indices[:split_point], indices[split_point:], data)


def vfold_cv(data: List[Dict[str, float]], v: int = 4, seed: int = 42) -> List[Split]:
    """Menghasilkan V-Fold cross validation splits."""
    rng = random.Random(seed)
    indices = list(range(len(data)))
    rng.shuffle(indices)
    folds = []
    fold_size = len(data) // v
    for i in range(v):
        test_start = i * fold_size
        test_end = (i + 1) * fold_size if i != v - 1 else len(data)
        val_idx = indices[test_start:test_end]
        train_idx = [idx for idx in indices if idx not in val_idx]
        folds.append(Split(train_idx, val_idx, data))
    return folds

# ============================================================================
# 2. RECIPES: Declarative Preprocessing Pipeline
# ============================================================================
class RecipeStep:
    def fit(self, data: List[Dict[str, float]]):
        pass

    def transform(self, data: List[Dict[str, float]]) -> List[Dict[str, float]]:
        return data


class StepNormalize(RecipeStep):
    """Menormalisasi fitur ke zero mean dan unit variance (Z-score)."""
    def __init__(self, variables: List[str]):
        self.variables = variables
        self.stats: Dict[str, Tuple[float, float]] = {}

    def fit(self, data: List[Dict[str, float]]):
        for var in self.variables:
            values = [row[var] for row in data]
            mean = sum(values) / len(values)
            variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1 if len(values) > 1 else 1.0)
            std = math.sqrt(variance) if variance > 0 else 1.0
            self.stats[var] = (mean, std)

    def transform(self, data: List[Dict[str, float]]) -> List[Dict[str, float]]:
        transformed = []
        for row in data:
            new_row = row.copy()
            for var in self.variables:
                if var in self.stats:
                    mean, std = self.stats[var]
                    new_row[var] = (new_row[var] - mean) / std
            transformed.append(new_row)
        return transformed


class Recipe:
    """Pipeline resep pemrosesan data deklaratif (Tidymodels recipes pattern)."""
    def __init__(self, outcome: str, predictors: List[str]):
        self.outcome = outcome
        self.predictors = predictors
        self.steps: List[RecipeStep] = []
        self.trained = False

    def add_step(self, step: RecipeStep) -> "Recipe":
        self.steps.append(step)
        return self

    def prep(self, training_data: List[Dict[str, float]]) -> "Recipe":
        """Estimasi parameter preprocessing menggunakan analysis/training data."""
        current_data = training_data
        for step in self.steps:
            step.fit(current_data)
            current_data = step.transform(current_data)
        self.trained = True
        return self

    def bake(self, new_data: List[Dict[str, float]]) -> List[Dict[str, float]]:
        """Menerapkan transformasi terlatih ke data baru."""
        if not self.trained:
            raise RuntimeError("Recipe harus melalui tahap 'prep()' sebelum 'bake()'.")
        res = new_data
        for step in self.steps:
            res = step.transform(res)
        return res

# ============================================================================
# 3. PARSNIP: Unified Model Specification
# ============================================================================
class ParsnipLinearRegression:
    """Spesifikasi model Linear Regression independen dengan penalty L2 (Ridge)."""
    def __init__(self, penalty: float = 0.0, learning_rate: float = 0.01, epochs: int = 150):
        self.penalty = penalty
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.weights: Dict[str, float] = {}
        self.bias: float = 0.0

    def fit(self, data: List[Dict[str, float]], predictors: List[str], outcome: str) -> "ParsnipLinearRegression":
        # Inisialisasi bobot
        self.weights = {var: 0.0 for var in predictors}
        self.bias = 0.0
        n = len(data)

        # Gradient Descent Optimization
        for _ in range(self.epochs):
            grad_bias = 0.0
            grad_weights = {var: 0.0 for var in predictors}

            for row in data:
                pred = self.bias + sum(self.weights[var] * row[var] for var in predictors)
                error = pred - row[outcome]
                grad_bias += error
                for var in predictors:
                    grad_weights[var] += error * row[var]

            # Update parameter dengan regularisasi L2
            self.bias -= (self.learning_rate / n) * grad_bias
            for var in predictors:
                reg_term = self.penalty * self.weights[var]
                self.weights[var] -= self.learning_rate * ((grad_weights[var] / n) + reg_term)

        return self

    def predict(self, data: List[Dict[str, float]], predictors: List[str]) -> List[float]:
        preds = []
        for row in data:
            val = self.bias + sum(self.weights[var] * row[var] for var in predictors)
            preds.append(val)
        return preds

# ============================================================================
# 4. YARDSTICK: Tidy Performance Metrics
# ============================================================================
class Yardstick:
    """Kumpulan metrik evaluasi model (Loss & Goodness of Fit)."""
    @staticmethod
    def rmse(truth: List[float], estimate: List[float]) -> float:
        mse = sum((y - y_hat) ** 2 for y, y_hat in zip(truth, estimate)) / len(truth)
        return math.sqrt(mse)

    @staticmethod
    def mae(truth: List[float], estimate: List[float]) -> float:
        return sum(abs(y - y_hat) for y, y_hat in zip(truth, estimate)) / len(truth)

    @staticmethod
    def rsq(truth: List[float], estimate: List[float]) -> float:
        mean_y = sum(truth) / len(truth)
        ss_tot = sum((y - mean_y) ** 2 for y in truth)
        ss_res = sum((y - y_hat) ** 2 for y, y_hat in zip(truth, estimate))
        if ss_tot == 0:
            return 0.0
        return max(0.0, 1.0 - (ss_res / ss_tot))

# ============================================================================
# 5. WORKFLOWS: End-to-End Orchestrator
# ============================================================================
class Workflow:
    """Mengintegrasikan Recipe dan Parsnip Specification menjadi artefak tunggal."""
    def __init__(self):
        self.recipe: Optional[Recipe] = None
        self.model_spec: Optional[ParsnipLinearRegression] = None
        self.fitted_model: Optional[ParsnipLinearRegression] = None
        self.trained_recipe: Optional[Recipe] = None

    def add_recipe(self, recipe: Recipe) -> "Workflow":
        self.recipe = recipe
        return self

    def add_model(self, model_spec: ParsnipLinearRegression) -> "Workflow":
        self.model_spec = model_spec
        return self

    def fit(self, data: List[Dict[str, float]]) -> "Workflow":
        if not self.recipe or not self.model_spec:
            raise ValueError("Workflow harus memiliki recipe dan model_spec.")
        # Step 1: Prep & Bake Data Pelatihan
        self.trained_recipe = self.recipe.prep(data)
        baked_data = self.trained_recipe.bake(data)

        # Step 2: Fit Model menggunakan data yang telah di-bake
        self.fitted_model = ParsnipLinearRegression(
            penalty=self.model_spec.penalty,
            learning_rate=self.model_spec.learning_rate,
            epochs=self.model_spec.epochs
        )
        self.fitted_model.fit(
            baked_data,
            predictors=self.recipe.predictors,
            outcome=self.recipe.outcome
        )
        return self

    def predict(self, new_data: List[Dict[str, float]]) -> List[float]:
        if not self.fitted_model or not self.trained_recipe:
            raise RuntimeError("Workflow belum di-fit.")
        baked_new = self.trained_recipe.bake(new_data)
        return self.fitted_model.predict(baked_new, predictors=self.recipe.predictors)

# ============================================================================
# 6. TUNE: Hyperparameter Tuning via Resampling
# ============================================================================
def tune_grid(workflow_template: Callable[[float], Workflow],
              resamples: List[Split],
              param_grid: List[float],
              outcome: str) -> List[Dict[str, Any]]:
    """Mengevaluasi hyperparameter grid pada V-Fold cross validation splits."""
    tuning_results = []

    for penalty in param_grid:
        fold_metrics = []
        for split in resamples:
            train_fold = split.analysis()
            val_fold = split.assessment()

            wf = workflow_template(penalty)
            wf.fit(train_fold)

            actuals = [row[outcome] for row in val_fold]
            predictions = wf.predict(val_fold)

            fold_rmse = Yardstick.rmse(actuals, predictions)
            fold_rsq = Yardstick.rsq(actuals, predictions)
            fold_metrics.append((fold_rmse, fold_rsq))

        avg_rmse = sum(m[0] for m in fold_metrics) / len(fold_metrics)
        avg_rsq = sum(m[1] for m in fold_metrics) / len(fold_metrics)

        tuning_results.append({
            "penalty": penalty,
            "mean_rmse": avg_rmse,
            "mean_rsq": avg_rsq
        })

    return tuning_results

# ============================================================================
# MAIN SIMULATION RUNNER
# ============================================================================
def generate_synthetic_housing_data(n: int = 150, seed: int = 101) -> List[Dict[str, float]]:
    """Membuat dataset harga properti sintetis dengan noise realistis."""
    rng = random.Random(seed)
    dataset = []
    for _ in range(n):
        sqft = rng.uniform(800.0, 3500.0)
        rooms = float(rng.randint(2, 6))
        distance_km = rng.uniform(1.0, 25.0)
        # Target: price (ribu USD) = 50 + 0.15*sqft + 15*rooms - 3.5*distance + noise
        noise = rng.gauss(0.0, 15.0)
        price = 50.0 + (0.15 * sqft) + (15.0 * rooms) - (3.5 * distance_km) + noise
        dataset.append({
            "sqft": sqft,
            "rooms": rooms,
            "distance_km": distance_km,
            "price": price
        })
    return dataset


def main():
    print(f"\n{ConsoleStyle.BOLD}{ConsoleStyle.CYAN}" + "="*75)
    print(" LAB HANDS-ON: SIMULASI TIDYMODELS ECOSYSTEM (R ML MODERN)")
    print("="*75 + f"{ConsoleStyle.RESET}\n")

    # 1. Dataset Generation
    print(f"{ConsoleStyle.badge('DATA', ConsoleStyle.BLUE)} Menghasilkan dataset perumahan sintetis (N=150)...")
    dataset = generate_synthetic_housing_data(n=150, seed=42)
    print(f"  Contoh baris 1: {dataset[0]}")

    # 2. rsample: Initial Split & Cross-Validation Folds
    print(f"\n{ConsoleStyle.badge('RSAMPLE', ConsoleStyle.GREEN)} Melakukan Initial Split (80/20) dan 4-Fold Cross Validation...")
    split_obj = initial_split(dataset, prop=0.8, seed=123)
    train_data = split_obj.analysis()
    test_data = split_obj.assessment()
    cv_folds = vfold_cv(train_data, v=4, seed=123)
    print(f"  Dataset Training: {len(train_data)} baris | Testing: {len(test_data)} baris")
    print(f"  V-Fold CV Dibentuk: {len(cv_folds)} folds untuk tuning hyperparameter.")

    # 3. Defining Workflow Factory (Recipe + Parsnip spec)
    predictors = ["sqft", "rooms", "distance_km"]
    outcome = "price"

    def build_workflow(penalty: float) -> Workflow:
        # Deklarasi Resep Pemrosesan
        rec = Recipe(outcome=outcome, predictors=predictors)
        rec.add_step(StepNormalize(variables=predictors))

        # Deklarasi Parsnip Model Spec
        model_spec = ParsnipLinearRegression(
            penalty=penalty,
            learning_rate=0.08,
            epochs=250
        )

        wf = Workflow()
        wf.add_recipe(rec)
        wf.add_model(model_spec)
        return wf

    # 4. tune: Hyperparameter Grid Search via CV
    print(f"\n{ConsoleStyle.badge('TUNE', ConsoleStyle.YELLOW)} Menjalankan grid tuning untuk hyperparameter Ridge Penalty (L2)...")
    penalty_grid = [0.0, 0.001, 0.01, 0.1, 0.5, 2.0]
    tune_results = tune_grid(build_workflow, cv_folds, penalty_grid, outcome=outcome)

    print(f"{ConsoleStyle.DIM}  {'-'*60}{ConsoleStyle.RESET}")
    print(f"  {'Penalty (L2)':<15} | {'CV Mean RMSE':<18} | {'CV Mean R²':<15}")
    print(f"{ConsoleStyle.DIM}  {'-'*60}{ConsoleStyle.RESET}")
    for res in tune_results:
        print(f"  {res['penalty']:<15.4f} | {res['mean_rmse']:<18.4f} | {res['mean_rsq']:<15.4f}")
    print(f"{ConsoleStyle.DIM}  {'-'*60}{ConsoleStyle.RESET}")

    # Seleksi hyperparameter terbaik berdasarkan RMSE terendah
    best_config = min(tune_results, key=lambda x: x["mean_rmse"])
    best_penalty = best_config["penalty"]
    print(f"  {ConsoleStyle.BOLD}Hyperparameter Terbaik:{ConsoleStyle.RESET} Penalty = {best_penalty:.4f} (RMSE: {best_config['mean_rmse']:.4f})")

    # 5. Final Fit pada Seluruh Data Training
    print(f"\n{ConsoleStyle.badge('WORKFLOWS', ConsoleStyle.BLUE)} Melakukan Final Fit Workflow pada seluruh Training Data...")
    final_workflow = build_workflow(penalty=best_penalty)
    final_workflow.fit(train_data)
    
    weights_info = final_workflow.fitted_model.weights
    print(f"  Model Weights Terlatih (Standardized Scale):")
    for var, w in weights_info.items():
        print(f"    - {var:<12}: {w:>8.3f}")
    print(f"    - {'Bias (Inter)':<12}: {final_workflow.fitted_model.bias:>8.3f}")

    # 6. yardstick: Evaluasi Kinerja Akhir pada Test Data (Hold-out Test Set)
    print(f"\n{ConsoleStyle.badge('YARDSTICK', ConsoleStyle.GREEN)} Evaluasi Final Test Set (Generalization Performance):")
    test_actuals = [row[outcome] for row in test_data]
    test_predictions = final_workflow.predict(test_data)

    test_rmse = Yardstick.rmse(test_actuals, test_predictions)
    test_mae = Yardstick.mae(test_actuals, test_predictions)
    test_rsq = Yardstick.rsq(test_actuals, test_predictions)

    print(f"  {ConsoleStyle.BOLD}Final Metrics on Test Data:{ConsoleStyle.RESET}")
    print(f"    • {ConsoleStyle.CYAN}RMSE (Root Mean Squared Error){ConsoleStyle.RESET} : {test_rmse:.4f}")
    print(f"    • {ConsoleStyle.CYAN}MAE  (Mean Absolute Error)     {ConsoleStyle.RESET} : {test_mae:.4f}")
    print(f"    • {ConsoleStyle.CYAN}R²   (Coefficient of Determ.)  {ConsoleStyle.RESET} : {test_rsq:.4f}")

    # Verifikasi Prediksi Sampel
    print(f"\n{ConsoleStyle.badge('INFERENCE', ConsoleStyle.HEADER)} Perbandingan Sampel Test (5 Observasi Pertama):")
    print(f"  {'Aktual (USD)':<15} | {'Prediksi (USD)':<15} | {'Selisih (Error)':<15}")
    print(f"  {'-'*50}")
    for act, pred in zip(test_actuals[:5], test_predictions[:5]):
        diff = pred - act
        color = ConsoleStyle.GREEN if abs(diff) < 15.0 else ConsoleStyle.YELLOW
        print(f"  {act:<15.2f} | {pred:<15.2f} | {color}{diff:>+14.2f}{ConsoleStyle.RESET}")

    print(f"\n{ConsoleStyle.BOLD}{ConsoleStyle.GREEN}✓ Lab Ekosistem Tidymodels Berhasil Dieksekusi Secara Utuh.{ConsoleStyle.RESET}\n")

if __name__ == "__main__":
    main()
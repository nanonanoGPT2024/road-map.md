import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.genmod.generalized_linear_model import GLM
from statsmodels.genmod import families
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.model_selection import train_test_split, RepeatedStratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import RobustScaler, OneHotEncoder
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    roc_auc_score, 
    brier_score_loss, 
    classification_report, 
    precision_recall_curve, 
    auc
)

# ==============================================================================
# 1. PENGEMBANGAN DATASET SINTETIK ENTERPRISE P2P
# ==============================================================================
def generate_production_data(n_records: int = 5000, seed: int = 101) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    
    credit_score = rng.normal(loc=650, scale=70, size=n_records).clip(300, 850)
    monthly_income = rng.lognormal(mean=9.2, sigma=0.75, size=n_records) # Skewed distribution
    dti_ratio = rng.uniform(0.05, 0.60, size=n_records) # Debt-to-income
    loan_amount = rng.uniform(2000, 35000, size=n_records)
    interest_rate = 0.05 + 0.15 * (1 - (credit_score - 300) / 550) + rng.normal(0, 0.01, size=n_records)
    interest_rate = interest_rate.clip(0.04, 0.35)
    employment_type = rng.choice(['Full-time', 'Self-employed', 'Contractor', 'Unemployed'], 
                                 size=n_records, p=[0.65, 0.20, 0.10, 0.05])
    
    # Structural Data Generating Process for Churn / Default
    # True Log-Odds equation
    log_odds = (
        -4.2
        - 0.006 * (credit_score - 650)
        + 4.5 * dti_ratio
        + 8.5 * interest_rate
        - 0.00005 * (monthly_income - np.median(monthly_income))
        + (employment_type == 'Unemployed') * 1.2
        + (employment_type == 'Contractor') * 0.4
    )
    
    # Injeksi non-linear interaction noise
    log_odds += 0.02 * (interest_rate * dti_ratio * 100)
    
    churn_prob = 1 / (1 + np.exp(-log_odds))
    churn_label = rng.binomial(1, churn_prob)
    
    return pd.DataFrame({
        'credit_score': credit_score,
        'monthly_income': monthly_income,
        'dti_ratio': dti_ratio,
        'loan_amount': loan_amount,
        'interest_rate': interest_rate,
        'employment_type': employment_type,
        'churn': churn_label
    })

raw_data = generate_production_data(n_records=7500, seed=2024)

# ==============================================================================
# 2. PEMODELAN INFERENSIAL: LOGISTIC REGRESSION VIA STATSMODELS (GLM)
# ==============================================================================
print("=== [FASE 1: PEMODELAN INFERENSIAL REGRESI LOGISTIK (GLM)] ===")

# Persiapan Matriks Kovariat Inferensial
inferential_df = raw_data.copy()
# Encode categorical dummy variables manual untuk statsmodels
inferential_df = pd.get_dummies(inferential_df, columns=['employment_type'], drop_first=True, dtype=float)

X_cols = [c for c in inferential_df.columns if c != 'churn']
X_inferential = sm.add_constant(inferential_df[X_cols])
y_inferential = inferential_df['churn']

# Fit GLM Family Binomial dengan Logit Link & Robust Covariance Estimator (HC3)
glm_binom = GLM(y_inferential, X_inferential, family=families.Binomial())
glm_results = glm_binom.fit(cov_type='HC3')

print(glm_results.summary())

# Menghitung Odds Ratio (OR) dan 95% Confidence Interval
odds_ratios = np.exp(glm_results.params)
conf = np.exp(glm_results.conf_int())
conf['Odds_Ratio'] = odds_ratios
conf.columns = ['CI_2.5%', 'CI_97.5%', 'Odds_Ratio']
print("\n--- ESTIMASI ODDS RATIO (EFEK KAUSAL SENSITIVITAS) ---")
print(conf.sort_values(by='Odds_Ratio', ascending=False))

# ==============================================================================
# 3. PEMODELAN PREDIKTIF TERAPAN: PRODUCTION-READY SCIKIT-LEARN PIPELINE
# ==============================================================================
print("\n=== [FASE 2: PEMODELAN PREDIKTIF TERAPAN MACHINE LEARNING] ===")

# Isolasi Partisi Data Latih dan Uji Out-of-Sample
X = raw_data.drop(columns=['churn'])
y = raw_data['churn']

X_train, X_test, y_train, y_test = train_test_split(
    X, y, 
    test_size=0.25, 
    random_state=999, 
    stratify=y
)

# Custom Outlier Clipper Transformer
class RobustWinsorizer(BaseEstimator, TransformerMixin):
    """Membatasi nilai ekstrem berdasarkan persentil 1% dan 99% data latih."""
    def __init__(self, lower_percentile: float = 0.01, upper_percentile: float = 0.99):
        self.lower_percentile = lower_percentile
        self.upper_percentile = upper_percentile
        self.bounds_ = {}

    def fit(self, X, y=None):
        X_df = pd.DataFrame(X)
        for col in X_df.columns:
            self.bounds_[col] = (
                X_df[col].quantile(self.lower_percentile),
                X_df[col].quantile(self.upper_percentile)
            )
        return self

    def transform(self, X):
        X_df = pd.DataFrame(X).copy()
        for col, (lower, upper) in self.bounds_.items():
            X_df[col] = X_df[col].clip(lower=lower, upper=upper)
        return X_df.values

# Preprocessing Pipelines
numeric_cols = ['credit_score', 'monthly_income', 'dti_ratio', 'loan_amount', 'interest_rate']
categorical_cols = ['employment_type']

numeric_transformer = Pipeline([
    ('winsorizer', RobustWinsorizer()),
    ('scaler', RobustScaler())
])

categorical_transformer = OneHotEncoder(drop='first', sparse_output=False, handle_unknown='ignore')

preprocessor = ColumnTransformer(
    transformers=[
        ('num', numeric_transformer, numeric_cols),
        ('cat', categorical_transformer, categorical_cols)
    ]
)

# Definisi Estimator Model: Histogram-based Gradient Boosting
base_estimator = HistGradientBoostingClassifier(
    max_iter=150,
    learning_rate=0.05,
    max_leaf_nodes=31,
    min_samples_leaf=20,
    l2_regularization=1.5,
    random_state=42
)

# Model Pipeline Lengkap Terkalibrasi
full_model = Pipeline([
    ('preprocessor', preprocessor),
    ('calibrated_classifier', CalibratedClassifierCV(
        estimator=base_estimator, 
        method='sigmoid', 
        cv=3
    ))
])

# Evaluasi Cross Validation Berlapis
cv_scheme = RepeatedStratifiedKFold(n_splits=5, n_repeats=2, random_state=42)
cv_results = cross_validate(
    full_model, X_train, y_train, 
    cv=cv_scheme, 
    scoring=['roc_auc', 'neg_brier_score'],
    n_jobs=-1,
    return_train_score=False
)

print(f"Mean CV ROC-AUC: {-1 * cv_results['test_roc_auc'].mean():.4f} "
      f"(+/- {cv_results['test_roc_auc'].std():.4f})")
print(f"Mean CV Brier Loss: {-1 * cv_results['test_neg_brier_score'].mean():.4f}")

# Pelatihan Akhir dan Penilaian Data Uji (Out-of-Sample)
full_model.fit(X_train, y_train)
y_test_proba = full_model.predict_proba(X_test)[:, 1]
y_test_pred = (y_test_proba >= 0.35).astype(int) # Customized Threshold for Risk Aversion

test_auc = roc_auc_score(y_test, y_test_proba)
test_brier = brier_score_loss(y_test, y_test_proba)

precision, recall, _ = precision_recall_curve(y_test, y_test_proba)
pr_auc = auc(recall, precision)

print("\n--- PERFORMA FINAL PADA UNSEEN TEST SET ---")
print(f"Test ROC-AUC Score       : {test_auc:.4f}")
print(f"Test Precision-Recall AUC: {pr_auc:.4f}")
print(f"Test Brier Score         : {test_brier:.4f}")
print("\nClassification Report (Ambang Batas Probabilitas 0.35):")
print(classification_report(y_test, y_test_pred, digits=4))

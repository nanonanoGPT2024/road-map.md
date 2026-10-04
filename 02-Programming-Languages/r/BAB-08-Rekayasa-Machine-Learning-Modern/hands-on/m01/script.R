# Instansiasi pustaka produksi
suppressPackageStartupMessages({
  library(tidymodels)
  library(themis)     # Untuk step_smote
  library(xgboost)    # Engine XGBoost
  library(bundle)     # Ekstraksi artefak model self-contained
  library(vetiver)    # Model deployment & versioning
  library(future)     # Paralelisasi asinkron
  library(doFuture)   # Backend parallel foreach
})

# 1. SETUP PARALELISASI MULTI-CORE
plan(multisession, workers = 2)

# 2. GENERASI DATASET TRANSAKSI HIGH-SKEW & IMBALANCED
set.seed(999)
n_tx <- 5000

fraud_df <- tibble::tibble(
  tx_amount = c(rlnorm(n_tx * 0.995, meanlog = 4, sdlog = 1.5), rlnorm(n_tx * 0.005, meanlog = 8, sdlog = 0.5)),
  tx_velocity_1h = c(rpois(n_tx * 0.995, lambda = 1), rpois(n_tx * 0.005, lambda = 8)),
  device_trust_score = c(runif(n_tx * 0.995, 0.4, 1.0), runif(n_tx * 0.005, 0.0, 0.3)),
  country_risk_level = sample(c("Low", "Medium", "High"), size = n_tx, replace = TRUE, prob = c(0.7, 0.25, 0.05)),
  is_foreign = sample(c("Domestic", "CrossBorder"), size = n_tx, replace = TRUE, prob = c(0.85, 0.15)),
  is_fraud = factor(
    c(rep("Legit", n_tx * 0.995), rep("Fraud", n_tx * 0.005)),
    levels = c("Fraud", "Legit") # Fraud sebagai event target utama
  )
)

# 3. SPLIT STRATIFIKASI REPRODUSIBEL
tx_split <- rsample::initial_split(fraud_df, prop = 0.80, strata = is_fraud)
tx_train <- rsample::training(tx_split)
tx_test  <- rsample::testing(tx_split)

# 4. CROSS VALIDATION RESAMPLES DENGAN STRATIFIKASI KETAT
tx_folds <- rsample::vfold_cv(tx_train, v = 5, strata = is_fraud)

# 5. PREPROCESSING BLUEPRINT ANTI-LEAKAGE DENGAN SMOTE
fraud_recipe <- recipes::recipe(is_fraud ~ ., data = tx_train) %>%
  recipes::step_log(tx_amount, base = 10, offset = 1) %>% # Reduksi skewness
  recipes::step_novel(recipes::all_nominal_predictors()) %>% # Penanganan level baru di runtime
  recipes::step_dummy(recipes::all_nominal_predictors(), one_hot = TRUE) %>%
  recipes::step_zv(recipes::all_predictors()) %>% # Hapus prediktor tanpa varians
  themis::step_smote(is_fraud, over_ratio = 0.20, seed = 42) # SMOTE hanya terjadi di Analysis Split!

# 6. MODEL SPECIFICATION (XGBOOST)
xgb_spec <- parsnip::boost_tree(
  trees = 300,
  tree_depth = parsnip::tune(),
  learn_rate = parsnip::tune(),
  loss_reduction = parsnip::tune()
) %>%
  parsnip::set_engine("xgboost", nthread = 1, eval_metric = "aucpr") %>%
  parsnip::set_mode("classification")

# 7. WORKFLOW CONSOLIDATION
fraud_workflow <- workflows::workflow() %>%
  workflows::add_recipe(fraud_recipe) %>%
  workflows::add_model(xgb_spec)

# 8. DEFINE PARAMETER SEARCH BOUNDS
xgb_params <- fraud_workflow %>%
  tune::extract_parameter_set_dials() %>%
  recipes::update(
    tree_depth = dials::tree_depth(range = c(3, 8)),
    learn_rate = dials::learn_rate(range = c(-3, -1), trans = scales::log10_trans()),
    loss_reduction = dials::loss_reduction(range = c(-2, 1), trans = scales::log10_trans())
  )

# 9. BAYESIAN HYPERPARAMETER OPTIMIZATION
eval_metrics <- yardstick::metric_set(
  yardstick::pr_auc,
  yardstick::roc_auc,
  yardstick::mn_log_loss
)

tune_ctrl <- tune::control_bayes(
  no_improve = 10,
  verbose = FALSE,
  save_pred = FALSE,
  parallel_over = "resamples"
)

cat("Memulai Bayesian Hyperparameter Optimization...\n")
set.seed(123)
bayes_results <- tune::tune_bayes(
  fraud_workflow,
  resamples = tx_folds,
  param_info = xgb_params,
  iter = 10,
  metrics = eval_metrics,
  initial = 5,
  control = tune_ctrl
)

# 10. IDENTIFIKASI DAN FINALISASI WORKFLOW
best_xgb_params <- tune::select_best(bayes_results, metric = "pr_auc")
print(best_xgb_params)

finalized_fraud_wf <- workflows::finalize_workflow(fraud_workflow, best_xgb_params)

# 11. HOLDOUT EVALUATION (LAST FIT)
final_test_fit <- tune::last_fit(
  finalized_fraud_wf,
  split = tx_split,
  metrics = eval_metrics
)

# Ambil metrik pada data testing murni
holdout_metrics <- tune::collect_metrics(final_test_fit)
cat("\nMetrik Holdout Testing:\n")
print(holdout_metrics)

# 12. FIT MODEL LENGKAP PADA SELURUH DATA TRAIN UNTUK PACKAGING
fitted_production_wf <- parsnip::fit(finalized_fraud_wf, data = tx_train)

# 13. PACKAGING UNTUK DEPLOYMENT (VETIVER + BUNDLE)
# Membuat deployable artifact yang mengisolasi referensi environment
v_model <- vetiver::vetiver_model(
  model = fitted_production_wf,
  model_name = "fraud_detection_xgb",
  save_ptype = tx_train[1:5, ] %>% dplyr::select(-is_fraud) # Schema prototype untuk validasi input
)

print(v_model)

# 14. MEMULIHKAN COMPUTATION PLAN
plan(sequential)

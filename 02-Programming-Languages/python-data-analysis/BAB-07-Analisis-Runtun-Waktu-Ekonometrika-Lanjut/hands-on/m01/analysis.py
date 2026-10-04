import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.api import VAR
from statsmodels.tsa.vector_ar.vecm import coint_johansen
from arch import arch_model
import warnings
warnings.filterwarnings('ignore')

class EconometricPipeline:
    """Production-grade econometric engine handling VAR and GARCH dynamics."""
    
    def __init__(self, data: pd.DataFrame):
        self.raw_data = data.copy()
        self.differenced_data = pd.DataFrame()
        self.var_model = None
        self.var_results = None
        self.garch_results = None
        
    def prepare_data(self) -> None:
        """Sanitasi dan pembersihan missing values menggunakan interpolasi runtun waktu linear."""
        self.raw_data = self.raw_data.infer_objects(copy=False).interpolate(method='time').dropna()
        # Log difference untuk proksi return kontinu (stasioneritas)
        self.differenced_data = np.log(self.raw_data).diff().dropna()

    def test_johansen_cointegration(self, det_order: int = 0, k_ar_diff: int = 1) -> None:
        """
        Menjalankan Uji Kointegrasi Johansen.
        det_order: -1 (no deterministic part), 0 (constant in cointegrating space), 1 (trend).
        """
        print("=== UJI KOINTEGRASI JOHANSEN ===")
        # Johansen dijalankan pada level series, BUKAN difference
        jres = coint_johansen(self.raw_data, det_order, k_ar_diff)
        
        # Trace test statistic vs critical values (90%, 95%, 99%)
        traces = jres.lr1
        cvm = jres.cvm[:, 1]  # Kolom 1 adalah 95% critical value
        
        for i in range(len(traces)):
            status = "Terkointegrasi" if traces[i] > cvm[i] else "Tidak Terkointegrasi"
            print(f"Rank r <= {i}: Trace Stat = {traces[i]:.3f}, Critical Val (95%) = {cvm[i]:.3f} -> {status}")

    def fit_var(self, maxlags: int = 5, criterion: str = 'aic') -> None:
        """Estimasi Vector Autoregression dengan seleksi ordo otomatis."""
        print("\n=== MODELING VECTOR AUTOREGRESSION (VAR) ===")
        self.var_model = VAR(self.differenced_data)
        self.var_results = self.var_model.fit(maxlags=maxlags, ic=criterion)
        print(f"Optimal Lags Selected ({criterion.upper()}): {self.var_results.k_ar}")
        print(self.var_results.summary())

    def fit_portfolio_garch(self, target_col: str, p: int = 1, q: int = 1) -> None:
        """Pemodelan Volatilitas Menggunakan GARCH(1,1) dengan distribusi Student-t."""
        print(f"\n=== ESTIMASI GARCH({p},{q}) PADA: {target_col} ===")
        series = self.differenced_data[target_col] * 100.0  # Skala return ke persentase
        
        # Menggunakan distribusi Student's t untuk menangkap 'fat-tails'
        garch = arch_model(series, vol='Garch', p=p, q=q, dist='StudentsT', mean='AR', lags=1)
        self.garch_results = garch.fit(disp='off')
        print(self.garch_results.summary())

# ==========================================
# SIMULASI DATA DAN EKSEKUSI PIPELINE
# ==========================================
if __name__ == "__main__":
    np.random.seed(1337)
    periods = 1200
    dates = pd.date_range("2018-01-01", periods=periods, freq="B")
    
    # Inisialisasi proses terkointegrasi sintetis:
    # Seri 1: Random walk
    shock_1 = np.random.normal(0, 0.02, periods)
    oil_log = np.cumsum(shock_1) + 4.5
    
    # Seri 2: Equilibrium relationship + transient shock
    shock_2 = np.random.normal(0, 0.015, periods)
    interest_log = 0.7 * oil_log + np.cumsum(shock_2) * 0.1
    
    df_market = pd.DataFrame({
        'Oil_Price': np.exp(oil_log),
        'Interest_Proxy': np.exp(interest_log)
    }, index=dates)
    
    # Pipeline Execution
    engine = EconometricPipeline(df_market)
    engine.prepare_data()
    
    # 1. Cek Kointegrasi Johansen (Ekuilibrium Jangka Panjang)
    engine.test_johansen_cointegration()
    
    # 2. VAR Modeling (Dinamika Transmisi Jangka Pendek)
    engine.fit_var(maxlags=4)
    
    # 3. Dynamic Volatility Modeling
    engine.fit_portfolio_garch(target_col='Oil_Price', p=1, q=1)

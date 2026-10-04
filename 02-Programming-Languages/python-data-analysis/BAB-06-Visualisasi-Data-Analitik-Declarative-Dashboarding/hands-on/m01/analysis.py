"""
Logistics SLA & Real-Time Fleet Performance Dashboard
Framework: Streamlit & Altair Declarative Specification
Architecture: In-Memory Caching + Declarative Cross-Filtering
"""

from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import altair as alt
import streamlit as st

# ==========================================
# 01. ENGINE CONFIGURATION & STYLING SETUP
# ==========================================
st.set_page_config(
    page_title="Logistics SLA Mission Control",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Optimasi Altair Render: Batasi pengiriman payload row inline jika melebihi 5000 baris
alt.data_transformers.disable_max_rows()

# ==========================================
# 02. HIGH-PERFORMANCE DATA GENERATOR & CACHING
# ==========================================
@st.cache_data(ttl=3600, show_spinner="Memuat Dataset Operasional Logistik...")
def load_logistics_telemetry(n_records: int = 15_000) -> pd.DataFrame:
    """
    Menghasilkan data telemetri logistik sintetis berskala enterprise.
    Dioptimasi menggunakan tipe data hemat memori (category & float32).
    """
    np.random.seed(42)
    start_date = datetime.now() - timedelta(days=30)
    
    regions = ["DKI Jakarta", "Jawa Barat", "Jawa Timur", "Sumatera Utara", "Sulawesi Selatan"]
    sla_status = ["On-Time", "Delayed", "Severely Delayed"]
    transport_modes = ["Van", "Truck Large", "Motorcycle Cargo"]
    
    random_dates = [start_date + timedelta(minutes=int(x)) for x in np.random.randint(0, 30 * 24 * 60, n_records)]
    
    # Distribusi probabilitas yang merefleksikan operasional dunia nyata
    assigned_regions = np.random.choice(regions, size=n_records, p=[0.35, 0.25, 0.20, 0.12, 0.08])
    assigned_sla = np.random.choice(sla_status, size=n_records, p=[0.78, 0.16, 0.06])
    assigned_mode = np.random.choice(transport_modes, size=n_records, p=[0.50, 0.20, 0.30])
    
    # Delay durasi dalam satuan jam (log-normal distribution)
    delays_hours = np.where(
        assigned_sla == "On-Time",
        0.0,
        np.random.lognormal(mean=1.5, sigma=0.75, size=n_records)
    ).astype(np.float32)
    
    shipping_cost = np.random.uniform(15_000, 450_000, size=n_records).astype(np.float32)
    
    df = pd.DataFrame({
        "order_id": [f"TRX-{1000000 + i}" for i in range(n_records)],
        "timestamp": random_dates,
        "region": pd.Categorical(assigned_regions),
        "sla_status": pd.Categorical(assigned_sla),
        "transport_mode": pd.Categorical(assigned_mode),
        "delay_hours": delays_hours,
        "shipping_cost": shipping_cost
    })
    
    return df

# Eksekusi pemuatan data dengan memoization
df_telemetry = load_logistics_telemetry(n_records=20_000)

# ==========================================
# 03. SIDEBAR COMPONENT: STATEFUL FILTERS
# ==========================================
st.sidebar.header("Filter Parameter Analitik")

selected_regions = st.sidebar.multiselect(
    "Pilih Wilayah Operasional:",
    options=list(df_telemetry["region"].cat.categories),
    default=list(df_telemetry["region"].cat.categories)
)

selected_modes = st.sidebar.multiselect(
    "Pilih Moda Transportasi:",
    options=list(df_telemetry["transport_mode"].cat.categories),
    default=list(df_telemetry["transport_mode"].cat.categories)
)

# Filter Dataframe di level Python memory sebelum disajikan ke visual spec
filtered_mask = (
    df_telemetry["region"].isin(selected_regions) &
    df_telemetry["transport_mode"].isin(selected_modes)
)
df_filtered = df_telemetry[filtered_mask]

# ==========================================
# 04. TOP KPI CARDS EXECUTION
# ==========================================
st.title("🚚 Operational Logistics & SLA Mission Control")
st.markdown("Dashboard Analitik Deklaratif Pemantauan Deviasi SLA Logistik")

kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

total_shipments = len(df_filtered)
delayed_shipments = int((df_filtered["sla_status"] != "On-Time").sum())
sla_compliance_rate = ((total_shipments - delayed_shipments) / total_shipments * 100) if total_shipments > 0 else 0.0
avg_delay = float(df_filtered[df_filtered["delay_hours"] > 0]["delay_hours"].mean())
if np.isnan(avg_delay):
    avg_delay = 0.0

with kpi_col1:
    st.metric(label="Total Pengiriman", value=f"{total_shipments:,}")
with kpi_col2:
    st.metric(label="SLA Compliance Rate", value=f"{sla_compliance_rate:.2f}%", delta=f"{sla_compliance_rate - 85.0:.2f}% vs Target")
with kpi_col3:
    st.metric(label="Total Deviasi SLA (Late)", value=f"{delayed_shipments:,}", delta_color="inverse")
with kpi_col4:
    st.metric(label="Rata-rata Keterlambatan", value=f"{avg_delay:.2f} Jam")

st.divider()

# ==========================================
# 05. DECLARATIVE VISUAL ANALYTICS (ALTAIR)
# Cross-Filtering Interactivity Specs
# ==========================================

# 1. Definisi Selection Brush deklaratif untuk interaktivitas silang
brush_selection = alt.selection_interval(
    encodings=['x'],
    name="time_window_brush"
)

# 2. Chart Atas: Time-Series Density Volume vs SLA Failure
chart_timeline = alt.Chart(df_filtered).mark_area(opacity=0.6).encode(
    x=alt.X("yearmonthdate(timestamp):T", title="Tanggal Operasional"),
    y=alt.Y("count():Q", title="Volume Pengiriman"),
    color=alt.Color(
        "sla_status:N",
        scale=alt.Scale(
            domain=["On-Time", "Delayed", "Severely Delayed"],
            range=["#2ECC71", "#F39C12", "#E74C3C"]
        ),
        legend=alt.Legend(title="Status SLA")
    ),
    tooltip=[
        alt.Tooltip("yearmonthdate(timestamp):T", title="Tanggal"),
        alt.Tooltip("count():Q", title="Total Paket"),
        alt.Tooltip("sla_status:N", title="Status")
    ]
).properties(
    height=220,
    title="Tren Volume Pengiriman & Deviasi SLA Harian (Drag kursor untuk Filter Wilayah Bawah)"
).add_params(
    brush_selection
)

# 3. Chart Bawah Kiri: Regional SLA Compliance Bar Chart (Reaktif terhadap Brush)
chart_region = alt.Chart(df_filtered).mark_bar().encode(
    x=alt.X("count():Q", title="Jumlah Kasus"),
    y=alt.Y("region:N", title="Wilayah", sort="-x"),
    color=alt.Color("sla_status:N", legend=None),
    tooltip=[
        alt.Tooltip("region:N"),
        alt.Tooltip("sla_status:N"),
        alt.Tooltip("count():Q")
    ]
).transform_filter(
    brush_selection  # Transformasi deklaratif berbasis state seleksi chart timeline
).properties(
    height=280,
    title="Distribusi Status SLA per Wilayah"
)

# 4. Chart Bawah Kanan: Scatter Plot Korelasi Biaya Kirim vs Jam Keterlambatan
chart_scatter = alt.Chart(df_filtered[df_filtered["delay_hours"] > 0]).mark_circle(size=45, opacity=0.5).encode(
    x=alt.X("shipping_cost:Q", title="Biaya Pengiriman (IDR)", axis=alt.Axis(format="~s")),
    y=alt.Y("delay_hours:Q", title="Keterlambatan (Jam)"),
    color=alt.Color("transport_mode:N", title="Moda Armada"),
    tooltip=[
        alt.Tooltip("order_id:N"),
        alt.Tooltip("shipping_cost:Q", format=",.0f"),
        alt.Tooltip("delay_hours:Q", format=".2f"),
        alt.Tooltip("transport_mode:N")
    ]
).transform_filter(
    brush_selection
).properties(
    height=280,
    title="Korelasi Biaya vs. Lama Keterlambatan"
)

# ==========================================
# 06. COMPOSITION & RENDERING
# ==========================================
# Menggabungkan komponen chart secara deklaratif menggunakan vconcat (&) dan hconcat (|)
compound_dashboard = alt.vconcat(
    chart_timeline,
    alt.hconcat(chart_region, chart_scatter).resolve_scale(color='independent')
).configure_view(
    strokeWidth=0
).configure_axis(
    labelFontSize=11,
    titleFontSize=12
)

# Tampilkan ke container Streamlit
st.altair_chart(compound_dashboard, use_container_width=True)

# ==========================================
# 07. RAW DATA DRILLDOWN (LAZY PAGINATION)
# ==========================================
with st.expander("🔍 Inspeksi Sampel Data Anomali (Keterlambatan Ekstrem > 12 Jam)"):
    df_severe = df_filtered[df_filtered["delay_hours"] >= 12.0].sort_values(
        by="delay_hours", ascending=False
    ).head(100)
    
    st.dataframe(
        df_severe[[
            "order_id", "timestamp", "region", "transport_mode", 
            "delay_hours", "shipping_cost", "sla_status"
        ]],
        use_container_width=True,
        hide_index=True
    )

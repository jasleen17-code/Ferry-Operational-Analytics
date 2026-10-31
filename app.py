
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(
    page_title="Ferry Operational Analytics",
    page_icon="⛴️",
    layout="wide"
)

st.title("⛴️ Ferry Operational Analytics Dashboard")
st.markdown("### Capacity Utilization | Congestion | Idle Capacity | Efficiency")

DATA_FILE = Path(__file__).parent / "ferry_operational_analysis.csv"

@st.cache_data
def load_data():
    if not DATA_FILE.exists():
        return None

    data = pd.read_csv(DATA_FILE)

    if "timestamp" in data.columns:
        data["timestamp"] = pd.to_datetime(
            data["timestamp"], errors="coerce"
        )

    elif "Timestamp" in data.columns:
        data["Timestamp"] = pd.to_datetime(
            data["Timestamp"], errors="coerce"
        )
        data = data.rename(columns={"Timestamp": "timestamp"})

    data.columns = [
        c.strip().lower().replace(" ", "_")
        for c in data.columns
    ]

    return data

df = load_data()

if df is None:
    st.error("CSV file not found. Place ferry_operational_analysis.csv in the same folder as app.py.")
    st.stop()

if "timestamp" not in df.columns:
    st.error("Timestamp column is missing from the dataset.")
    st.stop()

df = df.dropna(subset=["timestamp"]).sort_values("timestamp")

numeric_cols = df.select_dtypes(include=np.number).columns

for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")

st.sidebar.header("Dashboard Filters")

min_date = df["timestamp"].min().date()
max_date = df["timestamp"].max().date()

date_range = st.sidebar.date_input(
    "Select Date Range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date

filtered = df[
    (df["timestamp"].dt.date >= start_date) &
    (df["timestamp"].dt.date <= end_date)
].copy()

if filtered.empty:
    st.warning("No data available for the selected dates.")
    st.stop()

if "sales_count" not in filtered.columns:
    filtered["sales_count"] = 0

if "redemption_count" not in filtered.columns:
    filtered["redemption_count"] = 0

filtered["sales_count"] = filtered["sales_count"].fillna(0)
filtered["redemption_count"] = filtered["redemption_count"].fillna(0)

if "total_activity_load" not in filtered.columns:
    filtered["total_activity_load"] = (
        filtered["sales_count"] + filtered["redemption_count"]
    )

if "capacity_utilization_ratio" not in filtered.columns:
    filtered["capacity_utilization_ratio"] = np.nan

if "congestion_pressure_index" not in filtered.columns:
    filtered["congestion_pressure_index"] = np.nan

if "oli_score" not in filtered.columns:
    filtered["oli_score"] = np.nan

if "idle_capacity_indicator" not in filtered.columns:
    filtered["idle_capacity_indicator"] = 0

st.sidebar.subheader("Analysis Settings")

granularity = st.sidebar.selectbox(
    "Time Granularity",
    ["15-Minute / Original", "Hourly", "Daily"]
)

threshold = st.sidebar.slider(
    "Congestion Threshold (%)",
    0, 100, 80
)

idle_threshold = st.sidebar.slider(
    "Idle Activity Threshold",
    0, 100, 20
)

if granularity == "Hourly":
    analysis = (
        filtered.set_index("timestamp")
        .resample("h")
        .agg({
            "sales_count": "sum",
            "redemption_count": "sum",
            "total_activity_load": "sum",
            "capacity_utilization_ratio": "mean",
            "congestion_pressure_index": "mean",
            "oli_score": "mean"
        })
        .reset_index()
    )

elif granularity == "Daily":
    analysis = (
        filtered.set_index("timestamp")
        .resample("D")
        .agg({
            "sales_count": "sum",
            "redemption_count": "sum",
            "total_activity_load": "sum",
            "capacity_utilization_ratio": "mean",
            "congestion_pressure_index": "mean",
            "oli_score": "mean"
        })
        .reset_index()
    )

else:
    analysis = filtered.copy()

analysis["total_activity_load"] = (
    analysis["sales_count"] + analysis["redemption_count"]
)

analysis["hour"] = analysis["timestamp"].dt.hour
analysis["day"] = analysis["timestamp"].dt.day_name()
analysis["month"] = analysis["timestamp"].dt.month_name()
analysis["year"] = analysis["timestamp"].dt.year
analysis["season"] = np.select(
    [
        analysis["timestamp"].dt.month.isin([3, 4, 5, 6]),
        analysis["timestamp"].dt.month.isin([7, 8, 9, 10]),
        analysis["timestamp"].dt.month.isin([11, 12, 1, 2])
    ],
    ["Summer", "Monsoon", "Winter"],
    default="Other"
)

if analysis["capacity_utilization_ratio"].max() <= 1:
    analysis["utilization_percent"] = (
        analysis["capacity_utilization_ratio"] * 100
    )
else:
    analysis["utilization_percent"] = (
        analysis["capacity_utilization_ratio"]
    )

analysis["utilization_percent"] = (
    analysis["utilization_percent"].clip(0, 100)
)

if analysis["utilization_percent"].isna().all():
    analysis["utilization_percent"] = (
        analysis["total_activity_load"] /
        max(analysis["total_activity_load"].max(), 1) * 100
    )

analysis["congestion_status"] = np.where(
    analysis["utilization_percent"] >= threshold,
    "Congestion",
    "Normal"
)

analysis["idle_status"] = np.where(
    analysis["utilization_percent"] <= idle_threshold,
    "Idle",
    "Active"
)

st.markdown("---")
st.header("1. Key Performance Indicators")

c1, c2, c3, c4 = st.columns(4)

avg_util = analysis["utilization_percent"].mean()
peak_util = analysis["utilization_percent"].max()
idle_pct = (analysis["idle_status"] == "Idle").mean() * 100
congestion_pct = (
    analysis["congestion_status"] == "Congestion"
).mean() * 100

c1.metric("Average Utilization", f"{avg_util:.2f}%")
c2.metric("Peak Utilization", f"{peak_util:.2f}%")
c3.metric("Idle Capacity", f"{idle_pct:.2f}%")
c4.metric("Congestion Intervals", f"{congestion_pct:.2f}%")

c5, c6, c7, c8 = st.columns(4)

c5.metric("Total Tickets Sold", f"{analysis['sales_count'].sum():,.0f}")
c6.metric("Total Redemptions", f"{analysis['redemption_count'].sum():,.0f}")
c7.metric("Total Activity", f"{analysis['total_activity_load'].sum():,.0f}")
c8.metric("Records Analysed", f"{len(analysis):,}")

st.markdown("---")
st.header("2. Capacity Utilization Timeline")

fig = px.line(
    analysis,
    x="timestamp",
    y="utilization_percent",
    title="Ferry Capacity Utilization Over Time",
    labels={
        "timestamp": "Date",
        "utilization_percent": "Utilization (%)"
    }
)

fig.add_hline(
    y=threshold,
    line_dash="dash",
    annotation_text="Congestion Threshold"
)

fig.update_layout(height=450)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.header("3. Congestion and Idle Capacity Analysis")

col1, col2 = st.columns(2)

with col1:
    fig = px.histogram(
        analysis,
        x="congestion_status",
        color="congestion_status",
        title="Congestion vs Normal Intervals"
    )
    st.plotly_chart(fig, use_container_width=True)

with col2:
    fig = px.histogram(
        analysis,
        x="idle_status",
        color="idle_status",
        title="Idle vs Active Intervals"
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.header("4. Hourly Congestion Heatmap")

heatmap_data = analysis.pivot_table(
    index="day",
    columns="hour",
    values="utilization_percent",
    aggfunc="mean"
)

day_order = [
    "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday", "Sunday"
]

heatmap_data = heatmap_data.reindex(
    [d for d in day_order if d in heatmap_data.index]
)

fig = px.imshow(
    heatmap_data,
    color_continuous_scale="RdYlGn_r",
    title="Day vs Hour Utilization Heatmap",
    labels=dict(
        x="Hour",
        y="Day",
        color="Utilization %"
    ),
    aspect="auto"
)

st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.header("5. Seasonal Efficiency Comparison")

season_data = (
    analysis.groupby("season")
    .agg(
        Average_Utilization=("utilization_percent", "mean"),
        Total_Activity=("total_activity_load", "sum"),
        Sales=("sales_count", "sum"),
        Redemptions=("redemption_count", "sum")
    )
    .reset_index()
)

fig = px.bar(
    season_data,
    x="season",
    y="Average_Utilization",
    color="season",
    title="Average Capacity Utilization by Season"
)

st.plotly_chart(fig, use_container_width=True)
st.dataframe(season_data, use_container_width=True)

st.markdown("---")
st.header("6. Weekday vs Weekend Efficiency")

analysis["day_type"] = np.where(
    analysis["timestamp"].dt.dayofweek >= 5,
    "Weekend",
    "Weekday"
)

day_comparison = (
    analysis.groupby("day_type")
    .agg(
        Average_Utilization=("utilization_percent", "mean"),
        Total_Activity=("total_activity_load", "sum")
    )
    .reset_index()
)

fig = px.bar(
    day_comparison,
    x="day_type",
    y="Average_Utilization",
    color="day_type",
    title="Weekday vs Weekend Utilization"
)

st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.header("7. Morning, Afternoon and Evening Analysis")

analysis["time_band"] = pd.cut(
    analysis["hour"],
    bins=[-1, 11, 16, 23],
    labels=["Morning", "Afternoon", "Evening"]
)

time_analysis = (
    analysis.groupby("time_band", observed=False)
    ["utilization_percent"].mean()
    .reset_index()
)

fig = px.bar(
    time_analysis,
    x="time_band",
    y="utilization_percent",
    color="time_band",
    title="Time Band Efficiency"
)

st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.header("8. Annual Operational Trends")

year_analysis = (
    analysis.groupby("year")
    .agg(
        Average_Utilization=("utilization_percent", "mean"),
        Total_Activity=("total_activity_load", "sum")
    )
    .reset_index()
)

fig = px.line(
    year_analysis,
    x="year",
    y="Average_Utilization",
    markers=True,
    title="Year-wise Capacity Utilization Trend"
)

st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.header("9. Operational Load Index")

if analysis["oli_score"].notna().any():
    fig = px.line(
        analysis,
        x="timestamp",
        y="oli_score",
        title="Operational Load Index Trend"
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("OLI values are not available in this exported dataset.")

st.markdown("---")
st.header("10. Peak Congestion and Idle Periods")

congestion_data = analysis[
    analysis["utilization_percent"] >= threshold
].sort_values("utilization_percent", ascending=False)

idle_data = analysis[
    analysis["utilization_percent"] <= idle_threshold
].sort_values("utilization_percent")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Highest Pressure Intervals")
    st.dataframe(
        congestion_data[
            ["timestamp", "total_activity_load", "utilization_percent"]
        ].head(20),
        use_container_width=True
    )

with col2:
    st.subheader("Idle Capacity Intervals")
    st.dataframe(
        idle_data[
            ["timestamp", "total_activity_load", "utilization_percent"]
        ].head(20),
        use_container_width=True
    )

st.markdown("---")
st.header("11. Operational Recommendations")

if avg_util >= threshold:
    st.warning(
        "High average utilization detected. Review ferry deployment "
        "and consider additional capacity during high-pressure periods."
    )
elif idle_pct >= 30:
    st.info(
        "Significant idle capacity detected. Consider adjusting "
        "schedules and reallocating resources during low-activity periods."
    )
else:
    st.success(
        "Overall utilization is within the selected operational thresholds."
    )

if congestion_pct > 20:
    st.warning("Frequent congestion intervals detected. Review peak-period scheduling.")

if idle_pct > 20:
    st.info("Idle periods are significant. Consider optimizing off-peak deployment.")

st.markdown("---")
st.header("12. Download Analytical Results")

csv = analysis.to_csv(index=False).encode("utf-8")

st.download_button(
    "Download Filtered Analysis CSV",
    data=csv,
    file_name="ferry_operational_dashboard_results.csv",
    mime="text/csv"
)

st.download_button(
    "Download Seasonal Analysis",
    data=season_data.to_csv(index=False).encode("utf-8"),
    file_name="ferry_seasonal_analysis.csv",
    mime="text/csv"
)

st.success("Ferry Operational Analytics Dashboard Loaded Successfully.")

st.caption(
    "Ferry Operational Analytics | Data-driven Capacity and Resource Optimization"
)

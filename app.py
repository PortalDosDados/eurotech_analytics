import streamlit as st
import pandas as pd
import sqlite3
import os

# -------------------------------
# CONFIG
# -------------------------------
st.set_page_config(page_title="Monitoramento de Motor", layout="wide")


# -------------------------------
# CARGA DE DADOS (AGORA DO SQLITE)
# -------------------------------
@st.cache_data(ttl=60)
def carregar_dados():
    try:
        conn = sqlite3.connect("motor.db")
        df = pd.read_sql("SELECT * FROM dados", conn)
        conn.close()

        df["data_hora"] = pd.to_datetime(df["data_hora"], errors="coerce")

        df = (
            df.dropna(subset=["data_hora"])
            .sort_values("data_hora")
            .drop_duplicates("data_hora")
        )

        return df

    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()


# -------------------------------
# FUNÇÕES AUXILIARES
# -------------------------------
def aggregate_time(df, col="temp_motor_1", freq="H"):
    if df.empty or col not in df.columns:
        return pd.DataFrame()

    df2 = df.set_index("data_hora").sort_index()
    agg = df2[col].resample(freq).agg(["mean", "median", "std", "min", "max", "count"])
    agg = agg.dropna(subset=["mean"])

    return agg


def aggregate_all_means(df, freq="H"):
    if df.empty:
        return pd.DataFrame()

    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    if not numeric_cols:
        return pd.DataFrame()

    df2 = df.set_index("data_hora").sort_index()
    agg_mean = df2[numeric_cols].resample(freq).mean()
    agg_mean = agg_mean.dropna(how="all")

    return agg_mean


def calcular_kpi(df, coluna):
    if coluna not in df.columns:
        return None, None

    serie = df[coluna].dropna()

    if serie.empty:
        return None, None

    return round(serie.mean(), 2), round(serie.max(), 2)


def fmt(x):
    return f"{x:.2f}" if isinstance(x, (int, float)) else "—"


# -------------------------------
# APP
# -------------------------------
df = carregar_dados()

if df.empty:
    st.warning("Sem dados no banco")
    st.stop()


# -------------------------------
# HEADER
# -------------------------------

col1, col2, col3 = st.columns([1, 1, 1])

with col2:
    st.image("assets/banner_new.png", width=600)

st.title("🛩️ Painel de Bordo - Monitoramento de Motor")


# -------------------------------
# FILTROS
# -------------------------------
f_col1, f_col2, f_col3 = st.columns([1, 1, 1])

with f_col1:
    data_inicio = st.date_input("Data inicial", df["data_hora"].min().date())

with f_col2:
    data_fim = st.date_input("Data final", df["data_hora"].max().date())

with f_col3:
    freq_label = st.selectbox(
        "Intervalo de agregação", ["Dia", "Hora", "Minuto"], index=1
    )
    freq_map = {"Dia": "D", "Hora": "H", "Minuto": "5T"}
    freq = freq_map.get(freq_label, "H")


# filtro
df_filtrado = df[
    (df["data_hora"].dt.date >= data_inicio) & (df["data_hora"].dt.date <= data_fim)
]

df_agg = aggregate_time(df_filtrado, "temp_motor_1", freq=freq)
df_agg_mean = aggregate_all_means(df_filtrado, freq=freq)


# -------------------------------
# KPIs
# -------------------------------


def kpi_centered(label, value, delta=None):
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.metric(label, value, delta)


if not df_agg.empty:
    df_agg = df_agg.round(2)
    media_temp = df_agg["mean"].mean()
    max_temp = df_agg["max"].max()
else:
    media_temp, max_temp = None, None

if not df_agg_mean.empty:
    media_vib = (
        df_agg_mean["vel_rms"].mean() if "vel_rms" in df_agg_mean.columns else None
    )
    max_vib = df_agg_mean["vel_rms"].max() if "vel_rms" in df_agg_mean.columns else None
    media_tensao = (
        df_agg_mean["tensao"].mean() if "tensao" in df_agg_mean.columns else None
    )
    media_corrente = (
        df_agg_mean["corrente"].mean() if "corrente" in df_agg_mean.columns else None
    )
else:
    media_vib, max_vib = calcular_kpi(df_filtrado, "vel_rms")
    media_tensao, _ = calcular_kpi(df_filtrado, "tensao")
    media_corrente, _ = calcular_kpi(df_filtrado, "corrente")


# KPIs centralizados (mobile friendly)
kpi_centered("🌡️ Temp Motor", fmt(media_temp), f"Max {fmt(max_temp)}")
kpi_centered("📳 Vibração", fmt(media_vib), f"Max {fmt(max_vib)}")
kpi_centered("⚡ Tensão", fmt(media_tensao))
kpi_centered("🔌 Corrente", fmt(media_corrente))


# -------------------------------
# ALERTA
# -------------------------------
if "vel_rms" in df_filtrado.columns:
    max_vib_alert = df_filtrado["vel_rms"].max()
    if pd.notna(max_vib_alert) and max_vib_alert > 2.0:
        st.error(f"⚠️ ALERTA: Vibração crítica ({round(max_vib_alert, 2)})")


# -------------------------------
# GRÁFICOS
# -------------------------------
df_plot = df_filtrado.set_index("data_hora")

linha1_col1, linha1_col2 = st.columns(2)
linha2_col1, linha2_col2 = st.columns(2)

with linha1_col1:
    st.subheader("🌡️ Temperatura")
    if not df_agg.empty:
        plot_df = df_agg[["mean"]].rename(columns={"mean": "Média"})
        st.line_chart(plot_df.round(2), height=200)

with linha1_col2:
    st.subheader("📳 Vibração RMS")
    if not df_agg_mean.empty and "vel_rms" in df_agg_mean.columns:
        st.line_chart(df_agg_mean[["vel_rms"]].round(2), height=200)
    elif "vel_rms" in df_plot.columns:
        st.line_chart(df_plot["vel_rms"].round(2), height=200)

with linha2_col1:
    st.subheader("⚡ Tensão")
    if not df_agg_mean.empty and "tensao" in df_agg_mean.columns:
        st.line_chart(df_agg_mean[["tensao"]].round(2), height=200)
    elif "tensao" in df_plot.columns:
        st.line_chart(df_plot["tensao"].round(2), height=200)

with linha2_col2:
    st.subheader("🔌 Corrente")
    if not df_agg_mean.empty and "corrente" in df_agg_mean.columns:
        st.line_chart(df_agg_mean[["corrente"]].round(2), height=200)
    elif "corrente" in df_plot.columns:
        st.line_chart(df_plot["corrente"].round(2), height=200)


# -------------------------------
# TABELA
# -------------------------------
st.subheader("📋 Últimos Registros")

df_display = df_filtrado.sort_values("data_hora", ascending=False).head(10).copy()

num_cols = df_display.select_dtypes(include=["number"]).columns.tolist()
if num_cols:
    df_display.loc[:, num_cols] = df_display[num_cols].round(2)

st.dataframe(df_display, height=200)

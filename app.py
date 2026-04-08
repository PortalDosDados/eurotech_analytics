import streamlit as st
import pandas as pd
import sqlite3

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
# KPIs
# -------------------------------
def calcular_kpi(df, coluna):
    if coluna not in df:
        return None, None

    serie = df[coluna].dropna()

    if serie.empty:
        return None, None

    return round(serie.mean(), 2), round(serie.max(), 2)


# -------------------------------
# APP
# -------------------------------
df = carregar_dados()

if df.empty:
    st.warning("Sem dados no banco")
    st.stop()

# -------------------------------
# FILTROS
# -------------------------------
st.sidebar.title("Filtros")

data_inicio = st.sidebar.date_input("Data inicial", df["data_hora"].min().date())

data_fim = st.sidebar.date_input("Data final", df["data_hora"].max().date())

df_filtrado = df[
    (df["data_hora"].dt.date >= data_inicio) & (df["data_hora"].dt.date <= data_fim)
]

# -------------------------------
# HEADER
# -------------------------------
st.title("🛩️ Painel de Bordo - Monitoramento de Motor")

# -------------------------------
# KPIs
# -------------------------------
col1, col2, col3, col4 = st.columns(4)

media_temp, max_temp = calcular_kpi(df_filtrado, "temp_motor_1")
media_vib, max_vib = calcular_kpi(df_filtrado, "vel_rms")
media_tensao, _ = calcular_kpi(df_filtrado, "tensao")
media_corrente, _ = calcular_kpi(df_filtrado, "corrente")

col1.metric("🌡️ Temp Motor", media_temp, f"Max {max_temp}")
col2.metric("📳 Vibração", media_vib, f"Max {max_vib}")
col3.metric("⚡ Tensão", media_tensao)
col4.metric("🔌 Corrente", media_corrente)

# -------------------------------
# ALERTA
# -------------------------------
if "vel_rms" in df_filtrado:
    max_vib = df_filtrado["vel_rms"].max()
    if pd.notna(max_vib) and max_vib > 2.0:
        st.error(f"⚠️ ALERTA: Vibração crítica ({round(max_vib,2)})")

# -------------------------------
# GRID (SEM SCROLL)
# -------------------------------
df_plot = df_filtrado.set_index("data_hora")

linha1_col1, linha1_col2 = st.columns(2)
linha2_col1, linha2_col2 = st.columns(2)

with linha1_col1:
    st.subheader("🌡️ Temperatura")
    if "temp_motor_1" in df_plot:
        st.line_chart(df_plot["temp_motor_1"], height=200)

with linha1_col2:
    st.subheader("📳 Vibração RMS")
    if "vel_rms" in df_plot:
        st.line_chart(df_plot["vel_rms"], height=200)

with linha2_col1:
    st.subheader("⚡ Tensão")
    if "tensao" in df_plot:
        st.line_chart(df_plot["tensao"], height=200)

with linha2_col2:
    st.subheader("🔌 Corrente")
    if "corrente" in df_plot:
        st.line_chart(df_plot["corrente"], height=200)

# -------------------------------
# TABELA
# -------------------------------
st.subheader("📋 Últimos Registros")

st.dataframe(df_filtrado.sort_values("data_hora", ascending=False).head(10), height=200)

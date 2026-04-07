import streamlit as st
import pandas as pd
import requests
from io import StringIO

# -------------------------------
# CONFIG
# -------------------------------
st.set_page_config(page_title="Monitoramento de Motor", layout="wide")

URL = "https://docs.google.com/spreadsheets/d/1m36eKlRRDIuc_1ZhaMEzPX1Pa0miLULj9Nnni6tcnIU/export?format=csv&gid=1669276523"


# -------------------------------
# FUNÇÃO DE CARGA E TRATAMENTO
# -------------------------------
@st.cache_data(ttl=60)
def carregar_dados():
    response = requests.get(URL)
    response.raise_for_status()

    df = pd.read_csv(StringIO(response.text))

    # -------------------------------
    # NORMALIZAR NOMES DAS COLUNAS
    # -------------------------------
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace(".", "", regex=False)
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("utf-8")
    )

    # -------------------------------
    # DETECTAR COLUNA DE DATA
    # -------------------------------
    col_data = None
    for col in df.columns:
        if "data" in col:
            col_data = col
            break

    if col_data is None:
        st.error(
            f"❌ Coluna de data não encontrada. Colunas disponíveis: {df.columns.tolist()}"
        )
        st.stop()

    # -------------------------------
    # MAPEAR COLUNAS (FLEXÍVEL)
    # -------------------------------
    colunas_map = {
        col_data: "data_hora",
        "tmotor": "temp_motor_1",
        "temp_ambiente": "temp_ambiente",
        "umidade": "umidade",
        "v": "tensao",
        "a": "corrente",
        "p": "potencia",
        "velrms": "vel_rms",
        "tempmotor": "temp_motor_2",
        "vel_vibratoria": "vel_vibratoria",
    }

    colunas_existentes = {k: v for k, v in colunas_map.items() if k in df.columns}

    df = df[list(colunas_existentes.keys())]
    df.rename(columns=colunas_existentes, inplace=True)

    # -------------------------------
    # LIMPEZA DE DADOS
    # -------------------------------
    df.replace("#REF!", pd.NA, inplace=True)

    # Corrigir vírgula decimal
    for col in df.columns:
        df[col] = df[col].astype(str).str.replace(",", ".", regex=False)

    # Converter numérico
    for col in df.columns:
        if col != "data_hora":
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Converter data
    df["data_hora"] = pd.to_datetime(
        df["data_hora"], dayfirst=True, format="mixed", errors="coerce"
    )

    # Remover inválidos
    df = df.dropna(subset=["data_hora"])

    return df


# -------------------------------
# CARREGAR DADOS
# -------------------------------
df = carregar_dados()

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
# TÍTULO
# -------------------------------
st.title("📊 Monitoramento de Motor")


# -------------------------------
# KPIs
# -------------------------------
def media_segura(col):
    if col in df_filtrado:
        return round(df_filtrado[col].dropna().mean(), 2)
    return 0


col1, col2, col3, col4 = st.columns(4)

col1.metric("Temp Motor (°C)", media_segura("temp_motor_1"))
col2.metric("Vibração RMS", media_segura("vel_rms"))
col3.metric("Tensão (V)", media_segura("tensao"))
col4.metric("Corrente (A)", media_segura("corrente"))

# -------------------------------
# ALERTA
# -------------------------------
if "vel_rms" in df_filtrado:
    if df_filtrado["vel_rms"].dropna().max() > 2.0:
        st.error("⚠️ Vibração acima do limite!")

# -------------------------------
# GRÁFICOS
# -------------------------------
st.subheader("📈 Temperatura do Motor")

if "temp_motor_1" in df_filtrado:
    st.line_chart(df_filtrado.set_index("data_hora")["temp_motor_1"])

st.subheader("📈 Vibração RMS")

if "vel_rms" in df_filtrado:
    st.line_chart(df_filtrado.set_index("data_hora")["vel_rms"])

st.subheader("📈 Corrente x Tensão")

if "tensao" in df_filtrado and "corrente" in df_filtrado:
    st.line_chart(df_filtrado.set_index("data_hora")[["tensao", "corrente"]])

# -------------------------------
# TABELA
# -------------------------------
st.subheader("📋 Dados recentes")

st.dataframe(df_filtrado.sort_values("data_hora", ascending=False).head(50))

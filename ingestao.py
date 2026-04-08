import pandas as pd
import sqlite3
import requests
from io import StringIO
from datetime import datetime

# URL da planilha (export CSV)
URL = "https://docs.google.com/spreadsheets/d/1m36eKlRRDIuc_1ZhaMEzPX1Pa0miLULj9Nnni6tcnIU/export?format=csv&gid=1669276523"

DB_PATH = "motor.db"


# -------------------------------
# LOG
# -------------------------------
def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


# -------------------------------
# CONEXÃO
# -------------------------------
def get_connection():
    return sqlite3.connect(DB_PATH)


# -------------------------------
# CRIAR TABELA
# -------------------------------
def criar_tabela():
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dados (
            data_hora TEXT PRIMARY KEY,
            temp_motor_1 REAL,
            temp_motor_2 REAL,
            vel_rms REAL,
            tensao REAL,
            corrente REAL
        )
    """
    )
    conn.commit()
    conn.close()


# -------------------------------
# ÚLTIMA DATA
# -------------------------------
def get_ultima_data():
    conn = get_connection()
    try:
        df = pd.read_sql("SELECT MAX(data_hora) as max_data FROM dados", conn)
        ultima_data = df["max_data"].iloc[0]
        return pd.to_datetime(ultima_data) if ultima_data else None
    except:
        return None
    finally:
        conn.close()


# -------------------------------
# CARREGAR PLANILHA
# -------------------------------
def carregar_planilha():
    # Requisição com timeout e checagem
    response = requests.get(URL, timeout=10)
    response.raise_for_status()

    df = pd.read_csv(
        StringIO(response.text), sep=",", engine="python", on_bad_lines="skip"
    )

    log(f"Colunas encontradas: {df.columns.tolist()}")

    # -------------------------------
    # NORMALIZAÇÃO DE COLUNAS
    # -------------------------------
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace(".", "", regex=False)
        .str.replace("/", "_", regex=False)
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("utf-8")
    )

    log(f"Colunas normalizadas: {df.columns.tolist()}")

    # Garantir nomes de colunas únicos (se duplicados, renomeia com sufixo)
    if df.columns.duplicated().any():
        counts = {}
        new_cols = []
        for c in df.columns:
            if c in counts:
                counts[c] += 1
                new_cols.append(f"{c}_dup{counts[c]}")
            else:
                counts[c] = 0
                new_cols.append(c)
        df.columns = new_cols
        log(f"Colunas duplicadas renomeadas: {df.columns.tolist()}")

    # -------------------------------
    # IDENTIFICAR COLUNA DE DATA
    # -------------------------------
    col_data = None
    possiveis = ["data", "date", "datetime", "timestamp", "hora"]

    for col in df.columns:
        if any(p in col for p in possiveis):
            col_data = col
            break

    if col_data is None:
        raise ValueError(
            f"Coluna de data não encontrada. Colunas: {df.columns.tolist()}"
        )

    log(f"Coluna de data identificada: {col_data}")

    # -------------------------------
    # RENOMEAR COLUNAS IMPORTANTES
    # -------------------------------
    df.rename(
        columns={
            col_data: "data_hora",
            "tmotor": "temp_motor_1",
            "temp_motor": "temp_motor_2",
            "velrms": "vel_rms",
            "v": "tensao",
            "a": "corrente",
        },
        inplace=True,
    )

    # -------------------------------
    # LIMPEZA NUMÉRICA (ROBUSTA)
    # -------------------------------
    for col in df.columns:
        if col == "data_hora":
            continue

        col_data = df[col]

        # Se por algum motivo a seleção retornou um DataFrame, pegue a primeira coluna
        if isinstance(col_data, pd.DataFrame):
            col_data = col_data.iloc[:, 0]

        # Forçar string, substituir vírgula por ponto e converter para numérico
        col_data = col_data.astype(str).str.replace(",", ".", regex=False)
        df[col] = pd.to_numeric(col_data, errors="coerce")

    # -------------------------------
    # TRATAMENTO DE DATA
    # -------------------------------
    df["data_hora"] = pd.to_datetime(df["data_hora"], errors="coerce")
    df = df.dropna(subset=["data_hora"])

    return df


# -------------------------------
# FILTRAR NOVOS REGISTROS
# -------------------------------
def filtrar_novos(df, ultima_data):
    if ultima_data is None:
        return df
    return df[df["data_hora"] > ultima_data]


# -------------------------------
# SALVAR NO BANCO
# -------------------------------
def salvar_no_banco(df):
    if df.empty:
        log("Nenhum novo dado para inserir.")
        return

    # Normalizar data_hora para string compatível e remover duplicatas
    df = df.dropna(subset=["data_hora"]).copy()
    df["data_hora"] = pd.to_datetime(df["data_hora"], errors="coerce")
    df = df.dropna(subset=["data_hora"])  # garantir

    # Converter para formato consistente antes de comparar/insert
    df["data_hora"] = df["data_hora"].dt.strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()

    # Evitar inserir registros já presentes: buscar chaves existentes
    try:
        existing = pd.read_sql("SELECT data_hora FROM dados", conn)
        existing_set = set(existing["data_hora"].astype(str).tolist())
    except Exception:
        existing_set = set()

    df = df[~df["data_hora"].astype(str).isin(existing_set)]

    if df.empty:
        log("Nenhum novo dado após deduplicação com o banco.")
        conn.close()
        return

    # Alinhar colunas do DataFrame com o schema da tabela no banco
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(dados)")
        cols_info = cur.fetchall()
        db_cols = [c[1] for c in cols_info]
        # Garantir que todas as colunas do DB existam no DF (preencher com NaN se necessário)
        for c in db_cols:
            if c not in df.columns:
                df[c] = pd.NA

        # Reordenar/selecionar apenas colunas do DB
        df_to_insert = df[db_cols]
    except Exception:
        df_to_insert = df

    # Inserir usando INSERT OR IGNORE para evitar violação de UNIQUE
    try:
        cur = conn.cursor()
        cols_placeholders = ",".join(["?"] * len(df_to_insert.columns))
        cols_names = ",".join([f"{c}" for c in df_to_insert.columns])

        # Converter NaN/NA para None e preparar tuplas
        data_tuples = (
            [None if pd.isna(x) else x for x in row]
            for row in df_to_insert.itertuples(index=False, name=None)
        )

        stmt = (
            f"INSERT OR IGNORE INTO dados ({cols_names}) VALUES ({cols_placeholders})"
        )
        cur.executemany(stmt, data_tuples)
        conn.commit()

        # contar quantos foram inseridos (sqlite total_changes)
        inserted = conn.total_changes
    except Exception as e:
        conn.close()
        raise

    conn.close()

    log(f"{inserted} registros inseridos.")


# -------------------------------
# PIPELINE
# -------------------------------
def executar_pipeline():
    log("Iniciando pipeline...")

    criar_tabela()

    ultima_data = get_ultima_data()

    if ultima_data:
        log(f"Última data no banco: {ultima_data}")
    else:
        log("Banco vazio. Primeira carga completa.")

    df = carregar_planilha()

    df_novo = filtrar_novos(df, ultima_data)

    salvar_no_banco(df_novo)

    log("Pipeline finalizado.")


# -------------------------------
# EXECUÇÃO
# -------------------------------
if __name__ == "__main__":
    executar_pipeline()

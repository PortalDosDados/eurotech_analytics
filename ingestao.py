import pandas as pd
import sqlite3
import requests
from io import StringIO

URL = "SUA_URL_AQUI"


def carregar_planilha():
    response = requests.get(URL)
    df = pd.read_csv(StringIO(response.text))

    df.columns = df.columns.str.strip().str.lower()

    df.rename(
        columns={
            "data": "data_hora",
            "tmotor": "temp_motor_1",
            "velrms": "vel_rms",
            "v": "tensao",
            "a": "corrente",
        },
        inplace=True,
    )

    df["data_hora"] = pd.to_datetime(df["data_hora"], errors="coerce")

    return df.dropna(subset=["data_hora"])


def inserir_somente_novos(df):
    conn = sqlite3.connect("motor.db")

    existentes = pd.read_sql("SELECT data_hora FROM dados", conn)

    df_novos = df[~df["data_hora"].astype(str).isin(existentes["data_hora"])]

    df_novos.to_sql("dados", conn, if_exists="append", index=False)

    print(f"{len(df_novos)} novos registros inseridos")

    conn.close()


if __name__ == "__main__":
    df = carregar_planilha()
    inserir_somente_novos(df)

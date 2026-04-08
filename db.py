import sqlite3


def criar_banco():
    conn = sqlite3.connect("motor.db")
    cursor = conn.cursor()

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS dados (
        data_hora TEXT PRIMARY KEY,
        temp_motor_1 REAL,
        vel_rms REAL,
        tensao REAL,
        corrente REAL
    )
    """
    )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    criar_banco()

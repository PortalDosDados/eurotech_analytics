import sqlite3

conn = sqlite3.connect("motor.db")
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print(cursor.fetchall())

cursor.execute("SELECT COUNT(*) FROM dados;")
print(cursor.fetchone())

conn.close()

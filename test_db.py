import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Pega as env vars que você exportou
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=5432  # padrão PostgreSQL
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT version();")
    version = cur.fetchone()
    print("✅ Conexão OK! Versão PostgreSQL:", version[0])
    cur.execute("SELECT current_database();")
    db = cur.fetchone()
    print("📊 Banco conectado:", db[0])
    cur.close()
    conn.close()
except Exception as e:
    print("❌ Erro na conexão:", e)
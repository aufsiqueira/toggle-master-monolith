import os
import click
from flask import Flask, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import boto3
from botocore.exceptions import ClientError

app = Flask(__name__)

# Nome/ARN do secret e região
SECRET_NAME = os.getenv("techchallenge/3DCLT/app/togglemaster")
REGION_NAME = os.getenv("AWS_REGION", "us-east-1")

def load_db_credentials_from_secret():
    if not SECRET_NAME:
        raise RuntimeError("DB_SECRET_NAME não definido nas variáveis de ambiente")

    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=REGION_NAME)

    try:
        response = client.get_secret_value(SecretId=SECRET_NAME)
    except ClientError as e:
        raise RuntimeError(f"Erro ao buscar secret {SECRET_NAME} no Secrets Manager: {e}")

    # SecretString (texto)
    secret_string = response.get("SecretString")
    if not secret_string:
        raise RuntimeError(f"Secret {SECRET_NAME} não contém campo SecretString")

    secret_dict = json.loads(secret_string)

    return {
        "host": secret_dict["host"],
        "dbname": secret_dict.get("dbname", "postgres"),
        "user": secret_dict["username"],
        "password": secret_dict["password"],
        "port": secret_dict.get("port", 5432),
    }

# Tenta carregar do Secrets Manager; se falhar, cai para env vars
try:
    creds = load_db_credentials_from_secret()
    DB_HOST = creds["host"]
    DB_NAME = creds["dbname"]
    DB_USER = creds["user"]
    DB_PASSWORD = creds["password"]
    DB_PORT = creds["port"]
except Exception as e:
    print(f"Não foi possível carregar credenciais do Secrets Manager, usando env vars. Detalhes: {e}")
    
    DB_HOST = os.getenv("DB_HOST")
    DB_NAME = os.getenv("DB_NAME", "postgres")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_PORT = int(os.getenv("DB_PORT", "5432"))


def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT,
    )
    return conn

def init_db():
    print("Tentando inicializar a tabela 'flags'...")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS flags (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                is_enabled BOOLEAN NOT NULL DEFAULT false,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("Tabela 'flags' inicializada com sucesso.")
    except psycopg2.OperationalError as e:
        print(f"Erro de conexão ao inicializar o banco de dados: {e}")
    except Exception as e:
        print(f"Um erro inesperado ocorreu durante a inicialização do DB: {e}")

@app.cli.command("init-db")
def init_db_command():
    init_db()

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok"}), 200

@app.route('/flags', methods=['POST'])
def create_flag():
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({"error": "O campo 'name' é obrigatório"}), 400
    
    name = data['name']
    is_enabled = data.get('is_enabled', False)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO flags (name, is_enabled) VALUES (%s, %s)", (name, is_enabled))
        conn.commit()
    except psycopg2.IntegrityError:
        return jsonify({"error": f"A flag '{name}' já existe"}), 409
    except Exception as e:
        return jsonify({"error": "Erro interno no servidor ao criar a flag", "details": str(e)}), 500
    finally:
        if 'cur' in locals() and not cur.closed:
            cur.close()
        if 'conn' in locals() and not conn.closed:
            conn.close()
            
    return jsonify({"message": f"Flag '{name}' criada com sucesso"}), 201

@app.route('/flags', methods=['GET'])
def get_flags():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT name, is_enabled FROM flags ORDER BY name")
        flags = cur.fetchall()
    except Exception as e:
        return jsonify({"error": "Erro interno no servidor ao buscar as flags", "details": str(e)}), 500
    finally:
        if 'cur' in locals() and not cur.closed:
            cur.close()
        if 'conn' in locals() and not conn.closed:
            conn.close()

    return jsonify(flags), 200

@app.route('/flags/<string:name>', methods=['GET'])
def get_flag_status(name):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT name, is_enabled FROM flags WHERE name = %s", (name,))
        flag = cur.fetchone()
    except Exception as e:
        return jsonify({"error": "Erro interno no servidor ao buscar a flag", "details": str(e)}), 500
    finally:
        if 'cur' in locals() and not cur.closed:
            cur.close()
        if 'conn' in locals() and not conn.closed:
            conn.close()
    
    if flag:
        return jsonify(flag), 200
    return jsonify({"error": "Flag não encontrada"}), 404

@app.route('/flags/<string:name>', methods=['PUT'])
def update_flag(name):
    data = request.get_json()
    if data is None or 'is_enabled' not in data or not isinstance(data['is_enabled'], bool):
        return jsonify({"error": "O campo 'is_enabled' (booleano) é obrigatório"}), 400
        
    is_enabled = data['is_enabled']
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE flags SET is_enabled = %s WHERE name = %s", (is_enabled, name))
        
        if cur.rowcount == 0:
            return jsonify({"error": "Flag não encontrada"}), 404
            
        conn.commit()
    except Exception as e:
        return jsonify({"error": "Erro interno no servidor ao atualizar a flag", "details": str(e)}), 500
    finally:
        if 'cur' in locals() and not cur.closed:
            cur.close()
        if 'conn' in locals() and not conn.closed:
            conn.close()
    
    return jsonify({"message": f"Flag '{name}' atualizada"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
import os
import json
import click
import boto3
from botocore.exceptions import ClientError
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Nome/ARN do secret e região
SECRET_NAME = "techchallenge/3DCLT/app/togglemaster"
REGION_NAME = "us-east-1"

def load_db_credentials_from_secret():
    if not SECRET_NAME:
        raise RuntimeError("DB_SECRET_NAME não definido nas variáveis de ambiente")

    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=REGION_NAME)

    try:
        response = client.get_secret_value(SecretId=SECRET_NAME)
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print("The requested secret " + SECRET_NAME + " was not found")
        elif e.response['Error']['Code'] == 'InvalidRequestException':
            print("The request was invalid due to:", e)
        elif e.response['Error']['Code'] == 'InvalidParameterException':
            print("The request had invalid params:", e)
        elif e.response['Error']['Code'] == 'DecryptionFailure':
            print("The requested secret can't be decrypted using the provided KMS key:", e)
        elif e.response['Error']['Code'] == 'InternalServiceError':
            print("An error occurred on service side:", e)

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

try:
    creds = load_db_credentials_from_secret()
    conn = psycopg2.connect(
        host= creds["host"],
        database= creds["dbname"],
        user= creds["user"],
        password= creds["password"],
        port= creds["port"]
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
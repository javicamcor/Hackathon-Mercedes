import json
import sqlite3
import datetime
import hashlib  # Añadido para generar el hash de la caché

DB_NAME = "finops.db"
LLAMA_TOKEN_RATIO_VS_MISTRAL = 0.82  # llama usa ~18% menos tokens que mistral


def _ensure_column(cursor, table_name: str, column_name: str, column_definition: str):
    """Añade una columna si no existe para mantener compatibilidad con bases ya creadas."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing_columns = {row[1] for row in cursor.fetchall()}
    if column_name not in existing_columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_definition}")

def init_db():
    """Crea las tablas si no existen."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Tabla de Consumidores (Equipos)
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS consumers (
                                                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                            name TEXT UNIQUE,
                                                            budget_limit REAL,
                                                            current_spend REAL DEFAULT 0.0
                   )
                   ''')

    # Tabla de Logs de llamadas a la IA
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS logs (
                                                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                       consumer_name TEXT,
                                                       requested_model TEXT,
                                                       provider_model TEXT,
                                                       prompt_tokens INTEGER,
                                                       completion_tokens INTEGER,
                                                       total_cost REAL,
                                                       applied_rule TEXT,
                                                       savings REAL,
                                                       timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                   )
                   ''')

    # NUEVA TABLA: Caché de respuestas
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS cache (
                                                        prompt_hash TEXT PRIMARY KEY,
                                                        respuesta_texto TEXT,
                                                        modelo_usado TEXT
                   )
                   ''')

    # NUEVA TABLA: Alertas FinOps
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS alerts (
                                                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                         consumer_name TEXT,
                                                         message TEXT,
                                                         timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                   )
                   ''')

    conn.commit()
    conn.close()
    print("Base de datos inicializada")

def insertar_consumidores_prueba():
    """Inserta dos consumidores base para poder realizar las pruebas del Hackathon."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Lista de equipos de prueba: (nombre, limite_presupuesto, gasto_inicial)
    equipos_prueba = [
        ("equipo_desarrollo", 10.0, 0.0),    # Presupuesto holgado
        ("equipo_marketing", 2.0, 1.95)    # Presupuesto casi agotado (para forzar la regla FinOps)
    ]

    # Usamos INSERT OR IGNORE para que no falle si la función se ejecuta más de una vez
    cursor.executemany('''
                   INSERT OR IGNORE INTO consumers (name, budget_limit, current_spend)
                   VALUES (?, ?, ?)
                   ''', equipos_prueba)

    conn.commit()
    conn.close()
    print("Consumidores de prueba insertados (o ya existentes).")

def get_consumer(name):
    """Devuelve los datos de un consumidor."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT name, budget_limit, current_spend FROM consumers WHERE name = ?", (name,))
    result = cursor.fetchone()
    conn.close()
    return {"name": result[0], "budget_limit": result[1], "current_spend": result[2]} if result else None

def check_budget(name):
    """Comprueba si el usuario ha superado su presupuesto."""
    consumer = get_consumer(name)
    if not consumer:
        return False, "Consumidor no encontrado"

    has_budget = consumer["current_spend"] < consumer["budget_limit"]
    return has_budget, consumer

def log_usage(consumer_name, requested_model, provider_model, prompt_tokens, completion_tokens, cost, applied_rule, savings):
    """Registra la llamada y actualiza el gasto del consumidor."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp_local = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Insertar el log
    cursor.execute('''
                   INSERT INTO logs (consumer_name, requested_model, provider_model, prompt_tokens, completion_tokens, total_cost, applied_rule, savings)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ''', (consumer_name, requested_model, provider_model, prompt_tokens, completion_tokens, cost, applied_rule, savings))

    cursor.execute('''
                   UPDATE logs
                   SET timestamp = ?
                   WHERE id = last_insert_rowid()
                   ''', (timestamp_local,))

    # 2. Actualizar el gasto acumulado del consumidor
    cursor.execute('''
                   UPDATE consumers
                   SET current_spend = current_spend + ?
                   WHERE name = ?
                   ''', (cost, consumer_name))

    conn.commit()
    conn.close()
    print(f"💰 Log guardado: {consumer_name} gastó ${cost:.6f} en {provider_model}")

def log_alert(consumer_name, message):
    """Registra una alerta en la base de datos."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
                   INSERT INTO alerts (consumer_name, message)
                   VALUES (?, ?)
                   ''', (consumer_name, message))
    conn.commit()
    conn.close()
    print(f"[BD ALERTA] Alerta guardada en BD para {consumer_name}: {message}")

# --- FUNCIONES DE CACHÉ ---

def _generar_hash(texto):
    """Genera una huella digital única (MD5) para el texto del prompt."""
    return hashlib.md5(texto.lower().strip().encode('utf-8')).hexdigest()

def buscar_en_cache(prompt):
    """Busca si el prompt ya ha sido respondido antes."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    prompt_hash = _generar_hash(prompt)
    cursor.execute("SELECT respuesta_texto, modelo_usado FROM cache WHERE prompt_hash = ?", (prompt_hash,))
    resultado = cursor.fetchone()

    conn.close()

    if resultado:
        print("⚡ Devolviendo respuesta guardada en caché (Coste: $0.00)")
        respuesta_texto, modelo_usado = resultado
        try:
            payload = json.loads(respuesta_texto)
            return {
                "respuesta": payload.get("respuesta", respuesta_texto),
                "modelo": payload.get("modelo", modelo_usado),
                "savings": payload.get("original_cost", payload.get("savings", 0.0)),
            }
        except (TypeError, json.JSONDecodeError):
            return {"respuesta": respuesta_texto, "modelo": modelo_usado, "savings": 0.0}
    return None

def guardar_en_cache(prompt, respuesta_texto, modelo, original_cost=0.0):
    """Guarda la respuesta en la base de datos para futuras consultas."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    prompt_hash = _generar_hash(prompt)
    payload = json.dumps({
        "respuesta": respuesta_texto,
        "modelo": modelo,
        "original_cost": original_cost,
    }, ensure_ascii=False)

    # Usamos INSERT OR REPLACE para mantener actualizada la metadata de caché.
    cursor.execute('''
                   INSERT OR REPLACE INTO cache (prompt_hash, respuesta_texto, modelo_usado)
                   VALUES (?, ?, ?)
                   ''', (prompt_hash, payload, modelo))

    conn.commit()
    conn.close()

# --- BLOQUE DE EJECUCIÓN PRINCIPAL ---
if __name__ == "__main__":
    print("=== CONFIGURANDO BASE DE DATOS ===")
    init_db()
    insertar_consumidores_prueba()

    # Comprobación rápida por consola
    print("\nEstado actual de los equipos de prueba:")
    print(get_consumer("equipo_marketing"))
    print(get_consumer("equipo_desarrollo"))
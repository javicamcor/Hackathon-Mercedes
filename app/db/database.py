import sqlite3
import datetime
import hashlib

DB_NAME = "finops.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS consumers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE,
                        budget_limit REAL,
                        current_spend REAL DEFAULT 0.0
                   )
                   ''')

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
                        latency_ms REAL DEFAULT 0.0,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                   )
                   ''')

    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS cache (
                        prompt_hash TEXT PRIMARY KEY,
                        respuesta_texto TEXT,
                        modelo_usado TEXT,
                        coste_original REAL
                   )
                   ''')

    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        consumer_name TEXT,
                        message TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                   )
                   ''')

    # Actualizar tabla si ya existe
    try:
        cursor.execute("ALTER TABLE logs ADD COLUMN latency_ms REAL DEFAULT 0.0")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()
    print("✅ Base de datos inicializada")

def insertar_consumidores_prueba():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    equipos_prueba = [
        ("equipo_desarrollo", 10.0, 7.99),
        ("equipo_marketing", 2.0, 1.95)
    ]

    cursor.executemany('''
                   INSERT OR IGNORE INTO consumers (name, budget_limit, current_spend)
                   VALUES (?, ?, ?)
                   ''', equipos_prueba)

    conn.commit()
    conn.close()
    print("✅ Consumidores de prueba insertados.")

def get_consumer(name):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT name, budget_limit, current_spend FROM consumers WHERE name = ?", (name,))
    result = cursor.fetchone()
    conn.close()
    return {"name": result[0], "budget_limit": result[1], "current_spend": result[2]} if result else None

def check_budget(name):
    consumer = get_consumer(name)
    if not consumer:
        return False, "Consumidor no encontrado"
    has_budget = consumer["current_spend"] < consumer["budget_limit"]
    return has_budget, consumer

def log_usage(consumer_name, requested_model, provider_model, prompt_tokens, completion_tokens, cost, applied_rule, savings, latency_ms=0.0):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp_local = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute('''
                   INSERT INTO logs (consumer_name, requested_model, provider_model, prompt_tokens, completion_tokens, total_cost, applied_rule, savings, latency_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ''', (consumer_name, requested_model, provider_model, prompt_tokens, completion_tokens, cost, applied_rule, savings, latency_ms))

    cursor.execute('''
                   UPDATE logs
                   SET timestamp = ?
                   WHERE id = last_insert_rowid()
                   ''', (timestamp_local,))

    cursor.execute('''
                   UPDATE consumers
                   SET current_spend = current_spend + ?
                   WHERE name = ?
                   ''', (cost, consumer_name))

    conn.commit()
    conn.close()
    print(f"💰 Log guardado: {consumer_name} gastó ${cost:.6f} en {provider_model} (Ahorro: ${savings:.6f})")

def log_alert(consumer_name, message):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
                   INSERT INTO alerts (consumer_name, message)
                   VALUES (?, ?)
                   ''', (consumer_name, message))
    conn.commit()
    conn.close()
    print(f"🚨 [BD ALERTA] Alerta guardada para {consumer_name}: {message}")

def _generar_hash(texto):
    return hashlib.md5(texto.lower().strip().encode('utf-8')).hexdigest()

def buscar_en_cache(prompt):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    prompt_hash = _generar_hash(prompt)

    try:
        cursor.execute("SELECT respuesta_texto, modelo_usado, coste_original FROM cache WHERE prompt_hash = ?", (prompt_hash,))
        resultado = cursor.fetchone()
    except sqlite3.OperationalError:
        cursor.execute("SELECT respuesta_texto, modelo_usado FROM cache WHERE prompt_hash = ?", (prompt_hash,))
        resultado_viejo = cursor.fetchone()
        resultado = (resultado_viejo[0], resultado_viejo[1], 0.0) if resultado_viejo else None

    conn.close()

    if resultado:
        print(f"⚡ Devolviendo respuesta guardada en caché (Ahorro histórico exacto: ${resultado[2]:.6f})")
        return {"respuesta": resultado[0], "modelo": resultado[1], "coste_original": resultado[2]}
    return None

def guardar_en_cache(prompt, respuesta_texto, modelo, coste_total):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    prompt_hash = _generar_hash(prompt)

    try:
        cursor.execute('''
                       INSERT OR IGNORE INTO cache (prompt_hash, respuesta_texto, modelo_usado, coste_original)
                       VALUES (?, ?, ?, ?)
                       ''', (prompt_hash, respuesta_texto, modelo, coste_total))
    except sqlite3.OperationalError:
        cursor.execute('''
                       INSERT OR IGNORE INTO cache (prompt_hash, respuesta_texto, modelo_usado)
                       VALUES (?, ?, ?)
                       ''', (prompt_hash, respuesta_texto, modelo))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    insertar_consumidores_prueba()
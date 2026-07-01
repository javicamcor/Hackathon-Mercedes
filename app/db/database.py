import sqlite3
import datetime
import hashlib  # Añadido para generar el hash de la caché

DB_NAME = "finops.db"

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

    conn.commit()
    conn.close()
    print("Base de datos inicializada")

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

def log_usage(consumer_name, requested_model, provider_model, prompt_tokens, completion_tokens, total_cost, applied_rule, savings):
    """Registra la llamada y actualiza el gasto del consumidor."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Insertar el log
    cursor.execute('''
                   INSERT INTO logs (consumer_name, requested_model, provider_model, prompt_tokens, completion_tokens, total_cost, applied_rule, savings)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ''', (consumer_name, requested_model, provider_model, prompt_tokens, completion_tokens, total_cost, applied_rule, savings))

    # 2. Actualizar el gasto acumulado del consumidor
    cursor.execute('''
                   UPDATE consumers
                   SET current_spend = current_spend + ?
                   WHERE name = ?
                   ''', (total_cost, consumer_name))

    conn.commit()
    conn.close()
    print(f"Log guardado: {consumer_name} gastó ${total_cost:.6f} en {provider_model} (Ahorro: ${savings:.6f})")

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
        print(" Devolviendo respuesta guardada (Coste: $0.00)")
        return {"respuesta": resultado[0], "modelo": resultado[1]}
    return None

def guardar_en_cache(prompt, respuesta_texto, modelo):
    """Guarda la respuesta en la base de datos para futuras consultas."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    prompt_hash = _generar_hash(prompt)

    # Usamos INSERT OR IGNORE por si hay duplicados
    cursor.execute('''
                   INSERT OR IGNORE INTO cache (prompt_hash, respuesta_texto, modelo_usado)
    VALUES (?, ?, ?)
                   ''', (prompt_hash, respuesta_texto, modelo))

    conn.commit()
    conn.close()

# Bloque de ejecución principal para probar
if __name__ == "__main__":
    init_db()
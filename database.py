import sqlite3
import datetime

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
        provider_model TEXT,
        prompt_tokens INTEGER,
        completion_tokens INTEGER,
        total_cost REAL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    conn.close()
    print("Base de datos inicializada correctamente.")

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

def log_usage(consumer_name, model, prompt_tokens, completion_tokens, cost):
    """Registra la llamada y actualiza el gasto del consumidor."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Insertar el log
    cursor.execute('''
    INSERT INTO logs (consumer_name, provider_model, prompt_tokens, completion_tokens, total_cost)
    VALUES (?, ?, ?, ?, ?)
    ''', (consumer_name, model, prompt_tokens, completion_tokens, cost))
    
    # 2. Actualizar el gasto acumulado del consumidor
    cursor.execute('''
    UPDATE consumers 
    SET current_spend = current_spend + ? 
    WHERE name = ?
    ''', (cost, consumer_name))
    
    conn.commit()
    conn.close()
    print(f"💰 Log guardado: {consumer_name} gastó ${cost:.6f} en {model}")

# Bloque de ejecución principal para probar
if __name__ == "__main__":
    init_db()
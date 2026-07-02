import sqlite3
import datetime
import os

# Obtener la ruta a la base de datos (se asume que el script corre en la raíz del proyecto)
DB_PATH = "finops.db"

def simulate_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Fechas simuladas: ayer y anteayer
    ayer = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    anteayer = (datetime.datetime.now() - datetime.timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    
    # (consumer_name, requested_model, provider_model, prompt_tokens, completion_tokens, total_cost, applied_rule, savings, latency_ms, timestamp)
    logs_falsos = [
        # Gastos de anteayer
        ("equipo_desarrollo", "mistral:7b", "mistral:7b", 100, 50, 0.30, "Ninguna", 0.0, 1500.5, anteayer),
        ("equipo_marketing", "mistral:7b", "mistral:7b", 150, 75, 0.45, "Ninguna", 0.0, 1800.2, anteayer),
        
        # Gastos de ayer
        ("equipo_desarrollo", "mistral", "mistral", 200, 100, 0.60, "Ninguna", 0.0, 2200.0, ayer),
        ("equipo_marketing", "llama3.2:3b", "llama3.2:3b", 300, 150, 0.15, "Degradación del modelo", 0.30, 850.4, ayer),
    ]
    
    for log in logs_falsos:
        cursor.execute('''
            INSERT INTO logs (consumer_name, requested_model, provider_model, prompt_tokens, completion_tokens, total_cost, applied_rule, savings, latency_ms, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', log)
        
        # Actualizamos el gasto del consumidor para mantener la consistencia
        cursor.execute('''
            UPDATE consumers 
            SET current_spend = current_spend + ? 
            WHERE name = ?
        ''', (log[5], log[0]))
        
    conn.commit()
    conn.close()
    print("✅ Peticiones simuladas de ayer y anteayer inyectadas correctamente en finops.db.")

if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        simulate_data()
    else:
        print("❌ No se ha encontrado finops.db. Arranca primero la base de datos.")
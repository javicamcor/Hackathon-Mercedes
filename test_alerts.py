from fastapi.testclient import TestClient
from app.main import app
import sqlite3

client = TestClient(app)

print("--- Haciendo petición como 'equipo_marketing' ---")
response = client.post(
    "/v1/chat/completions",
    headers={"X-Consumer-ID": "equipo_marketing", "Content-Type": "application/json"},
    json={
        "model": "llama3.2:3b",
        "messages": [{"role": "user", "content": "Hola mundo"}]
    }
)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")

print("\n--- Verificando la tabla de alertas en la BD ---")
conn = sqlite3.connect("finops.db")
cursor = conn.cursor()
cursor.execute("SELECT * FROM alerts")
alerts = cursor.fetchall()
for alert in alerts:
    print(alert)
conn.close()

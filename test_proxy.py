import httpx
import json
import sqlite3

PROXY_URL = "http://localhost:8000/v1/chat/completions"

def hacer_peticion(nombre_test, equipo, modelo_pedido, prompt):
    print(f"\n{'='*50}\n🚀 TEST: {nombre_test}")
    print(f"👤 Equipo: {equipo} | 🎯 Modelo pedido: {modelo_pedido}")
    print(f"📝 Prompt ({len(prompt)} chars): {prompt[:50]}...")
    
    headers = {"X-Consumer-ID": equipo, "Content-Type": "application/json"}
    payload = {
        "model": modelo_pedido,
        "messages": [{"role": "user", "content": prompt}]
    }
    
    try:
        # Aumentamos el timeout porque los modelos locales pueden tardar en responder
        response = httpx.post(PROXY_URL, headers=headers, json=payload, timeout=300.0)
        
        if response.status_code == 200:
            data = response.json()
            modelo_real = data.get('model', 'Desconocido')
            texto = data['choices'][0]['message']['content']
            print(f"✅ ÉXITO!")
            print(f"🤖 Modelo que ha respondido realmente: {modelo_real}")
            print(f"💬 Respuesta IA: {texto.strip()}")
        else:
            print(f"❌ ERROR HTTP {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"❌ EXCEPCIÓN: {str(e)}")

# Prompt Corto (Nivel 1)
prompt_corto = "Hola, dime un dato curioso muy breve."
# Otro Prompt Corto para evitar caché en la prueba de Downgrade
prompt_facil_mistral = "Dime cuáles son los colores del arcoíris."
# Prompt Largo y Complejo (Nivel 2)
prompt_largo = "Necesito desarrollar un script avanzado en python para un modelo de machine learning de prediccion. " * 5
# Otro Prompt Largo (Nivel 2) para evitar caché en la prueba de Degradación por Presupuesto
prompt_largo_marketing = "Quiero que analices y evalues las tendencias del mercado usando machine learning para una presentacion. " * 5

# --- EJECUCIÓN DE LOS CASOS ---

# 1. Petición Normal -> Debería ir a llama3.2:3b
hacer_peticion("Nivel 1 (Pide Llama)", "equipo_desarrollo", "llama3.2:3b", prompt_corto)

# 1.5. Petición Fácil pidiendo Mistral -> Debería hacer DOWNGRADE a llama3.2:3b para ahorrar
hacer_peticion("Optimización Downgrade (Pide Mistral para algo fácil)", "equipo_desarrollo", "mistral:7b", prompt_facil_mistral)

# 2. Petición Compleja pidiendo Mistral -> Debería ir a mistral:7b
hacer_peticion("Nivel 2 (Pide Mistral)", "equipo_desarrollo", "mistral:7b", prompt_largo)

# 3. Petición Compleja pidiendo Automático (modelo inventado 'auto') -> Debería auto-enrutar a mistral:7b
hacer_peticion("Nivel 2 (Pide Automático)", "equipo_desarrollo", "auto", prompt_largo)

# 4. Petición que rebasa presupuesto (Degradación FinOps) -> Forzará Llama3.2:3b aunque pidas Mistral
# El equipo_marketing ya empieza con 1.95$ gastados de 2.00$ de presupuesto.
hacer_peticion("Degradación por Presupuesto", "equipo_marketing", "mistral:7b", prompt_largo_marketing)

# 5. Petición de Caché -> Si repetimos la primera, debería responder instantáneo y gratis
hacer_peticion("Prueba de Caché Semántica", "equipo_desarrollo", "llama3.2:3b", prompt_corto)

# ==========================================
# PRUEBAS DE ALERTAS (80% y 100%)
# ==========================================

def forzar_gasto(equipo, cantidad):
    try:
        conn = sqlite3.connect('finops.db')
        conn.execute("UPDATE consumers SET current_spend = ? WHERE name = ?", (cantidad, equipo))
        conn.commit()
        conn.close()
        print(f"\n🔧 [SISTEMA] -> Gasto de '{equipo}' alterado artificialmente a {cantidad}$ en base de datos.")
    except Exception as e:
        pass

# 6. Simular Alerta del 80% (equipo_desarrollo tiene 10$ de limite, le ponemos 7.95$ y lanzamos Mistral)
forzar_gasto("equipo_desarrollo", 7.95)
hacer_peticion("Alarma 80% Presupuesto", "equipo_desarrollo", "mistral:7b", prompt_largo)

# 7. Simular Alerta del 100% y Bloqueo Total (equipo_marketing tiene 2$ de limite, lo llenamos)
forzar_gasto("equipo_marketing", 2.00)
hacer_peticion("Alarma 100% (Bloqueo de Petición)", "equipo_marketing", "llama3.2:3b", prompt_corto)

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
prompt_largo = (
    "Estoy desarrollando una arquitectura backend en python y necesito que me ayudes a refactorizar "
    "varias funciones. Quiero implementar una API REST escalable con llamadas asíncronas, conectar "
    "todo el sistema a una base de datos SQL de alto rendimiento y extraer métricas relevantes. "
    "Analiza el siguiente pseudocódigo y devuelve una solución optimizada paso a paso usando las "
    "mejores prácticas de la industria de desarrollo de software y patrones de diseño modernos. "
    "Además, evalua la seguridad del flujo de datos en cada endpoint."
)

# Otro Prompt Largo (Nivel 2) para evitar caché en la prueba de Degradación por Presupuesto
prompt_largo_marketing = (
    "Redacta una estrategia integral de expansión para una empresa de software B2B que busca entrar en el mercado asiático. "
    "Considera las diferencias culturales en la negociación, los requisitos de cumplimiento de datos locales como el PIPL en China, "
    "y diseña una campaña de marketing de contenidos multicanal que maximice la generación de leads. "
    "Justifica el presupuesto estimado para cada fase y define los KPIs de éxito basándote en la retención de clientes a largo plazo."
)

# Prompts exclusivos para Enrutamiento Automático (evitar caché)
prompt_auto_facil = "Dime la capital de Francia en una sola palabra."
prompt_auto_dificil = (
    "Desarrolla un plan de optimización de infraestructura para un clúster de Kubernetes que maneja miles de microservicios. "
    "Analiza el balance entre el uso de recursos, la latencia de red y la disponibilidad en zonas múltiples. "
    "Describe cómo implementarías una estrategia de auto-escalado predictivo usando métricas de Prometheus, "
    "gestionarías los secretos en un entorno multi-inquilino y asegurarías que los despliegues tengan cero tiempo de inactividad."
)

# --- EJECUCIÓN DE LOS CASOS ---

# 1. Petición Normal -> Debería ir a llama3.2:3b
hacer_peticion("Nivel 1 (Pide Llama)", "equipo_desarrollo", "llama3.2:3b", prompt_corto)

# 1.5. Petición Fácil pidiendo Mistral -> Ahora debe RESPETA la elección y usar mistral:7b
hacer_peticion("Respeto a Elección Explícita (Pide Mistral para algo fácil)", "equipo_desarrollo", "mistral:7b", prompt_facil_mistral)

# 2. Petición Compleja pidiendo Mistral -> Debería ir a mistral:7b
hacer_peticion("Nivel 2 (Pide Mistral)", "equipo_desarrollo", "mistral:7b", prompt_largo)

# 3.1 Petición Automática Fácil -> Debería ir a llama3.2:3b
hacer_peticion("Auto Fácil (Enrutamiento Automático)", "equipo_desarrollo", "auto", prompt_auto_facil)

# 3.2 Petición Automática Compleja -> Debería ir a mistral:7b
hacer_peticion("Auto Complejo (Enrutamiento Automático)", "equipo_desarrollo", "auto", prompt_auto_dificil)

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
forzar_gasto("equipo_desarrollo", 8)
hacer_peticion("Alarma 80% Presupuesto", "equipo_desarrollo", "mistral:7b", prompt_largo)

# 7. Simular Alerta del 100% y Bloqueo Total (equipo_marketing tiene 2$ de limite, lo llenamos)
forzar_gasto("equipo_marketing", 2.00)
hacer_peticion("Alarma 100% (Bloqueo de Petición)", "equipo_marketing", "llama3.2:3b", prompt_corto)

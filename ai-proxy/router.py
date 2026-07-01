import requests

# Configuración de los Proveedores (URLs según el Starter Kit)
PROVEEDOR_A_URL = "http://localhost:11434/v1/chat/completions"
PROVEEDOR_B_URL = "http://localhost:11435/v1/chat/completions"

# Precios por cada 1,000,000 de tokens
PRECIOS = {
    "llama3.2:3b": {"entrada": 0.06, "salida": 0.06},
    "mistral:7b": {"entrada": 0.24, "salida": 0.24}
}

def evaluar_complejidad(prompt: str) -> str:
    """
    CRITERIO 1: Evalúa la complejidad del prompt.
    Si tiene menos de 100 caracteres, asumimos que es simple y usamos Llama 3.2 (Barato).
    Si es más largo, usamos Mistral (Caro).
    """
    if len(prompt) < 100:
        print(f"   -> [Cerebro] Prompt corto ({len(prompt)} caracteres). Elegido: llama3.2:3b")
        return "llama3.2:3b"
    else:
        print(f"   -> [Cerebro] Prompt largo ({len(prompt)} caracteres). Elegido: mistral:7b")
        return "mistral:7b"


def enrutar_peticion(prompt: str, porcentaje_presupuesto_gastado: float, mensajes_completos: list) -> dict:
    """
    Función principal que decide el modelo, modifica el body para adaptarlo 
    al proveedor y hace la llamada HTTP.
    """
    print(f"\n[Cerebro] Evaluando ruta para el prompt. Presupuesto gastado: {porcentaje_presupuesto_gastado:.2f}%")
    
    # 1. Aplicar Criterio 1: Complejidad
    modelo_elegido = evaluar_complejidad(prompt)
    url_destino = PROVEEDOR_A_URL if modelo_elegido == "llama3.2:3b" else PROVEEDOR_B_URL
    
    # 2. Aplicar Criterio 2: FinOps (Degradación controlada)
    if porcentaje_presupuesto_gastado >= 90.0 and modelo_elegido == "mistral:7b":
        print("   ⚠️ [Cerebro] ¡Alerta FinOps! Consumo > 90%. Forzando degradación a llama3.2:3b para ahorrar.")
        modelo_elegido = "llama3.2:3b"
        url_destino = PROVEEDOR_A_URL

    # 3. Preparar el body idéntico al formato OpenAI / Ollama
    payload = {
        "model": modelo_elegido,
        "messages": mensajes_completos,
        "temperature": 0.7
    }
    
    # 4. Hacer la llamada real al Ollama local correspondiente
    try:
        print(f"   -> [Cerebro] Enviando petición a {url_destino}...")
        respuesta = requests.post(url_destino, json=payload, timeout=30)
        respuesta.raise_for_status()
        return respuesta.json()
        
    except requests.exceptions.RequestException as e:
        print(f"   ❌ [Cerebro] Error al conectar con el proveedor: {e}")
        return {"error": "No se pudo conectar con el proveedor de IA", "detalles": str(e)}

# --- BLOQUE DE PRUEBA LOCAL ---
if __name__ == "__main__":
    print("=== PROBANDO EL CEREBRO EN LOCAL ===")
    
    # Simulación 1: Prompt corto, presupuesto saludable (Debería usar Llama 3.2)
    prompt_corto = "Hola, ¿cómo estás?"
    mensajes_1 = [{"role": "user", "content": prompt_corto}]
    resultado_1 = enrutar_peticion(prompt_corto, porcentaje_presupuesto_gastado=10.0, mensajes_completos=mensajes_1)
    
    print("\n------------------------------------")
    
    # Simulación 2: Prompt largo, presupuesto saludable (Debería usar Mistral)
    prompt_largo = "Necesito que escribas una función en Python muy compleja que ordene una lista de diccionarios por múltiples llaves dinámicas y que además gestione excepciones de tipos de datos de forma segura."
    mensajes_2 = [{"role": "user", "content": prompt_largo}]
    resultado_2 = enrutar_peticion(prompt_largo, porcentaje_presupuesto_gastado=15.0, mensajes_completos=mensajes_2)

    print("\n------------------------------------")

    # Simulación 3: Prompt largo pero presupuesto CRÍTICO (Debería forzar Llama 3.2 por FinOps)
    resultado_3 = enrutar_peticion(prompt_largo, porcentaje_presupuesto_gastado=92.5, mensajes_completos=mensajes_2)
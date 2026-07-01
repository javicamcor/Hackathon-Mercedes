import httpx
import asyncio

# Configuración de los Proveedores (URLs locales configuradas en el docker-compose del Starter Kit)
PROVEEDOR_A_URL = "http://localhost:11434/v1/chat/completions"
PROVEEDOR_B_URL = "http://localhost:11435/v1/chat/completions"

# Precios de referencia por cada 1,000,000 de tokens (según la tabla del README)
PRECIOS = {
    "llama3.2:3b": {"entrada": 0.06, "salida": 0.06},
    "mistral:7b": {"entrada": 0.24, "salida": 0.24}
}

def evaluar_complejidad(prompt: str) -> str:
    """
    CRITERIO 1: Evalúa la complejidad del prompt basándose en su longitud.
    Si tiene menos de 100 caracteres, asumimos que es una tarea simple -> Llama 3.2 (Barato).
    Si es más largo, asumimos que requiere más razonamiento -> Mistral (Caro).
    """
    UMBRAL_CARACTERES = 100
    
    if len(prompt) < UMBRAL_CARACTERES:
        print(f"   -> [Cerebro] Prompt corto ({len(prompt)} caracteres). Modelo óptimo: llama3.2:3b")
        return "llama3.2:3b"
    else:
        print(f"   -> [Cerebro] Prompt largo ({len(prompt)} caracteres). Modelo óptimo: mistral:7b")
        return "mistral:7b"


async def enrutar_peticion(prompt: str, porcentaje_presupuesto_gastado: float, mensajes_completos: list) -> dict:
    """
    Función principal de El Cerebro (Módulo 3).
    Decide el modelo, aplica políticas FinOps de ahorro y gestiona la llamada HTTP asíncrona.
    """
    print(f"\n[Cerebro] Evaluando enrutamiento. Gasto actual del consumidor: {porcentaje_presupuesto_gastado:.2f}%")
    
    # 1. Aplicar Criterio 1: Complejidad del prompt
    modelo_elegido = evaluar_complejidad(prompt)
    url_destino = PROVEEDOR_A_URL if modelo_elegido == "llama3.2:3b" else PROVEEDOR_B_URL
    
    # 2. Aplicar Criterio 2: FinOps (Degradación controlada de servicio por presupuesto crítico)
    # Si el equipo ya ha consumido el 90% o más de su dinero, forzamos el modelo barato (Proveedor A)
    if porcentaje_presupuesto_gastado >= 90.0 and modelo_elegido == "mistral:7b":
        print("   ⚠️ [Cerebro] ¡Alerta FinOps! Consumo >= 90%. Forzando degradación a llama3.2:3b para mitigar costes.")
        modelo_elegido = "llama3.2:3b"
        url_destino = PROVEEDOR_A_URL

    # 3. Construir el cuerpo de la petición (Payload) compatible con OpenAI / Ollama
    payload = {
        "model": modelo_elegido,
        "messages": mensajes_completos,  # Mantiene el historial de chat enviado por El Guardián
        "temperature": 0.7
    }
    
    # 4. Realizar la llamada HTTP asíncrona al Ollama correspondiente
    try:
        print(f"   -> [Cerebro] Conectando de forma asíncrona con {url_destino}...")
        
        async with httpx.AsyncClient() as client:
            respuesta = await client.post(url_destino, json=payload, timeout=30.0)
            respuesta.raise_for_status()  # Lanza una excepción si el servidor devuelve un error (4xx o 5xx)
            
            # Devolvemos el JSON tal cual responde Ollama (incluyendo el objeto 'usage' con los tokens)
            return respuesta.json()
            
    except httpx.HTTPStatusError as e:
        print(f"   ❌ [Cerebro] El proveedor de IA devolvió un error de estado: {e}")
        return {"error": "Error interno del proveedor de IA", "detalles": str(e)}
    except httpx.RequestError as e:
        print(f"   ❌ [Cerebro] Error de red al intentar conectar con el proveedor: {e}")
        return {"error": "No se pudo establecer conexión con el motor de IA", "detalles": str(e)}

# --- BLOQUE DE PRUEBA LOCAL EN CONSOLA ---
# Este bloque solo se ejecuta cuando ejecutas este archivo directamente (python router.py)
if __name__ == "__main__":
    
    async def ejecutar_pruebas_locales():
        print("=== INICIANDO SIMULACIÓN DE PRUEBAS DE ENRUTAMIENTO (CEREBRO) ===")
        
        # Simulación 1: Prompt corto con presupuesto sano (Debería ir al Proveedor A - Llama 3.2)
        prompt_1 = "Hola, ¿cuál es la capital de Francia?"
        mensajes_1 = [{"role": "user", "content": prompt_1}]
        await enrutar_peticion(prompt_1, porcentaje_presupuesto_gastado=12.5, mensajes_completos=mensajes_1)
        
        print("\n" + "-"*50)
        
        # Simulación 2: Prompt largo con presupuesto sano (Debería ir al Proveedor B - Mistral)
        prompt_2 = (
            "Escribe un script estructurado en Python que permita realizar web scraping de una página "
            "de noticias de forma ética, utilizando BeautifulSoup, extrayendo títulos y enlaces, e "
            "incluyendo un control de errores robusto para conexiones caídas o tags inexistentes."
        )
        mensajes_2 = [{"role": "user", "content": prompt_2}]
        await enrutar_peticion(prompt_2, porcentaje_presupuesto_gastado=45.0, mensajes_completos=mensajes_2)
        
        print("\n" + "-"*50)
        
        # Simulación 3: Prompt largo pero presupuesto CRÍTICO (Debería saltar la alerta FinOps y forzar Llama 3.2)
        print("Simulando escenario con el mismo prompt largo pero presupuesto agotándose...")
        await enrutar_peticion(prompt_2, porcentaje_presupuesto_gastado=91.0, mensajes_completos=mensajes_2)
        
        print("\n=== SIMULACIÓN FINALIZADA ===")

    # Lanzamos el bucle de eventos asíncronos para poder ejecutar las pruebas locales
    asyncio.run(ejecutar_pruebas_locales())
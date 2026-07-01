import httpx
import asyncio
import re

# Configuración de los Proveedores (URLs locales configuradas en el docker-compose del Starter Kit)
PROVEEDOR_A_URL = "http://localhost:11434/v1/chat/completions"
PROVEEDOR_B_URL = "http://localhost:11435/v1/chat/completions"

# Precios de referencia por cada 1,000,000 de tokens (según la tabla del README)
PRECIOS = {
    "llama3.2:3b": {"entrada": 0.06, "salida": 0.06},
    "mistral:7b": {"entrada": 0.24, "salida": 0.24}
}

# =====================================================================
# DICCIONARIO SEMÁNTICO DE TAREAS COMPLEJAS
# Si el prompt contiene alguna de estas palabras, requiere razonamiento
# avanzado y se enruta a Mistral 7B.
# =====================================================================
PALABRAS_COMPLEJAS = {
    # 1. Lenguajes de Programación y Tecnologías
    "python", "javascript", "java", "c++", "c#", "sql", "html", "css", "php",
    "ruby", "swift", "golang", "rust", "bash", "shell", "powershell", "typescript",
    "docker", "kubernetes", "git", "linux", "aws", "azure", "gcp", "terraform",
    "kotlin", "scala", "dart", "perl", "haskell", "lua", "matlab", "r",

    # 2. Conceptos de Desarrollo y Arquitectura
    "api", "rest", "graphql", "json", "xml", "yaml", "regex", "debug", "refactoriza",
    "compila", "despliegue", "frontend", "backend", "query", "consulta", "algoritmo",
    "bucle", "función", "clase", "objeto", "asíncrono", "framework", "react",
    "angular", "vue", "django", "flask", "fastapi", "node", "express", "spring",
    "arquitectura", "escalabilidad", "rendimiento", "microservicios", "patrón",
    "script", "código", "programar", "variable", "repositorio", "commit", "merge",
    "pipeline", "ci/cd", "testing", "unitario", "mock", "middleware", "endpoint",

    # 3. Datos, Bases de Datos y Formatos
    "csv", "excel", "pandas", "dataframe", "scraping", "parsear", "extraer",
    "transformar", "etl", "dashboard", "gráfica", "visualización", "dataset",
    "mysql", "postgres", "mongodb", "nosql", "redis", "elasticsearch", "supabase",
    "oracle", "sqlite", "cassandra", "hadoop", "spark", "kafka", "parquet",

    # 4. Data Science, IA y Machine Learning
    "machine", "learning", "ia", "deep", "redes", "neuronales", "nlp", "visión",
    "entrenamiento", "predicción", "clustering", "regresión", "clasificación",
    "tensor", "pytorch", "scikit", "llm", "prompt", "token", "embedding",

    # 5. Razonamiento, Lógica y Matemáticas
    "analiza", "evalúa", "compara", "deduce", "justifica", "optimiza", "abstracción",
    "inferencia", "estadística", "probabilidad", "matemáticas", "cálculo", "ecuación",
    "integral", "derivada", "matriz", "álgebra", "física", "teoría", "teorema",
    "demuestra", "lógica", "hipótesis", "complejidad", "heurística", "trigonometría",
    "geometría", "aritmética", "proporción", "varianza", "distribución",

    # 6. Documentación Profesional, Legal y Corporativa
    "ensayo", "tesis", "informe", "contrato", "legal", "cláusula", "patente",
    "científico", "paper", "metodología", "bibliografía", "citación", "apa",
    "normativa", "cumplimiento", "auditoría", "vulnerabilidad", "ciberseguridad",
    "gdpr", "criptografía", "encriptación", "estratégico", "financiero", "balance"
}

def evaluar_complejidad(prompt: str) -> str:
    """
    CRITERIO 1: Evalúa la complejidad mediante análisis semántico (O(1)).
    Busca intersecciones entre las palabras del usuario y nuestro diccionario.
    """
    # 1. Extraer palabras en minúsculas ignorando signos de puntuación
    palabras_usuario = set(re.findall(r'\b\w+\b', prompt.lower()))

    # 2. Intersección con el diccionario técnico
    palabras_encontradas = palabras_usuario.intersection(PALABRAS_COMPLEJAS)

    if palabras_encontradas:
        print(f"   -> [Cerebro] Tarea técnica detectada (Palabras: {palabras_encontradas}). Modelo óptimo: mistral:7b")
        return "mistral:7b"

    # 3. Fallback por longitud (Si es inusualmente largo, requiere más contexto)
    UMBRAL_CARACTERES = 400
    if len(prompt) > UMBRAL_CARACTERES:
        print(f"   -> [Cerebro] Prompt largo sin palabras clave ({len(prompt)} chars). Modelo óptimo: mistral:7b")
        return "mistral:7b"

    # 4. Por defecto: Tarea conversacional
    print(f"   -> [Cerebro] Tarea conversacional simple. Modelo óptimo: llama3.2:3b")
    return "llama3.2:3b"

async def enrutar_peticion(prompt: str, porcentaje_presupuesto_gastado: float, mensajes_completos: list) -> tuple:
    """
    Función principal de El Cerebro (Módulo 3).
    Decide el modelo, aplica políticas FinOps de ahorro y gestiona la llamada HTTP asíncrona.
    Returns: (respuesta_json, modelo_elegido, regla_aplicada)
    """
    print(f"\n[Cerebro] Evaluando enrutamiento. Gasto actual del consumidor: {porcentaje_presupuesto_gastado:.2f}%")

    # 1. Aplicar Criterio 1: Complejidad del prompt (Ahora con palabras clave)
    modelo_elegido = evaluar_complejidad(prompt)
    url_destino = PROVEEDOR_A_URL if modelo_elegido == "llama3.2:3b" else PROVEEDOR_B_URL
    regla_aplicada = "None" if modelo_elegido == "mistral:7b" else "Simple Task"

    # 2. Aplicar Criterio 2: FinOps (Degradación controlada de servicio por presupuesto crítico)
    if porcentaje_presupuesto_gastado >= 90.0 and modelo_elegido == "mistral:7b":
        print("   ⚠️ [Cerebro] ¡Alerta FinOps! Consumo >= 90%. Forzando degradación a llama3.2:3b para mitigar costes.")
        modelo_elegido = "llama3.2:3b"
        url_destino = PROVEEDOR_A_URL
        regla_aplicada = "Budget Degradation"

    # 3. Construir el cuerpo de la petición (Payload) compatible con OpenAI / Ollama
    payload = {
        "model": modelo_elegido,
        "messages": mensajes_completos,
        "temperature": 0.7
    }

    # 4. Realizar la llamada HTTP asíncrona al Ollama correspondiente
    try:
        print(f"   -> [Cerebro] Conectando de forma asíncrona con {url_destino}...")

        async with httpx.AsyncClient() as client:
            respuesta = await client.post(url_destino, json=payload, timeout=30.0)
            respuesta.raise_for_status()

            # Devolvemos el JSON tal cual responde Ollama, junto con los metadatos de enrutamiento
            return respuesta.json(), modelo_elegido, regla_aplicada

    except httpx.HTTPStatusError as e:
        print(f" [Cerebro] El proveedor de IA devolvió un error de estado: {e}")
        return {"error": "Error interno del proveedor de IA", "detalles": str(e)}, modelo_elegido, regla_aplicada
    except httpx.RequestError as e:
        print(f" [Cerebro] Error de red al intentar conectar con el proveedor: {e}")
        return {"error": "No se pudo establecer conexión con el motor de IA", "detalles": str(e)}, modelo_elegido, regla_aplicada

# --- BLOQUE DE PRUEBA LOCAL EN CONSOLA ---
if __name__ == "__main__":

    async def ejecutar_pruebas_locales():
        print("=== INICIANDO SIMULACIÓN DE PRUEBAS DE ENRUTAMIENTO (CEREBRO) ===")

        # Simulación 1: Prompt conversacional corto sin palabras clave -> Llama 3.2
        prompt_1 = "Hola, ¿cuál es la capital de Francia?"
        mensajes_1 = [{"role": "user", "content": prompt_1}]
        await enrutar_peticion(prompt_1, porcentaje_presupuesto_gastado=12.5, mensajes_completos=mensajes_1)

        print("\n" + "-"*50)

        # Simulación 2: Prompt con palabras clave (python, scraping) -> Mistral 7B
        prompt_2 = (
            "Escribe un script estructurado en python que permita realizar web scraping de una página "
            "de noticias de forma ética, extrayendo títulos y enlaces."
        )
        mensajes_2 = [{"role": "user", "content": prompt_2}]
        await enrutar_peticion(prompt_2, porcentaje_presupuesto_gastado=45.0, mensajes_completos=mensajes_2)

        print("\n" + "-"*50)

        # Simulación 3: Prompt técnico pero con presupuesto crítico (>90%) -> Forzado a Llama 3.2
        print("Simulando escenario con el mismo prompt técnico pero presupuesto agotándose...")
        await enrutar_peticion(prompt_2, porcentaje_presupuesto_gastado=91.0, mensajes_completos=mensajes_2)

        print("\n=== SIMULACIÓN FINALIZADA ===")

    asyncio.run(ejecutar_pruebas_locales())
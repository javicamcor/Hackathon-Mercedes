import asyncio
import logging
import re
import unicodedata

import httpx

# Configuración de los Proveedores (URLs locales configuradas en el docker-compose del Starter Kit)
PROVEEDOR_A_URL = "http://localhost:11434/v1/chat/completions"
PROVEEDOR_B_URL = "http://localhost:11435/v1/chat/completions"

# Precios de referencia por cada 1,000,000 de tokens (según la tabla del README)
PRECIOS = {
    "llama3.2:3b": {"entrada": 0.06, "salida": 0.06},
    "mistral:7b": {"entrada": 0.24, "salida": 0.24}
}

logger = logging.getLogger(__name__)

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
    "bucle", "funcion", "clase", "objeto", "asincrono", "framework", "react",
    "angular", "vue", "django", "flask", "fastapi", "node", "express", "spring",
    "arquitectura", "escalabilidad", "rendimiento", "microservicios", "patrón",
    "script", "código", "programar", "variable", "repositorio", "commit", "merge",
    "pipeline", "ci/cd", "testing", "unitario", "mock", "middleware", "endpoint",

    # 3. Datos, Bases de Datos y Formatos
    "csv", "excel", "pandas", "dataframe", "scraping", "parsear", "extraer",
    "transformar", "etl", "dashboard", "grafica", "visualizacion", "dataset",
    "mysql", "postgres", "mongodb", "nosql", "redis", "elasticsearch", "supabase",
    "oracle", "sqlite", "cassandra", "hadoop", "spark", "kafka", "parquet",

    # 4. Data Science, IA y Machine Learning
    "machine", "learning", "ia", "deep", "redes", "neuronales", "nlp", "vision",
    "entrenamiento", "prediccion", "clustering", "regresion", "clasificacion",
    "tensor", "pytorch", "scikit", "llm", "prompt", "token", "embedding",

    # 5. Razonamiento, Lógica y Matemáticas
    "analiza", "evalua", "compara", "deduce", "justifica", "optimiza", "abstraccion",
    "inferencia", "estadistica", "probabilidad", "matematicas", "calculo", "ecuacion",
    "integral", "derivada", "matriz", "algebra", "fisica", "teoria", "teorema",
    "demuestra", "logica", "hipotesis", "complejidad", "heuristica", "trigonometria",
    "geometria", "aritmetica", "proporcion", "varianza", "distribucion",

    # 6. Documentación Profesional, Legal y Corporativa
    "ensayo", "tesis", "informe", "contrato", "legal", "clausula", "patente",
    "cientifico", "paper", "metodologia", "bibliografia", "citacion", "apa",
    "normativa", "cumplimiento", "auditoria", "vulnerabilidad", "ciberseguridad",
    "gdpr", "criptografia", "encriptacion", "estrategico", "financiero", "balance"
}

def _normalizar_texto(texto: str) -> str:
    texto_normalizado = unicodedata.normalize("NFKD", texto)
    texto_sin_tildes = "".join(
        caracter for caracter in texto_normalizado if not unicodedata.combining(caracter)
    )
    return texto_sin_tildes.casefold()


def evaluar_complejidad(prompt: str) -> str:
    """
    CRITERIO 1: Evalúa la complejidad mediante análisis semántico (O(n)).
    Busca intersecciones entre las palabras del usuario y nuestro diccionario.
    """
    # 1. Normalizar el texto para ignorar tildes y mayúsculas
    prompt_normalizado = _normalizar_texto(prompt)
    palabras_usuario = set(re.findall(r'\b\w+\b', prompt_normalizado))

    # 2. Intersección con el diccionario técnico
    palabras_encontradas = palabras_usuario.intersection(PALABRAS_COMPLEJAS)

    if palabras_encontradas:
        logger.info("Tarea técnica detectada (Palabras: %s). Modelo óptimo: mistral:7b", palabras_encontradas)
        return "mistral:7b"

    # 3. Fallback por longitud (Si es inusualmente largo, requiere más contexto)
    UMBRAL_CARACTERES = 400
    if len(prompt) > UMBRAL_CARACTERES:
        logger.info("Prompt largo sin palabras clave (%s chars). Modelo óptimo: mistral:7b", len(prompt))
        return "mistral:7b"

    # 4. Por defecto: Tarea conversacional
    logger.info("Tarea conversacional simple. Modelo óptimo: llama3.2:3b")
    return "llama3.2:3b"

async def enrutar_peticion(prompt: str, porcentaje_presupuesto_gastado: float, mensajes_completos: list) -> dict:
    """
    Función principal de El Cerebro (Módulo 3).
    Decide el modelo, aplica políticas FinOps de ahorro y gestiona la llamada HTTP asíncrona.
    """
    logger.info("Evaluando enrutamiento. Gasto actual del consumidor: %.2f%%", porcentaje_presupuesto_gastado)

    # 1. Aplicar Criterio 1: Complejidad del prompt (Ahora con palabras clave)
    modelo_elegido = evaluar_complejidad(prompt)
    url_destino = PROVEEDOR_A_URL if modelo_elegido == "llama3.2:3b" else PROVEEDOR_B_URL

    # 2. Aplicar Criterio 2: FinOps (Degradación controlada de servicio por presupuesto crítico)
    if porcentaje_presupuesto_gastado >= 90.0 and modelo_elegido == "mistral:7b":
        logger.warning("Alerta FinOps: consumo >= 90%%. Forzando degradación a llama3.2:3b para mitigar costes.")
        modelo_elegido = "llama3.2:3b"
        url_destino = PROVEEDOR_A_URL

    # 3. Construir el cuerpo de la petición (Payload) compatible con OpenAI / Ollama
    payload = {
        "model": modelo_elegido,
        "messages": mensajes_completos,
        "temperature": 0.7
    }

    # 4. Realizar la llamada HTTP asíncrona al Ollama correspondiente
    try:
        logger.info("Conectando de forma asíncrona con %s...", url_destino)

        async with httpx.AsyncClient() as client:
            respuesta = await client.post(url_destino, json=payload, timeout=30.0)
            respuesta.raise_for_status()

            # Devolvemos el JSON tal cual responde Ollama, pero enriquecemos si faltan campos
            resp_json = respuesta.json()

            # Aseguramos que `model` exista en la respuesta
            if isinstance(resp_json, dict) and "model" not in resp_json:
                resp_json["model"] = modelo_elegido

            return resp_json

    except httpx.HTTPStatusError as e:
        logger.exception("El proveedor de IA devolvió un error de estado")
        return {"error": "Error interno del proveedor de IA", "detalles": str(e)}
    except httpx.RequestError as e:
        logger.exception("Error de red al intentar conectar con el proveedor")
        return {"error": "No se pudo establecer conexión con el motor de IA", "detalles": str(e)}

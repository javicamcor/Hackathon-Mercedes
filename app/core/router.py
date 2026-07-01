import asyncio
import logging
import re
import unicodedata
import math
from typing import Any, Dict, List, Tuple

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


def _normalizar_texto(texto: str) -> str:
    texto_normalizado = unicodedata.normalize("NFKD", texto.lower())
    texto_sin_tildes = "".join(caracter for caracter in texto_normalizado if not unicodedata.combining(caracter))
    return texto_sin_tildes


def _detectar_modelo(prompt: str) -> Tuple[str, str]:
    """
    Devuelve el modelo elegido y una razón corta de la decisión.
    """
    prompt_normalizado = _normalizar_texto(prompt)

    # 1. Extraer palabras ignorando signos de puntuación y tildes
    palabras_usuario = set(re.findall(r"\b\w+\b", prompt_normalizado))
    palabras_encontradas = palabras_usuario.intersection(PALABRAS_COMPLEJAS)

    if palabras_encontradas:
        logger.info("Tarea técnica detectada (Palabras: %s). Modelo óptimo: mistral:7b", palabras_encontradas)
        return "mistral:7b", "palabras_clave"

    # 2. Fallback por longitud
    UMBRAL_CARACTERES = 400
    if len(prompt_normalizado) > UMBRAL_CARACTERES:
        logger.info("Prompt largo sin palabras clave (%s chars). Modelo óptimo: mistral:7b", len(prompt_normalizado))
        return "mistral:7b", "longitud"

    # 3. Por defecto: tarea conversacional
    logger.info("Tarea conversacional simple. Modelo óptimo: llama3.2:3b")
    return "llama3.2:3b", "simple"


def estimar_tokens_prompt(prompt: str) -> int:
    """
    Estima cuántos tokens consume un prompt antes de enviarlo al proveedor.

    Es una aproximación simple basada en longitud del texto, útil para
    mostrar coste estimado por prompt antes de recibir la respuesta real.
    """
    prompt_normalizado = _normalizar_texto(prompt)
    return max(1, math.ceil(len(prompt_normalizado) / 4))


def _obtener_tarifas(modelo: str) -> Dict[str, float]:
    return PRECIOS.get(modelo, {"entrada": 0.0, "salida": 0.0})


def _calcular_costes(modelo: str, prompt_tokens: int, completion_tokens: int) -> Dict[str, float]:
    tarifas = _obtener_tarifas(modelo)
    coste_prompt = (prompt_tokens * tarifas["entrada"]) / 1_000_000
    coste_completion = (completion_tokens * tarifas["salida"]) / 1_000_000
    return {
        "prompt_cost": coste_prompt,
        "completion_cost": coste_completion,
        "total_cost": coste_prompt + coste_completion,
    }


def estimar_coste_prompt(prompt: str, modelo: str) -> float:
    """
    Estima el coste de entrada del prompt para un modelo concreto.
    """
    prompt_tokens = estimar_tokens_prompt(prompt)
    return _calcular_costes(modelo, prompt_tokens, 0)["prompt_cost"]


def estimar_completion_tokens(prompt: str) -> int:
    """
    Estima cuántos tokens podría generar la respuesta.

    Es una heurística simple para tener una estimación total antes de recibir
    la respuesta real del proveedor.
    """
    prompt_tokens = estimar_tokens_prompt(prompt)
    return max(16, math.ceil(prompt_tokens * 0.75))


def estimar_coste_total(prompt: str, modelo: str) -> Dict[str, float]:
    """
    Estima el coste total aproximado del prompt más la respuesta.
    """
    prompt_tokens = estimar_tokens_prompt(prompt)
    completion_tokens = estimar_completion_tokens(prompt)
    costes = _calcular_costes(modelo, prompt_tokens, completion_tokens)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens_estimados": completion_tokens,
        "prompt_cost": costes["prompt_cost"],
        "completion_cost": costes["completion_cost"],
        "total_cost": costes["total_cost"],
    }


def evaluar_complejidad(prompt: str) -> str:
    """
    CRITERIO 1: Evalúa la complejidad mediante análisis semántico (O(n)).
    Busca intersecciones entre las palabras del usuario y nuestro diccionario.
    """
    modelo, _ = _detectar_modelo(prompt)
    return modelo


async def enrutar_peticion(prompt: str, porcentaje_presupuesto_gastado: float, mensajes_completos: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Función principal de El Cerebro (Módulo 3).
    Decide el modelo, aplica políticas FinOps de ahorro y gestiona la llamada HTTP asíncrona.
    """
    logger.info("Evaluando enrutamiento. Gasto actual del consumidor: %.2f%%", porcentaje_presupuesto_gastado)

    # 1. Aplicar Criterio 1: Complejidad del prompt (Ahora con palabras clave)
    modelo_elegido, motivo_ruta = _detectar_modelo(prompt)
    url_destino = PROVEEDOR_A_URL if modelo_elegido == "llama3.2:3b" else PROVEEDOR_B_URL
    proveedor_destino = "provider-a" if modelo_elegido == "llama3.2:3b" else "provider-b"
    degradado_por_finops = False
    estimacion_costes = estimar_coste_total(prompt, modelo_elegido)

    # 2. Aplicar Criterio 2: FinOps (Degradación controlada de servicio por presupuesto crítico)
    if porcentaje_presupuesto_gastado >= 90.0 and modelo_elegido == "mistral:7b":
        logger.warning("Alerta FinOps: consumo >= 90%%. Forzando degradación a llama3.2:3b para mitigar costes.")
        modelo_elegido = "llama3.2:3b"
        url_destino = PROVEEDOR_A_URL
        proveedor_destino = "provider-a"
        degradado_por_finops = True

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

            respuesta_json = respuesta.json()
            respuesta_json["router"] = {
                "provider": proveedor_destino,
                "model": modelo_elegido,
                "degraded_by_finops": degradado_por_finops,
                "routing_reason": motivo_ruta,
                "estimated_prompt_tokens": estimacion_costes["prompt_tokens"],
                "estimated_completion_tokens": estimacion_costes["completion_tokens_estimados"],
                "estimated_prompt_cost": estimacion_costes["prompt_cost"],
                "estimated_completion_cost": estimacion_costes["completion_cost"],
                "estimated_total_cost": estimacion_costes["total_cost"],
            }

            # Devolvemos la respuesta del proveedor con metadata adicional de ruta
            return respuesta_json

    except httpx.HTTPStatusError as e:
        logger.exception("El proveedor de IA devolvió un error de estado")
        return {"error": "Error interno del proveedor de IA", "detalles": str(e)}
    except httpx.RequestError as e:
        logger.exception("Error de red al intentar conectar con el proveedor")
        return {"error": "No se pudo establecer conexión con el motor de IA", "detalles": str(e)}

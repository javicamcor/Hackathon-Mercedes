import asyncio
import os
import logging
import re
import unicodedata
import time

import httpx
from deep_translator import GoogleTranslator

# =====================================================================
# CATÁLOGO ESCALABLE DE MODELOS
# =====================================================================
REGISTRO_MODELOS = {
    "llama3.2:3b": {
        "proveedor": "provider-a",
        "url": os.getenv("AI_FINOPS_PROVIDER_A_URL", "http://localhost:11434/v1/chat/completions"),
        "nivel_exigencia": 1,      # Nivel 1: Para peticiones estándar o incompletas
        "precio_in": 0.06,
        "precio_out": 0.06,
        "factor_eficiencia": 0.82
    },
    "mistral:7b": {
        "proveedor": "provider-b",
        "url": os.getenv("AI_FINOPS_PROVIDER_B_URL", "http://localhost:11435/v1/chat/completions"),
        "nivel_exigencia": 2,      # Nivel 2: Para peticiones estrictamente complejas y largas
        "precio_in": 0.24,
        "precio_out": 0.24,
        "factor_eficiencia": 1.00
    }
}

logger = logging.getLogger(__name__)

# =====================================================================
# DICCIONARIO SEMÁNTICO
# =====================================================================
PALABRAS_COMPLEJAS = {
    # 1. Programming Languages and Technologies
    "python", "javascript", "java", "c++", "c#", "sql", "html", "css", "php",
    "ruby", "swift", "golang", "rust", "bash", "shell", "powershell", "typescript",
    "docker", "kubernetes", "git", "linux", "aws", "azure", "gcp", "terraform",
    "kotlin", "scala", "dart", "perl", "haskell", "lua", "matlab", "r",

    # 2. Development and Architecture Concepts
    "api", "rest", "graphql", "json", "xml", "yaml", "regex", "debug", "refactor",
    "compile", "deployment", "frontend", "backend", "query", "algorithm",
    "loop", "function", "class", "object", "asynchronous", "framework", "react",
    "angular", "vue", "django", "flask", "fastapi", "node", "express", "spring",
    "architecture", "scalability", "performance", "microservices", "pattern",
    "script", "code", "program", "variable", "repository", "commit", "merge",
    "pipeline", "ci/cd", "testing", "unit", "mock", "middleware", "endpoint",

    # 3. Data, Databases and Formats
    "csv", "excel", "pandas", "dataframe", "scraping", "parse", "extract",
    "transform", "etl", "dashboard", "chart", "visualization", "dataset",
    "mysql", "postgres", "mongodb", "nosql", "redis", "elasticsearch", "supabase",
    "oracle", "sqlite", "cassandra", "hadoop", "spark", "kafka", "parquet",

    # 4. Data Science, AI and Machine Learning
    "machine", "learning", "ai", "deep", "networks", "neural", "nlp", "vision",
    "training", "prediction", "clustering", "regression", "classification",
    "tensor", "pytorch", "scikit", "llm", "prompt", "token", "embedding",

    # 5. Reasoning, Logic and Mathematics
    "analyze", "evaluate", "compare", "deduce", "justify", "optimize", "abstraction",
    "inference", "statistics", "probability", "mathematics", "calculus", "equation",
    "integral", "derivative", "matrix", "algebra", "physics", "theory", "theorem",
    "prove", "logic", "hypothesis", "complexity", "heuristic", "trigonometry",
    "geometry", "arithmetic", "proportion", "variance", "distribution",

    # 6. Professional, Legal and Corporate Documentation
    "essay", "thesis", "report", "contract", "legal", "clause", "patent",
    "scientific", "paper", "methodology", "bibliography", "citation", "apa",
    "regulation", "compliance", "audit", "vulnerability", "cybersecurity",
    "gdpr", "cryptography", "encryption", "strategic", "financial", "balance"
}

def _normalizar_texto(texto: str) -> str:
    texto_normalizado = unicodedata.normalize("NFKD", texto)
    texto_sin_tildes = "".join(
        caracter for caracter in texto_normalizado if not unicodedata.combining(caracter)
    )
    return texto_sin_tildes.casefold()

def evaluar_complejidad(prompt: str) -> int:
    """
    Asigna el Nivel de Exigencia:
    - Nivel 2 (Mistral): DEBE tener palabras clave Y más de 400 caracteres.
    - Nivel 1 (Llama): Cualquier otra cosa (falla en uno o ambos requisitos).
    """
    try:
        texto_a_traducir = prompt[:4500] if len(prompt) > 4500 else prompt
        if texto_a_traducir.strip():
            prompt_en = GoogleTranslator(source='auto', target='en').translate(texto_a_traducir)
        else:
            prompt_en = prompt
    except Exception as e:
        logger.error(f"Error translating prompt: {e}")
        prompt_en = prompt

    prompt_normalizado = _normalizar_texto(prompt_en)
    palabras_prompt_actual = set(re.findall(r'\b\w+\b', prompt_normalizado))

    tiene_palabras_complejas = bool(palabras_prompt_actual.intersection(PALABRAS_COMPLEJAS))
    es_largo = len(prompt) > 400

    if tiene_palabras_complejas and es_largo:
        return 2  # Pasa al resto (Mistral)

    return 1  # Va a Llama

def _seleccionar_mejor_modelo(nivel_requerido: int, modelo_solicitado: str) -> tuple[str, str]:
    modelos_validos = {
        nombre: info for nombre, info in REGISTRO_MODELOS.items()
        if info["nivel_exigencia"] >= nivel_requerido
    }

    if not modelos_validos:
        modelo_ideal = max(REGISTRO_MODELOS.items(), key=lambda x: x[1]["nivel_exigencia"])[0]
    else:
        modelo_ideal = min(modelos_validos.items(), key=lambda x: x[1]["precio_in"] + x[1]["precio_out"])[0]

    if modelo_solicitado and modelo_solicitado in REGISTRO_MODELOS:
        return modelo_solicitado, "Elección Explícita Respetada"

    return modelo_ideal, f"Enrutamiento Automático (Nivel {nivel_requerido})"

async def enrutar_peticion(prompt: str, porcentaje_presupuesto_gastado: float, mensajes_completos: list, modelo_solicitado: str) -> tuple[dict, dict]:
    nivel_requerido = evaluar_complejidad(prompt)
    modelo_elegido, regla_aplicada = _seleccionar_mejor_modelo(nivel_requerido, modelo_solicitado)

    if porcentaje_presupuesto_gastado >= 90.0:
        modelo_elegido = min(REGISTRO_MODELOS.items(), key=lambda x: x[1]["precio_in"] + x[1]["precio_out"])[0]
        regla_aplicada = "Degradación FinOps (Presupuesto >90%)"

    url_destino = REGISTRO_MODELOS[modelo_elegido]["url"]
    metadata = {"rule": regla_aplicada, "provider": REGISTRO_MODELOS[modelo_elegido]["proveedor"]}

    payload = {
        "model": modelo_elegido,
        "messages": mensajes_completos,
        "temperature": 0.7
    }

    try:
        async with httpx.AsyncClient() as client:
            t0_http = time.time()
            respuesta = await client.post(url_destino, json=payload, timeout=300.0)
            metadata["llm_latency_ms"] = (time.time() - t0_http) * 1000
            respuesta.raise_for_status()
            resp_json = respuesta.json()
            if isinstance(resp_json, dict) and "model" not in resp_json:
                resp_json["model"] = modelo_elegido
            return resp_json, metadata
    except httpx.HTTPStatusError as e:
        return {"error": "Error interno del proveedor de IA", "detalles": str(e)}, metadata
    except httpx.RequestError as e:
        return {"error": "No se pudo establecer conexión con el motor de IA", "detalles": str(e)}, metadata
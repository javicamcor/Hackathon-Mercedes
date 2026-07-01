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

PALABRAS_CAMBIO_RADICAL = {
    "hola", "adios", "gracias", "ok", "perfecto", "tiempo", "clima", 
    "chiste", "buenos", "dias", "noches", "tardes", "bien", "chao"
}

# Si el usuario dice algo corto pero usa estas palabras, MANTENEMOS el modelo complejo.
PALABRAS_CONTINUIDAD = {
    "resumen", "resume", "ejemplo", "explica", "escribe", "corrige", 
    "modifica", "cambia", "esto", "eso", "aquello", "continua", "sigue", "amplia"
}

def _normalizar_texto(texto: str) -> str:
    texto_normalizado = unicodedata.normalize("NFKD", texto)
    texto_sin_tildes = "".join(
        caracter for caracter in texto_normalizado if not unicodedata.combining(caracter)
    )
    return texto_sin_tildes.casefold()


def evaluar_complejidad(prompt: str, mensajes_completos: list) -> str:
    """
    CRITERIO 1 Avanzado: El "Semáforo Inteligente".
    Resuelve el dilema de la memoria pegajosa discriminando entre cambios
    radicales de tema y necesidades de continuidad del contexto.
    """
    # 1. Normalizar y aislar la ÚLTIMA pregunta del usuario (El Presente)
    prompt_normalizado = _normalizar_texto(prompt)
    palabras_prompt_actual = set(re.findall(r'\b\w+\b', prompt_normalizado))

    # REGLA B: COINCIDENCIA TÉCNICA DIRECTA (Caso: "Hazme el TFG")
    # Si la pregunta de ahora mismo ya trae dinamita técnica, va a Mistral de cabeza.
    if palabras_prompt_actual.intersection(PALABRAS_COMPLEJAS):
        logger.info("🧠 [Router] Keyword compleja detectada en el prompt actual. Usando: mistral:7b")
        return "mistral:7b"

    # REGLA C: REVISIÓN INTELIGENTE DEL CACHÉ (Caso: "Hazme un resumen")
    # Si la pregunta actual es ambigua pero requiere arrastrar contexto anterior:
    if len(mensajes_completos) > 2 and palabras_prompt_actual.intersection(PALABRAS_CONTINUIDAD):
        # Buscamos en el historial qué fue lo último que preguntó el usuario
        ultimo_prompt_usuario = ""
        for msg in reversed(mensajes_completos[:-1]):
            if msg.get("role") == "user":
                ultimo_prompt_usuario = _normalizar_texto(msg.get("content", ""))
                break
        
        palabras_historial = set(re.findall(r"\b\w+\b", ultimo_prompt_usuario))
        # Si veníamos de hablar de algo difícil en la caché, mantenemos el modelo potente
        if palabras_historial.intersection(PALABRAS_COMPLEJAS):
            logger.info("⏳ [Router] Manteniendo mistral:7b por arrastre e inercia del tema complejo anterior.")
            return "mistral:7b"

    # REGLA A: EL CORTAFUEGOS (Caso: "¿Dime el tiempo?")
    # Si la pregunta actual es de cortesía o un tema radicalmente simple,
    # ignoramos el historial anterior y forzamos Llama 3.2.
    if palabras_prompt_actual.intersection(PALABRAS_CAMBIO_RADICAL) or len(prompt_normalizado) < 30:
        logger.info("💥 [Router] Cambio radical de tema o cortesía detectado. Forzando: llama3.2:3b")
        return "llama3.2:3b"

    # REGLA D: FALLBACK POR LONGITUD DE TEXTO
    UMBRAL_CARACTERES = 400
    if len(prompt_normalizado) > UMBRAL_CARACTERES:
        logger.info("📏 [Router] Prompt largo sin palabras clave. Usando: mistral:7b")
        return "mistral:7b"

    # Por defecto, si no hay motivos para usar el caro, usamos el barato
    logger.info("🍃 [Router] Petición estándar suelta. Usando: llama3.2:3b")
    return "llama3.2:3b"

async def enrutar_peticion(prompt: str, porcentaje_presupuesto_gastado: float, mensajes_completos: list, modelo_solicitado: str) -> tuple[dict, dict]:
    """
    Función principal de El Cerebro (Módulo 3).
    Decide el modelo, aplica políticas FinOps de ahorro y gestiona la llamada HTTP asíncrona.
    """
    logger.info("Evaluando enrutamiento. Gasto actual del consumidor: %.2f%%", porcentaje_presupuesto_gastado)

    metadata = {"rule": "Ninguna"}

    # 1. Aplicar Criterio 1: Complejidad del prompt (Ahora con palabras clave)
    modelo_elegido = evaluar_complejidad(prompt, mensajes_completos)
    if modelo_elegido != modelo_solicitado:
        metadata["rule"] = "Enrutamiento por Complejidad"
        
    url_destino = PROVEEDOR_A_URL if modelo_elegido == "llama3.2:3b" else PROVEEDOR_B_URL

    # 2. Aplicar Criterio 2: FinOps (Degradación controlada de servicio por presupuesto crítico)
    if porcentaje_presupuesto_gastado >= 90.0 and modelo_elegido == "mistral:7b":
        logger.warning("Alerta FinOps: consumo >= 90%%. Forzando degradación a llama3.2:3b para mitigar costes.")
        modelo_elegido = "llama3.2:3b"
        url_destino = PROVEEDOR_A_URL
        metadata["rule"] = "Degradación FinOps"

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

            return resp_json, metadata

    except httpx.HTTPStatusError as e:
        logger.exception("El proveedor de IA devolvió un error de estado")
        return {"error": "Error interno del proveedor de IA", "detalles": str(e)}, metadata
    except httpx.RequestError as e:
        logger.exception("Error de red al intentar conectar con el proveedor")
        return {"error": "No se pudo establecer conexión con el motor de IA", "detalles": str(e)}, metadata

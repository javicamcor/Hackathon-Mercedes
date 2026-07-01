import time
from typing import List, Optional
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.db.database import check_budget, log_usage, buscar_en_cache, guardar_en_cache
from app.core.router import enrutar_peticion, PRECIOS

router = APIRouter()

class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

def _construir_respuesta_cache(modelo: str, texto: str, p_tokens: int, c_tokens: int) -> dict:
    return {
        "id": f"chatcmpl-cache-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": modelo,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": texto
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": p_tokens,
            "completion_tokens": c_tokens,
            "total_tokens": p_tokens + c_tokens
        }
    }


def _calcular_coste(modelo: str, prompt_tokens: int, completion_tokens: int) -> float:
    tarifas = PRECIOS.get(modelo, {"entrada": 0.0, "salida": 0.0})
    return (prompt_tokens * tarifas["entrada"] / 1_000_000) + (completion_tokens * tarifas["salida"] / 1_000_000)


def _estimar_modelo_contrario(modelo_real: str, prompt_tokens: int, completion_tokens: int) -> tuple[str, int, int]:
    """Estima los tokens del modelo contrario usando la relación media 18% menos de llama frente a mistral."""
    ratio_llama_vs_mistral = 0.82
    if modelo_real == "llama3.2:3b":
        return "mistral:7b", prompt_tokens, max(1, round(completion_tokens / ratio_llama_vs_mistral))
    if modelo_real == "mistral:7b":
        return "llama3.2:3b", prompt_tokens, max(1, round(completion_tokens * ratio_llama_vs_mistral))
    return modelo_real, prompt_tokens, completion_tokens

@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    x_consumer_id: Optional[str] = Header(None, alias="X-Consumer-ID")
):
    print("-> [Interceptor] Petición recibida en /v1/chat/completions")
    
    if not x_consumer_id:
        print("-> [Interceptor] Error: Falta cabecera X-Consumer-ID")
        raise HTTPException(status_code=400, detail="X-Consumer-ID header is required")

    print(f"-> [Interceptor] Consumidor identificado: {x_consumer_id}")
    
    # Paso A: Verificar Presupuesto
    has_budget, consumer_data = check_budget(x_consumer_id)
    if not has_budget:
        raise HTTPException(status_code=402, detail="Presupuesto agotado")
        
    # Paso B: Alerta FinOps
    porcentaje_gastado = (consumer_data["current_spend"] / consumer_data["budget_limit"]) * 100
    if porcentaje_gastado >= 80.0:
        print(f"🚨 [ALERTA FINOPS] ¡ATENCIÓN! El equipo '{x_consumer_id}' está al límite de su presupuesto. Consumo actual: {porcentaje_gastado:.2f}% 🚨")
        
    modelo_solicitado = request.model
    
    # Paso C: Caché Semántica
    prompt_usuario = request.messages[-1].content
    cache_result = buscar_en_cache(prompt_usuario)
    if cache_result:
        print("-> [Caché] ¡Acierto! Devolviendo respuesta cacheada.")
        texto_cacheado = cache_result.get("respuesta", "")
        coste_original = float(cache_result.get("original_cost", 0.0))

        # En caché, el ahorro es exactamente el coste previo real de la petición original.
        log_usage(x_consumer_id, modelo_solicitado, "caché", 0, 0, 0.0, "Caché Semántica", coste_original)
        respuesta_cache = _construir_respuesta_cache(modelo_solicitado, texto_cacheado, p_tokens=0, c_tokens=0)
        respuesta_cache["savings"] = coste_original
        return respuesta_cache

    # Paso D: Enrutamiento Real
    mensajes_completos = [{"role": msg.role, "content": msg.content} for msg in request.messages]
    ia_response, metadata = await enrutar_peticion(prompt_usuario, porcentaje_gastado, mensajes_completos, modelo_solicitado)
    
    if "error" in ia_response:
        raise HTTPException(status_code=500, detail=ia_response.get("detalles", ia_response["error"]))

    # Paso E: Cálculo de Coste Exacto
    modelo_real = ia_response.get("model", modelo_solicitado)
    usage = ia_response.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    
    coste_total = _calcular_coste(modelo_real, prompt_tokens, completion_tokens)

    # Estimamos el coste del modelo contrario usando la relación media de tokens.
    modelo_contrario, prompt_tokens_contrario, completion_tokens_contrario = _estimar_modelo_contrario(
        modelo_real, prompt_tokens, completion_tokens
    )
    coste_modelo_contrario = _calcular_coste(modelo_contrario, prompt_tokens_contrario, completion_tokens_contrario)

    savings = max(0.0, coste_modelo_contrario - coste_total)
    applied_rule = metadata.get("rule", "Ninguna")

    # Paso F: Persistencia
    print(f"-> [FinOps Log] Registrando coste exacto: ${coste_total:.6f} en {modelo_real}")
    log_usage(x_consumer_id, modelo_solicitado, modelo_real, prompt_tokens, completion_tokens, coste_total, applied_rule, savings)

    # Paso G: Guardar Caché
    try:
        texto_generado = ia_response["choices"][0]["message"]["content"]
        guardar_en_cache(prompt_usuario, texto_generado, modelo_real, original_cost=coste_total)
    except (KeyError, IndexError) as e:
        print(f"-> [Advertencia] No se pudo guardar en caché (estructura inesperada): {e}")

    # Paso H: Retornar respuesta
    return ia_response

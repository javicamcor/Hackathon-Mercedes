import time
from typing import List, Optional
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.db.database import check_budget, log_usage, buscar_en_cache, guardar_en_cache, LLAMA_TOKEN_RATIO_VS_MISTRAL
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


def _calcular_coste_referencia(modelo_real: str, prompt_tokens: int, completion_tokens: int) -> tuple[str, float]:
    """Devuelve el modelo de referencia y su coste estimado.

    Si el modelo real es llama, la referencia es mistral y viceversa. Además, se ajustan
    los tokens de referencia teniendo en cuenta que llama consume ~18% menos tokens que mistral.
    """
    if modelo_real == "llama3.2:3b":
        modelo_referencia = "mistral:7b"
        ref_prompt_tokens = max(1, round(prompt_tokens / LLAMA_TOKEN_RATIO_VS_MISTRAL)) if prompt_tokens else 0
        ref_completion_tokens = max(1, round(completion_tokens / LLAMA_TOKEN_RATIO_VS_MISTRAL)) if completion_tokens else 0
    else:
        modelo_referencia = "llama3.2:3b"
        ref_prompt_tokens = max(1, round(prompt_tokens * LLAMA_TOKEN_RATIO_VS_MISTRAL)) if prompt_tokens else 0
        ref_completion_tokens = max(1, round(completion_tokens * LLAMA_TOKEN_RATIO_VS_MISTRAL)) if completion_tokens else 0

    coste_referencia = _calcular_coste(modelo_referencia, ref_prompt_tokens, ref_completion_tokens)
    return modelo_referencia, coste_referencia

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
        print("-> [Caché] ¡Acierto! Devolviendo respuesta cacheada (Coste 0).")
        # Aseguramos extraer texto (soportando posible formato string o dict/tuple devuelto por la db)
        texto_cacheado = cache_result if isinstance(cache_result, str) else cache_result[0] if isinstance(cache_result, tuple) else cache_result.get("respuesta", str(cache_result))
        
        # Calculate theoretical cost for savings
        tarifas_solicitado = PRECIOS.get(modelo_solicitado, {"entrada": 0, "salida": 0})
        p_tokens = max(1, len(prompt_usuario) // 4)
        c_tokens = max(1, len(texto_cacheado) // 4)
        coste_solicitado = (p_tokens * tarifas_solicitado["entrada"] / 1_000_000) + (c_tokens * tarifas_solicitado["salida"] / 1_000_000)
        
        # En caché usamos el coste solicitado como referencia para que el dashboard pueda mostrar el ahorro.
        log_usage(x_consumer_id, modelo_solicitado, "caché", 0, 0, 0.0, "Caché Semántica", coste_solicitado)
        respuesta_cache = _construir_respuesta_cache(modelo_solicitado, texto_cacheado, p_tokens=0, c_tokens=0)
        respuesta_cache["savings"] = coste_solicitado
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
    
    # Obtenemos precios (por millón) y calculamos coste real
    tarifas_reales = PRECIOS.get(modelo_real, {"entrada": 0, "salida": 0})
    coste_total = (prompt_tokens * tarifas_reales["entrada"] / 1_000_000) + (completion_tokens * tarifas_reales["salida"] / 1_000_000)

    # Calculamos coste si se hubiera usado el modelo solicitado
    tarifas_solicitadas = PRECIOS.get(modelo_solicitado, {"entrada": 0, "salida": 0})
    coste_solicitado = (prompt_tokens * tarifas_solicitadas["entrada"] / 1_000_000) + (completion_tokens * tarifas_solicitadas["salida"] / 1_000_000)

    # Calculamos el ahorro usando la diferencia entre el coste del modelo solicitado y el coste real.
    savings = max(0.0, coste_solicitado - coste_total)
    applied_rule = metadata.get("rule", "Ninguna")

    # Paso F: Persistencia
    print(f"-> [FinOps Log] Registrando coste exacto: ${coste_total:.6f} en {modelo_real}")
    log_usage(x_consumer_id, modelo_solicitado, modelo_real, prompt_tokens, completion_tokens, coste_total, applied_rule, savings)

    ia_response["savings"] = savings
    ia_response["requested_cost"] = coste_solicitado

    # Paso G: Guardar Caché
    try:
        texto_generado = ia_response["choices"][0]["message"]["content"]
        guardar_en_cache(prompt_usuario, texto_generado, modelo_real)
    except (KeyError, IndexError) as e:
        print(f"-> [Advertencia] No se pudo guardar en caché (estructura inesperada): {e}")

    # Paso H: Retornar respuesta
    return ia_response

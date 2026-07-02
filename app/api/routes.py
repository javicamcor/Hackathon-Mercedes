import time
from typing import List, Optional
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.db.database import check_budget, log_usage, buscar_en_cache, guardar_en_cache, log_alert
from app.core.router import enrutar_peticion, REGISTRO_MODELOS, comprimir_prompt

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
            {"index": 0, "message": {"role": "assistant", "content": texto}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": p_tokens, "completion_tokens": c_tokens, "total_tokens": p_tokens + c_tokens}
    }

@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    x_consumer_id: Optional[str] = Header(None, alias="X-Consumer-ID")
):
    start_time = time.time()
    
    if not x_consumer_id:
        raise HTTPException(status_code=400, detail="X-Consumer-ID header is required")

    has_budget, consumer_data = check_budget(x_consumer_id)
    if not has_budget:
        mensaje_bloqueo = f"¡BLOQUEO! El equipo '{x_consumer_id}' agotó su presupuesto de ${consumer_data['budget_limit']}."
        log_alert(x_consumer_id, mensaje_bloqueo)
        raise HTTPException(status_code=402, detail="Presupuesto agotado")

    porcentaje_gastado = (consumer_data["current_spend"] / consumer_data["budget_limit"]) * 100
    if porcentaje_gastado >= 80.0:
        mensaje_alerta = f"¡ATENCIÓN! Equipo '{x_consumer_id}' al {porcentaje_gastado:.2f}% de consumo."
        log_alert(x_consumer_id, mensaje_alerta)

    modelo_solicitado = request.model

    
    prompt_usuario = comprimir_prompt(request.messages[-1].content)
    request.messages[-1].content = prompt_usuario

    cache_result = buscar_en_cache(prompt_usuario)
    if cache_result:
        texto_cacheado = cache_result.get("respuesta") if isinstance(cache_result, dict) else cache_result
        modelo_original_cacheado = cache_result.get("modelo") if isinstance(cache_result, dict) else modelo_solicitado

        coste_ahorrado = cache_result.get("coste_original", 0.0) if isinstance(cache_result, dict) else 0.0
        if coste_ahorrado == 0.0:
            info_orig = REGISTRO_MODELOS.get(modelo_original_cacheado, REGISTRO_MODELOS["llama3.2:3b"])
            p_tokens_est = max(1, len(prompt_usuario) // 3)
            c_tokens_est = max(1, len(texto_cacheado) // 3)
            coste_ahorrado = (p_tokens_est * info_orig["precio_in"] / 1_000_000) + (c_tokens_est * info_orig["precio_out"] / 1_000_000)

        latency_ms = round((time.time() - start_time) * 1000, 2)
        log_usage(x_consumer_id, modelo_solicitado, "caché", 0, 0, 0.0, "Caché Semántica", coste_ahorrado, latency_ms)
        return _construir_respuesta_cache(modelo_original_cacheado, texto_cacheado, p_tokens=0, c_tokens=0)

    mensajes_completos = [{"role": msg.role, "content": msg.content} for msg in request.messages]
    ia_response, metadata = await enrutar_peticion(prompt_usuario, porcentaje_gastado, mensajes_completos, modelo_solicitado)
    if "error" in ia_response:
        raise HTTPException(status_code=500, detail=ia_response.get("detalles", ia_response["error"]))

    modelo_real = ia_response.get("model", modelo_solicitado)
    usage = ia_response.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)

    info_real = REGISTRO_MODELOS.get(modelo_real, REGISTRO_MODELOS["llama3.2:3b"])
    coste_total = (prompt_tokens * info_real["precio_in"] / 1_000_000) + (completion_tokens * info_real["precio_out"] / 1_000_000)

    if modelo_solicitado in REGISTRO_MODELOS:
        modelo_base_ahorro = modelo_solicitado
    else:
        modelo_base_ahorro = max(REGISTRO_MODELOS.items(), key=lambda x: x[1]["nivel_exigencia"])[0]

    info_base = REGISTRO_MODELOS[modelo_base_ahorro]

    if modelo_base_ahorro == modelo_real:
        coste_solicitado = coste_total
    else:
        factor_real = info_real["factor_eficiencia"]
        factor_base = info_base["factor_eficiencia"]

        p_tokens_teoricos = prompt_tokens * (factor_base / factor_real)
        c_tokens_teoricos = completion_tokens * (factor_base / factor_real)

        coste_solicitado = (p_tokens_teoricos * info_base["precio_in"] / 1_000_000) + (c_tokens_teoricos * info_base["precio_out"] / 1_000_000)

    savings = max(0.0, coste_solicitado - coste_total)
    applied_rule = metadata.get("rule", "Ninguna")

    llm_latency_ms = metadata.get("llm_latency_ms", 0.0)
    latency_ms = round(max(0.01, ((time.time() - start_time) * 1000) - llm_latency_ms), 2)
    
    log_usage(x_consumer_id, modelo_solicitado, modelo_real, prompt_tokens, completion_tokens, coste_total, applied_rule, savings, latency_ms)

    try:
        texto_generado = ia_response["choices"][0]["message"]["content"]
        guardar_en_cache(prompt_usuario, texto_generado, modelo_real, coste_total)
    except (KeyError, IndexError):
        pass

    return ia_response
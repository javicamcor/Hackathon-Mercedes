import time
from typing import List, Optional
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.db.database import check_budget, log_usage, buscar_en_cache, guardar_en_cache, log_alert
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
        mensaje_bloqueo = f"¡BLOQUEO! El equipo '{x_consumer_id}' ha agotado su presupuesto de ${consumer_data['budget_limit']}."
        print(f"[ALERTA FINOPS] {mensaje_bloqueo}")
        log_alert(x_consumer_id, mensaje_bloqueo)
        raise HTTPException(status_code=402, detail="Presupuesto agotado")
        
    # Paso B: Alerta FinOps
    porcentaje_gastado = (consumer_data["current_spend"] / consumer_data["budget_limit"]) * 100
    if porcentaje_gastado >= 80.0:
        mensaje_alerta = f"¡ATENCIÓN! El equipo '{x_consumer_id}' está al límite de su presupuesto. Consumo actual: {porcentaje_gastado:.2f}%"
        print(f"[ALERTA FINOPS] {mensaje_alerta}")
        log_alert(x_consumer_id, mensaje_alerta)
        
    modelo_solicitado = request.model
    
    # Paso C: Caché Semántica
    prompt_usuario = request.messages[-1].content
    cache_result = buscar_en_cache(prompt_usuario)
    if cache_result:
        print("-> [Caché] ¡Acierto! Devolviendo respuesta cacheada (Coste 0).")
        # Aseguramos extraer texto (soportando posible formato string o dict/tuple devuelto por la db)
        texto_cacheado = cache_result.get("respuesta") if isinstance(cache_result, dict) else cache_result
        
        # Calculate theoretical cost for savings
        tarifas_solicitado = PRECIOS.get(modelo_solicitado, {"entrada": 0, "salida": 0})
        p_tokens = max(1, len(prompt_usuario) // 3) 
        c_tokens = max(1, len(texto_cacheado) // 3)
        coste_solicitado = (p_tokens * tarifas_solicitado["entrada"] / 1_000_000) + (c_tokens * tarifas_solicitado["salida"] / 1_000_000)
        
        log_usage(x_consumer_id, modelo_solicitado, "caché", 0, 0, 0.0, "Caché Semántica", coste_solicitado)
        return _construir_respuesta_cache(modelo_solicitado, texto_cacheado, p_tokens=0, c_tokens=0)

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
    
    savings = max(0.0, coste_solicitado - coste_total)
    applied_rule = metadata.get("rule", "Ninguna")

    # Paso F: Persistencia
    print(f"-> [FinOps Log] Registrando coste exacto: ${coste_total:.6f} en {modelo_real}")
    log_usage(x_consumer_id, modelo_solicitado, modelo_real, prompt_tokens, completion_tokens, coste_total, applied_rule, savings)

    # Paso G: Guardar Caché
    try:
        texto_generado = ia_response["choices"][0]["message"]["content"]
        guardar_en_cache(prompt_usuario, texto_generado, modelo_real)
    except (KeyError, IndexError) as e:
        print(f"-> [Advertencia] No se pudo guardar en caché (estructura inesperada): {e}")

    # Paso H: Retornar respuesta
    return ia_response

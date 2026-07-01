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

@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    x_consumer_id: Optional[str] = Header(None, alias="X-Consumer-ID")
):
    print(f"\n-> [Interceptor] Petición recibida para modelo: {request.model}")
    
    if not x_consumer_id:
        print("-> [Interceptor] Error: Falta cabecera X-Consumer-ID")
        raise HTTPException(status_code=400, detail="X-Consumer-ID header is required")
        
    print(f"-> [Interceptor] Consumidor identificado: {x_consumer_id}")
    
    # 1. Validar Presupuesto
    has_budget, consumer = check_budget(x_consumer_id)
    if consumer == "Consumidor no encontrado":
        raise HTTPException(status_code=403, detail="Consumer not found in database")
        
    if not has_budget:
        print(f"-> [FinOps] Bloqueo: El consumidor {x_consumer_id} ha superado su presupuesto.")
        raise HTTPException(status_code=402, detail="Budget limit exceeded")
        
    budget = consumer["budget_limit"]
    spent = consumer["current_spend"]
    pct_spent = (spent / budget) * 100 if budget > 0 else 100.0
    
    prompt = request.messages[-1].content if request.messages else ""
    
    # 2. Comprobar Caché
    cached = buscar_en_cache(prompt)
    if cached:
        print("-> [Cache] Acierto de caché. Devolviendo respuesta almacenada.")
        log_usage(x_consumer_id, request.model, cached["modelo"], 0, 0, 0.0, "Cache Hit", 0.0)
        return {
            "id": "chatcmpl-cache",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": cached["modelo"],
            "choices": [{"index": 0, "message": {"role": "assistant", "content": cached["respuesta"]}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        }
        
    # 3. Enrutar petición
    mensajes_dict = [{"role": m.role, "content": m.content} for m in request.messages]
    ollama_response, modelo_usado, regla_aplicada = await enrutar_peticion(prompt, pct_spent, mensajes_dict)
    
    if "error" in ollama_response:
        raise HTTPException(status_code=500, detail=ollama_response["error"])
        
    # 4. Calcular Costes y Ahorros
    usage = ollama_response.get("usage", {})
    p_tokens = usage.get("prompt_tokens", 0)
    c_tokens = usage.get("completion_tokens", 0)
    
    # Convertir precio por millón a precio por token
    precio_entrada = PRECIOS.get(modelo_usado, {"entrada": 0})["entrada"] / 1_000_000
    precio_salida = PRECIOS.get(modelo_usado, {"salida": 0})["salida"] / 1_000_000
    coste_real = (p_tokens * precio_entrada) + (c_tokens * precio_salida)
    
    ahorro = 0.0
    if request.model != modelo_usado and request.model in PRECIOS:
        p_entrada_req = PRECIOS[request.model]["entrada"] / 1_000_000
        p_salida_req = PRECIOS[request.model]["salida"] / 1_000_000
        coste_solicitado = (p_tokens * p_entrada_req) + (c_tokens * p_salida_req)
        ahorro = max(0.0, coste_solicitado - coste_real)
        
    # 5. Guardar en Caché y Base de datos
    try:
        respuesta_texto = ollama_response["choices"][0]["message"]["content"]
        guardar_en_cache(prompt, respuesta_texto, modelo_usado)
    except (KeyError, IndexError):
        pass # Por si la respuesta no tiene el formato esperado
        
    log_usage(x_consumer_id, request.model, modelo_usado, p_tokens, c_tokens, coste_real, regla_aplicada, ahorro)
    
    return ollama_response

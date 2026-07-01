import time
from typing import List, Optional
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

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
    print("-> [Interceptor] Petición recibida en /v1/chat/completions")
    
    if not x_consumer_id:
        print("-> [Interceptor] Error: Falta cabecera X-Consumer-ID")
        raise HTTPException(status_code=400, detail="X-Consumer-ID header is required")
        
    print(f"-> [Interceptor] Consumidor identificado: {x_consumer_id}")
    # TODO: Llamar a la BD y comprobar el presupuesto
    
    print("-> [Router IA] Enviando petición simulada a Ollama...")
    # TODO: Enviar la petición a Ollama
    
    mock_response = {
        "id": "chatcmpl-mock-finops",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "¡Hola! Soy el Guardián. Esta es una respuesta simulada con FinOps habilitado."
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 15,
            "completion_tokens": 10,
            "total_tokens": 25
        }
    }
    
    print("-> [Router IA] Respuesta simulada generada")
    
    print("-> [FinOps Log] Registrando coste en base de datos...")
    # TODO: Registrar el coste final en base de datos
    print(f"-> [FinOps Log] Coste registrado para {x_consumer_id}: 25 tokens")
    
    return mock_response

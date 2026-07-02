import asyncio
import sys
from pathlib import Path
from unittest.mock import patch


sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.core.router import enrutar_peticion, evaluar_complejidad


def _mensajes(prompt: str, historial: list | None = None):
    mensajes = historial[:] if historial else []
    mensajes.append({"role": "user", "content": prompt})
    return mensajes


async def test_evaluar_complejidad_simple():
    assert evaluar_complejidad("Hola, ¿cómo estás?", _mensajes("Hola, ¿cómo estás?")) == "llama3.2:3b"


async def test_evaluar_complejidad_tecnica():
    prompt = "Escribe un script en python para web scraping"
    assert evaluar_complejidad(prompt, _mensajes(prompt)) == "mistral:7b"


async def test_evaluar_complejidad_tecnica_con_tildes():
    prompt = "Analiza la complejidad de una función asíncrona en Python"
    assert evaluar_complejidad(prompt, _mensajes(prompt)) == "mistral:7b"


async def test_evaluar_complejidad_con_historial_tecnico():
    historial = [
        {"role": "user", "content": "Necesito ayuda con un TFG de Python sobre APIs y arquitectura."},
        {"role": "assistant", "content": "Claro, vamos a trabajarlo paso a paso."},
    ]
    # Cambiamos "Hazme un resumen" por "Hazme un resumen de ese código" o "de ese TFG"
    prompt_continuidad = "Hazme un resumen de ese TFG"
    assert evaluar_complejidad(prompt_continuidad, _mensajes(prompt_continuidad, historial)) == "mistral:7b"

async def test_enrutado_por_presupuesto_alto():
    prompt = "Escribe un script en python para web scraping"
    mensajes = _mensajes(prompt)

    class MockResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "model": "llama3.2:3b",
                "choices": [
                    {
                        "message": {
                            "content": "Respuesta simulada"
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 8,
                    "total_tokens": 20
                }
            }

    with patch("httpx.AsyncClient.post", return_value=MockResponse()):
        respuesta, metadata = await enrutar_peticion(
            prompt,
            porcentaje_presupuesto_gastado=91.0,
            mensajes_completos=mensajes,
            modelo_solicitado="mistral:7b"
        )

    assert "choices" in respuesta
    assert respuesta["model"] == "llama3.2:3b"
    assert metadata["rule"] == "Degradación FinOps"

async def test_filtro_privacidad_gobernanza():
    """
    Test de unidad que valida que el cortafuegos de gobernanza detecta datos sensibles
    (como emails corporativos y números de bastidor/VIN) y los anonimiza correctamente.
    """
    prompt_con_datos = (
        "Hola, analiza el chasis del coche con VIN WDD1690311J123456 "
        "y manda el informe al ingeniero a hugo.perez@mercedes-benz.com"
    )
    mensajes = _mensajes(prompt_con_datos)

    class MockResponse:
        def raise_for_status(self):
            return None
        def json(self):
            return {
                "model": "llama3.2:3b",
                "choices": [{"message": {"content": "Procesado seguro"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5}
            }

    # Simulamos la llamada HTTP para verificar qué payload se manda de verdad a la IA
    with patch("httpx.AsyncClient.post", return_value=MockResponse()) as mock_post:
        respuesta, metadata = await enrutar_peticion(
            prompt=prompt_con_datos,
            porcentaje_presupuesto_gastado=10.0,
            mensajes_completos=mensajes,
            modelo_solicitado="llama3.2:3b"
        )
        
        # 1. Recuperamos el payload exacto que el proxy intentó enviar por la red
        # mock_post.call_args.kwargs['json'] extrae el diccionario enviado
        payload_enviado = mock_post.call_args[1]['json']
        ultimo_mensaje_enviado = payload_enviado["messages"][-1]["content"]

        # 2. VALIDACIÓN CLAVE: El texto enviado a Ollama NO debe contener los datos reales
        assert "WDD1690311J123456" not in ultimo_mensaje_enviado
        assert "hugo.perez@mercedes-benz.com" not in ultimo_mensaje_enviado
        
        # 3. Validamos que en su lugar viajen las etiquetas de enmascaramiento específicas de Mercedes (NUEVO)
        assert "[REDACTED_MERCEDES_VIN]" in ultimo_mensaje_enviado
        assert "[REDACTED_EMAIL]" in ultimo_mensaje_enviado


async def main():
    print("=== Probando router ===")

    await test_evaluar_complejidad_simple()
    print("OK: complejidad simple")

    await test_evaluar_complejidad_tecnica()
    print("OK: complejidad técnica")

    await test_evaluar_complejidad_tecnica_con_tildes()
    print("OK: complejidad técnica con tildes")

    await test_evaluar_complejidad_con_historial_tecnico()
    print("OK: complejidad con historial técnico")

    await test_enrutado_por_presupuesto_alto()
    print("OK: enrutado con presupuesto alto")

    await test_filtro_privacidad_gobernanza()
    print("OK: cortafuegos de privacidad y gobernanza")

    print("=== Router validado ===")


if __name__ == "__main__":
    asyncio.run(main())
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
    assert evaluar_complejidad("Hazme un resumen", _mensajes("Hazme un resumen", historial)) == "mistral:7b"


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

    print("=== Router validado ===")


if __name__ == "__main__":
    asyncio.run(main())
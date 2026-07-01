import asyncio
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.core.router import enrutar_peticion, evaluar_complejidad


async def test_evaluar_complejidad_simple():
    assert evaluar_complejidad("Hola, ¿cómo estás?") == "llama3.2:3b"


async def test_evaluar_complejidad_tecnica():
    assert evaluar_complejidad("Escribe un script en python para web scraping") == "mistral:7b"


async def test_evaluar_complejidad_tecnica_con_tildes():
    assert evaluar_complejidad("Analiza la complejidad de una función asíncrona en Python") == "mistral:7b"


async def test_enrutado_por_presupuesto_alto():
    prompt = "Escribe un script en python para web scraping"
    mensajes = [{"role": "user", "content": prompt}]

    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"ok": True}

    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        respuesta = await enrutar_peticion(
            prompt,
            porcentaje_presupuesto_gastado=91.0,
            mensajes_completos=mensajes,
        )

    assert respuesta["ok"] is True
    assert respuesta["router"]["provider"] == "provider-a"
    assert respuesta["router"]["model"] == "llama3.2:3b"
    assert respuesta["router"]["degraded_by_finops"] is True
    assert respuesta["router"]["routing_reason"] == "palabras_clave"
    assert mock_post.called


async def main():
    print("=== Probando router ===")

    await test_evaluar_complejidad_simple()
    print("OK: complejidad simple")

    await test_evaluar_complejidad_tecnica()
    print("OK: complejidad técnica")

    await test_evaluar_complejidad_tecnica_con_tildes()
    print("OK: complejidad técnica con tildes")

    await test_enrutado_por_presupuesto_alto()
    print("OK: enrutado con presupuesto alto")

    print("=== Router validado ===")


if __name__ == "__main__":
    asyncio.run(main())
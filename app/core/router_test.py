import asyncio
import sys
from pathlib import Path


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

    # Ahora este test es de integración y requiere los contenedores locales corriendo (task start)
    respuesta, metadata = await enrutar_peticion(
        prompt,
        porcentaje_presupuesto_gastado=91.0,
        mensajes_completos=mensajes,
        modelo_solicitado="mistral:7b"
    )

    assert "choices" in respuesta or "error" in respuesta
    assert metadata["rule"] == "Degradación FinOps"


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
# AI FinOps Proxy — EigenMinds

Bienvenido al repositorio central de nuestro proxy de FinOps para IA. 
Este proyecto intercepta llamadas a modelos de IA, calcula sus costes, aplica límites de presupuesto y enruta dinámicamente las peticiones para optimizar el gasto.

## 🚀 Modelos y Costes de Referencia

Trabajamos con dos modelos locales servidos mediante Ollama, simulando dos proveedores distintos con diferentes capacidades y precios:

| Proveedor | Modelo | URL Base | Coste Entrada (1M) | Coste Salida (1M) |
| :--- | :--- | :--- | :--- | :--- |
| **A (Rápido/Barato)** | `llama3.2:3b` | `http://localhost:11434/v1` | $0.06 | $0.06 |
| **B (Lento/Caro)** | `mistral:7b` | `http://localhost:11435/v1` | $0.24 | $0.24 |

---

## 👥 Reparto del Equipo y Tareas

Para avanzar en paralelo y evitar conflictos de código, el trabajo se divide en 4 módulos independientes con sus respectivas carpetas:

### 🛡️ 1. El Guardián (Core Proxy) -> Asignado a: Juan Manuel Díaz Guardia
**Objetivo:** Crear la puerta de entrada de todas las peticiones (el interceptor).
* **Stack:** Python + FastAPI.
* **Archivos:** `app/main.py` y `app/api/routes.py`
* **Tareas:**
  * Configurar la app de FastAPI en `main.py`.
  * Crear el endpoint POST en `/v1/chat/completions` dentro de `routes.py`.
  * Extraer el identificador del consumidor desde los headers (ej. `X-Consumer-ID`).
  * Interceptar la llamada llamando a la BD antes de procesar para verificar saldo.
  * Llamar al Enrutador para obtener la respuesta de la IA y devolver el JSON de OpenAI.

### 📊 2. El Contable (Base de Datos) -> Asignado a: Javier Campos Córcoles
**Objetivo:** Persistir presupuestos, consumidores y registrar cada céntimo gastado.
* **Stack:** Python + SQLite.
* **Archivos:** `app/db/database.py` y `app/db/models.py`
* **Tareas:**
  * Configurar la conexión a `finops.db` en `database.py`.
  * Definir los esquemas/tablas en `models.py` (consumers y logs, guardando los JSON crudos).
  * Programar funciones: `check_budget(consumer_id)`, `update_spend(...)` y `log_request(...)`.

### 🧠 3. El Cerebro (Enrutamiento IA) -> Asignado a: Hugo Enriquez Jimenez
**Objetivo:** Decidir qué modelo usar en cada momento y conectarse a Ollama.
* **Stack:** Python + `httpx`.
* **Archivos:** `app/core/router.py` y `app/core/config.py`
* **Tareas:**
  * Guardar variables de entorno o URLs base en `config.py`.
  * Implementar la lógica de enrutamiento en `router.py` (Criterio de Complejidad y Criterio FinOps).
  * Usar `httpx.AsyncClient()` para conectarse de forma asíncrona a los contenedores locales.

### 📈 4. El Narrador (Dashboard FinOps) -> Asignado a: Jose Antonio Ponce Cerón
**Objetivo:** Dar visibilidad a los gastos y justificar el ahorro para la demo.
* **Stack:** Python + Streamlit.
* **Archivo:** `dashboard/app.py`
* **Tareas:**
  * Leer directamente de la base de datos local SQLite.
  * Mostrar gráficos del gasto actual vs. presupuesto.
  * Mostrar métricas del ahorro conseguido gracias al "Cerebro".

---

## 🛠️ Instrucciones de Arranque

1. Clonar este repositorio.
2. Crear un entorno virtual: `python -m venv venv` (Mac/Linux) o `python -m venv venv` (Windows).
3. Activar el entorno: `source venv/bin/activate` (Mac/Linux) o `venv\Scripts\activate` (Windows).
4. Instalar dependencias (cuando existan en el `requirements.txt`).
5. Trabajar en ramas separadas: `git checkout -b feature-[tu-rol]`.

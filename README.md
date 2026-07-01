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

Para avanzar en paralelo y evitar conflictos de código, el trabajo se divide en 4 módulos independientes:

### 🛡️ 1. El Guardián (Core Proxy) -> Asignado a: Juan Manuel Díaz Guardia
**Objetivo:** Crear la puerta de entrada de todas las peticiones (el interceptor).
* **Stack:** Python + FastAPI.
* **Tareas:**
  * Crear `api.py` con un endpoint POST en `/v1/chat/completions`.
  * Extraer el identificador del consumidor desde los headers (ej. `X-Consumer-ID: equipo-marketing`).
  * Llamar a las funciones de base de datos para verificar el presupuesto ANTES de procesar.
  * Llamar al Enrutador (router.py) para obtener la respuesta de la IA.
  * Devolver el JSON final al usuario exactamente con el formato de OpenAI.

### 📊 2. El Contable (Base de Datos) -> Asignado a: Javier Campos Córcoles
**Objetivo:** Persistir presupuestos, consumidores y registrar cada céntimo gastado.
* **Stack:** Python + SQLite.
* **Tareas:**
  * Crear `database.py` que inicialice `finops.db`.
  * Crear tabla `consumers` (id, nombre, presupuesto_maximo, gasto_actual).
  * Crear tabla `logs` (id, consumer_id, modelo_usado, prompt_tokens, completion_tokens, coste_total, timestamp).
  * Programar funciones: `check_budget(consumer_id)`, `update_spend(consumer_id, cost)` y `log_request(...)`.

### 🧠 3. El Cerebro (Enrutamiento IA) -> Asignado a: Hugo Enriquez Jimenez
**Objetivo:** Decidir qué modelo usar en cada momento y conectarse a Ollama.
* **Stack:** Python + `httpx`.
* **Tareas:**
  * Crear `router.py`.
  * Implementar **Criterio 1 (Complejidad):** Si el prompt tiene menos de N caracteres o no requiere razonamiento profundo, enviar a `llama3.2:3b`. Si es complejo, a `mistral:7b`.
  * Implementar **Criterio 2 (FinOps):** Si el usuario ha consumido >90% de su presupuesto, forzar la caída a `llama3.2:3b` sin importar la complejidad del prompt (degradación controlada).
  * Usar httpx.AsyncClient() para enviar el request HTTP a las URLs de Ollama sin bloquear el hilo de FastAPI y devolver el JSON de respuesta al Guardián.

### 📈 4. El Narrador (Dashboard FinOps) -> Asignado a: Jose Antonio Ponce Cerón
**Objetivo:** Dar visibilidad a los gastos y justificar el ahorro para la demo.
* **Stack:** Python + Streamlit.
* **Tareas:**
  * Crear `dashboard.py` que lea directamente de `finops.db`.
  * Mostrar gráficos del gasto actual vs. presupuesto de los 2 consumidores.
  * Mostrar métricas de ahorro: "X peticiones enviadas al modelo barato = $Y ahorrados".
  * Refinar la interfaz gráfica para que luzca profesional ante los jueces.

---

## 🛠️ Instrucciones de Arranque

1. Clonar este repositorio.
2. Crear un entorno virtual: `python -m venv venv` (Mac/Linux) o `python -m venv venv` (Windows).
3. Activar el entorno: `source venv/bin/activate` (Mac/Linux) o `venv\Scripts\activate` (Windows).
4. Instalar dependencias (cuando existan en el `requirements.txt`).
5. Trabajar en ramas separadas: `git checkout -b feature-[tu-rol]`.

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

# --- Configuración de la página ---
st.set_page_config(
    page_title="AI FinOps Proxy - Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Estilos Personalizados (CSS) ---
st.markdown("""
<style>
    /* Tipografía moderna y colores adaptables a tema claro/oscuro */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        background-color: var(--background-color);
        color: var(--text-color);
    }
    
    /* Tarjetas de métricas con Glassmorphism adaptable */
    .metric-card {
        background: var(--secondary-background-color);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 16px;
        padding: 24px;
        text-align: center;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
        transition: transform 0.3s ease;
        margin-bottom: 2rem;
    }
    
    .metric-card:hover {
        transform: translateY(-5px);
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(90deg, #0ea5e9, #6366f1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 8px;
    }
    
    .metric-label {
        font-size: 1rem;
        color: var(--text-color);
        opacity: 0.7;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .savings-value {
        background: linear-gradient(90deg, #10b981, #059669);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .header-title {
        font-size: 3.5rem;
        font-weight: 800;
        text-align: center;
        background: linear-gradient(90deg, #0ea5e9, #6366f1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
        padding-top: 1rem;
    }
    
    .header-subtitle {
        text-align: center;
        color: var(--text-color);
        opacity: 0.7;
        font-size: 1.2rem;
        margin-bottom: 3rem;
    }
    
    /* Centrar contenedor de pestañas */
    div[data-baseweb="tab-list"] {
        justify-content: center !important;
        gap: 10px !important;
    }

    /* Estilos Premium para las Pestañas (Tabs) */
    button[data-baseweb="tab"] {
        background-color: var(--secondary-background-color) !important;
        border: 1px solid rgba(128, 128, 128, 0.2) !important;
        border-radius: 8px !important;
        color: var(--text-color) !important;
        padding: 10px 20px !important;
        margin-right: 0 !important;
        transition: all 0.3s ease !important;
    }
    
    button[data-baseweb="tab"]:hover {
        background-color: var(--secondary-background-color) !important;
        opacity: 0.8 !important;
        color: var(--text-color) !important;
    }
    
    /* Mostrar título en el nav superior (Header) adaptable */
    header[data-testid="stHeader"] {
        background-color: black !important;
        background-image: none !important;
        border-bottom: 1px solid rgba(128, 128, 128, 0.2) !important;
    }
    header[data-testid="stHeader"] * {
        color: white !important;
    }
    header[data-testid="stHeader"]::before {
        content: "AI FinOps Proxy";
        color: white;
        font-weight: 700;
        font-size: 1.25rem;
        padding-left: 1.5rem;
        white-space: nowrap;
        display: flex;
        align-items: center;
    }
    
    button[data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(90deg, #0ea5e9, #6366f1) !important;
        border: none !important;
        color: white !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 15px rgba(14, 165, 233, 0.3) !important;
    }
    
    div[data-baseweb="tab-highlight"] {
        display: none !important; /* Ocultar la barra azul por defecto debajo de la pestaña activa */
    }
</style>
""", unsafe_allow_html=True)

# --- Conexión a la Base de Datos ---
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "finops.db")

def get_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        return conn
    except Exception as e:
        st.error(f"Error conectando a la base de datos: {e}")
        return None

# --- Obtención de Datos ---
conn = get_connection()
if conn:
    # Verificamos si las tablas reales existen (por si el backend aún no ha sido ejecutado)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='consumers'")
    if not cursor.fetchone():
        st.warning("⚠️ La base de datos aún no ha sido inicializada por el backend. Ejecuta el proxy primero.")
        st.stop()
        
    df_consumers = pd.read_sql_query("SELECT id, name as nombre, budget_limit as presupuesto_maximo, current_spend as gasto_actual FROM consumers", conn)
    
    # Adaptar los nombres de las columnas de logs del proxy a los esperados por el dashboard
    df_logs = pd.read_sql_query("""
        SELECT 
            id, 
            consumer_name as consumer_id, 
            IFNULL(requested_model, provider_model) as modelo_solicitado, 
            provider_model as modelo_usado, 
            prompt_tokens, 
            completion_tokens, 
            total_cost as coste_total, 
            IFNULL(applied_rule, 'Ninguna') as regla_aplicada,
            IFNULL(savings, 0.0) as ahorro_generado,
            IFNULL(latency_ms, 0.0) as latency_ms,
            timestamp
        FROM logs
    """, conn)
    
    # Obtener alertas
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alerts'")
    if cursor.fetchone():
        df_alerts = pd.read_sql_query("SELECT id, consumer_name, message, timestamp FROM alerts ORDER BY timestamp DESC", conn)
    else:
        df_alerts = pd.DataFrame(columns=["id", "consumer_name", "message", "timestamp"])
        
    if not df_alerts.empty:
        df_alerts['timestamp'] = pd.to_datetime(df_alerts['timestamp']) + pd.Timedelta(hours=2)
        
    conn.close()
    
    # Convertir timestamp a datetime para gráficas temporales
    if not df_logs.empty:
        df_logs['timestamp'] = pd.to_datetime(df_logs['timestamp']) + pd.Timedelta(hours=2)
        # Normalizar nombres de columnas para compatibilidad entre mock y DB real
        # Model usado
        model_cols = ['modelo_usado', 'provider_model', 'model_used']
        for c in model_cols:
            if c in df_logs.columns:
                df_logs['model_used'] = df_logs[c]
                break
        if 'model_used' not in df_logs.columns:
            df_logs['model_used'] = 'unknown'

        # Coste total
        cost_cols = ['coste_total', 'total_cost', 'coste']
        for c in cost_cols:
            if c in df_logs.columns:
                df_logs['coste_total'] = df_logs[c]
                break
        if 'coste_total' not in df_logs.columns:
            df_logs['coste_total'] = 0.0

        # Regla aplicada
        regla_cols = ['regla_aplicada']
        for c in regla_cols:
            if c in df_logs.columns:
                df_logs['regla_aplicada'] = df_logs[c]
                break
        if 'regla_aplicada' not in df_logs.columns:
            df_logs['regla_aplicada'] = 'Ninguna'

        # Ahorro generado
        ahorro_cols = ['ahorro_generado']
        for c in ahorro_cols:
            if c in df_logs.columns:
                df_logs['ahorro_generado'] = df_logs[c]
                break
        if 'ahorro_generado' not in df_logs.columns:
            df_logs['ahorro_generado'] = 0.0

        # Porcentaje de ahorro: se calcula solo con lo almacenado en BD.
        # savings = coste de referencia - coste real  =>  referencia = coste_real + savings
        # savings_pct = savings / referencia * 100
        df_logs['coste_referencia'] = df_logs['coste_total'] + df_logs['ahorro_generado']
        df_logs['savings_pct'] = df_logs.apply(
            lambda r: max(0.0, min(100.0, (r['ahorro_generado'] / r['coste_referencia'] * 100.0))) if r['coste_referencia'] and r['coste_referencia'] > 0 else 0.0,
            axis=1,
        )
else:
    st.stop()

# --- Cálculos Globales ---
gasto_total = df_consumers["gasto_actual"].sum()
presupuesto_total = df_consumers["presupuesto_maximo"].sum()
ahorro_total = df_logs["ahorro_generado"].sum() if 'ahorro_generado' in df_logs.columns else 0.0
ahorro_pct_medio = df_logs["savings_pct"].mean() if 'savings_pct' in df_logs.columns and not df_logs.empty else 0.0
peticiones_optimizadas = len(df_logs[df_logs["regla_aplicada"] != "Ninguna"]) if 'regla_aplicada' in df_logs.columns else 0

# --- Layout del Dashboard ---
st.markdown("<p class='header-subtitle' style='margin-top: -1rem; margin-bottom: 2rem; font-size: 1.6rem; font-weight: 500;'>Control de Gastos, Optimización y Gobernanza de IA Generativa</p>", unsafe_allow_html=True)

# 1. Tarjetas de Métricas Superiores
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f'''
        <div class="metric-card">
            <div class="metric-value">${gasto_total:.2f}</div>
            <div class="metric-label">Gasto Total Acumulado</div>
        </div>
    ''', unsafe_allow_html=True)

with col2:
    st.markdown(f'''
        <div class="metric-card">
            <div class="metric-value">${presupuesto_total:.2f}</div>
            <div class="metric-label">Presupuesto Global</div>
        </div>
    ''', unsafe_allow_html=True)

with col3:
    st.markdown(f'''
        <div class="metric-card">
            <div class="metric-value savings-value">${ahorro_total:.4f}</div>
            <div class="metric-label">Ahorro Generado ({peticiones_optimizadas} peticiones)</div>
        </div>
    ''', unsafe_allow_html=True)

st.write("---")

# TABS PRINCIPALES
tab1, tab2, tab3, tab4 = st.tabs(["VISIÓN GENERAL", "PREDICCIONES DE GASTO", "AUDITORÍA E IMPACTO", "ALERTAS FINOPS"])

with tab1:
    st.subheader("Control de Presupuesto por Equipo")
    cols = st.columns(len(df_consumers) if not df_consumers.empty else 1)
    
    for idx, row in df_consumers.iterrows():
        with cols[idx]:
            porcentaje = (row["gasto_actual"] / row["presupuesto_maximo"]) * 100 if row["presupuesto_maximo"] > 0 else 0
            color = "#10b981" if porcentaje < 75 else "#f59e0b" if porcentaje < 90 else "#ef4444"
            
            fig = go.Figure(go.Indicator(
                mode = "gauge+number+delta",
                value = row["gasto_actual"],
                title = {'text': f"<b>{row['nombre']}</b><br><span style='color: gray; font-size:0.8em'>ID: {row['id']}</span>"},
                delta = {'reference': row["presupuesto_maximo"], 'increasing': {'color': "#ef4444"}, 'decreasing': {'color': "#10b981"}},
                gauge = {
                    'axis': {'range': [None, row["presupuesto_maximo"]], 'tickwidth': 1, 'tickcolor': "gray"},
                    'bar': {'color': color},
                    'bgcolor': "rgba(0,0,0,0)",
                    'borderwidth': 0,
                    'steps': [
                        {'range': [0, row["presupuesto_maximo"]*0.75], 'color': "rgba(16, 185, 129, 0.2)"},
                        {'range': [row["presupuesto_maximo"]*0.75, row["presupuesto_maximo"]*0.9], 'color': "rgba(245, 158, 11, 0.2)"},
                        {'range': [row["presupuesto_maximo"]*0.9, row["presupuesto_maximo"]], 'color': "rgba(239, 68, 68, 0.2)"}],
                }
            ))
            
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=20, r=20, t=90, b=20), height=300)
            st.plotly_chart(fig, use_container_width=True)
            
    st.write("---")
    st.subheader("Análisis de peticiones")
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        if not df_logs.empty:
            df_modelo = df_logs.groupby("modelo_usado").size().reset_index(name="peticiones")
            fig_pie = px.pie(df_modelo, values='peticiones', names='modelo_usado', title='Peticiones por Modelo Usado',
                             color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No hay datos de logs registrados aún.")
            
    with col_chart2:
        if not df_logs.empty:
            df_costes = df_logs[~df_logs["modelo_usado"].str.contains("Caché|Cache", case=False, na=False)].groupby("modelo_usado")["coste_total"].sum().reset_index()
            fig_bar = px.bar(df_costes, x='modelo_usado', y='coste_total', title='Coste Total por Modelo ($)',
                             color='modelo_usado', text_auto='.4f')
            fig_bar.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                  xaxis_title="Modelo", yaxis_title="Coste ($)")
            st.plotly_chart(fig_bar, use_container_width=True)

with tab2:
    st.subheader("Predicción de Gasto a 3 Días")
    st.markdown("Proyección del gasto basada en el uso histórico de los últimos 7 días mediante regresión lineal.")
    
    if not df_logs.empty:
        # Agrupar costes por fecha (día) y acumulado
        df_logs['fecha'] = df_logs['timestamp'].dt.date
        df_daily_cost = df_logs.groupby('fecha')['coste_total'].sum().reset_index()
        df_daily_cost = df_daily_cost.sort_values('fecha')
        df_daily_cost['coste_acumulado'] = df_daily_cost['coste_total'].cumsum()
        
        # Predicción simple lineal (numpy)
        import numpy as np
        import datetime
        
        # Convertir fechas a ordinales para la regresión
        df_daily_cost['day_ordinal'] = pd.to_datetime(df_daily_cost['fecha']).apply(lambda x: x.toordinal())
        
        if len(df_daily_cost) > 1:
            x = df_daily_cost['day_ordinal'].values
            y_daily = df_daily_cost['coste_total'].values
            
            # Ajuste de regresión lineal (grado 1) sobre el coste DIARIO
            coeffs = np.polyfit(x, y_daily, 1)
            poly_eqn = np.poly1d(coeffs)
            
            # Generar datos futuros (próximos 3 días)
            last_date = df_daily_cost['fecha'].iloc[-1]
            future_dates = [last_date + datetime.timedelta(days=i) for i in range(1, 4)]
            future_ordinals = [pd.to_datetime(d).toordinal() for d in future_dates]
            
            # Predecir costes diarios futuros (asegurando que no sean negativos)
            future_daily_costs = np.maximum(0, poly_eqn(future_ordinals))
            
            # Calcular el coste acumulado futuro partiendo del último punto real
            last_acumulado = df_daily_cost['coste_acumulado'].iloc[-1]
            future_costs = last_acumulado + np.cumsum(future_daily_costs)
            
            # Construir DataFrame combinado para la gráfica
            df_hist = df_daily_cost[['fecha', 'coste_acumulado']].copy()
            df_hist['tipo'] = 'Histórico'
            
            df_futuro = pd.DataFrame({
                'fecha': future_dates,
                'coste_acumulado': future_costs,
                'tipo': 'Predicción'
            })
            
            # Conectar la línea de predicción con el último punto real
            df_futuro.loc[-1] = [last_date, df_hist['coste_acumulado'].iloc[-1], 'Predicción']
            df_futuro.index = df_futuro.index + 1
            df_futuro = df_futuro.sort_index()
            
            df_trend = pd.concat([df_hist, df_futuro], ignore_index=True)
            
            fig_trend = px.line(df_trend, x='fecha', y='coste_acumulado', color='tipo', 
                                title="Tendencia de Gasto y Predicción",
                                color_discrete_map={"Histórico": "#38bdf8", "Predicción": "#f59e0b"})
                                
            # Añadir línea de presupuesto total
            fig_trend.add_hline(y=presupuesto_total, line_dash="dash", line_color="#ef4444", annotation_text="Presupuesto Global")
            
            fig_trend.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                  xaxis_title="Fecha", yaxis_title="Coste Acumulado ($)")
            
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.warning("No hay suficientes días de datos para calcular una tendencia.")
    else:
        st.info("No hay datos para mostrar.")
        
with tab3:
    st.subheader("Impacto de Reglas de Optimización")
    ahorro_col1, ahorro_col2 = st.columns(2)
    with ahorro_col1:
        st.markdown(
            f'''
            <div class="metric-card">
                <div class="metric-value savings-value">{ahorro_pct_medio:.2f}%</div>
                <div class="metric-label">Porcentaje medio de ahorro</div>
            </div>
            ''',
            unsafe_allow_html=True,
        )
    with ahorro_col2:
        st.markdown(
            f'''
            <div class="metric-card">
                <div class="metric-value">${ahorro_total:.4f}</div>
                <div class="metric-label">Ahorro total acumulado</div>
            </div>
            ''',
            unsafe_allow_html=True,
        )

    if not df_logs.empty and 'regla_aplicada' in df_logs.columns:
        df_rules = df_logs[~df_logs['regla_aplicada'].isin(['Ninguna', 'Elección Inicial Óptima', 'Elección Explícita Respetada', 'Enrutamiento Automático (Nivel 2)'])]
        if not df_rules.empty:
            df_rules = df_rules.copy()
            df_rules['coste_referencia'] = df_rules['coste_total'] + df_rules['ahorro_generado']
            df_rules['savings_pct'] = df_rules.apply(
                lambda r: max(0.0, min(100.0, (r['ahorro_generado'] / r['coste_referencia'] * 100.0))) if r['coste_referencia'] and r['coste_referencia'] > 0 else 0.0,
                axis=1,
            )

            st.markdown("### Desglose de ahorro por regla")

            df_ahorro_por_regla = df_rules.groupby('regla_aplicada').agg(
                ahorro_generado=('ahorro_generado', 'sum'),
                coste_referencia=('coste_referencia', 'sum')
            ).reset_index()
            df_ahorro_por_regla['savings_pct'] = df_ahorro_por_regla.apply(
                lambda r: max(0.0, min(100.0, (r['ahorro_generado'] / r['coste_referencia'] * 100.0))) if r['coste_referencia'] and r['coste_referencia'] > 0 else 0.0,
                axis=1,
            )

            fig_rules = px.bar(df_ahorro_por_regla, x='ahorro_generado', y='regla_aplicada', orientation='h',
                               title="Ahorro Generado por Regla de Enrutamiento ($)",
                               color='regla_aplicada', text_auto='.4f')
            fig_rules.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                  xaxis_title="Ahorro ($)", yaxis_title="Regla")
            st.plotly_chart(fig_rules, use_container_width=True)
        else:
            st.info("No se han activado reglas de optimización todavía.")
            
    st.write("---")
    st.subheader("🧾 Últimas Peticiones (Registro de Auditoría)")
    if not df_logs.empty:
        # Formatear la tabla para mostrar mejor
        df_display = df_logs.sort_values(by="timestamp", ascending=False).head(20).drop(columns=['model_used', 'fecha'], errors='ignore')
        
        # Eliminar o renombrar columnas para que sea más claro
        st.dataframe(
            df_display, 
            use_container_width=True,
            column_config={
                "coste_total": st.column_config.NumberColumn("Coste ($)", format="%.5f"),
                "ahorro_generado": st.column_config.NumberColumn("Ahorro ($)", format="%.5f"),
                "coste_referencia": st.column_config.NumberColumn("Coste ref. ($)", format="%.5f"),
                "savings_pct": st.column_config.NumberColumn("Ahorro (%)", format="%.2f%%"),
                "timestamp": st.column_config.DatetimeColumn("Fecha y Hora", format="DD/MM/YYYY HH:mm:ss"),
                "latency_ms": st.column_config.NumberColumn("Latencia (ms)", format="%.2f ms")
            }
        )

with tab4:
    st.subheader("Registro Histórico de Alertas")
    if not df_alerts.empty:
        st.dataframe(
            df_alerts, 
            use_container_width=True, 
            column_config={
                "id": "ID Alerta", 
                "consumer_name": "Equipo Consumidor", 
                "message": "Mensaje de Alerta", 
                "timestamp": st.column_config.DatetimeColumn("Fecha y Hora", format="DD/MM/YYYY HH:mm:ss")
            }
        )
    else:
        st.info("✅ No hay alertas registradas en el sistema.")
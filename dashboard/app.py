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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', system-ui, -apple-system, sans-serif; }
    .stApp { background-color: #0b1120; color: #f8fafc; }
    header { visibility: hidden; display: none; }
    #MainMenu { visibility: hidden; display: none; }
    footer { visibility: hidden; display: none; }
    div.block-container { padding-top: 2rem; padding-bottom: 1rem; max-width: 95%; }
    .metric-card { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 20px; text-align: center; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); margin-bottom: 1rem; }
    .metric-value { font-size: 2.2rem; font-weight: 700; color: #ffffff; margin-bottom: 4px; letter-spacing: -0.02em; }
    .savings-value { color: #10b981; }
    .metric-label { font-size: 0.85rem; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
    .header-container { text-align: center; padding-bottom: 1.5rem; margin-bottom: 2rem; border-bottom: 1px solid #334155; }
    .header-title { font-size: 2.5rem; font-weight: 700; color: #ffffff; margin-bottom: 0.5rem; letter-spacing: -0.02em; }
    .header-subtitle { color: #94a3b8; font-size: 1.1rem; font-weight: 400; }
    .stTabs [data-baseweb="tab-list"] { gap: 2rem; justify-content: center; background-color: #0f172a; padding: 12px; border-radius: 8px; border: 1px solid #334155; margin-bottom: 2rem; }
    .stTabs [data-baseweb="tab"] { color: #94a3b8; font-weight: 600; }
    .stTabs [aria-selected="true"] { color: #ffffff !important; }
    /* Fix de contraste para tablas y desplegables */
    .stDataFrame, .streamlit-expanderHeader { color: #f8fafc !important; }
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
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='consumers'")
    if not cursor.fetchone():
        st.warning("⚠️ La base de datos aún no ha sido inicializada por el backend. Ejecuta el proxy primero.")
        st.stop()
        
    df_consumers = pd.read_sql_query("SELECT id, name as nombre, budget_limit as presupuesto_maximo, current_spend as gasto_actual FROM consumers", conn)
    
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
            timestamp 
        FROM logs
    """, conn)
    
    # Obtener Alertas si la tabla existe
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alerts'")
    if cursor.fetchone():
        df_alerts = pd.read_sql_query("SELECT id, consumer_name, message, timestamp FROM alerts ORDER BY timestamp DESC", conn)
    else:
        df_alerts = pd.DataFrame(columns=["id", "consumer_name", "message", "timestamp"])
        
    conn.close()
    
    if not df_logs.empty:
        df_logs['timestamp'] = pd.to_datetime(df_logs['timestamp'])
        model_cols = ['modelo_usado', 'provider_model', 'model_used']
        for c in model_cols:
            if c in df_logs.columns:
                df_logs['model_used'] = df_logs[c]
                break
        if 'model_used' not in df_logs.columns:
            df_logs['model_used'] = 'unknown'
        cost_cols = ['coste_total', 'total_cost', 'coste']
        for c in cost_cols:
            if c in df_logs.columns:
                df_logs['coste_total'] = df_logs[c]
                break
        if 'coste_total' not in df_logs.columns:
            df_logs['coste_total'] = 0.0
        regla_cols = ['regla_aplicada']
        for c in regla_cols:
            if c in df_logs.columns:
                df_logs['regla_aplicada'] = df_logs[c]
                break
        if 'regla_aplicada' not in df_logs.columns:
            df_logs['regla_aplicada'] = 'Ninguna'
        ahorro_cols = ['ahorro_generado']
        for c in ahorro_cols:
            if c in df_logs.columns:
                df_logs['ahorro_generado'] = df_logs[c]
                break
        if 'ahorro_generado' not in df_logs.columns:
            df_logs['ahorro_generado'] = 0.0
else:
    st.stop()

# --- Cálculos Globales ---
gasto_total = df_consumers["gasto_actual"].sum()
presupuesto_total = df_consumers["presupuesto_maximo"].sum()
ahorro_total = df_logs["ahorro_generado"].sum() if 'ahorro_generado' in df_logs.columns else 0.0
peticiones_optimizadas = len(df_logs[df_logs["regla_aplicada"] != "Ninguna"]) if 'regla_aplicada' in df_logs.columns else 0

# --- Layout del Dashboard ---
st.markdown('''
    <div class="header-container">
        <div class="header-title">AI FinOps Proxy</div>
        <div class="header-subtitle">Control de Gastos, Optimización y Gobernanza de IA Generativa</div>
    </div>
''', unsafe_allow_html=True)



# TABS PRINCIPALES
tab1, tab2, tab3, tab4 = st.tabs(["📊 Visión General", "📈 Predicciones de Gasto", "🧾 Auditoría e Impacto", "🚨 Alertas FinOps"])

with tab1:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'''<div class="metric-card"><div class="metric-value">${gasto_total:.2f}</div><div class="metric-label">Gasto Total Acumulado</div></div>''', unsafe_allow_html=True)
    with col2:
        st.markdown(f'''<div class="metric-card"><div class="metric-value">${presupuesto_total:.2f}</div><div class="metric-label">Presupuesto Global</div></div>''', unsafe_allow_html=True)
    with col3:
        st.markdown(f'''<div class="metric-card"><div class="metric-value savings-value">${ahorro_total:.4f}</div><div class="metric-label">Ahorro Generado ({peticiones_optimizadas} peticiones)</div></div>''', unsafe_allow_html=True)
    
    st.write("---")
    st.subheader("Control de Presupuesto por Equipo")
    cols = st.columns(len(df_consumers) if not df_consumers.empty else 1)
    
    for idx, row in df_consumers.iterrows():
        with cols[idx]:
            porcentaje = (row["gasto_actual"] / row["presupuesto_maximo"]) * 100 if row["presupuesto_maximo"] > 0 else 0
            color = "#10b981" if porcentaje < 75 else "#f59e0b" if porcentaje < 90 else "#ef4444"
            fig = go.Figure(go.Indicator(
                mode = "gauge+number+delta",
                value = row["gasto_actual"],
                title = {'text': f"<b style='font-size: 18px; color: #ffffff;'>{row['nombre']}</b><br><span style='color: #94a3b8; font-size:0.8em'>ID: {row['id']}</span>"},
                delta = {'reference': row["presupuesto_maximo"], 'increasing': {'color': "#ef4444"}, 'decreasing': {'color': "#10b981"}},
                gauge = {
                    'axis': {'range': [None, row["presupuesto_maximo"]], 'tickwidth': 1, 'tickcolor': "#475569"},
                    'bar': {'color': color},
                    'bgcolor': "rgba(0,0,0,0)",
                    'borderwidth': 0,
                    'steps': [
                        {'range': [0, row["presupuesto_maximo"]*0.75], 'color': "rgba(16, 185, 129, 0.1)"},
                        {'range': [row["presupuesto_maximo"]*0.75, row["presupuesto_maximo"]*0.9], 'color': "rgba(245, 158, 11, 0.1)"},
                        {'range': [row["presupuesto_maximo"]*0.9, row["presupuesto_maximo"]], 'color': "rgba(239, 68, 68, 0.1)"}],
                }
            ))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"}, margin=dict(l=20, r=20, t=90, b=20), height=280)
            st.plotly_chart(fig, use_container_width=True)
            
    st.write("---")
    st.subheader("Análisis de Modelos")
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        if not df_logs.empty:
            df_modelos_reales = df_logs[df_logs['modelo_usado'] != 'caché']
            df_modelo = df_modelos_reales.groupby("modelo_usado").size().reset_index(name="peticiones")
            fig_pie = px.pie(df_modelo, values='peticiones', names='modelo_usado', title='Peticiones por Modelo Usado',
                             color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_pie.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#ffffff", family="Inter"), height=320,
                xaxis=dict(showgrid=True, gridcolor='#334155', zerolinecolor='#475569', tickfont=dict(color='#ffffff'), title_font=dict(color='#ffffff')),
                yaxis=dict(showgrid=True, gridcolor='#334155', zerolinecolor='#475569', tickfont=dict(color='#ffffff'), title_font=dict(color='#ffffff'))
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No hay datos de logs registrados aún.")
            
    with col_chart2:
        if not df_logs.empty:
            df_modelos_reales = df_logs[df_logs['modelo_usado'] != 'caché']
            df_costes = df_modelos_reales.groupby("modelo_usado")["coste_total"].sum().reset_index()
            fig_bar = px.bar(df_costes, x='modelo_usado', y='coste_total', title='Coste Total por Modelo ($)',
                             color='modelo_usado', text_auto='.4f')
            fig_bar.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#ffffff", family="Inter"), height=320,
                xaxis_title="Modelo", yaxis_title="Coste ($)",
                xaxis=dict(showgrid=True, gridcolor='#334155', zerolinecolor='#475569', tickfont=dict(color='#ffffff'), title_font=dict(color='#ffffff')),
                yaxis=dict(showgrid=True, gridcolor='#334155', zerolinecolor='#475569', tickfont=dict(color='#ffffff'), title_font=dict(color='#ffffff'))
            )
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
            y = df_daily_cost['coste_acumulado'].values
            
            # Ajuste de regresión lineal (grado 1)
            coeffs = np.polyfit(x, y, 1)
            poly_eqn = np.poly1d(coeffs)
            
            # Generar datos futuros (próximos 3 días)
            last_date = df_daily_cost['fecha'].iloc[-1]
            future_dates = [last_date + datetime.timedelta(days=i) for i in range(1, 4)]
            future_ordinals = [pd.to_datetime(d).toordinal() for d in future_dates]
            future_costs = poly_eqn(future_ordinals)
            
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
            
            fig_trend.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#ffffff", family="Inter"), height=320,
                xaxis_title="Fecha", yaxis_title="Coste Acumulado ($)",
                xaxis=dict(showgrid=True, gridcolor='#334155', zerolinecolor='#475569', tickfont=dict(color='#ffffff'), title_font=dict(color='#ffffff')),
                yaxis=dict(showgrid=True, gridcolor='#334155', zerolinecolor='#475569', tickfont=dict(color='#ffffff'), title_font=dict(color='#ffffff'))
            )
            
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.warning("No hay suficientes días de datos para calcular una tendencia.")
    else:
        st.info("No hay datos para mostrar.")
        
with tab3:
    st.subheader("Impacto de Reglas de Optimización")
    if not df_logs.empty and 'regla_aplicada' in df_logs.columns:
        df_rules = df_logs[df_logs['regla_aplicada'] != 'Ninguna']
        if not df_rules.empty:
            df_ahorro_por_regla = df_rules.groupby('regla_aplicada')['ahorro_generado'].sum().reset_index()
            
            fig_rules = px.bar(df_ahorro_por_regla, x='ahorro_generado', y='regla_aplicada', orientation='h',
                               title="Ahorro Generado por Regla de Enrutamiento ($)",
                               color='regla_aplicada', text_auto='.4f')
            fig_rules.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#ffffff", family="Inter"), height=320,
                xaxis_title="Ahorro ($)", yaxis_title="Regla",
                xaxis=dict(showgrid=True, gridcolor='#334155', zerolinecolor='#475569', tickfont=dict(color='#ffffff'), title_font=dict(color='#ffffff')),
                yaxis=dict(showgrid=True, gridcolor='#334155', zerolinecolor='#475569', tickfont=dict(color='#ffffff'), title_font=dict(color='#ffffff'))
            )
            st.plotly_chart(fig_rules, use_container_width=True)
        else:
            st.info("No se han activado reglas de optimización todavía.")
            
    st.write("---")
    st.subheader("🧾 Últimas Peticiones (Registro de Auditoría)")
    if not df_logs.empty:
        # Formatear la tabla para mostrar mejor
        df_display = df_logs.sort_values(by="timestamp", ascending=False).head(20)
        columnas_a_borrar = ['id', 'model_used', 'fecha']
        df_display = df_display.drop(columns=[c for c in columnas_a_borrar if c in df_display.columns])
        
        # Eliminar o renombrar columnas para que sea más claro
        st.dataframe(
            df_display, 
            use_container_width=True,
            column_config={
                "coste_total": st.column_config.NumberColumn("Coste ($)", format="%.5f"),
                "ahorro_generado": st.column_config.NumberColumn("Ahorro ($)", format="%.5f")
            }
        )

with tab4:
    st.subheader("Registro Histórico de Alertas")
    st.markdown("Todas las notificaciones y bloqueos generados por el sistema de control de presupuesto.")

    if not df_alerts.empty:
        st.write("### 🚨 Últimas Notificaciones")
        for idx, row in df_alerts.head(3).iterrows():
            if "BLOQUEO" in row['message']:
                st.error(f"**{row['timestamp']}**: {row['message']}")
            else:
                st.warning(f"**{row['timestamp']}**: {row['message']}")
        st.write("---")

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
        st.info("✅ No hay alertas registradas en el sistema. Todos los equipos están dentro de su presupuesto.")
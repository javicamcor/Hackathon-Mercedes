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
    /* Tipografía moderna y fondo oscuro premium */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        background-color: #0f172a;
        color: #f8fafc;
    }
    
    /* Tarjetas de métricas con Glassmorphism */
    .metric-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 24px;
        text-align: center;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);
        transition: transform 0.3s ease;
        margin-bottom: 2rem;
    }
    
    .metric-card:hover {
        transform: translateY(-5px);
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(90deg, #38bdf8, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 8px;
    }
    
    .metric-label {
        font-size: 1rem;
        color: #94a3b8;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .savings-value {
        background: linear-gradient(90deg, #34d399, #10b981);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .header-title {
        font-size: 3.5rem;
        font-weight: 800;
        text-align: center;
        background: linear-gradient(90deg, #f8fafc, #94a3b8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
        padding-top: 1rem;
    }
    
    .header-subtitle {
        text-align: center;
        color: #64748b;
        font-size: 1.2rem;
        margin-bottom: 3rem;
    }
</style>
""", unsafe_allow_html=True)

# --- Conexión a la Base de Datos ---
# Buscar la base de datos en el directorio padre si se ejecuta desde dashboard/
if os.path.exists("../finops.db"):
    DB_PATH = "../finops.db"
elif os.path.exists("finops.db"):
    DB_PATH = "finops.db"
else:
    DB_PATH = "../finops.db" # Default a padre por si el proxy lo crea ahí

def get_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        return conn
    except Exception as e:
        st.error(f"Error conectando a la base de datos: {e}")
        return None

def init_mock_db():
    """Inicializa la DB con datos falsos si no existen tablas, para que la UI funcione durante el desarrollo."""
    conn = get_connection()
    if not conn:
        return
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS consumers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            budget_limit REAL,
            current_spend REAL DEFAULT 0.0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            consumer_name TEXT,
            requested_model TEXT,
            provider_model TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_cost REAL,
            applied_rule TEXT,
            savings REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert mock data if empty
    cursor.execute("SELECT COUNT(*) FROM consumers")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO consumers (name, budget_limit, current_spend) VALUES ('equipo-marketing', 10.0, 8.5)")
        cursor.execute("INSERT INTO consumers (name, budget_limit, current_spend) VALUES ('equipo-producto', 5.0, 1.2)")
        
        import datetime
        import random
        
        now = datetime.datetime.now()
        
        # Generar logs de los últimos 7 días para poder visualizar tendencias
        for i in range(50):
            days_ago = random.uniform(0, 7)
            ts = now - datetime.timedelta(days=days_ago)
            
            consumer = random.choice(['equipo-marketing', 'equipo-producto', 'equipo-marketing'])
            modelo_solic = random.choice(['gpt-4', 'mistral:7b', 'llama3.2:3b'])
            
            # Simulamos las reglas de enrutamiento del proxy
            if modelo_solic == 'gpt-4':
                modelo_usado = 'mistral:7b'
                regla = 'Fallback Provider'
                ahorro = random.uniform(0.01, 0.05)
            elif modelo_solic == 'mistral:7b' and random.random() > 0.5:
                modelo_usado = 'llama3.2:3b'
                regla = 'Simple Task'
                ahorro = random.uniform(0.001, 0.01)
            else:
                modelo_usado = modelo_solic
                regla = 'None'
                ahorro = 0.0
                
            p_tokens = random.randint(100, 3000)
            c_tokens = random.randint(50, 1500)
            
            coste = (p_tokens + c_tokens) * 0.000002
            
            cursor.execute('''
                INSERT INTO logs (consumer_name, requested_model, provider_model, prompt_tokens, completion_tokens, total_cost, applied_rule, savings, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (consumer, modelo_solic, modelo_usado, p_tokens, c_tokens, coste, regla, ahorro, ts.strftime('%Y-%m-%d %H:%M:%S')))
            
        conn.commit()
    conn.close()

# Cargar mock DB para demo si está vacío
init_mock_db()

# --- Obtención de Datos ---
conn = get_connection()
if conn:
    df_consumers = pd.read_sql_query("SELECT * FROM consumers", conn)
    df_logs = pd.read_sql_query("SELECT * FROM logs", conn)
    conn.close()
    
    # Convertir timestamp a datetime para gráficas temporales
    if not df_logs.empty:
        df_logs['timestamp'] = pd.to_datetime(df_logs['timestamp'])
else:
    st.stop()

# --- Cálculos Globales ---
gasto_total = df_consumers["current_spend"].sum() if not df_consumers.empty else 0.0
presupuesto_total = df_consumers["budget_limit"].sum() if not df_consumers.empty else 0.0
ahorro_total = df_logs["savings"].sum() if 'savings' in df_logs.columns else 0.0
peticiones_optimizadas = len(df_logs[df_logs["applied_rule"] != "None"]) if 'applied_rule' in df_logs.columns else 0

# --- Layout del Dashboard ---
st.markdown("<h1 class='header-title'>AI FinOps Proxy</h1>", unsafe_allow_html=True)
st.markdown("<p class='header-subtitle'>Control de Gastos, Optimización y Gobernanza de IA Generativa</p>", unsafe_allow_html=True)

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
tab1, tab2, tab3 = st.tabs(["📊 Visión General", "📈 Predicciones de Gasto", "🧾 Auditoría e Impacto"])

with tab1:
    st.subheader("Control de Presupuesto por Equipo")
    cols = st.columns(len(df_consumers) if not df_consumers.empty else 1)
    
    for idx, row in df_consumers.iterrows():
        with cols[idx]:
            porcentaje = (row["current_spend"] / row["budget_limit"]) * 100 if row["budget_limit"] > 0 else 0
            color = "#10b981" if porcentaje < 75 else "#f59e0b" if porcentaje < 90 else "#ef4444"
            
            fig = go.Figure(go.Indicator(
                mode = "gauge+number+delta",
                value = row["current_spend"],
                title = {'text': f"<b>{row['name']}</b>"},
                delta = {'reference': row["budget_limit"], 'increasing': {'color': "#ef4444"}, 'decreasing': {'color': "#10b981"}},
                gauge = {
                    'axis': {'range': [None, row["budget_limit"]], 'tickwidth': 1, 'tickcolor': "#475569"},
                    'bar': {'color': color},
                    'bgcolor': "rgba(0,0,0,0)",
                    'borderwidth': 0,
                    'steps': [
                        {'range': [0, row["budget_limit"]*0.75], 'color': "rgba(16, 185, 129, 0.1)"},
                        {'range': [row["budget_limit"]*0.75, row["budget_limit"]*0.9], 'color': "rgba(245, 158, 11, 0.1)"},
                        {'range': [row["budget_limit"]*0.9, row["budget_limit"]], 'color': "rgba(239, 68, 68, 0.1)"}],
                }
            ))
            
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"}, margin=dict(l=20, r=20, t=50, b=20), height=300)
            st.plotly_chart(fig, use_container_width=True)
            
    st.write("---")
    st.subheader("Análisis de Modelos")
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        if not df_logs.empty:
            df_modelo = df_logs.groupby("provider_model").size().reset_index(name="peticiones")
            fig_pie = px.pie(df_modelo, values='peticiones', names='provider_model', title='Peticiones por Modelo Usado',
                             color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No hay datos de logs registrados aún.")
            
    with col_chart2:
        if not df_logs.empty:
            df_costes = df_logs.groupby("provider_model")["total_cost"].sum().reset_index()
            fig_bar = px.bar(df_costes, x='provider_model', y='total_cost', title='Coste Total por Modelo ($)',
                             color='provider_model', text_auto='.4f')
            fig_bar.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={'color': "white"},
                                  xaxis_title="Modelo", yaxis_title="Coste ($)")
            st.plotly_chart(fig_bar, use_container_width=True)

with tab2:
    st.subheader("Predicción de Gasto a 3 Días")
    st.markdown("Proyección del gasto basada en el uso histórico de los últimos 7 días mediante regresión lineal.")
    
    if not df_logs.empty:
        df_logs['fecha'] = df_logs['timestamp'].dt.date
        df_daily_cost = df_logs.groupby('fecha')['total_cost'].sum().reset_index()
        df_daily_cost = df_daily_cost.sort_values('fecha')
        df_daily_cost['coste_acumulado'] = df_daily_cost['total_cost'].cumsum()
        
        import numpy as np
        import datetime
        
        df_daily_cost['day_ordinal'] = pd.to_datetime(df_daily_cost['fecha']).apply(lambda x: x.toordinal())
        
        if len(df_daily_cost) > 1:
            x = df_daily_cost['day_ordinal'].values
            y = df_daily_cost['coste_acumulado'].values
            
            coeffs = np.polyfit(x, y, 1)
            poly_eqn = np.poly1d(coeffs)
            
            last_date = df_daily_cost['fecha'].iloc[-1]
            future_dates = [last_date + datetime.timedelta(days=i) for i in range(1, 4)]
            future_ordinals = [pd.to_datetime(d).toordinal() for d in future_dates]
            future_costs = poly_eqn(future_ordinals)
            
            df_hist = df_daily_cost[['fecha', 'coste_acumulado']].copy()
            df_hist['tipo'] = 'Histórico'
            
            df_futuro = pd.DataFrame({
                'fecha': future_dates,
                'coste_acumulado': future_costs,
                'tipo': 'Predicción'
            })
            
            df_futuro.loc[-1] = [last_date, df_hist['coste_acumulado'].iloc[-1], 'Predicción']
            df_futuro.index = df_futuro.index + 1
            df_futuro = df_futuro.sort_index()
            
            df_trend = pd.concat([df_hist, df_futuro], ignore_index=True)
            
            fig_trend = px.line(df_trend, x='fecha', y='coste_acumulado', color='tipo', 
                                title="Tendencia de Gasto y Predicción",
                                color_discrete_map={"Histórico": "#38bdf8", "Predicción": "#f59e0b"})
                                
            fig_trend.add_hline(y=presupuesto_total, line_dash="dash", line_color="#ef4444", annotation_text="Presupuesto Global")
            
            fig_trend.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={'color': "white"},
                                  xaxis_title="Fecha", yaxis_title="Coste Acumulado ($)")
            
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.warning("No hay suficientes días de datos para calcular una tendencia.")
    else:
        st.info("No hay datos para mostrar.")
        
with tab3:
    st.subheader("Impacto de Reglas de Optimización")
    if not df_logs.empty and 'applied_rule' in df_logs.columns:
        df_rules = df_logs[df_logs['applied_rule'] != 'None']
        if not df_rules.empty:
            df_ahorro_por_regla = df_rules.groupby('applied_rule')['savings'].sum().reset_index()
            
            fig_rules = px.bar(df_ahorro_por_regla, x='savings', y='applied_rule', orientation='h',
                               title="Ahorro Generado por Regla de Enrutamiento ($)",
                               color='applied_rule', text_auto='.4f')
            fig_rules.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={'color': "white"},
                                  xaxis_title="Ahorro ($)", yaxis_title="Regla")
            st.plotly_chart(fig_rules, use_container_width=True)
        else:
            st.info("No se han activado reglas de optimización todavía.")
            
    st.write("---")
    st.subheader("🧾 Últimas Peticiones (Registro de Auditoría)")
    if not df_logs.empty:
        df_display = df_logs.sort_values(by="timestamp", ascending=False).head(20)
        
        st.dataframe(
            df_display, 
            use_container_width=True,
            column_config={
                "total_cost": st.column_config.NumberColumn("Coste ($)", format="%.5f"),
                "savings": st.column_config.NumberColumn("Ahorro ($)", format="%.5f")
            }
        )
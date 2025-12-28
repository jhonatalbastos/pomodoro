import streamlit as st
import pandas as pd
import time
import sqlite3
import requests
from datetime import datetime, timedelta
from groq import Groq
import streamlit.components.v1 as components

# --- CONFIGURAÇÕES DA PÁGINA ---
st.set_page_config(page_title="AI Pomodoro Expert", layout="wide", page_icon="🍅")

# Inicialização Groq
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception as e:
    st.error("Erro: Verifique a GROQ_API_KEY nos Secrets do Streamlit.")

# --- BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('pomodoro_v4.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  data TEXT, planejado TEXT, realizado TEXT, 
                  interrupcoes TEXT, duracao INTEGER, categoria TEXT)''')
    conn.commit()
    conn.close()

def get_history_tasks():
    conn = sqlite3.connect('pomodoro_v4.db')
    df = pd.read_sql_query("SELECT DISTINCT planejado FROM logs ORDER BY id DESC LIMIT 20", conn)
    conn.close()
    return df['planejado'].tolist()

init_db()

# --- NOTIFICAÇÃO ---
def notify_browser(title, message):
    js_code = f"""<script>
    if (Notification.permission === "granted") {{
        new Notification("{title}", {{ body: "{message}" }});
        new Audio('https://actions.google.com/sounds/v1/alarms/beep_short.ogg').play();
    }}
    </script>"""
    components.html(js_code, height=0)

# --- ESTADO ---
if 'end_time' not in st.session_state: st.session_state.end_time = None
if 'timer_active' not in st.session_state: st.session_state.timer_active = False

# --- UI ---
st.title("🍅 AI Pomodoro Analyzer")
components.html("<script>if(Notification.permission!=='granted') Notification.requestPermission();</script>", height=0)

col1, col2 = st.columns([1.2, 1])

with col1:
    st.subheader("🚀 Foco do Momento")
    
    # Busca tarefas já realizadas para facilitar a seleção (estilo histórico)
    tarefas_frequentes = ["--- Nova Tarefa ---"] + get_history_tasks()
    tarefa_selecionada = st.selectbox("Escolha uma tarefa recente ou digite abaixo:", tarefas_frequentes)
    
    if tarefa_selecionada == "--- Nova Tarefa ---":
        tarefa_nome = st.text_input("Nome da nova tarefa:", placeholder="Ex: Analisar balanço")
    else:
        tarefa_nome = tarefa_selecionada

    categoria = st.selectbox("Categoria:", ["Trabalho", "Estudo", "Pessoal", "Saúde"])
    tempo_foco = st.select_slider("Duração:", options=[1, 5, 10, 25, 45, 60], value=25)
    
    c1, c2 = st.columns(2)
    if c1.button("▶️ Iniciar", use_container_width=True, disabled=st.session_state.timer_active):
        if tarefa_nome:
            st.session_state.end_time = datetime.now() + timedelta(minutes=tempo_foco)
            st.session_state.timer_active = True
            st.rerun()
        else:
            st.warning("Dê um nome à tarefa!")

    if c2.button("⏹️ Resetar", use_container_width=True):
        st.session_state.timer_active = False
        st.session_state.end_time = None
        st.rerun()

    if st.session_state.timer_active and st.session_state.end_time:
        rest = st.session_state.end_time - datetime.now()
        if rest.total_seconds() > 0:
            m, s = divmod(int(rest.total_seconds()), 60)
            st.metric("Tempo Restante", f"{m:02d}:{s:02d}")
            time.sleep(1)
            st.rerun()
        else:
            st.session_state.timer_active = False
            notify_browser("Fim!", tarefa_nome)
            st.balloons()

    st.divider()
    with st.form("registro_ia"):
        realizado = st.text_area("Notas do que foi feito:")
        interrup = st.text_input("Interrupções?")
        if st.form_submit_button("✅ Salvar e Sincronizar"):
            conn = sqlite3.connect('pomodoro_v4.db')
            conn.execute("INSERT INTO logs (data, planejado, realizado, interrupcoes, duracao, categoria) VALUES (?,?,?,?,?,?)",
                         (datetime.now().strftime("%Y-%m-%d %H:%M"), tarefa_nome, realizado, interrup, tempo_foco, categoria))
            conn.commit()
            conn.close()
            
            webhook_url = st.secrets.get("POWER_AUTOMATE_URL") # Recomendado guardar nos secrets
            if webhook_url:
                requests.post(webhook_url, json={"tarefa": tarefa_nome, "notas": realizado, "interrupcoes": interrup, "minutos": int(tempo_foco)})
            st.success("Sincronizado!")

with col2:
    st.subheader("🤖 IA Mentor")
    # ... (mesma lógica de Chat e Stats anterior)
    st.info("A IA analisa seu histórico local para sugerir melhorias mesmo sem listar o MS To Do diretamente.")

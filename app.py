import streamlit as st
import pandas as pd
import time
import sqlite3
import requests
from datetime import datetime, timedelta
from groq import Groq
import streamlit.components.v1 as components

# --- CONFIGURAÇÕES DO STREAMLIT ---
st.set_page_config(page_title="AI Pomodoro + MS To Do", layout="wide", page_icon="🍅")

# Inicialização do Cliente Groq via Secrets
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception as e:
    st.error("Erro ao configurar API do Groq. Verifique as 'Secrets' no Streamlit Cloud.")

# --- BANCO DE DADOS LOCAL (Persistência Complementar) ---
def init_db():
    conn = sqlite3.connect('pomodoro_analytics.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  data TEXT, planejado TEXT, realizado TEXT, 
                  interrupcoes TEXT, duracao INTEGER)''')
    conn.commit()
    conn.close()

init_db()

# --- FUNÇÃO DE NOTIFICAÇÃO DO BROWSER ---
def notify_browser(title, message):
    js_code = f"""
    <script>
    if (Notification.permission === "granted") {{
        new Notification("{title}", {{ body: "{message}", icon: "https://cdn-icons-png.flaticon.com/512/2596/2596542.png" }});
        var audio = new Audio('https://actions.google.com/sounds/v1/alarms/beep_short.ogg');
        audio.play();
    }}
    </script>
    """
    components.html(js_code, height=0)

# --- ESTADO DA SESSÃO ---
if 'end_time' not in st.session_state: st.session_state.end_time = None
if 'timer_active' not in st.session_state: st.session_state.timer_active = False
if 'last_task' not in st.session_state: st.session_state.last_task = ""

# --- INTERFACE PRINCIPAL ---
st.title("🍅 AI Pomodoro & MS To Do Sync")

# Solicitar permissão de notificação
components.html("<script>if(Notification.permission!=='granted') Notification.requestPermission();</script>", height=0)

col1, col2 = st.columns([1, 1])

with col1:
    st.header("⏱️ Timer de Foco")
    
    # Configuração do Webhook (Pode ser colocado nas Secrets também)
    webhook_url = st.text_input("Webhook URL do Make.com:", type="password", help="Cole aqui o link gerado no Passo 1 do tutorial.")
    
    tarefa_atual = st.text_input("Tarefa ativa (Microsoft To Do):", value=st.session_state.last_task, placeholder="Ex: Analisar balanço trimestral")
    st.session_state.last_task = tarefa_atual

    tempo_min = st.select_slider("Tempo da sessão (minutos):", options=[5, 10, 15, 25, 45, 50, 60], value=25)
    
    c1, c2 = st.columns(2)
    if c1.button("🚀 Iniciar Pomodoro", use_container_width=True, disabled=st.session_state.timer_active):
        if tarefa_atual:
            st.session_state.end_time = datetime.now() + timedelta(minutes=tempo_min)
            st.session_state.timer_active = True
            st.rerun()
        else:
            st.warning("⚠️ Informe qual tarefa está a realizar.")

    if c2.button("⏹️ Parar/Resetar", use_container_width=True):
        st.session_state.timer_active = False
        st.session_state.end_time = None
        st.rerun()

    # Lógica do Timer
    if st.session_state.timer_active and st.session_state.end_time:
        restante = st.session_state.end_time - datetime.now()
        if restante.total_seconds() > 0:
            m, s = divmod(int(restante.total_seconds()), 60)
            st.metric("Tempo Restante", f"{m:02d}:{s:02d}")
            time.sleep(1)
            st.rerun()
        else:
            st.session_state.timer_active = False
            notify_browser("Pomodoro Finalizado!", f"Tarefa: {tarefa_atual}")
            st.balloons()
            st.success("✅ Sessão terminada! Descreva o que aconteceu abaixo.")

    st.divider()
    
    # --- REGISTRO DE DADOS ---
    st.subheader("📝 Registro de Atividade")
    with st.form("log_session", clear_on_submit=True):
        detalhes = st.text_area("O que realizou nesta sessão?")
        interrupcoes = st.text_input("Interrupções ou obstáculos?")
        sync_btn = st.form_submit_button("💾 Salvar e Sincronizar com MS To Do")
        
        if sync_btn:
            # 1. Salvar localmente (SQLite)
            conn = sqlite3.connect('pomodoro_analytics.db')
            conn.execute("INSERT INTO logs (data, planejado, realizado, interrupcoes, duracao) VALUES (?,?,?,?,?)",
                         (datetime.now().strftime("%Y-%m-%d %H:%M"), tarefa_atual, detalhes, interrupcoes, tempo_min))
            conn.commit()
            conn.close()
            
            # 2. Enviar para o Make.com (Microsoft To Do)
            if webhook_url:
                payload = {
                    "tarefa": tarefa_atual,
                    "notas": detalhes,
                    "interrupcoes": interrupcoes,
                    "duracao": tempo_min,
                    "timestamp": datetime.now().isoformat()
                }
                try:
                    res = requests.post(webhook_url, json=payload)
                    if res.status_code == 200:
                        st.success("✨ Sincronizado com Microsoft To Do!")
                    else:
                        st.error("Erro na comunicação com o Make.")
                except:
                    st.error("Falha ao conectar ao Webhook.")
            else:
                st.info("Log guardado localmente (Webhook não configurado).")

with col2:
    st.header("🤖 Análise da IA Groq")
    
    tab_chat, tab_report = st.tabs(["💬 Mentor IA", "📊 Relatório de Desempenho"])
    
    with tab_chat:
        user_msg = st.chat_input("Peça dicas ou análises sobre o seu dia...")
        if user_msg:
            with st.spinner("IA a pensar..."):
                conn = sqlite3.connect('pomodoro_analytics.db')
                dados_recentes = pd.read_sql_query("SELECT * FROM logs ORDER BY id DESC LIMIT 5", conn).to_string()
                conn.close()
                
                resp = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": f"És um mentor de produtividade. Histórico recente: {dados_recentes}"},
                        {"role": "user", "content": user_msg}
                    ],
                    model="llama-3.3-70b-versatile"
                )
                st.write(resp.choices[0].message.content)

    with tab_report:
        if st.button("📈 Gerar Relatório Estratégico"):
            conn = sqlite3.connect('pomodoro_analytics.db')
            df_full = pd.read_sql_query("SELECT * FROM logs", conn)
            conn.close()
            
            if not df_full.empty:
                with st.spinner("Analisando padrões..."):
                    prompt = f"Analise estes dados de pomodoro e dê um feedback sobre foco e interrupções: {df_full.to_string()}"
                    relatorio = client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model="llama-3.3-70b-versatile"
                    ).choices[0].message.content
                    st.markdown(relatorio)
                    st.dataframe(df_full)
            else:
                st.warning("Ainda não existem dados para análise.")

st.sidebar.markdown("---")
st.sidebar.caption("v1.0 - Sincronização MS To Do via Make.com")

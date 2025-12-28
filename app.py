import streamlit as st
import pandas as pd
import time
import sqlite3
from datetime import datetime, timedelta
from groq import Groq
import streamlit.components.v1 as components

# --- CONFIGURAÇÕES INICIAIS ---
st.set_page_config(page_title="AI Pomodoro Analyzer", layout="wide", page_icon="🍅")

# Função para disparar notificação do Navegador via JavaScript
def notify_browser(title, message):
    js_code = f"""
    <script>
    function playSound() {{
        var audio = new Audio('https://actions.google.com/sounds/v1/alarms/beep_short.ogg');
        audio.play();
    }}
    if (Notification.permission === "granted") {{
        new Notification("{title}", {{ body: "{message}", icon: "https://cdn-icons-png.flaticon.com/512/2596/2596542.png" }});
        playSound();
    }}
    </script>
    """
    components.html(js_code, height=0)

# Inicialização do Cliente Groq
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception as e:
    st.error("Erro ao configurar API do Groq.")

# --- BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('pomodoro_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  timestamp DATETIME, 
                  atividade TEXT, 
                  interrupcoes TEXT, 
                  duracao INTEGER)''')
    conn.commit()
    conn.close()

def save_log(atividade, interrupcoes, duracao):
    conn = sqlite3.connect('pomodoro_data.db')
    c = conn.cursor()
    c.execute("INSERT INTO logs (timestamp, atividade, interrupcoes, duracao) VALUES (?, ?, ?, ?)",
              (datetime.now(), atividade, interrupcoes, duracao))
    conn.commit()
    conn.close()

init_db()

# --- LÓGICA DE PERSISTÊNCIA DO TIMER ---
# Usamos o st.session_state para que o timer não resete ao trocar de aba
if 'end_time' not in st.session_state:
    st.session_state.end_time = None
if 'timer_active' not in st.session_state:
    st.session_state.timer_active = False
if 'pomodoro_finished' not in st.session_state:
    st.session_state.pomodoro_finished = False

# --- INTERFACE ---
st.title("🍅 AI Pomodoro & Insights")

# Script para manter a conexão e pedir permissão
components.html("""
<script>
if (Notification.permission !== "granted") {
    Notification.requestPermission();
}
</script>
""", height=0)

col1, col2 = st.columns([1, 1])

with col1:
    st.header("Timer")
    tempo_opcao = st.selectbox("Escolha o tempo (minutos):", [25, 50, 10, 5, 1], index=0)
    
    placeholder = st.empty()
    
    col_btn1, col_btn2 = st.columns(2)
    
    # Iniciar Timer
    if col_btn1.button("Iniciar Pomodoro", use_container_width=True):
        st.session_state.end_time = datetime.now() + timedelta(minutes=tempo_opcao)
        st.session_state.timer_active = True
        st.session_state.pomodoro_finished = False

    # Resetar Timer
    if col_btn2.button("Parar/Resetar", use_container_width=True):
        st.session_state.timer_active = False
        st.session_state.end_time = None
        st.session_state.pomodoro_finished = False
        st.rerun()

    # Loop de atualização do Timer
    if st.session_state.timer_active and st.session_state.end_time:
        remaining = st.session_state.end_time - datetime.now()
        
        if remaining.total_seconds() > 0:
            mins, secs = divmod(int(remaining.total_seconds()), 60)
            placeholder.metric("Tempo Restante", f"{mins:02d}:{secs:02d}")
            # Força o refresh da página a cada 10 segundos para manter o app vivo em segundo plano
            time.sleep(1)
            st.rerun()
        else:
            st.session_state.timer_active = False
            st.session_state.pomodoro_finished = True
            notify_browser("Pomodoro Finalizado!", "Hora de registrar suas atividades.")
            st.balloons()

    if st.session_state.pomodoro_finished:
        st.success("✅ Pomodoro Finalizado! Preencha o log abaixo.")

    st.divider()
    st.subheader("Registro da Sessão")
    with st.form("registro_form", clear_on_submit=True):
        desc = st.text_area("O que você fez nesse tempo?")
        interrupt = st.text_input("Houve interrupções? Quem/O quê?")
        submit = st.form_submit_button("Salvar Registro")
        
        if submit:
            if desc:
                save_log(desc, interrupt, tempo_opcao)
                st.session_state.pomodoro_finished = False
                st.success("Registrado com sucesso!")
            else:
                st.warning("Descreva sua atividade.")

with col2:
    st.header("IA Insights & Chat")
    tab1, tab2 = st.tabs(["Conversar com IA", "Gerar Relatórios"])
    
    with tab1:
        user_question = st.text_input("Pergunte algo à IA sobre seu trabalho:")
        if user_question:
            conn = sqlite3.connect('pomodoro_data.db')
            df_context = pd.read_sql_query("SELECT * FROM logs ORDER BY id DESC LIMIT 10", conn)
            conn.close()
            contexto = df_context.to_string()
            
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": f"Você é um mentor de produtividade. Histórico: {contexto}"},
                    {"role": "user", "content": user_question}
                ],
                model="llama-3.3-70b-versatile",
            )
            st.info(response.choices[0].message.content)

    with tab2:
        if st.button("Gerar Relatório Analítico"):
            conn = sqlite3.connect('pomodoro_data.db')
            df_total = pd.read_sql_query("SELECT * FROM logs", conn)
            conn.close()
            
            if not df_total.empty:
                prompt_relatorio = f"Analise estes registros e crie um relatório com padrões e dicas: {df_total.to_string()}"
                report = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt_relatorio}],
                    model="llama-3.3-70b-versatile",
                )
                st.markdown("### 📊 Relatório da IA")
                st.write(report.choices[0].message.content)
            else:
                st.warning("Sem dados suficientes.")

st.sidebar.title("Configurações")
st.sidebar.info("O timer agora usa tempo absoluto do sistema. Se você alternar de aba e voltar, ele calculará quanto tempo passou.")

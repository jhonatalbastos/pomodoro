import streamlit as st
import pandas as pd
import time
import sqlite3
from datetime import datetime
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
    }} else if (Notification.permission !== "denied") {{
        Notification.requestPermission().then(permission => {{
            if (permission === "granted") {{
                new Notification("{title}", {{ body: "{message}" }});
                playSound();
            }}
        }});
    }}
    </script>
    """
    components.html(js_code, height=0)

# Inicialização do Cliente Groq
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception as e:
    st.error("Erro ao configurar API do Groq. Verifique suas Secrets.")

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

# --- INTERFACE ---
st.title("🍅 AI Pomodoro & Insights")

# Solicitar permissão de notificação logo ao abrir o app
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
    tempo_opcao = st.selectbox("Escolha o tempo:", [25, 50, 10, 5], index=0)
    
    if 'timer_running' not in st.session_state:
        st.session_state.timer_running = False
    
    placeholder = st.empty()
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        start_btn = st.button("Iniciar Pomodoro", use_container_width=True)
    with col_btn2:
        stop_btn = st.button("Parar/Resetar", use_container_width=True)

    if stop_btn:
        st.session_state.timer_running = False
        st.rerun()

    if start_btn:
        st.session_state.timer_running = True
        seconds = tempo_opcao * 60
        while seconds > 0 and st.session_state.timer_running:
            mins, secs = divmod(seconds, 60)
            placeholder.metric("Tempo Restante", f"{mins:02d}:{secs:02d}")
            time.sleep(1)
            seconds -= 1
        
        if seconds == 0 and st.session_state.timer_running:
            st.session_state.timer_running = False
            # Chama a função de notificação e som
            notify_browser("Pomodoro Finalizado!", f"Seu tempo de {tempo_opcao} minutos acabou. Hora de registrar suas atividades.")
            st.balloons()
            st.success("Pomodoro Finalizado!")

    st.divider()
    st.subheader("Registro da Sessão")
    with st.form("registro_form", clear_on_submit=True):
        desc = st.text_area("O que você fez nesse tempo?")
        interrupt = st.text_input("Houve interrupções? Quem/O quê?")
        submit = st.form_submit_button("Salvar Registro")
        
        if submit:
            if desc:
                save_log(desc, interrupt, tempo_opcao)
                st.success("Registrado com sucesso!")
            else:
                st.warning("Descreva sua atividade antes de salvar.")

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
                    {"role": "system", "content": f"Você é um mentor de produtividade. Analise os registros do usuário e responda de forma inspiradora. Histórico: {contexto}"},
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
                with st.spinner("IA analisando seus padrões..."):
                    prompt_relatorio = f"Analise estes registros e crie um relatório de produtividade com: 1. Padrões identificados, 2. Principais fontes de interrupção, 3. Dicas personalizadas. Dados: {df_total.to_string()}"
                    report = client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt_relatorio}],
                        model="llama-3.3-70b-versatile",
                    )
                    st.markdown("### 📊 Relatório da IA")
                    st.write(report.choices[0].message.content)
                    st.dataframe(df_total)
            else:
                st.warning("Ainda não há dados suficientes para gerar um relatório.")

# --- SIDEBAR ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2596/2596542.png", width=100)
st.sidebar.title("Configurações")
st.sidebar.write("O app usa o navegador para enviar notificações e tocar alertas.")

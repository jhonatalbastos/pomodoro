import streamlit as st
import pandas as pd
import time
import sqlite3
from datetime import datetime
from groq import Groq

# --- CONFIGURAÇÕES INICIAIS ---
st.set_page_config(page_title="AI Pomodoro Analyzer", layout="wide")

# Inicialização do Cliente Groq
# Certifique-se de adicionar GROQ_API_KEY nos Secrets do Streamlit Cloud
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

# --- INTERFACE E LÓGICA ---
st.title("🍅 AI Pomodoro & Insights")

col1, col2 = st.columns([1, 1])

with col1:
    st.header("Timer")
    tempo_opcao = st.selectbox("Escolha o tempo:", [25, 50, 10, 5], index=0)
    
    if 'timer_running' not in st.session_state:
        st.session_state.timer_running = False
    
    placeholder = st.empty()
    
    if st.button("Iniciar Pomodoro"):
        st.session_state.timer_running = True
        seconds = tempo_opcao * 60
        while seconds > 0 and st.session_state.timer_running:
            mins, secs = divmod(seconds, 60)
            placeholder.metric("Tempo Restante", f"{mins:02d}:{secs:02d}")
            time.sleep(1)
            seconds -= 1
        
        if seconds == 0:
            st.balloons()
            st.success("Pomodoro Finalizado!")
            st.session_state.timer_running = False

    st.divider()
    st.subheader("Registro da Sessão")
    with st.form("registro_form"):
        desc = st.text_area("O que você fez nesse tempo?")
        interrupt = st.text_input("Houve interrupções? Quem/O quê?")
        submit = st.form_submit_button("Salvar Registro")
        
        if submit:
            save_log(desc, interrupt, tempo_opcao)
            st.success("Registrado com sucesso!")

with col2:
    st.header("IA Insights & Chat")
    
    # Aba para Chat e Aba para Relatórios
    tab1, tab2 = st.tabs(["Conversar com IA", "Gerar Relatórios"])
    
    with tab1:
        user_question = st.text_input("Pergunte algo à IA sobre seu trabalho:")
        if user_question:
            # Recuperar histórico para contexto
            conn = sqlite3.connect('pomodoro_data.db')
            df_context = pd.read_sql_query("SELECT * FROM logs ORDER BY id DESC LIMIT 10", conn)
            conn.close()
            
            contexto = df_context.to_string()
            
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": f"Você é um mentor de produtividade. Aqui está o histórico recente do usuário: {contexto}"},
                    {"role": "user", "content": user_question}
                ],
                model="llama-3.3-70b-versatile",
            )
            st.write(response.choices[0].message.content)

    with tab2:
        if st.button("Gerar Relatório de Desempenho"):
            conn = sqlite3.connect('pomodoro_data.db')
            df_total = pd.read_sql_query("SELECT * FROM logs", conn)
            conn.close()
            
            if not df_total.empty:
                prompt_relatorio = f"Analise estes registros de produtividade e dê um feedback detalhado, identifique padrões de interrupção e sugira melhorias: {df_total.to_string()}"
                
                report = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt_relatorio}],
                    model="llama-3.3-70b-versatile",
                )
                st.markdown("### Relatório da IA")
                st.write(report.choices[0].message.content)
                st.dataframe(df_total)
            else:
                st.warning("Ainda não há dados suficientes para gerar um relatório.")

# --- FOOTER ---
st.sidebar.markdown("---")
st.sidebar.info("App criado com Streamlit, Groq e SQLite.")

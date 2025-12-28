import streamlit as st
import pandas as pd
import time
import sqlite3
import requests
from datetime import datetime, timedelta
from groq import Groq
import streamlit.components.v1 as components

# --- CONFIGURAÇÕES ---
st.set_page_config(page_title="AI Pomodoro + MS To Do Simples", layout="wide", page_icon="🍅")

# Inicialização Groq
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    st.error("Erro na API Key do Groq. Adicione nos Secrets.")

# --- DATABASE LOCAL ---
def init_db():
    conn = sqlite3.connect('pomodoro_pro.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  data TEXT, planejado TEXT, realizado TEXT, 
                  interrupcoes TEXT, duracao INTEGER)''')
    conn.commit()
    conn.close()

init_db()

# --- ESTADO DA SESSÃO ---
if 'end_time' not in st.session_state: st.session_state.end_time = None
if 'timer_active' not in st.session_state: st.session_state.timer_active = False

# --- INTERFACE ---
st.title("🍅 AI Pomodoro + Microsoft To Do (via Webhook)")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("🚀 Foco e Automação")
    
    # Configuração do Webhook (Você pega esse link no Make.com)
    webhook_url = st.text_input("Link do Webhook (Make.com/Zapier):", type="password")
    
    tarefa_atual = st.text_input("Qual tarefa do MS To Do você vai realizar?", 
                                placeholder="Ex: Relatório Mensal")
    
    tempo_min = st.slider("Duração:", 5, 60, 25)
    
    btn_start, btn_stop = st.columns(2)
    if btn_start.button("Iniciar", use_container_width=True) and tarefa_atual:
        st.session_state.end_time = datetime.now() + timedelta(minutes=tempo_min)
        st.session_state.timer_active = True
        st.rerun()

    if btn_stop.button("Parar", use_container_width=True):
        st.session_state.timer_active = False
        st.session_state.end_time = None
        st.rerun()

    if st.session_state.timer_active and st.session_state.end_time:
        rem = st.session_state.end_time - datetime.now()
        if rem.total_seconds() > 0:
            m, s = divmod(int(rem.total_seconds()), 60)
            st.metric("Contagem", f"{m:02d}:{s:02d}")
            time.sleep(1)
            st.rerun()
        else:
            st.session_state.timer_active = False
            st.balloons()
            st.success("Pomodoro Finalizado!")

    st.divider()
    with st.form("registro"):
        realizado = st.text_area("Notas da atividade:")
        interrup = st.text_input("Interrupções:")
        enviar_ms = st.form_submit_button("Salvar e Sincronizar com MS To Do")
        
        if enviar_ms:
            # 1. Salva no Banco Local
            conn = sqlite3.connect('pomodoro_pro.db')
            conn.execute("INSERT INTO logs (data, planejado, realizado, interrupcoes, duracao) VALUES (?,?,?,?,?)",
                         (datetime.now().strftime("%d/%m/%Y %H:%M"), tarefa_atual, realizado, interrup, tempo_min))
            conn.commit()
            conn.close()
            
            # 2. Envia para o Make.com (Microsoft To Do)
            if webhook_url:
                dados_webhook = {
                    "tarefa": tarefa_atual,
                    "notas": realizado,
                    "interrupcoes": interrup,
                    "data": datetime.now().isoformat(),
                    "status": "Concluído"
                }
                try:
                    requests.post(webhook_url, json=dados_webhook)
                    st.success("Enviado para o Microsoft To Do via Make!")
                except:
                    st.error("Erro ao enviar para o Webhook.")
            else:
                st.info("Log salvo localmente. (Webhook não configurado)")

with col2:
    st.subheader("🤖 Inteligência Groq")
    
    if st.button("Gerar Relatório de Insights"):
        conn = sqlite3.connect('pomodoro_pro.db')
        df = pd.read_sql_query("SELECT * FROM logs", conn)
        conn.close()
        
        if not df.empty:
            contexto = df.tail(10).to_string()
            prompt = f"Com base nos meus logs do Microsoft To Do, como posso melhorar minha produtividade? Logs: {contexto}"
            resposta = client.chat.completions.create(messages=[{"role":"user", "content":prompt}], model="llama-3.3-70b-versatile")
            st.markdown(f"### 💡 Dica do Mentor:\n{resposta.choices[0].message.content}")
            st.dataframe(df)

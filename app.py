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

# --- BANCO DE DADOS (SQLite) ---
def init_db():
    conn = sqlite3.connect('pomodoro_v4.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  data TEXT, planejado TEXT, realizado TEXT, 
                  interrupcoes TEXT, duracao INTEGER, categoria TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- NOTIFICAÇÃO E SOM ---
def notify_browser(title, message):
    js_code = f"""
    <script>
    if (Notification.permission === "granted") {{
        new Notification("{title}", {{ body: "{message}" }});
        var audio = new Audio('https://actions.google.com/sounds/v1/alarms/beep_short.ogg');
        audio.play();
    }}
    </script>
    """
    components.html(js_code, height=0)

# --- ESTADO DA SESSÃO ---
if 'end_time' not in st.session_state: st.session_state.end_time = None
if 'timer_active' not in st.session_state: st.session_state.timer_active = False

# --- SIDEBAR (Configurações) ---
st.sidebar.title("⚙️ Configurações")
# A URL gerada no Power Automate Web (no bloco HTTP) deve ser colada aqui:
webhook_url = st.sidebar.text_input("URL Power Automate (HTTP POST URL):", type="password")
st.sidebar.info("Ao salvar, a tarefa será enviada para o Microsoft To Do via Power Automate V3.")

# --- INTERFACE PRINCIPAL ---
st.title("🍅 AI Pomodoro Analyzer")
components.html("<script>if(Notification.permission!=='granted') Notification.requestPermission();</script>", height=0)

col1, col2 = st.columns([1.2, 1])

with col1:
    st.subheader("🚀 Sessão Atual")
    
    tarefa_nome = st.text_input("O que você vai focar agora?", placeholder="Ex: Relatório de Vendas")
    categoria = st.selectbox("Categoria:", ["Trabalho", "Estudo", "Pessoal", "Saúde"])
    
    tempo_foco = st.select_slider("Duração (minutos):", options=[1, 5, 10, 25, 45, 50, 60], value=25)
    
    c1, c2 = st.columns(2)
    if c1.button("▶️ Iniciar Foco", use_container_width=True, disabled=st.session_state.timer_active):
        if tarefa_nome:
            st.session_state.end_time = datetime.now() + timedelta(minutes=tempo_foco)
            st.session_state.timer_active = True
            st.rerun()
        else:
            st.warning("⚠️ Dê um nome à tarefa antes de iniciar!")

    if c2.button("⏹️ Resetar", use_container_width=True):
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
            notify_browser("Pomodoro Finalizado!", f"Tarefa: {tarefa_nome}")
            st.balloons()
            st.success("🎉 Sessão Concluída!")

    st.divider()
    
    # --- FORMULÁRIO DE REGISTRO ---
    with st.form("registro_ia", clear_on_submit=True):
        st.write("### 📝 O que aconteceu?")
        notas_realizado = st.text_area("Descreva o que foi feito:")
        interrupcoes = st.text_input("Houve interrupções? Quem/O quê?")
        
        if st.form_submit_button("✅ Salvar e Sincronizar"):
            # Salvar no SQLite Local
            conn = sqlite3.connect('pomodoro_v4.db')
            conn.execute("INSERT INTO logs (data, planejado, realizado, interrupcoes, duracao, categoria) VALUES (?,?,?,?,?,?)",
                         (datetime.now().strftime("%Y-%m-%d %H:%M"), tarefa_nome, notas_realizado, interrupcoes, tempo_foco, categoria))
            conn.commit()
            conn.close()
            
            # Enviar para Power Automate
            if webhook_url:
                payload = {
                    "tarefa": tarefa_nome, 
                    "notas": notas_realizado, 
                    "interrupcoes": interrupcoes, 
                    "minutos": int(tempo_foco)
                }
                try:
                    r = requests.post(webhook_url, json=payload, timeout=10)
                    if r.status_code in [200, 202]:
                        st.success("🚀 Sincronizado com Microsoft To Do!")
                    else:
                        st.error(f"Erro no Power Automate (V3): {r.status_code}")
                except Exception as e:
                    st.error(f"Falha ao sincronizar: {e}")
            else:
                st.info("Log salvo apenas localmente. Configure a URL na barra lateral para sincronizar.")

with col2:
    st.subheader("🤖 IA Mentor & Insights")
    
    tab_chat, tab_stats = st.tabs(["💬 Chat com IA", "📊 Estatísticas"])
    
    with tab_chat:
        # Recuperar últimos logs para contexto da IA
        conn = sqlite3.connect('pomodoro_v4.db')
        df_ctx = pd.read_sql_query("SELECT * FROM logs ORDER BY id DESC LIMIT 5", conn)
        conn.close()
        
        user_input = st.chat_input("Peça dicas ou análises sobre seu desempenho...")
        if user_input:
            contexto = df_ctx.to_string()
            with st.spinner("IA analisando seu progresso..."):
                response = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": f"Você é um mentor de produtividade experiente. Analise o histórico e ajude o usuário. Histórico recente: {contexto}"},
                        {"role": "user", "content": user_input}
                    ],
                    model="llama-3.3-70b-versatile"
                )
                st.info(response.choices[0].message.content)

    with tab_stats:
        conn = sqlite3.connect('pomodoro_v4.db')
        df_stats = pd.read_sql_query("SELECT * FROM logs", conn)
        conn.close()
        
        if not df_stats.empty:
            st.write("Distribuição por Categoria")
            st.bar_chart(df_stats['categoria'].value_counts())
            
            if st.button("📈 Gerar Relatório Profundo"):
                with st.spinner("IA analisando tendências..."):
                    prompt = f"Analise meus padrões de trabalho, categorias e interrupções: {df_stats.to_string()}"
                    relatorio = client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model="llama-3.3-70b-versatile"
                    ).choices[0].message.content
                    st.markdown("### 📊 Relatório Estratégico")
                    st.markdown(relatorio)
        else:
            st.info("Complete sessões para ver suas estatísticas.")

# --- RODAPÉ ---
st.sidebar.markdown("---")
st.sidebar.caption("AI Pomodoro v4.1 (Power Automate V3 Edition)")

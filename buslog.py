import streamlit as st
import json
import pandas as pd
from datetime import datetime, timedelta
from github import Github
import io
import time
import bcrypt
import hashlib

# --- CONFIGURAÇÃO INICIAL (LAYOUT WIDE PARA CABER MAIS COISA) ---
st.set_page_config(page_title="BusBoxd", page_icon="🚌", layout="centered")

# --- CSS PERSONALIZADO (ESTÉTICA LETTERBOXD) ---
st.markdown("""
    <style>
    .big-day {
        font-size: 40px;
        font-weight: bold;
        color: #e0e0e0;
        line-height: 1;
        text-align: center;
    }
    .month-header {
        font-size: 24px;
        font-weight: bold;
        color: #888;
        border-bottom: 1px solid #444;
        margin-top: 20px;
        margin-bottom: 10px;
        padding-bottom: 5px;
    }
    .bus-line {
        font-size: 18px;
        font-weight: bold;
        color: #4CAF50; /* Verde onibus */
    }
    .route-info {
        font-size: 14px;
        color: #aaa;
    }
    </style>
""", unsafe_allow_html=True)

# --- SEGREDOS ---
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"] 
except FileNotFoundError:
    st.error("Configure os Secrets no Streamlit Cloud!")
    st.stop()

ARQUIVO_DB_VIAGENS = "viagens.csv"
ARQUIVO_DB_USUARIOS = "usuarios.json"
ARQUIVO_ROTAS = "rotasrj.json" # Corrigido conforme solicitado

# --- FUNÇÕES DE GITHUB ---
def get_repo():
    g = Github(GITHUB_TOKEN)
    return g.get_repo(REPO_NAME)

def ler_arquivo_github(nome_arquivo, tipo='json'):
    try:
        repo = get_repo()
        contents = repo.get_contents(nome_arquivo)
        decodificado = contents.decoded_content.decode("utf-8")
        if tipo == 'json':
            return json.loads(decodificado)
        else:
            return pd.read_csv(io.StringIO(decodificado))
    except:
        if tipo == 'json': return {}
        else: return pd.DataFrame()

def atualizar_arquivo_github(nome_arquivo, conteudo, mensagem_commit):
    repo = get_repo()
    try:
        contents = repo.get_contents(nome_arquivo)
        repo.update_file(contents.path, mensagem_commit, conteudo, contents.sha)
    except:
        repo.create_file(nome_arquivo, mensagem_commit, conteudo)

# --- FUNÇÕES DE SEGURANÇA ---
def hash_senha(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verificar_senha(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

# --- REGISTRO E LOGIN ---
def registrar_usuario(usuario, senha):
    db_usuarios = ler_arquivo_github(ARQUIVO_DB_USUARIOS, 'json')
    
    if usuario in db_usuarios:
        return False, "Usuário já existe! Escolha outro."
    
    db_usuarios[usuario] = {
        "password": hash_senha(senha),
        "created_at": str(datetime.now())
    }
    
    json_str = json.dumps(db_usuarios, indent=4)
    atualizar_arquivo_github(ARQUIVO_DB_USUARIOS, json_str, f"Novo usuario: {usuario}")
    return True, "Conta criada com sucesso!" # Mensagem alterada

def fazer_login(usuario, senha):
    db_usuarios = ler_arquivo_github(ARQUIVO_DB_USUARIOS, 'json')
    if usuario in db_usuarios:
        stored_pass = db_usuarios[usuario]['password']
        if verificar_senha(senha, stored_pass):
            return True
    return False

# --- CARREGAR ROTAS ---
@st.cache_data
def carregar_rotas():
    try:
        # Tenta ler localmente primeiro (para teste), depois tenta no GitHub se falhar
        try:
            with open(ARQUIVO_ROTAS, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            # Se não achar local, baixa do repo (útil se você não subiu o json pro github ainda)
            return ler_arquivo_github(ARQUIVO_ROTAS, 'json')
    except:
        return {}

rotas_db = carregar_rotas()
lista_linhas = list(rotas_db.keys()) if rotas_db else []

# --- TRADUÇÃO DE MESES ---
MESES_PT = {
    1: "JANEIRO", 2: "FEVEREIRO", 3: "MARÇO", 4: "ABRIL", 5: "MAIO", 6: "JUNHO",
    7: "JULHO", 8: "AGOSTO", 9: "SETEMBRO", 10: "OUTUBRO", 11: "NOVEMBRO", 12: "DEZEMBRO"
}

# --- INTERFACE ---
st.title("🚌 BusBoxd")

if "logado" not in st.session_state:
    st.session_state["logado"] = False
    st.session_state["usuario_atual"] = ""

# --- ÁREA LOGADA ---
if st.session_state["logado"]:
    c_user, c_logout = st.columns([8, 2])
    c_user.write(f"Olá, **{st.session_state['usuario_atual']}**")
    if c_logout.button("Sair"):
        st.session_state["logado"] = False
        st.rerun()
    
    aba1, aba2 = st.tabs(["📝 Nova Viagem", "📓 Diário"])
    
    # --- ABA 1: REGISTRO ---
    with aba1:
        with st.form("nova_viagem"):
            c1, c2 = st.columns(2)
            # format="DD/MM/YYYY" faz aparecer no padrão BR
            data = c1.date_input("Data", datetime.now(), format="DD/MM/YYYY") 
            hora = c2.time_input("Hora", datetime.now())
            
            linha = st.selectbox("Linha", [""] + lista_linhas)
            
            co1, co2 = st.columns(2)
            origem = co1.text_input("Origem")
            destino = co2.text_input("Destino")
            
            obs = st.text_area("Observações")
            
            if st.form_submit_button("Salvar Viagem", use_container_width=True):
                if not linha:
                    st.error("Escolha a linha!")
                else:
                    with st.spinner("Salvando..."):
                        df_antigo = ler_arquivo_github(ARQUIVO_DB_VIAGENS, 'csv')
                        novo_dado = {
                            "usuario": st.session_state['usuario_atual'], 
                            "linha": linha,
                            "data": str(data),
                            "hora": str(hora)[:5], # Pega só HH:MM
                            "origem": origem,
                            "destino": destino,
                            "obs": obs,
                            "timestamp": str(datetime.now())
                        }
                        df_novo = pd.DataFrame([novo_dado])
                        df_final = pd.concat([df_antigo, df_novo], ignore_index=True)
                        atualizar_arquivo_github(ARQUIVO_DB_VIAGENS, df_final.to_csv(index=False), "Nova viagem")
                        st.success("Registrado!")
                        time.sleep(1)
                        st.rerun()

    # --- ABA 2: HISTÓRICO ESTILO LETTERBOXD ---
    with aba2:
        df = ler_arquivo_github(ARQUIVO_DB_VIAGENS, 'csv')
        
        if not df.empty:
            # Filtra apenas viagens do usuário logado
            df = df[df['usuario'] == st.session_state['usuario_atual']]
            
            # Converte coluna data para datetime
            df['data_obj'] = pd.to_datetime(df['data'])
            
            # --- FILTROS ---
            filtro_tempo = st.pills("Filtrar por:", ["Tudo", "7 Dias", "30 Dias", "Este Ano"], default="Tudo")
            
            hoje = datetime.now()
            if filtro_tempo == "7 Dias":
                data_limite = hoje - timedelta(days=7)
                df = df[df['data_obj'] >= data_limite]
            elif filtro_tempo == "30 Dias":
                data_limite = hoje - timedelta(days=30)
                df = df[df['data_obj'] >= data_limite]
            elif filtro_tempo == "Este Ano":
                df = df[df['data_obj'].dt.year == hoje.year]
            
            # Ordena: Mais recente primeiro
            df = df.sort_values(by='data_obj', ascending=False)
            
            # Cria colunas auxiliares para agrupamento
            df['ano'] = df['data_obj'].dt.year
            df['mes'] = df['data_obj'].dt.month
            
            # Agrupa por Ano e Mês (para criar os cabeçalhos)
            grupos = df.groupby(['ano', 'mes'], sort=False)
            
            if df.empty:
                st.info("Nenhuma viagem nesse período.")
            else:
                for (ano, mes), grupo in grupos:
                    nome_mes = MESES_PT[mes]
                    # Cabeçalho do Mês (Ex: DEZEMBRO 2025)
                    st.markdown(f"<div class='month-header'>{nome_mes} {ano}</div>", unsafe_allow_html=True)
                    
                    for _, row in grupo.iterrows():
                        # Layout da linha: [Dia] | [Info da Linha]
                        col_dia, col_info = st.columns([1, 5])
                        
                        with col_dia:
                            # Dia bem grande
                            st.markdown(f"<div class='big-day'>{row['data_obj'].day}</div>", unsafe_allow_html=True)
                        
                        with col_info:
                            # Nome da Linha
                            st.markdown(f"<span class='bus-line'>{row['linha']}</span>", unsafe_allow_html=True)
                            
                            # Origem > Destino e Hora
                            txt_rota = f"{row['origem']} ➝ {row['destino']}" if row['origem'] or row['destino'] else "Rota não informada"
                            st.markdown(f"<div class='route-info'>{txt_rota} • 🕒 {str(row['hora'])[:5]}</div>", unsafe_allow_html=True)
                            
                            # Observação (se tiver)
                            if pd.notna(row['obs']) and row['obs']:
                                st.caption(f"📝 {row['obs']}")
                        
                        st.divider() # Linha separadora fina
        else:
            st.info("Seu diário está vazio. Comece a catalogar!")

# --- TELA DE LOGIN ---
else:
    tab_login, tab_cadastro = st.tabs(["Entrar", "Criar Conta"])
    
    with tab_login:
        l_user = st.text_input("Usuário")
        l_pass = st.text_input("Senha", type="password")
        if st.button("ENTRAR", use_container_width=True):
            with st.spinner("Verificando..."):
                if fazer_login(l_user, l_pass):
                    st.session_state["logado"] = True
                    st.session_state["usuario_atual"] = l_user
                    st.rerun()
                else:
                    st.error("Dados incorretos.")

    with tab_cadastro:
        st.write("### Criar Nova Conta")
        c_user = st.text_input("Escolha um Usuário")
        c_pass = st.text_input("Escolha uma Senha", type="password", key="reg_pass")
        c_pass2 = st.text_input("Confirme a Senha", type="password", key="reg_pass2")
        
        if st.button("CRIAR CONTA", use_container_width=True):
            if c_pass != c_pass2:
                st.error("Senhas não batem!")
            elif len(c_pass) < 4:
                st.error("Senha muito curta!")
            elif not c_user:
                st.error("Digite um usuário!")
            else:
                with st.spinner("Criando..."):
                    sucesso, msg = registrar_usuario(c_user, c_pass)
                    if sucesso:
                        st.success(msg)
                    else:
                        st.error(msg)

import streamlit as st
import json
import pandas as pd
from datetime import datetime
from github import Github
import io
import time
import bcrypt

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="BusBoxd", page_icon="🚌", layout="centered")

# --- SEGREDOS ---
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"] 
except FileNotFoundError:
    st.error("Configure os Secrets no Streamlit Cloud!")
    st.stop()

ARQUIVO_DB_VIAGENS = "viagens.csv"
ARQUIVO_DB_USUARIOS = "usuarios.json"

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
    """Cria o hash seguro da senha"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verificar_senha(password, hashed):
    """Confere se a senha bate"""
    return bcrypt.checkpw(password.encode(), hashed.encode())

# --- FUNÇÕES DE REGISTRO E LOGIN ---
def registrar_usuario(usuario, senha):
    db_usuarios = ler_arquivo_github(ARQUIVO_DB_USUARIOS, 'json')
    
    # Verifica se usuário já existe
    if usuario in db_usuarios:
        return False, "Usuário já existe! Escolha outro."
    
    # Salva no dicionário (Usuário legível, senha segura)
    db_usuarios[usuario] = {
        "password": hash_senha(senha),
        "created_at": str(datetime.now())
    }
    
    # Salva no GitHub
    json_str = json.dumps(db_usuarios, indent=4)
    atualizar_arquivo_github(ARQUIVO_DB_USUARIOS, json_str, f"Novo usuario: {usuario}")
    return True, "Conta criada! Pode fazer login."

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
        with open("rotasrj.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

rotas_db = carregar_rotas()
lista_linhas = list(rotas_db.keys())

# --- INTERFACE ---
st.title("🚌 BusBoxd")

# Inicializa estado de login
if "logado" not in st.session_state:
    st.session_state["logado"] = False
    st.session_state["usuario_atual"] = ""

# --- SE ESTIVER LOGADO ---
if st.session_state["logado"]:
    c_user, c_logout = st.columns([8, 2])
    c_user.write(f"Olá, **{st.session_state['usuario_atual']}**!")
    
    if c_logout.button("Sair"):
        st.session_state["logado"] = False
        st.session_state["usuario_atual"] = ""
        st.rerun()
    
    aba1, aba2 = st.tabs(["📝 Nova Viagem", "📋 Histórico"])
    
    with aba1:
        with st.form("nova_viagem"):
            c1, c2 = st.columns(2)
            data = c1.date_input("Data", datetime.now())
            hora = c2.time_input("Hora", datetime.now())
            linha = st.selectbox("Linha", [""] + lista_linhas)
            origem = st.text_input("Origem")
            destino = st.text_input("Destino")
            obs = st.text_area("Obs")
            
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
                            "hora": str(hora),
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

    with aba2:
        if st.button("🔄 Atualizar Lista"):
            st.rerun()
        df = ler_arquivo_github(ARQUIVO_DB_VIAGENS, 'csv')
        if not df.empty:
            st.dataframe(df.iloc[::-1], use_container_width=True)
        else:
            st.info("Nenhuma viagem ainda.")

# --- TELA DE LOGIN / CADASTRO ---
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
                    st.error("Usuário ou senha incorretos.")

    with tab_cadastro:
        st.write("### Novo Usuário")
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
                with st.spinner("Criando conta..."):
                    sucesso, msg = registrar_usuario(c_user, c_pass)
                    if sucesso:
                        st.success(msg)
                    else:
                        st.error(msg)

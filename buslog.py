import streamlit as st
import streamlit_authenticator as stauth
import json
import pandas as pd
from datetime import datetime
from github import Github
import io
import time
import bcrypt # Biblioteca padrao de criptografia

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="BusBoxd", page_icon="🚌", layout="centered")

# --- SEGREDOS ---
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"] 
    COOKIE_KEY = st.secrets["COOKIE_KEY"]
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
        # Retornos vazios seguros
        if tipo == 'json': return {"usernames": {}}
        else: return pd.DataFrame()

def atualizar_arquivo_github(nome_arquivo, conteudo, mensagem_commit):
    repo = get_repo()
    try:
        contents = repo.get_contents(nome_arquivo)
        repo.update_file(contents.path, mensagem_commit, conteudo, contents.sha)
    except:
        repo.create_file(nome_arquivo, mensagem_commit, conteudo)

# --- FUNÇÃO DE REGISTRO (CORRIGIDA COM BCRYPT) ---
def registrar_usuario(usuario, email, senha):
    db_usuarios = ler_arquivo_github(ARQUIVO_DB_USUARIOS, 'json')
    
    # Garante que a chave 'usernames' existe
    if 'usernames' not in db_usuarios:
        db_usuarios['usernames'] = {}

    if usuario in db_usuarios['usernames']:
        return False, "Usuário já existe!"
    
    try:
        # Criptografia manual via bcrypt (Mais estável que o Hasher da lib)
        senha_bytes = senha.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(senha_bytes, salt).decode('utf-8')
        
        # Adiciona ao dicionário
        db_usuarios['usernames'][usuario] = {
            "name": usuario, 
            "password": hashed_password,
            "email": email
        }
        
        # Salva no GitHub
        json_str = json.dumps(db_usuarios, indent=4)
        atualizar_arquivo_github(ARQUIVO_DB_USUARIOS, json_str, f"Novo usuário: {usuario}")
        return True, "Conta criada! Vá na aba 'Entrar' para fazer login."
        
    except Exception as e:
        return False, f"Erro técnico ao criar senha: {e}"

# --- CARREGAR DADOS ---
@st.cache_data
def carregar_rotas():
    try:
        with open("db_rotas_final.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

rotas_db = carregar_rotas()
lista_linhas = list(rotas_db.keys())

# --- LÓGICA DE AUTENTICAÇÃO ---
config_usuarios = ler_arquivo_github(ARQUIVO_DB_USUARIOS, 'json')

# Proteção contra arquivo vazio ou corrupto
if 'usernames' not in config_usuarios or not config_usuarios['usernames']:
    # Cria um usuario fake na memoria so pra o autenticador nao quebrar antes de ter alguem cadastrado
    config_usuarios = {'usernames': {'admin_temp': {'password': '123', 'name': 'temp', 'email': 't@t.com'}}}

authenticator = stauth.Authenticate(
    config_usuarios, # Passa o dicionario inteiro
    'busboxd_cookie',
    COOKIE_KEY,
    30
)

# --- INTERFACE ---
st.title("🚌 BusBoxd")

# O login renderiza aqui
authenticator.login('main')

# Verifica o estado da sessão
if st.session_state.get("authentication_status"):
    authenticator.logout('Sair', 'sidebar')
    st.write(f"Olá, **{st.session_state['name']}**!")
    
    # --- ÁREA LOGADA ---
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
                            "usuario": st.session_state['username'],
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

elif st.session_state.get("authentication_status") is False:
    st.error('Usuário ou senha incorretos')

elif st.session_state.get("authentication_status") is None:
    # --- ÁREA DESLOGADA (CRIAR CONTA) ---
    st.markdown("---")
    with st.expander("Não tem conta? Crie aqui"):
        with st.form("form_cadastro"):
            st.write("### Criar Nova Conta")
            novo_user = st.text_input("Usuário (Login)")
            novo_email = st.text_input("Email")
            nova_senha = st.text_input("Senha", type="password")
            nova_senha2 = st.text_input("Confirme a Senha", type="password")
            
            if st.form_submit_button("CRIAR CONTA"):
                if nova_senha != nova_senha2:
                    st.error("As senhas não batem!")
                elif len(nova_senha) < 4:
                    st.error("Senha muito curta!")
                elif not novo_user:
                    st.error("Digite um usuário!")
                else:
                    with st.spinner("Criando conta..."):
                        sucesso, msg = registrar_usuario(novo_user, novo_email, nova_senha)
                        if sucesso:
                            st.success(msg)
                        else:
                            st.error(msg)

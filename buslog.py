import streamlit as st
import json
import pandas as pd
from datetime import datetime, timedelta
from github import Github
import io
import time
import bcrypt

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="BusBoxd", page_icon="🚌", layout="centered")

# --- CSS PERSONALIZADO (NOISE + CARDS + FONTS) ---
st.markdown("""
    <style>
    /* 1. FUNDO GRANULADO (NOISE) */
    .stApp {
        background-color: #0e1117;
        background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='0.05'/%3E%3C/svg%3E");
    }

    /* 2. CABEÇALHO DO MÊS */
    .month-header {
        font-size: 18px;
        font-weight: 600;
        color: #888;
        margin-top: 25px;
        margin-bottom: 10px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    /* 3. CARD DA VIAGEM (CAIXA CINZA) */
    .journal-card {
        display: flex;
        background-color: #262730; /* Cinza do card */
        border-radius: 8px;
        margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        overflow: hidden; /* Para cortar a faixa arredondada */
        align-items: center; /* Centraliza verticalmente */
        height: 70px;
        transition: transform 0.1s;
    }
    .journal-card:hover {
        transform: scale(1.01);
        background-color: #2d2e38;
    }

    /* 4. FAIXA VERTICAL COLORIDA */
    .strip {
        width: 6px;
        height: 100%;
        background-color: #FF4B4B; /* Vermelho Streamlit (ou mude a cor) */
        border-top-left-radius: 8px;
        border-bottom-left-radius: 8px;
    }

    /* 5. DATA (DIA) */
    .date-col {
        width: 60px;
        text-align: center;
        font-size: 26px;
        font-weight: 300; /* Fonte fina/sutil */
        color: #e0e0e0;
        padding-left: 10px;
    }

    /* 6. CONTEÚDO (LINHA E HORA) */
    .info-col {
        flex-grow: 1;
        padding-left: 15px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .bus-line {
        font-size: 18px;
        font-weight: bold;
        color: #ffffff;
    }
    .meta-info {
        font-size: 13px;
        color: #aaa;
        margin-top: 2px;
    }
    
    /* Remove padding padrão chato do Streamlit */
    .block-container {
        padding-top: 2rem;
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
ARQUIVO_ROTAS = "rotasrj.json"

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

# --- SEGURANÇA ---
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
    return True, "Conta criada com sucesso!"

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
        try:
            with open(ARQUIVO_ROTAS, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return ler_arquivo_github(ARQUIVO_ROTAS, 'json')
    except:
        return {}

rotas_db = carregar_rotas()
lista_linhas = list(rotas_db.keys()) if rotas_db else []

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
    
    # --- ABA 1: REGISTRO (SIMPLIFICADA) ---
    with aba1:
        with st.form("nova_viagem"):
            c1, c2 = st.columns(2)
            
            # Data Atual
            data = c1.date_input("Data", datetime.now(), format="DD/MM/YYYY") 
            
            # Hora Atual (Forçamos o refresh da hora usando value direto)
            hora_atual = datetime.now().time()
            hora = c2.time_input("Hora", value=hora_atual)
            
            linha = st.selectbox("Linha", [""] + lista_linhas)
            
            # REMOVIDOS: Origem e Destino
            obs = st.text_area("Observações (Opcional)", height=80)
            
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
                            "hora": str(hora)[:5],
                            "obs": obs,
                            "timestamp": str(datetime.now())
                        }
                        df_novo = pd.DataFrame([novo_dado])
                        df_final = pd.concat([df_antigo, df_novo], ignore_index=True)
                        atualizar_arquivo_github(ARQUIVO_DB_VIAGENS, df_final.to_csv(index=False), "Nova viagem")
                        st.success("Registrado!")
                        time.sleep(1)
                        st.rerun()

    # --- ABA 2: HISTÓRICO VISUAL (CARDS) ---
    with aba2:
        df = ler_arquivo_github(ARQUIVO_DB_VIAGENS, 'csv')
        
        if not df.empty:
            df = df[df['usuario'] == st.session_state['usuario_atual']]
            df['data_obj'] = pd.to_datetime(df['data'])
            
            # Filtros
            filtro_tempo = st.pills("Período:", ["Tudo", "7 Dias", "30 Dias", "Este Ano"], default="Tudo")
            
            hoje = datetime.now()
            if filtro_tempo == "7 Dias":
                df = df[df['data_obj'] >= (hoje - timedelta(days=7))]
            elif filtro_tempo == "30 Dias":
                df = df[df['data_obj'] >= (hoje - timedelta(days=30))]
            elif filtro_tempo == "Este Ano":
                df = df[df['data_obj'].dt.year == hoje.year]
            
            df = df.sort_values(by='data_obj', ascending=False)
            df['ano'] = df['data_obj'].dt.year
            df['mes'] = df['data_obj'].dt.month
            
            grupos = df.groupby(['ano', 'mes'], sort=False)
            
            if df.empty:
                st.info("Nenhuma viagem nesse período.")
            else:
                for (ano, mes), grupo in grupos:
                    nome_mes = MESES_PT[mes]
                    # Header do Mês
                    st.markdown(f"<div class='month-header'>{nome_mes} {ano}</div>", unsafe_allow_html=True)
                    
                    for _, row in grupo.iterrows():
                        obs_texto = f" • {row['obs']}" if pd.notna(row['obs']) and row['obs'] else ""
                        
                        # Aqui montamos o HTML do CARD
                        card_html = f"""
                        <div class="journal-card">
                            <div class="strip"></div>
                            <div class="date-col">{row['data_obj'].day}</div>
                            <div class="info-col">
                                <div class="bus-line">{row['linha']}</div>
                                <div class="meta-info">🕒 {str(row['hora'])[:5]}{obs_texto}</div>
                            </div>
                        </div>
                        """
                        st.markdown(card_html, unsafe_allow_html=True)

        else:
            st.info("Seu diário está vazio. Comece a catalogar!")

# --- LOGIN / CADASTRO ---
else:
    tab_login, tab_cadastro = st.tabs(["Entrar", "Criar Conta"])
    
    with tab_login:
        l_user = st.text_input("Usuário")
        l_pass = st.text_input("Senha", type="password")
        if st.button("ENTRAR", use_container_width=True):
            with st.spinner("Entrando..."):
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
                st.error("Senha curta demais!")
            elif not c_user:
                st.error("Digite um usuário!")
            else:
                with st.spinner("Criando..."):
                    sucesso, msg = registrar_usuario(c_user, c_pass)
                    if sucesso:
                        st.success(msg)
                    else:
                        st.error(msg)

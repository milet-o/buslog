import streamlit as st
import json
import pandas as pd
from datetime import datetime, timedelta, time as datetime_time
from github import Github
import io
import time
import bcrypt
import base64

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="BusLog", page_icon="🚌", layout="centered")

# --- CSS PERSONALIZADO (CORRIGIDO PARA MODO CLARO/ESCURO) ---
st.markdown("""
    <style>
    /* 1. FORÇAR TEXTOS CLAROS (Para não bugar no Modo Claro do navegador) */
    h1, h2, h3, h4, h5, h6, p, span, label, .stMarkdown {
        color: #e0e0e0 !important;
    }
    .stTextInput > label, .stSelectbox > label, .stDateInput > label, .stTimeInput > label, .stTextArea > label {
        color: #e0e0e0 !important;
    }
    
    /* 2. FUNDO GRANULADO ESCURO FIXO */
    .stApp {
        background-color: #0e1117;
        background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='0.05'/%3E%3C/svg%3E");
        background-attachment: fixed;
    }
    
    /* 3. ESCONDER DICAS DO STREAMLIT */
    [data-testid="InputInstructions"] { display: none; }
    
    /* 4. HEADER DO MÊS */
    .month-header {
        font-size: 16px;
        font-weight: 600;
        color: #aaa !important; /* Mais claro para contraste */
        margin-top: 30px;
        margin-bottom: 10px;
        text-transform: uppercase;
        letter-spacing: 2px;
        border-bottom: 1px solid #333;
        padding-bottom: 5px;
    }

    /* 5. CARD DA VIAGEM */
    .journal-card {
        display: flex;
        background-color: #1c1c1e;
        border-radius: 6px;
        margin-bottom: 8px;
        border: 1px solid #333;
        align-items: stretch; 
        min-height: 75px; 
        transition: all 0.2s ease;
        overflow: hidden; 
    }
    .journal-card:hover {
        transform: translateX(5px);
        border-color: #555;
        background-color: #252528;
    }

    /* 6. FAIXA VERTICAL */
    .strip {
        width: 5px;
        background-color: #FF4B4B;
        flex-shrink: 0; 
    }

    /* 7. DATA */
    .date-col {
        width: 60px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        font-weight: 400;
        color: #eee !important;
        flex-shrink: 0; 
    }

    /* 8. CONTEÚDO */
    .info-col {
        flex-grow: 1;
        padding: 10px 15px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        min-width: 0; 
    }
    .bus-line {
        font-size: 17px;
        font-weight: 700;
        color: #fff !important;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis; 
    }
    .meta-info {
        font-size: 13px;
        color: #aaa !important;
        margin-top: 4px;
        word-wrap: break-word; 
        overflow-wrap: break-word;
        line-height: 1.4;
    }
    
    /* 9. AVISO DE PRIVACIDADE */
    .privacy-warning {
        font-size: 12px;
        color: #ff6c6c !important;
        margin-bottom: 5px;
        font-weight: 500;
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

# --- ESTADO DE SESSÃO ---
if "form_key" not in st.session_state:
    st.session_state["form_key"] = 0
if "limite_registros" not in st.session_state:
    st.session_state["limite_registros"] = 10 

# --- FUNÇÕES ---
def get_repo():
    g = Github(GITHUB_TOKEN)
    return g.get_repo(REPO_NAME)

def ler_arquivo_github(nome_arquivo, tipo='json'):
    try:
        repo = get_repo()
        contents = repo.get_contents(nome_arquivo)
        decodificado = contents.decoded_content.decode("utf-8")
        if tipo == 'json': return json.loads(decodificado)
        else: return pd.read_csv(io.StringIO(decodificado))
    except:
        return {} if tipo == 'json' else pd.DataFrame()

def atualizar_arquivo_github(nome_arquivo, conteudo, mensagem_commit):
    repo = get_repo()
    try:
        contents = repo.get_contents(nome_arquivo)
        repo.update_file(contents.path, mensagem_commit, conteudo, contents.sha)
    except:
        repo.create_file(nome_arquivo, mensagem_commit, conteudo)

def hash_senha(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verificar_senha(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

def registrar_usuario(usuario, senha):
    db_usuarios = ler_arquivo_github(ARQUIVO_DB_USUARIOS, 'json')
    if usuario in db_usuarios: return False, "Usuário já existe!"
    
    db_usuarios[usuario] = { "password": hash_senha(senha), "created_at": str(datetime.now()) }
    
    json_str = json.dumps(db_usuarios, indent=4)
    atualizar_arquivo_github(ARQUIVO_DB_USUARIOS, json_str, f"Novo usuario: {usuario}")
    return True, "Conta criada com sucesso!"

def fazer_login(usuario, senha):
    db_usuarios = ler_arquivo_github(ARQUIVO_DB_USUARIOS, 'json')
    if usuario in db_usuarios:
        if verificar_senha(senha, db_usuarios[usuario]['password']): return True
    return False

def tocar_buzina():
    arquivo_som = "bushorn.m4a"
    try:
        with open(arquivo_som, "rb") as f:
            data = f.read()
            b64 = base64.b64encode(data).decode()
            md = f"""
                <audio autoplay>
                <source src="data:audio/mp4;base64,{b64}" type="audio/mp4">
                </audio>
            """
            st.markdown(md, unsafe_allow_html=True)
    except FileNotFoundError:
        pass 

@st.cache_data
def carregar_rotas():
    try:
        try:
            with open(ARQUIVO_ROTAS, "r", encoding="utf-8") as f: return json.load(f)
        except: return ler_arquivo_github(ARQUIVO_ROTAS, 'json')
    except: return {}

rotas_db = carregar_rotas()
lista_linhas = list(rotas_db.keys()) if rotas_db else []

MESES_PT = {1: "JANEIRO", 2: "FEVEREIRO", 3: "MARÇO", 4: "ABRIL", 5: "MAIO", 6: "JUNHO", 7: "JULHO", 8: "AGOSTO", 9: "SETEMBRO", 10: "OUTUBRO", 11: "NOVEMBRO", 12: "DEZEMBRO"}

# --- INTERFACE ---
st.title("🚌 BusLog")

if "logado" not in st.session_state:
    st.session_state["logado"] = False
    st.session_state["usuario_atual"] = ""

# --- ÁREA LOGADA ---
if st.session_state["logado"]:
    with st.sidebar:
        # SAUDAÇÃO ALTERADA
        st.write(f"Olá, **busólogo**!")
        st.caption(f"Logado como: {st.session_state['usuario_atual']}")
        
        if st.button("Sair do BusLog"):
            st.session_state["logado"] = False
            st.rerun()
    
    aba1, aba2 = st.tabs(["📝 Nova Viagem", "📓 Diário"])
    
    # --- ABA 1: REGISTRO ---
    with aba1:
        key_atual = st.session_state["form_key"]
        
        with st.form(f"nova_viagem_{key_atual}"):
            c1, c2 = st.columns(2)
            data = c1.date_input("Data", datetime.now(), format="DD/MM/YYYY") 
            
            # HORA FIXA EM 00:00
            hora_padrao = datetime_time(0, 0)
            hora = c2.time_input("Hora", value=hora_padrao)
            
            linha = st.selectbox("Linha", [""] + lista_linhas)
            
            st.markdown('<div class="privacy-warning">⚠ Atenção: Este diário é público. Não escreva informações pessoais.</div>', unsafe_allow_html=True)
            obs = st.text_area("Observações (Opcional)", height=68, max_chars=50)
            
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
                        
                        tocar_buzina()
                        
                        st.success("Registrado!")
                        st.session_state["form_key"] += 1 
                        time.sleep(1)
                        st.rerun()

    # --- ABA 2: HISTÓRICO ---
    with aba2:
        df = ler_arquivo_github(ARQUIVO_DB_VIAGENS, 'csv')
        
        if not df.empty:
            df = df[df['usuario'] == st.session_state['usuario_atual']]
            
            df['data'] = df['data'].astype(str)
            df['hora'] = df['hora'].astype(str)
            df['datetime_full'] = pd.to_datetime(df['data'] + ' ' + df['hora'], errors='coerce')
            df = df.dropna(subset=['datetime_full'])
            
            filtro_tempo = st.pills("Período:", ["Tudo", "7 Dias", "30 Dias", "Este Ano"], default="Tudo")
            
            hoje = datetime.now()
            if filtro_tempo == "7 Dias":
                df = df[df['datetime_full'] >= (hoje - timedelta(days=7))]
            elif filtro_tempo == "30 Dias":
                df = df[df['datetime_full'] >= (hoje - timedelta(days=30))]
            elif filtro_tempo == "Este Ano":
                df = df[df['datetime_full'].dt.year == hoje.year]
            
            df = df.sort_values(by='datetime_full', ascending=False)
            
            total_registros = len(df)
            limite = st.session_state["limite_registros"]
            df_view = df.head(limite)
            
            df_view['ano'] = df_view['datetime_full'].dt.year
            df_view['mes'] = df_view['datetime_full'].dt.month
            grupos = df_view.groupby(['ano', 'mes'], sort=False)
            
            if df.empty:
                st.info("Nenhuma viagem válida encontrada neste período.")
            else:
                for (ano, mes), grupo in grupos:
                    nome_mes = MESES_PT[mes]
                    st.markdown(f"<div class='month-header'>{nome_mes} {ano}</div>", unsafe_allow_html=True)
                    
                    for _, row in grupo.iterrows():
                        obs_texto = f" • {row['obs']}" if pd.notna(row['obs']) and row['obs'] else ""
                        
                        card_html = f"""
                        <div class="journal-card">
                            <div class="strip"></div>
                            <div class="date-col">{row['datetime_full'].day}</div>
                            <div class="info-col">
                                <div class="bus-line">{row['linha']}</div>
                                <div class="meta-info">🕒 {str(row['hora'])[:5]}{obs_texto}</div>
                            </div>
                        </div>
                        """
                        st.markdown(card_html, unsafe_allow_html=True)
                
                if total_registros > limite:
                    st.markdown("---")
                    col_load, _ = st.columns([1, 2])
                    if col_load.button(f"Carregar mais antigos ({total_registros - limite} restantes)"):
                        st.session_state["limite_registros"] += 10 
                        st.rerun()
                elif total_registros > 10:
                    st.caption("Você chegou ao fim do diário.")

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
        
        # AVISO IMPORTANTE DE SENHA
        st.warning("⚠ **IMPORTANTE:** Anote sua senha em um local seguro! Como não coletamos e-mail por privacidade, **é impossível recuperar a conta** caso você a perca.")
        
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

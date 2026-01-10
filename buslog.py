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

# --- CSS PERSONALIZADO ---
st.markdown("""
    <style>
    /* 1. FORÇAR TEXTOS CLAROS */
    h1, h2, h3, h4, h5, h6, p, span, label, .stMarkdown, .stText, div[data-testid="stMetricValue"] { color: #e0e0e0 !important; }
    .stTextInput > label, .stSelectbox > label, .stDateInput > label, .stTimeInput > label, .stTextArea > label { color: #e0e0e0 !important; }
    
    /* 2. FUNDO GRANULADO */
    .stApp {
        background-color: #0e1117;
        background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='0.05'/%3E%3C/svg%3E");
        background-attachment: fixed;
    }
    
    /* 3. ESCONDER DICAS */
    [data-testid="InputInstructions"] { display: none; }
    
    /* 4. HEADER DO MÊS */
    .month-header {
        font-size: 16px;
        font-weight: 600;
        color: #aaa !important;
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
        transform: translateX(2px);
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
    
    /* 9. AVISO */
    .privacy-warning {
        font-size: 12px;
        color: #ff6c6c !important;
        margin-bottom: 5px;
        font-weight: 500;
    }

    /* 10. BOTÃO DE DELETAR */
    div[data-testid="column"] button {
        margin-top: 15px; 
    }

    /* 11. ESTILO DO PERFIL */
    .profile-header {
        background-color: #1c1c1e;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #333;
        text-align: center;
        margin-bottom: 20px;
    }
    .avatar {
        font-size: 60px;
        margin-bottom: 10px;
    }
    .display-name {
        font-size: 24px;
        font-weight: bold;
        color: #fff;
    }
    .username-tag {
        font-size: 14px;
        color: #888;
        margin-bottom: 10px;
    }
    .bio-text {
        font-size: 14px;
        color: #ccc;
        font-style: italic;
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
ARQUIVO_DB_PERFIL = "perfil.json" # NOVO ARQUIVO
ARQUIVO_ROTAS = "rotasrj.json"

# --- ESTADO DE SESSÃO ---
if "form_key" not in st.session_state:
    st.session_state["form_key"] = 0
if "limite_registros" not in st.session_state:
    st.session_state["limite_registros"] = 10 

# --- FUNÇÕES UTILITÁRIAS ---
def agora_br():
    return datetime.utcnow() - timedelta(hours=3)

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

# --- FUNÇÕES DE PERFIL (NOVAS) ---
def carregar_perfil(usuario):
    """Carrega o perfil do usuario, se nao existir, retorna padrao"""
    db_perfil = ler_arquivo_github(ARQUIVO_DB_PERFIL, 'json')
    if usuario in db_perfil:
        return db_perfil[usuario]
    else:
        # Perfil Padrão se não existir ainda
        return {
            "display_name": usuario.capitalize(),
            "bio": "Novo no BusLog!",
            "avatar": "👤"
        }

def salvar_perfil_editado(usuario, display_name, bio, avatar):
    db_perfil = ler_arquivo_github(ARQUIVO_DB_PERFIL, 'json')
    
    db_perfil[usuario] = {
        "display_name": display_name,
        "bio": bio,
        "avatar": avatar,
        "updated_at": str(agora_br())
    }
    
    json_str = json.dumps(db_perfil, indent=4)
    atualizar_arquivo_github(ARQUIVO_DB_PERFIL, json_str, f"Perfil atualizado: {usuario}")
    return True

# --- FUNÇÕES DE AUTH ---
def registrar_usuario(usuario, senha):
    usuario = usuario.lower().strip()
    db_usuarios = ler_arquivo_github(ARQUIVO_DB_USUARIOS, 'json')
    if usuario in db_usuarios: return False, "Usuário já existe!"
    
    db_usuarios[usuario] = { "password": hash_senha(senha), "created_at": str(agora_br()) }
    
    json_str = json.dumps(db_usuarios, indent=4)
    atualizar_arquivo_github(ARQUIVO_DB_USUARIOS, json_str, f"Novo usuario: {usuario}")
    
    # Cria perfil vazio inicial
    salvar_perfil_editado(usuario, usuario.capitalize(), "Busólogo iniciante.", "👤")
    
    return True, "Conta criada com sucesso!"

def fazer_login(usuario, senha):
    usuario = usuario.lower().strip()
    db_usuarios = ler_arquivo_github(ARQUIVO_DB_USUARIOS, 'json')
    if usuario in db_usuarios:
        if verificar_senha(senha, db_usuarios[usuario]['password']): return True
    return False

def excluir_registro(index_original):
    df = ler_arquivo_github(ARQUIVO_DB_VIAGENS, 'csv')
    if index_original in df.index:
        df = df.drop(index_original)
        if not df.empty:
            df['datetime_temp'] = pd.to_datetime(df['data'].astype(str) + ' ' + df['hora'].astype(str), errors='coerce')
            df = df.sort_values(by=['usuario', 'datetime_temp'], ascending=[True, False])
            df = df.drop(columns=['datetime_temp'])
        atualizar_arquivo_github(ARQUIVO_DB_VIAGENS, df.to_csv(index=False), "Registro excluído")
        return True
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
    user_atual = st.session_state["usuario_atual"]
    
    with st.sidebar:
        st.write(f"Olá, **busólogo**!")
        st.caption(f"Logado como: {user_atual}")
        if st.button("Sair do BusLog"):
            st.session_state["logado"] = False
            st.rerun()
    
    aba1, aba2, aba3 = st.tabs(["📝 Nova Viagem", "📓 Diário", "👤 Meu Perfil"])
    
    # --- ABA 1: REGISTRO ---
    with aba1:
        key_atual = st.session_state["form_key"]
        with st.form(f"nova_viagem_{key_atual}"):
            c1, c2 = st.columns(2)
            data = c1.date_input("Data", agora_br(), format="DD/MM/YYYY") 
            hora = c2.time_input("Hora", value=datetime_time(0, 0))
            linha = st.selectbox("Linha", [""] + lista_linhas)
            st.markdown('<div class="privacy-warning">⚠ Atenção: Este diário é público.</div>', unsafe_allow_html=True)
            obs = st.text_area("Observações (Opcional)", height=68, max_chars=50)
            
            if st.form_submit_button("Salvar Viagem", use_container_width=True):
                if not linha:
                    st.error("Escolha a linha!")
                else:
                    with st.spinner("Salvando..."):
                        df_antigo = ler_arquivo_github(ARQUIVO_DB_VIAGENS, 'csv')
                        novo_dado = {
                            "usuario": user_atual, 
                            "linha": linha,
                            "data": str(data),
                            "hora": str(hora)[:5],
                            "obs": obs,
                            "timestamp": str(agora_br())
                        }
                        df_novo = pd.DataFrame([novo_dado])
                        df_final = pd.concat([df_antigo, df_novo], ignore_index=True)
                        
                        df_final['datetime_temp'] = pd.to_datetime(df_final['data'].astype(str) + ' ' + df_final['hora'].astype(str), errors='coerce')
                        df_final = df_final.sort_values(by=['usuario', 'datetime_temp'], ascending=[True, False])
                        df_final = df_final.drop(columns=['datetime_temp'])
                        
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
            df_filtered = df[df['usuario'] == user_atual].copy()
            df_filtered['data'] = df_filtered['data'].astype(str)
            df_filtered['hora'] = df_filtered['hora'].astype(str)
            df_filtered['datetime_full'] = pd.to_datetime(df_filtered['data'] + ' ' + df_filtered['hora'], errors='coerce')
            df_filtered = df_filtered.dropna(subset=['datetime_full'])
            
            filtro_tempo = st.pills("Período:", ["Tudo", "7 Dias", "30 Dias", "Este Ano"], default="Tudo")
            hoje = agora_br()
            
            if filtro_tempo == "7 Dias":
                df_filtered = df_filtered[df_filtered['datetime_full'] >= (hoje - timedelta(days=7))]
            elif filtro_tempo == "30 Dias":
                df_filtered = df_filtered[df_filtered['datetime_full'] >= (hoje - timedelta(days=30))]
            elif filtro_tempo == "Este Ano":
                df_filtered = df_filtered[df_filtered['datetime_full'].dt.year == hoje.year]
            
            df_filtered = df_filtered.sort_values(by='datetime_full', ascending=False)
            
            total_registros = len(df_filtered)
            limite = st.session_state["limite_registros"]
            df_view = df_filtered.head(limite)
            
            df_view['ano'] = df_view['datetime_full'].dt.year
            df_view['mes'] = df_view['datetime_full'].dt.month
            grupos = df_view.groupby(['ano', 'mes'], sort=False)
            
            if df_filtered.empty:
                st.info("Nenhuma viagem neste período.")
            else:
                for (ano, mes), grupo in grupos:
                    nome_mes = MESES_PT[mes]
                    st.markdown(f"<div class='month-header'>{nome_mes} {ano}</div>", unsafe_allow_html=True)
                    for index, row in grupo.iterrows():
                        obs_texto = f" • {row['obs']}" if pd.notna(row['obs']) and row['obs'] else ""
                        col_card, col_del = st.columns([0.88, 0.12])
                        with col_card:
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
                        with col_del:
                            if st.button("❌", key=f"del_{index}", help="Excluir"):
                                with st.spinner("Apagando..."):
                                    if excluir_registro(index):
                                        st.success("Apagado!")
                                        time.sleep(1)
                                        st.rerun()
                if total_registros > limite:
                    if st.button(f"Carregar mais ({total_registros - limite} restantes)"):
                        st.session_state["limite_registros"] += 10 
                        st.rerun()
        else:
            st.info("Comece a catalogar suas viagens!")

    # --- ABA 3: PERFIL (NOVA) ---
    with aba3:
        perfil = carregar_perfil(user_atual)
        
        # Modo de Visualização
        if "editando_perfil" not in st.session_state:
            st.session_state["editando_perfil"] = False
        
        if not st.session_state["editando_perfil"]:
            # HTML do Perfil Visual
            html_perfil = f"""
            <div class="profile-header">
                <div class="avatar">{perfil.get('avatar', '👤')}</div>
                <div class="display-name">{perfil.get('display_name', user_atual)}</div>
                <div class="username-tag">@{user_atual}</div>
                <div class="bio-text">"{perfil.get('bio', '')}"</div>
            </div>
            """
            st.markdown(html_perfil, unsafe_allow_html=True)
            
            # ESTATÍSTICAS
            df_viagens = ler_arquivo_github(ARQUIVO_DB_VIAGENS, 'csv')
            if not df_viagens.empty:
                meus_dados = df_viagens[df_viagens['usuario'] == user_atual]
                total = len(meus_dados)
                linha_fav = meus_dados['linha'].mode()[0] if not meus_dados.empty else "-"
                
                k1, k2 = st.columns(2)
                k1.metric("Total de Viagens", total)
                k2.metric("Linha Favorita", linha_fav)
            else:
                st.info("Faça viagens para gerar estatísticas!")

            if st.button("Editar Perfil"):
                st.session_state["editando_perfil"] = True
                st.rerun()
        
        else:
            # Modo de Edição
            with st.form("form_perfil"):
                st.write("### Editando Perfil")
                novo_nome = st.text_input("Nome de Exibição", value=perfil.get('display_name', ''))
                nova_bio = st.text_area("Bio (Frase curta)", value=perfil.get('bio', ''), max_chars=100)
                
                # Seletor de Avatar (Emojis)
                opcoes_avatar = ["👤", "🚌", "🚍", "🚏", "🎫", "😎", "🤠", "👽", "👾", "🤖", "🐱", "🐶"]
                idx_atual = 0
                if perfil.get('avatar') in opcoes_avatar:
                    idx_atual = opcoes_avatar.index(perfil.get('avatar'))
                novo_avatar = st.selectbox("Escolha um Avatar", opcoes_avatar, index=idx_atual)
                
                c_salvar, c_cancelar = st.columns(2)
                with c_salvar:
                    if st.form_submit_button("Salvar Alterações", use_container_width=True):
                        if salvar_perfil_editado(user_atual, novo_nome, nova_bio, novo_avatar):
                            st.success("Perfil atualizado!")
                            st.session_state["editando_perfil"] = False
                            time.sleep(1)
                            st.rerun()
                
                with c_cancelar:
                     if st.form_submit_button("Cancelar", use_container_width=True):
                         st.session_state["editando_perfil"] = False
                         st.rerun()

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
                    st.session_state["usuario_atual"] = l_user.lower().strip()
                    st.rerun()
                else:
                    st.error("Dados incorretos.")

    with tab_cadastro:
        st.write("### Criar Nova Conta")
        st.warning("⚠ **IMPORTANTE:** Anote sua senha! Impossível recuperar.")
        c_user = st.text_input("Escolha um Usuário")
        c_pass = st.text_input("Escolha uma Senha", type="password", key="reg_pass")
        c_pass2 = st.text_input("Confirme a Senha", type="password", key="reg_pass2")
        if st.button("CRIAR CONTA", use_container_width=True):
            if c_pass != c_pass2: st.error("Senhas não batem!")
            elif len(c_pass) < 4: st.error("Senha curta!")
            elif not c_user: st.error("Digite um usuário!")
            else:
                with st.spinner("Criando..."):
                    sucesso, msg = registrar_usuario(c_user, c_pass)
                    if sucesso: st.success(msg)
                    else: st.error(msg)

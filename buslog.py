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
        font-size: 14px;
        font-weight: 600;
        color: #aaa !important;
        margin-top: 20px;
        margin-bottom: 10px;
        text-transform: uppercase;
        letter-spacing: 2px;
        border-bottom: 1px solid #333;
        padding-bottom: 5px;
    }

    /* 5. CARD DA VIAGEM (DIÁRIO) */
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

    /* 6. CARD DE ATIVIDADE (FEED) */
    .activity-card {
        background-color: #161618;
        border: 1px solid #333;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 12px;
    }
    .activity-header {
        display: flex;
        align-items: center;
        margin-bottom: 8px;
    }
    .user-avatar { font-size: 20px; margin-right: 8px; }
    .user-name { font-weight: bold; color: #fff; font-size: 15px; }
    .activity-time { font-size: 12px; color: #888; margin-left: auto; }
    
    .integration-badge {
        background-color: #2c2c30;
        color: #ddd;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border: 1px solid #444;
    }

    /* 7. FAIXA VERTICAL */
    .strip { width: 5px; background-color: #FF4B4B; flex-shrink: 0; }

    /* 8. DATA */
    .date-col {
        width: 50px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        font-weight: 400;
        color: #eee !important;
        flex-shrink: 0; 
    }

    /* 9. CONTEÚDO */
    .info-col {
        flex-grow: 1;
        padding: 8px 12px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        min-width: 0; 
    }
    .bus-line {
        font-size: 16px;
        font-weight: 700;
        color: #fff !important;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis; 
    }
    .meta-info {
        font-size: 12px;
        color: #aaa !important;
        margin-top: 2px;
    }
    
    /* 10. AVISO */
    .privacy-warning {
        font-size: 12px; color: #ff6c6c !important; margin-bottom: 5px; font-weight: 500;
    }

    /* 11. BOTÃO DE DELETAR */
    div[data-testid="column"] button { margin-top: 15px; }

    /* 12. PERFIL E STATS CORRIGIDOS */
    .profile-header {
        background-color: #1c1c1e; padding: 20px; border-radius: 10px;
        border: 1px solid #333; text-align: center; margin-bottom: 20px;
    }
    .avatar { font-size: 60px; margin-bottom: 10px; }
    .display-name { font-size: 24px; font-weight: bold; color: #fff; }
    .username-tag { font-size: 14px; color: #888; margin-bottom: 10px; }
    .bio-text { font-size: 14px; color: #ccc; font-style: italic; }
    
    .stat-box {
        background-color: #262730;
        padding: 10px;
        border-radius: 6px;
        text-align: center;
        border: 1px solid #333;
        height: 100%;
    }
    .stat-label { font-size: 12px; color: #888; text-transform: uppercase; }
    .stat-value { font-size: 24px; font-weight: bold; color: #fff; }
    .stat-value-small { font-size: 16px; font-weight: bold; color: #fff; word-wrap: break-word; }
    
    /* 13. Search User Result */
    .search-result {
        padding: 10px; border-bottom: 1px solid #333; cursor: pointer;
    }
    .search-result:hover { background-color: #262730; }
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
ARQUIVO_DB_PERFIL = "perfil.json"
ARQUIVO_DB_SOCIAL = "social.json" # NOVO
ARQUIVO_ROTAS = "rotasrj.json"

# --- ESTADO DE SESSÃO ---
if "form_key" not in st.session_state: st.session_state["form_key"] = 0
if "limite_registros" not in st.session_state: st.session_state["limite_registros"] = 10
if "perfil_visitado" not in st.session_state: st.session_state["perfil_visitado"] = None # Para visitar outros perfis

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

# --- FUNÇÕES SOCIAIS (NOVAS) ---
def carregar_social():
    return ler_arquivo_github(ARQUIVO_DB_SOCIAL, 'json')

def salvar_social(dados):
    json_str = json.dumps(dados, indent=4)
    atualizar_arquivo_github(ARQUIVO_DB_SOCIAL, json_str, "Social update")

def seguir_usuario(eu, outro):
    dados = carregar_social()
    if eu not in dados: dados[eu] = []
    if outro not in dados[eu]:
        dados[eu].append(outro)
        salvar_social(dados)
        return True
    return False

def deixar_seguir(eu, outro):
    dados = carregar_social()
    if eu in dados and outro in dados[eu]:
        dados[eu].remove(outro)
        salvar_social(dados)
        return True
    return False

def get_seguidores_count(usuario):
    dados = carregar_social()
    seguidores = 0
    seguindo = len(dados.get(usuario, []))
    for u, lista in dados.items():
        if usuario in lista:
            seguidores += 1
    return seguidores, seguindo

# --- PERFIL ---
def carregar_perfil(usuario):
    db_perfil = ler_arquivo_github(ARQUIVO_DB_PERFIL, 'json')
    if usuario in db_perfil: return db_perfil[usuario]
    else: return { "display_name": usuario.capitalize(), "bio": "Busólogo.", "avatar": "👤" }

def salvar_perfil_editado(usuario, display_name, bio, avatar):
    db_perfil = ler_arquivo_github(ARQUIVO_DB_PERFIL, 'json')
    db_perfil[usuario] = { "display_name": display_name, "bio": bio, "avatar": avatar, "updated_at": str(agora_br()) }
    json_str = json.dumps(db_perfil, indent=4)
    atualizar_arquivo_github(ARQUIVO_DB_PERFIL, json_str, f"Perfil atualizado: {usuario}")
    return True

# --- LÓGICA DE AGRUPAMENTO DE VIAGENS (INTEGRAÇÃO) ---
def agrupar_viagens_atividade(df_viagens):
    """Agrupa viagens do mesmo usuário em janelas de 2 horas"""
    if df_viagens.empty: return []
    
    # Prepara o DataFrame
    df_viagens['datetime_full'] = pd.to_datetime(df_viagens['data'].astype(str) + ' ' + df_viagens['hora'].astype(str), errors='coerce')
    df_viagens = df_viagens.dropna(subset=['datetime_full'])
    df_viagens = df_viagens.sort_values(by=['usuario', 'datetime_full'], ascending=[True, False]) # Ordena por user, depois data mais recente
    
    feed_items = []
    
    # Itera por usuário
    for usuario, grupo_user in df_viagens.groupby('usuario'):
        # Ordena as viagens desse usuario cronologicamente (antigo -> novo) para calcular janelas
        grupo_user = grupo_user.sort_values('datetime_full', ascending=True)
        
        viagens_user = grupo_user.to_dict('records')
        if not viagens_user: continue
        
        # Lógica de Agrupamento
        clusters = []
        if viagens_user:
            cluster_atual = [viagens_user[0]]
            
            for i in range(1, len(viagens_user)):
                viagem = viagens_user[i]
                ultima_do_cluster = cluster_atual[-1]
                
                # Diferença de tempo
                diff = viagem['datetime_full'] - ultima_do_cluster['datetime_full']
                
                if diff <= timedelta(hours=2):
                    cluster_atual.append(viagem)
                else:
                    clusters.append(cluster_atual)
                    cluster_atual = [viagem]
            clusters.append(cluster_atual)
            
        # Transforma clusters em Feed Items
        for cluster in clusters:
            # Pega o horario da primeira viagem do cluster (a mais antiga do grupo) ou a mais recente?
            # Para feed, geralmente a data do cluster é a data da ultima atividade (mais recente)
            viagem_recente = cluster[-1] 
            
            feed_items.append({
                "usuario": usuario,
                "datetime_ref": viagem_recente['datetime_full'], # Para ordenar o feed geral
                "viagens": cluster[::-1] # Inverte para mostrar a mais recente em cima dentro do card
            })
            
    # Ordena o feed geral (Clusters mais recentes primeiro)
    feed_items.sort(key=lambda x: x['datetime_ref'], reverse=True)
    return feed_items

# --- AUTH ---
def registrar_usuario(usuario, senha):
    usuario = usuario.lower().strip()
    db_usuarios = ler_arquivo_github(ARQUIVO_DB_USUARIOS, 'json')
    if usuario in db_usuarios: return False, "Usuário já existe!"
    db_usuarios[usuario] = { "password": hash_senha(senha), "created_at": str(agora_br()) }
    json_str = json.dumps(db_usuarios, indent=4)
    atualizar_arquivo_github(ARQUIVO_DB_USUARIOS, json_str, f"Novo usuario: {usuario}")
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
            md = f"""<audio autoplay><source src="data:audio/mp4;base64,{b64}" type="audio/mp4"></audio>"""
            st.markdown(md, unsafe_allow_html=True)
    except FileNotFoundError: pass 

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
    meu_user = st.session_state["usuario_atual"]
    
    # SIDEBAR COM PESQUISA E MENU
    with st.sidebar:
        st.write(f"Olá, **busólogo**!")
        st.caption(f"Logado como: @{meu_user}")
        
        st.markdown("---")
        st.write("🔍 **Explorar Usuários**")
        termo_busca = st.text_input("Buscar usuário:", placeholder="Digite o nome...").lower().strip()
        
        if termo_busca:
            db_perfis = ler_arquivo_github(ARQUIVO_DB_PERFIL, 'json')
            resultados = [u for u in db_perfis.keys() if termo_busca in u or termo_busca in db_perfis[u].get('display_name', '').lower()]
            
            if resultados:
                for res in resultados:
                    if st.button(f"👤 {res}", key=f"btn_search_{res}", use_container_width=True):
                        st.session_state["perfil_visitado"] = res
                        st.rerun()
            else:
                st.caption("Ninguém encontrado.")
        
        st.markdown("---")
        if st.button("🏠 Voltar ao Início", use_container_width=True):
            st.session_state["perfil_visitado"] = None
            st.rerun()
            
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state["logado"] = False
            st.rerun()

    # --- MODO VISITANTE (Ver Perfil de Outro) ---
    if st.session_state["perfil_visitado"]:
        visitado = st.session_state["perfil_visitado"]
        dados_perfil = carregar_perfil(visitado)
        
        # Botão de Seguir/Deixar de Seguir
        social_db = carregar_social()
        seguindo_lista = social_db.get(meu_user, [])
        eh_seguido = visitado in seguindo_lista
        
        # Header do Perfil Visitado
        col_voltar, col_seguir = st.columns([1, 3])
        if col_voltar.button("⬅ Voltar"):
            st.session_state["perfil_visitado"] = None
            st.rerun()
            
        if visitado != meu_user:
            label_btn = "Deixar de Seguir" if eh_seguido else "Seguir"
            tipo_btn = "primary" if not eh_seguido else "secondary"
            if col_seguir.button(label_btn, type=tipo_btn):
                with st.spinner("Processando..."):
                    if eh_seguido: deixar_seguir(meu_user, visitado)
                    else: seguir_usuario(meu_user, visitado)
                    st.rerun()

        st.markdown(f"""
        <div class="profile-header">
            <div class="avatar">{dados_perfil.get('avatar', '👤')}</div>
            <div class="display-name">{dados_perfil.get('display_name', visitado)}</div>
            <div class="username-tag">@{visitado}</div>
            <div class="bio-text">"{dados_perfil.get('bio', '')}"</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Stats do Visitado
        df_viagens = ler_arquivo_github(ARQUIVO_DB_VIAGENS, 'csv')
        segs, segds = get_seguidores_count(visitado)
        
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        col_s1.metric("Seguidores", segs)
        col_s2.metric("Seguindo", segds)
        
        if not df_viagens.empty:
            dados_visitado = df_viagens[df_viagens['usuario'] == visitado]
            total = len(dados_visitado)
            linha_fav = dados_visitado['linha'].mode()[0] if not dados_visitado.empty else "-"
        else:
            total = 0
            linha_fav = "-"
            
        col_s3.metric("Viagens", total)
        
        # Card HTML para Linha Favorita (Para quebrar texto)
        col_s4.markdown(f"""
            <div class="stat-box">
                <div class="stat-label">Linha Favorita</div>
                <div class="stat-value-small">{linha_fav}</div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### 📓 Diário de Viagens")
        # Logica de mostrar o diário do visitado (Copia simplificada do histórico)
        if total > 0:
            # Reutiliza logica de visualização
            dados_visitado['data'] = dados_visitado['data'].astype(str)
            dados_visitado['hora'] = dados_visitado['hora'].astype(str)
            dados_visitado['datetime_full'] = pd.to_datetime(dados_visitado['data'] + ' ' + dados_visitado['hora'], errors='coerce')
            dados_visitado = dados_visitado.sort_values(by='datetime_full', ascending=False).head(10)
            
            for index, row in dados_visitado.iterrows():
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
        else:
            st.info("Este usuário ainda não registrou viagens.")


    # --- MODO PRINCIPAL (Minha Conta) ---
    else:
        aba_feed, aba_nova, aba_diario, aba_perfil = st.tabs(["📡 Atividade", "📝 Nova Viagem", "📓 Diário", "👤 Meu Perfil"])
        
        # --- ABA FEED (NOVA) ---
        with aba_feed:
            df_viagens = ler_arquivo_github(ARQUIVO_DB_VIAGENS, 'csv')
            if not df_viagens.empty:
                # Filtra: Eu + Quem eu sigo
                social_db = carregar_social()
                quem_sigo = social_db.get(meu_user, [])
                quem_sigo.append(meu_user) # Inclui eu mesmo no feed
                
                df_feed = df_viagens[df_viagens['usuario'].isin(quem_sigo)].copy()
                
                # Gera Feed Agrupado
                feed_items = agrupar_viagens_atividade(df_feed)
                
                if not feed_items:
                    st.info("Nenhuma atividade recente.")
                else:
                    # Carrega perfis para mostrar avatares
                    db_perfis = ler_arquivo_github(ARQUIVO_DB_PERFIL, 'json')
                    
                    for item in feed_items:
                        user_item = item['usuario']
                        viagens = item['viagens']
                        qtd = len(viagens)
                        viagem_principal = viagens[0] # A mais recente
                        
                        perfil_user = db_perfis.get(user_item, {})
                        avatar = perfil_user.get('avatar', '👤')
                        nome_display = perfil_user.get('display_name', user_item)
                        
                        # Cabeçalho do Card de Atividade
                        with st.container():
                            st.markdown(f"""
                            <div class="activity-card">
                                <div class="activity-header">
                                    <span class="user-avatar">{avatar}</span>
                                    <span class="user-name">{nome_display}</span>
                                    <span class="activity-time">{viagem_principal['datetime_full'].strftime('%d/%m %H:%M')}</span>
                                </div>
                            """, unsafe_allow_html=True)
                            
                            # Se for INTEGRAÇÃO (>1 onibus)
                            if qtd > 1:
                                with st.expander(f"🚌 {qtd} Ônibus • Integração (Clique para ver)"):
                                    for v in viagens:
                                        st.markdown(f"**{v['hora'][:5]}** - {v['linha']}")
                            else:
                                # Viagem unica
                                st.markdown(f"<div style='color:#fff; font-weight:bold; font-size:16px; margin-left:30px;'>{viagem_principal['linha']}</div>", unsafe_allow_html=True)
                                if pd.notna(viagem_principal['obs']) and viagem_principal['obs']:
                                    st.markdown(f"<div style='color:#888; font-size:12px; margin-left:30px;'>📝 {viagem_principal['obs']}</div>", unsafe_allow_html=True)
                            
                            st.markdown("</div>", unsafe_allow_html=True) # Fecha card
            else:
                st.info("O feed está vazio.")

        # --- ABA REGISTRO ---
        with aba_nova:
            key_atual = st.session_state["form_key"]
            with st.form(f"nova_viagem_{key_atual}"):
                c1, c2 = st.columns(2)
                data = c1.date_input("Data", agora_br(), format="DD/MM/YYYY") 
                hora = c2.time_input("Hora", value=datetime_time(0, 0))
                linha = st.selectbox("Linha", [""] + lista_linhas)
                st.markdown('<div class="privacy-warning">⚠ Atenção: Este diário é público.</div>', unsafe_allow_html=True)
                obs = st.text_area("Observações", height=68, max_chars=50)
                
                if st.form_submit_button("Salvar Viagem", use_container_width=True):
                    if not linha: st.error("Escolha a linha!")
                    else:
                        with st.spinner("Salvando..."):
                            df_antigo = ler_arquivo_github(ARQUIVO_DB_VIAGENS, 'csv')
                            novo_dado = { "usuario": meu_user, "linha": linha, "data": str(data), "hora": str(hora)[:5], "obs": obs, "timestamp": str(agora_br()) }
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

        # --- ABA DIÁRIO (Manteve igual) ---
        with aba_diario:
            df = ler_arquivo_github(ARQUIVO_DB_VIAGENS, 'csv')
            if not df.empty:
                df_filtered = df[df['usuario'] == meu_user].copy()
                df_filtered['data'] = df_filtered['data'].astype(str)
                df_filtered['hora'] = df_filtered['hora'].astype(str)
                df_filtered['datetime_full'] = pd.to_datetime(df_filtered['data'] + ' ' + df_filtered['hora'], errors='coerce')
                df_filtered = df_filtered.dropna(subset=['datetime_full'])
                
                filtro_tempo = st.pills("Período:", ["Tudo", "7 Dias", "30 Dias", "Este Ano"], default="Tudo")
                hoje = agora_br()
                if filtro_tempo == "7 Dias": df_filtered = df_filtered[df_filtered['datetime_full'] >= (hoje - timedelta(days=7))]
                elif filtro_tempo == "30 Dias": df_filtered = df_filtered[df_filtered['datetime_full'] >= (hoje - timedelta(days=30))]
                elif filtro_tempo == "Este Ano": df_filtered = df_filtered[df_filtered['datetime_full'].dt.year == hoje.year]
                
                df_filtered = df_filtered.sort_values(by='datetime_full', ascending=False)
                total_registros = len(df_filtered)
                limite = st.session_state["limite_registros"]
                df_view = df_filtered.head(limite)
                
                df_view['ano'] = df_view['datetime_full'].dt.year
                df_view['mes'] = df_view['datetime_full'].dt.month
                grupos = df_view.groupby(['ano', 'mes'], sort=False)
                
                if df_filtered.empty: st.info("Nenhuma viagem.")
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
                                </div>"""
                                st.markdown(card_html, unsafe_allow_html=True)
                            with col_del:
                                if st.button("❌", key=f"del_{index}"):
                                    with st.spinner("Apagando..."):
                                        if excluir_registro(index):
                                            st.success("Apagado!")
                                            time.sleep(1)
                                            st.rerun()
                    if total_registros > limite:
                        if st.button(f"Carregar mais ({total_registros - limite})"):
                            st.session_state["limite_registros"] += 10 
                            st.rerun()
            else: st.info("Comece a catalogar!")

        # --- ABA PERFIL ---
        with aba_perfil:
            perfil = carregar_perfil(meu_user)
            segs, segds = get_seguidores_count(meu_user)
            
            if "editando_perfil" not in st.session_state: st.session_state["editando_perfil"] = False
            
            if not st.session_state["editando_perfil"]:
                st.markdown(f"""
                <div class="profile-header">
                    <div class="avatar">{perfil.get('avatar', '👤')}</div>
                    <div class="display-name">{perfil.get('display_name', meu_user)}</div>
                    <div class="username-tag">@{meu_user}</div>
                    <div class="bio-text">"{perfil.get('bio', '')}"</div>
                </div>
                """, unsafe_allow_html=True)
                
                col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                col_s1.metric("Seguidores", segs)
                col_s2.metric("Seguindo", segds)
                
                df_viagens = ler_arquivo_github(ARQUIVO_DB_VIAGENS, 'csv')
                if not df_viagens.empty:
                    meus_dados = df_viagens[df_viagens['usuario'] == meu_user]
                    total = len(meus_dados)
                    linha_fav = meus_dados['linha'].mode()[0] if not meus_dados.empty else "-"
                else:
                    total = 0
                    linha_fav = "-"
                
                col_s3.metric("Total", total)
                
                # HTML CARD PARA LINHA FAVORITA (CORRIGIDO PARA NÃO CORTAR TEXTO)
                col_s4.markdown(f"""
                    <div class="stat-box">
                        <div class="stat-label">Linha Favorita</div>
                        <div class="stat-value-small">{linha_fav}</div>
                    </div>
                """, unsafe_allow_html=True)

                if st.button("Editar Perfil"):
                    st.session_state["editando_perfil"] = True
                    st.rerun()
            else:
                with st.form("form_perfil"):
                    st.write("### Editando Perfil")
                    novo_nome = st.text_input("Nome de Exibição", value=perfil.get('display_name', ''))
                    nova_bio = st.text_area("Bio", value=perfil.get('bio', ''), max_chars=100)
                    opcoes_avatar = ["👤", "🚌", "🚍", "🚏", "🎫", "😎", "🤠", "👽", "👾", "🤖", "🐱", "🐶"]
                    idx_atual = opcoes_avatar.index(perfil.get('avatar')) if perfil.get('avatar') in opcoes_avatar else 0
                    novo_avatar = st.selectbox("Avatar", opcoes_avatar, index=idx_atual)
                    
                    c_salvar, c_cancelar = st.columns(2)
                    with c_salvar:
                        if st.form_submit_button("Salvar"):
                            salvar_perfil_editado(meu_user, novo_nome, nova_bio, novo_avatar)
                            st.success("Atualizado!")
                            st.session_state["editando_perfil"] = False
                            time.sleep(1)
                            st.rerun()
                    with c_cancelar:
                         if st.form_submit_button("Cancelar"):
                             st.session_state["editando_perfil"] = False
                             st.rerun()

# --- LOGIN / CADASTRO (IGUAL ANTES) ---
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
                else: st.error("Dados incorretos.")
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

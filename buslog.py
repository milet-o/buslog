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
    /* TEXTOS CLAROS */
    h1, h2, h3, h4, h5, h6, p, span, label, .stMarkdown, .stText, div[data-testid="stMetricValue"] { color: #e0e0e0 !important; }
    .stTextInput > label, .stSelectbox > label, .stDateInput > label, .stTimeInput > label, .stTextArea > label { color: #e0e0e0 !important; }
    
    /* FUNDO */
    .stApp {
        background-color: #0e1117;
        background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='0.05'/%3E%3C/svg%3E");
        background-attachment: fixed;
    }
    
    [data-testid="InputInstructions"] { display: none; }
    
    /* HEADER MÊS */
    .month-header {
        font-size: 14px; font-weight: 600; color: #aaa !important; margin-top: 20px;
        margin-bottom: 10px; text-transform: uppercase; letter-spacing: 2px;
        border-bottom: 1px solid #333; padding-bottom: 5px;
    }

    /* CARD DIÁRIO */
    .journal-card {
        display: flex; background-color: #1c1c1e; border-radius: 6px; margin-bottom: 8px;
        border: 1px solid #333; align-items: stretch; min-height: 75px; 
        transition: all 0.2s ease; overflow: hidden; 
    }
    .journal-card:hover { transform: translateX(2px); border-color: #555; background-color: #252528; }

    /* CARD FEED */
    .activity-card {
        background-color: #161618; border: 1px solid #333; border-radius: 8px;
        padding: 12px; margin-bottom: 12px;
    }
    .activity-header { display: flex; align-items: center; margin-bottom: 8px; }
    .user-avatar { font-size: 20px; margin-right: 8px; }
    .user-name { font-weight: bold; color: #fff; font-size: 15px; }
    .activity-time { font-size: 12px; color: #888; margin-left: auto; }

    /* COMPONENTES DO CARD */
    .strip { width: 5px; background-color: #FF4B4B; flex-shrink: 0; }
    .date-col { width: 50px; display: flex; align-items: center; justify-content: center; font-size: 20px; color: #eee !important; flex-shrink: 0; }
    .info-col { flex-grow: 1; padding: 8px 12px; display: flex; flex-direction: column; justify-content: center; min-width: 0; }
    .bus-line { font-size: 16px; font-weight: 700; color: #fff !important; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .meta-info { font-size: 12px; color: #aaa !important; margin-top: 2px; }
    
    .privacy-warning { font-size: 12px; color: #ff6c6c !important; margin-bottom: 5px; font-weight: 500; }
    div[data-testid="column"] button { margin-top: 15px; }

    /* PERFIL */
    .profile-header {
        background-color: #1c1c1e; padding: 20px; border-radius: 10px;
        border: 1px solid #333; text-align: center; margin-bottom: 20px;
    }
    .avatar { font-size: 60px; margin-bottom: 10px; }
    .display-name { font-size: 24px; font-weight: bold; color: #fff; }
    .username-tag { font-size: 14px; color: #888; margin-bottom: 10px; }
    .bio-text { font-size: 14px; color: #ccc; font-style: italic; }
    
    .stat-box {
        background-color: #262730; padding: 10px; border-radius: 6px;
        text-align: center; border: 1px solid #333; height: 100%; display: flex; flex-direction: column; justify-content: center;
    }
    .stat-label { font-size: 11px; color: #888; text-transform: uppercase; margin-bottom: 5px; }
    .stat-value { font-size: 20px; font-weight: bold; color: #fff; }
    .stat-value-small { font-size: 14px; font-weight: bold; color: #fff; word-wrap: break-word; line-height: 1.2; }
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
ARQUIVO_DB_SOCIAL = "social.json"
ARQUIVO_ROTAS = "rotasrj.json"

# --- ESTADO DE SESSÃO ---
if "form_key" not in st.session_state: st.session_state["form_key"] = 0
if "limite_registros" not in st.session_state: st.session_state["limite_registros"] = 10
if "perfil_visitado" not in st.session_state: st.session_state["perfil_visitado"] = None

# --- FUNÇÕES ---
def agora_br(): return datetime.utcnow() - timedelta(hours=3)

def get_repo(): return Github(GITHUB_TOKEN).get_repo(REPO_NAME)

def ler_arquivo_github(nome_arquivo, tipo='json'):
    try:
        repo = get_repo()
        contents = repo.get_contents(nome_arquivo)
        decodificado = contents.decoded_content.decode("utf-8")
        if tipo == 'json': return json.loads(decodificado)
        else: return pd.read_csv(io.StringIO(decodificado))
    except: return {} if tipo == 'json' else pd.DataFrame()

def atualizar_arquivo_github(nome_arquivo, conteudo, mensagem_commit):
    repo = get_repo()
    try:
        contents = repo.get_contents(nome_arquivo)
        repo.update_file(contents.path, mensagem_commit, conteudo, contents.sha)
    except:
        repo.create_file(nome_arquivo, mensagem_commit, conteudo)

def hash_senha(password): return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
def verificar_senha(password, hashed): return bcrypt.checkpw(password.encode(), hashed.encode())

# --- SOCIAL & PERFIL ---
def carregar_social(): return ler_arquivo_github(ARQUIVO_DB_SOCIAL, 'json')

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
        if usuario in lista: seguidores += 1
    return seguidores, seguindo

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

# --- LÓGICA FEED ---
def agrupar_viagens_atividade(df_viagens):
    if df_viagens.empty: return []
    df_viagens['datetime_full'] = pd.to_datetime(df_viagens['data'].astype(str) + ' ' + df_viagens['hora'].astype(str), errors='coerce')
    df_viagens = df_viagens.dropna(subset=['datetime_full'])
    df_viagens = df_viagens.sort_values(by=['usuario', 'datetime_full'], ascending=[True, False])
    
    feed_items = []
    for usuario, grupo_user in df_viagens.groupby('usuario'):
        grupo_user = grupo_user.sort_values('datetime_full', ascending=True)
        viagens_user = grupo_user.to_dict('records')
        if not viagens_user: continue
        
        clusters = []
        cluster_atual = [viagens_user[0]]
        for i in range(1, len(viagens_user)):
            viagem = viagens_user[i]
            ultima = cluster_atual[-1]
            if (viagem['datetime_full'] - ultima['datetime_full']) <= timedelta(hours=2):
                cluster_atual.append(viagem)
            else:
                clusters.append(cluster_atual)
                cluster_atual = [viagem]
        clusters.append(cluster_atual)
        
        for cluster in clusters:
            feed_items.append({ "usuario": usuario, "datetime_ref": cluster[-1]['datetime_full'], "viagens": cluster[::-1] })
            
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
    return True, "Conta criada!"

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
            st.markdown(f"""<audio autoplay><source src="data:audio/mp4;base64,{b64}" type="audio/mp4"></audio>""", unsafe_allow_html=True)
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
    
    # SIDEBAR: Busca e Menu
    with st.sidebar:
        st.write(f"Olá, **busólogo**!")
        st.caption(f"Logado como: @{meu_user}")
        
        st.markdown("---")
        st.write("🔍 **Buscar Usuário**")
        termo_busca = st.text_input("Digite o nome:", placeholder="Ex: maria").lower().strip()
        
        # Lógica de Busca (Sempre ativa)
        if termo_busca:
            db_perfis = ler_arquivo_github(ARQUIVO_DB_PERFIL, 'json')
            # Busca nas chaves (user) e no display name
            resultados = [u for u in db_perfis.keys() if termo_busca in u or termo_busca in db_perfis[u].get('display_name', '').lower()]
            
            if resultados:
                st.caption(f"{len(resultados)} encontrados:")
                for res in resultados:
                    # Botão para visitar
                    if st.button(f"👤 {db_perfis[res].get('display_name', res)}", key=f"btn_search_{res}", use_container_width=True):
                        st.session_state["perfil_visitado"] = res
                        st.rerun()
            else:
                st.warning("Ninguém encontrado.")
        
        st.markdown("---")
        if st.button("🏠 Início", use_container_width=True):
            st.session_state["perfil_visitado"] = None
            st.rerun()
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state["logado"] = False
            st.rerun()

    # --- MODO VISITANTE ---
    if st.session_state["perfil_visitado"]:
        visitado = st.session_state["perfil_visitado"]
        dados_perfil = carregar_perfil(visitado)
        
        # Header Visitante
        if st.button("⬅ Voltar ao Início"):
            st.session_state["perfil_visitado"] = None
            st.rerun()
            
        social_db = carregar_social()
        seguindo_lista = social_db.get(meu_user, [])
        eh_seguido = visitado in seguindo_lista
        
        # Botão Seguir (Só se não for eu mesmo)
        if visitado != meu_user:
            btn_txt = "Deixar de Seguir" if eh_seguido else "Seguir"
            btn_type = "primary" if not eh_seguido else "secondary"
            if st.button(btn_txt, type=btn_type, use_container_width=True):
                with st.spinner("Atualizando social..."):
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
        
        # Stats Visitado
        df_viagens = ler_arquivo_github(ARQUIVO_DB_VIAGENS, 'csv')
        segs, segds = get_seguidores_count(visitado)
        col1, col2, col3, col4 = st.columns(4)
        col1.markdown(f"<div class='stat-box'><div class='stat-label'>Seguidores</div><div class='stat-value'>{segs}</div></div>", unsafe_allow_html=True)
        col2.markdown(f"<div class='stat-box'><div class='stat-label'>Seguindo</div><div class='stat-value'>{segds}</div></div>", unsafe_allow_html=True)
        
        total, linha_fav = 0, "-"
        if not df_viagens.empty:
            dv = df_viagens[df_viagens['usuario'] == visitado]
            total = len(dv)
            if not dv.empty: linha_fav = dv['linha'].mode()[0]
            
        col3.markdown(f"<div class='stat-box'><div class='stat-label'>Viagens</div><div class='stat-value'>{total}</div></div>", unsafe_allow_html=True)
        col4.markdown(f"<div class='stat-box'><div class='stat-label'>Linha Fav.</div><div class='stat-value-small'>{linha_fav}</div></div>", unsafe_allow_html=True)
        
        st.write("")
        st.markdown("### 📓 Diário Público")
        if total > 0:
            dv['datetime_full'] = pd.to_datetime(dv['data'].astype(str) + ' ' + dv['hora'].astype(str), errors='coerce')
            dv = dv.sort_values(by='datetime_full', ascending=False).head(10)
            for _, row in dv.iterrows():
                obs = f" • {row['obs']}" if pd.notna(row['obs']) and row['obs'] else ""
                st.markdown(f"""
                <div class="journal-card">
                    <div class="strip"></div><div class="date-col">{row['datetime_full'].day}</div>
                    <div class="info-col"><div class="bus-line">{row['linha']}</div><div class="meta-info">🕒 {str(row['hora'])[:5]}{obs}</div></div>
                </div>""", unsafe_allow_html=True)
        else: st.info("Sem registros públicos.")

    # --- MODO PRINCIPAL ---
    else:
        aba_feed, aba_nova, aba_diario, aba_perfil = st.tabs(["📡 Atividade", "📝 Nova Viagem", "📓 Diário", "👤 Meu Perfil"])
        
        with aba_feed:
            df_viagens = ler_arquivo_github(ARQUIVO_DB_VIAGENS, 'csv')
            if not df_viagens.empty:
                social_db = carregar_social()
                quem_sigo = social_db.get(meu_user, [])
                
                if not quem_sigo:
                    st.info("Você não segue ninguém ainda. Use a busca na lateral!")
                else:
                    # FILTRO CORRIGIDO: Exclui meu_user, mostra só quem sigo
                    df_feed = df_viagens[df_viagens['usuario'].isin(quem_sigo)].copy()
                    feed_items = agrupar_viagens_atividade(df_feed)
                    
                    if not feed_items: st.info("Seus amigos ainda não postaram nada.")
                    else:
                        db_perfis = ler_arquivo_github(ARQUIVO_DB_PERFIL, 'json')
                        for item in feed_items:
                            u, viags = item['usuario'], item['viagens']
                            perf = db_perfis.get(u, {})
                            # Card Feed
                            with st.container():
                                st.markdown(f"""
                                <div class="activity-card">
                                    <div class="activity-header">
                                        <span class="user-avatar">{perf.get('avatar', '👤')}</span>
                                        <span class="user-name">{perf.get('display_name', u)}</span>
                                        <span class="activity-time">{viags[0]['datetime_full'].strftime('%d/%m %H:%M')}</span>
                                    </div>
                                """, unsafe_allow_html=True)
                                if len(viags) > 1:
                                    with st.expander(f"🚌 {len(viags)} Ônibus (Integração)"):
                                        for v in viags: st.markdown(f"**{v['hora'][:5]}** - {v['linha']}")
                                else:
                                    v = viags[0]
                                    obs = f"<div style='color:#888; font-size:12px; margin-left:30px;'>📝 {v['obs']}</div>" if pd.notna(v['obs']) and v['obs'] else ""
                                    st.markdown(f"<div style='color:#fff; font-weight:bold; font-size:16px; margin-left:30px;'>{v['linha']}</div>{obs}", unsafe_allow_html=True)
                                st.markdown("</div>", unsafe_allow_html=True)
            else: st.info("Feed vazio.")

        with aba_nova:
            k = st.session_state["form_key"]
            with st.form(f"n_{k}"):
                c1, c2 = st.columns(2)
                data = c1.date_input("Data", agora_br(), format="DD/MM/YYYY") 
                hora = c2.time_input("Hora", value=datetime_time(0, 0))
                linha = st.selectbox("Linha", [""] + lista_linhas)
                st.markdown('<div class="privacy-warning">⚠ Atenção: Este diário é público.</div>', unsafe_allow_html=True)
                obs = st.text_area("Obs", height=68, max_chars=50)
                if st.form_submit_button("Salvar Viagem", use_container_width=True):
                    if not linha: st.error("Escolha a linha!")
                    else:
                        with st.spinner("Salvando..."):
                            old = ler_arquivo_github(ARQUIVO_DB_VIAGENS, 'csv')
                            new = pd.DataFrame([{ "usuario": meu_user, "linha": linha, "data": str(data), "hora": str(hora)[:5], "obs": obs, "timestamp": str(agora_br()) }])
                            final = pd.concat([old, new], ignore_index=True)
                            final['dt'] = pd.to_datetime(final['data'].astype(str)+' '+final['hora'].astype(str), errors='coerce')
                            final = final.sort_values(by=['usuario', 'dt'], ascending=[True, False]).drop(columns=['dt'])
                            atualizar_arquivo_github(ARQUIVO_DB_VIAGENS, final.to_csv(index=False), "Nova")
                            tocar_buzina()
                            st.success("Salvo!"); st.session_state["form_key"]+=1; time.sleep(1); st.rerun()

        with aba_diario:
            df = ler_arquivo_github(ARQUIVO_DB_VIAGENS, 'csv')
            if not df.empty:
                dff = df[df['usuario'] == meu_user].copy()
                dff['dt'] = pd.to_datetime(dff['data'].astype(str)+' '+dff['hora'].astype(str), errors='coerce')
                dff = dff.dropna(subset=['dt']).sort_values(by='dt', ascending=False)
                
                ft = st.pills("Filtro:", ["Tudo", "7 Dias", "30 Dias", "Este Ano"], default="Tudo")
                h = agora_br()
                if ft=="7 Dias": dff=dff[dff['dt']>=(h-timedelta(days=7))]
                elif ft=="30 Dias": dff=dff[dff['dt']>=(h-timedelta(days=30))]
                elif ft=="Este Ano": dff=dff[dff['dt'].dt.year==h.year]
                
                lim = st.session_state["limite_registros"]
                view = dff.head(lim)
                if dff.empty: st.info("Nada aqui.")
                else:
                    for (y, m), g in view.groupby([view['dt'].dt.year, view['dt'].dt.month], sort=False):
                        st.markdown(f"<div class='month-header'>{MESES_PT[m]} {y}</div>", unsafe_allow_html=True)
                        for i, r in g.iterrows():
                            o = f" • {r['obs']}" if pd.notna(r['obs']) and r['obs'] else ""
                            c1, c2 = st.columns([0.88, 0.12])
                            c1.markdown(f"""<div class="journal-card"><div class="strip"></div><div class="date-col">{r['dt'].day}</div><div class="info-col"><div class="bus-line">{r['linha']}</div><div class="meta-info">🕒 {str(r['hora'])[:5]}{o}</div></div></div>""", unsafe_allow_html=True)
                            if c2.button("❌", key=f"d_{i}"):
                                with st.spinner("..."): 
                                    if excluir_registro(i): st.rerun()
                    if len(dff) > lim:
                        if st.button("Carregar +"): st.session_state["limite_registros"]+=10; st.rerun()
            else: st.info("Vazio.")

        with aba_perfil:
            p = carregar_perfil(meu_user)
            s1, s2 = get_seguidores_count(meu_user)
            if "edit_p" not in st.session_state: st.session_state["edit_p"] = False
            
            if not st.session_state["edit_p"]:
                st.markdown(f"""<div class="profile-header"><div class="avatar">{p.get('avatar','👤')}</div><div class="display-name">{p.get('display_name', meu_user)}</div><div class="username-tag">@{meu_user}</div><div class="bio-text">"{p.get('bio','')}"</div></div>""", unsafe_allow_html=True)
                c1, c2, c3, c4 = st.columns(4)
                c1.markdown(f"<div class='stat-box'><div class='stat-label'>Seguidores</div><div class='stat-value'>{s1}</div></div>", unsafe_allow_html=True)
                c2.markdown(f"<div class='stat-box'><div class='stat-label'>Seguindo</div><div class='stat-value'>{s2}</div></div>", unsafe_allow_html=True)
                
                dfv = ler_arquivo_github(ARQUIVO_DB_VIAGENS, 'csv')
                tot, fav = 0, "-"
                if not dfv.empty:
                    dm = dfv[dfv['usuario']==meu_user]
                    tot = len(dm)
                    if not dm.empty: fav = dm['linha'].mode()[0]
                
                c3.markdown(f"<div class='stat-box'><div class='stat-label'>Viagens</div><div class='stat-value'>{tot}</div></div>", unsafe_allow_html=True)
                c4.markdown(f"<div class='stat-box'><div class='stat-label'>Linha Fav.</div><div class='stat-value-small'>{fav}</div></div>", unsafe_allow_html=True)
                
                if st.button("Editar Perfil"): st.session_state["edit_p"] = True; st.rerun()
            else:
                with st.form("fp"):
                    nn = st.text_input("Nome", value=p.get('display_name',''))
                    nb = st.text_area("Bio", value=p.get('bio',''), max_chars=100)
                    avs = ["👤", "🚌", "🚍", "🚏", "🎫", "😎", "🤠", "👽", "👾", "🤖", "🐱", "🐶"]
                    na = st.selectbox("Avatar", avs, index=avs.index(p.get('avatar')) if p.get('avatar') in avs else 0)
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("Salvar"):
                        with st.spinner("Salvando..."): salvar_perfil_editado(meu_user, nn, nb, na); st.session_state["edit_p"]=False; st.rerun()
                    if c2.form_submit_button("Cancelar"): st.session_state["edit_p"]=False; st.rerun()

else:
    tab1, tab2 = st.tabs(["Entrar", "Criar Conta"])
    with tab1:
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type="password")
        if st.button("ENTRAR", use_container_width=True):
            with st.spinner("..."):
                if fazer_login(u, p): st.session_state["logado"]=True; st.session_state["usuario_atual"]=u.lower().strip(); st.rerun()
                else: st.error("Erro.")
    with tab2:
        st.warning("⚠ Anote sua senha!")
        cu = st.text_input("Usuário novo")
        cp = st.text_input("Senha nova", type="password")
        cp2 = st.text_input("Confirme", type="password")
        if st.button("CRIAR", use_container_width=True):
            if cp!=cp2: st.error("Senhas não batem")
            elif len(cp)<4: st.error("Curta demais")
            elif not cu: st.error("Digite user")
            else:
                with st.spinner("Criando..."):
                    suc, msg = registrar_usuario(cu, cp)
                    if suc: st.success(msg)
                    else: st.error(msg)

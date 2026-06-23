from datetime import datetime
import streamlit as st
import pandas as pd

# =========================
# LOGO DIESP - SVG INLINE
# =========================
DIESP_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 120" width="140" height="84">
    <rect width="200" height="120" fill="white" rx="10"/>
    <text x="100" y="22" font-family="Arial Black,Arial" font-weight="900" font-size="22"
          fill="#f39a1f" text-anchor="middle" letter-spacing="6">DIESP</text>
    <ellipse cx="100" cy="70" rx="62" ry="36" fill="none" stroke="#2e6b3e" stroke-width="4"/>
    <line x1="38" y1="70" x2="28" y2="60" stroke="#2e6b3e" stroke-width="3" stroke-linecap="round"/>
    <line x1="162" y1="70" x2="172" y2="60" stroke="#2e6b3e" stroke-width="3" stroke-linecap="round"/>
    <circle cx="100" cy="70" r="26" fill="#2e6b3e"/>
    <circle cx="100" cy="70" r="18" fill="#5a9e6f"/>
    <circle cx="108" cy="74" r="12" fill="#1a4a2a"/>
    <circle cx="105" cy="76" r="8" fill="#0d2d18"/>
    <circle cx="96" cy="67" r="3" fill="white" opacity="0.7"/>
    <circle cx="115" cy="80" r="10" fill="none" stroke="white" stroke-width="2.5"/>
    <line x1="122" y1="87" x2="130" y2="95" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
    <text x="100" y="112" font-family="Arial" font-size="7" fill="#2e6b3e"
          text-anchor="middle" font-weight="700">DIRETORIA DE ESTRATEGIA DE SEG. PUBLICA</text>
</svg>
"""

DIESP_SVG_B64 = "data:image/svg+xml;base64," + __import__('base64').b64encode(DIESP_SVG.encode()).decode()

# =========================
# CONFIGURACAO DA PAGINA
# =========================
st.set_page_config(
    page_title="QGP Online - SUPESP/CE",
    page_icon="\U0001f6e1",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# CSS CUSTOMIZADO
# =========================
def load_custom_css():
    st.markdown("""
        <style>
        .stApp {
            background: linear-gradient(180deg, #022b26 0%, #011917 100%);
            color: #f3f4ef;
        }
        section[data-testid="stSidebar"] {
            background: #031f1b;
            border-right: 3px solid #d88a18;
        }
        section[data-testid="stSidebar"] * {
            color: #f3f4ef !important;
        }
        .topbar {
            display: flex;
            align-items: center;
            gap: 14px;
            margin-bottom: 1rem;
            padding: 0.4rem 0 0.8rem 0;
            border-bottom: 1px solid rgba(216,138,24,0.18);
        }
        .topbar-title {
            font-size: 1.9rem;
            font-weight: 800;
            color: #ffffff;
            line-height: 1.05;
            margin: 0;
        }
        .topbar-subtitle {
            font-size: 0.95rem;
            font-weight: 700;
            color: #f39a1f;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-top: 0.25rem;
        }
        .sidebar-brand {
            text-align: center;
            margin-top: 0.4rem;
            margin-bottom: 1.2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid rgba(216,138,24,0.14);
        }
        .sidebar-brand img {
            width: 130px;
            max-width: 100%;
            border-radius: 10px;
            border: 1px solid rgba(243,154,31,0.25);
            margin-bottom: 0.5rem;
            background: #ffffff;
            padding: 4px;
        }
        .sidebar-brand-title {
            color: #f3f4ef;
            font-size: 1.06rem;
            font-weight: 800;
            margin-bottom: 0.2rem;
        }
        .sidebar-brand-subtitle {
            color: #cfd7d2;
            font-size: 0.84rem;
            font-weight: 500;
        }
        .stButton > button {
            background: #f39a1f !important;
            color: #16211d !important;
            border: none !important;
            border-radius: 12px !important;
            font-weight: 800 !important;
            padding: 0.75rem 1.15rem !important;
        }
        .stButton > button:hover {
            background: #ffae34 !important;
            color: #101816 !important;
        }
        .metric-chip {
            display: inline-block;
            background: rgba(243,154,31,0.12);
            color: #ffd089;
            border: 1px solid rgba(243,154,31,0.22);
            border-radius: 999px;
            padding: 0.35rem 0.8rem;
            font-size: 0.85rem;
            font-weight: 700;
            margin-right: 0.5rem;
            margin-bottom: 0.5rem;
        }
        .footer-note {
            color: #b8c3bd;
            font-size: 0.9rem;
            margin-top: 1rem;
            text-align: center;
        }
        </style>
    """, unsafe_allow_html=True)

# =========================
# TOPBAR
# =========================
def render_topbar():
    st.markdown(f"""
        <div class="topbar">
            <div>
                <div class="topbar-title">QGP Online</div>
                <div class="topbar-subtitle">SUPESP / CE &middot; Atualizador de Indicadores</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# =========================
# SIDEBAR BRAND
# =========================
def render_sidebar_brand():
    with st.sidebar:
        st.markdown(f"""
            <div class="sidebar-brand">
                <img src="{DIESP_SVG_B64}" alt="Logo DIESP">
                <div class="sidebar-brand-title">SUPESP / CE</div>
                <div class="sidebar-brand-subtitle">Sistema Integrado de Gestao e Inteligencia</div>
            </div>
        """, unsafe_allow_html=True)

# =========================
# INICIALIZACAO
# =========================
load_custom_css()
render_sidebar_brand()
render_topbar()

# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.markdown("### Painel de Controle")
    indicador = st.selectbox(
        "Selecione o Indicador",
        [
            "Selecione um indicador...",
            "CVLI",
            "CVP (SPORTAL)",
            "CVP (SIP)",
            "PERTURBACAO DO SOSSEGO ALHEIO",
            "DESLOCAMENTO FORCADO",
            "ROUBO DE VEICULO (SPORTAL)",
            "ROUBO DE VEICULO (SIP)",
            "ACIDENTE DE TRANSITO",
            "FURTO (SPORTAL)",
            "FURTO (SIP)",
            "TODOS OS INDICADORES",
        ],
    )

    salvar_drive = st.checkbox("\U0001f4c2 Salvar no Google Drive")

    st.markdown("### Informacoes")
    st.markdown(f'<div class="metric-chip">Versao 1.0.0</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-chip">Data {datetime.now().strftime("%d/%m/%Y")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-chip">Hora {datetime.now().strftime("%H:%M:%S")}</div>', unsafe_allow_html=True)

# =========================
# CONTEUDO PRINCIPAL
# =========================
st.markdown("## Upload de Arquivos")
col_up1, col_up2 = st.columns([1, 1])

with col_up1:
    arquivo_02 = st.file_uploader(
        "Arquivo 02 (planilha com multiplas abas)",
        type=["xlsx", "xls"]
    )

with col_up2:
    arquivos_01 = st.file_uploader(
        "Arquivos 01 (um ou varios)",
        type=["xlsx", "xls"],
        accept_multiple_files=True
    )

processar = st.button("\u25b6\ufe0f Processar Indicador")

# =========================
# PROCESSAMENTO
# =========================
if processar:
    erros = []

    if indicador == "Selecione um indicador...":
        erros.append("Selecione um indicador valido.")

    if arquivo_02 is None:
        erros.append("Envie o Arquivo 02.")

    if not arquivos_01:
        erros.append("Envie pelo menos um Arquivo 01.")

    if erros:
        for erro in erros:
            st.error(erro)
    else:
        st.success("Arquivos recebidos com sucesso.")
        st.write(f"**Indicador selecionado:** {indicador}")
        st.write(f"**Salvar no Google Drive:** {'Sim' if salvar_drive else 'Nao'}")
        st.write(f"**Arquivo 02:** {arquivo_02.name}")
        st.write("**Arquivos 01 carregados:**")
        for arq in arquivos_01:
            st.write(f"- {arq.name}")

        try:
            df_preview = pd.read_excel(arquivo_02)
            st.info("Pre-visualizacao do Arquivo 02")
            st.dataframe(df_preview.head())
        except Exception as exc:
            st.warning(f"Nao foi possivel gerar preview: {exc}")

# =========================
# RODAPE
# =========================
st.markdown(
    '<div class="footer-note">QGP Online &mdash; Atualizador de Indicadores de Seguranca Publica &mdash; SUPESP/CE</div>',
    unsafe_allow_html=True
)

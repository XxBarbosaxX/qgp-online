from pathlib import Path
import base64
from datetime import datetime
import streamlit as st
import pandas as pd


st.set_page_config(
    page_title="QGP Online - SUPESP/CE",
    layout="wide",
    initial_sidebar_state="expanded"
)


def image_to_base64(image_path: str) -> str:
    path = Path(image_path)
    if not path.exists():
        return ""
    return base64.b64encode(path.read_bytes()).decode("utf-8")


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
            border-bottom: 1px solid rgba(216, 138, 24, 0.18);
        }

        .topbar-logo {
            width: 58px;
            height: 58px;
            object-fit: cover;
            border-radius: 10px;
            border: 1px solid rgba(243, 154, 31, 0.35);
            background: #ffffff;
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
            border-bottom: 1px solid rgba(216, 138, 24, 0.14);
        }

        .sidebar-brand img {
            width: 118px;
            max-width: 100%;
            border-radius: 12px;
            border: 1px solid rgba(243, 154, 31, 0.25);
            margin-bottom: 0.65rem;
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

        .section-title {
            font-size: 2rem;
            font-weight: 800;
            color: #ffffff;
            margin-bottom: 0.1rem;
        }

        .section-subtitle {
            font-size: 1rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            color: #f39a1f;
            text-transform: uppercase;
            margin-bottom: 1.8rem;
        }

        .custom-card {
            background: rgba(4, 58, 50, 0.92);
            border: 1px solid rgba(216, 138, 24, 0.16);
            border-radius: 22px;
            padding: 1.4rem 1.4rem 1.2rem 1.4rem;
            box-shadow: 0 10px 24px rgba(0, 0, 0, 0.18);
            margin-bottom: 1rem;
        }

        .custom-card h3 {
            color: #ffffff;
            margin-bottom: 0.75rem;
            font-size: 1.25rem;
            font-weight: 800;
        }

        .custom-card p {
            color: #d5ddd8;
            line-height: 1.65;
            font-size: 0.98rem;
            margin-bottom: 0;
        }

        .status-box {
            background: rgba(3, 46, 40, 0.85);
            border: 1px dashed rgba(216, 138, 24, 0.28);
            border-radius: 18px;
            padding: 1rem 1.2rem;
            margin-top: 1rem;
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

        div[data-testid="stSelectbox"] > div,
        div[data-testid="stFileUploader"],
        div[data-testid="stTextInput"] > div {
            background: rgba(5, 47, 41, 0.55);
            border-radius: 14px;
        }

        .metric-chip {
            display: inline-block;
            background: rgba(243, 154, 31, 0.12);
            color: #ffd089;
            border: 1px solid rgba(243, 154, 31, 0.22);
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
        }
    </style>
    """, unsafe_allow_html=True)


def render_topbar(logo_base64: str):
    logo_html = ""
    if logo_base64:
        logo_html = f'<img src="data:image/jpeg;base64,{logo_base64}" class="topbar-logo">'
    st.markdown(
        f"""
        <div class="topbar">
            {logo_html}
            <div>
                <div class="topbar-title">QGP Online</div>
                <div class="topbar-subtitle">SUPESP / CE · Atualizador de Indicadores</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_sidebar_brand(logo_base64: str):
    logo_html = ""
    if logo_base64:
        logo_html = f'<img src="data:image/jpeg;base64,{logo_base64}" alt="Logo DIESP">'
    with st.sidebar:
        st.markdown(
            f"""
            <div class="sidebar-brand">
                {logo_html}
                <div class="sidebar-brand-title">SUPESP / CE</div>
                <div class="sidebar-brand-subtitle">Sistema Integrado de Gestão e Inteligência</div>
            </div>
            """,
            unsafe_allow_html=True
        )


LOGO_PATH = "assets/DIESP_nano_v3.jpg"
LOGO_BASE64 = image_to_base64(LOGO_PATH)

load_custom_css()
render_sidebar_brand(LOGO_BASE64)
render_topbar(LOGO_BASE64)

with st.sidebar:
    st.markdown("### Painel de Controle")
    indicador = st.selectbox(
        "Selecione o Indicador",
        [
            "Selecione um indicador...",
            "CVLI",
            "CVP (SPORTAL)",
            "CVP (SIP)",
            "PERTURBAÇÃO DO SOSSEGO ALHEIO",
            "DESLOCAMENTO FORÇADO",
            "ROUBO DE VEÍCULO (SPORTAL)",
            "ROUBO DE VEÍCULO (SIP)",
            "ACIDENTE DE TRÂNSITO",
            "FURTO (SPORTAL)",
            "FURTO (SIP)",
            "TODOS OS INDICADORES",
        ],
    )

    salvar_drive = st.checkbox("📂 Salvar no Google Drive")

    st.markdown("### Informações")
    st.markdown('<div class="metric-chip">Versão 1.0.0</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="metric-chip">Data {datetime.now().strftime("%d/%m/%Y")}</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        f'<div class="metric-chip">Hora {datetime.now().strftime("%H:%M:%S")}</div>',
        unsafe_allow_html=True
    )

st.markdown('<div class="section-title">Painel Estratégico</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-subtitle">Sistema Integrado de Gestão e Inteligência</div>',
    unsafe_allow_html=True
)

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    <div class="custom-card">
        <h3>Sobre a Plataforma</h3>
        <p>
            Aplicação web para atualização, tratamento e consolidação dos indicadores
            de segurança pública, com foco em padronização operacional, auditoria e
            escalabilidade da rotina técnica.
        </p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="custom-card">
        <h3>Processamento Inteligente</h3>
        <p>
            O sistema foi estruturado para receber planilhas, validar entradas,
            processar indicadores e futuramente integrar armazenamento automatizado
            com Google Drive e controle de execução online.
        </p>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="custom-card">
        <h3>Operação QGP</h3>
        <p>
            Interface institucional com foco em produtividade, visual estratégico e
            organização do fluxo de trabalho para atualização das bases e geração
            dos arquivos finais do QGP.
        </p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("## Upload de Arquivos")

col_up1, col_up2 = st.columns([1, 1])

with col_up1:
    arquivo_02 = st.file_uploader(
        "Arquivo 02 (planilha com múltiplas abas)",
        type=["xlsx", "xls"]
    )

with col_up2:
    arquivos_01 = st.file_uploader(
        "Arquivos 01 (um ou vários)",
        type=["xlsx", "xls"],
        accept_multiple_files=True
    )

processar = st.button("Processar Indicador")

if processar:
    erros = []

    if indicador == "Selecione um indicador...":
        erros.append("Selecione um indicador válido.")
    if arquivo_02 is None:
        erros.append("Envie o Arquivo 02.")
    if not arquivos_01:
        erros.append("Envie pelo menos um Arquivo 01.")

    if erros:
        for erro in erros:
            st.error(erro)
    else:
        st.success("Arquivos recebidos com sucesso.")
        st.markdown('<div class="status-box">', unsafe_allow_html=True)
        st.write(f"**Indicador selecionado:** {indicador}")
        st.write(f"**Salvar no Google Drive:** {'Sim' if salvar_drive else 'Não'}")
        st.write(f"**Arquivo 02:** {arquivo_02.name}")
        st.write("**Arquivos 01 carregados:**")
        for arq in arquivos_01:
            st.write(f"- {arq.name}")
        st.markdown("</div>", unsafe_allow_html=True)

        try:
            df_preview = pd.read_excel(arquivo_02)
            st.info("Pré-visualização do Arquivo 02")
            st.dataframe(df_preview.head())
        except Exception as exc:
            st.warning(f"Não foi possível gerar preview do Arquivo 02: {exc}")

st.markdown(
    '<div class="footer-note">QGP Online - Atualizador de Indicadores de Segurança Pública - SUPESP/CE</div>',
    unsafe_allow_html=True
)

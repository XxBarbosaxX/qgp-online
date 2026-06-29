# QGP Online - Atualizador de Indicadores de Segurança Pública - SUPESP/CE
# fix: set_page_config movido para o topo; imports lazy para evitar crash

import streamlit as st
from datetime import datetime
import sys
import os

# =========================
# CONFIGURAÇÃO DA PÁGINA (DEVE SER O PRIMEIRO COMANDO st.*)
# =========================
st.set_page_config(
    page_title="QGP Online - SUPESP/CE",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Adicionar pasta módulos ao path
sys.path.insert(0, os.path.dirname(__file__))  # Raiz do projeto para imports como 'from modulos.utils import'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'modulos'))

# =========================
# ESTADO DA APLICAÇÃO
# =========================
if "indicador_selecionado" not in st.session_state:
    st.session_state.indicador_selecionado = "Selecione um indicador..."

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
        display: none !important;
    }

    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
    }

    .topbar {
        display: flex;
        align-items: center;
        gap: 14px;
        margin-bottom: 1rem;
        padding: 0.4rem 0 0.8rem 0;
        border-bottom: 1px solid rgba(216, 138, 24, 0.18);
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

    .home-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(243, 154, 31, 0.14);
        border-radius: 18px;
        padding: 1.2rem 1.2rem 1rem 1.2rem;
        margin-top: 1rem;
        margin-bottom: 1rem;
    }

    .home-title {
        font-size: 1.35rem;
        font-weight: 800;
        color: #ffffff;
        margin-bottom: 0.35rem;
    }

    .home-subtitle {
        color: #cdd8d2;
        font-size: 0.98rem;
        margin-bottom: 0.3rem;
    }

    .section-title {
        font-size: 1.1rem;
        font-weight: 800;
        color: #f7f7f2;
        margin-top: 1rem;
        margin-bottom: 0.8rem;
    }

    .info-row {
        margin-top: 0.8rem;
        margin-bottom: 1rem;
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

    .stButton > button {
        background: #f39a1f !important;
        color: #16211d !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 800 !important;
        padding: 0.75rem 1.15rem !important;
        width: 100% !important;
    }

    .stButton > button:hover {
        background: #ffae34 !important;
        color: #101816 !important;
    }

    .secondary-button .stButton > button {
        background: transparent !important;
        color: #f3f4ef !important;
        border: 1px solid rgba(243, 154, 31, 0.28) !important;
    }

    .secondary-button .stButton > button:hover {
        background: rgba(243, 154, 31, 0.08) !important;
        color: #ffffff !important;
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
    st.markdown("""
    <div class="topbar">
        <div>
            <div class="topbar-title">QGP Online</div>
            <div class="topbar-subtitle">SUPESP / CE &middot; Atualizador de Indicadores</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# =========================
# FUNÇÃO PARA IMPORTAR MÓDULO SOB DEMANDA (lazy import)
# Evita crash do app se um módulo tiver erro
# =========================
def carregar_modulo(nome_modulo: str, nome_funcao: str):
    """Importa um módulo sob demanda e retorna a função solicitada.
    Retorna None se o módulo falhar, exibindo o erro de forma amigável."""
    try:
        import importlib
        mod = importlib.import_module(f"modulos.{nome_modulo}")
        return getattr(mod, nome_funcao, None)
    except Exception as e:
        st.error(f"❌ Erro ao carregar módulo '{nome_modulo}': {e}")
        import traceback
        with st.expander("Detalhes do erro"):
            st.code(traceback.format_exc())
        return None

# =========================
# MAPEAMENTO DE INDICADORES
# =========================
MAPEAMENTO = {
    "CVLI": ("cvli", "interface_cvli"),
    "CVP (SPORTAL)": ("cvp_sportal", "interface_cvp_sportal"),
    "CVP (SIP)": ("cvp_sip", "interface_cvp_sip"),
    "PERTURBAÇÃO AO SOSSEGO ALHEIO": ("perturbacao_sossego", "interface_perturbacao_sossego"),
    "DESLOCAMENTO FORÇADO": ("deslocamento_forcado", "interface_deslocamento_forcado"),
    "ROUBO DE VEÍCULO (SPORTAL)": ("roubo_veiculo_sportal", "interface_roubo_veiculo_sportal"),
    "ROUBO DE VEÍCULO (SIP)": ("roubo_veiculo_sip", "interface_roubo_veiculo_sip"),
    "ACIDENTE DE TRÂNSITO": ("acidente_transito", "interface_acidente_transito"),
    "FURTO DE VEÍCULO (SPORTAL)": ("furto_veiculo_sportal", "interface_furto_veiculo_sportal"),
    "FURTO DE VEÍCULO (SIP)": ("furto_veiculo_sip", "interface_furto_veiculo_sip"),
    "TODOS OS INDICADORES": ("todos_indicadores", "interface_todos_indicadores"),
}

INDICADORES_HOME = [
    "CVLI",
    "CVP (SPORTAL)",
    "CVP (SIP)",
    "PERTURBAÇÃO AO SOSSEGO ALHEIO",
    "DESLOCAMENTO FORÇADO",
    "ROUBO DE VEÍCULO (SPORTAL)",
    "ROUBO DE VEÍCULO (SIP)",
    "ACIDENTE DE TRÂNSITO",
    "FURTO DE VEÍCULO (SPORTAL)",
    "FURTO DE VEÍCULO (SIP)",
    "TODOS OS INDICADORES",
]

# =========================
# AÇÕES DE NAVEGAÇÃO
# =========================
def selecionar_indicador(nome: str):
    st.session_state.indicador_selecionado = nome

def voltar_inicio():
    st.session_state.indicador_selecionado = "Selecione um indicador..."

# =========================
# TELA INICIAL
# =========================
def render_home():
    st.markdown("""
    <div class="home-card">
        <div class="home-title">Bem-vindo ao QGP Online</div>
        <div class="home-subtitle">Sistema de atualização de indicadores de Segurança Pública da SUPESP/CE.</div>
        <div class="home-subtitle">Selecione o indicador desejado para iniciar o processamento.</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Selecione o Indicador Abaixo:")

    col1, col2, col3 = st.columns(3)

    blocos = [
        INDICADORES_HOME[0:4],
        INDICADORES_HOME[4:8],
        INDICADORES_HOME[8:11],
    ]

    for coluna, bloco in zip([col1, col2, col3], blocos):
        with coluna:
            for nome in bloco:
                if st.button(nome, key=f"btn_{nome}", use_container_width=True):
                    selecionar_indicador(nome)
                    st.rerun()

    st.markdown('<div class="info-row">', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-chip">Versão 1.0.0</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-chip">Data {datetime.now().strftime("%d/%m/%Y")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-chip">Hora {datetime.now().strftime("%H:%M:%S")}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# INICIALIZAÇÃO
# =========================
load_custom_css()
render_topbar()

# =========================
# CONTEÚDO PRINCIPAL
# =========================
indicador = st.session_state.indicador_selecionado

if indicador == "Selecione um indicador...":
    render_home()

elif indicador in MAPEAMENTO:
    col_topo_1, col_topo_2 = st.columns([10, 2])

    with col_topo_2:
        st.markdown('<div class="secondary-button">', unsafe_allow_html=True)
        if st.button("← Voltar", use_container_width=True):
            voltar_inicio()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    nome_mod, nome_func = MAPEAMENTO[indicador]
    func = carregar_modulo(nome_mod, nome_func)

    if func:
        func()

else:
    st.warning(f"🚧 O indicador **{indicador}** estará disponível em breve")
    st.info("👨‍💻 Sistema em desenvolvimento")

# =========================
# RODAPÉ
# =========================
st.markdown(
    '<p class="footer-note">QGP Online — Atualizador de Indicadores de Segurança Pública — SUPESP/CE</p>',
    unsafe_allow_html=True
)

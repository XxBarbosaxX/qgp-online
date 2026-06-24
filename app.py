# QGP Online - Atualizador de Indicadores de Segurança Pública - SUPESP/CE
# fix: set_page_config movido para o topo; imports lazy para evitar crash

import streamlit as st
from datetime import datetime
import sys
import os

# =========================
# CONFIGURACAO DA PAGINA (DEVE SER O PRIMEIRO COMANDO st.*)
# =========================
st.set_page_config(
    page_title="QGP Online - SUPESP/CE",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Adicionar pasta modulos ao path
sys.path.insert(0, os.path.dirname(__file__))  # Raiz do projeto para imports como 'from modulos.utils import'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'modulos'))

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
# FUNCAO PARA IMPORTAR MODULO SOB DEMANDA (lazy import)
# Evita crash do app se um modulo tiver erro
# =========================
def carregar_modulo(nome_modulo: str, nome_funcao: str):
    """Importa um modulo sob demanda e retorna a funcao solicitada.
    Retorna None se o modulo falhar, exibindo o erro de forma amigavel."""
    try:
        import importlib
        mod = importlib.import_module(f"modulos.{nome_modulo}")
        return getattr(mod, nome_funcao, None)
    except Exception as e:
        st.error(f"❌ Erro ao carregar modulo '{nome_modulo}': {e}")
        import traceback
        with st.expander("Detalhes do erro"):
            st.code(traceback.format_exc())
        return None

# =========================
# INICIALIZACAO
# =========================
load_custom_css()
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

    st.markdown("### Informacoes")
    st.markdown(f'<div class="metric-chip">Versao 1.0.0</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-chip">Data {datetime.now().strftime("%d/%m/%Y")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-chip">Hora {datetime.now().strftime("%H:%M:%S")}</div>', unsafe_allow_html=True)

# =========================
# MAPEAMENTO DE INDICADORES
# =========================
MAPEAMENTO = {
    "CVLI":                       ("cvli",                  "interface_cvli"),
    "CVP (SPORTAL)":              ("cvp_sportal",           "interface_cvp_sportal"),
    "CVP (SIP)":                  ("cvp_sip",               "interface_cvp_sip"),
    "PERTURBACAO DO SOSSEGO ALHEIO": ("perturbacao_sossego", "interface_perturbacao_sossego"),
    "DESLOCAMENTO FORCADO":        ("deslocamento_forcado",  "interface_deslocamento_forcado"),
    "ROUBO DE VEICULO (SPORTAL)": ("roubo_veiculo_sportal", "interface_roubo_veiculo_sportal"),
    "ROUBO DE VEICULO (SIP)":     ("roubo_veiculo_sip",     "interface_roubo_veiculo_sip"),
    "ACIDENTE DE TRANSITO":        ("acidente_transito",     "interface_acidente_transito"),
    "FURTO (SPORTAL)":             ("furto_veiculo_sportal", "interface_furto_veiculo_sportal"),
    "FURTO (SIP)":                 ("furto_veiculo_sip",     "interface_furto_veiculo_sip"),
    "TODOS OS INDICADORES":        ("todos_indicadores",     "interface_todos_indicadores"),
}

# =========================
# CONTEUDO PRINCIPAL
# =========================
if indicador == "Selecione um indicador...":
    st.markdown("## Bem-vindo ao QGP Online")
    st.info("👉 Selecione um indicador no painel lateral para comecar")

    st.markdown("### Indicadores Disponiveis")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        - ✅ CVLI
        - ✅ CVP (SPORTAL)
        - ✅ CVP (SIP)
        - ✅ PERTURBACAO DO SOSSEGO
        """)

    with col2:
        st.markdown("""
        - ✅ DESLOCAMENTO FORCADO
        - ✅ ROUBO DE VEICULO (SPORTAL)
        - ✅ ROUBO DE VEICULO (SIP)
        - ✅ ACIDENTE DE TRANSITO
        """)

    with col3:
        st.markdown("""
        - ✅ FURTO (SPORTAL)
        - ✅ FURTO (SIP)
        - ✅ TODOS OS INDICADORES
        """)

elif indicador in MAPEAMENTO:
    nome_mod, nome_func = MAPEAMENTO[indicador]
    func = carregar_modulo(nome_mod, nome_func)
    if func:
        func()
else:
    st.warning(f"🚧 O indicador **{indicador}** estara disponivel em breve")
    st.info("👨‍💻 Sistema em desenvolvimento")

# =========================
# RODAPE
# =========================
st.markdown(
    '<p class="footer-note">QGP Online — Atualizador de Indicadores de Seguranca Publica — SUPESP/CE</p>',
    unsafe_allow_html=True
)

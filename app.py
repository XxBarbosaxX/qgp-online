from datetime import datetime
import streamlit as st
import pandas as pd
import sys
import os

# Adicionar pasta modulos ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'modulos'))

try:
    from modulos.cvli import interface_cvli
except ImportError:
    st.error("Erro ao importar módulo CVLI")
    interface_cvli = None

try:
    from modulos.cvp_sip import interface_cvp_sip
except ImportError:
    st.error("Erro ao importar módulo CVP SIP")
    interface_cvp_sip = None

# =========================
# CONFIGURACAO DA PAGINA
# =========================
st.set_page_config(
    page_title="QGP Online - SUPESP/CE",
    page_icon="🛡️",
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
# CONTEUDO PRINCIPAL
# =========================

if indicador == "Selecione um indicador...":
    st.markdown("## Bem-vindo ao QGP Online")
    st.info("👉 Selecione um indicador no painel lateral para começar")
    
    st.markdown("### Indicadores Disponíveis")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        - ✅ CVLI
        - 🚧 CVP (SPORTAL)
        - 🚧 CVP (SIP)
        - 🚧 PERTURBACAO DO SOSSEGO
        """)
    
    with col2:
        st.markdown("""
        - 🚧 DESLOCAMENTO FORCADO
        - 🚧 ROUBO DE VEICULO (SPORTAL)
        - 🚧 ROUBO DE VEICULO (SIP)
        - 🚧 ACIDENTE DE TRANSITO
        """)
    
    with col3:
        st.markdown("""
        - 🚧 FURTO (SPORTAL)
        - 🚧 FURTO (SIP)
        - 🚧 TODOS OS INDICADORES
        """)

elif indicador == "CVLI":
    if interface_cvli:
        interface_cvli()
    else:
        st.error("❌ Módulo CVLI não disponível")

elif indicador == "CVP (SPORTAL)":
    if interface_cvp_sportal:
        interface_cvp_sportal()
    else:
        st.error("❌ Módulo CVP (SPORTAL) não disponível")


elif indicador == "CVP (SIP)":
    if interface_cvp_sip:
        interface_cvp_sip()
    else:
        st.error("❌ Módulo CVP (SIP) não disponível")
else:
    st.warning(f"🚧 O indicador **{indicador}** estará disponível em breve")
    st.info("👨‍💻 Sistema em desenvolvimento")

# =========================
# RODAPE
# =========================
st.markdown(
    '<div class="footer-note">QGP Online &mdash; Atualizador de Indicadores de Seguranca Publica &mdash; SUPESP/CE</div>',
    unsafe_allow_html=True
)

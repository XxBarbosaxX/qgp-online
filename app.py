# QGP Online - Força redeploy
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

try:
    from modulos.perturbacao_sossego import interface_perturbacao_sossego
except ImportError:
    st.error("Erro ao importar módulo Perturbação do Sossego")
    interface_perturbacao_sossego = None

try:
    from modulos.cvp_sportal import interface_cvp_sportal
    except ImportError:
    interface_cvp_sportal = None

try:
    from modulos.deslocamento_forcado import interface_deslocamento_forcado
except ImportError:
    st.error("Erro ao importar módulo Deslocamento Forçado")
    interface_deslocamento_forcado = None

try:
    from modulos.roubo_veiculo_sportal import interface_roubo_veiculo_sportal
except ImportError:
    st.error("Erro ao importar módulo Roubo de Veículo SPORTAL")
    interface_roubo_veiculo_sportal = None

try:
    from modulos.roubo_veiculo_sip import interface_roubo_veiculo_sip
except ImportError:
    st.error("Erro ao importar módulo Roubo de Veículo SIP")
    interface_roubo_veiculo_sip = None

try:
    from modulos.acidente_transito import interface_acidente_transito
except ImportError:
    st.error("Erro ao importar módulo Acidente de Trânsito")
    interface_acidente_transito = None

try:
    from modulos.furto_veiculo_sportal import interface_furto_veiculo_sportal
except ImportError:
    st.error("Erro ao importar módulo Furto de Veículo SPORTAL")
    interface_furto_veiculo_sportal = None

try:
    from modulos.furto_veiculo_sip import interface_furto_veiculo_sip
except ImportError:
    st.error("Erro ao importar módulo Furto de Veículo SIP")
    interface_furto_veiculo_sip = None

try:
    from modulos.todos_indicadores import interface_todos_indicadores
except ImportError:
    st.error("Erro ao importar módulo TODOS OS INDICADORES")
    interface_todos_indicadores = None

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
                <div class="topbar-subtitle">SUPESP / CE · Atualizador de Indicadores</div>
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

elif indicador == "PERTURBACAO DO SOSSEGO ALHEIO":
    if interface_perturbacao_sossego:
        interface_perturbacao_sossego()
    else:
        st.error("❌ Módulo Perturbação do Sossego não disponível")

elif indicador == "DESLOCAMENTO FORCADO":
    if interface_deslocamento_forcado:
        interface_deslocamento_forcado()
    else:
        st.error("❌ Módulo Deslocamento Forçado não disponível")

elif indicador == "ROUBO DE VEICULO (SPORTAL)":
    if interface_roubo_veiculo_sportal:
        interface_roubo_veiculo_sportal()
    else:
        st.error("❌ Módulo Roubo de Veículo (SPORTAL) não disponível")

elif indicador == "ROUBO DE VEICULO (SIP)":
    if interface_roubo_veiculo_sip:
        interface_roubo_veiculo_sip()
    else:
        st.error("❌ Módulo Roubo de Veículo (SIP) não disponível")

elif indicador == "ACIDENTE DE TRANSITO":
    if interface_acidente_transito:
        interface_acidente_transito()
    else:
        st.error("❌ Módulo Acidente de Trânsito não disponível")

elif indicador == "FURTO (SPORTAL)":
    if interface_furto_veiculo_sportal:
        interface_furto_veiculo_sportal()
    else:
        st.error("❌ Módulo Furto de Veículo (SPORTAL) não disponível")

elif indicador == "FURTO (SIP)":
    if interface_furto_veiculo_sip:
        interface_furto_veiculo_sip()
    else:
        st.error("❌ Módulo Furto de Veículo (SIP) não disponível")

elif indicador == "TODOS OS INDICADORES":
    if interface_todos_indicadores:
        interface_todos_indicadores()
    else:
        st.error("❌ Módulo TODOS OS INDICADORES não disponível")

else:
    st.warning(f"🚧 O indicador **{indicador}** estará disponível em breve")
    st.info("👨‍💻 Sistema em desenvolvimento")

# =========================
# RODAPE
# =========================
st.markdown(
    '<p class="footer-note">QGP Online — Atualizador de Indicadores de Segurança Pública — SUPESP/CE</p>',
    unsafe_allow_html=True
)

# QGP Online - Atualizador de Indicadores de Segurança Pública - SUPESP/CE

import streamlit as st
from datetime import datetime
import sys
import os
import traceback

# =========================
# CONFIGURAÇÃO DA PÁGINA
# =========================
st.set_page_config(
    page_title="QGP Online - SUPESP/CE",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Adicionar pasta módulos ao path
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "modulos"))

# =========================
# ESTADO DA APLICAÇÃO
# =========================
if "indicador_selecionado" not in st.session_state:
    st.session_state.indicador_selecionado = "Selecione um indicador..."

# =========================
# HELPERS SEGUROS
# =========================
def safe_call_message(target, method_name: str, message: str):
    """Chama métodos do Streamlit com fallback seguro."""
    try:
        if target is not None and hasattr(target, method_name):
            getattr(target, method_name)(message)
        else:
            getattr(st, method_name)(message)
    except Exception:
        getattr(st, method_name)(message)

def executar_interface_segura(func, nome_indicador: str):
    """Executa interface dentro de container válido e captura erros com detalhes."""
    area_execucao = st.container()
    try:
        with area_execucao:
            func()
    except Exception as e:
        st.error(f"Erro ao executar o módulo '{nome_indicador}': {e}")
        with st.expander("Detalhes do erro"):
            st.code(traceback.format_exc())

# =========================
# CSS CUSTOMIZADO
# =========================
def load_custom_css():
    st.markdown("""
    <style>
    @keyframes pulse-border {
        0%   { box-shadow: 0 0 0 0 rgba(118, 255, 159, 0.24), 0 4px 14px rgba(72, 201, 120, 0.12); }
        70%  { box-shadow: 0 0 0 7px rgba(118, 255, 159, 0.00), 0 4px 14px rgba(72, 201, 120, 0.06); }
        100% { box-shadow: 0 0 0 0 rgba(118, 255, 159, 0.00), 0 4px 14px rgba(72, 201, 120, 0.12); }
    }

    .stApp {
        background: linear-gradient(180deg, #022b26 0%, #011917 100%);
        color: #f3f4ef;
    }

    section[data-testid="stSidebar"] {
        display: none !important;
    }

    .block-container {
        padding-top: 2.45rem !important;
        padding-bottom: 1.2rem !important;
        max-width: 99% !important;
    }

    .topbar {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-top: 0.28rem;
        margin-bottom: 0.72rem;
        padding: 0.18rem 0 0.58rem 0;
        border-bottom: 1px solid rgba(216, 138, 24, 0.16);
    }

    .topbar-title {
        font-size: 1.95rem;
        font-weight: 900;
        color: #ffffff;
        line-height: 1.04;
        margin: 0;
    }

    .topbar-subtitle {
        font-size: 0.90rem;
        font-weight: 800;
        color: #f39a1f;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        margin-top: 0.18rem;
    }

    .home-card {
        background: rgba(255,255,255,0.025);
        border: 1px solid rgba(243,154,31,0.11);
        border-radius: 16px;
        padding: 0.82rem 0.95rem 0.78rem 0.95rem;
        margin-top: 0.28rem;
        margin-bottom: 0.58rem;
    }

    .home-title {
        font-size: 1.16rem;
        font-weight: 800;
        color: #ffffff;
        margin-bottom: 0.18rem;
    }

    .home-subtitle {
        color: #cdd8d2;
        font-size: 0.90rem;
        margin-bottom: 0.14rem;
        line-height: 1.32;
    }

    .modules-heading {
        font-size: 1.95rem;
        font-weight: 900;
        color: #ffffff;
        line-height: 1.05;
        margin: 0.08rem 0 0.18rem 0;
        padding: 0;
    }

    .modules-row {
        width: 100%;
        margin-top: 0 !important;
        padding-top: 0 !important;
    }

    .module-shell {
        width: 100%;
        display: flex;
        flex-direction: column;
        align-items: stretch;
        justify-content: flex-start;
        margin-top: 0 !important;
        padding-top: 0 !important;
    }

    .section-wrap {
        width: 100%;
        height: 100%;
        padding: 0;
        margin: 0;
        background: transparent;
        border: none;
        box-shadow: none;
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
        align-items: stretch;
    }

    .section-card {
        width: 100%;
        background: rgba(255,255,255,0.028);
        border: 1px solid rgba(243,154,31,0.10);
        border-radius: 15px;
        padding: 0.72rem 0.88rem 0.68rem 0.88rem;
        margin: 0;
        min-height: 86px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-shadow:
            0 0 0 1px rgba(18, 77, 67, 0.18),
            0 6px 14px rgba(0, 0, 0, 0.08),
            inset 0 1px 0 rgba(255,255,255,0.02);
    }

    .section-title {
        font-size: 0.98rem;
        font-weight: 900;
        color: #ffffff;
        margin-bottom: 0.18rem;
        letter-spacing: 0.01em;
        text-transform: uppercase;
    }

    .section-subtitle {
        color: #d8e3de;
        font-size: 0.88rem;
        margin-bottom: 0;
        line-height: 1.28;
    }

    .section-spacer {
        height: 0.12rem;
    }

    .btn-gap-strong {
        height: 0.08rem;
    }

    .btn-gap-normal {
        height: 0.06rem;
    }

    .info-row {
        margin-top: 0.72rem;
        margin-bottom: 0.6rem;
    }

    .metric-chip {
        display: inline-block;
        background: rgba(243,154,31,0.12);
        color: #ffd089;
        border: 1px solid rgba(243,154,31,0.2);
        border-radius: 999px;
        padding: 0.28rem 0.62rem;
        font-size: 0.78rem;
        font-weight: 700;
        margin-right: 0.34rem;
        margin-bottom: 0.34rem;
    }

    .stButton {
        width: 100% !important;
        margin: 0 !important;
    }

    .stButton > button {
        width: 100% !important;
        display: block !important;
        background: linear-gradient(135deg, #f39a1f 0%, #e08010 100%) !important;
        color: #16211d !important;
        border: 1px solid rgba(243,154,31,0.30) !important;
        border-radius: 12px !important;
        font-weight: 900 !important;
        font-size: 0.88rem !important;
        padding: 0.38rem 0.74rem !important;
        min-height: 2.08rem !important;
        text-align: center !important;
        transition: transform 0.15s ease, box-shadow 0.18s ease,
                    background 0.18s ease, filter 0.15s ease !important;
        box-shadow: 0 2px 6px rgba(243,154,31,0.14) !important;
        letter-spacing: 0.01em !important;
        white-space: normal !important;
        line-height: 1.02 !important;
        margin: 0 !important;
    }

    .stButton > button p,
    .stButton > button span,
    .stButton > button div {
        font-weight: 900 !important;
        white-space: normal !important;
        line-height: 1.02 !important;
    }

    .stButton > button:hover {
        background: linear-gradient(135deg, #ffb83a 0%, #f39a1f 100%) !important;
        color: #0d1a16 !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(243,154,31,0.22) !important;
        filter: brightness(1.03) !important;
    }

    .stButton > button:active {
        transform: translateY(0px) scale(0.985) !important;
        box-shadow: 0 1px 3px rgba(243,154,31,0.12) !important;
        filter: brightness(0.98) !important;
    }

    .todos-btn .stButton > button {
        background: linear-gradient(135deg, #8df5ab 0%, #6ce592 100%) !important;
        color: #f39a1f !important;
        border: 2px solid rgba(183, 255, 203, 0.90) !important;
        border-radius: 13px !important;
        font-size: 0.93rem !important;
        min-height: 2.2rem !important;
        padding: 0.36rem 0.74rem !important;
        animation: pulse-border 2.2s ease-in-out infinite !important;
        letter-spacing: 0.015em !important;
        text-shadow: none !important;
        box-shadow:
            0 4px 12px rgba(72, 201, 120, 0.15),
            inset 0 1px 0 rgba(255,255,255,0.18) !important;
        font-weight: 900 !important;
    }

    .todos-btn .stButton > button:hover {
        background: linear-gradient(135deg, #9af7b5 0%, #7ae89c 100%) !important;
        color: #ff9f1a !important;
        transform: translateY(-1px) !important;
        box-shadow:
            0 6px 16px rgba(72, 201, 120, 0.20),
            0 0 0 2px rgba(171,255,193,0.14),
            inset 0 1px 0 rgba(255,255,255,0.20) !important;
        filter: brightness(1.01) !important;
    }

    .todos-btn .stButton > button:active {
        transform: translateY(0px) scale(0.985) !important;
        filter: brightness(0.98) !important;
    }

    .secondary-button .stButton > button {
        background: transparent !important;
        color: #f3f4ef !important;
        border: 1px solid rgba(243,154,31,0.24) !important;
        font-weight: 800 !important;
        box-shadow: none !important;
        min-height: 2.3rem !important;
        transition: transform 0.14s ease, background 0.16s ease, border-color 0.16s ease !important;
    }

    .secondary-button .stButton > button:hover {
        background: rgba(243,154,31,0.08) !important;
        color: #ffffff !important;
        border-color: rgba(243,154,31,0.46) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 3px 8px rgba(243,154,31,0.08) !important;
    }

    .secondary-button .stButton > button:active {
        transform: translateY(0px) scale(0.98) !important;
    }

    .footer-note {
        color: #b8c3bd;
        font-size: 0.84rem;
        margin-top: 0.72rem;
        text-align: center;
    }

    div[data-testid="column"] {
        display: flex !important;
        align-items: stretch !important;
    }

    div[data-testid="column"] > div {
        width: 100% !important;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
        align-items: stretch;
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
            <div class="topbar-subtitle">SUPESP / CE · Atualizador de Indicadores</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# =========================
# FUNÇÃO PARA IMPORTAR MÓDULO SOB DEMANDA
# =========================
def carregar_modulo(nome_modulo: str, nome_funcao: str):
    try:
        import importlib
        mod = importlib.import_module(f"modulos.{nome_modulo}")
        func = getattr(mod, nome_funcao, None)

        if func is None:
            st.error(f"Função '{nome_funcao}' não encontrada no módulo '{nome_modulo}'.")
            return None

        return func
    except Exception as e:
        st.error(f"Erro ao carregar módulo '{nome_modulo}': {e}")
        with st.expander("Detalhes do erro"):
            st.code(traceback.format_exc())
        return None

# =========================
# MAPEAMENTO DE MÓDULOS
# =========================
MAPEAMENTO = {
    "TODOS OS INDICADORES": ("todos_indicadores", "interface_todos_indicadores"),
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
    "GEOCODIFICAÇÃO": ("geocodificar", "interface_geocodificar"),
    "CONSOLIDAR INDICADORES": ("consolidar_indicadores", "interface_consolidar_indicadores"),
}

# =========================
# LISTAS DE EXIBIÇÃO
# =========================
INDICADORES_ATUALIZACAO = [
    "TODOS OS INDICADORES",
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
]

MODULOS_GEO = [
    "GEOCODIFICAÇÃO",
]

MODULOS_CONSOLIDACAO = [
    "CONSOLIDAR INDICADORES",
]

# =========================
# AÇÕES DE NAVEGAÇÃO
# =========================
def selecionar_indicador(nome: str):
    st.session_state.indicador_selecionado = nome

def voltar_inicio():
    st.session_state.indicador_selecionado = "Selecione um indicador..."

# =========================
# RENDER DE BLOCOS
# =========================
def render_header_bloco(titulo: str, subtitulo: str):
    st.markdown(f"""
    <div class="section-card">
        <div class="section-title"><strong>{titulo}</strong></div>
        <div class="section-subtitle">{subtitulo}</div>
    </div>
    """, unsafe_allow_html=True)

def render_lista_botoes(itens: list[str], key_prefix: str):
    for i, item in enumerate(itens):
        if i == 0:
            st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)

        if item == "TODOS OS INDICADORES":
            st.markdown('<div class="todos-btn">', unsafe_allow_html=True)
            if st.button(item, key=f"{key_prefix}_{item}", use_container_width=True):
                selecionar_indicador(item)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            if i < len(itens) - 1:
                st.markdown('<div class="btn-gap-strong"></div>', unsafe_allow_html=True)
        else:
            if st.button(item, key=f"{key_prefix}_{item}", use_container_width=True):
                selecionar_indicador(item)
                st.rerun()
            if i < len(itens) - 1:
                st.markdown('<div class="btn-gap-normal"></div>', unsafe_allow_html=True)

def render_bloco_completo(titulo: str, subtitulo: str, itens: list[str], key_prefix: str):
    st.markdown('<div class="module-shell">', unsafe_allow_html=True)
    st.markdown('<div class="section-wrap">', unsafe_allow_html=True)
    render_header_bloco(titulo, subtitulo)
    render_lista_botoes(itens, key_prefix)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# TELA INICIAL
# =========================
def render_home():
    st.markdown("""
    <div class="home-card">
        <div class="home-title">Bem-vindo ao QGP Online</div>
        <div class="home-subtitle">Sistema de atualização de indicadores de Segurança Pública da SUPESP/CE.</div>
        <div class="home-subtitle">Selecione o módulo desejado para iniciar o processamento.</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="modules-heading">Módulos disponíveis</div>', unsafe_allow_html=True)

    st.markdown('<div class="modules-row">', unsafe_allow_html=True)
    col_esq, col_centro, col_dir = st.columns([1, 1, 1], gap="small")

    with col_esq:
        render_bloco_completo(
            "ATUALIZAÇÃO DOS INDICADORES",
            "Selecione um indicador para processamento individual ou execução completa.",
            INDICADORES_ATUALIZACAO,
            "atualizacao"
        )

    with col_centro:
        render_bloco_completo(
            "GEOCODIFICAÇÃO",
            "Módulo dedicado à geocodificação de ocorrências e endereços.",
            MODULOS_GEO,
            "geocodificacao"
        )

    with col_dir:
        render_bloco_completo(
            "CONSOLIDAR INDICADORES",
            "Área reservada para o módulo de consolidação de indicadores.",
            MODULOS_CONSOLIDACAO,
            "consolidacao"
        )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="info-row">', unsafe_allow_html=True)
    st.markdown('<div class="metric-chip">Versão 1.0.0</div>', unsafe_allow_html=True)
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
        if st.button("Voltar", use_container_width=True):
            voltar_inicio()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    nome_mod, nome_func = MAPEAMENTO[indicador]
    func = carregar_modulo(nome_mod, nome_func)

    if func:
        executar_interface_segura(func, indicador)

else:
    st.warning(f"O módulo **{indicador}** estará disponível em breve.")
    st.info("Sistema em desenvolvimento.")

# =========================
# RODAPÉ
# =========================
st.markdown(
    '<p class="footer-note">QGP Online — Atualizador de Indicadores de Segurança Pública — SUPESP/CE</p>',
    unsafe_allow_html=True
)

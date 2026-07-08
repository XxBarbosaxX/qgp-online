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
        0%   { box-shadow: 0 0 0 0 rgba(52,168,83,0.42), 0 4px 18px rgba(52,168,83,0.18); }
        70%  { box-shadow: 0 0 0 8px rgba(52,168,83,0.00), 0 4px 18px rgba(52,168,83,0.10); }
        100% { box-shadow: 0 0 0 0 rgba(52,168,83,0.00), 0 4px 18px rgba(52,168,83,0.18); }
    }

    .stApp {
        background: linear-gradient(180deg, #022b26 0%, #011917 100%);
        color: #f3f4ef;
    }

    section[data-testid="stSidebar"] {
        display: none !important;
    }

    .block-container {
        padding-top: 2.6rem !important;
        padding-bottom: 2rem;
    }

    .topbar {
        display: flex;
        align-items: center;
        gap: 14px;
        margin-top: 0.4rem;
        margin-bottom: 1.2rem;
        padding: 0.8rem 0 1rem 0;
        border-bottom: 1px solid rgba(216, 138, 24, 0.18);
    }

    .topbar-title {
        font-size: 2.2rem;
        font-weight: 900;
        color: #ffffff;
        line-height: 1.15;
        margin: 0;
    }

    .topbar-subtitle {
        font-size: 0.98rem;
        font-weight: 800;
        color: #f39a1f;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-top: 0.35rem;
    }

    .home-card {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(243,154,31,0.14);
        border-radius: 18px;
        padding: 1.2rem;
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
        line-height: 1.5;
    }

    .section-card {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(243,154,31,0.14);
        border-radius: 18px;
        padding: 1.15rem 1.15rem 1rem 1.15rem;
        margin-top: 1rem;
        margin-bottom: 1rem;
    }

    .section-title {
        font-size: 1.08rem;
        font-weight: 900;
        color: #ffffff;
        margin-bottom: 0.25rem;
        letter-spacing: 0.01em;
    }

    .section-subtitle {
        color: #cdd8d2;
        font-size: 0.95rem;
        margin-bottom: 0.9rem;
        line-height: 1.45;
    }

    .info-row {
        margin-top: 0.8rem;
        margin-bottom: 1rem;
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

    .stButton > button {
        background: linear-gradient(135deg, #f39a1f 0%, #e08010 100%) !important;
        color: #16211d !important;
        border: 1px solid rgba(243,154,31,0.35) !important;
        border-radius: 12px !important;
        font-weight: 900 !important;
        font-size: 0.96rem !important;
        padding: 0.82rem 1rem !important;
        width: 100% !important;
        min-height: 3.15rem !important;
        text-align: center !important;
        transition: transform 0.15s ease, box-shadow 0.18s ease,
                    background 0.18s ease, filter 0.15s ease !important;
        box-shadow: 0 2px 8px rgba(243,154,31,0.18) !important;
        letter-spacing: 0.01em !important;
    }

    .stButton > button p,
    .stButton > button span,
    .stButton > button div {
        font-weight: 900 !important;
    }

    .stButton > button:hover {
        background: linear-gradient(135deg, #ffb83a 0%, #f39a1f 100%) !important;
        color: #0d1a16 !important;
        transform: translateY(-2px) scale(1.012) !important;
        box-shadow: 0 6px 20px rgba(243,154,31,0.32) !important;
        filter: brightness(1.06) !important;
    }

    .stButton > button:active {
        transform: translateY(0px) scale(0.98) !important;
        box-shadow: 0 1px 4px rgba(243,154,31,0.15) !important;
        filter: brightness(0.96) !important;
    }

    .todos-btn .stButton > button {
        background: linear-gradient(135deg, #34a853 0%, #6bcf63 100%) !important;
        color: #f39a1f !important;
        border: 2px solid rgba(129, 221, 124, 0.75) !important;
        border-radius: 14px !important;
        font-size: 1.02rem !important;
        min-height: 3.55rem !important;
        animation: pulse-border 2.2s ease-in-out infinite !important;
        letter-spacing: 0.03em !important;
        text-shadow: none !important;
        box-shadow: 0 4px 18px rgba(52,168,83,0.22) !important;
    }

    .todos-btn .stButton > button:hover {
        background: linear-gradient(135deg, #43bf64 0%, #7dd96e 100%) !important;
        color: #ffb347 !important;
        transform: translateY(-3px) scale(1.02) !important;
        box-shadow: 0 8px 26px rgba(52,168,83,0.32), 0 0 0 3px rgba(129,221,124,0.18) !important;
        filter: brightness(1.04) !important;
    }

    .todos-btn .stButton > button:active {
        transform: translateY(0px) scale(0.97) !important;
        filter: brightness(0.95) !important;
    }

    .secondary-button .stButton > button {
        background: transparent !important;
        color: #f3f4ef !important;
        border: 1px solid rgba(243,154,31,0.28) !important;
        font-weight: 800 !important;
        box-shadow: none !important;
        transition: transform 0.14s ease, background 0.16s ease, border-color 0.16s ease !important;
    }

    .secondary-button .stButton > button:hover {
        background: rgba(243,154,31,0.08) !important;
        color: #ffffff !important;
        border-color: rgba(243,154,31,0.55) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 3px 10px rgba(243,154,31,0.10) !important;
    }

    .secondary-button .stButton > button:active {
        transform: translateY(0px) scale(0.98) !important;
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
def render_bloco_modulos(titulo: str, subtitulo: str, itens: list[str], key_prefix: str):
    st.markdown(f"""
    <div class="section-card">
        <div class="section-title">{titulo}</div>
        <div class="section-subtitle">{subtitulo}</div>
    </div>
    """, unsafe_allow_html=True)

    if len(itens) == 1:
        item = itens[0]
        if item == "TODOS OS INDICADORES":
            st.markdown('<div class="todos-btn">', unsafe_allow_html=True)
            if st.button(item, key=f"{key_prefix}_{item}", use_container_width=True):
                selecionar_indicador(item)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            if st.button(item, key=f"{key_prefix}_{item}", use_container_width=True):
                selecionar_indicador(item)
                st.rerun()
        return

    colunas = st.columns(3)
    for i, item in enumerate(itens):
        with colunas[i % 3]:
            if item == "TODOS OS INDICADORES":
                st.markdown('<div class="todos-btn">', unsafe_allow_html=True)
                if st.button(item, key=f"{key_prefix}_{item}", use_container_width=True):
                    selecionar_indicador(item)
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                if st.button(item, key=f"{key_prefix}_{item}", use_container_width=True):
                    selecionar_indicador(item)
                    st.rerun()

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

    st.markdown("### Módulos disponíveis")

    render_bloco_modulos(
        "Atualização dos Indicadores",
        "Selecione um indicador para processamento individual ou execução completa.",
        INDICADORES_ATUALIZACAO,
        "atualizacao"
    )

    render_bloco_modulos(
        "Geocodificação",
        "Módulo dedicado à geocodificação de ocorrências e endereços.",
        MODULOS_GEO,
        "geocodificacao"
    )

    render_bloco_modulos(
        "Consolidar Indicadores",
        "Área reservada para o módulo de consolidação de indicadores.",
        MODULOS_CONSOLIDACAO,
        "consolidacao"
    )

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

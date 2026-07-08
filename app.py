"""
QGP Online - Atualizador de Indicadores de Segurança Pública - SUPESP/CE
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import importlib
import sys
import traceback

import streamlit as st


# =========================
# CONFIGURAÇÃO DA PÁGINA
# =========================
st.set_page_config(
    page_title="QGP Online - SUPESP/CE",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE_DIR = Path(__file__).resolve().parent
MODULOS_DIR = BASE_DIR / "modulos"

sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(MODULOS_DIR))


# =========================
# ESTADO DA APLICAÇÃO
# =========================
if "indicador_selecionado" not in st.session_state:
    st.session_state.indicador_selecionado = "Selecione um indicador..."

if "indicador_dropdown" not in st.session_state:
    st.session_state.indicador_dropdown = "CVLI"


# =========================
# MAPEAMENTO DE MÓDULOS
# =========================
MAPEAMENTO: dict[str, tuple[str, str]] = {
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

INDICADORES_ATUALIZACAO: list[str] = [
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

MODULOS_GEO: list[str] = [
    "GEOCODIFICAÇÃO",
]

MODULOS_CONSOLIDACAO: list[str] = [
    "CONSOLIDAR INDICADORES",
]


# =========================
# HELPERS
# =========================
def executar_interface_segura(func, nome_indicador: str) -> None:
    """Executa uma interface com tratamento seguro de exceções."""
    area_execucao = st.container()

    try:
        with area_execucao:
            func()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Erro ao executar o módulo '{nome_indicador}': {exc}")
        with st.expander("Detalhes do erro"):
            st.code(traceback.format_exc())


def carregar_modulo(nome_modulo: str, nome_funcao: str):
    """Importa um módulo sob demanda e retorna a função alvo."""
    try:
        modulo = importlib.import_module(f"modulos.{nome_modulo}")
        func = getattr(modulo, nome_funcao, None)

        if func is None:
            st.error(f"Função '{nome_funcao}' não encontrada no módulo '{nome_modulo}'.")
            return None

        return func

    except Exception as exc:  # noqa: BLE001
        st.error(f"Erro ao carregar módulo '{nome_modulo}': {exc}")
        with st.expander("Detalhes do erro"):
            st.code(traceback.format_exc())
        return None


def selecionar_indicador(nome: str) -> None:
    """Seleciona o indicador atual."""
    st.session_state.indicador_selecionado = nome


def voltar_inicio() -> None:
    """Retorna para a tela inicial."""
    st.session_state.indicador_selecionado = "Selecione um indicador..."


# =========================
# ESTILO
# =========================
def load_custom_css() -> None:
    """Carrega os estilos globais da aplicação."""
    st.markdown(
        """
        <style>
        :root {
            --bg-primary: #031f1c;
            --bg-secondary: #082926;
            --bg-tertiary: #0d332f;
            --surface: rgba(255, 255, 255, 0.035);
            --surface-hover: rgba(255, 255, 255, 0.055);
            --border: rgba(255, 255, 255, 0.08);
            --border-accent: rgba(243, 154, 31, 0.24);
            --text-primary: #f4f7f5;
            --text-secondary: #c8d4cf;
            --text-muted: #96aba4;
            --accent: #f39a1f;
            --accent-hover: #ffab38;
            --accent-dark: #14211d;
            --success: #4cd38a;
            --shadow-sm: 0 8px 24px rgba(0, 0, 0, 0.16);
            --shadow-md: 0 14px 34px rgba(0, 0, 0, 0.20);
            --radius-lg: 20px;
            --radius-md: 14px;
            --radius-sm: 10px;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(243, 154, 31, 0.06), transparent 22%),
                linear-gradient(180deg, #042824 0%, #021715 100%);
            color: var(--text-primary);
        }

        section[data-testid="stSidebar"] {
            display: none !important;
        }

        .block-container {
            max-width: 1380px !important;
            padding-top: 2rem !important;
            padding-bottom: 1.5rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }

        div[data-testid="column"] {
            display: flex !important;
            align-items: stretch !important;
        }

        div[data-testid="column"] > div {
            width: 100% !important;
        }

        .app-header {
            padding: 0.2rem 0 1rem 0;
            margin-bottom: 1.4rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }

        .app-title {
            margin: 0;
            font-size: 2.25rem;
            font-weight: 800;
            line-height: 1.05;
            color: #ffffff;
            letter-spacing: -0.02em;
        }

        .app-subtitle {
            margin-top: 0.45rem;
            color: var(--accent);
            font-size: 0.88rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }

        .hero-card {
            background: linear-gradient(180deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.025) 100%);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 1.4rem 1.5rem;
            margin-bottom: 1.3rem;
            box-shadow: var(--shadow-sm);
        }

        .hero-title {
            margin: 0 0 0.55rem 0;
            font-size: 1.35rem;
            font-weight: 700;
            color: #ffffff;
        }

        .hero-text {
            margin: 0;
            color: var(--text-secondary);
            font-size: 0.98rem;
            line-height: 1.6;
        }

        .section-title {
            margin: 0 0 1rem 0;
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.05;
            color: #ffffff;
            letter-spacing: -0.02em;
        }

        .panel-card {
            background: linear-gradient(180deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.025) 100%);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 1.2rem;
            min-height: 100%;
            box-shadow: var(--shadow-sm);
        }

        .panel-head {
            padding-bottom: 0.9rem;
            margin-bottom: 1rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.07);
        }

        .panel-kicker {
            margin-bottom: 0.5rem;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: var(--accent);
        }

        .panel-title {
            margin: 0 0 0.45rem 0;
            color: #ffffff;
            font-size: 1.1rem;
            font-weight: 700;
            line-height: 1.25;
        }

        .panel-description {
            margin: 0;
            color: var(--text-secondary);
            font-size: 0.92rem;
            line-height: 1.55;
        }

        .panel-footer {
            padding-top: 1rem;
            margin-top: 1rem;
            border-top: 1px solid rgba(255, 255, 255, 0.06);
            color: var(--text-muted);
            font-size: 0.82rem;
        }

        .chips-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin-top: 1.25rem;
        }

        .metric-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            background: rgba(243, 154, 31, 0.10);
            color: #ffd69d;
            border: 1px solid rgba(243, 154, 31, 0.18);
            border-radius: 999px;
            padding: 0.42rem 0.78rem;
            font-size: 0.80rem;
            font-weight: 700;
        }

        .stButton {
            width: 100% !important;
        }

        .stButton > button {
            width: 100% !important;
            min-height: 46px !important;
            border-radius: 12px !important;
            border: 1px solid rgba(243, 154, 31, 0.25) !important;
            background: linear-gradient(135deg, #f39a1f 0%, #e78812 100%) !important;
            color: #10201c !important;
            font-size: 0.93rem !important;
            font-weight: 800 !important;
            padding: 0.7rem 1rem !important;
            transition: all 0.18s ease !important;
            box-shadow: 0 6px 18px rgba(243, 154, 31, 0.15) !important;
        }

        .stButton > button:hover {
            transform: translateY(-1px) !important;
            background: linear-gradient(135deg, #ffb13d 0%, #f39a1f 100%) !important;
            box-shadow: 0 10px 24px rgba(243, 154, 31, 0.22) !important;
        }

        .stButton > button:focus {
            outline: none !important;
            box-shadow: 0 0 0 0.2rem rgba(243, 154, 31, 0.22) !important;
        }

        .secondary-button .stButton > button {
            background: transparent !important;
            color: var(--text-primary) !important;
            border: 1px solid var(--border-accent) !important;
            box-shadow: none !important;
        }

        .secondary-button .stButton > button:hover {
            background: rgba(243, 154, 31, 0.08) !important;
            color: #ffffff !important;
        }

        .stSelectbox label,
        .stMarkdown,
        .stCaption {
            color: var(--text-secondary) !important;
        }

        div[data-baseweb="select"] > div {
            min-height: 46px !important;
            border-radius: 12px !important;
            background: rgba(255, 255, 255, 0.03) !important;
            border: 1px solid rgba(255, 255, 255, 0.10) !important;
        }

        div[data-baseweb="select"] span {
            color: var(--text-primary) !important;
        }

        .footer-note {
            margin-top: 1.4rem;
            text-align: center;
            color: var(--text-muted);
            font-size: 0.84rem;
        }

        @media (max-width: 991px) {
            .block-container {
                padding-left: 1rem !important;
                padding-right: 1rem !important;
            }

            .app-title {
                font-size: 1.85rem;
            }

            .section-title {
                font-size: 1.7rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# =========================
# COMPONENTES DE UI
# =========================
def render_topbar() -> None:
    """Renderiza o cabeçalho principal."""
    st.markdown(
        """
        <div class="app-header">
            <div class="app-title">QGP Online</div>
            <div class="app-subtitle">SUPESP / CE · Atualizador de Indicadores</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_home_hero() -> None:
    """Renderiza o card principal da página inicial."""
    st.markdown(
        """
        <div class="hero-card">
            <div class="hero-title">Bem-vindo ao QGP Online</div>
            <p class="hero-text">
                Sistema de atualização de indicadores de Segurança Pública da SUPESP/CE.
                Selecione o módulo desejado para iniciar o processamento com mais rapidez,
                clareza operacional e melhor organização visual.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_panel_header(kicker: str, titulo: str, descricao: str) -> None:
    """Renderiza o cabeçalho de um painel."""
    st.markdown(
        f"""
        <div class="panel-head">
            <div class="panel-kicker">{kicker}</div>
            <div class="panel-title">{titulo}</div>
            <p class="panel-description">{descricao}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_panel_atualizacao() -> None:
    """Renderiza o painel de atualização de indicadores."""
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    render_panel_header(
        "Atualização",
        "Indicadores operacionais",
        "Execute a atualização completa ou selecione um indicador específico para processamento individual.",
    )

    if st.button("Executar todos os indicadores", use_container_width=True):
        selecionar_indicador("TODOS OS INDICADORES")
        st.rerun()

    st.markdown("<div style='height: 0.85rem;'></div>", unsafe_allow_html=True)

    st.selectbox(
        "Selecione o indicador",
        options=INDICADORES_ATUALIZACAO,
        key="indicador_dropdown",
        label_visibility="visible",
    )

    st.markdown("<div style='height: 0.65rem;'></div>", unsafe_allow_html=True)

    if st.button("Abrir indicador selecionado", use_container_width=True):
        selecionar_indicador(st.session_state.indicador_dropdown)
        st.rerun()

    st.markdown(
        f"""
        <div class="panel-footer">
            {len(INDICADORES_ATUALIZACAO)} indicadores disponíveis para processamento individual.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)


def render_panel_geocodificacao() -> None:
    """Renderiza o painel de geocodificação."""
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    render_panel_header(
        "Geoprocessamento",
        "Geocodificação",
        "Módulo dedicado ao tratamento espacial de ocorrências e endereços para apoio analítico.",
    )

    if st.button("Abrir módulo de geocodificação", key="btn_geo", use_container_width=True):
        selecionar_indicador("GEOCODIFICAÇÃO")
        st.rerun()

    st.markdown(
        """
        <div class="panel-footer">
            Recomendado para rotinas de qualificação territorial e análise espacial.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)


def render_panel_consolidacao() -> None:
    """Renderiza o painel de consolidação."""
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    render_panel_header(
        "Consolidação",
        "Consolidar indicadores",
        "Centralize resultados e organize a base consolidada para consumo analítico e institucional.",
    )

    if st.button("Abrir consolidação", key="btn_consolidar", use_container_width=True):
        selecionar_indicador("CONSOLIDAR INDICADORES")
        st.rerun()

    st.markdown(
        """
        <div class="panel-footer">
            Ideal para fechamento de rotinas e preparação de saídas unificadas.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)


def render_info_chips() -> None:
    """Renderiza os chips informativos do sistema."""
    agora = datetime.now()

    st.markdown(
        f"""
        <div class="chips-row">
            <div class="metric-chip">Versão 1.0.0</div>
            <div class="metric-chip">Data {agora.strftime("%d/%m/%Y")}</div>
            <div class="metric-chip">Hora {agora.strftime("%H:%M:%S")}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_home() -> None:
    """Renderiza a tela inicial."""
    render_home_hero()

    st.markdown(
        '<div class="section-title">Módulos disponíveis</div>',
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3, gap="large")

    with col1:
        render_panel_atualizacao()

    with col2:
        render_panel_geocodificacao()

    with col3:
        render_panel_consolidacao()

    render_info_chips()


def render_modulo() -> None:
    """Renderiza o módulo selecionado."""
    indicador = st.session_state.indicador_selecionado

    col_titulo, col_acao = st.columns([10, 2], gap="medium")

    with col_titulo:
        st.markdown(
            f"""
            <div style="padding: 0.15rem 0 0.75rem 0;">
                <div class="panel-kicker">Módulo ativo</div>
                <div class="section-title" style="margin-bottom:0;">{indicador}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_acao:
        st.markdown('<div class="secondary-button">', unsafe_allow_html=True)
        if st.button("← Voltar", use_container_width=True):
            voltar_inicio()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    nome_modulo, nome_funcao = MAPEAMENTO[indicador]
    func = carregar_modulo(nome_modulo, nome_funcao)

    if func:
        executar_interface_segura(func, indicador)


# =========================
# APP
# =========================
load_custom_css()
render_topbar()

indicador = st.session_state.indicador_selecionado

if indicador == "Selecione um indicador...":
    render_home()
elif indicador in MAPEAMENTO:
    render_modulo()
else:
    st.warning(f"O módulo **{indicador}** estará disponível em breve.")
    st.info("Sistema em desenvolvimento.")

st.markdown(
    '<p class="footer-note">QGP Online — Atualizador de Indicadores de Segurança Pública — SUPESP/CE</p>',
    unsafe_allow_html=True,
)

from __future__ import annotations

import base64
import html
import importlib
import logging
from typing import Callable, Optional

import streamlit as st

from config.settings import BASE_DIR


logger = logging.getLogger(__name__)


MAPEAMENTO: dict[str, tuple[str, str]] = {
    "TODOS OS INDICADORES": (
        "modulos.todos_indicadores",
        "interface_todos_indicadores",
    ),
    "CVLI": (
        "modulos.cvli",
        "interface_cvli",
    ),
    "CVP (SPORTAL)": (
        "modulos.cvp_sportal",
        "interface_cvp_sportal",
    ),
    "CVP (SIP)": (
        "modulos.cvp_sip",
        "interface_cvp_sip",
    ),
    "PERTURBAÇÃO AO SOSSEGO ALHEIO": (
        "modulos.perturbacao_sossego",
        "interface_perturbacao_sossego",
    ),
    "DESLOCAMENTO FORÇADO": (
        "modulos.deslocamento_forcado",
        "interface_deslocamento_forcado",
    ),
    "ROUBO DE VEÍCULO (SPORTAL)": (
        "modulos.roubo_veiculo_sportal",
        "interface_roubo_veiculo_sportal",
    ),
    "ROUBO DE VEÍCULO (SIP)": (
        "modulos.roubo_veiculo_sip",
        "interface_roubo_veiculo_sip",
    ),
    "ACIDENTE DE TRÂNSITO": (
        "modulos.acidente_transito",
        "interface_acidente_transito",
    ),
    "MORTES NO TRÂNSITO (SIP)": (
        "modulos.acidente_transito_sip",
        "interface_acidente_transito_sip",
    ),
    "FURTO DE VEÍCULO (SPORTAL)": (
        "modulos.furto_veiculo_sportal",
        "interface_furto_veiculo_sportal",
    ),
    "FURTO DE VEÍCULO (SIP)": (
        "modulos.furto_veiculo_sip",
        "interface_furto_veiculo_sip",
    ),
    "GEOCODIFICAÇÃO": (
        "modulos.geocodificar",
        "interface_geocodificar",
    ),
    "CONVERSÃO": (
        "modulos.conversor_coordenadas",
        "interface_conversor_coordenadas",
    ),
    "CONSOLIDAR INDICADORES": (
        "modulos.consolidar_indicadores_criminais",
        "interface_consolidar_indicadores_criminais",
    ),
}


INDICADORES_ATUALIZACAO: list[str] = [
    nome
    for nome in MAPEAMENTO.keys()
    if nome
    not in {
        "TODOS OS INDICADORES",
        "GEOCODIFICAÇÃO",
        "CONVERSÃO",
        "CONSOLIDAR INDICADORES",
    }
]


def carregar_modulo(nome_modulo: str, nome_funcao: str) -> Optional[Callable]:
    """Carrega dinamicamente a função de interface de um módulo."""
    try:
        modulo = importlib.import_module(nome_modulo)
        func = getattr(modulo, nome_funcao, None)

        if func is None:
            logger.error(
                "Função '%s' não encontrada no módulo '%s'.",
                nome_funcao,
                nome_modulo,
            )
            return None

        return func

    except Exception:
        logger.exception("Erro ao importar módulo '%s'.", nome_modulo)
        return None


def executar_interface_segura(func: Callable, indicador: str) -> None:
    """Executa a interface do módulo com tratamento seguro de erros."""
    try:
        func()
    except Exception:
        logger.exception("Erro ao executar o módulo '%s'.", indicador)
        st.error(
            "Ocorreu um erro interno ao executar o módulo selecionado. "
            "Tente novamente ou contate o administrador."
        )


def selecionar_indicador(nome: str) -> None:
    """Seleciona o módulo ativo."""
    st.session_state.indicador_selecionado = nome


def voltar_inicio() -> None:
    """Retorna para a tela inicial."""
    st.session_state.indicador_selecionado = "Selecione um indicador..."


@st.cache_data(show_spinner=False)
def _obter_logo_base64() -> str | None:
    """Carrega o logo da aplicação e retorna em base64."""
    candidatos = [
        BASE_DIR / "assets" / "Logo DIESP.PNG",
        BASE_DIR / "assets" / "LOGO DIESP.PNG",
        BASE_DIR / "assets" / "logo diesp.png",
        BASE_DIR / "assets" / "LXogo DIESP.PNG",
    ]

    for caminho_logo in candidatos:
        if not caminho_logo.exists():
            continue

        try:
            return base64.b64encode(caminho_logo.read_bytes()).decode("utf-8")
        except Exception:
            logger.exception("Falha ao carregar logo: %s", caminho_logo)
            continue

    return None


def render_topbar() -> None:
    """Renderiza o cabeçalho superior da aplicação."""
    logo_base64 = _obter_logo_base64()

    if logo_base64:
        logo_html = f"""
        <div class="app-header-logo-wrap">
            <img
                src="data:image/png;base64,{logo_base64}"
                alt="Logo DIESP"
                class="app-header-logo"
            >
        </div>
        """
    else:
        logo_html = ""

    st.markdown(
        f"""
        <div class="app-header app-header-with-logo">
            <div class="app-header-main">
                <div class="app-title">QGP Online</div>
                <div class="app-subtitle">SUPESP / CE · Atualizador de Indicadores</div>
            </div>
            {logo_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_home_hero() -> None:
    """Renderiza o bloco principal da página inicial."""
    st.markdown(
        """
        <div class="hero-card">
            <div class="hero-title">Bem-vindo ao QGP Online</div>
            <p class="hero-text">
                Sistema de atualização de indicadores de Segurança Pública da SUPESP/CE.
                Selecione o módulo desejado para iniciar o processamento de forma clara, rápida e organizada.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_panel_text(kicker: str, titulo: str, descricao: str) -> None:
    """Renderiza o conteúdo textual padrão de um painel."""
    st.markdown(
        f"""
        <div class="panel-kicker">{html.escape(kicker)}</div>
        <div class="panel-title">{html.escape(titulo)}</div>
        <p class="panel-description">{html.escape(descricao)}</p>
        """,
        unsafe_allow_html=True,
    )


def render_panel_atualizacao() -> None:
    """Renderiza o painel de atualização dos indicadores."""
    with st.container():
        render_panel_text(
            "Atualização",
            "Indicadores operacionais",
            "Execute a atualização completa ou selecione um indicador específico para processamento individual.",
        )

        st.markdown('<div class="field-gap-sm"></div>', unsafe_allow_html=True)

        if st.button(
            "Executar todos os indicadores",
            key="btn_todos",
            use_container_width=True,
        ):
            selecionar_indicador("TODOS OS INDICADORES")
            st.rerun()

        st.markdown('<div class="panel-divider"></div>', unsafe_allow_html=True)

        st.selectbox(
            "Selecione um indicador",
            options=INDICADORES_ATUALIZACAO,
            key="indicador_dropdown",
        )

        st.markdown('<div class="field-gap-sm"></div>', unsafe_allow_html=True)

        if st.button(
            "Abrir indicador selecionado",
            key="btn_abrir_indicador",
            use_container_width=True,
        ):
            selecionar_indicador(st.session_state.indicador_dropdown)
            st.rerun()

        st.markdown(
            f"""
            <div class="panel-footer panel-footer-tight">
                {len(INDICADORES_ATUALIZACAO)} indicadores disponíveis para processamento individual.
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_panel_geocodificacao() -> None:
    """Renderiza o painel do módulo de geocodificação."""
    with st.container():
        render_panel_text(
            "Geoprocessamento",
            "Geocodificação",
            "Módulo dedicado à geocodificação de ocorrências e endereços.",
        )

        st.markdown('<div class="panel-divider"></div>', unsafe_allow_html=True)

        if st.button(
            "Abrir módulo de geocodificação",
            key="btn_geo",
            use_container_width=True,
        ):
            selecionar_indicador("GEOCODIFICAÇÃO")
            st.rerun()

        st.markdown(
            """
            <div class="panel-footer">
                Recomendado para geocodificar ocorrências por endereços.
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_panel_conversao() -> None:
    """Renderiza o painel do módulo de conversão."""
    with st.container():
        render_panel_text(
            "Conversão",
            "Conversor de Coordenadas",
            "Converta camadas em UTM para SIRGAS 2000 / UTM zona 24S.",
        )

        st.markdown('<div class="panel-divider"></div>', unsafe_allow_html=True)

        if st.button(
            "Abrir módulo de conversão",
            key="btn_conversao",
            use_container_width=True,
        ):
            selecionar_indicador("CONVERSÃO")
            st.rerun()

        st.markdown(
            """
            <div class="panel-footer">
                Indicado para padronização cartográfica para análises territoriais no Ceará.
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_panel_consolidacao() -> None:
    """Renderiza o painel do módulo de consolidação."""
    with st.container():
        render_panel_text(
            "Consolidação",
            "Consolidar indicadores",
            "Organize e unifique os indicadores de fechamento em uma base consolidada.",
        )

        st.markdown('<div class="panel-divider"></div>', unsafe_allow_html=True)

        if st.button(
            "Abrir módulo de consolidação",
            key="btn_consolidar",
            use_container_width=True,
        ):
            selecionar_indicador("CONSOLIDAR INDICADORES")
            st.rerun()

        st.markdown(
            """
            <div class="panel-footer">
                Ideal para consolidação de bases de arquivos de indicadores separados.
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_home() -> None:
    """Renderiza a tela inicial da aplicação."""
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
        render_panel_conversao()

    with col3:
        render_panel_consolidacao()


def render_modulo() -> None:
    """Renderiza o módulo selecionado pelo usuário."""
    indicador = st.session_state.indicador_selecionado

    col_titulo, col_acao = st.columns([10, 2], gap="medium")

    with col_titulo:
        st.markdown(
            f"""
            <div class="module-header">
                <div class="panel-kicker">Módulo ativo</div>
                <div class="section-title module-title">{html.escape(indicador)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_acao:
        if st.button("← Voltar", key="btn_voltar", use_container_width=True):
            voltar_inicio()
            st.rerun()

    if indicador in MAPEAMENTO:
        nome_modulo, nome_funcao = MAPEAMENTO[indicador]
        func = carregar_modulo(nome_modulo, nome_funcao)

        if func:
            executar_interface_segura(func, indicador)
        else:
            st.error(
                "Não foi possível carregar o módulo selecionado. "
                "Verifique a configuração da aplicação."
            )
    else:
        st.warning(f"O módulo {indicador} estará disponível em breve.")
        st.info("Sistema em desenvolvimento.")

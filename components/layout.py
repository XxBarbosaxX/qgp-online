from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from services.modules_loader import (
    INDICADORES_ATUALIZACAO,
    MAPEAMENTO,
    carregar_modulo,
    executar_interface_segura,
)


def selecionar_indicador(nome: str) -> None:
    st.session_state.indicador_selecionado = nome


def voltar_inicio() -> None:
    st.session_state.indicador_selecionado = "Selecione um indicador..."


def _obter_logo_base64() -> str | None:
    caminho_logo = Path("assets") / "LXogo DIESP.PNG"

    if not caminho_logo.exists():
        return None

    try:
        return base64.b64encode(caminho_logo.read_bytes()).decode("utf-8")
    except Exception:
        return None


def render_topbar() -> None:
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
    st.markdown(
        f"""
        <div class="panel-kicker">{kicker}</div>
        <div class="panel-title">{titulo}</div>
        <p class="panel-description">{descricao}</p>
        """,
        unsafe_allow_html=True,
    )


def render_panel_atualizacao() -> None:
    with st.container(key="panel-atualizacao"):
        render_panel_text(
            "🔄 Atualização",
            "Indicadores operacionais",
            "Execute a atualização completa ou selecione um indicador específico para processamento individual.",
        )

        st.markdown('<div class="panel-divider"></div>', unsafe_allow_html=True)

        if st.button("Executar todos os indicadores", key="btn_todos", use_container_width=True):
            selecionar_indicador("TODOS OS INDICADORES")
            st.rerun()

        st.markdown('<div class="field-gap"></div>', unsafe_allow_html=True)

        st.selectbox(
            "Selecione um Indicador",
            options=INDICADORES_ATUALIZACAO,
            key="indicador_dropdown",
            label_visibility="visible",
        )

        st.markdown('<div class="field-gap-sm"></div>', unsafe_allow_html=True)

        if st.button("Abrir indicador selecionado", key="btn_abrir_indicador", use_container_width=True):
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
    with st.container(key="panel-geocodificacao"):
        render_panel_text(
            "🌐 Geoprocessamento",
            "Geocodificação",
            "Módulo dedicado à geocodificação de ocorrências e endereços.",
        )

        st.markdown('<div class="panel-divider"></div>', unsafe_allow_html=True)

        if st.button("Abrir módulo de geocodificação", key="btn_geo", use_container_width=True):
            selecionar_indicador("GEOCODIFICAÇÃO")
            st.rerun()

        st.markdown(
            """
            <div class="panel-footer">
                Recomendado para Geocodificar ocorrências por endereços.
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_panel_conversao() -> None:
    with st.container(key="panel-conversao"):
        render_panel_text(
            "📍 Conversão",
            "Conversor de Coordenadas",
            "Converta camadas em UTM para SIRGAS 2000 / UTM zona 24S.",
        )

        st.markdown('<div class="panel-divider"></div>', unsafe_allow_html=True)

        if st.button("Abrir módulo de conversão", key="btn_conversao", use_container_width=True):
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
    with st.container(key="panel-consolidacao"):
        render_panel_text(
            "✅ Consolidação",
            "Consolidar indicadores",
            "Organize e unifique os indicadores de fechamento em uma base consolidada.",
        )

        st.markdown('<div class="panel-divider"></div>', unsafe_allow_html=True)

        if st.button("Abrir módulo de consolidação", key="btn_consolidar", use_container_width=True):
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
    indicador = st.session_state.indicador_selecionado

    col_titulo, col_acao = st.columns([10, 2], gap="medium")

    with col_titulo:
        st.markdown(
            f"""
            <div class="module-header">
                <div class="panel-kicker">Módulo ativo</div>
                <div class="section-title module-title">{indicador}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_acao:
        with st.container(key="panel-voltar"):
            if st.button("← Voltar", key="btn_voltar", use_container_width=True):
                voltar_inicio()
                st.rerun()

    if indicador in MAPEAMENTO:
        nome_modulo, nome_funcao = MAPEAMENTO[indicador]
        func = carregar_modulo(nome_modulo, nome_funcao)
        if func:
            executar_interface_segura(func, indicador)
    else:
        st.warning(f"O módulo **{indicador}** estará disponível em breve.")
        st.info("Sistema em desenvolvimento.")

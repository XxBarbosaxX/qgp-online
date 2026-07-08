"""
app.py
Arquivo principal do QGP Online - Atualizador de Indicadores de Segurança Pública.
"""

from __future__ import annotations

import streamlit as st

from modulos.cvli import interface_cvli
from modulos.cvp_sportal import interface_cvp_sportal
# importe aqui os demais módulos conforme forem padronizados:
# from modulos.cvp_sip import interface_cvp_sip
# from modulos.todos_indicadores import interface_todos_indicadores
# ...


def _voltar_para_home() -> None:
    """Retorna para a tela inicial."""
    st.session_state.pagina_atual = "home"
    st.rerun()


def _render_header_global() -> None:
    """Renderiza o cabeçalho global da aplicação."""
    st.markdown(
        """
        <div style="margin-bottom: 1.25rem;">
            <h1 style="margin: 0; color: #f8fafc;">QGP Online</h1>
            <p style="
                margin: 0.35rem 0 0 0;
                color: #f7b267;
                font-weight: 700;
                letter-spacing: 0.12em;
                text-transform: uppercase;
                font-size: 0.78rem;
            ">
                SUPESP / CE • Atualizador de Indicadores
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_topbar_com_voltar() -> None:
    """Renderiza apenas a barra superior com o botão Voltar."""
    col_spacer, col_button = st.columns([5, 1])

    with col_button:
        if st.button("← Voltar", key="btn_voltar_modulo", use_container_width=True):
            _voltar_para_home()


def _render_home() -> None:
    """Renderiza a página inicial (hub de módulos)."""
    st.markdown(
        """
        ### Seleção de módulo

        Escolha abaixo qual módulo deseja atualizar.
        """,
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("CVLI", use_container_width=True, key="btn_home_cvli"):
            st.session_state.pagina_atual = "cvli"
            st.rerun()

        if st.button("CVP (SPORTAL)", use_container_width=True, key="btn_home_cvp_sportal"):
            st.session_state.pagina_atual = "cvp_sportal"
            st.rerun()

    with col2:
        # exemplos de outros módulos
        if st.button("CVP (SIP)", use_container_width=True, key="btn_home_cvp_sip"):
            st.session_state.pagina_atual = "cvp_sip"
            st.rerun()

    with col3:
        if st.button("Todos os Indicadores", use_container_width=True, key="btn_home_todos"):
            st.session_state.pagina_atual = "todos_indicadores"
            st.rerun()


def _render_pagina_atual() -> None:
    """Controla a navegação principal da aplicação."""
    pagina_atual = st.session_state.get("pagina_atual", "home")

    _render_header_global()

    if pagina_atual == "home":
        _render_home()
        return

    if pagina_atual == "cvli":
        _render_topbar_com_voltar()
        interface_cvli()
        return

    if pagina_atual == "cvp_sportal":
        _render_topbar_com_voltar()
        interface_cvp_sportal()
        return

    # Exemplo de outros módulos (mantendo padrão visual)
    # if pagina_atual == "cvp_sip":
    #     _render_topbar_com_voltar()
    #     interface_cvp_sip()
    #     return
    #
    # if pagina_atual == "todos_indicadores":
    #     _render_topbar_com_voltar()
    #     interface_todos_indicadores()
    #     return

    st.warning("Página não encontrada.")


def main() -> None:
    """Função principal da aplicação."""
    st.set_page_config(
        page_title="QGP Online - Atualizador de Indicadores",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    _render_pagina_atual()


if __name__ == "__main__":
    main()

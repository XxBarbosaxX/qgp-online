from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

from components.footer import render_footer
from components.layout import render_home, render_modulo, render_topbar
from config.settings import (
    BASE_DIR,
    MODULOS_DIR,
    INITIAL_SIDEBAR_STATE,
    PAGE_ICON,
    PAGE_LAYOUT,
    PAGE_TITLE,
)


def load_theme_css() -> None:
    css_path = BASE_DIR / "assets" / "css" / "theme.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)


def configure_env() -> None:
    sys.path.insert(0, str(BASE_DIR))
    sys.path.insert(0, str(MODULOS_DIR))


def configure_page() -> None:
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon=PAGE_ICON,
        layout=PAGE_LAYOUT,
        initial_sidebar_state=INITIAL_SIDEBAR_STATE,
    )


def init_state() -> None:
    if "indicador_selecionado" not in st.session_state:
        st.session_state.indicador_selecionado = "Selecione um indicador..."

    if "indicador_dropdown" not in st.session_state:
        st.session_state.indicador_dropdown = "CVLI"


def main() -> None:
    configure_page()
    configure_env()
    init_state()
    load_theme_css()

    render_topbar()

    indicador = st.session_state.indicador_selecionado
    if indicador == "Selecione um indicador...":
        render_home()
    else:
        render_modulo()

    render_footer()


if __name__ == "__main__":
    main()

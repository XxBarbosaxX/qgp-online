from __future__ import annotations

import logging
import sys

import streamlit as st

from components.footer import render_footer
from components.layout import render_home, render_modulo, render_topbar
from config.settings import (
    BASE_DIR,
    INITIAL_SIDEBAR_STATE,
    PAGE_ICON,
    PAGE_LAYOUT,
    PAGE_TITLE,
)


logger = logging.getLogger(__name__)


@st.cache_data(show_spinner=False)
def _carregar_theme_css() -> str:
    """Carrega o conteúdo do CSS principal do tema."""
    css_path = BASE_DIR / "assets" / "css" / "theme.css"
    if not css_path.exists():
        logger.warning("Arquivo de tema não encontrado: %s", css_path)
        return ""
    return css_path.read_text(encoding="utf-8")


def load_theme_css() -> None:
    """Aplica o CSS do tema, se disponível."""
    css = _carregar_theme_css()
    if css:
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def configure_env() -> None:
    """Garante que o diretório base do projeto esteja disponível para imports."""
    base_dir_str = str(BASE_DIR)
    if base_dir_str not in sys.path:
        sys.path.insert(0, base_dir_str)


def configure_logging() -> None:
    """Configura o logging base da aplicação."""
    root_logger = logging.getLogger()

    if root_logger.handlers:
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def configure_page() -> None:
    """Configura os parâmetros globais da página Streamlit."""
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon=PAGE_ICON,
        layout=PAGE_LAYOUT,
        initial_sidebar_state=INITIAL_SIDEBAR_STATE,
    )


def init_state() -> None:
    """Inicializa as chaves básicas do session_state."""
    if "indicador_selecionado" not in st.session_state:
        st.session_state.indicador_selecionado = "Selecione um indicador..."

    if "indicador_dropdown" not in st.session_state:
        st.session_state.indicador_dropdown = "CVLI"


def main() -> None:
    """Executa o fluxo principal da aplicação."""
    configure_page()
    configure_logging()
    configure_env()
    init_state()

    render_topbar()
    load_theme_css()

    indicador = st.session_state.indicador_selecionado
    logger.info("Indicador atual: %s", indicador)

    if indicador == "Selecione um indicador...":
        render_home()
    else:
        render_modulo()

    render_footer()


if __name__ == "__main__":
    main()

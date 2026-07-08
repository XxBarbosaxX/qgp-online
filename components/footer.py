from __future__ import annotations

import streamlit as st


def render_footer() -> None:
    st.markdown(
        """
        <p class="footer-note">
            QGP Online — Atualizador de Indicadores de Segurança Pública — SUPESP/CE
        </p>
        """,
        unsafe_allow_html=True,
    )

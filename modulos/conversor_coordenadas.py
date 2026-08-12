from __future__ import annotations

import traceback
from typing import Any

import pandas as pd
import streamlit as st

from modulos.utils import (
    converter_coordenadas_para_wgs84_auto,
    encontrar_coluna_por_nomes,
    excluir_coordenadas_invalidas,
    gerar_arquivo_excel,
    normalizar_colunas,
)

NOME_ARQUIVO_FINAL = "Arquivo Convertido.xlsx"


def _aplicar_estilo_conversor() -> None:
    """Aplica o estilo visual do módulo Conversor de Coordenadas."""
    st.markdown(
        """
        <style>
            .conv-section-card {
                background: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 18px;
                padding: 1.1rem 1.1rem 0.7rem 1.1rem;
                margin: 1rem 0;
            }

            .conv-section-title {
                font-size: 1.15rem;
                font-weight: 800;
                color: #f8fafc;
                margin-bottom: 0.25rem;
            }

            .conv-section-desc {
                font-size: 0.93rem;
                color: rgba(255, 255, 255, 0.70);
                margin-bottom: 0.9rem;
                line-height: 1.5;
            }

            .conv-mini-list {
                margin: 0.6rem 0 0 0;
                padding-left: 1rem;
                color: rgba(255,255,255,0.78);
                font-size: 0.92rem;
            }

            .conv-grid-status {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.85rem;
                margin: 1rem 0 0.2rem 0;
            }

            .conv-stat {
                background: rgba(255, 255, 255, 0.025);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
                padding: 0.95rem 1rem;
            }

            .conv-stat-label {
                font-size: 0.78rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                color: rgba(255, 255, 255, 0.58);
                margin-bottom: 0.35rem;
                font-weight: 700;
            }

            .conv-stat-value {
                font-size: 1.20rem;
                font-weight: 900;
                color: #ffffff;
                line-height: 1.15;
                word-break: break-word;
            }

            .conv-badge-wrap {
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem;
                margin-top: 0.55rem;
                margin-bottom: 0.15rem;
            }

            .conv-badge {
                display: inline-flex;
                align-items: center;
                gap: 0.35rem;
                padding: 0.5rem 0.72rem;
                border-radius: 999px;
                font-size: 0.82rem;
                font-weight: 700;
                border: 1px solid rgba(255, 255, 255, 0.08);
                background: rgba(255, 255, 255, 0.03);
                color: #e5f3ee;
            }

            .conv-badge.ok {
                background: rgba(34, 197, 94, 0.10);
                color: #b7f7c9;
                border-color: rgba(34, 197, 94, 0.22);
            }

            .conv-badge.warn {
                background: rgba(245, 158, 11, 0.10);
                color: #fde4b0;
                border-color: rgba(245, 158, 11, 0.22);
            }

            .conv-upload-label {
                font-size: 0.95rem;
                font-weight: 700;
                color: #f8fafc;
                margin-bottom: 0.35rem;
            }

            @media (max-width: 1180px) {
                .conv-grid-status {
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }
            }

            @media (max-width: 640px) {
                .conv-grid-status {
                    grid-template-columns: 1fr;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _limpar_estado_conversor() -> None:
    """Limpa os estados do módulo Conversor de Coordenadas."""
    chaves = [
        "conv_arquivo",
        "conv_resultado",
    ]
    for chave in chaves:
        if chave in st.session_state:
            del st.session_state[chave]


def _identificar_colunas_coordenadas(df: pd.DataFrame) -> tuple[str | None, str | None]:
    """Identifica automaticamente as colunas de coordenadas."""
    col_lat_ou_y = encontrar_coluna_por_nomes(
        df,
        ["latitude", "lat", "y", "coord_y", "utm_y", "northing"],
    )
    col_lon_ou_x = encontrar_coluna_por_nomes(
        df,
        ["longitude", "long", "lon", "x", "coord_x", "utm_x", "easting"],
    )
    return col_lat_ou_y, col_lon_ou_x


def _processar_conversor(arquivo) -> dict[str, Any]:
    """Executa a conversão de coordenadas a partir de um único arquivo."""
    df_original = pd.read_excel(arquivo)
    df = normalizar_colunas(df_original.copy())

    total_lido = len(df)

    col_lat_ou_y, col_lon_ou_x = _identificar_colunas_coordenadas(df)

    if not col_lat_ou_y or not col_lon_ou_x:
        raise ValueError(
            "Não foi possível identificar automaticamente as colunas de coordenadas. "
            "Verifique se o arquivo possui campos como latitude/longitude, lat/long, x/y, utm_x/utm_y."
        )

    df_validado = excluir_coordenadas_invalidas(df, col_lat_ou_y, col_lon_ou_x)
    removidos_invalidos = total_lido - len(df_validado)

    if df_validado.empty:
        raise ValueError(
            "Após excluir coordenadas inválidas, o arquivo ficou sem registros válidos."
        )

    df_convertido = converter_coordenadas_para_wgs84_auto(
        df_validado.copy(),
        col_y_or_lat=col_lat_ou_y,
        col_x_or_lon=col_lon_ou_x,
        col_lat_destino="latitude",
        col_lon_destino="longitude",
    )

    total_final = len(df_convertido)

    situacao = (
        "Arquivo processado com sucesso. As coordenadas válidas foram convertidas "
        "automaticamente para o padrão WGS84."
    )

    return {
        "df_final": df_convertido,
        "total_lido": total_lido,
        "total_final": total_final,
        "removidos_invalidos": removidos_invalidos,
        "coluna_origem_y_lat": col_lat_ou_y,
        "coluna_origem_x_lon": col_lon_ou_x,
        "situacao": situacao,
    }


def interface_conversor_coordenadas() -> None:
    """Interface Streamlit para o Conversor de Coordenadas."""
    _aplicar_estilo_conversor()

    st.markdown(
        """
        <div class="conv-section-card">
            <div class="conv-section-title">Conversor de Coordenadas</div>
            <div class="conv-section-desc">
                Envie um arquivo Excel com coordenadas geográficas ou projetadas para conversão
                automática e geração de um novo arquivo final no padrão WGS84.
            </div>
            <ul class="conv-mini-list">
                <li>Upload de um único arquivo.</li>
                <li>Identificação automática das colunas de coordenadas.</li>
                <li>Validação e remoção de coordenadas inválidas.</li>
                <li>Conversão automática para latitude/longitude em WGS84.</li>
                <li>Geração do arquivo final convertido para download.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="conv-upload-label">📁 Arquivo para conversão</div>',
        unsafe_allow_html=True,
    )
    arquivo = st.file_uploader(
        "Arquivo para conversão",
        type=["xlsx", "xls"],
        key="conv_arquivo",
        label_visibility="collapsed",
    )

    pode_processar = arquivo is not None

    st.markdown(
        """
        <div class="conv-section-card">
            <div class="conv-section-title">Execução da conversão</div>
            <div class="conv-section-desc">
                Após carregar o arquivo, inicie o processamento para validar os registros,
                converter as coordenadas automaticamente e gerar o arquivo final.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        processar = st.button(
            "Processar conversão",
            type="primary",
            use_container_width=True,
            disabled=not pode_processar,
            key="btn_processar_conversor",
        )

    with col_btn2:
        limpar = st.button(
            "Limpar seleção",
            use_container_width=True,
            key="btn_limpar_conversor",
        )

    if limpar:
        _limpar_estado_conversor()
        st.rerun()

    if processar:
        try:
            with st.spinner("Processando arquivo e convertendo coordenadas..."):
                resultado = _processar_conversor(arquivo)

            st.session_state.conv_resultado = resultado

        except Exception as exc:
            st.session_state.conv_resultado = {
                "erro": str(exc),
                "traceback": traceback.format_exc(),
            }

    resultado = st.session_state.get("conv_resultado")

    if not resultado:
        return

    if "erro" in resultado:
        st.error(f"Erro durante o processamento: {resultado['erro']}")
        with st.expander("Detalhes do erro"):
            st.code(resultado["traceback"])
        return

    st.success("✅ Conversão concluída com sucesso.")

    badges = [
        f'<span class="conv-badge ok">Coluna origem Y/Lat: {resultado["coluna_origem_y_lat"]}</span>',
        f'<span class="conv-badge ok">Coluna origem X/Lon: {resultado["coluna_origem_x_lon"]}</span>',
    ]

    if resultado["removidos_invalidos"] > 0:
        badges.append(
            f'<span class="conv-badge warn">Coordenadas inválidas removidas: {resultado["removidos_invalidos"]}</span>'
        )
    else:
        badges.append('<span class="conv-badge ok">Nenhuma coordenada inválida removida</span>')

    st.markdown(
        f"""
        <div class="conv-section-card">
            <div class="conv-section-title">Resumo da conversão</div>
            <div class="conv-section-desc">{resultado["situacao"]}</div>
            <div class="conv-grid-status">
                <div class="conv-stat">
                    <div class="conv-stat-label">Total lido</div>
                    <div class="conv-stat-value">{resultado["total_lido"]}</div>
                </div>
                <div class="conv-stat">
                    <div class="conv-stat-label">Total final</div>
                    <div class="conv-stat-value">{resultado["total_final"]}</div>
                </div>
                <div class="conv-stat">
                    <div class="conv-stat-label">Inválidos removidos</div>
                    <div class="conv-stat-value">{resultado["removidos_invalidos"]}</div>
                </div>
                <div class="conv-stat">
                    <div class="conv-stat-label">Padrão de saída</div>
                    <div class="conv-stat-value">WGS84</div>
                </div>
            </div>
            <div class="conv-badge-wrap">
                {"".join(badges)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Prévia dos dados convertidos", expanded=False):
        st.dataframe(
            resultado["df_final"].head(200),
            use_container_width=True,
            hide_index=True,
        )

    excel_data = gerar_arquivo_excel(resultado["df_final"], sheet_name="CONVERSAO")

    st.download_button(
        label="💾 Baixar Arquivo Convertido",
        data=excel_data,
        file_name=NOME_ARQUIVO_FINAL,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key="download_arquivo_convertido",
    )

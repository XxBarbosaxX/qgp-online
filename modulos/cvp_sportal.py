"""
Modulo CVP (SPORTAL) - Crimes Violentos contra o Patrimonio
Processamento e atualizacao de dados CVP do sistema SPORTAL para QGP Online
"""

from __future__ import annotations

import traceback

import pandas as pd
import streamlit as st

from modulos.utils import (
    alinhar_colunas_com_base,
    converter_coordenadas_para_wgs84_auto,
    criar_coluna_datahora,
    encontrar_coluna_data,
    encontrar_coluna_hora,
    encontrar_coluna_por_nomes,
    excluir_coordenadas_invalidas,
    filtrar_apenas_registros_posteriores,
    gerar_arquivo_excel,
    nome_arquivo_padrao,
    normalizar_colunas,
    obter_ultima_datahora,
    renomear_colunas_equivalentes,
    selecionar_aba_atualizacao,
)

NOME_ARQUIVO_FINAL = nome_arquivo_padrao(2, "CVP-SPORTAL")


def _selecionar_aba_arquivo_02(sheet_names: list[str]) -> str:
    """Seleciona a aba correta do Arquivo 02 conforme chaveamento oficial."""
    return selecionar_aba_atualizacao(sheet_names, "cvp_sportal")


def processar_cvp_sportal(arquivo_01, arquivo_02):
    """Processa os arquivos de CVP SPORTAL e retorna df_final e resumo."""
    arquivo_01.seek(0)
    arquivo_02.seek(0)

    xls_base = pd.ExcelFile(arquivo_01)
    xls_novo = pd.ExcelFile(arquivo_02)

    aba_base = xls_base.sheet_names[0]
    aba_novo = _selecionar_aba_arquivo_02(xls_novo.sheet_names)

    df_base = pd.read_excel(xls_base, sheet_name=aba_base)
    df_novo = pd.read_excel(xls_novo, sheet_name=aba_novo)

    df_base = normalizar_colunas(df_base)
    df_novo = normalizar_colunas(df_novo)

    col_data_base = encontrar_coluna_data(df_base)
    col_data_novo = encontrar_coluna_data(df_novo)
    col_hora_base = encontrar_coluna_hora(df_base)
    col_hora_novo = encontrar_coluna_hora(df_novo)

    if col_data_base != col_data_novo:
        df_novo = df_novo.rename(columns={col_data_novo: col_data_base})
    if col_hora_base != col_hora_novo:
        df_novo = df_novo.rename(columns={col_hora_novo: col_hora_base})

    col_data = col_data_base
    col_hora = col_hora_base

    col_lat_base = encontrar_coluna_por_nomes(df_base, ["lat", "latitude"], obrigatoria=True)
    col_lon_base = encontrar_coluna_por_nomes(
        df_base,
        ["long", "longitude", "lon"],
        obrigatoria=True,
    )
    col_lat_novo = encontrar_coluna_por_nomes(df_novo, ["latitude"], obrigatoria=True)
    col_lon_novo = encontrar_coluna_por_nomes(df_novo, ["longitude"], obrigatoria=True)

    col_territorio_novo = encontrar_coluna_por_nomes(
        df_novo,
        ["território", "territorio", "regiões", "regioes"],
        obrigatoria=False,
    )
    if col_territorio_novo and col_territorio_novo != "Território":
        df_novo = df_novo.rename(columns={col_territorio_novo: "Território"})

    df_novo = renomear_colunas_equivalentes(
        df_base,
        df_novo,
        mapa_extra={
            "Território": ["Regiões", "Regioes", "Territorio", "Território"],
            "AISNova": ["AIS", "AISNova", "AIS Nova", "AIS_Nova", "aisnova"],
            "AIS": ["AISNova", "AIS Nova", "AIS_Nova", "aisnova"],
        },
    )

    total_lido_arquivo_02 = len(df_novo)

    df_novo = excluir_coordenadas_invalidas(df_novo, col_lat_novo, col_lon_novo)
    removidos_invalidos = total_lido_arquivo_02 - len(df_novo)

    if df_novo.empty:
        raise ValueError(
            "Apos excluir coordenadas invalidas, o Arquivo 02 ficou sem registros validos."
        )

    df_base = criar_coluna_datahora(df_base, col_data, col_hora)
    df_novo = criar_coluna_datahora(df_novo, col_data, col_hora)

    ultima_datahora_base = obter_ultima_datahora(df_base, "datahora")

    total_antes_filtro_tempo = len(df_novo)
    df_novo_filtrado = filtrar_apenas_registros_posteriores(
        df_novo,
        "datahora",
        ultima_datahora_base,
    )
    removidos_por_datahora = total_antes_filtro_tempo - len(df_novo_filtrado)

    base_sem_aux = df_base.drop(columns=["datahora"]).copy()

    if ultima_datahora_base is None:
        df_novo_util = df_novo.copy()
        situacao = "Base anterior sem DataHora valida - Arquivo 02 incluido integralmente."
    elif df_novo_filtrado.empty:
        df_novo_util = df_novo_filtrado.copy()
        situacao = "Nenhum registro novo encontrado apos a ultima DataHora da base."
    else:
        df_novo_util = df_novo_filtrado.copy()
        situacao = "Somente registros posteriores a ultima DataHora foram adicionados."

    adicionados = len(df_novo_util)

    if not df_novo_util.empty:
        df_novo_util = converter_coordenadas_para_wgs84_auto(
            df_novo_util,
            col_y_or_lat=col_lat_novo,
            col_x_or_lon=col_lon_novo,
            col_lat_destino=col_lat_base,
            col_lon_destino=col_lon_base,
        )
        df_novo_util = alinhar_colunas_com_base(base_sem_aux, df_novo_util)
        df_final = pd.concat([base_sem_aux, df_novo_util], ignore_index=True)
    else:
        df_final = base_sem_aux.copy()

    df_final = criar_coluna_datahora(df_final, col_data, col_hora)
    df_final = df_final.sort_values(
        by="datahora",
        ascending=True,
        na_position="last",
    ).reset_index(drop=True)
    df_final = df_final.drop(columns=["datahora"])

    total_final = len(df_final)

    resumo = {
        "adicionados": adicionados,
        "total_final": total_final,
        "ultima_datahora_base": (
            ultima_datahora_base.strftime("%d/%m/%Y %H:%M:%S")
            if ultima_datahora_base is not None
            else "N/A"
        ),
        "situacao": situacao,
        "removidos_invalidos": removidos_invalidos,
        "removidos_por_datahora": removidos_por_datahora,
        "nome_arquivo": NOME_ARQUIVO_FINAL,
        "aba_arquivo_01": aba_base,
        "aba_arquivo_02": aba_novo,
    }

    return df_final, resumo


def _render_resumo_cvp_sportal(resumo: dict) -> None:
    """Renderiza o resumo do processamento com componentes nativos do Streamlit."""
    st.markdown(
        """
        <div class="cvp-sportal-card">
            <div class="cvp-sportal-card-header">Resultado do processamento</div>
            <div class="cvp-sportal-card-desc">
                O processamento foi concluído com sucesso. Abaixo estão os principais indicadores da execução.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.success("Processamento finalizado com sucesso.")
    st.caption(resumo["situacao"])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Registros adicionados", resumo["adicionados"])
    with col2:
        st.metric("Total final", resumo["total_final"])
    with col3:
        st.metric("Última DataHora base", resumo["ultima_datahora_base"])

    col4, col5 = st.columns(2)
    with col4:
        st.info(f"**Aba arquivo 01:** {resumo['aba_arquivo_01']}")
    with col5:
        st.info(f"**Aba arquivo 02:** {resumo['aba_arquivo_02']}")

    if resumo["removidos_invalidos"] > 0:
        st.warning(
            f"Registros excluídos por coordenadas inválidas: {resumo['removidos_invalidos']}"
        )

    if resumo["removidos_por_datahora"] > 0:
        st.warning(
            "Registros excluídos por serem anteriores ou iguais à última DataHora: "
            f"{resumo['removidos_por_datahora']}"
        )


def interface_cvp_sportal() -> None:
    """Interface Streamlit para CVP SPORTAL."""
    st.markdown(
        """
        <style>
        .cvp-sportal-card {
            border-radius: 0.85rem;
            padding: 1rem 1.1rem;
            margin-bottom: 0.75rem;
            border: 1px solid rgba(148, 163, 184, 0.30);
            background: linear-gradient(180deg, rgba(2, 44, 34, 0.95), rgba(2, 26, 23, 0.95));
        }
        .cvp-sportal-card-header {
            font-weight: 700;
            font-size: 1rem;
            margin-bottom: 0.45rem;
            color: rgba(248, 250, 252, 0.98);
        }
        .cvp-sportal-card-desc {
            font-size: 0.84rem;
            color: rgba(226, 232, 240, 0.86);
            margin-bottom: 0.15rem;
            line-height: 1.6;
        }
        .cvp-sportal-list {
            margin: 0.7rem 0 0 0;
            padding-left: 1.2rem;
            color: rgba(226, 232, 240, 0.92);
        }
        .cvp-sportal-list li {
            margin-bottom: 0.35rem;
        }
        .cvp-sportal-file-card {
            border-radius: 0.75rem;
            padding: 0.75rem 0.85rem;
            background: rgba(15, 23, 42, 0.92);
            border: 1px solid rgba(148, 163, 184, 0.20);
            margin-top: 0.4rem;
            margin-bottom: 0.45rem;
        }
        .cvp-sportal-file-title {
            font-size: 0.8rem;
            font-weight: 700;
            color: rgba(248, 250, 252, 0.98);
            margin-bottom: 0.2rem;
        }
        .cvp-sportal-file-desc {
            font-size: 0.78rem;
            color: rgba(148, 163, 184, 0.95);
        }
        .element-container:has(#cvp-sportal-download-marker) + div button {
            background: linear-gradient(135deg, #ea580c, #f97316) !important;
            border-color: rgba(248, 250, 252, 0.15) !important;
            color: #fff7ed !important;
            font-weight: 700 !important;
        }
        .element-container:has(#cvp-sportal-download-marker) + div button:hover {
            background: linear-gradient(135deg, #c2410c, #ea580c) !important;
        }
        .element-container:has(#cvp-sportal-download-marker) + div button p {
            color: #fff7ed !important;
            font-weight: 700 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.caption(
        "Atualização da base de Crimes Violentos contra o Patrimônio com dados do sistema SPORTAL."
    )

    st.markdown(
        """
        <div class="cvp-sportal-card">
            <div class="cvp-sportal-card-header">Processamento de CVP SPORTAL</div>
            <div class="cvp-sportal-card-desc">
                Envie a base histórica e o complemento SPORTAL para atualizar a base consolidada do indicador
                CVP no padrão do QGP Online, com validação de coordenadas, conversão geográfica automática,
                filtro temporal por DataHora e padronização final da estrutura.
            </div>
            <ul class="cvp-sportal-list">
                <li>Seleção automática da aba correta do arquivo complementar.</li>
                <li>Validação e exclusão de coordenadas inválidas antes do processamento.</li>
                <li>Conversão automática das coordenadas para WGS84 quando necessário.</li>
                <li>Inclusão apenas de registros posteriores à última DataHora da base.</li>
                <li>Geração do arquivo final consolidado para download.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="cvp-sportal-card">
            <div class="cvp-sportal-card-header">Entrada de arquivos</div>
            <div class="cvp-sportal-card-desc">
                Envie a base atual do CVP e o arquivo complementar do SPORTAL. O sistema irá localizar a aba correta,
                validar coordenadas, converter o sistema geográfico quando necessário e adicionar apenas registros
                posteriores à última DataHora da base.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
            <div class="cvp-sportal-file-card">
                <div class="cvp-sportal-file-title">Arquivo 01</div>
                <div class="cvp-sportal-file-desc">Base histórica consolidada do CVP.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        arquivo_base = st.file_uploader(
            "Arquivo 01 - Base CVP",
            type=["xlsx", "xls"],
            key="cvp_sportal_base",
            label_visibility="collapsed",
        )

    with col2:
        st.markdown(
            """
            <div class="cvp-sportal-file-card">
                <div class="cvp-sportal-file-title">Arquivo 02</div>
                <div class="cvp-sportal-file-desc">Arquivo complementar do SPORTAL para atualização.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        arquivo_novo = st.file_uploader(
            "Arquivo 02 - Complemento SPORTAL",
            type=["xlsx", "xls"],
            key="cvp_sportal_novo",
            label_visibility="collapsed",
        )

    pode_processar = arquivo_base is not None and arquivo_novo is not None
    processar = st.button(
        "Processar CVP Sportal",
        type="primary",
        use_container_width=True,
        disabled=not pode_processar,
        key="processar_cvp_sportal",
    )

    if not processar:
        return

    if not arquivo_base or not arquivo_novo:
        st.warning("Envie os dois arquivos para continuar.")
        return

    try:
        with st.spinner("Processando arquivos..."):
            df_final, resumo = processar_cvp_sportal(arquivo_base, arquivo_novo)

        _render_resumo_cvp_sportal(resumo)

        excel_data = gerar_arquivo_excel(df_final, sheet_name="CVP-SPORTAL")

        st.markdown(
            """
            <div class="cvp-sportal-card">
                <div class="cvp-sportal-card-header">Download</div>
                <div class="cvp-sportal-card-desc">
                    Baixe o arquivo final processado no padrão oficial do módulo CVP Sportal.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<span id="cvp-sportal-download-marker"></span>', unsafe_allow_html=True)
        st.download_button(
            label="Baixar arquivo processado",
            data=excel_data,
            file_name=NOME_ARQUIVO_FINAL,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="download_cvp_sportal",
        )

    except Exception as e:
        st.error(f"Erro durante o processamento: {str(e)}")
        with st.expander("Detalhes do erro"):
            st.code(traceback.format_exc())

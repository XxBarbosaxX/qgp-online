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
    normalizar_colunas,
    obter_ultima_datahora,
    renomear_colunas_equivalentes,
)

# Nome fixo solicitado
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

            .conv-badge.err {
                background: rgba(239, 68, 68, 0.10);
                color: #fecaca;
                border-color: rgba(239, 68, 68, 0.22);
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
        "conv_base",
        "conv_novo",
        "conv_resultado",
    ]
    for chave in chaves:
        if chave in st.session_state:
            del st.session_state[chave]


def _normalizar_texto(txt: str) -> str:
    """Normaliza texto para comparação simplificada."""
    return str(txt).strip().lower()


def _encontrar_col_orig_exata_ou_parcial(
    cols: list[str],
    opcoes: list[str],
) -> str | None:
    """
    Procura uma coluna por nomes equivalentes.
    Primeiro tenta igualdade exata, depois ocorrência parcial.
    """
    cols_map = {col: _normalizar_texto(col) for col in cols}

    for nome in opcoes:
        nome_norm = _normalizar_texto(nome)
        for col, col_norm in cols_map.items():
            if col_norm == nome_norm:
                return col

    for nome in opcoes:
        nome_norm = _normalizar_texto(nome)
        for col, col_norm in cols_map.items():
            if nome_norm in col_norm:
                return col

    return None


def _col_norm_de_orig(
    cols_orig: list[str],
    col_orig: str | None,
    cols_norm: list[str],
) -> str | None:
    """Obtém o nome normalizado correspondente a uma coluna original."""
    if col_orig is None:
        return None
    try:
        idx = cols_orig.index(col_orig)
        return cols_norm[idx]
    except (ValueError, IndexError):
        return None


def _processar_conversor(arquivo_base, arquivo_novo) -> dict:
    """
    Executa a lógica de conversão de coordenadas.

    Mantém a mesma lógica do fluxo CVP/SPORTAL, mas
    conceitualmente usado aqui como Conversor de Coordenadas.
    """
    df_base = pd.read_excel(arquivo_base)
    df_novo = pd.read_excel(arquivo_novo)

    cols_orig_base = list(df_base.columns)
    cols_orig_novo = list(df_novo.columns)

    nome_ocorr_orig_base = _encontrar_col_orig_exata_ou_parcial(
        cols_orig_base,
        ["Nome da Ocorrência", "Nome Ocorrência"],
    )
    subnome_ocorr_orig_base = _encontrar_col_orig_exata_ou_parcial(
        cols_orig_base,
        ["Subnome da Ocorrência", "Subnome Ocorrência"],
    )
    territorio_orig_base = _encontrar_col_orig_exata_ou_parcial(
        cols_orig_base,
        ["Território", "Territorio", "Regiões", "Regioes"],
    )

    nome_ocorr_orig_novo = _encontrar_col_orig_exata_ou_parcial(
        cols_orig_novo,
        ["Nome da Ocorrência", "Nome Ocorrência"],
    )
    subnome_ocorr_orig_novo = _encontrar_col_orig_exata_ou_parcial(
        cols_orig_novo,
        ["Subnome da Ocorrência", "Subnome Ocorrência"],
    )
    territorio_orig_novo = _encontrar_col_orig_exata_ou_parcial(
        cols_orig_novo,
        ["Território", "Territorio", "Regiões", "Regioes"],
    )

    df_base = normalizar_colunas(df_base)
    df_novo = normalizar_colunas(df_novo)

    cols_norm_base = list(df_base.columns)
    cols_norm_novo = list(df_novo.columns)

    nome_ocorr_norm_base = _col_norm_de_orig(
        cols_orig_base,
        nome_ocorr_orig_base,
        cols_norm_base,
    )
    subnome_ocorr_norm_base = _col_norm_de_orig(
        cols_orig_base,
        subnome_ocorr_orig_base,
        cols_norm_base,
    )
    territorio_norm_base = _col_norm_de_orig(
        cols_orig_base,
        territorio_orig_base,
        cols_norm_base,
    )

    nome_ocorr_norm_novo = _col_norm_de_orig(
        cols_orig_novo,
        nome_ocorr_orig_novo,
        cols_norm_novo,
    )
    subnome_ocorr_norm_novo = _col_norm_de_orig(
        cols_orig_novo,
        subnome_ocorr_orig_novo,
        cols_norm_novo,
    )
    territorio_norm_novo = _col_norm_de_orig(
        cols_orig_novo,
        territorio_orig_novo,
        cols_norm_novo,
    )

    rename_map_especifico: dict[str, str] = {}

    if (
        nome_ocorr_norm_base
        and nome_ocorr_norm_novo
        and nome_ocorr_norm_novo != nome_ocorr_norm_base
        and nome_ocorr_norm_novo in df_novo.columns
    ):
        rename_map_especifico[nome_ocorr_norm_novo] = nome_ocorr_norm_base

    if (
        subnome_ocorr_norm_base
        and subnome_ocorr_norm_novo
        and subnome_ocorr_norm_novo != subnome_ocorr_norm_base
        and subnome_ocorr_norm_novo in df_novo.columns
    ):
        rename_map_especifico[subnome_ocorr_norm_novo] = subnome_ocorr_norm_base

    if (
        territorio_norm_base
        and territorio_norm_novo
        and territorio_norm_novo != territorio_norm_base
        and territorio_norm_novo in df_novo.columns
    ):
        rename_map_especifico[territorio_norm_novo] = territorio_norm_base

    if rename_map_especifico:
        df_novo = df_novo.rename(columns=rename_map_especifico)

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

    col_lat_base = encontrar_coluna_por_nomes(df_base, ["lat", "latitude"])
    col_lon_base = encontrar_coluna_por_nomes(df_base, ["long", "longitude", "lon"])
    col_lat_novo = encontrar_coluna_por_nomes(df_novo, ["latitude", "lat"])
    col_lon_novo = encontrar_coluna_por_nomes(df_novo, ["longitude", "long", "lon"])

    df_novo = renomear_colunas_equivalentes(df_base, df_novo)

    if nome_ocorr_norm_base and nome_ocorr_norm_base in df_novo.columns:
        nome_ocorr_norm_novo = nome_ocorr_norm_base
    if subnome_ocorr_norm_base and subnome_ocorr_norm_base in df_novo.columns:
        subnome_ocorr_norm_novo = subnome_ocorr_norm_base
    if territorio_norm_base and territorio_norm_base in df_novo.columns:
        territorio_norm_novo = territorio_norm_base

    total_lido_arquivo_02 = len(df_novo)

    df_novo = excluir_coordenadas_invalidas(df_novo, col_lat_novo, col_lon_novo)
    removidos_invalidos = total_lido_arquivo_02 - len(df_novo)

    if df_novo.empty:
        raise ValueError(
            "Após excluir coordenadas inválidas, o Arquivo 02 ficou sem registros válidos."
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

    base_sem_aux = df_base.drop(columns=["datahora"], errors="ignore")

    if ultima_datahora_base is None:
        df_novo_util = df_novo.copy()
        situacao = "Base anterior sem DataHora válida - complemento incluído integralmente."
    elif df_novo_filtrado.empty:
        df_novo_util = df_novo_filtrado.copy()
        situacao = "Nenhum registro novo encontrado após a última DataHora da base."
    else:
        df_novo_util = df_novo_filtrado.copy()
        situacao = "Somente registros posteriores à última DataHora foram adicionados."

    adicionados = len(df_novo_util)

    colunas_criticas = [
        nome_ocorr_norm_base,
        subnome_ocorr_norm_base,
        territorio_norm_base,
    ]

    for col in colunas_criticas:
        if col and col not in df_novo_util.columns:
            df_novo_util[col] = pd.NA

    if not df_novo_util.empty:
        df_novo_util = converter_coordenadas_para_wgs84_auto(
            df_novo_util,
            col_y_or_lat=col_lat_novo,
            col_x_or_lon=col_lon_novo,
            col_lat_destino=col_lat_base,
            col_lon_destino=col_lon_base,
        )

        rename_map_final: dict[str, str] = {}

        if (
            nome_ocorr_norm_base
            and nome_ocorr_norm_novo
            and nome_ocorr_norm_novo in df_novo_util.columns
            and nome_ocorr_norm_novo != nome_ocorr_norm_base
        ):
            rename_map_final[nome_ocorr_norm_novo] = nome_ocorr_norm_base

        if (
            subnome_ocorr_norm_base
            and subnome_ocorr_norm_novo
            and subnome_ocorr_norm_novo in df_novo_util.columns
            and subnome_ocorr_norm_novo != subnome_ocorr_norm_base
        ):
            rename_map_final[subnome_ocorr_norm_novo] = subnome_ocorr_norm_base

        if (
            territorio_norm_base
            and territorio_norm_novo
            and territorio_norm_novo in df_novo_util.columns
            and territorio_norm_novo != territorio_norm_base
        ):
            rename_map_final[territorio_norm_novo] = territorio_norm_base

        if rename_map_final:
            df_novo_util = df_novo_util.rename(columns=rename_map_final)

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
    df_final = df_final.drop(columns=["datahora"], errors="ignore")

    total_final = len(df_final)

    return {
        "df_final": df_final,
        "adicionados": adicionados,
        "total_final": total_final,
        "ultima_datahora_base": ultima_datahora_base,
        "removidos_invalidos": removidos_invalidos,
        "removidos_por_datahora": removidos_por_datahora,
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
                Envie a base de referência e o complemento com coordenadas para realizar a
                conversão automática e gerar um arquivo único pronto para uso analítico
                e espacial.
            </div>
            <ul class="conv-mini-list">
                <li>Validação automática de coordenadas válidas.</li>
                <li>Conversão automática para WGS84 quando necessário.</li>
                <li>Inclusão apenas de registros posteriores à última DataHora da base.</li>
                <li>Geração do arquivo final consolidado para download.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            '<div class="conv-upload-label">📁 Arquivo 01 - Base de referência</div>',
            unsafe_allow_html=True,
        )
        arquivo_base = st.file_uploader(
            "Arquivo base",
            type=["xlsx", "xls"],
            key="conv_base",
            label_visibility="collapsed",
        )

    with col2:
        st.markdown(
            '<div class="conv-upload-label">📁 Arquivo 02 - Complemento a converter</div>',
            unsafe_allow_html=True,
        )
        arquivo_novo = st.file_uploader(
            "Arquivo complemento",
            type=["xlsx", "xls"],
            key="conv_novo",
            label_visibility="collapsed",
        )

    pode_processar = bool(arquivo_base and arquivo_novo)

    st.markdown(
        """
        <div class="conv-section-card">
            <div class="conv-section-title">Execução da conversão</div>
            <div class="conv-section-desc">
                Após validar os arquivos carregados, inicie a conversão. O fluxo aplicará
                as regras de integridade temporal, consistência estrutural e tratamento
                de coordenadas para gerar o arquivo final convertido.
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
            with st.spinner("Processando arquivos e convertendo coordenadas..."):
                resultado = _processar_conversor(arquivo_base, arquivo_novo)

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

    ultima_ref = (
        resultado["ultima_datahora_base"].strftime("%d/%m/%Y %H:%M:%S")
        if resultado["ultima_datahora_base"] is not None
        else "N/A"
    )

    st.success("✅ Conversão concluída com sucesso.")

    badges = []
    if resultado["removidos_invalidos"] > 0:
        badges.append(
            f'<span class="conv-badge warn">Coordenadas inválidas removidas: {resultado["removidos_invalidos"]}</span>'
        )
    else:
        badges.append('<span class="conv-badge ok">Nenhuma coordenada inválida removida</span>')

    if resultado["removidos_por_datahora"] > 0:
        badges.append(
            f'<span class="conv-badge warn">Filtrados por DataHora: {resultado["removidos_por_datahora"]}</span>'
        )
    else:
        badges.append('<span class="conv-badge ok">Nenhum registro descartado por DataHora</span>')

    st.markdown(
        f"""
        <div class="conv-section-card">
            <div class="conv-section-title">Resumo da conversão</div>
            <div class="conv-section-desc">{resultado["situacao"]}</div>
            <div class="conv-grid-status">
                <div class="conv-stat">
                    <div class="conv-stat-label">Registros adicionados</div>
                    <div class="conv-stat-value">{resultado["adicionados"]}</div>
                </div>
                <div class="conv-stat">
                    <div class="conv-stat-label">Total final</div>
                    <div class="conv-stat-value">{resultado["total_final"]}</div>
                </div>
                <div class="conv-stat">
                    <div class="conv-stat-label">Última DataHora base</div>
                    <div class="conv-stat-value">{ultima_ref}</div>
                </div>
                <div class="conv-stat">
                    <div class="conv-stat-label">Inválidos removidos</div>
                    <div class="conv-stat-value">{resultado["removidos_invalidos"]}</div>
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

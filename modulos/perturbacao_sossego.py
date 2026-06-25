"""
Modulo Perturbacao ao Sossego Alheio
Versao Streamlit adaptada para o QGP Online.
"""

from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from modulos.utils import (
    alinhar_colunas_com_base,
    criar_coluna_datahora,
    encontrar_coluna_data,
    encontrar_coluna_hora,
    encontrar_coluna_por_nomes,
    filtrar_apenas_registros_posteriores,
    nome_arquivo_padrao,
    normalizar_colunas,
    obter_ultima_datahora,
    renomear_colunas_equivalentes,
)

NOME_ARQUIVO_FINAL = nome_arquivo_padrao(3, "PERTURBACAO-SOSSEGO-ALHEIO")


def _normalizar_nome_aba(nome: str) -> str:
    return (
        str(nome or "")
        .strip()
        .upper()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
    )


def _selecionar_aba_arquivo_01(sheet_names: list[str]) -> str:
    prioridades = [
        "PERTURBACAOAOSOSSEGOALHEIO",
        "PERTURBACAOAOSOSSEGO",
        "SOSSEGOALHEIO",
        "PERTURBACAO",
        "BASE",
    ]

    normalizadas = {aba: _normalizar_nome_aba(aba) for aba in sheet_names}

    for prioridade in prioridades:
        for aba, nome_norm in normalizadas.items():
            if nome_norm == prioridade:
                return aba

    for aba, nome_norm in normalizadas.items():
        if "PERTURBACAO" in nome_norm or "SOSSEGO" in nome_norm:
            return aba

    return sheet_names[0]


def _selecionar_aba_arquivo_02(sheet_names: list[str]) -> str:
    prioridades = [
        "PERTURBACAOAOSOSSEGOALHEIO",
        "PERTURBACAOAOSOSSEGO",
        "SOSSEGOALHEIO",
        "PERTURBACAO",
    ]

    normalizadas = {aba: _normalizar_nome_aba(aba) for aba in sheet_names}

    for prioridade in prioridades:
        for aba, nome_norm in normalizadas.items():
            if nome_norm == prioridade:
                return aba

    for aba, nome_norm in normalizadas.items():
        if "PERTURBACAO" in nome_norm or "SOSSEGO" in nome_norm:
            return aba

    return sheet_names[0]


def gerar_excel_em_memoria(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="PERTURBACAO_SOSSEGO")
    buffer.seek(0)
    return buffer.getvalue()


def processar_perturbacao_sossego(arquivo_01, arquivo_02):
    arquivo_01.seek(0)
    arquivo_02.seek(0)

    xls_base = pd.ExcelFile(arquivo_01)
    xls_novo = pd.ExcelFile(arquivo_02)

    abas_base = xls_base.sheet_names
    abas_novo = xls_novo.sheet_names

    aba_base = _selecionar_aba_arquivo_01(abas_base)
    aba_novo = _selecionar_aba_arquivo_02(abas_novo)

    df_base = pd.read_excel(xls_base, sheet_name=aba_base)
    df_novo = pd.read_excel(xls_novo, sheet_name=aba_novo)

    df_base = normalizar_colunas(df_base)
    df_novo = normalizar_colunas(df_novo)

    col_data_base = encontrar_coluna_data(df_base)
    col_hora_base = encontrar_coluna_hora(df_base)

    col_data_novo = encontrar_coluna_data(df_novo)
    col_hora_novo = encontrar_coluna_hora(df_novo)

    if col_data_novo is None:
        col_datahora_novo = encontrar_coluna_por_nomes(
            df_novo,
            ["datahora", "data_hora", "data/hora", "data hora"],
            obrigatoria=True,
        )
        df_novo["__datahora__"] = pd.to_datetime(
            df_novo[col_datahora_novo],
            errors="coerce",
            dayfirst=True,
        )
    else:
        df_novo = criar_coluna_datahora(df_novo, col_data_novo, col_hora_novo, "__datahora__")

    df_base = criar_coluna_datahora(df_base, col_data_base, col_hora_base, "__datahora__")

    ultima_datahora_base = obter_ultima_datahora(df_base, "__datahora__")

    total_antes_filtro = len(df_novo)
    df_novo_filtrado = filtrar_apenas_registros_posteriores(
        df_novo,
        "__datahora__",
        ultima_datahora_base,
    )
    removidos_por_datahora = total_antes_filtro - len(df_novo_filtrado)

    base_sem_aux = df_base.drop(columns=["__datahora__"], errors="ignore").copy()

    df_novo = renomear_colunas_equivalentes(base_sem_aux, df_novo)
    df_novo_filtrado = renomear_colunas_equivalentes(base_sem_aux, df_novo_filtrado)

    if ultima_datahora_base is None:
        df_novo_util = df_novo.copy()
        situacao = "Base anterior sem Data/Hora valida: Arquivo 02 foi incluido integralmente."
    elif df_novo_filtrado.empty:
        df_novo_util = df_novo_filtrado.copy()
        situacao = (
            "Nenhum registro novo encontrado apos a ultima Data/Hora da base: "
            "Arquivo 01 foi mantido sem acrescimos."
        )
    else:
        df_novo_util = df_novo_filtrado.copy()
        situacao = (
            "Base anterior localizada: somente registros posteriores a ultima "
            "Data/Hora foram adicionados."
        )

    if not df_novo_util.empty:
        df_novo_util = df_novo_util.drop(columns=["__datahora__"], errors="ignore")
        df_novo_util = alinhar_colunas_com_base(base_sem_aux, df_novo_util)
        df_final = pd.concat([base_sem_aux, df_novo_util], ignore_index=True)
        adicionados = len(df_novo_util)
    else:
        df_final = base_sem_aux.copy()
        adicionados = 0

    df_final = criar_coluna_datahora(df_final, col_data_base, col_hora_base, "__datahora__")
    df_final = df_final.sort_values(
        by="__datahora__",
        ascending=True,
        na_position="last",
    ).reset_index(drop=True)
    df_final = df_final.drop(columns=["__datahora__"], errors="ignore")

    total_final = len(df_final)

    ultima_ref = (
        ultima_datahora_base.strftime("%d/%m/%Y %H:%M:%S")
        if ultima_datahora_base is not None
        else "sem referencia anterior valida"
    )

    resumo = {
        "adicionados": adicionados,
        "total_final": total_final,
        "removidos_por_datahora": removidos_por_datahora,
        "ultima_datahora_base": ultima_ref,
        "situacao": situacao,
        "aba_arquivo_01": aba_base,
        "aba_arquivo_02": aba_novo,
    }

    return df_final, resumo


def _init_state():
    defaults = {
        "perturbacao_arquivo_01_bytes": None,
        "perturbacao_arquivo_01_nome": None,
        "perturbacao_arquivo_02_bytes": None,
        "perturbacao_arquivo_02_nome": None,
        "perturbacao_resultado_excel": None,
        "perturbacao_resultado_df": None,
        "perturbacao_resumo": None,
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def render():
    _init_state()

    st.subheader("Perturbacao ao Sossego Alheio")
    st.write(
        "Envie a base historica e o arquivo complementar para atualizar a base com os novos registros."
    )

    arquivo_01 = st.file_uploader(
        "Arquivo 01 - Base historica de Perturbacao ao Sossego Alheio",
        type=["xlsx", "xls"],
        key="perturbacao_upload_01",
    )

    arquivo_02 = st.file_uploader(
        "Arquivo 02 - Complemento de Perturbacao ao Sossego Alheio",
        type=["xlsx", "xls"],
        key="perturbacao_upload_02",
    )

    if arquivo_01 is not None:
        arquivo_01.seek(0)
        st.session_state.perturbacao_arquivo_01_bytes = arquivo_01.read()
        st.session_state.perturbacao_arquivo_01_nome = arquivo_01.name

    if arquivo_02 is not None:
        arquivo_02.seek(0)
        st.session_state.perturbacao_arquivo_02_bytes = arquivo_02.read()
        st.session_state.perturbacao_arquivo_02_nome = arquivo_02.name

    if st.session_state.perturbacao_arquivo_01_nome:
        st.info(f"Arquivo 01 carregado: {st.session_state.perturbacao_arquivo_01_nome}")

    if st.session_state.perturbacao_arquivo_02_nome:
        st.info(f"Arquivo 02 carregado: {st.session_state.perturbacao_arquivo_02_nome}")

    pode_processar = (
        st.session_state.perturbacao_arquivo_01_bytes is not None
        and st.session_state.perturbacao_arquivo_02_bytes is not None
    )

    if st.button(
        "Processar Perturbacao ao Sossego Alheio",
        type="primary",
        disabled=not pode_processar,
    ):
        try:
            arquivo_01_buffer = BytesIO(st.session_state.perturbacao_arquivo_01_bytes)
            arquivo_02_buffer = BytesIO(st.session_state.perturbacao_arquivo_02_bytes)

            with st.spinner("Processando registros de Perturbacao ao Sossego Alheio..."):
                df_final, resumo = processar_perturbacao_sossego(
                    arquivo_01_buffer,
                    arquivo_02_buffer,
                )
                arquivo_excel_bytes = gerar_excel_em_memoria(df_final)

            st.session_state.perturbacao_resultado_df = df_final
            st.session_state.perturbacao_resumo = resumo
            st.session_state.perturbacao_resultado_excel = arquivo_excel_bytes

            st.success("Processamento concluido com sucesso.")

        except Exception as exc:
            st.exception(exc)

    if (
        st.session_state.perturbacao_resultado_df is not None
        and st.session_state.perturbacao_resumo is not None
    ):
        df_final = st.session_state.perturbacao_resultado_df
        resumo = st.session_state.perturbacao_resumo

        c1, c2 = st.columns(2)
        c1.metric("Novos registros adicionados", resumo["adicionados"])
        c2.metric("Total final da base", resumo["total_final"])

        st.info(
            f"Aba usada no Arquivo 01: {resumo['aba_arquivo_01']} | "
            f"Aba usada no Arquivo 02: {resumo['aba_arquivo_02']}"
        )

        st.info(
            f"Ultima Data/Hora da base: {resumo['ultima_datahora_base']} | "
            f"Removidos por filtro temporal: {resumo['removidos_por_datahora']}"
        )

        st.caption(resumo["situacao"])
        st.dataframe(df_final.head(50), use_container_width=True)

        if st.session_state.perturbacao_resultado_excel is not None:
            st.download_button(
                label="Baixar arquivo final",
                data=st.session_state.perturbacao_resultado_excel,
                file_name=NOME_ARQUIVO_FINAL,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="perturbacao_download_final",
            )


interface_perturbacao_sossego = render

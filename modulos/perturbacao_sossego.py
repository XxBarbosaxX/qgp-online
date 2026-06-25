"""
Modulo Perturbacao ao Sossego Alheio
Versao Streamlit adaptada para o QGP Online.
"""

from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st
from pyproj import Transformer

from modulos.utils import (
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

EPSG_ORIGEM = 31984
EPSG_DESTINO = 4326


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


def _padronizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    renomeacoes = {}

    col_data = encontrar_coluna_por_nomes(df, ["data"], obrigatoria=False)
    if col_data and col_data != "Data":
        renomeacoes[col_data] = "Data"

    col_hora = encontrar_coluna_por_nomes(df, ["hora"], obrigatoria=False)
    if col_hora and col_hora != "Hora":
        renomeacoes[col_hora] = "Hora"

    col_territorio = encontrar_coluna_por_nomes(
        df,
        ["território", "territorio", "regiões", "regioes"],
        obrigatoria=False,
    )
    if col_territorio and col_territorio != "Território":
        renomeacoes[col_territorio] = "Território"

    col_ne = encontrar_coluna_por_nomes(df, ["ne"], obrigatoria=False)
    if col_ne and col_ne != "NE":
        renomeacoes[col_ne] = "NE"

    col_x = encontrar_coluna_por_nomes(df, ["longitude", "long", "lon"], obrigatoria=False)
    if col_x and col_x != "Longitude":
        renomeacoes[col_x] = "Longitude"

    col_y = encontrar_coluna_por_nomes(df, ["latitude", "lat"], obrigatoria=False)
    if col_y and col_y != "Latitude":
        renomeacoes[col_y] = "Latitude"

    if renomeacoes:
        df = df.rename(columns=renomeacoes)

    return df


def _converter_utm_para_wgs84(df: pd.DataFrame, col_x: str = "Longitude", col_y: str = "Latitude") -> pd.DataFrame:
    df = df.copy()

    x = pd.to_numeric(df[col_x], errors="coerce")
    y = pd.to_numeric(df[col_y], errors="coerce")

    mascara_valida = (
        x.notna()
        & y.notna()
        & (x != 0)
        & (y != 0)
    )

    df = df.loc[mascara_valida].copy()
    x = x.loc[mascara_valida]
    y = y.loc[mascara_valida]

    transformador = Transformer.from_crs(
        f"EPSG:{EPSG_ORIGEM}",
        f"EPSG:{EPSG_DESTINO}",
        always_xy=True,
    )

    longitudes, latitudes = transformador.transform(
        x.astype(float).to_numpy(),
        y.astype(float).to_numpy(),
    )

    df["Long"] = pd.to_numeric(pd.Series(longitudes, index=df.index), errors="coerce")
    df["Lat"] = pd.to_numeric(pd.Series(latitudes, index=df.index), errors="coerce")

    df = df[
        df["Long"].notna()
        & df["Lat"].notna()
        & (df["Long"] != 0)
        & (df["Lat"] != 0)
        & (df["Long"].between(-180, 180))
        & (df["Lat"].between(-90, 90))
    ].copy()

    return df


def _alinhar_com_base(base_sem_aux: pd.DataFrame, df_novo_util: pd.DataFrame) -> pd.DataFrame:
    df_novo_util = df_novo_util.copy()

    df_novo_util = renomear_colunas_equivalentes(base_sem_aux, df_novo_util)

    for coluna in base_sem_aux.columns:
        if coluna not in df_novo_util.columns:
            df_novo_util[coluna] = pd.NA

    return df_novo_util[base_sem_aux.columns]


def processar_perturbacao_sossego(arquivo_01, arquivo_02):
    progresso = st.progress(0)
    status = st.empty()

    status.info("Lendo os arquivos enviados...")
    arquivo_01.seek(0)
    arquivo_02.seek(0)

    xls_base = pd.ExcelFile(arquivo_01)
    xls_novo = pd.ExcelFile(arquivo_02)
    progresso.progress(10)

    aba_base = _selecionar_aba_arquivo_01(xls_base.sheet_names)
    aba_novo = _selecionar_aba_arquivo_02(xls_novo.sheet_names)

    status.info("Carregando as abas de trabalho...")
    df_base = pd.read_excel(xls_base, sheet_name=aba_base)
    df_novo = pd.read_excel(xls_novo, sheet_name=aba_novo)
    progresso.progress(20)

    status.info("Normalizando e padronizando nomes de colunas...")
    df_base = normalizar_colunas(df_base)
    df_novo = normalizar_colunas(df_novo)

    df_base = _padronizar_colunas(df_base)
    df_novo = _padronizar_colunas(df_novo)
    progresso.progress(30)

    status.info("Identificando colunas de data e hora...")
    col_data_base = encontrar_coluna_por_nomes(df_base, ["Data"], obrigatoria=False) or encontrar_coluna_data(df_base)
    col_hora_base = encontrar_coluna_por_nomes(df_base, ["Hora"], obrigatoria=False) or encontrar_coluna_hora(df_base)

    col_data_novo = encontrar_coluna_por_nomes(df_novo, ["Data"], obrigatoria=False) or encontrar_coluna_data(df_novo)
    col_hora_novo = encontrar_coluna_por_nomes(df_novo, ["Hora"], obrigatoria=False) or encontrar_coluna_hora(df_novo)

    if col_data_base is None:
        raise ValueError("O Arquivo 01 precisa possuir uma coluna de Data valida.")

    if col_data_novo is None:
        raise ValueError("O Arquivo 02 precisa possuir uma coluna de Data valida.")

    df_base = criar_coluna_datahora(df_base, col_data_base, col_hora_base, "__datahora__")
    df_novo = criar_coluna_datahora(df_novo, col_data_novo, col_hora_novo, "__datahora__")
    progresso.progress(40)

    status.info("Verificando a ultima Data/Hora da base...")
    ultima_datahora_base = obter_ultima_datahora(df_base, "__datahora__")

    total_antes_filtro = len(df_novo)
    df_novo_filtrado = filtrar_apenas_registros_posteriores(
        df_novo,
        "__datahora__",
        ultima_datahora_base,
    )
    removidos_por_datahora = total_antes_filtro - len(df_novo_filtrado)
    progresso.progress(50)

    base_sem_aux = df_base.drop(columns=["__datahora__"], errors="ignore").copy()

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

    if df_novo_util.empty:
        progresso.progress(100)
        status.success("Nenhum novo registro foi encontrado para processamento.")

        df_final = base_sem_aux.copy()
        df_final = criar_coluna_datahora(df_final, col_data_base, col_hora_base, "__datahora__")
        df_final = df_final.sort_values(by="__datahora__", ascending=True, na_position="last").reset_index(drop=True)
        df_final = df_final.drop(columns=["__datahora__"], errors="ignore")

        ultima_ref = (
            ultima_datahora_base.strftime("%d/%m/%Y %H:%M:%S")
            if ultima_datahora_base is not None
            else "sem referencia anterior valida"
        )

        resumo = {
            "adicionados": 0,
            "total_final": len(df_final),
            "removidos_por_datahora": removidos_por_datahora,
            "removidos_coord_invalidas": 0,
            "ultima_datahora_base": ultima_ref,
            "situacao": situacao,
            "aba_arquivo_01": aba_base,
            "aba_arquivo_02": aba_novo,
        }
        return df_final, resumo

    status.info("Removendo registros com coordenadas em branco ou zeradas...")
    total_antes_coord = len(df_novo_util)
    df_novo_util = _converter_utm_para_wgs84(df_novo_util, "Longitude", "Latitude")
    removidos_coord_invalidas = total_antes_coord - len(df_novo_util)
    progresso.progress(75)

    if df_novo_util.empty:
        progresso.progress(100)
        status.warning("Todos os novos registros foram descartados por coordenadas invalidas.")

        df_final = base_sem_aux.copy()
        df_final = criar_coluna_datahora(df_final, col_data_base, col_hora_base, "__datahora__")
        df_final = df_final.sort_values(by="__datahora__", ascending=True, na_position="last").reset_index(drop=True)
        df_final = df_final.drop(columns=["__datahora__"], errors="ignore")

        ultima_ref = (
            ultima_datahora_base.strftime("%d/%m/%Y %H:%M:%S")
            if ultima_datahora_base is not None
            else "sem referencia anterior valida"
        )

        resumo = {
            "adicionados": 0,
            "total_final": len(df_final),
            "removidos_por_datahora": removidos_por_datahora,
            "removidos_coord_invalidas": removidos_coord_invalidas,
            "ultima_datahora_base": ultima_ref,
            "situacao": "Todos os novos registros foram descartados por coordenadas invalidas.",
            "aba_arquivo_01": aba_base,
            "aba_arquivo_02": aba_novo,
        }
        return df_final, resumo

    status.info("Alinhando colunas e preparando inclusao dos novos registros...")
    df_novo_util = df_novo_util.drop(columns=["__datahora__"], errors="ignore")
    df_novo_util = _alinhar_com_base(base_sem_aux, df_novo_util)
    progresso.progress(90)

    status.info("Gerando arquivo final...")
    df_final = pd.concat([base_sem_aux, df_novo_util], ignore_index=True)
    df_final = criar_coluna_datahora(df_final, col_data_base, col_hora_base, "__datahora__")
    df_final = df_final.sort_values(by="__datahora__", ascending=True, na_position="last").reset_index(drop=True)
    df_final = df_final.drop(columns=["__datahora__"], errors="ignore")
    progresso.progress(100)

    adicionados = len(df_novo_util)

    status.success(f"Processamento concluido. Novos registros adicionados: {adicionados}")

    ultima_ref = (
        ultima_datahora_base.strftime("%d/%m/%Y %H:%M:%S")
        if ultima_datahora_base is not None
        else "sem referencia anterior valida"
    )

    resumo = {
        "adicionados": adicionados,
        "total_final": len(df_final),
        "removidos_por_datahora": removidos_por_datahora,
        "removidos_coord_invalidas": removidos_coord_invalidas,
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

    st.caption(
        "O sistema verifica a ultima Data/Hora da base historica, identifica apenas ocorrencias posteriores no arquivo complementar, elimina coordenadas invalidas, converte UTM (SIRGAS2000 / 24S) para WGS84 e inclui somente os novos registros validos no arquivo final."
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

            df_final, resumo = processar_perturbacao_sossego(
                arquivo_01_buffer,
                arquivo_02_buffer,
            )
            arquivo_excel_bytes = gerar_excel_em_memoria(df_final)

            st.session_state.perturbacao_resultado_df = df_final
            st.session_state.perturbacao_resumo = resumo
            st.session_state.perturbacao_resultado_excel = arquivo_excel_bytes

        except Exception as exc:
            st.exception(exc)

    if (
        st.session_state.perturbacao_resultado_df is not None
        and st.session_state.perturbacao_resumo is not None
    ):
        df_final = st.session_state.perturbacao_resultado_df
        resumo = st.session_state.perturbacao_resumo

        c1, c2, c3 = st.columns(3)
        c1.metric("Novos registros adicionados", resumo["adicionados"])
        c2.metric("Total final da base", resumo["total_final"])
        c3.metric("Coordenadas invalidas removidas", resumo["removidos_coord_invalidas"])

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

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

    col_x = encontrar_coluna_por_nomes(
        df,
        ["longitude", "long", "lon"],
        obrigatoria=False,
    )
    if col_x and col_x != "Longitude":
        renomeacoes[col_x] = "Longitude"

    col_y = encontrar_coluna_por_nomes(
        df,
        ["latitude", "lat"],
        obrigatoria=False,
    )
    if col_y and col_y != "Latitude":
        renomeacoes[col_y] = "Latitude"

    if renomeacoes:
        df = df.rename(columns=renomeacoes)

    return df


def _validar_e_converter_utm_para_wgs84(
    df: pd.DataFrame,
    col_x: str = "Longitude",
    col_y: str = "Latitude",
) -> tuple[pd.DataFrame, int]:
    df = df.copy()

    x = pd.to_numeric(df[col_x], errors="coerce")
    y = pd.to_numeric(df[col_y], errors="coerce")

    mascara_valida = x.notna() & y.notna() & (x != 0) & (y != 0)

    removidos_invalidos_entrada = len(df) - int(mascara_valida.sum())

    df = df.loc[mascara_valida].copy()
    x = x.loc[mascara_valida]
    y = y.loc[mascara_valida]

    if df.empty:
        return df, removidos_invalidos_entrada

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

    mascara_wgs84 = (
        df["Long"].notna()
        & df["Lat"].notna()
        & (df["Long"] != 0)
        & (df["Lat"] != 0)
        & df["Long"].between(-180, 180)
        & df["Lat"].between(-90, 90)
    )

    removidos_invalidos_saida = len(df) - int(mascara_wgs84.sum())
    df = df.loc[mascara_wgs84].copy()

    removidos_total = removidos_invalidos_entrada + removidos_invalidos_saida
    return df, removidos_total


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
    removidos_coord_invalidas = 0

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

    status.info("Identificando colunas de Data e Hora...")
    col_data_base = encontrar_coluna_por_nomes(df_base, ["Data"], obrigatoria=False) or encontrar_coluna_data(df_base)
    col_hora_base = encontrar_coluna_por_nomes(df_base, ["Hora"], obrigatoria=False) or encontrar_coluna_hora(df_base)

    col_data_novo = encontrar_coluna_por_nomes(df_novo, ["Data"], obrigatoria=False) or encontrar_coluna_data(df_novo)
    

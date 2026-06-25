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


def _padronizar_colunas_arquivo_02(df_novo: pd.DataFrame) -> pd.DataFrame:
    df_novo = df_novo.copy()

    mapa_renomeacao = {}

    col_data = encontrar_coluna_por_nomes(df_novo, ["data"], obrigatoria=False)
    if col_data and col_data != "Data":
        mapa_renomeacao[col_data] = "Data"

    col_hora = encontrar_coluna_por_nomes(df_novo, ["hora"], obrigatoria=False)
    if col_hora and col_hora != "Hora":
        mapa_renomeacao[col_hora] = "Hora"

    col_territorio = encontrar_coluna_por_nomes(
        df_novo,
        ["território", "territorio", "regiões", "regioes"],
        obrigatoria=False,
    )
    if col_territorio and col_territorio != "Território":
        mapa_renomeacao[col_territorio] = "Território"

    col_ne = encontrar_coluna_por_nomes(df_novo, ["ne"], obrigatoria=False)
    if col_ne and col_ne != "NE":
        mapa_renomeacao[col_ne] = "NE"

    col_lat = encontrar_coluna_por_nomes(df_novo, ["latitude", "lat"], obrigatoria=False)
    if col_lat and col_lat != "Latitude":
        mapa_renomeacao[col_lat] = "Latitude"

    col_lon = encontrar_coluna_por_nomes(df_novo, ["longitude", "long", "lon"], obrigatoria=False)
    if col_lon and col_lon != "Longitude":
        mapa_renomeacao[col_lon] = "Longitude"

    if mapa_renomeacao:
        df_novo = df_novo.rename(columns=mapa_renomeacao)

    return df_novo


def _converter_utm_para_wgs84(df: pd.DataFrame, col_x: str, col_y: str) -> pd.DataFrame:
    df = df.copy()

    x = pd.to_numeric(df[col_x], errors="coerce")
    y = pd.to_numeric(df[col_y], errors="coerce")
    mascara = x.notna() & y.notna()

    if "Long" not in df.columns:
        df["Long"] = pd.NA
    if "Lat" not in df.columns:
        df["Lat"] = pd.NA

    if mascara.any():
        transformador = Transformer.from_crs(
            f"EPSG:{EPSG_ORIGEM}",
            f"EPSG:{EPSG_DESTINO}",
            always_xy=True,
        )
        longitudes, latitudes = transformador.transform(
            x[mascara].astype(float).to_numpy(),
            y[mascara].astype(float).to_numpy(),
        )
        df.loc[mascara, "Long"] = longitudes
        df.loc[mascara, "Lat"] = latitudes

    return df


def _garantir_colunas_finais(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "data" in df.columns and "Data" not in df.columns:
        df = df.rename(columns={"data": "Data"})

    if "hora" in df.columns and "Hora" not in df.columns:
        df = df.rename(columns={"hora": "Hora"})

    if "Regiões" in df.columns and "Território" not in df.columns:
        df = df.rename(columns={"Regiões": "Território"})

    if "regioes" in df.columns and "Território" not in df.columns:
        df = df.rename(columns={"regioes": "Território"})

    if "territorio" in df.columns and "Território" not in df.columns:
        df = df.rename(columns={"territorio": "Território"})

    if "Latitude" in df.columns and "Lat" not in df.columns:
        df = df.rename(columns={"Latitude": "Lat"})

    if "Longitude" in df.columns and "Long" not in df.columns:
        df = df.rename(columns={"Longitude": "Long"})

    if "ne" in df.columns and "NE" not in df.columns:
        df = df.rename(columns={"ne": "NE"})

    return df


def processar_perturbacao_sossego(arquivo_01, arquivo_02):
    progresso = st.progress(0)
    status = st.empty()

    status.info("Lendo os arquivos enviados...")
    arquivo_01.seek(0)
    arquivo_02.seek(0)

    xls_base = pd.ExcelFile(arquivo_01)
    xls_novo = pd.ExcelFile(arquivo_02)
    progresso.progress(10)

    abas_base = xls_base.sheet_names
    abas_novo = xls_novo.sheet_names

    aba_base = _selecionar_aba_arquivo_01(abas_base)
    aba_novo = _selecionar_aba_arquivo_02(abas_novo)

    status.info("Carregando as abas de trabalho...")
    df_base = pd.read_excel(xls_base, sheet_name=aba_base)
    df_novo = pd.read_excel(xls_novo, sheet_name=aba_novo)
    progresso.progress(20)

    status.info("Normalizando nomes de colunas...")
    df_base = normalizar_colunas(df_base)
    df_novo = normalizar_colunas(df_novo)

    df_base = _garantir_colunas_finais(df_base)
    df_novo = _padronizar_colunas_arquivo_02(df_novo)
    df_novo = _garantir_colunas_finais(df_novo)
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
    base_sem_aux = _garantir_colunas_finais(base_sem_aux)

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
            "adicionados": 0,
            "total_final": total_final,
            "removidos_por_datahora": removidos_por_datahora,
            "ultima_datahora_base": ultima_ref,
            "situacao": situacao,
            "aba_arquivo_01": aba_base,
            "aba_arquivo_02": aba_novo,
        }
        return df_final, resumo

    status.info("Convertendo coordenadas UTM (SIRGAS2000) para WGS84 apenas nos registros novos...")
    col_x_novo = encontrar_coluna_por_nomes(df_novo_util, ["Longitude"], obrigatoria=False) or encontrar_coluna_por_nomes(df_novo_util, ["Long", "lon"], obrigatoria=False)
    col_y_novo = encontrar_coluna_por_nomes(df_novo_util, ["Latitude"], obrigatoria=False) or encontrar_coluna_por_nomes(df_novo_util, ["Lat"], obrigatoria=False)

    if col_x_novo is None or col_y_novo is None:
        raise ValueError(
            "O Arquivo 02 precisa conter colunas de coordenadas UTM, como Longitude/Latitude."
        )

    df_novo_util = _converter_utm_para_wgs84(df_novo_util, col_x_novo, col_y_novo)
    progresso.progress(70)

    status.info("Padronizando colunas finais dos novos registros...")
    df_novo_util = df_novo_util.drop(columns=["__datahora__"], errors="ignore")
    df_novo_util = _garantir_colunas_finais(df_novo_util)
    df_novo_util = renomear_colunas_equivalentes(base_sem_aux, df_novo_util)
    df_novo_util = _garantir_colunas_finais(df_novo_util)
    progresso.progress(80)

    status.info("Alinhando colunas e preparando inclusao dos novos registros...")
    for coluna in base_sem_aux.columns:
        if coluna not in df_novo_util.columns:
            df_novo_util[coluna] = pd.NA

    df_novo_util = df_novo_util[base_sem_aux.columns]
    progresso.progress(90)

    status.info("Gerando arquivo final...")
    df_final = pd.concat([base_sem_aux, df_novo_util], ignore_index=True)
    adicionados = len(df_novo_util)

    df_final = _garantir_colunas_finais(df_final)
    df_final = criar_coluna_datahora(df_final, col_data_base, col_hora_base, "__datahora__")
    df_final = df_final.sort_values(
        by="__datahora__",
        ascending=True,
        na_position="last",
    ).reset_index(drop=True)
    df_final = df_final.drop(columns=["__datahora__"], errors="ignore")
    progresso.progress(100)

    status.success(f"Processamento concluido. Novos registros adicionados: {adicionados}")

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

    st.caption(
        "O sistema verifica a ultima Data/Hora da base historica, identifica apenas ocorrencias posteriores no arquivo complementar, converte coordenadas UTM (SIRGAS2000) para WGS84 e inclui somente os novos registros no arquivo final."
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

"""
Modulo Deslocamento Forcado
Versao Streamlit adaptada para o QGP Online, com logs de auditoria seguros.
"""

from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st
from pyproj import Transformer

from modulos.utils import nome_arquivo_padrao

NOME_ARQUIVO_FINAL = nome_arquivo_padrao(5, "DESLOCAMENTO-FORCADO")
EPSG_UTM_SIRGAS_24S = 31984
EPSG_WGS84 = 4326


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
    prioridades = ["DESLOCAMENTOFORCADO", "DESLOCAMENTO", "FORCADO", "BASE"]
    normalizadas = {aba: _normalizar_nome_aba(aba) for aba in sheet_names}

    for prioridade in prioridades:
        for aba, nome_norm in normalizadas.items():
            if nome_norm == prioridade:
                return aba

    for aba, nome_norm in normalizadas.items():
        if "DESLOCAMENTO" in nome_norm or "FORCADO" in nome_norm:
            return aba

    return sheet_names[0]


def _selecionar_aba_arquivo_02(sheet_names: list[str]) -> str:
    prioridades = ["DESLOCAMENTOFORCADO", "DESLOCAMENTO", "FORCADO", "COMPLEMENTO"]
    normalizadas = {aba: _normalizar_nome_aba(aba) for aba in sheet_names}

    for prioridade in prioridades:
        for aba, nome_norm in normalizadas.items():
            if nome_norm == prioridade:
                return aba

    for aba, nome_norm in normalizadas.items():
        if "DESLOCAMENTO" in nome_norm or "FORCADO" in nome_norm:
            return aba

    return sheet_names[0]


def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def encontrar_coluna_data(df: pd.DataFrame) -> str:
    for c in df.columns:
        if str(c).strip().lower() == "data":
            return c
    for c in df.columns:
        if "data" in str(c).strip().lower():
            return c
    raise ValueError("Nao foi encontrada a coluna 'Data'.")


def encontrar_coluna_hora(df: pd.DataFrame) -> str:
    for c in df.columns:
        if str(c).strip().lower() == "hora":
            return c
    for c in df.columns:
        if "hora" in str(c).strip().lower():
            return c
    raise ValueError("Nao foi encontrada a coluna 'Hora'.")


def valor_numerico_exato(v):
    if pd.isna(v):
        return None

    if isinstance(v, str):
        s = v.strip()
        if s == "":
            return None
        s = s.replace(".", "").replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return None

    try:
        return float(v)
    except Exception:
        return None


def normalizar_data_para_texto(v):
    if pd.isna(v):
        return None
    if isinstance(v, pd.Timestamp):
        return v.strftime("%d/%m/%Y")

    dt = pd.to_datetime(v, errors="coerce", dayfirst=True)
    if pd.isna(dt):
        return None
    return dt.strftime("%d/%m/%Y")


def normalizar_hora_para_texto(v):
    if pd.isna(v):
        return None
    if isinstance(v, pd.Timestamp):
        return v.strftime("%H:%M:%S")

    s = str(v).strip()
    if s == "":
        return None

    for fmt in ["%H:%M:%S", "%H:%M"]:
        dt = pd.to_datetime(s, errors="coerce", format=fmt)
        if not pd.isna(dt):
            return dt.strftime("%H:%M:%S")

    dt = pd.to_datetime(s, errors="coerce")
    if pd.isna(dt):
        return None
    return dt.strftime("%H:%M:%S")


def criar_coluna_datahora(df: pd.DataFrame, coluna_data: str, coluna_hora: str, nome_coluna="__datahora__"):
    df = df.copy()

    datas = df[coluna_data].apply(normalizar_data_para_texto)
    horas = df[coluna_hora].apply(normalizar_hora_para_texto)

    df[nome_coluna] = pd.to_datetime(
        [
            f"{d} {h}" if d is not None and h is not None else None
            for d, h in zip(datas, horas)
        ],
        errors="coerce",
        dayfirst=True,
    )
    return df


def excluir_coordenadas_invalidas(df: pd.DataFrame, col_lat_utm: str, col_lon_utm: str):
    manter = []

    for lat_raw, lon_raw in zip(df[col_lat_utm], df[col_lon_utm]):
        lat = valor_numerico_exato(lat_raw)
        lon = valor_numerico_exato(lon_raw)

        valido = (
            lat is not None
            and lon is not None
            and lat != 0
            and lon != 0
        )
        manter.append(valido)

    df_filtrado = df.loc[manter].copy()
    removidos = len(df) - len(df_filtrado)
    return df_filtrado, removidos


def reprojetar_utm_para_wgs84(df: pd.DataFrame, col_lat_utm: str, col_lon_utm: str) -> pd.DataFrame:
    df = df.copy()

    transformer = Transformer.from_crs(
        f"EPSG:{EPSG_UTM_SIRGAS_24S}",
        f"EPSG:{EPSG_WGS84}",
        always_xy=True,
    )

    latitudes = []
    longitudes = []

    for lat_utm_raw, lon_utm_raw in zip(df[col_lat_utm], df[col_lon_utm]):
        y = valor_numerico_exato(lat_utm_raw)
        x = valor_numerico_exato(lon_utm_raw)

        if y is None or x is None:
            latitudes.append(pd.NA)
            longitudes.append(pd.NA)
        else:
            lon_wgs, lat_wgs = transformer.transform(x, y)
            latitudes.append(lat_wgs)
            longitudes.append(lon_wgs)

    df["Latitude"] = latitudes
    df["Longitude"] = longitudes
    return df


def obter_ultimo_datahora(df: pd.DataFrame, coluna_datahora: str):
    df_valid = df[df[coluna_datahora].notna()].copy()
    if df_valid.empty:
        return None
    return df_valid[coluna_datahora].max()


def filtrar_apenas_registros_posteriores(df: pd.DataFrame, coluna_datahora: str, limite_datahora):
    if limite_datahora is None:
        return df.copy()
    return df[df[coluna_datahora] > limite_datahora].copy()


def montar_dataframe_no_esquema_da_base(df_base: pd.DataFrame, df_novo: pd.DataFrame) -> pd.DataFrame:
    base_cols = list(df_base.columns)
    saida = pd.DataFrame(index=df_novo.index)

    mapa_preferencial = {
        "Endereço": ["Endereço"],
        "Latitude": ["Latitude"],
        "Longitude": ["Longitude"],
        "Nome da Ocorrência": ["Nome da Ocorrência", "Nome Ocorrencia", "nome da ocorrencia"],
        "Subnome da Ocorrência": ["Subnome da Ocorrência", "Subnome Ocorrencia", "subnome da ocorrencia"],
        "Território": ["Território", "Regiões", "Regioes", "Região", "Regiao"],
        "Município": ["Município"],
        "Bairro": ["Bairro"],
        "AIS": ["AIS", "AISNova", "AIS Nova", "AIS_NOVA"],
        "data": ["data", "Data"],
        "Hora": ["Hora", "hora"],
    }

    for col_base in base_cols:
        candidatos = mapa_preferencial.get(col_base, [col_base])
        coluna_encontrada = None

        for candidato in candidatos:
            if candidato in df_novo.columns:
                coluna_encontrada = candidato
                break

        if coluna_encontrada is not None:
            saida[col_base] = df_novo[coluna_encontrada]
        else:
            saida[col_base] = pd.NA

    return saida[base_cols].copy()


def colunas_existentes(df: pd.DataFrame, colunas_desejadas: list[str]) -> list[str]:
    return [c for c in colunas_desejadas if c in df.columns]


def mostrar_amostra_segura(titulo: str, df: pd.DataFrame, colunas_desejadas: list[str], n: int = 10):
    st.write(titulo)
    cols = colunas_existentes(df, colunas_desejadas)

    if cols:
        st.dataframe(df[cols].head(n))
    else:
        st.warning("Nenhuma das colunas solicitadas existe nesta etapa.")
        st.write("Colunas disponiveis:")
        st.write(list(df.columns))


def gerar_excel_em_memoria(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="DESLOCAMENTO_FORCADO")
    buffer.seek(0)
    return buffer.getvalue()


def processar_deslocamento_forcado(arquivo_01, arquivo_02):
    progresso = st.progress(0)
    status = st.empty()

    arquivo_01.seek(0)
    arquivo_02.seek(0)

    status.info("Lendo os arquivos enviados...")
    xls_base = pd.ExcelFile(arquivo_01)
    xls_novo = pd.ExcelFile(arquivo_02)
    progresso.progress(10)

    aba_base = _selecionar_aba_arquivo_01(xls_base.sheet_names)
    aba_novo = _selecionar_aba_arquivo_02(xls_novo.sheet_names)

    status.info(f"Usando aba '{aba_base}' no Arquivo 01 e '{aba_novo}' no Arquivo 02.")
    df_base = pd.read_excel(xls_base, sheet_name=aba_base)
    df_novo = pd.read_excel(xls_novo, sheet_name=aba_novo)
    progresso.progress(20)

    df_base = normalizar_colunas(df_base)
    df_novo = normalizar_colunas(df_novo)

    mostrar_amostra_segura(
        "Pré-visualização Arquivo 01 (base):",
        df_base,
        ["Endereço", "Latitude", "Longitude", "Nome da Ocorrência", "Subnome da Ocorrência"],
        5,
    )

    mostrar_amostra_segura(
        "Pré-visualização Arquivo 02 (complemento):",
        df_novo,
        ["Endereço", "Latitude", "Longitude", "Nome da Ocorrência", "Subnome da Ocorrência", "Regiões", "AISNova"],
        5,
    )
    progresso.progress(30)

    if "Latitude" not in df_novo.columns or "Longitude" not in df_novo.columns:
        raise ValueError("O Arquivo 02 nao possui as colunas Latitude e Longitude esperadas.")

    df_novo = df_novo.rename(columns={"Latitude": "Latitude_UTM", "Longitude": "Longitude_UTM"})

    mostrar_amostra_segura(
        "Arquivo 02 após renomear Latitude/Longitude -> Latitude_UTM/Longitude_UTM:",
        df_novo,
        ["Latitude_UTM", "Longitude_UTM", "Nome da Ocorrência", "Subnome da Ocorrência"],
        5,
    )
    progresso.progress(40)

    col_data_base = encontrar_coluna_data(df_base)
    col_hora_base = encontrar_coluna_hora(df_base)
    col_data_novo = encontrar_coluna_data(df_novo)
    col_hora_novo = encontrar_coluna_hora(df_novo)

    if col_data_novo != col_data_base:
        df_novo = df_novo.rename(columns={col_data_novo: col_data_base})
    if col_hora_novo != col_hora_base:
        df_novo = df_novo.rename(columns={col_hora_novo: col_hora_base})

    col_data = col_data_base
    col_hora = col_hora_base

    status.info("Excluindo registros com coordenadas invalidas...")
    total_lido_arquivo_02 = len(df_novo)
    df_novo, removidos_invalidos = excluir_coordenadas_invalidas(df_novo, "Latitude_UTM", "Longitude_UTM")

    mostrar_amostra_segura(
        "Arquivo 02 após filtro de coordenadas inválidas:",
        df_novo,
        ["Latitude_UTM", "Longitude_UTM", "Nome da Ocorrência", "Subnome da Ocorrência"],
        5,
    )
    progresso.progress(50)

    status.info("Criando referencia temporal...")
    df_base = criar_coluna_datahora(df_base, col_data, col_hora, "__datahora__")
    df_novo = criar_coluna_datahora(df_novo, col_data, col_hora, "__datahora__")
    ultimo_datahora_base = obter_ultimo_datahora(df_base, "__datahora__")
    st.write("Última Data/Hora da base:", ultimo_datahora_base)
    progresso.progress(60)

    status.info("Filtrando apenas registros posteriores...")
    total_antes_filtro = len(df_novo)
    df_novo_filtrado = filtrar_apenas_registros_posteriores(df_novo, "__datahora__", ultimo_datahora_base)
    removidos_por_datahora = total_antes_filtro - len(df_novo_filtrado)

    mostrar_amostra_segura(
        "Arquivo 02 após filtro por Data/Hora:",
        df_novo_filtrado,
        ["__datahora__", "Latitude_UTM", "Longitude_UTM", "Nome da Ocorrência", "Subnome da Ocorrência"],
        5,
    )
    progresso.progress(70)

    base_sem_aux = df_base.drop(columns=["__datahora__"], errors="ignore").copy()

    if ultimo_datahora_base is None:
        df_novo_util = df_novo.copy()
        situacao = "Base sem Data/Hora valida; complemento incluido integralmente."
    elif df_novo_filtrado.empty:
        df_novo_util = df_novo_filtrado.copy()
        situacao = "Nenhum registro novo posterior a base."
    else:
        df_novo_util = df_novo_filtrado.copy()
        situacao = "Somente registros posteriores a ultima Data/Hora da base foram adicionados."

    if not df_novo_util.empty:
        status.info("Reprojetando coordenadas...")
        df_novo_util = reprojetar_utm_para_wgs84(df_novo_util, "Latitude_UTM", "Longitude_UTM")

        mostrar_amostra_segura(
            "Complemento após reprojeção UTM -> WGS84:",
            df_novo_util,
            ["Latitude_UTM", "Longitude_UTM", "Latitude", "Longitude", "Nome da Ocorrência", "Subnome da Ocorrência"],
            10,
        )

        status.info("Montando complemento no esquema exato da base...")
        df_novo_saida = montar_dataframe_no_esquema_da_base(base_sem_aux, df_novo_util)

        mostrar_amostra_segura(
            "Complemento final no esquema da base:",
            df_novo_saida,
            ["Endereço", "Latitude", "Longitude", "Nome da Ocorrência", "Subnome da Ocorrência", "Território", "Município", "Bairro"],
            10,
        )

        df_final = pd.concat([base_sem_aux, df_novo_saida], ignore_index=True)
        adicionados = len(df_novo_saida)
    else:
        df_final = base_sem_aux.copy()
        adicionados = 0

    progresso.progress(85)

    status.info("Ordenando resultado final...")
    df_final = criar_coluna_datahora(df_final, col_data, col_hora, "__datahora__")
    df_final = df_final.sort_values(by="__datahora__", ascending=True, na_position="last").reset_index(drop=True)
    df_final = df_final.drop(columns=["__datahora__"], errors="ignore")
    progresso.progress(100)

    mostrar_amostra_segura(
        "Resultado final (amostra):",
        df_final,
        ["Endereço", "Latitude", "Longitude", "Nome da Ocorrência", "Subnome da Ocorrência", "Território", "Município", "Bairro"],
        20,
    )

    ultima_ref = (
        ultimo_datahora_base.strftime("%d/%m/%Y %H:%M:%S")
        if ultimo_datahora_base is not None
        else "sem referencia anterior valida"
    )

    resumo = {
        "adicionados": adicionados,
        "total_final": len(df_final),
        "removidos_coord_invalidas": removidos_invalidos,
        "removidos_por_datahora": removidos_por_datahora,
        "ultima_datahora_base": ultima_ref,
        "situacao": situacao,
        "aba_arquivo_01": aba_base,
        "aba_arquivo_02": aba_novo,
        "total_lido_arquivo_02": total_lido_arquivo_02,
    }

    status.success(f"Processo finalizado. {adicionados} registros novos adicionados.")
    return df_final, resumo


def _init_state():
    defaults = {
        "deslocamento_arquivo_01_bytes": None,
        "deslocamento_arquivo_01_nome": None,
        "deslocamento_arquivo_02_bytes": None,
        "deslocamento_arquivo_02_nome": None,
        "deslocamento_resultado_excel": None,
        "deslocamento_resultado_df": None,
        "deslocamento_resumo": None,
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def render():
    _init_state()

    st.subheader("Deslocamento Forcado")
    st.write("Envie a base historica e o arquivo complementar para atualizar a base com novos registros.")

    arquivo_01 = st.file_uploader(
        "Arquivo 01 - Base historica de Deslocamento Forcado",
        type=["xlsx", "xls"],
        key="deslocamento_upload_01",
    )

    arquivo_02 = st.file_uploader(
        "Arquivo 02 - Complemento de Deslocamento Forcado",
        type=["xlsx", "xls"],
        key="deslocamento_upload_02",
    )

    if arquivo_01 is not None:
        arquivo_01.seek(0)
        st.session_state.deslocamento_arquivo_01_bytes = arquivo_01.read()
        st.session_state.deslocamento_arquivo_01_nome = arquivo_01.name

    if arquivo_02 is not None:
        arquivo_02.seek(0)
        st.session_state.deslocamento_arquivo_02_bytes = arquivo_02.read()
        st.session_state.deslocamento_arquivo_02_nome = arquivo_02.name

    pode_processar = (
        st.session_state.deslocamento_arquivo_01_bytes is not None
        and st.session_state.deslocamento_arquivo_02_bytes is not None
    )

    if st.button("Processar Deslocamento Forcado", type="primary", disabled=not pode_processar):
        try:
            arquivo_01_buffer = BytesIO(st.session_state.deslocamento_arquivo_01_bytes)
            arquivo_02_buffer = BytesIO(st.session_state.deslocamento_arquivo_02_bytes)

            df_final, resumo = processar_deslocamento_forcado(arquivo_01_buffer, arquivo_02_buffer)
            arquivo_excel_bytes = gerar_excel_em_memoria(df_final)

            st.session_state.deslocamento_resultado_df = df_final
            st.session_state.deslocamento_resumo = resumo
            st.session_state.deslocamento_resultado_excel = arquivo_excel_bytes

        except Exception as exc:
            st.exception(exc)

    if (
        st.session_state.deslocamento_resultado_df is not None
        and st.session_state.deslocamento_resumo is not None
    ):
        resumo = st.session_state.deslocamento_resumo

        c1, c2, c3 = st.columns(3)
        c1.metric("Novos registros adicionados", resumo.get("adicionados", 0))
        c2.metric("Total final da base", resumo.get("total_final", 0))
        c3.metric("Coordenadas invalidas removidas", resumo.get("removidos_coord_invalidas", 0))

        st.info(
            f"Aba Arquivo 01: {resumo.get('aba_arquivo_01', '-')} | "
            f"Aba Arquivo 02: {resumo.get('aba_arquivo_02', '-')}"
        )

        st.info(
            f"Ultima Data/Hora da base: {resumo.get('ultima_datahora_base', '-')} | "
            f"Removidos por filtro temporal: {resumo.get('removidos_por_datahora', 0)}"
        )

        st.caption(resumo.get("situacao", "Processamento concluido."))

        if st.session_state.deslocamento_resultado_excel is not None:
            st.download_button(
                label="Baixar arquivo final",
                data=st.session_state.deslocamento_resultado_excel,
                file_name=NOME_ARQUIVO_FINAL,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="deslocamento_download_final",
            )


interface_deslocamento_forcado = render

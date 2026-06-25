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


def excluir_coordenadas_invalidas(df: pd.DataFrame, col_easting: str, col_northing: str):
    manter = []

    for e_raw, n_raw in zip(df[col_easting], df[col_northing]):
        e = valor_numerico_exato(e_raw)
        n = valor_numerico_exato(n_raw)

        valido = (
            e is not None
            and n is not None
            and e != 0
            and n != 0
        )
        manter.append(valido)

    df_filtrado = df.loc[manter].copy()
    removidos = len(df) - len(df_filtrado)
    return df_filtrado, removidos


def reprojetar_utm_para_wgs84(df: pd.DataFrame, col_easting: str, col_northing: str) -> pd.DataFrame:
    """
    No Arquivo 02:
    - coluna 'Latitude'  = UTM Easting  (X / Oriental) <- nome enganoso
    - coluna 'Longitude' = UTM Northing (Y / Norte)    <- nome enganoso

    O Transformer com always_xy=True espera (X, Y) = (Easting, Northing).
    Portanto: transformer.transform(easting, northing)
    Retorna: (longitude_wgs, latitude_wgs)
    """
    df = df.copy()

    transformer = Transformer.from_crs(
        f"EPSG:{EPSG_UTM_SIRGAS_24S}",
        f"EPSG:{EPSG_WGS84}",
        always_xy=True,
    )

    latitudes_wgs = []
    longitudes_wgs = []

    for easting_raw, northing_raw in zip(df[col_easting], df[col_northing]):
        easting = valor_numerico_exato(easting_raw)
        northing = valor_numerico_exato(northing_raw)

        if easting is None or northing is None:
            latitudes_wgs.append(pd.NA)
            longitudes_wgs.append(pd.NA)
        else:
            lon_wgs, lat_wgs = transformer.transform(easting, northing)
            latitudes_wgs.append(lat_wgs)
            longitudes_wgs.append(lon_wgs)

    df["Latitude"] = latitudes_wgs
    df["Longitude"] = longitudes_wgs
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
    """
    Monta o complemento usando EXATAMENTE o esquema do Arquivo 01.
    Garante que Nome da Ocorrencia e Subnome da Ocorrencia apareçam no resultado.
    """
    base_cols = list(df_base.columns)
    saida = pd.DataFrame(index=df_novo.index)

    mapa_preferencial = {
        "Endereço": ["Endereço", "Endereco"],
        "Latitude": ["Latitude"],
        "Longitude": ["Longitude"],
        "Nome da Ocorrência": ["Nome da Ocorrência", "Nome da Ocorrencia", "Nome Ocorrencia"],
        "Subnome da Ocorrência": ["Subnome da Ocorrência", "Subnome da Ocorrencia", "Subnome Ocorrencia"],
        "Território": ["Território", "Territorio", "Regiões", "Regioes", "Região", "Regiao"],
        "Município": ["Município", "Municipio"],
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
            saida[col_base] = df_novo[coluna_encontrada].values
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
        st.write("Colunas disponiveis:", list(df.columns))


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
        "AUDITORIA — Arquivo 01 (base):",
        df_base,
        ["Endereço", "Latitude", "Longitude", "Nome da Ocorrência", "Subnome da Ocorrência"],
        5,
    )

    mostrar_amostra_segura(
        "AUDITORIA — Arquivo 02 (complemento, colunas brutas):",
        df_novo,
        ["Endereço", "Latitude", "Longitude", "Nome da Ocorrência", "Subnome da Ocorrência", "Regiões", "AISNova"],
        5,
    )
    progresso.progress(30)

    if "Latitude" not in df_novo.columns or "Longitude" not in df_novo.columns:
        raise ValueError("O Arquivo 02 nao possui as colunas Latitude e Longitude esperadas.")

    # No Arquivo 02:
    # 'Latitude'  = UTM Easting  (X / Oriental) — nome enganoso
    # 'Longitude' = UTM Northing (Y / Norte)    — nome enganoso
    df_novo = df_novo.rename(columns={
        "Latitude": "UTM_Easting",
        "Longitude": "UTM_Northing",
    })

    mostrar_amostra_segura(
        "AUDITORIA — Arquivo 02 após renomear coordenadas UTM:",
        df_novo,
        ["UTM_Easting", "UTM_Northing", "Nome da Ocorrência", "Subnome da Ocorrência"],
        5,
    )
    progresso.progress(40

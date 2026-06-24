"""
utils.py - Modulo utilitario compartilhado para QGP Online
Funcoes comuns usadas por todos os indicadores
"""

import io
import pandas as pd
from datetime import datetime


# ===========================================================
# NORMALIZACAO DE COLUNAS
# ===========================================================

def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Remove espacos dos nomes das colunas."""
    df.columns = [str(c).strip() for c in df.columns]
    return df


# ===========================================================
# BUSCA DE COLUNAS
# ===========================================================

def encontrar_coluna_data(df: pd.DataFrame) -> str:
    """Localiza a coluna de data (exata ou aproximada)."""
    exatos = [c for c in df.columns if str(c).strip().lower() == "data"]
    if exatos:
        return exatos[0]
    aproximados = [c for c in df.columns if "data" in str(c).strip().lower()]
    if aproximados:
        return aproximados[0]
    raise ValueError("Nao foi encontrada a coluna Data.")


def encontrar_coluna_hora(df: pd.DataFrame) -> str:
    """Localiza a coluna de hora (exata ou aproximada)."""
    exatos = [c for c in df.columns if str(c).strip().lower() == "hora"]
    if exatos:
        return exatos[0]
    aproximados = [c for c in df.columns if "hora" in str(c).strip().lower()]
    if aproximados:
        return aproximados[0]
    raise ValueError("Nao foi encontrada a coluna Hora.")


def encontrar_coluna_por_nomes(
    df: pd.DataFrame,
    nomes_possiveis: list,
    obrigatoria: bool = True
):
    """Localiza coluna pelo nome exato ou parcial a partir de lista de candidatos."""
    cols_map = {str(c).strip().lower(): c for c in df.columns}
    for nome in nomes_possiveis:
        if nome.lower() in cols_map:
            return cols_map[nome.lower()]
    for c in df.columns:
        c_l = str(c).strip().lower()
        for nome in nomes_possiveis:
            if nome.lower() in c_l:
                return c
    if obrigatoria:
        raise ValueError(
            f"Nao foi possivel localizar nenhuma das colunas: {nomes_possiveis}"
        )
    return None


# ===========================================================
# RENOMEACAO DE EQUIVALENCIAS
# ===========================================================

MAPA_EQUIVALENCIAS_PADRAO = {
    "AIS": ["AIS-Nova", "AIS Nova", "AIS-NOVA", "ais-nova", "aisnova",
            "AIS_Nova", "AISNOVA", "ais nova", "ais_nova"],
    "Territorio": ["Regioes", "Regiao", "regioes", "regiao",
                   "Regioes", "Regiao", "Territorio", "territorio"],
}


def renomear_colunas_equivalentes(
    df_base: pd.DataFrame,
    df_novo: pd.DataFrame,
    mapa_extra: dict = None
) -> pd.DataFrame:
    """Renomeia colunas do df_novo para corresponder ao layout do df_base."""
    mapa = dict(MAPA_EQUIVALENCIAS_PADRAO)
    if mapa_extra:
        mapa.update(mapa_extra)

    colunas_base_map = {str(c).strip().lower(): c for c in df_base.columns}
    colunas_novo_map = {str(c).strip().lower(): c for c in df_novo.columns}
    renomeacoes = {}

    for coluna_base_oficial, aliases in mapa.items():
        chave_base = coluna_base_oficial.strip().lower()
        if chave_base not in colunas_base_map:
            continue
        nome_real_base = colunas_base_map[chave_base]
        if nome_real_base in df_novo.columns:
            continue
        for alias in aliases:
            chave_alias = alias.strip().lower()
            if chave_alias in colunas_novo_map:
                renomeacoes[colunas_novo_map[chave_alias]] = nome_real_base
                break

    if renomeacoes:
        df_novo = df_novo.rename(columns=renomeacoes)
    return df_novo


# ===========================================================
# ALINHAMENTO DE COLUNAS
# ===========================================================

def alinhar_colunas_com_base(
    df_base: pd.DataFrame,
    df_novo: pd.DataFrame
) -> pd.DataFrame:
    """Garante que df_novo tenha exatamente as mesmas colunas que df_base."""
    df_novo = renomear_colunas_equivalentes(df_base, df_novo)
    for col in df_base.columns:
        if col not in df_novo.columns:
            df_novo[col] = pd.NA
    return df_novo[list(df_base.columns)]


# ===========================================================
# CONVERSAO DE VALORES
# ===========================================================

def valor_numerico_exato(v):
    """Converte valor para float, retorna None se invalido."""
    if pd.isna(v):
        return None
    if isinstance(v, str):
        s = v.strip()
        if not s:
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


# ===========================================================
# NORMALIZACAO DE DATAS E HORAS
# ===========================================================

def normalizar_data_para_texto(v) -> str:
    """Converte qualquer valor de data para string d/m/Y."""
    if pd.isna(v):
        return None
    if isinstance(v, pd.Timestamp):
        return v.strftime("%d/%m/%Y")
    try:
        dt = pd.to_datetime(v, errors='coerce', dayfirst=True)
        if pd.isna(dt):
            return None
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return None


def normalizar_hora_para_texto(v) -> str:
    """Converte qualquer valor de hora para string H:M:S."""
    if pd.isna(v):
        return None
    if isinstance(v, pd.Timestamp):
        return v.strftime("%H:%M:%S")
    s = str(v).strip()
    if not s:
        return None
    for fmt in ["%H:%M:%S", "%H:%M"]:
        dt = pd.to_datetime(s, errors='coerce', format=fmt)
        if not pd.isna(dt):
            return dt.strftime("%H:%M:%S")
    try:
        dt = pd.to_datetime(s, errors='coerce')
        if not pd.isna(dt):
            return dt.strftime("%H:%M:%S")
    except Exception:
        pass
    return None


def criar_coluna_datahora(
    df: pd.DataFrame,
    coluna_data: str,
    coluna_hora: str,
    nome_coluna: str = "datahora"
) -> pd.DataFrame:
    """Cria coluna DataHora combinando Data e Hora."""
    datas = df[coluna_data].apply(normalizar_data_para_texto)
    horas = df[coluna_hora].apply(normalizar_hora_para_texto)
    combinado = []
    for d, h in zip(datas, horas):
        if d is None or h is None:
            combinado.append(pd.NaT)
        else:
            combinado.append(
                pd.to_datetime(f"{d} {h}", errors='coerce', dayfirst=True)
            )
    df[nome_coluna] = combinado
    return df


def converter_coluna_data(df: pd.DataFrame, coluna_data: str) -> pd.DataFrame:
    """Converte coluna de data para datetime."""
    df[coluna_data] = pd.to_datetime(
        df[coluna_data], errors='coerce', dayfirst=True
    )
    return df


# ===========================================================
# COORDENADAS
# ===========================================================

def excluir_coordenadas_invalidas(
    df: pd.DataFrame,
    col_lat: str,
    col_lon: str
) -> pd.DataFrame:
    """Remove registros com coordenadas nulas ou zero."""
    manter = []
    for lat_raw, lon_raw in zip(df[col_lat], df[col_lon]):
        lat = valor_numerico_exato(lat_raw)
        lon = valor_numerico_exato(lon_raw)
        if lat is None or lon is None or lat == 0 or lon == 0:
            manter.append(False)
        else:
            manter.append(True)
    return df.loc[manter].copy()


def reprojetar_utm_para_wgs84(
    df: pd.DataFrame,
    col_y: str,
    col_x: str,
    col_lat_destino: str = "LAT",
    col_lon_destino: str = "LONG"
) -> pd.DataFrame:
    """Converte coordenadas UTM SIRGAS2000 (EPSG:31984) para WGS84."""
    try:
        from pyproj import Transformer
        transformer = Transformer.from_crs(
            "EPSG:31984", "EPSG:4326", always_xy=True
        )
        lat_resultado = []
        lon_resultado = []
        for y_raw, x_raw in zip(df[col_y], df[col_x]):
            y = valor_numerico_exato(y_raw)
            x = valor_numerico_exato(x_raw)
            if y is None or x is None:
                lat_resultado.append(pd.NA)
                lon_resultado.append(pd.NA)
            else:
                lon, lat = transformer.transform(x, y)
                lat_resultado.append(lat)
                lon_resultado.append(lon)
        df[col_lat_destino] = lat_resultado
        df[col_lon_destino] = lon_resultado
    except ImportError:
        raise ImportError(
            "pyproj nao esta instalado. Adicione 'pyproj>=3.6.0' ao requirements.txt"
        )
    return df


# ===========================================================
# FILTROS TEMPORAIS
# ===========================================================

def obter_ultima_datahora(df: pd.DataFrame, coluna_datahora: str):
    """Retorna a data/hora maxima valida do DataFrame."""
    df_valid = df[df[coluna_datahora].notna()].copy()
    if df_valid.empty:
        return None
    return df_valid[coluna_datahora].max()


def filtrar_apenas_registros_posteriores(
    df: pd.DataFrame,
    coluna_datahora: str,
    limite_datahora
) -> pd.DataFrame:
    """Retorna apenas registros com DataHora posterior ao limite."""
    if limite_datahora is None:
        return df.copy()
    return df[df[coluna_datahora] > limite_datahora].copy()


def obter_meses_anos(df: pd.DataFrame, coluna_data: str) -> set:
    """Retorna conjunto de tuplas (ano, mes) presentes no DataFrame."""
    base_valida = df[df[coluna_data].notna()].copy()
    return set(
        zip(base_valida[coluna_data].dt.year, base_valida[coluna_data].dt.month)
    )


# ===========================================================
# EXPORTACAO
# ===========================================================

def gerar_arquivo_excel(
    df: pd.DataFrame,
    sheet_name: str = "Dados"
) -> bytes:
    """Gera arquivo Excel em memoria e retorna bytes para download."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()


def nome_arquivo_padrao(numero: int, sigla: str) -> str:
    """Gera nome padrao do arquivo de saida: ex. '1-CVLI-2026-QGP.xlsx'"""
    return f"{numero}-{sigla}-{datetime.now().year}-QGP.xlsx"

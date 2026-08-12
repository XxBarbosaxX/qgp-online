from __future__ import annotations

import io
import re
import unicodedata
from datetime import datetime
from typing import Any, Optional, Tuple

import pandas as pd

# ===========================================================
# NORMALIZAÇÃO DE TEXTO E COLUNAS
# ===========================================================


def normalizar_texto(valor: Any) -> str:
    """Normaliza texto removendo acentos, espaços extras e padronizando caixa."""
    if valor is None:
        return ""

    texto = str(valor).strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\s+", " ", texto)
    return texto.lower().strip()


def normalizar_nome_coluna(valor: Any) -> str:
    """Normaliza nome de coluna para comparação semântica."""
    texto = normalizar_texto(valor)
    texto = texto.replace("/", " ")
    texto = texto.replace("-", " ")
    texto = texto.replace("_", " ")
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def normalizar_nome_aba(valor: Any) -> str:
    """Normaliza nome de aba para comparação exata e tolerante a acentos/espaços."""
    texto = normalizar_texto(valor)
    texto = texto.replace("_", "")
    texto = texto.replace("-", "")
    texto = texto.replace("/", "")
    texto = re.sub(r"\s+", "", texto)
    return texto


def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza os nomes das colunas:
    - remove espaços excedentes;
    - trata colunas vazias/sem nome;
    - evita duplicidade de cabeçalhos.
    """
    novas_colunas: list[str] = []
    contadores: dict[str, int] = {}
    contador_sem_nome = 0

    for coluna in df.columns:
        coluna_original = "" if coluna is None else str(coluna).strip()

        if not coluna_original or coluna_original.lower().startswith("unnamed:"):
            contador_sem_nome += 1
            nome_base = f"coluna_sem_nome_{contador_sem_nome}"
        else:
            nome_base = re.sub(r"\s+", " ", coluna_original).strip()

        if nome_base in contadores:
            contadores[nome_base] += 1
            nome_final = f"{nome_base}_{contadores[nome_base]}"
        else:
            contadores[nome_base] = 1
            nome_final = nome_base

        novas_colunas.append(nome_final)

    df = df.copy()
    df.columns = novas_colunas
    return df


# ===========================================================
# CHAVEAMENTO DE ABAS DE ATUALIZAÇÃO
# ===========================================================

ABAS_ATUALIZACAO: dict[str, str] = {
    "cvli": "CVLI",
    "cvp_sportal": "CVPCIOPS",
    "cvp_sip": "CVPSIP",
    "perturbacao_sossego": "Perturbação ao Sossego Alheio",
    "deslocamento_forcado": "Grupo Criminoso",
    "roubo_veiculo_sportal": "CVPCIOPS",
    "roubo_veiculo_sip": "CVPSIP",
    "acidente_transito": "Acidente de Trânsito",
    "furto_veiculo_sportal": "Furto CIOPS",
    "furto_veiculo_sip": "Furto SIP",
}


def selecionar_aba_exata(sheet_names: list[str], nome_esperado: str) -> str:
    """Seleciona uma aba pelo nome exato, com tolerância a acentos, espaços e separadores."""
    alvo = normalizar_nome_aba(nome_esperado)

    for aba in sheet_names:
        if normalizar_nome_aba(aba) == alvo:
            return aba

    raise ValueError(
        f"A aba obrigatória '{nome_esperado}' não foi encontrada no arquivo. "
        f"Abas disponíveis: {sheet_names}"
    )


def selecionar_aba_atualizacao(sheet_names: list[str], chave_modulo: str) -> str:
    """Seleciona a aba correta do Arquivo 02 com base no chaveamento oficial do módulo."""
    if chave_modulo not in ABAS_ATUALIZACAO:
        raise KeyError(
            f"Chave de módulo inválida: '{chave_modulo}'. "
            f"Chaves disponíveis: {sorted(ABAS_ATUALIZACAO)}"
        )

    return selecionar_aba_exata(sheet_names, ABAS_ATUALIZACAO[chave_modulo])


# ===========================================================
# BUSCA DE COLUNAS
# ===========================================================


def encontrar_coluna_por_nomes(
    df: pd.DataFrame,
    nomes_possiveis: list[str],
    obrigatoria: bool = True,
) -> str | None:
    """
    Localiza coluna pelo nome exato ou parcial a partir de lista de candidatos.
    Faz comparação com normalização semântica.
    """
    colunas_normalizadas = {
        normalizar_nome_coluna(coluna): coluna for coluna in df.columns
    }

    for nome in nomes_possiveis:
        chave = normalizar_nome_coluna(nome)
        if chave in colunas_normalizadas:
            return colunas_normalizadas[chave]

    for coluna in df.columns:
        coluna_norm = normalizar_nome_coluna(coluna)
        for nome in nomes_possiveis:
            nome_norm = normalizar_nome_coluna(nome)
            if nome_norm in coluna_norm or coluna_norm in nome_norm:
                return coluna

    if obrigatoria:
        raise ValueError(
            f"Não foi possível localizar nenhuma das colunas: {nomes_possiveis}"
        )
    return None


def encontrar_coluna_data(df: pd.DataFrame) -> str:
    """
    Localiza a coluna principal de data, evitando falsos positivos
    como 'Data de Nascimento'.
    """
    candidatos_prioritarios = [
        "data",
        "dt fato",
        "data fato",
        "data ocorrencia",
        "data da ocorrencia",
    ]

    coluna = encontrar_coluna_por_nomes(df, candidatos_prioritarios, obrigatoria=False)
    if coluna:
        return coluna

    candidatos_secundarios = []
    for col in df.columns:
        col_norm = normalizar_nome_coluna(col)
        if "data" in col_norm and "nascimento" not in col_norm:
            candidatos_secundarios.append(col)

    if candidatos_secundarios:
        return candidatos_secundarios[0]

    raise ValueError("Não foi encontrada uma coluna de data válida.")


def encontrar_coluna_hora(df: pd.DataFrame) -> str:
    """Localiza a coluna principal de hora."""
    candidatos = [
        "hora",
        "hora ocorrencia",
        "hora da ocorrencia",
        "hora fato",
    ]

    coluna = encontrar_coluna_por_nomes(df, candidatos, obrigatoria=False)
    if coluna:
        return coluna

    aproximadas = [c for c in df.columns if "hora" in normalizar_nome_coluna(c)]
    if aproximadas:
        return aproximadas[0]

    raise ValueError("Não foi encontrada a coluna Hora.")


# ===========================================================
# EQUIVALÊNCIAS DE COLUNAS
# ===========================================================

MAPA_EQUIVALENCIAS_PADRAO: dict[str, list[str]] = {
    "AISNova": [
        "AIS",
        "AIS-Nova",
        "AIS Nova",
        "AIS_Nova",
        "aisnova",
        "ais nova",
        "ais_nova",
        "ais-nova",
    ],
    "Regiões": [
        "Territorio",
        "Território",
        "Regiao",
        "Região",
        "Regioes",
        "Regiões",
    ],
    "Endereço": [
        "Endereco",
        "Logradouro",
        "Logradorou",
        "Endereço do Fato",
    ],
    "Complemento do Endereço": [
        "Complemento Endereço",
        "Complemento do Endereco",
        "Complemento 1",
        "Complemento 2",
    ],
    "Município": [
        "Municipio",
        "Cidade",
    ],
    "Nome da Ocorrência": [
        "Nome Ocorrência",
        "Nome da Ocorrencia",
    ],
    "Subnome da Ocorrência": [
        "Subnome Ocorrência",
        "Subnome da Ocorrencia",
    ],
}


def renomear_colunas_equivalentes(
    df_base: pd.DataFrame,
    df_novo: pd.DataFrame,
    mapa_extra: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    """
    Renomeia colunas do df_novo para corresponder ao layout do df_base
    usando equivalências semânticas.
    """
    mapa = dict(MAPA_EQUIVALENCIAS_PADRAO)
    if mapa_extra:
        mapa.update(mapa_extra)

    df_novo = df_novo.copy()

    colunas_base_map = {
        normalizar_nome_coluna(coluna): coluna for coluna in df_base.columns
    }
    colunas_novo_map = {
        normalizar_nome_coluna(coluna): coluna for coluna in df_novo.columns
    }

    renomeacoes: dict[str, str] = {}

    for coluna_base_oficial, aliases in mapa.items():
        chave_base = normalizar_nome_coluna(coluna_base_oficial)
        if chave_base not in colunas_base_map:
            continue

        nome_real_base = colunas_base_map[chave_base]
        if nome_real_base in df_novo.columns:
            continue

        for alias in aliases:
            chave_alias = normalizar_nome_coluna(alias)
            if chave_alias in colunas_novo_map:
                renomeacoes[colunas_novo_map[chave_alias]] = nome_real_base
                break

    if renomeacoes:
        df_novo = df_novo.rename(columns=renomeacoes)

    return df_novo


def alinhar_colunas_com_base(
    df_base: pd.DataFrame,
    df_novo: pd.DataFrame,
    valor_padrao: Any = pd.NA,
) -> pd.DataFrame:
    """
    Garante que df_novo tenha exatamente as mesmas colunas que df_base.
    Permite definir valor padrão para colunas ausentes.
    """
    df_novo = renomear_colunas_equivalentes(df_base, df_novo)

    for col in df_base.columns:
        if col not in df_novo.columns:
            df_novo[col] = valor_padrao

    return df_novo[list(df_base.columns)].copy()


# ===========================================================
# CONVERSÃO DE VALORES
# ===========================================================


def valor_numerico_exato(valor: Any) -> float | None:
    """
    Converte valor textual ou numérico para float com suporte a:
    - decimal com vírgula;
    - decimal com ponto;
    - milhares com ponto e decimal com vírgula.
    """
    if pd.isna(valor):
        return None

    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)

    texto = str(valor).strip()
    if not texto:
        return None

    texto = texto.replace(" ", "")

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(".", "").replace(",", ".")

    try:
        return float(texto)
    except ValueError:
        return None


# ===========================================================
# NORMALIZAÇÃO DE DATAS E HORAS
# ===========================================================


def normalizar_data_para_texto(valor: Any) -> str | None:
    """Converte qualquer valor de data para string dd/mm/YYYY."""
    if pd.isna(valor):
        return None

    if isinstance(valor, pd.Timestamp):
        return valor.strftime("%d/%m/%Y")

    try:
        dt = pd.to_datetime(valor, errors="coerce", dayfirst=True)
        if pd.isna(dt):
            return None
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return None


def normalizar_hora_para_texto(valor: Any) -> str | None:
    """Converte qualquer valor de hora para string HH:MM:SS."""
    if pd.isna(valor):
        return None

    if isinstance(valor, pd.Timestamp):
        return valor.strftime("%H:%M:%S")

    texto = str(valor).strip()
    if not texto:
        return None

    for fmt in ("%H:%M:%S", "%H:%M"):
        dt = pd.to_datetime(texto, errors="coerce", format=fmt)
        if not pd.isna(dt):
            return dt.strftime("%H:%M:%S")

    try:
        dt = pd.to_datetime(texto, errors="coerce")
        if not pd.isna(dt):
            return dt.strftime("%H:%M:%S")
    except Exception:
        pass

    return None


def criar_coluna_datahora(
    df: pd.DataFrame,
    coluna_data: str,
    coluna_hora: str,
    nome_coluna: str = "datahora",
) -> pd.DataFrame:
    """Cria coluna DataHora combinando data e hora."""
    df = df.copy()

    datas = df[coluna_data].apply(normalizar_data_para_texto)
    horas = df[coluna_hora].apply(normalizar_hora_para_texto)

    combinado = []
    for data_txt, hora_txt in zip(datas, horas):
        if data_txt is None or hora_txt is None:
            combinado.append(pd.NaT)
        else:
            combinado.append(
                pd.to_datetime(
                    f"{data_txt} {hora_txt}",
                    errors="coerce",
                    dayfirst=True,
                )
            )

    df[nome_coluna] = combinado
    return df


def converter_coluna_data(df: pd.DataFrame, coluna_data: str) -> pd.DataFrame:
    """Converte coluna de data para datetime."""
    df = df.copy()
    df[coluna_data] = pd.to_datetime(
        df[coluna_data],
        errors="coerce",
        dayfirst=True,
    )
    return df


# ===========================================================
# COORDENADAS
# ===========================================================


def excluir_coordenadas_invalidas(
    df: pd.DataFrame,
    col_lat: str,
    col_lon: str,
) -> pd.DataFrame:
    """Remove registros com coordenadas nulas, inválidas ou zero."""
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
    col_lon_destino: str = "LONG",
) -> pd.DataFrame:
    """Converte coordenadas UTM SIRGAS2000 (EPSG:31984) para WGS84."""
    try:
        from pyproj import Transformer

        transformer = Transformer.from_crs(
            "EPSG:31984",
            "EPSG:4326",
            always_xy=True,
        )
    except ImportError as exc:
        raise ImportError(
            "pyproj não está instalado. Adicione 'pyproj>=3.6.0' ao requirements.txt"
        ) from exc

    df = df.copy()
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
    return df


def converter_coordenadas_para_wgs84_auto(
    df: pd.DataFrame,
    col_y_or_lat: str,
    col_x_or_lon: str,
    col_lat_destino: str = "LAT",
    col_lon_destino: str = "LONG",
) -> pd.DataFrame:
    """
    Detecta automaticamente se as coordenadas estão em graus decimais (WGS84)
    ou em UTM projetado, e converte apenas quando necessário.

    Suporta três cenários:
      - Graus decimais (lat/lon): passados diretamente para a saída.
      - UTM com ordem correta (col_y=Northing, col_x=Easting): reprojetado via EPSG:31984 ou EPSG:31983.
      - UTM com colunas invertidas (col_y=Easting, col_x=Northing): detecta a inversão e corrige
        antes de reprojetar.

    Zonas suportadas:
      - EPSG:31984 — SIRGAS 2000 / UTM zona 24S.
      - EPSG:31983 — SIRGAS 2000 / UTM zona 23S.
    """
    try:
        from pyproj import Transformer

        transformer_24s = Transformer.from_crs(
            "EPSG:31984",
            "EPSG:4326",
            always_xy=True,
        )
        transformer_23s = Transformer.from_crs(
            "EPSG:31983",
            "EPSG:4326",
            always_xy=True,
        )
    except ImportError as exc:
        raise ImportError(
            "pyproj não está instalado. Adicione 'pyproj>=3.6.0' ao requirements.txt"
        ) from exc

    _LON_MIN, _LON_MAX = -75.0, -28.0
    _LAT_MIN, _LAT_MAX = -35.0, 6.0

    def _reprojetar(
        easting: float,
        northing: float,
    ) -> Optional[Tuple[float, float]]:
        """
        Tenta reprojetar via zona 24S; usa 23S como fallback.
        Retorna (lat, lon) ou None.
        """
        for transformer in (transformer_24s, transformer_23s):
            try:
                lon, lat = transformer.transform(easting, northing)
                if _LON_MIN <= lon <= _LON_MAX and _LAT_MIN <= lat <= _LAT_MAX:
                    return lat, lon
            except Exception:
                continue
        return None

    df = df.copy()
    lat_resultado = []
    lon_resultado = []

    for y_raw, x_raw in zip(df[col_y_or_lat], df[col_x_or_lon]):
        y = valor_numerico_exato(y_raw)
        x = valor_numerico_exato(x_raw)

        if y is None or x is None or y == 0 or x == 0:
            lat_resultado.append(pd.NA)
            lon_resultado.append(pd.NA)
            continue

        parecem_graus = (-90.0 <= y <= 90.0) and (-180.0 <= x <= 180.0)

        parecem_utm_direto = (
            100_000 <= abs(x) <= 900_000
            and 1_000_000 <= abs(y) <= 10_000_000
        )

        parecem_utm_invertido = (
            100_000 <= abs(y) <= 900_000
            and 1_000_000 <= abs(x) <= 10_000_000
        )

        if parecem_graus:
            lat_resultado.append(y)
            lon_resultado.append(x)

        elif parecem_utm_direto:
            resultado = _reprojetar(easting=x, northing=y)
            if resultado is not None:
                lat_resultado.append(resultado[0])
                lon_resultado.append(resultado[1])
            else:
                lat_resultado.append(pd.NA)
                lon_resultado.append(pd.NA)

        elif parecem_utm_invertido:
            resultado = _reprojetar(easting=y, northing=x)
            if resultado is not None:
                lat_resultado.append(resultado[0])
                lon_resultado.append(resultado[1])
            else:
                lat_resultado.append(pd.NA)
                lon_resultado.append(pd.NA)

        else:
            lat_resultado.append(pd.NA)
            lon_resultado.append(pd.NA)

    df[col_lat_destino] = lat_resultado
    df[col_lon_destino] = lon_resultado
    return df


# ===========================================================
# FILTROS TEMPORAIS
# ===========================================================


def obter_ultima_datahora(df: pd.DataFrame, coluna_datahora: str) -> pd.Timestamp | None:
    """Retorna a data/hora máxima válida do DataFrame."""
    df_valid = df[df[coluna_datahora].notna()].copy()
    if df_valid.empty:
        return None
    return df_valid[coluna_datahora].max()


def filtrar_apenas_registros_posteriores(
    df: pd.DataFrame,
    coluna_datahora: str,
    limite_datahora: pd.Timestamp | None,
) -> pd.DataFrame:
    """Retorna apenas registros com DataHora posterior ao limite."""
    if limite_datahora is None:
        return df.copy()
    return df[df[coluna_datahora] > limite_datahora].copy()


def obter_meses_anos(df: pd.DataFrame, coluna_data: str) -> set[tuple[int, int]]:
    """Retorna conjunto de tuplas (ano, mes) presentes no DataFrame."""
    base = df.copy()
    base[coluna_data] = pd.to_datetime(base[coluna_data], errors="coerce", dayfirst=True)
    base_valida = base[base[coluna_data].notna()].copy()
    return set(
        zip(base_valida[coluna_data].dt.year, base_valida[coluna_data].dt.month)
    )


# ===========================================================
# EXPORTAÇÃO
# ===========================================================


def gerar_arquivo_excel(
    df: pd.DataFrame,
    sheet_name: str = "Dados",
) -> bytes:
    """Gera arquivo Excel em memória e retorna bytes para download."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()


def nome_arquivo_padrao(numero: int, sigla: str) -> str:
    """Gera nome padrão do arquivo de saída."""
    return f"{numero}-{sigla}-{datetime.now().year}-QGP.xlsx"

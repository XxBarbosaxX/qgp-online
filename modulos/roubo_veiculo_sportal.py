"""<br>Modulo Roubo de Veiculo SPORTAL<br>Versao Streamlit adaptada para o QGP Online, com logs de auditoria seguros.<br>"""

from __future__ import annotations

from io import BytesIO
import re
import unicodedata

import pandas as pd
import streamlit as st
from pyproj import Transformer

from modulos.utils import nome_arquivo_padrao


NOME_ARQUIVO_FINAL = nome_arquivo_padrao(6, "ROUBO-DE-VEICULO-SPORTAL-LAT-LONG")
EPSG_UTM_SIRGAS_24S = 31984
EPSG_WGS84 = 4326
VALOR_FILTRO_OCORRENCIA = "ROUBO DE VEÍCULO"


def _normalizar_nome_aba(nome: str) -> str:
    return (
        str(nome or "")
        .strip()
        .upper()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
    )


def _normalizar_texto(valor: str) -> str:
    valor = str(valor or "").strip()
    valor = unicodedata.normalize("NFKD", valor)
    valor = "".join(ch for ch in valor if not unicodedata.combining(ch))
    valor = valor.upper().strip()
    valor = re.sub(r"\s+", " ", valor)
    return valor


def _selecionar_aba_arquivo_01(sheet_names: list[str]) -> str:
    prioridades = [
        "ROUBODEVEICULO",
        "ROUBOVEICULO",
        "SPORTAL",
        "BASE",
    ]
    normalizadas = {aba: _normalizar_nome_aba(aba) for aba in sheet_names}

    for prioridade in prioridades:
        for aba, nome_norm in normalizadas.items():
            if nome_norm == prioridade:
                return aba

    for aba, nome_norm in normalizadas.items():
        if "ROUBO" in nome_norm and "VEICULO" in nome_norm:
            return aba

    return sheet_names[0]


def _selecionar_aba_arquivo_02(sheet_names: list[str]) -> str:
    normalizadas = {aba: _normalizar_nome_aba(aba) for aba in sheet_names}

    prioridades_exatas = [
        "CVPCIOPS",
    ]

    for prioridade in prioridades_exatas:
        for aba, nome_norm in normalizadas.items():
            if nome_norm == prioridade:
                return aba

    prioridades_aproximadas = [
        "CVPCIOPS",
        "CVP",
        "CIOPS",
        "SPORTAL",
    ]

    for prioridade in prioridades_aproximadas:
        for aba, nome_norm in normalizadas.items():
            if prioridade in nome_norm:
                return aba

    return sheet_names[0]


def _normalizar_chave_coluna(nome: str) -> str:
    nome = str(nome or "").strip()
    nome = re.sub(r"\.\d+$", "", nome)
    nome = unicodedata.normalize("NFKD", nome)
    nome = "".join(ch for ch in nome if not unicodedata.combining(ch))
    nome = nome.lower().strip()
    nome = nome.replace("_", " ").replace("-", " ")
    nome = re.sub(r"\s+", " ", nome)
    return nome


def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def encontrar_coluna_data(df: pd.DataFrame) -> str:
    exatos = [c for c in df.columns if _normalizar_chave_coluna(c) == "data"]
    if exatos:
        return exatos[0]

    aproximados = [c for c in df.columns if "data" in _normalizar_chave_coluna(c)]
    if aproximados:
        return aproximados[0]

    raise ValueError("Nao foi encontrada a coluna 'Data'.")


def encontrar_coluna_hora(df: pd.DataFrame) -> str:
    exatos = [c for c in df.columns if _normalizar_chave_coluna(c) == "hora"]
    if exatos:
        return exatos[0]

    aproximados = [c for c in df.columns if "hora" in _normalizar_chave_coluna(c)]
    if aproximados:
        return aproximados[0]

    raise ValueError("Nao foi encontrada a coluna 'Hora'.")


def encontrar_coluna_por_nomes(
    df: pd.DataFrame,
    nomes_possiveis: list[str],
    obrigatoria: bool = True,
):
    cols_map = {_normalizar_chave_coluna(c): c for c in df.columns}

    for nome in nomes_possiveis:
        chave = _normalizar_chave_coluna(nome)
        if chave in cols_map:
            return cols_map[chave]

    for c in df.columns:
        cl = _normalizar_chave_coluna(c)
        for nome in nomes_possiveis:
            if _normalizar_chave_coluna(nome) in cl:
                return c

    if obrigatoria:
        raise ValueError(
            f"Nao foi possivel localizar nenhuma das colunas esperadas: {nomes_possiveis}"
        )
    return None


def renomear_colunas_equivalentes(df_base: pd.DataFrame, df_novo: pd.DataFrame) -> pd.DataFrame:
    mapa_equivalencias = {
        "AIS": [
            "AISNova",
            "AIS Nova",
            "AIS_NOVA",
            "aisnova",
            "ais_nova",
        ],
        "Território": [
            "Regiões",
            "Regioes",
            "Região",
            "Regiao",
            "território",
            "territorio",
            "regiões",
            "regioes",
        ],
    }

    colunas_base_map = {_normalizar_chave_coluna(c): c for c in df_base.columns}
    colunas_novo_map = {_normalizar_chave_coluna(c): c for c in df_novo.columns}

    renomeacoes = {}

    for coluna_base_oficial, aliases in mapa_equivalencias.items():
        chave_base = _normalizar_chave_coluna(coluna_base_oficial)

        if chave_base not in colunas_base_map:
            continue

        nome_real_base = colunas_base_map[chave_base]

        if nome_real_base in df_novo.columns:
            continue

        for alias in aliases:
            chave_alias = _normalizar_chave_coluna(alias)
            if chave_alias in colunas_novo_map:
                nome_real_novo = colunas_novo_map[chave_alias]
                renomeacoes[nome_real_novo] = nome_real_base
                break

    if renomeacoes:
        df_novo = df_novo.rename(columns=renomeacoes)

    return df_novo


def filtrar_por_nome_ocorrencia(
    df: pd.DataFrame,
    coluna_nome_ocorrencia: str,
    valor_filtro: str = VALOR_FILTRO_OCORRENCIA,
) -> pd.DataFrame:
    serie = df[coluna_nome_ocorrencia].astype(str).apply(_normalizar_texto)
    valor_norm = _normalizar_texto(valor_filtro)
    return df.loc[serie == valor_norm].copy()


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

    try:
        dt = pd.to_datetime(v, errors="coerce", dayfirst=True)
        if pd.isna(dt):
            return None
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return None


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

    try:
        dt = pd.to_datetime(s, errors="coerce")
        if not pd.isna(dt):
            return dt.strftime("%H:%M:%S")
    except Exception:
        pass

    return None


def criar_coluna_datahora(
    df: pd.DataFrame,
    coluna_data: str,
    coluna_hora: str,
    nome_coluna="__datahora__",
):
    df = df.copy()
    datas = df[coluna_data].apply(normalizar_data_para_texto)
    horas = df[coluna_hora].apply(normalizar_hora_para_texto)

    combinado = []
    for d, h in zip(datas, horas):
        if d is None or h is None:
            combinado.append(pd.NaT)
        else:
            combinado.append(pd.to_datetime(f"{d} {h}", errors="coerce", dayfirst=True))

    df[nome_coluna] = combinado
    return df


def excluir_coordenadas_invalidas(df: pd.DataFrame, col_lat: str, col_lon: str):
    manter = []

    for lat_raw, lon_raw in zip(df[col_lat], df[col_lon]):
        lat = valor_numerico_exato(lat_raw)
        lon = valor_numerico_exato(lon_raw)

        if lat is None or lon is None:
            manter.append(False)
        elif lat == 0 or lon == 0:
            manter.append(False)
        else:
            manter.append(True)

    df_filtrado = df.loc[manter].copy()
    removidos = len(df) - len(df_filtrado)
    return df_filtrado, removidos


def coordenadas_parecem_wgs84(df: pd.DataFrame, col_lat: str, col_lon: str, amostra: int = 30) -> bool:
    coords_validas = []

    for lat_raw, lon_raw in zip(df[col_lat], df[col_lon]):
        lat = valor_numerico_exato(lat_raw)
        lon = valor_numerico_exato(lon_raw)

        if lat is None or lon is None:
            continue

        coords_validas.append((lat, lon))
        if len(coords_validas) >= amostra:
            break

    if not coords_validas:
        return False

    qtd_wgs84 = sum(-90 <= lat <= 90 and -180 <= lon <= 180 for lat, lon in coords_validas)
    proporcao = qtd_wgs84 / len(coords_validas)

    return proporcao >= 0.8


def coordenadas_parecem_utm(df: pd.DataFrame, col_y: str, col_x: str, amostra: int = 30) -> bool:
    coords_validas = []

    for y_raw, x_raw in zip(df[col_y], df[col_x]):
        y = valor_numerico_exato(y_raw)
        x = valor_numerico_exato(x_raw)

        if y is None or x is None:
            continue

        coords_validas.append((y, x))
        if len(coords_validas) >= amostra:
            break

    if not coords_validas:
        return False

    qtd_utm = sum(100000 <= x <= 900000 and 1000000 <= y <= 10000000 for y, x in coords_validas)
    proporcao = qtd_utm / len(coords_validas)

    return proporcao >= 0.8


def preparar_coordenadas_finais(
    df: pd.DataFrame,
    col_origem_y: str,
    col_origem_x: str,
    col_lat_destino: str,
    col_lon_destino: str,
):
    df = df.copy()

    colunas_para_remover = []
    if col_lat_destino in df.columns and col_lat_destino not in {col_origem_y, col_origem_x}:
        colunas_para_remover.append(col_lat_destino)
    if col_lon_destino in df.columns and col_lon_destino not in {col_origem_y, col_origem_x}:
        colunas_para_remover.append(col_lon_destino)

    if colunas_para_remover:
        df = df.drop(columns=colunas_para_remover, errors="ignore")

    origem_wgs84 = coordenadas_parecem_wgs84(df, col_origem_y, col_origem_x)
    origem_utm = coordenadas_parecem_utm(df, col_origem_y, col_origem_x)

    if origem_wgs84 and not origem_utm:
        df[col_lat_destino] = df[col_origem_y].apply(valor_numerico_exato)
        df[col_lon_destino] = df[col_origem_x].apply(valor_numerico_exato)
        modo = "wgs84_direto"
        return df, modo

    transformer = Transformer.from_crs(
        f"EPSG:{EPSG_UTM_SIRGAS_24S}",
        f"EPSG:{EPSG_WGS84}",
        always_xy=True,
    )

    lat_resultado = []
    lon_resultado = []

    for y_raw, x_raw in zip(df[col_origem_y], df[col_origem_x]):
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
    modo = "utm_reprojetado"
    return df, modo


def alinhar_colunas_arquivo_02_com_base(df_base: pd.DataFrame, df_novo: pd.DataFrame) -> pd.DataFrame:
    colunas_base = list(df_base.columns)

    df_novo = renomear_colunas_equivalentes(df_base, df_novo)

    for col in colunas_base:
        if col not in df_novo.columns:
            df_novo[col] = pd.NA

    df_saida = df_novo.loc[:, colunas_base].copy()

    if df_saida.columns.duplicated().any():
        df_saida = df_saida.loc[:, ~df_saida.columns.duplicated()]
        colunas_faltantes = [c for c in colunas_base if c not in df_saida.columns]

        for col in colunas_faltantes:
            df_saida[col] = pd.NA

        df_saida = df_saida.loc[:, colunas_base].copy()

    return df_saida


def obter_ultimo_datahora(df: pd.DataFrame, coluna_datahora: str):
    df_valid = df[df[coluna_datahora].notna()].copy()
    if df_valid.empty:
        return None
    return df_valid[coluna_datahora].max()


def filtrar_apenas_registros_posteriores(
    df: pd.DataFrame,
    coluna_datahora: str,
    limite_datahora,
):
    if limite_datahora is None:
        return df.copy()
    return df[df[coluna_datahora] > limite_datahora].copy()


def colunas_existentes(df: pd.DataFrame, colunas_desejadas: list[str]) -> list[str]:
    cols = []
    vistos = set()

    for c in colunas_desejadas:
        if c in df.columns and c not in vistos:
            cols.append(c)
            vistos.add(c)

    return cols


def mostrar_amostra_segura(
    titulo: str,
    df: pd.DataFrame,
    colunas_desejadas: list[str],
    n: int = 10,
):
    st.write(titulo)

    cols = colunas_existentes(df, colunas_desejadas)

    if not cols:
        st.warning("Nenhuma das colunas solicitadas existe nesta etapa.")
        st.write("Colunas disponiveis:")
        st.write(list(df.columns))
        return

    df_preview = df.loc[:, cols].copy()

    if df_preview.columns.duplicated().any():
        df_preview = df_preview.loc[:, ~df_preview.columns.duplicated()]

    st.dataframe(df_preview.head(n))


def gerar_excel_em_memoria(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="ROUBO_VEICULOS")
    buffer.seek(0)
    return buffer.getvalue()


def processar_roubo_veiculo_sportal(arquivo_01, arquivo_02):
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
        "Pré-visualização Arquivo 02 (aba CVPCIOPS):",
        df_novo,
        [
            "Endereço",
            "Latitude",
            "Longitude",
            "Latitude_UTM",
            "Longitude_UTM",
            "Nome da Ocorrência",
            "Subnome da Ocorrência",
            "Regiões",
            "AISNova",
        ],
        5,
    )
    progresso.progress(30)

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

    col_nome_ocorrencia = encontrar_coluna_por_nomes(
        df_novo,
        ["nome da ocorrência", "nome ocorrencia", "ocorrência", "ocorrencia"],
        obrigatoria=True,
    )

    total_lido_arquivo_02 = len(df_novo)

    status.info("Filtrando apenas ocorrencias de ROUBO DE VEÍCULO...")
    df_novo = filtrar_por_nome_ocorrencia(df_novo, col_nome_ocorrencia, VALOR_FILTRO_OCORRENCIA)
    removidos_por_tipo = total_lido_arquivo_02 - len(df_novo)

    mostrar_amostra_segura(
        "Arquivo 02 após filtro por Nome da Ocorrência = ROUBO DE VEÍCULO:",
        df_novo,
        ["Data", "Hora", col_nome_ocorrencia, "Subnome da Ocorrência", "Latitude", "Longitude"],
        10,
    )

    if df_novo.empty:
        raise ValueError(
            "Apos filtrar a coluna 'Nome da Ocorrência' por 'ROUBO DE VEÍCULO', "
            "o Arquivo 02 ficou sem registros validos."
        )

    df_novo = renomear_colunas_equivalentes(df_base, df_novo)

    col_lat_base = encontrar_coluna_por_nomes(df_base, ["lat", "latitude"], obrigatoria=True)
    col_lon_base = encontrar_coluna_por_nomes(df_base, ["long", "longitude", "lon"], obrigatoria=True)

    col_lat_novo = encontrar_coluna_por_nomes(
        df_novo,
        ["latitude_utm", "latitude", "lat_utm", "utm_norte", "y"],
        obrigatoria=True,
    )
    col_lon_novo = encontrar_coluna_por_nomes(
        df_novo,
        ["longitude_utm", "longitude", "lon_utm", "utm_leste", "x"],
        obrigatoria=True,
    )

    status.info("Excluindo registros com coordenadas invalidas...")
    total_apos_filtro_tipo = len(df_novo)
    df_novo, removidos_invalidos = excluir_coordenadas_invalidas(df_novo, col_lat_novo, col_lon_novo)

    mostrar_amostra_segura(
        "Arquivo 02 após filtro de coordenadas inválidas:",
        df_novo,
        [col_lat_novo, col_lon_novo, "Nome da Ocorrência", "Subnome da Ocorrência"],
        5,
    )

    if df_novo.empty:
        raise ValueError("Apos excluir coordenadas invalidas, o Arquivo 02 ficou sem registros validos.")

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
        ["__datahora__", col_lat_novo, col_lon_novo, "Nome da Ocorrência", "Subnome da Ocorrência"],
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

    modo_coordenadas = "sem_novos_registros"

    if not df_novo_util.empty:
        status.info("Preparando coordenadas finais...")

        df_novo_util, modo_coordenadas = preparar_coordenadas_finais(
            df_novo_util,
            col_origem_y=col_lat_novo,
            col_origem_x=col_lon_novo,
            col_lat_destino=col_lat_base,
            col_lon_destino=col_lon_base,
        )

        if modo_coordenadas == "wgs84_direto":
            st.info("Arquivo 02 aparenta já estar em WGS84 decimal. A reprojeção foi ignorada.")
        else:
            st.info("Arquivo 02 aparenta estar em UTM. Coordenadas reprojetadas para WGS84.")

        mostrar_amostra_segura(
            "Complemento após preparação das coordenadas:",
            df_novo_util,
            [
                col_lat_novo,
                col_lon_novo,
                col_lat_base,
                col_lon_base,
                "Nome da Ocorrência",
                "Subnome da Ocorrência",
            ],
            10,
        )

        status.info("Montando complemento no esquema exato da base...")
        df_novo_saida = alinhar_colunas_arquivo_02_com_base(base_sem_aux, df_novo_util)

        mostrar_amostra_segura(
            "Complemento final no esquema da base:",
            df_novo_saida,
            [
                "Endereço",
                col_lat_base,
                col_lon_base,
                "Nome da Ocorrência",
                "Subnome da Ocorrência",
                "Território",
                "Município",
                "Bairro",
                "AIS",
            ],
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
    df_final = (
        df_final
        .sort_values(by="__datahora__", ascending=True, na_position="last")
        .reset_index(drop=True)
    )
    df_final = df_final.drop(columns=["__datahora__"], errors="ignore")

    if df_final.columns.duplicated().any():
        df_final = df_final.loc[:, ~df_final.columns.duplicated()].copy()

    progresso.progress(100)

    mostrar_amostra_segura(
        "Resultado final (amostra):",
        df_final,
        [
            "Endereço",
            col_lat_base,
            col_lon_base,
            "Nome da Ocorrência",
            "Subnome da Ocorrência",
            "Território",
            "Município",
            "Bairro",
            "AIS",
        ],
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
        "removidos_por_tipo": removidos_por_tipo,
        "removidos_coord_invalidas": removidos_invalidos,
        "removidos_por_datahora": removidos_por_datahora,
        "ultima_datahora_base": ultima_ref,
        "situacao": situacao,
        "aba_arquivo_01": aba_base,
        "aba_arquivo_02": aba_novo,
        "total_lido_arquivo_02": total_lido_arquivo_02,
        "modo_coordenadas": modo_coordenadas,
    }

    status.success(f"Processo finalizado. {adicionados} registros novos adicionados.")
    return df_final, resumo


def _init_state():
    defaults = {
        "roubo_veiculo_sportal_arquivo_01_bytes": None,
        "roubo_veiculo_sportal_arquivo_01_nome": None,
        "roubo_veiculo_sportal_arquivo_02_bytes": None,
        "roubo_veiculo_sportal_arquivo_02_nome": None,
        "roubo_veiculo_sportal_resultado_excel": None,
        "roubo_veiculo_sportal_resultado_df": None,
        "roubo_veiculo_sportal_resumo": None,
    }

    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def render():
    _init_state()

    st.subheader("Roubo de Veículo SPORTAL")
    st.write("Envie a base historica e o arquivo complementar SPORTAL para atualizar a base com novos registros.")

    arquivo_01 = st.file_uploader(
        "Arquivo 01 - Base historica de Roubo de Veículo",
        type=["xlsx", "xls"],
        key="roubo_veiculo_sportal_upload_01",
    )

    arquivo_02 = st.file_uploader(
        "Arquivo 02 - Complemento SPORTAL",
        type=["xlsx", "xls"],
        key="roubo_veiculo_sportal_upload_02",
    )

    if arquivo_01 is not None:
        arquivo_01.seek(0)
        st.session_state.roubo_veiculo_sportal_arquivo_01_bytes = arquivo_01.read()
        st.session_state.roubo_veiculo_sportal_arquivo_01_nome = arquivo_01.name

    if arquivo_02 is not None:
        arquivo_02.seek(0)
        st.session_state.roubo_veiculo_sportal_arquivo_02_bytes = arquivo_02.read()
        st.session_state.roubo_veiculo_sportal_arquivo_02_nome = arquivo_02.name

    pode_processar = (
        st.session_state.roubo_veiculo_sportal_arquivo_01_bytes is not None
        and st.session_state.roubo_veiculo_sportal_arquivo_02_bytes is not None
    )

    if st.button("Processar Roubo de Veículo SPORTAL", type="primary", disabled=not pode_processar):
        try:
            arquivo_01_buffer = BytesIO(st.session_state.roubo_veiculo_sportal_arquivo_01_bytes)
            arquivo_02_buffer = BytesIO(st.session_state.roubo_veiculo_sportal_arquivo_02_bytes)

            df_final, resumo = processar_roubo_veiculo_sportal(arquivo_01_buffer, arquivo_02_buffer)
            arquivo_excel_bytes = gerar_excel_em_memoria(df_final)

            st.session_state.roubo_veiculo_sportal_resultado_df = df_final
            st.session_state.roubo_veiculo_sportal_resumo = resumo
            st.session_state.roubo_veiculo_sportal_resultado_excel = arquivo_excel_bytes
        except Exception as exc:
            st.exception(exc)

    if (
        st.session_state.roubo_veiculo_sportal_resultado_df is not None
        and st.session_state.roubo_veiculo_sportal_resumo is not None
    ):
        resumo = st.session_state.roubo_veiculo_sportal_resumo

        c1, c2, c3 = st.columns(3)
        c1.metric("Novos registros adicionados", resumo.get("adicionados", 0))
        c2.metric("Total final da base", resumo.get("total_final", 0))
        c3.metric("Ocorrencias removidas por tipo", resumo.get("removidos_por_tipo", 0))

        st.info(
            f"Aba Arquivo 01: {resumo.get('aba_arquivo_01', '-')} | "
            f"Aba Arquivo 02: {resumo.get('aba_arquivo_02', '-')}"
        )

        st.info(
            f"Ultima Data/Hora da base: {resumo.get('ultima_datahora_base', '-')} | "
            f"Removidos por coordenadas invalidas: {resumo.get('removidos_coord_invalidas', 0)} | "
            f"Removidos por filtro temporal: {resumo.get('removidos_por_datahora', 0)}"
        )

        st.info(f"Modo de tratamento das coordenadas: {resumo.get('modo_coordenadas', '-')}")
        st.caption(resumo.get("situacao", "Processamento concluido."))

        if st.session_state.roubo_veiculo_sportal_resultado_excel is not None:
            st.download_button(
                label="Baixar arquivo final",
                data=st.session_state.roubo_veiculo_sportal_resultado_excel,
                file_name=NOME_ARQUIVO_FINAL,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="roubo_veiculo_sportal_download_final",
            )


interface_roubo_veiculo_sportal = render

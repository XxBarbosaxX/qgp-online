"""
Modulo Deslocamento Forcado
Versao Streamlit adaptada para o QGP Online no padrao de Perturbacao ao Sossego Alheio.
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
    prioridades = [
        "DESLOCAMENTOFORCADO",
        "DESLOCAMENTO",
        "FORCADO",
        "BASE",
    ]
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
    prioridades = [
        "DESLOCAMENTOFORCADO",
        "DESLOCAMENTO",
        "FORCADO",
        "COMPLEMENTO",
    ]
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
    exatos = [c for c in df.columns if str(c).strip().lower() == "data"]
    if exatos:
        return exatos[0]

    aproximados = [c for c in df.columns if "data" in str(c).strip().lower()]
    if aproximados:
        return aproximados[0]

    raise ValueError("Nao foi encontrada a coluna 'Data'.")


def encontrar_coluna_hora(df: pd.DataFrame) -> str:
    exatos = [c for c in df.columns if str(c).strip().lower() == "hora"]
    if exatos:
        return exatos[0]

    aproximados = [c for c in df.columns if "hora" in str(c).strip().lower()]
    if aproximados:
        return aproximados[0]

    raise ValueError("Nao foi encontrada a coluna 'Hora'.")


def encontrar_coluna_por_nomes(
    df: pd.DataFrame,
    nomes_possiveis: list[str],
    obrigatoria: bool = True,
):
    cols_map = {str(c).strip().lower(): c for c in df.columns}

    for nome in nomes_possiveis:
        if nome.lower() in cols_map:
            return cols_map[nome.lower()]

    for c in df.columns:
        cl = str(c).strip().lower()
        for nome in nomes_possiveis:
            if nome.lower() in cl:
                return c

    if obrigatoria:
        raise ValueError(
            f"Nao foi possivel localizar nenhuma das colunas esperadas: {nomes_possiveis}"
        )
    return None


def renomear_colunas_equivalentes(df_base: pd.DataFrame, df_novo: pd.DataFrame) -> pd.DataFrame:
    """
    Alinha nomes de colunas entre base e complemento.
    Inclui AIS, Territorio e possiveis variacoes de Nome/Subnome da Ocorrencia.
    """
    mapa_equivalencias = {
        "AIS": ["AISNova", "AIS Nova", "AIS_NOVA", "aisnova", "ais_nova"],
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
        "Nome da Ocorrência": [
            "Nome Ocorrencia",
            "Nome Ocorrência",
            "Nome_Ocorrencia",
            "nome da ocorrencia",
            "nome ocorrencia",
        ],
        "Subnome da Ocorrência": [
            "Subnome Ocorrencia",
            "Subnome Ocorrência",
            "Subnome_Ocorrencia",
            "subnome da ocorrencia",
            "subnome ocorrencia",
        ],
    }

    colunas_base_map = {str(c).strip().lower(): c for c in df_base.columns}
    colunas_novo_map = {str(c).strip().lower(): c for c in df_novo.columns}

    renomeacoes = {}

    for coluna_base_oficial, aliases in mapa_equivalencias.items():
        chave_base = coluna_base_oficial.strip().lower()

        if chave_base not in colunas_base_map:
            continue

        nome_real_base = colunas_base_map[chave_base]

        if nome_real_base in df_novo.columns:
            continue

        for alias in aliases:
            chave_alias = alias.strip().lower()
            if chave_alias in colunas_novo_map:
                nome_real_novo = colunas_novo_map[chave_alias]
                renomeacoes[nome_real_novo] = nome_real_base
                break

    if renomeacoes:
        df_novo = df_novo.rename(columns=renomeacoes)

    return df_novo


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

    formatos = ["%H:%M:%S", "%H:%M"]
    for fmt in formatos:
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
    nome_coluna: str = "__datahora__",
) -> pd.DataFrame:
    df = df.copy()

    datas = df[coluna_data].apply(normalizar_data_para_texto)
    horas = df[coluna_hora].apply(normalizar_hora_para_texto)

    combinado = []
    for d, h in zip(datas, horas):
        if d is None or h is None:
            combinado.append(pd.NaT)
        else:
            combinado.append(
                pd.to_datetime(f"{d} {h}", errors="coerce", dayfirst=True)
            )

    df[nome_coluna] = combinado
    return df


def excluir_coordenadas_invalidas(
    df: pd.DataFrame,
    col_lat: str,
    col_lon: str,
) -> tuple[pd.DataFrame, int]:
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


def reprojetar_utm_para_wgs84(
    df: pd.DataFrame,
    col_y: str,
    col_x: str,
    col_lat_destino: str,
    col_lon_destino: str,
) -> pd.DataFrame:
    """
    col_y = Latitude UTM (Y / Northing)
    col_x = Longitude UTM (X / Easting)
    Resultado gravado em col_lat_destino (Lat_WGS) e col_lon_destino (Long_WGS).
    """
    df = df.copy()

    transformer = Transformer.from_crs(
        f"EPSG:{EPSG_UTM_SIRGAS_24S}",
        f"EPSG:{EPSG_WGS84}",
        always_xy=True,
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
    return df


def alinhar_colunas_arquivo_02_com_base(
    df_base: pd.DataFrame,
    df_novo: pd.DataFrame,
) -> pd.DataFrame:
    """
    Garante que o complemento tenha todas as colunas da base, preservando
    colunas como Nome da Ocorrencia e Subnome da Ocorrencia.
    """
    colunas_base = list(df_base.columns)

    df_novo = renomear_colunas_equivalentes(df_base, df_novo)

    for col in colunas_base:
        if col not in df_novo.columns:
            df_novo[col] = pd.NA

    return df_novo[colunas_base]


def obter_ultimo_datahora(df: pd.DataFrame, coluna_datahora: str):
    df_valid = df[df[coluna_datahora].notna()].copy()
    if df_valid.empty:
        return None
    return df_valid[coluna_datahora].max()


def filtrar_apenas_registros_posteriores(
    df: pd.DataFrame,
    coluna_datahora: str,
    limite_datahora,
) -> pd.DataFrame:
    if limite_datahora is None:
        return df.copy()
    return df[df[coluna_datahora] > limite_datahora].copy()


def gerar_excel_em_memoria(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="DESLOCAMENTO_FORCADO")
    buffer.seek(0)
    return buffer.getvalue()


def processar_deslocamento_forcado(arquivo_01, arquivo_02):
    progresso = st.progress(0)
    status = st.empty()

    removidos_invalidos = 0
    removidos_por_datahora = 0
    adicionados = 0

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

    status.info("Normalizando nomes de colunas...")
    df_base = normalizar_colunas(df_base)
    df_novo = normalizar_colunas(df_novo)
    progresso.progress(30)

    status.info("Identificando colunas de Data e Hora...")
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

    status.info("Identificando colunas de coordenadas e equivalencias...")
    col_lat_base_utm = encontrar_coluna_por_nomes(
        df_base, ["lat", "latitude"], obrigatoria=True
    )
    col_lon_base_utm = encontrar_coluna_por_nomes(
        df_base, ["long", "longitude", "lon"], obrigatoria=True
    )

    col_lat_novo_utm = encontrar_coluna_por_nomes(
        df_novo, ["latitude"], obrigatoria=True
    )
    col_lon_novo_utm = encontrar_coluna_por_nomes(
        df_novo, ["longitude"], obrigatoria=True
    )

    df_novo = renomear_colunas_equivalentes(df_base, df_novo)
    progresso.progress(40)

    status.info("Excluindo registros com coordenadas invalidas no Arquivo 02...")
    total_lido_arquivo_02 = len(df_novo)
    df_novo, removidos_invalidos = excluir_coordenadas_invalidas(
        df_novo, col_lat_novo_utm, col_lon_novo_utm
    )

    if df_novo.empty:
        raise ValueError(
            "Apos excluir coordenadas invalidas, o Arquivo 02 ficou sem registros validos."
        )
    progresso.progress(50)

    status.info("Montando coluna Data/Hora e verificando a ultima referencia da base...")
    df_base = criar_coluna_datahora(df_base, col_data, col_hora, "__datahora__")
    df_novo = criar_coluna_datahora(df_novo, col_data, col_hora, "__datahora__")

    ultimo_datahora_base = obter_ultimo_datahora(df_base, "__datahora__")
    progresso.progress(60)

    status.info("Filtrando apenas registros posteriores a ultima Data/Hora da base...")
    total_antes_filtro_tempo = len(df_novo)
    df_novo_filtrado = filtrar_apenas_registros_posteriores(
        df_novo,
        "__datahora__",
        ultimo_datahora_base,
    )
    removidos_por_datahora = total_antes_filtro_tempo - len(df_novo_filtrado)

    base_sem_aux = df_base.drop(columns=["__datahora__"], errors="ignore").copy()

    # Cria colunas WGS na base (se ainda nao existirem)
    if "Lat_WGS" not in base_sem_aux.columns:
        base_sem_aux["Lat_WGS"] = pd.NA
    if "Long_WGS" not in base_sem_aux.columns:
        base_sem_aux["Long_WGS"] = pd.NA

    if ultimo_datahora_base is None:
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
    progresso.progress(70)

    if not df_novo_util.empty:
        status.info("Reprojetando coordenadas UTM (SIRGAS2000 / 24S) para WGS84...")
        df_novo_util = reprojetar_utm_para_wgs84(
            df_novo_util,
            col_y=col_lat_novo_utm,
            col_x=col_lon_novo_utm,
            col_lat_destino="Lat_WGS",
            col_lon_destino="Long_WGS",
        )
        progresso.progress(80)

        status.info("Alinhando colunas e gerando base final...")
        df_novo_util = alinhar_colunas_arquivo_02_com_base(base_sem_aux, df_novo_util)
        df_final = pd.concat([base_sem_aux, df_novo_util], ignore_index=True)
        adicionados = len(df_novo_util)
    else:
        df_final = base_sem_aux.copy()
        adicionados = 0
    progresso.progress(90)

    status.info("Ordenando arquivo final...")
    df_final = criar_coluna_datahora(df_final, col_data, col_hora, "__datahora__")
    df_final = df_final.sort_values(
        by="__datahora__",
        ascending=True,
        na_position="last",
    ).reset_index(drop=True)
    df_final = df_final.drop(columns=["__datahora__"], errors="ignore")
    progresso.progress(100)

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

    status.success(
        f"Processo finalizado. {adicionados} registros novos adicionados ao arquivo final."
    )

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
    st.write(
        "Envie a base historica e o arquivo complementar para atualizar a base com novos registros de Deslocamento Forcado."
    )

    st.caption(
        "Fluxo: identificar a ultima Data/Hora do Arquivo 01, localizar no Arquivo 02 apenas ocorrencias posteriores, "
        "excluir coordenadas invalidas, reprojetar UTM SIRGAS2000 / 24S para WGS84 e gerar a planilha final mantendo todas as colunas da base."
    )

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

    if st.session_state.deslocamento_arquivo_01_nome:
        st.info(f"Arquivo 01 carregado: {st.session_state.deslocamento_arquivo_01_nome}")

    if st.session_state.deslocamento_arquivo_02_nome:
        st.info(f"Arquivo 02 carregado: {st.session_state.deslocamento_arquivo_02_nome}")

    pode_processar = (
        st.session_state.deslocamento_arquivo_01_bytes is not None
        and st.session_state.deslocamento_arquivo_02_bytes is not None
    )

    if st.button(
        "Processar Deslocamento Forcado",
        type="primary",
        disabled=not pode_processar,
    ):
        try:
            arquivo_01_buffer = BytesIO(st.session_state.deslocamento_arquivo_01_bytes)
            arquivo_02_buffer = BytesIO(st.session_state.deslocamento_arquivo_02_bytes)

            df_final, resumo = processar_deslocamento_forcado(
                arquivo_01_buffer,
                arquivo_02_buffer,
            )
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
        df_final = st.session_state.deslocamento_resultado_df
        resumo = st.session_state.deslocamento_resumo

        c1, c2, c3 = st.columns(3)
        c1.metric("Novos registros adicionados", resumo.get("adicionados", 0))
        c2.metric("Total final da base", resumo.get("total_final", 0))
        c3.metric(
            "Coordenadas invalidas removidas",
            resumo.get("removidos_coord_invalidas", 0),
        )

        st.info(
            f"Aba usada no Arquivo 01: {resumo.get('aba_arquivo_01', '-')} | "
            f"Aba usada no Arquivo 02: {resumo.get('aba_arquivo_02', '-')}"
        )

        st.info(
            f"Ultima Data/Hora da base: {resumo.get('ultima_datahora_base', '-')} | "
            f"Removidos por filtro temporal: {resumo.get('removidos_por_datahora', 0)}"
        )

        st.caption(resumo.get("situacao", "Processamento concluido."))
        st.dataframe(df_final.head(50), use_container_width=True)

        if st.session_state.deslocamento_resultado_excel is not None:
            st.download_button(
                label="Baixar arquivo final",
                data=st.session_state.deslocamento_resultado_excel,
                file_name=NOME_ARQUIVO_FINAL,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="deslocamento_download_final",
            )


interface_deslocamento_forcado = render

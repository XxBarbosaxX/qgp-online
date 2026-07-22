from __future__ import annotations

import calendar
import io
import re
import time
import unicodedata
import zipfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

INDICADORES_DISPONIVEIS = [
    "CVLI",
    "ARMA",
    "CVPCIOPS",
    "CVPSIP",
    "Orcrim",
    "Incêndio Vegetação",
    "Apreensão de Arma",
    "TRAFICO",
    "LESÃO",
    "Tentativa",
    "Lesão Corporal Dolosa",
    "Perturbação ao Sossego Alheio",
    "Grupo Criminoso",
    "Drone",
    "Infrator",
    "Extorsão",
    "Esbulho",
    "ExtorsãoSIP",
    "EsbulhoSIP",
    "Acidente de Trânsito",
    "Furto CIOPS",
    "Furto SIP",
]

PREENCHIMENTO_COLUNA_AUSENTE = pd.NA
LIMIAR_FUZZY = 0.82
LIMIAR_TAXA_DATA_VALIDA = 0.50

FAIXA_LATITUDE = (-35.0, 5.5)
FAIXA_LONGITUDE = (-74.0, -28.0)

FORMATOS_DATA_BRASIL = [
    "%d/%m/%Y",
    "%d/%m/%y",
    "%d-%m-%Y",
    "%d-%m-%y",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d.%m.%Y",
    "%d.%m.%y",
    "%Y%m%d",
]

SINONIMOS_COLUNAS: Dict[str, str] = {
    "data": "Data",
    "data_completa": "Data",
    "data_ocorrencia": "Data",
    "data_fato": "Data",
    "data_registro": "Data",
    "data_do_fato": "Data",
    "data_da_ocorrencia": "Data",
    "dt_fato": "Data",
    "dt_ocorrencia": "Data",
    "dt_registro": "Data",
    "dt": "Data",
    "date": "Data",
    "hora": "Hora",
    "hora_fato": "Hora",
    "hora_registro": "Hora",
    "hora_ocorrencia": "Hora",
    "hora_do_fato": "Hora",
    "hr": "Hora",
    "time": "Hora",
    "latitude": "Latitude",
    "lat": "Latitude",
    "latitude_gps": "Latitude",
    "latitude_ocorrencia": "Latitude",
    "latitude_gps_ocorrencia": "Latitude",
    "coord_lat": "Latitude",
    "y": "Latitude",
    "longitude": "Longitude",
    "lon": "Longitude",
    "long": "Longitude",
    "lng": "Longitude",
    "longitude_gps": "Longitude",
    "longitude_ocorrencia": "Longitude",
    "longitude_gps_ocorrencia": "Longitude",
    "coord_lon": "Longitude",
    "x": "Longitude",
    "aisnova": "AISNova",
    "ais_nova": "AISNova",
    "ais": "AISNova",
    "ais_atual": "AISNova",
    "area_integrada": "AISNova",
    "area_integrada_de_seguranca": "AISNova",
    "area_integrada_seguranca": "AISNova",
    "regiao": "Região",
    "regiao_ais": "Região",
    "regioes": "Região",
    "territorio": "Região",
    "territorio_operacional": "Região",
    "territorio_de_seguranca": "Região",
    "area": "Região",
    "municipio": "Município",
    "cidade": "Município",
    "localidade": "Município",
    "mun": "Município",
    "bairro": "Bairro",
    "bairro_ocorrencia": "Bairro",
    "natureza": "Natureza",
    "tipo": "Natureza",
    "tipo_ocorrencia": "Natureza",
    "tipo_fato": "Natureza",
    "modalidade": "Natureza",
    "nome_da_ocorrencia": "Natureza",
    "nome_ocorrencia": "Natureza",
    "tombo": "Tombo",
    "num_tombo": "Tombo",
    "numero_tombo": "Tombo",
    "tombo_ocorrencia": "Tombo",
    "id_ocorrencia": "Tombo",
    "registro": "Tombo",
    "eid": "Tombo",
    "nome_da_vitima": "Nome da Vítima",
    "nome_vitima": "Nome da Vítima",
    "vitima": "Nome da Vítima",
    "nome_da_vitima_1": "Nome da Vítima",
    "sexo": "Sexo",
    "genero": "Sexo",
    "sexo_vitima": "Sexo",
    "idade": "Idade",
    "idade_vitima": "Idade",
    "faixa_etaria": "Idade",
    "endereco": "Endereço",
    "logradouro": "Endereço",
    "rua": "Endereço",
    "local": "Endereço",
    "local_do_fato": "Endereço",
    "circunstancia": "Circunstância",
    "circunstancias": "Circunstância",
    "forma": "Circunstância",
    "instrumento": "Instrumento",
    "meio": "Instrumento",
    "arma_utilizada": "Instrumento",
    "tipo_arma": "Instrumento",
    "dia": "dia",
    "subnome_da_ocorrencia": "Subnome da Ocorrência",
    "subnome_ocorrencia": "Subnome da Ocorrência",
}

@dataclass
class ArquivoAbaLida:
    nome_arquivo: str
    indicador: str
    ordem_colunas_base: List[str]
    coluna_data_real: str
    coluna_hora_real: Optional[str]
    df_processado: pd.DataFrame
    dt_min: Optional[pd.Timestamp]
    dt_max: Optional[pd.Timestamp]
    log_colunas: Dict[str, object] = field(default_factory=dict)

@dataclass
class ResultadoIndicador:
    indicador: str
    sucesso: bool
    mensagem: str
    df_consolidado: pd.DataFrame = field(default_factory=pd.DataFrame)
    df_completude: pd.DataFrame = field(default_factory=pd.DataFrame)
    df_auditoria: pd.DataFrame = field(default_factory=pd.DataFrame)
    df_log: pd.DataFrame = field(default_factory=pd.DataFrame)
    arquivo_bytes: bytes = b""
    nome_arquivo_saida: str = ""
    total_arquivos_lidos: int = 0
    total_registros_saida: int = 0
    total_meses: int = 0
    total_meses_incompletos: int = 0
    erros: List[str] = field(default_factory=list)

def normalizar_texto(valor: str) -> str:
    if valor is None:
        return ""
    valor = str(valor).strip()
    valor = unicodedata.normalize("NFKD", valor)
    valor = "".join(c for c in valor if not unicodedata.combining(c))
    valor = valor.lower()
    valor = re.sub(r"\s+", " ", valor)
    return valor

def slugify(valor: str) -> str:
    base = normalizar_texto(valor)
    base = re.sub(r"[^a-z0-9]+", "_", base)
    base = re.sub(r"_+", "_", base).strip("_")
    return base or "arquivo"

def slug_coluna(valor: str) -> str:
    return slugify(valor)

def _sequencia_comum(a: str, b: str) -> int:
    m, n = len(a), len(b)
    if m == 0 or n == 0:
        return 0
    prev = [0] * (n + 1)
    for i in range(1, m + 1):
        curr = [0] * (n + 1)
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(curr[j - 1], prev[j])
        prev = curr
    return prev[n]

def similaridade_fuzzy(a: str, b: str) -> float:
    a, b = normalizar_texto(a), normalizar_texto(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    lcs = _sequencia_comum(a, b)
    return (2 * lcs) / (len(a) + len(b))

def _taxa_datas_validas(serie: pd.Series) -> float:
    amostra = serie.dropna().head(200)
    if len(amostra) == 0:
        return 0.0
    if pd.api.types.is_datetime64_any_dtype(serie):
        return 1.0
    convertidos = pd.to_datetime(amostra, errors="coerce", dayfirst=True)
    taxa = convertidos.notna().sum() / len(amostra)
    return float(taxa)

def parse_data_robusta(serie: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(serie):
        return serie
    serie_str = serie.astype(str).str.strip()
    serie_str = serie_str.replace({"nan": pd.NA, "NaT": pd.NA, "None": pd.NA, "": pd.NA})
    resultado = pd.Series(pd.NaT, index=serie.index)
    pendente_mask = serie_str.notna()
    for fmt in FORMATOS_DATA_BRASIL:
        if not pendente_mask.any():
            break
        tentativa = pd.to_datetime(
            serie_str.where(pendente_mask),
            format=fmt,
            errors="coerce",
        )
        acertou = tentativa.notna() & pendente_mask
        resultado = resultado.where(~acertou, tentativa)
        pendente_mask = pendente_mask & ~acertou
    if pendente_mask.any():
        fallback = pd.to_datetime(
            serie_str.where(pendente_mask),
            errors="coerce",
            dayfirst=True,
            infer_datetime_format=True,
        )
        acertou = fallback.notna() & pendente_mask
        resultado = resultado.where(~acertou, fallback)
    return resultado

def resolver_coluna_por_sinonimo(nome_coluna: str) -> Optional[str]:
    chave = slug_coluna(nome_coluna)
    if chave in SINONIMOS_COLUNAS:
        return SINONIMOS_COLUNAS[chave]
    melhor_score = 0.0
    melhor_valor = None
    for sinonimo, canonico in SINONIMOS_COLUNAS.items():
        score = similaridade_fuzzy(chave, sinonimo)
        if score > melhor_score:
            melhor_score = score
            melhor_valor = canonico
    if melhor_score >= LIMIAR_FUZZY:
        return melhor_valor
    return None

def _detectar_coordenada_por_conteudo(serie: pd.Series) -> Optional[str]:
    valores = pd.to_numeric(serie.dropna(), errors="coerce").dropna()
    if len(valores) < 5:
        return None
    vmin, vmax = float(valores.min()), float(valores.max())
    if FAIXA_LATITUDE[0] <= vmin and vmax <= FAIXA_LATITUDE[1] and (vmax - vmin) < 20:
        return "Latitude"
    if FAIXA_LONGITUDE[0] <= vmin and vmax <= FAIXA_LONGITUDE[1] and (vmax - vmin) < 20:
        return "Longitude"
    return None

def renomear_colunas_por_sinonimos(
    df: pd.DataFrame,
) -> Tuple[pd.DataFrame, Dict[str, str], List[str], List[str]]:
    mapa: Dict[str, str] = {}
    nao_reconhecidas: List[str] = []
    novas_colunas: List[str] = []
    nomes_finais = {}
    usados_canonicos: Dict[str, int] = {}
    for col in df.columns:
        canonico = resolver_coluna_por_sinonimo(col)
        if canonico is None:
            canonico = _detectar_coordenada_por_conteudo(df[col])
        if canonico:
            contagem = usados_canonicos.get(canonico, 0)
            usados_canonicos[canonico] = contagem + 1
            nome_final = canonico if contagem == 0 else f"{canonico}_{contagem}"
            mapa[col] = nome_final
            nomes_finais[col] = nome_final
        else:
            nao_reconhecidas.append(col)
            novas_colunas.append(col)
            nomes_finais[col] = col
    df_renomeado = df.rename(columns=nomes_finais)
    return df_renomeado, mapa, nao_reconhecidas, novas_colunas

def encontrar_coluna_por_nome_oficial(df: pd.DataFrame, nome_oficial: str) -> Optional[str]:
    alvo = normalizar_texto(nome_oficial)
    for col in df.columns:
        if normalizar_texto(col) == alvo:
            return col
    return None

def detectar_coluna_data(df: pd.DataFrame, log: List[str]) -> Optional[str]:
    candidatos_data = sorted(
        [c for c in df.columns if re.match(r"^Data(_\d+)?$", c, re.IGNORECASE)],
        key=lambda c: (
            0 if c == "Data"
            else int(re.search(r"_(\d+)$", c).group(1)) if re.search(r"_(\d+)$", c) else 1
        ),
    )
    for col in candidatos_data:
        taxa = _taxa_datas_validas(df[col])
        if taxa >= LIMIAR_TAXA_DATA_VALIDA:
            if col != "Data":
                log.append(
                    f"Coluna '{col}' selecionada como data (taxa={taxa:.0%}). "
                    f"'Data' foi ignorada por conter valores não-data."
                )
            return col
    candidatos_alt = [
        "Data Completa", "Data Ocorrência", "Data Fato", "Data Registro",
        "Data do Fato", "Data da Ocorrência", "dt_fato", "dt_ocorrencia",
        "Hora",
    ]
    for nome in candidatos_alt:
        col = encontrar_coluna_por_nome_oficial(df, nome)
        if col:
            taxa = _taxa_datas_validas(df[col])
            if taxa >= LIMIAR_TAXA_DATA_VALIDA:
                log.append(
                    f"Coluna '{col}' selecionada como data via candidato alternativo (taxa={taxa:.0%})."
                )
                return col
    melhor_col = None
    melhor_taxa = 0.0
    for col in df.columns:
        if col.startswith("_"):
            continue
        taxa = _taxa_datas_validas(df[col])
        if taxa > melhor_taxa:
            melhor_taxa = taxa
            melhor_col = col
    if melhor_col and melhor_taxa >= LIMIAR_TAXA_DATA_VALIDA:
        log.append(
            f"Coluna '{melhor_col}' selecionada como data via varredura completa (taxa={melhor_taxa:.0%})."
        )
        return melhor_col
    return None

def detectar_coluna_hora(df: pd.DataFrame) -> Optional[str]:
    candidatos = sorted(
        [c for c in df.columns if re.match(r"^Hora(_\d+)?$", c, re.IGNORECASE)],
        key=lambda c: (
            0 if c == "Hora"
            else int(re.search(r"_(\d+)$", c).group(1)) if re.search(r"_(\d+)$", c) else 1
        ),
    )
    return candidatos[0] if candidatos else None

def encontrar_nome_aba(sheet_names: List[str], indicador: str) -> Optional[str]:
    alvo = normalizar_texto(indicador)
    mapa = {normalizar_texto(nome): nome for nome in sheet_names}
    if alvo in mapa:
        return mapa[alvo]
    melhor_score = 0.0
    melhor_nome = None
    for norm, original in mapa.items():
        score = similaridade_fuzzy(alvo, norm)
        if score > melhor_score:
            melhor_score = score
            melhor_nome = original
    if melhor_score >= LIMIAR_FUZZY:
        return melhor_nome
    return None

def limpar_nome_colunas(df: pd.DataFrame) -> pd.DataFrame:
    novas = []
    usados: Dict[str, int] = {}
    for col in df.columns:
        nome = str(col).strip() if str(col).strip() else "coluna_sem_nome"
        if nome in usados:
            usados[nome] += 1
            nome = f"{nome}_{usados[nome]}"
        else:
            usados[nome] = 1
        novas.append(nome)
    df = df.copy()
    df.columns = novas
    return df

def remover_linhas_vazias(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df.dropna(how="all").copy()

def normalizar_hora_para_6(valor) -> str:
    if pd.isna(valor):
        return "000000"
    txt = str(valor).strip()
    if txt.lower() in {"", "nan", "nat", "none", "null"}:
        return "000000"
    txt = re.sub(r"\D", "", txt)
    if not txt:
        return "000000"
    txt = txt.zfill(6)
    return txt[:6]

def montar_datetime(
    df: pd.DataFrame, col_data: str, col_hora: Optional[str]
) -> pd.Series:
    datas = parse_data_robusta(df[col_data])
    tem_hora_na_data = False
    if pd.api.types.is_datetime64_any_dtype(datas):
        horas_na_data = datas.dropna()
        if not horas_na_data.empty:
            segundos_distintos = (
                horas_na_data.dt.hour * 3600
                + horas_na_data.dt.minute * 60
                + horas_na_data.dt.second
            )
            tem_hora_na_data = segundos_distintos.nunique() > 1
    if tem_hora_na_data:
        return datas
    if col_hora and col_hora in df.columns:
        horas = df[col_hora].apply(normalizar_hora_para_6)
    else:
        horas = pd.Series(["000000"] * len(df), index=df.index)
    hh = horas.str[0:2]
    mm = horas.str[2:4]
    ss = horas.str[4:6]
    dt_str = datas.dt.strftime("%Y-%m-%d").fillna("") + " " + hh + ":" + mm + ":" + ss
    dt = pd.to_datetime(dt_str, errors="coerce")
    dt = dt.where(datas.notna(), pd.NaT)
    return dt

def identificar_periodo_aba(aba: ArquivoAbaLida) -> Optional[str]:
    df = aba.df_processado
    if "_datetime_oficial" not in df.columns:
        return None
    datas = df["_datetime_oficial"].dropna()
    if datas.empty:
        return None
    periodos = datas.dt.to_period("M")
    return str(periodos.value_counts().idxmax())

def selecionar_base_mais_completa(
    abas_mesmo_mes: List[ArquivoAbaLida],
) -> ArquivoAbaLida:
    def score(aba: ArquivoAbaLida) -> Tuple:
        df = aba.df_processado
        datas = df["_datetime_oficial"].dropna()
        if datas.empty:
            return (0, 0, 0)
        return (
            int(datas.dt.day.max()),
            int(datas.dt.date.nunique()),
            len(df),
        )
    return max(abas_mesmo_mes, key=score)

def agrupar_e_selecionar_por_mes(
    abas_lidas: List[ArquivoAbaLida],
) -> Tuple[List[ArquivoAbaLida], List[str], Dict[str, str]]:
    grupos: Dict[str, List[ArquivoAbaLida]] = {}
    sem_periodo: List[ArquivoAbaLida] = []
    mapa_mes_arquivo: Dict[str, str] = {}
    for aba in abas_lidas:
        periodo = identificar_periodo_aba(aba)
        if periodo is None:
            sem_periodo.append(aba)
        else:
            grupos.setdefault(periodo, []).append(aba)
    selecionadas: List[ArquivoAbaLida] = []
    log_descartes: List[str] = []
    for periodo, grupo in sorted(grupos.items()):
        if len(grupo) == 1:
            escolhida = grupo[0]
            selecionadas.append(escolhida)
            mapa_mes_arquivo[periodo] = escolhida.nome_arquivo
        else:
            escolhida = selecionar_base_mais_completa(grupo)
            descartadas = [a for a in grupo if a is not escolhida]
            selecionadas.append(escolhida)
            mapa_mes_arquivo[periodo] = escolhida.nome_arquivo
            for d in descartadas:
                log_descartes.append(
                    f"[{periodo}] Descartado '{d.nome_arquivo}' em favor de "
                    f"'{escolhida.nome_arquivo}' (base mais completa)."
                )
    for aba in sem_periodo:
        selecionadas.append(aba)
    return selecionadas, log_descartes, mapa_mes_arquivo

def preencher_colunas_ausentes(
    df: pd.DataFrame, ordem_base: List[str]
) -> pd.DataFrame:
    df = df.copy()
    for col in ordem_base:
        if col not in df.columns:
            df[col] = pd.NA
    extras = [c for c in df.columns if c not in ordem_base]
    return df[ordem_base + extras]

def gerar_chave_cvli(
    df: pd.DataFrame, col_tombo: str, col_data: str, col_vitima: str
) -> pd.Series:
    tombo = df[col_tombo].astype(str).fillna("").str.strip()
    data = parse_data_robusta(df[col_data]).dt.strftime("%Y-%m-%d").fillna("")
    vitima = df[col_vitima].astype(str).fillna("").str.strip().map(normalizar_texto)
    return tombo + "||" + data + "||" + vitima

def gerar_chave_secundaria_incremental(df: pd.DataFrame) -> pd.Series:
    candidatos_nomes = [
        "Natureza", "Ocorrência", "Ocorrencia",
        "Nome da Ocorrência", "Nome da Ocorrencia",
        "Tombo", "Município", "Municipio",
    ]
    candidatos = []
    for nome in candidatos_nomes:
        col = encontrar_coluna_por_nome_oficial(df, nome)
        if col:
            candidatos.append(col)
    if not candidatos:
        candidatos = list(df.columns[: min(4, len(df.columns))])
    partes = [
        df[col].astype(str).fillna("").str.strip().map(normalizar_texto)
        for col in candidatos
    ]
    chave = partes[0]
    for serie in partes[1:]:
        chave = chave + "||" + serie
    return chave

def ordenar_arquivos_por_periodo(
    abas_lidas: List[ArquivoAbaLida],
) -> List[ArquivoAbaLida]:
    return sorted(
        abas_lidas,
        key=lambda x: (
            pd.Timestamp.max
            if x.dt_min is None or pd.isna(x.dt_min)
            else x.dt_min,
            x.nome_arquivo.lower(),
        ),
    )

def ler_aba_indicador(
    uploaded_file, indicador: str
) -> Tuple[Optional[ArquivoAbaLida], Optional[str]]:
    try:
        uploaded_file.seek(0)
        xls = pd.ExcelFile(uploaded_file)
    except Exception as e:
        return None, f"Falha ao abrir o arquivo {uploaded_file.name}: {e}"
    nome_aba_real = encontrar_nome_aba(xls.sheet_names, indicador)
    if not nome_aba_real:
        return None, (
            f"A aba '{indicador}' não foi localizada no arquivo {uploaded_file.name}."
        )
    try:
        uploaded_file.seek(0)
        df = pd.read_excel(uploaded_file, sheet_name=nome_aba_real)
    except Exception as e:
        return None, (
            f"Falha ao ler a aba '{indicador}' do arquivo {uploaded_file.name}: {e}"
        )
    df = limpar_nome_colunas(df)
    df = remover_linhas_vazias(df)
    if df.empty:
        return None, (
            f"A aba '{indicador}' do arquivo {uploaded_file.name} está vazia."
        )
    df_renomeado, mapa_renomeio, nao_reconhecidas, novas_colunas = (
        renomear_colunas_por_sinonimos(df)
    )
    log_erros_deteccao: List[str] = []
    coluna_data_real = detectar_coluna_data(df_renomeado, log_erros_deteccao)
    if not coluna_data_real:
        return None, (
            f"A aba '{indicador}' do arquivo {uploaded_file.name} não possui "
            f"coluna de data reconhecida com dados válidos suficientes."
        )
    df_renomeado[coluna_data_real] = parse_data_robusta(df_renomeado[coluna_data_real])
    coluna_hora_real = detectar_coluna_hora(df_renomeado)
    df_proc = df_renomeado.copy()
    df_proc["_data_oficial"] = df_proc[coluna_data_real]
    df_proc["_hora_oficial"] = (
        df_proc[coluna_hora_real].apply(normalizar_hora_para_6)
        if coluna_hora_real and coluna_hora_real in df_proc.columns
        else "000000"
    )
    df_proc["_datetime_oficial"] = montar_datetime(
        df_proc, coluna_data_real, coluna_hora_real
    )
    serie_dt = df_proc["_datetime_oficial"].dropna()
    dt_min = serie_dt.min() if not serie_dt.empty else None
    dt_max = serie_dt.max() if not serie_dt.empty else None
    log_colunas = {
        "mapa_renomeio": mapa_renomeio,
        "nao_reconhecidas": nao_reconhecidas,
        "novas_colunas": novas_colunas,
        "coluna_data": coluna_data_real,
        "coluna_hora": coluna_hora_real,
        "avisos_deteccao": log_erros_deteccao,
    }
    return (
        ArquivoAbaLida(
            nome_arquivo=uploaded_file.name,
            indicador=indicador,
            ordem_colunas_base=list(df_renomeado.columns),
            coluna_data_real=coluna_data_real,
            coluna_hora_real=coluna_hora_real,
            df_processado=df_proc,
            dt_min=dt_min,
            dt_max=dt_max,
            log_colunas=log_colunas,
        ),
        None,
    )

def _unificar_ordem_colunas(abas_lidas: List[ArquivoAbaLida]) -> List[str]:
    ordem: List[str] = []
    visto: set = set()
    for aba in abas_lidas:
        for col in aba.ordem_colunas_base:
            if col not in visto:
                ordem.append(col)
                visto.add(col)
    for interno in ["_data_oficial", "_hora_oficial", "_datetime_oficial"]:
        if interno not in visto:
            ordem.append(interno)
            visto.add(interno)
    return ordem

def consolidar_cvli(
    abas_lidas: List[ArquivoAbaLida],
) -> Tuple[pd.DataFrame, str]:
    if not abas_lidas:
        return pd.DataFrame(), "Nenhum arquivo válido para CVLI."
    abas_lidas = ordenar_arquivos_por_periodo(abas_lidas)
    ordem_base = _unificar_ordem_colunas(abas_lidas)
    df_base = pd.DataFrame()
    chaves_existentes: set = set()
    for idx, item in enumerate(abas_lidas):
        df = preencher_colunas_ausentes(item.df_processado.copy(), ordem_base)
        col_tombo = encontrar_coluna_por_nome_oficial(df, "Tombo")
        col_vitima = identificar_coluna_vitima_cvli(df)
        if not col_tombo or not col_vitima:
            return pd.DataFrame(), (
                f"No arquivo {item.nome_arquivo}, a aba CVLI não contém as colunas "
                f"obrigatórias para deduplicação (Tombo + Data + Nome da Vítima)."
            )
        df["_chave_cvli"] = gerar_chave_cvli(
            df, col_tombo, item.coluna_data_real, col_vitima
        )
        if idx == 0:
            df_base = df.copy()
            chaves_existentes = set(df_base["_chave_cvli"].astype(str))
        else:
            novos = df[~df["_chave_cvli"].astype(str).isin(chaves_existentes)].copy()
            if not novos.empty:
                chaves_existentes.update(novos["_chave_cvli"].astype(str))
                df_base = pd.concat([df_base, novos], ignore_index=True)
    df_base = df_base.sort_values(
        "_datetime_oficial", ascending=True, na_position="last"
    ).reset_index(drop=True)
    colunas_exportar = [c for c in ordem_base if not c.startswith("_")]
    return df_base[colunas_exportar].copy(), "Consolidação de CVLI concluída com sucesso."

def identificar_coluna_vitima_cvli(df: pd.DataFrame) -> Optional[str]:
    candidatos = [
        "Nome da Vítima", "Nome da Vitima",
        "Nome Vítima", "Nome Vitima", "Nome",
    ]
    for candidato in candidatos:
        col = encontrar_coluna_por_nome_oficial(df, candidato)
        if col:
            return col
    return None

def consolidar_incremental(
    abas_lidas: List[ArquivoAbaLida],
) -> Tuple[pd.DataFrame, str]:
    if not abas_lidas:
        return pd.DataFrame(), "Nenhum arquivo válido para o indicador."
    abas_lidas = ordenar_arquivos_por_periodo(abas_lidas)
    ordem_base = _unificar_ordem_colunas(abas_lidas)
    frames: List[pd.DataFrame] = []
    for item in abas_lidas:
        df = preencher_colunas_ausentes(item.df_processado.copy(), ordem_base)
        frames.append(df)
    if not frames:
        return pd.DataFrame(), "Nenhum frame válido para consolidação."
    df_total = pd.concat(frames, ignore_index=True)
    df_total["_chave_sec"] = gerar_chave_secundaria_incremental(df_total)
    df_total = df_total.drop_duplicates(subset=["_chave_sec"], keep="first")
    df_total = df_total.sort_values(
        "_datetime_oficial", ascending=True, na_position="last"
    ).reset_index(drop=True)
    colunas_exportar = [c for c in ordem_base if not c.startswith("_")]
    return df_total[colunas_exportar].copy(), "Consolidação incremental concluída."

def montar_resumo_completude(
    df: pd.DataFrame, coluna_data_real: str, mapa_mes_arquivo: Dict[str, str]
) -> pd.DataFrame:
    col_data = coluna_data_real if coluna_data_real in df.columns else None
    colunas_resultado = [
        "Nome Planilha",
        "Mês",
        "Ocorrências",
        "Primeiro Dia",
        "Último Dia",
        "Dias com Registro",
        "Dias no Mês",
        "Dias Faltantes",
        "Cobertura (%)",
        "Status",
    ]
    if df.empty or not col_data:
        return pd.DataFrame(columns=colunas_resultado)
    temp = df.copy()
    temp["_data_ref"] = parse_data_robusta(temp[col_data])
    temp = temp[temp["_data_ref"].notna()].copy()
    if temp.empty:
        return pd.DataFrame(columns=colunas_resultado)
    temp["_mes"] = temp["_data_ref"].dt.to_period("M")
    linhas = []
    for mes_periodo, grupo in temp.groupby("_mes", sort=True):
        ano = mes_periodo.year
        mes = mes_periodo.month
        chave_mes = f"{ano:04d}-{mes:02d}"
        dias_mes = calendar.monthrange(ano, mes)[1]
        dias_registrados = sorted(
            grupo["_data_ref"].dt.day.dropna().astype(int).unique().tolist()
        )
        qtd_dias = len(dias_registrados)
        primeiro_dia = min(dias_registrados) if dias_registrados else 0
        ultimo_dia = max(dias_registrados) if dias_registrados else 0
        qtd_faltantes = max(dias_mes - qtd_dias, 0)
        cobertura = round((qtd_dias / dias_mes) * 100, 1) if dias_mes > 0 else 0.0
        status = "Completo" if cobertura >= 100.0 else ("Parcial" if cobertura >= 50.0 else "Incompleto")
        nome_planilha = mapa_mes_arquivo.get(chave_mes, "")
        linhas.append({
            "Nome Planilha": nome_planilha,
            "Mês": chave_mes,
            "Ocorrências": len(grupo),
            "Primeiro Dia": primeiro_dia,
            "Último Dia": ultimo_dia,
            "Dias com Registro": qtd_dias,
            "Dias no Mês": dias_mes,
            "Dias Faltantes": qtd_faltantes,
            "Cobertura (%)": cobertura,
            "Status": status,
        })
    return pd.DataFrame(linhas)

def montar_auditoria(
    indicador: str,
    abas_lidas: List[ArquivoAbaLida],
    consolidado: pd.DataFrame,
    log_descartes: List[str],
) -> pd.DataFrame:
    linhas = []
    for item in abas_lidas:
        avisos = item.log_colunas.get("avisos_deteccao", [])
        linhas.append({
            "Indicador": indicador,
            "Arquivo": item.nome_arquivo,
            "Coluna de Data": item.coluna_data_real,
            "Coluna de Hora": item.coluna_hora_real or "",
            "Data Inicial": (
                "" if item.dt_min is None or pd.isna(item.dt_min)
                else item.dt_min.strftime("%Y-%m-%d %H:%M:%S")
            ),
            "Data Final": (
                "" if item.dt_max is None or pd.isna(item.dt_max)
                else item.dt_max.strftime("%Y-%m-%d %H:%M:%S")
            ),
            "Registros Lidos": len(item.df_processado),
            "Observações": "; ".join(avisos + log_descartes),
        })
    linhas.append({
        "Indicador": indicador,
        "Arquivo": "TOTAL CONSOLIDADO",
        "Coluna de Data": "",
        "Coluna de Hora": "",
        "Data Inicial": "",
        "Data Final": "",
        "Registros Lidos": len(consolidado),
        "Observações": "",
    })
    return pd.DataFrame(linhas)

def montar_log_execucao(
    indicador: str,
    abas_lidas: List[ArquivoAbaLida],
    tempo_segundos: float,
    erros: List[str],
    log_descartes: List[str],
) -> pd.DataFrame:
    linhas = []
    for item in abas_lidas:
        log = item.log_colunas
        mapa = log.get("mapa_renomeio", {})
        nao_rec = log.get("nao_reconhecidas", [])
        novas = log.get("novas_colunas", [])
        avisos = log.get("avisos_deteccao", [])
        linhas.append({
            "Indicador": indicador,
            "Arquivo": item.nome_arquivo,
            "Coluna de Data Selecionada": item.coluna_data_real,
            "Coluna de Hora Selecionada": item.coluna_hora_real or "",
            "Registros": len(item.df_processado),
            "Colunas Renomeadas": "; ".join(f"{o} → {d}" for o, d in mapa.items()),
            "Colunas Não Reconhecidas": "; ".join(nao_rec),
            "Colunas Novas": "; ".join(novas),
            "Avisos Detecção": "; ".join(avisos),
            "Tempo (s)": round(tempo_segundos, 2),
            "Erros/Descartes": "; ".join((erros + log_descartes)[:10]),
        })
    return pd.DataFrame(linhas)

def exportar_excel_indicador(
    indicador: str,
    consolidado: pd.DataFrame,
    completude: pd.DataFrame,
    auditoria: pd.DataFrame,
    log_df: pd.DataFrame,
) -> Tuple[bytes, str]:
    output = io.BytesIO()
    nome_saida = f"{slugify(indicador)}_consolidado.xlsx"
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        consolidado.to_excel(writer, index=False, sheet_name="consolidado")
        completude.to_excel(writer, index=False, sheet_name="completude_mensal")
        auditoria.to_excel(writer, index=False, sheet_name="auditoria")
        if not log_df.empty:
            log_df.to_excel(writer, index=False, sheet_name="log_execucao")
    output.seek(0)
    return output.getvalue(), nome_saida

def exportar_excel_multi_abas(
    resultados_validos: List[ResultadoIndicador],
) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for resultado in resultados_validos:
            nome_aba = slugify(resultado.indicador)[:31]
            if not resultado.df_consolidado.empty:
                resultado.df_consolidado.to_excel(
                    writer, index=False, sheet_name=nome_aba
                )
    output.seek(0)
    return output.getvalue()

def criar_zip_resultados(
    resultados_validos: List[ResultadoIndicador],
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in resultados_validos:
            zf.writestr(r.nome_arquivo_saida, r.arquivo_bytes)
    buffer.seek(0)
    return buffer.getvalue()

def processar_indicador(
    indicador: str, arquivos_excel
) -> ResultadoIndicador:
    t_inicio = time.perf_counter()
    abas_validas: List[ArquivoAbaLida] = []
    erros: List[str] = []
    for arq in arquivos_excel:
        aba_lida, erro = ler_aba_indicador(arq, indicador)
        if erro:
            erros.append(erro)
        elif aba_lida:
            abas_validas.append(aba_lida)
        try:
            arq.seek(0)
        except Exception:
            pass
    if not abas_validas:
        return ResultadoIndicador(
            indicador=indicador,
            sucesso=False,
            mensagem="Nenhuma aba válida encontrada para este indicador.",
            erros=erros,
            df_auditoria=pd.DataFrame({"Erro": erros}) if erros else pd.DataFrame(),
        )
    abas_selecionadas, log_descartes, mapa_mes_arquivo = agrupar_e_selecionar_por_mes(abas_validas)
    if log_descartes:
        erros.extend(log_descartes)
    if indicador == "CVLI":
        consolidado, mensagem = consolidar_cvli(abas_selecionadas)
    else:
        consolidado, mensagem = consolidar_incremental(abas_selecionadas)
    t_fim = time.perf_counter()
    tempo_proc = t_fim - t_inicio
    if consolidado.empty:
        auditoria = montar_auditoria(indicador, abas_selecionadas, consolidado, log_descartes)
        return ResultadoIndicador(
            indicador=indicador,
            sucesso=False,
            mensagem=mensagem,
            erros=erros,
            df_auditoria=auditoria,
        )
    coluna_data_ref = abas_selecionadas[0].coluna_data_real
    completude = montar_resumo_completude(consolidado, coluna_data_ref, mapa_mes_arquivo)
    auditoria = montar_auditoria(indicador, abas_selecionadas, consolidado, log_descartes)
    log_df = montar_log_execucao(
        indicador, abas_selecionadas, tempo_proc, erros, log_descartes
    )
    arquivo_bytes, nome_saida = exportar_excel_indicador(
        indicador, consolidado, completude, auditoria, log_df
    )
    meses_incompletos = 0
    if not completude.empty and "Status" in completude.columns:
        meses_incompletos = int((completude["Status"] != "Completo").sum())
    return ResultadoIndicador(
        indicador=indicador,
        sucesso=True,
        mensagem=mensagem,
        df_consolidado=consolidado,
        df_completude=completude,
        df_auditoria=auditoria,
        df_log=log_df,
        arquivo_bytes=arquivo_bytes,
        nome_arquivo_saida=nome_saida,
        total_arquivos_lidos=len(abas_selecionadas),
        total_registros_saida=len(consolidado),
        total_meses=len(completude),
        total_meses_incompletos=meses_incompletos,
        erros=erros,
    )

def aplicar_estilo_local():
    st.markdown(
        """
        <style>
        .qgp-card {
            border: 1px solid rgba(120,120,120,0.20);
            border-radius: 14px;
            padding: 14px 16px;
            background: rgba(255,255,255,0.02);
            min-height: 110px;
        }
        .qgp-label {
            font-size: 0.86rem;
            color: #9aa0a6;
            margin-bottom: 6px;
        }
        .qgp-value {
            font-size: 1.45rem;
            font-weight: 700;
            line-height: 1.2;
        }
        .qgp-subvalue {
            font-size: 0.90rem;
            color: #b8bec5;
            margin-top: 6px;
        }
        .qgp-download-title {
            font-weight: 600;
            margin-top: 0.25rem;
            margin-bottom: 0.5rem;
        }
        .qgp-divider {
            margin-top: 0.5rem;
            margin-bottom: 0.75rem;
            border-top: 1px solid rgba(120,120,120,0.15);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_card(label: str, value: str, subvalue: str = ""):
    st.markdown(
        f"""
        <div class="qgp-card">
            <div class="qgp-label">{label}</div>
            <div class="qgp-value">{value}</div>
            <div class="qgp-subvalue">{subvalue}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_resumo_resultado(resultado: ResultadoIndicador):
    st.markdown(f"### {resultado.indicador}")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_card("Arquivos lidos", str(resultado.total_arquivos_lidos), "Planilhas válidas")
    with c2:
        render_card("Registros finais", str(resultado.total_registros_saida), "Após consolidação")
    with c3:
        render_card("Meses identificados", str(resultado.total_meses), "Resumo mensal gerado")
    with c4:
        render_card("Meses incompletos", str(resultado.total_meses_incompletos), "Parcial ou Incompleto")
    with st.expander(f"Detalhes de {resultado.indicador}", expanded=False):
        if resultado.erros:
            st.warning("Ocorreram alertas durante o processamento:")
            for erro in resultado.erros:
                st.write(f"- {erro}")
        st.markdown("#### Completude mensal")
        if not resultado.df_completude.empty:
            st.dataframe(resultado.df_completude, use_container_width=True, hide_index=True)
        else:
            st.info("Sem dados suficientes para montar o resumo mensal.")
        st.markdown("#### Auditoria")
        if not resultado.df_auditoria.empty:
            st.dataframe(resultado.df_auditoria, use_container_width=True, hide_index=True)
        st.markdown("#### Log de execução")
        if not resultado.df_log.empty:
            st.dataframe(resultado.df_log, use_container_width=True, hide_index=True)

def render_downloads_grid(
    resultados_validos: List[ResultadoIndicador],
    zip_bytes: Optional[bytes] = None,
    excel_multi_abas: Optional[bytes] = None,
):
    st.markdown("### Downloads")
    col_zip, col_multi = st.columns(2)
    with col_zip:
        if zip_bytes:
            st.download_button(
                "⬇ Baixar ZIP (indicadores separados)",
                data=zip_bytes,
                file_name="indicadores_consolidados.zip",
                mime="application/zip",
                use_container_width=True,
            )
    with col_multi:
        if excel_multi_abas:
            st.download_button(
                "⬇ Baixar Excel único (multi-abas)",
                data=excel_multi_abas,
                file_name="Resultado_Consolidado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
    st.markdown('<div class="qgp-divider"></div>', unsafe_allow_html=True)
    colunas_grade = 3
    for i in range(0, len(resultados_validos), colunas_grade):
        cols = st.columns(colunas_grade)
        bloco = resultados_validos[i : i + colunas_grade]
        for j, resultado in enumerate(bloco):
            with cols[j]:
                st.markdown(
                    f'<div class="qgp-download-title">{resultado.indicador}</div>',
                    unsafe_allow_html=True,
                )
                st.download_button(
                    label=f"Baixar {resultado.nome_arquivo_saida}",
                    data=resultado.arquivo_bytes,
                    file_name=resultado.nome_arquivo_saida,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key=f"download_{slugify(resultado.indicador)}",
                )

def interface_consolidar_indicadores_criminais():
    aplicar_estilo_local()
    st.caption(
        "Unifica planilhas de indicadores criminais por aba, reconhece colunas automaticamente, "
        "valida e normaliza datas em múltiplos formatos, seleciona a base mais completa por mês "
        "e gera arquivo consolidado ordenado cronologicamente."
    )
    arquivos = st.file_uploader(
        "Selecione de 1 a 24 planilhas Excel",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
    )
    col_ind1, col_ind2 = st.columns([3, 1])
    with col_ind1:
        indicadores = st.multiselect(
            "Selecione um ou mais indicadores criminais",
            options=INDICADORES_DISPONIVEIS,
            default=[],
        )
    with col_ind2:
        selecionar_todos = st.checkbox("Todos", value=False)
    if selecionar_todos:
        indicadores = INDICADORES_DISPONIVEIS
    st.markdown("#### Formato de saída")
    formato_saida = st.radio(
        "Como deseja o resultado?",
        options=["Arquivos separados por indicador", "Um único Excel com múltiplas abas"],
        horizontal=True,
    )
    c1, c2 = st.columns([1, 1])
    with c1:
        executar = st.button("Executar consolidação", type="primary", use_container_width=True)
    with c2:
        limpar = st.button("Limpar seleção", use_container_width=True)
    if limpar:
        st.rerun()
    if not executar:
        return
    if not arquivos:
        st.warning("Selecione pelo menos uma planilha Excel.")
        return
    if not indicadores:
        st.warning("Selecione pelo menos um indicador criminal.")
        return
    total = len(indicadores)
    barra_global = st.progress(0, text="Preparando execução...")
    status = st.empty()
    resultados: List[ResultadoIndicador] = []
    for idx, indicador in enumerate(indicadores, start=1):
        status.info(f"Processando {indicador} ({idx}/{total})...")
        resultado = processar_indicador(indicador, arquivos)
        resultados.append(resultado)
        barra_global.progress(
            int((idx / total) * 100),
            text=f"Processados {idx} de {total} indicadores",
        )
    status.empty()
    st.success("Processamento finalizado.")
    resultados_validos = [r for r in resultados if r.sucesso]
    resultados_invalidos = [r for r in resultados if not r.sucesso]
    if resultados_validos:
        total_arq = sum(r.total_arquivos_lidos for r in resultados_validos)
        total_reg = sum(r.total_registros_saida for r in resultados_validos)
        total_inc = sum(r.total_meses_incompletos for r in resultados_validos)
        st.markdown("### Resumo geral")
        g1, g2, g3, g4 = st.columns(4)
        with g1:
            render_card("Indicadores com sucesso", str(len(resultados_validos)), "Arquivos gerados")
        with g2:
            render_card("Arquivos lidos", str(total_arq), "Somatório das abas válidas")
        with g3:
            render_card("Registros consolidados", str(total_reg), "Total em todos os indicadores")
        with g4:
            render_card("Meses incompletos", str(total_inc), "Parcial ou Incompleto")
        for resultado in resultados_validos:
            render_resumo_resultado(resultado)
        zip_bytes = None
        excel_multi = None
        if formato_saida == "Arquivos separados por indicador":
            zip_bytes = criar_zip_resultados(resultados_validos) if len(resultados_validos) > 1 else None
        else:
            excel_multi = exportar_excel_multi_abas(resultados_validos)
        render_downloads_grid(
            resultados_validos,
            zip_bytes=zip_bytes,
            excel_multi_abas=excel_multi,
        )
    if resultados_invalidos:
        st.markdown("### Indicadores com falha")
        for r in resultados_invalidos:
            st.error(f"{r.indicador}: {r.mensagem}")
            if r.erros:
                for erro in r.erros:
                    st.write(f"- {erro}")
            if not r.df_auditoria.empty:
                st.dataframe(r.df_auditoria, use_container_width=True, hide_index=True)

render = interface_consolidar_indicadores_criminais

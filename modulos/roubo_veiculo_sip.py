"""Modulo Roubo de Veiculo (SIP)"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import gzip
import json
import re
import unicodedata
import urllib.request

import numpy as np
import pandas as pd
import streamlit as st
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import ArcGIS
from rapidfuzz import fuzz
from scipy.spatial import cKDTree

from modulos.utils import nome_arquivo_padrao


BASE_DIR = Path(__file__).resolve().parent.parent

NOME_ARQUIVO_FINAL = nome_arquivo_padrao(7, "ROUBO-DE-VEICULO-SIP-ENDERECO")
USAR_EXTERNO = True
LIMIAR_NOME = 88
RAIO_CONFIRMA_M = 100.0
RAIO_MUNICIPIO_KM = 8.0
LIMIAR_SUSPEITO = 5
UF_CODIGO = "23"
VALOR_FILTRO_NATUREZA = "ROUBO DE VEICULO"
ARQ_CACHE_MUN = BASE_DIR / "municipios_ce.json"

SUBST = {
    "AV": "Avenida", "AVD": "Avenida", "AVENIDA": "Avenida",
    "R": "Rua", "RUA": "Rua", "TV": "Travessa", "TRV": "Travessa",
    "TRAV": "Travessa", "TRAVESSA": "Travessa", "PC": "Praca", "PCA": "Praca",
    "PRACA": "Praca", "ROD": "Rodovia", "AL": "Alameda", "PSO": "Passeio",
    "GRJ": "", "DR": "Doutor", "DRA": "Doutora", "PE": "Padre",
    "PRES": "Presidente", "CEL": "Coronel", "GEN": "General",
    "PROF": "Professor", "MAE": "Maestro",
}
CORR = {"RAIMUINDO": "RAIMUNDO", "OSWALDO": "OSVALDO"}
RUIDO = ["LADO PAR", "LADO IMPAR", "- P", "FORTALEZA, CE", ", CE"]
RE_BNI = re.compile(r"\(?\s*bairro\s+n[aã]o\s+identificad[oa]\s*\)?", flags=re.IGNORECASE)
TIPOS = ("Rua", "Avenida", "Travessa", "Praca", "Rodovia", "Alameda", "Passeio")
ROOFTOP = ("pointaddress", "streetaddress", "subaddress", "pointaddressvd")


def _normalizar_nome_aba(nome: str) -> str:
    return (
        str(nome or "")
        .strip()
        .upper()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
    )


def _normalizar_chave_coluna(nome: str) -> str:
    nome = str(nome or "").strip()
    nome = re.sub(r"\.\d+$", "", nome)
    nome = unicodedata.normalize("NFKD", nome)
    nome = "".join(ch for ch in nome if not unicodedata.combining(ch))
    nome = nome.lower().strip()
    nome = nome.replace("_", " ").replace("-", " ")
    nome = re.sub(r"\s+", " ", nome)
    return nome


def sem_acento(s):
    n = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in n if not unicodedata.combining(c)).upper().strip()


def _selecionar_aba_arquivo_01(sheet_names: list[str]) -> str:
    prioridades = [
        "ROUBODEVEICULO",
        "ROUBOVEICULO",
        "SIP",
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

    prioridades_exatas = ["CVPSIP"]

    for prioridade in prioridades_exatas:
        for aba, nome_norm in normalizadas.items():
            if nome_norm == prioridade:
                return aba

    prioridades_aproximadas = ["CVPSIP", "CVP", "SIP"]

    for prioridade in prioridades_aproximadas:
        for aba, nome_norm in normalizadas.items():
            if prioridade in nome_norm:
                return aba

    return sheet_names[0]


def normalizar_colunas(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def encontrar_coluna_por_nomes(df, nomes_possiveis, obrigatoria=True):
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
        raise ValueError(f"Nao foi possivel localizar nenhuma das colunas esperadas: {nomes_possiveis}")
    return None


def encontrar_coluna_data_base(df):
    exatos = [c for c in df.columns if _normalizar_chave_coluna(c) == "data"]
    if exatos:
        return exatos[0]
    aproximados = [c for c in df.columns if "data" in _normalizar_chave_coluna(c)]
    if aproximados:
        return aproximados[0]
    raise ValueError("Nao foi encontrada a coluna 'Data' no Arquivo 01.")


def encontrar_coluna_hora_base(df):
    exatos = [c for c in df.columns if _normalizar_chave_coluna(c) == "hora"]
    if exatos:
        return exatos[0]
    aproximados = [c for c in df.columns if "hora" in _normalizar_chave_coluna(c)]
    if aproximados:
        return aproximados[0]
    raise ValueError("Nao foi encontrada a coluna 'Hora' no Arquivo 01.")


def encontrar_coluna_datahora_arquivo_02(df):
    exatos = [c for c in df.columns if _normalizar_chave_coluna(c) == "data"]
    if exatos:
        return exatos[0]
    aproximados = [c for c in df.columns if "data" in _normalizar_chave_coluna(c)]
    if aproximados:
        return aproximados[0]
    raise ValueError("Nao foi encontrada a coluna 'Data' no Arquivo 02.")


def filtrar_por_natureza(df, natureza_alvo=VALOR_FILTRO_NATUREZA):
    col_natureza = encontrar_coluna_por_nomes(df, ["Natureza"], obrigatoria=True)
    alvo = sem_acento(natureza_alvo)
    return df[df[col_natureza].apply(sem_acento) == alvo].copy(), col_natureza


def renomear_colunas_equivalentes(df_base, df_novo):
    mapa_equivalencias = {
        "AIS": ["AISNova", "AIS Nova", "AIS_NOVA", "aisnova", "ais_nova"],
        "Território": ["Regiões", "Regioes", "Região", "Regiao", "regiões", "regioes", "região", "regiao"],
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
                renomeacoes[colunas_novo_map[chave_alias]] = nome_real_base
                break

    if renomeacoes:
        df_novo = df_novo.rename(columns=renomeacoes)
    return df_novo


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


def criar_datahora_base(df, coluna_data, coluna_hora, nome_coluna="__datahora__"):
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


def criar_datahora_arquivo_02(df, coluna_datahora, nome_coluna="__datahora__"):
    df = df.copy()
    df[nome_coluna] = pd.to_datetime(df[coluna_datahora], errors="coerce", dayfirst=True)
    return df


def obter_ultimo_datahora(df, coluna_datahora):
    df_valid = df[df[coluna_datahora].notna()].copy()
    if df_valid.empty:
        return None
    return df_valid[coluna_datahora].max()


def filtrar_apenas_registros_posteriores(df, coluna_datahora, limite_datahora):
    if limite_datahora is None:
        return df.copy()
    return df[df[coluna_datahora] > limite_datahora].copy()


def alinhar_colunas_arquivo_02_com_base(df_base, df_novo):
    colunas_base = list(df_base.columns)
    df_novo = renomear_colunas_equivalentes(df_base, df_novo)

    for col in colunas_base:
        if col not in df_novo.columns:
            df_novo[col] = pd.NA

    df_saida = df_novo.loc[:, colunas_base].copy()

    if df_saida.columns.duplicated().any():
        df_saida = df_saida.loc[:, ~df_saida.columns.duplicated()]
        for col in colunas_base:
            if col not in df_saida.columns:
                df_saida[col] = pd.NA
        df_saida = df_saida.loc[:, colunas_base].copy()

    return df_saida


def limpar_logradouro(texto):
    t = str(texto or "").upper().strip()
    if t in ("NAN", "NONE", ""):
        return ""
    for a, b in CORR.items():
        t = t.replace(a, b)
    for r in RUIDO:
        t = t.replace(r.upper(), " ")
    t = re.sub(r"\d{4,}", " ", t)
    t = re.sub(r"[.\,/\\-]", " ", t)
    toks = [SUBST.get(tok, tok) for tok in t.split()]
    toks = [x for x in toks if x != ""]
    while len(toks) > 1 and toks[0] in TIPOS and toks[1] in TIPOS:
        toks.pop(0)
    return " 

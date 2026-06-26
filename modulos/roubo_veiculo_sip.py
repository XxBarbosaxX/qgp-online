"""Modulo Roubo de Veiculo (SIP)"""

from __future__ import annotations

from io import BytesIO
import json
import os
import re
import unicodedata
import urllib.request
import gzip

import numpy as np
import pandas as pd
import streamlit as st
from rapidfuzz import fuzz
from scipy.spatial import cKDTree
from geopy.geocoders import ArcGIS
from geopy.extra.rate_limiter import RateLimiter

from modulos.utils import nome_arquivo_padrao


NOME_ARQUIVO_FINAL = nome_arquivo_padrao(7, "ROUBO-DE-VEICULO-SIP-ENDERECO")
USAR_EXTERNO = True
CAMINHO_BASE_ENXUTA = os.path.join("modulos", "CVP_SIP_GEOCODIFICAR.parquet")
LIMIAR_NOME = 88
RAIO_CONFIRMA_M = 100.0
RAIO_MUNICIPIO_KM = 8.0
LIMIAR_SUSPEITO = 5
UF_CODIGO = "23"
ARQ_CACHE_MUN = os.path.join("modulos", "municipios_ce.json")
VALOR_FILTRO_NATUREZA = "ROUBO DE VEICULO"

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
        if "ROUBO" 

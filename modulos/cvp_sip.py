"""
Modulo CVP (SIP) - Geocodificacao por endereco
Versao Streamlit adaptada para o QGP Online.
"""

from __future__ import annotations

import json
import re
import unicodedata
from io import BytesIO
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import ArcGIS
from rapidfuzz import fuzz
from scipy.spatial import cKDTree

from modulos.utils import (
    alinhar_colunas_com_base,
    criar_coluna_datahora,
    encontrar_coluna_data,
    encontrar_coluna_hora,
    encontrar_coluna_por_nomes,
    filtrar_apenas_registros_posteriores,
    gerar_arquivo_excel,
    nome_arquivo_padrao,
    normalizar_colunas,
    obter_ultima_datahora,
    renomear_colunas_equivalentes,
    selecionar_aba_atualizacao,
)

NOME_ARQUIVO_FINAL = nome_arquivo_padrao(3, "CVP-SIP-ENDERECO")

USAR_EXTERNO = True
CAMINHO_BASE_ENXUTA = "CVP_SIP_GEOCODIFICAR.parquet"

LIMIAR_NOME = 88
RAIO_CONFIRMA_M = 100.0
RAIO_MUNICIPIO_KM = 8.0
LIMIAR_SUSPEITO = 5

UF_CODIGO = "23"
ARQ_CACHE_MUN = "municipios_ce.json"

SUBST = {
    "AV": "Avenida",
    "AVD": "Avenida",
    "AVENIDA": "Avenida",
    "R": "Rua",
    "RUA": "Rua",
    "TV": "Travessa",
    "TRV": "Travessa",
    "TRAV": "Travessa",
    "TRAVESSA": "Travessa",
    "PC": "Praca",
    "PCA": "Praca",
    "PRACA": "Praca",
    "ROD": "Rodovia",
    "AL": "Alameda",
    "PSO": "Passeio",
    "GRJ": "",
    "DR": "Doutor",
    "DRA": "Doutora",
    "PE": "Padre",
    "PRES": "Presidente",
    "CEL": "Coronel",
    "GEN": "General",
    "PROF": "Professor",
    "MAE": "Maestro",
}

CORR = {"RAIMUINDO": "RAIMUNDO", "OSWALDO": "OSVALDO"}

RUIDO = ["LADO PAR", "LADO IMPAR", "- P", "FORTALEZA, CE", ", CE"]

RE_BNI = re.compile(
    r"\(?\s*bairro\s+n[aã]o\s+identificad[oa]\s*\)?",
    flags=re.IGNORECASE,
)

TIPOS = ("Rua", "Avenida", "Travessa", "Praca", "Rodovia", "Alameda", "Passeio")
ROOFTOP = ("pointaddress", "streetaddress", "subaddress", "pointaddressvd")

# Níveis possíveis de geocodificação usados no filtro (agora incluindo "Nao Encontrado")
NIVEIS_GEOCODIFICACAO_POSSIVEIS = [
    "Exato (Numero)",
    "Centroide de Rua",
    "Centroide de Bairro",
    "Centroide de Cidade",
    "Nao Encontrado",
]


def obter_configuracao_tecnica() -> dict:
    """Obtém a configuração técnica atual do módulo a partir do session_state."""
    return {
        "usar_externo": st.session_state.get("cvp_sip_cfg_usar_externo", USAR_EXTERNO),
        "caminho_base_enxuta": st.session_state.get(
            "cvp_sip_cfg_caminho_base_enxuta",
            CAMINHO_BASE_ENXUTA,
        ),
        "arq_cache_mun": st.session_state.get("cvp_sip_cfg_arq_cache_mun", ARQ_CACHE_MUN),
        "limiar_nome": int(st.session_state.get("cvp_sip_cfg_limiar_nome", LIMIAR_NOME)),
        "raio_confirma_m": float(
            st.session_state.get("cvp_sip_cfg_raio_confirma_m", RAIO_CONFIRMA_M)
        ),
        "raio_municipio_km": float(
            st.session_state.get("cvp_sip_cfg_raio_municipio_km", RAIO_MUNICIPIO_KM)
        ),
        "limiar_suspeito": int(
            st.session_state.get("cvp_sip_cfg_limiar_suspeito", LIMIAR_SUSPEITO)
        ),
        # novo campo: níveis de geocodificação a manter no arquivo final
        "niveis_filtrar": st.session_state.get(
            "cvp_sip_cfg_niveis_filtrar",
            ["Exato (Numero)", "Centroide de Rua"],
        ),
    }


def sem_acento(texto: str) -> str:
    """Remove acentos, normaliza e converte para caixa alta."""
    normalizado = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in normalizado if not unicodedata.combining(c)).upper().strip()


def _normalizar_nome_aba(nome: str) -> str:
    """Normaliza nome de aba para comparacao."""
    return sem_acento(nome).replace(" ", "").replace("_", "").replace("-", "")


def _selecionar_aba_arquivo_02(sheet_names: list[str]) -> str:
    """Seleciona a aba correta do Arquivo 02 conforme chaveamento oficial."""
    return selecionar_aba_atualizacao(sheet_names, "cvp_sip")


def _selecionar_aba_arquivo_01(sheet_names: list[str]) -> str:
    """Seleciona a aba correta do Arquivo 01 para CVP SIP."""
    prioridades = ["CVPSIP", "CVP", "BASECVP", "BASEHISTORICACVP", "BASE"]
    normalizadas = {aba: _normalizar_nome_aba(aba) for aba in sheet_names}

    for prioridade in prioridades:
        for aba, nome_norm in normalizadas.items():
            if nome_norm == prioridade:
                return aba

    for aba, nome_norm in normalizadas.items():
        if "CVP" in nome_norm:
            return aba

    return sheet_names[0]


def gerar_excel_em_memoria(df: pd.DataFrame) -> bytes:
    """Gera arquivo Excel em memória."""
    return gerar_arquivo_excel(df, sheet_name="CVP_SIP_ENDERECO")


@st.cache_data(show_spinner=False)
def carregar_municipios() -> dict:
    """Carrega municipios do Ceará a partir de cache local ou API do IBGE."""
    config = obter_configuracao_tecnica()
    caminho = Path(config["arq_cache_mun"])

    if caminho.exists():
        try:
            with open(caminho, encoding="utf-8") as arquivo:
                return json.load(arquivo)
        except Exception:
            pass

    url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{UF_CODIGO}/municipios"

    try:
        import gzip
        import urllib.request

        requisicao = urllib.request.Request(url, headers={"Accept-Encoding": "gzip"})
        with urllib.request.urlopen(requisicao, timeout=30) as resposta:
            dados = resposta.read()
            if resposta.info().get("Content-Encoding") == "gzip":
                dados = gzip.decompress(dados)

        lista = json.loads(dados.decode("utf-8"))
        mapa = {sem_acento(m["nome"]): str(m["id"])[:7] for m in lista}

        with open(caminho, "w", encoding="utf-8") as arquivo:
            json.dump(mapa, arquivo, ensure_ascii=False)

        return mapa
    except Exception:
        return {}


def _montar_nome_logradouro(tipo: str, nome: str) -> str:
    """Monta nome padronizado do logradouro."""
    partes = []
    tipo = str(tipo or "").strip()
    nome = str(nome or "").strip()

    if tipo and tipo.lower() != "none":
        partes.append(tipo)
    if nome and nome.lower() != "none":
        partes.append(nome)

    return " ".join(partes).strip()


@st.cache_data(show_spinner=False)
def carregar_base_geografica() -> Optional[pd.DataFrame]:
    """Carrega a base geografica enxuta usada na validacao e geocodificacao."""
    config = obter_configuracao_tecnica()
    caminho_parquet = Path(config["caminho_base_enxuta"])
    if not caminho_parquet.exists():
        return None

    base = pd.read_parquet(caminho_parquet).reset_index(drop=True)
    colunas_esperadas = {
        "CD_SETOR",
        "CD_QUADRA",
        "CD_FACE",
        "NM_TIP_LOG",
        "NM_LOG",
        "Latitude",
        "Longitude",
        "CD_MUN",
        "NM_MUN",
        "SIGLA_UF",
    }
    faltantes = colunas_esperadas - set(base.columns)

    if faltantes:
        raise ValueError(
            f"O arquivo {config['caminho_base_enxuta']} nao possui as colunas esperadas: {sorted(faltantes)}"
        )

    base = base.copy()
    base["cod_mun"] = (
        base["CD_MUN"]
        .fillna(base["CD_SETOR"])
        .astype(str)
        .str.extract(r"(\d+)", expand=False)
        .fillna("")
        .str[:7]
    )
    base["nome_orig"] = base.apply(
        lambda linha: _montar_nome_logradouro(linha.get("NM_TIP_LOG"), linha.get("NM_LOG")),
        axis=1,
    )
    base["nome_norm"] = base["nome_orig"].apply(sem_acento)
    base["lat"] = pd.to_numeric(base["Latitude"], errors="coerce")
    base["lon"] = pd.to_numeric(base["Longitude"], errors="coerce")
    base["tot_geral"] = 1

    base = base.dropna(subset=["lat", "lon"]).copy()
    base = base[base["nome_orig"].astype(str).str.strip() != ""].copy()
    base = base[base["cod_mun"].astype(str).str.strip() != ""].copy()

    base = base.drop_duplicates(
        subset=["cod_mun", "nome_norm", "lat", "lon"]
    ).reset_index(drop=True)

    return base[["cod_mun", "nome_norm", "nome_orig", "lat", "lon", "tot_geral"]]


@st.cache_resource(show_spinner=False)
def obter_geocoder_arcgis():
    """Instancia geocoder ArcGIS com rate limit."""
    config = obter_configuracao_tecnica()
    if not config["usar_externo"]:
        return None

    arc = ArcGIS(timeout=15)
    return RateLimiter(
        arc.geocode,
        min_delay_seconds=0.4,
        max_retries=2,
        swallow_exceptions=True,
    )


def limpar_logradouro(texto: str) -> str:
    """Limpa e padroniza logradouro."""
    valor = str(texto or "").upper().strip()

    if valor in ("NAN", "NONE", ""):
        return ""

    for origem, destino in CORR.items():
        valor = valor.replace(origem, destino)

    for ruido in RUIDO:
        valor = valor.replace(ruido.upper(), " ")

    valor = re.sub(r"\d{4,}", " ", valor)
    valor = re.sub(r"[.\,/\\-]", " ", valor)

    tokens = [SUBST.get(token, token) for token in valor.split()]
    tokens = [token for token in tokens if token != ""]

    while len(tokens) > 1 and tokens[0] in TIPOS and tokens[1] in TIPOS:
        tokens.pop(0)

    return " ".join(" ".join(tokens).split()).title()


def limpar_bairro(bairro: str, municipio: str) -> str:
    """Limpa e padroniza bairro."""
    valor = str(bairro or "").strip()

    if valor.lower() in ("nan", "none", ""):
        return ""

    valor = RE_BNI.sub("", valor)
    valor = re.sub(r"\(.*?\)", "", valor)
    valor = " ".join(valor.strip(" ()-").split())

    if valor == "" or sem_acento(valor) == sem_acento(municipio):
        return ""

    return valor


def limpar_numero(numero: str) -> str:
    """Limpa e padroniza numero do endereco."""
    valor = str(numero or "").strip()

    if valor.lower() in ("nan", "none", "", "0", "0.0", "s/n", "sn"):
        return ""

    try:
        return str(int(float(valor)))
    except Exception:
        return re.sub(r"\D", "", valor)


def _hav(lat1, lon1, lat2, lon2):
    """Calcula distancia haversine em metros."""
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(np.radians(lat1))
        * np.cos(np.radians(lat2))
        * np.sin(dlon / 2) ** 2
    )
    return 2 * 6371000.0 * np.arcsin(np.sqrt(a))


class MotorGeocodificacaoSoberana:
    """Motor de geocodificacao com base local e ArcGIS."""

    def __init__(self):
        self.config = obter_configuracao_tecnica()
        self.base = carregar_base_geografica()
        self.municipios = carregar_municipios()
        self.tree = None
        self.centroides_municipio = {}

        if self.base is not None and len(self.base):
            self.glat = self.base["lat"].values.astype(float)
            self.glon = self.base["lon"].values.astype float)
            # ... restante igual à versão anterior ...

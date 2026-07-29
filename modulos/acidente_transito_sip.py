from __future__ import annotations

import json
import re
import traceback
import unicodedata
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import streamlit as st
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import ArcGIS
from rapidfuzz import fuzz
from scipy.spatial import cKDTree

from modulos.utils import (
    alinhar_colunas_com_base,
    encontrar_coluna_por_nomes,
    gerar_arquivo_excel,
    normalizar_colunas,
)

NOME_ARQUIVO_FINAL = "11 - ACIDENTE DE TRANSITO - SIP - 2026 - QGP.xlsx"

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

CORR = {
    "RAIMUINDO": "RAIMUNDO",
    "OSWALDO": "OSVALDO",
}

RUIDO = [
    "LADO PAR",
    "LADO IMPAR",
    "- P",
    "FORTALEZA, CE",
    ", CE",
]

RE_BNI = re.compile(
    r"\(?\s*bairro\s+n[aã]o\s+identificad[oa]\s*\)?",
    flags=re.IGNORECASE,
)

TIPOS = ("Rua", "Avenida", "Travessa", "Praca", "Rodovia", "Alameda", "Passeio")
ROOFTOP = ("pointaddress", "streetaddress", "subaddress", "pointaddressvd")

NIVEIS_GEOCODIFICACAO_POSSIVEIS = [
    "Exato (Numero)",
    "Centroide de Rua",
    "Centroide de Bairro",
    "Centroide de Cidade",
    "Nao Encontrado",
]

COLUNAS_FINAIS_ESPERADAS = [
    "ais",
    "natureza",
    "tombo",
    "tipo",
    "procedimento",
    "regiao",
    "municipio",
    "bairro",
    "logradouro",
    "numero",
    "complemento",
    "latitude",
    "longitude",
    "data",
    "hora",
    "lat",
    "lon",
    "nivel_geocodificacao",
    "geocodificacao",
]


def obter_configuracao_tecnica() -> dict[str, Any]:
    """Obtém a configuração técnica atual do módulo a partir do session_state."""
    return {
        "usar_externo": st.session_state.get("acdt_sip_cfg_usar_externo", USAR_EXTERNO),
        "caminho_base_enxuta": st.session_state.get(
            "acdt_sip_cfg_caminho_base_enxuta",
            CAMINHO_BASE_ENXUTA,
        ),
        "arq_cache_mun": st.session_state.get(
            "acdt_sip_cfg_arq_cache_mun",
            ARQ_CACHE_MUN,
        ),
        "limiar_nome": int(
            st.session_state.get("acdt_sip_cfg_limiar_nome", LIMIAR_NOME)
        ),
        "raio_confirma_m": float(
            st.session_state.get("acdt_sip_cfg_raio_confirma_m", RAIO_CONFIRMA_M)
        ),
        "raio_municipio_km": float(
            st.session_state.get("acdt_sip_cfg_raio_municipio_km", RAIO_MUNICIPIO_KM)
        ),
        "limiar_suspeito": int(
            st.session_state.get("acdt_sip_cfg_limiar_suspeito", LIMIAR_SUSPEITO)
        ),
        "niveis_filtrar": st.session_state.get(
            "acdt_sip_cfg_niveis_filtrar",
            ["Exato (Numero)", "Centroide de Rua", "Centroide de Bairro", "Centroide de Cidade"],
        ),
    }


def sem_acento(texto: str) -> str:
    """Remove acentos, normaliza e converte para caixa alta."""
    normalizado = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(
        caractere for caractere in normalizado if not unicodedata.combining(caractere)
    ).upper().strip()


def _aplicar_estilo_acidente_transito_sip() -> None:
    """Aplica o estilo visual do módulo Acidente de Trânsito SIP."""
    st.markdown(
        """
        <style>
            .acdt-section-card {
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 18px;
                padding: 1.1rem 1.1rem 0.8rem 1.1rem;
                margin: 1rem 0;
            }

            .acdt-section-title {
                font-size: 1.15rem;
                font-weight: 800;
                color: #f8fafc;
                margin-bottom: 0.25rem;
            }

            .acdt-section-desc {
                font-size: 0.93rem;
                color: rgba(255, 255, 255, 0.72);
                margin-bottom: 0.85rem;
                line-height: 1.55;
            }

            .acdt-mini-list {
                margin: 0.6rem 0 0 0;
                padding-left: 1rem;
                color: rgba(255,255,255,0.80);
                font-size: 0.92rem;
            }

            .acdt-grid-status {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.85rem;
                margin: 1rem 0 0.2rem 0;
            }

            .acdt-stat {
                background: rgba(255, 255, 255, 0.025);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
                padding: 0.95rem 1rem;
            }

            .acdt-stat-label {
                font-size: 0.78rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                color: rgba(255, 255, 255, 0.58);
                margin-bottom: 0.35rem;
                font-weight: 700;
            }

            .acdt-stat-value {
                font-size: 1.20rem;
                font-weight: 900;
                color: #ffffff;
                line-height: 1.15;
                word-break: break-word;
            }

            .acdt-badge-wrap {
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem;
                margin-top: 0.6rem;
                margin-bottom: 0.15rem;
            }

            .acdt-badge {
                display: inline-flex;
                align-items: center;
                gap: 0.35rem;
                padding: 0.5rem 0.72rem;
                border-radius: 999px;
                font-size: 0.82rem;
                font-weight: 700;
                border: 1px solid rgba(255, 255, 255, 0.08);
                background: rgba(255, 255, 255, 0.03);
                color: #e5f3ee;
            }

            .acdt-badge.ok {
                background: rgba(34, 197, 94, 0.10);
                color: #b7f7c9;
                border-color: rgba(34, 197, 94, 0.22);
            }

            .acdt-badge.warn {
                background: rgba(245, 158, 11, 0.10);
                color: #fde4b0;
                border-color: rgba(245, 158, 11, 0.22);
            }

            .acdt-upload-label {
                font-size: 0.95rem;
                font-weight: 700;
                color: #f8fafc;
                margin-bottom: 0.35rem;
            }

            @media (max-width: 1180px) {
                .acdt-grid-status {
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }
            }

            @media (max-width: 640px) {
                .acdt-grid-status {
                    grid-template-columns: 1fr;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _limpar_estado_acidente_transito_sip() -> None:
    """Limpa os estados do módulo Acidente de Trânsito SIP."""
    chaves = [
        "acdt_sip_arquivo_consolidada",
        "acdt_sip_arquivo_complementar",
        "acdt_sip_resultado",
        "acdt_sip_cfg_usar_externo",
        "acdt_sip_cfg_caminho_base_enxuta",
        "acdt_sip_cfg_arq_cache_mun",
        "acdt_sip_cfg_limiar_nome",
        "acdt_sip_cfg_raio_confirma_m",
        "acdt_sip_cfg_raio_municipio_km",
        "acdt_sip_cfg_limiar_suspeito",
        "acdt_sip_cfg_niveis_filtrar",
    ]
    for chave in chaves:
        if chave in st.session_state:
            del st.session_state[chave]


def _init_state_acidente_transito_sip() -> None:
    """Inicializa as chaves de session_state do módulo."""
    defaults = {
        "acdt_sip_cfg_usar_externo": USAR_EXTERNO,
        "acdt_sip_cfg_caminho_base_enxuta": CAMINHO_BASE_ENXUTA,
        "acdt_sip_cfg_arq_cache_mun": ARQ_CACHE_MUN,
        "acdt_sip_cfg_limiar_nome": LIMIAR_NOME,
        "acdt_sip_cfg_raio_confirma_m": RAIO_CONFIRMA_M,
        "acdt_sip_cfg_raio_municipio_km": RAIO_MUNICIPIO_KM,
        "acdt_sip_cfg_limiar_suspeito": LIMIAR_SUSPEITO,
        "acdt_sip_cfg_niveis_filtrar": [
            "Exato (Numero)",
            "Centroide de Rua",
            "Centroide de Bairro",
            "Centroide de Cidade",
        ],
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def _normalizar_nome_aba(nome: str) -> str:
    """Normaliza nome de aba para comparação."""
    return sem_acento(nome).replace(" ", "").replace("_", "").replace("-", "")


def _selecionar_aba_consolidada(sheet_names: list[str]) -> str:
    """Seleciona a aba principal da planilha consolidada."""
    prioridades = [
        "CONSOLIDADA",
        "BASE",
        "DADOS",
        "PLAN1",
    ]
    normalizadas = {aba: _normalizar_nome_aba(aba) for aba in sheet_names}

    for prioridade in prioridades:
        for aba, nome_norm in normalizadas.items():
            if nome_norm == prioridade:
                return aba

    return sheet_names[0]


def _selecionar_aba_complementar(sheet_names: list[str]) -> str:
    """Seleciona a aba principal da planilha complementar."""
    prioridades = [
        "COMPLEMENTAR",
        "BASE",
        "DADOS",
        "PLAN1",
    ]
    normalizadas = {aba: _normalizar_nome_aba(aba) for aba in sheet_names}

    for prioridade in prioridades:
        for aba, nome_norm in normalizadas.items():
            if nome_norm == prioridade:
                return aba

    return sheet_names[0]


@st.cache_data(show_spinner=False)
def carregar_municipios() -> dict[str, str]:
    """Carrega municípios do Ceará a partir de cache local ou API do IBGE."""
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
        mapa = {sem_acento(municipio["nome"]): str(municipio["id"])[:7] for municipio in lista}

        with open(caminho, "w", encoding="utf-8") as arquivo:
            json.dump(mapa, arquivo, ensure_ascii=False)

        return mapa
    except Exception:
        return {}


def _montar_nome_logradouro(tipo: str, nome: str) -> str:
    """Monta nome padronizado do logradouro."""
    partes: list[str] = []
    tipo = str(tipo or "").strip()
    nome = str(nome or "").strip()

    if tipo and tipo.lower() != "none":
        partes.append(tipo)
    if nome and nome.lower() != "none":
        partes.append(nome)

    return " ".join(partes).strip()


@st.cache_data(show_spinner=False)
def carregar_base_geografica() -> Optional[pd.DataFrame]:
    """Carrega a base geográfica enxuta usada na validação e geocodificação."""
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
            f"O arquivo {config['caminho_base_enxuta']} não possui as colunas esperadas: {sorted(faltantes)}"
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
        lambda linha: _montar_nome_logradouro(
            linha.get("NM_TIP_LOG"),
            linha.get("NM_LOG"),
        ),
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
    """Limpa e padroniza número do endereço."""
    valor = str(numero or "").strip()

    if valor.lower() in ("nan", "none", "", "0", "0.0", "s/n", "sn"):
        return ""

    try:
        return str(int(float(valor)))
    except Exception:
        return re.sub(r"\D", "", valor)


def _hav(lat1, lon1, lat2, lon2):
    """Calcula distância haversine em metros."""
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
    """Motor de geocodificação com base local e ArcGIS."""

    def __init__(self) -> None:
        """Inicializa recursos de geocodificação e validação territorial."""
        self.config = obter_configuracao_tecnica()
        self.base = carregar_base_geografica()
        self.municipios = carregar_municipios()
        self.tree = None
        self.centroides_municipio: dict[str, tuple[float, float]] = {}

        if self.base is not None and len(self.base):
            self.glat = self.base["lat"].values.astype(float)
            self.glon = self.base["lon"].values.astype(float)
            self.gnome = self.base["nome_norm"].astype(str).values
            self.gcod = self.base["cod_mun"].astype(str).values
            self.tree = cKDTree(np.c_[self.glat, self.glon])

            centroides = self.base.groupby("cod_mun")[["lat", "lon"]].mean()
            self.centroides_municipio = {
                codigo: (linha["lat"], linha["lon"])
                for codigo, linha in centroides.iterrows()
            }

        self.geocode_ext = obter_geocoder_arcgis()

    def cod_municipio(self, municipio: str) -> str:
        """Retorna o código IBGE do município."""
        return self.municipios.get(sem_acento(municipio), "")

    def _idx_municipio(
        self,
        cod: str,
        ancora: Optional[tuple[float, float]],
    ) -> np.ndarray:
        """Retorna índices do município ou por proximidade."""
        if cod and self.tree is not None:
            indices = np.where(self.gcod == cod)[0]
            if len(indices):
                return indices

        if ancora is not None and self.tree is not None:
            indices = self.tree.query_ball_point(
                [ancora[0], ancora[1]],
                r=self.config["raio_municipio_km"] / 111.0,
            )
            return np.array(indices, dtype=int)

        return np.array([], dtype=int)

    def casar_rua(
        self,
        rua_norm: str,
        cod: str,
        ancora: Optional[tuple[float, float]],
    ) -> Optional[tuple[float, float, int]]:
        """Busca melhor casamento de rua na base local."""
        indices = self._idx_municipio(cod, ancora)
        if not len(indices):
            return None

        melhor_indice = None
        melhor_score = 0

        for indice in indices:
            score = fuzz.token_set_ratio(rua_norm, self.gnome[indice])
            if score > melhor_score:
                melhor_score = score
                melhor_indice = indice

        if melhor_indice is not None and melhor_score >= self.config["limiar_nome"]:
            return (
                float(self.glat[melhor_indice]),
                float(self.glon[melhor_indice]),
                melhor_score,
            )

        return None

    def validar(
        self,
        lat: float,
        lon: float,
        rua_norm: str,
        cod: str,
        ancora: Optional[tuple[float, float]],
    ) -> tuple[bool, Optional[float]]:
        """Valida coordenada externa com base local."""
        indices = self._idx_municipio(cod, ancora or (lat, lon))
        if not len(indices):
            return False, None

        nomes = self.gnome[indices]
        mascara = np.array(
            [
                fuzz.token_set_ratio(rua_norm, nome) >= self.config["limiar_nome"]
                for nome in nomes
            ]
        )

        if not mascara.any():
            return False, None

        indices_filtrados = indices[mascara]
        distancias = _hav(lat, lon, self.glat[indices_filtrados], self.glon[indices_filtrados])
        melhor = float(distancias.min())

        return melhor <= self.config["raio_confirma_m"], melhor

    def geocodificar(
        self,
        rua: str,
        numero: str,
        bairro: str,
        municipio: str,
    ) -> tuple[Optional[float], Optional[float], str, str, bool, Optional[float]]:
        """Executa estratégia hierárquica de geocodificação."""
        rua_limpa = limpar_logradouro(rua)
        bairro_limpo = limpar_bairro(bairro, municipio)
        numero_limpo = limpar_numero(numero)
        municipio_limpo = str(municipio or "").strip()
        rua_norm = sem_acento(rua_limpa)
        cod = self.cod_municipio(municipio_limpo)

        tem_rua = rua_limpa != ""
        tem_numero = numero_limpo != ""
        tem_bairro = bairro_limpo != ""
        tem_municipio = municipio_limpo != ""

        if tem_rua and tem_numero and tem_bairro and tem_municipio:
            partes = [
                f"{rua_limpa}, {numero_limpo}",
                bairro_limpo,
                municipio_limpo,
                "Ceara",
                "Brasil",
            ]
            consulta = ", ".join([parte for parte in partes if parte])

            externo = None
            if self.geocode_ext is not None:
                loc = self.geocode_ext(consulta, out_fields="*")
                if loc:
                    addr_type = ((loc.raw or {}).get("attributes", {}) or {}).get(
                        "Addr_type",
                        "",
                    )
                    externo = (
                        float(loc.latitude),
                        float(loc.longitude),
                        str(addr_type).lower(),
                    )

            ancora = (externo[0], externo[1]) if externo else None

            if externo:
                ok, distancia = self.validar(externo[0], externo[1], rua_norm, cod, ancora)
                if ok:
                    return (
                        externo[0],
                        externo[1],
                        "Exato (Numero)",
                        "ArcGIS+Parquet",
                        True,
                        distancia,
                    )

                if externo[2] in ROOFTOP:
                    return (
                        externo[0],
                        externo[1],
                        "Exato (Numero)",
                        "ArcGIS Rooftop",
                        False,
                        distancia,
                    )

            geobase = self.casar_rua(rua_norm, cod, ancora)
            if geobase:
                return (
                    geobase[0],
                    geobase[1],
                    "Centroide de Rua",
                    "Parquet (Base Enxuta)",
                    True,
                    0.0,
                )

            if externo:
                return (
                    externo[0],
                    externo[1],
                    "Centroide de Rua",
                    "ArcGIS (nao confirmado)",
                    False,
                    None,
                )

        if tem_rua:
            partes = [rua_limpa]
            if tem_bairro:
                partes.append(bairro_limpo)
            if tem_municipio:
                partes.extend([municipio_limpo, "Ceara", "Brasil"])
            consulta = ", ".join([parte for parte in partes if parte])

            externo = None
            if self.geocode_ext is not None:
                loc = self.geocode_ext(consulta, out_fields="*")
                if loc:
                    externo = (float(loc.latitude), float(loc.longitude))

            ancora = externo if externo else None
            geobase = self.casar_rua(rua_norm, cod, ancora)
            if geobase:
                return (
                    geobase[0],
                    geobase[1],
                    "Centroide de Rua",
                    "Parquet (Base Enxuta)",
                    True,
                    0.0,
                )

            if externo:
                return (
                    externo[0],
                    externo[1],
                    "Centroide de Rua",
                    "ArcGIS (nao confirmado)",
                    False,
                    None,
                )

        if tem_bairro and tem_municipio and self.geocode_ext is not None:
            consulta = ", ".join([bairro_limpo, municipio_limpo, "Ceara", "Brasil"])
            loc = self.geocode_ext(consulta, out_fields="*")
            if loc:
                return (
                    float(loc.latitude),
                    float(loc.longitude),
                    "Centroide de Bairro",
                    "ArcGIS Bairro",
                    False,
                    None,
                )

        centroide = self.centroides_municipio.get(cod)
        if centroide:
            return (
                centroide[0],
                centroide[1],
                "Centroide de Cidade",
                "Centroide Municipio",
                False,
                None,
            )

        if tem_municipio and self.geocode_ext is not None:
            loc = self.geocode_ext(f"{municipio_limpo}, Ceara, Brasil", out_fields="*")
            if loc:
                return (
                    float(loc.latitude),
                    float(loc.longitude),
                    "Centroide de Cidade",
                    "ArcGIS Cidade",
                    False,
                    None,
                )

        return (None, None, "Nao Encontrado", "-", False, None)


def _garantir_colunas(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    """Garante a existência das colunas esperadas no DataFrame."""
    df = df.copy()
    for coluna in colunas:
        if coluna not in df.columns:
            df[coluna] = pd.NA
    return df


def _validar_colunas_consolidada(df: pd.DataFrame) -> None:
    """Valida as colunas mínimas da planilha consolidada."""
    colunas_obrigatorias = [
        "ais",
        "natureza",
        "tombo",
        "tipo",
        "procedimento",
        "regiao",
        "municipio",
        "bairro",
        "logradouro",
        "numero",
        "complemento",
        "latitude",
        "longitude",
        "data",
        "hora",
        "lat",
        "lon",
        "nivel_geocodificacao",
        "geocodificacao",
    ]
    faltantes = [coluna for coluna in colunas_obrigatorias if coluna not in df.columns]
    if faltantes:
        raise ValueError(
            "A planilha Consolidada não possui todas as colunas esperadas: "
            f"{faltantes}"
        )


def _renomear_colunas_complementar(df: pd.DataFrame) -> pd.DataFrame:
    """Padroniza os nomes da planilha complementar para o layout esperado."""
    df = df.copy()

    mapa_renomeacao: dict[str, str] = {}

    col_ais = encontrar_coluna_por_nomes(df, ["ais"], obrigatoria=True)
    col_natureza = encontrar_coluna_por_nomes(df, ["natureza"], obrigatoria=True)
    col_tombo = encontrar_coluna_por_nomes(df, ["tombo"], obrigatoria=True)
    col_tipo = encontrar_coluna_por_nomes(df, ["tipo"], obrigatoria=True)
    col_procedimento = encontrar_coluna_por_nomes(
        df,
        ["procedimento", "tipo_procedimento", "tipoprocedimento", "tipo procedimento"],
        obrigatoria=True,
    )
    col_regiao = encontrar_coluna_por_nomes(df, ["regiao", "região"], obrigatoria=True)
    col_municipio = encontrar_coluna_por_nomes(
        df,
        ["municipio", "município"],
        obrigatoria=True,
    )
    col_bairro = encontrar_coluna_por_nomes(df, ["bairro"], obrigatoria=True)
    col_logradouro = encontrar_coluna_por_nomes(
        df,
        ["logradouro", "endereco", "endereço", "rua"],
        obrigatoria=True,
    )
    col_numero = encontrar_coluna_por_nomes(
        df,
        ["numero", "número"],
        obrigatoria=True,
    )
    col_complemento = encontrar_coluna_por_nomes(df, ["complemento"], obrigatoria=True)
    col_latitude = encontrar_coluna_por_nomes(df, ["latitude"], obrigatoria=True)
    col_longitude = encontrar_coluna_por_nomes(df, ["longitude"], obrigatoria=True)
    col_data = encontrar_coluna_por_nomes(df, ["data"], obrigatoria=True)
    col_hora = encontrar_coluna_por_nomes(df, ["hora"], obrigatoria=True)

    mapa_renomeacao[col_ais] = "ais"
    mapa_renomeacao[col_natureza] = "natureza"
    mapa_renomeacao[col_tombo] = "tombo"
    mapa_renomeacao[col_tipo] = "tipo"
    mapa_renomeacao[col_procedimento] = "procedimento"
    mapa_renomeacao[col_regiao] = "regiao"
    mapa_renomeacao[col_municipio] = "municipio"
    mapa_renomeacao[col_bairro] = "bairro"
    mapa_renomeacao[col_logradouro] = "logradouro"
    mapa_renomeacao[col_numero] = "numero"
    mapa_renomeacao[col_complemento] = "complemento"
    mapa_renomeacao[col_latitude] = "latitude"
    mapa_renomeacao[col_longitude] = "longitude"
    mapa_renomeacao[col_data] = "data"
    mapa_renomeacao[col_hora] = "hora"

    df = df.rename(columns=mapa_renomeacao)
    return _garantir_colunas(df, COLUNAS_FINAIS_ESPERADAS)


def preparar_campos_geocodificacao(
    df: pd.DataFrame,
    col_endereco: str,
    col_numero: str,
    col_bairro: str,
    col_municipio: str,
) -> pd.DataFrame:
    """Prepara campos auxiliares para geocodificação."""
    df = df.copy()
    df["logradouro_busca"] = df[col_endereco].apply(limpar_logradouro)
    df["numero_busca"] = df[col_numero].apply(limpar_numero)
    df["bairro_busca"] = df.apply(
        lambda linha: limpar_bairro(linha[col_bairro], linha[col_municipio]),
        axis=1,
    )
    df["municipio_busca"] = df[col_municipio].fillna("").astype(str).str.strip()
    return df


def geocodificar_linhas_novas(
    df: pd.DataFrame,
    col_lat_destino: str,
    col_lon_destino: str,
) -> tuple[pd.DataFrame, int]:
    """Geocodifica linhas sem coordenadas coletadas e retorna DataFrame atualizado."""
    config = obter_configuracao_tecnica()
    motor = MotorGeocodificacaoSoberana()

    lats = []
    lons = []
    niveis = []
    fontes = []
    confirmados = []
    distancias = []
    origens_geo = []

    total = len(df)
    geocodificados = 0
    progresso = st.progress(0)
    status = st.empty()

    for indice, (_, linha) in enumerate(df.iterrows(), start=1):
        lat_coletada = pd.to_numeric(linha.get("latitude"), errors="coerce")
        lon_coletada = pd.to_numeric(linha.get("longitude"), errors="coerce")

        if pd.notna(lat_coletada) and pd.notna(lon_coletada):
            lats.append(float(lat_coletada))
            lons.append(float(lon_coletada))
            niveis.append("Localização Coletada")
            fontes.append("Coordenada Informada")
            confirmados.append(True)
            distancias.append(0.0)
            origens_geo.append("Localização Coletada")
        else:
            resultado = motor.geocodificar(
                linha.get("logradouro_busca", ""),
                linha.get("numero_busca", ""),
                linha.get("bairro_busca", ""),
                linha.get("municipio_busca", ""),
            )

            lats.append(resultado[0])
            lons.append(resultado[1])
            niveis.append(resultado[2])
            fontes.append(resultado[3])
            confirmados.append(resultado[4])
            distancias.append(resultado[5])
            origens_geo.append(
                "Localização Geocodificada"
                if resultado[0] is not None and resultado[1] is not None
                else pd.NA
            )

            if resultado[0] is not None and resultado[1] is not None:
                geocodificados += 1

        progresso.progress(indice / max(total, 1))
        status.info(
            f"Processando registros... {indice}/{total} | "
            f"Geocodificados pelo sistema: {geocodificados}"
        )

    df = df.copy()
    df[col_lat_destino] = lats
    df[col_lon_destino] = lons
    df["nivel_geocodificacao"] = niveis
    df["geocodificacao"] = origens_geo
    df["fonte"] = fontes
    df["_confirmado_base"] = confirmados
    df["_dist_validacao_m"] = distancias

    lat_series = pd.to_numeric(df[col_lat_destino], errors="coerce")
    lon_series = pd.to_numeric(df[col_lon_destino], errors="coerce")
    chave = lat_series.round(6).astype(str) + "," + lon_series.round(6).astype(str)
    contagem = chave.value_counts()
    df["ocorrencias_mesmo_ponto"] = chave.map(contagem).fillna(1).astype(int)
    df["_loc_aproximada"] = (
        (df["ocorrencias_mesmo_ponto"] >= config["limiar_suspeito"])
        & (df["numero_busca"].fillna("").astype(str).str.strip() == "")
    )

    progresso.empty()
    status.success(
        f"Processamento concluído. Registros geocodificados pelo sistema: {geocodificados}"
    )
    return df, geocodificados


def _ordenar_dataframe_final(df: pd.DataFrame) -> pd.DataFrame:
    """Ordena o DataFrame final por data e hora."""
    df = df.copy()

    data_aux = pd.to_datetime(df["data"], errors="coerce", dayfirst=True)
    hora_aux = pd.to_datetime(
        df["hora"].astype(str),
        errors="coerce",
        format="%H:%M:%S",
    )

    hora_texto = hora_aux.dt.strftime("%H:%M:%S")
    datahora = pd.to_datetime(
        data_aux.dt.strftime("%Y-%m-%d").fillna("")
        + " "
        + hora_texto.fillna("00:00:00"),
        errors="coerce",
    )

    df["__datahora__"] = datahora
    df = df.sort_values(
        by="__datahora__",
        ascending=True,
        na_position="last",
    ).reset_index(drop=True)

    return df.drop(columns=["__datahora__"], errors="ignore")


def _render_configuracao_tecnica_acidente_transito_sip() -> None:
    """Renderiza a seção de configuração técnica do módulo."""
    with st.expander("Configuração técnica", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.toggle(
                "Usar ArcGIS como fallback",
                key="acdt_sip_cfg_usar_externo",
                help="Quando ativado, usa ArcGIS como apoio à geocodificação além da base parquet local.",
            )
            st.text_input(
                "Base geográfica (.parquet)",
                key="acdt_sip_cfg_caminho_base_enxuta",
                help="Arquivo parquet enxuto utilizado para validação e apoio na geocodificação.",
            )
            st.text_input(
                "Arquivo cache de municípios",
                key="acdt_sip_cfg_arq_cache_mun",
                help="Arquivo JSON local usado para cache dos municípios do Ceará.",
            )

        with col2:
            st.slider(
                "Limiar de similaridade",
                min_value=70,
                max_value=100,
                key="acdt_sip_cfg_limiar_nome",
                help="Percentual mínimo de similaridade entre logradouro informado e base local.",
            )
            st.number_input(
                "Raio de confirmação (m)",
                min_value=1.0,
                step=1.0,
                format="%.2f",
                key="acdt_sip_cfg_raio_confirma_m",
                help="Distância máxima em metros para considerar uma coordenada validada.",
            )
            st.number_input(
                "Raio do município (km)",
                min_value=1.0,
                step=1.0,
                format="%.2f",
                key="acdt_sip_cfg_raio_municipio_km",
                help="Raio usado para busca aproximada quando não há código municipal válido.",
            )
            st.number_input(
                "Limiar de ponto suspeito",
                min_value=1,
                step=1,
                key="acdt_sip_cfg_limiar_suspeito",
                help="Quantidade mínima de ocorrências no mesmo ponto para sinalização de localização aproximada.",
            )

        st.multiselect(
            "Selecione o nível de geocodificação a manter no arquivo final",
            options=NIVEIS_GEOCODIFICACAO_POSSIVEIS,
            default=st.session_state.get(
                "acdt_sip_cfg_niveis_filtrar",
                ["Exato (Numero)", "Centroide de Rua", "Centroide de Bairro", "Centroide de Cidade"],
            ),
            key="acdt_sip_cfg_niveis_filtrar",
            help=(
                "Escolha quais níveis de geocodificação produzidos pelo sistema devem ser mantidos no arquivo final. "
                "Registros com Localização Coletada serão mantidos independentemente deste filtro."
            ),
        )


def _processar_acidente_transito_sip(
    arquivo_consolidada,
    arquivo_complementar,
) -> dict[str, Any]:
    """Processa os arquivos do indicador Acidente de Trânsito SIP."""
    arquivo_consolidada.seek(0)
    arquivo_complementar.seek(0)

    xls_consolidada = pd.ExcelFile(arquivo_consolidada)
    xls_complementar = pd.ExcelFile(arquivo_complementar)

    aba_consolidada = _selecionar_aba_consolidada(xls_consolidada.sheet_names)
    aba_complementar = _selecionar_aba_complementar(xls_complementar.sheet_names)

    df_consolidada = pd.read_excel(xls_consolidada, sheet_name=aba_consolidada)
    df_complementar = pd.read_excel(xls_complementar, sheet_name=aba_complementar)

    df_consolidada = normalizar_colunas(df_consolidada)
    df_complementar = normalizar_colunas(df_complementar)

    _validar_colunas_consolidada(df_consolidada)
    df_complementar = _renomear_colunas_complementar(df_complementar)

    df_consolidada = _garantir_colunas(df_consolidada, COLUNAS_FINAIS_ESPERADAS)
    df_complementar = _garantir_colunas(df_complementar, COLUNAS_FINAIS_ESPERADAS)

    total_lido = len(df_complementar)

    df_complementar = preparar_campos_geocodificacao(
        df_complementar,
        col_endereco="logradouro",
        col_numero="numero",
        col_bairro="bairro",
        col_municipio="municipio",
    )

    df_complementar, geocodificados = geocodificar_linhas_novas(
        df_complementar,
        col_lat_destino="lat",
        col_lon_destino="lon",
    )

    total_com_coordenada_coletada = int(
        (
            pd.to_numeric(df_complementar["latitude"], errors="coerce").notna()
            & pd.to_numeric(df_complementar["longitude"], errors="coerce").notna()
        ).sum()
    )

    antes_exclusao_sem_geo = len(df_complementar)
    df_complementar = df_complementar.dropna(subset=["lat", "lon"]).copy()
    removidos_sem_geocodificacao = antes_exclusao_sem_geo - len(df_complementar)

    niveis_filtrar = obter_configuracao_tecnica().get("niveis_filtrar") or []
    if niveis_filtrar:
        mascara_manter = (
            df_complementar["geocodificacao"].eq("Localização Coletada")
            | df_complementar["nivel_geocodificacao"].isin(niveis_filtrar)
        )
        df_complementar = df_complementar[mascara_manter].copy()

    df_complementar = df_complementar.drop(
        columns=[
            "logradouro_busca",
            "numero_busca",
            "bairro_busca",
            "municipio_busca",
            "fonte",
            "_confirmado_base",
            "_dist_validacao_m",
            "ocorrencias_mesmo_ponto",
            "_loc_aproximada",
        ],
        errors="ignore",
    )

    df_complementar = alinhar_colunas_com_base(
        df_consolidada[COLUNAS_FINAIS_ESPERADAS],
        df_complementar,
    )

    df_final = pd.concat(
        [
            df_consolidada[COLUNAS_FINAIS_ESPERADAS].copy(),
            df_complementar[COLUNAS_FINAIS_ESPERADAS].copy(),
        ],
        ignore_index=True,
    )

    df_final = _ordenar_dataframe_final(df_final)

    contagens_nivel = (
        df_final["nivel_geocodificacao"]
        .fillna("Nao Informado")
        .value_counts(dropna=False)
        .to_dict()
        if "nivel_geocodificacao" in df_final.columns
        else {}
    )

    total_final = len(df_final)
    adicionados = len(df_complementar)

    situacao = (
        "Arquivo complementar processado com sucesso. Registros com coordenadas pré-existentes "
        "foram marcados como Localização Coletada e os demais foram geocodificados pelo sistema."
    )

    return {
        "df_final": df_final,
        "total_lido": total_lido,
        "total_final": total_final,
        "adicionados": adicionados,
        "geocodificados": geocodificados,
        "localizacao_coletada": total_com_coordenada_coletada,
        "removidos_sem_geocodificacao": removidos_sem_geocodificacao,
        "contagens_nivel": contagens_nivel,
        "aba_consolidada": aba_consolidada,
        "aba_complementar": aba_complementar,
        "situacao": situacao,
    }


def interface_acidente_transito_sip() -> None:
    """Interface Streamlit para o módulo Acidente de Trânsito SIP."""
    _init_state_acidente_transito_sip()
    _aplicar_estilo_acidente_transito_sip()

    st.markdown(
        """
        <div class="acdt-section-card">
            <div class="acdt-section-title">ACIDENTE DE TRANSITO - SIP</div>
            <div class="acdt-section-desc">
                Envie a planilha consolidada e a planilha complementar para gerar a base final
                do indicador com reaproveitamento de coordenadas já coletadas e geocodificação
                automática dos registros sem coordenadas.
            </div>
            <ul class="acdt-mini-list">
                <li>Leitura da base consolidada no layout oficial do indicador.</li>
                <li>Leitura da base complementar com normalização automática de colunas.</li>
                <li>Reaproveitamento de LATITUDE/LONGITUDE já existentes como Localização Coletada.</li>
                <li>Geocodificação dos demais registros com a mesma metodologia do módulo CVP SIP.</li>
                <li>Geração do arquivo final no padrão exigido pelo QGP.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _render_configuracao_tecnica_acidente_transito_sip()

    st.markdown(
        f"""
        <div class="acdt-section-card">
            <div class="acdt-section-title">Base geográfica de apoio</div>
            <div class="acdt-section-desc">
                Este módulo utiliza a base geográfica auxiliar localizada em
                <strong>{st.session_state.get("acdt_sip_cfg_caminho_base_enxuta", CAMINHO_BASE_ENXUTA)}</strong>
                para validação e apoio à geocodificação dos registros sem coordenadas.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        base_geo = carregar_base_geografica()
        caminho_base = st.session_state.get(
            "acdt_sip_cfg_caminho_base_enxuta",
            CAMINHO_BASE_ENXUTA,
        )
        if base_geo is not None and not base_geo.empty:
            st.success(
                f"Base geográfica carregada com sucesso: {len(base_geo):,} registros em {caminho_base}"
            )
        else:
            st.warning(
                f"A base geográfica não foi carregada. Verifique o arquivo {caminho_base}."
            )
    except Exception as exc:
        st.error(f"Erro ao carregar base geográfica: {exc}")

    st.markdown(
        '<div class="acdt-upload-label">📁 Planilha Consolidada</div>',
        unsafe_allow_html=True,
    )
    arquivo_consolidada = st.file_uploader(
        "Planilha Consolidada",
        type=["xlsx", "xls"],
        key="acdt_sip_arquivo_consolidada",
        label_visibility="collapsed",
    )

    st.markdown(
        '<div class="acdt-upload-label">📁 Planilha Complementar</div>',
        unsafe_allow_html=True,
    )
    arquivo_complementar = st.file_uploader(
        "Planilha Complementar",
        type=["xlsx", "xls"],
        key="acdt_sip_arquivo_complementar",
        label_visibility="collapsed",
    )

    pode_processar = (
        arquivo_consolidada is not None
        and arquivo_complementar is not None
    )

    st.markdown(
        """
        <div class="acdt-section-card">
            <div class="acdt-section-title">Execução do processamento</div>
            <div class="acdt-section-desc">
                Após carregar os dois arquivos, inicie o processamento para consolidar,
                geocodificar os registros sem coordenadas e gerar o arquivo final.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        processar = st.button(
            "Processar Acidente de Trânsito SIP",
            type="primary",
            use_container_width=True,
            disabled=not pode_processar,
            key="btn_processar_acidente_transito_sip",
        )

    with col_btn2:
        limpar = st.button(
            "Limpar seleção",
            use_container_width=True,
            key="btn_limpar_acidente_transito_sip",
        )

    if limpar:
        _limpar_estado_acidente_transito_sip()
        st.rerun()

    if processar:
        try:
            carregar_base_geografica.clear()
            carregar_municipios.clear()
            obter_geocoder_arcgis.clear()

            with st.spinner("Processando base e geocodificando ocorrências..."):
                resultado = _processar_acidente_transito_sip(
                    arquivo_consolidada,
                    arquivo_complementar,
                )

            st.session_state.acdt_sip_resultado = resultado

        except Exception as exc:
            st.session_state.acdt_sip_resultado = {
                "erro": str(exc),
                "traceback": traceback.format_exc(),
            }

    resultado = st.session_state.get("acdt_sip_resultado")

    if not resultado:
        return

    if "erro" in resultado:
        st.error(f"Erro durante o processamento: {resultado['erro']}")
        with st.expander("Detalhes do erro"):
            st.code(resultado["traceback"])
        return

    badges = [
        f'<span class="acdt-badge ok">Aba consolidada: {resultado["aba_consolidada"]}</span>',
        f'<span class="acdt-badge ok">Aba complementar: {resultado["aba_complementar"]}</span>',
        f'<span class="acdt-badge ok">Localização coletada: {resultado["localizacao_coletada"]}</span>',
        f'<span class="acdt-badge ok">Geocodificados pelo sistema: {resultado["geocodificados"]}</span>',
    ]

    if resultado["removidos_sem_geocodificacao"] > 0:
        badges.append(
            f'<span class="acdt-badge warn">Sem geocodificação removidos: {resultado["removidos_sem_geocodificacao"]}</span>'
        )
    else:
        badges.append(
            '<span class="acdt-badge ok">Nenhum registro removido por ausência de coordenadas</span>'
        )

    st.success("✅ Processamento concluído com sucesso.")

    st.markdown(
        f"""
        <div class="acdt-section-card">
            <div class="acdt-section-title">Resumo do processamento</div>
            <div class="acdt-section-desc">{resultado["situacao"]}</div>
            <div class="acdt-grid-status">
                <div class="acdt-stat">
                    <div class="acdt-stat-label">Total lido</div>
                    <div class="acdt-stat-value">{resultado["total_lido"]}</div>
                </div>
                <div class="acdt-stat">
                    <div class="acdt-stat-label">Adicionados</div>
                    <div class="acdt-stat-value">{resultado["adicionados"]}</div>
                </div>
                <div class="acdt-stat">
                    <div class="acdt-stat-label">Total final</div>
                    <div class="acdt-stat-value">{resultado["total_final"]}</div>
                </div>
                <div class="acdt-stat">
                    <div class="acdt-stat-label">Geocodificados</div>
                    <div class="acdt-stat-value">{resultado["geocodificados"]}</div>
                </div>
            </div>
            <div class="acdt-badge-wrap">
                {"".join(badges)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    contagens_nivel = resultado.get("contagens_nivel", {})
    if contagens_nivel:
        st.markdown(
            """
            <div class="acdt-section-card">
                <div class="acdt-section-title">Níveis de geocodificação</div>
                <div class="acdt-section-desc">
                    Distribuição final dos registros por nível de geocodificação.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        n1, n2, n3, n4 = st.columns(4)
        n1.metric("Exato (Número)", contagens_nivel.get("Exato (Numero)", 0))
        n2.metric("Centroide de Rua", contagens_nivel.get("Centroide de Rua", 0))
        n3.metric("Centroide de Bairro", contagens_nivel.get("Centroide de Bairro", 0))
        n4.metric("Centroide de Cidade", contagens_nivel.get("Centroide de Cidade", 0))

    with st.expander("Prévia do arquivo final", expanded=False):
        st.dataframe(
            resultado["df_final"].head(200),
            use_container_width=True,
            hide_index=True,
        )

    excel_data = gerar_arquivo_excel(
        resultado["df_final"],
        sheet_name="ACIDENTE_TRANSITO_SIP",
    )

    st.download_button(
        label="💾 Baixar arquivo final",
        data=excel_data,
        file_name=NOME_ARQUIVO_FINAL,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key="download_acidente_transito_sip",
    )

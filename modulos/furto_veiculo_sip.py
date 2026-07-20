"""
Módulo Furto de Veículo (SIP) - Geocodificação por endereço
Versão Streamlit adaptada para o QGP Online.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
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
    nome_arquivo_padrao,
    normalizar_colunas,
    obter_ultima_datahora,
    renomear_colunas_equivalentes,
)

NOME_ARQUIVO_FINAL = nome_arquivo_padrao(7, "FURTO-DE-VEICULO-SIP-ENDERECO")


@dataclass(frozen=True)
class FurtoVeiculoSipConfig:
    usar_externo: bool = True
    caminho_base_enxuta: str = "CVP_SIP_GEOCODIFICAR.parquet"
    limiar_nome: int = 88
    raio_confirma_m: float = 100.0
    raio_municipio_km: float = 8.0
    limiar_suspeito: int = 5
    uf_codigo: str = "23"
    arq_cache_mun: str = "municipios_ce.json"
    arcgis_timeout: int = 15
    arcgis_delay_s: float = 0.4
    arcgis_retries: int = 2
    # novo campo: níveis de geocodificação a manter no arquivo final
    niveis_filtrar: Optional[list[str]] = None


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
    "LADO ÍMPAR",
    "- P",
    "FORTALEZA, CE",
    ", CE",
]

RE_BNI = re.compile(
    r"\(?\s*bairro\s+n[aã]o\s+identificad[oa]\s*\)?",
    flags=re.IGNORECASE,
)

TIPOS = (
    "Rua",
    "Avenida",
    "Travessa",
    "Praca",
    "Rodovia",
    "Alameda",
    "Passeio",
)

ROOFTOP = (
    "pointaddress",
    "streetaddress",
    "subaddress",
    "pointaddressvd",
)

# níveis possíveis de geocodificação para seleção
NIVEIS_GEOCODIFICACAO_POSSIVEIS = [
    "Exato (Numero)",
    "Centroide de Rua",
    "Centroide de Bairro",
    "Centroide de Cidade",
    "Nao Encontrado",
]


def _resolver_caminho_base_enxuta(caminho_informado: str) -> str:
    """
    Resolve o caminho do parquet de apoio de forma robusta para execução
    standalone e também via módulo agregador.
    """
    candidatos = [
        Path(caminho_informado),
        Path(f"./{caminho_informado}"),
        Path("services") / caminho_informado,
        Path("./services") / caminho_informado,
        Path("services/CVP_SIP_GEOCODIFICAR.parquet"),
        Path("./services/CVP_SIP_GEOCODIFICAR.parquet"),
        Path("CVP_SIP_GEOCODIFICAR.parquet"),
        Path("./CVP_SIP_GEOCODIFICAR.parquet"),
    ]

    vistos = set()
    for candidato in candidatos:
        candidato_str = str(candidato)
        if candidato_str in vistos:
            continue
        vistos.add(candidato_str)
        if candidato.exists():
            return candidato_str

    return str(Path(caminho_informado))


def _normalizar_config(config: Optional[FurtoVeiculoSipConfig]) -> FurtoVeiculoSipConfig:
    """
    Garante uma configuração válida mesmo quando o módulo for chamado
    externamente sem config explícito.
    """
    if config is None:
        config = FurtoVeiculoSipConfig()

    caminho_resolvido = _resolver_caminho_base_enxuta(config.caminho_base_enxuta)

    # default de níveis se não informado
    niveis_default = ["Exato (Numero)", "Centroide de Rua"]
    niveis_filtrar = config.niveis_filtrar or niveis_default

    return FurtoVeiculoSipConfig(
        usar_externo=config.usar_externo,
        caminho_base_enxuta=caminho_resolvido,
        limiar_nome=int(config.limiar_nome),
        raio_confirma_m=float(config.raio_confirma_m),
        raio_municipio_km=float(config.raio_municipio_km),
        limiar_suspeito=int(config.limiar_suspeito),
        uf_codigo=str(config.uf_codigo),
        arq_cache_mun=str(config.arq_cache_mun),
        arcgis_timeout=int(config.arcgis_timeout),
        arcgis_delay_s=float(config.arcgis_delay_s),
        arcgis_retries=int(config.arcgis_retries),
        niveis_filtrar=list(niveis_filtrar),
    )


def _aplicar_estilo_furto_veiculo_sip() -> None:
    """Aplica estilo visual padronizado ao módulo."""
    st.markdown(
        """
        <style>
            .fvsip-card {
                background: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 18px;
                padding: 1.1rem 1.1rem 0.85rem 1.1rem;
                margin: 1rem 0;
            }
            .fvsip-title {
                font-size: 1.15rem;
                font-weight: 800;
                color: #f8fafc;
                margin-bottom: 0.25rem;
            }
            .fvsip-desc {
                font-size: 0.93rem;
                color: rgba(255, 255, 255, 0.72);
                margin-bottom: 0.8rem;
                line-height: 1.55;
            }
            .fvsip-list {
                margin: 0.55rem 0 0 0;
                padding-left: 1rem;
                color: rgba(255, 255, 255, 0.78);
                font-size: 0.92rem;
            }
            .fvsip-grid {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.85rem;
                margin-top: 1rem;
            }
            .fvsip-stat {
                background: rgba(255, 255, 255, 0.025);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
                padding: 0.95rem 1rem;
            }
            .fvsip-stat-label {
                font-size: 0.78rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                color: rgba(255, 255, 255, 0.58);
                margin-bottom: 0.35rem;
                font-weight: 700;
            }
            .fvsip-stat-value {
                font-size: 1.18rem;
                font-weight: 900;
                color: #ffffff;
                line-height: 1.15;
                word-break: break-word;
            }
            .fvsip-badges {
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem;
                margin-top: 0.65rem;
            }
            .fvsip-badge {
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
            .fvsip-badge.ok {
                background: rgba(34, 197, 94, 0.10);
                color: #b7f7c9;
                border-color: rgba(34, 197, 94, 0.22);
            }
            .fvsip-badge.warn {
                background: rgba(245, 158, 11, 0.10);
                color: #fde4b0;
                border-color: rgba(245, 158, 11, 0.22);
            }
            .fvsip-badge.info {
                background: rgba(59, 130, 246, 0.10);
                color: #bfdbfe;
                border-color: rgba(59, 130, 246, 0.22);
            }
            .fvsip-badge.neutral {
                background: rgba(255, 255, 255, 0.04);
                color: #e5e7eb;
                border-color: rgba(255, 255, 255, 0.10);
            }
            .fvsip-level-grid {
                display: grid;
                grid-template-columns: repeat(5, minmax(0, 1fr));
                gap: 0.75rem;
                margin-top: 0.9rem;
            }
            .fvsip-level {
                background: rgba(255,255,255,0.025);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 14px;
                padding: 0.85rem 0.9rem;
            }
            .fvsip-level-name {
                font-size: 0.78rem;
                color: rgba(255,255,255,0.64);
                font-weight: 700;
                margin-bottom: 0.35rem;
                min-height: 2rem;
            }
            .fvsip-level-value {
                font-size: 1.12rem;
                font-weight: 900;
                color: #fff;
            }
            .fvsip-field-label {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                margin-bottom: 0.45rem;
                margin-top: 0.2rem;
            }
            .fvsip-field-label-text {
                font-size: 0.92rem;
                font-weight: 700;
                color: rgba(255, 255, 255, 0.90);
                line-height: 1.2;
            }
            .fvsip-tooltip {
                position: relative;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 18px;
                height: 18px;
                border-radius: 999px;
                border: 1px solid rgba(255, 255, 255, 0.16);
                background: rgba(255, 255, 255, 0.05);
                color: #dbeafe;
                font-size: 0.72rem;
                font-weight: 800;
                cursor: help;
                flex-shrink: 0;
            }
            .fvsip-tooltip-box {
                position: absolute;
                left: calc(100% + 10px);
                top: 50%;
                transform: translateY(-50%);
                width: 300px;
                background: #0f172a;
                color: #e5eefb;
                border: 1px solid rgba(148, 163, 184, 0.28);
                border-radius: 12px;
                padding: 0.75rem 0.85rem;
                font-size: 0.82rem;
                line-height: 1.45;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.30);
                opacity: 0;
                visibility: hidden;
                pointer-events: none;
                transition: opacity 0.18s ease, transform 0.18s ease;
                z-index: 9999;
            }
            .fvsip-tooltip-box::before {
                content: "";
                position: absolute;
                left: -6px;
                top: 50%;
                width: 10px;
                height: 10px;
                background: #0f172a;
                border-left: 1px solid rgba(148, 163, 184, 0.28);
                border-bottom: 1px solid rgba(148, 163, 184, 0.28);
                transform: translateY(-50%) rotate(45deg);
            }
            .fvsip-tooltip:hover .fvsip-tooltip-box {
                opacity: 1;
                visibility: visible;
                transform: translateY(-50%) translateX(2px);
            }
            @media (max-width: 1200px) {
                .fvsip-grid {
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }
                .fvsip-level-grid {
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }
            }
            @media (max-width: 640px) {
                .fvsip-grid,
                .fvsip-level-grid {
                    grid-template-columns: 1fr;
                }
                .fvsip-tooltip-box {
                    left: 50%;
                    top: calc(100% + 10px);
                    transform: translateX(-50%);
                    width: min(280px, 80vw);
                }
                .fvsip-tooltip-box::before {
                    left: 50%;
                    top: -6px;
                    transform: translateX(-50%) rotate(45deg);
                    border-left: 1px solid rgba(148, 163, 184, 0.28);
                    border-top: 1px solid rgba(148, 163, 184, 0.28);
                    border-bottom: none;
                }
                .fvsip-tooltip:hover .fvsip-tooltip-box {
                    transform: translateX(-50%);
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_label_flutuante(label: str, tooltip: str) -> None:
    st.markdown(
        f"""
        <div class="fvsip-field-label">
            <span class="fvsip-field-label-text">{label}</span>
            <span class="fvsip-tooltip">
                ?
                <span class="fvsip-tooltip-box">{tooltip}</span>
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sem_acento(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in normalizado if not unicodedata.combining(c)).upper().strip()


def _normalizar_nome_aba(nome: str) -> str:
    return sem_acento(nome).replace(" ", "").replace("_", "").replace("-", "")


def _selecionar_aba_arquivo_02(sheet_names: list[str]) -> str:
    alvo = "FURTOSIP"
    for aba in sheet_names:
        if _normalizar_nome_aba(aba) == alvo:
            return aba

    for aba in sheet_names:
        nome = _normalizar_nome_aba(aba)
        if "FURTO" in nome and "SIP" in nome:
            return aba

    raise ValueError(
        f"Aba 'Furto SIP' não encontrada no Arquivo 02. Abas disponíveis: {sheet_names}"
    )


def _selecionar_aba_arquivo_01(sheet_names: list[str]) -> str:
    prioridades = [
        "FURTOVEICULOSIP",
        "FURTODEVEICULO",
        "FURTOVEICULO",
        "BASE",
        "BASEFURTO",
    ]
    normalizadas = {aba: _normalizar_nome_aba(aba) for aba in sheet_names}

    for prioridade in prioridades:
        for aba, nome_norm in normalizadas.items():
            if nome_norm == prioridade:
                return aba

    for aba, nome_norm in normalizadas.items():
        if "FURTO" in nome_norm and "VEICULO" in nome_norm:
            return aba

    return sheet_names[0]


def _obter_coluna_natureza(df: pd.DataFrame) -> str | None:
    return encontrar_coluna_por_nomes(
        df,
        [
            "natureza",
            "descricao_natureza",
            "tipo_crime",
            "tipo_ocorrencia",
            "ocorrencia",
        ],
        obrigatoria=False,
    )


def _eh_furto_veiculo(valor: str) -> bool:
    txt = sem_acento(valor)
    if not txt:
        return False

    termos_excludentes = [
        "PLACA",
        "PLACAS",
        "DOCUMENTO",
        "DOCUMENTOS",
        "CRLV",
        "CRV",
        "CHAVE",
        "CHAVES",
        "ESTEPE",
        "PNEU",
        "PNEUS",
        "RODA",
        "RODAS",
        "BATERIA",
        "SOM",
        "RETROVISOR",
        "ACESSORIO",
        "ACESSORIOS",
        "PECAS",
        "PECA",
    ]
    if any(termo in txt for termo in termos_excludentes):
        return False

    padroes_exatos_ou_fortes = [
        "FURTO DE VEICULO",
        "FURTO VEICULO",
        "FURTO DE VEICULOS",
        "FURTO VEICULOS",
        "FURTO DE AUTOMOVEL",
        "FURTO AUTOMOVEL",
        "FURTO DE MOTOCICLETA",
        "FURTO MOTOCICLETA",
        "FURTO DE CARRO",
        "FURTO CARRO",
        "FURTO DE MOTO",
        "FURTO MOTO",
    ]

    if any(padrao in txt for padrao in padroes_exatos_ou_fortes):
        return True

    return "FURTO" in txt and "VEICULO" in txt and "PLACA" not in txt


def gerar_excel_em_memoria(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="FURTO_VEICULO_SIP_ENDERECO")
    buffer.seek(0)
    return buffer.getvalue()


@st.cache_data(show_spinner=False)
def carregar_municipios(uf_codigo: str, arq_cache_mun: str) -> dict:
    caminho = Path(arq_cache_mun)
    if caminho.exists():
        try:
            with open(caminho, encoding="utf-8") as arquivo:
                return json.load(arquivo)
        except Exception:
            pass

    url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf_codigo}/municipios"
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
    partes = []
    tipo = str(tipo or "").strip()
    nome = str(nome or "").strip()
    if tipo and tipo.lower() != "none":
        partes.append(tipo)
    if nome and nome.lower() != "none":
        partes.append(nome)
    return " ".join(partes).strip()


@st.cache_data(show_spinner=False)
def carregar_base_geografica(caminho_base_enxuta: str) -> Optional[pd.DataFrame]:
    caminho_parquet = Path(caminho_base_enxuta)
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
            f"O arquivo {caminho_base_enxuta} não possui as colunas esperadas: {sorted(faltantes)}"
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
def obter_geocoder_arcgis(
    usar_externo: bool,
    timeout: int,
    delay_s: float,
    retries: int,
):
    if not usar_externo:
        return None

    arc = ArcGIS(timeout=timeout)
    return RateLimiter(
        arc.geocode,
        min_delay_seconds=delay_s,
        max_retries=retries,
        swallow_exceptions=True,
    )


def limpar_logradouro(texto: str) -> str:
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
    valor = str(numero or "").strip()
    if valor.lower() in ("nan", "none", "", "0", "0.0", "s/n", "sn"):
        return ""

    try:
        return str(int(float(valor)))
    except Exception:
        return re.sub(r"\D", "", valor)


def _hav(lat1, lon1, lat2, lon2):
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
    def __init__(self, config: FurtoVeiculoSipConfig):
        self.config = _normalizar_config(config)
        self.base = carregar_base_geografica(self.config.caminho_base_enxuta)
        self.municipios = carregar_municipios(
            self.config.uf_codigo,
            self.config.arq_cache_mun,
        )
        self.tree = None
        self.centroides_municipio = {}

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

        self.geocode_ext = obter_geocoder_arcgis(
            self.config.usar_externo,
            self.config.arcgis_timeout,
            self.config.arcgis_delay_s,
            self.config.arcgis_retries,
        )

    def cod_municipio(self, municipio: str) -> str:
        return self.municipios.get(sem_acento(municipio), "")

    def _idx_municipio(self, cod: str, ancora):
        if cod and self.tree is not None:
            indices = np.where(self.gcod == cod)[0]
            if len(indices):
                return indices

        if ancora is not None and self.tree is not None:
            indices = self.tree.query_ball_point(
                [ancora[0], ancora[1]],
                r=self.config.raio_municipio_km / 111.0,
            )
            return np.array(indices, dtype=int)

        return np.array([], dtype=int)

    def casar_rua(self, rua_norm: str, cod: str, ancora):
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

        if melhor_indice is not None and melhor_score >= self.config.limiar_nome:
            return (
                float(self.glat[melhor_indice]),
                float(self.glon[melhor_indice]),
                melhor_score,
            )

        return None

    def validar(self, lat: float, lon: float, rua_norm: str, cod: str, ancora):
        indices = self._idx_municipio(cod, ancora or (lat, lon))
        if not len(indices):
            return False, None

        nomes = self.gnome[indices]
        mascara = np.array(
            [
                fuzz.token_set_ratio(rua_norm, nome) >= self.config.limiar_nome
                for nome in nomes
            ]
        )
        if not mascara.any():
            return False, None

        indices_filtrados = indices[mascara]
        distancias = _hav(
            lat,
            lon,
            self.glat[indices_filtrados],
            self.glon[indices_filtrados],
        )
        melhor = float(distancias.min())
        return melhor <= self.config.raio_confirma_m, melhor

    def geocodificar(self, rua: str, numero: str, bairro: str, municipio: str):
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
            consulta = ", ".join([p for p in partes if p])

            externo = None
            if self.geocode_ext is not None:
                loc = self.geocode_ext(consulta, out_fields="*")
                if loc:
                    addr_type = (
                        ((loc.raw or {}).get("attributes", {}) or {}).get("Addr_type", "")
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

            consulta = ", ".join([p for p in partes if p])

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


def preparar_campos_geocodificacao(
    df: pd.DataFrame,
    col_endereco: str,
    col_numero: str,
    col_bairro: str,
    col_municipio: str,
) -> pd.DataFrame:
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
    config: FurtoVeiculoSipConfig,
) -> tuple[pd.DataFrame, int]:
    motor = MotorGeocodificacaoSoberana(config)

    lats = []
    lons = []
    niveis = []
    fontes = []
    confirmados = []
    distancias = []

    total = len(df)
    geocodificados = 0

    progresso = st.progress(0)
    status = st.empty()

    for indice, (_, linha) in enumerate(df.iterrows(), start=1):
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

        if resultado[0] is not None and resultado[1] is not None:
            geocodificados += 1

        progresso.progress(indice / max(total, 1))
        status.info(
            f"Geocodificando linhas novas... {indice}/{total} | "
            f"Geocodificados: {geocodificados}"
        )

    df = df.copy()
    df[col_lat_destino] = lats
    df[col_lon_destino] = lons
    df["Nivel_Geocodificacao"] = niveis
    df["Fonte"] = fontes
    df["_confirmado_base"] = confirmados
    df["_dist_validacao_m"] = distancias

    lat_series = pd.to_numeric(df[col_lat_destino], errors="coerce")
    lon_series = pd.to_numeric(df[col_lon_destino], errors="coerce")
    chave = lat_series.round(6).astype(str) + "," + lon_series.round(6).astype(str)
    contagem = chave.value_counts()
    df["Ocorrencias_Mesmo_Ponto"] = chave.map(contagem).fillna(1).astype(int)
    df["_loc_aproximada"] = (
        (df["Ocorrencias_Mesmo_Ponto"] >= motor.config.limiar_suspeito)
        & (df["numero_busca"].fillna("").astype(str).str.strip() == "")
    )

    status.success(f"Geocodificação concluída. Registros geocodificados: {geocodificados}")
    return df, geocodificados


def processar_furto_veiculo_sip(
    arquivo_01,
    arquivo_02,
    config: Optional[FurtoVeiculoSipConfig] = None,
):
    config = _normalizar_config(config)

    arquivo_01.seek(0)
    arquivo_02.seek(0)

    xls_base = pd.ExcelFile(arquivo_01)
    xls_novo = pd.ExcelFile(arquivo_02)

    abas_base = xls_base.sheet_names
    abas_novo = xls_novo.sheet_names

    aba_base = _selecionar_aba_arquivo_01(abas_base)
    aba_novo = _selecionar_aba_arquivo_02(abas_novo)

    df_base = pd.read_excel(xls_base, sheet_name=aba_base)
    df_novo = pd.read_excel(xls_novo, sheet_name=aba_novo)

    df_base = normalizar_colunas(df_base)
    df_novo = normalizar_colunas(df_novo)

    total_lido_arquivo_02 = len(df_novo)

    col_natureza = _obter_coluna_natureza(df_novo)
    if col_natureza is None:
        raise ValueError(
            "A aba 'Furto SIP' não possui coluna de Natureza identificável para filtrar 'Furto de Veículo'."
        )

    total_antes_filtro_tipo = len(df_novo)
    serie_natureza = df_novo[col_natureza].fillna("").astype(str)
    mascara_furto_veiculo = serie_natureza.apply(_eh_furto_veiculo)
    df_novo = df_novo.loc[mascara_furto_veiculo].copy()
    removidos_por_tipo = total_antes_filtro_tipo - len(df_novo)

    if df_novo.empty:
        raise ValueError(
            f"Após aplicar o filtro de Natureza na coluna '{col_natureza}', nenhum registro "
            f"de Furto de Veículo foi encontrado na aba '{aba_novo}'."
        )

    col_data_base = encontrar_coluna_data(df_base)
    col_hora_base = encontrar_coluna_hora(df_base)
    col_data_novo = encontrar_coluna_data(df_novo)
    col_datahora_novo = encontrar_coluna_por_nomes(
        df_novo,
        ["datahora", "data/hora", "data hora"],
        obrigatoria=False,
    )

    if col_data_novo and col_data_base and col_data_novo != col_data_base:
        df_novo = df_novo.rename(columns={col_data_novo: col_data_base})

    if col_datahora_novo is None:
        col_datahora_novo = col_data_base

    col_lat_base = encontrar_coluna_por_nomes(
        df_base,
        ["lat", "latitude"],
        obrigatoria=True,
    )
    col_lon_base = encontrar_coluna_por_nomes(
        df_base,
        ["lon", "long", "longitude"],
        obrigatoria=True,
    )

    col_endereco_base = encontrar_coluna_por_nomes(
        df_base,
        ["endereço", "endereco", "logradouro", "rua"],
        obrigatoria=True,
    )
    col_endereco_novo = encontrar_coluna_por_nomes(
        df_novo,
        ["logradouro", "endereço", "endereco", "rua"],
        obrigatoria=True,
    )

    if col_endereco_novo != col_endereco_base:
        df_novo = df_novo.rename(columns={col_endereco_novo: col_endereco_base})

    col_endereco = col_endereco_base

    col_numero = encontrar_coluna_por_nomes(
        df_novo,
        ["número", "numero", "localnumero", "num"],
        obrigatoria=True,
    )
    col_bairro = encontrar_coluna_por_nomes(df_novo, ["bairro"], obrigatoria=True)
    col_municipio = encontrar_coluna_por_nomes(
        df_novo,
        ["município", "municipio", "cidade"],
        obrigatoria=True,
    )

    col_ais_base = encontrar_coluna_por_nomes(
        df_base,
        ["AISNova", "AIS Nova", "AIS_NOVA", "AIS"],
        obrigatoria=False,
    )
    col_ais_novo = encontrar_coluna_por_nomes(
        df_novo,
        ["AISNova", "AIS Nova", "AIS_NOVA", "AIS"],
        obrigatoria=False,
    )
    if col_ais_base and col_ais_novo and col_ais_base != col_ais_novo:
        df_novo = df_novo.rename(columns={col_ais_novo: col_ais_base})

    col_regioes_base = encontrar_coluna_por_nomes(
        df_base,
        ["Regiões", "Regioes", "Região", "Regiao", "Território", "Territorio"],
        obrigatoria=False,
    )
    col_regioes_novo = encontrar_coluna_por_nomes(
        df_novo,
        ["Regiões", "Regioes", "Região", "Regiao", "Território", "Territorio"],
        obrigatoria=False,
    )
    if col_regioes_base and col_regioes_novo and col_regioes_base != col_regioes_novo:
        df_novo = df_novo.rename(columns={col_regioes_novo: col_regioes_base})

    col_complemento_base = encontrar_coluna_por_nomes(
        df_base,
        [
            "Complemento do Endereço",
            "Complemento do Endereco",
            "Complemento Endereço",
            "Complemento Endereco",
            "Complemento",
        ],
        obrigatoria=False,
    )
    col_complemento_novo = encontrar_coluna_por_nomes(
        df_novo,
        [
            "Complemento do Endereço",
            "Complemento do Endereco",
            "Complemento Endereço",
            "Complemento Endereco",
            "Complemento",
        ],
        obrigatoria=False,
    )
    if (
        col_complemento_base
        and col_complemento_novo
        and col_complemento_base != col_complemento_novo
    ):
        df_novo = df_novo.rename(columns={col_complemento_novo: col_complemento_base})

    df_novo = renomear_colunas_equivalentes(df_base, df_novo)

    df_base = criar_coluna_datahora(df_base, col_data_base, col_hora_base, "__datahora__")
    if col_hora_base in df_novo.columns:
        df_novo = criar_coluna_datahora(df_novo, col_data_base, col_hora_base, "__datahora__")
    else:
        df_novo["__datahora__"] = pd.to_datetime(
            df_novo[col_datahora_novo],
            errors="coerce",
            dayfirst=True,
        )

    ultima_datahora_base = obter_ultima_datahora(df_base, "__datahora__")

    total_antes_filtro = len(df_novo)
    df_novo_filtrado = filtrar_apenas_registros_posteriores(
        df_novo,
        "__datahora__",
        ultima_datahora_base,
    )
    removidos_por_datahora = total_antes_filtro - len(df_novo_filtrado)

    base_sem_aux = df_base.drop(columns=["__datahora__"]).copy()

    for coluna_extra in [
        "Nivel_Geocodificacao",
        "Fonte",
        "_confirmado_base",
        "_dist_validacao_m",
        "Ocorrencias_Mesmo_Ponto",
        "_loc_aproximada",
    ]:
        if coluna_extra not in base_sem_aux.columns:
            base_sem_aux[coluna_extra] = pd.NA

    if ultima_datahora_base is None:
        df_novo_util = df_novo.copy()
        situacao = (
            "Base anterior sem Data/Hora válida: registros do Arquivo 02, já filtrados para "
            "Furto de Veículo, foram incluídos integralmente."
        )
    elif df_novo_filtrado.empty:
        df_novo_util = df_novo_filtrado.copy()
        situacao = (
            "Nenhum registro novo de Furto de Veículo encontrado após a última Data/Hora "
            "da base: Arquivo 01 foi mantido sem acréscimos."
        )
    else:
        df_novo_util = df_novo_filtrado.copy()
        situacao = (
            "Base anterior localizada: somente registros de Furto de Veículo posteriores "
            "à última Data/Hora foram adicionados."
        )

    geocodificados = 0
    removidos_sem_geocodificacao = 0

    if not df_novo_util.empty:
        df_novo_util = preparar_campos_geocodificacao(
            df_novo_util,
            col_endereco,
            col_numero,
            col_bairro,
            col_municipio,
        )

        df_novo_util, geocodificados = geocodificar_linhas_novas(
            df_novo_util,
            col_lat_base,
            col_lon_base,
            config,
        )

        antes_exclusao_sem_geo = len(df_novo_util)
        df_novo_util = df_novo_util.dropna(subset=[col_lat_base, col_lon_base]).copy()
        removidos_sem_geocodificacao = antes_exclusao_sem_geo - len(df_novo_util)

        df_novo_util = df_novo_util.drop(
            columns=[
                "__datahora__",
                "logradouro_busca",
                "numero_busca",
                "bairro_busca",
                "municipio_busca",
            ],
            errors="ignore",
        )

        df_novo_util = alinhar_colunas_com_base(base_sem_aux, df_novo_util)
        df_final = pd.concat([base_sem_aux, df_novo_util], ignore_index=True)
        adicionados = len(df_novo_util)
    else:
        df_final = base_sem_aux.copy()
        adicionados = 0

    df_final = criar_coluna_datahora(df_final, col_data_base, col_hora_base, "__datahora__")
    df_final = df_final.sort_values(
        by="__datahora__",
        ascending=True,
        na_position="last",
    ).reset_index(drop=True)
    df_final = df_final.drop(columns=["__datahora__"], errors="ignore")

    # filtro por nível de geocodificação selecionado em config
    niveis_filtrar = config.niveis_filtrar or []
    if "Nivel_Geocodificacao" in df_final.columns and niveis_filtrar:
        df_final = df_final[
            df_final["Nivel_Geocodificacao"].isin(niveis_filtrar)
        ].reset_index(drop=True)

    contagens_nivel = {}
    if "Nivel_Geocodificacao" in df_final.columns:
        contagens_nivel = (
            df_final["Nivel_Geocodificacao"]
            .fillna("Nao Informado")
            .value_counts(dropna=False)
            .to_dict()
        )

    df_final = df_final.drop(
        columns=[
            "Fonte",
            "_confirmado_base",
            "_dist_validacao_m",
            "Ocorrencias_Mesmo_Ponto",
            "_loc_aproximada",
        ],
        errors="ignore",
    )

    total_final = len(df_final)
    ultima_ref = (
        ultima_datahora_base.strftime("%d/%m/%Y %H:%M:%S")
        if ultima_datahora_base is not None
        else "sem referencia anterior valida"
    )

    resumo = {
        "adicionados": adicionados,
        "total_final": total_final,
        "geocodificados": geocodificados,
        "removidos_por_tipo": removidos_por_tipo,
        "removidos_por_datahora": removidos_por_datahora,
        "removidos_sem_geocodificacao": removidos_sem_geocodificacao,
        "ultima_datahora_base": ultima_ref,
        "situacao": situacao,
        "aba_arquivo_01": aba_base,
        "aba_arquivo_02": aba_novo,
        "coluna_natureza": col_natureza,
        "contagens_nivel": contagens_nivel,
        "total_lido_arquivo_02": total_lido_arquivo_02,
        "coluna_endereco_base": col_endereco_base,
    }

    return df_final, resumo


def _init_state() -> None:
    defaults = {
        "furto_veiculo_sip_arquivo_01_bytes": None,
        "furto_veiculo_sip_arquivo_01_nome": None,
        "furto_veiculo_sip_arquivo_02_bytes": None,
        "furto_veiculo_sip_arquivo_02_nome": None,
        "furto_veiculo_sip_resultado_excel": None,
        "furto_veiculo_sip_resultado_df": None,
        "furto_veiculo_sip_resumo": None,
        "furto_veiculo_sip_config": None,
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def _limpar_estado_furto_veiculo_sip() -> None:
    chaves = [
        "furto_veiculo_sip_arquivo_01_bytes",
        "furto_veiculo_sip_arquivo_01_nome",
        "furto_veiculo_sip_arquivo_02_bytes",
        "furto_veiculo_sip_arquivo_02_nome",
        "furto_veiculo_sip_resultado_excel",
        "furto_veiculo_sip_resultado_df",
        "furto_veiculo_sip_resumo",
        "furto_veiculo_sip_config",
        "furto_veiculo_sip_upload_01",
        "furto_veiculo_sip_upload_02",
        "fvsip_cfg_usar_externo",
        "fvsip_cfg_base_parquet",
        "fvsip_cfg_cache_municipios",
        "fvsip_cfg_limiar_nome",
        "fvsip_cfg_raio_confirma",
        "fvsip_cfg_raio_municipio",
        "fvsip_cfg_limiar_suspeito",
        "fvsip_cfg_niveis_filtrar",
    ]
    for chave in chaves:
        if chave in st.session_state:
            del st.session_state[chave]


def _obter_configuracao_ui() -> FurtoVeiculoSipConfig:
    with st.expander("Configuração técnica", expanded=False):
        col_cfg1, col_cfg2 = st.columns(2, gap="large")

        with col_cfg1:
            _render_label_flutuante(
                "Usar ArcGIS como fallback",
                (
                    "Quando ativado, o sistema complementa a busca na base enxuta "
                    "com geocodificação externa ArcGIS para melhorar a cobertura."
                ),
            )
            usar_externo = st.toggle(
                "Usar ArcGIS como fallback",
                value=True,
                label_visibility="collapsed",
                key="fvsip_cfg_usar_externo",
            )

            _render_label_flutuante(
                "Base geográfica (.parquet)",
                (
                    "Arquivo parquet auxiliar com logradouros e coordenadas utilizado "
                    "como base principal de geocodificação local."
                ),
            )
            caminho_base_enxuta = st.text_input(
                "Base geográfica (.parquet)",
                value="CVP_SIP_GEOCODIFICAR.parquet",
                label_visibility="collapsed",
                key="fvsip_cfg_base_parquet",
            )

            _render_label_flutuante(
                "Arquivo cache de municípios",
                (
                    "Arquivo JSON local usado para armazenar o mapeamento IBGE "
                    "dos municípios e reduzir consultas repetidas."
                ),
            )
            arq_cache_mun = st.text_input(
                "Arquivo cache de municípios",
                value="municipios_ce.json",
                label_visibility="collapsed",
                key="fvsip_cfg_cache_municipios",
            )

        with col_cfg2:
            _render_label_flutuante(
                "Limiar de similaridade",
                (
                    "Percentual mínimo de similaridade entre o logradouro informado e "
                    "o logradouro da base para aceitar o casamento textual."
                ),
            )
            limiar_nome = st.slider(
                "Limiar de similaridade",
                min_value=70,
                max_value=100,
                value=88,
                label_visibility="collapsed",
                key="fvsip_cfg_limiar_nome",
            )

            _render_label_flutuante(
                "Raio de confirmação (m)",
                (
                    "Distância máxima, em metros, para validar se o ponto retornado "
                    "pelo ArcGIS é coerente com a base espacial local."
                ),
            )
            raio_confirma_m = st.number_input(
                "Raio de confirmação (m)",
                min_value=10.0,
                value=100.0,
                step=10.0,
                label_visibility="collapsed",
                key="fvsip_cfg_raio_confirma",
            )

            _render_label_flutuante(
                "Raio do município (km)",
                (
                    "Raio usado para restringir a busca espacial quando o município "
                    "não é localizado diretamente por código."
                ),
            )
            raio_municipio_km = st.number_input(
                "Raio do município (km)",
                min_value=1.0,
                value=8.0,
                step=1.0,
                label_visibility="collapsed",
                key="fvsip_cfg_raio_municipio",
            )

            _render_label_flutuante(
                "Limiar de ponto suspeito",
                (
                    "Quantidade mínima de ocorrências no mesmo ponto para marcar "
                    "localização aproximada em registros sem número."
                ),
            )
            limiar_suspeito = st.number_input(
                "Limiar de ponto suspeito",
                min_value=2,
                value=5,
                step=1,
                label_visibility="collapsed",
                key="fvsip_cfg_limiar_suspeito",
            )

        # seleção dos níveis de geocodificação para o arquivo final
        _render_label_flutuante(
            "Níveis de geocodificação a manter",
            (
                "Selecione quais níveis de geocodificação serão mantidos na base final "
                "de Furto de Veículo (SIP). Registros com níveis não selecionados serão descartados."
            ),
        )
        niveis_filtrar = st.multiselect(
            "Níveis de geocodificação",
            options=NIVEIS_GEOCODIFICACAO_POSSIVEIS,
            default=st.session_state.get(
                "fvsip_cfg_niveis_filtrar",
                ["Exato (Numero)", "Centroide de Rua"],
            ),
            key="fvsip_cfg_niveis_filtrar",
        )

    return _normalizar_config(
        FurtoVeiculoSipConfig(
            usar_externo=usar_externo,
            caminho_base_enxuta=caminho_base_enxuta.strip()
            or "CVP_SIP_GEOCODIFICAR.parquet",
            limiar_nome=int(limiar_nome),
            raio_confirma_m=float(raio_confirma_m),
            raio_municipio_km=float(raio_municipio_km),
            limiar_suspeito=int(limiar_suspeito),
            arq_cache_mun=arq_cache_mun.strip() or "municipios_ce.json",
            niveis_filtrar=list(niveis_filtrar or ["Exato (Numero)", "Centroide de Rua"]),
        )
    )


def render() -> None:
    _init_state()
    _aplicar_estilo_furto_veiculo_sip()

    st.markdown(
        """
        <div class="fvsip-card">
            <div class="fvsip-title">Processamento de Furto de Veículo (SIP)</div>
            <div class="fvsip-desc">
                Envie a base histórica e o complemento SIP para atualizar a base consolidada
                com geocodificação por endereço, filtro por natureza, validação temporal e
                padronização final no formato do QGP Online.
            </div>
            <ul class="fvsip-list">
                <li>Filtro automático dos registros compatíveis com Furto de Veículo.</li>
                <li>Geocodificação híbrida com ArcGIS e base parquet enxuta.</li>
                <li>Validação por similaridade de logradouro e contexto municipal.</li>
                <li>Classificação por nível de geocodificação.</li>
                <li>Geração do arquivo final consolidado para download.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    config = _obter_configuracao_ui()
    st.session_state.furto_veiculo_sip_config = config

    st.markdown(
        f"""
        <div class="fvsip-card">
            <div class="fvsip-title">Base geográfica de apoio</div>
            <div class="fvsip-desc">
                Arquivo esperado na raiz do projeto: <strong>{config.caminho_base_enxuta}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        base_geo = carregar_base_geografica(config.caminho_base_enxuta)
        if base_geo is not None and not base_geo.empty:
            st.markdown(
                f"""
                <div class="fvsip-card">
                    <div class="fvsip-title">Base geográfica disponível</div>
                    <div class="fvsip-desc">
                        A base auxiliar foi carregada com sucesso e está pronta para apoiar
                        a geocodificação dos novos registros.
                    </div>
                    <div class="fvsip-badges">
                        <span class="fvsip-badge ok">Arquivo: {config.caminho_base_enxuta}</span>
                        <span class="fvsip-badge info">Registros: {len(base_geo):,}</span>
                        <span class="fvsip-badge info">Fallback ArcGIS: {"Sim" if config.usar_externo else "Não"}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div class="fvsip-card">
                    <div class="fvsip-title">Base geográfica indisponível</div>
                    <div class="fvsip-desc">
                        A base auxiliar não foi carregada. Verifique se o arquivo está
                        presente e íntegro na raiz do projeto.
                    </div>
                    <div class="fvsip-badges">
                        <span class="fvsip-badge warn">Arquivo esperado: {config.caminho_base_enxuta}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    except Exception as exc:
        st.markdown(
            f"""
            <div class="fvsip-card">
                <div class="fvsip-title">Erro ao carregar base geográfica</div>
                <div class="fvsip-desc">
                    Ocorreu uma falha ao validar a base auxiliar do processo.
                </div>
                <div class="fvsip-badges">
                    <span class="fvsip-badge warn">{str(exc)}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    col1, col2 = st.columns(2)

    with col1:
        arquivo_01 = st.file_uploader(
            "📁 Arquivo 01 - Base histórica",
            type=["xlsx", "xls"],
            key="furto_veiculo_sip_upload_01",
        )

    with col2:
        arquivo_02 = st.file_uploader(
            "📁 Arquivo 02 - Complemento SIP",
            type=["xlsx", "xls"],
            key="furto_veiculo_sip_upload_02",
        )

    if arquivo_01 is not None:
        arquivo_01.seek(0)
        st.session_state.furto_veiculo_sip_arquivo_01_bytes = arquivo_01.read()
        st.session_state.furto_veiculo_sip_arquivo_01_nome = arquivo_01.name

    if arquivo_02 is not None:
        arquivo_02.seek(0)
        st.session_state.furto_veiculo_sip_arquivo_02_bytes = arquivo_02.read()
        st.session_state.furto_veiculo_sip_arquivo_02_nome = arquivo_02.name

    badges_upload = []
    if st.session_state.furto_veiculo_sip_arquivo_01_nome:
        badges_upload.append(
            f'<span class="fvsip-badge ok">Base carregada: {st.session_state.furto_veiculo_sip_arquivo_01_nome}</span>'
        )
    if st.session_state.furto_veiculo_sip_arquivo_02_nome:
        badges_upload.append(
            f'<span class="fvsip-badge ok">Complemento carregado: {st.session_state.furto_veiculo_sip_arquivo_02_nome}</span>'
        )

    if badges_upload:
        st.markdown(
            f'<div class="fvsip-badges">{"".join(badges_upload)}</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div class="fvsip-card">
            <div class="fvsip-title">Execução do processamento</div>
            <div class="fvsip-desc">
                Após validar os arquivos enviados, execute a rotina para filtrar,
                geocodificar, consolidar e gerar a base final pronta para exportação.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    pode_processar = (
        st.session_state.furto_veiculo_sip_arquivo_01_bytes is not None
        and st.session_state.furto_veiculo_sip_arquivo_02_bytes is not None
    )

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        processar = st.button(
            "Processar Furto de Veículo (SIP)",
            type="primary",
            disabled=not pode_processar,
            use_container_width=True,
            key="btn_processar_furto_veiculo_sip",
        )

    with col_btn2:
        limpar = st.button(
            "Limpar seleção",
            use_container_width=True,
            key="btn_limpar_furto_veiculo_sip",
        )

    if limpar:
        _limpar_estado_furto_veiculo_sip()
        st.rerun()

    if processar:
        try:
            arquivo_01_buffer = BytesIO(st.session_state.furto_veiculo_sip_arquivo_01_bytes)
            arquivo_02_buffer = BytesIO(st.session_state.furto_veiculo_sip_arquivo_02_bytes)

            with st.spinner("Processando e geocodificando registros..."):
                df_final, resumo = processar_furto_veiculo_sip(
                    arquivo_01_buffer,
                    arquivo_02_buffer,
                    config,
                )

            st.session_state.furto_veiculo_sip_resultado_df = df_final
            st.session_state.furto_veiculo_sip_resumo = resumo
            st.session_state.furto_veiculo_sip_resultado_excel = gerar_excel_em_memoria(df_final)

            st.success("Processamento concluído com sucesso.")
        except Exception as exc:
            st.error(f"Erro no processamento: {exc}")

    if st.session_state.furto_veiculo_sip_resumo:
        resumo = st.session_state.furto_veiculo_sip_resumo

        st.markdown(
            """
            <div class="fvsip-card">
                <div class="fvsip-title">Resumo do processamento</div>
                <div class="fvsip-desc">
                    Resultado consolidado da atualização, com foco em filtragem,
                    geocodificação e consistência temporal.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Adicionados", resumo.get("adicionados", 0))
        col2.metric("Total final", resumo.get("total_final", 0))
        col3.metric("Geocodificados", resumo.get("geocodificados", 0))
        col4.metric("Removidos por tipo", resumo.get("removidos_por_tipo", 0))

        st.info(resumo.get("situacao", ""))

        contagens_nivel = resumo.get("contagens_nivel", {})
        if contagens_nivel:
            st.markdown(
                """
                <div class="fvsip-card">
                    <div class="fvsip-title">Níveis de geocodificação</div>
                    <div class="fvsip-desc">
                        Distribuição dos registros conforme o nível de precisão obtido na geocodificação.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            exato_numero = contagens_nivel.get("Exato (Numero)", 0)
            centroide_rua = contagens_nivel.get("Centroide de Rua", 0)
            centroide_bairro = contagens_nivel.get("Centroide de Bairro", 0)
            centroide_cidade = contagens_nivel.get("Centroide de Cidade", 0)
            nao_encontrado = contagens_nivel.get("Nao Encontrado", 0)

            grid = st.columns(5)
            grid[0].metric("Exato (Número)", exato_numero)
            grid[1].metric("Centroide de Rua", centroide_rua)
            grid[2].metric("Centroide de Bairro", centroide_bairro)
            grid[3].metric("Centroide de Cidade", centroide_cidade)
            grid[4].metric("Não encontrado", nao_encontrado)

    if st.session_state.furto_veiculo_sip_resultado_df is not None:
        st.dataframe(
            st.session_state.furto_veiculo_sip_resultado_df,
            use_container_width=True,
            hide_index=True,
        )

    if st.session_state.furto_veiculo_sip_resultado_excel is not None:
        st.download_button(
            label="Baixar arquivo final",
            data=st.session_state.furto_veiculo_sip_resultado_excel,
            file_name=NOME_ARQUIVO_FINAL,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="furto_veiculo_sip_download_final",
            use_container_width=True,
        )


interface_furto_veiculo_sip = render

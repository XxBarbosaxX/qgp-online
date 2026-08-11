# -*- coding: utf-8 -*-
"""
GEOCODIFICADOR DIESP - VERSAO MODULAR PARA QGP ONLINE
====================================================

Motor de geocodificacao adaptado para uso no QGP Online com interface Streamlit.

Fluxo principal:
1. Upload de arquivo pelo usuario.
2. Deteccao ou selecao manual das colunas.
3. Execucao da geocodificacao com feedback visual.
4. Exibicao de metricas, preview e exportacao do resultado.
"""

from __future__ import annotations

import html
import io
import json
import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import ArcGIS
from rapidfuzz import fuzz
from scipy.spatial import cKDTree


logger = logging.getLogger(__name__)


# ============================================================================
# CONFIG
# ============================================================================

SESSION_TTL_MINUTOS = 30
BASES_DIR = os.path.abspath("bases")


@dataclass
class GeocodificadorConfig:
    usar_externo: bool = True
    caminho_gpkg: str = "bases/Faces_de_Quadra_-_Ceara_ARRUAMENTO.gpkg"
    caminho_base_enxuta: str = "bases/faces_quadras_ce.parquet"
    layer_gpkg: str = "reprojetado"
    epsg_gpkg: int = 31984

    limiar_nome: int = 88
    raio_confirma_m: float = 100.0
    raio_municipio_km: float = 8.0
    limiar_suspeito: int = 5

    uf_codigo: str = "23"
    arq_cache_mun: str = "bases/municipios_ce.json"
    arq_centroides_municipios: str = "bases/centroides_municipios_ce.parquet"

    arcgis_timeout: int = 15
    arcgis_delay_s: float = 0.4
    arcgis_retries: int = 2
    arcgis_location_type: str = "rooftop"
    arcgis_score_minimo_exato: float = 85.0
    raio_confirma_exato_m: float = 200.0
    permitir_exato_sem_confirmacao_local: bool = True

    coluna_lat_saida: str = "lat"
    coluna_lon_saida: str = "lon"
    coluna_nivel_saida: str = "Nivel_Geocodificacao"
    coluna_fonte_saida: str = "Fonte"
    coluna_confirmado_saida: str = "_confirmado_base"
    coluna_dist_saida: str = "_dist_validacao_m"
    coluna_mesmo_ponto_saida: str = "Ocorrencias_Mesmo_Ponto"
    coluna_aproximada_saida: str = "_loc_aproximada"
    coluna_motivo_saida: str = "Motivo_Geocodificacao"
    coluna_arcgis_tipo_saida: str = "ArcGIS_Addr_type"
    coluna_arcgis_score_saida: str = "ArcGIS_Score"


# ============================================================================
# TEXTO
# ============================================================================

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

RUIDO = ["LADO PAR", "LADO IMPAR", "- P", "FORTALEZA, CE", ", CE"]

RE_BNI = re.compile(r"\(?\s*bairro\s+n[aã]o\s+identificad[oa]\s*\)?", flags=re.IGNORECASE)

TIPOS = ("Rua", "Avenida", "Travessa", "Praca", "Rodovia", "Alameda", "Passeio")

ROOFTOP = ("pointaddress", "streetaddress", "subaddress", "pointaddressvd")


# ============================================================================
# UI / ESTILO
# ============================================================================

def _aplicar_estilo_geocodificacao() -> None:
    st.markdown(
        """
        <style>
            .geo-card {
                background: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 18px;
                padding: 1.1rem 1.1rem 0.85rem 1.1rem;
                margin: 1rem 0;
            }

            .geo-title {
                font-size: 1.15rem;
                font-weight: 800;
                color: #f8fafc;
                margin-bottom: 0.25rem;
            }

            .geo-desc {
                font-size: 0.93rem;
                color: rgba(255, 255, 255, 0.72);
                margin-bottom: 0.8rem;
                line-height: 1.55;
            }

            .geo-list {
                margin: 0.55rem 0 0 0;
                padding-left: 1rem;
                color: rgba(255, 255, 255, 0.78);
                font-size: 0.92rem;
            }

            .geo-grid {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.85rem;
                margin-top: 1rem;
            }

            .geo-stat {
                background: rgba(255, 255, 255, 0.025);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
                padding: 0.95rem 1rem;
            }

            .geo-stat-label {
                font-size: 0.78rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                color: rgba(255, 255, 255, 0.58);
                margin-bottom: 0.35rem;
                font-weight: 700;
            }

            .geo-stat-value {
                font-size: 1.18rem;
                font-weight: 900;
                color: #ffffff;
                line-height: 1.15;
            }

            .geo-badges {
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem;
                margin-top: 0.65rem;
            }

            .geo-badge {
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

            .geo-badge.ok {
                background: rgba(34, 197, 94, 0.10);
                color: #b7f7c9;
                border-color: rgba(34, 197, 94, 0.22);
            }

            .geo-badge.info {
                background: rgba(59, 130, 246, 0.10);
                color: #bfdbfe;
                border-color: rgba(59, 130, 246, 0.22);
            }

            .geo-badge.warn {
                background: rgba(245, 158, 11, 0.10);
                color: #fde4b0;
                border-color: rgba(245, 158, 11, 0.22);
            }

            .geo-field-label {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                margin-bottom: 0.45rem;
                margin-top: 0.2rem;
            }

            .geo-field-label-text {
                font-size: 0.92rem;
                font-weight: 700;
                color: rgba(255, 255, 255, 0.90);
                line-height: 1.2;
            }

            .geo-tooltip {
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

            .geo-tooltip-box {
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

            .geo-tooltip-box::before {
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

            .geo-tooltip:hover .geo-tooltip-box {
                opacity: 1;
                visibility: visible;
                transform: translateY(-50%) translateX(2px);
            }

            @media (max-width: 1200px) {
                .geo-grid {
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }

                .geo-tooltip-box {
                    left: auto;
                    right: 0;
                    top: calc(100% + 10px);
                    transform: none;
                    width: min(300px, 80vw);
                }

                .geo-tooltip-box::before {
                    left: auto;
                    right: 10px;
                    top: -6px;
                    transform: rotate(135deg);
                    border-left: 1px solid rgba(148, 163, 184, 0.28);
                    border-bottom: 1px solid rgba(148, 163, 184, 0.28);
                }

                .geo-tooltip:hover .geo-tooltip-box {
                    transform: translateY(2px);
                }
            }

            @media (max-width: 640px) {
                .geo-grid {
                    grid-template-columns: 1fr;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_label_flutuante(label: str, tooltip: str) -> None:
    label_html = html.escape(label)
    tooltip_html = html.escape(tooltip)
    st.markdown(
        f"""
        <div class="geo-field-label">
            <span class="geo-field-label-text">{label_html}</span>
            <span class="geo-tooltip">
                ?
                <span class="geo-tooltip-box">{tooltip_html}</span>
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================================
# HELPERS
# ============================================================================

def _touch_geo_session() -> None:
    st.session_state["geo_last_activity"] = datetime.now().isoformat()


def _is_subpath(path: str, base_dir: str) -> bool:
    path_abs = os.path.abspath(path)
    base_abs = os.path.abspath(base_dir)
    try:
        return os.path.commonpath([path_abs, base_abs]) == base_abs
    except ValueError:
        return False


def _validar_caminho_bases(path: str, extensoes_permitidas: tuple[str, ...]) -> str:
    caminho = (path or "").strip()
    if not caminho:
        raise ValueError("Caminho nao informado.")

    caminho_abs = os.path.abspath(caminho)
    ext = os.path.splitext(caminho_abs)[1].lower()

    if ext not in extensoes_permitidas:
        raise ValueError(f"Extensao nao permitida para o caminho informado: {ext}")

    if not _is_subpath(caminho_abs, BASES_DIR):
        raise ValueError("O caminho informado deve estar dentro da pasta 'bases/'.")

    return caminho_abs


def sem_acento(s: Any) -> str:
    n = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in n if not unicodedata.combining(c)).upper().strip()


def limpar_logradouro(texto: Any) -> str:
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

    return " ".join(" ".join(toks).split()).title()


def limpar_bairro(b: Any, municipio: Any) -> str:
    v = str(b or "").strip()
    if v.lower() in ("nan", "none", ""):
        return ""

    v = RE_BNI.sub("", v)
    v = re.sub(r"\(.*?\)", "", v)
    v = " ".join(v.strip(" ()-").split())

    if v == "" or sem_acento(v) == sem_acento(municipio):
        return ""

    return v


def limpar_numero(n: Any) -> str:
    s = str(n or "").strip()
    if s.lower() in ("nan", "none", "", "0", "0.0", "s/n", "sn"):
        return ""

    try:
        return str(int(float(s)))
    except Exception:
        return re.sub(r"\D", "", s)


def detectar(df: pd.DataFrame, candidatos) -> Optional[str]:
    mapa = {sem_acento(c).lower().replace(" ", ""): c for c in df.columns}

    for cand in candidatos:
        k = sem_acento(cand).lower().replace(" ", "")
        if k in mapa:
            return mapa[k]

    for cand in candidatos:
        k = sem_acento(cand).lower().replace(" ", "")
        for kk, original in mapa.items():
            if k in kk:
                return original

    return None


def _hav(lat1, lon1, lat2, lon2):
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
    )
    return 2 * 6371000.0 * np.arcsin(np.sqrt(a))


# ============================================================================
# SERVICO
# ============================================================================

class GeocodificadorDIESP:
    def __init__(self, config: Optional[GeocodificadorConfig] = None, logger=None):
        self.config = config or GeocodificadorConfig()
        self.logger = logger

        self.base = self._carregar_base()
        self.mun = self._carregar_municipios()

        self.tree = None
        self.cent_mun: Dict[str, Tuple[float, float]] = {}
        self.cent_mun_por_nome: Dict[str, Tuple[float, float]] = {}

        self.glat = None
        self.glon = None
        self.gnome = None
        self.gcod = None

        if self.base is not None and len(self.base):
            self.glat = self.base["lat"].values.astype(float)
            self.glon = self.base["lon"].values.astype(float)
            self.gnome = self.base["nome_norm"].astype(str).values
            self.gcod = self.base["cod_mun"].astype(str).values
            self.tree = cKDTree(np.c_[self.glat, self.glon])

            cm = self.base.groupby("cod_mun")[["lat", "lon"]].mean()
            self.cent_mun = {k: (v["lat"], v["lon"]) for k, v in cm.iterrows()}

        centroides_municipais = self._carregar_centroides_municipais()
        if centroides_municipais:
            self.cent_mun.update(centroides_municipais)

        self.cent_mun_por_nome = self._indexar_centroides_por_nome()

        self.geocode_ext = None
        if self.config.usar_externo:
            arc = ArcGIS(timeout=self.config.arcgis_timeout)
            self.geocode_ext = RateLimiter(
                arc.geocode,
                min_delay_seconds=self.config.arcgis_delay_s,
                max_retries=self.config.arcgis_retries,
                swallow_exceptions=True,
            )

    def _log(self, msg: str) -> None:
        logger.info(msg)
        if self.logger:
            try:
                self.logger(msg)
                return
            except Exception:
                logger.exception("Falha ao enviar log para callback da interface.")

    def _construir_base_enxuta(self, gpkg: str, parquet_saida: str) -> pd.DataFrame:
        import fiona
        from pyproj import Transformer
        from shapely.geometry import shape

        self._log("[BASE] Gerando base enxuta a partir do GPKG...")
        tr = Transformer.from_crs(
            f"EPSG:{self.config.epsg_gpkg}",
            "EPSG:4326",
            always_xy=True,
        )

        regs = []

        with fiona.open(gpkg, layer=self.config.layer_gpkg) as src:
            for f in src:
                p = f["properties"]

                tip = str(p.get("NM_TIP_LOG") or "").strip()
                tit = str(p.get("NM_TIT_LOG") or "").strip()
                log_nome = str(p.get("NM_LOG") or "").strip()
                nome = " ".join(x for x in (tip, tit, log_nome) if x and x.lower() != "none")
                if not nome:
                    continue

                try:
                    geom = shape(f["geometry"])
                    c = geom.centroid
                    lon, lat = tr.transform(c.x, c.y)
                except Exception:
                    continue

                cod = str(p.get("CD_SETOR") or "")[:7]

                try:
                    tot = int(p.get("TOT_GERAL") or 0)
                except Exception:
                    tot = 0

                nome_limpo = limpar_logradouro(nome)
                nome_norm = sem_acento(nome_limpo or nome)
                regs.append((cod, nome_norm, nome, lat, lon, tot))

        base = pd.DataFrame(
            regs,
            columns=["cod_mun", "nome_norm", "nome_orig", "lat", "lon", "tot_geral"],
        )

        pasta_saida = os.path.dirname(parquet_saida)
        if pasta_saida:
            os.makedirs(pasta_saida, exist_ok=True)

        base.to_parquet(parquet_saida, index=False)
        self._log(f"[BASE] Base enxuta gravada: {len(base)} faces -> {parquet_saida}")
        return base

    def _carregar_base(self) -> Optional[pd.DataFrame]:
        caminho_parquet = self.config.caminho_base_enxuta
        caminho_gpkg = self.config.caminho_gpkg

        if caminho_parquet and os.path.exists(caminho_parquet):
            ext = os.path.splitext(caminho_parquet)[1].lower()
            if ext != ".parquet":
                raise ValueError(
                    f"caminho_base_enxuta aponta para '{caminho_parquet}', "
                    "mas o geocodificador espera um arquivo .parquet."
                )

            try:
                base = pd.read_parquet(caminho_parquet)
                if "nome_orig" in base.columns:
                    base["nome_norm"] = base["nome_orig"].map(lambda x: sem_acento(limpar_logradouro(x) or x))
                elif "nome_norm" in base.columns:
                    base["nome_norm"] = base["nome_norm"].map(sem_acento)
                self._log(f"[BASE] Base enxuta carregada: {len(base)} faces.")
                return base.reset_index(drop=True)
            except Exception as e:
                raise RuntimeError(
                    f"Falha ao abrir a base enxuta '{caminho_parquet}'."
                ) from e

        if caminho_gpkg and os.path.exists(caminho_gpkg):
            return self._construir_base_enxuta(caminho_gpkg, caminho_parquet).reset_index(drop=True)

        self._log("[BASE] Base nao encontrada (nem parquet nem GPKG).")
        return None

    def _carregar_municipios(self) -> Dict[str, str]:
        arq_cache = self.config.arq_cache_mun

        if arq_cache and os.path.exists(arq_cache):
            try:
                with open(arq_cache, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                logger.exception("Falha ao abrir cache local de municipios.")

        url = (
            f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/"
            f"{self.config.uf_codigo}/municipios"
        )

        try:
            import gzip
            import urllib.request

            req = urllib.request.Request(url, headers={"Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=30) as r:
                dados = r.read()
                if r.info().get("Content-Encoding") == "gzip":
                    dados = gzip.decompress(dados)
                lista = json.loads(dados.decode("utf-8"))

            mapa = {sem_acento(m["nome"]): str(m["id"])[:7] for m in lista}

            if arq_cache:
                pasta_cache = os.path.dirname(arq_cache)
                if pasta_cache:
                    os.makedirs(pasta_cache, exist_ok=True)
                with open(arq_cache, "w", encoding="utf-8") as f:
                    json.dump(mapa, f, ensure_ascii=False)

            self._log(f"[MUN] Tabela de municipios carregada: {len(mapa)}.")
            return mapa

        except Exception:
            logger.exception("Nao foi possivel obter a tabela do IBGE.")
            self._log("[MUN] Nao foi possivel obter a tabela do IBGE.")
            return {}

    def _carregar_centroides_municipais(self) -> Dict[str, Tuple[float, float]]:
        caminho = (self.config.arq_centroides_municipios or "").strip()
        if not caminho:
            return {}

        if not os.path.exists(caminho):
            self._log(f"[MUN] Base de centroides municipais nao encontrada: {caminho}")
            return {}

        try:
            if caminho.lower().endswith(".parquet"):
                df = pd.read_parquet(caminho)
            elif caminho.lower().endswith(".csv"):
                df = pd.read_csv(caminho)
            elif caminho.lower().endswith((".xlsx", ".xls")):
                df = pd.read_excel(caminho)
            else:
                raise ValueError("Formato nao suportado para centroides municipais.")
        except Exception:
            logger.exception("Falha ao carregar base de centroides municipais.")
            self._log("[MUN] Falha ao carregar base de centroides municipais.")
            return {}

        col_cod = detectar(df, ["cod_mun", "codigo_municipio", "cod_ibge", "ibge", "id_municipio"])
        col_nome = detectar(df, ["municipio", "cidade", "nome_municipio", "nm_mun"])
        col_lat = detectar(df, ["lat", "latitude", "y"])
        col_lon = detectar(df, ["lon", "lng", "longitude", "x"])

        if not col_lat or not col_lon or (not col_cod and not col_nome):
            self._log(
                "[MUN] Base de centroides municipais ignorada: colunas obrigatorias nao identificadas."
            )
            return {}

        df = df.copy()
        df[col_lat] = pd.to_numeric(df[col_lat], errors="coerce")
        df[col_lon] = pd.to_numeric(df[col_lon], errors="coerce")
        df = df.dropna(subset=[col_lat, col_lon])

        centroides: Dict[str, Tuple[float, float]] = {}
        for _, row in df.iterrows():
            chave = ""
            if col_cod:
                chave = str(row.get(col_cod) or "").strip()
                chave = re.sub(r"\D", "", chave)[:7]

            if not chave and col_nome:
                nome = sem_acento(row.get(col_nome))
                chave = self.mun.get(nome, "")

            if not chave:
                continue

            centroides[chave] = (float(row[col_lat]), float(row[col_lon]))

        self._log(f"[MUN] Centroides municipais carregados: {len(centroides)}.")
        return centroides

    def _indexar_centroides_por_nome(self) -> Dict[str, Tuple[float, float]]:
        indice: Dict[str, Tuple[float, float]] = {}
        for nome_norm, cod in self.mun.items():
            centro = self.cent_mun.get(str(cod))
            if centro:
                indice[nome_norm] = centro
        return indice

    def obter_centroide_municipio(self, municipio: Any, cod: str = "") -> Optional[Tuple[float, float]]:
        cod_limpo = str(cod or "").strip()
        if cod_limpo:
            centro = self.cent_mun.get(cod_limpo)
            if centro:
                return centro

        nome_norm = sem_acento(municipio)
        if nome_norm:
            centro = self.cent_mun_por_nome.get(nome_norm)
            if centro:
                return centro

            cod_por_nome = self.mun.get(nome_norm, "")
            if cod_por_nome:
                centro = self.cent_mun.get(cod_por_nome)
                if centro:
                    return centro

        return None

    def cod_municipio(self, municipio: Any) -> str:
        return self.mun.get(sem_acento(municipio), "")

    def _idx_municipio(self, cod: str, ancora: Optional[Tuple[float, float]]):
        if cod and self.tree is not None:
            ix = np.where(self.gcod == cod)[0]
            if len(ix):
                return ix

        if ancora is not None and self.tree is not None:
            ix = self.tree.query_ball_point(
                [ancora[0], ancora[1]],
                r=self.config.raio_municipio_km / 111.0,
            )
            return np.array(ix, dtype=int)

        return np.array([], dtype=int)

    def _score_logradouro(self, consulta: str, candidato: str) -> int:
        consulta_n = sem_acento(limpar_logradouro(consulta) or consulta)
        candidato_n = sem_acento(limpar_logradouro(candidato) or candidato)

        if not consulta_n or not candidato_n:
            return 0

        score_set = fuzz.token_set_ratio(consulta_n, candidato_n)
        score_sort = fuzz.token_sort_ratio(consulta_n, candidato_n)
        score_partial = fuzz.partial_ratio(consulta_n, candidato_n)
        return int(max(score_set, score_sort, score_partial))

    def casar_rua(self, rua_norm: str, cod: str, ancora: Optional[Tuple[float, float]]):
        ix = self._idx_municipio(cod, ancora)
        if not len(ix):
            return None

        melhor, mscore = None, 0
        for j in ix:
            s = self._score_logradouro(rua_norm, self.gnome[j])
            if s > mscore:
                mscore, melhor = s, j

        if melhor is not None and mscore >= self.config.limiar_nome:
            return float(self.glat[melhor]), float(self.glon[melhor]), mscore

        return None

    def validar(
        self,
        lat: float,
        lon: float,
        rua_norm: str,
        cod: str,
        ancora: Optional[Tuple[float, float]],
    ):
        ix = self._idx_municipio(cod, ancora or (lat, lon))
        if not len(ix):
            return False, None

        nomes = self.gnome[ix]
        scores = np.array([self._score_logradouro(rua_norm, n) for n in nomes])
        msk = scores >= self.config.limiar_nome
        if not msk.any():
            return False, None

        mi = ix[msk]
        d = _hav(lat, lon, self.glat[mi], self.glon[mi])
        best = float(d.min())
        return best <= self.config.raio_confirma_m, best

    def geocodificar(
        self,
        rua: Any,
        num: Any,
        bairro: Any,
        municipio: Any,
    ) -> Tuple[Any, Any, str, str, bool, Optional[float], str, Optional[str], Optional[float]]:
        rua_l = limpar_logradouro(rua)
        bai_l = limpar_bairro(bairro, municipio)
        rua_n = sem_acento(rua_l)
        cod = self.cod_municipio(municipio)
        num_l = limpar_numero(num)

        if not rua_l:
            if bai_l and self.geocode_ext is not None:
                consulta_bairro = ", ".join(
                    p for p in [bai_l, str(municipio).strip(), "Ceara", "Brasil"] if p
                )
                loc_bairro = self.geocode_ext(consulta_bairro, out_fields="*")
                if loc_bairro:
                    at_bairro = str((((loc_bairro.raw or {}).get("attributes", {}) or {}).get("Addr_type", ""))).lower()
                    score_bairro_raw = (((loc_bairro.raw or {}).get("attributes", {}) or {}).get("Score"))
                    try:
                        score_bairro = float(score_bairro_raw) if score_bairro_raw is not None else None
                    except Exception:
                        score_bairro = None
                    if at_bairro in ("neighborhood", "district", "locality"):
                        return (
                            float(loc_bairro.latitude),
                            float(loc_bairro.longitude),
                            "Centroide de Bairro",
                            "ArcGIS (bairro)",
                            False,
                            None,
                            "Sem logradouro; fallback por bairro aplicado.",
                            at_bairro,
                            score_bairro,
                        )

            c = self.obter_centroide_municipio(municipio, cod) if hasattr(self, "obter_centroide_municipio") else self.cent_mun.get(cod)
            if c:
                return (
                    c[0],
                    c[1],
                    "Centroide de Cidade",
                    "Centroide Municipio",
                    False,
                    None,
                    "Sem logradouro; fallback por municipio aplicado.",
                    None,
                    None,
                )
            return (None, None, "Nao Encontrado", "-", False, None, "Sem logradouro e sem centroide municipal disponivel.", None, None)

        partes = [f"{rua_l}, {num_l}" if num_l else rua_l]
        if bai_l:
            partes.append(bai_l)
        partes += [str(municipio).strip(), "Ceara", "Brasil"]
        consulta = ", ".join(p for p in partes if p)

        ext = None
        if self.geocode_ext is not None:
            try:
                loc = self.geocode_ext(
                    consulta,
                    out_fields="*",
                    location_type=self.config.arcgis_location_type,
                )
            except TypeError:
                loc = self.geocode_ext(consulta, out_fields="*")

            if loc:
                attrs = ((loc.raw or {}).get("attributes", {}) or {})
                at = str(attrs.get("Addr_type", "")).lower()
                score_raw = attrs.get("Score")
                try:
                    score = float(score_raw) if score_raw is not None else None
                except Exception:
                    score = None

                disp_x = attrs.get("DisplayX")
                disp_y = attrs.get("DisplayY")
                try:
                    disp_lon = float(disp_x) if disp_x is not None else None
                    disp_lat = float(disp_y) if disp_y is not None else None
                except Exception:
                    disp_lon = None
                    disp_lat = None

                lat_valid = disp_lat if disp_lat is not None else float(loc.latitude)
                lon_valid = disp_lon if disp_lon is not None else float(loc.longitude)

                ext = {
                    "lat": float(loc.latitude),
                    "lon": float(loc.longitude),
                    "lat_valid": lat_valid,
                    "lon_valid": lon_valid,
                    "addr_type": at,
                    "score": score,
                    "tem_display": disp_lat is not None and disp_lon is not None,
                }

        ancora = (ext["lat_valid"], ext["lon_valid"]) if ext else None

        if ext and ext["addr_type"] in ROOFTOP and num_l:
            ok, dist = self.validar(ext["lat_valid"], ext["lon_valid"], rua_n, cod, ancora)
            score_ok = ext["score"] is None or ext["score"] >= self.config.arcgis_score_minimo_exato
            if ok and score_ok:
                origem = "ArcGIS+GPKG"
                detalhe = "com DisplayX/DisplayY" if ext["tem_display"] else "com coordenada principal do ArcGIS"
                return (
                    ext["lat_valid"],
                    ext["lon_valid"],
                    "Exato (Numero)",
                    origem,
                    True,
                    dist,
                    f"Endereco validado com numero, addr_type preciso e proximidade espacial confirmada {detalhe}.",
                    ext["addr_type"],
                    ext["score"],
                )
            if score_ok and self.config.permitir_exato_sem_confirmacao_local:
                return (
                    ext["lat_valid"],
                    ext["lon_valid"],
                    "Exato (Numero)",
                    "ArcGIS (sem confirmacao local)",
                    False,
                    dist,
                    "Endereco preciso no ArcGIS com score suficiente, mas sem confirmacao local pela base de faces/centroides.",
                    ext["addr_type"],
                    ext["score"],
                )
            if not ok:
                motivo = "ArcGIS retornou endereco preciso, mas a validacao espacial com a base local falhou."
            else:
                motivo = f"ArcGIS retornou endereco preciso, mas score abaixo do minimo configurado ({self.config.arcgis_score_minimo_exato})."
        elif num_l and self.geocode_ext is None:
            motivo = "Numero informado, mas ArcGIS esta desabilitado; nao ha como classificar como Exato (Numero)."
        elif num_l and ext is None:
            motivo = "Numero informado, mas ArcGIS nao retornou candidato para o endereco completo."
        elif num_l and ext and ext["addr_type"] not in ROOFTOP:
            motivo = f"ArcGIS retornou candidato com addr_type '{ext['addr_type']}', insuficiente para Exato (Numero)."
        else:
            motivo = "Numero ausente; fluxo segue para centroide de rua/bairro/municipio."

        g = self.casar_rua(rua_n, cod, ancora)
        if g:
            motivo_rua = motivo if num_l else "Logradouro encontrado na base local; classificado por centroide de rua."
            return (
                g[0],
                g[1],
                "Centroide de Rua",
                "GPKG (Faces de Quadra)",
                True,
                0.0,
                motivo_rua,
                ext["addr_type"] if ext else None,
                ext["score"] if ext else None,
            )

        if ext:
            addr_type = ext["addr_type"]
            if addr_type in ("streetname", "streetmidblock", "streetint", "streetaddress"):
                nivel = "Centroide de Rua"
            elif addr_type in ("locality", "neighborhood", "district") and bai_l:
                nivel = "Centroide de Bairro"
            else:
                nivel = "Centroide de Cidade"
            return (
                ext["lat_valid"],
                ext["lon_valid"],
                nivel,
                "ArcGIS (nao confirmado)",
                False,
                None,
                motivo,
                ext["addr_type"],
                ext["score"],
            )

        c = self.obter_centroide_municipio(municipio, cod) if hasattr(self, "obter_centroide_municipio") else self.cent_mun.get(cod)
        if c:
            return (
                c[0],
                c[1],
                "Centroide de Cidade",
                "Centroide Municipio",
                False,
                None,
                motivo,
                None,
                None,
            )

        return (None, None, "Nao Encontrado", "-", False, None, motivo, None, None)

    def diagnosticar_coordenadas(


        self,
        df: pd.DataFrame,
        lat_col: Optional[str] = None,
        lon_col: Optional[str] = None,
    ) -> pd.DataFrame:
        lat_col = lat_col or self.config.coluna_lat_saida
        lon_col = lon_col or self.config.coluna_lon_saida

        df[self.config.coluna_mesmo_ponto_saida] = 1
        df[self.config.coluna_aproximada_saida] = False

        val = df[[lat_col, lon_col]].dropna()
        if val.empty:
            return df

        chave = df[lat_col].round(6).astype(str) + "," + df[lon_col].round(6).astype(str)
        cont = chave.value_counts()

        df[self.config.coluna_mesmo_ponto_saida] = chave.map(cont).fillna(1).astype(int)

        suspeita = df[self.config.coluna_mesmo_ponto_saida] >= self.config.limiar_suspeito
        sem_num = df.get("_tem_numero", pd.Series([False] * len(df), index=df.index)) == False
        df[self.config.coluna_aproximada_saida] = suspeita & sem_num

        return df

    def geocodificar_dataframe(
        self,
        df: pd.DataFrame,
        coluna_logradouro: Optional[str] = None,
        coluna_numero: Optional[str] = None,
        coluna_bairro: Optional[str] = None,
        coluna_municipio: Optional[str] = None,
    ) -> pd.DataFrame:
        if df is None or df.empty:
            return df.copy()

        df = df.copy()

        c_log = coluna_logradouro or detectar(df, ["logradouro", "endereco", "rua"])
        c_num = coluna_numero or detectar(df, ["localNumero", "numero", "num"])
        c_bai = coluna_bairro or detectar(df, ["bairro"])
        c_mun = coluna_municipio or detectar(df, ["municipio", "cidade"])

        if not c_log or not c_mun:
            raise RuntimeError(
                "DataFrame sem coluna de logradouro/municipio. "
                f"Detectado: logradouro={c_log}, municipio={c_mun}"
            )

        lats, lons, nivel, fonte, conf, dists, temnum = [], [], [], [], [], [], []
        motivos, arcgis_tipos, arcgis_scores = [], [], []
        total = len(df)

        self._log(
            f"[COLUNAS] logradouro={c_log} numero={c_num} bairro={c_bai} municipio={c_mun}"
        )

        for i, row in df.iterrows():
            num = limpar_numero(row.get(c_num)) if c_num else ""

            r = self.geocodificar(
                row.get(c_log),
                num,
                row.get(c_bai) if c_bai else "",
                row.get(c_mun),
            )

            lats.append(r[0])
            lons.append(r[1])
            nivel.append(r[2])
            fonte.append(r[3])
            conf.append(r[4])
            dists.append(r[5])
            temnum.append(bool(num))
            motivos.append(r[6])
            arcgis_tipos.append(r[7])
            arcgis_scores.append(r[8])

            if (i + 1) % 25 == 0 or (i + 1) == total:
                self._log(f"[GEO] {i + 1}/{total}")

        df[self.config.coluna_lat_saida] = lats
        df[self.config.coluna_lon_saida] = lons
        df[self.config.coluna_nivel_saida] = nivel
        df[self.config.coluna_fonte_saida] = fonte
        df[self.config.coluna_confirmado_saida] = conf
        df[self.config.coluna_dist_saida] = dists
        df["_tem_numero"] = temnum
        df[self.config.coluna_motivo_saida] = motivos
        df[self.config.coluna_arcgis_tipo_saida] = arcgis_tipos
        df[self.config.coluna_arcgis_score_saida] = arcgis_scores

        df = self.diagnosticar_coordenadas(df)
        df = df.drop(columns=["_tem_numero"], errors="ignore")

        return df

    def resumir_resultado(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df is None or df.empty:
            return {
                "total": 0,
                "geocodificadas": 0,
                "perc_geocodificadas": 0.0,
                "exato_numero": 0,
                "nao_encontrado": 0,
            }

        col_nivel = self.config.coluna_nivel_saida
        total = len(df)
        enc = (df[col_nivel] != "Nao Encontrado").sum()
        num = (df[col_nivel] == "Exato (Numero)").sum()
        nao = (df[col_nivel] == "Nao Encontrado").sum()

        return {
            "total": int(total),
            "geocodificadas": int(enc),
            "perc_geocodificadas": round((enc / total) * 100, 2) if total else 0.0,
            "exato_numero": int(num),
            "nao_encontrado": int(nao),
        }

    def geocodificar_excel(
        self,
        caminho_entrada: str,
        caminho_saida: Optional[str] = None,
        **kwargs,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        if not caminho_entrada or not os.path.exists(caminho_entrada):
            raise FileNotFoundError(f"Arquivo nao encontrado: {caminho_entrada}")

        ext = os.path.splitext(caminho_entrada)[1].lower()
        if ext in [".xlsx", ".xls"]:
            df = pd.read_excel(caminho_entrada)
        elif ext == ".parquet":
            df = pd.read_parquet(caminho_entrada)
        elif ext == ".csv":
            df = pd.read_csv(caminho_entrada)
        else:
            raise ValueError(f"Formato nao suportado: {ext}")

        self._log(f"[ARQUIVO] Lido: {caminho_entrada} ({len(df)} linhas)")

        df_saida = self.geocodificar_dataframe(df, **kwargs)
        resumo = self.resumir_resultado(df_saida)

        if caminho_saida:
            pasta_saida = os.path.dirname(caminho_saida)
            if pasta_saida:
                os.makedirs(pasta_saida, exist_ok=True)

            ext_saida = os.path.splitext(caminho_saida)[1].lower()
            if ext_saida == ".xlsx":
                df_saida.to_excel(caminho_saida, index=False)
            elif ext_saida == ".parquet":
                df_saida.to_parquet(caminho_saida, index=False)
            elif ext_saida == ".csv":
                df_saida.to_csv(caminho_saida, index=False, encoding="utf-8-sig")
            else:
                raise ValueError(f"Formato de saida nao suportado: {ext_saida}")

            self._log(f"[ARQUIVO] Salvo: {caminho_saida}")

        return df_saida, resumo


# ============================================================================
# FUNCOES DE CONVENIENCIA
# ============================================================================

def geocodificar_ocorrencias(
    df: pd.DataFrame,
    config: Optional[GeocodificadorConfig] = None,
    logger=None,
    **kwargs,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    servico = GeocodificadorDIESP(config=config, logger=logger)
    df_saida = servico.geocodificar_dataframe(df, **kwargs)
    resumo = servico.resumir_resultado(df_saida)
    return df_saida, resumo


def geocodificar_arquivo_ocorrencias(
    caminho_entrada: str,
    caminho_saida: Optional[str] = None,
    config: Optional[GeocodificadorConfig] = None,
    logger=None,
    **kwargs,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    servico = GeocodificadorDIESP(config=config, logger=logger)
    return servico.geocodificar_excel(
        caminho_entrada=caminho_entrada,
        caminho_saida=caminho_saida,
        **kwargs,
    )


# ============================================================================
# UI STREAMLIT
# ============================================================================

def _ler_arquivo_upload(uploaded_file) -> pd.DataFrame:
    nome = uploaded_file.name.lower()

    if nome.endswith(".csv"):
        return pd.read_csv(uploaded_file)

    if nome.endswith(".xlsx") or nome.endswith(".xls"):
        return pd.read_excel(uploaded_file)

    if nome.endswith(".parquet"):
        return pd.read_parquet(uploaded_file)

    raise ValueError("Formato nao suportado. Envie CSV, XLSX, XLS ou Parquet.")


def _df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def _df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="geocodificacao")
    buffer.seek(0)
    return buffer.read()


def _expirar_estado_geocodificacao() -> None:
    ultimo = st.session_state.get("geo_last_activity")
    if not ultimo:
        _touch_geo_session()
        return

    try:
        dt_ultimo = datetime.fromisoformat(ultimo)
    except Exception:
        _touch_geo_session()
        return

    if datetime.now() - dt_ultimo > timedelta(minutes=SESSION_TTL_MINUTOS):
        _limpar_estado_geocodificacao()
        _touch_geo_session()


def _init_state_geocodificacao() -> None:
    defaults = {
        "geo_df_entrada": None,
        "geo_nome_upload": None,
        "geo_df_saida": None,
        "geo_resumo": None,
        "geo_nome_arquivo": None,
        "geo_logs": [],
        "geo_last_activity": datetime.now().isoformat(),
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def _limpar_estado_geocodificacao() -> None:
    chaves = [
        "geo_df_entrada",
        "geo_nome_upload",
        "geo_df_saida",
        "geo_resumo",
        "geo_nome_arquivo",
        "geo_logs",
        "geo_upload_arquivo",
        "geo_last_activity",
    ]
    for chave in chaves:
        if chave in st.session_state:
            del st.session_state[chave]


def interface_geocodificar() -> None:
    _init_state_geocodificacao()
    _expirar_estado_geocodificacao()
    _touch_geo_session()
    _aplicar_estilo_geocodificacao()

    st.markdown(
        """
        <div class="geo-card">
            <div class="geo-title">Geocodificação de ocorrências</div>
            <div class="geo-desc">
                Execute o processo de geocodificação de bases de ocorrências com apoio da base oficial,
                validação espacial, classificação por nível de precisão e fallback externo quando habilitado.
            </div>
            <ul class="geo-list">
                <li>Leitura de arquivos CSV, XLSX, XLS e Parquet.</li>
                <li>Detecção automática ou seleção manual das colunas principais.</li>
                <li>Geocodificação com base espacial local e ArcGIS como apoio.</li>
                <li>Diagnóstico de pontos repetidos e localização aproximada.</li>
                <li>Exportação final em CSV e Excel.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Configuração técnica", expanded=False):
        col_c1, col_c2 = st.columns(2, gap="large")

        with col_c1:
            _render_label_flutuante(
                "Usar ArcGIS como fallback",
                (
                    "Quando marcado, o sistema tenta geocodificar primeiro usando a base "
                    "oficial (faces de quadra / arruamento) e, se não encontrar ou tiver "
                    "baixa similaridade, faz uma busca complementar via serviço ArcGIS."
                ),
            )
            usar_externo = st.toggle(
                "Usar ArcGIS como fallback",
                value=True,
                label_visibility="collapsed",
            )

            _render_label_flutuante(
                "Caminho do GPKG",
                "Informe o caminho do arquivo GPKG contendo a base oficial de arruamento/faces de quadra utilizada na validação espacial.",
            )
            caminho_gpkg = st.text_input(
                "Caminho do GPKG",
                value="bases/Faces_de_Quadra_-_Ceara_ARRUAMENTO.gpkg",
                label_visibility="collapsed",
            )

            _render_label_flutuante(
                "Caminho da base enxuta (.parquet)",
                "Arquivo parquet otimizado com a base já preparada para acelerar a carga e a geocodificação.",
            )
            caminho_base_enxuta = st.text_input(
                "Caminho da base enxuta (.parquet)",
                value="bases/faces_quadras_ce.parquet",
                label_visibility="collapsed",
            )

            _render_label_flutuante(
                "Caminho dos centroides municipais",
                "Base opcional com centroides por municipio para cobrir registros sem logradouro e reforcar o fallback de centroide de cidade.",
            )
            caminho_centroides_municipios = st.text_input(
                "Caminho dos centroides municipais",
                value="bases/centroides_municipios_ce.parquet",
                label_visibility="collapsed",
            )

        with col_c2:
            _render_label_flutuante(
                "Limiar de similaridade",
                (
                    "É o valor (no seu caso 88, em uma escala de 70 a 100) que define "
                    "o quão parecido o texto do logradouro da ocorrência precisa ser com "
                    "o logradouro da base oficial para ser considerado match válido."
                ),
            )
            limiar_nome = st.slider(
                "Limiar de similaridade",
                70,
                100,
                88,
                label_visibility="collapsed",
            )

            _render_label_flutuante(
                "Raio de confirmação (m)",
                (
                    "É a distância em metros usada para confirmar se o ponto proposto "
                    "está próximo da face de quadra ou da referência espacial esperada."
                ),
            )
            raio_confirma_m = st.number_input(
                "Raio de confirmação (m)",
                min_value=10.0,
                value=200.0,
                step=10.0,
                label_visibility="collapsed",
            )

            _render_label_flutuante(
                "Raio do município (km)",
                (
                    "Define um raio máximo (em quilômetros) em torno do centro/limite de "
                    "um município para validar se o ponto geocodificado faz sentido espacialmente."
                ),
            )
            raio_municipio_km = st.number_input(
                "Raio do município (km)",
                min_value=1.0,
                value=8.0,
                step=1.0,
                label_visibility="collapsed",
            )

    uploaded_file = st.file_uploader(
        "Enviar arquivo de ocorrências",
        type=["csv", "xlsx", "xls", "parquet"],
        help="Formatos suportados: CSV, Excel e Parquet.",
        key="geo_upload_arquivo",
    )

    if uploaded_file is not None:
        try:
            df = _ler_arquivo_upload(uploaded_file)
            st.session_state["geo_df_entrada"] = df
            st.session_state["geo_nome_upload"] = uploaded_file.name
            _touch_geo_session()
        except Exception:
            logger.exception("Falha ao ler o arquivo enviado para geocodificacao.")
            st.error(
                "Nao foi possivel ler o arquivo enviado. "
                "Verifique o formato e tente novamente."
            )
            return

    df = st.session_state.get("geo_df_entrada")
    nome_upload = st.session_state.get("geo_nome_upload")

    if df is None:
        st.info("Envie um arquivo para iniciar a geocodificação.")
        return

    nome_upload_seguro = html.escape(str(nome_upload or "arquivo"))

    st.markdown(
        f"""
        <div class="geo-badges">
            <span class="geo-badge ok">Arquivo carregado: {nome_upload_seguro}</span>
            <span class="geo-badge info">Registros: {len(df):,}</span>
            <span class="geo-badge info">Colunas: {len(df.columns)}</span>
            <span class="geo-badge info">Formato: {html.escape(nome_upload.split('.')[-1].upper())}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="geo-card">
            <div class="geo-title">Pré-validação da base</div>
            <div class="geo-desc">
                Revise o layout dos dados antes do processamento e confirme o mapeamento
                das colunas utilizadas pelo geocodificador.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Pré-visualização da base carregada", expanded=False):
        st.dataframe(df.head(50), use_container_width=True, hide_index=True)

    colunas = list(df.columns)
    c_log_auto = detectar(df, ["logradouro", "endereco", "rua"])
    c_num_auto = detectar(df, ["localNumero", "numero", "num"])
    c_bai_auto = detectar(df, ["bairro"])
    c_mun_auto = detectar(df, ["municipio", "cidade"])

    st.markdown(
        """
        <div class="geo-card">
            <div class="geo-title">Mapeamento de colunas</div>
            <div class="geo-desc">
                Ajuste manualmente os campos caso a detecção automática não corresponda ao layout da planilha.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_f1, col_f2, col_f3, col_f4 = st.columns(4, gap="large")

    with col_f1:
        coluna_logradouro = st.selectbox(
            "Logradouro",
            options=colunas,
            index=colunas.index(c_log_auto) if c_log_auto in colunas else 0,
        )

    with col_f2:
        coluna_numero = st.selectbox(
            "Número",
            options=[""] + colunas,
            index=([""] + colunas).index(c_num_auto) if c_num_auto in colunas else 0,
        )

    with col_f3:
        coluna_bairro = st.selectbox(
            "Bairro",
            options=[""] + colunas,
            index=([""] + colunas).index(c_bai_auto) if c_bai_auto in colunas else 0,
        )

    with col_f4:
        coluna_municipio = st.selectbox(
            "Município",
            options=colunas,
            index=colunas.index(c_mun_auto) if c_mun_auto in colunas else 0,
        )

    st.markdown(
        """
        <div class="geo-card">
            <div class="geo-title">Execução do processamento</div>
            <div class="geo-desc">
                Inicie a geocodificação para gerar latitude, longitude, nível de geocodificação
                e metadados auxiliares da base processada.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        processar = st.button(
            "Iniciar geocodificação",
            use_container_width=True,
            type="primary",
            key="geo_processar",
        )

    with col_btn2:
        limpar = st.button(
            "Limpar seleção",
            use_container_width=True,
            key="geo_limpar",
        )

    if limpar:
        _limpar_estado_geocodificacao()
        st.rerun()

    if processar:
        logs = []

        def logger_ui(msg: str) -> None:
            logs.append(msg)

        try:
            caminho_gpkg_validado = _validar_caminho_bases(caminho_gpkg, (".gpkg",))
            caminho_base_enxuta_validado = _validar_caminho_bases(
                caminho_base_enxuta, (".parquet",)
            )
            caminho_centroides_municipios_validado = _validar_caminho_bases(
                caminho_centroides_municipios, (".parquet", ".csv", ".xlsx", ".xls")
            )

            config = GeocodificadorConfig(
                usar_externo=usar_externo,
                caminho_gpkg=caminho_gpkg_validado,
                caminho_base_enxuta=caminho_base_enxuta_validado,
                arq_centroides_municipios=caminho_centroides_municipios_validado,
                limiar_nome=limiar_nome,
                raio_confirma_m=raio_confirma_m,
                raio_municipio_km=raio_municipio_km,
            )

            with st.status("Processando geocodificação...", expanded=True) as status:
                status.write("Inicializando serviço...")
                geo = GeocodificadorDIESP(config=config, logger=logger_ui)

                status.write("Executando geocodificação da base...")
                df_saida = geo.geocodificar_dataframe(
                    df,
                    coluna_logradouro=coluna_logradouro,
                    coluna_numero=coluna_numero or None,
                    coluna_bairro=coluna_bairro or None,
                    coluna_municipio=coluna_municipio,
                )

                status.write("Consolidando resumo executivo...")
                resumo = geo.resumir_resultado(df_saida)

                for item in logs[-10:]:
                    status.write(item)

                status.update(
                    label="Geocodificação concluída com sucesso.",
                    state="complete",
                )

            st.session_state["geo_df_saida"] = df_saida
            st.session_state["geo_resumo"] = resumo
            st.session_state["geo_nome_arquivo"] = os.path.splitext(nome_upload)[0]
            st.session_state["geo_logs"] = logs
            _touch_geo_session()

            st.success("✅ Processamento concluído.")

        except ValueError:
            logger.exception("Falha de validacao de parametros no modulo de geocodificacao.")
            st.error(
                "Configuracao invalida. Revise os caminhos informados na pasta bases/ "
                "e tente novamente."
            )
            return
        except Exception:
            logger.exception("Erro ao executar geocodificacao.")
            st.error(
                "Ocorreu um erro interno durante a geocodificação. "
                "Tente novamente ou contate o administrador."
            )
            return

    if "geo_df_saida" not in st.session_state or st.session_state["geo_df_saida"] is None:
        return

    df_saida = st.session_state["geo_df_saida"]
    resumo = st.session_state["geo_resumo"]
    nome_arquivo = st.session_state.get("geo_nome_arquivo", "resultado_geocodificacao")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    st.markdown(
        f"""
        <div class="geo-card">
            <div class="geo-title">Resumo executivo</div>
            <div class="geo-desc">
                Resultado consolidado da geocodificação executada sobre a base enviada.
            </div>
            <div class="geo-grid">
                <div class="geo-stat">
                    <div class="geo-stat-label">Total</div>
                    <div class="geo-stat-value">{resumo['total']:,}</div>
                </div>
                <div class="geo-stat">
                    <div class="geo-stat-label">Geocodificadas</div>
                    <div class="geo-stat-value">{resumo['geocodificadas']:,}</div>
                </div>
                <div class="geo-stat">
                    <div class="geo-stat-label">Taxa de sucesso</div>
                    <div class="geo-stat-value">{resumo['perc_geocodificadas']}%</div>
                </div>
                <div class="geo-stat">
                    <div class="geo-stat-label">Não encontrado</div>
                    <div class="geo-stat-value">{resumo['nao_encontrado']:,}</div>
                </div>
            </div>
            <div class="geo-badges">
                <span class="geo-badge ok">Exato (Número): {resumo['exato_numero']:,}</span>
                <span class="geo-badge info">Arquivo base: {html.escape(nome_upload or '')}</span>
                <span class="geo-badge warn">Campos gerados: lat, lon, nível, fonte e diagnóstico</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Resultado processado", expanded=False):
        st.dataframe(df_saida, use_container_width=True, hide_index=True)

    col_d1, col_d2 = st.columns(2, gap="large")

    with col_d1:
        st.download_button(
            label="Baixar resultado em CSV",
            data=_df_to_csv_bytes(df_saida),
            file_name=f"{nome_arquivo}_geocodificado_{timestamp}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with col_d2:
        st.download_button(
            label="Baixar resultado em Excel",
            data=_df_to_excel_bytes(df_saida),
            file_name=f"{nome_arquivo}_geocodificado_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

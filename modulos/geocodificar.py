# -*- coding: utf-8 -*-
"""
GEOCODIFICADOR DIESP - VERSAO MODULAR PARA QGP ONLINE
====================================================
Adaptado para uso interno no sistema, sem interface interativa local/Colab.

ESCADA:
  1. ArcGIS (numero da porta) - so se confirmado pela base (<=100 m da face de
     mesmo nome). So roda com usar_externo=True.
  2. Base GPKG/parquet (nivel rua) - soberano, casamento por similaridade.
  3. ArcGIS nivel rua/bairro - cobre rua ausente da base (nao confirmado).
  4. Centroide do municipio - quando nem a base tem a rua.

USO PRINCIPAL:
    config = GeocodificadorConfig(
        caminho_gpkg="bases/Faces_de_Quadra_-_Ceara_ARRUAMENTO.gpkg",
        caminho_base_enxuta="bases/faces_quadras_ce.parquet",
    )
    geo = GeocodificadorDIESP(config)
    df_saida = geo.geocodificar_dataframe(df)

OPCIONAL:
    df_saida, resumo = geocodificar_ocorrencias(df, config=config)
"""

from __future__ import annotations

import os
import re
import json
import unicodedata
from dataclasses import dataclass
from typing import Optional, Dict, Tuple, Any

import numpy as np
import pandas as pd
from rapidfuzz import fuzz
from scipy.spatial import cKDTree
from geopy.geocoders import ArcGIS
from geopy.extra.rate_limiter import RateLimiter


# ============================================================================
# CONFIG
# ============================================================================

@dataclass
class GeocodificadorConfig:
    usar_externo: bool = True
    caminho_gpkg: str = "Faces_de_Quadra_-_Ceara_ARRUAMENTO.gpkg"
    caminho_base_enxuta: str = "ROUBO DE VEICULO GEOCODIFICAR.parquet"
    layer_gpkg: str = "reprojetado"
    epsg_gpkg: int = 31984

    limiar_nome: int = 88
    raio_confirma_m: float = 100.0
    raio_municipio_km: float = 8.0
    limiar_suspeito: int = 5

    uf_codigo: str = "23"
    arq_cache_mun: str = "municipios_ce.json"

    arcgis_timeout: int = 15
    arcgis_delay_s: float = 0.4
    arcgis_retries: int = 2

    coluna_lat_saida: str = "lat"
    coluna_lon_saida: str = "lon"
    coluna_nivel_saida: str = "Nivel_Geocodificacao"
    coluna_fonte_saida: str = "Fonte"
    coluna_confirmado_saida: str = "_confirmado_base"
    coluna_dist_saida: str = "_dist_validacao_m"
    coluna_mesmo_ponto_saida: str = "Ocorrencias_Mesmo_Ponto"
    coluna_aproximada_saida: str = "_loc_aproximada"


# ============================================================================
# TEXTO
# ============================================================================

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

        self.geocode_ext = None
        if self.config.usar_externo:
            arc = ArcGIS(timeout=self.config.arcgis_timeout)
            self.geocode_ext = RateLimiter(
                arc.geocode,
                min_delay_seconds=self.config.arcgis_delay_s,
                max_retries=self.config.arcgis_retries,
                swallow_exceptions=True
            )

    def _log(self, msg: str):
        if self.logger:
            try:
                self.logger(msg)
                return
            except Exception:
                pass

    # ========================================================================
    # BASE OFICIAL
    # ========================================================================

    def _construir_base_enxuta(self, gpkg: str, parquet_saida: str) -> pd.DataFrame:
        import fiona
        from shapely.geometry import shape
        from pyproj import Transformer

        self._log("[BASE] Gerando base enxuta a partir do GPKG...")
        tr = Transformer.from_crs(
            f"EPSG:{self.config.epsg_gpkg}",
            "EPSG:4326",
            always_xy=True
        )

        regs = []

        with fiona.open(gpkg, layer=self.config.layer_gpkg) as src:
            for f in src:
                p = f["properties"]

                tip = str(p.get("NM_TIP_LOG") or "").strip()
                tit = str(p.get("NM_TIT_LOG") or "").strip()
                log = str(p.get("NM_LOG") or "").strip()
                nome = " ".join(x for x in (tip, tit, log) if x and x.lower() != "none")
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

                regs.append((cod, sem_acento(nome), nome, lat, lon, tot))

        base = pd.DataFrame(
            regs,
            columns=["cod_mun", "nome_norm", "nome_orig", "lat", "lon", "tot_geral"]
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
                self._log(f"[BASE] Base enxuta carregada: {len(base)} faces.")
                return base.reset_index(drop=True)
            except Exception as e:
                raise RuntimeError(
                    f"Falha ao abrir a base enxuta '{caminho_parquet}'. "
                    f"Erro original: {e}"
                ) from e

        if caminho_gpkg and os.path.exists(caminho_gpkg):
            return self._construir_base_enxuta(caminho_gpkg, caminho_parquet).reset_index(drop=True)

        self._log(
            "[BASE] Base nao encontrada (nem parquet nem GPKG). "
            "Motor soberano indisponivel."
        )
        return None

    # ========================================================================
    # MUNICIPIOS
    # ========================================================================

    def _carregar_municipios(self) -> Dict[str, str]:
        arq_cache = self.config.arq_cache_mun

        if arq_cache and os.path.exists(arq_cache):
            try:
                with open(arq_cache, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        url = (
            f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/"
            f"{self.config.uf_codigo}/municipios"
        )

        try:
            import urllib.request
            import gzip

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

        except Exception as e:
            self._log(
                f"[MUN] Nao foi possivel obter a tabela do IBGE ({e}). "
                "Ancoragem pela base/ponto externo quando possivel."
            )
            return {}

    # ========================================================================
    # MOTOR
    # ========================================================================

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
                r=self.config.raio_municipio_km / 111.0
            )
            return np.array(ix, dtype=int)

        return np.array([], dtype=int)

    def casar_rua(self, rua_norm: str, cod: str, ancora: Optional[Tuple[float, float]]):
        ix = self._idx_municipio(cod, ancora)
        if not len(ix):
            return None

        melhor, mscore = None, 0
        for j in ix:
            s = fuzz.token_set_ratio(rua_norm, self.gnome[j])
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
        ancora: Optional[Tuple[float, float]]
    ):
        ix = self._idx_municipio(cod, ancora or (lat, lon))
        if not len(ix):
            return False, None

        nomes = self.gnome[ix]
        msk = np.array([
            fuzz.token_set_ratio(rua_norm, n) >= self.config.limiar_nome for n in nomes
        ])
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
        municipio: Any
    ) -> Tuple[Any, Any, str, str, bool, Optional[float]]:
        rua_l = limpar_logradouro(rua)
        bai_l = limpar_bairro(bairro, municipio)
        rua_n = sem_acento(rua_l)
        cod = self.cod_municipio(municipio)
        num_l = limpar_numero(num)

        if not rua_l:
            c = self.cent_mun.get(cod)
            if c:
                return (c[0], c[1], "Centroide de Cidade", "Centroide Municipio", False, None)
            return (None, None, "Nao Encontrado", "-", False, None)

        partes = [f"{rua_l}, {num_l}" if num_l else rua_l]
        if bai_l:
            partes.append(bai_l)
        partes += [str(municipio).strip(), "Ceara", "Brasil"]
        consulta = ", ".join(p for p in partes if p)

        ext = None
        if self.geocode_ext is not None:
            loc = self.geocode_ext(consulta, out_fields="*")
            if loc:
                at = ((loc.raw or {}).get("attributes", {}) or {}).get("Addr_type", "")
                ext = (float(loc.latitude), float(loc.longitude), str(at).lower())

        ancora = (ext[0], ext[1]) if ext else None

        if ext and ext[2] in ROOFTOP and num_l:
            ok, dist = self.validar(ext[0], ext[1], rua_n, cod, ancora)
            if ok:
                return (ext[0], ext[1], "Exato (Numero)", "ArcGIS+GPKG", True, dist)

        g = self.casar_rua(rua_n, cod, ancora)
        if g:
            return (g[0], g[1], "Centroide de Rua", "GPKG (Faces de Quadra)", True, 0.0)

        if ext:
            if ext[2] in ("streetname", "streetmidblock", "streetint") or num_l:
                nivel = "Centroide de Rua"
            elif ext[2] in ("locality", "neighborhood", "district"):
                nivel = "Centroide de Bairro"
            else:
                nivel = "Centroide de Cidade"
            return (ext[0], ext[1], nivel, "ArcGIS (nao confirmado)", False, None)

        c = self.cent_mun.get(cod)
        if c:
            return (c[0], c[1], "Centroide de Cidade", "Centroide Municipio", False, None)

        return (None, None, "Nao Encontrado", "-", False, None)

    # ========================================================================
    # POS-PROCESSAMENTO
    # ========================================================================

    def diagnosticar_coordenadas(
        self,
        df: pd.DataFrame,
        lat_col: Optional[str] = None,
        lon_col: Optional[str] = None
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

    # ========================================================================
    # PLANILHA / DATAFRAME
    # ========================================================================

    def geocodificar_dataframe(
        self,
        df: pd.DataFrame,
        coluna_logradouro: Optional[str] = None,
        coluna_numero: Optional[str] = None,
        coluna_bairro: Optional[str] = None,
        coluna_municipio: Optional[str] = None
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
                row.get(c_mun)
            )

            lats.append(r[0])
            lons.append(r[1])
            nivel.append(r[2])
            fonte.append(r[3])
            conf.append(r[4])
            dists.append(r[5])
            temnum.append(bool(num))

            if (i + 1) % 25 == 0 or (i + 1) == total:
                self._log(f"[GEO] {i + 1}/{total}")

        df[self.config.coluna_lat_saida] = lats
        df[self.config.coluna_lon_saida] = lons
        df[self.config.coluna_nivel_saida] = nivel
        df[self.config.coluna_fonte_saida] = fonte
        df[self.config.coluna_confirmado_saida] = conf
        df[self.config.coluna_dist_saida] = dists
        df["_tem_numero"] = temnum

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
                "nao_encontrado": 0
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
        **kwargs
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
    **kwargs
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
    **kwargs
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    servico = GeocodificadorDIESP(config=config, logger=logger)
    return servico.geocodificar_excel(
        caminho_entrada=caminho_entrada,
        caminho_saida=caminho_saida,
        **kwargs
    )

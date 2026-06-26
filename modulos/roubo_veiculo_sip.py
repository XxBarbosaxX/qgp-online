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
        "Endereço": ["Endereço", "Endereco", "endereço", "endereco"],
        "AIS": ["AISNova", "AIS Nova", "AIS_NOVA", "aisnova", "ais_nova"],
        "Território": [
            "Regiões", "Regioes", "Região", "Regiao",
            "território", "territorio", "regiões", "regioes"
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
    return " ".join(" ".join(toks).split()).title()


def limpar_bairro(b, municipio):
    v = str(b or "").strip()
    if v.lower() in ("nan", "none", ""):
        return ""
    v = RE_BNI.sub("", v)
    v = re.sub(r"\(.*?\)", "", v)
    v = " ".join(v.strip(" ()-").split())
    if v == "" or sem_acento(v) == sem_acento(municipio):
        return ""
    return v


def limpar_numero(n):
    s = str(n or "").strip()
    if s.lower() in ("nan", "none", "", "0", "0.0", "s/n", "sn"):
        return ""
    try:
        return str(int(float(s)))
    except Exception:
        return re.sub(r"\D", "", s)


def localizar_parquet_geocodificacao() -> Path:
    candidatos = [
        BASE_DIR / "CVP_SIP_GEOCODIFICAR.parquet",
        BASE_DIR / "modulos" / "CVP_SIP_GEOCODIFICAR.parquet",
        Path(__file__).resolve().parent / "CVP_SIP_GEOCODIFICAR.parquet",
        Path("CVP_SIP_GEOCODIFICAR.parquet"),
        Path("modulos") / "CVP_SIP_GEOCODIFICAR.parquet",
    ]

    for caminho in candidatos:
        if caminho.exists():
            return caminho

    raise FileNotFoundError(
        "Base parquet nao encontrada. Caminhos testados: "
        + " | ".join(str(c) for c in candidatos)
    )


def normalizar_colunas_base_geografica(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    col_lat = encontrar_coluna_por_nomes(
        df,
        ["lat", "latitude", "y", "latitud"],
        obrigatoria=True,
    )
    col_lon = encontrar_coluna_por_nomes(
        df,
        ["lon", "long", "longitude", "x", "longitud"],
        obrigatoria=True,
    )
    col_nome = encontrar_coluna_por_nomes(
        df,
        ["nome_norm", "logradouro_norm", "nome", "logradouro", "rua"],
        obrigatoria=True,
    )
    col_cod = encontrar_coluna_por_nomes(
        df,
        ["cod_mun", "codigo_municipio", "municipio_cod", "cod municipio", "ibge"],
        obrigatoria=True,
    )

    ren = {
        col_lat: "lat",
        col_lon: "lon",
        col_nome: "nome_norm",
        col_cod: "cod_mun",
    }

    if "nome_orig" not in df.columns:
        col_nome_orig = encontrar_coluna_por_nomes(
            df,
            ["nome_orig", "nome original", "logradouro_orig", "logradouro original", "nome", "logradouro", "rua"],
            obrigatoria=False,
        )
        if col_nome_orig:
            ren[col_nome_orig] = "nome_orig"

    if "tot_geral" not in df.columns:
        col_tot = encontrar_coluna_por_nomes(
            df,
            ["tot_geral", "total", "qtd", "quantidade"],
            obrigatoria=False,
        )
        if col_tot:
            ren[col_tot] = "tot_geral"

    df = df.rename(columns=ren)

    colunas_minimas = ["lat", "lon", "nome_norm", "cod_mun"]
    faltantes = [c for c in colunas_minimas if c not in df.columns]
    if faltantes:
        raise ValueError(
            f"A base parquet foi carregada, mas nao possui as colunas minimas esperadas apos normalizacao: {faltantes}. "
            f"Colunas encontradas: {list(df.columns)}"
        )

    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df["nome_norm"] = df["nome_norm"].astype(str).fillna("").map(sem_acento)
    df["cod_mun"] = df["cod_mun"].astype(str).str[:7]

    if "nome_orig" not in df.columns:
        df["nome_orig"] = df["nome_norm"]

    if "tot_geral" not in df.columns:
        df["tot_geral"] = 0

    df = df.dropna(subset=["lat", "lon"]).copy()
    return df.reset_index(drop=True)


def carregar_base_geografica():
    caminho = localizar_parquet_geocodificacao()
    df = pd.read_parquet(caminho).reset_index(drop=True)
    df = normalizar_colunas_base_geografica(df)
    return df, caminho


def carregar_municipios():
    caminho_cache = Path(ARQ_CACHE_MUN)

    if caminho_cache.exists():
        try:
            with open(caminho_cache, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{UF_CODIGO}/municipios"
    try:
        req = urllib.request.Request(url, headers={"Accept-Encoding": "gzip"})
        with urllib.request.urlopen(req, timeout=30) as r:
            dados = r.read()
            if r.info().get("Content-Encoding") == "gzip":
                dados = gzip.decompress(dados)
            lista = json.loads(dados.decode("utf-8"))

        mapa = {sem_acento(m["nome"]): str(m["id"])[:7] for m in lista}

        with open(caminho_cache, "w", encoding="utf-8") as f:
            json.dump(mapa, f, ensure_ascii=False)

        return mapa
    except Exception:
        return {}


def _hav(lat1, lon1, lat2, lon2):
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
    return 2 * 6371000.0 * np.arcsin(np.sqrt(a))


class MotorGeocodificacaoSoberana:
    def __init__(self):
        self.base, self.caminho_base = carregar_base_geografica()
        self.mun = carregar_municipios()
        self.tree = None
        self.cent_mun = {}

        if self.base is not None and len(self.base):
            self.glat = self.base["lat"].astype(float).values
            self.glon = self.base["lon"].astype(float).values
            self.gnome = self.base["nome_norm"].astype(str).values
            self.gcod = self.base["cod_mun"].astype(str).values
            self.tree = cKDTree(np.c_[self.glat, self.glon])

            cm = self.base.groupby("cod_mun")[["lat", "lon"]].mean(numeric_only=True)
            self.cent_mun = {k: (v["lat"], v["lon"]) for k, v in cm.iterrows()}

        self.geocode_ext = None
        if USAR_EXTERNO:
            arc = ArcGIS(timeout=15)
            self.geocode_ext = RateLimiter(
                arc.geocode,
                min_delay_seconds=0.4,
                max_retries=2,
                swallow_exceptions=True
            )

    def cod_municipio(self, municipio):
        return self.mun.get(sem_acento(municipio), "")

    def _idx_municipio(self, cod, ancora):
        if cod and self.tree is not None:
            ix = np.where(self.gcod == cod)[0]
            if len(ix):
                return ix
        if ancora is not None and self.tree is not None:
            ix = self.tree.query_ball_point([ancora[0], ancora[1]], r=RAIO_MUNICIPIO_KM / 111.0)
            return np.array(ix, dtype=int)
        return np.array([], dtype=int)

    def casar_rua(self, rua_norm, cod, ancora):
        ix = self._idx_municipio(cod, ancora)
        if not len(ix):
            return None
        melhor, mscore = None, 0
        for j in ix:
            s = fuzz.token_set_ratio(rua_norm, self.gnome[j])
            if s > mscore:
                mscore, melhor = s, j
        if melhor is not None and mscore >= LIMIAR_NOME:
            return float(self.glat[melhor]), float(self.glon[melhor]), mscore
        return None

    def validar(self, lat, lon, rua_norm, cod, ancora):
        ix = self._idx_municipio(cod, ancora or (lat, lon))
        if not len(ix):
            return False, None
        nomes = self.gnome[ix]
        msk = np.array([fuzz.token_set_ratio(rua_norm, n) >= LIMIAR_NOME for n in nomes])
        if not msk.any():
            return False, None
        mi = ix[msk]
        d = _hav(lat, lon, self.glat[mi], self.glon[mi])
        best = float(d.min())
        return best <= RAIO_CONFIRMA_M, best

    def geocodificar(self, rua, num, bairro, municipio):
        rua_l = limpar_logradouro(rua)
        bai_l = limpar_bairro(bairro, municipio)
        rua_n = sem_acento(rua_l)
        cod = self.cod_municipio(municipio)

        if not rua_l:
            c = self.cent_mun.get(cod)
            if c:
                return (c[0], c[1], "Centroide de Cidade", "Centroide Municipio", False, None)
            return (None, None, "Nao Encontrado", "-", False, None)

        partes = [f"{rua_l}, {num}" if num else rua_l]
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

        if ext and ext[2] in ROOFTOP and num:
            ok, dist = self.validar(ext[0], ext[1], rua_n, cod, ancora)
            if ok:
                return (ext[0], ext[1], "Exato (Numero)", "ArcGIS+Parquet", True, dist)

        g = self.casar_rua(rua_n, cod, ancora)
        if g:
            return (g[0], g[1], "Centroide de Rua", "Parquet (CVP SIP)", True, 0.0)

        if ext:
            if ext[2] in ("streetname", "streetmidblock", "streetint") or num:
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


def preparar_campos_geocodificacao(df, col_endereco, col_numero, col_bairro, col_municipio):
    df = df.copy()
    df["logradouro_busca"] = df[col_endereco].apply(limpar_logradouro)
    df["numero_busca"] = df[col_numero].apply(limpar_numero)
    df["bairro_busca"] = df.apply(lambda r: limpar_bairro(r[col_bairro], r[col_municipio]), axis=1)
    df["municipio_busca"] = df[col_municipio].fillna("").astype(str).str.strip()
    return df


def geocodificar_linhas_novas(df, col_lat_destino, col_lon_destino):
    motor = MotorGeocodificacaoSoberana()

    lats, lons, niveis, fontes, confirmados, distancias = [], [], [], [], [], []
    geocodificados = 0
    total = len(df)
    barra = st.progress(0)
    status = st.empty()

    for i, (_, row) in enumerate(df.iterrows(), start=1):
        num = limpar_numero(row.get("numero_busca", ""))
        r = motor.geocodificar(
            row.get("logradouro_busca", ""),
            num,
            row.get("bairro_busca", ""),
            row.get("municipio_busca", "")
        )
        lats.append(r[0])
        lons.append(r[1])
        niveis.append(r[2])
        fontes.append(r[3])
        confirmados.append(r[4])
        distancias.append(r[5])

        if r[0] is not None and r[1] is not None:
            geocodificados += 1

        barra.progress(int(i / max(total, 1) * 100))
        status.info(f"Geocodificando linhas novas... {i}/{total}")

    df = df.copy()
    df[col_lat_destino] = lats
    df[col_lon_destino] = lons
    df["Nivel_Geocodificacao"] = niveis
    df["Fonte"] = fontes
    df["_confirmado_base"] = confirmados
    df["_dist_validacao_m"] = distancias

    chave = df[col_lat_destino].round(6).astype(str) + "," + df[col_lon_destino].round(6).astype(str)
    cont = chave.value_counts()
    df["Ocorrencias_Mesmo_Ponto"] = chave.map(cont).fillna(1).astype(int)
    df["_loc_aproximada"] = (
        (df["Ocorrencias_Mesmo_Ponto"] >= LIMIAR_SUSPEITO)
        & (df["numero_busca"].fillna("").astype(str).str.strip() == "")
    )

    return df, geocodificados, str(motor.caminho_base)


def colunas_existentes(df: pd.DataFrame, colunas_desejadas: list[str]) -> list[str]:
    cols = []
    vistos = set()
    for c in colunas_desejadas:
        if c in df.columns and c not in vistos:
            cols.append(c)
            vistos.add(c)
    return cols


def mostrar_amostra_segura(titulo: str, df: pd.DataFrame, colunas_desejadas: list[str], n: int = 10):
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

    st.dataframe(df_preview.head(n), use_container_width=True)


def gerar_excel_em_memoria(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="CVP_SIP_ENDERECO")
    buffer.seek(0)
    return buffer.getvalue()


def processar_roubo_veiculo_sip(arquivo_01, arquivo_02):
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
        ["Data", "Hora", "Endereço", "Bairro", "Município", "Latitude", "Longitude"],
        5,
    )
    mostrar_amostra_segura(
        "Pré-visualização Arquivo 02 (aba CVPSIP):",
        df_novo,
        ["Data", "Natureza", "Endereço", "Número", "Bairro", "Município", "Regiões", "AISNova"],
        5,
    )
    progresso.progress(30)

    total_lido_arquivo_02 = len(df_novo)
    status.info("Filtrando apenas Natureza = ROUBO DE VEICULO...")
    df_novo, col_natureza = filtrar_por_natureza(df_novo, VALOR_FILTRO_NATUREZA)
    removidos_por_tipo = total_lido_arquivo_02 - len(df_novo)

    mostrar_amostra_segura(
        "Arquivo 02 após filtro por Natureza:",
        df_novo,
        ["Data", col_natureza, "Endereço", "Número", "Bairro", "Município", "Regiões", "AISNova"],
        10,
    )

    if df_base.empty:
        raise ValueError("O Arquivo 01 foi carregado, mas esta sem registros.")
    if df_novo.empty:
        raise ValueError("Apos filtrar a coluna 'Natureza' por 'ROUBO DE VEICULO', o Arquivo 02 ficou sem registros.")

    col_data_base = encontrar_coluna_data_base(df_base)
    col_hora_base = encontrar_coluna_hora_base(df_base)
    col_datahora_novo = encontrar_coluna_datahora_arquivo_02(df_novo)

    col_lat_base = encontrar_coluna_por_nomes(df_base, ["lat", "latitude"], obrigatoria=True)
    col_lon_base = encontrar_coluna_por_nomes(df_base, ["lon", "long", "longitude"], obrigatoria=True)

    df_novo = renomear_colunas_equivalentes(df_base, df_novo)

    col_endereco = encontrar_coluna_por_nomes(df_novo, ["endereço", "endereco", "logradouro", "rua"], obrigatoria=True)
    col_numero = encontrar_coluna_por_nomes(df_novo, ["número", "numero", "localNumero", "num"], obrigatoria=True)
    col_bairro = encontrar_coluna_por_nomes(df_novo, ["bairro"], obrigatoria=True)
    col_municipio = encontrar_coluna_por_nomes(df_novo, ["município", "municipio", "cidade"], obrigatoria=True)

    df_base = criar_datahora_base(df_base, col_data_base, col_hora_base)
    df_novo = criar_datahora_arquivo_02(df_novo, col_datahora_novo)

    ultimo_datahora_base = obter_ultimo_datahora(df_base, "__datahora__")
    total_antes_filtro_tempo = len(df_novo)
    df_novo_filtrado = filtrar_apenas_registros_posteriores(df_novo, "__datahora__", ultimo_datahora_base)
    removidos_por_datahora = total_antes_filtro_tempo - len(df_novo_filtrado)

    mostrar_amostra_segura(
        "Arquivo 02 após filtro por Data/Hora:",
        df_novo_filtrado,
        ["__datahora__", col_natureza, col_endereco, col_numero, col_bairro, col_municipio, "Território", "AIS"],
        10,
    )
    progresso.progress(50)

    base_sem_aux = df_base.drop(columns=["__datahora__"], errors="ignore").copy()

    for col_extra in [
        "Nivel_Geocodificacao",
        "Fonte",
        "_confirmado_base",
        "_dist_validacao_m",
        "Ocorrencias_Mesmo_Ponto",
        "_loc_aproximada",
    ]:
        if col_extra not in base_sem_aux.columns:
            base_sem_aux[col_extra] = pd.NA

    if ultimo_datahora_base is None:
        df_novo_util = df_novo.copy()
        situacao = "Base anterior sem Data/Hora valida: Arquivo 02 foi incluido integralmente."
    elif df_novo_filtrado.empty:
        df_novo_util = df_novo_filtrado.copy()
        situacao = "Nenhum registro novo encontrado apos a ultima Data/Hora da base: Arquivo 01 foi mantido sem acrescimos."
    else:
        df_novo_util = df_novo_filtrado.copy()
        situacao = "Base anterior localizada: somente registros posteriores a ultima Data/Hora foram adicionados."

    adicionados = len(df_novo_util)
    geocodificados = 0
    caminho_base_geocodificacao = "-"

    if not df_novo_util.empty:
        status.info("Preparando campos de geocodificação...")
        df_novo_util = preparar_campos_geocodificacao(
            df_novo_util,
            col_endereco,
            col_numero,
            col_bairro,
            col_municipio,
        )

        mostrar_amostra_segura(
            "Campos preparados para geocodificação:",
            df_novo_util,
            ["logradouro_busca", "numero_busca", "bairro_busca", "municipio_busca"],
            10,
        )

        progresso.progress(70)
        status.info("Geocodificando linhas novas com a base parquet...")
        df_novo_util, geocodificados, caminho_base_geocodificacao = geocodificar_linhas_novas(
            df_novo_util,
            col_lat_base,
            col_lon_base,
        )

        mostrar_amostra_segura(
            "Resultado da geocodificação:",
            df_novo_util,
            [col_lat_base, col_lon_base, "Nivel_Geocodificacao", "Fonte", "_dist_validacao_m"],
            10,
        )

        df_novo_util = df_novo_util.drop(
            columns=[
                c for c in [
                    "logradouro_busca",
                    "numero_busca",
                    "bairro_busca",
                    "municipio_busca",
                    "__datahora__",
                ] if c in df_novo_util.columns
            ],
            errors="ignore",
        )

        df_novo_util = alinhar_colunas_arquivo_02_com_base(base_sem_aux, df_novo_util)

        mostrar_amostra_segura(
            "Complemento final no esquema da base:",
            df_novo_util,
            [
                "Endereço",
                "Bairro",
                "Município",
                "Território",
                "AIS",
                col_lat_base,
                col_lon_base,
                "Nivel_Geocodificacao",
            ],
            10,
        )

        df_final = pd.concat([base_sem_aux, df_novo_util], ignore_index=True)
    else:
        df_final = base_sem_aux.copy()

    colunas_excluir_saida = [
        "Fonte",
        "_confirmado_base",
        "_dist_validacao_m",
        "Ocorrencias_Mesmo_Ponto",
        "_loc_aproximada",
    ]
    df_final = df_final.drop(columns=[c for c in colunas_excluir_saida if c in df_final.columns], errors="ignore")

    df_final = criar_datahora_base(df_final, col_data_base, col_hora_base)
    df_final = df_final.sort_values(by="__datahora__", ascending=True, na_position="last").reset_index(drop=True)
    df_final = df_final.drop(columns=["__datahora__"], errors="ignore")

    if df_final.columns.duplicated().any():
        df_final = df_final.loc[:, ~df_final.columns.duplicated()].copy()

    progresso.progress(100)

    mostrar_amostra_segura(
        "Resultado final (amostra):",
        df_final,
        ["Data", "Hora", "Endereço", "Bairro", "Município", "Território", "AIS", col_lat_base, col_lon_base, "Nivel_Geocodificacao"],
        20,
    )

    ultima_ref = (
        ultimo_datahora_base.strftime("%d/%m/%Y %H:%M:%S")
        if ultimo_datahora_base is not None else "sem referencia anterior valida"
    )

    resumo = {
        "adicionados": adicionados,
        "total_final": len(df_final),
        "removidos_por_tipo": removidos_por_tipo,
        "removidos_por_datahora": removidos_por_datahora,
        "geocodificados": geocodificados,
        "ultima_datahora_base": ultima_ref,
        "situacao": situacao,
        "aba_arquivo_01": aba_base,
        "aba_arquivo_02": aba_novo,
        "total_lido_arquivo_02": total_lido_arquivo_02,
        "base_geocodificacao": caminho_base_geocodificacao,
    }

    status.success(f"Processo finalizado. {adicionados} registros novos adicionados.")
    return df_final, resumo


def _init_state():
    defaults = {
        "roubo_veiculo_sip_arquivo_01_bytes": None,
        "roubo_veiculo_sip_arquivo_01_nome": None,
        "roubo_veiculo_sip_arquivo_02_bytes": None,
        "roubo_veiculo_sip_arquivo_02_nome": None,
        "roubo_veiculo_sip_resultado_excel": None,
        "roubo_veiculo_sip_resultado_df": None,
        "roubo_veiculo_sip_resumo": None,
    }

    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def render():
    _init_state()

    st.subheader("Roubo de Veículo (SIP)")
    st.write("Envie a base histórica e o arquivo complementar SIP para atualizar a base com novos registros geocodificados.")

    arquivo_01 = st.file_uploader(
        "Arquivo 01 - Base histórica de Roubo de Veículo",
        type=["xlsx", "xls"],
        key="roubo_veiculo_sip_upload_01",
    )

    arquivo_02 = st.file_uploader(
        "Arquivo 02 - Complemento SIP",
        type=["xlsx", "xls"],
        key="roubo_veiculo_sip_upload_02",
    )

    if arquivo_01 is not None:
        arquivo_01.seek(0)
        st.session_state.roubo_veiculo_sip_arquivo_01_bytes = arquivo_01.read()
        st.session_state.roubo_veiculo_sip_arquivo_01_nome = arquivo_01.name

    if arquivo_02 is not None:
        arquivo_02.seek(0)
        st.session_state.roubo_veiculo_sip_arquivo_02_bytes = arquivo_02.read()
        st.session_state.roubo_veiculo_sip_arquivo_02_nome = arquivo_02.name

    pode_processar = (
        st.session_state.roubo_veiculo_sip_arquivo_01_bytes is not None
        and st.session_state.roubo_veiculo_sip_arquivo_02_bytes is not None
    )

    if st.button("Processar Roubo de Veículo (SIP)", type="primary", disabled=not pode_processar):
        try:
            arquivo_01_buffer = BytesIO(st.session_state.roubo_veiculo_sip_arquivo_01_bytes)
            arquivo_02_buffer = BytesIO(st.session_state.roubo_veiculo_sip_arquivo_02_bytes)

            df_final, resumo = processar_roubo_veiculo_sip(arquivo_01_buffer, arquivo_02_buffer)
            arquivo_excel_bytes = gerar_excel_em_memoria(df_final)

            st.session_state.roubo_veiculo_sip_resultado_df = df_final
            st.session_state.roubo_veiculo_sip_resumo = resumo
            st.session_state.roubo_veiculo_sip_resultado_excel = arquivo_excel_bytes
        except Exception as exc:
            st.exception(exc)

    if (
        st.session_state.roubo_veiculo_sip_resultado_df is not None
        and st.session_state.roubo_veiculo_sip_resumo is not None
    ):
        resumo = st.session_state.roubo_veiculo_sip_resumo

        c1, c2, c3 = st.columns(3)
        c1.metric("Novos registros adicionados", resumo.get("adicionados", 0))
        c2.metric("Total final da base", resumo.get("total_final", 0))
        c3.metric("Geocodificados", resumo.get("geocodificados", 0))

        st.info(
            f"Aba Arquivo 01: {resumo.get('aba_arquivo_01', '-')} | "
            f"Aba Arquivo 02: {resumo.get('aba_arquivo_02', '-')}"
        )

        st.info(
            f"Última Data/Hora da base: {resumo.get('ultima_datahora_base', '-')} | "
            f"Removidos por Natureza: {resumo.get('removidos_por_tipo', 0)} | "
            f"Removidos por filtro temporal: {resumo.get('removidos_por_datahora', 0)}"
        )

        st.info(f"Base de geocodificação: {resumo.get('base_geocodificacao', '-')}")
        st.caption(resumo.get("situacao", "Processamento concluído."))

        if st.session_state.roubo_veiculo_sip_resultado_excel is not None:
            st.download_button(
                label="Baixar arquivo final",
                data=st.session_state.roubo_veiculo_sip_resultado_excel,
                file_name=NOME_ARQUIVO_FINAL,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="roubo_veiculo_sip_download_final",
            )


interface_roubo_veiculo_sip = render

"""
Modulo CVP (SIP) - Geocodificacao por endereco
Versao Streamlit adaptada para o QGP Online.

Fluxo:
- Arquivo 01: base historica CVP
- Arquivo 02: complemento SIP com enderecos
- Filtra apenas registros posteriores a ultima DataHora da base
- Geocodifica apenas as novas linhas
- Alinha colunas com a base
- Gera arquivo final para download
"""

from __future__ import annotations

import json
import re
import unicodedata
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
)

NOME_ARQUIVO_FINAL = nome_arquivo_padrao(3, "CVP-SIP-ENDERECO")
USAR_EXTERNO = True
CAMINHO_GPKG = "Faces_de_Quadra_-_Ceara_ARRUAMENTO.gpkg"
CAMINHO_BASE_ENXUTA = "CVP_SIP_GEOCODIFICAR.parquet"
LAYER_GPKG = "reprojetado"
EPSG_GPKG = 31984
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
RE_BNI = re.compile(r"\(?\s*bairro\s+n[aã]o\s+identificad[oa]\s*\)?", flags=re.IGNORECASE)
TIPOS = ("Rua", "Avenida", "Travessa", "Praca", "Rodovia", "Alameda", "Passeio")
ROOFTOP = ("pointaddress", "streetaddress", "subaddress", "pointaddressvd")


@st.cache_data(show_spinner=False)
def carregar_municipios() -> dict:
    caminho = Path(ARQ_CACHE_MUN)
    if caminho.exists():
        try:
            with open(caminho, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{UF_CODIGO}/municipios"
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
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(mapa, f, ensure_ascii=False)
        return mapa
    except Exception:
        return {}


@st.cache_data(show_spinner=False)
def carregar_base_geografica() -> Optional[pd.DataFrame]:
    caminho_parquet = Path(CAMINHO_BASE_ENXUTA)
    if caminho_parquet.exists():
        return pd.read_parquet(caminho_parquet).reset_index(drop=True)

    caminho_gpkg = Path(CAMINHO_GPKG)
    if not caminho_gpkg.exists():
        return None

    import fiona
    from pyproj import Transformer
    from shapely.geometry import shape

    tr = Transformer.from_crs(f"EPSG:{EPSG_GPKG}", "EPSG:4326", always_xy=True)
    regs = []

    with fiona.open(caminho_gpkg, layer=LAYER_GPKG) as src:
        for feat in src:
            prop = feat["properties"]
            tip = str(prop.get("NM_TIP_LOG") or "").strip()
            tit = str(prop.get("NM_TIT_LOG") or "").strip()
            log = str(prop.get("NM_LOG") or "").strip()
            nome = " ".join(x for x in (tip, tit, log) if x and x.lower() != "none")
            if not nome:
                continue

            try:
                geom = shape(feat["geometry"])
                centroid = geom.centroid
                lon, lat = tr.transform(centroid.x, centroid.y)
            except Exception:
                continue

            cod = str(prop.get("CD_SETOR") or "")[:7]
            try:
                tot = int(prop.get("TOT_GERAL") or 0)
            except Exception:
                tot = 0

            regs.append((cod, sem_acento(nome), nome, lat, lon, tot))

    if not regs:
        return None

    base = pd.DataFrame(
        regs,
        columns=["cod_mun", "nome_norm", "nome_orig", "lat", "lon", "tot_geral"],
    )
    base.to_parquet(caminho_parquet, index=False)
    return base.reset_index(drop=True)


@st.cache_resource(show_spinner=False)
def obter_geocoder_arcgis():
    if not USAR_EXTERNO:
        return None
    arc = ArcGIS(timeout=15)
    return RateLimiter(arc.geocode, min_delay_seconds=0.4, max_retries=2, swallow_exceptions=True)


def sem_acento(s: str) -> str:
    n = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in n if not unicodedata.combining(c)).upper().strip()


def limpar_logradouro(texto: str) -> str:
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


def limpar_bairro(bairro: str, municipio: str) -> str:
    v = str(bairro or "").strip()
    if v.lower() in ("nan", "none", ""):
        return ""
    v = RE_BNI.sub("", v)
    v = re.sub(r"\(.*?\)", "", v)
    v = " ".join(v.strip(" ()-").split())
    if v == "" or sem_acento(v) == sem_acento(municipio):
        return ""
    return v


def limpar_numero(numero: str) -> str:
    s = str(numero or "").strip()
    if s.lower() in ("nan", "none", "", "0", "0.0", "s/n", "sn"):
        return ""
    try:
        return str(int(float(s)))
    except Exception:
        return re.sub(r"\D", "", s)


def _hav(lat1, lon1, lat2, lon2):
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
    return 2 * 6371000.0 * np.arcsin(np.sqrt(a))


class MotorGeocodificacaoSoberana:
    def __init__(self):
        self.base = carregar_base_geografica()
        self.mun = carregar_municipios()
        self.tree = None
        self.cent_mun = {}

        if self.base is not None and len(self.base):
            self.glat = self.base["lat"].values.astype(float)
            self.glon = self.base["lon"].values.astype(float)
            self.gnome = self.base["nome_norm"].astype(str).values
            self.gcod = self.base["cod_mun"].astype(str).values
            self.tree = cKDTree(np.c_[self.glat, self.glon])
            cm = self.base.groupby("cod_mun")[["lat", "lon"]].mean()
            self.cent_mun = {k: (v["lat"], v["lon"]) for k, v in cm.iterrows()}

        self.geocode_ext = obter_geocoder_arcgis()

    def cod_municipio(self, municipio: str) -> str:
        return self.mun.get(sem_acento(municipio), "")

    def _idx_municipio(self, cod: str, ancora):
        if cod and self.tree is not None:
            ix = np.where(self.gcod == cod)[0]
            if len(ix):
                return ix
        if ancora is not None and self.tree is not None:
            ix = self.tree.query_ball_point([ancora[0], ancora[1]], r=RAIO_MUNICIPIO_KM / 111.0)
            return np.array(ix, dtype=int)
        return np.array([], dtype=int)

    def casar_rua(self, rua_norm: str, cod: str, ancora):
        ix = self._idx_municipio(cod, ancora)
        if not len(ix):
            return None
        melhor, mscore = None, 0
        for j in ix:
            score = fuzz.token_set_ratio(rua_norm, self.gnome[j])
            if score > mscore:
                mscore, melhor = score, j
        if melhor is not None and mscore >= LIMIAR_NOME:
            return float(self.glat[melhor]), float(self.glon[melhor]), mscore
        return None

    def validar(self, lat: float, lon: float, rua_norm: str, cod: str, ancora):
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

    def geocodificar(self, rua: str, num: str, bairro: str, municipio: str):
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
                return (ext[0], ext[1], "Exato (Numero)", "ArcGIS+GPKG", True, dist)

        g = self.casar_rua(rua_n, cod, ancora)
        if g:
            return (g[0], g[1], "Centroide de Rua", "GPKG (Faces de Quadra)", True, 0.0)

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
    df["bairro_busca"] = df.apply(lambda r: limpar_bairro(r[col_bairro], r[col_municipio]), axis=1)
    df["municipio_busca"] = df[col_municipio].fillna("").astype(str).str.strip()
    return df


def geocodificar_linhas_novas(
    df: pd.DataFrame,
    col_lat_destino: str,
    col_lon_destino: str,
    progress_bar,
    status_placeholder,
):
    motor = MotorGeocodificacaoSoberana()

    lats, lons, niveis, fontes, confirmados, distancias = [], [], [], [], [], []
    geocodificados = 0
    total = max(len(df), 1)

    for i, (_, row) in enumerate(df.iterrows(), start=1):
        num = limpar_numero(row.get("numero_busca", ""))
        r = motor.geocodificar(
            row.get("logradouro_busca", ""),
            num,
            row.get("bairro_busca", ""),
            row.get("municipio_busca", ""),
        )
        lats.append(r[0])
        lons.append(r[1])
        niveis.append(r[2])
        fontes.append(r[3])
        confirmados.append(r[4])
        distancias.append(r[5])

        if r[0] is not None and r[1] is not None:
            geocodificados += 1

        progress_bar.progress(i / total)
        status_placeholder.info(
            f"Geocodificando linhas novas... {i}/{total} processadas | {geocodificados} geocodificadas"
        )

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

    return df, geocodificados


def copiar_valor_entre_colunas(
    df: pd.DataFrame,
    coluna_destino: str,
    colunas_origem: list[str],
):
    if coluna_destino not in df.columns:
        return df
    if coluna_destino in colunas_origem:
        return df

    serie_destino = df[coluna_destino] if coluna_destino in df.columns else pd.Series(index=df.index, dtype="object")

    for col_origem in colunas_origem:
        if col_origem in df.columns:
            mask_vazio = serie_destino.isna() | (serie_destino.astype(str).str.strip() == "")
            df.loc[mask_vazio, coluna_destino] = df.loc[mask_vazio, col_origem]
            serie_destino = df[coluna_destino]
    return df


def interface_cvp_sip():
    st.markdown("## Atualizar CVP (SIP)")
    st.info(
        """
    **Instrucoes:**
    - **Arquivo 01:** Base CVP existente (dados historicos)
    - **Arquivo 02:** Complemento SIP com enderecos

    O sistema ira:
    - Identificar Data/Hora da base e Data/Hora do complemento SIP
    - Filtrar apenas ocorrencias posteriores a ultima DataHora da base
    - Geocodificar apenas as novas linhas
    - Alinhar o resultado ao layout da base
    - Gerar arquivo final consolidado para download
    """
    )

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Arquivo 01 - Base CVP")
        arquivo_base = st.file_uploader(
            "Selecione o arquivo base",
            type=["xlsx", "xls"],
            key="cvp_sip_base",
        )

    with col2:
        st.markdown("#### Arquivo 02 - Complemento SIP")
        arquivo_novo = st.file_uploader(
            "Selecione o arquivo complemento",
            type=["xlsx", "xls"],
            key="cvp_sip_novo",
        )

    if not arquivo_base or not arquivo_novo:
        st.warning("Por favor, faca upload dos dois arquivos para continuar.")
        return

    if st.button("Processar Arquivos", type="primary", use_container_width=True):
        try:
            with st.spinner("Lendo arquivos..."):
                df_base = pd.read_excel(arquivo_base)
                df_novo = pd.read_excel(arquivo_novo)

                df_base = normalizar_colunas(df_base)
                df_novo = normalizar_colunas(df_novo)

                col_data_base = encontrar_coluna_data(df_base)
                col_hora_base = encontrar_coluna_hora(df_base)

                col_data_novo = encontrar_coluna_data(df_novo)
                col_hora_novo = encontrar_coluna_por_nomes(
                    df_novo,
                    ["hora", "horario", "horário", "hora fato", "hora_fato"],
                    obrigatoria=False,
                )

                col_lat_base = encontrar_coluna_por_nomes(df_base, ["lat", "latitude"])
                col_lon_base = encontrar_coluna_por_nomes(df_base, ["long", "longitude", "lon"])

                col_endereco = encontrar_coluna_por_nomes(
                    df_novo, ["endereco", "endereço", "logradouro", "rua"]
                )

                col_numero = encontrar_coluna_por_nomes(
                    df_novo,
                    ["numero", "número", "nº", "n°", "num", "num.", "localnumero", "local_numero"],
                    obrigatoria=False,
                )
                if col_numero is None:
                    df_novo["Numero"] = ""
                    col_numero = "Numero"

                col_bairro = encontrar_coluna_por_nomes(df_novo, ["bairro"])
                col_municipio = encontrar_coluna_por_nomes(
                    df_novo, ["municipio", "município", "cidade"]
                )

                col_regioes_novo = encontrar_coluna_por_nomes(
                    df_novo,
                    ["regioes", "regiões", "regiao", "região", "territorio", "território"],
                    obrigatoria=False,
                )

                col_complemento_novo = encontrar_coluna_por_nomes(
                    df_novo,
                    [
                        "complemento do endereco",
                        "complemento do endereço",
                        "complemento endereco",
                        "complemento endereço",
                        "complemento",
                    ],
                    obrigatoria=False,
                )

                col_territorio_base = encontrar_coluna_por_nomes(
                    df_base,
                    ["territorio", "território", "regioes", "regiões", "regiao", "região"],
                    obrigatoria=False,
                )

                col_numero_base = encontrar_coluna_por_nomes(
                    df_base,
                    ["numero", "número", "nº", "n°", "num"],
                    obrigatoria=False,
                )

                col_complemento_base = encontrar_coluna_por_nomes(
                    df_base,
                    [
                        "complemento do endereco",
                        "complemento do endereço",
                        "complemento endereco",
                        "complemento endereço",
                        "complemento",
                    ],
                    obrigatoria=False,
                )

                mapa_extra = {}
                if col_regioes_novo and col_territorio_base:
                    mapa_extra[col_territorio_base] = [col_regioes_novo]
                if col_complemento_novo and col_complemento_base:
                    mapa_extra[col_complemento_base] = [col_complemento_novo]
                if col_numero and col_numero_base and col_numero != col_numero_base:
                    mapa_extra[col_numero_base] = [col_numero]

                df_novo = renomear_colunas_equivalentes(df_base, df_novo, mapa_extra=mapa_extra)
                df_base = criar_coluna_datahora(df_base, col_data_base, col_hora_base, nome_coluna="datahora")

                if col_hora_novo is None:
                    df_novo["Hora"] = "00:00:00"
                    col_hora_novo = "Hora"

                df_novo = criar_coluna_datahora(df_novo, col_data_novo, col_hora_novo, nome_coluna="datahora")

                ultima_datahora_base = obter_ultima_datahora(df_base, "datahora")
                total_antes_filtro_tempo = len(df_novo)

                df_novo_filtrado = filtrar_apenas_registros_posteriores(
                    df_novo, "datahora", ultima_datahora_base
                )
                removidos_por_datahora = total_antes_filtro_tempo - len(df_novo_filtrado)

                base_sem_aux = df_base.drop(columns=["datahora"])

                for col_aux in [
                    "Nivel_Geocodificacao",
                    "Fonte",
                    "_confirmado_base",
                    "_dist_validacao_m",
                    "Ocorrencias_Mesmo_Ponto",
                    "_loc_aproximada",
                ]:
                    if col_aux not in base_sem_aux.columns:
                        base_sem_aux[col_aux] = pd.NA

                if ultima_datahora_base is None:
                    df_novo_util = df_novo.copy()
                    situacao = "Base anterior sem DataHora valida - Arquivo 02 incluido integralmente."
                elif df_novo_filtrado.empty:
                    df_novo_util = df_novo_filtrado.copy()
                    situacao = "Nenhum registro novo encontrado apos a ultima DataHora da base."
                else:
                    df_novo_util = df_novo_filtrado.copy()
                    situacao = "Somente registros posteriores a ultima DataHora foram adicionados."

            adicionados = len(df_novo_util)
            geocodificados = 0
            progress_bar = st.progress(0)
            status_placeholder = st.empty()

            if not df_novo_util.empty:
                with st.spinner("Geocodificando novas ocorrencias..."):
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
                        progress_bar,
                        status_placeholder,
                    )

                    if col_data_base in base_sem_aux.columns and col_data_novo in df_novo_util.columns:
                        df_novo_util[col_data_base] = df_novo_util[col_data_novo]

                    if col_hora_base in base_sem_aux.columns and col_hora_novo in df_novo_util.columns:
                        df_novo_util[col_hora_base] = df_novo_util[col_hora_novo]

                    if col_territorio_base:
                        df_novo_util = copiar_valor_entre_colunas(
                            df_novo_util,
                            col_territorio_base,
                            [col_regioes_novo, "Regioes", "Regiões", "Territorio", "Território"],
                        )

                    if col_numero_base:
                        df_novo_util = copiar_valor_entre_colunas(
                            df_novo_util,
                            col_numero_base,
                            [col_numero, "Numero", "Número"],
                        )

                    if col_complemento_base:
                        df_novo_util = copiar_valor_entre_colunas(
                            df_novo_util,
                            col_complemento_base,
                            [
                                col_complemento_novo,
                                "Complemento do Endereco",
                                "Complemento do Endereço",
                                "Complemento",
                            ],
                        )

                    df_novo_util = df_novo_util.drop(
                        columns=[
                            c
                            for c in [
                                "logradouro_busca",
                                "numero_busca",
                                "bairro_busca",
                                "municipio_busca",
                                "datahora",
                            ]
                            if c in df_novo_util.columns
                        ]
                    )

                    df_novo_util = alinhar_colunas_com_base(base_sem_aux, df_novo_util)
                    df_final = pd.concat([base_sem_aux, df_novo_util], ignore_index=True)
            else:
                progress_bar.empty()
                status_placeholder.empty()
                df_final = base_sem_aux.copy()

            colunas_excluir_saida = [
                "Fonte",
                "_confirmado_base",
                "_dist_validacao_m",
                "Ocorrencias_Mesmo_Ponto",
                "_loc_aproximada",
            ]
            df_final = df_final.drop(columns=[c for c in colunas_excluir_saida if c in df_final.columns])

            df_final = criar_coluna_datahora(df_final, col_data_base, col_hora_base, nome_coluna="datahora")
            df_final = df_final.sort_values(by="datahora", ascending=True, na_position="last").reset_index(drop=True)
            df_final = df_final.drop(columns=["datahora"])

            total_final = len(df_final)

            st.success("Processamento Finalizado com Sucesso!")
            st.markdown("### Resumo")

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Registros Adicionados", adicionados)
            with c2:
                st.metric("Registros Geocodificados", geocodificados)
            with c3:
                st.metric("Total Final", total_final)

            if ultima_datahora_base is not None:
                st.info(f"Ultima DataHora da base: {ultima_datahora_base.strftime('%d/%m/%Y %H:%M:%S')}")
            st.info(f"Situacao: {situacao}")

            if removidos_por_datahora > 0:
                st.warning(
                    f"Registros excluidos por serem anteriores/iguais a ultima DataHora: {removidos_por_datahora}"
                )

            excel_data = gerar_arquivo_excel(df_final, sheet_name="CVP_SIP_ENDERECO")
            st.download_button(
                label="Baixar Arquivo Final",
                data=excel_data,
                file_name=NOME_ARQUIVO_FINAL,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        except Exception as e:
            st.error(f"Erro durante o processamento: {str(e)}")
            import traceback
            with st.expander("Detalhes do erro"):
                st.code(traceback.format_exc())

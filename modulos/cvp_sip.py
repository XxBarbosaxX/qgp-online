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
)

st.set_page_config(page_title="CVP (SIP)", layout="wide")

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

RE_BNI = re.compile(
    r"\(?\s*bairro\s+n[aã]o\s+identificad[oa]\s*\)?",
    flags=re.IGNORECASE,
)

TIPOS = ("Rua", "Avenida", "Travessa", "Praca", "Rodovia", "Alameda", "Passeio")
ROOFTOP = ("pointaddress", "streetaddress", "subaddress", "pointaddressvd")


def sem_acento(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in normalizado if not unicodedata.combining(c)).upper().strip()


@st.cache_data(show_spinner=False)
def carregar_municipios() -> dict:
    caminho = Path(ARQ_CACHE_MUN)

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


@st.cache_data(show_spinner=False)
def carregar_base_geografica() -> Optional[pd.DataFrame]:
    caminho_parquet = Path(CAMINHO_BASE_ENXUTA)
    if caminho_parquet.exists():
        return pd.read_parquet(caminho_parquet).reset_index(drop=True)

    caminho_gpkg = Path(CAMINHO_GPKG)
    if not caminho_gpkg.exists():
        return None

    try:
        import fiona
        from pyproj import Transformer
        from shapely.geometry import shape
    except Exception as exc:
        raise RuntimeError(
            "Dependências geoespaciais não disponíveis: fiona, pyproj e shapely são necessárias."
        ) from exc

    transformador = Transformer.from_crs(f"EPSG:{EPSG_GPKG}", "EPSG:4326", always_xy=True)
    registros = []

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
                centroide = geom.centroid
                lon, lat = transformador.transform(centroide.x, centroide.y)
            except Exception:
                continue

            cod = str(prop.get("CD_SETOR") or "")[:7]

            try:
                total = int(prop.get("TOT_GERAL") or 0)
            except Exception:
                total = 0

            registros.append((cod, sem_acento(nome), nome, lat, lon, total))

    if not registros:
        return None

    base = pd.DataFrame(
        registros,
        columns=["cod_mun", "nome_norm", "nome_orig", "lat", "lon", "tot_geral"],
    )
    base.to_parquet(caminho_parquet, index=False)
    return base.reset_index(drop=True)


@st.cache_resource(show_spinner=False)
def obter_geocoder_arcgis():
    if not USAR_EXTERNO:
        return None
    arc = ArcGIS(timeout=15)
    return RateLimiter(
        arc.geocode,
        min_delay_seconds=0.4,
        max_retries=2,
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
    def __init__(self):
        self.base = carregar_base_geografica()
        self.municipios = carregar_municipios()
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

        self.geocode_ext = obter_geocoder_arcgis()

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
                r=RAIO_MUNICIPIO_KM / 111.0,
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

        if melhor_indice is not None and melhor_score >= LIMIAR_NOME:
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
            [fuzz.token_set_ratio(rua_norm, nome) >= LIMIAR_NOME for nome in nomes]
        )

        if not mascara.any():
            return False, None

        indices_filtrados = indices[mascara]
        distancias = _hav(lat, lon, self.glat[indices_filtrados], self.glon[indices_filtrados])
        melhor = float(distancias.min())

        return melhor <= RAIO_CONFIRMA_M, melhor

    def geocodificar(self, rua: str, numero: str, bairro: str, municipio: str):
        rua_limpa = limpar_logradouro(rua)
        bairro_limpo = limpar_bairro(bairro, municipio)
        rua_norm = sem_acento(rua_limpa)
        cod = self.cod_municipio(municipio)

        if not rua_limpa:
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
            return (None, None, "Nao Encontrado", "-", False, None)

        partes = [f"{rua_limpa}, {numero}" if numero else rua_limpa]
        if bairro_limpo:
            partes.append(bairro_limpo)

        partes += [str(municipio).strip(), "Ceará", "Brasil"]
        consulta = ", ".join(p for p in partes if p)

        externo = None
        if self.geocode_ext is not None:
            loc = self.geocode_ext(consulta, out_fields="*")
            if loc:
                addr_type = ((loc.raw or {}).get("attributes", {}) or {}).get("Addr_type", "")
                externo = (float(loc.latitude), float(loc.longitude), str(addr_type).lower())

        ancora = (externo[0], externo[1]) if externo else None

        if externo and externo[2] in ROOFTOP and numero:
            ok, distancia = self.validar(externo[0], externo[1], rua_norm, cod, ancora)
            if ok:
                return (
                    externo[0],
                    externo[1],
                    "Exato (Numero)",
                    "ArcGIS+GPKG",
                    True,
                    distancia,
                )

        geobase = self.casar_rua(rua_norm, cod, ancora)
        if geobase:
            return (
                geobase[0],
                geobase[1],
                "Centroide de Rua",
                "GPKG (Faces de Quadra)",
                True,
                0.0,
            )

        if externo:
            if externo[2] in ("streetname", "streetmidblock", "streetint") or numero:
                nivel = "Centroide de Rua"
            elif externo[2] in ("locality", "neighborhood", "district"):
                nivel = "Centroide de Bairro"
            else:
                nivel = "Centroide de Cidade"

            return (
                externo[0],
                externo[1],
                nivel,
                "ArcGIS (nao confirmado)",
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
) -> tuple[pd.DataFrame, int]:
    motor = MotorGeocodificacaoSoberana()

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
        numero = limpar_numero(linha.get("numero_busca", ""))

        resultado = motor.geocodificar(
            linha.get("logradouro_busca", ""),
            numero,
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
        (df["Ocorrencias_Mesmo_Ponto"] >= LIMIAR_SUSPEITO)
        & (df["numero_busca"].fillna("").astype(str).str.strip() == "")
    )

    status.success(f"Geocodificação concluída. Registros geocodificados: {geocodificados}")
    return df, geocodificados


def processar_cvp_sip(arquivo_01, arquivo_02):
    df_base = pd.read_excel(arquivo_01)
    df_novo = pd.read_excel(arquivo_02)

    df_base = normalizar_colunas(df_base)
    df_novo = normalizar_colunas(df_novo)

    col_data_base = encontrar_coluna_data(df_base)
    col_hora_base = encontrar_coluna_hora(df_base)

    col_datahora_novo = encontrar_coluna_por_nomes(
        df_novo,
        ["data", "datahora", "data/hora", "data hora"],
        obrigatoria=True,
    )

    col_lat_base = encontrar_coluna_por_nomes(df_base, ["lat", "latitude"], obrigatoria=True)
    col_lon_base = encontrar_coluna_por_nomes(df_base, ["lon", "long", "longitude"], obrigatoria=True)

    col_endereco = encontrar_coluna_por_nomes(
        df_novo,
        ["endereço", "endereco", "logradouro", "rua"],
        obrigatoria=True,
    )
    col_numero = encontrar_coluna_por_nomes(
        df_novo,
        ["número", "numero", "localNumero", "num"],
        obrigatoria=True,
    )
    col_bairro = encontrar_coluna_por_nomes(df_novo, ["bairro"], obrigatoria=True)
    col_municipio = encontrar_coluna_por_nomes(
        df_novo,
        ["município", "municipio", "cidade"],
        obrigatoria=True,
    )

    df_novo = renomear_colunas_equivalentes(df_base, df_novo)

    df_base = criar_coluna_datahora(df_base, col_data_base, col_hora_base, "__datahora__")
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
        situacao = "Base anterior sem Data/Hora válida: Arquivo 02 foi incluído integralmente."
    elif df_novo_filtrado.empty:
        df_novo_util = df_novo_filtrado.copy()
        situacao = (
            "Nenhum registro novo encontrado após a última Data/Hora da base: "
            "Arquivo 01 foi mantido sem acréscimos."
        )
    else:
        df_novo_util = df_novo_filtrado.copy()
        situacao = (
            "Base anterior localizada: somente registros posteriores à última "
            "Data/Hora foram adicionados."
        )

    geocodificados = 0

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
        )

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

    total_final = len(df_final)

    ultima_ref = (
        ultima_datahora_base.strftime("%d/%m/%Y %H:%M:%S")
        if ultima_datahora_base is not None
        else "sem referência anterior válida"
    )

    resumo = {
        "adicionados": adicionados,
        "total_final": total_final,
        "geocodificados": geocodificados,
        "removidos_por_datahora": removidos_por_datahora,
        "ultima_datahora_base": ultima_ref,
        "situacao": situacao,
    }

    return df_final, resumo


def _init_state():
    defaults = {
        "cvp_sip_arquivo_01_bytes": None,
        "cvp_sip_arquivo_01_nome": None,
        "cvp_sip_arquivo_02_bytes": None,
        "cvp_sip_arquivo_02_nome": None,
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def _salvar_uploads():
    arquivo_01 = st.session_state.get("cvp_sip_upload_01")
    arquivo_02 = st.session_state.get("cvp_sip_upload_02")

    if arquivo_01 is not None:
        arquivo_01.seek(0)
        st.session_state.cvp_sip_arquivo_01_bytes = arquivo_01.read()
        st.session_state.cvp_sip_arquivo_01_nome = arquivo_01.name

    if arquivo_02 is not None:
        arquivo_02.seek(0)
        st.session_state.cvp_sip_arquivo_02_bytes = arquivo_02.read()
        st.session_state.cvp_sip_arquivo_02_nome = arquivo_02.name


def render():
    _init_state()

    st.title("CVP (SIP) - Geocodificação por Endereço")
    st.write(
        "Envie a base histórica e o complemento SIP para atualizar a base com geocodificação."
    )

    with st.container():
        with st.form("form_cvp_sip_upload", clear_on_submit=False):
            st.file_uploader(
                "Arquivo 01 - Base histórica CVP",
                type=["xlsx", "xls"],
                key="cvp_sip_upload_01",
            )

            st.file_uploader(
                "Arquivo 02 - Complemento SIP",
                type=["xlsx", "xls"],
                key="cvp_sip_upload_02",
            )

            submitted = st.form_submit_button("Carregar arquivos")

    if submitted:
        _salvar_uploads()
        st.success("Arquivos carregados com sucesso.")

    if st.session_state.cvp_sip_arquivo_01_nome:
        st.info(f"Arquivo 01 carregado: {st.session_state.cvp_sip_arquivo_01_nome}")

    if st.session_state.cvp_sip_arquivo_02_nome:
        st.info(f"Arquivo 02 carregado: {st.session_state.cvp_sip_arquivo_02_nome}")

    pode_processar = (
        st.session_state.cvp_sip_arquivo_01_bytes is not None
        and st.session_state.cvp_sip_arquivo_02_bytes is not None
    )

    if st.button("Processar CVP (SIP)", type="primary", disabled=not pode_processar):
        try:
            arquivo_01_buffer = BytesIO(st.session_state.cvp_sip_arquivo_01_bytes)
            arquivo_02_buffer = BytesIO(st.session_state.cvp_sip_arquivo_02_bytes)

            with st.spinner("Processando e geocodificando registros..."):
                df_final, resumo = processar_cvp_sip(arquivo_01_buffer, arquivo_02_buffer)

            st.success("Processamento concluído com sucesso.")

            c1, c2, c3 = st.columns(3)
            c1.metric("Novos registros adicionados", resumo["adicionados"])
            c2.metric("Total final da base", resumo["total_final"])
            c3.metric("Registros geocodificados", resumo["geocodificados"])

            st.info(
                f"Última Data/Hora da base: {resumo['ultima_datahora_base']} | "
                f"Removidos por filtro temporal: {resumo['removidos_por_datahora']}"
            )
            st.caption(resumo["situacao"])
            st.dataframe(df_final.head(50), use_container_width=True)

            arquivo_excel = gerar_arquivo_excel(
                df_final,
                nome_aba="CVP_SIP_ENDERECO",
            )

            st.download_button(
                label="Baixar arquivo final",
                data=arquivo_excel,
                file_name=NOME_ARQUIVO_FINAL,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        except Exception as exc:
            st.exception(exc)


render()

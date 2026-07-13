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
    caminho_parquet = Path(CAMINHO_BASE_ENXUTA)
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
            f"O arquivo {CAMINHO_BASE_ENXUTA} nao possui as colunas esperadas: {sorted(faltantes)}"
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
        """Retorna codigo IBGE do municipio."""
        return self.municipios.get(sem_acento(municipio), "")

    def _idx_municipio(self, cod: str, ancora):
        """Retorna indices do municipio ou por proximidade."""
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

        if melhor_indice is not None and melhor_score >= LIMIAR_NOME:
            return (
                float(self.glat[melhor_indice]),
                float(self.glon[melhor_indice]),
                melhor_score,
            )

        return None

    def validar(self, lat: float, lon: float, rua_norm: str, cod: str, ancora):
        """Valida coordenada externa com base local."""
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
        """Executa estrategia hierarquica de geocodificacao."""
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
                    addr_type = ((loc.raw or {}).get("attributes", {}) or {}).get("Addr_type", "")
                    externo = (float(loc.latitude), float(loc.longitude), str(addr_type).lower())

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
    """Prepara campos auxiliares para geocodificacao."""
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
    """Geocodifica linhas novas e retorna DataFrame atualizado."""
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
        (df["Ocorrencias_Mesmo_Ponto"] >= LIMIAR_SUSPEITO)
        & (df["numero_busca"].fillna("").astype(str).str.strip() == "")
    )

    progresso.empty()
    status.success(f"Geocodificacao concluida. Registros geocodificados: {geocodificados}")
    return df, geocodificados


def processar_cvp_sip(arquivo_01, arquivo_02):
    """Processa CVP SIP e retorna (df_final, resumo)."""
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

    col_data_base = encontrar_coluna_data(df_base)
    col_hora_base = encontrar_coluna_hora(df_base)

    col_datahora_novo = encontrar_coluna_por_nomes(
        df_novo,
        ["data", "datahora", "data/hora", "data hora"],
        obrigatoria=True,
    )

    col_lat_base = encontrar_coluna_por_nomes(df_base, ["lat", "latitude"], obrigatoria=True)
    col_lon_base = encontrar_coluna_por_nomes(
        df_base,
        ["lon", "long", "longitude"],
        obrigatoria=True,
    )

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

    col_territorio_novo = encontrar_coluna_por_nomes(
        df_novo,
        ["regiões", "regioes"],
        obrigatoria=False,
    )

    if col_territorio_novo and col_territorio_novo != "Território":
        df_novo = df_novo.rename(columns={col_territorio_novo: "Território"})

    df_novo = renomear_colunas_equivalentes(
        df_base,
        df_novo,
        mapa_extra={
            "AISNova": ["AIS", "AISNova", "AIS Nova", "AIS_Nova", "aisnova"],
            "AIS": ["AISNova", "AIS Nova", "AIS_Nova", "aisnova"],
        },
    )

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
        situacao = "Base anterior sem Data/Hora valida: Arquivo 02 foi incluido integralmente."
    elif df_novo_filtrado.empty:
        df_novo_util = df_novo_filtrado.copy()
        situacao = (
            "Nenhum registro novo encontrado apos a ultima Data/Hora da base: "
            "Arquivo 01 foi mantido sem acrescimos."
        )
    else:
        df_novo_util = df_novo_filtrado.copy()
        situacao = (
            "Base anterior localizada: somente registros posteriores a ultima "
            "Data/Hora foram adicionados."
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
        "removidos_por_datahora": removidos_por_datahora,
        "removidos_sem_geocodificacao": removidos_sem_geocodificacao,
        "ultima_datahora_base": ultima_ref,
        "situacao": situacao,
        "aba_arquivo_01": aba_base,
        "aba_arquivo_02": aba_novo,
        "contagens_nivel": contagens_nivel,
        "nome_arquivo": NOME_ARQUIVO_FINAL,
    }

    return df_final, resumo


def _init_state() -> None:
    """Inicializa chaves de session_state do módulo."""
    defaults = {
        "cvp_sip_arquivo_01_bytes": None,
        "cvp_sip_arquivo_01_nome": None,
        "cvp_sip_arquivo_02_bytes": None,
        "cvp_sip_arquivo_02_nome": None,
        "cvp_sip_resultado_excel": None,
        "cvp_sip_resultado_df": None,
        "cvp_sip_resumo": None,
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def _render_resumo_cvp_sip(resumo: dict, df_final: pd.DataFrame) -> None:
    """Renderiza o resumo do processamento."""
    st.markdown(
        """
        <div class="cvp-sip-card">
            <div class="cvp-sip-card-header">Resultado do processamento</div>
            <div class="cvp-sip-card-desc">
                O processamento foi concluído com sucesso. Abaixo estão os principais indicadores da execução.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.success("Processamento concluído com sucesso.")
    st.caption(resumo["situacao"])

    c1, c2, c3 = st.columns(3)
    c1.metric("Novos registros adicionados", resumo["adicionados"])
    c2.metric("Total final da base", resumo["total_final"])
    c3.metric("Registros geocodificados", resumo["geocodificados"])

    c4, c5, c6 = st.columns(3)
    c4.info(f"**Última Data/Hora base:** {resumo['ultima_datahora_base']}")
    c5.info(f"**Removidos por filtro temporal:** {resumo['removidos_por_datahora']}")
    c6.info(f"**Removidos sem geocodificação:** {resumo['removidos_sem_geocodificacao']}")

    c7, c8 = st.columns(2)
    c7.info(f"**Aba arquivo 01:** {resumo['aba_arquivo_01']}")
    c8.info(f"**Aba arquivo 02:** {resumo['aba_arquivo_02']}")

    contagens_nivel = resumo.get("contagens_nivel", {})
    if contagens_nivel:
        st.markdown(
            """
            <div class="cvp-sip-card">
                <div class="cvp-sip-card-header">Níveis de geocodificação</div>
                <div class="cvp-sip-card-desc">
                    Distribuição dos registros conforme o nível de precisão obtido no processo de geocodificação.
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

        n1, n2, n3 = st.columns(3)
        n1.metric("Exato (Número)", exato_numero)
        n2.metric("Centroide de Rua", centroide_rua)
        n3.metric("Centroide de Bairro", centroide_bairro)

        n4, n5 = st.columns(2)
        n4.metric("Centroide de Cidade", centroide_cidade)
        n5.metric("Não encontrado", nao_encontrado)

    st.markdown(
        """
        <div class="cvp-sip-card">
            <div class="cvp-sip-card-header">Pré-visualização</div>
            <div class="cvp-sip-card-desc">
                Visualização inicial dos primeiros registros do arquivo final processado.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.dataframe(df_final.head(50), use_container_width=True)


def render() -> None:
    """Renderiza a interface principal do módulo."""
    _init_state()

    st.markdown(
        """
        <style>
        .cvp-sip-card {
            border-radius: 0.85rem;
            padding: 1rem 1.1rem;
            margin-bottom: 0.75rem;
            border: 1px solid rgba(148, 163, 184, 0.30);
            background: #020617;
        }
        .cvp-sip-card-header {
            font-weight: 700;
            font-size: 0.98rem;
            margin-bottom: 0.35rem;
            color: rgba(248, 250, 252, 0.98);
        }
        .cvp-sip-card-desc {
            font-size: 0.84rem;
            color: rgba(226, 232, 240, 0.82);
            margin-bottom: 0.2rem;
        }
        .cvp-sip-file-card {
            border-radius: 0.75rem;
            padding: 0.75rem 0.85rem;
            background: rgba(15, 23, 42, 0.92);
            border: 1px solid rgba(148, 163, 184, 0.20);
            margin-top: 0.4rem;
            margin-bottom: 0.45rem;
        }
        .cvp-sip-file-title {
            font-size: 0.8rem;
            font-weight: 700;
            color: rgba(248, 250, 252, 0.98);
            margin-bottom: 0.2rem;
        }
        .cvp-sip-file-desc {
            font-size: 0.78rem;
            color: rgba(148, 163, 184, 0.95);
        }
        .element-container:has(#cvp-sip-download-marker) + div button {
            background: linear-gradient(135deg, #ea580c, #f97316) !important;
            border-color: rgba(248, 250, 252, 0.15) !important;
            color: #fff7ed !important;
            font-weight: 700 !important;
        }
        .element-container:has(#cvp-sip-download-marker) + div button:hover {
            background: linear-gradient(135deg, #c2410c, #ea580c) !important;
        }
        .element-container:has(#cvp-sip-download-marker) + div button p {
            color: #fff7ed !important;
            font-weight: 700 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("## CVP SIP")
    st.caption("Atualização da base CVP com geocodificação por endereço a partir do complemento SIP.")

    st.markdown(
        f"""
        <div class="cvp-sip-card">
            <div class="cvp-sip-card-header">Base geográfica de apoio</div>
            <div class="cvp-sip-card-desc">
                Este módulo utiliza a base geográfica auxiliar localizada em <strong>{CAMINHO_BASE_ENXUTA}</strong>
                para validação e apoio à geocodificação dos registros.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        base_geo = carregar_base_geografica()
        if base_geo is not None and not base_geo.empty:
            st.success(
                f"Base geográfica carregada com sucesso: {len(base_geo):,} registros em {CAMINHO_BASE_ENXUTA}"
            )
        else:
            st.warning(
                f"A base geográfica não foi carregada. Verifique o arquivo {CAMINHO_BASE_ENXUTA}."
            )
    except Exception as exc:
        st.error(f"Erro ao carregar base geográfica: {exc}")

    st.markdown(
        """
        <div class="cvp-sip-card">
            <div class="cvp-sip-card-header">Entrada de arquivos</div>
            <div class="cvp-sip-card-desc">
                Envie a base histórica e o arquivo complementar do SIP para processamento e geocodificação.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
            <div class="cvp-sip-file-card">
                <div class="cvp-sip-file-title">Arquivo 01</div>
                <div class="cvp-sip-file-desc">Base histórica consolidada do CVP.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        arquivo_01 = st.file_uploader(
            "Arquivo 01 - Base historica CVP",
            type=["xlsx", "xls"],
            key="cvp_sip_upload_01",
            label_visibility="collapsed",
        )

    with col2:
        st.markdown(
            """
            <div class="cvp-sip-file-card">
                <div class="cvp-sip-file-title">Arquivo 02</div>
                <div class="cvp-sip-file-desc">Complemento SIP para atualização e geocodificação.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        arquivo_02 = st.file_uploader(
            "Arquivo 02 - Complemento SIP",
            type=["xlsx", "xls"],
            key="cvp_sip_upload_02",
            label_visibility="collapsed",
        )

    if arquivo_01 is not None:
        arquivo_01.seek(0)
        st.session_state.cvp_sip_arquivo_01_bytes = arquivo_01.read()
        st.session_state.cvp_sip_arquivo_01_nome = arquivo_01.name

    if arquivo_02 is not None:
        arquivo_02.seek(0)
        st.session_state.cvp_sip_arquivo_02_bytes = arquivo_02.read()
        st.session_state.cvp_sip_arquivo_02_nome = arquivo_02.name

    col_status_1, col_status_2 = st.columns(2)
    with col_status_1:
        if st.session_state.cvp_sip_arquivo_01_nome:
            st.info(f"Arquivo 01 carregado: {st.session_state.cvp_sip_arquivo_01_nome}")
    with col_status_2:
        if st.session_state.cvp_sip_arquivo_02_nome:
            st.info(f"Arquivo 02 carregado: {st.session_state.cvp_sip_arquivo_02_nome}")

    pode_processar = (
        st.session_state.cvp_sip_arquivo_01_bytes is not None
        and st.session_state.cvp_sip_arquivo_02_bytes is not None
    )

    if st.button(
        "Processar CVP SIP",
        type="primary",
        disabled=not pode_processar,
        use_container_width=True,
        key="cvp_sip_processar",
    ):
        try:
            arquivo_01_buffer = BytesIO(st.session_state.cvp_sip_arquivo_01_bytes)
            arquivo_02_buffer = BytesIO(st.session_state.cvp_sip_arquivo_02_bytes)

            with st.spinner("Processando e geocodificando registros..."):
                df_final, resumo = processar_cvp_sip(arquivo_01_buffer, arquivo_02_buffer)
                arquivo_excel_bytes = gerar_excel_em_memoria(df_final)

            st.session_state.cvp_sip_resultado_df = df_final
            st.session_state.cvp_sip_resumo = resumo
            st.session_state.cvp_sip_resultado_excel = arquivo_excel_bytes

        except Exception as exc:
            st.exception(exc)

    if (
        st.session_state.cvp_sip_resultado_df is not None
        and st.session_state.cvp_sip_resumo is not None
    ):
        df_final = st.session_state.cvp_sip_resultado_df
        resumo = st.session_state.cvp_sip_resumo

        _render_resumo_cvp_sip(resumo, df_final)

        if st.session_state.cvp_sip_resultado_excel is not None:
            st.markdown(
                """
                <div class="cvp-sip-card">
                    <div class="cvp-sip-card-header">Download</div>
                    <div class="cvp-sip-card-desc">
                        Baixe o arquivo final processado no padrão oficial do módulo CVP SIP.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown('<span id="cvp-sip-download-marker"></span>', unsafe_allow_html=True)
            st.download_button(
                label="Baixar arquivo final",
                data=st.session_state.cvp_sip_resultado_excel,
                file_name=NOME_ARQUIVO_FINAL,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="cvp_sip_download_final",
                use_container_width=True,
            )


interface_cvp_sip = render

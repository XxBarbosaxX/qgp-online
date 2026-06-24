import os
import re
import json
import traceback
import unicodedata
import importlib.util
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from scipy.spatial import cKDTree
from rapidfuzz import fuzz
from geopy.geocoders import ArcGIS
from geopy.extra.rate_limiter import RateLimiter

NOME_ARQUIVO_FINAL = "7 - ROUBO DE VEÃCULO_SIP ENDERECO - 2026 - QGP.xlsx"
USAR_EXTERNO = True
CAMINHO_GPKG = "Faces_de_Quadra_-_CearÃ¡_ARRUAMENTO.gpkg"
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
RE_BNI = re.compile(r"\(?\s*bairro\s+n[aÃ£]o\s+identificad[oa]\s*\)?", flags=re.IGNORECASE)
TIPOS = ("Rua", "Avenida", "Travessa", "Praca", "Rodovia", "Alameda", "Passeio")
ROOFTOP = ("pointaddress", "streetaddress", "subaddress", "pointaddressvd")


def _pip(pacote):
    for args in ([os.sys.executable, "-m", "pip", "install", "-q", pacote],
                 [os.sys.executable, "-m", "pip", "install", "-q", pacote, "--break-system-packages"]):
        try:
            subprocess.check_call(args)
            return
        except Exception:
            continue


def garantir_dependencias():
    req = [
        ("fiona", "fiona"),
        ("pyarrow", "pyarrow"),
        ("shapely", "shapely"),
        ("pyproj", "pyproj"),
    ]
    for mod, pk in req:
        if importlib.util.find_spec(mod) is None:
            _pip(pk)


def selecionar_arquivo(titulo):
    return filedialog.askopenfilename(
        title=titulo,
        filetypes=[("Arquivos Excel", "*.xlsx *.xls")]
    )


def selecionar_pasta_saida():
    return filedialog.askdirectory(
        title="Selecione a pasta onde o arquivo final serÃ¡ salvo"
    )


def normalizar_colunas(df):
    df.columns = [str(c).strip() for c in df.columns]
    return df


def filtrar_por_natureza(df, natureza_alvo="ROUBO DE VEICULO"):
    col_natureza = encontrar_coluna_por_nomes(df, ["Natureza"], obrigatoria=True)
    alvo = sem_acento(natureza_alvo)
    return df[df[col_natureza].apply(sem_acento) == alvo].copy()


def encontrar_coluna_data_base(df):
    exatos = [c for c in df.columns if str(c).strip().lower() == "data"]
    if exatos:
        return exatos[0]
    aproximados = [c for c in df.columns if "data" in str(c).strip().lower()]
    if aproximados:
        return aproximados[0]
    raise ValueError("NÃ£o foi encontrada a coluna 'Data' no Arquivo 01.")


def encontrar_coluna_hora_base(df):
    exatos = [c for c in df.columns if str(c).strip().lower() == "hora"]
    if exatos:
        return exatos[0]
    aproximados = [c for c in df.columns if "hora" in str(c).strip().lower()]
    if aproximados:
        return aproximados[0]
    raise ValueError("NÃ£o foi encontrada a coluna 'Hora' no Arquivo 01.")


def encontrar_coluna_datahora_arquivo_02(df):
    exatos = [c for c in df.columns if str(c).strip().lower() == "data"]
    if exatos:
        return exatos[0]
    raise ValueError("NÃ£o foi encontrada a coluna 'data' no Arquivo 02.")


def encontrar_coluna_por_nomes(df, nomes_possiveis, obrigatoria=True):
    cols_map = {str(c).strip().lower(): c for c in df.columns}
    for nome in nomes_possiveis:
        if nome.lower() in cols_map:
            return cols_map[nome.lower()]
    for c in df.columns:
        cl = str(c).strip().lower()
        for nome in nomes_possiveis:
            if nome.lower() in cl:
                return c
    if obrigatoria:
        raise ValueError(f"NÃ£o foi possÃ­vel localizar nenhuma das colunas esperadas: {nomes_possiveis}")
    return None


def renomear_colunas_equivalentes(df_base, df_novo):
    mapa_equivalencias = {
        "AIS": ["AISNova", "AIS Nova", "AIS_NOVA", "aisnova", "ais_nova"],
        "TerritÃ³rio": ["RegiÃµes", "Regioes", "RegiÃ£o", "Regiao", "regiÃµes", "regioes", "regiÃ£o", "regiao"]
    }
    colunas_base_map = {str(c).strip().lower(): c for c in df_base.columns}
    colunas_novo_map = {str(c).strip().lower(): c for c in df_novo.columns}
    renomeacoes = {}
    for coluna_base_oficial, aliases in mapa_equivalencias.items():
        chave_base = coluna_base_oficial.strip().lower()
        if chave_base not in colunas_base_map:
            continue
        nome_real_base = colunas_base_map[chave_base]
        if nome_real_base in df_novo.columns:
            continue
        for alias in aliases:
            chave_alias = alias.strip().lower()
            if chave_alias in colunas_novo_map:
                renomeacoes[colunas_novo_map[chave_alias]] = nome_real_base
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
    formatos = ["%H:%M:%S", "%H:%M"]
    for fmt in formatos:
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
    return df_novo[colunas_base]


def sem_acento(s):
    n = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in n if not unicodedata.combining(c)).upper().strip()


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


def _construir_base_enxuta(gpkg, parquet_saida):
    garantir_dependencias()
    import fiona
    from shapely.geometry import shape
    from pyproj import Transformer

    tr = Transformer.from_crs(f"EPSG:{EPSG_GPKG}", "EPSG:4326", always_xy=True)
    regs = []
    with fiona.open(gpkg, layer=LAYER_GPKG) as src:
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
    base = pd.DataFrame(regs, columns=["cod_mun", "nome_norm", "nome_orig", "lat", "lon", "tot_geral"])
    base.to_parquet(parquet_saida, index=False)
    return base


def carregar_base_geografica():
    if os.path.exists(CAMINHO_BASE_ENXUTA):
        return pd.read_parquet(CAMINHO_BASE_ENXUTA).reset_index(drop=True)
    if os.path.exists(CAMINHO_GPKG):
        return _construir_base_enxuta(CAMINHO_GPKG, CAMINHO_BASE_ENXUTA).reset_index(drop=True)
    return None


def carregar_municipios():
    if os.path.exists(ARQ_CACHE_MUN):
        try:
            return json.load(open(ARQ_CACHE_MUN, encoding="utf-8"))
        except Exception:
            pass
    url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{UF_CODIGO}/municipios"
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
        json.dump(mapa, open(ARQ_CACHE_MUN, "w", encoding="utf-8"))
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
        partes += [str(municipio).strip(), "CearÃ¡", "Brasil"]
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


class JanelaProgresso:
    def __init__(self, total):
        self.total = max(total, 1)
        self.root = tk.Toplevel()
        self.root.title("Processando geocodificaÃ§Ã£o")
        self.root.geometry("560x220")
        self.root.resizable(False, False)
        self.label_status = tk.Label(self.root, text="Iniciando processamento...")
        self.label_status.pack(pady=(15, 8))
        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=500, mode="determinate")
        self.progress.pack(pady=5)
        self.progress["maximum"] = 100
        self.label_percentual = tk.Label(self.root, text="0%")
        self.label_percentual.pack(pady=(8, 5))
        self.label_detalhe = tk.Label(self.root, text="Aguardando...")
        self.label_detalhe.pack(pady=(4, 4))
        self.label_contadores = tk.Label(self.root, text="Processados: 0 | Geocodificados: 0")
        self.label_contadores.pack(pady=(4, 5))
        self.root.update_idletasks()

    def atualizar(self, atual, texto="Processando...", detalhe="", processados=0, geocodificados=0):
        percentual = int((atual / self.total) * 100)
        self.progress["value"] = percentual
        self.label_status.config(text=texto)
        self.label_percentual.config(text=f"{percentual}%")
        self.label_detalhe.config(text=detalhe)
        self.label_contadores.config(text=f"Processados: {processados} | Geocodificados: {geocodificados}")
        self.root.update_idletasks()
        self.root.update()

    def fechar(self):
        try:
            if self.root.winfo_exists():
                self.root.destroy()
        except Exception:
            pass


def geocodificar_linhas_novas(df, col_lat_destino, col_lon_destino, root_master):
    motor = MotorGeocodificacaoSoberana()
    progresso = JanelaProgresso(len(df))
    progresso.root.transient(root_master)

    lats, lons, niveis, fontes, confirmados, distancias, ocorrencias = [], [], [], [], [], [], []
    geocodificados = 0

    try:
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
            ocorrencias.append(1)
            if r[0] is not None and r[1] is not None:
                geocodificados += 1
            progresso.atualizar(i, "Geocodificando linhas novas...", f"Linha {i} de {len(df)}", i, geocodificados)
    finally:
        progresso.fechar()

    df[col_lat_destino] = lats
    df[col_lon_destino] = lons
    df["Nivel_Geocodificacao"] = niveis
    df["Fonte"] = fontes
    df["_confirmado_base"] = confirmados
    df["_dist_validacao_m"] = distancias

    chave = df[col_lat_destino].round(6).astype(str) + "," + df[col_lon_destino].round(6).astype(str)
    cont = chave.value_counts()
    df["Ocorrencias_Mesmo_Ponto"] = chave.map(cont).fillna(1).astype(int)
    df["_loc_aproximada"] = (df["Ocorrencias_Mesmo_Ponto"] >= LIMIAR_SUSPEITO) & (df["numero_busca"].fillna("").astype(str).str.strip() == "")
    return df, geocodificados


def preparar_campos_geocodificacao(df, col_endereco, col_numero, col_bairro, col_municipio):
    df = df.copy()
    df["logradouro_busca"] = df[col_endereco].apply(limpar_logradouro)
    df["numero_busca"] = df[col_numero].apply(limpar_numero)
    df["bairro_busca"] = df.apply(lambda r: limpar_bairro(r[col_bairro], r[col_municipio]), axis=1)
    df["municipio_busca"] = df[col_municipio].fillna("").astype(str).str.strip()
    return df


def salvar_excel(df, caminho_saida):
    with pd.ExcelWriter(caminho_saida, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="CVP_SIP_ENDERECO")


def registrar_erro(exc):
    pasta_log = os.path.join(os.path.expanduser("~"), "logs_python_cvp")
    os.makedirs(pasta_log, exist_ok=True)
    caminho_log = os.path.join(pasta_log, f"erro_cvp_sip_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    with open(caminho_log, "w", encoding="utf-8") as f:
        f.write("ERRO NO PROCESSAMENTO\n")
        f.write(f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        f.write(f"Tipo: {type(exc).__name__}\n")
        f.write(f"Mensagem: {str(exc).strip() or 'ExceÃ§Ã£o sem mensagem textual.'}\n\n")
        f.write("TRACEBACK COMPLETO:\n")
        f.write(traceback.format_exc())
    return caminho_log


def processar():
    root = tk.Tk()
    root.withdraw()
    try:
        arquivo_01 = selecionar_arquivo("Selecione o Arquivo 01 - Base CVP")
        if not arquivo_01:
            messagebox.showwarning("Aviso", "Processo cancelado: Arquivo 01 nÃ£o selecionado.")
            return

        arquivo_02 = selecionar_arquivo("Selecione o Arquivo 02 - Complemento SIP")
        if not arquivo_02:
            messagebox.showwarning("Aviso", "Processo cancelado: Arquivo 02 nÃ£o selecionado.")
            return

        pasta_saida = selecionar_pasta_saida()
        if not pasta_saida:
            messagebox.showwarning("Aviso", "Processo cancelado: pasta de destino nÃ£o selecionada.")
            return

        df_base = pd.read_excel(arquivo_01)
        df_novo = pd.read_excel(arquivo_02)

        df_base = normalizar_colunas(df_base)
        df_novo = normalizar_colunas(df_novo)

        # O filtro por Natureza deve ser aplicado somente no Arquivo 02.
        df_novo = filtrar_por_natureza(df_novo, "ROUBO DE VEICULO")

        if df_base.empty:
            raise ValueError("O Arquivo 01 foi carregado, mas estÃ¡ sem registros.")
        if df_novo.empty:
            raise ValueError("ApÃ³s filtrar a coluna 'Natureza' por 'ROUBO DE VEICULO', o Arquivo 02 ficou sem registros.")

        col_data_base = encontrar_coluna_data_base(df_base)
        col_hora_base = encontrar_coluna_hora_base(df_base)
        col_datahora_novo = encontrar_coluna_datahora_arquivo_02(df_novo)

        col_lat_base = encontrar_coluna_por_nomes(df_base, ["lat", "latitude"], obrigatoria=True)
        col_lon_base = encontrar_coluna_por_nomes(df_base, ["lon", "long", "longitude"], obrigatoria=True)

        col_endereco = encontrar_coluna_por_nomes(df_novo, ["endereÃ§o", "endereco", "logradouro", "rua"], obrigatoria=True)
        col_numero = encontrar_coluna_por_nomes(df_novo, ["nÃºmero", "numero", "localNumero", "num"], obrigatoria=True)
        col_bairro = encontrar_coluna_por_nomes(df_novo, ["bairro"], obrigatoria=True)
        col_municipio = encontrar_coluna_por_nomes(df_novo, ["municÃ­pio", "municipio", "cidade"], obrigatoria=True)

        df_novo = renomear_colunas_equivalentes(df_base, df_novo)
        df_base = criar_datahora_base(df_base, col_data_base, col_hora_base)
        df_novo = criar_datahora_arquivo_02(df_novo, col_datahora_novo)

        ultimo_datahora_base = obter_ultimo_datahora(df_base, "__datahora__")
        total_antes_filtro_tempo = len(df_novo)
        df_novo_filtrado = filtrar_apenas_registros_posteriores(df_novo, "__datahora__", ultimo_datahora_base)
        removidos_por_datahora = total_antes_filtro_tempo - len(df_novo_filtrado)

        base_sem_aux = df_base.drop(columns=["__datahora__"])
        if "Nivel_Geocodificacao" not in base_sem_aux.columns:
            base_sem_aux["Nivel_Geocodificacao"] = pd.NA
        if "Fonte" not in base_sem_aux.columns:
            base_sem_aux["Fonte"] = pd.NA
        if "_confirmado_base" not in base_sem_aux.columns:
            base_sem_aux["_confirmado_base"] = pd.NA
        if "_dist_validacao_m" not in base_sem_aux.columns:
            base_sem_aux["_dist_validacao_m"] = pd.NA
        if "Ocorrencias_Mesmo_Ponto" not in base_sem_aux.columns:
            base_sem_aux["Ocorrencias_Mesmo_Ponto"] = pd.NA
        if "_loc_aproximada" not in base_sem_aux.columns:
            base_sem_aux["_loc_aproximada"] = pd.NA

        if ultimo_datahora_base is None:
            df_novo_util = df_novo.copy()
            situacao = "Base anterior sem Data/Hora vÃ¡lida: Arquivo 02 foi incluÃ­do integralmente."
        elif df_novo_filtrado.empty:
            df_novo_util = df_novo_filtrado.copy()
            situacao = "Nenhum registro novo encontrado apÃ³s a Ãºltima Data/Hora da base: Arquivo 01 foi mantido sem acrÃ©scimos."
        else:
            df_novo_util = df_novo_filtrado.copy()
            situacao = "Base anterior localizada: somente registros posteriores Ã  Ãºltima Data/Hora foram adicionados."

        adicionados = len(df_novo_util)
        geocodificados = 0

        if not df_novo_util.empty:
            df_novo_util = preparar_campos_geocodificacao(df_novo_util, col_endereco, col_numero, col_bairro, col_municipio)
            df_novo_util, geocodificados = geocodificar_linhas_novas(df_novo_util, col_lat_base, col_lon_base, root)
            df_novo_util = df_novo_util.drop(columns=[c for c in ["logradouro_busca", "numero_busca", "bairro_busca", "municipio_busca", "__datahora__"] if c in df_novo_util.columns])
            df_novo_util = alinhar_colunas_arquivo_02_com_base(base_sem_aux, df_novo_util)
            df_final = pd.concat([base_sem_aux, df_novo_util], ignore_index=True)
        else:
            df_final = base_sem_aux.copy()

        colunas_excluir_saida = [
            "Fonte",
            "_confirmado_base",
            "_dist_validacao_m",
            "Ocorrencias_Mesmo_Ponto",
            "_loc_aproximada"
        ]
        df_final = df_final.drop(columns=[c for c in colunas_excluir_saida if c in df_final.columns])

        df_final = criar_datahora_base(df_final, col_data_base, col_hora_base)
        df_final = df_final.sort_values(by="__datahora__", ascending=True, na_position="last").reset_index(drop=True)
        df_final = df_final.drop(columns=["__datahora__"])

        total_final = len(df_final)
        caminho_saida = os.path.join(pasta_saida, NOME_ARQUIVO_FINAL)
        salvar_excel(df_final, caminho_saida)

        ultima_ref = ultimo_datahora_base.strftime("%d/%m/%Y %H:%M:%S") if ultimo_datahora_base is not None else "sem referÃªncia anterior vÃ¡lida"
        messagebox.showinfo(
            "Sucesso",
            f"Processo Finalizado, adicionado {adicionados} CVP's novos, total de {total_final} CVP's.\n"
            f"Ãšltima Data/Hora da base: {ultima_ref}\n"
            f"Registros excluÃ­dos por serem anteriores/iguais Ã  Ãºltima Data/Hora da base: {removidos_por_datahora}\n"
            f"Registros geocodificados nas linhas novas: {geocodificados}\n\n"
            f"{situacao}\n\n"
            f"O arquivo serÃ¡ salvo com o nome\n{NOME_ARQUIVO_FINAL}"
        )

    except Exception as e:
        caminho_log = registrar_erro(e)
        messagebox.showerror(
            "Erro",
            f"Ocorreu um erro durante o processamento.\n\n"
            f"Tipo: {type(e).__name__}\n"
            f"Mensagem: {str(e).strip() or 'ExceÃ§Ã£o sem mensagem textual.'}\n\n"
            f"Log salvo em:\n{caminho_log}"
        )
    finally:
        try:
            root.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    processar()

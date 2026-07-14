# modulos/consolidar_indicadores_criminais.py

from __future__ import annotations

import calendar
import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st


# =========================================================
# CONFIGURAÇÃO
# =========================================================

INDICADORES_DISPONIVEIS = [
    "CVLI",
    "ARMA",
    "CVPCIOPS",
    "CVPSIP",
    "Orcrim",
    "Incêndio Vegetação",
    "Apreensão de Arma",
    "TRAFICO",
    "LESÃO",
    "Tentativa",
    "Lesão Corporal Dolosa",
    "Perturbação ao Sossego Alheio",
    "Grupo Criminoso",
    "Drone",
    "Infrator",
    "Extorsão",
    "Esbulho",
    "ExtorsãoSIP",
    "EsbulhoSIP",
    "Acidente de Trânsito",
    "Furto CIOPS",
    "Furto SIP",
]

COLUNAS_DATA_CANDIDATAS = ["DATA", "data", "Data", "Data Completa"]
COLUNAS_HORA_CANDIDATAS = ["Hora", "HORA", "hora"]
PREENCHIMENTO_COLUNA_AUSENTE = "NÃO LOCALIZADO"

INDICADORES_COM_CHAVE_INCREMENTAL = [
    "ARMA",
    "CVPCIOPS",
    "CVPSIP",
    "Orcrim",
    "Incêndio Vegetação",
    "Apreensão de Arma",
    "TRAFICO",
    "LESÃO",
    "Tentativa",
    "Lesão Corporal Dolosa",
    "Perturbação ao Sossego Alheio",
    "Grupo Criminoso",
    "Drone",
    "Infrator",
    "Extorsão",
    "Esbulho",
    "ExtorsãoSIP",
    "EsbulhoSIP",
    "Acidente de Trânsito",
    "Furto CIOPS",
    "Furto SIP",
]


# =========================================================
# MODELOS
# =========================================================

@dataclass
class ArquivoAbaLida:
    nome_arquivo: str
    indicador: str
    df_original: pd.DataFrame
    ordem_colunas_base: List[str]
    coluna_data_real: str
    coluna_hora_real: Optional[str]
    df_processado: pd.DataFrame
    dt_min: Optional[pd.Timestamp]
    dt_max: Optional[pd.Timestamp]


@dataclass
class ResultadoIndicador:
    indicador: str
    sucesso: bool
    mensagem: str
    df_consolidado: pd.DataFrame = field(default_factory=pd.DataFrame)
    df_completude: pd.DataFrame = field(default_factory=pd.DataFrame)
    df_auditoria: pd.DataFrame = field(default_factory=pd.DataFrame)
    arquivo_bytes: bytes = b""
    nome_arquivo_saida: str = ""
    total_arquivos_lidos: int = 0
    total_registros_saida: int = 0


# =========================================================
# UTILITÁRIOS
# =========================================================

def normalizar_texto(valor: str) -> str:
    if valor is None:
        return ""
    valor = str(valor).strip()
    valor = unicodedata.normalize("NFKD", valor)
    valor = "".join(c for c in valor if not unicodedata.combining(c))
    valor = valor.lower()
    valor = re.sub(r"\s+", " ", valor)
    return valor


def slugify(valor: str) -> str:
    base = normalizar_texto(valor)
    base = re.sub(r"[^a-z0-9]+", "_", base)
    base = re.sub(r"_+", "_", base).strip("_")
    return base or "arquivo"


def encontrar_nome_aba(sheet_names: List[str], indicador: str) -> Optional[str]:
    alvo = normalizar_texto(indicador)
    mapa = {normalizar_texto(nome): nome for nome in sheet_names}
    return mapa.get(alvo)


def encontrar_coluna_real(df: pd.DataFrame, candidatos: List[str]) -> Optional[str]:
    mapa_colunas = {normalizar_texto(col): col for col in df.columns}
    for c in candidatos:
        if normalizar_texto(c) in mapa_colunas:
            return mapa_colunas[normalizar_texto(c)]
    return None


def encontrar_coluna_por_nome_oficial(df: pd.DataFrame, nome_oficial: str) -> Optional[str]:
    alvo = normalizar_texto(nome_oficial)
    for col in df.columns:
        if normalizar_texto(col) == alvo:
            return col
    return None


def limpar_nome_colunas(df: pd.DataFrame) -> pd.DataFrame:
    novas = []
    usados = {}
    for col in df.columns:
        nome = str(col).strip()
        if not nome:
            nome = "coluna_sem_nome"
        if nome in usados:
            usados[nome] += 1
            nome = f"{nome}_{usados[nome]}"
        else:
            usados[nome] = 1
        novas.append(nome)
    df = df.copy()
    df.columns = novas
    return df


def normalizar_hora_para_6(valor) -> str:
    if pd.isna(valor):
        return "000000"
    txt = str(valor).strip()
    if txt.lower() in {"nan", "nat", "none", ""}:
        return "000000"
    txt = re.sub(r"\D", "", txt)
    if not txt:
        return "000000"
    txt = txt.zfill(6)
    return txt[:6]


def parse_data_segura(serie: pd.Series) -> pd.Series:
    return pd.to_datetime(serie, errors="coerce", dayfirst=False)


def montar_datetime(df: pd.DataFrame, col_data: str, col_hora: Optional[str]) -> pd.Series:
    datas = parse_data_segura(df[col_data])
    if col_hora and col_hora in df.columns:
        horas = df[col_hora].apply(normalizar_hora_para_6)
    else:
        horas = pd.Series(["000000"] * len(df), index=df.index)

    hh = horas.str[0:2]
    mm = horas.str[2:4]
    ss = horas.str[4:6]

    dt_str = (
        datas.dt.strftime("%Y-%m-%d").fillna("") + " " + hh + ":" + mm + ":" + ss
    )
    dt = pd.to_datetime(dt_str, errors="coerce")
    dt = dt.where(datas.notna(), pd.NaT)
    return dt


def preencher_colunas_ausentes(df: pd.DataFrame, ordem_base: List[str]) -> pd.DataFrame:
    df = df.copy()
    for col in ordem_base:
        if col not in df.columns:
            df[col] = PREENCHIMENTO_COLUNA_AUSENTE

    cols_extras = [c for c in df.columns if c not in ordem_base]
    return df[ordem_base + cols_extras]


def remover_linhas_vazias(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df.dropna(how="all").copy()


def identificar_coluna_vitima_cvli(df: pd.DataFrame) -> Optional[str]:
    candidatos = [
        "Nome da Vítima",
        "Nome da Vitima",
        "Nome Vítima",
        "Nome Vitima",
        "Nome",
    ]
    for candidato in candidatos:
        achada = encontrar_coluna_por_nome_oficial(df, candidato)
        if achada:
            return achada
    return None


def gerar_chave_cvli(df: pd.DataFrame, col_tombo: str, col_data: str, col_vitima: str) -> pd.Series:
    tombo = df[col_tombo].astype(str).fillna("").str.strip()
    data = pd.to_datetime(df[col_data], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
    vitima = df[col_vitima].astype(str).fillna("").str.strip().apply(normalizar_texto)
    return tombo + "||" + data + "||" + vitima


def gerar_chave_secundaria_incremental(df: pd.DataFrame) -> pd.Series:
    candidatos = []
    for nome in ["Natureza", "Ocorrência", "Ocorrencia", "Nome da Ocorrência", "Nome da Ocorrencia", "Tombo", "Município", "Municipio"]:
        col = encontrar_coluna_por_nome_oficial(df, nome)
        if col:
            candidatos.append(col)

    if not candidatos:
        candidatos = list(df.columns[: min(4, len(df.columns))])

    partes = []
    for col in candidatos:
        partes.append(df[col].astype(str).fillna("").str.strip().apply(normalizar_texto))

    chave = partes[0]
    for serie in partes[1:]:
        chave = chave + "||" + serie
    return chave


def ordenar_arquivos_por_periodo(abas_lidas: List[ArquivoAbaLida]) -> List[ArquivoAbaLida]:
    return sorted(
        abas_lidas,
        key=lambda x: (
            pd.Timestamp.max if x.dt_min is None or pd.isna(x.dt_min) else x.dt_min,
            x.nome_arquivo.lower(),
        ),
    )


def montar_resumo_completude(df: pd.DataFrame, coluna_data_real: str) -> pd.DataFrame:
    if df.empty or coluna_data_real not in df.columns:
        return pd.DataFrame(
            columns=[
                "Mes",
                "Dias no Mês",
                "Dias com Registro",
                "Dias Faltantes do Mês",
                "Dias faltantes do mês",
                "Quantidade de Dias Faltantes",
                "Quantidade de ocorrências no mês",
            ]
        )

    datas = pd.to_datetime(df[coluna_data_real], errors="coerce").dropna()
    if datas.empty:
        return pd.DataFrame(
            columns=[
                "Mes",
                "Dias no Mês",
                "Dias com Registro",
                "Dias Faltantes do Mês",
                "Dias faltantes do mês",
                "Quantidade de Dias Faltantes",
                "Quantidade de ocorrências no mês",
            ]
        )

    temp = df.copy()
    temp["_data_ref"] = pd.to_datetime(temp[coluna_data_real], errors="coerce")
    temp = temp[temp["_data_ref"].notna()].copy()
    temp["_mes"] = temp["_data_ref"].dt.to_period("M")

    linhas = []
    for mes_periodo, grupo in temp.groupby("_mes", sort=True):
        ano = mes_periodo.year
        mes = mes_periodo.month
        dias_mes = calendar.monthrange(ano, mes)[1]

        dias_presentes = sorted(grupo["_data_ref"].dt.day.dropna().astype(int).unique().tolist())
        qtd_dias_presentes = len(dias_presentes)
        qtd_faltantes = max(dias_mes - qtd_dias_presentes, 0)
        faltantes = "NÃO" if qtd_faltantes == 0 else "SIM"

        linhas.append(
            {
                "Mes": f"{ano:04d}-{mes:02d}",
                "Dias no Mês": dias_mes,
                "Dias com Registro": qtd_dias_presentes,
                "Dias Faltantes do Mês": faltantes,
                "Dias faltantes do mês": faltantes,
                "Quantidade de Dias Faltantes": qtd_faltantes,
                "Quantidade de ocorrências no mês": int(len(grupo)),
            }
        )

    return pd.DataFrame(linhas)


def montar_auditoria(
    indicador: str,
    abas_lidas: List[ArquivoAbaLida],
    consolidado: pd.DataFrame,
) -> pd.DataFrame:
    linhas = []
    for item in abas_lidas:
        linhas.append(
            {
                "Indicador": indicador,
                "Arquivo": item.nome_arquivo,
                "Aba": item.indicador,
                "Coluna de Data": item.coluna_data_real,
                "Coluna de Hora": item.coluna_hora_real or "",
                "Data Inicial": "" if item.dt_min is None or pd.isna(item.dt_min) else item.dt_min.strftime("%Y-%m-%d %H:%M:%S"),
                "Data Final": "" if item.dt_max is None or pd.isna(item.dt_max) else item.dt_max.strftime("%Y-%m-%d %H:%M:%S"),
                "Registros Lidos": len(item.df_processado),
            }
        )

    linhas.append(
        {
            "Indicador": indicador,
            "Arquivo": "TOTAL",
            "Aba": indicador,
            "Coluna de Data": "",
            "Coluna de Hora": "",
            "Data Inicial": "",
            "Data Final": "",
            "Registros Lidos": len(consolidado),
        }
    )
    return pd.DataFrame(linhas)


def exportar_excel_indicador(
    indicador: str,
    consolidado: pd.DataFrame,
    completude: pd.DataFrame,
    auditoria: pd.DataFrame,
) -> Tuple[bytes, str]:
    output = io.BytesIO()
    nome_saida = f"{slugify(indicador)}_consolidado.xlsx"

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        consolidado.to_excel(writer, index=False, sheet_name="consolidado")
        completude.to_excel(writer, index=False, sheet_name="completude_mensal")
        auditoria.to_excel(writer, index=False, sheet_name="auditoria")

    output.seek(0)
    return output.getvalue(), nome_saida


# =========================================================
# LEITURA E PREPARO
# =========================================================

def ler_aba_indicador(uploaded_file, indicador: str) -> Tuple[Optional[ArquivoAbaLida], Optional[str]]:
    try:
        xls = pd.ExcelFile(uploaded_file)
    except Exception as e:
        return None, f"Falha ao abrir o arquivo {uploaded_file.name}: {e}"

    nome_aba_real = encontrar_nome_aba(xls.sheet_names, indicador)
    if not nome_aba_real:
        return None, f"A aba '{indicador}' não foi localizada no arquivo {uploaded_file.name}."

    try:
        df = pd.read_excel(uploaded_file, sheet_name=nome_aba_real)
    except Exception as e:
        return None, f"Falha ao ler a aba '{indicador}' do arquivo {uploaded_file.name}: {e}"

    df = limpar_nome_colunas(df)
    df = remover_linhas_vazias(df)

    if df.empty:
        return None, f"A aba '{indicador}' do arquivo {uploaded_file.name} está vazia."

    coluna_data_real = encontrar_coluna_real(df, COLUNAS_DATA_CANDIDATAS)
    if not coluna_data_real:
        return None, (
            f"A aba '{indicador}' do arquivo {uploaded_file.name} não possui coluna de data reconhecida "
            f"entre: {', '.join(COLUNAS_DATA_CANDIDATAS)}."
        )

    coluna_hora_real = encontrar_coluna_real(df, COLUNAS_HORA_CANDIDATAS)

    df_proc = df.copy()
    df_proc["_data_oficial"] = pd.to_datetime(df_proc[coluna_data_real], errors="coerce")
    df_proc["_hora_oficial"] = (
        df_proc[coluna_hora_real].apply(normalizar_hora_para_6)
        if coluna_hora_real and coluna_hora_real in df_proc.columns
        else "000000"
    )
    df_proc["_datetime_oficial"] = montar_datetime(df_proc, coluna_data_real, coluna_hora_real)

    dt_min = df_proc["_datetime_oficial"].dropna().min() if df_proc["_datetime_oficial"].notna().any() else None
    dt_max = df_proc["_datetime_oficial"].dropna().max() if df_proc["_datetime_oficial"].notna().any() else None

    return (
        ArquivoAbaLida(
            nome_arquivo=uploaded_file.name,
            indicador=indicador,
            df_original=df,
            ordem_colunas_base=list(df.columns),
            coluna_data_real=coluna_data_real,
            coluna_hora_real=coluna_hora_real,
            df_processado=df_proc,
            dt_min=dt_min,
            dt_max=dt_max,
        ),
        None,
    )


# =========================================================
# CONSOLIDAÇÃO
# =========================================================

def consolidar_cvli(abas_lidas: List[ArquivoAbaLida]) -> Tuple[pd.DataFrame, str]:
    if not abas_lidas:
        return pd.DataFrame(), "Nenhum arquivo válido foi encontrado para o indicador CVLI."

    abas_lidas = ordenar_arquivos_por_periodo(abas_lidas)

    ordem_base = abas_lidas[0].ordem_colunas_base
    col_data = abas_lidas[0].coluna_data_real

    df_base = pd.DataFrame()
    chaves_existentes = set()

    for idx, item in enumerate(abas_lidas):
        df = item.df_processado.copy()
        df = preencher_colunas_ausentes(df, ordem_base)

        col_tombo = encontrar_coluna_por_nome_oficial(df, "Tombo")
        col_vitima = identificar_coluna_vitima_cvli(df)
        if not col_tombo or not col_vitima:
            return pd.DataFrame(), (
                f"Na aba CVLI do arquivo {item.nome_arquivo}, não foi possível localizar "
                f"as colunas obrigatórias 'Tombo' e/ou nome da vítima."
            )

        df["_chave_cvli"] = gerar_chave_cvli(df, col_tombo, item.coluna_data_real, col_vitima)
        df = df[df["_chave_cvli"].notna()].copy()

        if idx == 0:
            df_base = df.copy()
            chaves_existentes = set(df_base["_chave_cvli"].astype(str).tolist())
        else:
            novos = df[~df["_chave_cvli"].astype(str).isin(chaves_existentes)].copy()
            if not novos.empty:
                chaves_existentes.update(novos["_chave_cvli"].astype(str).tolist())
                df_base = pd.concat([df_base, novos], ignore_index=True)

    df_base = df_base.sort_values("_datetime_oficial", ascending=True, na_position="last").reset_index(drop=True)
    df_base = df_base[ordem_base].copy()
    return df_base, "Consolidação CVLI realizada com sucesso."


def consolidar_incremental(abas_lidas: List[ArquivoAbaLida]) -> Tuple[pd.DataFrame, str]:
    if not abas_lidas:
        return pd.DataFrame(), "Nenhum arquivo válido foi encontrado para o indicador."

    abas_lidas = ordenar_arquivos_por_periodo(abas_lidas)

    ordem_base = abas_lidas[0].ordem_colunas_base
    df_final = pd.DataFrame()
    ultimo_datetime = None

    for idx, item in enumerate(abas_lidas):
        df = item.df_processado.copy()
        df = preencher_colunas_ausentes(df, ordem_base)
        df = df.sort_values("_datetime_oficial", ascending=True, na_position="last").reset_index(drop=True)

        if idx == 0:
            df_final = df.copy()
            serie_validas = df_final["_datetime_oficial"].dropna()
            ultimo_datetime = serie_validas.max() if not serie_validas.empty else None
            continue

        if ultimo_datetime is not None:
            novos = df[df["_datetime_oficial"] > ultimo_datetime].copy()
        else:
            novos = df.copy()

        if not novos.empty:
            chave_sec = gerar_chave_secundaria_incremental(novos)
            novos["_chave_sec"] = chave_sec

            if not df_final.empty:
                ja_existentes = set(gerar_chave_secundaria_incremental(df_final).astype(str).tolist())
                novos = novos[~novos["_chave_sec"].astype(str).isin(ja_existentes)].copy()

            if not novos.empty:
                df_final = pd.concat([df_final, novos], ignore_index=True)
                serie_validas = df_final["_datetime_oficial"].dropna()
                ultimo_datetime = serie_validas.max() if not serie_validas.empty else ultimo_datetime

    df_final = df_final.sort_values("_datetime_oficial", ascending=True, na_position="last").reset_index(drop=True)
    df_final = df_final[ordem_base].copy()
    return df_final, "Consolidação incremental realizada com sucesso."


def processar_indicador(indicador: str, arquivos_excel) -> ResultadoIndicador:
    abas_validas = []
    erros = []

    for arq in arquivos_excel:
        aba_lida, erro = ler_aba_indicador(arq, indicador)
        if erro:
            erros.append(erro)
        elif aba_lida:
            abas_validas.append(aba_lida)

        try:
            arq.seek(0)
        except Exception:
            pass

    if not abas_validas:
        return ResultadoIndicador(
            indicador=indicador,
            sucesso=False,
            mensagem="Nenhuma aba válida encontrada para este indicador.",
            df_auditoria=pd.DataFrame({"Erro": erros}) if erros else pd.DataFrame(),
        )

    if indicador == "CVLI":
        consolidado, mensagem = consolidar_cvli(abas_validas)
    else:
        consolidado, mensagem = consolidar_incremental(abas_validas)

    if consolidado.empty:
        auditoria = montar_auditoria(indicador, abas_validas, consolidado)
        if erros:
            auditoria_erros = pd.DataFrame({"Erro": erros})
            auditoria = pd.concat([auditoria, auditoria_erros], axis=1)
        return ResultadoIndicador(
            indicador=indicador,
            sucesso=False,
            mensagem=mensagem,
            df_auditoria=auditoria,
        )

    completude = montar_resumo_completude(consolidado, abas_validas[0].coluna_data_real)
    auditoria = montar_auditoria(indicador, abas_validas, consolidado)

    if erros:
        auditoria_erros = pd.DataFrame({"Erro": erros})
        auditoria = pd.concat([auditoria.reset_index(drop=True), auditoria_erros.reset_index(drop=True)], axis=1)

    arquivo_bytes, nome_saida = exportar_excel_indicador(indicador, consolidado, completude, auditoria)

    return ResultadoIndicador(
        indicador=indicador,
        sucesso=True,
        mensagem=mensagem,
        df_consolidado=consolidado,
        df_completude=completude,
        df_auditoria=auditoria,
        arquivo_bytes=arquivo_bytes,
        nome_arquivo_saida=nome_saida,
        total_arquivos_lidos=len(abas_validas),
        total_registros_saida=len(consolidado),
    )


# =========================================================
# INTERFACE
# =========================================================

def renderizar_resumo_indicador(resultado: ResultadoIndicador):
    with st.expander(f"{resultado.indicador} - detalhes", expanded=False):
        c1, c2 = st.columns(2)
        c1.metric("Arquivos lidos", resultado.total_arquivos_lidos)
        c2.metric("Registros no consolidado", resultado.total_registros_saida)

        st.markdown("### Completude mensal")
        if not resultado.df_completude.empty:
            st.dataframe(resultado.df_completude, use_container_width=True)
        else:
            st.info("Não foi possível gerar o resumo de completude para este indicador.")

        st.markdown("### Auditoria")
        if not resultado.df_auditoria.empty:
            st.dataframe(resultado.df_auditoria, use_container_width=True)
        else:
            st.info("Sem informações adicionais de auditoria.")


def renderizar_downloads_em_grade(resultados_validos: List[ResultadoIndicador], colunas_grade: int = 3):
    st.markdown("### Downloads")
    for i in range(0, len(resultados_validos), colunas_grade):
        cols = st.columns(colunas_grade)
        bloco = resultados_validos[i:i + colunas_grade]
        for j, resultado in enumerate(bloco):
            with cols[j]:
                st.download_button(
                    label=f"Baixar {resultado.indicador}",
                    data=resultado.arquivo_bytes,
                    file_name=resultado.nome_arquivo_saida,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key=f"download_{slugify(resultado.indicador)}",
                )


def interface_consolidar_indicadores_criminais():
    st.markdown("## Consolidar Indicadores Criminais")

    st.caption(
        "Unifique arquivos de indicadores criminais por aba, preserve a ordem das colunas "
        "do primeiro arquivo válido e gere um arquivo final por indicador."
    )

    arquivos = st.file_uploader(
        "Selecione de 6 a 24 planilhas Excel",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
    )

    indicadores_selecionados = st.multiselect(
        "Selecione os indicadores a consolidar",
        options=INDICADORES_DISPONIVEIS,
        default=[],
    )

    executar = st.button("Executar", type="primary", use_container_width=True)

    if not executar:
        return

    if not arquivos:
        st.warning("Selecione pelo menos uma planilha Excel.")
        return

    if not indicadores_selecionados:
        st.warning("Selecione pelo menos um indicador criminal.")
        return

    total = len(indicadores_selecionados)
    barra_global = st.progress(0, text="Iniciando processamento...")
    placeholder_status = st.empty()

    resultados = []

    for idx, indicador in enumerate(indicadores_selecionados, start=1):
        placeholder_status.info(f"Processando {indicador} ({idx}/{total})...")
        resultado = processar_indicador(indicador, arquivos)
        resultados.append(resultado)

        progresso = int((idx / total) * 100)
        barra_global.progress(
            progresso,
            text=f"Processados {idx} de {total} indicadores",
        )

    placeholder_status.empty()
    st.success("Processamento finalizado.")

    resultados_validos = [r for r in resultados if r.sucesso]
    resultados_invalidos = [r for r in resultados if not r.sucesso]

    if resultados_validos:
        st.markdown("### Indicadores processados com sucesso")
        for r in resultados_validos:
            st.success(f"{r.indicador}: {r.mensagem}")
            renderizar_resumo_indicador(r)

        renderizar_downloads_em_grade(resultados_validos, colunas_grade=3)

    if resultados_invalidos:
        st.markdown("### Indicadores com erro ou sem dados válidos")
        for r in resultados_invalidos:
            st.error(f"{r.indicador}: {r.mensagem}")
            if not r.df_auditoria.empty:
                st.dataframe(r.df_auditoria, use_container_width=True)


# Alias compatível com app principal, se necessário
render = interface_consolidar_indicadores_criminais
interface_consolidar_indicadores_criminais = interface_consolidar_indicadores_criminais

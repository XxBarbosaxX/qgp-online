from __future__ import annotations

import calendar
import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import pandas as pd
import streamlit as st


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


@dataclass
class ArquivoAbaLida:
    nome_arquivo: str
    indicador: str
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
    total_meses: int = 0
    total_meses_incompletos: int = 0
    erros: List[str] = field(default_factory=list)


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
        achada = mapa_colunas.get(normalizar_texto(c))
        if achada:
            return achada
    return None


def encontrar_coluna_por_nome_oficial(df: pd.DataFrame, nome_oficial: str) -> Optional[str]:
    alvo = normalizar_texto(nome_oficial)
    for col in df.columns:
        if normalizar_texto(col) == alvo:
            return col
    return None


def identificar_coluna_vitima_cvli(df: pd.DataFrame) -> Optional[str]:
    candidatos = [
        "Nome da Vítima",
        "Nome da Vitima",
        "Nome Vítima",
        "Nome Vitima",
        "Nome",
    ]
    for candidato in candidatos:
        col = encontrar_coluna_por_nome_oficial(df, candidato)
        if col:
            return col
    return None


def limpar_nome_colunas(df: pd.DataFrame) -> pd.DataFrame:
    novas = []
    usados = {}
    for col in df.columns:
        nome = str(col).strip() if str(col).strip() else "coluna_sem_nome"
        if nome in usados:
            usados[nome] += 1
            nome = f"{nome}_{usados[nome]}"
        else:
            usados[nome] = 1
        novas.append(nome)
    df = df.copy()
    df.columns = novas
    return df


def remover_linhas_vazias(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df.dropna(how="all").copy()


def normalizar_hora_para_6(valor) -> str:
    if pd.isna(valor):
        return "000000"
    txt = str(valor).strip()
    if txt.lower() in {"", "nan", "nat", "none", "null"}:
        return "000000"
    txt = re.sub(r"\D", "", txt)
    if not txt:
        return "000000"
    txt = txt.zfill(6)
    return txt[:6]


def parse_data_segura(serie: pd.Series) -> pd.Series:
    return pd.to_datetime(serie, errors="coerce")


def montar_datetime(df: pd.DataFrame, col_data: str, col_hora: Optional[str]) -> pd.Series:
    datas = parse_data_segura(df[col_data])

    if col_hora and col_hora in df.columns:
        horas = df[col_hora].apply(normalizar_hora_para_6)
    else:
        horas = pd.Series(["000000"] * len(df), index=df.index)

    hh = horas.str[0:2]
    mm = horas.str[2:4]
    ss = horas.str[4:6]

    dt_str = datas.dt.strftime("%Y-%m-%d").fillna("") + " " + hh + ":" + mm + ":" + ss
    dt = pd.to_datetime(dt_str, errors="coerce")
    dt = dt.where(datas.notna(), pd.NaT)
    return dt


def preencher_colunas_ausentes(df: pd.DataFrame, ordem_base: List[str]) -> pd.DataFrame:
    df = df.copy()
    for col in ordem_base:
        if col not in df.columns:
            df[col] = PREENCHIMENTO_COLUNA_AUSENTE

    extras = [c for c in df.columns if c not in ordem_base]
    return df[ordem_base + extras]


def gerar_chave_cvli(df: pd.DataFrame, col_tombo: str, col_data: str, col_vitima: str) -> pd.Series:
    tombo = df[col_tombo].astype(str).fillna("").str.strip()
    data = pd.to_datetime(df[col_data], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
    vitima = df[col_vitima].astype(str).fillna("").str.strip().apply(normalizar_texto)
    return tombo + "||" + data + "||" + vitima


def gerar_chave_secundaria_incremental(df: pd.DataFrame) -> pd.Series:
    candidatos = []
    for nome in [
        "Natureza",
        "Ocorrência",
        "Ocorrencia",
        "Nome da Ocorrência",
        "Nome da Ocorrencia",
        "Tombo",
        "Município",
        "Municipio",
    ]:
        col = encontrar_coluna_por_nome_oficial(df, nome)
        if col:
            candidatos.append(col)

    if not candidatos:
        candidatos = list(df.columns[: min(4, len(df.columns))])

    partes = [df[col].astype(str).fillna("").str.strip().apply(normalizar_texto) for col in candidatos]
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


def criar_zip_resultados(resultados_validos: List[ResultadoIndicador]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in resultados_validos:
            zf.writestr(r.nome_arquivo_saida, r.arquivo_bytes)
    buffer.seek(0)
    return buffer.getvalue()


def ler_aba_indicador(uploaded_file, indicador: str) -> Tuple[Optional[ArquivoAbaLida], Optional[str]]:
    try:
        uploaded_file.seek(0)
        xls = pd.ExcelFile(uploaded_file)
    except Exception as e:
        return None, f"Falha ao abrir o arquivo {uploaded_file.name}: {e}"

    nome_aba_real = encontrar_nome_aba(xls.sheet_names, indicador)
    if not nome_aba_real:
        return None, f"A aba '{indicador}' não foi localizada no arquivo {uploaded_file.name}."

    try:
        uploaded_file.seek(0)
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

    serie_dt = df_proc["_datetime_oficial"].dropna()
    dt_min = serie_dt.min() if not serie_dt.empty else None
    dt_max = serie_dt.max() if not serie_dt.empty else None

    return (
        ArquivoAbaLida(
            nome_arquivo=uploaded_file.name,
            indicador=indicador,
            ordem_colunas_base=list(df.columns),
            coluna_data_real=coluna_data_real,
            coluna_hora_real=coluna_hora_real,
            df_processado=df_proc,
            dt_min=dt_min,
            dt_max=dt_max,
        ),
        None,
    )


def montar_resumo_completude(df: pd.DataFrame, coluna_data_real: str) -> pd.DataFrame:
    col_data = coluna_data_real if coluna_data_real in df.columns else None
    if df.empty or not col_data:
        return pd.DataFrame(
            columns=[
                "Mes",
                "Dias no Mês",
                "Dias com Registro",
                "Dias faltantes do mês",
                "Quantidade de Dias Faltantes",
                "Quantidade de ocorrências no mês",
            ]
        )

    temp = df.copy()
    temp["_data_ref"] = pd.to_datetime(temp[col_data], errors="coerce")
    temp = temp[temp["_data_ref"].notna()].copy()

    if temp.empty:
        return pd.DataFrame(
            columns=[
                "Mes",
                "Dias no Mês",
                "Dias com Registro",
                "Dias faltantes do mês",
                "Quantidade de Dias Faltantes",
                "Quantidade de ocorrências no mês",
            ]
        )

    temp["_mes"] = temp["_data_ref"].dt.to_period("M")
    linhas = []

    for mes_periodo, grupo in temp.groupby("_mes", sort=True):
        ano = mes_periodo.year
        mes = mes_periodo.month
        dias_mes = calendar.monthrange(ano, mes)[1]
        dias_com_registro = sorted(grupo["_data_ref"].dt.day.dropna().astype(int).unique().tolist())
        qtd_dias_registro = len(dias_com_registro)
        qtd_faltantes = max(dias_mes - qtd_dias_registro, 0)
        faltantes = "SIM" if qtd_faltantes > 0 else "NÃO"

        linhas.append(
            {
                "Mes": f"{ano:04d}-{mes:02d}",
                "Dias no Mês": dias_mes,
                "Dias com Registro": qtd_dias_registro,
                "Dias faltantes do mês": faltantes,
                "Quantidade de Dias Faltantes": qtd_faltantes,
                "Quantidade de ocorrências no mês": int(len(grupo)),
            }
        )

    return pd.DataFrame(linhas)


def montar_auditoria(indicador: str, abas_lidas: List[ArquivoAbaLida], consolidado: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for item in abas_lidas:
        linhas.append(
            {
                "Indicador": indicador,
                "Arquivo": item.nome_arquivo,
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


def consolidar_cvli(abas_lidas: List[ArquivoAbaLida]) -> Tuple[pd.DataFrame, str]:
    if not abas_lidas:
        return pd.DataFrame(), "Nenhum arquivo válido para CVLI."

    abas_lidas = ordenar_arquivos_por_periodo(abas_lidas)
    ordem_base = abas_lidas[0].ordem_colunas_base

    df_base = pd.DataFrame()
    chaves_existentes = set()

    for idx, item in enumerate(abas_lidas):
        df = preencher_colunas_ausentes(item.df_processado.copy(), ordem_base)

        col_tombo = encontrar_coluna_por_nome_oficial(df, "Tombo")
        col_vitima = identificar_coluna_vitima_cvli(df)
        if not col_tombo or not col_vitima:
            return pd.DataFrame(), (
                f"No arquivo {item.nome_arquivo}, a aba CVLI não contém as colunas obrigatórias "
                f"para deduplicação por Tombo + Data + Nome da Vítima."
            )

        df["_chave_cvli"] = gerar_chave_cvli(df, col_tombo, item.coluna_data_real, col_vitima)

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
    return df_base, "Consolidação de CVLI concluída com sucesso."


def consolidar_incremental(abas_lidas: List[ArquivoAbaLida]) -> Tuple[pd.DataFrame, str]:
    if not abas_lidas:
        return pd.DataFrame(), "Nenhum arquivo válido para o indicador."

    abas_lidas = ordenar_arquivos_por_periodo(abas_lidas)
    ordem_base = abas_lidas[0].ordem_colunas_base

    df_final = pd.DataFrame()
    ultimo_datetime = None

    for idx, item in enumerate(abas_lidas):
        df = preencher_colunas_ausentes(item.df_processado.copy(), ordem_base)
        df = df.sort_values("_datetime_oficial", ascending=True, na_position="last").reset_index(drop=True)

        if idx == 0:
            df_final = df.copy()
            validos = df_final["_datetime_oficial"].dropna()
            ultimo_datetime = validos.max() if not validos.empty else None
            continue

        if ultimo_datetime is not None:
            novos = df[df["_datetime_oficial"] > ultimo_datetime].copy()
        else:
            novos = df.copy()

        if not novos.empty:
            novos["_chave_sec"] = gerar_chave_secundaria_incremental(novos)

            if not df_final.empty:
                existentes = set(gerar_chave_secundaria_incremental(df_final).astype(str).tolist())
                novos = novos[~novos["_chave_sec"].astype(str).isin(existentes)].copy()

            if not novos.empty:
                df_final = pd.concat([df_final, novos], ignore_index=True)
                validos = df_final["_datetime_oficial"].dropna()
                if not validos.empty:
                    ultimo_datetime = validos.max()

    df_final = df_final.sort_values("_datetime_oficial", ascending=True, na_position="last").reset_index(drop=True)
    df_final = df_final[ordem_base].copy()
    return df_final, "Consolidação incremental concluída com sucesso."


def processar_indicador(indicador: str, arquivos_excel) -> ResultadoIndicador:
    abas_validas: List[ArquivoAbaLida] = []
    erros: List[str] = []

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
            erros=erros,
            df_auditoria=pd.DataFrame({"Erro": erros}) if erros else pd.DataFrame(),
        )

    if indicador == "CVLI":
        consolidado, mensagem = consolidar_cvli(abas_validas)
    else:
        consolidado, mensagem = consolidar_incremental(abas_validas)

    if consolidado.empty:
        auditoria = montar_auditoria(indicador, abas_validas, consolidado)
        return ResultadoIndicador(
            indicador=indicador,
            sucesso=False,
            mensagem=mensagem,
            erros=erros,
            df_auditoria=auditoria,
        )

    coluna_data_ref = abas_validas[0].coluna_data_real
    completude = montar_resumo_completude(consolidado, coluna_data_ref)
    auditoria = montar_auditoria(indicador, abas_validas, consolidado)
    arquivo_bytes, nome_saida = exportar_excel_indicador(indicador, consolidado, completude, auditoria)

    meses_incompletos = 0
    if not completude.empty and "Dias faltantes do mês" in completude.columns:
        meses_incompletos = int((completude["Dias faltantes do mês"] == "SIM").sum())

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
        total_meses=len(completude),
        total_meses_incompletos=meses_incompletos,
        erros=erros,
    )


def aplicar_estilo_local():
    st.markdown(
        """
        <style>
        .qgp-card {
            border: 1px solid rgba(120,120,120,0.20);
            border-radius: 14px;
            padding: 14px 16px;
            background: rgba(255,255,255,0.02);
            min-height: 110px;
        }
        .qgp-label {
            font-size: 0.86rem;
            color: #9aa0a6;
            margin-bottom: 6px;
        }
        .qgp-value {
            font-size: 1.45rem;
            font-weight: 700;
            line-height: 1.2;
        }
        .qgp-subvalue {
            font-size: 0.90rem;
            color: #b8bec5;
            margin-top: 6px;
        }
        .qgp-download-title {
            font-weight: 600;
            margin-top: 0.25rem;
            margin-bottom: 0.5rem;
        }
        .qgp-divider {
            margin-top: 0.5rem;
            margin-bottom: 0.75rem;
            border-top: 1px solid rgba(120,120,120,0.15);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_card(label: str, value: str, subvalue: str = ""):
    st.markdown(
        f"""
        <div class="qgp-card">
            <div class="qgp-label">{label}</div>
            <div class="qgp-value">{value}</div>
            <div class="qgp-subvalue">{subvalue}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_resumo_resultado(resultado: ResultadoIndicador):
    st.markdown(f"### {resultado.indicador}")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_card("Arquivos lidos", str(resultado.total_arquivos_lidos), "Planilhas válidas na aba")
    with c2:
        render_card("Registros finais", str(resultado.total_registros_saida), "Após consolidação")
    with c3:
        render_card("Meses identificados", str(resultado.total_meses), "Resumo mensal gerado")
    with c4:
        render_card("Meses incompletos", str(resultado.total_meses_incompletos), "Dias faltantes no calendário")

    with st.expander(f"Detalhes de {resultado.indicador}", expanded=False):
        if resultado.erros:
            st.warning("Ocorreram alertas durante a leitura:")
            for erro in resultado.erros:
                st.write(f"- {erro}")

        st.markdown("#### Completude mensal")
        if not resultado.df_completude.empty:
            st.dataframe(resultado.df_completude, use_container_width=True, hide_index=True)
        else:
            st.info("Sem dados suficientes para montar o resumo mensal.")

        st.markdown("#### Auditoria")
        if not resultado.df_auditoria.empty:
            st.dataframe(resultado.df_auditoria, use_container_width=True, hide_index=True)
        else:
            st.info("Sem informações de auditoria.")


def render_downloads_grid(resultados_validos: List[ResultadoIndicador], zip_bytes: Optional[bytes] = None):
    st.markdown("### Downloads")

    if zip_bytes:
        st.download_button(
            "Baixar pacote ZIP com todos os indicadores processados",
            data=zip_bytes,
            file_name="indicadores_consolidados.zip",
            mime="application/zip",
            use_container_width=True,
        )

    st.markdown('<div class="qgp-divider"></div>', unsafe_allow_html=True)

    colunas_grade = 3
    for i in range(0, len(resultados_validos), colunas_grade):
        cols = st.columns(colunas_grade)
        bloco = resultados_validos[i:i + colunas_grade]

        for j, resultado in enumerate(bloco):
            with cols[j]:
                st.markdown(f'<div class="qgp-download-title">{resultado.indicador}</div>', unsafe_allow_html=True)
                st.download_button(
                    label=f"Baixar {resultado.nome_arquivo_saida}",
                    data=resultado.arquivo_bytes,
                    file_name=resultado.nome_arquivo_saida,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key=f"download_{slugify(resultado.indicador)}",
                )


def interface_consolidar_indicadores_criminais():
    aplicar_estilo_local()

    st.caption(
        "Unifica várias planilhas de indicadores criminais por aba, preservando a ordem das colunas "
        "do primeiro arquivo válido, identificando meses incompletos e gerando um arquivo final por indicador."
    )

    arquivos = st.file_uploader(
        "Selecione de 6 a 24 planilhas Excel",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
    )

    indicadores = st.multiselect(
        "Selecione um ou mais indicadores criminais",
        options=INDICADORES_DISPONIVEIS,
        default=[],
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        executar = st.button("Executar consolidação", type="primary", use_container_width=True)
    with c2:
        limpar = st.button("Limpar seleção", use_container_width=True)

    if limpar:
        st.rerun()

    if not executar:
        return

    if not arquivos:
        st.warning("Selecione pelo menos uma planilha Excel.")
        return

    if not indicadores:
        st.warning("Selecione pelo menos um indicador criminal.")
        return

    total = len(indicadores)
    barra_global = st.progress(0, text="Preparando execução...")
    status = st.empty()
    resultados: List[ResultadoIndicador] = []

    for idx, indicador in enumerate(indicadores, start=1):
        status.info(f"Processando {indicador} ({idx}/{total})...")
        resultado = processar_indicador(indicador, arquivos)
        resultados.append(resultado)

        progresso = int((idx / total) * 100)
        barra_global.progress(progresso, text=f"Processados {idx} de {total} indicadores")

    status.empty()
    st.success("Processamento finalizado.")

    resultados_validos = [r for r in resultados if r.sucesso]
    resultados_invalidos = [r for r in resultados if not r.sucesso]

    if resultados_validos:
        total_arquivos = sum(r.total_arquivos_lidos for r in resultados_validos)
        total_registros = sum(r.total_registros_saida for r in resultados_validos)
        total_meses_incompletos = sum(r.total_meses_incompletos for r in resultados_validos)

        st.markdown("### Resumo geral")
        g1, g2, g3, g4 = st.columns(4)
        with g1:
            render_card("Indicadores com sucesso", str(len(resultados_validos)), "Arquivos gerados")
        with g2:
            render_card("Arquivos lidos", str(total_arquivos), "Somatório das abas válidas")
        with g3:
            render_card("Registros consolidados", str(total_registros), "Total em todos os indicadores")
        with g4:
            render_card("Meses incompletos", str(total_meses_incompletos), "Somatório geral")

        for resultado in resultados_validos:
            render_resumo_resultado(resultado)

        zip_bytes = criar_zip_resultados(resultados_validos) if len(resultados_validos) > 1 else None
        render_downloads_grid(resultados_validos, zip_bytes=zip_bytes)

    if resultados_invalidos:
        st.markdown("### Indicadores com falha")
        for r in resultados_invalidos:
            st.error(f"{r.indicador}: {r.mensagem}")
            if r.erros:
                for erro in r.erros:
                    st.write(f"- {erro}")
            if not r.df_auditoria.empty:
                st.dataframe(r.df_auditoria, use_container_width=True, hide_index=True)


render = interface_consolidar_indicadores_criminais

"""
Módulo TODOS OS INDICADORES
Processamento consolidado de múltiplos indicadores
Chama os módulos individuais com suas lógicas reais (incluindo geocodificação).
"""
from __future__ import annotations

import zipfile
from io import BytesIO
from datetime import datetime

import pandas as pd
import streamlit as st

from modulos.cvli import ProcessadorCVLI
from modulos.cvp_sip import processar_cvp_sip
from modulos.perturbacao_sossego import processar_perturbacao_sossego
from modulos.deslocamento_forcado import processar_deslocamento_forcado
from modulos.roubo_veiculo_sportal import processar_roubo_veiculo_sportal
from modulos.roubo_veiculo_sip import processar_roubo_veiculo_sip
from modulos.acidente_transito import processar_acidente_transito
from modulos.furto_veiculo_sportal import processar_furto_veiculo_sportal
from modulos.furto_veiculo_sip import processar_furto_veiculo_sip
from modulos.utils import (
    nome_arquivo_padrao,
    gerar_arquivo_excel,
    normalizar_colunas,
    encontrar_coluna_data,
    encontrar_coluna_hora,
    encontrar_coluna_por_nomes,
    renomear_colunas_equivalentes,
    alinhar_colunas_com_base,
    criar_coluna_datahora,
    excluir_coordenadas_invalidas,
    converter_coordenadas_para_wgs84_auto,
    obter_ultima_datahora,
    filtrar_apenas_registros_posteriores,
)



# ── Configuração dos indicadores ──────────────────────────────────────────────

INDICADORES_CONFIG = {
    "CVLI": {
        "label": "CVLI - Crimes Violentos Letais Intencionais",
        "key": "cvli",
        "nome_arquivo": f"1-CVLI-{datetime.now().year}-QGP.xlsx",
        "geocodifica": False,
        "grupo": "Crime Violento",
    },
    "CVP (SPORTAL)": {
        "label": "CVP (SPORTAL)",
        "key": "cvp_sportal",
        "nome_arquivo": nome_arquivo_padrao(2, "CVP-SPORTAL"),
        "geocodifica": False,
        "grupo": "Crime Violento",
    },
    "CVP (SIP)": {
        "label": "CVP (SIP)",
        "key": "cvp_sip",
        "nome_arquivo": nome_arquivo_padrao(3, "CVP-SIP-ENDERECO"),
        "geocodifica": True,
        "grupo": "Crime Violento",
    },
    "PERTURBAÇÃO DO SOSSEGO": {
        "label": "Perturbação ao Sossego Alheio",
        "key": "perturbacao_sossego",
        "nome_arquivo": nome_arquivo_padrao(3, "PERTURBACAO-SOSSEGO-ALHEIO"),
        "geocodifica": False,
        "grupo": "Outros",
    },
    "DESLOCAMENTO FORÇADO": {
        "label": "Deslocamento Forçado",
        "key": "deslocamento_forcado",
        "nome_arquivo": nome_arquivo_padrao(5, "DESLOCAMENTO-FORCADO"),
        "geocodifica": False,
        "grupo": "Outros",
    },
    "ROUBO DE VEÍCULO (SPORTAL)": {
        "label": "Roubo de Veículo (SPORTAL)",
        "key": "roubo_sportal",
        "nome_arquivo": nome_arquivo_padrao(6, "ROUBO-DE-VEICULO-SPORTAL-LAT-LONG"),
        "geocodifica": False,
        "grupo": "Patrimônio",
    },
    "ROUBO DE VEÍCULO (SIP)": {
        "label": "Roubo de Veículo (SIP)",
        "key": "roubo_sip",
        "nome_arquivo": nome_arquivo_padrao(7, "ROUBO-DE-VEICULO-SIP-ENDERECO"),
        "geocodifica": True,
        "grupo": "Patrimônio",
    },
    "ACIDENTE DE TRÂNSITO": {
        "label": "Acidente de Trânsito",
        "key": "acidente_transito",
        "nome_arquivo": nome_arquivo_padrao(8, "ACIDENTE-DE-TRANSITO-SPORTAL-QGP"),
        "geocodifica": False,
        "grupo": "Outros",
    },
    "FURTO DE VEÍCULO (SPORTAL)": {
        "label": "Furto de Veículo (SPORTAL)",
        "key": "furto_sportal",
        "nome_arquivo": nome_arquivo_padrao(9, "FURTO-DE-VEICULO-SPORTAL-QGP"),
        "geocodifica": False,
        "grupo": "Patrimônio",
    },
    "FURTO DE VEÍCULO (SIP)": {
        "label": "Furto de Veículo (SIP)",
        "key": "furto_sip",
        "nome_arquivo": nome_arquivo_padrao(7, "FURTO-DE-VEICULO-SIP-ENDERECO"),
        "geocodifica": True,
        "grupo": "Patrimônio",
    },
}

GRUPOS = {
    "Crime Violento": ["CVLI", "CVP (SPORTAL)", "CVP (SIP)"],
    "Patrimônio": [
        "ROUBO DE VEÍCULO (SPORTAL)",
        "ROUBO DE VEÍCULO (SIP)",
        "FURTO DE VEÍCULO (SPORTAL)",
        "FURTO DE VEÍCULO (SIP)",
    ],
    "Outros": [
        "PERTURBAÇÃO DO SOSSEGO",
        "DESLOCAMENTO FORÇADO",
        "ACIDENTE DE TRÂNSITO",
    ],
}



# ── Wrapper CVP SPORTAL ────────────────────────────────────────────────────────────

def _processar_cvp_sportal(buf_01: BytesIO, buf_02: BytesIO):
    """Replica a lógica de processamento do cvp_sportal sem a UI Streamlit."""
    buf_01.seek(0)
    buf_02.seek(0)
    df_base = pd.read_excel(buf_01)
    df_novo = pd.read_excel(buf_02)
    df_base = normalizar_colunas(df_base)
    df_novo = normalizar_colunas(df_novo)
    col_data_base = encontrar_coluna_data(df_base)
    col_data_novo = encontrar_coluna_data(df_novo)
    col_hora_base = encontrar_coluna_hora(df_base)
    col_hora_novo = encontrar_coluna_hora(df_novo)
    if col_data_base and col_data_novo and col_data_base != col_data_novo:
        df_novo = df_novo.rename(columns={col_data_novo: col_data_base})
    if col_hora_base and col_hora_novo and col_hora_base != col_hora_novo:
        df_novo = df_novo.rename(columns={col_hora_novo: col_hora_base})
    col_data = col_data_base
    col_hora = col_hora_base
    col_lat_base = encontrar_coluna_por_nomes(df_base, ["lat", "latitude"], obrigatoria=False)
    col_lon_base = encontrar_coluna_por_nomes(df_base, ["long", "longitude", "lon"], obrigatoria=False)
    col_lat_novo = encontrar_coluna_por_nomes(df_novo, ["latitude"], obrigatoria=False)
    col_lon_novo = encontrar_coluna_por_nomes(df_novo, ["longitude"], obrigatoria=False)
    df_novo = renomear_colunas_equivalentes(df_base, df_novo)
    total_lido = len(df_novo)
    if col_lat_novo and col_lon_novo:
        df_novo = excluir_coordenadas_invalidas(df_novo, col_lat_novo, col_lon_novo)
    removidos_invalidos = total_lido - len(df_novo)
    df_base = criar_coluna_datahora(df_base, col_data, col_hora, "datahora")
    df_novo = criar_coluna_datahora(df_novo, col_data, col_hora, "datahora")
    ultima_dh = obter_ultima_datahora(df_base, "datahora")
    total_antes = len(df_novo)
    df_novo_filtrado = filtrar_apenas_registros_posteriores(df_novo, "datahora", ultima_dh)
    removidos_datahora = total_antes - len(df_novo_filtrado)
    base_sem_aux = df_base.drop(columns=["datahora"], errors="ignore").copy()
    if ultima_dh is None:
        df_novo_util = df_novo.drop(columns=["datahora"], errors="ignore").copy()
        situacao = "Base anterior sem Data/Hora válida - Arquivo 02 incluído integralmente."
    elif df_novo_filtrado.empty:
        df_novo_util = df_novo_filtrado.drop(columns=["datahora"], errors="ignore").copy()
        situacao = "Nenhum registro novo encontrado após a última Data/Hora da base."
    else:
        df_novo_util = df_novo_filtrado.drop(columns=["datahora"], errors="ignore").copy()
        situacao = "Somente registros posteriores à última Data/Hora foram adicionados."
    adicionados = len(df_novo_util)
    if not df_novo_util.empty and col_lat_novo and col_lon_novo and col_lat_base and col_lon_base:
        df_novo_util = converter_coordenadas_para_wgs84_auto(
            df_novo_util,
            col_y_or_lat=col_lat_novo,
            col_x_or_lon=col_lon_novo,
            col_lat_destino=col_lat_base,
            col_lon_destino=col_lon_base,
        )
    if not df_novo_util.empty:
        df_novo_util = alinhar_colunas_com_base(base_sem_aux, df_novo_util)
        df_final = pd.concat([base_sem_aux, df_novo_util], ignore_index=True)
    else:
        df_final = base_sem_aux.copy()
    df_final = criar_coluna_datahora(df_final, col_data, col_hora, "datahora")
    df_final = df_final.sort_values("datahora", ascending=True, na_position="last").reset_index(drop=True)
    df_final = df_final.drop(columns=["datahora"], errors="ignore")
    resumo = {
        "adicionados": adicionados,
        "total_final": len(df_final),
        "geocodificados": 0,
        "removidos_invalidos": removidos_invalidos,
        "removidos_datahora": removidos_datahora,
        "ultima_datahora_base": ultima_dh.strftime("%d/%m/%Y %H:%M:%S") if ultima_dh else "N/A",
        "situacao": situacao,
    }
    return df_final, resumo



# ── Dispatcher central ────────────────────────────────────────────────────────────────

def _chamar_processador(nome_indicador: str, buf_01: BytesIO, buf_02: BytesIO):
    """Chama a função de processamento correta para cada indicador."""
    buf_01.seek(0)
    buf_02.seek(0)
    if nome_indicador == "CVLI":
        proc = ProcessadorCVLI()
        res = proc.processar(buf_01, buf_02)
        if not res["sucesso"]:
            raise ValueError(res["erro"])
        df = res["df_final"]
        resumo = {
            "adicionados": res.get("adicionados", 0),
            "total_final": res.get("total_final", len(df)),
            "geocodificados": 0,
            "situacao": "Atualizado" if res.get("houve_substituicao") else "Complementado",
        }
        return df, resumo
    elif nome_indicador == "CVP (SPORTAL)":
        return _processar_cvp_sportal(buf_01, buf_02)
    elif nome_indicador == "CVP (SIP)":
        return processar_cvp_sip(buf_01, buf_02)
    elif nome_indicador == "PERTURBAÇÃO DO SOSSEGO":
        return processar_perturbacao_sossego(buf_01, buf_02)
    elif nome_indicador == "DESLOCAMENTO FORÇADO":
        return processar_deslocamento_forcado(buf_01, buf_02)
    elif nome_indicador == "ROUBO DE VEÍCULO (SPORTAL)":
        return processar_roubo_veiculo_sportal(buf_01, buf_02)
    elif nome_indicador == "ROUBO DE VEÍCULO (SIP)":
        return processar_roubo_veiculo_sip(buf_01, buf_02)
    elif nome_indicador == "ACIDENTE DE TRÂNSITO":
        return processar_acidente_transito(buf_01, buf_02)
    elif nome_indicador == "FURTO DE VEÍCULO (SPORTAL)":
        return processar_furto_veiculo_sportal(buf_01, buf_02)
    elif nome_indicador == "FURTO DE VEÍCULO (SIP)":
        return processar_furto_veiculo_sip(buf_01, buf_02)
    else:
        raise ValueError(f"Indicador desconhecido: {nome_indicador}")


def _df_para_excel(df: pd.DataFrame, sheet_name: str = "Dados") -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    buf.seek(0)
    return buf.getvalue()


# ── Inicialização de estado ──────────────────────────────────────────────────────────────

def _init_state():
    defaults = {
        "todos_arq01_bytes": {},
        "todos_arq01_nomes": {},
        "todos_arq02_bytes": None,
        "todos_arq02_nome": None,
        "todos_resultados_excel": {},
        "todos_resumos": {},
        "todos_erros": {},
        "todos_processando": False,
        "todos_parar": False,
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


# ── Interface principal ──────────────────────────────────────────────────────────────

def interface_todos_indicadores():
    """Interface principal do módulo TODOS OS INDICADORES"""
    _init_state()
    st.title("Processamento Consolidado")
    st.markdown("### TODOS OS INDICADORES")
    st.info(
        "Este módulo processa múltiplos indicadores sequencialmente, "
        "chamando cada módulo individual com sua lógica completa "
        "(incluindo geocodificação onde aplicável)."
    )
    st.divider()

    # ── Arquivo 02 único para todos ──
    st.subheader("Arquivo 02 - Complemento único (compartilhado por todos)")
    st.caption(
        "O Arquivo 02 contém as abas de cada indicador. "
        "Cada módulo seleciona automaticamente a aba correspondente."
    )
    arquivo_02_upload = st.file_uploader(
        "Arquivo 02 (Excel com múltiplas abas)",
        type=["xlsx", "xls"],
        key="todos_upload_02",
    )
    if arquivo_02_upload is not None:
        arquivo_02_upload.seek(0)
        st.session_state.todos_arq02_bytes = arquivo_02_upload.read()
        st.session_state.todos_arq02_nome = arquivo_02_upload.name

    if st.session_state.todos_arq02_nome:
        st.success(f"Arquivo 02 carregado: {st.session_state.todos_arq02_nome}")
    st.divider()

    # ── Arquivos 01 por indicador ──
    st.subheader("Arquivos 01 - Base Histórica (um por indicador)")
    tab_cv, tab_pat, tab_out = st.tabs(["Crime Violento", "Patrimônio", "Outros"])
    tabs_grupos = {
        "Crime Violento": tab_cv,
        "Patrimônio": tab_pat,
        "Outros": tab_out,
    }
    for grupo, tab in tabs_grupos.items():
        with tab:
            for nome_ind in GRUPOS[grupo]:
                cfg = INDICADORES_CONFIG[nome_ind]
                geo_tag = " [GEOCODIFICAÇÃO]" if cfg["geocodifica"] else ""
                arq = st.file_uploader(
                    f"{cfg['label']}{geo_tag}",
                    type=["xlsx", "xls"],
                    key=f"todos_upload_01_{cfg['key']}",
                )
                if arq is not None:
                    arq.seek(0)
                    st.session_state.todos_arq01_bytes[nome_ind] = arq.read()
                    st.session_state.todos_arq01_nomes[nome_ind] = arq.name
                if nome_ind in st.session_state.todos_arq01_nomes:
                    st.caption(f"Carregado: {st.session_state.todos_arq01_nomes[nome_ind]}")
    st.divider()


    # ── Botões de controle ──
    indicadores_prontos = [
        nome for nome in INDICADORES_CONFIG
        if nome in st.session_state.todos_arq01_bytes
    ]
    tem_arq02 = st.session_state.todos_arq02_bytes is not None

    if indicadores_prontos:
        st.success(
            f"{len(indicadores_prontos)} indicador(es) com Arquivo 01 carregado: "
            + ", ".join(indicadores_prontos)
        )
    else:
        st.warning("Nenhum Arquivo 01 carregado ainda.")

    if not tem_arq02:
        st.warning("Arquivo 02 não carregado.")

    pode_processar = len(indicadores_prontos) > 0 and tem_arq02

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        iniciar = st.button(
            "Processar Todos os Indicadores",
            type="primary",
            use_container_width=True,
            disabled=not pode_processar or st.session_state.todos_processando,
        )
    with col_btn2:
        if st.button(
            "PARAR PROCESSO",
            type="secondary",
            use_container_width=True,
            disabled=not st.session_state.todos_processando,
        ):
            st.session_state.todos_parar = True
            st.warning("Sinalizando parada...")

    if iniciar:
        st.session_state.todos_resultados_excel = {}
        st.session_state.todos_resumos = {}
        st.session_state.todos_erros = {}
        st.session_state.todos_processando = True
        st.session_state.todos_parar = False

        total = len(indicadores_prontos)
        progresso = st.progress(0)
        status = st.empty()
        resultados_linha = []

        for idx, nome_ind in enumerate(indicadores_prontos):
            if st.session_state.todos_parar:
                status.warning("Processo interrompido pelo usuário.")
                break

            cfg = INDICADORES_CONFIG[nome_ind]
            status.info(
                f"[{idx+1}/{total}] Processando: {cfg['label']}..."
                + (" (geocodificando, aguarde)" if cfg["geocodifica"] else "")
            )

            try:
                buf_01 = BytesIO(st.session_state.todos_arq01_bytes[nome_ind])
                buf_02 = BytesIO(st.session_state.todos_arq02_bytes)
                df_final, resumo = _chamar_processador(nome_ind, buf_01, buf_02)
                excel_bytes = _df_para_excel(df_final, sheet_name=nome_ind[:31])
                st.session_state.todos_resultados_excel[nome_ind] = (
                    excel_bytes,
                    cfg["nome_arquivo"],
                )
                st.session_state.todos_resumos[nome_ind] = resumo
                resultados_linha.append({
                    "Indicador": cfg["label"],
                    "Status": "Sucesso",
                    "Adicionados": resumo.get("adicionados", 0),
                    "Total Final": resumo.get("total_final", 0),
                    "Geocodificados": resumo.get("geocodificados", 0),
                    "Situacao": resumo.get("situacao", ""),
                })
            except Exception as exc:
                st.session_state.todos_erros[nome_ind] = str(exc)
                resultados_linha.append({
                    "Indicador": cfg["label"],
                    "Status": "ERRO",
                    "Adicionados": 0,
                    "Total Final": 0,
                    "Geocodificados": 0,
                    "Situacao": str(exc),
                })

            progresso.progress((idx + 1) / total)

        st.session_state.todos_processando = False
        status.success("Processamento concluído!")

        if resultados_linha:
            st.divider()
            st.subheader("Resultados")
            st.dataframe(pd.DataFrame(resultados_linha), use_container_width=True)

    # ── Downloads individuais ──
    if st.session_state.todos_resultados_excel:
        st.divider()
        st.subheader("Downloads Individuais")
        for nome_ind, (excel_bytes, nome_arq) in st.session_state.todos_resultados_excel.items():
            resumo = st.session_state.todos_resumos.get(nome_ind, {})
            cfg = INDICADORES_CONFIG[nome_ind]
            with st.expander(f"{cfg['label']} - Adicionados: {resumo.get('adicionados', 0)} | Total: {resumo.get('total_final', 0)}"):
                st.caption(resumo.get("situacao", ""))
                st.download_button(
                    label=f"Baixar {nome_arq}",
                    data=excel_bytes,
                    file_name=nome_arq,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"todos_dl_{cfg['key']}",
                )

        # ── Download ZIP com tudo ──
        st.divider()
        zip_buf = BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for nome_ind, (excel_bytes, nome_arq) in st.session_state.todos_resultados_excel.items():
                zf.writestr(nome_arq, excel_bytes)
        zip_buf.seek(0)
        st.download_button(
            label=f"Baixar ZIP com todos os indicadores ({len(st.session_state.todos_resultados_excel)} arquivos)",
            data=zip_buf.getvalue(),
            file_name=f"QGP-TODOS-INDICADORES-{datetime.now().year}.zip",
            mime="application/zip",
            use_container_width=True,
            key="todos_dl_zip",
        )

    # ── Erros ──
    if st.session_state.todos_erros:
        st.divider()
        st.subheader("Erros")
        for nome_ind, erro in st.session_state.todos_erros.items():
            cfg = INDICADORES_CONFIG[nome_ind]
            st.error(f"{cfg['label']}: {erro}")



# Alias de compatibilidade
ProcessadorTodosIndicadores = interface_todos_indicadores

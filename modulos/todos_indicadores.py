"""
Módulo Todos os Indicadores - Orquestrador principal do QGP Online.

Estratégia de estabilidade:
- evita armazenar bytes grandes em st.session_state;
- usa apenas objetos de upload do ciclo atual;
- mantém em sessão somente estado leve;
- executa um indicador por vez;
- preserva o resultado original devolvido por cada módulo;
- evita padronização destrutiva de colunas.
"""

from __future__ import annotations

import importlib
import io
import re
import traceback
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

import pandas as pd
import streamlit as st

from modulos.utils import nome_arquivo_padrao


@dataclass(frozen=True)
class IndicadorDef:
    chave: str
    ordem: int
    titulo: str
    tokens_obrigatorios: list[str]
    modulo: str
    funcao: str
    nome_saida: str
    ordem_arquivos: str = "mestre_primeiro"


INDICADORES: list[IndicadorDef] = [
    IndicadorDef(
        chave="cvli",
        ordem=1,
        titulo="CVLI",
        tokens_obrigatorios=["CVLI", "QGP"],
        modulo="cvli",
        funcao="processar_cvli",
        nome_saida=nome_arquivo_padrao(1, "CVLI"),
        ordem_arquivos="mestre_primeiro",
    ),
    IndicadorDef(
        chave="cvp_sportal",
        ordem=2,
        titulo="CVP Sportal",
        tokens_obrigatorios=["CVP", "SPORTAL", "QGP"],
        modulo="cvp_sportal",
        funcao="processar_cvp_sportal",
        nome_saida=nome_arquivo_padrao(2, "CVP-SPORTAL"),
        ordem_arquivos="consolidado_primeiro",
    ),
    IndicadorDef(
        chave="cvp_sip",
        ordem=3,
        titulo="CVP SIP Endereço",
        tokens_obrigatorios=["CVP", "SIP", "ENDERECO", "QGP"],
        modulo="cvp_sip",
        funcao="processar_cvp_sip",
        nome_saida=nome_arquivo_padrao(3, "CVP-SIP-ENDERECO"),
        ordem_arquivos="consolidado_primeiro",
    ),
    IndicadorDef(
        chave="perturbacao_sossego",
        ordem=4,
        titulo="Perturbação ao Sossego Alheio",
        tokens_obrigatorios=["PERTURBACAO", "SOSSEGO", "ALHEIO", "QGP"],
        modulo="perturbacao_sossego",
        funcao="processar_perturbacao_sossego",
        nome_saida=nome_arquivo_padrao(4, "PERTURBACAO-AO-SOSSEGO-ALHEIO"),
        ordem_arquivos="consolidado_primeiro",
    ),
    IndicadorDef(
        chave="deslocamento_forcado",
        ordem=5,
        titulo="Deslocamento Forçado",
        tokens_obrigatorios=["DESLOCAMENTO", "FORCADO", "QGP"],
        modulo="deslocamento_forcado",
        funcao="processar_deslocamento_forcado",
        nome_saida=nome_arquivo_padrao(5, "DESLOCAMENTO-FORCADO"),
        ordem_arquivos="mestre_primeiro",
    ),
    IndicadorDef(
        chave="roubo_veiculo_sportal",
        ordem=6,
        titulo="Roubo de Veículo Sportal",
        tokens_obrigatorios=["ROUBO", "VEICULO", "SPORTAL", "LAT", "LONG", "QGP"],
        modulo="roubo_veiculo_sportal",
        funcao="processar_roubo_veiculo_sportal",
        nome_saida=nome_arquivo_padrao(6, "ROUBO-DE-VEICULO-SPORTAL-LAT-LONG"),
        ordem_arquivos="consolidado_primeiro",
    ),
    IndicadorDef(
        chave="roubo_veiculo_sip",
        ordem=7,
        titulo="Roubo de Veículo SIP Endereço",
        tokens_obrigatorios=["ROUBO", "VEICULO", "SIP", "ENDERECO", "QGP"],
        modulo="roubo_veiculo_sip",
        funcao="processar_roubo_veiculo_sip",
        nome_saida=nome_arquivo_padrao(7, "ROUBO-DE-VEICULO-SIP-ENDERECO"),
        ordem_arquivos="consolidado_primeiro",
    ),
    IndicadorDef(
        chave="acidente_transito",
        ordem=8,
        titulo="Acidente de Trânsito Sportal",
        tokens_obrigatorios=["ACIDENTE", "TRANSITO", "SPORTAL", "QGP"],
        modulo="acidente_transito",
        funcao="processar_acidente_transito",
        nome_saida=nome_arquivo_padrao(8, "ACIDENTE-DE-TRANSITO-SPORTAL-QGP"),
        ordem_arquivos="mestre_primeiro",
    ),
    IndicadorDef(
        chave="furto_veiculo_sportal",
        ordem=9,
        titulo="Furto de Veículo Sportal",
        tokens_obrigatorios=["FURTO", "VEICULO", "SPORTAL", "QGP"],
        modulo="furto_veiculo_sportal",
        funcao="processar_furto_veiculo_sportal",
        nome_saida=nome_arquivo_padrao(9, "FURTO-DE-VEICULO-SPORTAL"),
        ordem_arquivos="consolidado_primeiro",
    ),
    IndicadorDef(
        chave="furto_veiculo_sip",
        ordem=10,
        titulo="Furto de Veículo SIP",
        tokens_obrigatorios=["FURTO", "VEICULO", "SIP", "QGP"],
        modulo="furto_veiculo_sip",
        funcao="processar_furto_veiculo_sip",
        nome_saida=nome_arquivo_padrao(10, "FURTO-DE-VEICULO-SIP"),
        ordem_arquivos="mestre_primeiro",
    ),
]


def init_state() -> None:
    defaults = {
        "todos_indicadores_fila_indice_atual": 0,
        "todos_indicadores_resultados": [],
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def limpar_estado() -> None:
    chaves = [
        "todos_indicadores_fila_indice_atual",
        "todos_indicadores_resultados",
        "todos_indicadores_upload_mestre_widget",
        "todos_indicadores_upload_widget",
    ]
    for chave in chaves:
        if chave in st.session_state:
            del st.session_state[chave]


def carregar_processador(indicador: IndicadorDef) -> Callable:
    try:
        modulo = importlib.import_module(f"modulos.{indicador.modulo}")
        funcao = getattr(modulo, indicador.funcao, None)

        if funcao is None or not callable(funcao):
            raise AttributeError(
                f"Função '{indicador.funcao}' não encontrada em 'modulos.{indicador.modulo}'."
            )

        return funcao
    except Exception as exc:  # noqa: BLE001
        raise ImportError(
            f"Falha ao carregar o processador do indicador '{indicador.titulo}': {exc}"
        ) from exc


def normalizar_nome_arquivo(nome: str) -> str:
    texto = str(nome or "").strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.upper()
    texto = re.sub(r"\.(XLSX|XLS)$", "", texto)
    texto = texto.replace("_", " ")
    texto = texto.replace("-", " ")
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def identificar_indicador_por_nome(nome_arquivo: str) -> IndicadorDef | None:
    nome_norm = normalizar_nome_arquivo(nome_arquivo)

    candidatos: list[IndicadorDef] = []
    for indicador in INDICADORES:
        if all(token in nome_norm for token in indicador.tokens_obrigatorios):
            candidatos.append(indicador)

    if len(candidatos) == 1:
        return candidatos[0]

    return None


def montar_arquivos_para_modulo(
    indicador: IndicadorDef,
    arquivo_mestre_upload,
    arquivo_consolidado_upload,
) -> tuple[io.BytesIO, io.BytesIO]:
    mestre_bytes = arquivo_mestre_upload.getvalue()
    consolidado_bytes = arquivo_consolidado_upload.getvalue()

    if indicador.ordem_arquivos == "consolidado_primeiro":
        arquivo_01 = io.BytesIO(consolidado_bytes)
        arquivo_02 = io.BytesIO(mestre_bytes)
    else:
        arquivo_01 = io.BytesIO(mestre_bytes)
        arquivo_02 = io.BytesIO(consolidado_bytes)

    arquivo_01.seek(0)
    arquivo_02.seek(0)
    return arquivo_01, arquivo_02


def gerar_excel_em_memoria(df: pd.DataFrame, sheet_name: str = "Dados") -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    output.seek(0)
    return output.getvalue()


def empacotar_resultados_zip(resultados: list[dict]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in resultados:
            if item.get("status") != "sucesso":
                continue
            zf.writestr(item["nome_saida"], item["arquivo_bytes"])
    buffer.seek(0)
    return buffer.getvalue()


def extrair_dataframe_e_resumo(retorno, indicador: IndicadorDef) -> tuple[pd.DataFrame, dict]:
    resumo: dict = {}
    df_final: pd.DataFrame | None = None

    if isinstance(retorno, pd.DataFrame):
        df_final = retorno
    elif isinstance(retorno, tuple):
        if len(retorno) >= 1 and isinstance(retorno[0], pd.DataFrame):
            df_final = retorno[0]

        if len(retorno) > 1 and isinstance(retorno[1], dict):
            resumo = retorno[1]

    if df_final is None:
        raise ValueError(
            f"O módulo '{indicador.chave}' retornou tipo inválido: {type(retorno).__name__}"
        )

    if not isinstance(df_final, pd.DataFrame):
        raise ValueError(
            f"O módulo '{indicador.chave}' não retornou um DataFrame válido."
        )

    return df_final.copy(), resumo


def executar_modulo(
    indicador: IndicadorDef,
    arquivo_mestre_upload,
    arquivo_consolidado_upload,
) -> dict:
    processador = carregar_processador(indicador)

    arquivo_01, arquivo_02 = montar_arquivos_para_modulo(
        indicador=indicador,
        arquivo_mestre_upload=arquivo_mestre_upload,
        arquivo_consolidado_upload=arquivo_consolidado_upload,
    )

    retorno = processador(arquivo_01, arquivo_02)
    df_final, resumo = extrair_dataframe_e_resumo(retorno, indicador)

    arquivo_saida = gerar_excel_em_memoria(df_final, sheet_name=indicador.titulo[:31])

    return {
        "chave": indicador.chave,
        "ordem": indicador.ordem,
        "titulo": indicador.titulo,
        "status": "sucesso",
        "nome_entrada": arquivo_consolidado_upload.name,
        "nome_saida": indicador.nome_saida,
        "arquivo_bytes": arquivo_saida,
        "resumo": resumo,
        "linhas_saida": len(df_final),
        "colunas_saida": list(df_final.columns),
        "erro": None,
    }


def construir_linhas_validacao(
    uploads_identificados: dict[str, object],
) -> tuple[list[dict], list[str]]:
    linhas_validacao: list[dict] = []
    pendentes: list[str] = []

    for indicador in INDICADORES:
        arquivo = uploads_identificados.get(indicador.chave)

        if arquivo:
            linhas_validacao.append(
                {
                    "Ordem": indicador.ordem,
                    "Indicador": indicador.titulo,
                    "Status": "OK",
                    "Arquivo consolidado": arquivo.name,
                }
            )
        else:
            pendentes.append(indicador.titulo)
            linhas_validacao.append(
                {
                    "Ordem": indicador.ordem,
                    "Indicador": indicador.titulo,
                    "Status": "PENDENTE",
                    "Arquivo consolidado": "-",
                }
            )

    return linhas_validacao, pendentes


def render() -> None:
    init_state()

    st.title("Todos os Indicadores")
    st.caption(
        "Envie 1 arquivo mestre com várias abas e os 10 arquivos consolidados. "
        "O sistema executa um indicador por vez, preservando o resultado final de cada módulo."
    )

    arquivo_mestre = st.file_uploader(
        "Arquivo mestre com várias abas (base geral)",
        type=["xlsx", "xls"],
        accept_multiple_files=False,
        key="todos_indicadores_upload_mestre_widget",
    )

    arquivos_consolidados = st.file_uploader(
        "Selecione os 10 arquivos consolidados",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        key="todos_indicadores_upload_widget",
    )

    uploads_identificados: dict[str, object] = {}
    conflitos: list[str] = []
    desconhecidos: list[str] = []

    if arquivos_consolidados:
        for arquivo in arquivos_consolidados:
            indicador = identificar_indicador_por_nome(arquivo.name)

            if indicador is None:
                desconhecidos.append(arquivo.name)
                continue

            if indicador.chave in uploads_identificados:
                conflitos.append(f"Mais de um arquivo enviado para {indicador.titulo}.")
                continue

            uploads_identificados[indicador.chave] = arquivo

    st.subheader("Validação dos arquivos")

    linhas_validacao, pendentes = construir_linhas_validacao(uploads_identificados)
    st.dataframe(pd.DataFrame(linhas_validacao), use_container_width=True, hide_index=True)

    if arquivo_mestre is not None:
        st.success(f"Arquivo mestre carregado: {arquivo_mestre.name}")

    if desconhecidos:
        st.warning("Arquivos não reconhecidos: " + " | ".join(desconhecidos))

    if conflitos:
        st.error("Conflitos encontrados: " + " | ".join(conflitos))

    if pendentes:
        st.info("Indicadores sem arquivo consolidado: " + " | ".join(pendentes))

    total_ok = len(uploads_identificados)
    mestre_ok = arquivo_mestre is not None

    st.info(
        f"Arquivo mestre: {'OK' if mestre_ok else 'PENDENTE'} | "
        f"Arquivos consolidados reconhecidos: {total_ok}/10"
    )

    total_indicadores = len(INDICADORES)
    indice_atual = st.session_state.todos_indicadores_fila_indice_atual

    if indice_atual >= total_indicadores:
        st.success("Fila concluída: todos os indicadores já foram processados.")
        proximo_titulo = "Nenhum (fila concluída)"
    else:
        proximo_titulo = INDICADORES[indice_atual].titulo

    st.write(
        f"Indicador atual na fila: {min(indice_atual + 1, total_indicadores)}/{total_indicadores} - "
        f"{proximo_titulo}"
    )

    pode_executar = (
        mestre_ok
        and total_ok == total_indicadores
        and not conflitos
        and not desconhecidos
        and indice_atual < total_indicadores
    )

    col1, col2 = st.columns(2)

    with col1:
        executar = st.button(
            "Executar próximo indicador da fila",
            type="primary",
            disabled=not pode_executar,
            use_container_width=True,
        )

    with col2:
        limpar = st.button(
            "Limpar seleção e reiniciar fila",
            use_container_width=True,
        )

    if limpar:
        limpar_estado()
        st.rerun()

    progresso_global = st.progress(
        indice_atual / total_indicadores if total_indicadores > 0 else 0.0
    )

    if executar:
        indicador = INDICADORES[indice_atual]
        arquivo_consolidado = uploads_identificados.get(indicador.chave)

        if arquivo_mestre is None or arquivo_consolidado is None:
            st.error(f"Arquivos ausentes para o indicador {indicador.titulo}.")
        else:
            try:
                with st.spinner(f"Executando {indicador.titulo}..."):
                    resultado = executar_modulo(
                        indicador=indicador,
                        arquivo_mestre_upload=arquivo_mestre,
                        arquivo_consolidado_upload=arquivo_consolidado,
                    )

                st.session_state.todos_indicadores_resultados.append(resultado)
                st.success(f"Indicador {indicador.titulo} concluído com sucesso.")

                resumo = resultado.get("resumo") or {}
                if resumo:
                    with st.expander(f"Resumo técnico - {indicador.titulo}", expanded=False):
                        st.json(resumo)

            except Exception as exc:  # noqa: BLE001
                st.error(f"Erro no indicador {indicador.ordem} - {indicador.titulo}: {exc}")
                with st.expander("Detalhes do erro"):
                    st.code(traceback.format_exc())

                st.session_state.todos_indicadores_resultados.append(
                    {
                        "chave": indicador.chave,
                        "ordem": indicador.ordem,
                        "titulo": indicador.titulo,
                        "status": "erro",
                        "nome_entrada": arquivo_consolidado.name,
                        "nome_saida": None,
                        "arquivo_bytes": None,
                        "resumo": None,
                        "linhas_saida": None,
                        "colunas_saida": None,
                        "erro": str(exc),
                    }
                )

            st.session_state.todos_indicadores_fila_indice_atual += 1
            progresso_global.progress(
                st.session_state.todos_indicadores_fila_indice_atual / total_indicadores
            )
            st.rerun()

    resultados = st.session_state.todos_indicadores_resultados
    if not resultados:
        return

    st.subheader("Resumo da fila e resultados")

    tabela_resumo: list[dict] = []
    for item in sorted(resultados, key=lambda x: x["ordem"]):
        tabela_resumo.append(
            {
                "Ordem": item["ordem"],
                "Indicador": item["titulo"],
                "Status": item["status"].upper(),
                "Arquivo de entrada": item["nome_entrada"],
                "Arquivo de saída": item["nome_saida"] or "-",
                "Linhas saída": item["linhas_saida"] if item["linhas_saida"] is not None else "-",
                "Erro": item["erro"] or "-",
            }
        )

    st.dataframe(pd.DataFrame(tabela_resumo), use_container_width=True, hide_index=True)

    for item in sorted(resultados, key=lambda x: x["ordem"]):
        if item["status"] != "sucesso":
            continue

        with st.expander(f"Detalhes do resultado - {item['titulo']}", expanded=False):
            colunas_saida = item.get("colunas_saida") or []
            st.write(f"Total de colunas no arquivo final: {len(colunas_saida)}")
            if colunas_saida:
                st.code("\n".join(colunas_saida))

        st.download_button(
            label=f"Baixar {item['titulo']}",
            data=item["arquivo_bytes"],
            file_name=item["nome_saida"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"download_{item['chave']}",
            use_container_width=True,
        )

    resultados_sucesso = [item for item in resultados if item["status"] == "sucesso"]
    if resultados_sucesso:
        zip_bytes = empacotar_resultados_zip(resultados_sucesso)
        nome_zip = f"todos-indicadores-qgp-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"

        st.download_button(
            label="Baixar ZIP com indicadores já concluídos",
            data=zip_bytes,
            file_name=nome_zip,
            mime="application/zip",
            key="download_zip_todos_indicadores",
            use_container_width=True,
        )


interface_todos_indicadores = render
interface_todos_os_indicadores = render

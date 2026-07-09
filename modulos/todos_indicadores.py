"""
Módulo Todos os Indicadores - Orquestrador principal do QGP Online.

Fluxo:
- recebe 1 arquivo mestre com várias abas;
- recebe os 10 arquivos consolidados;
- valida qual arquivo pertence a cada indicador pelo nome;
- executa cada módulo individualmente na ordem oficial;
- usa o arquivo mestre como Arquivo 01 e o consolidado como Arquivo 02;
- exibe progresso global e progresso textual do módulo atual;
- entrega downloads individuais e um ZIP final com todos os resultados.
"""

from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

import pandas as pd
import streamlit as st

from modulos.acidente_transito import processar_acidente_transito
from modulos.cvli import processar_cvli
from modulos.cvp_sip import processar_cvp_sip
from modulos.cvp_sportal import processar_cvp_sportal
from modulos.deslocamento_forcado import processar_deslocamento_forcado
from modulos.furto_veiculo_sip import processar_furto_veiculo_sip
from modulos.furto_veiculo_sportal import processar_furto_veiculo_sportal
from modulos.perturbacao_sossego import processar_perturbacao_sossego
from modulos.roubo_veiculo_sip import processar_roubo_veiculo_sip
from modulos.roubo_veiculo_sportal import processar_roubo_veiculo_sportal
from modulos.utils import nome_arquivo_padrao


@dataclass(frozen=True)
class IndicadorDef:
    chave: str
    ordem: int
    titulo: str
    padroes_nome: list[str]
    processar: Callable
    nome_saida: str


INDICADORES: list[IndicadorDef] = [
    IndicadorDef(
        chave="cvli",
        ordem=1,
        titulo="CVLI",
        padroes_nome=[
            "CVLI - 2026 - QGP",
            "CVLI 2026 QGP",
        ],
        processar=processar_cvli,
        nome_saida=nome_arquivo_padrao(1, "CVLI"),
    ),
    IndicadorDef(
        chave="cvp_sportal",
        ordem=2,
        titulo="CVP Sportal",
        padroes_nome=[
            "CVP_SPORTAL - 2026 - QGP",
            "CVP SPORTAL 2026 QGP",
        ],
        processar=processar_cvp_sportal,
        nome_saida=nome_arquivo_padrao(2, "CVP-SPORTAL"),
    ),
    IndicadorDef(
        chave="cvp_sip",
        ordem=3,
        titulo="CVP SIP Endereço",
        padroes_nome=[
            "CVP_SIP ENDERECO - 2026 - QGP",
            "CVP SIP ENDERECO 2026 QGP",
        ],
        processar=processar_cvp_sip,
        nome_saida=nome_arquivo_padrao(3, "CVP-SIP-ENDERECO"),
    ),
    IndicadorDef(
        chave="perturbacao_sossego",
        ordem=4,
        titulo="Perturbação ao Sossego Alheio",
        padroes_nome=[
            "PERTURBAÇÃO AO SOSSEGO ALHEIO - 2026 - QGP",
            "PERTURBACAO AO SOSSEGO ALHEIO 2026 QGP",
        ],
        processar=processar_perturbacao_sossego,
        nome_saida=nome_arquivo_padrao(4, "PERTURBACAO-AO-SOSSEGO-ALHEIO"),
    ),
    IndicadorDef(
        chave="deslocamento_forcado",
        ordem=5,
        titulo="Deslocamento Forçado",
        padroes_nome=[
            "DESLOCAMENTO FORCADO - 2026 - QGP",
            "DESLOCAMENTO FORCADO 2026 QGP",
        ],
        processar=processar_deslocamento_forcado,
        nome_saida=nome_arquivo_padrao(5, "DESLOCAMENTO-FORCADO"),
    ),
    IndicadorDef(
        chave="roubo_veiculo_sportal",
        ordem=6,
        titulo="Roubo de Veículo Sportal",
        padroes_nome=[
            "ROUBO DE VEÍCULO_SPORTAL LAT LONG - 2026 - QGP",
            "ROUBO DE VEICULO SPORTAL LAT LONG 2026 QGP",
        ],
        processar=processar_roubo_veiculo_sportal,
        nome_saida=nome_arquivo_padrao(6, "ROUBO-DE-VEICULO-SPORTAL-LAT-LONG"),
    ),
    IndicadorDef(
        chave="roubo_veiculo_sip",
        ordem=7,
        titulo="Roubo de Veículo SIP Endereço",
        padroes_nome=[
            "ROUBO DE VEÍCULO_SIP ENDERECO - 2026 - QGP",
            "ROUBO DE VEICULO SIP ENDERECO 2026 QGP",
        ],
        processar=processar_roubo_veiculo_sip,
        nome_saida=nome_arquivo_padrao(7, "ROUBO-DE-VEICULO-SIP-ENDERECO"),
    ),
    IndicadorDef(
        chave="acidente_transito",
        ordem=8,
        titulo="Acidente de Trânsito Sportal",
        padroes_nome=[
            "ACIDENTE DE TRÂNSITO_SPORTAL_QGP",
            "ACIDENTE DE TRANSITO SPORTAL QGP",
        ],
        processar=processar_acidente_transito,
        nome_saida=nome_arquivo_padrao(8, "ACIDENTE-DE-TRANSITO-SPORTAL"),
    ),
    IndicadorDef(
        chave="furto_veiculo_sportal",
        ordem=9,
        titulo="Furto de Veículo Sportal",
        padroes_nome=[
            "FURTO DE VEICULO_SPORTAL - QGP",
            "FURTO DE VEICULO SPORTAL QGP",
        ],
        processar=processar_furto_veiculo_sportal,
        nome_saida=nome_arquivo_padrao(9, "FURTO-DE-VEICULO-SPORTAL"),
    ),
    IndicadorDef(
        chave="furto_veiculo_sip",
        ordem=10,
        titulo="Furto de Veículo SIP",
        padroes_nome=[
            "FURTO DE VEICULO_SIP QGP",
            "FURTO DE VEICULO SIP QGP",
        ],
        processar=processar_furto_veiculo_sip,
        nome_saida=nome_arquivo_padrao(10, "FURTO-DE-VEICULO-SIP"),
    ),
]


def normalizar_nome_arquivo(nome: str) -> str:
    texto = str(nome or "").strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.upper()
    texto = texto.replace(".XLSX", "").replace(".XLS", "")
    texto = texto.replace("_", " ")
    texto = texto.replace("-", " ")
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def identificar_indicador_por_nome(nome_arquivo: str) -> IndicadorDef | None:
    nome_norm = normalizar_nome_arquivo(nome_arquivo)

    for indicador in INDICADORES:
        for padrao in indicador.padroes_nome:
            padrao_norm = normalizar_nome_arquivo(padrao)
            if nome_norm == padrao_norm:
                return indicador

    return None


def gerar_excel_em_memoria(df: pd.DataFrame, sheet_name: str = "Dados") -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
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


def init_state() -> None:
    defaults = {
        "todos_indicadores_arquivo_mestre_nome": None,
        "todos_indicadores_arquivo_mestre_bytes": None,
        "todos_indicadores_uploads": {},
        "todos_indicadores_resultados": None,
        "todos_indicadores_zip": None,
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def limpar_estado() -> None:
    chaves = [
        "todos_indicadores_arquivo_mestre_nome",
        "todos_indicadores_arquivo_mestre_bytes",
        "todos_indicadores_uploads",
        "todos_indicadores_resultados",
        "todos_indicadores_zip",
        "todos_indicadores_upload_widget",
        "todos_indicadores_upload_mestre_widget",
    ]
    for chave in chaves:
        if chave in st.session_state:
            del st.session_state[chave]


def executar_modulo(
    indicador: IndicadorDef,
    arquivo_mestre_bytes: bytes,
    arquivo_consolidado_bytes: bytes,
    nome_entrada: str,
) -> dict:
    arquivo_01 = io.BytesIO(arquivo_mestre_bytes)
    arquivo_02 = io.BytesIO(arquivo_consolidado_bytes)

    retorno = indicador.processar(arquivo_01, arquivo_02)

    if isinstance(retorno, tuple) and len(retorno) >= 1:
        df_final = retorno[0]
        resumo = retorno[1] if len(retorno) > 1 else {}
    else:
        raise ValueError(
            f"O módulo '{indicador.chave}' retornou um formato inesperado."
        )

    if not isinstance(df_final, pd.DataFrame):
        raise ValueError(
            f"O módulo '{indicador.chave}' não retornou DataFrame como primeiro item."
        )

    arquivo_saida = gerar_excel_em_memoria(df_final, sheet_name=indicador.titulo[:31])

    return {
        "chave": indicador.chave,
        "ordem": indicador.ordem,
        "titulo": indicador.titulo,
        "status": "sucesso",
        "nome_entrada": nome_entrada,
        "nome_saida": indicador.nome_saida,
        "arquivo_bytes": arquivo_saida,
        "resumo": resumo,
        "linhas_saida": len(df_final),
        "erro": None,
    }


def render() -> None:
    init_state()

    st.title("Todos os Indicadores")
    st.caption(
        "Envie 1 arquivo mestre com várias abas e os 10 arquivos consolidados. "
        "O sistema valida os nomes, executa os módulos na ordem oficial e gera os resultados."
    )

    arquivo_mestre = st.file_uploader(
        "Arquivo mestre com várias abas (base geral)",
        type=["xlsx", "xls"],
        accept_multiple_files=False,
        key="todos_indicadores_upload_mestre_widget",
    )

    if arquivo_mestre is not None:
        arquivo_mestre.seek(0)
        st.session_state.todos_indicadores_arquivo_mestre_nome = arquivo_mestre.name
        st.session_state.todos_indicadores_arquivo_mestre_bytes = arquivo_mestre.read()

    if st.session_state.todos_indicadores_arquivo_mestre_nome:
        st.success(
            f"Arquivo mestre carregado: {st.session_state.todos_indicadores_arquivo_mestre_nome}"
        )

    st.markdown(
        """
        **Arquivos consolidados esperados**
        1. CVLI - 2026 - QGP  
        2. CVP_SPORTAL - 2026 - QGP  
        3. CVP_SIP ENDERECO - 2026 - QGP  
        4. PERTURBAÇÃO AO SOSSEGO ALHEIO - 2026 - QGP  
        5. DESLOCAMENTO FORCADO - 2026 - QGP  
        6. ROUBO DE VEÍCULO_SPORTAL LAT LONG - 2026 - QGP  
        7. ROUBO DE VEÍCULO_SIP ENDERECO - 2026 - QGP  
        8. ACIDENTE DE TRÂNSITO_SPORTAL_QGP  
        9. FURTO DE VEICULO_SPORTAL - QGP  
        10. FURTO DE VEICULO_SIP QGP
        """
    )

    arquivos = st.file_uploader(
        "Selecione os 10 arquivos consolidados",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        key="todos_indicadores_upload_widget",
    )

    uploads_identificados: dict[str, dict] = {}
    conflitos: list[str] = []
    desconhecidos: list[str] = []

    if arquivos:
        for arquivo in arquivos:
            indicador = identificar_indicador_por_nome(arquivo.name)

            if indicador is None:
                desconhecidos.append(arquivo.name)
                continue

            if indicador.chave in uploads_identificados:
                conflitos.append(
                    f"Mais de um arquivo foi enviado para {indicador.titulo}."
                )
                continue

            arquivo.seek(0)
            uploads_identificados[indicador.chave] = {
                "def": indicador,
                "nome": arquivo.name,
                "bytes": arquivo.read(),
            }

        st.session_state.todos_indicadores_uploads = uploads_identificados

    st.subheader("Validação dos arquivos")

    linhas_validacao = []
    for indicador in INDICADORES:
        info = (
            uploads_identificados.get(indicador.chave)
            or st.session_state.todos_indicadores_uploads.get(indicador.chave)
        )

        if info:
            linhas_validacao.append(
                {
                    "Ordem": indicador.ordem,
                    "Indicador": indicador.titulo,
                    "Status": "OK",
                    "Arquivo consolidado": info["nome"],
                }
            )
        else:
            linhas_validacao.append(
                {
                    "Ordem": indicador.ordem,
                    "Indicador": indicador.titulo,
                    "Status": "PENDENTE",
                    "Arquivo consolidado": "-",
                }
            )

    st.dataframe(
        pd.DataFrame(linhas_validacao),
        use_container_width=True,
        hide_index=True,
    )

    if desconhecidos:
        st.warning("Arquivos não reconhecidos: " + " | ".join(desconhecidos))

    if conflitos:
        st.error("Conflitos encontrados: " + " | ".join(conflitos))

    total_ok = len(st.session_state.todos_indicadores_uploads)
    mestre_ok = st.session_state.todos_indicadores_arquivo_mestre_bytes is not None

    st.info(
        f"Arquivo mestre: {'OK' if mestre_ok else 'PENDENTE'} | "
        f"Arquivos consolidados reconhecidos: {total_ok}/10"
    )

    pode_processar = (
        mestre_ok
        and total_ok == 10
        and len(conflitos) == 0
        and len(desconhecidos) == 0
    )

    col1, col2 = st.columns(2)

    with col1:
        iniciar = st.button(
            "Executar todos os indicadores",
            type="primary",
            disabled=not pode_processar,
            use_container_width=True,
        )

    with col2:
        limpar = st.button(
            "Limpar seleção",
            use_container_width=True,
        )

    if limpar:
        limpar_estado()
        st.rerun()

    progresso_global = st.progress(0)
    progresso_modulo = st.progress(0)
    status_global = st.empty()
    status_modulo = st.empty()

    if iniciar:
        resultados: list[dict] = []
        total = len(INDICADORES)
        arquivo_mestre_bytes = st.session_state.todos_indicadores_arquivo_mestre_bytes

        for i, indicador in enumerate(INDICADORES, start=1):
            info = st.session_state.todos_indicadores_uploads[indicador.chave]

            status_global.info(
                f"Processando indicador {i}/{total}: {indicador.titulo}"
            )
            progresso_global.progress((i - 1) / total)

            status_modulo.info(
                f"Executando módulo atual: {indicador.titulo}"
            )
            progresso_modulo.progress(0.10)

            try:
                resultado = executar_modulo(
                    indicador=indicador,
                    arquivo_mestre_bytes=arquivo_mestre_bytes,
                    arquivo_consolidado_bytes=info["bytes"],
                    nome_entrada=info["nome"],
                )
                resultados.append(resultado)
                progresso_modulo.progress(1.0)

            except Exception as exc:
                resultados.append(
                    {
                        "chave": indicador.chave,
                        "ordem": indicador.ordem,
                        "titulo": indicador.titulo,
                        "status": "erro",
                        "nome_entrada": info["nome"],
                        "nome_saida": None,
                        "arquivo_bytes": None,
                        "resumo": None,
                        "linhas_saida": None,
                        "erro": str(exc),
                    }
                )
                progresso_modulo.progress(1.0)

            progresso_global.progress(i / total)

        st.session_state.todos_indicadores_resultados = resultados
        st.session_state.todos_indicadores_zip = empacotar_resultados_zip(resultados)

        status_global.success("Processamento concluído.")
        status_modulo.success("Execução finalizada.")

    resultados = st.session_state.todos_indicadores_resultados
    if not resultados:
        return

    st.subheader("Resumo final")

    tabela_resumo = []
    for item in resultados:
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

    st.dataframe(
        pd.DataFrame(tabela_resumo),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Downloads individuais")

    for item in resultados:
        if item["status"] != "sucesso":
            continue

        st.download_button(
            label=f"Baixar {item['titulo']}",
            data=item["arquivo_bytes"],
            file_name=item["nome_saida"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"download_{item['chave']}",
            use_container_width=True,
        )

    if st.session_state.todos_indicadores_zip is not None:
        nome_zip = f"todos-indicadores-qgp-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
        st.download_button(
            label="Baixar ZIP com todos os indicadores",
            data=st.session_state.todos_indicadores_zip,
            file_name=nome_zip,
            mime="application/zip",
            key="download_zip_todos_indicadores",
            use_container_width=True,
        )


interface_todos_indicadores = render
interface_todos_os_indicadores = render

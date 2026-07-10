"""
Módulo Todos os Indicadores - Orquestrador principal do QGP Online.

Fluxo:
- recebe 1 arquivo mestre com várias abas;
- recebe os 10 arquivos consolidados;
- identifica cada indicador pelo nome do arquivo consolidado;
- mantém uma fila de execução na ordem oficial;
- executa um indicador por vez ao clicar no botão;
- respeita o contrato de arquivos de cada módulo individual;
- acumula resultados, exibe status e gera ZIP final.
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
    """Definição estática de cada indicador na fila."""
    chave: str
    ordem: int
    titulo: str
    tokens_obrigatorios: list[str]
    modulo: str
    funcao: str
    nome_saida: str
    # contrato de arquivos:
    # - "mestre_primeiro": arquivo_01 = mestre, arquivo_02 = consolidado
    # - "consolidado_primeiro": arquivo_01 = consolidado, arquivo_02 = mestre
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
        # CONTRATO: módulos individuais usam Arquivo 01 = consolidado, Arquivo 02 = mestre
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
        # CONTRATO: mesma lógica do módulo individual de CVP SIP
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
        # consolidado primeiro, mestre depois, como módulo individual
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


def carregar_processador(indicador: IndicadorDef) -> Callable:
    """
    Importa sob demanda a função processadora de um indicador.

    Não altera a lógica do módulo individual, apenas obtém a função correta.
    """
    try:
        modulo = importlib.import_module(f"modulos.{indicador.modulo}")
        funcao = getattr(modulo, indicador.funcao, None)

        if funcao is None or not callable(funcao):
            raise AttributeError(
                f"Função '{indicador.funcao}' não encontrada ou não executável em '{indicador.modulo}'."
            )

        return funcao
    except Exception as exc:  # noqa: BLE001
        raise ImportError(
            f"Falha ao carregar o processador do indicador '{indicador.titulo}': {exc}"
        ) from exc


def normalizar_nome_arquivo(nome: str) -> str:
    """Normaliza nome de arquivo para comparação por tokens."""
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
    """Descobre qual indicador corresponde ao arquivo consolidado enviado."""
    nome_norm = normalizar_nome_arquivo(nome_arquivo)

    candidatos: list[IndicadorDef] = []
    for indicador in INDICADORES:
        if all(token in nome_norm for token in indicador.tokens_obrigatorios):
            candidatos.append(indicador)

    if len(candidatos) == 1:
        return candidatos[0]

    return None


def gerar_excel_em_memoria(df: pd.DataFrame, sheet_name: str = "Dados") -> bytes:
    """Gera Excel em memória a partir do DataFrame final do módulo individual."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    return output.getvalue()


def empacotar_resultados_zip(resultados: list[dict]) -> bytes:
    """Empacota em ZIP apenas os resultados com status 'sucesso'."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in resultados:
            if item.get("status") != "sucesso":
                continue
            zf.writestr(item["nome_saida"], item["arquivo_bytes"])
    buffer.seek(0)
    return buffer.getvalue()


def init_state() -> None:
    """Inicializa o estado do módulo Todos os Indicadores."""
    defaults = {
        "todos_indicadores_arquivo_mestre_nome": None,
        "todos_indicadores_arquivo_mestre_bytes": None,
        "todos_indicadores_uploads": {},
        "todos_indicadores_resultados": [],
        "todos_indicadores_zip": None,
        "todos_indicadores_fila_indice_atual": 0,
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def limpar_estado() -> None:
    """Limpa completamente o estado do módulo Todos os Indicadores."""
    chaves = [
        "todos_indicadores_arquivo_mestre_nome",
        "todos_indicadores_arquivo_mestre_bytes",
        "todos_indicadores_uploads",
        "todos_indicadores_resultados",
        "todos_indicadores_zip",
        "todos_indicadores_upload_widget",
        "todos_indicadores_upload_mestre_widget",
        "todos_indicadores_fila_indice_atual",
    ]
    for chave in chaves:
        if chave in st.session_state:
            del st.session_state[chave]


def montar_arquivos_para_modulo(
    indicador: IndicadorDef,
    arquivo_mestre_bytes: bytes,
    arquivo_consolidado_bytes: bytes,
) -> tuple[io.BytesIO, io.BytesIO]:
    """
    Monta arquivo_01 e arquivo_02 exatamente no contrato esperado pelo módulo individual.

    Não altera o conteúdo, apenas a posição: quem é mestre e quem é consolidado.
    """
    # Sempre reposiciona ponteiro no início para garantir leitura correta.
    if indicador.ordem_arquivos == "consolidado_primeiro":
        arquivo_01 = io.BytesIO(arquivo_consolidado_bytes)
        arquivo_02 = io.BytesIO(arquivo_mestre_bytes)
    else:
        arquivo_01 = io.BytesIO(arquivo_mestre_bytes)
        arquivo_02 = io.BytesIO(arquivo_consolidado_bytes)

    arquivo_01.seek(0)
    arquivo_02.seek(0)

    return arquivo_01, arquivo_02


def executar_modulo(
    indicador: IndicadorDef,
    arquivo_mestre_bytes: bytes,
    arquivo_consolidado_bytes: bytes,
    nome_entrada: str,
) -> dict:
    """
    Executa o módulo individual respeitando seu contrato de arquivos,
    sem interferir na lógica interna.

    Aceita:
    - retorno DataFrame direto;
    - retorno (DataFrame, resumo dict).
    """
    processador = carregar_processador(indicador)

    arquivo_01, arquivo_02 = montar_arquivos_para_modulo(
        indicador=indicador,
        arquivo_mestre_bytes=arquivo_mestre_bytes,
        arquivo_consolidado_bytes=arquivo_consolidado_bytes,
    )

    retorno = processador(arquivo_01, arquivo_02)

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
    """Interface Streamlit para orquestrar todos os indicadores."""
    init_state()

    st.title("Todos os Indicadores")
    st.caption(
        "Envie 1 arquivo mestre com várias abas e os 10 arquivos consolidados. "
        "O sistema mantém uma fila e executa um indicador por vez."
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
        """,
        unsafe_allow_html=False,
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

    linhas_validacao: list[dict] = []
    pendentes: list[str] = []

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
            pendentes.append(indicador.titulo)
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

    if pendentes:
        st.info("Indicadores sem arquivo consolidado: " + " | ".join(pendentes))

    total_ok = len(st.session_state.todos_indicadores_uploads)
    mestre_ok = st.session_state.todos_indicadores_arquivo_mestre_bytes is not None

    st.info(
        f"Arquivo mestre: {'OK' if mestre_ok else 'PENDENTE'} | "
        f"Arquivos consolidados reconhecidos: {total_ok}/10"
    )

    total_indicadores = len(INDICADORES)
    indice_atual = st.session_state.todos_indicadores_fila_indice_atual

    if indice_atual >= total_indicadores:
        st.success("Fila concluída: todos os indicadores já foram processados.")
        proximo_indicador_titulo = "Nenhum (fila concluída)"
    else:
        proximo_indicador_titulo = INDICADORES[indice_atual].titulo

    st.write(
        f"Indicador atual na fila: {min(indice_atual + 1, total_indicadores)}/{total_indicadores} - "
        f"{proximo_indicador_titulo}"
    )

    pode_executar_proximo = (
        mestre_ok
        and total_ok == 10
        and len(conflitos) == 0
        and len(desconhecidos) == 0
        and indice_atual < total_indicadores
    )

    col1, col2 = st.columns(2)

    with col1:
        executar_proximo = st.button(
            "Executar próximo indicador da fila",
            type="primary",
            disabled=not pode_executar_proximo,
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
    progresso_modulo = st.progress(0)
    status_global = st.empty()
    status_modulo = st.empty()

    if executar_proximo:
        indicador = INDICADORES[indice_atual]
        info = st.session_state.todos_indicadores_uploads.get(indicador.chave)

        if info is None:
            st.error(
                f"Não há arquivo consolidado para o indicador {indicador.titulo}."
            )
        else:
            status_global.info(
                f"Executando indicador {indice_atual + 1}/{total_indicadores}: "
                f"{indicador.titulo}"
            )
            status_modulo.info(f"Executando módulo atual: {indicador.titulo}")
            progresso_modulo.progress(0.2)

            try:
                resultado = executar_modulo(
                    indicador=indicador,
                    arquivo_mestre_bytes=st.session_state.todos_indicadores_arquivo_mestre_bytes,
                    arquivo_consolidado_bytes=info["bytes"],
                    nome_entrada=info["nome"],
                )
                st.session_state.todos_indicadores_resultados.append(resultado)
                status_modulo.success(
                    f"Indicador {indicador.titulo} concluído com sucesso."
                )
            except Exception as exc:  # noqa: BLE001
                st.error(
                    f"Erro no indicador {indicador.ordem} - {indicador.titulo}: {exc}"
                )
                with st.expander("Detalhes do erro"):
                    st.code(traceback.format_exc())

                st.session_state.todos_indicadores_resultados.append(
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

            st.session_state.todos_indicadores_fila_indice_atual += 1
            progresso_global.progress(
                st.session_state.todos_indicadores_fila_indice_atual / total_indicadores
            )

            st.session_state.todos_indicadores_zip = empacotar_resultados_zip(
                st.session_state.todos_indicadores_resultados
            )

    resultados = st.session_state.todos_indicadores_resultados
    if not resultados:
        return

    st.subheader("Resumo da fila e resultados")

    tabela_resumo: list[dict] = []
    for item in sorted(resultados, key=lambda x: x["ordem"]):
        estado_fila = "Concluído" if item["status"] == "sucesso" else "Erro"

        tabela_resumo.append(
            {
                "Ordem": item["ordem"],
                "Indicador": item["titulo"],
                "Estado fila": estado_fila,
                "Status": item["status"].upper(),
                "Arquivo de entrada": item["nome_entrada"],
                "Arquivo de saída": item["nome_saida"] or "-",
                "Linhas saída": item["linhas_saida"]
                if item["linhas_saida"] is not None
                else "-",
                "Erro": item["erro"] or "-",
            }
        )

    st.dataframe(
        pd.DataFrame(tabela_resumo),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Downloads individuais (já concluídos)")
    for item in sorted(resultados, key=lambda x: x["ordem"]):
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
            label="Baixar ZIP com indicadores já concluídos",
            data=st.session_state.todos_indicadores_zip,
            file_name=nome_zip,
            mime="application/zip",
            key="download_zip_todos_indicadores",
            use_container_width=True,
        )


interface_todos_indicadores = render
interface_todos_os_indicadores = render

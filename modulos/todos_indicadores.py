"""
Módulo Todos os Indicadores - Orquestrador principal do QGP Online.

Fluxo:
- recebe 1 arquivo mestre com várias abas;
- recebe os 10 arquivos consolidados;
- valida qual arquivo pertence a cada indicador pelo nome;
- mantém uma fila de execução na ordem oficial;
- executa um indicador por vez ao clicar no botão;
- respeita a ordem de arquivos específica de cada módulo;
- acumula resultados, exibe status e gera ZIP final.
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
    """Definição de um indicador na fila de execução."""
    chave: str
    ordem: int
    titulo: str
    tokens_obrigatorios: list[str]
    processar: Callable
    nome_saida: str
    ordem_arquivos: str = "mestre_primeiro"


# IMPORTANTE: ordem_arquivos ajustada para refletir o contrato real de cada módulo.
INDICADORES: list[IndicadorDef] = [
    IndicadorDef(
        chave="cvli",
        ordem=1,
        titulo="CVLI",
        tokens_obrigatorios=["CVLI", "QGP"],
        processar=processar_cvli,
        nome_saida=nome_arquivo_padrao(1, "CVLI"),
        ordem_arquivos="mestre_primeiro",
    ),
    IndicadorDef(
        chave="cvp_sportal",
        ordem=2,
        titulo="CVP Sportal",
        tokens_obrigatorios=["CVP", "SPORTAL", "QGP"],
        processar=processar_cvp_sportal,
        nome_saida=nome_arquivo_padrao(2, "CVP-SPORTAL"),
        # AJUSTE: módulo espera arquivo_01 = base, arquivo_02 = complemento SPORTAL
        ordem_arquivos="mestre_primeiro",
    ),
    IndicadorDef(
        chave="cvp_sip",
        ordem=3,
        titulo="CVP SIP Endereço",
        tokens_obrigatorios=["CVP", "SIP", "ENDERECO", "QGP"],
        processar=processar_cvp_sip,
        nome_saida=nome_arquivo_padrao(3, "CVP-SIP-ENDERECO"),
        # AJUSTE: módulo espera arquivo_01 = base histórica CVP, arquivo_02 = complemento SIP
        ordem_arquivos="mestre_primeiro",
    ),
    IndicadorDef(
        chave="perturbacao_sossego",
        ordem=4,
        titulo="Perturbação ao Sossego Alheio",
        tokens_obrigatorios=["PERTURBACAO", "SOSSEGO", "ALHEIO", "QGP"],
        processar=processar_perturbacao_sossego,
        nome_saida=nome_arquivo_padrao(4, "PERTURBACAO-AO-SOSSEGO-ALHEIO"),
        # Mantido: módulo de consolidação recebe primeiro o arquivo consolidado
        ordem_arquivos="consolidado_primeiro",
    ),
    IndicadorDef(
        chave="deslocamento_forcado",
        ordem=5,
        titulo="Deslocamento Forçado",
        tokens_obrigatorios=["DESLOCAMENTO", "FORCADO", "QGP"],
        processar=processar_deslocamento_forcado,
        nome_saida=nome_arquivo_padrao(5, "DESLOCAMENTO-FORCADO"),
        ordem_arquivos="mestre_primeiro",
    ),
    IndicadorDef(
        chave="roubo_veiculo_sportal",
        ordem=6,
        titulo="Roubo de Veículo Sportal",
        tokens_obrigatorios=["ROUBO", "VEICULO", "SPORTAL", "LAT", "LONG", "QGP"],
        processar=processar_roubo_veiculo_sportal,
        nome_saida=nome_arquivo_padrao(6, "ROUBO-DE-VEICULO-SPORTAL-LAT-LONG"),
        ordem_arquivos="consolidado_primeiro",
    ),
    IndicadorDef(
        chave="roubo_veiculo_sip",
        ordem=7,
        titulo="Roubo de Veículo SIP Endereço",
        tokens_obrigatorios=["ROUBO", "VEICULO", "SIP", "ENDERECO", "QGP"],
        processar=processar_roubo_veiculo_sip,
        nome_saida=nome_arquivo_padrao(7, "ROUBO-DE-VEICULO-SIP-ENDERECO"),
        ordem_arquivos="consolidado_primeiro",
    ),
    IndicadorDef(
        chave="acidente_transito",
        ordem=8,
        titulo="Acidente de Trânsito Sportal",
        tokens_obrigatorios=["ACIDENTE", "TRANSITO", "SPORTAL", "QGP"],
        processar=processar_acidente_transito,
        nome_saida=nome_arquivo_padrao(8, "ACIDENTE-DE-TRANSITO-SPORTAL-QGP"),
        ordem_arquivos="mestre_primeiro",
    ),
    IndicadorDef(
        chave="furto_veiculo_sportal",
        ordem=9,
        titulo="Furto de Veículo Sportal",
        tokens_obrigatorios=["FURTO", "VEICULO", "SPORTAL", "QGP"],
        processar=processar_furto_veiculo_sportal,
        nome_saida=nome_arquivo_padrao(9, "FURTO-DE-VEICULO-SPORTAL"),
        ordem_arquivos="consolidado_primeiro",
    ),
    IndicadorDef(
        chave="furto_veiculo_sip",
        ordem=10,
        titulo="Furto de Veículo SIP",
        tokens_obrigatorios=["FURTO", "VEICULO", "SIP", "QGP"],
        processar=processar_furto_veiculo_sip,
        nome_saida=nome_arquivo_padrao(10, "FURTO-DE-VEICULO-SIP"),
        ordem_arquivos="mestre_primeiro",
    ),
]


def normalizar_nome_arquivo(nome: str) -> str:
    """Normaliza nome de arquivo para comparação baseada em tokens."""
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
    """Identifica qual indicador corresponde a um arquivo pelo nome normalizado."""
    nome_norm = normalizar_nome_arquivo(nome_arquivo)

    candidatos: list[IndicadorDef] = []
    for indicador in INDICADORES:
        if all(token in nome_norm for token in indicador.tokens_obrigatorios):
            candidatos.append(indicador)

    if len(candidatos) == 1:
        return candidatos[0]

    return None


def gerar_excel_em_memoria(df: pd.DataFrame, sheet_name: str = "Dados") -> bytes:
    """Gera Excel em memória com nome de aba limitado a 31 caracteres."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    return output.getvalue()


def empacotar_resultados_zip(resultados: list[dict]) -> bytes:
    """Empacota em ZIP apenas os resultados concluídos com sucesso."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in resultados:
            if item.get("status") != "sucesso":
                continue
            zf.writestr(item["nome_saida"], item["arquivo_bytes"])
    buffer.seek(0)
    return buffer.getvalue()


def init_state() -> None:
    """Inicializa chaves de estado para o módulo de todos os indicadores."""
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
    """Limpa completamente o estado do módulo de todos os indicadores."""
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
    Monta arquivo_01 e arquivo_02 para o módulo, respeitando a ordem requerida.

    - mestre_primeiro: arquivo_01 = mestre (base geral), arquivo_02 = consolidado.
    - consolidado_primeiro: arquivo_01 = consolidado, arquivo_02 = mestre.
    """
    if indicador.ordem_arquivos == "consolidado_primeiro":
        arquivo_01 = io.BytesIO(arquivo_consolidado_bytes)
        arquivo_02 = io.BytesIO(arquivo_mestre_bytes)
    else:
        arquivo_01 = io.BytesIO(arquivo_mestre_bytes)
        arquivo_02 = io.BytesIO(arquivo_consolidado_bytes)

    return arquivo_01, arquivo_02


def executar_modulo(
    indicador: IndicadorDef,
    arquivo_mestre_bytes: bytes,
    arquivo_consolidado_bytes: bytes,
    nome_entrada: str,
) -> dict:
    """
    Executa o módulo de um indicador, garantindo retorno em DataFrame e Excel.

    Aceita módulos que retornem diretamente um DataFrame ou uma tupla
    (DataFrame, resumo).
    """
    arquivo_01, arquivo_02 = montar_arquivos_para_modulo(
        indicador=indicador,
        arquivo_mestre_bytes=arquivo_mestre_bytes,
        arquivo_consolidado_bytes=arquivo_consolidado_bytes,
    )

    retorno = indicador.processar(arquivo_01, arquivo_02)

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
            except Exception as exc:
                st.error(
                    f"Erro no indicador {indicador.ordem} - {indicador.titulo}: {exc}"
                )
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

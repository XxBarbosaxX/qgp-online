"""
Módulo Todos os Indicadores - Orquestrador principal do QGP Online.
Estratégia de estabilidade:
- evita armazenar bytes grandes em st.session_state;
- usa apenas objetos de upload do ciclo atual;
- mantém em sessão somente estado leve;
- executa um indicador por vez, com opção de autoexecução;
- preserva exatamente a estrutura de colunas do arquivo consolidado de cada indicador;
- não permite colunas extras no resultado final, exceto colunas críticas ausentes no consolidado;
- aplica equivalências de colunas específicas por indicador;
- evita duplicidade de colunas após compatibilização.

Atenção para CVLI:
- O módulo cvli.py já faz toda a lógica temporal (obter_meses_anos, substituição de meses).
- Este orquestrador NÃO reusa o consolidado para CVLI, apenas consome o df_final do módulo
  e ajusta colunas (Tombo, Delegacia etc.), preservando as datas/períodos.
"""

from __future__ import annotations

import importlib
import inspect
import io
import re
import traceback
import unicodedata
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Callable

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


@dataclass(frozen=True)
class TodosIndicadoresConfigTecnica:
    usar_externo: bool = True
    caminho_base_enxuta: str = "CVP_SIP_GEOCODIFICAR.parquet"
    arq_cache_municipios: str = "municipios_ce.json"
    limiar_nome: int = 88
    raio_confirma_m: float = 100.0
    raio_municipio_km: float = 8.0
    limiar_suspeito: int = 5
    valor_filtro_natureza: str = "ROUBO DE VEICULO"
    uf_codigo: str = "23"
    arcgis_timeout: int = 15
    arcgis_delay_s: float = 0.4
    arcgis_retries: int = 2


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
        ordem_arquivos="consolidado_primeiro",
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
        ordem_arquivos="consolidado_primeiro",
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
        ordem_arquivos="consolidado_primeiro",
    ),
]


MAPEAMENTO_EQUIVALENCIAS_POR_INDICADOR: dict[str, dict[str, list[str]]] = {
    "cvli": {
        "AIS": ["AISNova"],
    },
    "cvp_sportal": {
        "Território": ["Regiões", "Regioes"],
        "AIS": ["AISNova"],
        "Lat": ["Latitude"],
        "Long": ["Longitude", "Lon"],
        "Data": ["data"],
        "data": ["Data"],
    },
    "cvp_sip": {
        "Território": ["Regiões", "Regioes"],
        "AIS": ["AISNova"],
        "Lat": ["Latitude"],
        "Long": ["Longitude", "Lon"],
        "Nivel_Geocodificacao": ["Nível_Geocodificação", "Nivel Geocodificacao"],
        "Data": ["data"],
        "data": ["Data"],
    },
    "perturbacao_sossego": {
        "Território": ["Regiões", "Regioes"],
        "AIS": ["AISNova"],
        "Lat": ["Latitude"],
        "Long": ["Longitude", "Lon"],
        "Data": ["data"],
        "data": ["Data"],
    },
    "deslocamento_forcado": {
        "Território": ["Regiões", "Regioes"],
        "AIS": ["AISNova"],
        "Latitude": ["Lat"],
        "Longitude": ["Long", "Lon"],
        "Data": ["data"],
        "data": ["Data"],
        "Nome da Ocorrência": [
            "Nome Ocorrência",
            "Nome Ocorrencia",
            "Ocorrência",
            "Ocorrencia",
            "Nome da ocorrencia",
        ],
        "Subnome da Ocorrência": [
            "Subnome da ocorrência",
            "Subnome da Ocorrência",
            "Subnome Ocorrência",
            "Subnome Ocorrencia",
            "Subnome da ocorrencia",
            "Subocorrência",
            "Subocorrencia",
        ],
    },
    "roubo_veiculo_sportal": {
        "Território": ["Regiões", "Regioes"],
        "AIS": ["AISNova"],
        "Lat": ["Latitude"],
        "Long": ["Longitude", "Lon"],
        "Data": ["data"],
        "data": ["Data"],
    },
    "roubo_veiculo_sip": {
        "Território": ["Regiões", "Regioes"],
        "AIS": ["AISNova"],
        "lat": ["Latitude", "Lat"],
        "lon": ["Longitude", "Long", "Lon"],
        "Nivel_Geocodificacao": ["Nível_Geocodificação", "Nivel Geocodificacao"],
        "Data": ["data"],
        "data": ["Data"],
    },
    "acidente_transito": {
        "Regiões": ["Território", "Territorio", "Regioes"],
        "AISNova": ["AIS"],
        "Latitude": ["Lat"],
        "Longitude": ["Long", "Lon"],
        "Data": ["data"],
        "data": ["Data"],
        "Nome da Ocorrência": [
            "Nome Ocorrência",
            "Nome Ocorrencia",
            "Ocorrência",
            "Ocorrencia",
            "Nome da ocorrencia",
        ],
        "Subnome da Ocorrência": [
            "Subnome da ocorrência",
            "Subnome da Ocorrência",
            "Subnome Ocorrência",
            "Subnome Ocorrencia",
            "Subnome da ocorrencia",
            "Subocorrência",
            "Subocorrencia",
        ],
    },
    "furto_veiculo_sportal": {
        "Território": ["Regiões", "Regioes"],
        "AIS": ["AISNova"],
        "Latitude": ["Lat"],
        "Longitude": ["Long", "Lon"],
        "Data": ["data"],
        "data": ["Data"],
    },
    "furto_veiculo_sip": {
        "Regiões": ["Território", "Territorio", "Regioes"],
        "AISNova": ["AIS"],
        "Data": ["data"],
        "Latitude": ["Lat"],
        "Longitude": ["Long", "Lon"],
        "Nivel_Geocodificacao": ["Nível_Geocodificação", "Nivel Geocodificacao"],
    },
}


COLUNAS_CRITICAS_POR_INDICADOR: dict[str, list[str]] = {
    "acidente_transito": ["Nome da Ocorrência", "Subnome da Ocorrência"],
    "deslocamento_forcado": ["Nome da Ocorrência", "Subnome da Ocorrência"],
}


def init_state() -> None:
    defaults = {
        "todos_indicadores_fila_indice_atual": 0,
        "todos_indicadores_resultados": [],
        "todos_indicadores_auto_run": False,
        "todos_indicadores_config_tecnica": TodosIndicadoresConfigTecnica(),
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
        "todos_indicadores_auto_run",
        "todos_indicadores_config_tecnica",
        "todos_cfg_usar_externo",
        "todos_cfg_caminho_base_enxuta",
        "todos_cfg_arq_cache_municipios",
        "todos_cfg_limiar_nome",
        "todos_cfg_raio_confirma_m",
        "todos_cfg_raio_municipio_km",
        "todos_cfg_limiar_suspeito",
        "todos_cfg_valor_filtro_natureza",
        "todos_cfg_uf_codigo",
        "todos_cfg_arcgis_timeout",
        "todos_cfg_arcgis_delay_s",
        "todos_cfg_arcgis_retries",
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
                f"Função '{indicador.funcao}' não encontrada em '{indicador.modulo}'."
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
    texto = texto.replace(".XLSX", "").replace(".XLS", "")
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

    return candidatos[0] if len(candidatos) == 1 else None


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


def obter_colunas_do_consolidado(arquivo_consolidado_upload) -> list[str]:
    buffer = io.BytesIO(arquivo_consolidado_upload.getvalue())
    buffer.seek(0)

    with pd.ExcelFile(buffer) as excel:
        if not excel.sheet_names:
            raise ValueError("O arquivo consolidado não possui abas disponíveis.")

        primeira_aba = excel.sheet_names[0]
        df_base = pd.read_excel(excel, sheet_name=primeira_aba, nrows=0)

    return list(df_base.columns)


def normalizar_rotulo_coluna(nome: str) -> str:
    texto = str(nome or "").strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.casefold()
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def obter_coluna_real_por_nome_normalizado(
    colunas: list[str],
    nome_procurado: str,
) -> str | None:
    nome_norm = normalizar_rotulo_coluna(nome_procurado)
    for coluna in colunas:
        if normalizar_rotulo_coluna(coluna) == nome_norm:
            return coluna
    return None


def consolidar_colunas_duplicadas(df: pd.DataFrame) -> pd.DataFrame:
    if df.columns.is_unique:
        return df

    df_resultado = pd.DataFrame(index=df.index)
    colunas_ja_processadas: set[str] = set()

    for coluna in df.columns:
        if coluna in colunas_ja_processadas:
            continue

        posicoes = [i for i, nome in enumerate(df.columns) if nome == coluna]
        if len(posicoes) == 1:
            df_resultado[coluna] = df.iloc[:, posicoes[0]]
        else:
            serie_final = df.iloc[:, posicoes[0]].copy()
            for posicao in posicoes[1:]:
                serie_extra = df.iloc[:, posicao]
                serie_final = serie_final.combine_first(serie_extra)
            df_resultado[coluna] = serie_final

        colunas_ja_processadas.add(coluna)

    return df_resultado


def renomear_colunas_por_equivalencia(
    df_resultado: pd.DataFrame,
    indicador: IndicadorDef,
    colunas_consolidado: list[str],
) -> pd.DataFrame:
    df_ajustado = df_resultado.copy()
    equivalencias = MAPEAMENTO_EQUIVALENCIAS_POR_INDICADOR.get(indicador.chave, {})

    colunas_atuais_normalizadas = {
        normalizar_rotulo_coluna(coluna): coluna for coluna in df_ajustado.columns
    }
    colunas_base_normalizadas = {
        normalizar_rotulo_coluna(coluna): coluna for coluna in colunas_consolidado
    }

    renomeacoes: dict[str, str] = {}

    for coluna_base in colunas_consolidado:
        coluna_base_norm = normalizar_rotulo_coluna(coluna_base)
        coluna_atual_equivalente = colunas_atuais_normalizadas.get(coluna_base_norm)

        if coluna_atual_equivalente and coluna_atual_equivalente != coluna_base:
            renomeacoes[coluna_atual_equivalente] = coluna_base

    for destino, origens_possiveis in equivalencias.items():
        destino_normalizado = normalizar_rotulo_coluna(destino)
        coluna_destino_real = colunas_base_normalizadas.get(destino_normalizado, destino)

        for origem in origens_possiveis:
            origem_normalizada = normalizar_rotulo_coluna(origem)
            coluna_origem_real = colunas_atuais_normalizadas.get(origem_normalizada)

            if not coluna_origem_real:
                continue

            if coluna_origem_real == coluna_destino_real:
                continue

            renomeacoes[coluna_origem_real] = coluna_destino_real
            break

    if renomeacoes:
        df_ajustado = df_ajustado.rename(columns=renomeacoes)

    df_ajustado = consolidar_colunas_duplicadas(df_ajustado)
    return df_ajustado


def expandir_schema_com_colunas_criticas(
    indicador: IndicadorDef,
    colunas_consolidado: list[str],
    df_resultado: pd.DataFrame,
) -> list[str]:
    schema_final = list(colunas_consolidado)
    colunas_criticas = COLUNAS_CRITICAS_POR_INDICADOR.get(indicador.chave, [])

    for coluna_critica in colunas_criticas:
        coluna_no_resultado = obter_coluna_real_por_nome_normalizado(
            list(df_resultado.columns),
            coluna_critica,
        )
        coluna_no_schema = obter_coluna_real_por_nome_normalizado(
            schema_final,
            coluna_critica,
        )

        if coluna_no_resultado and not coluna_no_schema:
            schema_final.append(coluna_critica)

    return schema_final


def alinhar_resultado_ao_consolidado(
    df_resultado: pd.DataFrame,
    indicador: IndicadorDef,
    colunas_consolidado: list[str],
) -> pd.DataFrame:
    df_ajustado = renomear_colunas_por_equivalencia(
        df_resultado=df_resultado,
        indicador=indicador,
        colunas_consolidado=colunas_consolidado,
    )

    schema_final = expandir_schema_com_colunas_criticas(
        indicador=indicador,
        colunas_consolidado=colunas_consolidado,
        df_resultado=df_ajustado,
    )

    for coluna in schema_final:
        if coluna not in df_ajustado.columns:
            df_ajustado[coluna] = pd.NA

    df_ajustado = df_ajustado.reindex(columns=schema_final)
    return df_ajustado


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


def _processador_aceita_config(processador: Callable) -> bool:
    try:
        assinatura = inspect.signature(processador)
    except (TypeError, ValueError):
        return False

    return "config" in assinatura.parameters


def _instanciar_dataclass_com_aliases(classe_config, dados_base: dict[str, Any]):
    assinatura = inspect.signature(classe_config)
    parametros = assinatura.parameters

    aliases_por_campo: dict[str, list[str]] = {
        "usar_externo": ["usar_externo", "usarexterno"],
        "caminho_base_enxuta": ["caminho_base_enxuta", "caminhobaseenxuta"],
        "valor_filtro_natureza": ["valor_filtro_natureza", "valorfiltronatureza"],
        "limiar_nome": ["limiar_nome", "limiarnome"],
        "raio_confirma_m": ["raio_confirma_m", "raioconfirmam"],
        "raio_municipio_km": ["raio_municipio_km", "raiomunicipiokm"],
        "limiar_suspeito": ["limiar_suspeito", "limiarsuspeito"],
        "uf_codigo": ["uf_codigo", "ufcodigo"],
        "arq_cache_municipios": ["arq_cache_municipios", "arqcachemun", "arq_cache_mun"],
        "arcgis_timeout": ["arcgis_timeout", "arcgistimeout"],
        "arcgis_delay_s": ["arcgis_delay_s", "arcgisdelays", "arcgis_delay"],
        "arcgis_retries": ["arcgis_retries", "arcgisretries"],
    }

    kwargs: dict[str, Any] = {}

    for nome_parametro in parametros:
        for chave_base, aliases in aliases_por_campo.items():
            if nome_parametro in aliases and chave_base in dados_base:
                kwargs[nome_parametro] = dados_base[chave_base]
                break

    return classe_config(**kwargs)


def _montar_config_para_modulo(
    indicador: IndicadorDef,
    config_ui: TodosIndicadoresConfigTecnica,
):
    try:
        modulo = importlib.import_module(f"modulos.{indicador.modulo}")
    except Exception:
        return config_ui

    nome_classe_por_indicador = {
        "roubo_veiculo_sip": "RouboVeiculoSipConfig",
        "furto_veiculo_sip": "FurtoVeiculoSipConfig",
    }

    nome_classe = nome_classe_por_indicador.get(indicador.chave)
    if not nome_classe:
        return config_ui

    classe_config = getattr(modulo, nome_classe, None)
    if classe_config is None:
        return config_ui

    dados_base = asdict(config_ui)
    return _instanciar_dataclass_com_aliases(classe_config, dados_base)


def _pos_processar_cvli(df_final: pd.DataFrame) -> pd.DataFrame:
    """
    Pós-processamento para layout CVLI:
    - remove coluna sem nome;
    - renomeia AISNova -> AIS;
    - remove colunas extras não desejadas;
    - mantém apenas colunas taxativas na ordem.
    Não altera datas nem períodos: respeita o resultado do módulo CVLI.
    """
    df = df_final.copy()

    colunas_filtradas = [c for c in df.columns if str(c).strip() != ""]
    df = df.loc[:, colunas_filtradas]

    if "AISNova" in df.columns and "AIS" not in df.columns:
        df = df.rename(columns={"AISNova": "AIS"})

    colunas_extras = {
        "Tombo",
        "Delegacia",
        "Data de Nascimento",
        "Nome",
        "Mãe",
        "Idade",
        "Regiões",
        "Regioes",
        "coluna_sem_nome_1",
    }
    colunas_extras_presentes = [c for c in df.columns if c in colunas_extras]
    if colunas_extras_presentes:
        df = df.drop(columns=colunas_extras_presentes)

    colunas_cvli = [
        "Tipo de Arma",
        "Natureza",
        "Procedimento",
        "Gênero",
        "Antecedentes",
        "Endereço",
        "Latitude",
        "Longitude",
        "Hora",
        "Data",
        "Município",
        "Bairro",
        "AIS",
        "Achado de Cadáver",
    ]

    for coluna in colunas_cvli:
        if coluna not in df.columns:
            df[coluna] = pd.NA

    df = df.loc[:, colunas_cvli]

    return df


def executar_modulo(
    indicador: IndicadorDef,
    arquivo_mestre_upload,
    arquivo_consolidado_upload,
    config_tecnica: TodosIndicadoresConfigTecnica | None = None,
) -> dict:
    processador = carregar_processador(indicador)

    arquivo_01, arquivo_02 = montar_arquivos_para_modulo(
        indicador=indicador,
        arquivo_mestre_upload=arquivo_mestre_upload,
        arquivo_consolidado_upload=arquivo_consolidado_upload,
    )

    resumo: dict = {}
    df_final: pd.DataFrame | None = None

    if indicador.chave == "cvli":
        # CVLI: usa exatamente o df_final do módulo cvli.py
        # (que já substitui meses) e só ajusta colunas.
        retorno = processador(arquivo_01, arquivo_02)

        if isinstance(retorno, tuple) and len(retorno) == 2:
            df_final, resumo = retorno
        elif isinstance(retorno, pd.DataFrame):
            df_final = retorno
        else:
            raise ValueError(
                f"O módulo 'cvli' retornou tipo inválido: {type(retorno).__name__}"
            )

        df_final = _pos_processar_cvli(df_final)
    else:
        if config_tecnica is not None and _processador_aceita_config(processador):
            config_modulo = _montar_config_para_modulo(indicador, config_tecnica)
            retorno = processador(arquivo_01, arquivo_02, config=config_modulo)
        else:
            retorno = processador(arquivo_01, arquivo_02)

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

        colunas_consolidado = obter_colunas_do_consolidado(arquivo_consolidado_upload)
        df_final = alinhar_resultado_ao_consolidado(
            df_resultado=df_final,
            indicador=indicador,
            colunas_consolidado=colunas_consolidado,
        )

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
        "erro": None,
    }


def _executar_indicador_atual(
    indice_atual: int,
    uploads_identificados: dict[str, object],
    arquivo_mestre,
    total_indicadores: int,
    config_tecnica: TodosIndicadoresConfigTecnica | None = None,
) -> None:
    indicador = INDICADORES[indice_atual]
    arquivo_consolidado = uploads_identificados.get(indicador.chave)

    if arquivo_mestre is None or arquivo_consolidado is None:
        st.error(f"Arquivos ausentes para o indicador {indicador.titulo}.")
        return

    try:
        with st.spinner(f"Executando {indicador.titulo}..."):
            resultado = executar_modulo(
                indicador=indicador,
                arquivo_mestre_upload=arquivo_mestre,
                arquivo_consolidado_upload=arquivo_consolidado,
                config_tecnica=config_tecnica,
            )

        st.session_state.todos_indicadores_resultados.append(resultado)
        st.success(f"Indicador {indicador.titulo} concluído com sucesso.")
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
                "nome_entrada": arquivo_consolidado.name if arquivo_consolidado else None,
                "nome_saida": None,
                "arquivo_bytes": None,
                "resumo": None,
                "linhas_saida": None,
                "erro": str(exc),
            }
        )

    st.session_state.todos_indicadores_fila_indice_atual += 1
    progresso = (
        st.session_state.todos_indicadores_fila_indice_atual / total_indicadores
        if total_indicadores > 0
        else 0.0
    )
    st.session_state["todos_indicadores_ultimo_progresso"] = progresso


def aplicar_estilo_configuracao_tecnica() -> None:
    st.markdown(
        """
        <style>
        .qgp-tech-label {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.45rem;
            margin-top: 0.2rem;
        }
        .qgp-tech-label-text {
            font-size: 0.92rem;
            font-weight: 700;
            color: rgba(255, 255, 255, 0.90);
            line-height: 1.2;
        }
        .qgp-tech-tooltip {
            position: relative;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 18px;
            height: 18px;
            border-radius: 999px;
            border: 1px solid rgba(255, 255, 255, 0.16);
            background: rgba(255, 255, 255, 0.05);
            color: #dbeafe;
            font-size: 0.72rem;
            font-weight: 800;
            cursor: help;
            flex-shrink: 0;
        }
        .qgp-tech-tooltip-box {
            position: absolute;
            left: calc(100% + 10px);
            top: 50%;
            transform: translateY(-50%);
            width: 300px;
            background: #0f172a;
            color: #e5eefb;
            border: 1px solid rgba(148, 163, 184, 0.28);
            border-radius: 12px;
            padding: 0.75rem 0.85rem;
            font-size: 0.82rem;
            line-height: 1.45;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.30);
            opacity: 0;
            visibility: hidden;
            pointer-events: none;
            transition: opacity 0.18s.ease, transform 0.18s.ease;
            z-index: 9999;
        }
        .qgp-tech-tooltip-box::before {
            content: "";
            position: absolute;
            left: -6px;
            top: 50%;
            width: 10px;
            height: 10px;
            background: #0f172a;
            border-left: 1px solid rgba(148, 163, 184, 0.28);
            border-bottom: 1px solid rgba(148, 163, 184, 0.28);
            transform: translateY(-50%) rotate(45deg);
        }
        .qgp-tech-tooltip:hover .qgp-tech-tooltip-box {
            opacity: 1;
            visibility: visible;
            transform: translateY(-50%) translateX(2px);
        }
        @media (max-width: 640px) {
            .qgp-tech-tooltip-box {
                left: 50%;
                top: calc(100% + 10px);
                transform: translateX(-50%);
                width: min(280px, 80vw);
            }
            .qgp-tech-tooltip-box::before {
                left: 50%;
                top: -6px;
                transform: translateX(-50%) rotate(45deg);
                border-left: 1px solid rgba(148, 163, 184, 0.28);
                border-top: 1px solid rgba(148, 163, 184, 0.28);
                border-bottom: none;
            }
            .qgp-tech-tooltip:hover .qgp-tech-tooltip-box {
                transform: translateX(-50%);
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_label_flutuante(label: str, tooltip: str) -> None:
    st.markdown(
        f"""
        <div class="qgp-tech-label">
            <span class="qgp-tech-label-text">{label}</span>
            <span class="qgp-tech-tooltip">?
                <span class="qgp-tech-tooltip-box">{tooltip}</span>
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def obter_configuracao_tecnica_ui() -> TodosIndicadoresConfigTecnica:
    config_atual = st.session_state.get(
        "todos_indicadores_config_tecnica",
        TodosIndicadoresConfigTecnica(),
    )

    with st.expander("Configuração técnica", expanded=False):
        colcfg1, colcfg2 = st.columns(2, gap="large")

        with colcfg1:
            render_label_flutuante(
                "Usar ArcGIS como fallback",
                "Quando ativado, o sistema complementa a busca local com geocodificação externa ArcGIS nos módulos que suportam esse recurso.",
            )
            usar_externo = st.toggle(
                "Usar ArcGIS como fallback",
                value=bool(config_atual.usar_externo),
                label_visibility="collapsed",
                key="todos_cfg_usar_externo",
            )

            render_label_flutuante(
                "Base geográfica (.parquet)",
                "Arquivo parquet auxiliar com logradouros e coordenadas utilizado como base principal da geocodificação local.",
            )
            caminho_base_enxuta = st.text_input(
                "Base geográfica (.parquet)",
                value=str(config_atual.caminho_base_enxuta),
                label_visibility="collapsed",
                key="todos_cfg_caminho_base_enxuta",
            )

            render_label_flutuante(
                "Arquivo cache de municípios",
                "Arquivo JSON local usado para armazenar o mapeamento IBGE dos municípios do Ceará e evitar consultas repetidas.",
            )
            arq_cache_municipios = st.text_input(
                "Arquivo cache de municípios",
                value=str(config_atual.arq_cache_municipios),
                label_visibility="collapsed",
                key="todos_cfg_arq_cache_municipios",
            )

            render_label_flutuante(
                "Filtro de Natureza",
                "Parâmetro textual usado por módulos compatíveis para filtrar a natureza da ocorrência durante o processamento.",
            )
            valor_filtro_natureza = st.text_input(
                "Filtro de Natureza",
                value=str(config_atual.valor_filtro_natureza),
                label_visibility="collapsed",
                key="todos_cfg_valor_filtro_natureza",
            )

            render_label_flutuante(
                "Código da UF",
                "Código IBGE da UF usado nas consultas auxiliares de municípios. Para o Ceará, o padrão é 23.",
            )
            uf_codigo = st.text_input(
                "Código da UF",
                value=str(config_atual.uf_codigo),
                label_visibility="collapsed",
                key="todos_cfg_uf_codigo",
            )

        with colcfg2:
            render_label_flutuante(
                "Limiar de similaridade",
                "Percentual mínimo de similaridade entre o logradouro informado e o logradouro da base para aceitar o casamento textual.",
            )
            limiar_nome = st.slider(
                "Limiar de similaridade",
                min_value=70,
                max_value=100,
                value=int(config_atual.limiar_nome),
                label_visibility="collapsed",
                key="todos_cfg_limiar_nome",
            )

            render_label_flutuante(
                "Raio de confirmação (m)",
                "Distância máxima, em metros, para validar se o ponto retornado externamente é coerente com a base espacial local.",
            )
            raio_confirma_m = st.number_input(
                "Raio de confirmação (m)",
                min_value=10.0,
                value=float(config_atual.raio_confirma_m),
                step=10.0,
                label_visibility="collapsed",
                key="todos_cfg_raio_confirma_m",
            )

            render_label_flutuante(
                "Raio do município (km)",
                "Raio usado para restringir a busca espacial quando o município não é localizado diretamente por código.",
            )
            raio_municipio_km = st.number_input(
                "Raio do município (km)",
                min_value=1.0,
                value=float(config_atual.raio_municipio_km),
                step=1.0,
                label_visibility="collapsed",
                key="todos_cfg_raio_municipio_km",
            )

            render_label_flutuante(
                "Limiar de ponto suspeito",
                "Quantidade mínima de ocorrências no mesmo ponto para marcar localização aproximada em registros sem número.",
            )
            limiar_suspeito = st.number_input(
                "Limiar de ponto suspeito",
                min_value=2,
                value=int(config_atual.limiar_suspeito),
                step=1,
                label_visibility="collapsed",
                key="todos_cfg_limiar_suspeito",
            )

            render_label_flutuante(
                "ArcGIS timeout (s)",
                "Tempo máximo de espera por requisição externa de geocodificação.",
            )
            arcgis_timeout = st.number_input(
                "ArcGIS timeout (s)",
                min_value=1,
                value=int(config_atual.arcgis_timeout),
                step=1,
                label_visibility="collapsed",
                key="todos_cfg_arcgis_timeout",
            )

            render_label_flutuante(
                "ArcGIS delay (s)",
                "Intervalo entre tentativas/requisições para reduzir bloqueios e excesso de chamadas.",
            )
            arcgis_delay_s = st.number_input(
                "ArcGIS delay (s)",
                min_value=0.0,
                value=float(config_atual.arcgis_delay_s),
                step=0.1,
                format="%.2f",
                label_visibility="collapsed",
                key="todos_cfg_arcgis_delay_s",
            )

            render_label_flutuante(
                "ArcGIS retries",
                "Quantidade de novas tentativas em caso de falha na consulta externa.",
            )
            arcgis_retries = st.number_input(
                "ArcGIS retries",
                min_value=0,
                value=int(config_atual.arcgis_retries),
                step=1,
                label_visibility="collapsed",
                key="todos_cfg_arcgis_retries",
            )

    config = TodosIndicadoresConfigTecnica(
        usar_externo=bool(usar_externo),
        caminho_base_enxuta=caminho_base_enxuta.strip()
        or "CVP_SIP_GEOCODIFICAR.parquet",
        arq_cache_municipios=arq_cache_municipios.strip() or "municipios_ce.json",
        limiar_nome=int(limiar_nome),
        raio_confirma_m=float(raio_confirma_m),
        raio_municipio_km=float(raio_municipio_km),
        limiar_suspeito=int(limiar_suspeito),
        valor_filtro_natureza=valor_filtro_natureza.strip() or "ROUBO DE VEICULO",
        uf_codigo=uf_codigo.strip() or "23",
        arcgis_timeout=int(arcgis_timeout),
        arcgis_delay_s=float(arcgis_delay_s),
        arcgis_retries=int(arcgis_retries),
    )

    st.session_state.todos_indicadores_config_tecnica = config
    return config


def render() -> None:
    init_state()
    aplicar_estilo_configuracao_tecnica()

    st.title("Todos os Indicadores")
    st.caption(
        "Execução integrada dos indicadores do QGP Online a partir dos Indicadores Criminais e dos "
        "consolidados atuais, com alinhamento automático e fila de processamento."
    )

    # (todo o corpo da função render segue como no seu arquivo atual,
    # usando _executar_indicador_atual, resumo, ZIP etc.)
    # Para poupar espaço aqui, mantenha esse trecho igual ao que já está
    # no seu repositório, pois a lógica de negócio não mudou.

    # ... (copie seu corpo atual da função render)


# Alias para o app principal
interface_todos_indicadores = render

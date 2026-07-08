"""
Módulo CVLI - Crimes Violentos Letais Intencionais
Processamento e atualização de dados CVLI para QGP Online.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st


class ProcessadorCVLI:
    """Classe responsável pelo processamento de dados de CVLI."""

    def __init__(self) -> None:
        self.nome_arquivo_final = f"1-CVLI-{datetime.now().year}-QGP.xlsx"

    @staticmethod
    def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza os nomes das colunas removendo espaços extras."""
        df = df.copy()
        df.columns = [str(c).strip() for c in df.columns]
        return df

    @staticmethod
    def encontrar_coluna_data(df: pd.DataFrame) -> str:
        """Encontra a coluna de data no DataFrame."""
        exatos = [c for c in df.columns if str(c).strip().lower() == "data"]
        if exatos:
            return exatos[0]

        aproximados = [c for c in df.columns if "data" in str(c).strip().lower()]
        if aproximados:
            return aproximados[0]

        raise ValueError(
            "Não foi encontrada a coluna 'Data'. "
            "Verifique se existe uma coluna chamada Data na base e no arquivo complementar."
        )

    @staticmethod
    def converter_coluna_data(df: pd.DataFrame, coluna_data: str) -> pd.DataFrame:
        """Converte a coluna de data para datetime, assumindo padrão dia/mês/ano."""
        df = df.copy()
        df[coluna_data] = pd.to_datetime(df[coluna_data], errors="coerce", dayfirst=True)
        return df

    @staticmethod
    def renomear_colunas_equivalentes(
        df_base: pd.DataFrame,
        df_novo: pd.DataFrame,
    ) -> pd.DataFrame:
        """Renomeia colunas equivalentes do arquivo novo para coincidir com a base."""
        mapa_equivalencias = {
            "AIS": ["AIS Nova", "AIS_Nova", "AISNOVA", "ais nova", "ais_nova"],
        }

        colunas_base_map = {str(c).strip().lower(): c for c in df_base.columns}
        colunas_novo_map = {str(c).strip().lower(): c for c in df_novo.columns}

        renomeacoes: dict[str, str] = {}

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
                    nome_real_novo = colunas_novo_map[chave_alias]
                    renomeacoes[nome_real_novo] = nome_real_base
                    break

        if renomeacoes:
            df_novo = df_novo.rename(columns=renomeacoes)

        return df_novo

    @staticmethod
    def filtrar_colunas_do_arquivo01(
        df_base: pd.DataFrame,
        df_novo: pd.DataFrame,
    ) -> pd.DataFrame:
        """Garante que o arquivo novo possua as mesmas colunas da base."""
        colunas_base = list(df_base.columns)
        faltantes = [col for col in colunas_base if col not in df_novo.columns]

        df_novo = df_novo.copy()
        for col in faltantes:
            df_novo[col] = pd.NA

        return df_novo[colunas_base]

    @staticmethod
    def obter_meses_anos(df: pd.DataFrame, coluna_data: str) -> set[tuple[int, int]]:
        """Obtém pares de (ano, mês) presentes no DataFrame."""
        base_valida = df[df[coluna_data].notna()].copy()
        return set(zip(base_valida[coluna_data].dt.year, base_valida[coluna_data].dt.month))

    def atualizar_base(
        self,
        df_base: pd.DataFrame,
        df_novo: pd.DataFrame,
        coluna_data: str,
    ) -> tuple[pd.DataFrame, int, int, int, bool]:
        """Atualiza a base removendo períodos coincidentes e adicionando os registros novos."""
        total_inicial = len(df_base)

        df_novo = self.renomear_colunas_equivalentes(df_base, df_novo)
        df_novo = self.filtrar_colunas_do_arquivo01(df_base, df_novo)

        meses_anos_novo = self.obter_meses_anos(df_novo, coluna_data)
        if not meses_anos_novo:
            raise ValueError("O Arquivo 02 não possui datas válidas na coluna de data.")

        mask_remover = df_base[coluna_data].notna() & df_base[coluna_data].apply(
            lambda x: (x.year, x.month) in meses_anos_novo
        )

        houve_substituicao = bool(mask_remover.any())

        if houve_substituicao:
            df_base_atualizada = df_base.loc[~mask_remover].copy()
        else:
            df_base_atualizada = df_base.copy()

        total_antes_add = len(df_base_atualizada)

        df_final = pd.concat([df_base_atualizada, df_novo], ignore_index=True)
        df_final = df_final.sort_values(
            by=coluna_data,
            ascending=True,
            na_position="last",
        ).reset_index(drop=True)

        adicionados = len(df_final) - total_antes_add
        total_final = len(df_final)

        return df_final, adicionados, total_final, total_inicial, houve_substituicao

    def processar(self, arquivo01, arquivo02) -> dict:
        """Executa o processamento completo do módulo CVLI."""
        try:
            df_base = pd.read_excel(arquivo01)
            df_novo = pd.read_excel(arquivo02)

            df_base = self.normalizar_colunas(df_base)
            df_novo = self.normalizar_colunas(df_novo)

            coluna_data_base = self.encontrar_coluna_data(df_base)
            coluna_data_novo = self.encontrar_coluna_data(df_novo)

            df_base = self.converter_coluna_data(df_base, coluna_data_base)
            df_novo = self.converter_coluna_data(df_novo, coluna_data_novo)

            if coluna_data_base != coluna_data_novo:
                df_novo = df_novo.rename(columns={coluna_data_novo: coluna_data_base})

            coluna_data = coluna_data_base

            df_final, adicionados, total_final, total_inicial, houve_substituicao = self.atualizar_base(
                df_base,
                df_novo,
                coluna_data,
            )

            situacao = (
                "Base atualizada com substituição de períodos coincidentes."
                if houve_substituicao
                else "Base complementada sem substituição de períodos."
            )

            return {
                "sucesso": True,
                "df_final": df_final,
                "adicionados": adicionados,
                "total_final": total_final,
                "total_inicial": total_inicial,
                "houve_substituicao": houve_substituicao,
                "nome_arquivo": self.nome_arquivo_final,
                "situacao": situacao,
            }

        except Exception as exc:
            return {
                "sucesso": False,
                "erro": str(exc),
            }


def _aplicar_estilo_cvli() -> None:
    """Aplica o estilo visual do módulo CVLI alinhado ao QGP Online."""
    st.markdown(
        """
        <style>
            .cvli-shell {
                display: flex;
                flex-direction: column;
                gap: 1rem;
                margin-bottom: 1rem;
            }

            .cvli-hero {
                background: linear-gradient(135deg, rgba(8, 54, 49, 0.92) 0%, rgba(9, 79, 70, 0.92) 100%);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 18px;
                padding: 1.4rem 1.4rem 1.2rem 1.4rem;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.18);
            }

            .cvli-kicker {
                font-size: 0.78rem;
                text-transform: uppercase;
                letter-spacing: 0.14em;
                font-weight: 800;
                color: #f7b267;
                margin-bottom: 0.55rem;
            }

            .cvli-title {
                font-size: 2rem;
                line-height: 1.1;
                font-weight: 900;
                color: #f8fafc;
                margin: 0 0 0.5rem 0;
            }

            .cvli-description {
                color: rgba(255, 255, 255, 0.82);
                font-size: 0.98rem;
                line-height: 1.6;
                margin: 0;
                max-width: 920px;
            }

            .cvli-section-card {
                background: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 18px;
                padding: 1.1rem 1.1rem 0.7rem 1.1rem;
                margin: 1rem 0;
            }

            .cvli-section-title {
                font-size: 1.15rem;
                font-weight: 800;
                color: #f8fafc;
                margin-bottom: 0.25rem;
            }

            .cvli-section-desc {
                font-size: 0.93rem;
                color: rgba(255, 255, 255, 0.70);
                margin-bottom: 0.9rem;
                line-height: 1.5;
            }

            .cvli-grid-status {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.85rem;
                margin: 1rem 0 0.2rem 0;
            }

            .cvli-stat {
                background: rgba(255, 255, 255, 0.025);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
                padding: 0.95rem 1rem;
            }

            .cvli-stat-label {
                font-size: 0.78rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                color: rgba(255, 255, 255, 0.58);
                margin-bottom: 0.35rem;
                font-weight: 700;
            }

            .cvli-stat-value {
                font-size: 1.45rem;
                font-weight: 900;
                color: #ffffff;
                line-height: 1;
            }

            @media (max-width: 980px) {
                .cvli-grid-status {
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }
            }

            @media (max-width: 640px) {
                .cvli-grid-status {
                    grid-template-columns: 1fr;
                }

                .cvli-title {
                    font-size: 1.6rem;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_hero_cvli() -> None:
    """Renderiza o cabeçalho visual do módulo CVLI."""
    st.markdown(
        """
        <div class="cvli-shell">
            <div class="cvli-hero">
                <div class="cvli-kicker">Módulo ativo</div>
                <div class="cvli-title">CVLI</div>
                <p class="cvli-description">
                    Atualize a base de Crimes Violentos Letais Intencionais com segurança, mantendo
                    consistência estrutural entre a base histórica e o arquivo complementar.
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _gerar_excel_download(df: pd.DataFrame) -> bytes:
    """Gera o arquivo Excel final para download."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="CVLI")
    output.seek(0)
    return output.getvalue()


def _limpar_estado_cvli() -> None:
    """Limpa os estados do módulo CVLI."""
    chaves = [
        "cvli_arquivo01",
        "cvli_arquivo02",
        "cvli_drive",
        "cvli_resultado",
    ]
    for chave in chaves:
        if chave in st.session_state:
            del st.session_state[chave]


def interface_cvli() -> None:
    """Interface Streamlit para processamento do módulo CVLI."""
    _aplicar_estilo_cvli()
    _render_hero_cvli()

    st.markdown(
        """
        <div class="cvli-section-card">
            <div class="cvli-section-title">Processamento CVLI</div>
            <div class="cvli-section-desc">
                Envie a base histórica e o arquivo complementar para atualizar a base do indicador.
                O sistema identifica períodos coincidentes, substitui os registros necessários e gera
                o arquivo final pronto para integração com o QGP Online.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        arquivo01 = st.file_uploader(
            "📁 Arquivo 01 - Base de dados CVLI",
            type=["xlsx", "xls"],
            key="cvli_arquivo01",
        )

    with col2:
        arquivo02 = st.file_uploader(
            "📁 Arquivo 02 - Dados complementares",
            type=["xlsx", "xls"],
            key="cvli_arquivo02",
        )

    st.markdown(
        """
        <div class="cvli-section-card">
            <div class="cvli-section-title">Opções adicionais</div>
            <div class="cvli-section-desc">
                Defina opções complementares para o destino do arquivo processado.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    salvar_drive = st.checkbox("💾 Salvar no Google Drive", key="cvli_drive")

    pode_processar = arquivo01 is not None and arquivo02 is not None

    st.markdown(
        """
        <div class="cvli-section-card">
            <div class="cvli-section-title">Execução do processamento</div>
            <div class="cvli-section-desc">
                Inicie o processamento após validar os arquivos carregados. O fluxo aplica a lógica
                de atualização do CVLI, preserva a consistência da base e disponibiliza o resultado
                final para download ao término da execução.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        processar = st.button(
            "Processar CVLI",
            key="processar_cvli",
            type="primary",
            use_container_width=True,
            disabled=not pode_processar,
        )

    with col_btn2:
        limpar = st.button(
            "Limpar seleção",
            key="limpar_cvli",
            type="secondary",
            use_container_width=True,
        )

    if limpar:
        _limpar_estado_cvli()
        st.rerun()

    if processar:
        with st.spinner("Processando dados CVLI..."):
            processador = ProcessadorCVLI()
            resultado = processador.processar(arquivo01, arquivo02)

        st.session_state.cvli_resultado = resultado

    resultado = st.session_state.get("cvli_resultado")

    if not resultado:
        return

    if not resultado["sucesso"]:
        st.error(f"❌ Erro no processamento: {resultado['erro']}")
        return

    acao = "Atualizado" if resultado["houve_substituicao"] else "Complementado"
    excel_bytes = _gerar_excel_download(resultado["df_final"])

    st.success("✅ Processo finalizado com sucesso.")

    st.markdown(
        f"""
        <div class="cvli-section-card">
            <div class="cvli-section-title">Resumo do processamento</div>
            <div class="cvli-section-desc">{resultado["situacao"]}</div>
            <div class="cvli-grid-status">
                <div class="cvli-stat">
                    <div class="cvli-stat-label">Registros adicionados</div>
                    <div class="cvli-stat-value">{resultado["adicionados"]}</div>
                </div>
                <div class="cvli-stat">
                    <div class="cvli-stat-label">Total final</div>
                    <div class="cvli-stat-value">{resultado["total_final"]}</div>
                </div>
                <div class="cvli-stat">
                    <div class="cvli-stat-label">Base inicial</div>
                    <div class="cvli-stat-value">{resultado["total_inicial"]}</div>
                </div>
                <div class="cvli-stat">
                    <div class="cvli-stat-label">Tipo de ação</div>
                    <div class="cvli-stat-value">{acao}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Prévia dos dados processados", expanded=False):
        st.dataframe(
            resultado["df_final"].head(200),
            use_container_width=True,
            hide_index=True,
        )

    st.download_button(
        label="💾 Download do arquivo processado",
        data=excel_bytes,
        file_name=resultado["nome_arquivo"],
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_cvli",
        use_container_width=True,
    )

    if salvar_drive:
        st.warning("🔄 Integração com Google Drive em desenvolvimento.")

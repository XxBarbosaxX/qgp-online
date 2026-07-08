"""
Modulo Acidente de Transito (SPORTAL)
Versao Streamlit adaptada para o QGP Online.
"""

from __future__ import annotations

from io import BytesIO
import re
import unicodedata

import pandas as pd
import streamlit as st
from pyproj import Transformer

from modulos.utils import nome_arquivo_padrao


NOME_ARQUIVO_FINAL = nome_arquivo_padrao(8, "ACIDENTE-DE-TRANSITO-SPORTAL-QGP")


def _aplicar_estilo_acidente_transito() -> None:
    """Aplica estilo visual padronizado ao módulo."""
    st.markdown(
        """
        <style>
            .at-section-card {
                background: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 18px;
                padding: 1.1rem 1.1rem 0.7rem 1.1rem;
                margin: 1rem 0;
            }

            .at-section-title {
                font-size: 1.15rem;
                font-weight: 800;
                color: #f8fafc;
                margin-bottom: 0.25rem;
            }

            .at-section-desc {
                font-size: 0.93rem;
                color: rgba(255, 255, 255, 0.70);
                margin-bottom: 0.9rem;
                line-height: 1.5;
            }

            .at-mini-list {
                margin: 0.6rem 0 0 0;
                padding-left: 1rem;
                color: rgba(255,255,255,0.78);
                font-size: 0.92rem;
            }

            .at-grid-status {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.85rem;
                margin: 1rem 0 0.2rem 0;
            }

            .at-stat {
                background: rgba(255, 255, 255, 0.025);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
                padding: 0.95rem 1rem;
            }

            .at-stat-label {
                font-size: 0.78rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                color: rgba(255, 255, 255, 0.58);
                margin-bottom: 0.35rem;
                font-weight: 700;
            }

            .at-stat-value {
                font-size: 1.20rem;
                font-weight: 900;
                color: #ffffff;
                line-height: 1.15;
                word-break: break-word;
            }

            .at-badge-wrap {
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem;
                margin-top: 0.55rem;
                margin-bottom: 0.15rem;
            }

            .at-badge {
                display: inline-flex;
                align-items: center;
                gap: 0.35rem;
                padding: 0.5rem 0.72rem;
                border-radius: 999px;
                font-size: 0.82rem;
                font-weight: 700;
                border: 1px solid rgba(255, 255, 255, 0.08);
                background: rgba(255, 255, 255, 0.03);
                color: #e5f3ee;
            }

            .at-badge.ok {
                background: rgba(34, 197, 94, 0.10);
                color: #b7f7c9;
                border-color: rgba(34, 197, 94, 0.22);
            }

            .at-badge.warn {
                background: rgba(245, 158, 11, 0.10);
                color: #fde4b0;
                border-color: rgba(245, 158, 11, 0.22);
            }

            .at-badge.info {
                background: rgba(59, 130, 246, 0.10);
                color: #bfdbfe;
                border-color: rgba(59, 130, 246, 0.22);
            }

            @media (max-width: 1180px) {
                .at-grid-status {
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }
            }

            @media (max-width: 640px) {
                .at-grid-status {
                    grid-template-columns: 1fr;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _normalizar_nome_aba(nome: str) -> str:
    nome = str(nome or "").strip()
    nome = unicodedata.normalize("NFKD", nome)
    nome = "".join(c for c in nome if not unicodedata.combining(c))
    nome = nome.upper().strip()
    nome = nome.replace(" ", "").replace("_", "").replace("-", "")
    return nome


def _selecionar_aba_arquivo_02(sheet_names: list[str]) -> str:
    alvo_exato = "ACIDENTEDETRANSITO"

    for aba in sheet_names:
        if _normalizar_nome_aba(aba) == alvo_exato:
            return aba

    for aba in sheet_names:
        nome = _normalizar_nome_aba(aba)
        if "ACIDENTE" in nome and "TRANSITO" in nome:
            return aba

    raise ValueError(
        f"Aba 'Acidente de Trânsito' nao encontrada no Arquivo 02. "
        f"Abas disponiveis: {sheet_names}"
    )


def normalizar_colunas(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def encontrar_coluna_data(df):
    exatos = [c for c in df.columns if str(c).strip().lower() == "data"]
    if exatos:
        return exatos[0]
    aproximados = [c for c in df.columns if "data" in str(c).strip().lower()]
    if aproximados:
        return aproximados[0]
    raise ValueError("Nao foi encontrada a coluna 'Data'.")


def encontrar_coluna_hora(df):
    exatos = [c for c in df.columns if str(c).strip().lower() == "hora"]
    if exatos:
        return exatos[0]
    aproximados = [c for c in df.columns if "hora" in str(c).strip().lower()]
    if aproximados:
        return aproximados[0]
    raise ValueError("Nao foi encontrada a coluna 'Hora'.")


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
        raise ValueError(
            f"Nao foi possivel localizar nenhuma das colunas esperadas: {nomes_possiveis}"
        )
    return None


def valor_numerico_exato(v):
    if pd.isna(v):
        return None

    if isinstance(v, str):
        s = v.strip()
        if s == "":
            return None
        s = s.replace(".", "").replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return None

    try:
        return float(v)
    except Exception:
        return None


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


def criar_coluna_datahora(df, coluna_data, coluna_hora, nome_coluna="__datahora__"):
    df = df.copy()
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


def excluir_coordenadas_invalidas(df, col_lat, col_lon):
    manter = []

    for lat_raw, lon_raw in zip(df[col_lat], df[col_lon]):
        lat = valor_numerico_exato(lat_raw)
        lon = valor_numerico_exato(lon_raw)

        if lat is None or lon is None:
            manter.append(False)
        elif lat == 0 or lon == 0:
            manter.append(False)
        else:
            manter.append(True)

    return df.loc[manter].copy()


def reprojetar_utm_para_wgs84(df, col_y, col_x, col_lat_destino, col_lon_destino):
    df = df.copy()
    transformer = Transformer.from_crs("EPSG:31984", "EPSG:4326", always_xy=True)

    lat_resultado = []
    lon_resultado = []

    for y_raw, x_raw in zip(df[col_y], df[col_x]):
        y = valor_numerico_exato(y_raw)
        x = valor_numerico_exato(x_raw)

        if y is None or x is None:
            lat_resultado.append(pd.NA)
            lon_resultado.append(pd.NA)
        else:
            lon, lat = transformer.transform(x, y)
            lat_resultado.append(lat)
            lon_resultado.append(lon)

    df[col_lat_destino] = lat_resultado
    df[col_lon_destino] = lon_resultado
    return df


def alinhar_colunas_arquivo_02_com_base(df_base, df_novo):
    colunas_base = list(df_base.columns)

    for col in colunas_base:
        if col not in df_novo.columns:
            df_novo[col] = pd.NA

    return df_novo[colunas_base].copy()


def obter_ultimo_datahora(df, coluna_datahora):
    df_valid = df[df[coluna_datahora].notna()].copy()
    if df_valid.empty:
        return None
    return df_valid[coluna_datahora].max()


def filtrar_apenas_registros_posteriores(df, coluna_datahora, limite_datahora):
    if limite_datahora is None:
        return df.copy()
    return df[df[coluna_datahora] > limite_datahora].copy()


def gerar_excel_em_memoria(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="ACIDENTE_TRANSITO_SPORTAL")
    buffer.seek(0)
    return buffer.getvalue()


def processar_acidente_transito(arquivo_01, arquivo_02):
    arquivo_01.seek(0)
    arquivo_02.seek(0)

    xls_base = pd.ExcelFile(arquivo_01)
    xls_novo = pd.ExcelFile(arquivo_02)

    aba_base = xls_base.sheet_names[0]
    aba_novo = _selecionar_aba_arquivo_02(xls_novo.sheet_names)

    df_base = pd.read_excel(xls_base, sheet_name=aba_base)
    df_novo = pd.read_excel(xls_novo, sheet_name=aba_novo)

    df_base = normalizar_colunas(df_base)
    df_novo = normalizar_colunas(df_novo)

    col_data_base = encontrar_coluna_data(df_base)
    col_data_novo = encontrar_coluna_data(df_novo)
    col_hora_base = encontrar_coluna_hora(df_base)
    col_hora_novo = encontrar_coluna_hora(df_novo)

    if col_data_base != col_data_novo:
        df_novo = df_novo.rename(columns={col_data_novo: col_data_base})
    if col_hora_base != col_hora_novo:
        df_novo = df_novo.rename(columns={col_hora_novo: col_hora_base})

    col_data = col_data_base
    col_hora = col_hora_base

    col_lat_base = encontrar_coluna_por_nomes(df_base, ["lat", "latitude"], obrigatoria=True)
    col_lon_base = encontrar_coluna_por_nomes(df_base, ["long", "longitude", "lon"], obrigatoria=True)

    col_lat_novo = encontrar_coluna_por_nomes(df_novo, ["latitude"], obrigatoria=True)
    col_lon_novo = encontrar_coluna_por_nomes(df_novo, ["longitude"], obrigatoria=True)

    total_lido_arquivo_02 = len(df_novo)

    df_novo = excluir_coordenadas_invalidas(df_novo, col_lat_novo, col_lon_novo)
    removidos_invalidos = total_lido_arquivo_02 - len(df_novo)

    if df_novo.empty:
        raise ValueError("Apos excluir coordenadas invalidas, o Arquivo 02 ficou sem registros validos.")

    df_base = criar_coluna_datahora(df_base, col_data, col_hora)
    df_novo = criar_coluna_datahora(df_novo, col_data, col_hora)

    ultimo_datahora_base = obter_ultimo_datahora(df_base, "__datahora__")

    total_antes_filtro_tempo = len(df_novo)
    df_novo_filtrado = filtrar_apenas_registros_posteriores(df_novo, "__datahora__", ultimo_datahora_base)
    removidos_por_datahora = total_antes_filtro_tempo - len(df_novo_filtrado)

    base_sem_aux = df_base.drop(columns=["__datahora__"], errors="ignore").copy()

    if ultimo_datahora_base is None:
        df_novo_util = df_novo.copy()
        situacao = "Base anterior sem Data/Hora valida: Arquivo 02 foi incluido integralmente."
    elif df_novo_filtrado.empty:
        df_novo_util = df_novo_filtrado.copy()
        situacao = "Nenhum registro novo encontrado apos a ultima Data/Hora da base: Arquivo 01 foi mantido sem acrescimos."
    else:
        df_novo_util = df_novo_filtrado.copy()
        situacao = "Base anterior localizada: somente registros posteriores a ultima Data/Hora foram adicionados."

    adicionados = len(df_novo_util)

    if not df_novo_util.empty:
        df_novo_util = reprojetar_utm_para_wgs84(
            df_novo_util,
            col_y=col_lat_novo,
            col_x=col_lon_novo,
            col_lat_destino=col_lat_base,
            col_lon_destino=col_lon_base,
        )
        df_novo_util = alinhar_colunas_arquivo_02_com_base(base_sem_aux, df_novo_util)
        df_final = pd.concat([base_sem_aux, df_novo_util], ignore_index=True)
    else:
        df_final = base_sem_aux.copy()

    df_final = criar_coluna_datahora(df_final, col_data, col_hora)
    df_final = (
        df_final.sort_values(by="__datahora__", ascending=True, na_position="last")
        .reset_index(drop=True)
    )
    df_final = df_final.drop(columns=["__datahora__"], errors="ignore")

    total_final = len(df_final)

    ultima_ref = (
        ultimo_datahora_base.strftime("%d/%m/%Y %H:%M:%S")
        if ultimo_datahora_base is not None else "sem referencia anterior valida"
    )

    resumo = {
        "adicionados": adicionados,
        "total_final": total_final,
        "ultima_datahora_base": ultima_ref,
        "removidos_invalidos": removidos_invalidos,
        "removidos_por_datahora": removidos_por_datahora,
        "situacao": situacao,
        "aba_arquivo_01": aba_base,
        "aba_arquivo_02": aba_novo,
    }

    return df_final, resumo


def _init_state():
    defaults = {
        "acidente_transito_arquivo_01_bytes": None,
        "acidente_transito_arquivo_01_nome": None,
        "acidente_transito_arquivo_02_bytes": None,
        "acidente_transito_arquivo_02_nome": None,
        "acidente_transito_resultado_excel": None,
        "acidente_transito_resultado_df": None,
        "acidente_transito_resumo": None,
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def _limpar_estado_acidente_transito() -> None:
    chaves = [
        "acidente_transito_arquivo_01_bytes",
        "acidente_transito_arquivo_01_nome",
        "acidente_transito_arquivo_02_bytes",
        "acidente_transito_arquivo_02_nome",
        "acidente_transito_resultado_excel",
        "acidente_transito_resultado_df",
        "acidente_transito_resumo",
        "acidente_transito_upload_01",
        "acidente_transito_upload_02",
    ]
    for chave in chaves:
        if chave in st.session_state:
            del st.session_state[chave]


def render():
    _init_state()
    _aplicar_estilo_acidente_transito()

    st.markdown(
        """
        <div class="at-section-card">
            <div class="at-section-title">Processamento de Acidente de Trânsito (SPORTAL)</div>
            <div class="at-section-desc">
                Envie a base histórica e o complemento SPORTAL para atualizar a base
                consolidada, aplicando validação temporal, tratamento de coordenadas
                e padronização final no formato do QGP Online.
            </div>
            <ul class="at-mini-list">
                <li>Identificação automática da aba do complemento.</li>
                <li>Validação e exclusão de coordenadas inválidas.</li>
                <li>Reprojeção de coordenadas UTM para WGS84.</li>
                <li>Inclusão apenas de registros posteriores à última Data/Hora da base.</li>
                <li>Geração de arquivo final consolidado para download.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        arquivo_01 = st.file_uploader(
            "📁 Arquivo 01 - Base histórica",
            type=["xlsx", "xls"],
            key="acidente_transito_upload_01",
        )

    with col2:
        arquivo_02 = st.file_uploader(
            "📁 Arquivo 02 - Complemento SPORTAL",
            type=["xlsx", "xls"],
            key="acidente_transito_upload_02",
        )

    if arquivo_01 is not None:
        arquivo_01.seek(0)
        st.session_state.acidente_transito_arquivo_01_bytes = arquivo_01.read()
        st.session_state.acidente_transito_arquivo_01_nome = arquivo_01.name

    if arquivo_02 is not None:
        arquivo_02.seek(0)
        st.session_state.acidente_transito_arquivo_02_bytes = arquivo_02.read()
        st.session_state.acidente_transito_arquivo_02_nome = arquivo_02.name

    badges_upload = []
    if st.session_state.acidente_transito_arquivo_01_nome:
        badges_upload.append(
            f'<span class="at-badge ok">Base carregada: {st.session_state.acidente_transito_arquivo_01_nome}</span>'
        )
    if st.session_state.acidente_transito_arquivo_02_nome:
        badges_upload.append(
            f'<span class="at-badge ok">Complemento carregado: {st.session_state.acidente_transito_arquivo_02_nome}</span>'
        )

    if badges_upload:
        st.markdown(
            f'<div class="at-badge-wrap">{"".join(badges_upload)}</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div class="at-section-card">
            <div class="at-section-title">Execução do processamento</div>
            <div class="at-section-desc">
                Após validar os arquivos enviados, execute a rotina para consolidar os
                registros novos e gerar o arquivo final do indicador.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    pode_processar = (
        st.session_state.acidente_transito_arquivo_01_bytes is not None
        and st.session_state.acidente_transito_arquivo_02_bytes is not None
    )

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        processar = st.button(
            "Processar Acidente de Trânsito",
            type="primary",
            disabled=not pode_processar,
            use_container_width=True,
            key="btn_processar_acidente_transito",
        )

    with col_btn2:
        limpar = st.button(
            "Limpar seleção",
            use_container_width=True,
            key="btn_limpar_acidente_transito",
        )

    if limpar:
        _limpar_estado_acidente_transito()
        st.rerun()

    if processar:
        try:
            arquivo_01_buffer = BytesIO(st.session_state.acidente_transito_arquivo_01_bytes)
            arquivo_02_buffer = BytesIO(st.session_state.acidente_transito_arquivo_02_bytes)

            with st.spinner("Processando registros de acidente de trânsito..."):
                df_final, resumo = processar_acidente_transito(
                    arquivo_01_buffer,
                    arquivo_02_buffer,
                )
                arquivo_excel_bytes = gerar_excel_em_memoria(df_final)

            st.session_state.acidente_transito_resultado_df = df_final
            st.session_state.acidente_transito_resumo = resumo
            st.session_state.acidente_transito_resultado_excel = arquivo_excel_bytes

            st.success("✅ Processamento concluído com sucesso.")

        except Exception as exc:
            st.exception(exc)

    if (
        st.session_state.acidente_transito_resultado_df is None
        or st.session_state.acidente_transito_resumo is None
    ):
        return

    df_final = st.session_state.acidente_transito_resultado_df
    resumo = st.session_state.acidente_transito_resumo

    st.markdown(
        f"""
        <div class="at-section-card">
            <div class="at-section-title">Resumo do processamento</div>
            <div class="at-section-desc">{resumo.get("situacao", "Processamento concluído.")}</div>
            <div class="at-grid-status">
                <div class="at-stat">
                    <div class="at-stat-label">Registros adicionados</div>
                    <div class="at-stat-value">{resumo.get("adicionados", 0)}</div>
                </div>
                <div class="at-stat">
                    <div class="at-stat-label">Total final</div>
                    <div class="at-stat-value">{resumo.get("total_final", 0)}</div>
                </div>
                <div class="at-stat">
                    <div class="at-stat-label">Coord. inválidas removidas</div>
                    <div class="at-stat-value">{resumo.get("removidos_invalidos", 0)}</div>
                </div>
                <div class="at-stat">
                    <div class="at-stat-label">Filtrados por Data/Hora</div>
                    <div class="at-stat-value">{resumo.get("removidos_por_datahora", 0)}</div>
                </div>
            </div>
            <div class="at-badge-wrap">
                <span class="at-badge info">Aba base: {resumo.get("aba_arquivo_01", "-")}</span>
                <span class="at-badge info">Aba complemento: {resumo.get("aba_arquivo_02", "-")}</span>
                <span class="at-badge info">Última Data/Hora base: {resumo.get("ultima_datahora_base", "-")}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Prévia dos dados processados", expanded=False):
        st.dataframe(df_final.head(200), use_container_width=True, hide_index=True)

    if st.session_state.acidente_transito_resultado_excel is not None:
        st.download_button(
            label="💾 Baixar arquivo final",
            data=st.session_state.acidente_transito_resultado_excel,
            file_name=NOME_ARQUIVO_FINAL,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="acidente_transito_download_final",
            use_container_width=True,
        )


interface_acidente_transito = render

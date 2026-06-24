"""  
Módulo CVP (SPORTAL) - Crimes Violentos contra o Patrimônio
Processamento e atualização de dados CVP do sistema SPORTAL para QGP Online
"""

import pandas as pd
import streamlit as st
from datetime import datetime
from pyproj import Transformer
import io

NOME_ARQUIVO_FINAL = f"2-CVP-SPORTAL-{datetime.now().year}-QGP.xlsx"

def normalizar_colunas(df):
    """Normaliza os nomes das colunas removendo espaços"""
    df.columns = [str(c).strip() for c in df.columns]
    return df

def encontrar_coluna_data(df):
    """Encontra a coluna Data"""
    exatos = [c for c in df.columns if str(c).strip().lower() == "data"]
    if exatos:
        return exatos[0]
    aproximados = [c for c in df.columns if "data" in str(c).strip().lower()]
    if aproximados:
        return aproximados[0]
    raise ValueError("Não foi encontrada a coluna Data.")

def encontrar_coluna_hora(df):
    """Encontra a coluna Hora"""
    exatos = [c for c in df.columns if str(c).strip().lower() == "hora"]
    if exatos:
        return exatos[0]
    aproximados = [c for c in df.columns if "hora" in str(c).strip().lower()]
    if aproximados:
        return aproximados[0]
    raise ValueError("Não foi encontrada a coluna Hora.")

def encontrar_coluna_por_nomes(df, nomes_possiveis, obrigatoria=True):
    """Encontra coluna por lista de nomes possíveis"""
    cols_map = {str(c).strip().lower(): c for c in df.columns}
    for nome in nomes_possiveis:
        if nome.lower() in cols_map:
            return cols_map[nome.lower()]
    for c in df.columns:
        c_l = str(c).strip().lower()
        for nome in nomes_possiveis:
            if nome.lower() in c_l:
                return c
    if obrigatoria:
        raise ValueError(f"Não foi possível localizar nenhuma das colunas esperadas: {nomes_possiveis}")
    return None

def renomear_colunas_equivalentes(df_base, df_novo):
    """Renomeia colunas do DataFrame novo para corresponder ao base"""
    mapa_equivalencias = {
        "AIS": ["AIS-Nova", "AIS Nova", "AIS-NOVA", "ais-nova", "aisnova"],
        "Território": ["Regiões", "Regioes", "Região", "Regiao", "regiões", "regioes", "região", "regiao"],
    }
    
    colunas_base_map = {str(c).strip().lower(): c for c in df_base.columns}
    colunas_novo_map = {str(c).strip().lower(): c for c in df_novo.columns}
    
    renomeacoes = {}
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

def valor_numerico_exato(v):
    """Converte valor para número float"""
    if pd.isna(v):
        return None
    if isinstance(v, str):
        s = v.strip()
        if not s:
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
    """Normaliza data para texto d/m/Y"""
    if pd.isna(v):
        return None
    if isinstance(v, pd.Timestamp):
        return v.strftime("%d/%m/%Y")
    try:
        dt = pd.to_datetime(v, errors='coerce', dayfirst=True)
        if pd.isna(dt):
            return None
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return None

def normalizar_hora_para_texto(v):
    """Normaliza hora para texto H:M:S"""
    if pd.isna(v):
        return None
    if isinstance(v, pd.Timestamp):
        return v.strftime("%H:%M:%S")
    s = str(v).strip()
    if not s:
        return None
    formatos = ["%H:%M:%S", "%H:%M"]
    for fmt in formatos:
        dt = pd.to_datetime(s, errors='coerce', format=fmt)
        if not pd.isna(dt):
            return dt.strftime("%H:%M:%S")
    try:
        dt = pd.to_datetime(s, errors='coerce')
        if not pd.isna(dt):
            return dt.strftime("%H:%M:%S")
    except Exception:
        pass
    return None

def criar_coluna_datahora(df, coluna_data, coluna_hora, nome_coluna="datahora"):
    """Cria coluna DataHora combinando Data e Hora"""
    datas = df[coluna_data].apply(normalizar_data_para_texto)
    horas = df[coluna_hora].apply(normalizar_hora_para_texto)
    combinado = []
    for d, h in zip(datas, horas):
        if d is None or h is None:
            combinado.append(pd.NaT)
        else:
            combinado.append(pd.to_datetime(f"{d} {h}", errors='coerce', dayfirst=True))
    df[nome_coluna] = combinado
    return df

def excluir_coordenadas_invalidas(df, col_lat, col_lon):
    """Remove registros com coordenadas inválidas"""
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

def reprojetar_utm_para_wgs84(df, col_y, col_x, col_lat_destino="LAT", col_lon_destino="LONG"):
    """Converte coordenadas UTM (SIRGAS 2000) para WGS84"""
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


def alinhar_colunas_arquivo_02_com_base(df_base, df_novo):
    """Alinha colunas do arquivo novo com o base"""
    colunas_base = list(df_base.columns)
    df_novo = renomear_colunas_equivalentes(df_base, df_novo)
    for col in colunas_base:
        if col not in df_novo.columns:
            df_novo[col] = pd.NA
    return df_novo[colunas_base]

def obter_ultima_datahora(df, coluna_datahora):
    """Obtém a última DataHora do DataFrame"""
    df_valid = df[df[coluna_datahora].notna()].copy()
    if df_valid.empty:
        return None
    return df_valid[coluna_datahora].max()

def filtrar_apenas_registros_posteriores(df, coluna_datahora, limite_datahora):
    """Filtra apenas registros após determinada DataHora"""
    if limite_datahora is None:
        return df.copy()
    return df[df[coluna_datahora] > limite_datahora].copy()

def gerar_arquivo_excel(df):
    """Gera arquivo Excel em memória"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='CVP-SPORTAL')
    return output.getvalue()

def interface_cvp_sportal():
    """Interface Streamlit para CVP SPORTAL"""
    st.markdown("## 📊 CVP (SPORTAL) - Atualização de Dados")
    st.markdown("### Instruções")
    st.info("""
    📌 **Passo 1:** Faça upload do **Arquivo Base CVP** (arquivo principal com dados históricos)
    
    📌 **Passo 2:** Faça upload do **Arquivo Complemento SPORTAL** (novos registros para adicionar)
    
    ✅ O sistema irá:
    - Verificar coordenadas válidas
    - Converter coordenadas UTM para WGS84
    - Adicionar apenas registros novos (posteriores à última data/hora da base)
    - Gerar arquivo final consolidado
    """)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📁 Arquivo 01 - Base CVP")
        arquivo_base = st.file_uploader(
            "Selecione o arquivo base",
            type=['xlsx', 'xls'],
            key="cvp_sportal_base"
        )
    
    with col2:
        st.markdown("#### 📁 Arquivo 02 - Complemento SPORTAL")
        arquivo_novo = st.file_uploader(
            "Selecione o arquivo complemento",
            type=['xlsx', 'xls'],
            key="cvp_sportal_novo"
        )
    
    if not arquivo_base or not arquivo_novo:
        st.warning("⚠️ Por favor, faça upload dos dois arquivos para continuar.")
        return
    
    if st.button("🚀 Processar Arquivos", type="primary", use_container_width=True):
        try:
            with st.spinner("Processando arquivos..."): 
                # Leitura dos arquivos
                df_base = pd.read_excel(arquivo_base)
                df_novo = pd.read_excel(arquivo_novo)
                
                # Normalização
                df_base = normalizar_colunas(df_base)
                df_novo = normalizar_colunas(df_novo)
                
                # Encontrar colunas
                col_data_base = encontrar_coluna_data(df_base)
                col_data_novo = encontrar_coluna_data(df_novo)
                col_hora_base = encontrar_coluna_hora(df_base)
                col_hora_novo = encontrar_coluna_hora(df_novo)
                
                # Renomear para padronizar
                if col_data_base != col_data_novo:
                    df_novo = df_novo.rename(columns={col_data_novo: col_data_base})
                if col_hora_base != col_hora_novo:
                    df_novo = df_novo.rename(columns={col_hora_novo: col_hora_base})
                
                col_data = col_data_base
                col_hora = col_hora_base
                
                # Coordenadas
                col_lat_base = encontrar_coluna_por_nomes(df_base, ["lat", "latitude"])
                col_lon_base = encontrar_coluna_por_nomes(df_base, ["long", "longitude", "lon"])
                col_lat_novo = encontrar_coluna_por_nomes(df_novo, ["latitude"])
                col_lon_novo = encontrar_coluna_por_nomes(df_novo, ["longitude"])
                
                # Renomear equivalências
                df_novo = renomear_colunas_equivalentes(df_base, df_novo)
                
                total_lido_arquivo_02 = len(df_novo)
                
                # Excluir coordenadas inválidas
                df_novo = excluir_coordenadas_invalidas(df_novo, col_lat_novo, col_lon_novo)
                removidos_invalidos = total_lido_arquivo_02 - len(df_novo)
                
                if df_novo.empty:
                    st.error("❌ Após excluir coordenadas inválidas, o Arquivo 02 ficou sem registros válidos.")
                    return
                
                # Criar DataHora
                df_base = criar_coluna_datahora(df_base, col_data, col_hora)
                df_novo = criar_coluna_datahora(df_novo, col_data, col_hora)
                
                ultima_datahora_base = obter_ultima_datahora(df_base, "datahora")
                
                # Filtrar por data
                total_antes_filtro_tempo = len(df_novo)
                df_novo_filtrado = filtrar_apenas_registros_posteriores(df_novo, "datahora", ultima_datahora_base)
                removidos_por_datahora = total_antes_filtro_tempo - len(df_novo_filtrado)
                
                # Preparar base
                base_sem_aux = df_base.drop(columns=["datahora"])
                
                if ultima_datahora_base is None:
                    df_novo_util = df_novo.copy()
                    situacao = "Base anterior sem DataHora válida → Arquivo 02 foi incluído integralmente."
                elif df_novo_filtrado.empty:
                    df_novo_util = df_novo_filtrado.copy()
                    situacao = "Nenhum registro novo encontrado após a última DataHora da base → Arquivo 01 foi mantido sem acrés cimos."
                else:
                    df_novo_util = df_novo_filtrado.copy()
                    situacao = "Base anterior localizada → somente registros posteriores à última DataHora foram adicionados."
                
                adicionados = len(df_novo_util)
                
                # Reprojetar coordenadas
                if not df_novo_util.empty:
                    df_novo_util = reprojetar_utm_para_wgs84(
                        df_novo_util,
                        col_y=col_lat_novo,
                        col_x=col_lon_novo,
                        col_lat_destino=col_lat_base,
                        col_lon_destino=col_lon_base
                    )
                    df_novo_util = alinhar_colunas_arquivo_02_com_base(base_sem_aux, df_novo_util)
                    df_final = pd.concat([base_sem_aux, df_novo_util], ignore_index=True)
                else:
                    df_final = base_sem_aux.copy()
                
                # Ordenar
                df_final = criar_coluna_datahora(df_final, col_data, col_hora)
                df_final = df_final.sort_values(by="datahora", ascending=True, na_position='last').reset_index(drop=True)
                df_final = df_final.drop(columns=["datahora"])
                
                total_final = len(df_final)
                
                # Mensagem de sucesso
                st.success("✅ Processamento Finalizado com Sucesso!")
                
                st.markdown("### 📈 Resumo do Processamento")
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("Registros Adicionados", adicionados)
                with col_b:
                    st.metric("Total Final", total_final)
                with col_c:
                    ultima_ref = ultima_datahora_base.strftime("%d/%m/%Y %H:%M:%S") if ultima_datahora_base is not None else "N/A"
                    st.metric("Última DataHora Base", ultima_ref)
                
                st.info(f"📋 **Situação:** {situacao}")
                
                if removidos_invalidos > 0:
                    st.warning(f"⚠️ Registros excluídos por coordenadas inválidas: {removidos_invalidos}")
                if removidos_por_datahora > 0:
                    st.warning(f"⚠️ Registros excluídos por serem anteriores/iguais à última DataHora: {removidos_por_datahora}")
                
                # Download
                excel_data = gerar_arquivo_excel(df_final)
                st.download_button(
                    label="📥 Baixar Arquivo Final",
                    data=excel_data,
                    file_name=NOME_ARQUIVO_FINAL,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                
        except Exception as e:
            st.error(f"❌ Erro durante o processamento: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

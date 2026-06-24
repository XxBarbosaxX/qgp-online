"""Módulo TODOS OS INDICADORES
Processamento consolidado de múltiplos indicadores
"""
import pandas as pd
import streamlit as st
from datetime import datetime
import io
import zipfile


class ProcessadorTodosIndicadores:
    """Classe para processar todos os indicadores simultaneamente"""
    
    def __init__(self):
        self.indicadores_disponiveis = [
            "CVLI",
            "CVP (SPORTAL)",
            "CVP (SIP)",
            "PERTURBACAO DO SOSSEGO",
            "DESLOCAMENTO FORCADO",
            "ROUBO DE VEICULO (SPORTAL)",
            "ROUBO DE VEICULO (SIP)",
            "ACIDENTE DE TRANSITO",
            "FURTO DE VEICULO (SPORTAL)",
            "FURTO DE VEICULO (SIP)"
        ]
        self.arquivos_processados = {}
    
    @staticmethod
    def normalizar_colunas(df):
        """Normaliza os nomes das colunas removendo espaços"""
        df.columns = [str(c).strip() for c in df.columns]
        return df
    
    @staticmethod
    def encontrar_coluna_data(df):
        """Encontra a coluna de data no DataFrame"""
        exatos = [c for c in df.columns if str(c).strip().lower() == "data"]
        if exatos:
            return exatos[0]
        aproximados = [c for c in df.columns if "data" in str(c).strip().lower()]
        if aproximados:
            return aproximados[0]
        return None
    
    def processar_arquivo(self, df, nome_indicador, data_inicio, data_fim):
        """Processa um arquivo individual"""
        try:
            df = self.normalizar_colunas(df)
            coluna_data = self.encontrar_coluna_data(df)
            
            if not coluna_data:
                return None, f"Coluna de data não encontrada em {nome_indicador}"
            
            df[coluna_data] = pd.to_datetime(df[coluna_data], errors='coerce')
            df = df.dropna(subset=[coluna_data])
            
            mascara = (df[coluna_data] >= pd.to_datetime(data_inicio)) & \
                     (df[coluna_data] <= pd.to_datetime(data_fim))
            df_filtrado = df[mascara].copy()
            
            if df_filtrado.empty:
                return None, f"Nenhum registro no período para {nome_indicador}"
            
            return df_filtrado, None
            
        except Exception as e:
            return None, f"Erro em {nome_indicador}: {str(e)}"
    
    def gerar_arquivo_excel(self, df, nome_arquivo):
        """Gera arquivo Excel individual"""
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Dados')
        return output.getvalue()
    
    def gerar_zip_consolidado(self):
        """Gera arquivo ZIP com todos os indicadores processados"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for nome, dados in self.arquivos_processados.items():
                zip_file.writestr(nome, dados)
        return zip_buffer.getvalue()


def interface_todos_indicadores():
    """Interface principal do módulo TODOS OS INDICADORES"""
    st.title("📋 Processamento Consolidado")
    st.markdown("### 🔍 TODOS OS INDICADORES")
    st.divider()
    
    processador = ProcessadorTodosIndicadores()
    
    st.info("📌 Este módulo permite processar múltiplos indicadores simultaneamente")
    
    # Seleção de período
    st.subheader("📅 Período de Análise")
    col1, col2 = st.columns(2)
    with col1:
        data_inicio = st.date_input(
            "Data Início",
            value=datetime(datetime.now().year, 1, 1)
        )
    with col2:
        data_fim = st.date_input(
            "Data Fim",
            value=datetime.now()
        )
    
    st.divider()
    
    # Upload de arquivos
    st.subheader("📁 Upload dos Arquivos")
    st.markdown("**Faça upload dos arquivos para cada indicador:**")
    
    arquivos_carregados = {}
    
    # Criar tabs para organizar os uploads
    tab1, tab2, tab3 = st.tabs(["Crime Violento", "Patrimônio", "Outros"])
    
    with tab1:
        st.markdown("#### Crimes Violentos")
        arquivo_cvli = st.file_uploader("CVLI", type=['xlsx', 'xls', 'csv'], key="cvli")
        if arquivo_cvli:
            arquivos_carregados["CVLI"] = arquivo_cvli
        
        arquivo_cvp_sportal = st.file_uploader("CVP (SPORTAL)", type=['xlsx', 'xls', 'csv'], key="cvp_sportal")
        if arquivo_cvp_sportal:
            arquivos_carregados["CVP (SPORTAL)"] = arquivo_cvp_sportal
        
        arquivo_cvp_sip = st.file_uploader("CVP (SIP)", type=['xlsx', 'xls', 'csv'], key="cvp_sip")
        if arquivo_cvp_sip:
            arquivos_carregados["CVP (SIP)"] = arquivo_cvp_sip
    
    with tab2:
        st.markdown("#### Crimes contra o Patrimônio")
        arquivo_roubo_sportal = st.file_uploader("ROUBO DE VEICULO (SPORTAL)", type=['xlsx', 'xls', 'csv'], key="roubo_sportal")
        if arquivo_roubo_sportal:
            arquivos_carregados["ROUBO DE VEICULO (SPORTAL)"] = arquivo_roubo_sportal
        
        arquivo_roubo_sip = st.file_uploader("ROUBO DE VEICULO (SIP)", type=['xlsx', 'xls', 'csv'], key="roubo_sip")
        if arquivo_roubo_sip:
            arquivos_carregados["ROUBO DE VEICULO (SIP)"] = arquivo_roubo_sip
        
        arquivo_furto_sportal = st.file_uploader("FURTO DE VEICULO (SPORTAL)", type=['xlsx', 'xls', 'csv'], key="furto_sportal")
        if arquivo_furto_sportal:
            arquivos_carregados["FURTO DE VEICULO (SPORTAL)"] = arquivo_furto_sportal
        
        arquivo_furto_sip = st.file_uploader("FURTO DE VEICULO (SIP)", type=['xlsx', 'xls', 'csv'], key="furto_sip")
        if arquivo_furto_sip:
            arquivos_carregados["FURTO DE VEICULO (SIP)"] = arquivo_furto_sip
    
    with tab3:
        st.markdown("#### Outros Indicadores")
        arquivo_perturbacao = st.file_uploader("PERTURBACAO DO SOSSEGO", type=['xlsx', 'xls', 'csv'], key="perturbacao")
        if arquivo_perturbacao:
            arquivos_carregados["PERTURBACAO DO SOSSEGO"] = arquivo_perturbacao
        
        arquivo_deslocamento = st.file_uploader("DESLOCAMENTO FORCADO", type=['xlsx', 'xls', 'csv'], key="deslocamento")
        if arquivo_deslocamento:
            arquivos_carregados["DESLOCAMENTO FORCADO"] = arquivo_deslocamento
        
        arquivo_acidente = st.file_uploader("ACIDENTE DE TRANSITO", type=['xlsx', 'xls', 'csv'], key="acidente")
        if arquivo_acidente:
            arquivos_carregados["ACIDENTE DE TRANSITO"] = arquivo_acidente
    
    st.divider()
    
    # Processamento
    if arquivos_carregados:
        st.success(f"✅ {len(arquivos_carregados)} arquivo(s) carregado(s)")
        
        if st.button("🔄 Processar Todos os Indicadores", type="primary", use_container_width=True):
            processador.arquivos_processados = {}
            resultados = []
            erros = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total = len(arquivos_carregados)
            for idx, (nome, arquivo) in enumerate(arquivos_carregados.items()):
                status_text.text(f"Processando {nome}...")
                
                try:
                    # Ler arquivo
                    if arquivo.name.endswith('.csv'):
                        df = pd.read_csv(arquivo)
                    else:
                        df = pd.read_excel(arquivo)
                    
                    # Processar
                    df_processado, erro = processador.processar_arquivo(df, nome, data_inicio, data_fim)
                    
                    if df_processado is not None:
                        # Gerar Excel
                        nome_arquivo = f"{nome.replace(' ', '-')}-{datetime.now().year}-QGP.xlsx"
                        excel_data = processador.gerar_arquivo_excel(df_processado, nome_arquivo)
                        processador.arquivos_processados[nome_arquivo] = excel_data
                        
                        resultados.append({
                            "Indicador": nome,
                            "Status": "✅ Sucesso",
                            "Registros": len(df_processado)
                        })
                    else:
                        erros.append(f"❌ {erro}")
                        resultados.append({
                            "Indicador": nome,
                            "Status": "⚠️ Erro",
                            "Registros": 0
                        })
                
                except Exception as e:
                    erros.append(f"❌ Erro em {nome}: {str(e)}")
                    resultados.append({
                        "Indicador": nome,
                        "Status": "⚠️ Erro",
                        "Registros": 0
                    })
                
                progress_bar.progress((idx + 1) / total)
            
            status_text.text("Processamento concluído!")
            
            # Mostrar resultados
            st.divider()
            st.subheader("📈 Resultados do Processamento")
            
            df_resultados = pd.DataFrame(resultados)
            st.dataframe(df_resultados, use_container_width=True)
            
            # Mostrar erros se houver
            if erros:
                st.warning("⚠️ Alguns indicadores apresentaram problemas:")
                for erro in erros:
                    st.write(erro)
            
            # Botão de download
            if processador.arquivos_processados:
                st.divider()
                st.success(f"✅ {len(processador.arquivos_processados)} indicador(es) processado(s) com sucesso!")
                
                # Gerar ZIP
                zip_data = processador.gerar_zip_consolidado()
                st.download_button(
                    label="📦 Download ZIP com Todos os Indicadores",
                    data=zip_data,
                    file_name=f"QGP-TODOS-INDICADORES-{datetime.now().year}.zip",
                    mime="application/zip",
                    use_container_width=True
                )
    else:
        st.info("👆 Faça upload de pelo menos um arquivo para começar o processamento.")

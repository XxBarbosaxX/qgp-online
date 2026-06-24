def _init_state():
    if "cvp_sip_arquivo_01_bytes" not in st.session_state:
        st.session_state.cvp_sip_arquivo_01_bytes = None
    if "cvp_sip_arquivo_01_nome" not in st.session_state:
        st.session_state.cvp_sip_arquivo_01_nome = None
    if "cvp_sip_arquivo_02_bytes" not in st.session_state:
        st.session_state.cvp_sip_arquivo_02_bytes = None
    if "cvp_sip_arquivo_02_nome" not in st.session_state:
        st.session_state.cvp_sip_arquivo_02_nome = None


def _salvar_uploads():
    arquivo_01 = st.session_state.get("cvp_sip_upload_01")
    arquivo_02 = st.session_state.get("cvp_sip_upload_02")

    if arquivo_01 is not None:
        arquivo_01.seek(0)
        st.session_state.cvp_sip_arquivo_01_bytes = arquivo_01.read()
        st.session_state.cvp_sip_arquivo_01_nome = arquivo_01.name

    if arquivo_02 is not None:
        arquivo_02.seek(0)
        st.session_state.cvp_sip_arquivo_02_bytes = arquivo_02.read()
        st.session_state.cvp_sip_arquivo_02_nome = arquivo_02.name


def render():
    _init_state()

    st.subheader("CVP (SIP) - Geocodificação por Endereço")

    st.markdown(
        """
        Atualiza a base histórica CVP/SIP com geocodificação por endereço.

        **Fluxo**
        - Arquivo 01: base histórica CVP
        - Arquivo 02: complemento SIP
        - Filtra apenas registros posteriores à última Data/Hora
        - Geocodifica somente novas linhas
        - Alinha as colunas com a base histórica
        """
    )

    with st.form("form_cvp_sip_upload"):
        arquivo_01 = st.file_uploader(
            "Arquivo 01 - Base histórica CVP",
            type=["xlsx", "xls"],
            key="cvp_sip_upload_01",
        )

        arquivo_02 = st.file_uploader(
            "Arquivo 02 - Complemento SIP",
            type=["xlsx", "xls"],
            key="cvp_sip_upload_02",
        )

        submitted = st.form_submit_button("Carregar arquivos")

    if submitted:
        _salvar_uploads()
        st.success("Arquivos carregados com sucesso.")

    if st.session_state.cvp_sip_arquivo_01_nome:
        st.info(f"Arquivo 01 carregado: {st.session_state.cvp_sip_arquivo_01_nome}")

    if st.session_state.cvp_sip_arquivo_02_nome:
        st.info(f"Arquivo 02 carregado: {st.session_state.cvp_sip_arquivo_02_nome}")

    pode_processar = (
        st.session_state.cvp_sip_arquivo_01_bytes is not None
        and st.session_state.cvp_sip_arquivo_02_bytes is not None
    )

    if st.button("Processar CVP (SIP)", type="primary", disabled=not pode_processar):
        try:
            from io import BytesIO

            arquivo_01_buffer = BytesIO(st.session_state.cvp_sip_arquivo_01_bytes)
            arquivo_02_buffer = BytesIO(st.session_state.cvp_sip_arquivo_02_bytes)

            with st.spinner("Processando e geocodificando registros..."):
                df_final, resumo = processar_cvp_sip(arquivo_01_buffer, arquivo_02_buffer)

            st.success("Processamento concluído com sucesso.")

            col1, col2, col3 = st.columns(3)
            col1.metric("Novos registros adicionados", resumo["adicionados"])
            col2.metric("Total final da base", resumo["total_final"])
            col3.metric("Registros geocodificados", resumo["geocodificados"])

            st.info(
                f"Última Data/Hora da base: {resumo['ultima_datahora_base']} | "
                f"Removidos por filtro temporal: {resumo['removidos_por_datahora']}"
            )
            st.caption(resumo["situacao"])

            st.dataframe(df_final.head(50), use_container_width=True)

            arquivo_excel = gerar_arquivo_excel(
                df_final,
                nome_aba="CVP_SIP_ENDERECO",
            )

            st.download_button(
                label="Baixar arquivo final",
                data=arquivo_excel,
                file_name=NOME_ARQUIVO_FINAL,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        except Exception as exc:
            st.exception(exc)

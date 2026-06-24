import os
import traceback
import unicodedata
import pandas as pd
from pyproj import Transformer
from tkinter import Tk, filedialog, messagebox

NOME_ARQUIVO_FINAL = "9 - FURTO DE VEICULO_SPORTAL - QGP.xlsx"


def selecionar_arquivo(titulo):
    return filedialog.askopenfilename(
        title=titulo,
        filetypes=[("Arquivos Excel", "*.xlsx *.xls")]
    )


def selecionar_pasta_saida():
    return filedialog.askdirectory(
        title="Selecione a pasta onde o arquivo final serÃ¡ salvo"
    )


def normalizar_colunas(df):
    df.columns = [str(c).strip() for c in df.columns]
    return df


def sem_acento(texto):
    normalizado = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in normalizado if not unicodedata.combining(c)).upper().strip()


def filtrar_ocorrencias_arquivo_02(df):
    col_nome_ocorrencia = encontrar_coluna_por_nomes(
        df,
        ["Nome da OcorrÃªncia", "Nome da Ocorrencia"],
        obrigatoria=True
    )
    col_subnome_ocorrencia = encontrar_coluna_por_nomes(
        df,
        ["Subnome da OcorrÃªncia", "Subnome da Ocorrencia"],
        obrigatoria=True
    )

    nome_alvo = "FURTO DE VEICULO"
    subnomes_excluidos = {"BICICLETA", "BICICLETA DE APLICATIVO"}

    filtro_nome = df[col_nome_ocorrencia].apply(sem_acento) == nome_alvo
    filtro_subnome = ~df[col_subnome_ocorrencia].apply(sem_acento).isin(subnomes_excluidos)

    return df[filtro_nome & filtro_subnome].copy()


def encontrar_coluna_data(df):
    exatos = [c for c in df.columns if str(c).strip().lower() == "data"]
    if exatos:
        return exatos[0]
    aproximados = [c for c in df.columns if "data" in str(c).strip().lower()]
    if aproximados:
        return aproximados[0]
    raise ValueError("NÃ£o foi encontrada a coluna 'Data'.")


def encontrar_coluna_hora(df):
    exatos = [c for c in df.columns if str(c).strip().lower() == "hora"]
    if exatos:
        return exatos[0]
    aproximados = [c for c in df.columns if "hora" in str(c).strip().lower()]
    if aproximados:
        return aproximados[0]
    raise ValueError("NÃ£o foi encontrada a coluna 'Hora'.")


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
        raise ValueError(f"NÃ£o foi possÃ­vel localizar nenhuma das colunas esperadas: {nomes_possiveis}")
    return None


def renomear_colunas_equivalentes(df_base, df_novo):
    mapa_equivalencias = {
        "AIS": ["AISNova", "AIS Nova", "AIS_NOVA", "aisnova", "ais_nova"],
        "TerritÃ³rio": ["RegiÃµes", "Regioes", "RegiÃ£o", "Regiao", "regiÃµes", "regioes", "regiÃ£o", "regiao"]
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

    df_novo = renomear_colunas_equivalentes(df_base, df_novo)

    for col in colunas_base:
        if col not in df_novo.columns:
            df_novo[col] = pd.NA

    return df_novo[colunas_base]


def obter_ultimo_datahora(df, coluna_datahora):
    df_valid = df[df[coluna_datahora].notna()].copy()
    if df_valid.empty:
        return None
    return df_valid[coluna_datahora].max()


def filtrar_apenas_registros_posteriores(df, coluna_datahora, limite_datahora):
    if limite_datahora is None:
        return df.copy()
    return df[df[coluna_datahora] > limite_datahora].copy()


def salvar_excel(df, caminho_saida):
    with pd.ExcelWriter(caminho_saida, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="CVP_SPORTAL")


def processar():
    root = Tk()
    root.withdraw()

    try:
        arquivo_01 = selecionar_arquivo("Selecione o Arquivo 01 - Base CVP")
        if not arquivo_01:
            messagebox.showwarning("Aviso", "Processo cancelado: Arquivo 01 nÃ£o selecionado.")
            return

        arquivo_02 = selecionar_arquivo("Selecione o Arquivo 02 - Complemento SPORTAL")
        if not arquivo_02:
            messagebox.showwarning("Aviso", "Processo cancelado: Arquivo 02 nÃ£o selecionado.")
            return

        pasta_saida = selecionar_pasta_saida()
        if not pasta_saida:
            messagebox.showwarning("Aviso", "Processo cancelado: pasta de destino nÃ£o selecionada.")
            return

        df_base = pd.read_excel(arquivo_01)
        df_novo = pd.read_excel(arquivo_02)

        df_base = normalizar_colunas(df_base)
        df_novo = normalizar_colunas(df_novo)

        total_lido_arquivo_02 = len(df_novo)
        df_novo = filtrar_ocorrencias_arquivo_02(df_novo)
        removidos_por_filtro_ocorrencia = total_lido_arquivo_02 - len(df_novo)

        if df_novo.empty:
            raise ValueError(
                "ApÃ³s filtrar 'Nome da OcorrÃªncia' por 'FURTO DE VEÃCULO' e excluir 'BICICLETA' e "
                "'BICICLETA DE APLICATIVO' em 'Subnome da OcorrÃªncia', o Arquivo 02 ficou sem registros vÃ¡lidos."
            )

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

        df_novo = renomear_colunas_equivalentes(df_base, df_novo)

        total_apos_filtro_ocorrencia = len(df_novo)
        df_novo = excluir_coordenadas_invalidas(df_novo, col_lat_novo, col_lon_novo)
        removidos_invalidos = total_apos_filtro_ocorrencia - len(df_novo)

        if df_novo.empty:
            raise ValueError("ApÃ³s excluir coordenadas invÃ¡lidas, o Arquivo 02 ficou sem registros vÃ¡lidos.")

        df_base = criar_coluna_datahora(df_base, col_data, col_hora)
        df_novo = criar_coluna_datahora(df_novo, col_data, col_hora)

        ultimo_datahora_base = obter_ultimo_datahora(df_base, "__datahora__")

        total_antes_filtro_tempo = len(df_novo)
        df_novo_filtrado = filtrar_apenas_registros_posteriores(df_novo, "__datahora__", ultimo_datahora_base)
        removidos_por_datahora = total_antes_filtro_tempo - len(df_novo_filtrado)

        base_sem_aux = df_base.drop(columns=["__datahora__"])

        if ultimo_datahora_base is None:
            df_novo_util = df_novo.copy()
            situacao = "Base anterior sem Data/Hora vÃ¡lida: Arquivo 02 foi incluÃ­do integralmente."
        elif df_novo_filtrado.empty:
            df_novo_util = df_novo_filtrado.copy()
            situacao = "Nenhum registro novo encontrado apÃ³s a Ãºltima Data/Hora da base: Arquivo 01 foi mantido sem acrÃ©scimos."
        else:
            df_novo_util = df_novo_filtrado.copy()
            situacao = "Base anterior localizada: somente registros posteriores Ã  Ãºltima Data/Hora foram adicionados."

        adicionados = len(df_novo_util)

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

        df_final = criar_coluna_datahora(df_final, col_data, col_hora)
        df_final = df_final.sort_values(by="__datahora__", ascending=True, na_position="last").reset_index(drop=True)
        df_final = df_final.drop(columns=["__datahora__"])

        total_final = len(df_final)

        caminho_saida = os.path.join(pasta_saida, NOME_ARQUIVO_FINAL)
        salvar_excel(df_final, caminho_saida)

        ultima_ref = (
            ultimo_datahora_base.strftime("%d/%m/%Y %H:%M:%S")
            if ultimo_datahora_base is not None else "sem referÃªncia anterior vÃ¡lida"
        )

        mensagem = (
            f"Processo Finalizado, adicionado {adicionados} Furto(s) de VeÃ­culo novo(s), total de {total_final} Furto(s) de VeÃ­culo.\n"
            f"Ãšltima Data/Hora da base: {ultima_ref}\n"
            f"Registros excluÃ­dos pelo filtro de ocorrÃªncia: {removidos_por_filtro_ocorrencia}\n"
            f"Registros excluÃ­dos por coordenadas invÃ¡lidas: {removidos_invalidos}\n"
            f"Registros excluÃ­dos por serem anteriores/iguais Ã  Ãºltima Data/Hora da base: {removidos_por_datahora}\n\n"
            f"{situacao}\n\n"
            f"O arquivo serÃ¡ salvo com o nome\n{NOME_ARQUIVO_FINAL}"
        )

        messagebox.showinfo("Sucesso", mensagem)

    except Exception as e:
        messagebox.showerror("Erro", f"Ocorreu um erro durante o processamento:\n\n{str(e)}")
        traceback.print_exc()


if __name__ == "__main__":
    processar()

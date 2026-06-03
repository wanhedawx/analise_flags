from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
import re
import pandas as pd
import streamlit as st

# REGRAS DO NEGÓCIO
FLAGS_ATIVAS = {"A", "I", "V", "K", "L", "P"}
FLAGS_RISCO = {"B", "D", "F", "X"}

STATUS_COMPRA = {"1", "3", "4", "5", "6"}
STATUS_NAO_COMPRA = {"9"}

st.set_page_config(
    page_title="Análise de Alteração de flag",
    page_icon="📊",
    layout="wide",
)


# FUNÇÕES GERAIS
def moeda(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def numero_br(v):
    try:
        return f"{float(v):,.0f}".replace(",", ".")
    except Exception:
        return "0"


def nome_seguro(nome):
    nome = re.sub(r"\.[A-Za-z0-9]+$", "", str(nome))
    nome = re.sub(r"[^A-Za-z0-9_ -]", "", nome).strip()
    nome = re.sub(r"\s+", "_", nome)
    return nome[:80] or "resultado"


def normaliza_codigo(valor):
    if pd.isna(valor):
        return ""
    s = str(valor).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return re.sub(r"\D", "", s)


def normaliza_flag(valor):
    """Extrai flag letra: A/I/V/K/L/P/B/D/F/X."""
    if pd.isna(valor):
        return ""
    s = str(valor).strip().upper()
    # evita pegar letras de textos longos antes de tentar padrão curto
    tokens = re.findall(r"[A-Z]", s)
    for t in tokens:
        if t in FLAGS_ATIVAS or t in FLAGS_RISCO:
            return t
    return ""


def normaliza_status(valor):
    """Extrai status numérico: 1/3/4/5/6/9."""
    if pd.isna(valor):
        return ""
    s = str(valor).strip()
    if s.endswith(".0"):
        s = s[:-2]
    nums = re.findall(r"\d+", s)
    for n in nums:
        if n in STATUS_COMPRA or n in STATUS_NAO_COMPRA:
            return n
    return ""


def limpa_nome_coluna(nome):
    s = str(nome).strip().upper()
    trocas = {
        "Á": "A", "À": "A", "Ã": "A", "Â": "A",
        "É": "E", "Ê": "E",
        "Í": "I",
        "Ó": "O", "Ô": "O", "Õ": "O",
        "Ú": "U",
        "Ç": "C",
    }
    for a, b in trocas.items():
        s = s.replace(a, b)
    s = re.sub(r"\s+", " ", s)
    return s


def primeira_coluna_existente(df, opcoes, obrigatoria=True, contexto=""):
    mapa = {limpa_nome_coluna(c): c for c in df.columns}
    for op in opcoes:
        chave = limpa_nome_coluna(op)
        if chave in mapa:
            return mapa[chave]
    if obrigatoria:
        raise ValueError(
            f"Não encontrei a coluna necessária {contexto}.\n\n"
            "Procurei por:\n"
            + " | ".join(opcoes)
            + "\n\nColunas disponíveis:\n"
            + "\n".join(map(str, df.columns))
        )
    return None


def colunas_existentes(df, opcoes):
    mapa = {limpa_nome_coluna(c): c for c in df.columns}
    achadas = []
    for op in opcoes:
        chave = limpa_nome_coluna(op)
        if chave in mapa and mapa[chave] not in achadas:
            achadas.append(mapa[chave])
    return achadas


def valor_numerico(serie):
    if isinstance(serie, (int, float)):
        return pd.Series([serie])
    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_numeric(serie, errors="coerce").fillna(0)
    s = (
        serie.astype(str)
        .str.replace("R$", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.strip()
    )
    return pd.to_numeric(s, errors="coerce").fillna(0)


@st.cache_data(show_spinner=False)
def carrega_excel(uploaded_file):
    return pd.read_excel(uploaded_file)


# FLAGS / STATUS DO EMAIL
def carrega_flags_status(uploaded_file):
    df = carrega_excel(uploaded_file)

    # Corrige erro de float sem upper()
    mascara_cabecalho = df.apply(
        lambda r: any("CABEÇALHO DE SISTEMA" in str(x).upper() for x in r), axis=1
    )
    df = df[~mascara_cabecalho].copy()

    col_codigo = primeira_coluna_existente(df, [
        "COD.TOTVS", "COD.TOTVS.1", "CODIGO", "CÓD. PRODUTO", "COD. PRODUTO",
        "COD PRODUTO", "COD_PROD", "Cod_Prod", "COD PROD", "COD.PRODUTO"
    ], contexto="do código do produto no arquivo de alteração")

    col_desc = primeira_coluna_existente(df, [
        "DESCRIÇÃO", "DESCRICAO", "DESC. PRODUTO", "DESC_PROD", "Desc_Prod", "PRODUTO", "DESCRICAO PRODUTO"
    ], obrigatoria=False)

   
    col_ant = primeira_coluna_existente(df, [
        "STATUS ANTERIOR", "FLAG ANTERIOR", "FLAG ANTIGA", "STATUS ANTIGO", "ANTERIOR",
        "STATUS PROD ANTERIOR", "FLAG ABAST ANTERIOR", "FLAG PROD LOJA ANTERIOR", "STATUS PROD LOJA ANTERIOR",
        "STATUS PROD CD ANTERIOR", "FLAG PROD CD ANTERIOR"
    ], contexto="da situação anterior no arquivo de alteração")

    col_nova = primeira_coluna_existente(df, [
        "STATUS PROD", "FLAG ABAST", "FLAG NOVA", "STATUS NOVO", "NOVA FLAG", "NOVO STATUS",
        "FLAG PROD LOJA", "STATUS PROD LOJA", "FLAG PROD CD", "STATUS PROD CD", "STATUS"
    ], contexto="da situação nova no arquivo de alteração")

    out = pd.DataFrame()
    out["CODIGO"] = df[col_codigo].map(normaliza_codigo)
    out["DESCRICAO"] = df[col_desc] if col_desc else ""

    out["VALOR_ANTERIOR_ORIGINAL"] = df[col_ant].astype(str)
    out["VALOR_NOVO_ORIGINAL"] = df[col_nova].astype(str)

    out["FLAG_ANTERIOR"] = df[col_ant].map(normaliza_flag)
    out["FLAG_NOVA"] = df[col_nova].map(normaliza_flag)
    out["STATUS_ANTERIOR"] = df[col_ant].map(normaliza_status)
    out["STATUS_NOVO"] = df[col_nova].map(normaliza_status)

    out = out[out["CODIGO"] != ""].copy()

    def classificar(row):
        fa, fn = row["FLAG_ANTERIOR"], row["FLAG_NOVA"]
        sa, sn = row["STATUS_ANTERIOR"], row["STATUS_NOVO"]

        # Status numérico por loja tem prioridade quando existir
        if sa in STATUS_COMPRA and sn in STATUS_NAO_COMPRA:
            return "RISCO IMPRODUTIVO"
        if sa in STATUS_NAO_COMPRA and sn in STATUS_COMPRA:
            return "RISCO RUPTURA"

        # Flag letra para todas as lojas
        if fa in FLAGS_ATIVAS and fn in FLAGS_RISCO:
            return "RISCO IMPRODUTIVO"
        if fa in FLAGS_RISCO and fn in FLAGS_ATIVAS:
            return "RISCO RUPTURA"

        return "FORA DA REGRA"

    def tipo_regra(row):
        if row["STATUS_ANTERIOR"] and row["STATUS_NOVO"]:
            return "STATUS NUMÉRICO"
        if row["FLAG_ANTERIOR"] and row["FLAG_NOVA"]:
            return "FLAG LETRA"
        return "NÃO IDENTIFICADO"

    out["TIPO_REGRA"] = out.apply(tipo_regra, axis=1)
    out["MOVIMENTO_STATUS"] = out["STATUS_ANTERIOR"] + " -> " + out["STATUS_NOVO"]
    out["MOVIMENTO_FLAG"] = out["FLAG_ANTERIOR"] + " -> " + out["FLAG_NOVA"]
    out["MOVIMENTO"] = out.apply(
        lambda r: r["MOVIMENTO_STATUS"] if r["TIPO_REGRA"] == "STATUS NUMÉRICO" else r["MOVIMENTO_FLAG"],
        axis=1,
    )
    out["SITUACAO"] = out.apply(classificar, axis=1)
    out = out[out["SITUACAO"] != "FORA DA REGRA"].drop_duplicates()
    return out



# CARTEIRA
def carrega_carteira(uploaded_file):
    df = carrega_excel(uploaded_file)

    col_codigo = primeira_coluna_existente(df, [
        "Cod_Prod", "COD_PROD", "CODIGO", "CÓD. PRODUTO", "COD. PRODUTO", "COD PRODUTO", "COD PROD", "COD.PRODUTO"
    ], contexto="do código do produto na carteira")

    col_saldo = primeira_coluna_existente(df, [
        "Saldo R$ (CMV)", "SALDO CMV", "SALDO", "CARTEIRA", "VALOR CARTEIRA", "SALDO R$", "TOTAL CMV"
    ], contexto="do valor de carteira")

    col_qtd = primeira_coluna_existente(df, [
        "Saldo Qtd", "SALDO QTD", "QTD SALDO", "Quantidade Saldo", "QUANTIDADE SALDO",
        "QTD CARTEIRA", "CARTEIRA QTD", "Quantidade", "QTD"
    ], obrigatoria=False)

    col_pre_val = primeira_coluna_existente(df, [
        "Pré-nota R$ (CMV)", "PRE-NOTA R$ (CMV)", "PRÉ-NOTA CMV", "PRE NOTA CMV", "PRE NOTA R$", "PRÉ NOTA R$"
    ], obrigatoria=False)

    col_nao_fat = primeira_coluna_existente(df, [
        "Não Faturado R$ (CMV)", "NAO FATURADO R$ (CMV)", "NÃO FATURADO", "NAO FATURADO", "NAO FATURADO CMV"
    ], obrigatoria=False)

    col_pre_num = primeira_coluna_existente(df, [
        "Pré-Nota", "PRE-NOTA", "PRE NOTA", "PRÉ NOTA", "NUM PRE NOTA", "Nº PRE NOTA"
    ], obrigatoria=False)

    df["CODIGO"] = df[col_codigo].map(normaliza_codigo)
    df["CARTEIRA_QTD"] = valor_numerico(df[col_qtd]) if col_qtd else 0
    df["CARTEIRA_CMV"] = valor_numerico(df[col_saldo])
    df["PRE_NOTA_CMV"] = valor_numerico(df[col_pre_val]) if col_pre_val else 0
    df["NAO_FATURADO_CMV"] = valor_numerico(df[col_nao_fat]) if col_nao_fat else df["CARTEIRA_CMV"] - df["PRE_NOTA_CMV"]

    if col_pre_num:
        pre = df[col_pre_num].astype(str).str.strip()
        df["TEM_PRE_NOTA"] = df[col_pre_num].notna() & (~pre.isin(["", "0", "0.0", "nan", "NaN", "None"]))
    else:
        df["TEM_PRE_NOTA"] = df["PRE_NOTA_CMV"] > 0

    return df.groupby("CODIGO", as_index=False).agg(
        CARTEIRA_QTD=("CARTEIRA_QTD", "sum"),
        CARTEIRA_CMV=("CARTEIRA_CMV", "sum"),
        PRE_NOTA_CMV=("PRE_NOTA_CMV", "sum"),
        NAO_FATURADO_CMV=("NAO_FATURADO_CMV", "sum"),
        TEM_PRE_NOTA=("TEM_PRE_NOTA", "max"),
    )


# =========================
# COBERTURA / ESTOQUE
# =========================
def soma_grupo(df, opcoes):
    cols = colunas_existentes(df, opcoes)
    if not cols:
        return pd.Series(0, index=df.index), []
    total = pd.Series(0.0, index=df.index)
    for c in cols:
        total = total + valor_numerico(df[c])
    return total, cols


def carrega_cobertura(uploaded_file):
    df = carrega_excel(uploaded_file)

    col_codigo = primeira_coluna_existente(df, [
        "CÓD. PRODUTO", "COD. PRODUTO", "CODIGO", "COD_PROD", "Cod_Prod", "COD PRODUTO", "COD PROD", "COD.PRODUTO"
    ], contexto="do código do produto na cobertura")

    col_cmv = primeira_coluna_existente(df, [
        "VLR CMV POND.", "CMV", "CUSTO", "CUSTO MEDIO", "CUSTO MÉDIO", "CMV BASE"
    ], obrigatoria=False)

    disp_venda, cols_disp = soma_grupo(df, [
        "DISP. VEND.", "QTD DISP. VENDA", "DISP VEND", "DISP VENDA", "DISPONIVEL VENDA", "DISPONÍVEL VENDA"
    ])

    cd_atacados, cols_cd = soma_grupo(df, [
        "EST. CDAL DISP", "EST. CDAL DISP.",
        "EST. ATCE DISP", "EST. ATCE DISP.",
        "EST. ATPB DISP", "EST. ATPB DISP.",
    ])

    reserva, cols_reserva = soma_grupo(df, [
        "RESERVA CDALxLOJA", "RESERVA CDAL X LOJA", "RESERVA CDAL LOJA",
        "RESERVA ATCExLOJA", "RESERVA ATCE X LOJA", "RESERVA ATCE LOJA",
        "RESERVA ATPBxLOJA", "RESERVA ATPB X LOJA", "RESERVA ATPB LOJA",
        "RESERVA LOJAxLOJA", "RESERVA LOJA X LOJA",
    ])

    transito, cols_transito = soma_grupo(df, [
        "FAT. CDAL", "FAT CDAL",
        "FAT. ATCE", "FAT ATCE",
        "FAT. ATPB", "FAT ATPB",
        "FAT. LOJA", "FAT LOJA",
    ])

    df["CODIGO"] = df[col_codigo].map(normaliza_codigo)
    df["DISP_VENDA_QTD"] = disp_venda
    df["CD_ATACADOS_QTD"] = cd_atacados
    df["RESERVA_QTD"] = reserva
    df["TRANSITO_QTD"] = transito
    df["ESTOQUE_IMPACTO_QTD"] = (
        df["DISP_VENDA_QTD"] + df["CD_ATACADOS_QTD"] + df["RESERVA_QTD"] + df["TRANSITO_QTD"]
    )

    if col_cmv:
        df["CMV_UNITARIO"] = valor_numerico(df[col_cmv])
    else:
        df["CMV_UNITARIO"] = 0

    df["DISP_VENDA_VALOR"] = df["DISP_VENDA_QTD"] * df["CMV_UNITARIO"]
    df["CD_ATACADOS_VALOR"] = df["CD_ATACADOS_QTD"] * df["CMV_UNITARIO"]
    df["RESERVA_VALOR"] = df["RESERVA_QTD"] * df["CMV_UNITARIO"]
    df["TRANSITO_VALOR"] = df["TRANSITO_QTD"] * df["CMV_UNITARIO"]
    df["ESTOQUE_IMPACTO_VALOR"] = df["ESTOQUE_IMPACTO_QTD"] * df["CMV_UNITARIO"]

    return df.groupby("CODIGO", as_index=False).agg(
        DISP_VENDA_QTD=("DISP_VENDA_QTD", "sum"),
        DISP_VENDA_VALOR=("DISP_VENDA_VALOR", "sum"),
        CD_ATACADOS_QTD=("CD_ATACADOS_QTD", "sum"),
        CD_ATACADOS_VALOR=("CD_ATACADOS_VALOR", "sum"),
        RESERVA_QTD=("RESERVA_QTD", "sum"),
        RESERVA_VALOR=("RESERVA_VALOR", "sum"),
        TRANSITO_QTD=("TRANSITO_QTD", "sum"),
        TRANSITO_VALOR=("TRANSITO_VALOR", "sum"),
        ESTOQUE_IMPACTO_QTD=("ESTOQUE_IMPACTO_QTD", "sum"),
        ESTOQUE_IMPACTO_VALOR=("ESTOQUE_IMPACTO_VALOR", "sum"),
    )



# ANÁLISE
def montar_analise(arq_alteracao, carteira, cobertura):
    alteracoes = carrega_flags_status(arq_alteracao)
    base = alteracoes.merge(carteira, on="CODIGO", how="left").merge(cobertura, on="CODIGO", how="left")

    numericas = [
        "CARTEIRA_QTD", "CARTEIRA_CMV", "PRE_NOTA_CMV", "NAO_FATURADO_CMV",
        "DISP_VENDA_QTD", "DISP_VENDA_VALOR",
        "CD_ATACADOS_QTD", "CD_ATACADOS_VALOR",
        "RESERVA_QTD", "RESERVA_VALOR",
        "TRANSITO_QTD", "TRANSITO_VALOR",
        "ESTOQUE_IMPACTO_QTD", "ESTOQUE_IMPACTO_VALOR",
    ]
    for c in numericas:
        if c not in base.columns:
            base[c] = 0
        base[c] = pd.to_numeric(base[c], errors="coerce").fillna(0)

    base["TEM_PRE_NOTA"] = base["TEM_PRE_NOTA"].fillna(False)
    base["PRE_NOTA"] = base["TEM_PRE_NOTA"].map(lambda x: "SIM" if bool(x) else "NÃO")

    def situacao_operacional(row):
        partes = []
        partes.append("TEM CARTEIRA" if row["CARTEIRA_CMV"] > 0 or row["CARTEIRA_QTD"] > 0 else "SEM CARTEIRA")
        partes.append("TEM DISP VENDA" if row["DISP_VENDA_QTD"] > 0 else "SEM DISP VENDA")
        partes.append("TEM CD/ATACADOS" if row["CD_ATACADOS_QTD"] > 0 else "SEM CD/ATACADOS")
        partes.append("TEM RESERVA" if row["RESERVA_QTD"] > 0 else "SEM RESERVA")
        partes.append("TEM TRÂNSITO" if row["TRANSITO_QTD"] > 0 else "SEM TRÂNSITO")
        partes.append("COM PRÉ-NOTA" if bool(row["TEM_PRE_NOTA"]) else "SEM PRÉ-NOTA")
        return " | ".join(partes)

    def acao_sugerida(row):
        if row["SITUACAO"] == "RISCO IMPRODUTIVO":
            return "Produto saindo do abastecimento/sortimento: revisar carteira, estoque, reservas e trânsito para evitar improdutivo."
        if row["SITUACAO"] == "RISCO RUPTURA":
            if row["ESTOQUE_IMPACTO_QTD"] <= 0 and row["CARTEIRA_QTD"] <= 0 and row["CARTEIRA_CMV"] <= 0:
                return "Produto voltando para compra/ativo sem carteira e sem estoque: alto risco de ruptura."
            return "Produto voltando para compra/ativo: validar cobertura existente e necessidade de compra."
        return ""

    base["SITUACAO_OPERACIONAL"] = base.apply(situacao_operacional, axis=1)
    base["ACAO_SUGERIDA"] = base.apply(acao_sugerida, axis=1)

    resumo = base.groupby("SITUACAO", as_index=False).agg(
        ITENS=("CODIGO", "nunique"),
        CARTEIRA_QTD=("CARTEIRA_QTD", "sum"),
        CARTEIRA_CMV=("CARTEIRA_CMV", "sum"),
        PRE_NOTA_CMV=("PRE_NOTA_CMV", "sum"),
        NAO_FATURADO_CMV=("NAO_FATURADO_CMV", "sum"),
        DISP_VENDA_QTD=("DISP_VENDA_QTD", "sum"),
        DISP_VENDA_VALOR=("DISP_VENDA_VALOR", "sum"),
        CD_ATACADOS_QTD=("CD_ATACADOS_QTD", "sum"),
        CD_ATACADOS_VALOR=("CD_ATACADOS_VALOR", "sum"),
        RESERVA_QTD=("RESERVA_QTD", "sum"),
        RESERVA_VALOR=("RESERVA_VALOR", "sum"),
        TRANSITO_QTD=("TRANSITO_QTD", "sum"),
        TRANSITO_VALOR=("TRANSITO_VALOR", "sum"),
        ESTOQUE_IMPACTO_QTD=("ESTOQUE_IMPACTO_QTD", "sum"),
        ESTOQUE_IMPACTO_VALOR=("ESTOQUE_IMPACTO_VALOR", "sum"),
    )

    por_movimento = base.groupby(["SITUACAO", "TIPO_REGRA", "MOVIMENTO"], as_index=False).agg(
        ITENS=("CODIGO", "nunique"),
        CARTEIRA_QTD=("CARTEIRA_QTD", "sum"),
        CARTEIRA_CMV=("CARTEIRA_CMV", "sum"),
        DISP_VENDA_QTD=("DISP_VENDA_QTD", "sum"),
        CD_ATACADOS_QTD=("CD_ATACADOS_QTD", "sum"),
        RESERVA_QTD=("RESERVA_QTD", "sum"),
        TRANSITO_QTD=("TRANSITO_QTD", "sum"),
        ESTOQUE_IMPACTO_QTD=("ESTOQUE_IMPACTO_QTD", "sum"),
        ESTOQUE_IMPACTO_VALOR=("ESTOQUE_IMPACTO_VALOR", "sum"),
    )

    return base, resumo, por_movimento



# EXPORTAÇÃO
def gerar_excel(base, resumo, por_movimento):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        resumo.to_excel(writer, sheet_name="Resumo", index=False)
        por_movimento.to_excel(writer, sheet_name="Por Movimento", index=False)
        base.to_excel(writer, sheet_name="Detalhe", index=False)

        for situacao, dados in base.groupby("SITUACAO"):
            nome = re.sub(r"[^A-Za-z0-9 ]", "", situacao)[:31]
            dados.to_excel(writer, sheet_name=nome, index=False)

        wb = writer.book
        for ws in wb.worksheets:
            ws.freeze_panes = "A2"
            for cell in ws[1]:
                cell.font = cell.font.copy(bold=True)
            for col in ws.columns:
                max_len = 0
                col_letter = col[0].column_letter
                for cell in col:
                    if cell.value is not None:
                        max_len = max(max_len, len(str(cell.value)))
                ws.column_dimensions[col_letter].width = min(max(max_len + 2, 12), 45)

    output.seek(0)
    return output.getvalue()


def gerar_zip(resultados):
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as zf:
        for nome_arquivo, excel_bytes in resultados:
            zf.writestr(nome_arquivo, excel_bytes)
    output.seek(0)
    return output.getvalue()


def formatar_tabela(df):
    money_cols = [
        "CARTEIRA_CMV", "PRE_NOTA_CMV", "NAO_FATURADO_CMV",
        "DISP_VENDA_VALOR", "CD_ATACADOS_VALOR", "RESERVA_VALOR", "TRANSITO_VALOR",
        "ESTOQUE_IMPACTO_VALOR",
    ]
    fmt = {c: moeda for c in money_cols if c in df.columns}

    qtd_cols = [
        "ITENS", "CARTEIRA_QTD", "DISP_VENDA_QTD", "CD_ATACADOS_QTD",
        "RESERVA_QTD", "TRANSITO_QTD", "ESTOQUE_IMPACTO_QTD",
    ]
    for c in qtd_cols:
        if c in df.columns:
            fmt[c] = "{:.0f}"
    return df.style.format(fmt)


# TELA STREAMLIT

st.title("📊 Análise de alteração de flag")
st.caption("Analisa flags/letras e status/números, cruzando com carteira, pré-nota, disponibilidade, CD/atacados, reserva e trânsito.")

with st.sidebar:
    st.header("Importar arquivos")
    arq_alteracoes_lista = st.file_uploader(
        "1) Alteração de flag/status",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        help="Você pode selecionar um ou vários arquivos recebidos por e-mail.",
    )
    arq_carteira = st.file_uploader("2) Carteira com agendamento", type=["xlsx", "xls"])
    arq_cobertura = st.file_uploader("3) Cobertura / Cobertura Pura", type=["xlsx", "xls"])

if not (arq_alteracoes_lista and arq_carteira and arq_cobertura):
    st.info("Importe a carteira, a cobertura e pelo menos 1 arquivo de alteração na lateral.")
    st.stop()

try:
    with st.spinner("Lendo carteira e cobertura..."):
        carteira = carrega_carteira(arq_carteira)
        cobertura = carrega_cobertura(arq_cobertura)

    resultados_zip = []
    bases_consolidadas = []

    for idx, arq_alteracao in enumerate(arq_alteracoes_lista, start=1):
        nome_base = nome_seguro(arq_alteracao.name)

        with st.spinner(f"Processando {arq_alteracao.name}..."):
            base, resumo, por_movimento = montar_analise(arq_alteracao, carteira, cobertura)
            excel_bytes = gerar_excel(base, resumo, por_movimento)
            resultados_zip.append((f"resultado_{nome_base}.xlsx", excel_bytes))
            base_tmp = base.copy()
            base_tmp["ARQUIVO_ALTERACAO"] = arq_alteracao.name
            bases_consolidadas.append(base_tmp)

        st.markdown("---")
        st.subheader(f"📄 {idx}. {arq_alteracao.name}")

        total_itens = int(base["CODIGO"].nunique())
        total_carteira_qtd = base["CARTEIRA_QTD"].sum()
        total_carteira = base["CARTEIRA_CMV"].sum()
        total_impacto_qtd = base["ESTOQUE_IMPACTO_QTD"].sum()
        total_impacto_valor = base["ESTOQUE_IMPACTO_VALOR"].sum()
        qtd_improd = int(base.loc[base["SITUACAO"] == "RISCO IMPRODUTIVO", "CODIGO"].nunique())
        qtd_rupt = int(base.loc[base["SITUACAO"] == "RISCO RUPTURA", "CODIGO"].nunique())

        c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
        c1.metric("Itens", numero_br(total_itens))
        c2.metric("Qtd Carteira", numero_br(total_carteira_qtd))
        c3.metric("Carteira R$", moeda(total_carteira))
        c4.metric("Estoque Impacto Qtd", numero_br(total_impacto_qtd))
        c5.metric("Estoque Impacto R$", moeda(total_impacto_valor))
        c6.metric("Risco Improdutivo", numero_br(qtd_improd))
        c7.metric("Risco Ruptura", numero_br(qtd_rupt))

        st.download_button(
            f"⬇️ Baixar Excel - {arq_alteracao.name}",
            data=excel_bytes,
            file_name=f"resultado_{nome_base}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"download_excel_{idx}_{nome_base}",
        )

        aba1, aba2, aba3, aba4 = st.tabs(["Resumo", "Por movimento", "Detalhe", "Filtros"])

        with aba1:
            st.subheader("Resumo por situação")
            ordem_resumo = [
                "SITUACAO", "ITENS", "CARTEIRA_QTD", "CARTEIRA_CMV", "PRE_NOTA_CMV", "NAO_FATURADO_CMV",
                "DISP_VENDA_QTD", "DISP_VENDA_VALOR",
                "CD_ATACADOS_QTD", "CD_ATACADOS_VALOR",
                "RESERVA_QTD", "RESERVA_VALOR",
                "TRANSITO_QTD", "TRANSITO_VALOR",
                "ESTOQUE_IMPACTO_QTD", "ESTOQUE_IMPACTO_VALOR",
            ]
            ordem_resumo = [c for c in ordem_resumo if c in resumo.columns]
            st.dataframe(formatar_tabela(resumo[ordem_resumo]), use_container_width=True, hide_index=True)

        with aba2:
            st.subheader("Resumo por movimento")
            st.dataframe(formatar_tabela(por_movimento), use_container_width=True, hide_index=True)

        with aba3:
            st.subheader("Detalhe dos produtos")
            colunas = [
                "CODIGO", "DESCRICAO", "TIPO_REGRA", "MOVIMENTO", "SITUACAO",
                "STATUS_ANTERIOR", "STATUS_NOVO", "FLAG_ANTERIOR", "FLAG_NOVA",
                "CARTEIRA_QTD", "CARTEIRA_CMV", "PRE_NOTA_CMV", "NAO_FATURADO_CMV", "PRE_NOTA",
                "DISP_VENDA_QTD", "DISP_VENDA_VALOR",
                "CD_ATACADOS_QTD", "CD_ATACADOS_VALOR",
                "RESERVA_QTD", "RESERVA_VALOR",
                "TRANSITO_QTD", "TRANSITO_VALOR",
                "ESTOQUE_IMPACTO_QTD", "ESTOQUE_IMPACTO_VALOR",
                "SITUACAO_OPERACIONAL", "ACAO_SUGERIDA",
            ]
            colunas = [c for c in colunas if c in base.columns]
            st.dataframe(formatar_tabela(base[colunas]), use_container_width=True, hide_index=True)

        with aba4:
            st.subheader("Consultar produto ou situação")
            situacoes = ["Todas"] + sorted(base["SITUACAO"].dropna().unique().tolist())
            sit = st.selectbox("Situação", situacoes, key=f"situacao_{idx}_{nome_base}")
            busca = st.text_input("Buscar por código ou descrição", key=f"busca_{idx}_{nome_base}")

            filtrado = base.copy()
            if sit != "Todas":
                filtrado = filtrado[filtrado["SITUACAO"] == sit]
            if busca.strip():
                b = busca.strip().upper()
                filtrado = filtrado[
                    filtrado["CODIGO"].astype(str).str.upper().str.contains(b, na=False)
                    | filtrado["DESCRICAO"].astype(str).str.upper().str.contains(b, na=False)
                ]
            st.dataframe(formatar_tabela(filtrado[colunas]), use_container_width=True, hide_index=True)

    if len(resultados_zip) > 1:
        st.markdown("---")
        zip_bytes = gerar_zip(resultados_zip)
        st.download_button(
            "⬇️ Baixar todos os resultados em ZIP",
            data=zip_bytes,
            file_name="resultados_analise_alteracoes.zip",
            mime="application/zip",
        )

    if len(bases_consolidadas) > 1:
        st.markdown("---")
        st.subheader("Consolidado de todos os arquivos")
        base_geral = pd.concat(bases_consolidadas, ignore_index=True)
        resumo_geral = base_geral.groupby("SITUACAO", as_index=False).agg(
            ITENS=("CODIGO", "nunique"),
            CARTEIRA_QTD=("CARTEIRA_QTD", "sum"),
            CARTEIRA_CMV=("CARTEIRA_CMV", "sum"),
            PRE_NOTA_CMV=("PRE_NOTA_CMV", "sum"),
            NAO_FATURADO_CMV=("NAO_FATURADO_CMV", "sum"),
            DISP_VENDA_QTD=("DISP_VENDA_QTD", "sum"),
            DISP_VENDA_VALOR=("DISP_VENDA_VALOR", "sum"),
            CD_ATACADOS_QTD=("CD_ATACADOS_QTD", "sum"),
            CD_ATACADOS_VALOR=("CD_ATACADOS_VALOR", "sum"),
            RESERVA_QTD=("RESERVA_QTD", "sum"),
            RESERVA_VALOR=("RESERVA_VALOR", "sum"),
            TRANSITO_QTD=("TRANSITO_QTD", "sum"),
            TRANSITO_VALOR=("TRANSITO_VALOR", "sum"),
            ESTOQUE_IMPACTO_QTD=("ESTOQUE_IMPACTO_QTD", "sum"),
            ESTOQUE_IMPACTO_VALOR=("ESTOQUE_IMPACTO_VALOR", "sum"),
        )
        st.dataframe(formatar_tabela(resumo_geral), use_container_width=True, hide_index=True)

except Exception as e:
    st.error("Erro na análise")
    st.exception(e)

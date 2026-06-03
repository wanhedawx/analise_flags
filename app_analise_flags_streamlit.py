from io import BytesIO
from pathlib import Path
import re
import pandas as pd
import streamlit as st

FLAGS_COMPRA = {"A", "I", "V", "K", "L", "P"}
FLAGS_RISCO = {"B", "D", "F", "X"}

STATUS_COMPRA = {"1", "3", "4", "5", "6"}
STATUS_NAO_COMPRA = {"9"}
STATUS_CD_LOJA = {"1", "6"}

st.set_page_config(
    page_title="Análise de Flags",
    layout="wide",
)


# =========================
# ESTILO VISUAL DO APP
# =========================
def aplicar_layout():
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

            :root {
                --laranja: #f45b0b;
                --laranja-2: #ff7a1a;
                --amarelo: #f4bd24;
                --preto: #1f1913;
                --preto-2: #2b251f;
                --fundo: #f7f2ec;
                --card: #ffffff;
                --texto: #081733;
                --muted: #667085;
                --borda: #eee1d4;
            }

            html, body, [class*="css"] {
                font-family: 'Inter', sans-serif !important;
            }

            .stApp {
                background: linear-gradient(90deg, #f7f2ec 0%, #f7f2ec 72%, #fde9dc 72%, #fde9dc 100%);
                color: var(--texto);
            }

            section[data-testid="stSidebar"] {
                background: var(--preto) !important;
                border-right: 0 !important;
            }

            section[data-testid="stSidebar"] * {
                color: #ffffff !important;
            }

            section[data-testid="stSidebar"] h1,
            section[data-testid="stSidebar"] h2,
            section[data-testid="stSidebar"] h3,
            section[data-testid="stSidebar"] .stMarkdown {
                color: #ffffff !important;
            }

            section[data-testid="stSidebar"] [data-testid="stFileUploader"] {
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 18px;
                padding: 12px;
                margin-bottom: 14px;
            }

            section[data-testid="stSidebar"] [data-testid="stFileUploader"] button {
                border-radius: 12px !important;
                border: 1px solid rgba(244,91,11,.55) !important;
                background: rgba(244,91,11,.12) !important;
            }

            section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
                background: rgba(255,255,255,0.08) !important;
                border: 1px dashed rgba(255,255,255,0.25) !important;
                border-radius: 16px !important;
            }

            .main .block-container {
                max-width: 1240px;
                padding-top: 2.2rem;
                padding-bottom: 3rem;
            }

            .app-hero {
                background: rgba(255,255,255,0.82);
                border: 1px solid var(--borda);
                border-radius: 26px;
                padding: 26px 30px;
                box-shadow: 8px 8px 0 rgba(31,25,19,.14);
                margin-bottom: 22px;
            }

            .brand-line {
                display: flex;
                align-items: center;
                gap: 16px;
                margin-bottom: 4px;
            }

            .brand-mark {
                width: 62px;
                height: 62px;
                border-radius: 50%;
                background: #fff2e7;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 900;
                color: var(--laranja);
                font-size: 24px;
                letter-spacing: -5px;
            }

            .app-title {
                font-size: 38px;
                line-height: 1.08;
                font-weight: 800;
                color: var(--texto);
                margin: 0;
            }

            .app-subtitle {
                color: var(--muted);
                font-size: 15px;
                margin: 8px 0 0 80px;
            }

            .sidebar-brand {
                margin: 24px 0 34px 0;
                padding: 8px 4px;
            }

            .sidebar-logo {
                font-size: 52px;
                line-height: 1;
                color: var(--laranja) !important;
                font-weight: 900;
                letter-spacing: -8px;
                margin-bottom: 28px;
            }

            .sidebar-title {
                font-size: 22px;
                line-height: 1.12;
                font-weight: 800;
                margin-bottom: 24px;
                white-space: nowrap;
            }

            .sidebar-dash {
                width: 42px;
                height: 4px;
                background: var(--laranja);
                border-radius: 999px;
                margin-bottom: 28px;
            }

            .sidebar-subtitle {
                color: rgba(255,255,255,.82) !important;
                font-size: 14px;
                line-height: 1.35;
            }

            div[data-testid="stMetric"] {
                background: var(--card);
                border: 1px solid var(--borda);
                border-radius: 18px;
                padding: 18px 18px;
                box-shadow: 0 8px 18px rgba(31,25,19,.07);
            }

            div[data-testid="stMetric"] label {
                color: var(--muted) !important;
                font-weight: 700 !important;
            }

            div[data-testid="stMetric"] [data-testid="stMetricValue"] {
                color: var(--texto) !important;
                font-weight: 800 !important;
            }

            .stAlert {
                border-radius: 16px !important;
                border: 1px solid var(--borda) !important;
            }

            .stButton > button,
            .stDownloadButton > button {
                background: linear-gradient(90deg, var(--laranja), #ef5206) !important;
                color: white !important;
                border: 0 !important;
                border-radius: 14px !important;
                padding: 0.72rem 1.05rem !important;
                font-weight: 800 !important;
                box-shadow: 0 8px 16px rgba(244,91,11,.22);
            }

            .stTabs [data-baseweb="tab-list"] {
                gap: 8px;
                border-bottom: 1px solid var(--borda);
            }

            .stTabs [data-baseweb="tab"] {
                background: #fff;
                border-radius: 14px 14px 0 0;
                padding: 10px 16px;
                color: var(--muted);
                font-weight: 800;
            }

            .stTabs [aria-selected="true"] {
                color: var(--laranja) !important;
                border-bottom: 3px solid var(--laranja) !important;
            }

            h1, h2, h3 {
                color: var(--texto) !important;
                font-weight: 800 !important;
            }

            [data-testid="stDataFrame"] {
                background: #fff;
                border-radius: 18px;
                padding: 8px;
                border: 1px solid var(--borda);
                box-shadow: 0 8px 18px rgba(31,25,19,.05);
            }

            input, textarea, [data-baseweb="select"] > div {
                border-radius: 14px !important;
                border-color: #f0c5a7 !important;
                background: #fff !important;
                color: #111827 !important;
            }

            .stTextInput input,
            .stSelectbox div[data-baseweb="select"],
            .stSelectbox div[data-baseweb="select"] *,
            .stSelectbox [data-baseweb="select"] div,
            .stSelectbox [data-baseweb="select"] span {
                background: #fff !important;
                color: #111827 !important;
                -webkit-text-fill-color: #111827 !important;
            }

            .stTextInput input::placeholder {
                color: #6b7280 !important;
                -webkit-text-fill-color: #6b7280 !important;
            }

            .stSelectbox svg {
                color: #111827 !important;
                fill: #111827 !important;
            }

            .carajas-logo-box {
                background: #ffffff;
                border: 1px solid var(--borda);
                border-radius: 22px;
                padding: 12px;
                box-shadow: 0 8px 18px rgba(31,25,19,.07);
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 96px;
            }

            .orange-note {
                color: var(--laranja);
                font-weight: 800;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


aplicar_layout()


def caminho_logo():
    """Procura a logo no repositório. Suba a imagem em um desses caminhos."""
    opcoes = [
        Path("img/logo_carajas.png"),
        Path("img/logo.png"),
        Path("assets/logo_carajas.png"),
        Path("assets/logo.png"),
        Path("logo_carajas.png"),
        Path("logo.png"),
    ]
    for caminho in opcoes:
        if caminho.exists():
            return str(caminho)
    return None


def moeda(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def normaliza_codigo(valor):
    if pd.isna(valor):
        return ""
    s = str(valor).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return re.sub(r"\D", "", s)


def normaliza_flag(valor):
    """Extrai a flag/letra de compra. No e-mail ela pode vir em coluna chamada STATUS."""
    if pd.isna(valor):
        return ""
    s = str(valor).strip().upper()
    letras = re.findall(r"[A-Z]", s)
    for letra in letras:
        if letra in FLAGS_COMPRA or letra in FLAGS_RISCO:
            return letra
    return letras[0] if letras else ""


def normaliza_status(valor):
    """Extrai o status numérico. No e-mail ele pode vir em coluna chamada FLAG."""
    if pd.isna(valor):
        return ""
    s = str(valor).strip()
    if s.endswith(".0"):
        s = s[:-2]
    numeros = re.findall(r"\d+", s)
    if not numeros:
        return ""
    for n in numeros:
        if n in STATUS_COMPRA or n in STATUS_NAO_COMPRA:
            return n
    return numeros[0]


def limpa_nome_coluna(nome):
    s = str(nome).strip().upper()
    s = s.replace("Á", "A").replace("À", "A").replace("Ã", "A").replace("Â", "A")
    s = s.replace("É", "E").replace("Ê", "E")
    s = s.replace("Í", "I")
    s = s.replace("Ó", "O").replace("Ô", "O").replace("Õ", "O")
    s = s.replace("Ú", "U")
    s = s.replace("Ç", "C")
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


def valor_numerico(serie):
    if isinstance(serie, (int, float)):
        return serie
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


def carrega_flags(uploaded_file):
    df = carrega_excel(uploaded_file)

    mascara_cabecalho = df.apply(
        lambda r: any("CABEÇALHO DE SISTEMA" in str(x).upper() for x in r), axis=1
    )
    df = df[~mascara_cabecalho].copy()

    col_codigo = primeira_coluna_existente(df, [
        "COD.TOTVS", "COD.TOTVS.1", "CODIGO", "CÓD. PRODUTO", "COD. PRODUTO",
        "COD PRODUTO", "COD_PROD", "Cod_Prod", "COD PROD", "COD.PRODUTO"
    ], contexto="do código do produto no arquivo de alteração")

    col_desc = primeira_coluna_existente(df, [
        "DESCRIÇÃO", "DESCRICAO", "DESC. PRODUTO", "DESC_PROD", "Desc_Prod", "PRODUTO"
    ], obrigatoria=False)

    def coluna_com_conteudo(candidatas, tipo):
        """Escolhe a primeira coluna que existe e tem conteúdo útil do tipo pedido."""
        existentes = []
        for nome in candidatas:
            col = primeira_coluna_existente(df, [nome], obrigatoria=False)
            if col and col not in existentes:
                existentes.append(col)

        for col in existentes:
            serie = df[col]
            if tipo == "flag":
                qtd = serie.map(normaliza_flag).astype(str).ne("").sum()
            else:
                qtd = serie.map(normaliza_status).astype(str).ne("").sum()
            if qtd > 0:
                return col
        return existentes[0] if existentes else None

    # IMPORTANTE:
    # No e-mail vem trocado:
    # - FLAG real/letra vem nas colunas de STATUS.
    # - STATUS real/número vem nas colunas de FLAG.
    # Porém alguns arquivos podem vir com colunas vazias. Por isso escolhemos a coluna
    # que realmente tem letra/número, em vez de pegar só pelo nome.
    col_flag_nova = coluna_com_conteudo([
        "STATUS PROD", "STATUS NOVO", "STATUS NOVA", "NOVO STATUS", "NOVA STATUS",
        "STATUS PRODUTO", "STATUS"
    ], "flag")
    col_flag_ant = coluna_com_conteudo([
        "FLAG ANTERIOR", "STATUS ANTERIOR", "STATUS ANTIGO", "STATUS PROD ANTERIOR",
        "ANTERIOR", "STATUS PRODUTO ANTERIOR", "STATUS ANT", "FLAG ANTIGA",
        "FLAG ABAST ANTERIOR", "ANTIGA FLAG", "FLAG PROD ANTERIOR", "FLAG ANT"
    ], "flag")

    col_status_novo = coluna_com_conteudo([
        "FLAG ABAST", "FLAG NOVA", "NOVA FLAG", "FLAG PROD LOJA", "FLAG PROD CD",
        "FLAG NOVO", "FLAG NOVA PROD", "FLAG"
    ], "status")
    col_status_ant = coluna_com_conteudo([
        "STATUS ANTERIOR", "FLAG ANTERIOR", "FLAG ANTIGA", "FLAG ABAST ANTERIOR",
        "ANTIGA FLAG", "FLAG PROD ANTERIOR", "FLAG ANT", "STATUS ANTIGO",
        "STATUS PROD ANTERIOR", "ANTERIOR", "STATUS PRODUTO ANTERIOR", "STATUS ANT"
    ], "status")

    if (col_flag_nova is None or col_flag_ant is None) and (col_status_novo is None or col_status_ant is None):
        raise ValueError(
            "Não consegui localizar colunas válidas para FLAG ou STATUS.\n\n"
            "Colunas disponíveis:\n" + "\n".join(map(str, df.columns))
        )

    base = pd.DataFrame()
    base["CODIGO"] = df[col_codigo].map(normaliza_codigo)
    base["DESCRICAO"] = df[col_desc] if col_desc else ""

    base["STATUS_ANTERIOR"] = df[col_status_ant].map(normaliza_status) if col_status_ant else ""
    base["STATUS_NOVO"] = df[col_status_novo].map(normaliza_status) if col_status_novo else ""
    base["FLAG_ANTERIOR"] = df[col_flag_ant].map(normaliza_flag) if col_flag_ant else ""
    base["FLAG_NOVA"] = df[col_flag_nova].map(normaliza_flag) if col_flag_nova else ""
    base = base[base["CODIGO"] != ""].copy()

    def classificar_status(row):
        ant = row["STATUS_ANTERIOR"]
        nova = row["STATUS_NOVO"]

        # Regra principal do STATUS numérico/loja
        if ant == "9" and nova in STATUS_COMPRA:
            return "RISCO RUPTURA"
        if ant in STATUS_COMPRA and nova == "9":
            return "RISCO IMPRODUTIVO"

        # Fallback: se o arquivo trouxe status novo válido, não some com o item.
        # Assim o total bate com o arquivo de alteração quando existem mudanças fora da regra clássica.
        if nova in STATUS_COMPRA:
            return "RISCO RUPTURA"
        if nova in STATUS_NAO_COMPRA:
            return "RISCO IMPRODUTIVO"

        return "FORA DA REGRA"

    def classificar_flag(row):
        ant = row["FLAG_ANTERIOR"]
        nova = row["FLAG_NOVA"]

        # Regra principal da FLAG letra/global
        if ant in FLAGS_RISCO and nova in FLAGS_COMPRA:
            return "RISCO RUPTURA"
        if ant in FLAGS_COMPRA and nova in FLAGS_RISCO:
            return "RISCO IMPRODUTIVO"

        # Fallback: se a flag nova virou B/D/F/X, entra como risco improdutivo.
        # Isso evita perder itens cujo anterior vem como O/R/E ou outra letra fora do grupo A/I/V/K/L/P.
        if nova in FLAGS_RISCO:
            return "RISCO IMPRODUTIVO"
        if nova in FLAGS_COMPRA:
            return "RISCO RUPTURA"

        return "FORA DA REGRA"

    def obs_status(row):
        ant = row["STATUS_ANTERIOR"]
        nova = row["STATUS_NOVO"]
        if nova in STATUS_CD_LOJA or ant in STATUS_CD_LOJA:
            return "STATUS 1/6: validar estoque CD/redistribuição para loja"
        if ant == "9" and nova in STATUS_COMPRA:
            return "9: atenção para ruptura potencial"
        if ant in STATUS_COMPRA and nova == "9":
            return "9: atenção para estoque/carteira possivel improdutivo"
        return ""

    def obs_flag(row):
        ant = row["FLAG_ANTERIOR"]
        nova = row["FLAG_NOVA"]
        if ant in FLAGS_RISCO and nova in FLAGS_COMPRA:
            return "flag risco -> compra: atenção para ruptura potencial"
        if ant in FLAGS_COMPRA and nova in FLAGS_RISCO:
            return "flag compra -> risco: atenção para estoque/carteira possivel improdutivo"
        if nova in FLAGS_RISCO:
            return "flag nova em risco: item incluído no impacto improdutivo"
        if nova in FLAGS_COMPRA:
            return "flag nova em compra: item incluído no impacto ruptura"
        return ""

    partes = []
    if col_status_novo and col_status_ant:
        status = base.copy()
        status["ANALISE"] = "STATUS NUMÉRICO / LOJA"
        status["MOVIMENTO"] = status["STATUS_ANTERIOR"] + " -> " + status["STATUS_NOVO"]
        status["SITUACAO"] = status.apply(classificar_status, axis=1)
        status["OBS_ANALISE"] = status.apply(obs_status, axis=1)
        partes.append(status)

    if col_flag_nova and col_flag_ant:
        flag = base.copy()
        flag["ANALISE"] = "FLAG LETRA / GERAL"
        flag["MOVIMENTO"] = flag["FLAG_ANTERIOR"] + " -> " + flag["FLAG_NOVA"]
        flag["SITUACAO"] = flag.apply(classificar_flag, axis=1)
        flag["OBS_ANALISE"] = flag.apply(obs_flag, axis=1)
        partes.append(flag)

    out = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
    out = out[out["SITUACAO"] != "FORA DA REGRA"].drop_duplicates()
    return out

def primeira_coluna_por_palavras(df, obrigatorias, opcionais=None, proibidas=None):
    opcionais = opcionais or []
    proibidas = proibidas or []
    for c in df.columns:
        nome = limpa_nome_coluna(c)
        if any(p in nome for p in proibidas):
            continue
        if all(p in nome for p in obrigatorias) and all(p in nome for p in opcionais):
            return c
    return None


def colunas_por_palavras(df, deve_ter_um, tambem_deve_ter=None, proibidas=None):
    tambem_deve_ter = tambem_deve_ter or []
    proibidas = proibidas or []
    cols = []
    for c in df.columns:
        nome = limpa_nome_coluna(c)
        if any(p in nome for p in proibidas):
            continue
        if any(p in nome for p in deve_ter_um) and all(p in nome for p in tambem_deve_ter):
            cols.append(c)
    return list(dict.fromkeys(cols))


def soma_colunas_numericas(df, cols):
    if not cols:
        return 0
    total = pd.Series(0, index=df.index, dtype=float)
    for c in cols:
        total = total + valor_numerico(df[c])
    return total


def carrega_carteira(uploaded_file):
    df = carrega_excel(uploaded_file)

    col_codigo = primeira_coluna_existente(df, [
        "Cod_Prod", "COD_PROD", "CODIGO", "CÓD. PRODUTO", "COD. PRODUTO", "COD PRODUTO", "COD PROD", "COD.PRODUTO"
    ], contexto="do código do produto na carteira")

    col_carteira_val = primeira_coluna_existente(df, [
        "Saldo R$ (CMV)", "SALDO R$ CMV", "SALDO CMV", "VALOR CARTEIRA", "CARTEIRA R$", "SALDO R$", "TOTAL CMV"
    ], contexto="do valor de carteira")

    col_carteira_qtd = primeira_coluna_existente(df, [
        "Saldo Qtd", "SALDO QTD", "QTD CARTEIRA", "CARTEIRA QTD", "QUANTIDADE CARTEIRA", "QTD SALDO", "SALDO"
    ], obrigatoria=False)

    col_pre_val = primeira_coluna_existente(df, [
        "Pré-nota R$ (CMV)", "PRE-NOTA R$ (CMV)", "PRÉ-NOTA CMV", "PRE NOTA CMV", "PRE NOTA R$", "PRÉ NOTA R$", "VALOR PRE NOTA", "VALOR PRÉ NOTA"
    ], obrigatoria=False)

    col_pre_qtd = primeira_coluna_existente(df, [
        "Pré-nota Qtd", "PRE-NOTA QTD", "PRÉ NOTA QTD", "PRE NOTA QTD", "QTD PRE NOTA", "QTD PRÉ NOTA"
    ], obrigatoria=False)

    col_nao_fat_val = primeira_coluna_existente(df, [
        "Não Faturado R$ (CMV)", "NAO FATURADO R$ (CMV)", "NÃO FATURADO R$", "NAO FATURADO R$", "NAO FATURADO CMV", "NÃO FATURADO CMV", "VALOR NAO FATURADO", "VALOR NÃO FATURADO"
    ], obrigatoria=False)

    col_nao_fat_qtd = primeira_coluna_existente(df, [
        "Não Faturado Qtd", "NAO FATURADO QTD", "NÃO FATURADO QTD", "QTD NAO FATURADO", "QTD NÃO FATURADO"
    ], obrigatoria=False)

    col_pre_num = primeira_coluna_existente(df, [
        "Pré-Nota", "PRE-NOTA", "PRE NOTA", "PRÉ NOTA", "NUM PRE NOTA", "Nº PRE NOTA"
    ], obrigatoria=False)

    df["CODIGO"] = df[col_codigo].map(normaliza_codigo)
    df["CARTEIRA_VALOR"] = valor_numerico(df[col_carteira_val])
    df["CARTEIRA_QTD"] = valor_numerico(df[col_carteira_qtd]) if col_carteira_qtd else 0
    df["PRE_NOTA_VALOR"] = valor_numerico(df[col_pre_val]) if col_pre_val else 0
    df["PRE_NOTA_QTD"] = valor_numerico(df[col_pre_qtd]) if col_pre_qtd else 0
    df["NAO_FATURADO_VALOR"] = valor_numerico(df[col_nao_fat_val]) if col_nao_fat_val else df["CARTEIRA_VALOR"] - df["PRE_NOTA_VALOR"]
    df["NAO_FATURADO_QTD"] = valor_numerico(df[col_nao_fat_qtd]) if col_nao_fat_qtd else df["CARTEIRA_QTD"] - df["PRE_NOTA_QTD"]

    if col_pre_num:
        pre = df[col_pre_num].astype(str).str.strip()
        df["TEM_PRE_NOTA"] = df[col_pre_num].notna() & (~pre.isin(["", "0", "0.0", "nan", "NaN", "None"]))
    else:
        df["TEM_PRE_NOTA"] = (df["PRE_NOTA_VALOR"] > 0) | (df["PRE_NOTA_QTD"] > 0)

    return df.groupby("CODIGO", as_index=False).agg(
        CARTEIRA_QTD=("CARTEIRA_QTD", "sum"),
        CARTEIRA_VALOR=("CARTEIRA_VALOR", "sum"),
        PRE_NOTA_QTD=("PRE_NOTA_QTD", "sum"),
        PRE_NOTA_VALOR=("PRE_NOTA_VALOR", "sum"),
        NAO_FATURADO_QTD=("NAO_FATURADO_QTD", "sum"),
        NAO_FATURADO_VALOR=("NAO_FATURADO_VALOR", "sum"),
        TEM_PRE_NOTA=("TEM_PRE_NOTA", "max"),
    )


def carrega_cobertura(uploaded_file):
    df = carrega_excel(uploaded_file)

    col_codigo = primeira_coluna_existente(df, [
        "CÓD. PRODUTO", "COD. PRODUTO", "CODIGO", "COD_PROD", "Cod_Prod", "COD PRODUTO", "COD PROD", "COD.PRODUTO"
    ], contexto="do código do produto na cobertura")

    col_cmv = primeira_coluna_existente(df, [
        "VLR CMV POND.", "CMV", "CUSTO", "CUSTO MEDIO", "CUSTO MÉDIO", "CMV BASE"
    ], obrigatoria=False)

    col_disp = primeira_coluna_existente(df, [
        "QTD DISP. VENDA", "DISP. VEND.", "DISP VEND", "DISP VENDA", "DISPONIVEL VENDA", "DISPONÍVEL VENDA"
    ], obrigatoria=False)
    if col_disp is None:
        col_disp = primeira_coluna_por_palavras(df, ["DISP"], ["VEND"], proibidas=["FAT"])

    if col_disp is None:
        raise ValueError(
            "Não encontrei a coluna de DISP. VENDA / QTD DISP. VENDA na cobertura.\n\n"
            "Colunas disponíveis:\n" + "\n".join(map(str, df.columns))
        )

    # Soma tudo que for trânsito + reserva. 
    cols_reserv_trans = colunas_por_palavras(
        df,
        deve_ter_um=["TRANS", "TRANSITO", "RESERV", "RESERVA"],
        proibidas=["FAT", "FATUR", "LOJA"]
    )
    cols_reserv_trans = [c for c in cols_reserv_trans if c != col_disp]

    df["CODIGO"] = df[col_codigo].map(normaliza_codigo)
    df["DISP_VENDA_QTD"] = valor_numerico(df[col_disp])
    df["RESERV_TRANS_QTD"] = soma_colunas_numericas(df, cols_reserv_trans)

    if col_cmv:
        df["CMV_UNITARIO"] = valor_numerico(df[col_cmv])
    else:
        df["CMV_UNITARIO"] = 0

    df["DISP_VENDA_VALOR"] = df["DISP_VENDA_QTD"] * df["CMV_UNITARIO"]
    df["RESERV_TRANS_VALOR"] = df["RESERV_TRANS_QTD"] * df["CMV_UNITARIO"]
    df["TOTAL_ESTOQUE_QTD"] = df["DISP_VENDA_QTD"] + df["RESERV_TRANS_QTD"]
    df["TOTAL_ESTOQUE_VALOR"] = df["DISP_VENDA_VALOR"] + df["RESERV_TRANS_VALOR"]

    return df.groupby("CODIGO", as_index=False).agg(
        DISP_VENDA_QTD=("DISP_VENDA_QTD", "sum"),
        DISP_VENDA_VALOR=("DISP_VENDA_VALOR", "sum"),
        RESERV_TRANS_QTD=("RESERV_TRANS_QTD", "sum"),
        RESERV_TRANS_VALOR=("RESERV_TRANS_VALOR", "sum"),
        TOTAL_ESTOQUE_QTD=("TOTAL_ESTOQUE_QTD", "sum"),
        TOTAL_ESTOQUE_VALOR=("TOTAL_ESTOQUE_VALOR", "sum"),
    )


def montar_analise(arq_flags, arq_carteira, arq_cobertura):
    flags = carrega_flags(arq_flags)
    carteira = carrega_carteira(arq_carteira)
    cobertura = carrega_cobertura(arq_cobertura)

    base = flags.merge(carteira, on="CODIGO", how="left").merge(cobertura, on="CODIGO", how="left")

    numericas = [
        "CARTEIRA_QTD", "CARTEIRA_VALOR", "PRE_NOTA_QTD", "PRE_NOTA_VALOR",
        "NAO_FATURADO_QTD", "NAO_FATURADO_VALOR",
        "DISP_VENDA_QTD", "DISP_VENDA_VALOR",
        "RESERV_TRANS_QTD", "RESERV_TRANS_VALOR",
        "TOTAL_ESTOQUE_QTD", "TOTAL_ESTOQUE_VALOR",
    ]
    for c in numericas:
        base[c] = pd.to_numeric(base[c], errors="coerce").fillna(0)

    base["TEM_PRE_NOTA"] = base["TEM_PRE_NOTA"].fillna(False)
    base["PRE_NOTA"] = base["TEM_PRE_NOTA"].map(lambda x: "SIM" if bool(x) else "NÃO")

    def situacao_carteira(row):
        partes = []
        partes.append("TEM CARTEIRA" if row["CARTEIRA_VALOR"] > 0 or row["CARTEIRA_QTD"] > 0 else "SEM CARTEIRA")
        partes.append("TEM ESTOQUE" if row["TOTAL_ESTOQUE_QTD"] > 0 else "SEM ESTOQUE")
        partes.append("COM PRÉ-NOTA" if bool(row["TEM_PRE_NOTA"]) else "SEM PRÉ-NOTA")
        return " | ".join(partes)

    base["SITUACAO_CARTEIRA_ESTOQUE"] = base.apply(situacao_carteira, axis=1)

    resumo = base.groupby(["ANALISE", "SITUACAO"], as_index=False).agg(
        ITENS_QTD=("CODIGO", "nunique"),
        CARTEIRA_QTD=("CARTEIRA_QTD", "sum"),
        CARTEIRA_VALOR=("CARTEIRA_VALOR", "sum"),
        PRE_NOTA_QTD=("PRE_NOTA_QTD", "sum"),
        PRE_NOTA_VALOR=("PRE_NOTA_VALOR", "sum"),
        NAO_FATURADO_QTD=("NAO_FATURADO_QTD", "sum"),
        NAO_FATURADO_VALOR=("NAO_FATURADO_VALOR", "sum"),
        DISP_VENDA_QTD=("DISP_VENDA_QTD", "sum"),
        DISP_VENDA_VALOR=("DISP_VENDA_VALOR", "sum"),
        RESERV_TRANS_QTD=("RESERV_TRANS_QTD", "sum"),
        RESERV_TRANS_VALOR=("RESERV_TRANS_VALOR", "sum"),
        TOTAL_ESTOQUE_QTD=("TOTAL_ESTOQUE_QTD", "sum"),
        TOTAL_ESTOQUE_VALOR=("TOTAL_ESTOQUE_VALOR", "sum"),
    )

    por_movimento = base.groupby(["ANALISE", "SITUACAO", "MOVIMENTO"], as_index=False).agg(
        ITENS_QTD=("CODIGO", "nunique"),
        CARTEIRA_QTD=("CARTEIRA_QTD", "sum"),
        CARTEIRA_VALOR=("CARTEIRA_VALOR", "sum"),
        PRE_NOTA_QTD=("PRE_NOTA_QTD", "sum"),
        PRE_NOTA_VALOR=("PRE_NOTA_VALOR", "sum"),
        NAO_FATURADO_QTD=("NAO_FATURADO_QTD", "sum"),
        NAO_FATURADO_VALOR=("NAO_FATURADO_VALOR", "sum"),
        DISP_VENDA_QTD=("DISP_VENDA_QTD", "sum"),
        DISP_VENDA_VALOR=("DISP_VENDA_VALOR", "sum"),
        RESERV_TRANS_QTD=("RESERV_TRANS_QTD", "sum"),
        RESERV_TRANS_VALOR=("RESERV_TRANS_VALOR", "sum"),
        TOTAL_ESTOQUE_QTD=("TOTAL_ESTOQUE_QTD", "sum"),
        TOTAL_ESTOQUE_VALOR=("TOTAL_ESTOQUE_VALOR", "sum"),
    )

    return base, resumo, por_movimento


def nomes_relatorio(df):
    mapa = {
        "ANALISE": "ANÁLISE",
        "SITUACAO": "SITUAÇÃO",
        "STATUS_ANTERIOR": "STATUS ANTERIOR",
        "STATUS_NOVO": "STATUS NOVO",
        "OBS_ANALISE": "OBS ANÁLISE",
        "ITENS_QTD": "ITENS QTD",
        "CARTEIRA_QTD": "CARTEIRA QTD",
        "CARTEIRA_VALOR": "CARTEIRA R$",
        "PRE_NOTA_QTD": "PRE NOTA QTD",
        "PRE_NOTA_VALOR": "PRE NOTA VALOR",
        "NAO_FATURADO_QTD": "NÃO FAT. QTD",
        "NAO_FATURADO_VALOR": "NÃO FAT. VALOR",
        "DISP_VENDA_QTD": "DISP VENDA QTD",
        "DISP_VENDA_VALOR": "DISP VENDA VALOR",
        "RESERV_TRANS_QTD": "EST. RESERV/TRANS QTD",
        "RESERV_TRANS_VALOR": "EST. RESERV/TRANS VALOR",
        "TOTAL_ESTOQUE_QTD": "TOTAL IMPACTO EST. QTD",
        "TOTAL_ESTOQUE_VALOR": "TOTAL IMPACTO EST. VALOR",
    }
    return df.rename(columns={k: v for k, v in mapa.items() if k in df.columns})


def formatar_tabela(df):
    df = nomes_relatorio(df.copy())
    money_cols = [c for c in df.columns if "R$" in c or "VALOR" in c]
    qtd_cols = [c for c in df.columns if "QTD" in c or c == "ITENS QTD"]
    fmt = {c: moeda for c in money_cols}
    for c in qtd_cols:
        fmt[c] = "{:.0f}"
    return df.style.format(fmt)


def gerar_excel(base, resumo, por_movimento):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        nomes_relatorio(resumo).to_excel(writer, sheet_name="Resumo", index=False)
        nomes_relatorio(por_movimento).to_excel(writer, sheet_name="Por Movimento", index=False)
        nomes_relatorio(base).to_excel(writer, sheet_name="Detalhe", index=False)

        for situacao, dados in base.groupby("SITUACAO"):
            nome = re.sub(r"[^A-Za-z0-9 ]", "", situacao)[:31]
            nomes_relatorio(dados).to_excel(writer, sheet_name=nome, index=False)

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
                ws.column_dimensions[col_letter].width = min(max(max_len + 2, 12), 42)

    output.seek(0)
    return output.getvalue()



logo = caminho_logo()

st.markdown(
    """
    <div class="app-hero">
        <p class="app-title">Análise de alteração de flags</p>
        <p class="app-subtitle" style="margin-left:0;">Cruza status, flags, carteira, pré-nota e estoque para enxergar possíveis rupturas ou improdutivo.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    if logo:
        st.image(logo, width=120)
    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-title">Análise de Flags</div>
            <div class="sidebar-dash"></div>
            <div class="sidebar-subtitle">Gestão de alteração de status, carteira e estoque.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.header("Importar arquivos")
    arq_flags = st.file_uploader("1) Alteração de flags", type=["xlsx", "xls"])
    arq_carteira = st.file_uploader("2) Carteira com agendamento", type=["xlsx", "xls"])
    arq_cobertura = st.file_uploader("3) Cobertura / Cobertura Pura", type=["xlsx", "xls"])


if not (arq_flags and arq_carteira and arq_cobertura):
    st.info("Importe os 3 arquivos na lateral para gerar a análise.")
    st.stop()

try:
    with st.spinner("Processando arquivos..."):
        base, resumo, por_movimento = montar_analise(arq_flags, arq_carteira, arq_cobertura)
        excel_bytes = gerar_excel(base, resumo, por_movimento)


    total_itens = int(base["CODIGO"].nunique())
    total_carteira = base["CARTEIRA_VALOR"].sum()
    total_estoque_qtd = base["TOTAL_ESTOQUE_QTD"].sum()
    total_estoque_valor = base["TOTAL_ESTOQUE_VALOR"].sum()
    total_pre_nota = base["PRE_NOTA_VALOR"].sum()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Itens impactados", f"{total_itens:,.0f}".replace(",", "."))
    c2.metric("Carteira", moeda(total_carteira))
    c3.metric("Pré-nota", moeda(total_pre_nota))
    c4.metric("Estoque qtd", f"{total_estoque_qtd:,.0f}".replace(",", "."))
    c5.metric("Estoque valor", moeda(total_estoque_valor))

    st.download_button(
        "⬇️ Baixar resultado em Excel",
        data=excel_bytes,
        file_name="resultado_analise_flags.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    aba1, aba2, aba3, aba4 = st.tabs(["Resumo", "Por movimento", "Detalhe", "Filtros"])

    with aba1:
        st.subheader("Resumo por situação")
        st.dataframe(formatar_tabela(resumo), use_container_width=True, hide_index=True)


    with aba2:
        st.subheader("Resumo por movimento")
        st.dataframe(formatar_tabela(por_movimento), use_container_width=True, hide_index=True)

    with aba3:
        st.subheader("Detalhe dos produtos")
        colunas = [
            "CODIGO", "DESCRICAO", "ANALISE", "SITUACAO", "MOVIMENTO", "STATUS_ANTERIOR", "STATUS_NOVO", "FLAG_ANTERIOR", "FLAG_NOVA", "OBS_ANALISE",
            "CARTEIRA_QTD", "CARTEIRA_VALOR", "PRE_NOTA_QTD", "PRE_NOTA_VALOR",
            "NAO_FATURADO_QTD", "NAO_FATURADO_VALOR", "PRE_NOTA",
            "DISP_VENDA_QTD", "DISP_VENDA_VALOR", "RESERV_TRANS_QTD", "RESERV_TRANS_VALOR",
            "TOTAL_ESTOQUE_QTD", "TOTAL_ESTOQUE_VALOR", "SITUACAO_CARTEIRA_ESTOQUE"
        ]
        colunas = [c for c in colunas if c in base.columns]
        st.dataframe(formatar_tabela(base[colunas]), use_container_width=True, hide_index=True)

    with aba4:
        st.subheader("Consultar produto ou situação")
        situacoes = ["Todas"] + sorted(base["SITUACAO"].dropna().unique().tolist())
        sit = st.selectbox("Situação", situacoes)
        busca = st.text_input("Buscar por código ou descrição")

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

except Exception as e:
    st.error("Erro na análise")
    st.exception(e)

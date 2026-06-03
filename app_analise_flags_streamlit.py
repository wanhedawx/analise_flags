# -*- coding: utf-8 -*-
"""
APP STREAMLIT - ANÁLISE DE ALTERAÇÃO DE FLAGS/STATUS x CARTEIRA x ESTOQUE

Como usar no Streamlit Cloud:
1) Salve este arquivo como: app_analise_flags_streamlit.py
2) No requirements.txt coloque:
   streamlit
   pandas
   openpyxl
3) Rode localmente, se quiser testar:
   streamlit run app_analise_flags_streamlit.py

Conceito de negócio usado:
- Para a empresa:
  - FLAG = letra: A/I/V/K/L/P/B/D/F/X
  - STATUS = número: 1/3/4/5/6/9
- No e-mail/relatório, pode vir invertido:
  - coluna chamada FLAG pode conter o STATUS numérico por loja.
  - coluna chamada STATUS pode conter a FLAG letra do produto.

Classificação:
1) RISCO IMPRODUTIVO
   - Flag letra: A/I/V/K/L/P -> B/D/F/X
   - Status número: 1/3/4/5/6 -> 9

2) RISCO RUPTURA
   - Flag letra: B/D/F/X -> A/I/V/K/L/P
   - Status número: 9 -> 1/3/4/5/6

Estoque impactado:
Soma estoque disponível + pedidos + faturado/trânsito + reservas.
Não soma EMB. COMP., porque é embalagem de compra/embarque de compra.
"""

from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
import re
import pandas as pd
import streamlit as st

FLAGS_ATIVAS = {"A", "I", "V", "K", "L", "P"}
FLAGS_RISCO = {"B", "D", "F", "X"}
STATUS_COMPRA = {"1", "3", "4", "5", "6"}
STATUS_NAO_COMPRA = {"9"}

st.set_page_config(
    page_title="Análise de Flags/Status x Carteira x Estoque",
    page_icon="📊",
    layout="wide",
)


def moeda(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def nome_seguro(nome):
    nome = re.sub(r"\.[A-Za-z0-9]+$", "", str(nome))
    nome = re.sub(r"[^A-Za-z0-9_ -]", "", nome).strip()
    nome = re.sub(r"\s+", "_", nome)
    return nome[:80] or "resultado"


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
    s = s.replace("º", "")
    return s


def normaliza_codigo(valor):
    if pd.isna(valor):
        return ""
    s = str(valor).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return re.sub(r"\D", "", s)


def normaliza_flag_letra(valor):
    if pd.isna(valor):
        return ""
    s = str(valor).strip().upper()
    # Aceita "A", "A - ATIVO", "D DESCONTINUADO".
    letras = re.findall(r"[A-Z]", s)
    return letras[0] if letras else ""


def normaliza_status_numero(valor):
    if pd.isna(valor):
        return ""
    s = str(valor).strip()
    if s.endswith(".0"):
        s = s[:-2]
    nums = re.findall(r"\d+", s)
    if not nums:
        return ""
    return nums[0]


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


def colunas_por_palavras(df, inclui=None, exclui=None):
    inclui = inclui or []
    exclui = exclui or []
    achadas = []
    for c in df.columns:
        nome = limpa_nome_coluna(c)
        if all(p in nome for p in inclui) and not any(p in nome for p in exclui):
            achadas.append(c)
    return achadas


@st.cache_data(show_spinner=False)
def carrega_excel(uploaded_file):
    return pd.read_excel(uploaded_file)


def taxa_valores_validos(serie, tipo):
    if tipo == "status":
        vals = serie.map(normaliza_status_numero)
        return vals.isin(STATUS_COMPRA | STATUS_NAO_COMPRA).mean()
    vals = serie.map(normaliza_flag_letra)
    return vals.isin(FLAGS_ATIVAS | FLAGS_RISCO).mean()


def localizar_par_colunas(df, opcoes_ant, opcoes_nova, tipo, contexto):
    """Localiza par anterior/nova. Se nome não bater, tenta inferir por conteúdo."""
    col_ant = primeira_coluna_existente(df, opcoes_ant, obrigatoria=False)
    col_nova = primeira_coluna_existente(df, opcoes_nova, obrigatoria=False)
    if col_ant and col_nova:
        return col_ant, col_nova

    # Inferência por conteúdo e nome. Útil porque o e-mail pode chamar status numérico de FLAG.
    candidatos = []
    for c in df.columns:
        nome = limpa_nome_coluna(c)
        score = taxa_valores_validos(df[c], tipo)
        if score <= 0:
            continue
        candidatos.append((c, nome, score))

    anteriores = []
    novas = []
    for c, nome, score in candidatos:
        if any(p in nome for p in ["ANT", "ANTERIOR", "DE ", "OLD"]):
            anteriores.append((c, score))
        if any(p in nome for p in ["NOV", "NOVA", "NOVO", "PARA", "ATUAL", "PROD"]):
            novas.append((c, score))

    if not col_ant and anteriores:
        col_ant = sorted(anteriores, key=lambda x: x[1], reverse=True)[0][0]
    if not col_nova and novas:
        col_nova = sorted(novas, key=lambda x: x[1], reverse=True)[0][0]

    return col_ant, col_nova


def carrega_alteracoes(uploaded_file):
    df = carrega_excel(uploaded_file)

    # Remove eventual linha técnica de cabeçalho do sistema.
    mascara_cabecalho = df.apply(
        lambda r: any("CABEÇALHO DE SISTEMA" in str(x).upper() for x in r), axis=1
    )
    df = df[~mascara_cabecalho].copy()

    col_codigo = primeira_coluna_existente(df, [
        "COD.TOTVS", "COD.TOTVS.1", "CODIGO", "CÓD. PRODUTO", "COD. PRODUTO",
        "COD PRODUTO", "COD_PROD", "Cod_Prod", "COD PROD", "COD.PRODUTO", "CD ABASTECE"
    ], contexto="do código do produto no arquivo de alteração")

    col_desc = primeira_coluna_existente(df, [
        "DESCRIÇÃO", "DESCRICAO", "DESC. PRODUTO", "DESC_PROD", "Desc_Prod", "PRODUTO", "DESCRICAO PRODUTO"
    ], obrigatoria=False)

    col_loja = primeira_coluna_existente(df, [
        "LOJA", "FILIAL", "COD LOJA", "COD. LOJA", "CD LOJA", "EMPRESA", "UNIDADE"
    ], obrigatoria=False)

    # Para nós: FLAG = letra. No e-mail pode aparecer em coluna STATUS.
    col_flag_ant, col_flag_nova = localizar_par_colunas(
        df,
        opcoes_ant=[
            "STATUS ANTERIOR", "STATUS PROD ANTERIOR", "STATUS ANTIGO", "STATUS ANT", "ANTERIOR STATUS",
            "FLAG LETRA ANTERIOR", "FLAG PROD ANTERIOR", "FLAG ANTERIOR LETRA"
        ],
        opcoes_nova=[
            "STATUS PROD", "STATUS NOVO", "STATUS ATUAL", "NOVO STATUS", "STATUS",
            "FLAG LETRA", "FLAG PROD", "FLAG NOVA LETRA"
        ],
        tipo="flag",
        contexto="da flag letra"
    )

    # Para nós: STATUS = número. No e-mail pode aparecer em coluna FLAG.
    col_status_ant, col_status_novo = localizar_par_colunas(
        df,
        opcoes_ant=[
            "FLAG ANTERIOR", "FLAG ABAST ANTERIOR", "FLAG ANTIGA", "FLAG ANT", "ANTERIOR FLAG",
            "STATUS NUM ANTERIOR", "STATUS ABAST ANTERIOR", "MODO ABAST ANTERIOR"
        ],
        opcoes_nova=[
            "FLAG ABAST", "FLAG NOVA", "FLAG ATUAL", "NOVA FLAG", "FLAG", "FLAG PROD LOJA", "FLAG PROD CD",
            "STATUS NUM", "STATUS ABAST", "MODO ABAST", "MODO ABASTECIMENTO"
        ],
        tipo="status",
        contexto="do status numérico"
    )

    out = pd.DataFrame()
    out["CODIGO"] = df[col_codigo].map(normaliza_codigo)
    out["DESCRICAO"] = df[col_desc] if col_desc else ""
    out["LOJA"] = df[col_loja].astype(str).str.strip() if col_loja else ""

    if col_flag_ant and col_flag_nova:
        out["FLAG_ANTERIOR"] = df[col_flag_ant].map(normaliza_flag_letra)
        out["FLAG_NOVA"] = df[col_flag_nova].map(normaliza_flag_letra)
    else:
        out["FLAG_ANTERIOR"] = ""
        out["FLAG_NOVA"] = ""

    if col_status_ant and col_status_novo:
        out["STATUS_ANTERIOR"] = df[col_status_ant].map(normaliza_status_numero)
        out["STATUS_NOVO"] = df[col_status_novo].map(normaliza_status_numero)
    else:
        out["STATUS_ANTERIOR"] = ""
        out["STATUS_NOVO"] = ""

    out = out[out["CODIGO"] != ""].copy()

    def classificar(row):
        motivos = []
        situacoes = set()

        fa, fn = row["FLAG_ANTERIOR"], row["FLAG_NOVA"]
        sa, sn = row["STATUS_ANTERIOR"], row["STATUS_NOVO"]

        if fa in FLAGS_ATIVAS and fn in FLAGS_RISCO:
            situacoes.add("RISCO IMPRODUTIVO")
            motivos.append("FLAG ATIVA -> FLAG B/D/F/X")
        elif fa in FLAGS_RISCO and fn in FLAGS_ATIVAS:
            situacoes.add("RISCO RUPTURA")
            motivos.append("FLAG B/D/F/X -> FLAG ATIVA")

        if sa in STATUS_COMPRA and sn in STATUS_NAO_COMPRA:
            situacoes.add("RISCO IMPRODUTIVO")
            motivos.append("STATUS COMPRA -> 9")
        elif sa in STATUS_NAO_COMPRA and sn in STATUS_COMPRA:
            situacoes.add("RISCO RUPTURA")
            motivos.append("STATUS 9 -> COMPRA")

        if len(situacoes) == 1:
            return list(situacoes)[0], " + ".join(motivos)
        if len(situacoes) > 1:
            return "REVISAR - MOVIMENTOS OPOSTOS", " + ".join(motivos)
        return "FORA DA REGRA", ""

    classif = out.apply(classificar, axis=1, result_type="expand")
    out["SITUACAO"] = classif[0]
    out["MOTIVO"] = classif[1]
    out["MOVIMENTO_FLAG"] = out["FLAG_ANTERIOR"] + " -> " + out["FLAG_NOVA"]
    out["MOVIMENTO_STATUS"] = out["STATUS_ANTERIOR"] + " -> " + out["STATUS_NOVO"]

    out = out[out["SITUACAO"] != "FORA DA REGRA"].drop_duplicates()
    return out


def carrega_carteira(uploaded_file):
    df = carrega_excel(uploaded_file)

    col_codigo = primeira_coluna_existente(df, [
        "Cod_Prod", "COD_PROD", "CODIGO", "CÓD. PRODUTO", "COD. PRODUTO", "COD PRODUTO", "COD PROD", "COD.PRODUTO"
    ], contexto="do código do produto na carteira")

    col_saldo = primeira_coluna_existente(df, [
        "Saldo R$ (CMV)", "SALDO CMV", "SALDO", "CARTEIRA", "VALOR CARTEIRA", "SALDO R$", "TOTAL CMV"
    ], contexto="do valor de carteira")

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
    df["CARTEIRA_CMV"] = valor_numerico(df[col_saldo])
    df["PRE_NOTA_CMV"] = valor_numerico(df[col_pre_val]) if col_pre_val else 0
    df["NAO_FATURADO_CMV"] = valor_numerico(df[col_nao_fat]) if col_nao_fat else df["CARTEIRA_CMV"] - df["PRE_NOTA_CMV"]

    if col_pre_num:
        pre = df[col_pre_num].astype(str).str.strip()
        df["TEM_PRE_NOTA"] = df[col_pre_num].notna() & (~pre.isin(["", "0", "0.0", "nan", "NaN", "None"]))
    else:
        df["TEM_PRE_NOTA"] = df["PRE_NOTA_CMV"] > 0

    return df.groupby("CODIGO", as_index=False).agg(
        CARTEIRA_CMV=("CARTEIRA_CMV", "sum"),
        PRE_NOTA_CMV=("PRE_NOTA_CMV", "sum"),
        NAO_FATURADO_CMV=("NAO_FATURADO_CMV", "sum"),
        TEM_PRE_NOTA=("TEM_PRE_NOTA", "max"),
    )


def soma_colunas(df, opcoes_exatas=None, regras=None):
    opcoes_exatas = opcoes_exatas or []
    regras = regras or []
    cols = []
    mapa = {limpa_nome_coluna(c): c for c in df.columns}

    for op in opcoes_exatas:
        chave = limpa_nome_coluna(op)
        if chave in mapa and mapa[chave] not in cols:
            cols.append(mapa[chave])

    for c in df.columns:
        nome = limpa_nome_coluna(c)
        if c in cols:
            continue
        for inclui, exclui in regras:
            if all(p in nome for p in inclui) and not any(p in nome for p in exclui):
                cols.append(c)
                break

    if not cols:
        return pd.Series(0, index=df.index), []

    total = pd.Series(0, index=df.index, dtype="float64")
    for c in cols:
        total = total + valor_numerico(df[c])
    return total, cols


def carrega_cobertura(uploaded_file):
    df = carrega_excel(uploaded_file)

    col_codigo = primeira_coluna_existente(df, [
        "CÓD. PRODUTO", "COD. PRODUTO", "CODIGO", "COD_PROD", "Cod_Prod", "COD PRODUTO", "COD PROD", "COD.PRODUTO"
    ], contexto="do código do produto na cobertura")

    col_cmv = primeira_coluna_existente(df, [
        "VLR CMV POND.", "CMV", "CUSTO", "CUSTO MEDIO", "CUSTO MÉDIO", "CMV BASE", "CMV UNITARIO", "CMV UNITÁRIO"
    ], obrigatoria=False)

    df["CODIGO"] = df[col_codigo].map(normaliza_codigo)

    # 1) Estoque disponível físico nos CDs/atacados.
    df["ESTOQUE_DISP_QTD"], cols_disp = soma_colunas(
        df,
        opcoes_exatas=[
            "EST. CDAL DISP.", "EST CDAL DISP", "EST. ATCE DISP.", "EST ATCE DISP", "EST. ATPB DISP.", "EST ATPB DISP",
            "QTD DISP. VENDA", "DISP. VEND.", "DISP VEND", "DISP VENDA"
        ],
        regras=[
            (["EST", "DISP"], ["EMB", "COMP"]),
            (["DISP", "VEND"], ["EMB", "COMP"]),
        ]
    )

    # 2) Pedidos em aberto/futuros.
    df["PEDIDO_QTD"], cols_pedido = soma_colunas(
        df,
        opcoes_exatas=["PEDIDO CDAL", "PEDIDO ATCE", "PEDIDO ATPB"],
        regras=[(["PEDIDO"], ["EMB", "COMP"])]
    )

    # 3) Faturado / trânsito.
    df["FATURADO_TRANSITO_QTD"], cols_fat = soma_colunas(
        df,
        opcoes_exatas=["FAT. CDAL", "FAT. ATCE", "FAT. ATPB", "FAT CDAL", "FAT ATCE", "FAT ATPB"],
        regras=[(["FAT"], ["EMB", "COMP"])]
    )

    # 4) Reservas CD/atacado x loja.
    df["RESERVA_QTD"], cols_reserva = soma_colunas(
        df,
        opcoes_exatas=[
            "RESERVA CDALxLOJA", "RESERVA ATCExLOJA", "RESERVA ATPBxLOJA",
            "RESERVA CDAL X LOJA", "RESERVA ATCE X LOJA", "RESERVA ATPB X LOJA"
        ],
        regras=[(["RESERVA"], ["EMB", "COMP"])]
    )

    # EMB. COMP. fica fora por regra de negócio.
    df["ESTOQUE_IMPACTADO_QTD"] = (
        df["ESTOQUE_DISP_QTD"]
        + df["PEDIDO_QTD"]
        + df["FATURADO_TRANSITO_QTD"]
        + df["RESERVA_QTD"]
    )

    if col_cmv:
        df["CMV_UNITARIO"] = valor_numerico(df[col_cmv])
        df["ESTOQUE_IMPACTADO_VALOR"] = df["ESTOQUE_IMPACTADO_QTD"] * df["CMV_UNITARIO"]
        df["ESTOQUE_DISP_VALOR"] = df["ESTOQUE_DISP_QTD"] * df["CMV_UNITARIO"]
        df["PEDIDO_VALOR"] = df["PEDIDO_QTD"] * df["CMV_UNITARIO"]
        df["FATURADO_TRANSITO_VALOR"] = df["FATURADO_TRANSITO_QTD"] * df["CMV_UNITARIO"]
        df["RESERVA_VALOR"] = df["RESERVA_QTD"] * df["CMV_UNITARIO"]
    else:
        df["ESTOQUE_IMPACTADO_VALOR"] = 0
        df["ESTOQUE_DISP_VALOR"] = 0
        df["PEDIDO_VALOR"] = 0
        df["FATURADO_TRANSITO_VALOR"] = 0
        df["RESERVA_VALOR"] = 0

    cobertura = df.groupby("CODIGO", as_index=False).agg(
        ESTOQUE_DISP_QTD=("ESTOQUE_DISP_QTD", "sum"),
        PEDIDO_QTD=("PEDIDO_QTD", "sum"),
        FATURADO_TRANSITO_QTD=("FATURADO_TRANSITO_QTD", "sum"),
        RESERVA_QTD=("RESERVA_QTD", "sum"),
        ESTOQUE_IMPACTADO_QTD=("ESTOQUE_IMPACTADO_QTD", "sum"),
        ESTOQUE_DISP_VALOR=("ESTOQUE_DISP_VALOR", "sum"),
        PEDIDO_VALOR=("PEDIDO_VALOR", "sum"),
        FATURADO_TRANSITO_VALOR=("FATURADO_TRANSITO_VALOR", "sum"),
        RESERVA_VALOR=("RESERVA_VALOR", "sum"),
        ESTOQUE_IMPACTADO_VALOR=("ESTOQUE_IMPACTADO_VALOR", "sum"),
    )
    cobertura.attrs["colunas_usadas"] = {
        "estoque_disponivel": [str(c) for c in cols_disp],
        "pedido": [str(c) for c in cols_pedido],
        "faturado_transito": [str(c) for c in cols_fat],
        "reserva": [str(c) for c in cols_reserva],
        "excluido": ["EMB. COMP."]
    }
    return cobertura


def recomendacao(row):
    situacao = row.get("SITUACAO", "")
    status_ant = row.get("STATUS_ANTERIOR", "")
    status_novo = row.get("STATUS_NOVO", "")
    carteira = row.get("CARTEIRA_CMV", 0)
    estoque = row.get("ESTOQUE_IMPACTADO_QTD", 0)
    pedido = row.get("PEDIDO_QTD", 0)
    reserva = row.get("RESERVA_QTD", 0)

    if situacao == "RISCO IMPRODUTIVO":
        partes = []
        if carteira > 0:
            partes.append("tratar carteira")
        if estoque > 0:
            partes.append("definir ação para estoque/pedido/reserva")
        if status_novo == "9":
            partes.append("produto/loja deixará de ser comprado")
        return " | ".join(partes) if partes else "sem carteira/estoque impactado"

    if situacao == "RISCO RUPTURA":
        partes = []
        if status_ant == "9" and status_novo in STATUS_COMPRA:
            partes.append("começará a comprar para a loja")
        if estoque <= 0 and pedido <= 0 and carteira <= 0:
            partes.append("alto risco: sem estoque, pedido e carteira")
        elif estoque <= 0:
            partes.append("atenção: sem estoque disponível")
        if carteira > 0:
            partes.append("há carteira consolidada, validar se atende a loja")
        if reserva > 0:
            partes.append("há reserva comprometida")
        return " | ".join(partes) if partes else "monitorar abastecimento"

    return "validar manualmente"


def montar_analise(arq_alteracao, carteira, cobertura):
    alteracoes = carrega_alteracoes(arq_alteracao)
    base = alteracoes.merge(carteira, on="CODIGO", how="left").merge(cobertura, on="CODIGO", how="left")

    num_cols = [
        "CARTEIRA_CMV", "PRE_NOTA_CMV", "NAO_FATURADO_CMV",
        "ESTOQUE_DISP_QTD", "PEDIDO_QTD", "FATURADO_TRANSITO_QTD", "RESERVA_QTD", "ESTOQUE_IMPACTADO_QTD",
        "ESTOQUE_DISP_VALOR", "PEDIDO_VALOR", "FATURADO_TRANSITO_VALOR", "RESERVA_VALOR", "ESTOQUE_IMPACTADO_VALOR",
    ]
    for c in num_cols:
        if c not in base.columns:
            base[c] = 0
        base[c] = pd.to_numeric(base[c], errors="coerce").fillna(0)

    base["TEM_PRE_NOTA"] = base.get("TEM_PRE_NOTA", False)
    base["TEM_PRE_NOTA"] = base["TEM_PRE_NOTA"].fillna(False)
    base["PRE_NOTA"] = base["TEM_PRE_NOTA"].map(lambda x: "SIM" if bool(x) else "NÃO")

    def situacao_operacional(row):
        partes = []
        partes.append("TEM CARTEIRA" if row["CARTEIRA_CMV"] > 0 else "SEM CARTEIRA")
        partes.append("TEM ESTOQUE IMPACTADO" if row["ESTOQUE_IMPACTADO_QTD"] > 0 else "SEM ESTOQUE IMPACTADO")
        partes.append("COM PRÉ-NOTA" if bool(row["TEM_PRE_NOTA"]) else "SEM PRÉ-NOTA")
        return " | ".join(partes)

    base["SITUACAO_CARTEIRA_ESTOQUE"] = base.apply(situacao_operacional, axis=1)
    base["RECOMENDACAO"] = base.apply(recomendacao, axis=1)

    resumo = base.groupby("SITUACAO", as_index=False).agg(
        ITENS=("CODIGO", "nunique"),
        CARTEIRA_CMV=("CARTEIRA_CMV", "sum"),
        PRE_NOTA_CMV=("PRE_NOTA_CMV", "sum"),
        NAO_FATURADO_CMV=("NAO_FATURADO_CMV", "sum"),
        ESTOQUE_DISP_QTD=("ESTOQUE_DISP_QTD", "sum"),
        PEDIDO_QTD=("PEDIDO_QTD", "sum"),
        FATURADO_TRANSITO_QTD=("FATURADO_TRANSITO_QTD", "sum"),
        RESERVA_QTD=("RESERVA_QTD", "sum"),
        ESTOQUE_IMPACTADO_QTD=("ESTOQUE_IMPACTADO_QTD", "sum"),
        ESTOQUE_IMPACTADO_VALOR=("ESTOQUE_IMPACTADO_VALOR", "sum"),
    )

    por_movimento = base.groupby(["SITUACAO", "MOVIMENTO_FLAG", "MOVIMENTO_STATUS", "MOTIVO"], as_index=False).agg(
        ITENS=("CODIGO", "nunique"),
        CARTEIRA_CMV=("CARTEIRA_CMV", "sum"),
        ESTOQUE_IMPACTADO_QTD=("ESTOQUE_IMPACTADO_QTD", "sum"),
        ESTOQUE_IMPACTADO_VALOR=("ESTOQUE_IMPACTADO_VALOR", "sum"),
    )

    return base, resumo, por_movimento


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
                ws.column_dimensions[col_letter].width = min(max(max_len + 2, 12), 50)

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
    money_cols = [c for c in df.columns if c.endswith("CMV") or c.endswith("VALOR")]
    fmt = {c: moeda for c in money_cols}
    qtd_cols = [c for c in df.columns if c.endswith("QTD")]
    for c in qtd_cols:
        fmt[c] = "{:.0f}"
    return df.style.format(fmt)


st.title("📊 Análise de alteração de flags/status")
st.caption("Cruza alteração de flag/status com carteira, pré-nota e estoque impactado.")

with st.sidebar:
    st.header("Importar arquivos")
    arq_alteracoes_lista = st.file_uploader(
        "1) Alteração de flags/status",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        help="Você pode selecionar um ou vários arquivos recebidos por e-mail."
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

    st.success("Arquivos carregados. Análise concluída.")

    with st.expander("Ver composição do estoque impactado"):
        st.write("O app soma estoque disponível + pedido + faturado/trânsito + reserva. EMB. COMP. fica fora.")
        st.json(cobertura.attrs.get("colunas_usadas", {}))

    for idx, arq_alt in enumerate(arq_alteracoes_lista, start=1):
        nome_base = nome_seguro(arq_alt.name)

        with st.spinner(f"Processando {arq_alt.name}..."):
            base, resumo, por_movimento = montar_analise(arq_alt, carteira, cobertura)
            excel_bytes = gerar_excel(base, resumo, por_movimento)
            resultados_zip.append((f"resultado_{nome_base}.xlsx", excel_bytes))
            base_tmp = base.copy()
            base_tmp["ARQUIVO_ALTERACAO"] = arq_alt.name
            bases_consolidadas.append(base_tmp)

        st.markdown("---")
        st.subheader(f"📄 {idx}. {arq_alt.name}")

        total_itens = int(base["CODIGO"].nunique())
        total_carteira = base["CARTEIRA_CMV"].sum()
        total_pre_nota = base["PRE_NOTA_CMV"].sum()
        total_estoque_qtd = base["ESTOQUE_IMPACTADO_QTD"].sum()
        total_estoque_valor = base["ESTOQUE_IMPACTADO_VALOR"].sum()

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Itens impactados", f"{total_itens:,.0f}".replace(",", "."))
        c2.metric("Carteira", moeda(total_carteira))
        c3.metric("Pré-nota", moeda(total_pre_nota))
        c4.metric("Estoque impactado qtd", f"{total_estoque_qtd:,.0f}".replace(",", "."))
        c5.metric("Estoque impactado valor", moeda(total_estoque_valor))

        st.download_button(
            f"⬇️ Baixar Excel - {arq_alt.name}",
            data=excel_bytes,
            file_name=f"resultado_{nome_base}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"download_excel_{idx}_{nome_base}",
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
                "CODIGO", "DESCRICAO", "LOJA",
                "FLAG_ANTERIOR", "FLAG_NOVA", "MOVIMENTO_FLAG",
                "STATUS_ANTERIOR", "STATUS_NOVO", "MOVIMENTO_STATUS",
                "SITUACAO", "MOTIVO", "RECOMENDACAO",
                "CARTEIRA_CMV", "PRE_NOTA_CMV", "NAO_FATURADO_CMV", "PRE_NOTA",
                "ESTOQUE_DISP_QTD", "PEDIDO_QTD", "FATURADO_TRANSITO_QTD", "RESERVA_QTD",
                "ESTOQUE_IMPACTADO_QTD", "ESTOQUE_IMPACTADO_VALOR",
                "SITUACAO_CARTEIRA_ESTOQUE",
            ]
            colunas = [c for c in colunas if c in base.columns]
            st.dataframe(formatar_tabela(base[colunas]), use_container_width=True, hide_index=True)

        with aba4:
            st.subheader("Consultar produto ou situação")
            situacoes = ["Todas"] + sorted(base["SITUACAO"].dropna().unique().tolist())
            sit = st.selectbox("Situação", situacoes, key=f"situacao_{idx}_{nome_base}")
            busca = st.text_input("Buscar por código, descrição ou loja", key=f"busca_{idx}_{nome_base}")

            filtrado = base.copy()
            if sit != "Todas":
                filtrado = filtrado[filtrado["SITUACAO"] == sit]
            if busca.strip():
                b = busca.strip().upper()
                filtrado = filtrado[
                    filtrado["CODIGO"].astype(str).str.upper().str.contains(b, na=False)
                    | filtrado["DESCRICAO"].astype(str).str.upper().str.contains(b, na=False)
                    | filtrado["LOJA"].astype(str).str.upper().str.contains(b, na=False)
                ]
            st.dataframe(formatar_tabela(filtrado[colunas]), use_container_width=True, hide_index=True)

    if len(resultados_zip) > 1:
        st.markdown("---")
        zip_bytes = gerar_zip(resultados_zip)
        st.download_button(
            "⬇️ Baixar todos os resultados em ZIP",
            data=zip_bytes,
            file_name="resultados_analise_flags_status.zip",
            mime="application/zip",
        )

    if len(bases_consolidadas) > 1:
        st.markdown("---")
        st.subheader("Consolidado de todos os arquivos")
        base_geral = pd.concat(bases_consolidadas, ignore_index=True)
        resumo_geral = base_geral.groupby("SITUACAO", as_index=False).agg(
            ITENS=("CODIGO", "nunique"),
            CARTEIRA_CMV=("CARTEIRA_CMV", "sum"),
            PRE_NOTA_CMV=("PRE_NOTA_CMV", "sum"),
            NAO_FATURADO_CMV=("NAO_FATURADO_CMV", "sum"),
            ESTOQUE_IMPACTADO_QTD=("ESTOQUE_IMPACTADO_QTD", "sum"),
            ESTOQUE_IMPACTADO_VALOR=("ESTOQUE_IMPACTADO_VALOR", "sum"),
        )
        st.dataframe(formatar_tabela(resumo_geral), use_container_width=True, hide_index=True)

except Exception as e:
    st.error("Erro na análise")
    st.exception(e)

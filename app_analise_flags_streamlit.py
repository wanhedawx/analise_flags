# -*- coding: utf-8 -*-
"""
APP STREAMLIT - ANÁLISE DE ALTERAÇÃO DE FLAGS x CARTEIRA x ESTOQUE

Como usar:
1) Instale uma vez:
   pip install streamlit pandas openpyxl

2) Execute:
   streamlit run app_analise_flags_streamlit.py

3) Na tela, importe os 3 arquivos:
   - Alteração de flags recebido por e-mail
   - Carteira com agendamento / carteira sem pré-nota
   - Cobertura / Cobertura Pura

Regra:
- A/I/V/K/L/P -> B/D/F/X = RISCO IMPRODUTIVO
- B/D/F/X -> A/I/V/K/L/P = RISCO RUPTURA

Estoque:
- Usa DISP. VENDA e soma TRANSITO + RESERVA, ignorando FAT. LOJA.
"""

from io import BytesIO
import re
import pandas as pd
import streamlit as st

FLAGS_ATIVAS = {"A", "I", "V", "K", "L", "P"}
FLAGS_RISCO = {"B", "D", "F", "X"}

st.set_page_config(
    page_title="Análise de Flags x Carteira x Estoque",
    page_icon="📊",
    layout="wide",
)


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
    if pd.isna(valor):
        return ""
    s = str(valor).strip().upper()
    letras = re.findall(r"[A-Z]", s)
    return letras[0] if letras else ""


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
    ], contexto="do código do produto no arquivo de flags")

    col_desc = primeira_coluna_existente(df, [
        "DESCRIÇÃO", "DESCRICAO", "DESC. PRODUTO", "DESC_PROD", "Desc_Prod", "PRODUTO"
    ], obrigatoria=False)

    col_nova = primeira_coluna_existente(df, [
        "STATUS PROD", "FLAG ABAST", "FLAG NOVA", "STATUS NOVO", "NOVA FLAG", "FLAG PROD LOJA", "FLAG PROD CD"
    ], contexto="da flag nova no arquivo de flags")

    col_ant = primeira_coluna_existente(df, [
        "STATUS ANTERIOR", "FLAG ANTERIOR", "FLAG ANTIGA", "STATUS ANTIGO", "ANTERIOR",
        "STATUS PROD ANTERIOR", "FLAG ABAST ANTERIOR"
    ], contexto="da flag anterior no arquivo de flags")

    out = pd.DataFrame()
    out["CODIGO"] = df[col_codigo].map(normaliza_codigo)
    out["DESCRICAO"] = df[col_desc] if col_desc else ""
    out["FLAG_ANTERIOR"] = df[col_ant].map(normaliza_flag)
    out["FLAG_NOVA"] = df[col_nova].map(normaliza_flag)
    out = out[(out["CODIGO"] != "") & (out["FLAG_ANTERIOR"] != "") & (out["FLAG_NOVA"] != "")].copy()

    def classificar(row):
        ant = row["FLAG_ANTERIOR"]
        nova = row["FLAG_NOVA"]
        if ant in FLAGS_ATIVAS and nova in FLAGS_RISCO:
            return "RISCO IMPRODUTIVO"
        if ant in FLAGS_RISCO and nova in FLAGS_ATIVAS:
            return "RISCO RUPTURA"
        return "FORA DA REGRA"

    out["MOVIMENTO"] = out["FLAG_ANTERIOR"] + " -> " + out["FLAG_NOVA"]
    out["SITUACAO"] = out.apply(classificar, axis=1)
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

    # Soma tudo que for trânsito + reserva. Não usa FAT. LOJA.
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

    resumo = base.groupby("SITUACAO", as_index=False).agg(
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

    por_movimento = base.groupby(["SITUACAO", "MOVIMENTO"], as_index=False).agg(
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
        "SITUACAO": "SITUAÇÃO",
        "ITENS_QTD": "ITENS QTD",
        "CARTEIRA_QTD": "CARTEIRA QTD",
        "CARTEIRA_VALOR": "CARTEIRA R$",
        "PRE_NOTA_QTD": "PRE NOTA QTD",
        "PRE_NOTA_VALOR": "PRE NOTA VALOR",
        "NAO_FATURADO_QTD": "NÃO FATURADO QTD",
        "NAO_FATURADO_VALOR": "NÃO FATURADO VALOR",
        "DISP_VENDA_QTD": "DISP VENDA QTD",
        "DISP_VENDA_VALOR": "DISP VENDA VALOR",
        "RESERV_TRANS_QTD": "ESTOQUE RESERV/TRANS QTD",
        "RESERV_TRANS_VALOR": "ESTOQUE RESERV/TRANS VALOR",
        "TOTAL_ESTOQUE_QTD": "TOTAL IMPACTO ESTOQUE QTD",
        "TOTAL_ESTOQUE_VALOR": "TOTAL IMPACTO ESTOQUE VALOR",
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



st.title("📊 Análise de alteração de flags")
st.caption("Cruza alteração de flag com carteira, pré-nota e estoque disponível para venda.")

with st.sidebar:
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

    st.success("Análise concluída.")

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
            "CODIGO", "DESCRICAO", "FLAG_ANTERIOR", "FLAG_NOVA", "MOVIMENTO", "SITUACAO",
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

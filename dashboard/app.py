"""Dashboard executivo de Aviação EUA. A SPEC está na docstring de painel.py."""

import streamlit as st

from dashboard import painel

st.set_page_config(page_title="Aviação EUA | Visão da Operação", layout="wide")

MARCA = painel.COR_MARCA

# Cartões: (ícone, rótulo, formatador, coluna do Mart 11) — ordem da SPEC.
CARTOES = [
    ("flight", "Total de voos", painel.numero, "total_voos"),
    ("schedule", "Voos atrasados", painel.pct, "pct_atrasos"),
    ("cancel", "Voos cancelados", painel.pct, "pct_cancelamentos"),
    ("timer", "Atraso médio", painel.minutos, "atraso_medio_minutos"),
    ("connecting_airports", "Total de aeroportos", painel.numero, "total_aeroportos"),
]

st.markdown(
    f"""
    <style>
    .block-container {{ padding-top: 1.5rem; padding-bottom: 3rem; }}

    .st-key-cabecalho {{
        background: linear-gradient(135deg, {MARCA} 0%, #2a9d8f 100%);
        border-radius: 16px;
        padding: 26px 30px 22px;
        box-shadow: 0 6px 18px rgba(31, 122, 104, 0.25);
        margin-bottom: 0.5rem;
    }}
    .st-key-cabecalho h1, .st-key-cabecalho p {{ color: #ffffff; }}
    .st-key-cabecalho h1 {{ padding: 0 0 4px; font-size: 2.1rem; }}
    .st-key-cabecalho .descricao {{ font-size: 1.1rem; margin: 0 0 10px; opacity: 0.95; }}
    .st-key-cabecalho .periodo {{ font-size: 1.05rem; font-weight: 700; margin: 0 0 4px; }}
    .st-key-cabecalho .fonte {{ font-size: 0.9rem; margin: 0; opacity: 0.9; }}
    .st-key-cabecalho button {{
        background: #ffffff; border: none; color: {MARCA}; font-weight: 600;
    }}
    .st-key-cabecalho button p {{ color: {MARCA}; }}
    .st-key-cabecalho button:hover {{ background: #eef7f5; color: {MARCA}; }}

    .secao {{
        color: {painel.COR_TEXTO_SECUNDARIO};
        font-size: 0.8rem; font-weight: 700; letter-spacing: 0.08em;
        text-transform: uppercase;
        margin: 1.6rem 0 0.5rem; padding-left: 10px;
        border-left: 3px solid {MARCA};
    }}

    [data-testid="stMetric"] {{
        background: {painel.COR_MARCA_SUAVE};
        border-left: 5px solid {MARCA};
        border-radius: 12px;
        padding: 18px 20px;
        box-shadow: 0 1px 3px rgba(29, 36, 51, 0.08);
    }}
    [data-testid="stMetricLabel"] [data-testid="stIconMaterial"] {{ color: {MARCA}; }}
    [data-testid="stMetricLabel"] p {{
        color: {painel.COR_TEXTO_SECUNDARIO}; font-size: 0.95rem; font-weight: 600;
    }}
    [data-testid="stMetricValue"] {{
        color: {painel.COR_TEXTO}; font-weight: 700; font-size: 2rem;
    }}

    [class*="st-key-grafico_"] {{
        background: #ffffff;
        border: 1px solid {painel.COR_GRADE};
        border-radius: 12px;
        padding: 12px 14px 4px;
        box-shadow: 0 1px 3px rgba(29, 36, 51, 0.06);
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

COMANDO_MARTS = "uv run python -m pipeline.marts"


@st.cache_data(show_spinner="Lendo os Marts…")
def carregar():
    # painel.ler abre e fecha a conexão; só os DataFrames ficam em cache.
    return painel.ler(painel.MARTS)


def secao(texto):
    st.markdown(f'<div class="secao">{texto}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------- CABEÇALHO

with st.container(key="cabecalho"):
    texto, acao = st.columns([5, 1], vertical_alignment="top")
    texto.title("✈️ Aviação EUA · Visão da operação")
    texto.markdown(
        '<p class="descricao">Dashboard executivo de desempenho da aviação '
        "norte-americana</p>",
        unsafe_allow_html=True,
    )
    # Preenchido após a leitura, pois o tamanho da amostra vem do Mart 11.
    contexto = texto.empty()
    if acao.button("Recarregar dados", icon=":material/refresh:", width="stretch"):
        carregar.clear()

try:
    dados = carregar()
except painel.BancoNaoEncontrado as erro:
    st.error(f"Banco de dados não encontrado: `{erro}`")
    st.stop()
except painel.MartsAusentes as erro:
    st.error(
        "Marts ausentes no schema `marts`: "
        + ", ".join(f"`{m}`" for m in erro.ausentes)
    )
    st.info(
        "Execute manualmente o orquestrador abaixo. Antes, garanta que nenhum outro "
        "processo (MCP, UI do DuckDB, outro script) está com o banco aberto."
    )
    st.code(COMANDO_MARTS, language="powershell")
    st.stop()
except painel.ErroLeitura as erro:
    st.error(f"Erro ao conectar ou ler `aviation.duckdb`: {erro}")
    st.info(
        "Nenhuma nova tentativa será feita automaticamente. Se o banco estiver bloqueado "
        "por outro processo, aguarde a liberação e clique em **Recarregar dados**."
    )
    st.stop()

problemas = {mart: painel.problema(dados, mart) for mart in painel.MARTS}
problemas = {mart: msg for mart, msg in problemas.items() if msg}

fonte = "camada analítica MARTS (aviation.duckdb)"
if "kpis" not in problemas:
    total = painel.numero(dados["kpis"]["total_voos"].iloc[0])
    fonte = f"amostra de {total} voos · {fonte}"
contexto.markdown(
    '<p class="periodo">Período analisado: 2025 · Operação aérea dos Estados Unidos</p>'
    f'<p class="fonte">Fonte: {fonte}</p>',
    unsafe_allow_html=True,
)

if problemas:
    st.warning(
        "Alguns painéis não puderam ser exibidos e o dashboard está incompleto: "
        + "; ".join(problemas.values())
    )

# ---------------------------------------------------------------- FAIXA 1

secao("Indicadores gerais")
if "kpis" in problemas:
    st.error(f"Cartões indisponíveis. {problemas['kpis']}")
else:
    kpis = dados["kpis"].iloc[0]
    for coluna, (icone, rotulo, formatar, campo) in zip(
        st.columns(5), CARTOES, strict=True
    ):
        coluna.metric(f":material/{icone}: {rotulo}", formatar(kpis[campo]))


def mostrar(mart, onde=st):
    with onde.container(key=f"grafico_{mart}"):
        if mart in problemas:
            st.error(problemas[mart])
        else:
            st.plotly_chart(painel.GRAFICOS[mart](dados[mart]), width="stretch")


def faixa(*marts):
    for coluna, mart in zip(st.columns(len(marts)), marts, strict=True):
        mostrar(mart, coluna)


# ---------------------------------------------------------------- FAIXAS 2–6

secao("Destaque · Atrasos por aeroporto")
mostrar("aeroportos_taxa_atrasos")

secao("Aeroportos e companhias")
faixa(
    "aeroportos_taxa_cancelamentos",
    "aeroportos_tempo_medio_atraso",
    "companhias_taxa_atrasos",
)

secao("Companhias e rotas")
faixa(
    "companhias_taxa_cancelamentos",
    "companhias_comparativo_pontualidade",
    "rotas_taxa_atrasos",
)

secao("Rotas, horários e dias da semana")
faixa(
    "rotas_quantidade_cancelamentos",
    "horarios_taxa_atrasos",
    "dias_semana_taxa_atrasos",
)

secao("Visão geográfica")
mostrar("operacao_por_estado")

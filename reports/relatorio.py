"""
relatorio.py — Etapa 4.5: relatório HTML independente do dashboard.

:Gera `reports/relatorio.html` uma fotografia estática do painel aprovado
(app.py), para envio por e-mail e apresentação à diretoria.

- Dados: `painel.ler()` (somente leitura, conexão fechada ao final da leitura).
- Valores e gráficos: os formatadores e as funções de gráfico de `painel.py`.
  Nenhum cálculo de negócio, nenhum gráfico novo, nenhum dado alterado.
- Plotly via CDN, carregado uma única vez (estratégia do projeto Olist):
  primeiro gráfico com include_plotlyjs="cdn", demais com False.
- IDs fixos por gráfico (g01…g12), para o HTML ser estável entre execuções
  com os mesmos dados. O Mart 11 (kpis) alimenta os cartões e não é gráfico,
  por isso o id g11 não é usado.
- Abrir o HTML exige internet (CDN do Plotly e fontes), mas não exige
  Streamlit, servidor Python ou DuckDB.
- Não importa Streamlit.

Uso: uv run python -m reports.relatorio
"""

import sys
from datetime import datetime
from html import escape
from pathlib import Path

from dashboard import painel

SAIDA = Path(__file__).resolve().parent / "relatorio.html"

# Período validado em refined.voos_2025.data_voo: 2025-01-01 a 2025-12-31,
# 365 dias, 10.000 voos por mês (mesmo texto do cabeçalho do app.py).
PERIODO = "Período analisado: 2025 · Operação aérea dos Estados Unidos"
DESCRICAO = "Dashboard executivo de desempenho da aviação norte-americana"
FONTE_DADOS = "camada analítica MARTS (aviation.duckdb)"
COMANDO_MARTS = "uv run python -m pipeline.marts"

# Mesmos cartões, ícones e ordem do app.py.
CARTOES = [
    ("flight", "Total de voos", painel.numero, "total_voos"),
    ("schedule", "Voos atrasados", painel.pct, "pct_atrasos"),
    ("cancel", "Voos cancelados", painel.pct, "pct_cancelamentos"),
    ("timer", "Atraso médio", painel.minutos, "atraso_medio_minutos"),
    ("connecting_airports", "Total de aeroportos", painel.numero, "total_aeroportos"),
]

# Mesmas faixas e ordem do app.py.
FAIXAS = [
    ("Destaque · Atrasos por aeroporto", ["aeroportos_taxa_atrasos"]),
    (
        "Aeroportos e companhias",
        [
            "aeroportos_taxa_cancelamentos",
            "aeroportos_tempo_medio_atraso",
            "companhias_taxa_atrasos",
        ],
    ),
    (
        "Companhias e rotas",
        [
            "companhias_taxa_cancelamentos",
            "companhias_comparativo_pontualidade",
            "rotas_taxa_atrasos",
        ],
    ),
    (
        "Rotas, horários e dias da semana",
        [
            "rotas_quantidade_cancelamentos",
            "horarios_taxa_atrasos",
            "dias_semana_taxa_atrasos",
        ],
    ),
    ("Visão geográfica", ["operacao_por_estado"]),
]

IDS = {
    "aeroportos_taxa_atrasos": "g01",
    "aeroportos_taxa_cancelamentos": "g02",
    "aeroportos_tempo_medio_atraso": "g03",
    "companhias_taxa_atrasos": "g04",
    "companhias_taxa_cancelamentos": "g05",
    "companhias_comparativo_pontualidade": "g06",
    "rotas_taxa_atrasos": "g07",
    "rotas_quantidade_cancelamentos": "g08",
    "horarios_taxa_atrasos": "g09",
    "dias_semana_taxa_atrasos": "g10",
    "operacao_por_estado": "g12",
}

# Fonte que o Streamlit usa; aplicada aos gráficos só para o HTML ficar igual ao painel.
FAMILIA_FONTE = '"Source Sans 3", "Source Sans Pro", sans-serif'

CSS = f"""
* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: #f4f6f8; color: {painel.COR_TEXTO};
  font-family: {FAMILIA_FONTE};
}}
main {{ padding: 24px 48px 16px; }}
.material-symbols-rounded {{ font-size: 1.15em; vertical-align: -0.2em; }}

.cabecalho {{
  background: linear-gradient(135deg, {painel.COR_MARCA} 0%, #2a9d8f 100%);
  border-radius: 16px; padding: 26px 30px 22px; color: #ffffff;
  box-shadow: 0 6px 18px rgba(31, 122, 104, 0.25); margin-bottom: 0.5rem;
}}
.cabecalho h1 {{ margin: 0 0 8px; font-size: 2.1rem; font-weight: 700; }}
.cabecalho .descricao {{ font-size: 1.1rem; margin: 0 0 10px; opacity: 0.95; }}
.cabecalho .periodo {{ font-size: 1.05rem; font-weight: 700; margin: 0 0 4px; }}
.cabecalho .fonte {{ font-size: 0.9rem; margin: 0; opacity: 0.9; }}

.secao {{
  color: {painel.COR_TEXTO_SECUNDARIO};
  font-size: 0.8rem; font-weight: 700; letter-spacing: 0.08em;
  text-transform: uppercase;
  margin: 1.6rem 0 0.5rem; padding-left: 10px;
  border-left: 3px solid {painel.COR_MARCA};
}}

.cartoes {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; }}
.cartao {{
  background: {painel.COR_MARCA_SUAVE}; border-left: 5px solid {painel.COR_MARCA};
  border-radius: 12px; padding: 18px 20px;
  box-shadow: 0 1px 3px rgba(29, 36, 51, 0.08);
}}
.cartao .rotulo {{
  color: {painel.COR_TEXTO_SECUNDARIO}; font-size: 0.95rem; font-weight: 600; margin: 0 0 6px;
}}
.cartao .rotulo .material-symbols-rounded {{ color: {painel.COR_MARCA}; }}
.cartao .valor {{ color: {painel.COR_TEXTO}; font-size: 2rem; font-weight: 700; margin: 0; }}

.faixa {{ display: grid; gap: 16px; grid-template-columns: repeat(var(--colunas), 1fr); }}
.grafico {{
  background: #ffffff; border: 1px solid {painel.COR_GRADE}; border-radius: 12px;
  padding: 12px 14px 4px; box-shadow: 0 1px 3px rgba(29, 36, 51, 0.06); min-width: 0;
}}

.aviso, .erro {{ border-radius: 8px; padding: 12px 16px; margin: 12px 0; }}
.aviso {{ background: #fff6e0; color: #6b4e00; }}
.erro {{ background: #fdecec; color: #8a1c1c; }}

footer {{
  color: {painel.COR_TEXTO_SECUNDARIO}; font-size: 0.85rem;
  padding: 8px 48px 32px; text-align: right;
}}

@media (max-width: 1100px) {{
  .cartoes {{ grid-template-columns: repeat(2, 1fr); }}
  .faixa {{ grid-template-columns: 1fr; }}
}}
@media (max-width: 640px) {{
  main {{ padding: 16px; }}
  footer {{ padding: 8px 16px 24px; }}
  .cartoes {{ grid-template-columns: 1fr; }}
  .cabecalho h1 {{ font-size: 1.6rem; }}
}}
"""


def falhar(mensagem):
    print(f"Erro: {mensagem}", file=sys.stderr)
    print("O relatório não foi gerado.", file=sys.stderr)
    sys.exit(1)


def ler_dados():
    try:
        return painel.ler(painel.MARTS)
    except painel.BancoNaoEncontrado as erro:
        falhar(f"banco de dados não encontrado: {erro}")
    except painel.MartsAusentes as erro:
        falhar(
            "Marts ausentes no schema marts: "
            + ", ".join(erro.ausentes)
            + f"\nExecute manualmente: {COMANDO_MARTS} "
            "(sem outro processo com o banco aberto)."
        )
    except painel.ErroLeitura as erro:
        falhar(f"não foi possível conectar ou ler aviation.duckdb: {erro}")


def cabecalho(dados, problemas):
    fonte = FONTE_DADOS
    if "kpis" not in problemas:
        total = painel.numero(dados["kpis"]["total_voos"].iloc[0])
        fonte = f"amostra de {total} voos · {fonte}"
    return f"""
<header class="cabecalho">
  <h1>✈️ Aviação EUA · Visão da operação</h1>
  <p class="descricao">{escape(DESCRICAO)}</p>
  <p class="periodo">{escape(PERIODO)}</p>
  <p class="fonte">Fonte: {escape(fonte)}</p>
</header>"""


def cartoes(dados, problemas):
    if "kpis" in problemas:
        return f'<div class="erro">Cartões indisponíveis. {escape(problemas["kpis"])}</div>'
    kpis = dados["kpis"].iloc[0]
    itens = "".join(
        f"""
  <div class="cartao">
    <p class="rotulo"><span class="material-symbols-rounded">{icone}</span> {escape(rotulo)}</p>
    <p class="valor">{escape(formatar(kpis[campo]))}</p>
  </div>"""
        for icone, rotulo, formatar, campo in CARTOES
    )
    return f'<div class="cartoes">{itens}\n</div>'


def graficos(dados, problemas):
    blocos, plotly_carregado = [], False
    for titulo, marts in FAIXAS:
        celulas = []
        for mart in marts:
            if mart in problemas:
                conteudo = f'<div class="erro">{escape(problemas[mart])}</div>'
            else:
                figura = painel.GRAFICOS[mart](dados[mart])
                figura.update_layout(font_family=FAMILIA_FONTE)
                conteudo = figura.to_html(
                    full_html=False,
                    # Biblioteca pelo CDN uma única vez; os demais reutilizam.
                    include_plotlyjs=False if plotly_carregado else "cdn",
                    div_id=IDS[mart],
                    default_width="100%",
                    config={"responsive": True, "displaylogo": False},
                )
                plotly_carregado = True
            celulas.append(f'<div class="grafico">{conteudo}</div>')
        blocos.append(
            f'<div class="secao">{escape(titulo)}</div>\n'
            f'<div class="faixa" style="--colunas: {len(marts)}">{"".join(celulas)}</div>'
        )
    return "\n".join(blocos)


def montar(dados, gerado_em):
    problemas = {m: painel.problema(dados, m) for m in painel.MARTS}
    problemas = {m: msg for m, msg in problemas.items() if msg}
    aviso = ""
    if problemas:
        aviso = (
            '<div class="aviso">Alguns painéis não puderam ser exibidos e o relatório '
            "está incompleto: " + escape("; ".join(problemas.values())) + "</div>"
        )
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aviação EUA | Visão da Operação</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded&display=block">
<style>{CSS}</style>
</head>
<body>
<main>
{cabecalho(dados, problemas)}
{aviso}
<div class="secao">Indicadores gerais</div>
{cartoes(dados, problemas)}
{graficos(dados, problemas)}
</main>
<footer>Dados gerados em {gerado_em:%d/%m/%Y %H:%M}</footer>
</body>
</html>
"""


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    dados = ler_dados()
    try:
        SAIDA.write_text(montar(dados, datetime.now()), encoding="utf-8")
    except OSError as erro:
        falhar(f"não foi possível gravar {SAIDA}: {erro}")
    tamanho_kb = SAIDA.stat().st_size / 1024
    print("Relatório HTML gerado com sucesso!")
    print(f"Arquivo: {SAIDA}")
    print(f"Tamanho: {painel.numero(tamanho_kb, 1)} KB")


if __name__ == "__main__":
    main()

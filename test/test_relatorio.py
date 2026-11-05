"""Testes de relatorio.py — geração do HTML estático a partir dos 12 Marts.

Os Marts são inventados em um DuckDB temporário (painel.CAMINHO_BANCO
redirecionado) e o HTML é gravado em tmp_path (relatorio.SAIDA redirecionada).
O relatorio.html real e aviation.duckdb nunca são usados.
"""

import contextlib
import io
import re
from datetime import datetime

import duckdb
import pandas as pd

import painel
import relatorio

ORDEM_IDS = ["g01", "g02", "g03", "g04", "g05", "g06", "g07", "g08", "g09", "g10", "g12"]


def _marts_inventados():
    """Um DataFrame por Mart, com as colunas documentadas e poucos registros."""
    aeroportos = pd.DataFrame({
        "codigo_iata": ["AAA", "BBB"], "nome_aeroporto": ["Alfa", "Bravo"],
        "cidade": ["Alfa City", "Bravo City"], "estado": ["TX", "CA"],
        "total_voos": [200, 100], "voos_atrasados": [20, 30],
        "taxa_atrasos_percentual": [10.0, 30.0],
    })
    companhias = pd.DataFrame({
        "codigo_companhia": ["AA", "BB"], "companhia_aerea": ["Alfa Air", "Bravo Air"],
        "total_voos": [150, 150], "voos_atrasados": [15, 30], "voos_cancelados": [3, 6],
        "voos_pontuais": [135, 120], "taxa_atrasos_percentual": [10.0, 20.0],
        "taxa_cancelamentos_percentual": [2.0, 4.0], "taxa_pontualidade_percentual": [90.0, 80.0],
        "media_atraso_minutos": [5.0, 8.0],
    })
    rotas = pd.DataFrame({
        "codigo_origem": ["AAA"], "aeroporto_origem": ["Alfa"], "cidade_origem": ["Alfa City"],
        "codigo_destino": ["BBB"], "aeroporto_destino": ["Bravo"], "cidade_destino": ["Bravo City"],
        "total_voos": [120], "voos_atrasados": [12], "voos_cancelados": [6],
        "taxa_atrasos_percentual": [10.0], "taxa_cancelamentos_percentual": [5.0],
    })
    tabelas = {
        "aeroportos_taxa_atrasos": aeroportos,
        "aeroportos_taxa_cancelamentos": aeroportos.rename(columns={
            "voos_atrasados": "voos_cancelados",
            "taxa_atrasos_percentual": "taxa_cancelamentos_percentual"}),
        "aeroportos_tempo_medio_atraso": aeroportos.rename(columns={
            "taxa_atrasos_percentual": "tempo_medio_atraso_minutos"}),
        "companhias_taxa_atrasos": companhias,
        "companhias_taxa_cancelamentos": companhias,
        "companhias_comparativo_pontualidade": companhias,
        "rotas_taxa_atrasos": rotas,
        "rotas_quantidade_cancelamentos": rotas,
        "horarios_taxa_atrasos": pd.DataFrame({
            "faixa_horario_partida": ["06:00 - 06:59"], "total_voos": [300],
            "voos_atrasados": [45], "taxa_atrasos_percentual": [15.0],
            "media_atraso_minutos": [6.5]}),
        "dias_semana_taxa_atrasos": pd.DataFrame({
            "dia_semana": [3], "nome_dia_semana": ["Terca-feira"], "total_voos": [300],
            "voos_atrasados": [45], "taxa_atrasos_percentual": [15.0],
            "media_atraso_minutos": [6.5]}),
        # Cartões: 12.345 voos; 18,25% atrasos; 2,5% cancelamentos; 41,239 min; 7 aeroportos.
        "kpis": pd.DataFrame({
            "total_voos": [12345], "pct_atrasos": [18.25], "pct_cancelamentos": [2.5],
            "atraso_medio_minutos": [41.239], "total_companhias": [2], "total_aeroportos": [7]}),
        "operacao_por_estado": pd.DataFrame({
            "estado": ["TX", "CA"], "total_voos": [200, 100],
            "pct_atrasos": [10.0, 30.0], "pct_cancelamentos": [1.0, 2.0]}),
    }
    return {nome: df[painel.COLUNAS[nome]] for nome, df in tabelas.items()}


def _preparar(tmp_path, monkeypatch, marts=None):
    caminho = tmp_path / "teste.duckdb"
    con = duckdb.connect(str(caminho))
    try:
        con.execute("CREATE SCHEMA marts")
        for nome, df in (marts if marts is not None else _marts_inventados()).items():
            con.register("_origem", df)
            con.execute(f"CREATE TABLE marts.{nome} AS SELECT * FROM _origem")
            con.unregister("_origem")
    finally:
        con.close()
    saida = tmp_path / "relatorio.html"
    monkeypatch.setattr(painel, "CAMINHO_BANCO", caminho)
    monkeypatch.setattr(relatorio, "SAIDA", saida)
    return saida


def _executar():
    """Executa main() capturando stdout/stderr; devolve (código, stdout, stderr)."""
    saida = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    erros = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    codigo = 0
    with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(erros):
        try:
            relatorio.main()
        except SystemExit as fim:
            codigo = fim.code
    saida.flush()
    erros.flush()
    return (codigo, saida.buffer.getvalue().decode("utf-8"),
            erros.buffer.getvalue().decode("utf-8"))


def _gerar(tmp_path, monkeypatch):
    saida = _preparar(tmp_path, monkeypatch)
    codigo, _, erros = _executar()
    assert codigo == 0, erros
    return saida.read_text(encoding="utf-8")


def _sem_rodape(html):
    return re.sub(r"<footer>Dados gerados em [^<]*</footer>", "<footer></footer>", html)


# ====================================================================== geração


def test_relatorio_e_gerado_dentro_de_tmp_path(tmp_path, monkeypatch):
    saida = _preparar(tmp_path, monkeypatch)
    codigo, texto, _ = _executar()
    assert codigo == 0
    assert saida.is_file()
    assert "Relatório HTML gerado com sucesso!" in texto
    assert str(saida) in texto


def test_relatorio_tem_cabecalho_com_titulo_descricao_e_periodo(tmp_path, monkeypatch):
    html = _gerar(tmp_path, monkeypatch)
    assert '<header class="cabecalho">' in html
    assert "Aviação EUA · Visão da operação" in html
    assert "Dashboard executivo de desempenho da aviação norte-americana" in html
    assert "Período analisado: 2025 · Operação aérea dos Estados Unidos" in html


def test_fonte_do_cabecalho_usa_total_de_voos_do_mart_kpis(tmp_path, monkeypatch):
    html = _gerar(tmp_path, monkeypatch)
    assert "Fonte: amostra de 12.345 voos · camada analítica MARTS (aviation.duckdb)" in html


def test_relatorio_tem_os_cinco_cartoes_na_ordem_com_valores_dos_kpis(tmp_path, monkeypatch):
    html = _gerar(tmp_path, monkeypatch)
    cartoes = re.findall(
        r'<p class="rotulo"><span class="material-symbols-rounded">[^<]*</span> ([^<]*)</p>\s*'
        r'<p class="valor">([^<]*)</p>', html)
    assert cartoes == [
        ("Total de voos", "12.345"),
        ("Voos atrasados", "18,25%"),
        ("Voos cancelados", "2,50%"),
        ("Atraso médio", "41,24 min"),
        ("Total de aeroportos", "7"),
    ]
    # total_companhias não é exibido como cartão.
    assert html.count('class="cartao"') == 5


def test_relatorio_gera_os_11_graficos_com_ids_fixos_na_ordem(tmp_path, monkeypatch):
    html = _gerar(tmp_path, monkeypatch)
    ids = re.findall(r'<div id="(g\d\d)"', html)
    assert ids == ORDEM_IDS
    assert html.count('class="grafico"') == 11


def test_identificador_g11_nao_e_usado(tmp_path, monkeypatch):
    html = _gerar(tmp_path, monkeypatch)
    assert 'id="g11"' not in html
    assert '"g11"' not in html


def test_graficos_estao_agrupados_nas_faixas_da_implementacao(tmp_path, monkeypatch):
    html = _gerar(tmp_path, monkeypatch)
    secoes = re.findall(r'<div class="secao">([^<]*)</div>', html)
    assert secoes == [
        "Indicadores gerais",
        "Destaque · Atrasos por aeroporto",
        "Aeroportos e companhias",
        "Companhias e rotas",
        "Rotas, horários e dias da semana",
        "Visão geográfica",
    ]


def test_dados_dos_marts_sao_incorporados_no_html(tmp_path, monkeypatch):
    html = _gerar(tmp_path, monkeypatch)
    # Rótulos que só existem nos dados inventados.
    for texto in ('"AAA"', '"Alfa Air"', '"AAA \\u2192 BBB"', '"06:00 - 06:59"', '"Ter\\u00e7a-feira"'):
        assert texto in html
    assert "Plotly.newPlot" in html


def test_plotly_e_carregado_pelo_cdn_uma_unica_vez(tmp_path, monkeypatch):
    html = _gerar(tmp_path, monkeypatch)
    scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
    assert len([s for s in scripts if "cdn.plot.ly" in s]) == 1
    assert html.count("cdn.plot.ly") == 1
    # A biblioteca não é embutida (só referenciada pelo CDN).
    assert len(html) < 500_000


def test_html_nao_depende_de_servidor_local(tmp_path, monkeypatch):
    html = _gerar(tmp_path, monkeypatch).lower()
    for referencia in ("localhost", "127.0.0.1", "_stcore", "streamlit", "8501"):
        assert referencia not in html


def test_rodape_mostra_data_e_hora_da_geracao():
    html = relatorio.montar(_marts_inventados(), datetime(2026, 3, 7, 9, 5))
    assert "<footer>Dados gerados em 07/03/2026 09:05</footer>" in html


def test_relatorio_duas_execucoes_mantem_conteudo_estavel(tmp_path, monkeypatch):
    saida = _preparar(tmp_path, monkeypatch)
    _executar()
    primeira = saida.read_text(encoding="utf-8")
    _executar()
    segunda = saida.read_text(encoding="utf-8")
    assert _sem_rodape(primeira) == _sem_rodape(segunda)


def test_montar_com_mesmos_dados_difere_somente_no_rodape():
    dados = _marts_inventados()
    a = relatorio.montar(dados, datetime(2026, 1, 1, 8, 0))
    b = relatorio.montar(dados, datetime(2026, 12, 31, 23, 59))
    assert a != b
    assert _sem_rodape(a) == _sem_rodape(b)


def test_relatorio_completo_nao_mostra_aviso(tmp_path, monkeypatch):
    html = _gerar(tmp_path, monkeypatch)
    assert '<div class="aviso">' not in html
    assert '<div class="erro">' not in html


# ====================================================================== problemas de dados


def test_mart_vazio_gera_aviso_e_nao_exibe_o_grafico():
    dados = _marts_inventados()
    dados["rotas_taxa_atrasos"] = dados["rotas_taxa_atrasos"].iloc[0:0]
    html = relatorio.montar(dados, datetime(2026, 1, 1))
    assert '<div class="aviso">' in html
    assert "Mart `rotas_taxa_atrasos` está vazio." in html
    assert re.findall(r'<div id="(g\d\d)"', html) == [i for i in ORDEM_IDS if i != "g07"]


def test_kpis_indisponivel_remove_cartoes_e_total_da_fonte():
    dados = _marts_inventados()
    dados["kpis"] = dados["kpis"].drop(columns=["pct_atrasos"])
    html = relatorio.montar(dados, datetime(2026, 1, 1))
    assert "Cartões indisponíveis." in html
    assert "pct_atrasos" in html
    assert 'class="cartao"' not in html
    assert "Fonte: camada analítica MARTS (aviation.duckdb)" in html
    assert "amostra de" not in html


def test_banco_ausente_encerra_sem_gerar_relatorio(tmp_path, monkeypatch):
    saida = tmp_path / "relatorio.html"
    monkeypatch.setattr(painel, "CAMINHO_BANCO", tmp_path / "inexistente.duckdb")
    monkeypatch.setattr(relatorio, "SAIDA", saida)
    codigo, _, erros = _executar()
    assert codigo == 1
    assert "banco de dados não encontrado" in erros
    assert "O relatório não foi gerado." in erros
    assert not saida.exists()


def test_marts_ausentes_sao_listados_e_orientam_executar_o_orquestrador(tmp_path, monkeypatch):
    marts = _marts_inventados()
    del marts["kpis"], marts["operacao_por_estado"]
    saida = _preparar(tmp_path, monkeypatch, marts)
    codigo, _, erros = _executar()
    assert codigo == 1
    assert "kpis, operacao_por_estado" in erros
    assert "uv run python -m pipeline.marts" in erros
    assert not saida.exists()


def test_banco_ilegivel_encerra_com_erro_de_leitura(tmp_path, monkeypatch):
    caminho = tmp_path / "corrompido.duckdb"
    caminho.write_bytes(b"nao e duckdb" * 200)
    saida = tmp_path / "relatorio.html"
    monkeypatch.setattr(painel, "CAMINHO_BANCO", caminho)
    monkeypatch.setattr(relatorio, "SAIDA", saida)
    codigo, _, erros = _executar()
    assert codigo == 1
    assert "não foi possível conectar ou ler aviation.duckdb" in erros
    assert not saida.exists()

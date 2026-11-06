"""Testes de painel.py — leitura, formatação e funções de gráfico (SPEC seções 5 a 11).

Streamlit não é importado. ler() é exercitada contra um DuckDB temporário
(painel.CAMINHO_BANCO redirecionado); os gráficos recebem DataFrames inventados.
"""

import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pandas as pd
import plotly.graph_objects as go
import pytest

from dashboard import painel

RAIZ = Path(__file__).resolve().parent.parent


def _x(fig):
    return list(fig.data[0].x)


def _y(fig):
    return list(fig.data[0].y)


def _aeroportos(qtd, taxa="taxa_atrasos_percentual", contagem="voos_atrasados"):
    """qtd aeroportos A00..; total_voos decrescente (1000, 990, ...) e taxa crescente."""
    return pd.DataFrame({
        "codigo_iata": [f"A{i:02d}" for i in range(qtd)],
        "nome_aeroporto": [f"Aeroporto {i}" for i in range(qtd)],
        "cidade": ["Cidade"] * qtd,
        "estado": ["TX"] * qtd,
        "total_voos": [1000 - 10 * i for i in range(qtd)],
        contagem: [i for i in range(qtd)],
        taxa: [float(i) for i in range(qtd)],
    })


# ====================================================================== formatação


def test_numero_usa_ponto_no_milhar():
    assert painel.numero(120) == "120"
    assert painel.numero(4321) == "4.321"
    assert painel.numero(1234567) == "1.234.567"


def test_numero_com_casas_usa_virgula_no_decimal():
    assert painel.numero(1234.5, 1) == "1.234,5"
    assert painel.numero(0.456, 2) == "0,46"


def test_pct_tem_duas_casas_e_simbolo_de_percentual():
    assert painel.pct(7.3) == "7,30%"
    assert painel.pct(1234.567) == "1.234,57%"
    assert painel.pct(50, 0) == "50%"


def test_minutos_tem_duas_casas_e_unidade():
    assert painel.minutos(12.5) == "12,50 min"
    assert painel.minutos(1500) == "1.500,00 min"


def test_valores_nulos_sao_exibidos_como_travessao():
    for nulo in (None, float("nan"), pd.NA, pd.NaT):
        assert painel.numero(nulo) == "—"
        assert painel.pct(nulo) == "—"
        assert painel.minutos(nulo) == "—"


def test_formatacao_nao_modifica_o_valor_original():
    serie = pd.Series([1234.5678])
    painel.pct(serie.iloc[0])
    assert serie.iloc[0] == 1234.5678


# ====================================================================== leitura


def _banco_marts(tmp_path, monkeypatch, tabelas):
    caminho = tmp_path / "teste.duckdb"
    con = duckdb.connect(str(caminho))
    try:
        con.execute("CREATE SCHEMA marts")
        for nome, sql in tabelas.items():
            con.execute(f"CREATE TABLE marts.{nome} AS {sql}")
    finally:
        con.close()
    monkeypatch.setattr(painel, "CAMINHO_BANCO", caminho)
    return caminho


def test_ler_devolve_um_dataframe_por_mart_sem_modificar_os_dados(tmp_path, monkeypatch):
    _banco_marts(tmp_path, monkeypatch, {
        "kpis": "SELECT 10 AS total_voos, 12.5 AS pct_atrasos",
        "operacao_por_estado": "SELECT * FROM (VALUES ('TX', 3), ('CA', 7)) t(estado, total_voos)",
    })
    dados = painel.ler(["kpis", "operacao_por_estado"])
    assert list(dados) == ["kpis", "operacao_por_estado"]
    assert dados["kpis"].to_dict("records") == [{"total_voos": 10, "pct_atrasos": 12.5}]
    # Ordem das linhas preservada como gravada (sem ordenar nem agregar).
    assert list(dados["operacao_por_estado"]["estado"]) == ["TX", "CA"]


def test_ler_fecha_a_conexao_e_libera_o_banco(tmp_path, monkeypatch):
    caminho = _banco_marts(tmp_path, monkeypatch, {"kpis": "SELECT 1 AS total_voos"})
    painel.ler(["kpis"])
    # Uma conexão de escrita só abre se a leitura não mantiver o banco aberto em read_only.
    con = duckdb.connect(str(caminho))
    try:
        con.execute("CREATE TABLE marts.nova AS SELECT 1 AS x")
        assert con.execute("SELECT x FROM marts.nova").fetchone() == (1,)
    finally:
        con.close()


def test_ler_banco_ausente_gera_banco_nao_encontrado_sem_criar_arquivo(tmp_path, monkeypatch):
    caminho = tmp_path / "inexistente.duckdb"
    monkeypatch.setattr(painel, "CAMINHO_BANCO", caminho)
    with pytest.raises(painel.BancoNaoEncontrado):
        painel.ler(["kpis"])
    assert not caminho.exists()


def test_ler_lista_todos_os_marts_ausentes_de_uma_vez(tmp_path, monkeypatch):
    _banco_marts(tmp_path, monkeypatch, {"kpis": "SELECT 1 AS total_voos"})
    with pytest.raises(painel.MartsAusentes) as erro:
        painel.ler(["rotas_taxa_atrasos", "kpis", "operacao_por_estado"])
    assert erro.value.ausentes == ["rotas_taxa_atrasos", "operacao_por_estado"]


def test_ler_arquivo_invalido_gera_erro_de_leitura(tmp_path, monkeypatch):
    # Arquivo que não é um banco DuckDB.
    caminho = tmp_path / "corrompido.duckdb"
    caminho.write_bytes(b"isto nao e um banco duckdb" * 100)
    monkeypatch.setattr(painel, "CAMINHO_BANCO", caminho)
    with pytest.raises(painel.ErroLeitura):
        painel.ler(["kpis"])


def test_ler_rejeita_nome_de_mart_que_nao_e_identificador_simples(tmp_path, monkeypatch):
    monkeypatch.setattr(painel, "CAMINHO_BANCO", tmp_path / "x.duckdb")
    with pytest.raises(ValueError):
        painel.ler(["kpis; DROP SCHEMA marts"])


def test_marts_lidos_sao_os_12_documentados():
    assert len(painel.MARTS) == 12
    assert painel.MARTS[10] == "kpis"
    assert set(painel.GRAFICOS) == set(painel.MARTS) - {"kpis"}


# ====================================================================== problema()


def test_problema_informa_mart_e_colunas_ausentes():
    dados = {"kpis": pd.DataFrame({"total_voos": [1]})}
    mensagem = painel.problema(dados, "kpis")
    assert "kpis" in mensagem
    assert "pct_atrasos" in mensagem and "total_aeroportos" in mensagem
    assert "total_voos," not in mensagem


def test_problema_informa_mart_vazio():
    dados = {"kpis": pd.DataFrame(columns=painel.COLUNAS["kpis"])}
    assert painel.problema(dados, "kpis") == "Mart `kpis` está vazio."


def test_problema_devolve_none_para_mart_valido():
    dados = {"kpis": pd.DataFrame([[1, 2.0, 3.0, 4.0, 5, 6]], columns=painel.COLUNAS["kpis"])}
    assert painel.problema(dados, "kpis") is None


# ====================================================================== gráficos 01 e 02


def test_aeroportos_sao_selecionados_por_volume_antes_do_top_10_por_taxa():
    # 35 aeroportos: A30..A34 têm as maiores taxas, mas os menores volumes.
    fig = painel.grafico_01_aeroportos_atrasos(_aeroportos(35))
    assert isinstance(fig, go.Figure)
    # Dentro dos 30 maiores volumes (A00..A29), as 10 maiores taxas são A29..A20.
    assert _y(fig) == [f"A{i:02d}" for i in range(29, 19, -1)]
    assert _x(fig) == [float(i) for i in range(29, 19, -1)]


def test_empate_no_volume_e_desempatado_por_codigo_iata_crescente():
    # 31 aeroportos; os dois últimos empatam em volume na 30ª posição.
    df = _aeroportos(31)
    df.loc[29, ["codigo_iata", "total_voos", "taxa_atrasos_percentual"]] = ["ZZZ", 50, 99.0]
    df.loc[30, ["codigo_iata", "total_voos", "taxa_atrasos_percentual"]] = ["BBB", 50, 98.0]
    fig = painel.grafico_01_aeroportos_atrasos(df)
    # "BBB" < "ZZZ": BBB entra no grupo e ZZZ fica fora.
    assert "BBB" in _y(fig)
    assert "ZZZ" not in _y(fig)
    assert _y(fig)[0] == "BBB"


def test_empate_na_taxa_respeita_a_ordem_da_selecao_por_volume():
    # Todos com a mesma taxa: a ordem exibida é a da seleção (maior volume, depois IATA).
    df = _aeroportos(12)
    df["taxa_atrasos_percentual"] = 10.0
    df.loc[3, "total_voos"] = df.loc[2, "total_voos"]  # A02 e A03 empatam no volume
    fig = painel.grafico_01_aeroportos_atrasos(df)
    assert _y(fig) == [f"A{i:02d}" for i in range(10)]


def test_selecao_e_deterministica_quando_a_ordem_das_linhas_muda():
    df = _aeroportos(35)
    df.loc[[5, 6], "total_voos"] = 700  # empate de volume
    df.loc[[7, 8], "taxa_atrasos_percentual"] = 7.5  # empate de taxa
    original = painel.grafico_01_aeroportos_atrasos(df)
    embaralhado = painel.grafico_01_aeroportos_atrasos(df.sample(frac=1, random_state=7))
    invertido = painel.grafico_01_aeroportos_atrasos(df.iloc[::-1])
    assert _y(original) == _y(embaralhado) == _y(invertido)
    assert _x(original) == _x(embaralhado) == _x(invertido)


def test_grafico_02_aplica_a_mesma_regra_com_a_taxa_de_cancelamentos():
    df = _aeroportos(35, "taxa_cancelamentos_percentual", "voos_cancelados")
    fig = painel.grafico_02_aeroportos_cancelamentos(df)
    assert _y(fig) == [f"A{i:02d}" for i in range(29, 19, -1)]


def test_selecao_por_volume_e_independente_para_cada_mart():
    # Mesmos aeroportos; no Mart 02 o volume é invertido, então o grupo dos 30 muda.
    atrasos = _aeroportos(35)
    cancelamentos = _aeroportos(35, "taxa_cancelamentos_percentual", "voos_cancelados")
    cancelamentos["total_voos"] = list(reversed(cancelamentos["total_voos"]))
    g01 = painel.grafico_01_aeroportos_atrasos(atrasos)
    g02 = painel.grafico_02_aeroportos_cancelamentos(cancelamentos)
    # Mart 02: maiores volumes são A34..A05; maiores taxas nesse grupo: A34..A25.
    assert _y(g02) == [f"A{i:02d}" for i in range(34, 24, -1)]
    assert _y(g01) != _y(g02)


def test_graficos_01_e_02_tem_subtitulo_dos_30_aeroportos_com_mais_voos():
    g01 = painel.grafico_01_aeroportos_atrasos(_aeroportos(5))
    g02 = painel.grafico_02_aeroportos_cancelamentos(
        _aeroportos(5, "taxa_cancelamentos_percentual", "voos_cancelados"))
    for fig in (g01, g02):
        assert fig.layout.title.subtitle.text == "Entre os 30 aeroportos com mais voos"


def test_grafico_nao_altera_o_dataframe_recebido():
    df = _aeroportos(35)
    copia = df.copy()
    painel.grafico_01_aeroportos_atrasos(df)
    assert df.equals(copia)


# ====================================================================== gráficos 03 a 08 e 12


def test_grafico_03_top_10_por_tempo_medio_decrescente():
    df = _aeroportos(12, "tempo_medio_atraso_minutos")
    fig = painel.grafico_03_aeroportos_tempo_medio(df)
    assert _y(fig) == [f"A{i:02d}" for i in range(11, 1, -1)]
    assert fig.layout.xaxis.ticksuffix == " min"


def _companhias(coluna, valores):
    qtd = len(valores)
    return pd.DataFrame({
        "codigo_companhia": [f"C{i}" for i in range(qtd)],
        "companhia_aerea": [f"Companhia {i}" for i in range(qtd)],
        "total_voos": [100] * qtd,
        "voos_atrasados": [1] * qtd,
        "voos_cancelados": [1] * qtd,
        "voos_pontuais": [1] * qtd,
        "media_atraso_minutos": [1.0] * qtd,
        coluna: valores,
    })


def test_graficos_04_05_06_mostram_todas_as_companhias_em_ordem_decrescente():
    # 12 companhias com taxas fora de ordem: nenhum Top 10 nesses gráficos.
    valores = [5.0, 1.0, 9.0, 3.0, 7.0, 2.0, 8.0, 4.0, 6.0, 0.5, 11.0, 10.0]
    casos = [
        (painel.grafico_04_companhias_atrasos, "taxa_atrasos_percentual"),
        (painel.grafico_05_companhias_cancelamentos, "taxa_cancelamentos_percentual"),
        (painel.grafico_06_pontualidade, "taxa_pontualidade_percentual"),
    ]
    for funcao, coluna in casos:
        fig = funcao(_companhias(coluna, valores))
        assert len(_y(fig)) == 12
        assert _x(fig) == sorted(valores, reverse=True)
        assert _y(fig)[0] == "Companhia 10"
        assert fig.data[0].orientation == "h"


def _rotas(coluna, valores):
    qtd = len(valores)
    return pd.DataFrame({
        "codigo_origem": [f"O{i:02d}" for i in range(qtd)],
        "aeroporto_origem": ["Origem"] * qtd,
        "cidade_origem": ["Cidade O"] * qtd,
        "codigo_destino": [f"D{i:02d}" for i in range(qtd)],
        "aeroporto_destino": ["Destino"] * qtd,
        "cidade_destino": ["Cidade D"] * qtd,
        "total_voos": [200] * qtd,
        "voos_atrasados": [10] * qtd,
        "voos_cancelados": [5] * qtd,
        "taxa_atrasos_percentual": [1.0] * qtd,
        "taxa_cancelamentos_percentual": [1.0] * qtd,
    }).assign(**{coluna: valores})


def test_grafico_07_top_10_rotas_com_rotulo_origem_seta_destino():
    fig = painel.grafico_07_rotas_atrasos(_rotas("taxa_atrasos_percentual", [float(i) for i in range(12)]))
    assert _y(fig) == [f"O{i:02d} → D{i:02d}" for i in range(11, 1, -1)]


def test_grafico_08_top_10_rotas_por_voos_cancelados():
    fig = painel.grafico_08_rotas_cancelamentos(_rotas("voos_cancelados", [3, 50, 7, 1, 9, 2, 4, 8, 6, 5, 10, 0]))
    assert _x(fig) == [50, 10, 9, 8, 7, 6, 5, 4, 3, 2]
    assert _y(fig)[0] == "O01 → D01"


def test_grafico_12_top_10_estados_por_total_de_voos():
    estados = [f"E{i:02d}" for i in range(12)]
    df = pd.DataFrame({"estado": estados, "total_voos": [10 * i for i in range(12)],
                       "pct_atrasos": [1.0] * 12, "pct_cancelamentos": [1.0] * 12})
    fig = painel.grafico_12_estados(df.iloc[::-1])
    assert _y(fig) == [f"E{i:02d}" for i in range(11, 1, -1)]
    assert _x(fig) == [10 * i for i in range(11, 1, -1)]


# ====================================================================== gráficos 09 e 10


def test_grafico_09_ordena_as_faixas_cronologicamente():
    faixas = ["23:00 - 23:59", "06:00 - 06:59", "00:01 - 05:59", "12:00 - 12:59", "07:00 - 07:59"]
    df = pd.DataFrame({"faixa_horario_partida": faixas, "total_voos": [1] * 5,
                       "voos_atrasados": [1] * 5, "taxa_atrasos_percentual": [5.0, 1.0, 9.0, 3.0, 2.0],
                       "media_atraso_minutos": [1.0] * 5})
    fig = painel.grafico_09_horarios(df)
    ordem = ["00:01 - 05:59", "06:00 - 06:59", "07:00 - 07:59", "12:00 - 12:59", "23:00 - 23:59"]
    assert _x(fig) == ordem
    assert list(fig.layout.xaxis.categoryarray) == ordem
    assert _y(fig) == [9.0, 1.0, 2.0, 3.0, 5.0]


def _dias(ordem):
    nomes = {1: "Domingo", 2: "Segunda-feira", 3: "Terca-feira", 4: "Quarta-feira",
             5: "Quinta-feira", 6: "Sexta-feira", 7: "Sabado"}
    return pd.DataFrame({
        "dia_semana": ordem,
        "nome_dia_semana": [nomes[d] for d in ordem],
        "total_voos": [1] * len(ordem),
        "voos_atrasados": [1] * len(ordem),
        "taxa_atrasos_percentual": [float(d) for d in ordem],
        "media_atraso_minutos": [1.0] * len(ordem),
    })


def test_grafico_10_ordena_os_dias_pelo_campo_dia_semana():
    # Entrada na ordem do Mart (por taxa decrescente, aqui invertida).
    fig = painel.grafico_10_dias_semana(_dias([7, 3, 5, 1, 6, 2, 4]))
    assert _y(fig) == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]


def test_grafico_10_exibe_os_nomes_dos_dias_com_acentuacao_correta():
    fig = painel.grafico_10_dias_semana(_dias([7, 6, 5, 4, 3, 2, 1]))
    assert _x(fig) == ["Domingo", "Segunda-feira", "Terça-feira", "Quarta-feira",
                       "Quinta-feira", "Sexta-feira", "Sábado"]


def test_grafico_10_acento_so_no_rotulo_e_nome_nao_previsto_e_mantido():
    df = _dias([3, 7])
    df.loc[len(df)] = [8, "Feriado", 1, 1, 8.0, 1.0]
    copia = df.copy()
    fig = painel.grafico_10_dias_semana(df)
    assert _x(fig) == ["Terça-feira", "Sábado", "Feriado"]
    # O DataFrame do Mart continua com os nomes originais, sem acento.
    assert df.equals(copia)
    assert list(df["nome_dia_semana"]) == ["Terca-feira", "Sabado", "Feriado"]


# ====================================================================== identidade e arquitetura


def _todas_as_figuras():
    dias = _dias([1, 2])
    horarios = pd.DataFrame({"faixa_horario_partida": ["06:00 - 06:59"], "total_voos": [1],
                             "voos_atrasados": [1], "taxa_atrasos_percentual": [1.0],
                             "media_atraso_minutos": [1.0]})
    estados = pd.DataFrame({"estado": ["TX"], "total_voos": [1], "pct_atrasos": [1.0],
                            "pct_cancelamentos": [1.0]})
    entradas = {
        "aeroportos_taxa_atrasos": _aeroportos(3),
        "aeroportos_taxa_cancelamentos": _aeroportos(3, "taxa_cancelamentos_percentual", "voos_cancelados"),
        "aeroportos_tempo_medio_atraso": _aeroportos(3, "tempo_medio_atraso_minutos"),
        "companhias_taxa_atrasos": _companhias("taxa_atrasos_percentual", [1.0, 2.0]),
        "companhias_taxa_cancelamentos": _companhias("taxa_cancelamentos_percentual", [1.0, 2.0]),
        "companhias_comparativo_pontualidade": _companhias("taxa_pontualidade_percentual", [1.0, 2.0]),
        "rotas_taxa_atrasos": _rotas("taxa_atrasos_percentual", [1.0, 2.0]),
        "rotas_quantidade_cancelamentos": _rotas("voos_cancelados", [1, 2]),
        "horarios_taxa_atrasos": horarios,
        "dias_semana_taxa_atrasos": dias,
        "operacao_por_estado": estados,
    }
    return {nome: painel.GRAFICOS[nome](df) for nome, df in entradas.items()}


def test_cada_funcao_de_grafico_devolve_figura_plotly_de_barras():
    figuras = _todas_as_figuras()
    assert len(figuras) == 11
    for fig in figuras.values():
        assert isinstance(fig, go.Figure)
        assert [t.type for t in fig.data] == ["bar"]


def test_todas_as_barras_usam_a_cor_unica_da_marca():
    for fig in _todas_as_figuras().values():
        assert fig.data[0].marker.color == "#1f7a68"


def test_graficos_usam_separadores_brasileiros():
    for fig in _todas_as_figuras().values():
        assert fig.layout.separators == ",."


def test_titulos_dos_graficos_seguem_a_numeracao_da_spec():
    numeros = [fig.layout.title.text[:2] for fig in _todas_as_figuras().values()]
    assert numeros == ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "12"]


def test_painel_nao_importa_streamlit():
    resultado = subprocess.run(
        [sys.executable, "-c", "import sys; from dashboard import painel; print('streamlit' in sys.modules)"],
        cwd=RAIZ, env={**os.environ, "PYTHONPATH": str(RAIZ)}, capture_output=True, text=True, check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout.strip() == "False"

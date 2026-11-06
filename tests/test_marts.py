"""Testes de pipeline/marts.py e das regras de negócio de sql/marts/*.sql.

Parte 1 — executor: SQLs inventados em tmp_path (PASTA_SQL redirecionada).
Parte 2 — regras dos 12 SQLs reais do projeto, executados contra tabelas
REFINED inventadas em um DuckDB temporário. Os resultados esperados são
calculados à mão a partir das linhas inventadas de cada teste.
aviation.duckdb nunca é aberto.
"""

import contextlib
import io
from pathlib import Path

import duckdb

from pipeline import db, marts

PASTA_SQL_REAL = Path(marts.__file__).resolve().parent.parent / "sql" / "marts"


# ====================================================================== apoio


def _banco(tmp_path, monkeypatch):
    caminho = tmp_path / "teste.duckdb"
    monkeypatch.setattr(db, "CAMINHO_BANCO", caminho)
    return caminho


def voo(origem="AAA", destino="BBB", companhia="AA", cancelado=False, atraso=0,
        flag=0, faixa="0600-0659", dia=1, n=1):
    """n voos iguais: (origem, destino, companhia, cancelado, atraso, flag 15min, faixa, dia)."""
    return [(origem, destino, companhia, cancelado, atraso, flag, faixa, dia)] * n


AEROPORTOS = [
    # código, nome, cidade, estado
    ("AAA", "Alfa", "Alfa City", "TX"),
    ("BBB", "Bravo", "Bravo City", "TX"),
    ("CCC", "Charlie", "Charlie City", "CA"),
    ("DDD", "Delta", "Delta City", "NY"),
]
COMPANHIAS = [("AA", "Alfa Air"), ("BB", "Bravo Air"), ("CC", "Charlie Air")]


def _criar_refined(caminho, voos, aeroportos=AEROPORTOS, companhias=COMPANHIAS, omitir=()):
    con = duckdb.connect(str(caminho))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS refined")
        definicoes = {
            "voos_2025": "origem VARCHAR, destino VARCHAR, codigo_companhia VARCHAR, "
            "cancelado BOOLEAN, atraso_partida DECIMAL(10,2), atraso_partida_15min INTEGER, "
            "faixa_horario_partida VARCHAR, dia_semana INTEGER",
            "aeroportos": "codigo_iata VARCHAR, nome_aeroporto VARCHAR, cidade VARCHAR, estado VARCHAR",
            "companhias_aereas": "codigo_companhia VARCHAR, companhia_aerea VARCHAR",
            "estatisticas_diarias_aeroportos": "data_voo DATE, aeroporto VARCHAR",
        }
        linhas = {"voos_2025": voos, "aeroportos": aeroportos, "companhias_aereas": companhias,
                  "estatisticas_diarias_aeroportos": []}
        for tabela, definicao in definicoes.items():
            if tabela in omitir:
                continue
            con.execute(f"CREATE OR REPLACE TABLE refined.{tabela} ({definicao})")
            if linhas[tabela]:
                marcadores = ", ".join("?" * len(linhas[tabela][0]))
                con.executemany(f"INSERT INTO refined.{tabela} VALUES ({marcadores})", linhas[tabela])
    finally:
        con.close()


def _mart(caminho, arquivo):
    """Executa um SQL real de sql/marts/ e devolve as linhas como dicionários."""
    sql = marts._consulta(PASTA_SQL_REAL / arquivo)
    con = duckdb.connect(str(caminho), read_only=True)
    try:
        cursor = con.execute(sql)
        nomes = [d[0] for d in cursor.description]
        return [dict(zip(nomes, linha)) for linha in cursor.fetchall()]
    finally:
        con.close()


def _pasta_sql(tmp_path, monkeypatch, arquivos):
    pasta = tmp_path / "sql_marts"
    pasta.mkdir(exist_ok=True)
    for nome, conteudo in arquivos.items():
        (pasta / nome).write_text(conteudo, encoding="utf-8")
    monkeypatch.setattr(marts, "PASTA_SQL", pasta)
    return pasta


def _executar():
    saida = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    codigo = 0
    with contextlib.redirect_stdout(saida):
        try:
            marts.main()
        except SystemExit as fim:
            codigo = fim.code
    saida.flush()
    return codigo, saida.buffer.getvalue().decode("utf-8")


def _consultar(caminho, sql):
    con = duckdb.connect(str(caminho), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _tabelas_marts(caminho):
    return [t for (t,) in _consultar(
        caminho,
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'marts' ORDER BY table_name",
    )]


# ====================================================================== executor


def test_arquivo_00_teste_cria_marts_teste_com_uma_linha(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    _criar_refined(caminho, voo())
    _pasta_sql(tmp_path, monkeypatch, {"00_teste.sql": "SELECT 1 AS x"})
    codigo, texto = _executar()
    assert codigo == 0
    assert _consultar(caminho, "SELECT x FROM marts.teste") == [(1,)]
    assert "✓ marts.teste" in texto and "1 linhas" in texto


def test_arquivo_removido_faz_a_tabela_desaparecer_na_proxima_execucao(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    _criar_refined(caminho, voo())
    pasta = _pasta_sql(tmp_path, monkeypatch,
                       {"00_teste.sql": "SELECT 1 AS x", "01_outro.sql": "SELECT 2 AS y"})
    _executar()
    (pasta / "00_teste.sql").unlink()
    codigo, _ = _executar()
    assert codigo == 0
    assert _tabelas_marts(caminho) == ["outro"]


def test_nome_da_tabela_e_o_arquivo_sem_prefixo_e_sem_extensao(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    _criar_refined(caminho, voo())
    _pasta_sql(tmp_path, monkeypatch, {"10_dias_semana_taxa_atrasos.sql": "SELECT 1 AS x"})
    _executar()
    assert _tabelas_marts(caminho) == ["dias_semana_taxa_atrasos"]


def test_arquivos_sao_executados_em_ordem_alfabetica(tmp_path, monkeypatch):
    # Criados fora de ordem; a saída deve seguir 01, 02, 10.
    caminho = _banco(tmp_path, monkeypatch)
    _criar_refined(caminho, voo())
    _pasta_sql(tmp_path, monkeypatch, {"10_c.sql": "SELECT 1 AS x",
                                       "01_a.sql": "SELECT 1 AS x",
                                       "02_b.sql": "SELECT 1 AS x"})
    _, texto = _executar()
    linhas = [x.split()[1] for x in texto.splitlines() if x.startswith("✓")]
    assert linhas == ["marts.a", "marts.b", "marts.c"]


def test_sql_com_comentarios_cte_espacos_e_ponto_e_virgula_final_e_aceito(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    _criar_refined(caminho, voo(n=3))
    sql = "\n\n-- comentário inicial\nWITH base AS (SELECT * FROM refined.voos_2025)\n" \
          "SELECT COUNT(*) AS total FROM base;\n\n   "
    _pasta_sql(tmp_path, monkeypatch, {"01_contagem.sql": sql})
    codigo, _ = _executar()
    assert codigo == 0
    assert _consultar(caminho, "SELECT total FROM marts.contagem") == [(3,)]


def test_consulta_remove_somente_espacos_e_um_ponto_e_virgula_final(tmp_path):
    arquivo = tmp_path / "01_x.sql"
    arquivo.write_text("  \n-- nota;\nSELECT ';' AS x;\n  ", encoding="utf-8")
    assert marts._consulta(arquivo) == "-- nota;\nSELECT ';' AS x"


def test_saida_mostra_total_de_marts_e_linhas_com_milhar_em_ponto(tmp_path, monkeypatch):
    # 1.000 + 500 linhas geradas por range.
    caminho = _banco(tmp_path, monkeypatch)
    _criar_refined(caminho, voo())
    _pasta_sql(tmp_path, monkeypatch, {"01_mil.sql": "SELECT * FROM range(1000)",
                                       "02_quinhentos.sql": "SELECT * FROM range(500)"})
    _, texto = _executar()
    assert "1.000 linhas" in texto
    assert texto.rstrip().splitlines()[-1] == "TOTAL: 2 marts | 1.500 linhas"


def test_erro_de_sintaxe_interrompe_mostra_arquivo_e_mantem_o_schema(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    _criar_refined(caminho, voo())
    pasta = _pasta_sql(tmp_path, monkeypatch, {"01_valido.sql": "SELECT 1 AS x"})
    _executar()

    # Nova execução: um arquivo válido novo antes do arquivo com erro.
    (pasta / "00_novo.sql").write_text("SELECT 1 AS n", encoding="utf-8")
    (pasta / "02_quebrado.sql").write_text("SELEC 1", encoding="utf-8")
    codigo, texto = _executar()

    assert codigo == 1
    assert "Falha no arquivo: 02_quebrado.sql" in texto
    assert "syntax error" in texto.lower()
    assert "ROLLBACK" in texto
    assert _tabelas_marts(caminho) == ["valido"]


def test_erro_em_um_arquivo_impede_a_execucao_dos_seguintes(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    _criar_refined(caminho, voo())
    _pasta_sql(tmp_path, monkeypatch, {"01_erro.sql": "SELECT * FROM refined.inexistente",
                                       "02_depois.sql": "SELECT 1 AS x"})
    codigo, texto = _executar()
    assert codigo == 1
    assert "01_erro.sql" in texto
    assert "marts.depois" not in texto


def test_arquivo_sem_prefixo_interrompe_antes_de_qualquer_sql(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    _pasta_sql(tmp_path, monkeypatch, {"01_ok.sql": "SELECT 1 AS x", "teste.sql": "SELECT 1 AS x"})
    codigo, texto = _executar()
    assert codigo == 1
    assert "teste.sql" in texto
    assert "01_ok.sql" not in texto
    # A validação ocorre antes de abrir o banco: nenhum banco foi criado.
    assert not caminho.exists()


def test_dois_arquivos_com_o_mesmo_nome_de_tabela_interrompem_antes_de_qualquer_sql(
    tmp_path, monkeypatch
):
    caminho = _banco(tmp_path, monkeypatch)
    _pasta_sql(tmp_path, monkeypatch, {"01_kpis.sql": "SELECT 1 AS x", "02_kpis.sql": "SELECT 2 AS x"})
    codigo, texto = _executar()
    assert codigo == 1
    assert "marts.kpis: 01_kpis.sql, 02_kpis.sql" in texto
    assert not caminho.exists()


def test_mart_com_zero_linhas_interrompe_e_provoca_rollback(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    _criar_refined(caminho, voo())
    pasta = _pasta_sql(tmp_path, monkeypatch, {"01_valido.sql": "SELECT 1 AS x"})
    _executar()
    (pasta / "02_vazio.sql").write_text("SELECT 1 AS x WHERE FALSE", encoding="utf-8")
    codigo, texto = _executar()
    assert codigo == 1
    assert "02_vazio.sql" in texto
    assert "Mart criado sem registros." in texto
    assert _tabelas_marts(caminho) == ["valido"]


def test_tabela_refined_ausente_informa_quais_faltam_e_orienta_a_transformacao(
    tmp_path, monkeypatch
):
    caminho = _banco(tmp_path, monkeypatch)
    _criar_refined(caminho, voo(), omitir=("aeroportos", "voos_2025"))
    _pasta_sql(tmp_path, monkeypatch, {"01_x.sql": "SELECT 1 AS x"})
    codigo, texto = _executar()
    assert codigo == 1
    assert "refined.aeroportos" in texto and "refined.voos_2025" in texto
    assert "refined.companhias_aereas" not in texto
    assert "uv run python -m pipeline.transformacao" in texto
    # Nenhuma SQL executada: o schema marts não foi criado.
    assert _tabelas_marts(caminho) == []


def test_pasta_sem_sql_encerra_sem_alterar_o_schema_existente(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    _criar_refined(caminho, voo())
    pasta = _pasta_sql(tmp_path, monkeypatch, {"01_valido.sql": "SELECT 1 AS x"})
    _executar()
    (pasta / "01_valido.sql").unlink()
    codigo, texto = _executar()
    assert codigo == 1
    assert "Nenhum arquivo .sql encontrado" in texto
    assert _tabelas_marts(caminho) == ["valido"]


def test_executor_nao_escreve_em_refined(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    _criar_refined(caminho, voo(n=2))
    antes = _consultar(caminho, "SELECT * FROM refined.voos_2025")
    _pasta_sql(tmp_path, monkeypatch, {"01_x.sql": "SELECT 1 AS x"})
    _executar()
    assert _consultar(caminho, "SELECT * FROM refined.voos_2025") == antes
    assert _consultar(
        caminho, "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'refined'"
    ) == [(4,)]


def _voos_que_preenchem_todos_os_marts():
    # 100 voos AAA->BBB pela AA atrasados (30 min) + 1 cancelado: atende aos
    # mínimos de 100 voos dos Marts 03, 06, 07 e 08, e nenhum Mart fica vazio.
    return voo(atraso=30, flag=1, n=100) + voo(cancelado=True, atraso=None, flag=None)


def test_os_arquivos_reais_geram_uma_tabela_por_arquivo_sem_prefixo(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    _criar_refined(caminho, _voos_que_preenchem_todos_os_marts())
    codigo, texto = _executar()
    esperados = sorted(marts.PADRAO_ARQUIVO.match(a.name).group(1)
                       for a in PASTA_SQL_REAL.glob("*.sql"))
    assert codigo == 0
    assert len(esperados) == 12
    assert _tabelas_marts(caminho) == esperados
    assert "TOTAL: 12 marts" in texto


def test_duas_execucoes_sem_alteracoes_produzem_mesma_saida_e_tabelas(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    _criar_refined(caminho, _voos_que_preenchem_todos_os_marts())
    _, primeira = _executar()
    conteudo_1 = _consultar(caminho, "SELECT * FROM marts.kpis")
    _, segunda = _executar()
    conteudo_2 = _consultar(caminho, "SELECT * FROM marts.kpis")
    assert primeira == segunda
    assert conteudo_1 == conteudo_2


# ====================================================================== regras dos SQLs


# ---- 01 aeroportos_taxa_atrasos


def test_mart01_cancelado_fica_fora_do_denominador_da_taxa_de_atrasos(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    voos = (
        voo(atraso=20, flag=1)                         # atrasado
        + voo(atraso=0, flag=0)                        # pontual
        + voo(atraso=14, flag=0)                       # 14 min: não é atraso
        + voo(atraso=None, flag=None)                  # sem classificação: conta no denominador
        + voo(cancelado=True, atraso=50, flag=1, n=3)  # cancelados: fora do cálculo
    )
    _criar_refined(caminho, voos)
    (linha,) = _mart(caminho, "01_aeroportos_taxa_atrasos.sql")
    # 1 atrasado / 4 não cancelados = 25,00%
    assert (linha["codigo_iata"], linha["total_voos"], linha["voos_atrasados"]) == ("AAA", 4, 1)
    assert linha["taxa_atrasos_percentual"] == 25.0


def test_mart01_voo_com_atraso_de_15_minutos_e_classificado_como_atrasado(tmp_path, monkeypatch):
    # O SQL usa a flag atraso_partida_15min = 1 (atraso de 15 min ou mais).
    caminho = _banco(tmp_path, monkeypatch)
    _criar_refined(caminho, voo(atraso=15, flag=1) + voo(atraso=14, flag=0) + voo(atraso=1, flag=0))
    (linha,) = _mart(caminho, "01_aeroportos_taxa_atrasos.sql")
    assert linha["voos_atrasados"] == 1
    assert linha["taxa_atrasos_percentual"] == 33.33  # 1/3 arredondado em 2 casas


def test_mart01_agrupa_por_aeroporto_de_origem_e_ordena_pela_taxa(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    voos = (
        voo(origem="AAA", flag=1) + voo(origem="AAA", flag=0, n=3)  # 25%
        + voo(origem="CCC", flag=1, n=3) + voo(origem="CCC", flag=0)  # 75%
        + voo(origem="ZZZ", flag=1)  # origem fora de refined.aeroportos: INNER JOIN exclui
    )
    _criar_refined(caminho, voos)
    linhas = _mart(caminho, "01_aeroportos_taxa_atrasos.sql")
    assert [(x["codigo_iata"], x["taxa_atrasos_percentual"]) for x in linhas] == [
        ("CCC", 75.0), ("AAA", 25.0)
    ]
    assert linhas[0]["estado"] == "CA"


# ---- 02 aeroportos_taxa_cancelamentos


def test_mart02_denominador_inclui_os_voos_cancelados(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    _criar_refined(caminho, voo(cancelado=True) + voo(n=3))
    (linha,) = _mart(caminho, "02_aeroportos_taxa_cancelamentos.sql")
    # 1 cancelado / 4 voos = 25,00%
    assert (linha["total_voos"], linha["voos_cancelados"]) == (4, 1)
    assert linha["taxa_cancelamentos_percentual"] == 25.0


def test_mart02_ordena_pela_maior_taxa_de_cancelamentos(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    voos = (voo(origem="AAA", cancelado=True) + voo(origem="AAA", n=9)      # 10%
            + voo(origem="DDD", cancelado=True, n=2) + voo(origem="DDD", n=1))  # 66,67%
    _criar_refined(caminho, voos)
    linhas = _mart(caminho, "02_aeroportos_taxa_cancelamentos.sql")
    assert [(x["codigo_iata"], x["taxa_cancelamentos_percentual"]) for x in linhas] == [
        ("DDD", 66.67), ("AAA", 10.0)
    ]


# ---- 03 aeroportos_tempo_medio_atraso


def test_mart03_media_considera_somente_atrasados_nao_cancelados(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    voos = (
        voo(atraso=20, flag=1, n=50) + voo(atraso=40, flag=1, n=50)  # 100 atrasados, média 30
        + voo(atraso=10, flag=0, n=30)                               # pontuais: fora da média
        + voo(cancelado=True, atraso=900, flag=1, n=5)               # cancelados: fora
        + voo(atraso=None, flag=1, n=5)                              # atraso nulo: fora
    )
    _criar_refined(caminho, voos)
    (linha,) = _mart(caminho, "03_aeroportos_tempo_medio_atraso.sql")
    assert linha["total_voos"] == 100
    assert linha["voos_atrasados"] == 100
    assert linha["tempo_medio_atraso_minutos"] == 30.0


def test_mart03_exige_pelo_menos_100_voos_atrasados_por_aeroporto(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    voos = (
        voo(origem="AAA", atraso=20, flag=1, n=100)       # 100 atrasados: entra
        + voo(origem="CCC", atraso=60, flag=1, n=99)      # 99 atrasados: fica fora
        + voo(origem="CCC", atraso=None, flag=1, n=5)     # sem minutos: não completam 100
        + voo(origem="CCC", atraso=5, flag=0, n=50)       # pontuais: não completam 100
    )
    _criar_refined(caminho, voos)
    linhas = _mart(caminho, "03_aeroportos_tempo_medio_atraso.sql")
    assert [x["codigo_iata"] for x in linhas] == ["AAA"]


def test_mart03_ordena_pelo_maior_tempo_medio(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    voos = voo(origem="AAA", atraso=20, flag=1, n=100) + voo(origem="CCC", atraso=45, flag=1, n=100)
    _criar_refined(caminho, voos)
    linhas = _mart(caminho, "03_aeroportos_tempo_medio_atraso.sql")
    assert [(x["codigo_iata"], x["tempo_medio_atraso_minutos"]) for x in linhas] == [
        ("CCC", 45.0), ("AAA", 20.0)
    ]


# ---- 04 companhias_taxa_atrasos


def test_mart04_agrupa_por_companhia_e_exclui_cancelados(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    voos = (
        voo(companhia="AA", flag=1) + voo(companhia="AA", flag=0)    # AA: 50%
        + voo(companhia="AA", cancelado=True, flag=1, n=4)           # cancelados: fora
        + voo(companhia="BB", flag=1, n=4) + voo(companhia="BB", flag=0)  # BB: 80%
        + voo(companhia="XX", flag=1)                                # sem cadastro: fora
    )
    _criar_refined(caminho, voos)
    linhas = _mart(caminho, "04_companhias_taxa_atrasos.sql")
    assert [(x["codigo_companhia"], x["companhia_aerea"], x["total_voos"],
             x["voos_atrasados"], x["taxa_atrasos_percentual"]) for x in linhas] == [
        ("BB", "Bravo Air", 5, 4, 80.0),
        ("AA", "Alfa Air", 2, 1, 50.0),
    ]


# ---- 05 companhias_taxa_cancelamentos


def test_mart05_denominador_inclui_cancelados_e_ordena_pela_taxa(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    voos = (
        voo(companhia="AA", cancelado=True) + voo(companhia="AA", n=7)       # 1/8 = 12,5%
        + voo(companhia="BB", cancelado=True, n=3) + voo(companhia="BB", n=3)  # 3/6 = 50%
    )
    _criar_refined(caminho, voos)
    linhas = _mart(caminho, "05_companhias_taxa_cancelamentos.sql")
    assert [(x["codigo_companhia"], x["total_voos"], x["voos_cancelados"],
             x["taxa_cancelamentos_percentual"]) for x in linhas] == [
        ("BB", 6, 3, 50.0),
        ("AA", 8, 1, 12.5),
    ]


# ---- 06 companhias_comparativo_pontualidade


def test_mart06_pontualidade_usa_voos_elegiveis_como_denominador(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    voos = (
        voo(companhia="AA", atraso=0, flag=0, n=80)         # pontuais
        + voo(companhia="AA", atraso=30, flag=1, n=20)      # atrasados
        + voo(companhia="AA", atraso=None, flag=None, n=10)  # sem classificação: fora
        + voo(companhia="AA", cancelado=True, flag=0, n=10)  # cancelados: fora
    )
    _criar_refined(caminho, voos)
    (linha,) = _mart(caminho, "06_companhias_comparativo_pontualidade.sql")
    # 80 / 100 = 80%; média = (80*0 + 20*30) / 100 = 6
    assert (linha["total_voos"], linha["voos_pontuais"], linha["voos_atrasados"]) == (100, 80, 20)
    assert linha["taxa_pontualidade_percentual"] == 80.0
    assert linha["media_atraso_minutos"] == 6.0


def test_mart06_media_ignora_atraso_nulo_entre_os_elegiveis(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    # 100 elegíveis; 2 com minutos nulos: média = (49*10 + 49*30) / 98 = 20
    voos = (voo(atraso=10, flag=0, n=49) + voo(atraso=None, flag=0)
            + voo(atraso=30, flag=1, n=49) + voo(atraso=None, flag=1))
    _criar_refined(caminho, voos)
    (linha,) = _mart(caminho, "06_companhias_comparativo_pontualidade.sql")
    assert linha["total_voos"] == 100
    assert linha["media_atraso_minutos"] == 20.0


def test_mart06_exige_pelo_menos_100_voos_elegiveis(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    voos = (
        voo(companhia="AA", flag=0, n=100)                          # 100 elegíveis: entra
        + voo(companhia="BB", flag=0, n=99)                         # 99 elegíveis: fora
        + voo(companhia="BB", flag=None, n=10)                      # sem classificação
        + voo(companhia="BB", cancelado=True, flag=0, n=10)         # cancelados
    )
    _criar_refined(caminho, voos)
    linhas = _mart(caminho, "06_companhias_comparativo_pontualidade.sql")
    assert [x["codigo_companhia"] for x in linhas] == ["AA"]


# ---- 07 rotas_taxa_atrasos


def test_mart07_agrupa_por_rota_com_minimo_de_100_voos_nao_cancelados(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    voos = (
        voo(origem="AAA", destino="BBB", flag=1, n=25)
        + voo(origem="AAA", destino="BBB", flag=0, n=75)            # 25/100 = 25%
        + voo(origem="BBB", destino="AAA", flag=1, n=99)            # 99 não cancelados: fora
        + voo(origem="BBB", destino="AAA", cancelado=True, n=10)    # cancelados não completam
    )
    _criar_refined(caminho, voos)
    linhas = _mart(caminho, "07_rotas_taxa_atrasos.sql")
    assert len(linhas) == 1
    rota = linhas[0]
    assert (rota["codigo_origem"], rota["codigo_destino"]) == ("AAA", "BBB")
    assert (rota["cidade_origem"], rota["aeroporto_destino"]) == ("Alfa City", "Bravo")
    assert (rota["total_voos"], rota["voos_atrasados"], rota["taxa_atrasos_percentual"]) == (
        100, 25, 25.0
    )


def test_mart07_rota_e_direcional(tmp_path, monkeypatch):
    # AAA->CCC e CCC->AAA são rotas diferentes.
    caminho = _banco(tmp_path, monkeypatch)
    voos = (voo(origem="AAA", destino="CCC", flag=1, n=10) + voo(origem="AAA", destino="CCC", n=90)
            + voo(origem="CCC", destino="AAA", flag=1, n=50) + voo(origem="CCC", destino="AAA", n=50))
    _criar_refined(caminho, voos)
    linhas = _mart(caminho, "07_rotas_taxa_atrasos.sql")
    assert [(x["codigo_origem"], x["codigo_destino"], x["taxa_atrasos_percentual"]) for x in linhas] == [
        ("CCC", "AAA", 50.0), ("AAA", "CCC", 10.0)
    ]


# ---- 08 rotas_quantidade_cancelamentos


def test_mart08_ordena_por_cancelamentos_e_desempata_pela_taxa(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    voos = (
        voo(origem="AAA", destino="BBB", cancelado=True, n=10) + voo(origem="AAA", destino="BBB", n=90)    # 10 / 10%
        + voo(origem="AAA", destino="CCC", cancelado=True, n=10) + voo(origem="AAA", destino="CCC", n=190)  # 10 / 5%
        + voo(origem="CCC", destino="DDD", cancelado=True, n=20) + voo(origem="CCC", destino="DDD", n=80)   # 20 / 20%
    )
    _criar_refined(caminho, voos)
    linhas = _mart(caminho, "08_rotas_quantidade_cancelamentos.sql")
    assert [(x["codigo_origem"], x["codigo_destino"], x["voos_cancelados"],
             x["taxa_cancelamentos_percentual"]) for x in linhas] == [
        ("CCC", "DDD", 20, 20.0),
        ("AAA", "BBB", 10, 10.0),
        ("AAA", "CCC", 10, 5.0),
    ]


def test_mart08_cancelados_contam_para_o_minimo_de_100_voos(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    voos = (
        voo(origem="BBB", destino="AAA", cancelado=True, n=10) + voo(origem="BBB", destino="AAA", n=90)  # 100: entra
        + voo(origem="DDD", destino="AAA", cancelado=True, n=9) + voo(origem="DDD", destino="AAA", n=90)  # 99: fora
    )
    _criar_refined(caminho, voos)
    linhas = _mart(caminho, "08_rotas_quantidade_cancelamentos.sql")
    assert [(x["codigo_origem"], x["total_voos"]) for x in linhas] == [("BBB", 100)]


# ---- 09 horarios_taxa_atrasos


def test_mart09_formata_a_faixa_e_calcula_taxa_e_media_por_faixa(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    voos = (
        voo(faixa="0600-0659", atraso=30, flag=1) + voo(faixa="0600-0659", atraso=0, flag=0)  # 50%, média 15
        + voo(faixa="0001-0559", atraso=20, flag=1, n=3) + voo(faixa="0001-0559", atraso=4, flag=0)  # 75%, média 16
        + voo(faixa="0600-0659", cancelado=True, atraso=500, flag=1)   # cancelado: fora
        + voo(faixa=None, atraso=90, flag=1)                           # faixa nula: fora
    )
    _criar_refined(caminho, voos)
    linhas = _mart(caminho, "09_horarios_taxa_atrasos.sql")
    assert [(x["faixa_horario_partida"], x["total_voos"], x["voos_atrasados"],
             x["taxa_atrasos_percentual"], x["media_atraso_minutos"]) for x in linhas] == [
        ("00:01 - 05:59", 4, 3, 75.0, 16.0),
        ("06:00 - 06:59", 2, 1, 50.0, 15.0),
    ]


def test_mart09_voo_sem_classificacao_conta_no_denominador(tmp_path, monkeypatch):
    # O SQL 09 filtra apenas cancelado e faixa nula; flag nula permanece no total.
    caminho = _banco(tmp_path, monkeypatch)
    _criar_refined(caminho, voo(flag=1) + voo(flag=None))
    (linha,) = _mart(caminho, "09_horarios_taxa_atrasos.sql")
    assert (linha["total_voos"], linha["taxa_atrasos_percentual"]) == (2, 50.0)


# ---- 10 dias_semana_taxa_atrasos


def test_mart10_mapeia_numero_do_dia_para_o_nome(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    voos = []
    for dia in range(1, 8):
        voos += voo(dia=dia, flag=1, n=dia) + voo(dia=dia, flag=0, n=8 - dia)  # taxa cresce com o dia
    _criar_refined(caminho, voos)
    linhas = _mart(caminho, "10_dias_semana_taxa_atrasos.sql")
    assert [(x["dia_semana"], x["nome_dia_semana"]) for x in linhas] == [
        (7, "Sabado"), (6, "Sexta-feira"), (5, "Quinta-feira"), (4, "Quarta-feira"),
        (3, "Terca-feira"), (2, "Segunda-feira"), (1, "Domingo"),
    ]


def test_mart10_denominador_exclui_cancelados_e_sem_classificacao(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    voos = (
        voo(dia=2, atraso=40, flag=1) + voo(dia=2, atraso=0, flag=0, n=3)  # 1/4 = 25%, média 10
        + voo(dia=2, atraso=None, flag=None, n=5)                           # sem classificação: fora
        + voo(dia=2, cancelado=True, atraso=100, flag=1, n=5)               # cancelados: fora
    )
    _criar_refined(caminho, voos)
    (linha,) = _mart(caminho, "10_dias_semana_taxa_atrasos.sql")
    assert (linha["total_voos"], linha["voos_atrasados"]) == (4, 1)
    assert (linha["taxa_atrasos_percentual"], linha["media_atraso_minutos"]) == (25.0, 10.0)


# ---- 11 kpis


def test_mart11_indicadores_consolidados_em_uma_unica_linha(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    voos = (
        voo(atraso=20, flag=1) + voo(atraso=40, flag=1)    # 2 atrasados, média 30
        + voo(atraso=0, flag=0, n=6)                       # 6 pontuais
        + voo(atraso=None, flag=None, n=2)                 # 2 sem classificação
        + voo(cancelado=True, atraso=300, flag=1, n=2)     # 2 cancelados
    )
    _criar_refined(caminho, voos)
    linhas = _mart(caminho, "11_kpis.sql")
    assert len(linhas) == 1
    kpis = linhas[0]
    assert kpis["total_voos"] == 12
    assert kpis["pct_atrasos"] == 25.0           # 2 / (12 - 2 cancelados - 2 sem classificação)
    assert kpis["pct_cancelamentos"] == 16.67    # 2 / 12
    assert kpis["atraso_medio_minutos"] == 30.0  # só atrasados não cancelados
    assert kpis["total_companhias"] == 3         # cadastro de companhias, não os voos
    assert kpis["total_aeroportos"] == 4         # cadastro de aeroportos


def test_mart11_contagem_de_cadastros_e_distinta(tmp_path, monkeypatch):
    # Aeroporto AAA e companhia AA repetidos no cadastro contam uma vez.
    caminho = _banco(tmp_path, monkeypatch)
    _criar_refined(caminho, voo(),
                   aeroportos=AEROPORTOS + [("AAA", "Alfa 2", "X", "TX")],
                   companhias=COMPANHIAS + [("AA", "Alfa Air")])
    (kpis,) = _mart(caminho, "11_kpis.sql")
    assert (kpis["total_aeroportos"], kpis["total_companhias"]) == (4, 3)


# ---- 12 operacao_por_estado


def test_mart12_agrupa_pelo_estado_de_origem(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    voos = (
        voo(origem="AAA", destino="CCC", flag=1, n=2)              # TX
        + voo(origem="BBB", destino="DDD", flag=0, n=2)            # TX (outro aeroporto)
        + voo(origem="AAA", destino="CCC", cancelado=True, flag=None)  # TX, cancelado
        + voo(origem="CCC", destino="AAA", flag=0, n=2)            # CA
    )
    _criar_refined(caminho, voos)
    linhas = _mart(caminho, "12_operacao_por_estado.sql")
    # TX: 5 voos; atrasos 2/4 = 50%; cancelados 1/5 = 20%. CA: 2 voos; 0%; 0%.
    # NY só aparece como destino: não é contado.
    assert [(x["estado"], x["total_voos"], x["pct_atrasos"], x["pct_cancelamentos"])
            for x in linhas] == [("TX", 5, 50.0, 20.0), ("CA", 2, 0.0, 0.0)]


def test_mart12_origem_sem_cadastro_fica_com_estado_nulo(tmp_path, monkeypatch):
    # LEFT JOIN: voo de origem desconhecida é mantido, com estado NULL.
    caminho = _banco(tmp_path, monkeypatch)
    _criar_refined(caminho, voo(origem="AAA", n=2) + voo(origem="ZZZ"))
    linhas = _mart(caminho, "12_operacao_por_estado.sql")
    assert [(x["estado"], x["total_voos"]) for x in linhas] == [("TX", 2), (None, 1)]


def test_mart12_pct_atrasos_exclui_cancelados_e_sem_classificacao(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    voos = voo(flag=1) + voo(flag=0, n=2) + voo(flag=None, n=3) + voo(cancelado=True, flag=1)
    _criar_refined(caminho, voos)
    (linha,) = _mart(caminho, "12_operacao_por_estado.sql")
    # atrasos 1/3 = 33,33%; cancelados 1/7 = 14,29%
    assert (linha["total_voos"], linha["pct_atrasos"], linha["pct_cancelamentos"]) == (7, 33.33, 14.29)

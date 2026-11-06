"""Testes de pipeline/ingestao.py — seções 1 a 5 da SPEC.

Os quatro CSVs são inventados em tmp_path/Banco; PASTA_RAW e o caminho do
banco são redirecionados. Nenhum arquivo de Banco/ ou data_base/ é lido.
"""

import contextlib
import io

import duckdb

from pipeline import db, ingestao

# Conteúdo mínimo de cada arquivo. Cada CSV tem uma finalidade:
CSVS = {
    # 2 companhias; _source_file ausente -> a coluna deve ser acrescentada ao final.
    "airlines.csv": "airline_code,airline,_ingested_at\n"
    "AA,American,2025-06-01 10:00:00+00\n"
    "DL,Delta,2025-06-01 10:00:00+00\n",
    # 3 aeroportos; _source_file no meio com valor herdado (flights.parquet), que é
    # substituído; "NA" (Namíbia) e "NULL" são texto; campo vazio vira nulo.
    "airports.csv": "iata_code,_source_file,state,elevation_ft,_ingested_at\n"
    "AAA,flights.parquet,NA,0010,2025-06-01 10:00:00+00\n"
    "BBB,flights.parquet,NULL,,2025-06-01 10:00:00+00\n"
    "CCC,flights.parquet,nan,1.50,2025-06-01 10:00:00+00\n",
    # 1 linha de estatística diária.
    "daily_airport_stats.csv": "flight_date,airport,_ingested_at\n"
    "2025-01-01,AAA,2025-06-01 10:00:00+00\n",
    # 4 voos: duas linhas idênticas (não deduplicar), um de 2026 (sem filtro de ano)
    # e um com atraso em formato inválido "abc" (sem correção de valores).
    "flights_2025_sample.csv": "flight_date,origin,dep_delay,_source_file,_ingested_at\n"
    "2025-01-01,AAA,5,old.parquet,2025-06-01 10:00:00+00\n"
    "2025-01-01,AAA,5,old.parquet,2025-06-01 10:00:00+00\n"
    "2026-01-01,BBB,abc,old.parquet,2025-06-01 10:00:00+00\n"
    "2025-03-01,CCC,,old.parquet,2025-06-01 10:00:00+00\n",
}


def _preparar(tmp_path, monkeypatch, arquivos=CSVS):
    pasta = tmp_path / "Banco"
    pasta.mkdir()
    for nome, conteudo in arquivos.items():
        (pasta / nome).write_text(conteudo, encoding="utf-8")
    banco = tmp_path / "teste.duckdb"
    monkeypatch.setattr(ingestao, "PASTA_RAW", pasta)
    monkeypatch.setattr(db, "CAMINHO_BANCO", banco)
    return pasta, banco


def _executar():
    """Executa main() capturando stdout; devolve (código de saída, texto)."""
    saida = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    codigo = 0
    with contextlib.redirect_stdout(saida):
        try:
            ingestao.main()
        except SystemExit as fim:
            codigo = fim.code
    saida.flush()
    return codigo, saida.buffer.getvalue().decode("utf-8")


def _consultar(banco, sql):
    con = duckdb.connect(str(banco), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


# ------------------------------------------------------------------ escopo e nomes


def test_os_quatro_csvs_geram_as_quatro_tabelas_no_schema_raw(tmp_path, monkeypatch):
    _, banco = _preparar(tmp_path, monkeypatch)
    codigo, _ = _executar()
    tabelas = _consultar(
        banco,
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'raw' ORDER BY table_name",
    )
    assert codigo == 0
    assert tabelas == [
        ("airlines",),
        ("airports",),
        ("daily_airport_stats",),
        ("flights_2025",),
    ]


def test_ingestao_preserva_a_quantidade_de_linhas_de_cada_arquivo(tmp_path, monkeypatch):
    _, banco = _preparar(tmp_path, monkeypatch)
    _executar()
    contagens = {
        t: _consultar(banco, f"SELECT COUNT(*) FROM raw.{t}")[0][0]
        for t in ("airlines", "airports", "daily_airport_stats", "flights_2025")
    }
    assert contagens == {
        "airlines": 2,
        "airports": 3,
        "daily_airport_stats": 1,
        "flights_2025": 4,
    }


def test_saida_mostra_registros_por_tabela_e_total(tmp_path, monkeypatch):
    _preparar(tmp_path, monkeypatch)
    _, texto = _executar()
    assert "RAW.airlines" in texto and "| 2 registros" in texto
    assert "RAW.flights_2025" in texto and "| 4 registros" in texto
    # 2 + 3 + 1 + 4 = 10
    assert texto.rstrip().splitlines()[-1].startswith("TOTAL")
    assert texto.rstrip().endswith("| 10 registros")


# ------------------------------------------------------------------ preservação


def test_todas_as_colunas_sao_importadas_como_texto(tmp_path, monkeypatch):
    _, banco = _preparar(tmp_path, monkeypatch)
    _executar()
    tipos = _consultar(
        banco,
        "SELECT DISTINCT data_type FROM information_schema.columns WHERE table_schema = 'raw'",
    )
    assert tipos == [("VARCHAR",)]


def test_valores_nao_sao_convertidos_nem_corrigidos(tmp_path, monkeypatch):
    # "0010" e "1.50" mantêm zeros; "abc" continua como recebido.
    _, banco = _preparar(tmp_path, monkeypatch)
    _executar()
    altitudes = _consultar(banco, "SELECT elevation_ft FROM raw.airports ORDER BY iata_code")
    atrasos = _consultar(banco, "SELECT dep_delay FROM raw.flights_2025 ORDER BY flight_date")
    assert altitudes == [("0010",), (None,), ("1.50",)]
    assert atrasos == [("5",), ("5",), (None,), ("abc",)]


def test_linhas_identicas_nao_sao_deduplicadas(tmp_path, monkeypatch):
    _, banco = _preparar(tmp_path, monkeypatch)
    _executar()
    repetidas = _consultar(
        banco,
        "SELECT COUNT(*) FROM raw.flights_2025 WHERE flight_date = '2025-01-01' AND origin = 'AAA'",
    )
    assert repetidas == [(2,)]


def test_registros_de_2026_nao_sao_descartados(tmp_path, monkeypatch):
    _, banco = _preparar(tmp_path, monkeypatch)
    _executar()
    assert _consultar(
        banco, "SELECT COUNT(*) FROM raw.flights_2025 WHERE flight_date LIKE '2026%'"
    ) == [(1,)]


def test_campo_vazio_vira_nulo_e_textos_na_null_nan_permanecem_texto(
    tmp_path, monkeypatch
):
    _, banco = _preparar(tmp_path, monkeypatch)
    _executar()
    estados = _consultar(banco, "SELECT iata_code, state FROM raw.airports ORDER BY iata_code")
    vazio = _consultar(banco, "SELECT elevation_ft FROM raw.airports WHERE iata_code = 'BBB'")
    assert estados == [("AAA", "NA"), ("BBB", "NULL"), ("CCC", "nan")]
    assert vazio == [(None,)]


def test_source_file_recebe_o_nome_do_arquivo_lido_em_todas_as_linhas(
    tmp_path, monkeypatch
):
    _, banco = _preparar(tmp_path, monkeypatch)
    _executar()
    origens = {
        tabela: _consultar(banco, f"SELECT DISTINCT _source_file FROM raw.{tabela}")
        for tabela in ("airlines", "airports", "daily_airport_stats", "flights_2025")
    }
    assert origens == {
        "airlines": [("airlines.csv",)],
        "airports": [("airports.csv",)],
        "daily_airport_stats": [("daily_airport_stats.csv",)],
        "flights_2025": [("flights_2025_sample.csv",)],
    }


def test_source_file_existente_mantem_nome_e_posicao_da_coluna(tmp_path, monkeypatch):
    # Em airports.csv a coluna _source_file é a segunda.
    _, banco = _preparar(tmp_path, monkeypatch)
    _executar()
    colunas = _consultar(
        banco,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'raw' AND table_name = 'airports' ORDER BY ordinal_position",
    )
    assert [c for (c,) in colunas] == [
        "iata_code",
        "_source_file",
        "state",
        "elevation_ft",
        "_ingested_at",
    ]


def test_source_file_ausente_e_acrescentado_ao_final(tmp_path, monkeypatch):
    _, banco = _preparar(tmp_path, monkeypatch)
    _executar()
    colunas = _consultar(
        banco,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'raw' AND table_name = 'airlines' ORDER BY ordinal_position",
    )
    assert [c for (c,) in colunas] == ["airline_code", "airline", "_ingested_at", "_source_file"]


def test_ingested_at_permanece_como_recebido_no_csv(tmp_path, monkeypatch):
    _, banco = _preparar(tmp_path, monkeypatch)
    _executar()
    assert _consultar(banco, "SELECT DISTINCT _ingested_at FROM raw.flights_2025") == [
        ("2025-06-01 10:00:00+00",)
    ]


# ------------------------------------------------------------------ reexecução e blocos


def test_reexecutar_recria_as_tabelas_sem_duplicar(tmp_path, monkeypatch):
    _, banco = _preparar(tmp_path, monkeypatch)
    _executar()
    _executar()
    assert _consultar(banco, "SELECT COUNT(*) FROM raw.flights_2025") == [(4,)]


def test_leitura_em_varios_blocos_preserva_todas_as_linhas(tmp_path, monkeypatch):
    # Blocos de 1 linha: os 4 voos chegam em 4 blocos e todos são gravados.
    _, banco = _preparar(tmp_path, monkeypatch)
    monkeypatch.setattr(ingestao, "LINHAS_POR_BLOCO", 1)
    _executar()
    assert _consultar(banco, "SELECT COUNT(*) FROM raw.flights_2025") == [(4,)]
    assert _consultar(banco, "SELECT DISTINCT _source_file FROM raw.flights_2025") == [
        ("flights_2025_sample.csv",)
    ]


def test_csv_em_utf8_preserva_acentuacao(tmp_path, monkeypatch):
    # Nome de companhia com acentos; o restante dos arquivos é o padrão.
    arquivos = dict(CSVS)
    arquivos["airlines.csv"] = "airline_code,airline\nXX,Aérea São João\n"
    _, banco = _preparar(tmp_path, monkeypatch, arquivos)
    _executar()
    assert _consultar(banco, "SELECT airline FROM raw.airlines") == [("Aérea São João",)]


# ------------------------------------------------------------------ validação


def test_arquivo_ausente_encerra_sem_criar_banco_e_lista_os_ausentes(
    tmp_path, monkeypatch
):
    # Faltam dois dos quatro arquivos.
    parciais = {k: v for k, v in CSVS.items() if k in ("airlines.csv", "airports.csv")}
    _, banco = _preparar(tmp_path, monkeypatch, parciais)
    codigo, texto = _executar()
    assert codigo == 1
    assert "daily_airport_stats.csv" in texto
    assert "flights_2025_sample.csv" in texto
    assert "airlines.csv" not in texto
    # Verificação antes de abrir o banco: nenhum arquivo de banco foi criado.
    assert not banco.exists()


def test_arquivo_ausente_nao_altera_ingestao_anterior(tmp_path, monkeypatch):
    pasta, banco = _preparar(tmp_path, monkeypatch)
    _executar()
    (pasta / "flights_2025_sample.csv").unlink()
    (pasta / "airlines.csv").write_text("airline_code\nZZ\n", encoding="utf-8")
    codigo, _ = _executar()
    assert codigo == 1
    # Nenhuma ingestão parcial: raw.airlines continua com as 2 linhas originais.
    assert _consultar(banco, "SELECT COUNT(*) FROM raw.airlines") == [(2,)]


def test_flights_2025_csv_nao_faz_parte_do_pipeline(tmp_path, monkeypatch):
    # Um flights_2025.csv presente na pasta é ignorado; só a amostra é lida.
    pasta, banco = _preparar(tmp_path, monkeypatch)
    (pasta / "flights_2025.csv").write_text("flight_date\n2025-12-31\n", encoding="utf-8")
    _executar()
    assert _consultar(banco, "SELECT COUNT(*) FROM raw.flights_2025") == [(4,)]
    assert set(ingestao.ARQUIVOS) == {
        "airlines.csv",
        "airports.csv",
        "daily_airport_stats.csv",
        "flights_2025_sample.csv",
    }

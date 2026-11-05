"""Testes de pipeline/transformacao.py — seções 1 a 12 da SPEC.

As tabelas RAW são criadas em um DuckDB temporário (todas as colunas VARCHAR,
como a ingestão grava), com registros inventados. aviation.duckdb nunca é aberto.
"""

import contextlib
import io
from datetime import date
from decimal import Decimal

import duckdb

from pipeline import db, transformacao
from pipeline.transformacao import TABELAS

TS = "2025-06-01 10:00:00+00"

# Linha válida de referência para cada tabela RAW (colunas omitidas ficam nulas).
COMPANHIA = {"airline_code": "AA", "airline": "American", "flights": "10",
             "on_time_arrival_rate": "0.81234", "cancel_rate": "0.01",
             "first_flight_date": "2025-01-01", "last_flight_date": "2025-12-31",
             "_source_file": "airlines.csv", "_ingested_at": TS}
AEROPORTO = {"iata_code": "AAA", "icao_code": "KAAA", "airport_name": "Alfa",
             "city": "Alfa City", "state": "TX", "latitude": "32.123456",
             "longitude": "-97.5", "elevation_ft": "500", "departures": "100",
             "arrivals": "90", "_source_file": "airports.csv", "_ingested_at": TS}
ESTATISTICA = {"flight_date": "2025-01-01", "airport": "AAA", "departures_scheduled": "50",
               "cancelled": "1", "diverted": "0", "dep_delay_mean": "12.3456",
               "dep_del15_rate": "0.2", "_source_file": "daily.csv", "_ingested_at": TS}
VOO = {"flight_date": "2025-01-01", "year": "2025", "month": "1", "day_of_week": "4",
       "airline_code": "AA", "airline": "American", "flight_number": "100",
       "origin": "AAA", "dest": "BBB", "sched_dep_time": "0600", "dep_time": "0610",
       "dep_delay": "10.00", "dep_del15": "0", "dep_time_block": "0600-0659",
       "cancelled": "0", "diverted": "0", "distance": "500",
       "_source_file": "flights.csv", "_ingested_at": TS}


def _banco(tmp_path, monkeypatch):
    caminho = tmp_path / "teste.duckdb"
    monkeypatch.setattr(db, "CAMINHO_BANCO", caminho)
    return caminho


def _criar_raw(caminho, linhas=None, omitir=()):
    """Cria raw.* com todas as colunas VARCHAR; linhas = {origem: [dict, ...]}."""
    padrao = {"airlines": [COMPANHIA], "airports": [AEROPORTO],
              "daily_airport_stats": [ESTATISTICA], "flights_2025": [VOO]}
    padrao.update(linhas or {})
    con = duckdb.connect(str(caminho))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        for tabela in TABELAS:
            if tabela.origem in omitir:
                continue
            colunas = [c[0] for c in tabela.colunas]
            definicao = ", ".join(f'"{c}" VARCHAR' for c in colunas)
            con.execute(f"CREATE OR REPLACE TABLE raw.{tabela.origem} ({definicao})")
            marcadores = ", ".join("?" for _ in colunas)
            for linha in padrao[tabela.origem]:
                con.execute(
                    f"INSERT INTO raw.{tabela.origem} VALUES ({marcadores})",
                    [linha.get(c) for c in colunas],
                )
    finally:
        con.close()


def _executar():
    saida = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    codigo = 0
    with contextlib.redirect_stdout(saida):
        try:
            transformacao.main()
        except SystemExit as fim:
            codigo = fim.code
    saida.flush()
    return codigo, saida.buffer.getvalue().decode("utf-8")


def _bloco(texto, destino):
    """Linhas impressas para refined.<destino>, até a linha em branco seguinte."""
    linhas = texto.splitlines()
    inicio = next(i for i, x in enumerate(linhas) if x.startswith(f"refined.{destino} "))
    fim = linhas.index("", inicio)
    return "\n".join(linhas[inicio:fim])


def _consultar(caminho, sql):
    con = duckdb.connect(str(caminho), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _tipos(caminho, tabela):
    return dict(_consultar(
        caminho,
        "SELECT column_name, data_type FROM information_schema.columns "
        f"WHERE table_schema = 'refined' AND table_name = '{tabela}' ORDER BY ordinal_position",
    ))


# ------------------------------------------------------------------ escopo e nomes


def test_as_quatro_tabelas_raw_geram_as_quatro_tabelas_refined(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    _criar_raw(caminho)
    codigo, _ = _executar()
    tabelas = _consultar(
        caminho,
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'refined' ORDER BY table_name",
    )
    assert codigo == 0
    assert tabelas == [("aeroportos",), ("companhias_aereas",),
                       ("estatisticas_diarias_aeroportos",), ("voos_2025",)]


def test_colunas_sao_renomeadas_exatamente_conforme_o_mapa(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    _criar_raw(caminho)
    _executar()
    for tabela in TABELAS:
        assert list(_tipos(caminho, tabela.destino)) == [c[1] for c in tabela.colunas]


def test_camada_raw_e_apenas_lida(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    _criar_raw(caminho)
    antes = _consultar(caminho, "SELECT * FROM raw.flights_2025")
    _executar()
    assert _consultar(caminho, "SELECT * FROM raw.flights_2025") == antes


def test_registros_de_2026_sao_preservados(tmp_path, monkeypatch):
    # Um voo de 2025 e um de 2026: nenhum filtro de ano.
    caminho = _banco(tmp_path, monkeypatch)
    voo_2026 = {**VOO, "flight_date": "2026-01-02", "year": "2026", "flight_number": "200"}
    _criar_raw(caminho, {"flights_2025": [VOO, voo_2026]})
    _executar()
    assert _consultar(caminho, "SELECT ano FROM refined.voos_2025 ORDER BY ano") == [
        (2025,), (2026,)
    ]


# ------------------------------------------------------------------ tipos


def test_tipos_convertidos_conforme_a_spec(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    _criar_raw(caminho)
    _executar()
    companhias = _tipos(caminho, "companhias_aereas")
    aeroportos = _tipos(caminho, "aeroportos")
    estatisticas = _tipos(caminho, "estatisticas_diarias_aeroportos")
    voos = _tipos(caminho, "voos_2025")

    assert companhias["data_primeiro_voo"] == "DATE"
    assert companhias["quantidade_voos"] == "BIGINT"
    assert companhias["taxa_cancelamento"] == "DECIMAL(8,5)"
    assert companhias["data_ingestao"] == "TIMESTAMP WITH TIME ZONE"
    assert aeroportos["latitude"] == "DECIMAL(10,6)"
    assert estatisticas["atraso_medio_partida"] == "DECIMAL(10,4)"
    assert voos["atraso_partida"] == "DECIMAL(10,2)"
    assert voos["cancelado"] == "BOOLEAN"
    assert voos["arquivo_origem"] == "VARCHAR"


def test_identificadores_e_horarios_hhmm_permanecem_texto(tmp_path, monkeypatch):
    # sched_dep_time "0600" está no mapa como INTEGER; dep_time_block e códigos ficam VARCHAR.
    caminho = _banco(tmp_path, monkeypatch)
    _criar_raw(caminho)
    _executar()
    voos = _tipos(caminho, "voos_2025")
    assert voos["codigo_companhia"] == "VARCHAR"
    assert voos["origem"] == "VARCHAR"
    assert voos["faixa_horario_partida"] == "VARCHAR"
    assert voos["numero_matricula_aeronave"] == "VARCHAR"
    assert _consultar(caminho, "SELECT faixa_horario_partida FROM refined.voos_2025") == [
        ("0600-0659",)
    ]


def test_valores_validos_sao_convertidos_sem_alteracao(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    _criar_raw(caminho)
    _executar()
    linha = _consultar(
        caminho,
        "SELECT data_voo, numero_voo, atraso_partida, cancelado FROM refined.voos_2025",
    )
    assert linha == [(date(2025, 1, 1), 100, Decimal("10.00"), False)]


def test_numeros_aceitam_espacos_nas_extremidades_e_sinal(tmp_path, monkeypatch):
    # " +15 " -> 15 ; "-3.5" -> -3.50
    caminho = _banco(tmp_path, monkeypatch)
    voo = {**VOO, "flight_number": " +15 ", "dep_delay": "-3.5"}
    _criar_raw(caminho, {"flights_2025": [voo]})
    codigo, _ = _executar()
    assert codigo == 0
    assert _consultar(caminho, "SELECT numero_voo, atraso_partida FROM refined.voos_2025") == [
        (15, Decimal("-3.50"))
    ]


def test_booleano_aceita_0_1_true_false(tmp_path, monkeypatch):
    # Quatro voos com representações diferentes de cancelado.
    caminho = _banco(tmp_path, monkeypatch)
    voos = [
        {**VOO, "flight_number": "1", "cancelled": "1"},
        {**VOO, "flight_number": "2", "cancelled": "0"},
        {**VOO, "flight_number": "3", "cancelled": "true"},
        {**VOO, "flight_number": "4", "cancelled": "f"},
    ]
    _criar_raw(caminho, {"flights_2025": voos})
    _executar()
    assert _consultar(caminho, "SELECT cancelado FROM refined.voos_2025 ORDER BY numero_voo") == [
        (True,), (False,), (True,), (False,)
    ]


def test_latitude_com_mais_de_seis_casas_e_arredondada(tmp_path, monkeypatch):
    # Exceção 4.2: casas extras de latitude/longitude são arredondadas pelo CAST.
    caminho = _banco(tmp_path, monkeypatch)
    aeroporto = {**AEROPORTO, "latitude": "32.1234567", "longitude": "-97.0000004"}
    _criar_raw(caminho, {"airports": [aeroporto]})
    codigo, _ = _executar()
    assert codigo == 0
    assert _consultar(caminho, "SELECT latitude, longitude FROM refined.aeroportos") == [
        (Decimal("32.123457"), Decimal("-97.000000"))
    ]


# ------------------------------------------------------------------ validação estrita


def _valor_invalido_interrompe(tmp_path, monkeypatch, tabela_raw, base, coluna, valor):
    caminho = _banco(tmp_path, monkeypatch)
    _criar_raw(caminho, {tabela_raw: [{**base, coluna: valor}]})
    codigo, texto = _executar()
    return caminho, codigo, texto


def test_inteiro_com_casas_decimais_e_rejeitado(tmp_path, monkeypatch):
    # '1.5' viraria 2 com CAST direto; deve interromper.
    _, codigo, texto = _valor_invalido_interrompe(
        tmp_path, monkeypatch, "flights_2025", VOO, "flight_number", "1.5"
    )
    assert codigo == 1
    assert "raw.flights_2025" in texto
    assert "flight_number" in texto
    assert "'1.5'" in texto
    assert "ROLLBACK" in texto


def test_decimal_com_mais_casas_que_a_escala_e_rejeitado(tmp_path, monkeypatch):
    # '1.234' em DECIMAL(10,2) seria truncado para 1.23.
    _, codigo, texto = _valor_invalido_interrompe(
        tmp_path, monkeypatch, "flights_2025", VOO, "dep_delay", "1.234"
    )
    assert codigo == 1
    assert "dep_delay" in texto and "'1.234'" in texto


def test_decimal_com_digitos_inteiros_acima_do_limite_e_rejeitado(tmp_path, monkeypatch):
    # DECIMAL(8,5) admite 3 dígitos inteiros; '1234.5' tem 4.
    _, codigo, texto = _valor_invalido_interrompe(
        tmp_path, monkeypatch, "airlines", COMPANHIA, "cancel_rate", "1234.5"
    )
    assert codigo == 1
    assert "raw.airlines" in texto and "cancel_rate" in texto


def test_zeros_a_esquerda_nao_contam_no_limite_de_digitos_inteiros(tmp_path, monkeypatch):
    # '000123.45' tem 3 dígitos inteiros significativos: cabe em DECIMAL(8,5).
    caminho = _banco(tmp_path, monkeypatch)
    _criar_raw(caminho, {"airlines": [{**COMPANHIA, "cancel_rate": "000123.45"}]})
    codigo, _ = _executar()
    assert codigo == 0
    assert _consultar(caminho, "SELECT taxa_cancelamento FROM refined.companhias_aereas") == [
        (Decimal("123.45000"),)
    ]


def test_notacao_cientifica_e_rejeitada(tmp_path, monkeypatch):
    _, codigo, texto = _valor_invalido_interrompe(
        tmp_path, monkeypatch, "flights_2025", VOO, "distance", "1e3"
    )
    assert codigo == 1
    assert "distance" in texto and "'1e3'" in texto


def test_data_com_horario_e_rejeitada(tmp_path, monkeypatch):
    # '2025-01-01 10:00' viraria DATE 2025-01-01 com CAST direto.
    _, codigo, texto = _valor_invalido_interrompe(
        tmp_path, monkeypatch, "daily_airport_stats", ESTATISTICA, "flight_date", "2025-01-01 10:00"
    )
    assert codigo == 1
    assert "raw.daily_airport_stats" in texto and "flight_date" in texto


def test_data_fora_do_formato_yyyy_mm_dd_e_rejeitada(tmp_path, monkeypatch):
    _, codigo, texto = _valor_invalido_interrompe(
        tmp_path, monkeypatch, "flights_2025", VOO, "flight_date", "01/02/2025"
    )
    assert codigo == 1
    assert "'01/02/2025'" in texto


def test_timestamptz_sem_fuso_e_rejeitado(tmp_path, monkeypatch):
    _, codigo, texto = _valor_invalido_interrompe(
        tmp_path, monkeypatch, "airports", AEROPORTO, "_ingested_at", "2025-06-01 10:00:00"
    )
    assert codigo == 1
    assert "_ingested_at" in texto


def test_timestamptz_com_fracao_e_fuso_e_aceito(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    _criar_raw(caminho, {"airports": [{**AEROPORTO, "_ingested_at": "2025-06-01 10:00:00.123-03:00"}]})
    codigo, _ = _executar()
    assert codigo == 0
    assert _consultar(
        caminho, "SELECT epoch_ms(data_ingestao) FROM refined.aeroportos"
    ) == _consultar(caminho, "SELECT epoch_ms(TIMESTAMPTZ '2025-06-01 13:00:00.123+00')")


def test_falha_de_conversao_nao_altera_a_refined_existente(tmp_path, monkeypatch):
    # 1ª execução válida; 2ª com companhia nova e voo inválido (4ª tabela).
    caminho = _banco(tmp_path, monkeypatch)
    _criar_raw(caminho)
    _executar()
    _criar_raw(caminho, {
        "airlines": [COMPANHIA, {**COMPANHIA, "airline_code": "DL"}],
        "flights_2025": [{**VOO, "month": "1.5"}],
    })
    codigo, _ = _executar()
    assert codigo == 1
    # ROLLBACK: a primeira tabela continua com a única companhia da 1ª execução.
    assert _consultar(caminho, "SELECT codigo_companhia FROM refined.companhias_aereas") == [
        ("AA",)
    ]


def test_falha_de_conversao_lista_cada_coluna_invalida(tmp_path, monkeypatch):
    # Dois valores inválidos na mesma tabela: ambos aparecem no diagnóstico.
    caminho = _banco(tmp_path, monkeypatch)
    _criar_raw(caminho, {"flights_2025": [{**VOO, "month": "x", "distance": "9.9"}]})
    codigo, texto = _executar()
    assert codigo == 1
    assert "coluna: month" in texto and "'x'" in texto
    assert "coluna: distance" in texto and "'9.9'" in texto


# ------------------------------------------------------------------ duplicatas e nulos


def test_linhas_repetidas_e_conflitos_sao_contados_e_mantidos(tmp_path, monkeypatch):
    # 4 voos: duas linhas idênticas (1 repetição) e dois com a mesma chave e
    # atraso diferente (1 conflito). Nenhum é removido.
    caminho = _banco(tmp_path, monkeypatch)
    voos = [
        VOO,
        VOO,
        {**VOO, "flight_number": "300", "dep_delay": "1.00"},
        {**VOO, "flight_number": "300", "dep_delay": "2.00"},
    ]
    _criar_raw(caminho, {"flights_2025": voos})
    codigo, texto = _executar()
    bloco = _bloco(texto, "voos_2025")
    assert codigo == 0
    assert _consultar(caminho, "SELECT COUNT(*) FROM refined.voos_2025") == [(4,)]
    assert "linhas integralmente repetidas" in bloco
    assert bloco.split("linhas integralmente repetidas")[1].split()[0] == "1"
    assert bloco.split("conflitos de chave")[1].split()[0] == "1"
    exemplos = [x for x in bloco.splitlines() if "versões" in x]
    assert len(exemplos) == 1
    assert "numero_voo=300," in exemplos[0]
    assert exemplos[0].endswith("-> 2 versões")


def test_conflito_considera_arquivo_origem(tmp_path, monkeypatch):
    # Duas companhias iguais exceto pelo arquivo de origem: é conflito, não repetição.
    caminho = _banco(tmp_path, monkeypatch)
    _criar_raw(caminho, {"airlines": [COMPANHIA, {**COMPANHIA, "_source_file": "outro.csv"}]})
    _, texto = _executar()
    bloco = _bloco(texto, "companhias_aereas")
    assert bloco.split("linhas integralmente repetidas")[1].split()[0] == "0"
    assert bloco.split("conflitos de chave")[1].split()[0] == "1"


def test_nulos_sao_mantidos_e_listados_na_saida(tmp_path, monkeypatch):
    # Voo sem atraso informado (dep_delay nulo) e sem matrícula.
    caminho = _banco(tmp_path, monkeypatch)
    _criar_raw(caminho, {"flights_2025": [{**VOO, "dep_delay": None}]})
    codigo, texto = _executar()
    bloco = _bloco(texto, "voos_2025")
    assert codigo == 0
    assert _consultar(caminho, "SELECT atraso_partida FROM refined.voos_2025") == [(None,)]
    assert "atraso_partida" in bloco


def test_tabela_sem_nulos_informa_nenhum(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    _criar_raw(caminho)
    _, texto = _executar()
    bloco = _bloco(texto, "companhias_aereas")
    assert "Nulos mantidos: nenhum" in bloco


def test_saida_mostra_origem_destino_e_total_com_milhar_em_ponto(tmp_path, monkeypatch):
    # 1.001 voos idênticos gerados para verificar o separador de milhar.
    caminho = _banco(tmp_path, monkeypatch)
    _criar_raw(caminho, {"flights_2025": [VOO] * 1001})
    _, texto = _executar()
    assert "1.001 -> 1.001 linhas" in texto
    # 1 + 1 + 1 + 1.001 = 1.004
    assert texto.rstrip().splitlines()[-1].split() == ["TOTAL", "1.004", "->", "1.004", "linhas"]


# ------------------------------------------------------------------ reexecução e erros


def test_reexecutar_nao_acrescenta_registros(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    _criar_raw(caminho, {"flights_2025": [VOO, {**VOO, "flight_number": "2"}]})
    _, primeira = _executar()
    _, segunda = _executar()
    assert _consultar(caminho, "SELECT COUNT(*) FROM refined.voos_2025") == [(2,)]
    assert primeira == segunda


def test_tabela_raw_ausente_lista_todas_e_nada_e_transformado(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    _criar_raw(caminho, omitir=("airports", "flights_2025"))
    codigo, texto = _executar()
    assert codigo == 1
    assert "raw.airports" in texto and "raw.flights_2025" in texto
    assert "raw.airlines" not in texto
    assert "uv run python -m pipeline.ingestao" in texto
    assert _consultar(
        caminho, "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'refined'"
    ) == [(0,)]


def test_divergencia_raw_refined_faz_rollback_e_informa_esperado_e_encontrado(
    tmp_path, monkeypatch
):
    # A divergência não ocorre com CAST real; ela é simulada substituindo a contagem
    # de nulos da REFINED de uma tabela, para comprovar a regra 12 (ROLLBACK + saída).
    caminho = _banco(tmp_path, monkeypatch)
    _criar_raw(caminho)
    _executar()
    _criar_raw(caminho, {"airlines": [COMPANHIA, {**COMPANHIA, "airline_code": "DL"}]})

    original = transformacao._nulos

    def nulos_divergentes(con, relacao, colunas):
        resultado = original(con, relacao, colunas)
        if relacao == '"refined"."voos_2025"':
            resultado[0] += 7
        return resultado

    monkeypatch.setattr(transformacao, "_nulos", nulos_divergentes)
    codigo, texto = _executar()
    assert codigo == 1
    assert "refined.voos_2025" in texto
    assert "coluna: data_voo (nulos)  |  esperado: 0  |  encontrado: 7" in texto
    assert _consultar(caminho, "SELECT COUNT(*) FROM refined.companhias_aereas") == [(1,)]

"""
pipeline/transformacao.py — padronização da camada RAW para a camada REFINED.

SPEC (fonte: SPECS/Transformação.txt)
----
Objetivo: ler as quatro tabelas do schema raw, traduzir nomes para
português, converter tipos com SQL do DuckDB e gravar no schema refined,
sem filtrar, deduplicar, preencher ou interpretar os dados.

Execução: uv run python -m pipeline.transformacao

1. ESCOPO
   raw.airlines              -> refined.companhias_aereas
   raw.airports              -> refined.aeroportos
   raw.daily_airport_stats   -> refined.estatisticas_diarias_aeroportos
   raw.flights_2025          -> refined.voos_2025
   A camada RAW é apenas lida. Nenhum filtro de ano: registros de 2026
   são preservados.
   Motivo: a REFINED representa os dados recebidos após a padronização;
   recortes de período pertencem à camada analítica.

2. NOMES
   Tabelas e todas as colunas, inclusive metadados, em português snake_case,
   exatamente conforme os mapas em TABELAS. Nenhuma coluna criada ou removida.
   Motivo: o vocabulário das consultas e JOINs é em português (padrão Olist).

3. TIPOS
   Conversão feita no DuckDB, em SQL, sem trazer dados para o Pandas.
   Datas DATE; data_ingestao TIMESTAMPTZ; contagens BIGINT; coordenadas
   DECIMAL(10,6); taxas DECIMAL(8,5); atrasos e tempos DECIMAL(10,2);
   atraso_medio_partida DECIMAL(10,4) (a origem tem até 4 casas decimais).
   Identificadores e horários HHMM não são convertidos para número/TIME.
   Motivo: códigos são rótulos; HHMM -> TIME exigiria regras para 2400,
   virada de dia e valores inválidos.

4. CONVERSÃO E VALIDAÇÃO ESTRITA
   O formato do texto é validado antes do CAST, porque o CAST do DuckDB
   arredonda ou trunca sem erro ('1.5' -> INTEGER 2; '1.234' ->
   DECIMAL(10,2) 1.23; '2025-01-01 10:00' -> DATE 2025-01-01).
   - INTEGER/BIGINT: só dígitos; rejeita casas decimais.
   - DECIMAL(p,s): no máximo p-s dígitos inteiros e s casas; não arredonda.
   - DATE: somente YYYY-MM-DD.
   - TIMESTAMPTZ: YYYY-MM-DD HH:MM:SS[.ffffff]±HH[:MM]; data, hora e fuso
     são obrigatórios.
   - Notação científica rejeitada. Números aceitam espaços nas extremidades
     e sinal + ou -.
   Fora do formato: error() no SQL interrompe; informa tabela, coluna e
   valor; ROLLBACK; sys.exit(1). Sem TRY_CAST nem coerção para NULL.
   4.1 BOOLEAN: CAST direto (0/1, true/false, t/f, yes/no).
   4.2 Exceção: latitude e longitude podem ter mais de 6 casas e são
       arredondadas pelo CAST (casas extras são ruído de float32; 6 casas
       ≈ 11 cm). Dígitos inteiros e notação científica seguem a regra geral.
   Motivo: um NULL ou valor alterado pela conversão fica indistinguível do
   dado verdadeiro recebido na origem.

5. DUPLICATAS E CHAVES
   Chaves: companhias_aereas (codigo_companhia); aeroportos (codigo_iata);
   estatisticas_diarias_aeroportos (data_voo + aeroporto); voos_2025
   (data_voo + codigo_companhia + numero_voo + origem + destino +
   horario_partida_programado — provisória, validada só na amostra).
   Linhas integralmente repetidas e conflitos (chave igual, conteúdo
   diferente) consideram todas as colunas, inclusive arquivo_origem e
   data_ingestao. São contados e exibidos; nada é removido e a execução
   prossegue (política provisória).
   Motivo: a transformação não decide silenciosamente qual registro é o correto.

6. NULOS
   Nenhuma linha eliminada por nulo; nenhum nulo preenchido.
   Motivo: a ausência de informação pode ser característica legítima da operação.

7. METADADOS
   _source_file -> arquivo_origem (VARCHAR); _ingested_at -> data_ingestao
   (TIMESTAMPTZ), nas quatro tabelas, com o valor recebido.
   Motivo: rastrear origem e momento da ingestão de cada registro.

8. SAÍDA
   "refined.x   N -> N linhas" por tabela, com origem, destino, linhas
   repetidas, conflitos e nulos abaixo; só colunas com nulos são listadas,
   senão "Nulos mantidos: nenhum". TOTAL ao final. Contagens do DuckDB,
   milhares com ponto, stdout UTF-8.
   Motivo: a saída é o instrumento de conferência entre RAW e REFINED.

9. REEXECUÇÃO
   CREATE OR REPLACE TABLE; nunca acrescenta registros.
   Motivo: dez execuções produzem o mesmo resultado de uma.

10. ERRO
   Tabela RAW ausente: lista todas as ausentes, orienta executar
   `uv run python -m pipeline.ingestao`, sys.exit(1), nada é transformado.
   Motivo: impedir atualização parcial da REFINED.

11. TRANSAÇÃO E ATOMICIDADE
   Uma única transação: transforma as quatro tabelas, valida contagens e
   nulos, e só então COMMIT. Qualquer falha: ROLLBACK.
   Motivo: uma falha na quarta tabela não pode deixar as três primeiras
   atualizadas.

12. INTEGRIDADE RAW × REFINED
   Após cada tabela, compara linhas e nulos por coluna. Divergência:
   informa tabela, coluna, esperado e encontrado; ROLLBACK; sys.exit(1).
   Motivo: a REFINED precisa preservar a integridade dos registros recebidos.
"""

import re
import sys
from dataclasses import dataclass

import duckdb

from pipeline.db import conectar, criar_schema

SCHEMA_ORIGEM = "raw"
SCHEMA_DESTINO = "refined"
LARGURA_ROTULO = 42
LARGURA_DETALHE = 38
MAX_EXEMPLOS_CONFLITO = 5
_MARCADOR_ERRO = "CONVERSAO_INVALIDA:"
_FORMATO_TIMESTAMPTZ = (
    r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?"
    r"[+-][0-9]{2}(:[0-9]{2})?"
)


@dataclass(frozen=True)
class Tabela:
    origem: str
    destino: str
    colunas: tuple[tuple[str, str, str], ...]  # (coluna RAW, coluna REFINED, tipo)
    chave: tuple[str, ...]
    arredondamento_aceito: frozenset[str] = frozenset()


TABELAS = (
    Tabela(
        origem="airlines",
        destino="companhias_aereas",
        colunas=(
            ("airline_code", "codigo_companhia", "VARCHAR"),
            ("airline", "companhia_aerea", "VARCHAR"),
            ("flights", "quantidade_voos", "BIGINT"),
            ("on_time_arrival_rate", "taxa_chegadas_no_horario", "DECIMAL(8,5)"),
            ("cancel_rate", "taxa_cancelamento", "DECIMAL(8,5)"),
            ("first_flight_date", "data_primeiro_voo", "DATE"),
            ("last_flight_date", "data_ultimo_voo", "DATE"),
            ("_source_file", "arquivo_origem", "VARCHAR"),
            ("_ingested_at", "data_ingestao", "TIMESTAMPTZ"),
        ),
        chave=("codigo_companhia",),
    ),
    Tabela(
        origem="airports",
        destino="aeroportos",
        colunas=(
            ("iata_code", "codigo_iata", "VARCHAR"),
            ("icao_code", "codigo_icao", "VARCHAR"),
            ("airport_name", "nome_aeroporto", "VARCHAR"),
            ("city", "cidade", "VARCHAR"),
            ("state", "estado", "VARCHAR"),
            ("latitude", "latitude", "DECIMAL(10,6)"),
            ("longitude", "longitude", "DECIMAL(10,6)"),
            ("elevation_ft", "altitude_pes", "INTEGER"),
            ("airport_type", "tipo_aeroporto", "VARCHAR"),
            ("departures", "quantidade_partidas", "BIGINT"),
            ("arrivals", "quantidade_chegadas", "BIGINT"),
            ("_source_file", "arquivo_origem", "VARCHAR"),
            ("_ingested_at", "data_ingestao", "TIMESTAMPTZ"),
        ),
        chave=("codigo_iata",),
        arredondamento_aceito=frozenset({"latitude", "longitude"}),
    ),
    Tabela(
        origem="daily_airport_stats",
        destino="estatisticas_diarias_aeroportos",
        colunas=(
            ("flight_date", "data_voo", "DATE"),
            ("airport", "aeroporto", "VARCHAR"),
            ("departures_scheduled", "partidas_programadas", "BIGINT"),
            ("cancelled", "voos_cancelados", "BIGINT"),
            ("diverted", "voos_desviados", "BIGINT"),
            ("dep_delay_mean", "atraso_medio_partida", "DECIMAL(10,4)"),
            ("dep_del15_rate", "taxa_atrasos_partida_15min", "DECIMAL(8,5)"),
            ("arr_del15_rate", "taxa_atrasos_chegada_15min", "DECIMAL(8,5)"),
            ("weather_delay_minutes", "atraso_clima_minutos", "BIGINT"),
            ("nas_delay_minutes", "atraso_nas_minutos", "BIGINT"),
            ("carrier_delay_minutes", "atraso_companhia_minutos", "BIGINT"),
            ("late_aircraft_delay_minutes", "atraso_aeronave_anterior_minutos", "BIGINT"),
            ("cancel_rate", "taxa_cancelamento", "DECIMAL(8,5)"),
            ("_source_file", "arquivo_origem", "VARCHAR"),
            ("_ingested_at", "data_ingestao", "TIMESTAMPTZ"),
        ),
        chave=("data_voo", "aeroporto"),
    ),
    Tabela(
        origem="flights_2025",
        destino="voos_2025",
        colunas=(
            ("flight_date", "data_voo", "DATE"),
            ("year", "ano", "INTEGER"),
            ("month", "mes", "INTEGER"),
            ("day_of_week", "dia_semana", "INTEGER"),
            ("airline_code", "codigo_companhia", "VARCHAR"),
            ("airline", "companhia_aerea", "VARCHAR"),
            ("tail_number", "numero_matricula_aeronave", "VARCHAR"),
            ("flight_number", "numero_voo", "INTEGER"),
            ("origin", "origem", "VARCHAR"),
            ("origin_city", "cidade_origem", "VARCHAR"),
            ("origin_state", "estado_origem", "VARCHAR"),
            ("dest", "destino", "VARCHAR"),
            ("dest_city", "cidade_destino", "VARCHAR"),
            ("dest_state", "estado_destino", "VARCHAR"),
            ("sched_dep_time", "horario_partida_programado", "INTEGER"),
            ("dep_time", "horario_partida_real", "INTEGER"),
            ("dep_delay", "atraso_partida", "DECIMAL(10,2)"),
            ("dep_del15", "atraso_partida_15min", "INTEGER"),
            ("dep_time_block", "faixa_horario_partida", "VARCHAR"),
            ("taxi_out", "tempo_taxi_saida", "DECIMAL(10,2)"),
            ("wheels_off", "horario_decolagem", "INTEGER"),
            ("wheels_on", "horario_pouso", "INTEGER"),
            ("taxi_in", "tempo_taxi_chegada", "DECIMAL(10,2)"),
            ("sched_arr_time", "horario_chegada_programado", "INTEGER"),
            ("arr_time", "horario_chegada_real", "INTEGER"),
            ("arr_delay", "atraso_chegada", "DECIMAL(10,2)"),
            ("arr_del15", "atraso_chegada_15min", "INTEGER"),
            ("cancelled", "cancelado", "BOOLEAN"),
            ("cancellation_code", "codigo_cancelamento", "VARCHAR"),
            ("cancellation_reason", "motivo_cancelamento", "VARCHAR"),
            ("diverted", "desviado", "BOOLEAN"),
            ("sched_elapsed_time", "tempo_total_programado", "INTEGER"),
            ("actual_elapsed_time", "tempo_total_real", "DECIMAL(10,2)"),
            ("air_time", "tempo_voo", "DECIMAL(10,2)"),
            ("distance", "distancia", "INTEGER"),
            ("carrier_delay", "atraso_companhia", "DECIMAL(10,2)"),
            ("weather_delay", "atraso_clima", "DECIMAL(10,2)"),
            ("nas_delay", "atraso_nas", "DECIMAL(10,2)"),
            ("security_delay", "atraso_seguranca", "DECIMAL(10,2)"),
            ("late_aircraft_delay", "atraso_aeronave_anterior", "DECIMAL(10,2)"),
            ("_source_file", "arquivo_origem", "VARCHAR"),
            ("_ingested_at", "data_ingestao", "TIMESTAMPTZ"),
        ),
        chave=(
            "data_voo",
            "codigo_companhia",
            "numero_voo",
            "origem",
            "destino",
            "horario_partida_programado",
        ),
    ),
)


class FalhaConversao(Exception):
    pass


class FalhaConferencia(Exception):
    pass


def _ident(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def _literal(texto: str) -> str:
    return "'" + texto.replace("'", "''") + "'"


def _formatar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _formato_exigido(tipo: str, arredondamento_aceito: bool) -> str | None:
    """Regex que o texto precisa satisfazer para o CAST não alterar o valor."""
    if tipo in ("INTEGER", "BIGINT"):
        return r"[+-]?[0-9]+"
    if tipo == "DATE":
        return r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
    if tipo == "TIMESTAMPTZ":
        return _FORMATO_TIMESTAMPTZ
    decimal = re.fullmatch(r"DECIMAL\((\d+),(\d+)\)", tipo)
    if decimal:
        precisao, escala = map(int, decimal.groups())
        casas = "[0-9]*" if arredondamento_aceito else rf"[0-9]{{0,{escala}}}"
        # Zeros à esquerda não contam para o limite de dígitos inteiros.
        return rf"[+-]?0*[0-9]{{1,{precisao - escala}}}(\.{casas})?"
    return None


def _expressao(coluna_raw: str, tipo: str, arredondamento_aceito: bool) -> str:
    col = _ident(coluna_raw)
    if tipo == "VARCHAR":
        return col
    cast = f"CAST({col} AS {tipo})"
    formato = _formato_exigido(tipo, arredondamento_aceito)
    if formato is None:
        return cast
    numerico = tipo in ("INTEGER", "BIGINT") or tipo.startswith("DECIMAL")
    alvo = f"trim({col})" if numerico else col
    return (
        f"CASE WHEN {col} IS NULL OR regexp_full_match({alvo}, {_literal(formato)}) "
        f"THEN {cast} ELSE error({_literal(_MARCADOR_ERRO)} || {col}) END"
    )


def _select(tabela: Tabela, colunas=None) -> str:
    colunas = tabela.colunas if colunas is None else colunas
    campos = ",\n    ".join(
        f"{_expressao(raw, tipo, dest in tabela.arredondamento_aceito)} AS {_ident(dest)}"
        for raw, dest, tipo in colunas
    )
    return f"SELECT\n    {campos}\nFROM {_origem(tabela)}"


def _destino(tabela: Tabela) -> str:
    return f"{_ident(SCHEMA_DESTINO)}.{_ident(tabela.destino)}"


def _origem(tabela: Tabela) -> str:
    return f"{_ident(SCHEMA_ORIGEM)}.{_ident(tabela.origem)}"


def _tabelas_ausentes(con: duckdb.DuckDBPyConnection) -> list[str]:
    existentes = {
        nome
        for (nome,) in con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_catalog = current_database() AND table_schema = ?",
            [SCHEMA_ORIGEM],
        ).fetchall()
    }
    return [f"{SCHEMA_ORIGEM}.{t.origem}" for t in TABELAS if t.origem not in existentes]


def _exemplo_do_erro(mensagem: str) -> str:
    if _MARCADOR_ERRO in mensagem:
        return mensagem.split(_MARCADOR_ERRO, 1)[1].splitlines()[0]
    citado = re.search(r"""["']([^"']*)["']""", mensagem)
    return citado.group(1) if citado else mensagem.splitlines()[0]


def _diagnosticar(con, tabela: Tabela) -> list[tuple[str, str]]:
    """Reconverte coluna a coluna para identificar quais falham e um valor de exemplo."""
    falhas = []
    for coluna in tabela.colunas:
        # COUNT(coluna), não COUNT(*): com COUNT(*) o otimizador descarta a projeção e o CAST não roda.
        try:
            con.execute(
                f"SELECT COUNT({_ident(coluna[1])}) FROM ({_select(tabela, [coluna])})"
            ).fetchone()
        except (duckdb.ConversionException, duckdb.InvalidInputException) as erro:
            falhas.append((coluna[0], _exemplo_do_erro(str(erro))))
    return falhas


def _contar(con, relacao: str) -> int:
    return con.execute(f"SELECT COUNT(*) FROM {relacao}").fetchone()[0]


def _nulos(con, relacao: str, colunas: list[str]) -> list[int]:
    expressoes = ", ".join(f"COUNT(*) - COUNT({_ident(c)})" for c in colunas)
    return list(con.execute(f"SELECT {expressoes} FROM {relacao}").fetchone())


def _duplicidades(con, tabela: Tabela) -> tuple[int, int, list[tuple]]:
    destino = _destino(tabela)
    repetidas = con.execute(
        f"SELECT (SELECT COUNT(*) FROM {destino}) "
        f"- (SELECT COUNT(*) FROM (SELECT DISTINCT * FROM {destino}))"
    ).fetchone()[0]

    # Sobre linhas distintas: uma chave que reaparece aqui tem conteúdos diferentes.
    chave = ", ".join(_ident(c) for c in tabela.chave)
    conflitos_sql = (
        f"SELECT {chave}, COUNT(*) AS versoes "
        f"FROM (SELECT DISTINCT * FROM {destino}) GROUP BY {chave} HAVING COUNT(*) > 1"
    )
    conflitos = con.execute(f"SELECT COUNT(*) FROM ({conflitos_sql})").fetchone()[0]
    exemplos = con.execute(
        f"{conflitos_sql} ORDER BY {chave} LIMIT {MAX_EXEMPLOS_CONFLITO}"
    ).fetchall()
    return repetidas, conflitos, exemplos


def _transformar(con, tabela: Tabela) -> dict:
    try:
        con.execute(f"CREATE OR REPLACE TABLE {_destino(tabela)} AS\n{_select(tabela)}")
    except (duckdb.ConversionException, duckdb.InvalidInputException) as erro:
        raise FalhaConversao(tabela) from erro

    divergencias = []
    origem = _contar(con, _origem(tabela))
    destino = _contar(con, _destino(tabela))
    if origem != destino:
        divergencias.append(("(quantidade de linhas)", origem, destino))

    nulos_raw = _nulos(con, _origem(tabela), [c[0] for c in tabela.colunas])
    nulos_refined = _nulos(con, _destino(tabela), [c[1] for c in tabela.colunas])
    divergencias += [
        (f"{dest} (nulos)", esperado, encontrado)
        for (_, dest, _), esperado, encontrado in zip(tabela.colunas, nulos_raw, nulos_refined)
        if esperado != encontrado
    ]
    if divergencias:
        raise FalhaConferencia(tabela, divergencias)

    repetidas, conflitos, exemplos = _duplicidades(con, tabela)
    return {
        "origem": origem,
        "destino": destino,
        "nulos": [(c[1], n) for c, n in zip(tabela.colunas, nulos_refined) if n],
        "repetidas": repetidas,
        "conflitos": conflitos,
        "exemplos": exemplos,
    }


def _detalhe(rotulo: str, valor: str) -> None:
    print(f"    {rotulo:<{LARGURA_DETALHE}}{valor}")


def _imprimir(tabela: Tabela, r: dict) -> None:
    rotulo = f"{SCHEMA_DESTINO}.{tabela.destino}"
    print(f"{rotulo:<{LARGURA_ROTULO}}{_formatar(r['origem'])} -> {_formatar(r['destino'])} linhas")
    _detalhe("registros na origem", f"{_formatar(r['origem'])}  ({SCHEMA_ORIGEM}.{tabela.origem})")
    _detalhe("registros no destino", f"{_formatar(r['destino'])}  ({rotulo})")
    _detalhe("linhas integralmente repetidas", _formatar(r["repetidas"]))
    _detalhe("conflitos de chave", f"{_formatar(r['conflitos'])}  ({' + '.join(tabela.chave)})")
    for *valores, versoes in r["exemplos"]:
        chave = ", ".join(f"{c}={v}" for c, v in zip(tabela.chave, valores))
        _detalhe("", f"  {chave} -> {_formatar(versoes)} versões")
    if not r["nulos"]:
        print("    Nulos mantidos: nenhum")
    else:
        print("    Nulos mantidos:")
        for coluna, n in r["nulos"]:
            _detalhe(f"  {coluna}", _formatar(n))
    print()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    con = conectar()
    try:
        ausentes = _tabelas_ausentes(con)
        if ausentes:
            print("Tabelas RAW ausentes:")
            for nome in ausentes:
                print(f"  - {nome}")
            print("Execute antes: uv run python -m pipeline.ingestao")
            sys.exit(1)

        criar_schema(con, SCHEMA_DESTINO)

        resultados = []
        con.begin()
        try:
            for tabela in TABELAS:
                resultados.append((tabela, _transformar(con, tabela)))
            con.commit()
        except FalhaConversao as falha:
            con.rollback()
            tabela = falha.args[0]
            print("Conversão inválida. ROLLBACK executado; nenhuma tabela REFINED foi alterada.")
            print(f"  tabela: {SCHEMA_ORIGEM}.{tabela.origem}")
            for coluna, exemplo in _diagnosticar(con, tabela) or [("?", str(falha.__cause__))]:
                print(f"  coluna: {coluna}  |  valor inválido: {exemplo!r}")
            sys.exit(1)
        except FalhaConferencia as falha:
            con.rollback()
            tabela, divergencias = falha.args
            print("Conferência RAW x REFINED falhou. ROLLBACK executado; nenhuma tabela REFINED foi alterada.")
            print(f"  tabela: {SCHEMA_DESTINO}.{tabela.destino}")
            for coluna, esperado, encontrado in divergencias:
                print(
                    f"  coluna: {coluna}  |  esperado: {_formatar(esperado)}"
                    f"  |  encontrado: {_formatar(encontrado)}"
                )
            sys.exit(1)
        except BaseException:
            con.rollback()
            raise
    finally:
        con.close()

    for tabela, r in resultados:
        _imprimir(tabela, r)

    total_origem = sum(r["origem"] for _, r in resultados)
    total_destino = sum(r["destino"] for _, r in resultados)
    print(f"{'TOTAL':<{LARGURA_ROTULO}}{_formatar(total_origem)} -> {_formatar(total_destino)} linhas")


if __name__ == "__main__":
    main()

"""
pipeline/marts.py — orquestrador da camada MARTS.

SPEC — ORQUESTRADOR DA CAMADA MARTS
-----------------------------------

CONTEXTO
    Projeto: US Aviation Data Pipeline. Spec-driven development: esta SPEC é a
    fonte da verdade e o código é consequência dela.
    Objetivo: materializar as consultas SQL da pasta sql/marts/ como tabelas
    físicas no schema marts do DuckDB. O Python atua exclusivamente como
    orquestrador; nenhuma regra de negócio é implementada nele.

STACK
    Python 3.13, uv, DuckDB. Banco: aviation.duckdb, na raiz do projeto.

O QUE JÁ EXISTE (usar, não reimplementar)
    - pipeline/db.py: conectar() e criar_schema(con, nome).
    - Schema refined, criado por pipeline/transformacao.py, com as tabelas
      refined.companhias_aereas, refined.aeroportos,
      refined.estatisticas_diarias_aeroportos e refined.voos_2025.
    - Pasta sql/marts/ com os arquivos SQL dos indicadores analíticos, que
      contêm as regras de negócio, JOINs, filtros, agregações e cálculos.

ARTEFATO
    pipeline/marts.py — execução: uv run python -m pipeline.marts

1. ESCOPO
   Lê dados exclusivamente do schema refined e materializa os resultados no
   schema marts. Nunca escreve em raw ou refined.
   O schema marts é apagado e recriado a cada execução
   (DROP SCHEMA IF EXISTS marts CASCADE).
   Motivo: se um arquivo SQL for removido da pasta, sua tabela também deve
   desaparecer do banco na próxima execução.

2. UM ARQUIVO, UMA TABELA
   Lê todos os arquivos sql/marts/*.sql em ordem alfabética. Cada arquivo gera
   uma tabela no schema marts, cujo nome é o nome do arquivo sem a extensão
   .sql e sem o prefixo numérico NN_.
     sql/marts/01_aeroportos_taxa_atrasos.sql  -> marts.aeroportos_taxa_atrasos
     sql/marts/10_dias_semana_taxa_atrasos.sql -> marts.dias_semana_taxa_atrasos
   O prefixo serve apenas para ordenar os arquivos; não faz parte do nome.
   Execução: CREATE TABLE marts.<nome> AS <conteúdo do arquivo>.
   O conteúdo é usado integralmente. Antes da execução o Python remove somente
   espaços em branco no início e no final e um ponto e vírgula final, se
   existir. Não altera, monta, completa, interpreta ou modifica a SQL.
   Os arquivos podem começar com comentários (--) e usar CTEs (WITH).
   Motivo: toda a regra de negócio pertence aos arquivos SQL.

3. SAÍDA NA TELA
   Uma linha por tabela criada, com a quantidade de registros consultada no
   DuckDB:  ✓ marts.aeroportos_taxa_atrasos        345 linhas
   Milhares separados por ponto. Ao final:  TOTAL: 10 marts | 25.430 linhas
   O stdout é reconfigurado para UTF-8.
   Motivo: acompanhar a execução e conferir rapidamente os resultados.

4. ERROS E VALIDAÇÕES
   4.1 Tabelas REFINED ausentes: antes de qualquer SQL, verificar as quatro
       tabelas. Se faltar alguma: listar todas as ausentes, orientar a executar
       uv run python -m pipeline.transformacao, sys.exit(1), nenhuma SQL
       executada.
   4.2 Pasta sem arquivos SQL: informar que nenhum arquivo foi encontrado e
       sys.exit(1). Motivo: não substituir um schema válido por um vazio.
   4.3 Nome de arquivo inválido: todos os arquivos devem ter o prefixo NN_
       (ex. válido 01_aeroportos_taxa_atrasos.sql; inválido
       aeroportos_taxa_atrasos.sql). Se houver inválidos: listá-los,
       sys.exit(1), nenhuma SQL executada.
   4.4 Nomes de tabelas duplicados: se dois ou mais arquivos resultarem no
       mesmo nome de tabela, listar os arquivos envolvidos, sys.exit(1),
       nenhuma SQL executada.
   4.5 Erro na execução de um arquivo: mostrar o nome do arquivo e a mensagem
       original do DuckDB, não executar os seguintes, ROLLBACK, sys.exit(1).
   4.6 Mart sem registros: após criar cada tabela, consultar sua contagem; se
       for zero, mostrar o arquivo, informar que o Mart foi criado sem
       registros, ROLLBACK, sys.exit(1).
   4.7 Transação e atomicidade: remoção do schema anterior, criação do novo
       schema, criação de todas as tabelas e validação das contagens ocorrem
       em uma única transação. COMMIT só após tudo concluir; qualquer falha
       gera ROLLBACK e o schema marts volta exatamente ao estado da última
       execução bem-sucedida.

CRITÉRIOS DE ACEITE
    1. sql/marts/00_teste.sql com "SELECT 1 AS x" cria marts.teste com 1 linha.
    2. Apagado o arquivo e executado novamente, marts.teste deixa de existir.
    3. Arquivo com erro de sintaxe interrompe, mostra o arquivo e a mensagem
       do DuckDB; o schema marts permanece como estava.
    4. Arquivo sem prefixo (teste.sql) interrompe antes de qualquer SQL.
    5. Dois arquivos com o mesmo nome de tabela interrompem antes de qualquer SQL.
    6. Mart com zero linhas interrompe e provoca ROLLBACK.
    7. Tabela REFINED ausente: informa qual falta e orienta a transformação.
    8. Pasta sem SQL: informa e encerra sem alterar o schema existente.
    9. Os dez arquivos geram dez tabelas em marts, sem prefixo nos nomes.
   10. Duas execuções consecutivas sem alterações produzem a mesma saída e as
       mesmas tabelas.

RESPONSABILIDADE DO SCRIPT
    Validar pré-requisitos, localizar os arquivos SQL, validar nomes de
    arquivos e tabelas, criar o schema de destino, executar cada consulta,
    materializá-la como tabela, conferir contagens, controlar a transação e
    exibir o resumo. Toda a inteligência analítica permanece nos arquivos SQL.
    Não modifica os arquivos SQL, pipeline/db.py nem pipeline/transformacao.py.
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

import duckdb

from pipeline.db import conectar, criar_schema

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
PASTA_SQL = RAIZ_PROJETO / "sql" / "marts"

SCHEMA_ORIGEM = "refined"
SCHEMA_DESTINO = "marts"
TABELAS_REFINED = (
    "companhias_aereas",
    "aeroportos",
    "estatisticas_diarias_aeroportos",
    "voos_2025",
)

PADRAO_ARQUIVO = re.compile(r"^\d{2}_(.+)\.sql$")


class FalhaMart(Exception):
    """Interrompe a transação; args = (arquivo, mensagem)."""


def _ident(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def _formatar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _tabelas_ausentes(con: duckdb.DuckDBPyConnection) -> list[str]:
    existentes = {
        nome
        for (nome,) in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = ?",
            [SCHEMA_ORIGEM],
        ).fetchall()
    }
    return [f"{SCHEMA_ORIGEM}.{t}" for t in TABELAS_REFINED if t not in existentes]


def _consulta(arquivo: Path) -> str:
    sql = arquivo.read_text(encoding="utf-8").strip()
    if sql.endswith(";"):
        sql = sql[:-1]
    return sql


def _encerrar(*linhas: str) -> None:
    for linha in linhas:
        print(linha)
    sys.exit(1)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    # Validações de arquivos vêm antes de abrir o banco: nenhuma depende dele.
    arquivos = sorted(PASTA_SQL.glob("*.sql"), key=lambda p: p.name)
    if not arquivos:
        _encerrar(f"Nenhum arquivo .sql encontrado em {PASTA_SQL}. Schema marts não alterado.")

    invalidos = [a.name for a in arquivos if not PADRAO_ARQUIVO.match(a.name)]
    if invalidos:
        _encerrar(
            "Arquivos sem o prefixo numérico NN_ (ex.: 01_nome.sql):",
            *(f"  - {nome}" for nome in invalidos),
        )

    por_tabela: dict[str, list[str]] = defaultdict(list)
    for arquivo in arquivos:
        por_tabela[PADRAO_ARQUIVO.match(arquivo.name).group(1)].append(arquivo.name)
    duplicados = {t: nomes for t, nomes in por_tabela.items() if len(nomes) > 1}
    if duplicados:
        linhas = ["Arquivos que geram o mesmo nome de tabela:"]
        for tabela, nomes in duplicados.items():
            linhas.append(f"  {SCHEMA_DESTINO}.{tabela}: {', '.join(nomes)}")
        _encerrar(*linhas)

    con = conectar()
    try:
        ausentes = _tabelas_ausentes(con)
        if ausentes:
            _encerrar(
                "Tabelas REFINED ausentes:",
                *(f"  - {nome}" for nome in ausentes),
                "Execute antes: uv run python -m pipeline.transformacao",
            )

        largura = max(len(f"{SCHEMA_DESTINO}.{t}") for t in por_tabela)
        total_linhas = 0

        con.begin()
        try:
            con.execute(f"DROP SCHEMA IF EXISTS {_ident(SCHEMA_DESTINO)} CASCADE")
            criar_schema(con, SCHEMA_DESTINO)

            for arquivo in arquivos:
                tabela = PADRAO_ARQUIVO.match(arquivo.name).group(1)
                destino = f"{_ident(SCHEMA_DESTINO)}.{_ident(tabela)}"
                try:
                    con.execute(f"CREATE TABLE {destino} AS {_consulta(arquivo)}")
                    linhas = con.execute(f"SELECT COUNT(*) FROM {destino}").fetchone()[0]
                except duckdb.Error as erro:
                    raise FalhaMart(arquivo.name, str(erro)) from erro
                if linhas == 0:
                    raise FalhaMart(arquivo.name, "Mart criado sem registros.")

                total_linhas += linhas
                rotulo = f"{SCHEMA_DESTINO}.{tabela}"
                print(f"✓ {rotulo:<{largura}}  {_formatar(linhas):>12} linhas")

            con.commit()
        except FalhaMart as falha:
            con.rollback()
            arquivo, mensagem = falha.args
            _encerrar(
                "",
                f"✗ Falha no arquivo: {arquivo}",
                f"  {mensagem}",
                "ROLLBACK executado; schema marts mantido como na última execução bem-sucedida.",
            )
        except BaseException:
            con.rollback()
            raise

        print()
        print(f"TOTAL: {_formatar(len(arquivos))} marts | {_formatar(total_linhas)} linhas")
    finally:
        con.close()


if __name__ == "__main__":
    main()

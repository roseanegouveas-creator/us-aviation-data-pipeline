"""
pipeline/db.py — conexão e gravação no DuckDB.

SPEC
----
Objetivo: módulo central responsável exclusivamente pela conexão com o
DuckDB, criação de schemas e gravação de DataFrames. As etapas seguintes
importam este módulo.

D1. CAMINHOS
    - aviation.duckdb é resolvido a partir da localização deste arquivo
      (pipeline/db.py) e fica na raiz do projeto, um nível acima de pipeline/.
    - A pasta de arquivos originais é `Banco/` na raiz do projeto
      (decisão do usuário: a estrutura existente usa Banco/, não Raw/).
    Motivo: executar um script a partir de outra pasta não pode criar um
    banco vazio no local errado.

D2. FUNÇÕES E CONSTANTES — o módulo expõe exatamente:
    - PASTA_RAW: Path da pasta de arquivos originais.
    - conectar(): abre o banco, criando-o caso não exista.
    - criar_schema(con, nome): CREATE SCHEMA IF NOT EXISTS.
    - gravar(con, dados, schema, tabela): grava e devolve a quantidade de
      registros efetivamente gravados.
    Não lê CSV, não conhece nomes de tabelas, não converte tipos, não limpa
    nem exclui dados, não imprime mensagens.
    Motivo: cada etapa decide suas próprias regras; o módulo é reutilizável.

D3. GRAVAÇÃO
    - Recebe conexão, dados, schema e tabela.
    - `dados` é um DataFrame ou um iterável de DataFrames (blocos), para
      permitir arquivos maiores que a memória disponível (decisão do usuário).
    - O primeiro bloco recria a tabela com CREATE OR REPLACE TABLE; os
      blocos seguintes, da MESMA execução, são acrescentados a ela.
    - Tudo ocorre em uma única transação: se falhar, a tabela anterior
      permanece intacta.
    - Preserva colunas e tipos do DataFrame.
    - Devolve SELECT COUNT(*) consultado no banco.
    - Não deixa views ou tabelas temporárias.
    Motivo: a contagem exibida precisa representar o conteúdo efetivamente
    gravado no banco; reexecutar nunca duplica dados.

D4. CONEXÃO
    conectar() devolve uma conexão aberta; quem chama fecha. Sem conexão global.

Critérios de aceite
    - Importar pipeline.db não abre o banco nem cria arquivos.
    - conectar() a partir de outra pasta cria aviation.duckdb na raiz.
    - criar_schema() não gera erro quando o schema já existe.
    - Gravar um DataFrame de três registros devolve três.
    - Gravar novamente substitui os registros, sem duplicar.
"""

from collections.abc import Iterable
from pathlib import Path

import duckdb
import pandas as pd

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
CAMINHO_BANCO = RAIZ_PROJETO / "aviation.duckdb"
PASTA_RAW = RAIZ_PROJETO / "Banco"

__all__ = ["PASTA_RAW", "conectar", "criar_schema", "gravar"]

_VIEW_TEMPORARIA = "_bloco_em_gravacao"


def _ident(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def conectar() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(CAMINHO_BANCO))


def criar_schema(con: duckdb.DuckDBPyConnection, nome: str) -> None:
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {_ident(nome)}")


def gravar(
    con: duckdb.DuckDBPyConnection,
    dados: pd.DataFrame | Iterable[pd.DataFrame],
    schema: str,
    tabela: str,
) -> int:
    destino = f"{_ident(schema)}.{_ident(tabela)}"
    blocos = [dados] if isinstance(dados, pd.DataFrame) else dados

    con.begin()
    try:
        primeiro = True
        for bloco in blocos:
            con.register(_VIEW_TEMPORARIA, bloco)
            try:
                if primeiro:
                    con.execute(
                        f"CREATE OR REPLACE TABLE {destino} AS "
                        f"SELECT * FROM {_VIEW_TEMPORARIA}"
                    )
                    primeiro = False
                else:
                    # BY NAME: garante o alinhamento das colunas entre blocos.
                    con.execute(
                        f"INSERT INTO {destino} BY NAME "
                        f"SELECT * FROM {_VIEW_TEMPORARIA}"
                    )
            finally:
                con.unregister(_VIEW_TEMPORARIA)
        if primeiro:
            raise ValueError(f"Nenhum DataFrame recebido para {schema}.{tabela}.")
        con.commit()
    except BaseException:
        con.rollback()
        raise

    return con.execute(f"SELECT COUNT(*) FROM {destino}").fetchone()[0]

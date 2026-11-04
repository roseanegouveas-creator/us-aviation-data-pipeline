"""
pipeline/ingestao.py — ingestão dos quatro CSVs para o schema raw.

SPEC
----
Objetivo: carregar os arquivos de referência e a amostra de voos para o
schema raw do DuckDB, sem aplicar regras de transformação.

1. ESCOPO E NOMES
   airlines.csv                  -> raw.airlines
   airports.csv                  -> raw.airports
   daily_airport_stats.csv       -> raw.daily_airport_stats
   flights_2025_sample.csv       -> raw.flights_2025

   O arquivo flights_2025.csv não faz parte do pipeline.
   A única fonte de voos é Banco/flights_2025_sample.csv.

2. PRESERVAÇÃO
   Não converter tipos, descartar linhas, deduplicar, renomear colunas,
   corrigir valores, preencher nulos ou aplicar regras de negócio.
   Todas as colunas são importadas como texto.

   2.1 _source_file é coluna de controle do pipeline, não dado recebido:
       recebe o nome do arquivo lido em Banco/ (sem caminho), em todas as
       linhas. Substitui o valor do CSV (ex.: flights.parquet, herdado de
       uma exportação anterior), mantendo nome e posição da coluna; se o
       arquivo não a tiver, é acrescentada ao final. Única exceção à
       proibição de corrigir valores.
       Motivo: rastrear de qual arquivo cada registro entrou no pipeline.
   2.2 _ingested_at permanece como recebido no CSV.
       Motivo: manter a ingestão reprodutível.

3. REEXECUÇÃO
   As tabelas são recriadas a cada execução. A gravação em blocos permite
   ler arquivos grandes sem carregar todo o conteúdo na memória.

4. LEITURA
   Os arquivos são lidos da pasta Banco/, resolvida a partir da raiz do
   projeto. Encoding UTF-8. Campos vazios são nulos; textos como NA, NULL
   e nan permanecem texto.

5. VALIDAÇÃO
   Todos os quatro arquivos são verificados antes de abrir o banco.
   Se algum estiver ausente, a execução termina sem ingestão parcial.

6. EXECUÇÃO
   uv run python -m pipeline.ingestao
"""

import sys

import pandas as pd

from pipeline.db import PASTA_RAW, conectar, criar_schema, gravar

SCHEMA = "raw"

ARQUIVOS = {
    "airlines.csv": "airlines",
    "airports.csv": "airports",
    "daily_airport_stats.csv": "daily_airport_stats",
    "flights_2025_sample.csv": "flights_2025",
}

LINHAS_POR_BLOCO = 500_000
LARGURA_ROTULO = 28
COLUNA_ORIGEM = "_source_file"


def _registrar_origem(blocos, nome_arquivo: str):
    for bloco in blocos:
        bloco[COLUNA_ORIGEM] = nome_arquivo
        yield bloco


def _ler_csv(caminho):
    return pd.read_csv(
        caminho,
        dtype=str,
        encoding="utf-8",
        compression=None,
        keep_default_na=False,
        na_values=[""],
        chunksize=LINHAS_POR_BLOCO,
    )


def _formatar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    ausentes = [nome for nome in ARQUIVOS if not (PASTA_RAW / nome).is_file()]
    if ausentes:
        print("Arquivos obrigatórios ausentes:")
        for nome in ausentes:
            print(f"  - {nome}")
        print(f"Pasta verificada: {PASTA_RAW}")
        sys.exit(1)

    con = conectar()
    try:
        criar_schema(con, SCHEMA)
        total = 0

        for arquivo, tabela in ARQUIVOS.items():
            with _ler_csv(PASTA_RAW / arquivo) as blocos:
                registros = gravar(con, _registrar_origem(blocos, arquivo), SCHEMA, tabela)

            total += registros
            rotulo = f"{SCHEMA.upper()}.{tabela}"
            print(f"{rotulo:<{LARGURA_ROTULO}} | {_formatar(registros)} registros")
    finally:
        con.close()

    print()
    print(f"{'TOTAL':<{LARGURA_ROTULO}} | {_formatar(total)} registros")


if __name__ == "__main__":
    main()

"""
ui.py — interface de exploração do banco pelo navegador.

SPEC
----
U1. Utiliza aviation.duckdb como banco principal e aviation_ui.duckdb
    como banco auxiliar da extensão UI.

U2. O banco principal é anexado em modo READ_ONLY. A interface não altera
    as tabelas do pipeline.

U3. O banco auxiliar é gravável porque a extensão UI armazena informações
    internas, como notebooks e estado da interface.

U4. Se aviation.duckdb não existir, encerra sem criar um banco vazio.

U5. A conexão permanece aberta até CTRL+C. Ao encerrar, fecha a conexão.

U6. A interface não executa a ingestão. O banco deve ser reconstruído antes
    de iniciar a UI, usando pipeline.ingestao.

U7. A fonte oficial dos registros de voos do projeto é
    data/raw/flights_2025_sample.csv, carregada em raw.flights_2025.

U8. Utiliza a porta 4213 e abre o navegador automaticamente.
"""

import sys
import time
import webbrowser
from pathlib import Path

import duckdb

PASTA_PROJETO = Path(__file__).resolve().parent.parent

CAMINHO_BANCO = PASTA_PROJETO / "aviation.duckdb"
CAMINHO_UI = PASTA_PROJETO / "aviation_ui.duckdb"

PORTA = 4213
URL = f"http://localhost:{PORTA}"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    if not CAMINHO_BANCO.is_file():
        print(f"Banco não encontrado: {CAMINHO_BANCO}")
        print("Reconstrua o banco executando:")
        print("uv run python -m pipeline.ingestao")
        sys.exit(1)

    con = duckdb.connect(str(CAMINHO_UI))

    try:
        con.execute("INSTALL ui")
        con.execute("LOAD ui")

        caminho = str(CAMINHO_BANCO).replace("\\", "/").replace("'", "''")
        con.execute(f"ATTACH '{caminho}' AS aviation (READ_ONLY)")
        con.execute("USE aviation")
        con.execute(f"SET ui_local_port = {PORTA}")
        con.execute("CALL start_ui()")

        print("US Aviation Data Pipeline")
        print()
        print(f"Banco principal: {CAMINHO_BANCO.name}")
        print("Fonte dos voos: data/raw/flights_2025_sample.csv")
        print("Tabela de voos: raw.flights_2025")
        print(f"Banco auxiliar: {CAMINHO_UI.name}")
        print(f"Interface: {URL}")
        print()
        print("Pressione Ctrl+C para encerrar.")

        webbrowser.open(URL)

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nEncerrando interface...")

    finally:
        con.close()
        print("Conexão encerrada.")


if __name__ == "__main__":
    main()

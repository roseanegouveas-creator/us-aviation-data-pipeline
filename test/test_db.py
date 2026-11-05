"""Testes de pipeline/db.py — critérios D1 a D4 da SPEC.

Todo banco é criado em tmp_path; db.CAMINHO_BANCO é redirecionado antes de
qualquer chamada a conectar(). aviation.duckdb nunca é aberto.
"""

import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from pipeline import db

RAIZ = Path(__file__).resolve().parent.parent


def _banco_temporario(tmp_path, monkeypatch, nome="teste.duckdb"):
    caminho = tmp_path / nome
    monkeypatch.setattr(db, "CAMINHO_BANCO", caminho)
    return caminho


def _tres_registros():
    # Três registros com tipos distintos (texto, inteiro, decimal, data, booleano).
    return pd.DataFrame(
        {
            "codigo": ["AAA", "BBB", "CCC"],
            "quantidade": pd.Series([1, 2, 3], dtype="int64"),
            "taxa": [0.5, 1.25, 2.0],
            "data": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"]),
            "ativo": [True, False, True],
        }
    )


# ------------------------------------------------------------------ D1 / D2


def test_importar_pipeline_db_nao_abre_banco_nem_cria_arquivos(tmp_path):
    # Processo separado, com a pasta de trabalho vazia: o import não pode criar nada.
    resultado = subprocess.run(
        [sys.executable, "-c", "import pipeline.db"],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(RAIZ)},
        capture_output=True,
        check=False,
        text=True,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert list(tmp_path.iterdir()) == []


def test_caminho_do_banco_e_resolvido_pela_raiz_do_projeto_e_nao_pela_pasta_atual():
    # D1: aviation.duckdb fica um nível acima de pipeline/; Banco/ também na raiz.
    raiz = Path(db.__file__).resolve().parent.parent
    assert db.CAMINHO_BANCO == raiz / "aviation.duckdb"
    assert db.PASTA_RAW == raiz / "Banco"


def test_modulo_expoe_exatamente_pasta_raw_conectar_criar_schema_e_gravar():
    assert db.__all__ == ["PASTA_RAW", "conectar", "criar_schema", "gravar"]


def test_conectar_a_partir_de_outra_pasta_cria_o_banco_no_caminho_configurado(
    tmp_path, monkeypatch
):
    raiz = tmp_path / "raiz"
    raiz.mkdir()
    outra = tmp_path / "outra_pasta"
    outra.mkdir()
    monkeypatch.setattr(db, "CAMINHO_BANCO", raiz / "aviation.duckdb")
    monkeypatch.chdir(outra)

    con = db.conectar()
    con.close()

    assert (raiz / "aviation.duckdb").is_file()
    assert list(outra.iterdir()) == []


def test_conectar_devolve_conexao_aberta_que_quem_chama_fecha(tmp_path, monkeypatch):
    _banco_temporario(tmp_path, monkeypatch)
    con = db.conectar()
    assert con.execute("SELECT 42").fetchone()[0] == 42
    con.close()
    with pytest.raises(duckdb.ConnectionException):
        con.execute("SELECT 1")


def test_conectar_nao_mantem_conexao_global(tmp_path, monkeypatch):
    # D4: cada chamada devolve uma conexão nova; fechar uma não afeta a outra.
    _banco_temporario(tmp_path, monkeypatch)
    primeira = db.conectar()
    segunda = db.conectar()
    assert primeira is not segunda
    primeira.close()
    assert segunda.execute("SELECT 1").fetchone()[0] == 1
    segunda.close()


# ------------------------------------------------------------------ criar_schema


def test_criar_schema_nao_gera_erro_quando_o_schema_ja_existe(tmp_path, monkeypatch):
    _banco_temporario(tmp_path, monkeypatch)
    con = db.conectar()
    try:
        db.criar_schema(con, "raw")
        db.criar_schema(con, "raw")
        schemas = con.execute(
            "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name = 'raw'"
        ).fetchone()[0]
    finally:
        con.close()
    assert schemas == 1


# ------------------------------------------------------------------ D3 gravar


def test_gravar_dataframe_de_tres_registros_devolve_tres(tmp_path, monkeypatch):
    _banco_temporario(tmp_path, monkeypatch)
    con = db.conectar()
    try:
        db.criar_schema(con, "raw")
        assert db.gravar(con, _tres_registros(), "raw", "exemplo") == 3
    finally:
        con.close()


def test_gravar_novamente_substitui_os_registros_sem_duplicar(tmp_path, monkeypatch):
    _banco_temporario(tmp_path, monkeypatch)
    con = db.conectar()
    try:
        db.criar_schema(con, "raw")
        db.gravar(con, _tres_registros(), "raw", "exemplo")
        # Segunda gravação com apenas um registro: a tabela passa a ter só ele.
        devolvido = db.gravar(con, _tres_registros().head(1), "raw", "exemplo")
        codigos = con.execute("SELECT codigo FROM raw.exemplo").fetchall()
    finally:
        con.close()
    assert devolvido == 1
    assert codigos == [("AAA",)]


def test_gravar_preserva_colunas_e_tipos_do_dataframe(tmp_path, monkeypatch):
    _banco_temporario(tmp_path, monkeypatch)
    con = db.conectar()
    try:
        db.criar_schema(con, "raw")
        db.gravar(con, _tres_registros(), "raw", "exemplo")
        colunas = con.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'raw' AND table_name = 'exemplo' ORDER BY ordinal_position"
        ).fetchall()
    finally:
        con.close()
    assert [c for c, _ in colunas] == ["codigo", "quantidade", "taxa", "data", "ativo"]
    tipos = dict(colunas)
    assert tipos["codigo"] == "VARCHAR"
    assert tipos["quantidade"] == "BIGINT"
    assert tipos["taxa"] == "DOUBLE"
    assert tipos["data"].startswith("TIMESTAMP")
    assert tipos["ativo"] == "BOOLEAN"


def test_gravar_em_blocos_acrescenta_os_blocos_seguintes_da_mesma_execucao(
    tmp_path, monkeypatch
):
    _banco_temporario(tmp_path, monkeypatch)
    # Três blocos (2 + 1 + 2 linhas); o terceiro com colunas em outra ordem (BY NAME).
    blocos = [
        pd.DataFrame({"a": ["1", "2"], "b": ["x", "y"]}),
        pd.DataFrame({"a": ["3"], "b": ["z"]}),
        pd.DataFrame({"b": ["w", "v"], "a": ["4", "5"]}),
    ]
    con = db.conectar()
    try:
        db.criar_schema(con, "raw")
        total = db.gravar(con, iter(blocos), "raw", "blocos")
        linhas = con.execute("SELECT a, b FROM raw.blocos ORDER BY a").fetchall()
    finally:
        con.close()
    assert total == 5
    assert linhas == [("1", "x"), ("2", "y"), ("3", "z"), ("4", "w"), ("5", "v")]


def test_gravar_devolve_a_contagem_consultada_no_banco(tmp_path, monkeypatch):
    _banco_temporario(tmp_path, monkeypatch)
    con = db.conectar()
    try:
        db.criar_schema(con, "raw")
        devolvido = db.gravar(con, _tres_registros(), "raw", "exemplo")
        no_banco = con.execute("SELECT COUNT(*) FROM raw.exemplo").fetchone()[0]
    finally:
        con.close()
    assert devolvido == no_banco


def test_falha_em_um_bloco_mantem_a_tabela_anterior_intacta(tmp_path, monkeypatch):
    _banco_temporario(tmp_path, monkeypatch)
    con = db.conectar()
    try:
        db.criar_schema(con, "raw")
        db.gravar(con, _tres_registros(), "raw", "exemplo")

        # Primeiro bloco válido; segundo com coluna inexistente: o INSERT BY NAME falha.
        blocos = [
            pd.DataFrame({"codigo": ["NOVO"]}),
            pd.DataFrame({"coluna_inexistente": ["X"]}),
        ]
        with pytest.raises(duckdb.Error):
            db.gravar(con, blocos, "raw", "exemplo")

        codigos = con.execute("SELECT codigo FROM raw.exemplo ORDER BY codigo").fetchall()
    finally:
        con.close()
    assert codigos == [("AAA",), ("BBB",), ("CCC",)]


def test_iteravel_sem_dataframes_gera_erro_e_preserva_tabela_anterior(
    tmp_path, monkeypatch
):
    _banco_temporario(tmp_path, monkeypatch)
    con = db.conectar()
    try:
        db.criar_schema(con, "raw")
        db.gravar(con, _tres_registros(), "raw", "exemplo")
        with pytest.raises(ValueError, match="raw.exemplo"):
            db.gravar(con, [], "raw", "exemplo")
        restantes = con.execute("SELECT COUNT(*) FROM raw.exemplo").fetchone()[0]
    finally:
        con.close()
    assert restantes == 3


def test_gravar_nao_deixa_views_ou_tabelas_temporarias(tmp_path, monkeypatch):
    _banco_temporario(tmp_path, monkeypatch)
    con = db.conectar()
    try:
        db.criar_schema(con, "raw")
        db.gravar(con, [_tres_registros(), _tres_registros()], "raw", "exemplo")
        views = con.execute(
            "SELECT view_name FROM duckdb_views() WHERE NOT internal"
        ).fetchall()
        tabelas = con.execute(
            "SELECT schema_name, table_name FROM duckdb_tables()"
        ).fetchall()
    finally:
        con.close()
    assert views == []
    assert tabelas == [("raw", "exemplo")]

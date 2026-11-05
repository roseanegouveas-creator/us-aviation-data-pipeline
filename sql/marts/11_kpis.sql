
-- ============================================================
-- MART 11: KPIs GERAIS DA OPERACAO AEREA
-- ============================================================
-- Pergunta: como esta a operacao aerea como um todo?
--
-- Grao: operacao inteira, uma unica linha.
--
-- Indicadores:
-- - total_voos: quantidade total de voos.
-- - pct_atrasos: percentual de voos atrasados em 15 minutos
--   ou mais, excluindo cancelados e registros sem classificacao.
-- - pct_cancelamentos: percentual de voos cancelados sobre
--   o total de voos.
-- - atraso_medio_minutos: media de atraso dos voos com
--   atraso igual ou superior a 15 minutos, excluindo cancelados.
-- - total_companhias: quantidade de companhias cadastradas.
-- - total_aeroportos: quantidade de aeroportos cadastrados.
--
-- Cada CTE retorna uma unica linha.
-- Por isso, as CTEs podem ser combinadas sem ON.
-- O resultado final deve conter exatamente uma linha.
-- ============================================================

WITH indicadores_voos AS (
    SELECT
        COUNT(*) AS total_voos,

        ROUND(
            100.0 * COUNT(*) FILTER (
                WHERE atraso_partida_15min = 1
                  AND cancelado = FALSE
            )
            / NULLIF(
                COUNT(*) FILTER (
                    WHERE cancelado = FALSE
                      AND atraso_partida_15min IS NOT NULL
                ),
                0
            ),
            2
        ) AS pct_atrasos,

        ROUND(
            100.0 * COUNT(*) FILTER (
                WHERE cancelado = TRUE
            )
            / NULLIF(COUNT(*), 0),
            2
        ) AS pct_cancelamentos,

        ROUND(
            AVG(atraso_partida) FILTER (
                WHERE atraso_partida_15min = 1
                  AND cancelado = FALSE
            ),
            2
        ) AS atraso_medio_minutos

    FROM refined.voos_2025
),

indicadores_companhias AS (
    SELECT
        COUNT(DISTINCT codigo_companhia) AS total_companhias
    FROM refined.companhias_aereas
),

indicadores_aeroportos AS (
    SELECT
        COUNT(DISTINCT codigo_iata) AS total_aeroportos
    FROM refined.aeroportos
)

SELECT
    v.total_voos,
    v.pct_atrasos,
    v.pct_cancelamentos,
    v.atraso_medio_minutos,
    c.total_companhias,
    a.total_aeroportos

FROM indicadores_voos AS v,
     indicadores_companhias AS c,
     indicadores_aeroportos AS a;

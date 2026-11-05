
-- ============================================================
-- MART 12: OPERACAO AEREA POR ESTADO
-- ============================================================
-- Pergunta: em quais estados esta concentrada a operacao aerea?
--
-- Grao: um estado de origem.
--
-- Indicadores:
-- - estado: UF ou nome do estado do aeroporto de origem.
-- - total_voos: quantidade de voos originados no estado.
-- - pct_atrasos: percentual de voos atrasados em 15 minutos
--   ou mais, excluindo cancelados e registros sem classificacao.
-- - pct_cancelamentos: percentual de voos cancelados sobre
--   o total de voos originados no estado.
--
-- O estado e obtido pelo relacionamento entre o codigo IATA
-- do aeroporto de origem e a tabela de aeroportos.
--
-- ATENCAO:
-- A soma de voos por estado representa voos por estado de origem.
-- Cada voo e contabilizado somente no estado de seu aeroporto
-- de origem, nao no estado de destino.
-- ============================================================

SELECT
    a.estado AS estado,

    COUNT(*) AS total_voos,

    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE v.atraso_partida_15min = 1
              AND v.cancelado = FALSE
        )
        / NULLIF(
            COUNT(*) FILTER (
                WHERE v.cancelado = FALSE
                  AND v.atraso_partida_15min IS NOT NULL
            ),
            0
        ),
        2
    ) AS pct_atrasos,

    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE v.cancelado = TRUE
        )
        / NULLIF(COUNT(*), 0),
        2
    ) AS pct_cancelamentos

FROM refined.voos_2025 AS v

LEFT JOIN refined.aeroportos AS a
    ON v.origem = a.codigo_iata

GROUP BY a.estado

ORDER BY total_voos DESC;

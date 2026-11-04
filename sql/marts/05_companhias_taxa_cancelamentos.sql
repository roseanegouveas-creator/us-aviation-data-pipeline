-- Quais companhias aereas apresentam a maior taxa de cancelamentos?
-- Grao: uma companhia aerea com pelo menos 100 voos registrados, uma linha.
-- Denominador: todos os voos registrados da companhia, incluindo cancelados.
-- Cancelado: cancelado = TRUE.

SELECT
    c.codigo_companhia,
    c.companhia_aerea,

    COUNT(*) AS total_voos,

    COUNT(*) FILTER (
        WHERE v.cancelado = TRUE
    ) AS voos_cancelados,

    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE v.cancelado = TRUE
        ) / NULLIF(COUNT(*), 0),
        2
    ) AS taxa_cancelamentos_percentual

FROM refined.voos_2025 AS v

INNER JOIN refined.companhias_aereas AS c
    ON v.codigo_companhia = c.codigo_companhia

GROUP BY
    c.codigo_companhia,
    c.companhia_aerea


ORDER BY taxa_cancelamentos_percentual DESC;

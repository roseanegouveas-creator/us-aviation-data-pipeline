-- Quais aeroportos apresentam a maior taxa de cancelamentos?
-- Grao: um aeroporto de origem, uma linha.
-- Denominador: todos os voos registrados com origem no aeroporto, incluindo cancelados.
-- Cancelado: cancelado = TRUE.

SELECT
    a.codigo_iata,
    a.nome_aeroporto,
    a.cidade,
    a.estado,

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

INNER JOIN refined.aeroportos AS a
    ON v.origem = a.codigo_iata

GROUP BY
    a.codigo_iata,
    a.nome_aeroporto,
    a.cidade,
    a.estado

ORDER BY taxa_cancelamentos_percentual DESC;

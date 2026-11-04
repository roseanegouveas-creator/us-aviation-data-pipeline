-- Quais aeroportos apresentam a maior taxa de atrasos nas partidas?
-- Grao: um aeroporto de origem, uma linha.
-- Denominador: voos nao cancelados com origem no aeroporto.
-- Atrasado: partida com atraso de 15 minutos ou mais (atraso_partida_15min = 1).

SELECT
    a.codigo_iata,
    a.nome_aeroporto,
    a.cidade,
    a.estado,

    COUNT(*) AS total_voos,

    COUNT(*) FILTER (
        WHERE v.atraso_partida_15min = 1
    ) AS voos_atrasados,

    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE v.atraso_partida_15min = 1
        ) / NULLIF(COUNT(*), 0),
        2
    ) AS taxa_atrasos_percentual

FROM refined.voos_2025 AS v

INNER JOIN refined.aeroportos AS a
    ON v.origem = a.codigo_iata

WHERE v.cancelado = FALSE

GROUP BY
    a.codigo_iata,
    a.nome_aeroporto,
    a.cidade,
    a.estado

ORDER BY taxa_atrasos_percentual DESC;

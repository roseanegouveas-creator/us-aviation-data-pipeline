-- Quais companhias aereas apresentam a maior taxa de atrasos nas partidas?
-- Grao: uma companhia aerea, uma linha.
-- Denominador: voos nao cancelados operados pela companhia.
-- Atrasado: partida com atraso de 15 minutos ou mais (atraso_partida_15min = 1).

SELECT
    c.codigo_companhia,
    c.companhia_aerea,

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

INNER JOIN refined.companhias_aereas AS c
    ON v.codigo_companhia = c.codigo_companhia

WHERE v.cancelado = FALSE

GROUP BY
    c.codigo_companhia,
    c.companhia_aerea
    
ORDER BY taxa_atrasos_percentual DESC;

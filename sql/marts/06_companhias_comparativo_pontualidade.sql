-- Qual e a pontualidade de cada companhia aerea?
-- Grao: uma companhia aerea com pelo menos 100 voos elegiveis, uma linha.
-- Denominador: voos nao cancelados com classificacao de atraso_partida_15min preenchida.
-- Pontual: atraso_partida_15min = 0 (atraso inferior a 15 minutos, incluindo partida no horario).
-- Atrasado: atraso_partida_15min = 1 (atraso de 15 minutos ou mais).
-- A media de atraso considera atraso_partida dos voos elegiveis; valores NULL sao ignorados pelo AVG.

SELECT
    c.codigo_companhia,
    c.companhia_aerea,

    COUNT(*) AS total_voos,

    COUNT(*) FILTER (
        WHERE v.atraso_partida_15min = 0
    ) AS voos_pontuais,

    COUNT(*) FILTER (
        WHERE v.atraso_partida_15min = 1
    ) AS voos_atrasados,

    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE v.atraso_partida_15min = 0
        ) / NULLIF(COUNT(*), 0),
        2
    ) AS taxa_pontualidade_percentual,

    ROUND(
        AVG(v.atraso_partida),
        2
    ) AS media_atraso_minutos

FROM refined.voos_2025 AS v

INNER JOIN refined.companhias_aereas AS c
    ON v.codigo_companhia = c.codigo_companhia

WHERE v.cancelado = FALSE
  AND v.atraso_partida_15min IS NOT NULL

GROUP BY
    c.codigo_companhia,
    c.companhia_aerea

HAVING COUNT(*) >= 100

ORDER BY taxa_pontualidade_percentual DESC;

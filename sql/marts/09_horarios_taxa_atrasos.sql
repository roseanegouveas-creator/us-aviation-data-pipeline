-- Em quais faixas horarias de partida ocorre a maior taxa de atrasos?
-- Grao: uma faixa horaria programada de partida, uma linha.
-- Denominador: voos nao cancelados com faixa_horario_partida preenchida.
-- Atrasado: partida com atraso de 15 minutos ou mais (atraso_partida_15min = 1).
-- A faixa e apresentada no formato HH:MM - HH:MM; a origem do valor continua sendo faixa_horario_partida.

SELECT
    SUBSTRING(v.faixa_horario_partida, 1, 2)
        || ':' ||
    SUBSTRING(v.faixa_horario_partida, 3, 2)
        || ' - ' ||
    SUBSTRING(v.faixa_horario_partida, 6, 2)
        || ':' ||
    SUBSTRING(v.faixa_horario_partida, 8, 2)
        AS faixa_horario_partida,

    COUNT(*) AS total_voos,

    COUNT(*) FILTER (
        WHERE v.atraso_partida_15min = 1
    ) AS voos_atrasados,

    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE v.atraso_partida_15min = 1
        ) / NULLIF(COUNT(*), 0),
        2
    ) AS taxa_atrasos_percentual,

    ROUND(
        AVG(v.atraso_partida),
        2
    ) AS media_atraso_minutos

FROM refined.voos_2025 AS v

WHERE v.cancelado = FALSE
  AND v.faixa_horario_partida IS NOT NULL

GROUP BY v.faixa_horario_partida


ORDER BY taxa_atrasos_percentual DESC;

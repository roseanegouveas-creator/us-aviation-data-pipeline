-- Quais dias da semana apresentam a maior taxa de atrasos nas partidas?
-- Grao: um dia da semana, uma linha.
-- Denominador: voos nao cancelados com classificacao de atraso_partida_15min preenchida.
-- Atrasado: partida com atraso de 15 minutos ou mais (atraso_partida_15min = 1).
-- A numeracao dos dias segue a correspondencia definida no CASE desta consulta: 1 = domingo ate 7 = sabado.

SELECT
    v.dia_semana,

    CASE v.dia_semana
        WHEN 1 THEN 'Domingo'
        WHEN 2 THEN 'Segunda-feira'
        WHEN 3 THEN 'Terca-feira'
        WHEN 4 THEN 'Quarta-feira'
        WHEN 5 THEN 'Quinta-feira'
        WHEN 6 THEN 'Sexta-feira'
        WHEN 7 THEN 'Sabado'
    END AS nome_dia_semana,

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
  AND v.atraso_partida_15min IS NOT NULL

GROUP BY
    v.dia_semana


ORDER BY taxa_atrasos_percentual DESC;

-- Quais aeroportos apresentam o maior tempo medio de atraso nas partidas?
-- Grao: um aeroporto de origem com pelo menos 100 voos atrasados (15 minutos ou mais), uma linha.
-- Base do calculo: somente voos nao cancelados, com atraso_partida_15min = 1 e atraso_partida preenchido.
-- Media: media dos minutos de atraso apenas entre esses voos atrasados.
-- Observacao: nesta consulta, total_voos representa a quantidade de voos atrasados considerados, devido aos filtros do WHERE.

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
        AVG(v.atraso_partida),
        2
    ) AS tempo_medio_atraso_minutos

FROM refined.voos_2025 AS v

INNER JOIN refined.aeroportos AS a
    ON v.origem = a.codigo_iata

WHERE v.cancelado = FALSE
  AND v.atraso_partida_15min = 1
  AND v.atraso_partida IS NOT NULL

GROUP BY
    a.codigo_iata,
    a.nome_aeroporto,
    a.cidade,
    a.estado
    
--critério mínimo de volume 100 voos por aeroporto   

HAVING COUNT(*) >= 100

ORDER BY tempo_medio_atraso_minutos DESC;

-- Quais rotas apresentam a maior taxa de atrasos nas partidas?
-- Grao: uma combinacao de aeroporto de origem e aeroporto de destino com pelo menos 100 voos, uma linha.
-- Denominador: voos nao cancelados registrados na rota.
-- Atrasado: partida com atraso de 15 minutos ou mais (atraso_partida_15min = 1).

SELECT
    origem.codigo_iata AS codigo_origem,
    origem.nome_aeroporto AS aeroporto_origem,
    origem.cidade AS cidade_origem,

    destino.codigo_iata AS codigo_destino,
    destino.nome_aeroporto AS aeroporto_destino,
    destino.cidade AS cidade_destino,

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

INNER JOIN refined.aeroportos AS origem
    ON v.origem = origem.codigo_iata

INNER JOIN refined.aeroportos AS destino
    ON v.destino = destino.codigo_iata

WHERE v.cancelado = FALSE

GROUP BY
    origem.codigo_iata,
    origem.nome_aeroporto,
    origem.cidade,
    destino.codigo_iata,
    destino.nome_aeroporto,
    destino.cidade

--rotas com pelo menos 100 voos

HAVING COUNT(*) >= 100

ORDER BY taxa_atrasos_percentual DESC;

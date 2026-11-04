-- Quais rotas concentram a maior quantidade de voos cancelados?
-- Grao: uma combinacao de aeroporto de origem e aeroporto de destino com pelo menos 100 voos, uma linha.
-- Denominador da taxa: todos os voos registrados na rota, incluindo cancelados.
-- Cancelado: cancelado = TRUE.
-- Ordenacao: maior quantidade de cancelamentos; em caso de empate, maior taxa de cancelamento.

SELECT
    origem.codigo_iata AS codigo_origem,
    origem.nome_aeroporto AS aeroporto_origem,
    origem.cidade AS cidade_origem,

    destino.codigo_iata AS codigo_destino,
    destino.nome_aeroporto AS aeroporto_destino,
    destino.cidade AS cidade_destino,

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

INNER JOIN refined.aeroportos AS origem
    ON v.origem = origem.codigo_iata

INNER JOIN refined.aeroportos AS destino
    ON v.destino = destino.codigo_iata

GROUP BY
    origem.codigo_iata,
    origem.nome_aeroporto,
    origem.cidade,
    destino.codigo_iata,
    destino.nome_aeroporto,
    destino.cidade
    
--Pelo menos 100 voos por rota

HAVING COUNT(*) >= 100

ORDER BY
    voos_cancelados DESC,
    taxa_cancelamentos_percentual DESC;

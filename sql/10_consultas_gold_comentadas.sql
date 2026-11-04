-- ============================================================
-- 01_aeroportos_taxa_atrasos.sql
-- ============================================================

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



-- ============================================================
-- 02_aeroportos_taxa_cancelamentos.sql
-- ============================================================

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



-- ============================================================
-- 03_aeroportos_tempo_medio_atraso.sql
-- ============================================================

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



-- ============================================================
-- 04_companhias_taxa_atrasos.sql
-- ============================================================

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



-- ============================================================
-- 05_companhias_taxa_cancelamentos.sql
-- ============================================================

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

HAVING COUNT(*) >= 100

ORDER BY taxa_cancelamentos_percentual DESC;



-- ============================================================
-- 06_companhias_comparativo_pontualidade.sql
-- ============================================================

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



-- ============================================================
-- 07_rotas_taxa_atrasos.sql
-- ============================================================

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



-- ============================================================
-- 08_rotas_quantidade_cancelamentos.sql
-- ============================================================

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



-- ============================================================
-- 09_horarios_taxa_atrasos.sql
-- ============================================================

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



-- ============================================================
-- 10_dias_semana_taxa_atrasos.sql
-- ============================================================

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



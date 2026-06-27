{{
    config(materialized='table')
}}
-- Pre-aggregated market KPIs for the Executive Overview dashboard.
-- One row per (issue_date × notice_type × buyer_country_code × cpv_division).
-- Materialised as a table so dashboard queries are instant on load.

select
    issue_date,
    notice_type,
    buyer_country_code,
    cpv_division,
    max(cpv_name)                               as cpv_name,
    procurement_type,

    count(distinct notice_publication_id)       as notices,
    count(*)                                    as lots,
    sum(lot_value_eur)                          as total_value_eur,
    avg(lot_value_eur)                          as avg_lot_value_eur

from {{ ref('silver_lots_enriched') }}
where issue_date is not null
group by
    issue_date,
    notice_type,
    buyer_country_code,
    cpv_division,
    procurement_type

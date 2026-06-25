-- Aggregated award outcomes by winner for the Supplier & Awards page.
-- One row per (tenderer_name × tenderer_country_code).
-- Kept as a view — small result set, fast to compute from silver.

select
    tenderer_name,
    tenderer_country_code,

    count(distinct notice_publication_id)       as awards,
    count(distinct buyer_country_code)          as buyer_countries,

    sum(lot_value_eur)                          as total_won_eur,
    avg(lot_value_eur)                          as avg_contract_eur,
    max(lot_value_eur)                          as largest_contract_eur,

    -- CPV breakdown: which divisions does this winner operate in?
    collect_set(cpv_division)                   as cpv_divisions

from {{ ref('silver_lots_enriched') }}
where notice_type   = 'ContractAwardNotice'
  and tenderer_name is not null
group by tenderer_name, tenderer_country_code
order by total_won_eur desc nulls last

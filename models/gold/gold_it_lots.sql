{{
    config(materialized='table')
}}
-- IT-relevant open tenders (CPV divisions 72, 48, 30) for the Opportunity Radar.
-- One row per lot. The opportunity_score column is NULL until Bojana's XGBoost model
-- writes to capstone.ted.gold_opportunity_scores — at that point update this model to
-- join on (notice_publication_id, lot_id) and pull the score across.

with it_lots as (

    select *
    from {{ ref('silver_lots_enriched') }}
    where notice_type = 'ContractNotice'
      and cpv_division in ('72', '48', '30')

)

select
    notice_publication_id,
    lot_id,
    lot_name,
    description,
    issue_date,
    submission_deadline_date,

    -- Classification
    cpv_code,
    cpv_name,
    cpv_division,
    procurement_type,
    procurement_procedure,
    buyer_legal_type,

    -- Value
    lot_value_eur,

    -- Buyer
    buyer_name,
    buyer_country_code,
    buyer_org_ref,

    -- Simple log-scaled value proxy (0–10) until the ML score is wired in.
    -- ln(50M) ≈ 17.7 so a €50M contract → score 10; €100K → ~4.7; null → null.
    case
        when lot_value_eur is null then null
        else round(
            least(ln(greatest(lot_value_eur, 1)) / ln(50000000) * 10, 10), 2
        )
    end                     as value_proxy_score,

    -- Placeholder: replaced by ML output table once available
    cast(null as double)    as opportunity_score,
    cast(null as string)    as predicted_competition

from it_lots
order by lot_value_eur desc nulls last

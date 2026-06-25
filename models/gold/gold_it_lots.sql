{{
    config(materialized='table')
}}
-- IT-relevant open tenders (CPV divisions 72, 48, 30) for the Opportunity Radar.
-- One row per lot, joined to Bojana's ML scores from gold_opportunity_scores.
-- opportunity_score and predicted_competition are null until the ML pipeline has run.

with it_lots as (

    select *
    from {{ ref('silver_lots_enriched') }}
    where notice_type = 'ContractNotice'
      and cpv_division in ('72', '48', '30')

)

select
    l.notice_publication_id,
    l.lot_id,
    l.lot_name,
    l.description,
    l.issue_date,
    l.submission_deadline_date,

    -- Classification
    l.cpv_code,
    l.cpv_name,
    l.cpv_division,
    l.procurement_type,
    l.procurement_procedure,
    l.buyer_legal_type,

    -- Value
    l.lot_value_eur,

    -- Buyer
    l.buyer_name,
    l.buyer_country_code,
    l.buyer_org_ref,

    -- Competition feature
    l.nb_tenders_received,

    -- Simple log-scaled value proxy (0–10); shown when ML score is absent.
    case
        when l.lot_value_eur is null then null
        else round(
            least(ln(greatest(l.lot_value_eur, 1)) / ln(50000000) * 10, 10), 2
        )
    end                         as value_proxy_score,

    -- ML scores from Bojana's XGBoost pipeline (null until first ML run)
    ml.expected_value           as opportunity_score,
    ml.p_low_competition        as predicted_competition

from it_lots l
left join capstone.ted.gold_opportunity_scores ml
    on  l.notice_publication_id = ml.notice_publication_id
    and l.lot_id                = ml.lot_id
order by coalesce(ml.expected_value, l.lot_value_eur) desc nulls last

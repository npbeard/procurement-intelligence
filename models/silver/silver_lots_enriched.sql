-- Lot-level Silver model — the primary input for ML feature engineering.
-- One row per lot, enriched with notice context, buyer info, CPV name,
-- and tenderer identity (populated only for contract award notices).
with lots as (

    select * from {{ ref('bronze_lots') }}

),

notices as (

    select
        notice_publication_id,
        notice_type,
        subtype_code,
        issue_date,
        buyer_org_ref,
        buyer_legal_type,
        procurement_procedure,
        estimated_value,
        estimated_currency,
        total_value,
        total_currency
    from {{ ref('bronze_notices') }}
    qualify row_number() over (
        partition by notice_publication_id
        order by issue_date desc, source_file desc
    ) = 1

),

organizations as (

    select
        notice_publication_id,
        org_ref,
        name,
        country_code
    from {{ ref('bronze_organizations') }}
    qualify row_number() over (
        partition by notice_publication_id, org_ref
        order by name
    ) = 1

)

select
    -- Lot identity
    l.notice_publication_id,
    l.lot_id,
    l.name                              as lot_name,
    l.description,

    -- Notice context
    n.notice_type,
    n.subtype_code,
    n.issue_date,
    n.buyer_legal_type,
    n.procurement_procedure,
    l.procurement_type,
    l.status,
    l.submission_deadline_date,

    -- CPV classification
    l.cpv_code,
    cpv.name                            as cpv_name,
    left(l.cpv_code, 2)                 as cpv_division,

    -- Contract value (lot level; EUR passthrough, nulled otherwise)
    l.value                             as lot_value,
    l.currency                          as lot_currency,
    case when l.currency = 'EUR' then l.value end as lot_value_eur,

    -- Notice-level value fallbacks
    n.estimated_value,
    n.estimated_currency,
    n.total_value,
    n.total_currency,

    -- Buyer
    n.buyer_org_ref,
    buyer.name                          as buyer_name,
    buyer.country_code                  as buyer_country_code,

    -- Winner (present only in CAN award notices)
    l.tenderer_org_ref,
    winner.name                         as tenderer_name,
    winner.country_code                 as tenderer_country_code

from lots l
left join notices n
    using (notice_publication_id)
left join organizations buyer
    on  l.notice_publication_id = buyer.notice_publication_id
    and n.buyer_org_ref = buyer.org_ref
left join organizations winner
    on  l.notice_publication_id = winner.notice_publication_id
    and l.tenderer_org_ref = winner.org_ref
left join {{ ref('cpv_codes') }} cpv
    on l.cpv_code = cpv.code

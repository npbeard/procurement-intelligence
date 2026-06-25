with latest_notices as (

    select
        notice_publication_id,
        notice_type,
        subtype_code,
        issue_date,
        publication_date,
        language,
        regulatory_domain,
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
        order by issue_date desc, publication_date desc, source_file desc
    ) = 1

),

buyer_organizations as (

    select
        notice_publication_id,
        org_ref,
        name,
        city,
        country_code
    from {{ ref('bronze_organizations') }}
    qualify row_number() over (
        partition by notice_publication_id, org_ref
        order by name
    ) = 1

),

-- Pick the CPV from the highest-value lot as the notice's primary CPV.
-- Falls back to lot_id order when value is null.
primary_cpv as (

    select
        notice_publication_id,
        cpv_code as primary_cpv_code
    from {{ ref('bronze_lots') }}
    qualify row_number() over (
        partition by notice_publication_id
        order by value desc nulls last, lot_id asc
    ) = 1

)

select
    n.notice_publication_id,
    n.notice_type,
    n.subtype_code,
    n.issue_date,
    n.publication_date,
    n.language,
    n.regulatory_domain,
    n.buyer_org_ref,
    n.buyer_legal_type,
    n.procurement_procedure,
    o.name           as buyer_name,
    o.country_code   as buyer_country_code,
    o.city           as buyer_city,
    n.estimated_value,
    n.estimated_currency,
    n.total_value,
    n.total_currency,
    pc.primary_cpv_code,
    cpv.name         as primary_cpv_name,
    left(pc.primary_cpv_code, 2) as primary_cpv_division
from latest_notices n
left join buyer_organizations o
    on  n.notice_publication_id = o.notice_publication_id
    and n.buyer_org_ref = o.org_ref
left join primary_cpv pc
    using (notice_publication_id)
left join {{ ref('cpv_codes') }} cpv
    on pc.primary_cpv_code = cpv.code

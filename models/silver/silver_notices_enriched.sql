with latest_notices as (

    select
        notice_publication_id,
        notice_type,
        issue_date,
        publication_date,
        language,
        regulatory_domain,
        buyer_org_ref,
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

)

select
    n.notice_publication_id,
    n.notice_type,
    n.issue_date,
    n.publication_date,
    n.language,
    n.regulatory_domain,
    n.buyer_org_ref,
    o.name as buyer_name,
    o.country_code as buyer_country_code,
    o.city as buyer_city,
    n.estimated_value,
    n.estimated_currency,
    n.total_value,
    n.total_currency
from latest_notices n
left join buyer_organizations o
    on n.notice_publication_id = o.notice_publication_id
    and n.buyer_org_ref = o.org_ref
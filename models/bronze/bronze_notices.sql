select
    notice_publication_id,
    notice_uuid,
    notice_type,
    subtype_code,
    to_date(
        regexp_replace(issue_date, '(Z|[+-]\\d{1,2}:\\d{2})$', ''),
        'yyyy-MM-dd'
        ) as issue_date,
    to_date(
        regexp_replace(issue_date, '(Z|[+-]\\d{1,2}:\\d{2})$', ''),
        'yyyy-MM-dd'
        ) as publication_date,
    gazette_id,
    language,
    regulatory_domain,
    buyer_org_ref,
    estimated_value,
    estimated_currency,
    total_value,
    total_currency,
    source_file
from {{ source('ted_raw', 'notices') }}
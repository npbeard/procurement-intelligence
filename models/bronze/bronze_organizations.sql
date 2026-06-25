select
    notice_publication_id,
    org_ref,
    name,
    city,
    country_code,
    company_id,
    website
from {{ source('ted_raw', 'organizations') }}
select
    notice_publication_id,
    lot_id,
    name,
    description,
    procurement_type,
    cpv_code,
    value,
    currency,
    status,
    to_date(
        regexp_replace( submission_deadline_date , '(Z|[+-]\\d{1,2}:\\d{2})$', ''),
        'yyyy-MM-dd'
    ) as submission_deadline_date,
    to_timestamp(
        concat(substr( submission_deadline_date , 1, 10), 'T', submission_deadline_time ),
        "yyyy-MM-dd'T'HH:mm:ssXXX"
    ) as submission_deadline_time
from {{ source('ted_raw', 'lots') }}
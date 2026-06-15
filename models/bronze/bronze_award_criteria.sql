select
    notice_publication_id,
    lot_id,
    criterion_index,
    criterion_type,
    description,
    weight,
    weight_type
from {{ source('ted_raw', 'award_criteria') }}
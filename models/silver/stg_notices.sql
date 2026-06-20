{{ config(materialized='view') }}

select * from {{ source('ted_raw', 'notices') }}

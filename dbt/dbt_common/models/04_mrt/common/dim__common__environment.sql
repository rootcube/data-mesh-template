{{
    config(
        enabled=true,
        tags=['owner=public', 'system=common', 'category=environment']
    )
}}

SELECT
  SHA1(environment_code) AS id_dim__common__environment

, environment_code
, environment_name
, environment_alias
, environment_desc
, environment_sort

FROM
  {{ ref('int__common__environment') }}

UNION ALL

SELECT
  CAST(unknown_id AS VARCHAR) AS id_dim__common__environment

-- Attributes
, unknown_code                AS environment_code
, unknown_name                AS environment_name
, unknown_name                AS environment_alias
, ''                          AS environment_desc
, -1                          AS environment_sort
FROM
  {{ ref('stg__seed__unknown') }}

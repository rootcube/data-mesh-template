SELECT
  environment_code
, environment_name
, environment_alias
, environment_desc
, environment_sort

FROM
  {{ ref('stg__seed__environment') }}

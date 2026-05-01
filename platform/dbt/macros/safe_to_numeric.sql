{% macro safe_to_numeric(value_expression) -%}
  {{ return(adapter.dispatch('safe_to_numeric', 'activationos_transform')(value_expression)) }}
{%- endmacro %}

{% macro activationos_transform__safe_to_numeric(value_expression) -%}
  cast(null as numeric)
{%- endmacro %}

{% macro postgres__safe_to_numeric(value_expression) -%}
  case
    when {{ value_expression }} ~ '^[-+]?[0-9]*\.?[0-9]+$' then cast({{ value_expression }} as numeric)
    else null
  end
{%- endmacro %}

{% macro duckdb__safe_to_numeric(value_expression) -%}
  try_cast({{ value_expression }} as double)
{%- endmacro %}

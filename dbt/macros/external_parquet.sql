{% macro parquet_scan(path_var) -%}
read_parquet('{{ var(path_var) | replace("'", "''") }}/*.parquet', union_by_name=true)
{%- endmacro %}

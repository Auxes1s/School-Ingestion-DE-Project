select * from read_parquet('{{ var("linkage_results_path") | replace("'", "''") }}')

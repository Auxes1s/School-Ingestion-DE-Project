select * from read_parquet('{{ var("linkage_candidates_path") | replace("'", "''") }}')

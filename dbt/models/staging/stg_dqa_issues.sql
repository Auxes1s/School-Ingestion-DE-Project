select * from read_parquet('{{ var("dqa_issues_path") | replace("'", "''") }}')

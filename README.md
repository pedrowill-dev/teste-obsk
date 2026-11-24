# ETL de vendas (exemplo do obskitpy)

Extrai um CSV sujo de pedidos, limpa e valida, e carrega um warehouse SQLite por ambiente (`warehouse/<env>.db`).
Linhas rejeitadas vão para `rejected_orders` com o motivo; mais de 15% rejeitadas falha a execução (`ETL_MAX_REJECT_RATE`).

```bash
pip install "obskitpy[portal]" pytest
python -m pytest tests -q                 # 13 testes
obskitpy init -y --service etl-vendas --up && obskitpy portal enable
obskitpy login --url http://localhost:8700 --email admin@obskitpy.local
obskitpy robot apply -f robot.json
obskitpy agent run --source-dir . --otlp-endpoint http://localhost:4317 &
obskitpy robot run ETL_VENDAS --env dev --follow
```

A experiência completa, com prints e lacunas encontradas: `docs/pt-BR/experience-etl.md`.

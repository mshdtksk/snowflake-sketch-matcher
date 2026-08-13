# Snowflake Sketch Matcher

手描きイラストを撮影すると Snowflake Cortex が分析し、
関連するSnowflakeサービスを推測するアプリです。

## ローカル実行

```bash
pip install -r requirements.txt

streamlit run app.py
```

## Streamlit Community Cloud

Secretsに以下を登録してください。

```toml
SNOWFLAKE_ACCOUNT="xxxxx"

SNOWFLAKE_USER="xxxxx"

SNOWFLAKE_PASSWORD="xxxxx"

SNOWFLAKE_WAREHOUSE="COMPUTE_WH"

SNOWFLAKE_DATABASE="SKETCH_MATCHER_DB"

SNOWFLAKE_SCHEMA="PUBLIC"

SNOWFLAKE_ROLE="ACCOUNTADMIN"
```

## デプロイ

1. GitHubへPush
2. Streamlit Community Cloudへログイン
3. Create App選択
4. Repository選択
5. Deploy

完了
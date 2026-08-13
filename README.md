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
[connections.snowflake]
account = "your_account_identifier"   # 例: xy12345.ap-northeast-1.aws
user = "your_username"
password = "your_password"
role = "your_role"                    # 例: SYSADMIN
warehouse = "your_warehouse"          # 例: COMPUTE_WH
database = "SKETCH_MATCHER_DB"
schema = "PUBLIC"
```

## デプロイ

1. GitHubへPush
2. Streamlit Community Cloudへログイン
3. Create App選択
4. Repository選択
5. Deploy

完了

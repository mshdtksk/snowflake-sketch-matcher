# Camera-based sketch to Snowflake service matcher using st.camera_input
# Works with both Streamlit in Snowflake and Streamlit Community Cloud

import os
import json
import uuid
import tempfile
from typing import Any, Dict

import streamlit as st


st.set_page_config(
    page_title="Sketch Camera Matcher",
    page_icon="📷",
    layout="centered",
)


# ------------------------------------------------------------
# Connection
# ------------------------------------------------------------

@st.cache_resource
def get_snowflake_session():
    """
    Streamlit in Snowflake:
        st.connection("snowflake") connects automatically.

    Streamlit Community Cloud:
        Configure [connections.snowflake] in Secrets.
    """
    conn = st.connection(
        "snowflake",
        ttl=int(os.getenv("SNOWFLAKE_CONNECTION_TTL", "3600")),
    )
    return conn.session()


session = get_snowflake_session()


# ------------------------------------------------------------
# Config helpers
# ------------------------------------------------------------

def get_config_value(key: str, default: str) -> str:
    """
    Priority:
    1. Streamlit Secrets top-level value
    2. Environment variable
    3. Default value
    """
    try:
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass

    return os.getenv(key, default)


TARGET_DB = get_config_value("SNOWFLAKE_DATABASE", "SKETCH_MATCHER_DB")
TARGET_SCHEMA = get_config_value("SNOWFLAKE_SCHEMA", "PUBLIC")
STAGE_NAME = get_config_value("STAGE_NAME", "SKETCH_CAMERA_STAGE")

RESULTS_TABLE = get_config_value(
    "RESULTS_TABLE",
    f"{TARGET_DB}.{TARGET_SCHEMA}.SKETCH_RESULTS",
)

MODEL_NAME = get_config_value("SNOWFLAKE_CORTEX_MODEL", "pixtral-large")

FULL_STAGE = f"{TARGET_DB}.{TARGET_SCHEMA}.{STAGE_NAME}"


def sql_literal(value: Any) -> str:
    """
    Escape value for SQL string literal.
    """
    if value is None:
        return ""
    return str(value).replace("'", "''")


# ------------------------------------------------------------
# App UI
# ------------------------------------------------------------

st.title("📷 Snowflake Sketch Camera Matcher")
st.markdown("カメラで手描きの絵を撮影すると、連想されるSnowflakeサービスを判定します！")

TEAMS = [chr(i) for i in range(ord("A"), ord("R") + 1)]
selected_team = st.selectbox("チームを選択してください", TEAMS, index=0)

SERVICES_LIST = [
    "Alert",
    "Array",
    "COPY INTO",
    "Credit",
    "Data Lake",
    "Data Masking",
    "Lock NoteBooks",
    "Object",
    "Share",
    "Snowpipe",
    "Stage",
    "Star Schema",
    "Table",
    "Tag",
    "Time Travel",
    "UNION",
    "User",
    "Warehouse",
    "Window",
    "くま太郎",
]

SNOWFLAKE_SERVICES = """
- Snowpark: データエンジニアリングとML（パイプライン、データフレーム、Python/Java/Scala）
- Cortex AI: AI/ML機能（LLM、AI関数、ベクトル検索、ファインチューニング）
- Snowpipe / Snowpipe Streaming: リアルタイムデータ取り込み（パイプ、ストリーム）
- Dynamic Tables: 宣言的データパイプライン（自動更新、DAG）
- Streamlit in Snowflake: データアプリ構築（ダッシュボード、UI）
- Cortex Search: セマンティック検索・RAG
- Cortex Analyst: 自然言語でのデータ分析（セマンティックビュー）
- Snowflake Notebooks: インタラクティブな開発環境（Jupyter的）
- Native Apps Framework: アプリのパッケージ化と配布（マーケットプレイス）
- Data Sharing / Marketplace: データの共有と取引
- Snowflake Tasks: スケジュール実行・ワークフロー
- Streams: CDC（変更データキャプチャ）
- Iceberg Tables: オープンテーブルフォーマット対応
- Arctic: Snowflakeオリジナルのオープンソースモデル
- Snowpark Container Services (SPCS): コンテナ実行環境（GPU、カスタムモデル）
- Data Clean Rooms: プライバシー保護付きデータコラボレーション
- Horizon: データガバナンスとセキュリティ
- Time Travel: 過去のデータ状態へのアクセス
- Zero-Copy Cloning: ストレージ不要のデータ複製
- Warehouses: コンピュートリソース管理
"""


# ------------------------------------------------------------
# Snowflake objects
# ------------------------------------------------------------

def ensure_stage_exists():
    """
    Create required Snowflake objects.

    If your Streamlit Community Cloud role cannot create database/schema,
    create them manually in Snowflake and keep this role with USAGE/CREATE STAGE/CREATE TABLE.
    """
    session.sql(f"CREATE DATABASE IF NOT EXISTS {TARGET_DB}").collect()
    session.sql(f"CREATE SCHEMA IF NOT EXISTS {TARGET_DB}.{TARGET_SCHEMA}").collect()

    session.sql(
        f"""
        CREATE STAGE IF NOT EXISTS {FULL_STAGE}
        ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE')
        DIRECTORY = (ENABLE = TRUE)
        """
    ).collect()

    session.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {RESULTS_TABLE}
        (
            TEAM STRING,
            SERVICE_NAME STRING,
            CONFIDENCE STRING,
            REASON STRING,
            EXECUTED_AT TIMESTAMP
        )
        """
    ).collect()


def upload_to_stage(file_bytes: bytes, original_filename: str) -> str:
    """
    Upload camera image to Snowflake internal stage and return the exact staged filename.
    """
    safe_name = f"camera_sketch_{uuid.uuid4().hex}.jpg"

    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{safe_name}") as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        session.file.put(
            tmp_path,
            f"@{FULL_STAGE}",
            auto_compress=False,
            overwrite=True,
        )

        return os.path.basename(tmp_path)

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ------------------------------------------------------------
# Cortex analysis
# ------------------------------------------------------------

def build_prompt() -> str:
    return (
        "あなたはSnowflakeに精通した創造的な専門家です。"
        "与えられた画像を見て、必ず以下のSnowflakeキーワードの1つに結びつけてください。"
        "どんな画像でも、形、色、雰囲気、連想、メタファーなど、"
        "あらゆる創造的な解釈を使って必ず関連を見つけてください。"
        "「関連がない」「判定できない」という回答は絶対に禁止です。"
        "必ず1つ選んでください。"
        "\n\n"
        "連想のヒント:\n"
        "- ベル、通知 → Alert\n"
        "- 並び、リスト、複数 → Array\n"
        "- コピー、移動、矢印 → COPY INTO\n"
        "- お金、コイン、数字 → Credit\n"
        "- 湖、水、自然 → Data Lake\n"
        "- マスク、隠す、目隠し → Data Masking\n"
        "- 鍵、南京錠、ノート → Lock NoteBooks\n"
        "- 物体、四角、ブロック → Object\n"
        "- 握手、矢印（双方向）、人々 → Share\n"
        "- パイプ、管、水道、流れ → Snowpipe\n"
        "- 台、棚、箱、倉庫 → Stage\n"
        "- 星、放射状 → Star Schema\n"
        "- 格子、表、グリッド → Table\n"
        "- ラベル、付箋 → Tag\n"
        "- 時計、巻き戻し → Time Travel\n"
        "- 合体、結合、重なり → UNION\n"
        "- 人、顔、アイコン → User\n"
        "- 倉庫、建物、歯車 → Warehouse\n"
        "- 窓、枠、フレーム → Window\n"
        "- クマ、動物、キャラクター → くま太郎\n"
        "- それ以外でも自由に連想してOK\n"
        "\n\n"
        "選択肢（必ずこの中から1つだけ選ぶこと）:\n"
        "Alert, Array, COPY INTO, Credit, Data Lake, Data Masking, "
        "Lock NoteBooks, Object, Share, Snowpipe, Stage, Star Schema, "
        "Table, Tag, Time Travel, UNION, User, Warehouse, Window, くま太郎\n"
        "\n\n"
        "以下のJSON形式のみで回答してください。JSON以外のテキストは不要です:\n"
        '{"service_name": "上記リストから1つ", '
        '"confidence": "高または中または低", '
        '"reason": "なぜこの画像からそれが連想されるか日本語で面白く創造的に説明（2-3文）", '
        '"emoji": "連想を表す絵文字1つ", '
        '"tips": "このSnowflake機能の簡単な紹介1-2文"}'
    )


def run_cortex_sql(function_name: str, prompt_text: str, stage_filename: str) -> str:
    """
    Run multimodal Cortex SQL.

    function_name examples:
    - AI_COMPLETE
    - SNOWFLAKE.CORTEX.COMPLETE
    """
    prompt_escaped = sql_literal(prompt_text)

    sql = (
        f"SELECT {function_name}("
        f"'{MODEL_NAME}', "
        f"'{prompt_escaped}', "
        f"TO_FILE('@{FULL_STAGE}', '{sql_literal(stage_filename)}')"
        f") AS RESULT"
    )

    result = session.sql(sql).collect()

    if not result:
        return ""

    return str(result[0][0])


def analyze_sketch(stage_filename: str) -> str:
    """
    Prefer AI_COMPLETE.
    Fallback to SNOWFLAKE.CORTEX.COMPLETE for accounts where multimodal COMPLETE is enabled.
    """
    prompt_text = build_prompt()

    try:
        return run_cortex_sql("AI_COMPLETE", prompt_text, stage_filename)

    except Exception as first_error:
        try:
            return run_cortex_sql("SNOWFLAKE.CORTEX.COMPLETE", prompt_text, stage_filename)

        except Exception as second_error:
            raise RuntimeError(
                "Cortex image analysis failed. "
                f"AI_COMPLETE error: {first_error}. "
                f"SNOWFLAKE.CORTEX.COMPLETE error: {second_error}"
            )


# ------------------------------------------------------------
# Result parsing
# ------------------------------------------------------------

def guess_service_from_text(text: str) -> str:
    """
    テキスト中のキーワードから最も近いサービスを推定する。
    """
    keywords_map = {
        "Alert": ["alert", "通知", "ベル", "警告", "アラート"],
        "Array": ["array", "配列", "リスト", "並び", "複数"],
        "COPY INTO": ["copy", "コピー", "移動", "転送", "取り込み"],
        "Credit": ["credit", "クレジット", "お金", "コイン", "料金"],
        "Data Lake": ["lake", "湖", "水", "自然", "データレイク"],
        "Data Masking": ["mask", "マスク", "隠す", "秘密", "プライバシー"],
        "Lock NoteBooks": ["lock", "鍵", "ロック", "ノート", "南京錠"],
        "Object": ["object", "オブジェクト", "物体", "四角", "ブロック"],
        "Share": ["share", "共有", "シェア", "握手", "人々"],
        "Snowpipe": ["pipe", "パイプ", "管", "流れ", "水道"],
        "Stage": ["stage", "ステージ", "台", "棚", "倉庫", "箱"],
        "Star Schema": ["star", "星", "スター", "放射"],
        "Table": ["table", "テーブル", "表", "格子", "グリッド"],
        "Tag": ["tag", "タグ", "ラベル", "付箋"],
        "Time Travel": ["time", "時間", "時計", "巻き戻し", "過去"],
        "UNION": ["union", "結合", "合体", "重なり", "マージ"],
        "User": ["user", "ユーザー", "人", "顔", "アイコン"],
        "Warehouse": ["warehouse", "倉庫", "建物", "歯車", "計算"],
        "Window": ["window", "窓", "枠", "フレーム", "ウィンドウ"],
        "くま太郎": ["くま", "クマ", "熊", "動物", "キャラ", "bear"],
    }

    text_lower = text.lower()
    best_service = "くま太郎"
    best_score = 0

    for service, keywords in keywords_map.items():
        score = sum(1 for kw in keywords if kw.lower() in text_lower)
        if score > best_score:
            best_score = score
            best_service = service

    return best_service


def normalize_result(parsed: Dict[str, Any], raw_text: str) -> Dict[str, str]:
    service_name = str(parsed.get("service_name", "")).strip()

    if service_name not in SERVICES_LIST:
        service_name = guess_service_from_text(raw_text)

    confidence = str(parsed.get("confidence", "中")).strip()
    if confidence not in ["高", "中", "低"]:
        confidence = "中"

    reason = str(parsed.get("reason", "")).strip()
    emoji = str(parsed.get("emoji", "❄️")).strip()
    tips = str(parsed.get("tips", "")).strip()

    if not reason:
        reason = "画像の特徴からSnowflakeの概念へ創造的にマッピングしました。"

    if not tips:
        tips = f"{service_name}はSnowflakeに関連する重要な概念です。"

    return {
        "service_name": service_name,
        "confidence": confidence,
        "reason": reason,
        "emoji": emoji,
        "tips": tips,
    }


def parse_result(result_text: str) -> Dict[str, str]:
    if not result_text:
        return {
            "service_name": "くま太郎",
            "confidence": "中",
            "reason": "画像の分析結果が取得できませんでしたが、くま太郎が応援しています！",
            "emoji": "🐻",
            "tips": "くま太郎はSnowflakeの学習を応援するマスコットです。",
        }

    text = str(result_text).strip()

    try:
        start = text.find("{")
        end = text.rfind("}") + 1

        if start != -1 and end > start:
            json_text = text[start:end]
        else:
            json_text = text

        parsed = json.loads(json_text)

        return normalize_result(parsed, text)

    except Exception:
        guessed = guess_service_from_text(text)

        return {
            "service_name": guessed,
            "confidence": "中",
            "reason": text[:300] if len(text) > 300 else text,
            "emoji": "❄️",
            "tips": f"{guessed}はSnowflakeの主要サービスの1つです。",
        }


# ------------------------------------------------------------
# Display and save
# ------------------------------------------------------------

def display_result(result: Dict[str, str]):
    st.markdown(
        f"### {result.get('emoji', '❄️')} {result.get('service_name', '不明')}"
    )

    confidence = result.get("confidence", "中")
    conf_color = {
        "高": "green",
        "中": "orange",
        "低": "red",
    }.get(confidence, "gray")

    st.markdown(f"**確信度:** :{conf_color}[{confidence}]")
    st.markdown(f"**理由:** {result.get('reason', '不明')}")
    st.info(f"💡 {result.get('tips', '')}")


def save_result(team: str, result: Dict[str, str]):
    service_name = sql_literal(result.get("service_name", ""))
    confidence = sql_literal(result.get("confidence", ""))
    reason = sql_literal(result.get("reason", ""))[:1000]

    session.sql(
        f"""
        INSERT INTO {RESULTS_TABLE}
            (TEAM, SERVICE_NAME, CONFIDENCE, REASON, EXECUTED_AT)
        VALUES
            ('{sql_literal(team)}', '{service_name}', '{confidence}', '{reason}', CURRENT_TIMESTAMP())
        """
    ).collect()


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

with st.expander("接続設定", expanded=False):
    st.caption("Streamlit Community Cloudでは Secrets の [connections.snowflake] を使います。")
    st.write("Database:", TARGET_DB)
    st.write("Schema:", TARGET_SCHEMA)
    st.write("Stage:", FULL_STAGE)
    st.write("Results table:", RESULTS_TABLE)
    st.write("Model:", MODEL_NAME)

st.markdown("### 📸 カメラで絵を撮影してください")
camera_photo = st.camera_input("手描きの絵にカメラを向けて撮影ボタンを押してください")

if camera_photo is not None:
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("撮影した絵")
        st.image(camera_photo, use_container_width=True)

    with col2:
        st.subheader("判定結果")

        with st.spinner("AIが絵を分析中... 🔍"):
            try:
                ensure_stage_exists()

                file_bytes = camera_photo.getvalue()
                stage_filename = upload_to_stage(file_bytes, "camera_sketch.jpg")

                result_text = analyze_sketch(stage_filename)
                result = parse_result(result_text)

                display_result(result)
                save_result(selected_team, result)

                st.success(f"✅ チーム{selected_team}の結果を保存しました")

                with st.expander("DEBUG: Cortex raw response", expanded=False):
                    st.code(result_text)

            except Exception as e:
                st.error("エラーが発生しました")
                st.exception(e)

st.markdown("---")
st.markdown(
    "💡 **使い方:** 紙に絵を描いて、カメラで撮影するだけ！ "
    "星→Star Schema、パイプ→Snowpipe、時計→Time Travel、クマ→くま太郎... "
    "何を描いてもAIが創造的にSnowflakeの概念と結びつけます。"
)

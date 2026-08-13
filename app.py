import os
import json
import tempfile

import streamlit as st
from snowflake.snowpark import Session


st.set_page_config(
    page_title="Snowflake Sketch Matcher",
    page_icon="📷",
    layout="centered",
)


@st.cache_resource
def get_session():

    connection_parameters = {
        "account": st.secrets["SNOWFLAKE_ACCOUNT"],
        "user": st.secrets["SNOWFLAKE_USER"],
        "password": st.secrets["SNOWFLAKE_PASSWORD"],
        "warehouse": st.secrets["SNOWFLAKE_WAREHOUSE"],
        "database": st.secrets["SNOWFLAKE_DATABASE"],
        "schema": st.secrets["SNOWFLAKE_SCHEMA"],
        "role": st.secrets["SNOWFLAKE_ROLE"],
    }

    return Session.builder.configs(
        connection_parameters
    ).create()


session = get_session()


RESULTS_TABLE = "PUBLIC.SKETCH_RESULTS"

TARGET_DB = st.secrets["SNOWFLAKE_DATABASE"]
TARGET_SCHEMA = st.secrets["SNOWFLAKE_SCHEMA"]

STAGE_NAME = "SKETCH_CAMERA_STAGE"

FULL_STAGE = f"{TARGET_DB}.{TARGET_SCHEMA}.{STAGE_NAME}"

MODEL_NAME = "pixtral-large"

TEAMS = [chr(i) for i in range(ord("A"), ord("R") + 1)]

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


def ensure_objects():

    session.sql(
        f"""
        CREATE STAGE IF NOT EXISTS {FULL_STAGE}
        DIRECTORY=(ENABLE=TRUE)
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


def upload_to_stage(file_bytes):

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".jpg",
    ) as tmp:

        tmp.write(file_bytes)
        path = tmp.name

    session.file.put(
        path,
        f"@{FULL_STAGE}",
        auto_compress=False,
        overwrite=True,
    )

    filename = os.path.basename(path)

    os.unlink(path)

    return filename


def analyze_sketch(stage_filename):

    prompt = """
あなたはSnowflake専門家です。

必ず以下から1つ選択してください。

Alert
Array
COPY INTO
Credit
Data Lake
Data Masking
Lock NoteBooks
Object
Share
Snowpipe
Stage
Star Schema
Table
Tag
Time Travel
UNION
User
Warehouse
Window
くま太郎

JSONのみ返してください。

{
 "service_name":"",
 "confidence":"",
 "reason":"",
 "emoji":"",
 "tips":""
}
"""

    prompt = prompt.replace("'", "''")

    sql = f"""
    SELECT AI_COMPLETE(
        '{MODEL_NAME}',
        '{prompt}',
        TO_FILE('@{FULL_STAGE}', '{stage_filename}')
    ) AS RESULT
    """

    result = session.sql(sql).collect()

    return result[0]["RESULT"]


def parse_result(text):

    try:

        start = text.find("{")
        end = text.rfind("}") + 1

        obj = json.loads(text[start:end])

        return obj

    except Exception:

        return {
            "service_name": "くま太郎",
            "confidence": "中",
            "reason": "解析できませんでした",
            "emoji": "🐻",
            "tips": "くま太郎が応援しています",
        }


def save_result(team, result):

    service_name = result["service_name"].replace("'", "")
    confidence = result["confidence"].replace("'", "")
    reason = result["reason"].replace("'", "")

    session.sql(
        f"""
        INSERT INTO {RESULTS_TABLE}
        VALUES(
            '{team}',
            '{service_name}',
            '{confidence}',
            '{reason}',
            CURRENT_TIMESTAMP()
        )
        """
    ).collect()


st.title("📷 Snowflake Sketch Matcher")

st.write(
    "スケッチを撮影するとSnowflakeサービスを推測します"
)

team = st.selectbox("チーム", TEAMS)

camera_photo = st.camera_input(
    "手描きイラストを撮影"
)

if camera_photo:

    ensure_objects()

    st.image(
        camera_photo,
        caption="撮影画像"
    )

    with st.spinner("解析中"):

        filename = upload_to_stage(
            camera_photo.getvalue()
        )

        result_text = analyze_sketch(filename)

        result = parse_result(result_text)

    st.success("判定完了")

    st.subheader(
        f"{result['emoji']} {result['service_name']}"
    )

    st.write(
        f"確信度: {result['confidence']}"
    )

    st.write(
        result["reason"]
    )

    st.info(
        result["tips"]
    )

    save_result(team, result)
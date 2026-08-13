# Camera-based sketch to Snowflake service matcher using st.camera_input
# Streamlit Cloud version
import os
import json
import tempfile
import streamlit as st

# st.set_page_config は最初のStreamlitコマンドにする必要がある
st.set_page_config(page_title="Sketch Camera Matcher", page_icon="📷", layout="centered")


@st.cache_resource
def get_session():
    """Snowflakeセッションを取得(キャッシュして再利用)"""
    conn = st.connection("snowflake")
    return conn.session()


try:
    session = get_session()
except Exception as e:
    st.error(f"Snowflakeへの接続に失敗しました: {str(e)}")
    st.info("secrets.toml に接続情報が正しく設定されているか確認してください。")
    st.stop()

st.title("📷 Snowflake Sketch Camera Matcher")
st.markdown("カメラで手描きの絵を撮影すると、連想されるSnowflakeサービスを判定します！")

TEAMS = [chr(i) for i in range(ord("A"), ord("R") + 1)]
selected_team = st.selectbox("チームを選択してください", TEAMS, index=0)

RESULTS_TABLE = "MADB.PUBLIC.SKETCH_RESULTS"

TARGET_DB = "SKETCH_MATCHER_DB"
TARGET_SCHEMA = "PUBLIC"
STAGE_NAME = "SKETCH_CAMERA_STAGE"
FULL_STAGE = f"{TARGET_DB}.{TARGET_SCHEMA}.{STAGE_NAME}"


def ensure_stage_exists():
    session.sql(f"CREATE DATABASE IF NOT EXISTS {TARGET_DB}").collect()
    session.sql(f"CREATE SCHEMA IF NOT EXISTS {TARGET_DB}.{TARGET_SCHEMA}").collect()
    session.sql(
        f"CREATE STAGE IF NOT EXISTS {FULL_STAGE} "
        f"ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE') "
        f"DIRECTORY = (ENABLE = TRUE)"
    ).collect()


def upload_to_stage(file_bytes, filename):
    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{filename}") as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    session.file.put(
        tmp_path,
        f"@{FULL_STAGE}",
        auto_compress=False,
        overwrite=True,
    )
    os.unlink(tmp_path)
    return os.path.basename(tmp_path)


def analyze_sketch(stage_filename):
    prompt_text = (
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
    prompt_escaped = prompt_text.replace("'", "''")
    sql = (
        f"SELECT AI_COMPLETE("
        f"'pixtral-large', "
        f"'{prompt_escaped}', "
        f"TO_FILE('@{FULL_STAGE}', '{stage_filename}')"
        f") AS result"
    )
    result = session.sql(sql).collect()
    return result[0][0]


SERVICES_LIST = [
    "Alert", "Array", "COPY INTO", "Credit", "Data Lake", "Data Masking",
    "Lock NoteBooks", "Object", "Share", "Snowpipe", "Stage",
    "Star Schema", "Table", "Tag", "Time Travel", "UNION",
    "User", "Warehouse", "Window", "くま太郎",
]


def guess_service_from_text(text):
    """テキスト中のキーワードから最も近いサービスを推定する。"""
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
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > best_score:
            best_score = score
            best_service = service
    return best_service


def parse_result(result_text):
    if not result_text:
        return {
            "service_name": "くま太郎",
            "confidence": "中",
            "reason": "画像の分析結果が取得できませんでしたが、くま太郎が応援しています！",
            "emoji": "🐻",
            "tips": "くま太郎はSnowflakeの学習を応援するマスコットです。",
        }
    try:
        start = result_text.find("{")
        end = result_text.rfind("}") + 1
        if start != -1 and end > start:
            parsed = json.loads(result_text[start:end])
        else:
            parsed = json.loads(result_text)
        if parsed.get("service_name") in SERVICES_LIST:
            return parsed
        guessed = guess_service_from_text(result_text)
        parsed["service_name"] = guessed
        return parsed
    except json.JSONDecodeError:
        guessed = guess_service_from_text(result_text)
        return {
            "service_name": guessed,
            "confidence": "中",
            "reason": result_text[:200] if len(result_text) > 200 else result_text,
            "emoji": "❄️",
            "tips": f"{guessed}はSnowflakeの主要サービスの1つです。",
        }


def display_result(result):
    st.markdown(f"### {result.get('emoji', '❄️')} {result.get('service_name', '不明')}")
    confidence = result.get("confidence", "中")
    conf_color = {"高": "green", "中": "orange", "低": "red"}.get(confidence, "gray")
    st.markdown(f"**確信度:** :{conf_color}[{confidence}]")
    st.markdown(f"**理由:** {result.get('reason', '不明')}")
    st.info(f"💡 {result.get('tips', '')}")


def save_result(team, result):
    service_name = result.get("service_name", "").replace("'", "''")
    confidence = result.get("confidence", "").replace("'", "''")
    reason = result.get("reason", "").replace("'", "''")[:1000]
    session.sql(
        f"INSERT INTO {RESULTS_TABLE} (TEAM, SERVICE_NAME, CONFIDENCE, REASON, EXECUTED_AT) "
        f"VALUES ('{team}', '{service_name}', '{confidence}', '{reason}', CURRENT_TIMESTAMP())"
    ).collect()


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
            except Exception as e:
                st.error(f"エラーが発生しました: {str(e)}")

st.markdown("---")
st.markdown(
    "💡 **使い方:** 紙に絵を描いて、カメラで撮影するだけ！ "
    "星→Star Schema、パイプ→Snowpipe、時計→Time Travel、クマ→くま太郎... "
    "何を描いてもAIが創造的にSnowflakeの概念と結びつけます。"
)

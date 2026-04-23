import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

import gspread
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from google.oauth2.service_account import Credentials

# ─────────────────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────────────────
st.set_page_config(
    page_title="🏔️ 오르다",
    page_icon="🏔️",
    layout="wide",
)

# ─────────────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────────────
SHEET_STUDENTS = "학생명단"
SHEET_RECORDS = "체력기록"
KST = timezone(timedelta(hours=9))

ITEMS = [
    "3분왕복달리기(회)",
    "사이드스텝(회)",
    "플랭크(초)",
    "윗몸앞으로굽히기(cm)",
]

ITEM_LABELS = {
    "3분왕복달리기(회)": "🏃 심폐지구력",
    "사이드스텝(회)": "⚡ 순발력",
    "플랭크(초)": "💪 근지구력",
    "윗몸앞으로굽히기(cm)": "🧘 유연성",
}

PRIVACY_POLICY_MD = """
**[개인정보 처리방침]**

「오르다」 프로젝트 앱(이하 '본 앱')은 남산초등학교 학생들의 자기주도적 체력 관리 및 디지털교육 선도학교 연구 목적으로 운영되며, 사용자의 개인정보를 중요하게 생각하고 안전하게 보호하기 위해 최선을 다하고 있습니다.

**1. 수집하는 개인정보 항목**  
본 앱은 서비스 제공을 위해 아래와 같은 최소한의 개인정보를 수집합니다.
- **필수 항목**: 학년, 반, 번호, 성명, 비밀번호(본 앱 전용, 해시 처리 저장)
- **건강/체력 데이터**: 3분 왕복달리기(회), 사이드스텝(회), 플랭크(초), 윗몸앞으로굽히기(cm) 측정 기록

**2. 개인정보의 수집 및 이용 목적**  
수집된 개인정보는 다음의 목적을 위해서만 이용됩니다.
- **학생 체력 관리**: 개인별 체력 데이터 시각화, 성장 추이 분석 및 맞춤형 피드백 제공
- **통계 및 연구**: 반별·학년별 통계 산출 및 디지털교육 선도학교 운영 결과 분석  
  (이 경우, 개인을 식별할 수 없는 비식별화 데이터로 변환하여 활용합니다.)
- **서비스 운영**: 본인 인증, 기록 조회 권한 확인 및 관리

**3. 개인정보의 보유 및 이용 기간**
- 본 앱에서 수집된 개인정보 및 체력 데이터는 해당 학년도 프로젝트 종료 시까지 보유하며, 목적 달성 후에는 복구할 수 없는 방법으로 지체 없이 영구 파기합니다.
- 단, 연구 보고서 작성을 위해 활용되는 데이터는 개인을 식별할 수 없도록 익명화 처리하여 보관될 수 있습니다.

**4. 개인정보의 제3자 제공**  
본 앱은 수집된 개인정보를 원칙적으로 외부에 제공하지 않습니다. 다만, 법령의 규정에 의거하거나 수사 목적으로 법령에 정해진 절차와 방법에 따라 요구받은 경우는 예외로 합니다.

**5. 사용자의 권리 및 행사 방법**
- 학생 및 학부모님은 언제든지 등록되어 있는 자신의 개인정보를 조회하거나 수정할 수 있으며, 관리자(담당 교사)에게 정보 삭제 및 처리 정지를 요청할 수 있습니다.
- 열람, 수정, 삭제 요청은 담당 교사에게 직접 문의해주시기 바랍니다.

**6. 개인정보 보호를 위한 안전성 확보 조치**
- 데이터는 보안이 적용된 Google Cloud(Google Sheets) 환경에 저장되며, 접근 권한은 담당 교사에게만 엄격히 제한됩니다.
- 학생 비밀번호는 평문이 아닌 해시 형태로 저장됩니다.
- 학생 본인의 계정으로 로그인한 경우에만 자신의 기록을 열람할 수 있도록 시스템이 구성되어 있습니다.

**7. 개인정보 보호 책임자**
- 소속/성명: 남산초등학교 체육전담교사
- 연락처: 053-852-5006

**시행일자: 2026년 4월 13일**
"""

# ─────────────────────────────────────────────────────
# 공통 유틸
# ─────────────────────────────────────────────────────
def now_kst() -> datetime:
    return datetime.now(timezone.utc).astimezone(KST)


def clear_data_caches():
    get_student_list.clear()
    get_student_records.clear()
    get_all_records.clear()


def hash_password(raw_password: str) -> str:
    return hashlib.sha256(str(raw_password).encode("utf-8")).hexdigest()


def verify_password(input_password: str, stored_password: str) -> bool:
    """
    기존 평문 비밀번호와 새 해시 비밀번호를 모두 허용.
    기존 데이터와의 호환성을 유지하기 위한 처리.
    """
    if stored_password is None:
        return False

    stored = str(stored_password).strip()
    raw = str(input_password).strip()

    return stored == raw or stored == hash_password(raw)


def clean_cell(v) -> str:
    if pd.isna(v):
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


def normalize_password_cell(v) -> str:
    s = clean_cell(v)

    # sha256 해시이면 그대로 유지
    if len(s) == 64 and all(c in "0123456789abcdef" for c in s.lower()):
        return s

    # "1.0" 같은 값 방지
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]

    # 숫자 비밀번호면 앞자리를 0으로 채워 4자리 유지
    return s.zfill(4) if s.isdigit() else s


def sort_students_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    out["_grade_num"] = pd.to_numeric(out.get("학년"), errors="coerce")
    out["_class_num"] = pd.to_numeric(out.get("반"), errors="coerce")
    out["_num_num"] = pd.to_numeric(out.get("번호"), errors="coerce")
    out = out.sort_values(
        by=["_grade_num", "_class_num", "_num_num", "이름"],
        na_position="last"
    )
    return out.drop(columns=["_grade_num", "_class_num", "_num_num"], errors="ignore")


def normalize_student_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()

    for col in ["학년", "반", "번호", "이름"]:
        if col in out.columns:
            out[col] = out[col].apply(clean_cell)

    if "비밀번호" in out.columns:
        out["비밀번호"] = out["비밀번호"].apply(normalize_password_cell)

    return sort_students_df(out)


def normalize_records_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()

    for col in ["학년", "반", "번호", "이름", "측정회차", "측정일"]:
        if col in out.columns:
            out[col] = out[col].apply(clean_cell)

    out["_grade_num"] = pd.to_numeric(out.get("학년"), errors="coerce")
    out["_class_num"] = pd.to_numeric(out.get("반"), errors="coerce")
    out["_num_num"] = pd.to_numeric(out.get("번호"), errors="coerce")
    out["_round_num"] = pd.to_numeric(out.get("측정회차"), errors="coerce")
    out["_date_dt"] = pd.to_datetime(out.get("측정일"), errors="coerce")

    out = out.sort_values(
        by=["_grade_num", "_class_num", "_num_num", "_round_num", "_date_dt"],
        na_position="last"
    )

    return out.drop(
        columns=["_grade_num", "_class_num", "_num_num", "_round_num", "_date_dt"],
        errors="ignore"
    )


def get_class_options(df: pd.DataFrame) -> List[str]:
    if df.empty or "반" not in df.columns:
        return []
    classes = df["반"].astype(str).dropna().unique().tolist()
    return sorted(classes, key=lambda x: int(x) if str(x).isdigit() else str(x))


def get_grade_options(df: pd.DataFrame) -> List[str]:
    if df.empty or "학년" not in df.columns:
        return []
    grades = df["학년"].astype(str).dropna().unique().tolist()
    return sorted(grades, key=lambda x: int(x) if str(x).isdigit() else str(x))


def get_student_options(df: pd.DataFrame) -> List[str]:
    if df.empty:
        return []
    sorted_df = sort_students_df(df)
    return [f"{row['번호']}번 - {row['이름']}" for _, row in sorted_df.iterrows()]


def parse_optional_int(raw_value: str, label: str, min_value: Optional[int] = None, max_value: Optional[int] = None) -> Tuple[Optional[int], Optional[str]]:
    raw = str(raw_value).strip()
    if raw == "":
        return None, None

    try:
        num = float(raw)
    except ValueError:
        return None, f"'{label}'에는 숫자만 입력해주세요."

    if not num.is_integer():
        return None, f"'{label}'에는 정수를 입력해주세요."

    value = int(num)

    if min_value is not None and value < min_value:
        return None, f"'{label}'은(는) {min_value} 이상이어야 합니다."
    if max_value is not None and value > max_value:
        return None, f"'{label}'은(는) {max_value} 이하여야 합니다."

    return value, None


def parse_optional_float(raw_value: str, label: str, min_value: Optional[float] = None, max_value: Optional[float] = None) -> Tuple[Optional[float], Optional[str]]:
    raw = str(raw_value).strip()
    if raw == "":
        return None, None

    try:
        value = float(raw)
    except ValueError:
        return None, f"'{label}'에는 숫자만 입력해주세요."

    if min_value is not None and value < min_value:
        return None, f"'{label}'은(는) {min_value} 이상이어야 합니다."
    if max_value is not None and value > max_value:
        return None, f"'{label}'은(는) {max_value} 이하여야 합니다."

    return value, None


def gs_retry(func, retries: int = 4, base_delay: float = 1.0):
    last_error = None
    for attempt in range(retries):
        try:
            return func()
        except gspread.exceptions.APIError as e:
            last_error = e
            msg = str(e)
            status_code = getattr(getattr(e, "response", None), "status_code", None)

            if status_code == 429 or "Quota exceeded" in msg or "Read requests per minute" in msg:
                time.sleep(base_delay * (2 ** attempt))
                continue
            raise
        except Exception as e:
            last_error = e
            raise last_error
    raise last_error


# ─────────────────────────────────────────────────────
# Google Sheets 연결
# ─────────────────────────────────────────────────────
@st.cache_resource
def get_google_connection():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("🚨 Secrets에 [gcp_service_account] 정보가 없습니다.")
            return None

        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        return gspread.authorize(credentials)

    except Exception as e:
        st.error(f"🚨 구글 서버 연결 실패: {e}")
        return None


def get_spreadsheet_name() -> Optional[str]:
    if "spreadsheet_name" in st.secrets:
        return st.secrets["spreadsheet_name"]

    if "spreadsheet_name" in st.secrets.get("gcp_service_account", {}):
        return st.secrets["gcp_service_account"]["spreadsheet_name"]

    st.error("🚨 Secrets에 'spreadsheet_name'이 설정되지 않았습니다.")
    return None


@st.cache_resource
def get_spreadsheet(_client, doc_name: str):
    return gs_retry(lambda: _client.open(doc_name))


def get_worksheet(client, sheet_name: str, create_if_missing: bool = True):
    try:
        doc_name = get_spreadsheet_name()
        if not doc_name:
            return None

        try:
            spreadsheet = get_spreadsheet(client, doc_name)
        except gspread.SpreadsheetNotFound:
            st.error(f"🚨 구글 드라이브에서 '{doc_name}' 스프레드시트를 찾을 수 없습니다.")
            st.info("💡 해결법: service account의 client_email을 스프레드시트 공유에 '편집자'로 추가해주세요.")
            return None

        try:
            return gs_retry(lambda: spreadsheet.worksheet(sheet_name))
        except gspread.WorksheetNotFound:
            if not create_if_missing:
                return None
            return gs_retry(lambda: spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20))

    except Exception as e:
        st.error(f"🚨 데이터베이스 접근 중 에러 발생: {e}")
        return None


# ─────────────────────────────────────────────────────
# 초기 데이터 생성
# ─────────────────────────────────────────────────────
def init_student_list(client) -> bool:
    ws = get_worksheet(client, SHEET_STUDENTS)
    if ws is None:
        return False

    existing = gs_retry(lambda: ws.get_all_values())
    if len(existing) <= 1:
        headers = ["학년", "반", "번호", "이름", "비밀번호"]
        students = []

        # 3~6학년, 각 학년 1반, 18명 기준 더미 데이터
        for grade in [3, 4, 5, 6]:
            for num in range(1, 19):
                default_name = f"{grade}-1-{num}"
                default_pw = f"{num:04d}"
                students.append([
                    str(grade),
                    "1",
                    str(num),
                    default_name,
                    hash_password(default_pw),
                ])

        gs_retry(lambda: ws.clear())
        gs_retry(lambda: ws.update(range_name="A1", values=[headers] + students))
        clear_data_caches()

    return True


def init_records_sheet(client) -> bool:
    ws = get_worksheet(client, SHEET_RECORDS)
    if ws is None:
        return False

    existing = gs_retry(lambda: ws.get_all_values())
    if len(existing) <= 1:
        headers = [
            "학년", "반", "번호", "이름", "측정회차", "측정일",
            "3분왕복달리기(회)", "사이드스텝(회)",
            "플랭크(초)", "윗몸앞으로굽히기(cm)"
        ]
        gs_retry(lambda: ws.clear())
        gs_retry(lambda: ws.update(range_name="A1", values=[headers]))
        clear_data_caches()

    return True


# ─────────────────────────────────────────────────────
# 데이터 조회
# ─────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def get_student_list(_client):
    ws = get_worksheet(_client, SHEET_STUDENTS, create_if_missing=False)
    if ws is None:
        return pd.DataFrame()

    data = gs_retry(lambda: ws.get_all_records())
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    return normalize_student_df(df)


@st.cache_data(ttl=60)
def get_all_records(_client):
    ws = get_worksheet(_client, SHEET_RECORDS, create_if_missing=False)
    if ws is None:
        return pd.DataFrame()

    data = gs_retry(lambda: ws.get_all_records())
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    return normalize_records_df(df)


@st.cache_data(ttl=60)
def get_student_records(_client, grade, cls, num):
    df = get_all_records(_client)
    if df.empty:
        return pd.DataFrame()

    return df[
        (df["학년"] == str(grade)) &
        (df["반"] == str(cls)) &
        (df["번호"] == str(num))
    ].copy()


# ─────────────────────────────────────────────────────
# 데이터 입력/수정/삭제
# ─────────────────────────────────────────────────────
def add_record(client, record):
    ws = get_worksheet(client, SHEET_RECORDS)
    if ws is None:
        return False, "체력기록 시트에 접근할 수 없습니다."

    grade, cls, num, _, round_num = record[:5]
    values = record[6:]

    if all(v in ("", None) for v in values):
        return False, "적어도 한 종목 이상 입력해주세요."

    existing = get_student_records(client, grade, cls, num)
    if not existing.empty:
        duplicate = existing[existing["측정회차"].astype(str) == str(round_num)]
        if not duplicate.empty:
            return False, f"{round_num}회차 기록이 이미 존재합니다."

    gs_retry(lambda: ws.append_row(record))
    clear_data_caches()
    return True, f"{round_num}회차 기록이 저장되었습니다."


def add_student(client, grade, cls, num, name, password):
    ws = get_worksheet(client, SHEET_STUDENTS)
    if ws is None:
        return False, "학생명단 시트에 접근할 수 없습니다."

    grade = str(grade).strip()
    cls = str(cls).strip()
    num = str(num).strip()
    name = str(name).strip()
    password = str(password).strip()

    if not all([grade, cls, num, name, password]):
        return False, "모든 항목을 입력해주세요."

    students = get_student_list(client)
    duplicate = students[
        (students["학년"] == grade) &
        (students["반"] == cls) &
        (students["번호"] == num)
    ]
    if not duplicate.empty:
        return False, "같은 학년/반/번호의 학생이 이미 존재합니다."

    gs_retry(lambda: ws.append_row([grade, cls, num, name, hash_password(password)]))
    clear_data_caches()
    return True, f"{name} 학생이 추가되었습니다."


def delete_student(client, grade, cls, num, delete_records=False):
    student_ws = get_worksheet(client, SHEET_STUDENTS)
    if student_ws is None:
        return False, "학생명단 시트에 접근할 수 없습니다."

    student_data = gs_retry(lambda: student_ws.get_all_values())
    target_row = None

    for i, row in enumerate(student_data):
        if i == 0:
            continue
        if len(row) >= 3 and str(row[0]) == str(grade) and str(row[1]) == str(cls) and str(row[2]) == str(num):
            target_row = i + 1
            break

    if target_row is None:
        return False, "삭제할 학생을 찾지 못했습니다."

    gs_retry(lambda: student_ws.delete_rows(target_row))

    deleted_record_count = 0
    if delete_records:
        record_ws = get_worksheet(client, SHEET_RECORDS, create_if_missing=False)
        if record_ws is not None:
            record_data = gs_retry(lambda: record_ws.get_all_values())
            delete_row_indices = []

            for i, row in enumerate(record_data):
                if i == 0:
                    continue
                if len(row) >= 3 and str(row[0]) == str(grade) and str(row[1]) == str(cls) and str(row[2]) == str(num):
                    delete_row_indices.append(i + 1)

            for row_idx in reversed(delete_row_indices):
                gs_retry(lambda row_idx=row_idx: record_ws.delete_rows(row_idx))
                deleted_record_count += 1

    clear_data_caches()

    if delete_records:
        return True, f"학생 삭제 완료 (체력기록 {deleted_record_count}건 함께 삭제)"
    return True, "학생 삭제 완료"


def update_student(client, grade, cls, num, new_name="", new_password="", sync_record_name=True):
    student_ws = get_worksheet(client, SHEET_STUDENTS)
    if student_ws is None:
        return False, "학생명단 시트에 접근할 수 없습니다."

    new_name = str(new_name).strip()
    new_password = str(new_password).strip()

    if not new_name and not new_password:
        return False, "수정할 내용을 입력해주세요."

    student_data = gs_retry(lambda: student_ws.get_all_values())
    target_row = None

    for i, row in enumerate(student_data):
        if i == 0:
            continue
        if len(row) >= 3 and str(row[0]) == str(grade) and str(row[1]) == str(cls) and str(row[2]) == str(num):
            target_row = i + 1
            break

    if target_row is None:
        return False, "수정할 학생을 찾지 못했습니다."

    if new_name:
        gs_retry(lambda: student_ws.update_cell(target_row, 4, new_name))

    if new_password:
        gs_retry(lambda: student_ws.update_cell(target_row, 5, hash_password(new_password)))

    updated_record_count = 0
    if new_name and sync_record_name:
        record_ws = get_worksheet(client, SHEET_RECORDS, create_if_missing=False)
        if record_ws is not None:
            record_data = gs_retry(lambda: record_ws.get_all_values())
            for i, row in enumerate(record_data):
                if i == 0:
                    continue
                if len(row) >= 4 and str(row[0]) == str(grade) and str(row[1]) == str(cls) and str(row[2]) == str(num):
                    gs_retry(lambda i=i: record_ws.update_cell(i + 1, 4, new_name))
                    updated_record_count += 1

    clear_data_caches()

    msg_parts = ["학생 정보 수정 완료"]
    if new_name and sync_record_name:
        msg_parts.append(f"(체력기록 이름 {updated_record_count}건 동기화)")
    return True, " ".join(msg_parts)


# ─────────────────────────────────────────────────────
# 분석/시각화
# ─────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=3600)
def generate_gemini_feedback(records_df, item_name, student_name):
    if "GEMINI_API_KEY" not in st.secrets:
        return "⚠️ Secrets에 GEMINI_API_KEY가 없습니다. 관리자에게 문의하세요."

    try:
        import google.generativeai as genai
    except ImportError:
        return "⚠️ google-generativeai 패키지가 설치되지 않았습니다."

    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-1.5-flash")

    df = records_df[["측정회차", item_name]].dropna().copy()
    df["_round_num"] = pd.to_numeric(df["측정회차"], errors="coerce")
    df = df.sort_values("_round_num")

    if len(df) < 2:
        return "💬 2회 이상 기록이 누적되면 AI 체육 선생님의 맞춤 분석이 제공됩니다!"

    records_text = "\n".join([f"- {row['측정회차']}회차: {row[item_name]}" for _, row in df.iterrows()])

    prompt = f"""
    당신은 초등학생들을 사랑으로 가르치는 다정하고 열정적인 체육 선생님입니다.
    학생의 이름은 '{student_name}'이며, '{item_name}' 종목의 체력 측정 기록은 다음과 같습니다.

    [측정 기록]
    {records_text}

    위 데이터를 바탕으로 학생에게 직접 말하듯이 친절하고 격려하는 말투(해요체/해요)로 피드백을 작성해주세요.
    초등학생 눈높이에 맞게 이모지(🏃, 💪, ⚡ 등)를 적절히 사용해주세요.
    다음 3가지 내용이 반드시 순서대로 들어가야 합니다:
    1. 기록 변화 분석: 이전 회차와 비교해서 얼마나 발전했는지, 혹은 꾸준히 잘하고 있는지 구체적인 수치로 칭찬해주세요. (기록이 떨어졌다면 위로와 격려를 해주세요.)
    2. 따뜻한 격려: 학생의 노력에 대한 칭찬과 긍정적인 동기부여.
    3. 맞춤형 운동 추천: 이 종목({item_name})의 기록을 더 높이기 위해 집이나 학교에서 안전하게 할 수 있는 구체적이고 쉬운 맨몸 운동 1가지를 추천해주세요.

    너무 길지 않게 3~4문장 내외로 작성해주세요.
    """

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"⚠️ AI 분석 중 일시적인 오류가 발생했습니다. 나중에 다시 시도해주세요. ({e})"


def create_growth_chart(records_df, item_name):
    if records_df.empty or item_name not in records_df.columns:
        return None

    df = records_df.copy()
    df[item_name] = pd.to_numeric(df[item_name], errors="coerce")
    df["_round_num"] = pd.to_numeric(df["측정회차"], errors="coerce")
    df["_date_dt"] = pd.to_datetime(df["측정일"], errors="coerce")
    df = df.dropna(subset=[item_name])
    df = df.sort_values(["_round_num", "_date_dt"], na_position="last")

    if df.empty:
        return None

    colors = {
        "3분왕복달리기(회)": "#FF6B6B",
        "사이드스텝(회)": "#4ECDC4",
        "플랭크(초)": "#45B7D1",
        "윗몸앞으로굽히기(cm)": "#96CEB4",
    }
    color = colors.get(item_name, "#FF6B6B")

    short_name = item_name.split("(")[0]
    unit = item_name.split("(")[1].replace(")", "") if "(" in item_name else ""

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["측정회차"].astype(str) + "회차",
            y=df[item_name],
            mode="lines+markers+text",
            text=df[item_name].round(1).astype(str),
            textposition="top center",
            line=dict(color=color, width=3),
            marker=dict(size=12, color=color),
            name=short_name,
        )
    )

    fig.update_layout(
        title=dict(text=short_name, font=dict(size=16)),
        xaxis_title="측정 회차",
        yaxis_title=unit,
        template="plotly_white",
        height=300,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


# ─────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────
def main():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "student_info" not in st.session_state:
        st.session_state.student_info = {}
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False

    client = get_google_connection()
    if client is None:
        st.error("⚠️ Google Sheets 연결에 실패했습니다.")
        st.stop()

    if not st.session_state.logged_in:
        show_login_page(client)
    elif st.session_state.is_admin:
        show_admin_page(client)
    else:
        show_student_dashboard(client)


# ─────────────────────────────────────────────────────
# 로그인 페이지
# ─────────────────────────────────────────────────────
def show_login_page(client):
    st.markdown(
        """
        <div style='text-align: center; padding: 2rem;'>
            <h1>🏔️ 오르다</h1>
            <p style='font-size: 1.3rem; color: #888;'>
                <b>흥미</b>가 오르다, <b>체력</b>이 오르다, <b>건강</b>이 오르다
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### 🔑 로그인")
        students = get_student_list(client)

        if students.empty:
            st.warning("학생 데이터가 없습니다. 관리자 모드에서 초기 세팅을 진행해주세요.")
        else:
            grade_options = get_grade_options(students)
            if not grade_options:
                st.warning("학년 정보가 없습니다.")
            else:
                selected_grade = st.selectbox("학년", grade_options, format_func=lambda x: f"{x}학년")

                grade_df = students[students["학년"] == selected_grade]
                class_options = get_class_options(grade_df)

                if not class_options:
                    st.warning("해당 학년에 반 정보가 없습니다.")
                else:
                    selected_class = st.selectbox("반", class_options, format_func=lambda x: f"{x}반")

                    filtered = grade_df[grade_df["반"] == selected_class]
                    name_options = get_student_options(filtered)

                    if name_options:
                        selected_display = st.selectbox("이름", name_options)
                    else:
                        selected_display = None
                        st.warning("해당 반에 학생이 없습니다.")

                    password = st.text_input("비밀번호", type="password", placeholder="비밀번호 입력")

                    if st.button("🚀 로그인", use_container_width=True):
                        if not selected_display or not password:
                            st.warning("이름과 비밀번호를 확인해주세요.")
                        else:
                            sel_num = selected_display.split("번")[0].strip()

                            selected_student = students[
                                (students["학년"] == selected_grade) &
                                (students["반"] == selected_class) &
                                (students["번호"] == sel_num)
                            ]

                            if selected_student.empty:
                                st.error("선택한 학생 정보를 찾을 수 없습니다.")
                            else:
                                stored_password = selected_student.iloc[0]["비밀번호"]
                                if verify_password(password, stored_password):
                                    st.session_state.logged_in = True
                                    st.session_state.student_info = {
                                        "grade": selected_grade,
                                        "class": selected_class,
                                        "num": sel_num,
                                        "name": selected_student.iloc[0]["이름"],
                                    }
                                    st.session_state.is_admin = False
                                    st.rerun()
                                else:
                                    st.error("비밀번호가 틀렸습니다.")

        st.markdown("---")
        with st.expander("🔧 관리자 모드"):
            admin_pw = st.text_input("관리자 비밀번호", type="password", key="admin_pw")
            admin_secret = st.secrets.get("admin_password")

            if st.button("관리자 로그인"):
                if not admin_secret:
                    st.error("Secrets에 'admin_password'가 설정되지 않았습니다.")
                elif admin_pw == admin_secret:
                    st.session_state.logged_in = True
                    st.session_state.is_admin = True
                    st.session_state.student_info = {}
                    st.rerun()
                else:
                    st.error("관리자 비밀번호가 틀렸습니다.")

        st.markdown("---")
        with st.expander("📄 개인정보 처리방침"):
            st.markdown(PRIVACY_POLICY_MD)


# ─────────────────────────────────────────────────────
# 학생 대시보드
# ─────────────────────────────────────────────────────
def show_student_dashboard(client):
    info = st.session_state.student_info

    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f"### 🏔️ {info['grade']}학년 {info['class']}반 {info['name']}님의 오르다")
    with col2:
        if st.button("🚪 로그아웃"):
            st.session_state.logged_in = False
            st.session_state.student_info = {}
            st.session_state.is_admin = False
            st.rerun()

    screen = st.radio(
        "메뉴 선택",
        ["📝 기록 입력", "📊 성장 분석"],
        horizontal=True,
        label_visibility="collapsed",
    )

    records = get_student_records(client, info["grade"], info["class"], info["num"])

    if screen == "📝 기록 입력":
        show_record_input(client, info, records)
    else:
        show_growth_analysis(records, info)


def show_record_input(client, info, records):
    st.markdown("#### 📝 체력 측정 기록 입력")

    timer_html = """
    <div style="font-family: 'Malgun Gothic', sans-serif; text-align: center; padding: 10px; background: #f0f2f6; border-radius: 10px; margin-bottom: 20px;">
        <h4 style="margin-top: 0; color: #31333F;">⏱️ 측정 도우미</h4>

        <div style="display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 150px; padding: 15px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                <div style="font-size: 14px; font-weight: bold; color: #666;">⏳ 20초 타이머</div>
                <div id="timerDisplay" style="font-size: 28px; font-weight: bold; color: #ff4b4b; margin: 10px 0;">20.00</div>
                <button onclick="startTimer()" style="padding: 8px 15px; border: none; border-radius: 5px; background: #4CAF50; color: white; cursor: pointer; font-weight: bold;">시작</button>
                <button onclick="resetTimer()" style="padding: 8px 15px; border: none; border-radius: 5px; background: #f44336; color: white; cursor: pointer; font-weight: bold;">리셋</button>
            </div>

            <div style="flex: 1; min-width: 150px; padding: 15px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                <div style="font-size: 14px; font-weight: bold; color: #666;">⏱️ 스톱워치</div>
                <div id="stopwatchDisplay" style="font-size: 28px; font-weight: bold; color: #31333F; margin: 10px 0;">00:00.00</div>
                <button onclick="startStopwatch()" id="swStartBtn" style="padding: 8px 15px; border: none; border-radius: 5px; background: #008CBA; color: white; cursor: pointer; font-weight: bold;">시작</button>
                <button onclick="resetStopwatch()" style="padding: 8px 15px; border: none; border-radius: 5px; background: #555; color: white; cursor: pointer; font-weight: bold;">리셋</button>
            </div>
        </div>
    </div>

    <script>
        let timerInterval;
        let timerTime = 20000;
        const timerDisplay = document.getElementById('timerDisplay');

        function updateTimerDisplay(ms) {
            let seconds = Math.floor(ms / 1000);
            let milliseconds = Math.floor((ms % 1000) / 10);
            timerDisplay.innerText = seconds + "." + (milliseconds < 10 ? "0" : "") + milliseconds;
        }

        function startTimer() {
            clearInterval(timerInterval);
            timerTime = 20000;
            timerDisplay.style.color = "#ff4b4b";
            timerInterval = setInterval(() => {
                timerTime -= 10;
                if (timerTime <= 0) {
                    clearInterval(timerInterval);
                    timerTime = 0;
                    timerDisplay.innerText = "종료! 🔔";
                    timerDisplay.style.color = "#4CAF50";
                } else {
                    updateTimerDisplay(timerTime);
                }
            }, 10);
        }

        function resetTimer() {
            clearInterval(timerInterval);
            timerTime = 20000;
            timerDisplay.style.color = "#ff4b4b";
            updateTimerDisplay(timerTime);
        }

        let swInterval;
        let swTime = 0;
        let swRunning = false;
        const swDisplay = document.getElementById('stopwatchDisplay');
        const swStartBtn = document.getElementById('swStartBtn');

        function updateSwDisplay(ms) {
            let minutes = Math.floor(ms / 60000);
            let seconds = Math.floor((ms % 60000) / 1000);
            let milliseconds = Math.floor((ms % 1000) / 10);
            swDisplay.innerText =
                (minutes < 10 ? "0" : "") + minutes + ":" +
                (seconds < 10 ? "0" : "") + seconds + "." +
                (milliseconds < 10 ? "0" : "") + milliseconds;
        }

        function startStopwatch() {
            if (!swRunning) {
                swRunning = true;
                swStartBtn.innerText = "정지";
                swStartBtn.style.background = "#ff9800";
                let startTime = Date.now() - swTime;
                swInterval = setInterval(() => {
                    swTime = Date.now() - startTime;
                    updateSwDisplay(swTime);
                }, 10);
            } else {
                swRunning = false;
                swStartBtn.innerText = "이어서";
                swStartBtn.style.background = "#008CBA";
                clearInterval(swInterval);
            }
        }

        function resetStopwatch() {
            swRunning = false;
            clearInterval(swInterval);
            swTime = 0;
            swStartBtn.innerText = "시작";
            swStartBtn.style.background = "#008CBA";
            updateSwDisplay(swTime);
        }
    </script>
    """

    components.html(timer_html, height=220)

    today_str = now_kst().strftime("%Y-%m-%d")

    already_saved_today = False
    if not records.empty and "측정일" in records.columns:
        if today_str in records["측정일"].values:
            already_saved_today = True

    if already_saved_today:
        st.warning("🚨 오늘의 체력 기록을 이미 저장했습니다! 대단해요! 👍\n\n(잘못 입력하여 수정이 필요하다면 선생님께 말씀해주세요.)")
        return

    if records.empty:
        next_round = 1
    else:
        existing_rounds = pd.to_numeric(records["측정회차"], errors="coerce").dropna()
        next_round = int(existing_rounds.max()) + 1 if not existing_rounds.empty else 1

    with st.form("student_record_form"):
        col_round, col_date = st.columns(2)
        with col_round:
            round_num = st.number_input(
                "측정 회차",
                min_value=1,
                value=next_round,
                disabled=True,
                help="학생 계정에서는 다음 회차만 자동으로 입력됩니다.",
            )
        with col_date:
            measure_date = st.date_input("측정일", value=now_kst().date())

        st.markdown("---")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### 🏃 심폐지구력")
            v1_raw = st.text_input(
                "3분 왕복달리기 (회)",
                value="",
                placeholder="미입력",
                key="sv1",
                help="전원 동시, 2인 1조",
            )
            st.markdown("##### 💪 근지구력")
            v3_raw = st.text_input(
                "플랭크 (초, 최대 180초)",
                value="",
                placeholder="미입력",
                key="sv3",
                help="2인 1조 관찰",
            )
        with c2:
            st.markdown("##### ⚡ 순발력")
            v2_raw = st.text_input(
                "사이드스텝 (회/20초)",
                value="",
                placeholder="미입력",
                key="sv2",
            )
            st.markdown("##### 🧘 유연성")
            v4_raw = st.text_input(
                "윗몸앞으로굽히기 (cm)",
                value="",
                placeholder="미입력",
                key="sv4",
                help="0.5 단위 입력 가능",
            )

        submitted = st.form_submit_button("💾 기록 저장", use_container_width=True)

    if submitted:
        errors = []

        v1, err = parse_optional_int(v1_raw, "3분 왕복달리기 (회)", min_value=0)
        if err:
            errors.append(err)

        v2, err = parse_optional_int(v2_raw, "사이드스텝 (회/20초)", min_value=0)
        if err:
            errors.append(err)

        v3, err = parse_optional_int(v3_raw, "플랭크 (초)", min_value=0, max_value=180)
        if err:
            errors.append(err)

        v4, err = parse_optional_float(v4_raw, "윗몸앞으로굽히기 (cm)", min_value=-30.0)
        if err:
            errors.append(err)

        if errors:
            for err in errors:
                st.error(err)
            return

        record = [
            info["grade"],
            info["class"],
            info["num"],
            info["name"],
            round_num,
            measure_date.strftime("%Y-%m-%d"),
            "" if v1 is None else v1,
            "" if v2 is None else v2,
            "" if v3 is None else v3,
            "" if v4 is None else v4,
        ]

        ok, msg = add_record(client, record)
        if ok:
            st.success(f"✅ {msg}")
            st.rerun()
        else:
            st.error(f"❌ {msg}")

    if not records.empty:
        st.markdown("---")
        st.markdown("#### 📋 나의 기록")

        display_cols = [
            "측정회차", "측정일",
            "3분왕복달리기(회)", "사이드스텝(회)",
            "플랭크(초)", "윗몸앞으로굽히기(cm)",
        ]
        available_cols = [c for c in display_cols if c in records.columns]
        st.dataframe(records[available_cols], use_container_width=True, hide_index=True)


def show_growth_analysis(records, info):
    st.markdown("#### 📊 나의 성장 분석")

    if records.empty:
        st.info("아직 측정 기록이 없어요. '기록 입력'에서 먼저 기록해보세요! 🏃")
        return

    col1, col2 = st.columns(2)

    for idx, item in enumerate(ITEMS):
        target_col = [col1, col2][idx % 2]
        with target_col:
            st.markdown(f"**{ITEM_LABELS[item]}**")

            fig = create_growth_chart(records, item)
            if fig is not None:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"{item.split('(')[0]} 기록이 없습니다.")

            short_name = item.split("(")[0]
            with st.spinner(f"🤖 AI가 {short_name} 기록을 분석하고 있어요..."):
                feedback = generate_gemini_feedback(records, item, info["name"])

            if feedback.startswith("💬") or feedback.startswith("⚠️"):
                st.info(feedback)
            else:
                st.success(f"**🤖 AI 체육 선생님의 맞춤 피드백**\n\n{feedback}")
            st.markdown("")

    st.markdown("---")
    st.markdown("#### 📊 4종목 누적 기록 요약")

    summary_data = []
    for item in ITEMS:
        if item not in records.columns:
            continue

        vals = pd.to_numeric(records[item], errors="coerce").dropna()
        if vals.empty:
            continue

        summary_data.append({
            "종목": item.split("(")[0],
            "단위": item.split("(")[1].replace(")", ""),
            "최초 기록": round(float(vals.iloc[0]), 1),
            "최근 기록": round(float(vals.iloc[-1]), 1),
            "최고 기록": round(float(vals.max()), 1),
            "변화량": round(float(vals.iloc[-1] - vals.iloc[0]), 1),
            "측정 횟수": int(len(vals)),
        })

    if summary_data:
        summary_df = pd.DataFrame(summary_data)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
    else:
        st.info("아직 기록이 없습니다.")


# ─────────────────────────────────────────────────────
# 관리자 페이지
# ─────────────────────────────────────────────────────
def show_admin_page(client):
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("### 🔧 관리자 페이지")
    with col2:
        if st.button("🚪 로그아웃"):
            st.session_state.logged_in = False
            st.session_state.is_admin = False
            st.session_state.student_info = {}
            st.rerun()

    admin_menu = st.radio(
        "관리 메뉴",
        ["🔄 초기 세팅", "📝 기록 입력", "👥 학생 관리", "📊 전체 기록"],
        horizontal=True,
        label_visibility="collapsed",
    )

    # ─── 메뉴1: 초기 세팅 ───
    if admin_menu == "🔄 초기 세팅":
        st.markdown("#### 🔄 초기 데이터 생성")
        st.warning("⚠️ 처음 한 번만 실행하세요. 기존 데이터가 있으면 건너뜁니다.")

        if st.button("🚀 초기 데이터 생성", use_container_width=True):
            with st.spinner("생성 중..."):
                s1 = init_student_list(client)
                s2 = init_records_sheet(client)

                if s1 and s2:
                    clear_data_caches()
                    st.success("✅ 초기 데이터 생성 완료!")
                    st.info("3~6학년 1반(각 18명 기준) 더미 데이터가 등록되었습니다.")
                    st.info("👥 학생 관리 메뉴에서 실제 이름으로 수정해주세요.")
                else:
                    st.error("❌ 초기 세팅에 실패했습니다.")

    # ─── 메뉴2: 기록 입력 ───
    elif admin_menu == "📝 기록 입력":
        st.markdown("#### 📝 체력 측정 기록 입력 (관리자)")
        students = get_student_list(client)

        if students.empty:
            st.warning("먼저 초기 세팅을 진행해주세요.")
        else:
            col_sel1, col_sel2, col_sel3 = st.columns(3)

            with col_sel1:
                grade_options = get_grade_options(students)
                if not grade_options:
                    st.warning("학년 정보가 없습니다.")
                    return
                grade = st.selectbox(
                    "학년",
                    grade_options,
                    format_func=lambda x: f"{x}학년",
                    key="ar_grade",
                )

            filtered_grade = students[students["학년"] == grade]

            with col_sel2:
                class_options = get_class_options(filtered_grade)
                if not class_options:
                    st.warning("해당 학년의 반 정보가 없습니다.")
                    return
                cls_val = st.selectbox(
                    "반",
                    class_options,
                    format_func=lambda x: f"{x}반",
                    key="ar_class",
                )

            filtered_students = filtered_grade[filtered_grade["반"] == cls_val]
            student_options = get_student_options(filtered_students)

            with col_sel3:
                if not student_options:
                    st.warning("해당 반에 학생이 없습니다.")
                    return
                selected = st.selectbox("학생 선택", student_options, key="ar_student")

            if selected:
                s_num = selected.split("번")[0].strip()
                s_name = selected.split(" - ", 1)[1]
                admin_records = get_student_records(client, grade, cls_val, s_num)

                if admin_records.empty:
                    next_round = 1
                else:
                    existing_rounds = pd.to_numeric(admin_records["측정회차"], errors="coerce").dropna()
                    next_round = int(existing_rounds.max()) + 1 if not existing_rounds.empty else 1

                with st.form("admin_record_form"):
                    st.info(f"현재 입력 대상: {grade}학년 {cls_val}반 {selected}")

                    col_r, col_d = st.columns(2)
                    with col_r:
                        round_num = st.number_input(
                            "측정 회차",
                            min_value=1,
                            value=next_round,
                            key="ar_round",
                        )
                    with col_d:
                        measure_date = st.date_input("측정일", value=now_kst().date(), key="ar_date")

                    st.markdown("**체력 측정 항목 (측정하지 않은 종목은 비워두세요)**")
                    c1, c2 = st.columns(2)

                    with c1:
                        v1_raw = st.text_input(
                            "3분 왕복달리기 (회)",
                            value="",
                            placeholder="미측정",
                            key="ar_v1",
                        )
                        v3_raw = st.text_input(
                            "플랭크 (초, 최대 180)",
                            value="",
                            placeholder="미측정",
                            key="ar_v3",
                        )
                    with c2:
                        v2_raw = st.text_input(
                            "사이드스텝 (회/20초)",
                            value="",
                            placeholder="미측정",
                            key="ar_v2",
                        )
                        v4_raw = st.text_input(
                            "윗몸앞으로굽히기 (cm)",
                            value="",
                            placeholder="미측정",
                            key="ar_v4",
                        )

                    submitted = st.form_submit_button("💾 기록 저장", use_container_width=True)

                if submitted:
                    errors = []

                    v1, err = parse_optional_int(v1_raw, "3분 왕복달리기 (회)", min_value=0)
                    if err:
                        errors.append(err)

                    v2, err = parse_optional_int(v2_raw, "사이드스텝 (회/20초)", min_value=0)
                    if err:
                        errors.append(err)

                    v3, err = parse_optional_int(v3_raw, "플랭크 (초)", min_value=0, max_value=180)
                    if err:
                        errors.append(err)

                    v4, err = parse_optional_float(v4_raw, "윗몸앞으로굽히기 (cm)", min_value=-30.0)
                    if err:
                        errors.append(err)

                    if errors:
                        for err in errors:
                            st.error(err)
                        return

                    record = [
                        grade,
                        cls_val,
                        s_num,
                        s_name,
                        round_num,
                        measure_date.strftime("%Y-%m-%d"),
                        "" if v1 is None else v1,
                        "" if v2 is None else v2,
                        "" if v3 is None else v3,
                        "" if v4 is None else v4,
                    ]

                    ok, msg = add_record(client, record)
                    if ok:
                        st.success(f"✅ {s_name} 학생의 {msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

    # ─── 메뉴3: 학생 관리 ───
    elif admin_menu == "👥 학생 관리":
        st.markdown("#### 👥 학생 명단 관리")
        students = get_student_list(client)

        if students.empty:
            st.warning("먼저 초기 세팅을 진행해주세요.")
        else:
            display_students = students[["학년", "반", "번호", "이름"]].copy()
            display_students = sort_students_df(display_students)
            st.dataframe(display_students, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("**➕ 학생 추가**")
            with st.form("add_student_form"):
                ac1, ac2, ac3, ac4, ac5 = st.columns(5)
                with ac1:
                    new_grade = st.selectbox("학년", ["3", "4", "5", "6"], key="new_grade")
                with ac2:
                    new_class = st.text_input("반", value="1", key="new_class")
                with ac3:
                    new_num = st.text_input("번호", key="new_num")
                with ac4:
                    new_name = st.text_input("이름", key="new_name")
                with ac5:
                    new_pw = st.text_input("비밀번호", type="password", key="new_pw")

                submitted_add = st.form_submit_button("➕ 추가", use_container_width=True)

            if submitted_add:
                ok, msg = add_student(client, new_grade, new_class, new_num, new_name, new_pw)
                if ok:
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.warning(msg)

            st.markdown("---")
            st.markdown("**🗑️ 학생 삭제**")

            grade_options = get_grade_options(students)
            if grade_options:
                del_col1, del_col2, del_col3 = st.columns(3)
                with del_col1:
                    del_grade = st.selectbox(
                        "학년 선택",
                        grade_options,
                        key="del_grade",
                        format_func=lambda x: f"{x}학년",
                    )

                del_grade_df = students[students["학년"] == del_grade]

                with del_col2:
                    del_class_options = get_class_options(del_grade_df)
                    if not del_class_options:
                        st.warning("삭제 가능한 반 정보가 없습니다.")
                        del_grade = None
                    else:
                        del_class = st.selectbox(
                            "반 선택",
                            del_class_options,
                            key="del_class",
                            format_func=lambda x: f"{x}반",
                        )

                if del_grade is not None and del_class_options:
                    del_students_df = del_grade_df[del_grade_df["반"] == del_class]
                    del_options = get_student_options(del_students_df)

                    with del_col3:
                        if del_options:
                            del_selected = st.selectbox("삭제할 학생", del_options, key="del_student")
                        else:
                            del_selected = None
                            st.warning("삭제할 학생이 없습니다.")

                    delete_records_too = st.checkbox("체력기록도 함께 삭제", value=False, key="delete_records_too")

                    if st.button("🗑️ 삭제", use_container_width=True):
                        if not del_selected:
                            st.warning("삭제할 학생을 선택해주세요.")
                        else:
                            d_num = del_selected.split("번")[0].strip()
                            ok, msg = delete_student(client, del_grade, del_class, d_num, delete_records=delete_records_too)
                            if ok:
                                st.success(f"✅ {msg}")
                                st.rerun()
                            else:
                                st.error(f"❌ {msg}")

            st.markdown("---")
            st.markdown("**✏️ 학생 정보 수정**")

            if grade_options:
                edit_col1, edit_col2, edit_col3 = st.columns(3)
                with edit_col1:
                    edit_grade = st.selectbox(
                        "학년 선택",
                        grade_options,
                        key="edit_grade",
                        format_func=lambda x: f"{x}학년",
                    )

                edit_grade_df = students[students["학년"] == edit_grade]

                with edit_col2:
                    edit_class_options = get_class_options(edit_grade_df)
                    if not edit_class_options:
                        st.warning("수정 가능한 반 정보가 없습니다.")
                        edit_grade = None
                    else:
                        edit_class = st.selectbox(
                            "반 선택",
                            edit_class_options,
                            key="edit_class",
                            format_func=lambda x: f"{x}반",
                        )

                if edit_grade is not None and edit_class_options:
                    edit_students_df = edit_grade_df[edit_grade_df["반"] == edit_class]
                    edit_options = get_student_options(edit_students_df)

                    with edit_col3:
                        if edit_options:
                            edit_selected = st.selectbox("수정할 학생", edit_options, key="edit_student")
                        else:
                            edit_selected = None
                            st.warning("수정할 학생이 없습니다.")

                    ec1, ec2 = st.columns(2)
                    with ec1:
                        edit_name = st.text_input("새 이름", key="edit_name")
                    with ec2:
                        edit_pw = st.text_input("새 비밀번호", type="password", key="edit_pw")

                    sync_record_name = st.checkbox("기존 체력기록 이름도 함께 수정", value=True, key="sync_record_name")

                    if st.button("✏️ 수정", use_container_width=True):
                        if not edit_selected:
                            st.warning("수정할 학생을 선택해주세요.")
                        else:
                            e_num = edit_selected.split("번")[0].strip()
                            ok, msg = update_student(
                                client,
                                edit_grade,
                                edit_class,
                                e_num,
                                new_name=edit_name,
                                new_password=edit_pw,
                                sync_record_name=sync_record_name,
                            )
                            if ok:
                                st.success(f"✅ {msg}")
                                st.rerun()
                            else:
                                st.warning(msg)

    # ─── 메뉴4: 전체 기록 ───
    elif admin_menu == "📊 전체 기록":
        st.markdown("#### 📊 전체 기록 확인")
        all_records = get_all_records(client)

        if all_records.empty:
            st.info("아직 입력된 기록이 없습니다.")
        else:
            vf1, vf2 = st.columns(2)

            with vf1:
                grade_options = ["전체"] + get_grade_options(all_records)
                view_grade = st.selectbox(
                    "학년 선택",
                    grade_options,
                    key="view_grade",
                )

            filtered_records = all_records.copy()
            if view_grade != "전체":
                filtered_records = filtered_records[filtered_records["학년"] == view_grade]

            with vf2:
                class_source = filtered_records if view_grade != "전체" else all_records
                class_options = ["전체"] + get_class_options(class_source)
                view_class = st.selectbox("반 선택", class_options, key="view_class")

            if view_class != "전체":
                filtered_records = filtered_records[filtered_records["반"] == view_class]

            display_cols = [
                "학년", "반", "번호", "이름", "측정회차", "측정일",
                "3분왕복달리기(회)", "사이드스텝(회)", "플랭크(초)", "윗몸앞으로굽히기(cm)"
            ]
            available_cols = [c for c in display_cols if c in filtered_records.columns]
            st.dataframe(filtered_records[available_cols], use_container_width=True, hide_index=True)

    st.markdown("---")
    with st.expander("📄 개인정보 처리방침"):
        st.markdown(PRIVACY_POLICY_MD)


if __name__ == "__main__":
    main()

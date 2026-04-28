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
SHEET_GROUPS = "모둠"
SHEET_CHALLENGE = "챌린지기록"
KST = timezone(timedelta(hours=9))

# 오르다 100 챌린지 설정
CHALLENGE_START_DATE = "2026-04-28"  # 챌린지 시작일 (2회차 측정일)
CHALLENGE_GOAL = 100  # 주당 목표 점수
CHALLENGE_MAX_COUNT = 50  # 1회 입력 최대 횟수
CHALLENGE_MAX_PER_DAY = 3  # 같은 종목 하루 최대 입력 횟수
CHALLENGE_RECENT_WEEKS = 12  # 드롭다운에 표시할 최근 주차 수

# 챌린지 체력 요소 (라벨, 이모지, 예시 운동)
CHALLENGE_ELEMENTS = [
    ("심폐지구력", "🏃", "버피 · 줄넘기(5회)"),
    ("근지구력", "💪", "플랭크(5초) · 스쿼트 · 니푸시업"),
    ("순발력", "⚡", "라인터치 · 사이드스텝"),
    ("유연성", "🧘", "스트레칭(10초) · 앉아 굽히기(10초)"),
]

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


def get_current_week() -> Optional[int]:
    """오늘이 챌린지 몇 주차인지 반환. 시작 전이면 None. 상한 없음 (무제한)"""
    today = now_kst().date()
    start = datetime.strptime(CHALLENGE_START_DATE, "%Y-%m-%d").date()

    if today < start:
        return None

    days_passed = (today - start).days
    week = days_passed // 7 + 1
    return week


def get_available_weeks(recent_only: bool = True) -> List[int]:
    """
    현재 시점까지 열린 주차 목록.
    recent_only=True면 최근 CHALLENGE_RECENT_WEEKS주만, False면 전체.
    최신 주차가 맨 앞에 오도록 내림차순 정렬.
    """
    current = get_current_week()
    if current is None:
        return []
    if recent_only:
        start_week = max(1, current - CHALLENGE_RECENT_WEEKS + 1)
    else:
        start_week = 1
    return list(range(current, start_week - 1, -1))


def get_week_date_range(week: int) -> Tuple[str, str]:
    """특정 주차의 시작일/종료일 반환"""
    start = datetime.strptime(CHALLENGE_START_DATE, "%Y-%m-%d").date()
    week_start = start + timedelta(days=(week - 1) * 7)
    week_end = week_start + timedelta(days=6)
    return week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d")


def format_week_label(week: int, current_week: Optional[int] = None) -> str:
    """드롭다운용 주차 라벨 생성: '3주차 (5/20~5/26) ⭐'"""
    week_start, week_end = get_week_date_range(week)
    # 월/일만 간략하게 표시
    start_short = datetime.strptime(week_start, "%Y-%m-%d").strftime("%-m/%-d") if hasattr(datetime, 'strptime') else week_start[5:].replace("-", "/")
    try:
        start_dt = datetime.strptime(week_start, "%Y-%m-%d")
        end_dt = datetime.strptime(week_end, "%Y-%m-%d")
        start_short = f"{start_dt.month}/{start_dt.day}"
        end_short = f"{end_dt.month}/{end_dt.day}"
    except Exception:
        start_short = week_start[5:]
        end_short = week_end[5:]

    label = f"{week}주차 ({start_short}~{end_short})"
    if current_week is not None and week == current_week:
        label += " ⭐"
    return label


def clear_data_caches():
    get_student_list.clear()
    get_student_records.clear()
    get_all_records.clear()
    get_group_data.clear()
    get_challenge_records.clear()


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


def init_challenge_sheet(client) -> bool:
    ws = get_worksheet(client, SHEET_CHALLENGE)
    if ws is None:
        return False

    existing = gs_retry(lambda: ws.get_all_values())
    if len(existing) <= 1:
        headers = [
            "학년", "반", "번호", "이름", "주차", "입력일시", "체력요소", "횟수", "기록ID"
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


@st.cache_data(ttl=60)
def get_group_data(_client):
    ws = get_worksheet(_client, SHEET_GROUPS, create_if_missing=False)
    if ws is None:
        return pd.DataFrame()
    data = gs_retry(lambda: ws.get_all_records())
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    # 셀값 정리 (문자열 공백/NaN 제거)
    for col in df.columns:
        df[col] = df[col].apply(clean_cell)
    return df


def get_student_group(group_df, grade, cls, name):
    """학생의 모둠 정보 반환. 없으면 None"""
    if group_df.empty:
        return None
    match = group_df[
        (group_df["학년"].astype(str) == str(grade)) &
        (group_df["반"].astype(str) == str(cls)) &
        (group_df["학생이름"] == str(name))
    ]
    if match.empty:
        return None
    row = match.iloc[0]
    group_num = str(row.get("모둠번호", ""))
    group_name = str(row.get("모둠이름", "")).strip()
    if not group_name:
        group_name = f"{group_num}모둠"
    return {"번호": group_num, "이름": group_name}


def get_group_members(group_df, grade, cls, group_num):
    """같은 모둠 학생 목록 반환"""
    if group_df.empty:
        return []
    members = group_df[
        (group_df["학년"].astype(str) == str(grade)) &
        (group_df["반"].astype(str) == str(cls)) &
        (group_df["모둠번호"].astype(str) == str(group_num))
    ]
    return members["학생이름"].tolist()


def get_group_avg_records(all_records_df, group_df, grade, cls, group_num):
    """모둠원 전체 최근 기록의 평균 계산"""
    members = get_group_members(group_df, grade, cls, group_num)
    if not members or all_records_df.empty:
        return pd.Series(dtype=float)

    result = {}
    for item in ITEMS:
        vals = []
        for name in members:
            member_records = all_records_df[
                (all_records_df["학년"].astype(str) == str(grade)) &
                (all_records_df["반"].astype(str) == str(cls)) &
                (all_records_df["이름"] == name)
            ]
            if member_records.empty or item not in member_records.columns:
                continue
            numeric = pd.to_numeric(member_records[item], errors="coerce").dropna()
            if not numeric.empty:
                vals.append(float(numeric.iloc[-1]))  # 가장 최근 기록
        if vals:
            result[item] = round(sum(vals) / len(vals), 1)
    return pd.Series(result)


# ─── 챌린지 관련 함수 ───
@st.cache_data(ttl=60)
def get_challenge_records(_client):
    ws = get_worksheet(_client, SHEET_CHALLENGE, create_if_missing=False)
    if ws is None:
        return pd.DataFrame()
    data = gs_retry(lambda: ws.get_all_records())
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    for col in ["학년", "반", "번호", "이름", "주차", "입력일시", "체력요소", "기록ID"]:
        if col in df.columns:
            df[col] = df[col].apply(clean_cell)
    return df


def get_my_week_challenge(challenge_df, grade, cls, num, week):
    """내 특정 주차 기록 전체 반환 (여러 행)"""
    if challenge_df.empty:
        return pd.DataFrame()
    df = challenge_df[
        (challenge_df["학년"].astype(str) == str(grade)) &
        (challenge_df["반"].astype(str) == str(cls)) &
        (challenge_df["번호"].astype(str) == str(num)) &
        (challenge_df["주차"].astype(str) == str(week))
    ].copy()
    # 최신순 정렬
    if not df.empty and "입력일시" in df.columns:
        df = df.sort_values("입력일시", ascending=False)
    return df


def get_my_today_count_by_element(challenge_df, grade, cls, num, element):
    """오늘 내가 특정 체력 요소로 기록한 횟수 (장난 방지용)"""
    if challenge_df.empty:
        return 0
    today_str = now_kst().strftime("%Y-%m-%d")
    df = challenge_df[
        (challenge_df["학년"].astype(str) == str(grade)) &
        (challenge_df["반"].astype(str) == str(cls)) &
        (challenge_df["번호"].astype(str) == str(num)) &
        (challenge_df["체력요소"] == element)
    ]
    if df.empty:
        return 0
    # 입력일시 앞 10자리가 오늘 날짜와 같은지 확인
    today_df = df[df["입력일시"].str[:10] == today_str]
    return len(today_df)


def get_group_challenge_total(challenge_df, group_df, grade, cls, group_num, week):
    """모둠원 전체의 특정 주차 합계 + 입력 현황 반환"""
    members = get_group_members(group_df, grade, cls, group_num)
    if not members:
        return {"total": 0, "members_status": []}

    members_status = []
    total = 0

    for name in members:
        if challenge_df.empty:
            members_status.append({"name": name, "sum": 0, "count": 0})
            continue

        match = challenge_df[
            (challenge_df["학년"].astype(str) == str(grade)) &
            (challenge_df["반"].astype(str) == str(cls)) &
            (challenge_df["이름"] == name) &
            (challenge_df["주차"].astype(str) == str(week))
        ]

        if match.empty:
            members_status.append({"name": name, "sum": 0, "count": 0})
        else:
            my_sum = pd.to_numeric(match["횟수"], errors="coerce").fillna(0).sum()
            my_sum = int(my_sum)
            members_status.append({
                "name": name,
                "sum": my_sum,
                "count": len(match),
            })
            total += my_sum

    return {"total": total, "members_status": members_status}


def get_group_cumulative_total(challenge_df, group_df, grade, cls, group_num):
    """모둠의 전체 기간 누적 합계 반환"""
    members = get_group_members(group_df, grade, cls, group_num)
    if not members or challenge_df.empty:
        return {"total": 0, "weeks_achieved": 0, "total_weeks": 0}

    total = 0
    weeks_achieved = 0
    total_weeks = 0

    # 모든 주차 순회
    all_weeks = pd.to_numeric(challenge_df["주차"], errors="coerce").dropna().unique()

    for week in all_weeks:
        week = int(week)
        total_weeks += 1
        week_result = get_group_challenge_total(
            challenge_df, group_df, grade, cls, group_num, week
        )
        total += week_result["total"]
        if week_result["total"] >= CHALLENGE_GOAL:
            weeks_achieved += 1

    return {
        "total": total,
        "weeks_achieved": weeks_achieved,
        "total_weeks": total_weeks,
    }


def get_my_cumulative_total(challenge_df, grade, cls, num):
    """개인 누적 총합 반환"""
    if challenge_df.empty:
        return {"total": 0, "record_count": 0, "weeks_participated": 0}

    my_records = challenge_df[
        (challenge_df["학년"].astype(str) == str(grade)) &
        (challenge_df["반"].astype(str) == str(cls)) &
        (challenge_df["번호"].astype(str) == str(num))
    ]

    if my_records.empty:
        return {"total": 0, "record_count": 0, "weeks_participated": 0}

    total = int(pd.to_numeric(my_records["횟수"], errors="coerce").fillna(0).sum())
    weeks = my_records["주차"].astype(str).nunique()

    return {
        "total": total,
        "record_count": len(my_records),
        "weeks_participated": weeks,
    }


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


def add_challenge_record(client, grade, cls, num, name, week, element, count):
    """챌린지 기록 추가 (누적형)"""
    ws = get_worksheet(client, SHEET_CHALLENGE)
    if ws is None:
        return False, "챌린지기록 시트에 접근할 수 없습니다."

    # 횟수 검증
    if count <= 0:
        return False, "횟수는 1 이상이어야 해요."
    if count > CHALLENGE_MAX_COUNT:
        return False, f"1회 기록은 최대 {CHALLENGE_MAX_COUNT}회까지만 입력할 수 있어요."

    # 하루 같은 종목 입력 횟수 제한
    challenge_df = get_challenge_records(client)
    today_count = get_my_today_count_by_element(challenge_df, grade, cls, num, element)
    if today_count >= CHALLENGE_MAX_PER_DAY:
        return False, f"오늘 '{element}' 종목은 이미 {CHALLENGE_MAX_PER_DAY}번 기록했어요. 내일 다시 도전해봐요!"

    # 고유 기록 ID 생성 (타임스탬프 + 학생 식별자)
    now = now_kst()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    record_id = f"{timestamp}_{grade}-{cls}-{num}"
    input_datetime = now.strftime("%Y-%m-%d %H:%M:%S")

    new_row = [
        str(grade), str(cls), str(num), name, str(week),
        input_datetime, element, int(count), record_id
    ]

    gs_retry(lambda: ws.append_row(new_row))
    clear_data_caches()
    return True, f"{element} {count}회 기록 추가 완료! 💪"


def delete_challenge_record(client, record_id):
    """챌린지 기록 ID로 삭제"""
    ws = get_worksheet(client, SHEET_CHALLENGE, create_if_missing=False)
    if ws is None:
        return False, "챌린지기록 시트를 찾을 수 없어요."

    all_data = gs_retry(lambda: ws.get_all_values())
    target_row = None

    for i, row in enumerate(all_data):
        if i == 0:
            continue
        # 기록ID는 9번째 열 (index 8)
        if len(row) >= 9 and str(row[8]) == str(record_id):
            target_row = i + 1
            break

    if target_row is None:
        return False, "삭제할 기록을 찾지 못했어요."

    gs_retry(lambda: ws.delete_rows(target_row))
    clear_data_caches()
    return True, "기록이 삭제되었어요."


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
        ["📝 기록 입력", "📊 성장 분석", "👥 내 모둠"],
        horizontal=True,
        label_visibility="collapsed",
    )

    records = get_student_records(client, info["grade"], info["class"], info["num"])

    if screen == "📝 기록 입력":
        show_record_input(client, info, records)
    elif screen == "📊 성장 분석":
        show_growth_analysis(records, info)
    else:
        show_my_group(client, info)


def show_my_group(client, info):
    st.markdown("#### 👥 내 모둠")

    group_df = get_group_data(client)
    group_info = get_student_group(group_df, info["grade"], info["class"], info["name"])

    if group_info is None:
        st.info("아직 모둠이 배정되지 않았어요. 선생님께 문의해주세요! 🙋")
        return

    # 모둠 기본 정보
    st.success(f"🏅 **{group_info['이름']}** ({info['grade']}학년 {info['class']}반 {group_info['번호']}모둠)")

    # 모둠원 목록
    members = get_group_members(group_df, info["grade"], info["class"], group_info["번호"])
    st.markdown("**👫 모둠원**")
    if members:
        member_cols = st.columns(len(members))
        for i, name in enumerate(members):
            with member_cols[i]:
                if name == info["name"]:
                    st.markdown(f"⭐ **{name}** *(나)*")
                else:
                    st.markdown(f"👤 {name}")
    else:
        st.info("모둠원이 없습니다.")

    # 모둠 평균 체력 현황
    st.markdown("---")
    st.markdown("**📊 우리 모둠 평균 체력 (최근 측정 기준)**")
    all_records = get_all_records(client)
    avg = get_group_avg_records(all_records, group_df, info["grade"], info["class"], group_info["번호"])

    if avg.empty:
        st.info("아직 모둠원들의 기록이 없어요. 측정 후 다시 확인해보세요!")
    else:
        avg_cols = st.columns(4)
        for i, item in enumerate(ITEMS):
            with avg_cols[i]:
                label = ITEM_LABELS[item]
                unit = item.split("(")[1].replace(")", "")
                if item in avg:
                    st.metric(label=label, value=f"{avg[item]} {unit}")
                else:
                    st.metric(label=label, value="기록 없음")

    # ─── 🎯 오르다 100 챌린지 ───
    st.markdown("---")
    st.markdown("### 🎯 오르다 100 챌린지")

    current_week = get_current_week()

    if current_week is None:
        st.info(f"📅 챌린지는 **{CHALLENGE_START_DATE}**부터 시작됩니다. 조금만 기다려주세요!")
        return

    available_weeks = get_available_weeks(recent_only=True)
    selected_week = st.selectbox(
        "주차 선택",
        available_weeks,
        index=0,  # 최신 주차가 맨 앞에 있으므로 index 0
        format_func=lambda x: format_week_label(x, current_week),
        key="challenge_week",
    )

    challenge_df = get_challenge_records(client)

    # 우리 모둠 진행률 (최상단)
    result = get_group_challenge_total(
        challenge_df, group_df, info["grade"], info["class"], group_info["번호"], selected_week
    )
    total = result["total"]
    progress = min(total / CHALLENGE_GOAL, 1.0)

    col_prog1, col_prog2 = st.columns([3, 1])
    with col_prog1:
        st.progress(progress)
    with col_prog2:
        if total >= CHALLENGE_GOAL:
            st.markdown(f"### 🏆 {total} / {CHALLENGE_GOAL}")
        else:
            st.markdown(f"### {total} / {CHALLENGE_GOAL}")

    if total >= CHALLENGE_GOAL:
        extra = total - CHALLENGE_GOAL
        if extra > 0:
            st.success(f"🎉 **초과 달성!** 목표보다 {extra}회 더 해냈어요! 대단해요! 🔥")
        else:
            st.success("🎉 **목표 달성!** 우리 모둠 최고! 🏅")

    # ─── 운동 기록 추가 ───
    st.markdown(f"**➕ 운동 기록 추가하기 ({selected_week}주차)**")

    is_current_week = (selected_week == current_week)
    if not is_current_week:
        st.warning(f"⚠️ {selected_week}주차는 이미 지났어요. 기록은 이번 주에만 추가할 수 있어요.")
    else:
        element_options = [f"{emoji} {label} ({example})" for label, emoji, example in CHALLENGE_ELEMENTS]

        with st.form("challenge_add_form", clear_on_submit=True):
            fc1, fc2 = st.columns([2, 1])
            with fc1:
                selected_element_display = st.selectbox(
                    "체력 요소",
                    element_options,
                    key="ch_element",
                )
            with fc2:
                count_raw = st.text_input(
                    "횟수",
                    value="",
                    placeholder="예: 10",
                    key="ch_count",
                )
            add_submitted = st.form_submit_button("💾 기록 추가", use_container_width=True)

        st.caption(f"💡 1회 최대 {CHALLENGE_MAX_COUNT}회 · 같은 종목 하루 {CHALLENGE_MAX_PER_DAY}번까지")

        if add_submitted:
            # 선택된 체력요소 원본 라벨 추출
            selected_idx = element_options.index(selected_element_display)
            element_label = CHALLENGE_ELEMENTS[selected_idx][0]  # 예: "심폐지구력"

            count_val, err = parse_optional_int(
                count_raw, "횟수", min_value=1, max_value=CHALLENGE_MAX_COUNT
            )

            if err:
                st.error(err)
            elif count_val is None:
                st.error("횟수를 입력해주세요.")
            else:
                ok, msg = add_challenge_record(
                    client, info["grade"], info["class"], info["num"], info["name"],
                    selected_week, element_label, count_val
                )
                if ok:
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")

    # ─── 이번 주 나의 기록 목록 ───
    st.markdown(f"**📋 {selected_week}주차 나의 기록**")

    my_week_records = get_my_week_challenge(
        challenge_df, info["grade"], info["class"], info["num"], selected_week
    )

    if my_week_records.empty:
        st.info("아직 이번 주 기록이 없어요. 운동하고 기록을 남겨보세요! 💪")
    else:
        my_sum = pd.to_numeric(my_week_records["횟수"], errors="coerce").fillna(0).sum()
        st.markdown(f"**총 합계: {int(my_sum)}회** ({len(my_week_records)}건)")

        # 체력요소별 이모지 매핑
        emoji_map = {label: emoji for label, emoji, _ in CHALLENGE_ELEMENTS}

        for _, row in my_week_records.iterrows():
            element = str(row.get("체력요소", ""))
            emoji = emoji_map.get(element, "🏃")
            count = row.get("횟수", 0)
            input_dt = str(row.get("입력일시", ""))[:16]  # 분까지
            record_id = str(row.get("기록ID", ""))

            rec_col1, rec_col2, rec_col3 = st.columns([3, 1, 1])
            with rec_col1:
                st.markdown(f"{emoji} **{element}** — {input_dt}")
            with rec_col2:
                st.markdown(f"**{count}회**")
            with rec_col3:
                # 이번 주 기록만 삭제 가능
                if is_current_week and record_id:
                    if st.button("🗑️", key=f"del_{record_id}", help="이 기록 삭제"):
                        ok, msg = delete_challenge_record(client, record_id)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

    # ─── 모둠원 입력 현황 ───
    st.markdown("---")
    st.markdown(f"**👫 우리 모둠 {selected_week}주차 입력 현황**")
    for ms in result["members_status"]:
        name = ms["name"]
        is_me = "⭐ " if name == info["name"] else ""
        if ms["count"] > 0:
            st.markdown(f"{is_me}✅ **{name}**: {ms['sum']}회 *({ms['count']}건)*")
        else:
            st.markdown(f"{is_me}⏰ {name}: *아직 기록 없음*")

    # ─── 🏆 누적 통계 (명예의 전당) ───
    st.markdown("---")
    st.markdown("### 🏆 우리 모둠 누적 기록")

    cumulative = get_group_cumulative_total(
        challenge_df, group_df, info["grade"], info["class"], group_info["번호"]
    )
    my_cumulative = get_my_cumulative_total(
        challenge_df, info["grade"], info["class"], info["num"]
    )

    cum_cols = st.columns(3)
    with cum_cols[0]:
        st.metric(
            "🏅 모둠 누적 총합",
            f"{cumulative['total']:,}회",
            help="우리 모둠이 챌린지 시작부터 지금까지 쌓은 전체 기록",
        )
    with cum_cols[1]:
        if cumulative["total_weeks"] > 0:
            achievement_rate = round(cumulative["weeks_achieved"] / cumulative["total_weeks"] * 100)
            st.metric(
                "🎯 주차 달성률",
                f"{cumulative['weeks_achieved']}/{cumulative['total_weeks']}주",
                delta=f"{achievement_rate}%",
            )
        else:
            st.metric("🎯 주차 달성률", "-")
    with cum_cols[2]:
        st.metric(
            "⭐ 내 누적 기록",
            f"{my_cumulative['total']:,}회",
            help=f"내가 {my_cumulative['weeks_participated']}주 동안 쌓은 총 기록",
        )


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
        ["🔄 초기 세팅", "📝 기록 입력", "👥 학생 관리", "📊 전체 기록", "🏅 모둠 관리"],
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
                s3 = init_challenge_sheet(client)

                if s1 and s2 and s3:
                    clear_data_caches()
                    st.success("✅ 초기 데이터 생성 완료!")
                    st.info("3~6학년 1반(각 18명 기준) 더미 데이터가 등록되었습니다.")
                    st.info("📋 학생명단 / 체력기록 / 챌린지기록 시트가 자동 생성되었습니다.")
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

    # ─── 메뉴5: 모둠 관리 ───
    elif admin_menu == "🏅 모둠 관리":
        st.markdown("#### 🏅 모둠 현황")

        group_df = get_group_data(client)

        if group_df.empty:
            st.warning("모둠 시트에 데이터가 없습니다. 구글 시트 '모둠' 탭을 확인해주세요.")
            st.info("📋 헤더 순서: 학년 | 반 | 모둠번호 | 모둠이름 | 학생이름")
        else:
            # 학급 필터
            gf1, gf2 = st.columns(2)
            with gf1:
                g_grades = sorted(
                    group_df["학년"].astype(str).unique().tolist(),
                    key=lambda x: int(x) if x.isdigit() else x,
                )
                sel_grade = st.selectbox("학년", g_grades, format_func=lambda x: f"{x}학년", key="gm_grade")

            grade_group_df = group_df[group_df["학년"].astype(str) == sel_grade]

            with gf2:
                g_classes = sorted(
                    grade_group_df["반"].astype(str).unique().tolist(),
                    key=lambda x: int(x) if x.isdigit() else x,
                )
                sel_class = st.selectbox("반", g_classes, format_func=lambda x: f"{x}반", key="gm_class")

            class_group_df = grade_group_df[grade_group_df["반"].astype(str) == sel_class]
            group_nums = sorted(
                class_group_df["모둠번호"].astype(str).unique().tolist(),
                key=lambda x: int(x) if x.isdigit() else x,
            )

            st.markdown(f"**{sel_grade}학년 {sel_class}반 — 총 {len(group_nums)}모둠**")

            # 모둠별 카드 표시
            all_records = get_all_records(client)

            cols_per_row = 3
            for i in range(0, len(group_nums), cols_per_row):
                row_cols = st.columns(cols_per_row)
                for j, gnum in enumerate(group_nums[i:i + cols_per_row]):
                    with row_cols[j]:
                        g_rows = class_group_df[class_group_df["모둠번호"].astype(str) == gnum]
                        gname = ""
                        if not g_rows.empty:
                            gname = str(g_rows["모둠이름"].iloc[0]).strip()
                        if not gname:
                            gname = f"{gnum}모둠"
                        members = g_rows["학생이름"].tolist()
                        avg = get_group_avg_records(all_records, group_df, sel_grade, sel_class, gnum)

                        st.markdown(f"**🏅 {gname}**")
                        st.caption(" · ".join([f"👤{m}" for m in members]) if members else "학생 없음")
                        if not avg.empty:
                            for item in ITEMS:
                                if item in avg:
                                    unit = item.split("(")[1].replace(")", "")
                                    st.caption(f"{ITEM_LABELS[item]}: **{avg[item]}{unit}**")
                        else:
                            st.caption("기록 없음")
                        st.markdown("---")

            # ─── 🎯 오르다 100 챌린지 현황 ───
            st.markdown("---")
            st.markdown("### 🎯 오르다 100 챌린지 현황")

            current_week = get_current_week()
            if current_week is None:
                st.info(f"📅 챌린지는 {CHALLENGE_START_DATE}부터 시작됩니다.")
            else:
                ch_available_weeks = get_available_weeks(recent_only=False)
                ch_week = st.selectbox(
                    "주차 선택",
                    ch_available_weeks,
                    index=0,  # 최신 주차가 맨 앞
                    format_func=lambda x: format_week_label(x, current_week),
                    key="admin_ch_week",
                )

                challenge_df = get_challenge_records(client)
                week_start, week_end = get_week_date_range(ch_week)

                st.markdown(f"**{sel_grade}학년 {sel_class}반 · {ch_week}주차** <span style='color: gray; font-size: 12px;'>({week_start} ~ {week_end})</span>", unsafe_allow_html=True)

                if not group_nums:
                    st.info("모둠이 없습니다.")
                else:
                    ch_cols_per_row = 2
                    for i in range(0, len(group_nums), ch_cols_per_row):
                        ch_row_cols = st.columns(ch_cols_per_row)
                        for j, gnum in enumerate(group_nums[i:i + ch_cols_per_row]):
                            with ch_row_cols[j]:
                                g_rows = class_group_df[class_group_df["모둠번호"].astype(str) == gnum]
                                gname = ""
                                if not g_rows.empty:
                                    gname = str(g_rows["모둠이름"].iloc[0]).strip()
                                if not gname:
                                    gname = f"{gnum}모둠"

                                result = get_group_challenge_total(
                                    challenge_df, group_df, sel_grade, sel_class, gnum, ch_week
                                )
                                ch_total = result["total"]
                                ch_progress = min(ch_total / CHALLENGE_GOAL, 1.0)
                                entered_count = sum(1 for ms in result["members_status"] if ms["count"] > 0)
                                total_members = len(result["members_status"])

                                if ch_total >= CHALLENGE_GOAL:
                                    extra = ch_total - CHALLENGE_GOAL
                                    if extra > 0:
                                        status = f"🏆 {ch_total}/{CHALLENGE_GOAL} (+{extra})"
                                    else:
                                        status = f"🏆 {ch_total}/{CHALLENGE_GOAL} 달성!"
                                else:
                                    status = f"{ch_total}/{CHALLENGE_GOAL}"

                                st.markdown(f"**🏅 {gname}** — {status}")
                                st.progress(ch_progress)
                                st.caption(f"입력 완료: {entered_count}/{total_members}명")
                                st.markdown("")

                # 전체 통계
                if group_nums:
                    st.markdown("---")
                    st.markdown("**📈 학급 전체 통계**")
                    total_groups = len(group_nums)
                    achieved_groups = 0
                    grand_total = 0
                    for gnum in group_nums:
                        result = get_group_challenge_total(
                            challenge_df, group_df, sel_grade, sel_class, gnum, ch_week
                        )
                        grand_total += result["total"]
                        if result["total"] >= CHALLENGE_GOAL:
                            achieved_groups += 1

                    stat_cols = st.columns(3)
                    with stat_cols[0]:
                        st.metric("달성 모둠", f"{achieved_groups} / {total_groups}")
                    with stat_cols[1]:
                        st.metric("학급 총합", f"{grand_total}회")
                    with stat_cols[2]:
                        avg_per_group = round(grand_total / total_groups, 1) if total_groups > 0 else 0
                        st.metric("모둠 평균", f"{avg_per_group}회")

                # ─── 🏆 누적 랭킹 (명예의 전당) ───
                if group_nums:
                    st.markdown("---")
                    st.markdown("### 🏆 누적 랭킹 (명예의 전당)")
                    st.caption(f"챌린지 시작({CHALLENGE_START_DATE})부터 지금까지의 전체 누적")

                    ranking_data = []
                    for gnum in group_nums:
                        g_rows = class_group_df[class_group_df["모둠번호"].astype(str) == gnum]
                        gname = ""
                        if not g_rows.empty:
                            gname = str(g_rows["모둠이름"].iloc[0]).strip()
                        if not gname:
                            gname = f"{gnum}모둠"

                        cum = get_group_cumulative_total(
                            challenge_df, group_df, sel_grade, sel_class, gnum
                        )
                        ranking_data.append({
                            "모둠명": gname,
                            "누적 총합": cum["total"],
                            "달성 주차": f"{cum['weeks_achieved']} / {cum['total_weeks']}",
                            "_sort_total": cum["total"],
                            "_sort_achieved": cum["weeks_achieved"],
                        })

                    # 누적 총합 기준 정렬
                    ranking_data.sort(key=lambda x: (-x["_sort_total"], -x["_sort_achieved"]))

                    # 메달 부여
                    for idx, row in enumerate(ranking_data):
                        if idx == 0:
                            row["순위"] = "🥇 1위"
                        elif idx == 1:
                            row["순위"] = "🥈 2위"
                        elif idx == 2:
                            row["순위"] = "🥉 3위"
                        else:
                            row["순위"] = f"{idx + 1}위"

                    ranking_df = pd.DataFrame(ranking_data)
                    display_ranking = ranking_df[["순위", "모둠명", "누적 총합", "달성 주차"]].copy()
                    display_ranking["누적 총합"] = display_ranking["누적 총합"].apply(lambda x: f"{x:,}회")
                    st.dataframe(display_ranking, use_container_width=True, hide_index=True)

    st.markdown("---")
    with st.expander("📄 개인정보 처리방침"):
        st.markdown(PRIVACY_POLICY_MD)


if __name__ == "__main__":
    main()

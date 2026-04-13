import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
import time

# ─── 페이지 설정 ───
st.set_page_config(
    page_title="🏔️ 오르다",
    page_icon="🏔️",
    layout="wide"
)

# ─── Google Sheets 연결 (오류 자동 보정 및 탐지기 버전) ───
@st.cache_resource
def get_google_connection():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("🚨 Secrets에 [gcp_service_account] 정보가 없습니다. 셋팅을 확인해주세요.")
            return None
            
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"🚨 구글 서버 연결 실패: {e}")
        return None

def get_or_create_sheet(client, sheet_name):
    try:
        # 1. 파일 이름 찾기 (Secrets 설정 위치 오류 자동 보정)
        if "spreadsheet_name" in st.secrets:
            doc_name = st.secrets["spreadsheet_name"]
        elif "spreadsheet_name" in st.secrets.get("gcp_service_account", {}):
            doc_name = st.secrets["gcp_service_account"]["spreadsheet_name"]
        else:
            st.error("🚨 Secrets에 'spreadsheet_name'이 설정되지 않았습니다.")
            return None
            
        # 2. 파일 열기 시도
        try:
            spreadsheet = client.open(doc_name)
        except gspread.SpreadsheetNotFound:
            st.error(f"🚨 구글 드라이브에서 '{doc_name}' 스프레드시트를 찾을 수 없습니다!")
            st.info("💡 해결법: Secrets에 있는 client_email 주소를 스프레드시트 우측 상단 [공유] 버튼을 눌러 '편집자'로 꼭 추가해주세요.")
            return None
            
        # 3. 내부 시트(탭) 열기
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
        return worksheet
        
    except Exception as e:
        st.error(f"🚨 데이터베이스 접근 중 알 수 없는 에러 발생: {e}")
        return None

# ─── 초기 데이터 생성 ───
def init_student_list(client):
    ws = get_or_create_sheet(client, "학생명단")
    if ws is None:
        return False
    existing = ws.get_all_values()
    if len(existing) <= 1:
        headers = ["학년", "반", "번호", "이름", "비밀번호"]
        students = []
        for i in range(1, 18):
            students.append(["5", "1", str(i), f"5-1-{i}", f"{i:04d}"])
        for i in range(1, 19):
            students.append(["6", "1", str(i), f"6-1-{i}", f"{i:04d}"])
        ws.clear()
        ws.update(range_name="A1", values=[headers] + students)
        time.sleep(1)
    return True

def init_records_sheet(client):
    ws = get_or_create_sheet(client, "체력기록")
    if ws is None:
        return False
    existing = ws.get_all_values()
    if len(existing) <= 1:
        headers = ["학년", "반", "번호", "이름", "측정회차", "측정일",
                   "3분왕복달리기(회)", "사이드스텝(회)",
                   "플랭크(초)", "윗몸앞으로굽히기(cm)"]
        ws.clear()
        ws.update(range_name="A1", values=[headers])
    return True

# ─── 데이터 조회 ───
def get_student_list(client):
    ws = get_or_create_sheet(client, "학생명단")
    if ws is None:
        return pd.DataFrame()
    data = ws.get_all_records()
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data)

def get_student_records(client, grade, cls, num):
    ws = get_or_create_sheet(client, "체력기록")
    if ws is None:
        return pd.DataFrame()
    data = ws.get_all_records()
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df = df[(df["학년"].astype(str) == str(grade)) &
            (df["반"].astype(str) == str(cls)) &
            (df["번호"].astype(str) == str(num))]
    return df

def get_all_records(client):
    ws = get_or_create_sheet(client, "체력기록")
    if ws is None:
        return pd.DataFrame()
    data = ws.get_all_records()
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data)

# ─── 데이터 입력/수정/삭제 ───
def add_record(client, record):
    ws = get_or_create_sheet(client, "체력기록")
    if ws is None:
        return False
    ws.append_row(record)
    return True

def add_student(client, student_data):
    ws = get_or_create_sheet(client, "학생명단")
    if ws is None:
        return False
    ws.append_row(student_data)
    return True

def delete_student(client, grade, cls, num):
    ws = get_or_create_sheet(client, "학생명단")
    if ws is None:
        return False
    data = ws.get_all_values()
    for i, row in enumerate(data):
        if i == 0:
            continue
        if str(row[0]) == str(grade) and str(row[1]) == str(cls) and str(row[2]) == str(num):
            ws.delete_rows(i + 1)
            return True
    return False

# ─── AI 피드백 생성 ───
def generate_item_feedback(records_df, item_name):
    if records_df.empty or len(records_df) < 4:
        return None
    vals = pd.to_numeric(records_df[item_name], errors="coerce").dropna()
    if len(vals) < 4:
        return None
    first = vals.iloc[0]
    last = vals.iloc[-1]
    diff = last - first
    item_short = item_name.split("(")[0]

    if "플랭크" in item_name:
        if diff > 10:
            return f"🔥 {item_short} 기록이 {diff:.0f}초 향상! 코어 근력이 확실히 좋아지고 있어요! 💪"
        elif diff > 0:
            return f"📈 {item_short} 기록이 조금씩 늘고 있어요. 꾸준히 하면 더 좋아질 거예요! 👍"
        elif diff == 0:
            return f"📊 {item_short} 기록이 유지되고 있어요. 조금만 더 도전해볼까요? 😊"
        else:
            return f"💡 {item_short} 기록이 살짝 줄었어요. 매일 30초씩 연습하면 금방 회복돼요! 💪"
    elif "왕복달리기" in item_name:
        if diff > 5:
            return f"🔥 {item_short} {diff:.0f}회 증가! 심폐지구력이 많이 좋아졌어요! 🏃"
        elif diff > 0:
            return f"📈 {item_short} 기록이 조금씩 늘고 있어요. 꾸준한 달리기가 효과를 보고 있어요! 👍"
        elif diff == 0:
            return f"📊 {item_short} 기록이 유지 중이에요. 매일 조금씩 더 뛰어볼까요? 😊"
        else:
            return f"💡 {item_short} 기록이 약간 줄었지만 괜찮아요! 가볍게 달리기 연습해보세요! 🏃"
    elif "사이드스텝" in item_name:
        if diff > 3:
            return f"🔥 {item_short} {diff:.0f}회 증가! 순발력이 눈에 띄게 좋아졌어요! ⚡"
        elif diff > 0:
            return f"📈 {item_short} 기록이 향상되고 있어요! 민첩성이 좋아지고 있는 증거예요! 👍"
        elif diff == 0:
            return f"📊 {item_short} 기록이 안정적이에요. 줄넘기로 스텝 연습해볼까요? 😊"
        else:
            return f"💡 {item_short} 기록이 조금 줄었어요. 좌우 스텝 연습을 하면 금방 늘 거예요! ⚡"
    elif "굽히기" in item_name:
        if diff > 3:
            return f"🔥 {item_short} {diff:.1f}cm 향상! 유연성이 정말 좋아졌어요! 🧘"
        elif diff > 0:
            return f"📈 {item_short} 기록이 조금씩 늘고 있어요! 스트레칭 효과가 나타나고 있어요! 👍"
        elif diff == 0:
            return f"📊 {item_short} 기록이 유지 중이에요. 매일 스트레칭 습관을 들여볼까요? 😊"
        else:
            return f"💡 {item_short} 기록이 살짝 줄었어요. 매일 10초씩 스트레칭하면 금방 좋아져요! 🧘"
    return None

# ─── 성장 그래프 ───
def create_growth_chart(records_df, item_name):
    if records_df.empty or item_name not in records_df.columns:
        return None
    df = records_df.copy()
    df[item_name] = pd.to_numeric(df[item_name], errors="coerce")
    df = df.dropna(subset=[item_name])
    df = df.sort_values("측정회차")
    if df.empty:
        return None

    colors = {
        "3분왕복달리기(회)": "#FF6B6B",
        "사이드스텝(회)": "#4ECDC4",
        "플랭크(초)": "#45B7D1",
        "윗몸앞으로굽히기(cm)": "#96CEB4"
    }
    color = colors.get(item_name, "#FF6B6B")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["측정회차"].astype(str) + "회차",
        y=df[item_name],
        mode="lines+markers+text",
        text=df[item_name].round(1).astype(str),
        textposition="top center",
        line=dict(color=color, width=3),
        marker=dict(size=12, color=color),
        name=item_name
    ))

    unit = item_name.split("(")[1].replace(")", "") if "(" in item_name else ""
    short_name = item_name.split("(")[0]

    fig.update_layout(
        title=dict(text=f"{short_name}", font=dict(size=16)),
        xaxis_title="측정 회차",
        yaxis_title=f"{unit}",
        template="plotly_white",
        height=300,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    return fig

# ─── 메인 앱 ───
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

# ─── 로그인 페이지 ───
def show_login_page(client):
    st.markdown("""
    <div style='text-align: center; padding: 2rem;'>
        <h1>🏔️ 오르다</h1>
        <p style='font-size: 1.3rem; color: #888;'>
            <b>흥미</b>가 오르다, <b>체력</b>이 오르다, <b>건강</b>이 오르다
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### 🔑 로그인")
        students = get_student_list(client)

        if students.empty:
            st.warning("학생 데이터가 없습니다. 관리자 모드에서 초기 세팅을 진행해주세요.")
        else:
            grades = sorted(students["학년"].astype(str).unique().tolist())
            selected_grade = st.selectbox("학년", grades, format_func=lambda x: f"{x}학년")

            filtered_by_grade = students[students["학년"].astype(str) == selected_grade]
            classes = sorted(filtered_by_grade["반"].astype(str).unique().tolist())
            selected_class = st.selectbox("반", classes, format_func=lambda x: f"{x}반")

            filtered = filtered_by_grade[filtered_by_grade["반"].astype(str) == selected_class]
            filtered = filtered.sort_values("번호", key=lambda x: x.astype(int))
            names = filtered.apply(lambda row: f"{row['번호']}번 {row['이름']}", axis=1).tolist()

            if names:
                selected_display = st.selectbox("이름", names)
            else:
                selected_display = None
                st.warning("해당 반에 학생이 없습니다.")

            password = st.text_input("비밀번호", type="password", placeholder="비밀번호 입력")

            if st.button("🚀 로그인", use_container_width=True):
                if not selected_display or not password:
                    st.warning("이름과 비밀번호를 확인해주세요.")
                else:
                    sel_num = selected_display.split("번")[0].strip()
                    match = students[
                        (students["학년"].astype(str) == selected_grade) &
                        (students["반"].astype(str) == selected_class) &
                        (students["번호"].astype(str) == sel_num) &
                        (students["비밀번호"].astype(str) == str(password))
                    ]
                    if not match.empty:
                        st.session_state.logged_in = True
                        st.session_state.student_info = {
                            "grade": selected_grade,
                            "class": selected_class,
                            "num": sel_num,
                            "name": match.iloc[0]["이름"]
                        }
                        st.session_state.is_admin = False
                        st.rerun()
                    else:
                        st.error("비밀번호가 틀렸습니다.")

        st.markdown("---")
        with st.expander("🔧 관리자 모드"):
            admin_pw = st.text_input("관리자 비밀번호", type="password", key="admin_pw")
            if st.button("관리자 로그인"):
                if admin_pw == "admin0000":
                    st.session_state.logged_in = True
                    st.session_state.is_admin = True
                    st.rerun()
                else:
                    st.error("관리자 비밀번호가 틀렸습니다.")

# ─── 하단 개인정보 처리방침 (제공해주신 텍스트 그대로 반영) ───
        st.markdown("---")
        with st.expander("📄 개인정보 처리방침"):
            st.markdown("""
            **[개인정보 처리방침]**
            
            「오르다」 프로젝트 앱(이하 '본 앱')은 남산초등학교 학생들의 자기주도적 체력 관리 및 디지털교육 선도학교 연구 목적으로 운영되며, 사용자의 개인정보를 중요하게 생각하고 안전하게 보호하기 위해 최선을 다하고 있습니다.
            
            **1. 수집하는 개인정보 항목**
            본 앱은 서비스 제공을 위해 아래와 같은 최소한의 개인정보를 수집합니다.
            * **필수 항목**: 학년, 반, 번호, 성명, 비밀번호(본 앱 전용)
            * **건강/체력 데이터**: 3분 왕복달리기(회), 사이드스텝(회), 플랭크(초), 윗몸앞으로굽히기(cm) 측정 기록 및 목표 설정 데이터
            * **자동 수집 항목**: 서비스 이용 기록, 접속 일시 등
            
            **2. 개인정보의 수집 및 이용 목적**
            수집된 개인정보는 다음의 목적을 위해서만 이용됩니다.
            * **학생 체력 관리**: 개인별 체력 데이터 시각화, 성장 추이 분석 및 AI 맞춤형 피드백 제공
            * **통계 및 연구**: 반별/학년별 통계 산출 및 디지털교육 선도학교 운영 결과 분석 (이 경우, 개인을 식별할 수 없는 비식별화 데이터로 변환하여 활용합니다.)
            * **서비스 운영**: 본인 인증, 기록 조회 권한 확인 및 관리
            
            **3. 개인정보의 보유 및 이용 기간**
            * 본 앱에서 수집된 개인정보 및 체력 데이터는 해당 학년도 프로젝트 종료 시까지 보유하며, 목적 달성 후에는 복구할 수 없는 방법으로 지체 없이 영구 파기합니다.
            * 단, 연구 보고서 작성을 위해 활용되는 데이터는 개인을 식별할 수 없도록 익명화 처리하여 보관될 수 있습니다.
            
            **4. 개인정보의 제3자 제공**
            본 앱은 수집된 개인정보를 원칙적으로 외부에 제공하지 않습니다. 다만, 법령의 규정에 의거하거나 수사 목적으로 법령에 정해진 절차와 방법에 따라 요구받은 경우는 예외로 합니다.
            
            **5. 사용자의 권리 및 행사 방법**
            * 학생 및 학부모님은 언제든지 등록되어 있는 자신의 개인정보를 조회하거나 수정할 수 있으며, 관리자(담당 교사)에게 정보 삭제 및 처리 정지를 요청할 수 있습니다.
            * 열람, 수정, 삭제 요청은 담당 교사에게 직접 문의해주시기 바랍니다.
            
            **6. 개인정보 보호를 위한 안전성 확보 조치**
            * 데이터는 보안이 적용된 Google Cloud(Google Sheets) 환경에 저장되며, 접근 권한은 담당 교사에게만 엄격히 제한됩니다.
            * 학생 본인의 계정으로 로그인한 경우에만 자신의 기록을 열람할 수 있도록 시스템이 구성되어 있습니다.
            
            **7. 개인정보 보호 책임자**
            * 소속/성명: 남산초등학교 체육전담교사
            * 연락처: 053-852-5006
            
            **시행일자: 2026년 4월 13일**
            """)

# ─── 학생 대시보드 ───
def show_student_dashboard(client):
    info = st.session_state.student_info

    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f"### 🏔️ {info['grade']}학년 {info['class']}반 {info['name']}님의 오르다")
    with col2:
        if st.button("🚪 로그아웃"):
            st.session_state.logged_in = False
            st.session_state.student_info = {}
            st.rerun()

    screen = st.radio("", ["📝 기록 입력", "📊 성장 분석"], horizontal=True, label_visibility="collapsed")
    records = get_student_records(client, info["grade"], info["class"], info["num"])

    if screen == "📝 기록 입력":
        show_record_input(client, info, records)
    else:
        show_growth_analysis(client, info, records)

def show_record_input(client, info, records):
    st.markdown("#### 📝 체력 측정 기록 입력")

    # 기존 기록을 바탕으로 다음 회차 자동 계산
    if records.empty:
        next_round = 1
    else:
        existing_rounds = pd.to_numeric(records["측정회차"], errors="coerce").dropna()
        next_round = int(existing_rounds.max()) + 1 if not existing_rounds.empty else 1

    col_round, col_date = st.columns(2)
    with col_round:
        round_num = st.number_input("측정 회차 (자동 계산)", min_value=1, value=next_round)
    with col_date:
        kst_now = datetime.now(timezone.utc) + timedelta(hours=9)
        measure_date = st.date_input("측정일", value=kst_now)

    st.markdown("---")

    # 사분할 입력
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### 🏃 심폐지구력")
        v1 = st.number_input("3분 왕복달리기 (회)", min_value=0, value=0, key="v1",
                             help="전원 동시, 2인 1조")
        st.markdown("##### 💪 근지구력")
        v3 = st.number_input("플랭크 (초, 최대 180초)", min_value=0, max_value=180, value=0, key="v3",
                             help="2인 1조 관찰")
    with c2:
        st.markdown("##### ⚡ 순발력")
        v2 = st.number_input("사이드스텝 (회/20초)", min_value=0, value=0, key="v2")
        st.markdown("##### 🧘 유연성")
        v4 = st.number_input("윗몸앞으로굽히기 (cm)", min_value=-30.0, value=0.0, step=0.5, key="v4")

    st.markdown("---")

    if st.button("💾 기록 저장", use_container_width=True):
        record = [
            info["grade"], info["class"], info["num"], info["name"],
            round_num, measure_date.strftime("%Y-%m-%d"),
            v1, v2, v3, v4
        ]
        if add_record(client, record):
            st.success(f"✅ {round_num}회차 기록이 저장되었습니다! 🎉")
            time.sleep(1)
            st.rerun()
        else:
            st.error("❌ 저장에 실패했습니다.")

    if not records.empty:
        st.markdown("---")
        st.markdown("#### 📋 나의 기록")
        display_cols = ["측정회차", "측정일", "3분왕복달리기(회)", "사이드스텝(회)", "플랭크(초)", "윗몸앞으로굽히기(cm)"]
        available_cols = [c for c in display_cols if c in records.columns]
        st.dataframe(records[available_cols], use_container_width=True, hide_index=True)

def show_growth_analysis(client, info, records):
    st.markdown("#### 📊 나의 성장 분석")

    if records.empty:
        st.info("아직 측정 기록이 없어요. \'기록 입력\' 에서 먼저 기록해보세요! 🏃")
        return

    items = ["3분왕복달리기(회)", "사이드스텝(회)", "플랭크(초)", "윗몸앞으로굽히기(cm)"]
    item_icons = ["🏃 심폐지구력", "⚡ 순발력", "💪 근지구력", "🧘 유연성"]

    # 4개 그래프 (2x2) + AI 피드백
    col1, col2 = st.columns(2)
    for idx, (item, icon) in enumerate(zip(items, item_icons)):
        with [col1, col2][idx % 2]:
            st.markdown(f"**{icon}**")
            fig = create_growth_chart(records, item)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"{item.split('(')[0]} 기록이 없습니다.")

            feedback = generate_item_feedback(records, item)
            if feedback:
                st.info(f"🤖 {feedback}")
            else:
                rec_count = len(pd.to_numeric(records.get(item, pd.Series()), errors="coerce").dropna())
                if rec_count < 4:
                    st.caption(f"💬 4회 이상 기록 시 AI 피드백이 나타나요! (현재 {rec_count}회)")
            st.markdown("")

    # 누적 기록 요약
    st.markdown("---")
    st.markdown("#### 📊 4종목 누적 기록 요약")

    summary_data = []
    for item in items:
        if item in records.columns:
            vals = pd.to_numeric(records[item], errors="coerce").dropna()
            if not vals.empty:
                summary_data.append({
                    "종목": item.split("(")[0],
                    "단위": item.split("(")[1].replace(")", ""),
                    "최초 기록": vals.iloc[0],
                    "최근 기록": vals.iloc[-1],
                    "최고 기록": vals.max(),
                    "변화량": round(vals.iloc[-1] - vals.iloc[0], 1),
                    "측정 횟수": int(len(vals))
                })

    if summary_data:
        summary_df = pd.DataFrame(summary_data)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)
    else:
        st.info("아직 기록이 없습니다.")

# ─── 관리자 페이지 ───
def show_admin_page(client):
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("### 🔧 관리자 페이지")
    with col2:
        if st.button("🚪 로그아웃"):
            st.session_state.logged_in = False
            st.session_state.is_admin = False
            st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(["🔄 초기 세팅", "📝 기록 입력", "👥 학생 관리", "📊 전체 기록"])

    # ─── 탭1: 초기 세팅 ───
    with tab1:
        st.markdown("#### 🔄 초기 데이터 생성")
        st.warning("⚠️ 처음 한 번만 실행하세요! 기존 데이터가 있으면 건너뜁니다.")
        if st.button("🚀 초기 데이터 생성", use_container_width=True):
            with st.spinner("생성 중..."):
                s1 = init_student_list(client)
                time.sleep(1)
                s2 = init_records_sheet(client)
                if s1 and s2:
                    st.success("✅ 초기 데이터 생성 완료!")
                    st.info("5학년 1반 17명, 6학년 1반 18명이 등록되었습니다.")
                    st.info("👥 학생 관리 탭에서 실제 이름으로 수정해주세요.")
                else:
                    st.error("❌ 시트 생성에 실패했습니다.")

    # ─── 탭2: 기록 입력 (자동 회차 계산 및 KST 적용) ───
    with tab2:
        st.markdown("#### 📝 체력 측정 기록 입력 (관리자)")
        students = get_student_list(client)
        if students.empty:
            st.warning("먼저 초기 세팅을 진행해주세요.")
        else:
            col_sel1, col_sel2 = st.columns(2)
            with col_sel1:
                grade = st.selectbox("학년", sorted(students["학년"].astype(str).unique()),
                                     format_func=lambda x: f"{x}학년", key="ar_grade_out")
                filtered = students[students["학년"].astype(str) == grade]
                filtered = filtered.sort_values("번호", key=lambda x: x.astype(int))
                student_options = [f"{row['번호']}번 - {row['이름']}" for _, row in filtered.iterrows()]
                selected = st.selectbox("학생 선택", student_options, key="ar_student_out")

            if selected:
                s_num = selected.split("번")[0]
                cls_val = str(filtered[filtered["번호"].astype(str) == s_num].iloc[0]["반"])
                admin_records = get_student_records(client, grade, cls_val, s_num)

                if admin_records.empty:
                    next_round = 1
                else:
                    existing_rounds = pd.to_numeric(admin_records["측정회차"], errors="coerce").dropna()
                    next_round = int(existing_rounds.max()) + 1 if not existing_rounds.empty else 1
            else:
                next_round = 1

            with st.form("admin_record_form"):
                st.info(f"현재 입력 대상: {grade}학년 {selected}")
                
                col_r, col_d = st.columns(2)
                with col_r:
                    round_num = st.number_input("측정 회차 (자동 계산)", min_value=1, value=next_round, key="ar_round")
                with col_d:
                    try:
                        from datetime import timedelta, timezone
                        kst_now = datetime.now(timezone.utc) + timedelta(hours=9)
                    except ImportError:
                        kst_now = datetime.now()
                    measure_date = st.date_input("측정일", value=kst_now, key="ar_date")

                st.markdown("**체력 측정 항목**")
                c1, c2 = st.columns(2)
                with c1:
                    v1 = st.number_input("3분 왕복달리기 (회)", min_value=0, value=0, key="ar_v1")
                    v3 = st.number_input("플랭크 (초, 최대 180)", min_value=0, max_value=180, value=0, key="ar_v3")
                with c2:
                    v2 = st.number_input("사이드스텝 (회/20초)", min_value=0, value=0, key="ar_v2")
                    v4 = st.number_input("윗몸앞으로굽히기 (cm)", min_value=-30.0, value=0.0, step=0.5, key="ar_v4")

                submitted = st.form_submit_button("💾 기록 저장", use_container_width=True)
                if submitted:
                    s_name = selected.split(" - ")[1]
                    record = [grade, cls_val, s_num, s_name, round_num,
                              measure_date.strftime("%Y-%m-%d"), v1, v2, v3, v4]
                    if add_record(client, record):
                        st.success(f"✅ {s_name} 학생의 {round_num}회차 기록이 저장되었습니다!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ 저장에 실패했습니다.")

    # ─── 탭3: 학생 명단 관리 ───
    with tab3:
        st.markdown("#### 👥 학생 명단 관리")
        students = get_student_list(client)
        if students.empty:
            st.warning("먼저 초기 세팅을 진행해주세요.")
        else:
            st.dataframe(students, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("**➕ 학생 추가**")
            with st.form("add_student_form"):
                ac1, ac2, ac3, ac4, ac5 = st.columns(5)
                with ac1:
                    new_grade = st.selectbox("학년", ["5", "6"], key="new_grade")
                with ac2:
                    new_class = st.text_input("반", value="1", key="new_class")
                with ac3:
                    new_num = st.text_input("번호", key="new_num")
                with ac4:
                    new_name = st.text_input("이름", key="new_name")
                with ac5:
                    new_pw = st.text_input("비밀번호", key="new_pw")
                if st.form_submit_button("➕ 추가", use_container_width=True):
                    if new_num and new_name and new_pw:
                        if add_student(client, [new_grade, new_class, new_num, new_name, new_pw]):
                            st.success(f"✅ {new_name} 학생이 추가되었습니다!")
                            st.rerun()
                    else:
                        st.warning("모든 항목을 입력해주세요.")

            st.markdown("---")
            st.markdown("**🗑️ 학생 삭제**")
            del_grade = st.selectbox("학년 선택", sorted(students["학년"].astype(str).unique()),
                                    key="del_grade", format_func=lambda x: f"{x}학년")
            filtered_del = students[students["학년"].astype(str) == del_grade]
            filtered_del = filtered_del.sort_values("번호", key=lambda x: x.astype(int))
            del_options = [f"{row['번호']}번 - {row['이름']}" for _, row in filtered_del.iterrows()]
            del_selected = st.selectbox("삭제할 학생", del_options, key="del_student")
            if st.button("🗑️ 삭제"):
                d_num = del_selected.split("번")[0]
                d_cls = str(filtered_del.iloc[0]["반"])
                if delete_student(client, del_grade, d_cls, d_num):
                    st.success("✅ 삭제 완료!")
                    st.rerun()

            st.markdown("---")
            st.markdown("**✏️ 학생 정보 수정**")
            edit_grade = st.selectbox("학년 선택", sorted(students["학년"].astype(str).unique()),
                                     key="edit_grade", format_func=lambda x: f"{x}학년")
            filtered_edit = students[students["학년"].astype(str) == edit_grade]
            filtered_edit = filtered_edit.sort_values("번호", key=lambda x: x.astype(int))
            edit_options = [f"{row['번호']}번 - {row['이름']}" for _, row in filtered_edit.iterrows()]
            edit_selected = st.selectbox("수정할 학생", edit_options, key="edit_student")
            ec1, ec2 = st.columns(2)
            with ec1:
                edit_name = st.text_input("새 이름", key="edit_name")
            with ec2:
                edit_pw = st.text_input("새 비밀번호", key="edit_pw")
            if st.button("✏️ 수정", use_container_width=True):
                e_num = edit_selected.split("번")[0]
                ws = get_or_create_sheet(client, "학생명단")
                if ws:
                    data = ws.get_all_values()
                    for i, row in enumerate(data):
                        if i == 0:
                            continue
                        if str(row[0]) == edit_grade and str(row[2]) == e_num:
                            if edit_name:
                                ws.update_cell(i + 1, 4, edit_name)
                            if edit_pw:
                                ws.update_cell(i + 1, 5, edit_pw)
                            st.success("✅ 수정 완료!")
                            st.rerun()
                            break

    # ─── 탭4: 전체 기록 확인 ───
    with tab4:
        st.markdown("#### 📊 전체 기록 확인")
        all_records = get_all_records(client)
        if not all_records.empty:
            view_grade = st.selectbox("학년 선택",
                                     ["전체"] + sorted(all_records["학년"].astype(str).unique().tolist()),
                                     key="view_grade")
            if view_grade != "전체":
                all_records = all_records[all_records["학년"].astype(str) == view_grade]
            st.dataframe(all_records, use_container_width=True, hide_index=True)
        else:
            st.info("아직 입력된 기록이 없습니다.")

    # ─── 하단: 개인정보 처리방침 (제공해주신 텍스트 적용) ───
    st.markdown("---")
    with st.expander("📄 개인정보 처리방침"):
        st.markdown("""
        **[개인정보 처리방침]**
        
        「오르다」 프로젝트 앱(이하 '본 앱')은 남산초등학교 학생들의 자기주도적 체력 관리 및 디지털교육 선도학교 연구 목적으로 운영되며, 사용자의 개인정보를 중요하게 생각하고 안전하게 보호하기 위해 최선을 다하고 있습니다.
        
        **1. 수집하는 개인정보 항목**
        본 앱은 서비스 제공을 위해 아래와 같은 최소한의 개인정보를 수집합니다.
        * **필수 항목**: 학년, 반, 번호, 성명, 비밀번호(본 앱 전용)
        * **건강/체력 데이터**: 3분 왕복달리기(회), 사이드스텝(회), 플랭크(초), 윗몸앞으로굽히기(cm) 측정 기록 및 목표 설정 데이터
        * **자동 수집 항목**: 서비스 이용 기록, 접속 일시 등
        
        **2. 개인정보의 수집 및 이용 목적**
        수집된 개인정보는 다음의 목적을 위해서만 이용됩니다.
        * **학생 체력 관리**: 개인별 체력 데이터 시각화, 성장 추이 분석 및 AI 맞춤형 피드백 제공
        * **통계 및 연구**: 반별/학년별 통계 산출 및 디지털교육 선도학교 운영 결과 분석 (이 경우, 개인을 식별할 수 없는 비식별화 데이터로 변환하여 활용합니다.)
        * **서비스 운영**: 본인 인증, 기록 조회 권한 확인 및 관리
        
        **3. 개인정보의 보유 및 이용 기간**
        * 본 앱에서 수집된 개인정보 및 체력 데이터는 해당 학년도 프로젝트 종료 시까지 보유하며, 목적 달성 후에는 복구할 수 없는 방법으로 지체 없이 영구 파기합니다.
        * 단, 연구 보고서 작성을 위해 활용되는 데이터는 개인을 식별할 수 없도록 익명화 처리하여 보관될 수 있습니다.
        
        **4. 개인정보의 제3자 제공**
        본 앱은 수집된 개인정보를 원칙적으로 외부에 제공하지 않습니다. 다만, 법령의 규정에 의거하거나 수사 목적으로 법령에 정해진 절차와 방법에 따라 요구받은 경우는 예외로 합니다.
        
        **5. 사용자의 권리 및 행사 방법**
        * 학생 및 학부모님은 언제든지 등록되어 있는 자신의 개인정보를 조회하거나 수정할 수 있으며, 관리자(담당 교사)에게 정보 삭제 및 처리 정지를 요청할 수 있습니다.
        * 열람, 수정, 삭제 요청은 담당 교사에게 직접 문의해주시기 바랍니다.
        
        **6. 개인정보 보호를 위한 안전성 확보 조치**
        * 데이터는 보안이 적용된 Google Cloud(Google Sheets) 환경에 저장되며, 접근 권한은 담당 교사에게만 엄격히 제한됩니다.
        * 학생 본인의 계정으로 로그인한 경우에만 자신의 기록을 열람할 수 있도록 시스템이 구성되어 있습니다.
        
        **7. 개인정보 보호 책임자**
        * 소속/성명: 남산초등학교 체육전담교사
        * 연락처: 053-852-5006
        
        **시행일자: 2026년 4월 13일**
        """)

if __name__ == "__main__":
    main()

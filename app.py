import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import json
import time

# ─── 페이지 설정 ───
st.set_page_config(
    page_title="🏔️ 오르다",
    page_icon="🏔️",
    layout="wide"
)

# ─── Google Sheets 연결 ───
@st.cache_resource
def get_google_connection():
    """Google Sheets 연결"""
    try:
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
        st.error(f"Google Sheets 연결 실패: {e}")
        return None

def get_or_create_sheet(client, sheet_name):
    """스프레드시트 가져오기 또는 생성"""
    try:
        spreadsheet = client.open(st.secrets["spreadsheet_name"])
    except gspread.SpreadsheetNotFound:
        st.error(f"스프레드시트 \'{st.secrets['spreadsheet_name']}\'을 찾을 수 없습니다.")
        st.info("Google Drive에서 스프레드시트를 만들고 서비스 계정 이메일에 편집 권한을 공유해주세요.")
        return None

    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)

    return worksheet

# ─── 초기 데이터 생성 ───
def init_student_list(client):
    """학생 명단 시트 초기화"""
    ws = get_or_create_sheet(client, "학생명단")
    if ws is None:
        return False

    existing = ws.get_all_values()
    if len(existing) <= 1:  # 헤더만 있거나 비어있음
        headers = ["번호", "이름", "비밀번호"]
        students = []
        for i in range(1, 36):
            students.append([str(i), f"학생{i}", f"{i:04d}"])

        ws.clear()
        ws.update(range_name="A1", values=[headers] + students)
        time.sleep(1)
    return True

def init_records_sheet(client):
    """기록 시트 초기화"""
    ws = get_or_create_sheet(client, "체력기록")
    if ws is None:
        return False

    existing = ws.get_all_values()
    if len(existing) <= 1:
        headers = ["번호", "이름", "측정회차", "측정일", 
                   "왕복오래달리기(회)", "50m달리기(초)", 
                   "앉아윗몸앞으로굽히기(cm)", "팔굽혀펴기(회)", 
                   "윗몸말아올리기(회)"]
        ws.clear()
        ws.update(range_name="A1", values=[headers])
    return True

def init_goals_sheet(client):
    """목표 시트 초기화"""
    ws = get_or_create_sheet(client, "목표설정")
    if ws is None:
        return False

    existing = ws.get_all_values()
    if len(existing) <= 1:
        headers = ["번호", "이름", "설정일", 
                   "왕복오래달리기_목표", "50m달리기_목표",
                   "앉아윗몸앞으로굽히기_목표", "팔굽혀펴기_목표",
                   "윗몸말아올리기_목표", "한줄다짐"]
        ws.clear()
        ws.update(range_name="A1", values=[headers])
    return True

# ─── 데이터 조회 ───
def get_student_list(client):
    """학생 명단 조회"""
    ws = get_or_create_sheet(client, "학생명단")
    if ws is None:
        return pd.DataFrame()
    data = ws.get_all_records()
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data)

def get_student_records(client, student_num):
    """특정 학생의 체력 기록 조회"""
    ws = get_or_create_sheet(client, "체력기록")
    if ws is None:
        return pd.DataFrame()
    data = ws.get_all_records()
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df = df[df["번호"].astype(str) == str(student_num)]
    return df

def get_all_records(client):
    """전체 체력 기록 조회"""
    ws = get_or_create_sheet(client, "체력기록")
    if ws is None:
        return pd.DataFrame()
    data = ws.get_all_records()
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data)

def get_student_goals(client, student_num):
    """학생 목표 조회"""
    ws = get_or_create_sheet(client, "목표설정")
    if ws is None:
        return pd.DataFrame()
    data = ws.get_all_records()
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df = df[df["번호"].astype(str) == str(student_num)]
    return df

# ─── 데이터 입력 ───
def add_record(client, record):
    """체력 기록 추가"""
    ws = get_or_create_sheet(client, "체력기록")
    if ws is None:
        return False
    ws.append_row(record)
    return True

def save_goal(client, goal_data):
    """목표 저장"""
    ws = get_or_create_sheet(client, "목표설정")
    if ws is None:
        return False
    ws.append_row(goal_data)
    return True

def update_student_name(client, row_num, new_name):
    """학생 이름 수정"""
    ws = get_or_create_sheet(client, "학생명단")
    if ws is None:
        return False
    ws.update_cell(row_num + 1, 2, new_name)  # +1 for header
    return True

def update_student_password(client, row_num, new_pw):
    """학생 비밀번호 수정"""
    ws = get_or_create_sheet(client, "학생명단")
    if ws is None:
        return False
    ws.update_cell(row_num + 1, 3, new_pw)
    return True

# ─── 성장 그래프 ───
def create_growth_chart(records_df, item_name):
    """성장 그래프 생성"""
    if records_df.empty or item_name not in records_df.columns:
        return None

    df = records_df.copy()
    df[item_name] = pd.to_numeric(df[item_name], errors="coerce")
    df = df.dropna(subset=[item_name])

    if df.empty:
        return None

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["측정회차"].astype(str),
        y=df[item_name],
        mode="lines+markers+text",
        text=df[item_name].round(1).astype(str),
        textposition="top center",
        line=dict(color="#FF6B6B", width=3),
        marker=dict(size=12, color="#FF6B6B"),
        name=item_name
    ))

    fig.update_layout(
        title=dict(text=f"📈 {item_name} 변화", font=dict(size=18)),
        xaxis_title="측정 회차",
        yaxis_title=item_name,
        template="plotly_white",
        height=350,
        margin=dict(l=20, r=20, t=50, b=20)
    )

    return fig

# ─── 또래 비교 차트 ───
def create_comparison_chart(all_records, student_num, item_name, round_num):
    """또래 비교 차트"""
    if all_records.empty:
        return None

    df = all_records[all_records["측정회차"].astype(str) == str(round_num)].copy()
    if df.empty or item_name not in df.columns:
        return None

    df[item_name] = pd.to_numeric(df[item_name], errors="coerce")
    df = df.dropna(subset=[item_name])

    if df.empty:
        return None

    avg_val = df[item_name].mean()
    student_data = df[df["번호"].astype(str) == str(student_num)]
    my_val = student_data[item_name].values[0] if not student_data.empty else 0

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=["반 평균", "내 기록"],
        y=[avg_val, my_val],
        marker_color=["#4ECDC4", "#FF6B6B"],
        text=[f"{avg_val:.1f}", f"{my_val:.1f}"],
        textposition="outside"
    ))

    fig.update_layout(
        title=dict(text=f"👥 {item_name} - 또래 비교 ({round_num}회차)", font=dict(size=16)),
        template="plotly_white",
        height=350,
        margin=dict(l=20, r=20, t=50, b=20)
    )

    return fig

# ─── AI 피드백 (규칙 기반) ───
def generate_feedback(records_df):
    """규칙 기반 AI 피드백 생성"""
    if records_df.empty or len(records_df) < 2:
        return "📊 2회 이상 측정 후 피드백이 제공됩니다. 열심히 기록해보세요! 💪"

    items = ["왕복오래달리기(회)", "50m달리기(초)", 
             "앉아윗몸앞으로굽히기(cm)", "팔굽혀펴기(회)", 
             "윗몸말아올리기(회)"]

    feedback_parts = []
    improved = []
    declined = []

    for item in items:
        if item not in records_df.columns:
            continue
        vals = pd.to_numeric(records_df[item], errors="coerce").dropna()
        if len(vals) < 2:
            continue

        first = vals.iloc[0]
        last = vals.iloc[-1]
        diff = last - first

        # 50m 달리기는 낮을수록 좋음
        if "50m" in item:
            if diff < 0:
                improved.append(item)
            elif diff > 0:
                declined.append(item)
        else:
            if diff > 0:
                improved.append(item)
            elif diff < 0:
                declined.append(item)

    if improved:
        items_str = ", ".join([i.split("(")[0] for i in improved])
        feedback_parts.append(f"🔥 **성장 중!** {items_str} 항목이 향상되고 있어요! 정말 멋져요!")

    if declined:
        items_str = ", ".join([i.split("(")[0] for i in declined])
        feedback_parts.append(f"💡 **도전 포인트!** {items_str} 항목을 조금 더 연습해볼까요? 할 수 있어요!")

    if not improved and not declined:
        feedback_parts.append("📊 기록이 안정적으로 유지되고 있어요! 꾸준함이 최고의 실력입니다! 👍")

    if len(records_df) >= 4:
        feedback_parts.append("\n🏅 **4회 이상 측정 달성!** 꾸준한 노력이 빛나고 있어요! ⭐")

    return "\n\n".join(feedback_parts)

# ─── 메인 앱 ───
def main():
    # 세션 상태 초기화
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "student_num" not in st.session_state:
        st.session_state.student_num = None
    if "student_name" not in st.session_state:
        st.session_state.student_name = None
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False

    # Google Sheets 연결
    client = get_google_connection()
    if client is None:
        st.error("⚠️ Google Sheets 연결에 실패했습니다. Secrets 설정을 확인해주세요.")
        st.stop()

    # 로그인 안 된 상태
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
        <p style='font-size: 1.2rem; color: #666;'>기록하면 보이고, 보이면 오른다</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("### 🔑 로그인")

        # 학생 로그인
        student_num = st.text_input("번호", placeholder="예: 1")
        password = st.text_input("비밀번호", type="password", placeholder="예: 0001")

        if st.button("🚀 로그인", use_container_width=True):
            if not student_num or not password:
                st.warning("번호와 비밀번호를 입력해주세요.")
                return

            students = get_student_list(client)
            if students.empty:
                st.error("학생 명단이 없습니다. 관리자에게 문의하세요.")
                return

            match = students[
                (students["번호"].astype(str) == str(student_num)) & 
                (students["비밀번호"].astype(str) == str(password))
            ]

            if not match.empty:
                st.session_state.logged_in = True
                st.session_state.student_num = str(student_num)
                st.session_state.student_name = match.iloc[0]["이름"]
                st.session_state.is_admin = False
                st.rerun()
            else:
                st.error("번호 또는 비밀번호가 틀렸습니다.")

        st.markdown("---")

        # 관리자 로그인
        with st.expander("🔧 관리자 모드"):
            admin_pw = st.text_input("관리자 비밀번호", type="password", key="admin_pw")
            if st.button("관리자 로그인"):
                if admin_pw == "admin0000":
                    st.session_state.logged_in = True
                    st.session_state.is_admin = True
                    st.rerun()
                else:
                    st.error("관리자 비밀번호가 틀렸습니다.")

# ─── 학생 대시보드 ───
def show_student_dashboard(client):
    # 상단 바
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f"### 🏔️ {st.session_state.student_name}님의 오르다")
    with col2:
        if st.button("🚪 로그아웃"):
            st.session_state.logged_in = False
            st.session_state.student_num = None
            st.session_state.student_name = None
            st.rerun()

    # 탭
    tab1, tab2, tab3, tab4 = st.tabs(["📈 내 성장", "👥 또래 비교", "🎯 목표 설정", "🤖 AI 피드백"])

    student_num = st.session_state.student_num
    records = get_student_records(client, student_num)

    # ─── 탭1: 내 성장 ───
    with tab1:
        st.markdown("#### 📈 나의 체력 성장 그래프")

        if records.empty:
            st.info("아직 측정 기록이 없어요. 체력 측정 후 확인해보세요! 🏃")
        else:
            items = ["왕복오래달리기(회)", "50m달리기(초)", 
                     "앉아윗몸앞으로굽히기(cm)", "팔굽혀펴기(회)", 
                     "윗몸말아올리기(회)"]

            col1, col2 = st.columns(2)
            for idx, item in enumerate(items):
                fig = create_growth_chart(records, item)
                if fig:
                    with [col1, col2][idx % 2]:
                        st.plotly_chart(fig, use_container_width=True)

    # ─── 탭2: 또래 비교 ───
    with tab2:
        st.markdown("#### 👥 반 친구들과 비교")

        all_records = get_all_records(client)
        if all_records.empty:
            st.info("아직 반 전체 기록이 없어요.")
        else:
            rounds = sorted(all_records["측정회차"].unique())
            selected_round = st.selectbox("측정 회차 선택", rounds)

            items = ["왕복오래달리기(회)", "50m달리기(초)", 
                     "앉아윗몸앞으로굽히기(cm)", "팔굽혀펴기(회)", 
                     "윗몸말아올리기(회)"]

            col1, col2 = st.columns(2)
            for idx, item in enumerate(items):
                fig = create_comparison_chart(all_records, student_num, item, selected_round)
                if fig:
                    with [col1, col2][idx % 2]:
                        st.plotly_chart(fig, use_container_width=True)

    # ─── 탭3: 목표 설정 ───
    with tab3:
        st.markdown("#### 🎯 나의 목표 설정")

        goals = get_student_goals(client, student_num)
        if not goals.empty:
            latest = goals.iloc[-1]
            st.success(f"✅ 최근 목표 (설정일: {latest.get('설정일', '-')})")
            st.markdown(f"> 💬 *{latest.get('한줄다짐', '')}*")

        st.markdown("---")
        st.markdown("**새 목표 설정하기**")

        with st.form("goal_form"):
            g1 = st.number_input("왕복오래달리기 목표 (회)", min_value=0, value=0)
            g2 = st.number_input("50m달리기 목표 (초)", min_value=0.0, value=0.0, step=0.1)
            g3 = st.number_input("앉아윗몸앞으로굽히기 목표 (cm)", min_value=0.0, value=0.0, step=0.5)
            g4 = st.number_input("팔굽혀펴기 목표 (회)", min_value=0, value=0)
            g5 = st.number_input("윗몸말아올리기 목표 (회)", min_value=0, value=0)
            promise = st.text_input("한줄 다짐 ✍️", placeholder="예: 매일 줄넘기 100개 하기!")

            submitted = st.form_submit_button("🎯 목표 저장", use_container_width=True)
            if submitted:
                goal_data = [
                    student_num, st.session_state.student_name,
                    datetime.now().strftime("%Y-%m-%d"),
                    g1, g2, g3, g4, g5, promise
                ]
                if save_goal(client, goal_data):
                    st.success("🎯 목표가 저장되었습니다! 화이팅! 💪")
                    st.rerun()

    # ─── 탭4: AI 피드백 ───
    with tab4:
        st.markdown("#### 🤖 AI 코치의 피드백")
        feedback = generate_feedback(records)
        st.markdown(feedback)

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

    tab1, tab2, tab3 = st.tabs(["🔄 초기 세팅", "📝 기록 입력", "👥 학생 관리"])

    # ─── 탭1: 초기 세팅 ───
    with tab1:
        st.markdown("#### 🔄 초기 데이터 생성")
        st.warning("⚠️ 처음 한 번만 실행하세요! 기존 데이터가 있으면 건너뜁니다.")

        if st.button("🚀 초기 데이터 생성", use_container_width=True):
            with st.spinner("생성 중..."):
                s1 = init_student_list(client)
                time.sleep(1)
                s2 = init_records_sheet(client)
                time.sleep(1)
                s3 = init_goals_sheet(client)

                if s1 and s2 and s3:
                    st.success("✅ 초기 데이터 생성 완료! 학생 35명이 등록되었습니다.")
                    st.info("👥 학생 관리 탭에서 실제 이름으로 수정해주세요.")
                else:
                    st.error("❌ 일부 시트 생성에 실패했습니다. 스프레드시트 공유 설정을 확인해주세요.")

    # ─── 탭2: 기록 입력 ───
    with tab2:
        st.markdown("#### 📝 체력 측정 기록 입력")

        students = get_student_list(client)
        if students.empty:
            st.warning("먼저 초기 세팅을 진행해주세요.")
        else:
            with st.form("record_form"):
                col1, col2 = st.columns(2)
                with col1:
                    student_options = [f"{row['번호']}번 - {row['이름']}" for _, row in students.iterrows()]
                    selected = st.selectbox("학생 선택", student_options)
                with col2:
                    round_num = st.selectbox("측정 회차", [1, 2, 3, 4, 5])

                measure_date = st.date_input("측정일", value=datetime.now())

                st.markdown("**체력 측정 항목**")
                c1, c2, c3 = st.columns(3)
                with c1:
                    v1 = st.number_input("왕복오래달리기 (회)", min_value=0, value=0)
                    v2 = st.number_input("50m달리기 (초)", min_value=0.0, value=0.0, step=0.1)
                with c2:
                    v3 = st.number_input("앉아윗몸앞으로굽히기 (cm)", min_value=-20.0, value=0.0, step=0.5)
                    v4 = st.number_input("팔굽혀펴기 (회)", min_value=0, value=0)
                with c3:
                    v5 = st.number_input("윗몸말아올리기 (회)", min_value=0, value=0)

                submitted = st.form_submit_button("💾 기록 저장", use_container_width=True)
                if submitted:
                    s_num = selected.split("번")[0]
                    s_name = selected.split(" - ")[1]
                    record = [
                        s_num, s_name, round_num,
                        measure_date.strftime("%Y-%m-%d"),
                        v1, v2, v3, v4, v5
                    ]
                    if add_record(client, record):
                        st.success(f"✅ {s_name} 학생의 {round_num}회차 기록이 저장되었습니다!")
                    else:
                        st.error("❌ 저장에 실패했습니다.")

            # 일괄 입력
            st.markdown("---")
            st.markdown("#### 📋 전체 기록 확인")
            all_records = get_all_records(client)
            if not all_records.empty:
                st.dataframe(all_records, use_container_width=True)
            else:
                st.info("아직 입력된 기록이 없습니다.")

    # ─── 탭3: 학생 관리 ───
    with tab3:
        st.markdown("#### 👥 학생 명단 관리")

        students = get_student_list(client)
        if students.empty:
            st.warning("먼저 초기 세팅을 진행해주세요.")
        else:
            st.dataframe(students, use_container_width=True)

            st.markdown("---")
            st.markdown("**학생 정보 수정**")

            col1, col2, col3 = st.columns(3)
            with col1:
                edit_num = st.selectbox(
                    "수정할 번호", 
                    students["번호"].tolist()
                )
            with col2:
                new_name = st.text_input("새 이름")
            with col3:
                new_pw = st.text_input("새 비밀번호")

            if st.button("✏️ 수정하기"):
                row_idx = students[students["번호"].astype(str) == str(edit_num)].index
                if len(row_idx) > 0:
                    row = row_idx[0] + 1  # 0-based index + header
                    if new_name:
                        update_student_name(client, row, new_name)
                    if new_pw:
                        update_student_password(client, row, new_pw)
                    st.success("✅ 수정 완료!")
                    st.cache_resource.clear()
                    st.rerun()

if __name__ == "__main__":
    main()

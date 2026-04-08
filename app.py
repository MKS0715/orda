
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, date
import json
import time

# ─── 페이지 설정 ───
st.set_page_config(
    page_title="오르다 🏔️",
    page_icon="🏔️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─── 스타일 ───
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap');

    * { font-family: 'Noto Sans KR', sans-serif; }

    .main-title {
        text-align: center;
        font-size: 3.5rem;
        font-weight: 900;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    .sub-title {
        text-align: center;
        font-size: 1.1rem;
        color: #888;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: white;
        border-radius: 16px;
        padding: 1.2rem;
        box-shadow: 0 2px 12px rgba(0,0,0,0.08);
        text-align: center;
        border-left: 4px solid;
    }
    .record-table {
        font-size: 0.85rem;
    }
    .stButton > button {
        border-radius: 12px;
        font-weight: 600;
        padding: 0.5rem 2rem;
    }
    div[data-testid="stSidebar"] { display: none; }

    .success-msg {
        background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
        border-radius: 16px;
        padding: 1.5rem;
        text-align: center;
        font-size: 1.2rem;
        font-weight: 600;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ─── Google Sheets 연결 ───
@st.cache_resource
def get_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    return gspread.authorize(creds)

def get_spreadsheet():
    client = get_client()
    return client.open(st.secrets["spreadsheet_name"])

# ─── 데이터 함수들 ───
def get_students_df(sp):
    """학생목록 시트에서 학생 정보 가져오기"""
    try:
        ws = sp.worksheet("학생목록")
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def get_student_records(sp, sheet_name):
    """개별 학생 시트에서 기록 가져오기"""
    try:
        ws = sp.worksheet(sheet_name)
        data = ws.get_all_records()
        if data:
            df = pd.DataFrame(data)
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def save_record(sp, sheet_name, record_data):
    """학생 시트에 기록 추가"""
    try:
        ws = sp.worksheet(sheet_name)
        ws.append_row(record_data)
        return True
    except:
        return False

def init_student_sheet(sp, sheet_name):
    """학생 개인 시트 생성"""
    try:
        sp.worksheet(sheet_name)
    except:
        ws = sp.add_worksheet(title=sheet_name, rows=1000, cols=10)
        ws.append_row(["날짜", "왕복달리기(회)", "사이드스텝(회)", "플랭크(초)", "윗몸앞으로굽히기(cm)"])
        ws.format("1", {"textFormat": {"bold": True}})

def update_student_info(sp, grade, old_name, new_name, new_pw):
    """학생 정보 수정"""
    ws = sp.worksheet("학생목록")
    data = ws.get_all_records()
    for i, row in enumerate(data):
        if str(row["학년"]) == str(grade) and row["이름"] == old_name:
            if new_name:
                ws.update_cell(i+2, 2, new_name)
                # 시트 이름도 변경
                old_sheet_name = f"{grade}_{old_name}"
                new_sheet_name = f"{grade}_{new_name}"
                try:
                    student_ws = sp.worksheet(old_sheet_name)
                    student_ws.update_title(new_sheet_name)
                except:
                    pass
            if new_pw:
                ws.update_cell(i+2, 3, new_pw)
            return True
    return False

def add_student(sp, grade, name, pw):
    """학생 추가"""
    ws = sp.worksheet("학생목록")
    ws.append_row([int(grade), name, pw])
    sheet_name = f"{grade}_{name}"
    init_student_sheet(sp, sheet_name)
    return True

def delete_student(sp, grade, name):
    """학생 삭제"""
    ws = sp.worksheet("학생목록")
    data = ws.get_all_records()
    for i, row in enumerate(data):
        if str(row["학년"]) == str(grade) and row["이름"] == name:
            ws.delete_rows(i+2)
            try:
                student_ws = sp.worksheet(f"{grade}_{name}")
                sp.del_worksheet(student_ws)
            except:
                pass
            return True
    return False

def delete_record(sp, sheet_name, row_idx):
    """특정 기록 삭제"""
    try:
        ws = sp.worksheet(sheet_name)
        ws.delete_rows(row_idx + 2)  # 헤더 + 0-index 보정
        return True
    except:
        return False

def get_admin_pw(sp):
    """관리자 비밀번호 가져오기"""
    try:
        ws = sp.worksheet("설정")
        return ws.cell(2, 2).value
    except:
        return "admin0000"

def set_admin_pw(sp, new_pw):
    """관리자 비밀번호 변경"""
    try:
        ws = sp.worksheet("설정")
        ws.update_cell(2, 2, new_pw)
        return True
    except:
        return False

# ─── 초기화 함수 ───
def initialize_spreadsheet(sp):
    """스프레드시트 초기 세팅"""
    # 학생목록 시트
    try:
        ws = sp.worksheet("학생목록")
    except:
        ws = sp.add_worksheet(title="학생목록", rows=100, cols=5)
        ws.append_row(["학년", "이름", "비밀번호"])
        ws.format("1", {"textFormat": {"bold": True}})

        # 5학년 17명
        for i in range(1, 18):
            name = f"학생{i:02d}"
            ws.append_row([5, name, "1234"])
            init_student_sheet(sp, f"5_{name}")

        # 6학년 18명
        for i in range(1, 19):
            name = f"학생{i:02d}"
            ws.append_row([6, name, "1234"])
            init_student_sheet(sp, f"6_{name}")

    # 설정 시트
    try:
        sp.worksheet("설정")
    except:
        ws2 = sp.add_worksheet(title="설정", rows=10, cols=5)
        ws2.append_row(["항목", "값"])
        ws2.append_row(["관리자비밀번호", "admin0000"])

    # 기본 Sheet1 삭제
    try:
        default = sp.worksheet("Sheet1")
        sp.del_worksheet(default)
    except:
        pass

# ═══════════════════════════════════
# 페이지들
# ═══════════════════════════════════

def login_page():
    """로그인 페이지"""
    st.markdown('<div class="main-title">🏔️ 오르다</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">흥미가 오르다, 체력이 오르다, 건강이 오르다</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        with st.container(border=True):
            st.subheader("🔐 로그인")

            grade = st.selectbox("학년", ["선택하세요", "5학년", "6학년"], key="login_grade")

            if grade != "선택하세요":
                grade_num = grade.replace("학년", "")
                try:
                    sp = get_spreadsheet()
                    students_df = get_students_df(sp)
                    grade_students = students_df[students_df["학년"].astype(str) == grade_num]["이름"].tolist()

                    name = st.selectbox("이름", ["선택하세요"] + grade_students, key="login_name")
                    pw = st.text_input("비밀번호 (4자리)", type="password", max_chars=4, key="login_pw")

                    if st.button("🔓 로그인", use_container_width=True, type="primary"):
                        if name == "선택하세요":
                            st.error("이름을 선택해주세요!")
                        elif not pw:
                            st.error("비밀번호를 입력해주세요!")
                        else:
                            student_row = students_df[
                                (students_df["학년"].astype(str) == grade_num) & 
                                (students_df["이름"] == name)
                            ]
                            if not student_row.empty and str(student_row.iloc[0]["비밀번호"]) == pw:
                                st.session_state.logged_in = True
                                st.session_state.is_admin = False
                                st.session_state.grade = grade_num
                                st.session_state.name = name
                                st.session_state.sheet_name = f"{grade_num}_{name}"
                                st.rerun()
                            else:
                                st.error("❌ 비밀번호가 틀렸습니다!")
                except Exception as e:
                    st.error(f"연결 오류: {e}")

        st.markdown("---")

        # 관리자 모드
        with st.expander("🔧 관리자 모드"):
            admin_pw = st.text_input("관리자 비밀번호", type="password", key="admin_pw_input")
            if st.button("관리자 로그인", use_container_width=True):
                try:
                    sp = get_spreadsheet()
                    real_pw = get_admin_pw(sp)
                    if admin_pw == real_pw:
                        st.session_state.logged_in = True
                        st.session_state.is_admin = True
                        st.rerun()
                    else:
                        st.error("❌ 관리자 비밀번호가 틀렸습니다!")
                except Exception as e:
                    st.error(f"연결 오류: {e}")


def student_app():
    """학생 앱 메인"""
    sp = get_spreadsheet()

    # 상단 헤더
    hcol1, hcol2, hcol3 = st.columns([1, 3, 1])
    with hcol1:
        st.markdown(f"**{st.session_state.grade}학년 {st.session_state.name}**")
    with hcol2:
        st.markdown('<div style="text-align:center; font-size:1.5rem; font-weight:700;">🏔️ 오르다</div>', unsafe_allow_html=True)
    with hcol3:
        if st.button("🚪 로그아웃", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    st.markdown("---")

    # 탭
    tab1, tab2 = st.tabs(["✏️ 기록 입력", "📊 나의 성장"])

    with tab1:
        input_page(sp)

    with tab2:
        dashboard_page(sp)


def input_page(sp):
    """기록 입력 페이지"""
    today = date.today().strftime("%Y-%m-%d")

    st.markdown(f"### 📅 오늘의 측정 ({today})")
    st.caption("측정한 종목만 입력하세요. 빈 칸은 저장되지 않습니다.")

    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):
            st.markdown("#### 🫁 심폐지구력")
            st.caption("3분 왕복달리기")
            v1 = st.number_input("왕복 횟수 (회)", min_value=0, max_value=200, value=0, step=1, key="input_cardio")

        with st.container(border=True):
            st.markdown("#### 💪 근지구력")
            st.caption("플랭크 버티기")
            v3 = st.number_input("버틴 시간 (초)", min_value=0, max_value=600, value=0, step=1, key="input_muscle")

    with col2:
        with st.container(border=True):
            st.markdown("#### ⚡ 순발력")
            st.caption("사이드스텝 (20초)")
            v2 = st.number_input("횟수 (회)", min_value=0, max_value=100, value=0, step=1, key="input_agility")

        with st.container(border=True):
            st.markdown("#### 🤸 유연성")
            st.caption("윗몸앞으로굽히기")
            v4 = st.number_input("길이 (cm)", min_value=-30.0, max_value=50.0, value=0.0, step=0.1, format="%.1f", key="input_flex")

    st.markdown("")

    if st.button("💾 기록 저장하기", use_container_width=True, type="primary"):
        if v1 == 0 and v2 == 0 and v3 == 0 and v4 == 0.0:
            st.warning("⚠️ 최소 1개 종목의 기록을 입력해주세요!")
        else:
            record = [
                today,
                v1 if v1 > 0 else "",
                v2 if v2 > 0 else "",
                v3 if v3 > 0 else "",
                v4 if v4 != 0.0 else ""
            ]
            with st.spinner("저장 중..."):
                if save_record(sp, st.session_state.sheet_name, record):
                    st.markdown('<div class="success-msg">✅ 기록이 저장되었습니다! 🎉</div>', unsafe_allow_html=True)
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ 저장에 실패했습니다. 다시 시도해주세요.")


def dashboard_page(sp):
    """나의 성장 대시보드"""
    df = get_student_records(sp, st.session_state.sheet_name)

    if df.empty:
        st.info("📭 아직 기록이 없습니다. 첫 번째 기록을 입력해보세요!")
        return

    # 컬럼명 정리
    cols = ["날짜", "왕복달리기(회)", "사이드스텝(회)", "플랭크(초)", "윗몸앞으로굽히기(cm)"]
    df.columns = cols[:len(df.columns)]

    # 숫자 변환
    for c in cols[1:]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # ─── 최신 기록 요약 카드 ───
    st.markdown("### 📋 최신 기록")
    latest = df.iloc[-1]

    mcol1, mcol2, mcol3, mcol4 = st.columns(4)

    items = [
        ("🫁 심폐지구력", "왕복달리기(회)", "회", "#667eea", mcol1),
        ("⚡ 순발력", "사이드스텝(회)", "회", "#f093fb", mcol2),
        ("💪 근지구력", "플랭크(초)", "초", "#4facfe", mcol3),
        ("🤸 유연성", "윗몸앞으로굽히기(cm)", "cm", "#43e97b", mcol4),
    ]

    for label, col_name, unit, color, mcol in items:
        with mcol:
            val = latest.get(col_name, None)
            val_str = f"{val}{unit}" if pd.notna(val) and val != "" else "-"

            # 성장 계산
            valid = df[col_name].dropna()
            valid = valid[valid != ""]
            if len(valid) >= 2:
                diff = float(valid.iloc[-1]) - float(valid.iloc[-2])
                if diff > 0:
                    change = f"📈 +{diff:.1f}"
                elif diff < 0:
                    change = f"📉 {diff:.1f}"
                else:
                    change = "➡️ 유지"
            else:
                change = "첫 기록"

            st.metric(label=label, value=val_str, delta=change if change != "첫 기록" else None)

    st.markdown("---")

    # ─── 4분할 성장 그래프 ───
    st.markdown("### 📈 성장 그래프")

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=("🫁 심폐지구력 (왕복달리기)", "⚡ 순발력 (사이드스텝)", 
                       "💪 근지구력 (플랭크)", "🤸 유연성 (윗몸앞으로굽히기)"),
        vertical_spacing=0.15,
        horizontal_spacing=0.1
    )

    chart_items = [
        ("왕복달리기(회)", "회", "#667eea", 1, 1),
        ("사이드스텝(회)", "회", "#f093fb", 1, 2),
        ("플랭크(초)", "초", "#4facfe", 2, 1),
        ("윗몸앞으로굽히기(cm)", "cm", "#43e97b", 2, 2),
    ]

    for col_name, unit, color, row, col in chart_items:
        if col_name in df.columns:
            plot_df = df[["날짜", col_name]].copy()
            plot_df[col_name] = pd.to_numeric(plot_df[col_name], errors="coerce")
            plot_df = plot_df.dropna(subset=[col_name])

            if not plot_df.empty:
                fig.add_trace(
                    go.Scatter(
                        x=plot_df["날짜"],
                        y=plot_df[col_name],
                        mode="lines+markers+text",
                        text=[f"{v:.0f}" if v == int(v) else f"{v:.1f}" for v in plot_df[col_name]],
                        textposition="top center",
                        textfont=dict(size=11),
                        line=dict(color=color, width=3),
                        marker=dict(size=10, color=color),
                        name=col_name,
                        showlegend=False
                    ),
                    row=row, col=col
                )

    fig.update_layout(
        height=600,
        font=dict(family="Noto Sans KR, sans-serif"),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(0,0,0,0.05)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(0,0,0,0.05)")

    st.plotly_chart(fig, use_container_width=True)

    # ─── 전체 기록 테이블 ───
    st.markdown("### 📋 전체 기록")
    display_df = df.sort_index(ascending=False)
    st.dataframe(display_df, use_container_width=True, hide_index=True)


def admin_app():
    """관리자 앱"""
    sp = get_spreadsheet()

    # 상단
    hcol1, hcol2, hcol3 = st.columns([1, 3, 1])
    with hcol1:
        st.markdown("**🔧 관리자 모드**")
    with hcol2:
        st.markdown('<div style="text-align:center; font-size:1.5rem; font-weight:700;">🏔️ 오르다 관리자</div>', unsafe_allow_html=True)
    with hcol3:
        if st.button("🚪 로그아웃", use_container_width=True, key="admin_logout"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs(["👥 학생 관리", "📊 전체 기록", "⚙️ 설정", "🔄 초기 세팅"])

    # ─── 학생 관리 ───
    with tab1:
        students_df = get_students_df(sp)

        if not students_df.empty:
            for grade in ["5", "6"]:
                st.markdown(f"#### {grade}학년")
                grade_df = students_df[students_df["학년"].astype(str) == grade]

                for idx, row in grade_df.iterrows():
                    with st.expander(f"📌 {row['이름']} (비밀번호: {row['비밀번호']})"):
                        ncol1, ncol2, ncol3 = st.columns([2, 2, 1])
                        with ncol1:
                            new_name = st.text_input("새 이름", value=row["이름"], key=f"name_{grade}_{idx}")
                        with ncol2:
                            new_pw = st.text_input("새 비밀번호", value=str(row["비밀번호"]), key=f"pw_{grade}_{idx}")
                        with ncol3:
                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.button("💾 수정", key=f"edit_{grade}_{idx}"):
                                update_student_info(sp, grade, row["이름"], new_name, new_pw)
                                st.success("✅ 수정 완료!")
                                time.sleep(1)
                                st.rerun()

                        if st.button(f"🗑️ {row['이름']} 삭제", key=f"del_{grade}_{idx}", type="secondary"):
                            delete_student(sp, grade, row["이름"])
                            st.success("✅ 삭제 완료!")
                            time.sleep(1)
                            st.rerun()

                st.markdown("---")

        # 학생 추가
        st.markdown("#### ➕ 학생 추가")
        acol1, acol2, acol3 = st.columns(3)
        with acol1:
            new_grade = st.selectbox("학년", ["5", "6"], key="add_grade")
        with acol2:
            add_name = st.text_input("이름", key="add_name")
        with acol3:
            add_pw = st.text_input("비밀번호", value="1234", key="add_pw")

        if st.button("➕ 학생 추가", type="primary"):
            if add_name:
                add_student(sp, new_grade, add_name, add_pw)
                st.success(f"✅ {new_grade}학년 {add_name} 추가 완료!")
                time.sleep(1)
                st.rerun()
            else:
                st.warning("이름을 입력해주세요!")

    # ─── 전체 기록 ───
    with tab2:
        students_df = get_students_df(sp)

        filter_grade = st.selectbox("학년 필터", ["전체", "5학년", "6학년"], key="filter_grade")

        if not students_df.empty:
            if filter_grade != "전체":
                grade_num = filter_grade.replace("학년", "")
                filtered = students_df[students_df["학년"].astype(str) == grade_num]
            else:
                filtered = students_df

            for _, row in filtered.iterrows():
                sheet_name = f"{row['학년']}_{row['이름']}"
                records = get_student_records(sp, sheet_name)

                with st.expander(f"📋 {row['학년']}학년 {row['이름']} ({len(records)}건)"):
                    if not records.empty:
                        st.dataframe(records, use_container_width=True, hide_index=True)
                    else:
                        st.caption("기록 없음")

        # CSV 내보내기
        st.markdown("---")
        if st.button("📥 전체 데이터 CSV 다운로드"):
            all_data = []
            for _, row in students_df.iterrows():
                sheet_name = f"{row['학년']}_{row['이름']}"
                records = get_student_records(sp, sheet_name)
                if not records.empty:
                    records.insert(0, "이름", row["이름"])
                    records.insert(0, "학년", row["학년"])
                    all_data.append(records)

            if all_data:
                full_df = pd.concat(all_data, ignore_index=True)
                csv = full_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button("💾 CSV 파일 다운로드", csv, "오르다_전체기록.csv", "text/csv")
            else:
                st.info("아직 기록이 없습니다.")

    # ─── 설정 ───
    with tab3:
        st.markdown("#### 🔑 관리자 비밀번호 변경")
        new_admin_pw = st.text_input("새 관리자 비밀번호", type="password", key="new_admin_pw")
        new_admin_pw2 = st.text_input("비밀번호 확인", type="password", key="new_admin_pw2")

        if st.button("🔑 비밀번호 변경"):
            if new_admin_pw and new_admin_pw == new_admin_pw2:
                set_admin_pw(sp, new_admin_pw)
                st.success("✅ 관리자 비밀번호가 변경되었습니다!")
            elif new_admin_pw != new_admin_pw2:
                st.error("비밀번호가 일치하지 않습니다!")

        st.markdown("---")
        st.markdown("#### 🔄 전체 비밀번호 초기화")
        if st.button("⚠️ 모든 학생 비밀번호를 1234로 초기화", type="secondary"):
            ws = sp.worksheet("학생목록")
            data = ws.get_all_records()
            for i in range(len(data)):
                ws.update_cell(i+2, 3, "1234")
            st.success("✅ 전체 비밀번호가 1234로 초기화되었습니다.")

    # ─── 초기 세팅 ───
    with tab4:
        st.markdown("#### 🔄 스프레드시트 초기 세팅")
        st.warning("⚠️ 처음 한 번만 실행하세요! 이미 데이터가 있으면 실행하지 마세요.")

        if st.button("🚀 초기 데이터 생성 (학생 35명 + 시트 생성)", type="primary"):
            with st.spinner("생성 중... (약 1~2분 소요)"):
                initialize_spreadsheet(sp)
            st.success("✅ 초기 세팅 완료! 학생목록 시트와 개인 시트 35개가 생성되었습니다.")
            st.balloons()


# ═══════════════════════════════════
# 메인
# ═══════════════════════════════════
def main():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        login_page()
    else:
        if st.session_state.get("is_admin", False):
            admin_app()
        else:
            student_app()

if __name__ == "__main__":
    main()

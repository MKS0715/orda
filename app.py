import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
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
    try:
        spreadsheet = client.open(st.secrets["spreadsheet_name"])
    except gspread.SpreadsheetNotFound:
        st.error(f"스프레드시트를 찾을 수 없습니다. Google Drive 공유 설정을 확인해주세요.")
        return None
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
    return worksheet

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

def init_records

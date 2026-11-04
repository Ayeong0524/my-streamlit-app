

import os, json, smtplib, re   # ★ re 추가 (음성용 텍스트 정리)
import pandas as pd
import streamlit as st
from openai import OpenAI
from email.mime.text import MIMEText

import calendar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import streamlit as st

def get_task_priority(task, today):
    """날짜를 기준으로 긴급도와 정렬 순서를 계산합니다."""
    due_text = task.get("due_date")

    try:
        due = date.fromisoformat(due_text) if due_text else None
    except (ValueError, TypeError):
        due = None

    if due is None:
        urgency_rank = 3
        urgency = "기한 확인 필요"
        deadline_label = "확인 필요"
    else:
        days_left = (due - today).days

        if days_left < 0:
            urgency_rank = 0
            urgency = "기한 경과"
            deadline_label = f"{abs(days_left)}일 경과"

        elif days_left <= 3:
            urgency_rank = 1
            urgency = "긴급"
            deadline_label = "오늘 마감" if days_left == 0 else f"D-{days_left}"

        else:
            urgency_rank = 2
            urgency = "일반"
            deadline_label = f"D-{days_left}"

    importance_rank = {
        "높음": 0,
        "보통": 1,
        "낮음": 2,
        "확인 필요": 3
    }.get(task["importance"], 3)

    sort_key = (
        urgency_rank,
        importance_rank,
        due or date.max
    )

    return sort_key, urgency, deadline_label

def group_preview_tasks(tasks, base_date):
    """미완료 업무를 마감일 기준으로 분류합니다."""
    upcoming, overdue, undated = [], [], []
    for task in tasks:
        if task.get("done", False):
            continue
        try:
            due = date.fromisoformat(task["due_date"]) if task.get("due_date") else None
        except (ValueError, TypeError):
            due = None
        if due is None:
            undated.append(task)
        elif due < base_date:
            overdue.append((due, task))
        else:
            upcoming.append((due, task))
    upcoming.sort(key=lambda item: (item[0], item[1]["title"]))
    overdue.sort(key=lambda item: (item[0], item[1]["title"]))
    return upcoming, overdue, undated


def render_calendar(tasks):
    """월간 캘린더, 날짜별 업무 상세, 기한 미정 목록."""

        # ==================================================
    # 11. 업무 캘린더
    # ==================================================
    st.divider()
    st.subheader("📅 업무 캘린더")
    st.caption("날짜를 누르면 해당 날짜에 마감하는 업무를 확인할 수 있습니다.")

    calendar_today = datetime.now(ZoneInfo("Asia/Seoul")).date()

    # 캘린더 화면 상태
    if "calendar_month" not in st.session_state:
        st.session_state.calendar_month = calendar_today.replace(day=1)

    if "calendar_selected_date" not in st.session_state:
        st.session_state.calendar_selected_date = calendar_today


    # --------------------------------------------------
    # 캘린더 조작 함수
    # --------------------------------------------------
    def move_calendar_month(offset):
        current = st.session_state.calendar_month

        # 연도가 바뀌는 경우도 처리
        month_index = current.year * 12 + current.month - 1 + offset
        year, month_zero = divmod(month_index, 12)

        target = date(year, month_zero + 1, 1)

        st.session_state.calendar_month = target
        st.session_state.calendar_selected_date = target


    def select_calendar_date(selected_date):
        st.session_state.calendar_selected_date = selected_date


    def go_to_calendar_today():
        current_today = datetime.now(ZoneInfo("Asia/Seoul")).date()
        st.session_state.calendar_month = current_today.replace(day=1)
        st.session_state.calendar_selected_date = current_today


    def calendar_task_label(task):
        if task.get("done", False):
            return "✅ 완료"

        _, urgency, _ = get_task_priority(task, calendar_today)

        return {
            "기한 경과": "🔴 기한 경과",
            "긴급": "🟠 마감 임박",
            "일반": "🔵 예정",
            "기한 확인 필요": "⚪ 기한 미정"
        }[urgency]


    # --------------------------------------------------
    # 기존 업무를 날짜별로 분류
    # 별도의 AI 호출 없이 체크리스트 데이터를 사용
    # --------------------------------------------------
    tasks_by_date = {}
    undated_tasks = []

    for task in tasks:
        try:
            due = (
                date.fromisoformat(task["due_date"])
                if task.get("due_date")
                else None
            )
        except (ValueError, TypeError):
            due = None

        if due is None:
            undated_tasks.append(task)
        else:
            tasks_by_date.setdefault(due, []).append(task)


    # --------------------------------------------------
    # 월 이동 버튼
    # --------------------------------------------------
    prev_col, title_col, next_col, today_col = st.columns([1, 3, 1, 1])

    with prev_col:
        st.button(
            "◀ 이전 달",
            key="calendar_prev",
            on_click=move_calendar_month,
            args=(-1,),
            use_container_width=True
        )

    with next_col:
        st.button(
            "다음 달 ▶",
            key="calendar_next",
            on_click=move_calendar_month,
            args=(1,),
            use_container_width=True
        )

    with today_col:
        st.button(
            "오늘",
            key="calendar_today_button",
            on_click=go_to_calendar_today,
            use_container_width=True
        )

    view_month = st.session_state.calendar_month
    selected_date = st.session_state.calendar_selected_date

    with title_col:
        st.markdown(f"### {view_month.year}년 {view_month.month}월")

    st.caption("🔴 기한 경과 · 🟠 마감 임박 · 🔵 예정 · ✅ 완료")


    # --------------------------------------------------
    # 요일 표시
    # --------------------------------------------------
    weekday_columns = st.columns(7)

    for column, weekday in zip(
        weekday_columns,
        ["월", "화", "수", "목", "금", "토", "일"]
    ):
        column.markdown(f"**{weekday}**")


    # --------------------------------------------------
    # 월간 달력 표시
    # --------------------------------------------------
    month_calendar = calendar.Calendar(firstweekday=0)
    weeks = month_calendar.monthdayscalendar(
        view_month.year,
        view_month.month
    )

    for week_index, week in enumerate(weeks):
        day_columns = st.columns(7)

        for weekday_index, day_number in enumerate(week):
            with day_columns[weekday_index]:
                # 이번 달에 포함되지 않는 빈칸
                if day_number == 0:
                    st.write("")
                    continue

                current_date = date(
                    view_month.year,
                    view_month.month,
                    day_number
                )

                day_tasks = tasks_by_date.get(current_date, [])

                # 미완료 업무를 먼저 표시
                day_tasks = sorted(
                    day_tasks,
                    key=lambda task: (
                        task.get("done", False),
                        *get_task_priority(task, calendar_today)[0]
                    )
                )

                with st.container(border=True):
                    date_label = f"{day_number}일"

                    if current_date == calendar_today:
                        date_label += " · 오늘"

                    st.button(
                        date_label,
                        key=f"calendar_day_{current_date.isoformat()}",
                        type=(
                            "primary"
                            if current_date == selected_date
                            else "secondary"
                        ),
                        on_click=select_calendar_date,
                        args=(current_date,),
                        use_container_width=True
                    )

                    if day_tasks:
                        st.caption(f"마감 업무 {len(day_tasks)}건")

                        # 칸이 너무 길어지지 않도록 2건까지만 미리 보기
                        for task in day_tasks[:2]:
                            status = calendar_task_label(task)
                            icon = status.split()[0]

                            title = task["title"]
                            short_title = (
                                title[:16] + "…"
                                if len(title) > 16
                                else title
                            )

                            st.caption(f"{icon} {short_title}")

                        if len(day_tasks) > 2:
                            st.caption(f"외 {len(day_tasks) - 2}건")


    # --------------------------------------------------
    # 선택한 날짜의 업무 상세
    # --------------------------------------------------
    st.markdown(
        f"#### 📌 {selected_date.month}월 {selected_date.day}일 마감 업무"
    )

    selected_tasks = sorted(
        tasks_by_date.get(selected_date, []),
        key=lambda task: (
            task.get("done", False),
            *get_task_priority(task, calendar_today)[0]
        )
    )

    if not selected_tasks:
        st.info("선택한 날짜에 마감하는 업무가 없습니다.")

    else:
        for task in selected_tasks:
            with st.container(border=True):
                st.markdown(f"**{task['title']}**")

                _, _, deadline_label = get_task_priority(
                    task,
                    calendar_today
                )

                st.caption(
                    f"{calendar_task_label(task)}"
                    f" · 중요도: {task['importance']}"
                    f" · {deadline_label}"
                )

                st.write(task["detail"])

                with st.expander("마감일과 중요도 근거"):
                    st.write("마감일 근거:", task["due_evidence"])
                    st.write("중요도 근거:", task["importance_evidence"])

        st.caption("완료 여부와 마감일은 아래 일정 관리에서 변경해 주세요.")


    # --------------------------------------------------
    # 기한이 없는 업무
    # --------------------------------------------------
    with st.expander(f"⚪ 기한 미정 업무 {len(undated_tasks)}건"):
        if not undated_tasks:
            st.write("기한 미정 업무가 없습니다.")

        for task in undated_tasks:
            status = "✅ 완료" if task.get("done", False) else "⬜ 미완료"

            st.markdown(f"**{status} · {task['title']}**")
            st.write(task["detail"])
            st.caption(f"기한 근거: {task['due_evidence']}")

# ==================================================


def render_calendar_preview(tasks):
    """마감 일정 미리보기. st.columns의 우측 열 안에서 호출 가능."""
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    with st.container(border=True):
        st.subheader("📅 마감 일정 미리보기")
        st.caption(f"{today.isoformat()} 기준 · 미완료 업무")

        upcoming, overdue, undated = group_preview_tasks(
            tasks, today
        )

        if not tasks:
            st.info("업무 목록을 전달하면 마감 일정이 표시됩니다.")
        elif not (upcoming or overdue or undated):
            st.success("모든 업무를 완료했습니다! 🎉")
        else:
            if overdue:
                st.error(f"기한이 지난 미완료 업무 {len(overdue)}건")
                with st.expander("기한 경과 업무 확인"):
                    for due, task in overdue:
                        st.write(f"🔴 {task['title']}")
                        st.caption(f"{due.isoformat()} · {(today - due).days}일 경과")
                        st.write(task["detail"])

            st.markdown("**다가오는 마감**")
            if not upcoming:
                st.caption("예정된 마감 업무가 없습니다.")

            for due, task in upcoming[:5]:
                days_left = (due - today).days
                badge = "D-day" if days_left == 0 else f"D-{days_left}"
                icon = "🟠" if days_left <= 3 else "🔵"
                with st.expander(f"{icon} {badge} · {task['title']}"):
                    st.caption(f"마감일: {due.isoformat()} · 중요도: {task['importance']}")
                    st.write(task["detail"])
                    st.write("기한 근거:", task["due_evidence"])

            if len(upcoming) > 5:
                st.caption(f"이후 일정 {len(upcoming) - 5}건은 업무 캘린더에서 확인하세요.")

            if undated:
                with st.expander(f"⚪ 기한 미정 {len(undated)}건"):
                    for task in undated:
                        st.write(task["title"])
                        st.caption(task["due_evidence"])

        st.divider()
        st.caption("전체 일정은 📅 마감 캘린더 탭에서 확인하세요.")
        st.caption("일정 관리에서 완료하면 미리보기에서 자동으로 제외됩니다.")





# 캘린더 연결: 회의록 원문 기한은 보존하고 명확한 날짜만 변환합니다.
def resolve_deadline(value, base):
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    # 여러 날짜, 범위, 모호한 주간 표현은 사용자가 확인합니다.
    if re.search(r"[~～]|부터|사이|주말|주중|초순|중순|하순", text):
        return None
    full = re.fullmatch(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})(?:까지|마감)?", text.replace(" ", ""))
    korean = re.fullmatch(r"(?:(\d{4})년\s*)?(\d{1,2})월\s*(\d{1,2})일(?:까지|\s*마감)?", text)
    if full or korean:
        m = full or korean
        try:
            return date(int(m[1] or base.year), int(m[2]), int(m[3])).isoformat()
        except ValueError:
            return None
    compact = re.sub(r"\s+", "", text)
    compact = re.sub(r"(?:까지|마감)$", "", compact)
    relative = {"오늘": 0, "내일": 1, "모레": 2}
    if compact in relative:
        return (base + timedelta(days=relative[compact])).isoformat()
    m = re.fullmatch(r"(\d+)일(?:후|뒤)", compact)
    if m:
        return (base + timedelta(days=int(m[1]))).isoformat()
    m = re.fullmatch(r"(이번주|다음주|다다음주)([월화수목금토일])요일", compact)
    if m:
        offset = {"이번주": 0, "다음주": 7, "다다음주": 14}[m[1]]
        return (base - timedelta(days=base.weekday()) + timedelta(days=offset + "월화수목금토일".index(m[2]))).isoformat()
    if compact in ("이번달말", "이번달말일", "이달말"):
        return base.replace(day=calendar.monthrange(base.year, base.month)[1]).isoformat()
    return None


def calendar_tasks_from_analysis(data, base):
    return [{"id": f"task_{i}", "title": item["업무명"],
             "detail": item.get("근거", ""),
             "due_date": resolve_deadline(item.get("기한"), base),
             "done": False, "importance": item.get("중요도", "확인 필요"),
             "due_evidence": item.get("기한") or "기록에 없음",
             "importance_evidence": item.get("근거", ""),
             "date_source": "원문에서 변환"}
            for i, item in enumerate(data.get("업무목록", []))]


def render_schedule_editor():
    st.subheader("📝 일정 관리")
    st.caption("원문 기한을 확인하고 필요한 날짜를 직접 지정하세요. 기한 미정은 달력에 배치되지 않습니다.")
    with st.form("calendar_manage_form"):
        changes = []
        for task in st.session_state.calendar_tasks:
            st.markdown(f"**{task['title']}**")
            st.caption(f"원문 기한: {task['due_evidence']} · {task['date_source']}")
            c1, c2 = st.columns([3, 1])
            due = c1.date_input("마감일 (미정이면 비워두세요)",
                value=date.fromisoformat(task['due_date']) if task['due_date'] else None,
                key=f"calendar_edit_date_{task['id']}")
            done = c2.checkbox("완료", value=task['done'], key=f"calendar_edit_done_{task['id']}")
            changes.append((task, due.isoformat() if due else None, done))
        if st.form_submit_button("일정 변경 저장"):
            for task, due, done in changes:
                if task['due_date'] != due:
                    task['date_source'] = "사용자 지정"
                task['due_date'], task['done'] = due, done
            st.rerun()


# ── 기본 설정 ─────────────────────────────────────
# 키는 환경변수에서 자동
client = OpenAI()

# 이메일 요청 시 받을 주소 (음성 인식 오류를 피하려고 코드에 고정)
MY_EMAIL = "spider379@naver.com"

# ★ [화면] 에이블 대표 이미지 경로 (app.py와 같은 폴더에 둔 파일 이름)
IMAGE_PATH = "able.png"

# ★ [추가 기능 2] 대화 기록 최대 개수 (질문 1 + 답변 1 = 2개 → 10이면 최근 5번의 대화)
MAX_HISTORY = 10

# ★ [추가 기능 3] 음성용 텍스트 정리: 마크다운 기호를 빼야 TTS가 매끄럽게 읽음
def to_speech_text(text):
    text = re.sub(r"[#*`>|]", "", text)              # 제목·굵게 등 기호 제거
    text = re.sub(r"^\s*-\s*", "", text, flags=re.M)  # 줄 앞 목록 기호 '-' 제거
    return text[:4000]                                # TTS 입력 길이 한도

# 에이블 역할
sys_role = """
당신은 '김 대리'의 개인 비서 '에이블'입니다.
김 대리가 회의에 참석하지 못했을 때, 회의 내용을 정리해 업무를 놓치지 않도록 돕습니다.

[주요 업무]
1. 회의록을 분석하고 핵심 내용을 요약합니다.
2. 회의록에서 김 대리에게 배정된 업무 지시사항을 찾아 자세히 정리합니다.
3. 김 대리의 다양한 질문에 답변합니다.

[답변 규칙]
- 한국어로 정중하고 간결하게 답변합니다.
- 회의록에 없는 내용은 지어내지 않습니다.
- 요약을 주제 → 논의 내용 → 결정 사항 순서로 구역을 나눠서 진행합니다.
- 김 대리 담당 업무는 요약과 별도로 정리하고, 업무마다 업무명, 세부 내용, 기한을 함께 적습니다. 기한이 언급되지 않은 업무는 '기한 미정'으로 표시합니다.
- 결정 사항에는 예산, 일정, 채널처럼 구체적인 수치와 항목을 포함합니다.
- 업무 세부 내용에는 회의에서 언급된 방향과 조건을 포함합니다.
- 기한은 회의에서 해당 업무에 대해 명시적으로 언급된 경우에만 적습니다. 추측하지 않습니다.
- 이메일은 김 대리가 요청한 경우에만 보내고 이메일 본문은 마크다운 기호 없이 작성합니다.
- 이메일 요청이 있으면 반드시 send_email 도구를 사용해 실제로 보냅니다. 도구를 쓰지 않고 보냈다고 말하지 않습니다.
- 받는 사람 주소는 [김 대리 이메일 주소]에 적힌 값만 사용합니다.
"""

# ── 이메일 발송 함수 (미션 1) ──
def send_email(to, subject, body):
    sender = os.getenv("GMAIL_ADDRESS")
    password = os.getenv("GMAIL_APP_PASSWORD")

    # Secrets에 값이 없으면 연결 전에 바로 안내
    if not sender or not password:
        return {"status": "failed",
                "error": "GMAIL_ADDRESS 또는 GMAIL_APP_PASSWORD가 설정되지 않았습니다."}

    msg = MIMEText(body, "plain", "utf-8")   # 한글 본문 깨짐 방지
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to

    try:
        # 465 포트: 처음부터 SSL로 연결 (클라우드 서버에서 더 안정적)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as s:
            s.login(sender, password)
            s.sendmail(sender, to, msg.as_string())
        return {"status": "success"}
    except Exception as e:
        return {"status": "failed", "error": str(e)}

# ── 도구 정의 (미션 7)  ──
# description: LLM이 도구를 언제·어떻게 쓸지 판단하는 기준
tools = [{
    "type": "function",
    "name": "send_email",
    "description": "이메일을 발송합니다. 요청받은 내용은 한 통의 이메일로 모아서 보냅니다.",
    "parameters": {
        "type": "object",
        "properties": {
            "to": {"type": "string",
                   "description": "이메일 수신자. 예: 'test@gmail.com'"},
            "subject": {"type": "string",
                        "description": "이메일 제목. 예: '마케팅 전략 초안'"},
            "body": {"type": "string",
                     "description": "이메일 본문. 회의 요약과 김 대리 담당 업무를 모두 포함하고, 마크다운 기호(#, *, -) 없이 일반 텍스트로 작성. 예: '안녕하세요, 김 대리님. 비서 에이블입니다.'"}
        },
        "required": ["to", "subject", "body"],
        "additionalProperties": False
    },
    "strict": True
}]

# ── 업무 우선순위 분석용 출력 스키마 (05 실습 JSON 구조화) ──
priority_schema = {
    "type": "json_schema",
    "name": "priority",
    "schema": {
        "type": "object",
        "properties": {
            "업무목록": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "업무명": {"type": "string"},
                        "기한": {"type": ["string", "null"]},
                        "긴급도": {"type": "string", "enum": ["높음", "낮음"]},
                        "중요도": {"type": "string", "enum": ["높음", "낮음"]},
                        "근거": {"type": "string"}
                    },
                    "required": ["업무명", "기한", "긴급도", "중요도", "근거"],
                    "additionalProperties": False
                }
            },
            "참석자별업무": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "이름": {"type": "string"},
                        "업무수": {"type": "integer"}
                    },
                    "required": ["이름", "업무수"],
                    "additionalProperties": False
                }
            }
        },
        "required": ["업무목록", "참석자별업무"],
        "additionalProperties": False
    }
}

# 우선순위 분석 프롬프트 템플릿
priority_template = """
다음 회의록을 분석하세요.

1. 김 대리에게 배정된 업무를 모두 추출하세요.
   - 기한은 회의록에서 해당 업무에 명시된 표현 그대로 적고, 없으면 null로 하세요.
   - 긴급도: 기한이 가깝거나 회의에서 서둘러야 한다고 언급되면 '높음', 아니면 '낮음'
   - 중요도: 신제품 출시와 매출에 직접 영향을 주면 '높음', 보조 업무면 '낮음'
   - 근거: 판단 이유를 회의록 내용에 근거해 한 문장으로 쓰세요.
2. 회의 참석자(김 대리 포함)별로 새로 배정된 업무 수를 세세요.
   업무를 전달하거나 회의록을 정리하는 일은 업무로 세지 않습니다.

회의록에 없는 내용은 지어내지 마세요.

[회의록]
{meeting}
"""

# 긴급도 × 중요도 → 분류 (파이썬으로 정해서 결과 일관되게)
def classify(urgent, important):
    if urgent == "높음" and important == "높음":
        return "즉시 착수"
    elif important == "높음":
        return "순차 진행"
    else:
        return "위임 검토"

# ── 화면: 제목 ──
st.set_page_config(page_title="AI 개인비서 에이블", page_icon="🤖", layout="wide")
st.title("🤖 AI 개인비서 에이블")
st.caption("음성으로 질문하시면 답변해 드립니다.")

# ★ [화면] 소개 영역: 왼쪽 이미지 / 오른쪽 역할·핵심 기능
left, right = st.columns([1, 2])
with left:
    if os.path.exists(IMAGE_PATH):
        st.image(IMAGE_PATH, width="stretch")   # 칸 너비에 맞춤
    else:
        st.info("🖼️ 이미지 준비 중\n\n(IMAGE_PATH 경로에 파일을 넣으세요)")
with right:
    st.markdown("""
#### 김 대리의 AI 개인비서, 에이블
- 📝 회의록을 분석해 **요약하고 내 업무를 찾아** 드립니다.
- 🎙️ **음성으로 질문**하면 글과 음성으로 답하고, 요청 시 **이메일**로 보냅니다.
- 📅 업무 **우선순위**를 정리하고 마감일을 **캘린더**에 등록합니다.
""")

st.divider()

# ── 세션 상태 초기화 (S04: 처음 한 번만) ──
if "messages" not in st.session_state:
    st.session_state.messages = []        # 대화 히스토리
if "meeting_text" not in st.session_state:
    st.session_state.meeting_text = ""    # 업로드한 회의록 (탭 전환 시 유지)

if "priority_data" not in st.session_state:
    st.session_state.priority_data = None
if "calendar_tasks" not in st.session_state:
    st.session_state.calendar_tasks = []
if "calendar_base_date" not in st.session_state:
    st.session_state.calendar_base_date = None

# ★ [화면] 기능별 탭 (제목을 누르면 해당 기능만 보임)
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🎙️ AI 비서 (회의록·음성 질문)", "📊 업무 우선순위 분석", "📅 마감 캘린더",
                                        "📨 팔로업 메일", "🎧 출근길 브리핑"])

# ════════════════ 탭 1: 회의록 업로드 · 음성 질문 · AI 답변 · 대화 기록 ════════════════
with tab1:
    # ── 화면: 회의록 업로드  ──
    uploaded_file = st.file_uploader("회의록 파일 업로드 (txt)", type=["txt"])

    # 새 파일이 올라오면 세션 상태에 저장 → 다른 탭에 갔다 와도 유지됨
    if uploaded_file is not None:
        new_text = uploaded_file.getvalue().decode("utf-8-sig")
        if new_text != st.session_state.meeting_text:
            st.session_state.meeting_text = new_text
            st.session_state.messages = []
            st.session_state.priority_data = None
            st.session_state.calendar_tasks = []
            st.session_state.calendar_base_date = None
            for key in list(st.session_state):
                if key.startswith("calendar_edit_"):
                    del st.session_state[key]

    # 아래 코드는 모두 meeting_text 하나로 사용
    meeting_text = st.session_state.meeting_text

    if meeting_text == "":
        st.info("회의록 파일을 업로드하면 회의 내용을 바탕으로 답변합니다.")
    else:
        st.success("회의록이 준비되었습니다.")
        st.text_area("회의록 내용", meeting_text, height=150)

    # ── 화면: 음성 녹음 + 실행 버튼 ──
    audio_value = st.audio_input("무엇을 도와드릴까요?")
    voice_on = st.toggle("🔊 답변을 음성으로 듣기", value=True)   # ★ [추가 기능 3] 음성 켜기/끄기

    if st.button("실행"):
        if audio_value is None:
            st.warning("먼저 마이크 버튼을 눌러 질문을 녹음해 주세요.")
        else:
            try:
                # 시간이 걸리는 작업 동안 스피너 표시
                with st.spinner("답변을 준비하고 있습니다.."):

                    # STT: 녹음은 파일이 아니라 메모리 데이터 → (파일명, 바이트)로 전달
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=("recording.wav", audio_value.getvalue())
                    )

                    # 프롬프트: 음성 요청 + 고정 이메일 주소 + 회의록
                    prompt = f"""
{transcript.text}

[김 대리 이메일 주소]
{MY_EMAIL}

[미팅 내용]
{meeting_text}
"""

                    # 음성 요청에 '메일'이 들어 있으면 이메일 도구를 반드시 사용
                    # ('이 메일', '이메일' 모두 잡히도록 '메일'로 검사)
                    wants_email = "메일" in transcript.text
                    if wants_email:
                        choice = {"type": "function", "name": "send_email"}
                    else:
                        choice = "auto"

                    # 1단계: 질문 + 도구 정의 전달
                    # parallel False: 메일 한 통만
                    response = client.responses.create(
                        model="gpt-4o-mini",
                        # ★ [추가 기능 1] 멀티턴: 역할 → 이전 대화 → 이번 질문 순서로 전달
                        input=[{"role": "system", "content": sys_role}]
                              + st.session_state.messages
                              + [{"role": "user", "content": prompt}],
                        tools=tools,
                        tool_choice=choice,
                        parallel_tool_calls=False,
                        temperature=0
                    )

                    # 도구 호출 요청이 있는지 확인
                    tool_calls = [item for item in response.output
                                  if item.type == "function_call"]

                    if not tool_calls:
                        answer = response.output_text
                    else:
                        # 2단계: LLM이 정한 인자(to, subject, body)로 함수 실행
                        tool_outputs = []
                        for item in tool_calls:
                            if item.name == "send_email":
                                args = json.loads(item.arguments)
                                result = send_email(**args)
                                tool_outputs.append({
                                    "type": "function_call_output",
                                    "call_id": item.call_id,
                                    "output": json.dumps(result, ensure_ascii=False)
                                })

                        # 3단계: 실행 결과를 LLM에 돌려주고 최종 답변 받기
                        final_response = client.responses.create(
                            model="gpt-4o-mini",
                            previous_response_id=response.id,
                            input=tool_outputs,
                            temperature=0
                        )
                        answer = final_response.output_text

                # ── 결과 화면 ──────────────────────────
                st.markdown("#### 🎙️ 인식된 질문")
                st.info(transcript.text)   # 음성 인식이 정확한지 확인용

                if tool_calls:   # 메일을 보냈을 때만 발송 결과 표시
                    if result["status"] == "success":
                        st.success(f"📧 {args['to']}(으)로 이메일을 보냈습니다.")
                    else:
                        st.error(f"이메일 발송 실패: {result.get('error')}")

                st.divider()
                st.markdown("### AI 답변")
                st.markdown(answer)   # 마크다운(###, **)을 서식으로 변환해 표시

                # ★ [추가 기능 3] LLM 최종 응답을 음성으로 즉시 재생 (미션 5·6 TTS)
                if voice_on:
                    with st.spinner("음성을 준비하고 있습니다.."):
                        speech = client.audio.speech.create(
                            model="gpt-4o-mini-tts",
                            voice="nova",
                            input=to_speech_text(answer),
                            instructions="비서가 담당자에게 얘기하는 정중한 말투로 빠뜨리지 말고 또박또박 읽어주세요."
                        )
                    st.audio(speech.content, format="audio/mp3", autoplay=True)

                # 대화 히스토리 저장 (질문·답변 한 쌍씩, 최근 10개만 유지)
                st.session_state.messages.append({"role": "user", "content": transcript.text})
                st.session_state.messages.append({"role": "assistant", "content": answer})
                st.session_state.messages = st.session_state.messages[-MAX_HISTORY:]   # ★ 숫자를 변수로

            except Exception as e:
                # API·네트워크 오류 시 앱이 멈추지 않고 안내만 표시 (종합실습6)
                st.error(f"오류가 발생했습니다: {e}")

    # ── 화면: 대화 기록 (종합실습6 st.chat_message) ──
    if st.session_state.messages:
        with st.expander(f"💬 대화 기록 ({len(st.session_state.messages) // 2}건)"):
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
        # ★ [추가 기능 2] 대화 기록 지우기 (새 회의록으로 바꿀 때 이전 대화가 섞이지 않게)
        if st.button("🗑️ 대화 기록 지우기"):
            st.session_state.messages = []
            st.rerun()   # 화면을 바로 다시 그려 기록을 지움

# ════════════════ 탭 2: 업무 우선순위 분석 ════════════════
with tab2:
    st.subheader("📊 업무 우선순위 분석")
    st.caption("업로드한 회의록에서 김 대리 업무를 긴급도 × 중요도로 분류합니다.")

    if st.button("우선순위 분석"):
        if meeting_text == "":
            st.warning("먼저 회의록 파일을 업로드해 주세요.")
        else:
            try:
                with st.spinner("업무를 분석하고 있습니다.."):
                    response = client.responses.create(
                        model="gpt-4o-mini",
                        input=[{"role": "user",
                                "content": priority_template.format(meeting=meeting_text)}],
                        text={"format": priority_schema},   # 정해진 JSON 형식으로만 답변
                        temperature=0
                    )
                    data = json.loads(response.output_text)   # JSON 문자열 → 딕셔너리

                st.session_state.priority_data = data
                base = datetime.now(ZoneInfo("Asia/Seoul")).date()
                st.session_state.calendar_tasks = calendar_tasks_from_analysis(data, base)
                st.session_state.calendar_base_date = base.isoformat()
                for key in list(st.session_state):
                    if key.startswith("calendar_edit_"):
                        del st.session_state[key]

            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")

    if st.session_state.priority_data is not None:
        data = st.session_state.priority_data
        # ── ① 업무 집중도 (R&R 밸런스) ──────────
        df_people = pd.DataFrame(data["참석자별업무"], columns=["이름", "업무수"])
        kim = df_people[df_people["이름"].str.contains("김", na=False)]["업무수"].sum()
        total = df_people["업무수"].sum()

        st.markdown("#### ⚖️ 업무 집중도")
        col1, col2 = st.columns(2)
        col1.metric("김 대리 배정 업무", f"{kim}건")
        col2.metric("전체 배정 업무 중 비중",
                    f"{kim / total * 100:.0f}%" if total else "-")

        # 김 대리 업무가 3건 이상이거나 절반 이상이면 경보
        if kim >= 3 or (total and kim / total >= 0.5):
            st.error("🚨 김 대리에게 업무가 집중되어 있습니다. 우선순위와 위임을 검토하세요.")
        else:
            st.success("업무 배분이 적정한 수준입니다.")

        st.bar_chart(df_people.set_index("이름")["업무수"])

        # ── ② 우선순위 매트릭스 ──────────────────
        df_task = pd.DataFrame(data["업무목록"], columns=["업무명", "기한", "긴급도", "중요도", "근거"])
        df_task["기한"] = df_task["기한"].fillna("기한 미정").replace("null", "기한 미정")
        df_task["분류"] = [classify(r["긴급도"], r["중요도"]) for _, r in df_task.iterrows()]

        st.markdown("#### 🗂️ 우선순위 가이드")
        cols = st.columns(3)
        for col, group, icon in zip(cols,
                                    ["즉시 착수", "순차 진행", "위임 검토"],
                                    ["🔴", "🟡", "🔵"]):
            col.markdown(f"**{icon} {group}**")
            tasks = df_task[df_task["분류"] == group]
            if tasks.empty:
                col.caption("해당 업무 없음")
            for _, t in tasks.iterrows():
                col.info(f"**{t['업무명']}**\n\n⏰ {t['기한']}")

        # ── ③ 판단 근거 표 ───────────────────────
        st.markdown("#### 📋 판단 근거")
        st.dataframe(df_task[["분류", "업무명", "기한", "긴급도", "중요도", "근거"]],
                     hide_index=True)
        st.caption("※ 중요도는 회의 내용을 바탕으로 한 에이블의 판단입니다.")

# ════════════════ 탭 3: 연결된 캘린더 ════════════════
with tab3:
    if st.session_state.priority_data is None:
        st.info("회의록을 업로드한 뒤 ‘업무 우선순위 분석’ 탭에서 분석 버튼을 눌러주세요.")
    elif not st.session_state.calendar_tasks:
        st.info("회의록에서 김 대리에게 배정된 업무를 찾지 못했습니다.")
    else:
        st.caption(f"상대 날짜 기준: {st.session_state.calendar_base_date} (한국 시간, 분석 실행일) · 날짜만 조작할 때는 AI를 다시 호출하지 않습니다.")
        st.caption("연도가 없는 월·일은 분석한 해를 적용합니다. 모호한 기한은 미정으로 두며 아래 일정 관리에서 수정할 수 있습니다.")
        main_calendar, preview = st.columns([3, 1])
        with main_calendar:
            render_calendar(st.session_state.calendar_tasks)
        with preview:
            render_calendar_preview(st.session_state.calendar_tasks)
        render_schedule_editor()

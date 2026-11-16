
import os
import logging
from pathlib import Path

import streamlit as st

from rag import rag_pipeline


st.set_page_config(
    page_title="AIVLE 학습도우미",
    page_icon="🎓",
    layout="centered",
)

st.markdown(
    """
    <style>
        .stApp {
            background-color: #F7F8FC;
        }
        .block-container {
            max-width: 900px;
            padding-top: 2rem;
        }
        [data-testid="stSidebar"] {
            background-color: #EEF1F8;
        }
        [data-testid="stChatMessage"] {
            background-color: white;
            border: 1px solid #E4E8F0;
            border-radius: 14px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# API 키 확인
api_key = os.environ.get("OPENAI_API_KEY")

if not api_key:
    try:
        api_key = st.secrets.get("OPENAI_API_KEY")
    except FileNotFoundError:
        api_key = None

if not api_key:
    st.error("앱 Settings → Secrets에 OPENAI_API_KEY를 설정해 주세요.")
    st.stop()

os.environ["OPENAI_API_KEY"] = api_key


# PDF 경로: GitHub 저장소에 함께 올린 파일
pdf_path = Path(__file__).resolve().parent / "aivle_whitepaper.pdf"

if not pdf_path.is_file():
    st.error("저장소에 aivle_whitepaper.pdf 파일이 없습니다.")
    st.stop()


# 대화 기록
if "messages" not in st.session_state:
    st.session_state.messages = []


# 같은 서버에서 체인을 공유해 중복 초기화 방지
@st.cache_resource
def load_chain(filepath, modified_time, file_size):
    return rag_pipeline(filepath, search_type="mmr", k=6)


with st.sidebar:
    st.title("🎓 AIVLE")
    st.caption("백서 기반 학습도우미")
    st.divider()

    st.markdown("**이런 내용을 물어보세요**")
    st.markdown(
        "- 교육 과정과 트랙\n"
        "- 출결과 훈련장려금\n"
        "- 학습 전략과 프로젝트\n"
        "- 선배 후기와 취업 준비"
    )

    st.divider()

    if st.button("🗑️ 대화 초기화", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.caption(
        "기수별 운영 기준과 선배 개인 경험을 구분하여 확인해 주세요."
    )


st.title("AIVLE School 학습도우미")
st.write("궁금한 내용을 질문하면 백서에서 근거를 찾아 답해 드려요.")
st.caption("교육 안내 · 학습 전략 · 프로젝트 · 취업 준비")


# 백서 연결
try:
    stat = pdf_path.stat()

    with st.spinner("백서를 연결하고 있어요. 첫 실행에는 시간이 걸릴 수 있어요."):
        chain = load_chain(
            str(pdf_path),
            stat.st_mtime_ns,
            stat.st_size,
        )

except Exception:
    logging.exception("RAG 초기화 실패")
    st.error("백서 연결에 실패했어요. Manage app의 로그를 확인해 주세요.")
    st.stop()


# 추천 질문
selected_question = None

if not st.session_state.messages:
    st.subheader("어떤 내용이 궁금한가요?")

    examples = [
        "훈련장려금 지급 조건을 알려줘.",
        "지각과 조퇴는 출결에 어떻게 반영돼?",
        "교육 초반에 어떻게 공부하면 좋을까?",
        "9기 DX 1차 미니프로젝트는 어떤 내용이야?",
    ]

    columns = st.columns(2)

    for i, example in enumerate(examples):
        with columns[i % 2]:
            if st.button(
                example,
                key=f"example_{i}",
                use_container_width=True,
            ):
                selected_question = example


# 이전 대화 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


typed_question = st.chat_input(
    "예: 정상수료와 우수수료는 어떻게 다른가요?"
)

question = selected_question or typed_question

if question:
    st.session_state.messages.append({
        "role": "user",
        "content": question,
    })

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        try:
            with st.spinner("백서에서 답변을 찾고 있어요..."):
                answer = chain.invoke({"input": question})

            st.markdown(answer)

            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
            })

        except Exception:
            logging.exception("답변 생성 실패")
            st.error(
                "답변 생성에 실패했어요. "
                "Manage app의 로그를 확인해 주세요."
            )

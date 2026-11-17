
import hashlib
import logging
import os
import tempfile
from pathlib import Path

import streamlit as st

from rag import rag_pipeline


st.set_page_config(
    page_title="AIVLE School 학습 도우미",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded",
)

state = st.session_state
state.setdefault("messages", [])
state.setdefault("selected_hash", None)
state.setdefault("chain", None)
state.setdefault("work_dir", None)

MAX_PDF_MB = 25

EXAMPLES = [
    "훈련장려금을 받으려면 어떤 조건을 충족해야 하나요?",
    "지각과 조퇴는 출결에 어떻게 반영되나요?",
    "교육 초반에는 어떻게 공부하면 좋을까요?",
    "미니프로젝트는 어떻게 준비하면 좋을까요?",
]


def clear_document():
    """연결과 채팅을 초기화하고 이전 작업 폴더를 정리합니다."""
    state.chain = None
    state.messages = []

    if state.work_dir is not None:
        state.work_dir.cleanup()
        state.work_dir = None


# 왼쪽 화면 · 문서 관리와 추천 질문
with st.sidebar:
    st.title("📘 AIVLE")
    st.caption("백서로 찾는 교육 정보와 학습 가이드")

    st.divider()
    st.subheader("1. 백서 업로드")

    uploaded = st.file_uploader(
        "백서 PDF 한 개를 선택해 주세요.",
        type=["pdf"],
        key="whitepaper",
    )

    pdf_data = None
    file_hash = None

    if uploaded is not None:
        if uploaded.size == 0:
            st.warning("빈 파일입니다. 다른 PDF를 선택해 주세요.")
        elif uploaded.size > MAX_PDF_MB * 1024 * 1024:
            st.warning(f"{MAX_PDF_MB}MB 이하의 PDF를 선택해 주세요.")
        else:
            pdf_data = uploaded.getvalue()
            file_hash = hashlib.sha256(pdf_data).hexdigest()

    # 다른 문서를 선택하거나 파일을 제거한 경우 이전 연결 해제
    if file_hash != state.selected_hash:
        clear_document()
        state.selected_hash = file_hash

    if st.button(
        "문서 연결",
        type="primary",
        use_container_width=True,
        disabled=pdf_data is None or state.chain is not None,
    ):
        if not os.environ.get("OPENAI_API_KEY"):
            st.error("Streamlit 앱 Settings → Secrets에서 OPENAI_API_KEY를 설정해 주세요.")
        else:
            # 업로드한 문서마다 임시 PDF와 Chroma 저장소를 따로 사용
            work_dir = tempfile.TemporaryDirectory(prefix="aivle_")
            try:
                root = Path(work_dir.name)
                pdf_path = root / "whitepaper.pdf"
                pdf_path.write_bytes(pdf_data)

                with st.spinner("백서를 읽고 검색을 준비하고 있어요..."):
                    state.chain = rag_pipeline(
                        str(pdf_path),
                        search_type="mmr",
                        k=6,
                        db_directory=str(root / "chroma_db"),
                    )

                state.work_dir = work_dir

            except Exception:
                work_dir.cleanup()
                logging.exception("백서 연결 실패")
                st.error(
                    "백서를 연결하지 못했어요. PDF와 API 키를 확인해 주세요. "
                    "자세한 원인은 Manage app 로그에서 확인할 수 있어요."
                )

    ready = state.chain is not None

    if ready:
        st.success("문서 연결 완료")
        st.caption(f"현재 문서 · {uploaded.name}")
    elif pdf_data is not None:
        st.caption("문서 연결 버튼을 누르면 질문할 수 있어요.")

    st.divider()
    st.subheader("2. 추천 질문")

    selected_question = None

    for index, example in enumerate(EXAMPLES):
        if st.button(
            example,
            key=f"example_{index}",
            use_container_width=True,
            disabled=not ready,
        ):
            selected_question = example

    st.divider()

    if st.button(
        "🗑️ 대화 삭제",
        use_container_width=True,
        disabled=not state.messages,
    ):
        state.messages = []
        st.rerun()

    st.caption("대화 삭제 후에도 백서 연결은 유지돼요.")


# 오른쪽 화면 · 채팅
st.title("AIVLE School 학습 도우미")
st.caption("출결·지원 제도·프로젝트·학습 전략을 백서에서 찾아보세요.")

if not ready:
    st.info("왼쪽에서 PDF를 업로드하고 **문서 연결**을 눌러 주세요.")
elif not state.messages:
    with st.chat_message("assistant", avatar="📘"):
        st.markdown(
            "백서가 연결됐어요! 추천 질문을 누르거나 "
            "아래에 궁금한 내용을 입력해 주세요."
        )

for message in state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

typed_question = st.chat_input(
    "예: 정상수료와 우수수료는 어떻게 다른가요?",
    disabled=not ready,
    max_chars=1000,
)

question = (selected_question or typed_question or "").strip()

if ready and question:
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant", avatar="📘"):
        try:
            with st.spinner("백서에서 답변 근거를 찾고 있어요..."):
                answer = st.write_stream(
                    state.chain.stream({"input": question})
                )

            if answer:
                state.messages.extend([
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": answer},
                ])
            else:
                st.warning("답변을 받지 못했어요. 다시 질문해 주세요.")

        except Exception:
            logging.exception("답변 생성 실패")
            st.error("답변을 끝까지 받지 못했어요. 잠시 후 다시 질문해 주세요.")




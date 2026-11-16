
import os
import streamlit as st

from rag import rag_pipeline


# 1. 화면 설정
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


# 2. 대화와 체인 저장
if "messages" not in st.session_state:
    st.session_state.messages = []

if "rag_chain" not in st.session_state:
    st.session_state.rag_chain = None


# 3. 사이드바
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

    if st.button(
        "🗑️ 대화 초기화",
        use_container_width=True,
    ):
        st.session_state.messages = []
        st.rerun()

    st.caption(
        "선배 후기는 해당 기수의 경험입니다. "
        "운영 기준은 적용 기수를 함께 확인해 주세요."
    )


# 4. 메인 제목
st.title("AIVLE School 학습도우미")
st.write("궁금한 내용을 질문하면 백서에서 근거를 찾아 답해 드려요.")
st.caption("교육 안내 · 학습 전략 · 프로젝트 · 취업 준비")


# 5. 기존 벡터 DB 연결
# 첫 접속 때만 체인을 만들고 이후 질문에서는 재사용
if st.session_state.rag_chain is None:
    pdf_path = os.environ.get("AIVLE_PDF_PATH")

    if not pdf_path or not os.path.isfile(pdf_path):
        st.error("PDF 경로를 확인해 주세요. 코랩의 ①번 셀을 실행해야 합니다.")
        st.stop()

    try:
        with st.spinner("백서 검색 자료를 연결하고 있어요..."):
            st.session_state.rag_chain = rag_pipeline(
                pdf_path,
                search_type="mmr",
                k=6,
            )

    except Exception:
        st.error("검색 자료 연결에 실패했어요.")

        # 오류 상세는 코랩의 streamlit.log에 기록
        import logging
        logging.exception("RAG 초기화 실패")

        st.info("코랩에서 streamlit.log를 확인해 주세요.")
        st.stop()


# 6. 추천 질문
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


# 7. 이전 대화 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# 8. 질문 입력
typed_question = st.chat_input(
    "예: 정상수료와 우수수료는 어떻게 다른가요?"
)

question = selected_question or typed_question


# 9. 답변 생성
if question:
    with st.chat_message("user"):
        st.markdown(question)

    st.session_state.messages.append(
        {"role": "user", "content": question}
    )

    with st.chat_message("assistant"):
        try:
            with st.spinner("백서에서 답변을 찾고 있어요..."):
                answer = st.session_state.rag_chain.invoke(
                    {"input": question}
                )

            st.markdown(answer)

            st.session_state.messages.append(
                {"role": "assistant", "content": answer}
            )

        except Exception:
            st.error(
                "답변 생성에 실패했어요. "
                "연결 상태를 확인한 뒤 다시 질문해 주세요."
            )

            import logging
            logging.exception("답변 생성 실패")

import streamlit as st
import pandas as pd
import random
from pandasql import sqldf
import ollama
import re
import sqlite3
from io import StringIO

# 모델 설정
MODEL_NAME = "gemma2:9b"
SQL_VALIDATION_MODEL = "codellama:7b"  # SQL 문법 검증용
LOGIC_VALIDATION_MODEL = "llama3.1:8b"  # 논리 검증용
# -----------------------------
# 매핑 파일 로더 (심플)
# -----------------------------
def load_mapping(file):
    mdf = pd.read_excel(file)
    if mdf.empty or len(mdf.columns) < 2:
        raise ValueError("매핑 파일은 최소 2개 컬럼(english, korean)이 필요합니다.")
    cols = {str(c).strip().lower(): c for c in mdf.columns}
    eng_key = cols.get("english") or cols.get("eng") or cols.get("en") or cols.get("영문") or cols.get("영문명")
    kor_key = cols.get("korean")  or cols.get("kor") or cols.get("ko") or cols.get("한글") or cols.get("한글명") or cols.get("alias") or cols.get("별칭")
    if eng_key is None or kor_key is None:
        eng_key, kor_key = mdf.columns[:2]
    ko2en = {}
    rows = []
    for _, r in mdf.iterrows():
        en = str(r[eng_key]).strip()
        ko = str(r[kor_key]).strip()
        if en and ko and en.lower() != "nan" and ko.lower() != "nan":
            ko2en[ko] = en
            rows.append({"korean": ko, "english": en})
    preview_df = pd.DataFrame(rows)
    return ko2en, preview_df
# -----------------------------
# SQL 검증 함수들
# -----------------------------
def validate_sql_syntax(sql_query, df, table_name="df"):
    """SQL 문법 검증 (CodeLlama 사용)"""
    try:
        # SQLite 문법 검증
        conn = sqlite3.connect(':memory:')
        df.to_sql(table_name, conn, index=False, if_exists='replace')
        
        # SQL 파싱 테스트
        cursor = conn.cursor()
        cursor.execute(f"EXPLAIN QUERY PLAN {sql_query}")
        conn.close()
        
        return True, "SQL 문법이 올바릅니다."
    except Exception as e:
        return False, f"SQL 문법 오류: {str(e)}"

def validate_sql_with_llm(sql_query, original_query, df, table_name="df"):
    """LLM을 사용한 SQL 검증 (CodeLlama + Llama)"""
    schema_info = f"Columns: {', '.join(map(str, df.columns))}\n\nSample Data:\n{df.head(3).to_string(index=False)}"
    
    # 1. 문법 검증 (CodeLlama)
    syntax_prompt = f"""
    다음 SQL 쿼리의 문법을 검증해주세요. SQLite 문법을 기준으로 합니다.
    
    스키마 정보:
    {schema_info}
    
    SQL 쿼리: {sql_query}
    
    응답 형식:
    - 문법이 올바르면: "VALID: [간단한 설명]"
    - 문법 오류가 있으면: "INVALID: [오류 내용과 수정 제안]"
    """
    
    try:
        syntax_response = ollama.chat(
            model=SQL_VALIDATION_MODEL,
            messages=[{"role": "user", "content": syntax_prompt}]
        )
        syntax_result = syntax_response["message"]["content"].strip()
    except Exception as e:
        syntax_result = f"문법 검증 실패: {str(e)}"
    
    # 2. 논리 검증 (Llama)
    logic_prompt = f"""
    다음 자연어 질의와 생성된 SQL 쿼리가 논리적으로 일치하는지 검증해주세요.
    
    원본 질의: "{original_query}"
    생성된 SQL: {sql_query}
    스키마 정보: {schema_info}
    
    검증 기준:
    1. SQL이 원본 질의의 의도를 정확히 반영하는가?
    2. 사용된 컬럼명이 스키마에 존재하는가?
    3. 조건문이 논리적으로 타당한가?
    4. 예상되는 결과가 질의와 일치하는가?
    
    응답 형식:
    - 논리가 올바르면: "LOGIC_VALID: [간단한 설명]"
    - 논리 오류가 있으면: "LOGIC_INVALID: [문제점과 개선 제안]"
    """
    
    try:
        logic_response = ollama.chat(
            model=LOGIC_VALIDATION_MODEL,
            messages=[{"role": "user", "content": logic_prompt}]
        )
        logic_result = logic_response["message"]["content"].strip()
    except Exception as e:
        logic_result = f"논리 검증 실패: {str(e)}"
    
    return syntax_result, logic_result

def get_validation_summary(syntax_result, logic_result):
    """검증 결과 요약"""
    syntax_valid = "VALID:" in syntax_result.upper()
    logic_valid = "LOGIC_VALID:" in logic_result.upper()
    
    if syntax_valid and logic_valid:
        return "✅ 검증 통과", "success"
    elif syntax_valid and not logic_valid:
        return "⚠️ 문법은 올바르지만 논리에 문제가 있습니다", "warning"
    elif not syntax_valid and logic_valid:
        return "⚠️ 논리는 맞지만 문법에 문제가 있습니다", "warning"
    else:
        return "❌ 문법과 논리 모두에 문제가 있습니다", "error"

def validate_winners_hallucination(winners_df, original_query, sql_query, df, table_name="df"):
    """당첨자 할루시네이션 검증"""
    if winners_df.empty:
        return "❌ 검증할 당첨자가 없습니다", "error", ""
    
    # 당첨자 샘플 데이터 준비 (최대 5명)
    sample_winners = winners_df.head(5)
    winners_info = []
    for idx, row in sample_winners.iterrows():
        winner_data = {col: str(val) for col, val in row.items()}
        winners_info.append(f"당첨자 {idx+1}: {winner_data}")
    
    winners_sample = "\n".join(winners_info)
    schema_info = f"Columns: {', '.join(map(str, df.columns))}\n\nSample Data:\n{df.head(3).to_string(index=False)}"
    
    # 할루시네이션 검증 프롬프트
    hallucination_prompt = f"""
    다음 정보를 바탕으로 당첨자들이 원본 조건에 부합하는지 검증해주세요.

    원본 질의: "{original_query}"
    실행된 SQL: {sql_query}
    스키마 정보: {schema_info}
    
    당첨자 샘플 (총 {len(winners_df)}명 중 5명):
    {winners_sample}
    
    검증 기준:
    1. 각 당첨자가 원본 질의의 모든 조건을 만족하는가?
    2. SQL 쿼리가 올바르게 실행되어 적절한 결과를 반환했는가?
    3. 데이터 타입이나 값의 범위가 올바른가?
    4. 누락된 조건이나 잘못된 매핑이 있는가?
    
    응답 형식:
    - 모든 당첨자가 조건에 부합하면: "VALID: [간단한 설명]"
    - 일부 또는 모든 당첨자가 조건에 부합하지 않으면: "INVALID: [문제점과 상세 설명]"
    """
    
    try:
        response = ollama.chat(
            model=LOGIC_VALIDATION_MODEL,  # Llama 3.1 사용
            messages=[{"role": "user", "content": hallucination_prompt}]
        )
        result = response["message"]["content"].strip()
        
        # 결과 분석
        is_valid = "VALID:" in result.upper()
        if is_valid:
            return "✅ 모든 당첨자가 조건에 부합합니다", "success", result
        else:
            return "❌ 일부 당첨자가 조건에 부합하지 않습니다", "error", result
            
    except Exception as e:
        return f"❌ 할루시네이션 검증 실패: {str(e)}", "error", ""

def get_detailed_verification(winners_df, original_query, sql_query):
    """상세 검증 정보 생성"""
    verification_info = {
        "총 당첨자 수": len(winners_df),
        "원본 질의": original_query,
        "실행된 SQL": sql_query,
        "당첨자 컬럼": list(winners_df.columns),
        "데이터 타입": {col: str(winners_df[col].dtype) for col in winners_df.columns}
    }
    
    # 숫자형 컬럼의 통계 정보
    numeric_cols = winners_df.select_dtypes(include=['number']).columns
    if len(numeric_cols) > 0:
        verification_info["숫자형 컬럼 통계"] = winners_df[numeric_cols].describe().to_dict()
    
    # 범주형 컬럼의 고유값 개수
    categorical_cols = winners_df.select_dtypes(include=['object']).columns
    if len(categorical_cols) > 0:
        verification_info["범주형 컬럼 고유값"] = {
            col: winners_df[col].nunique() for col in categorical_cols
        }
    
    return verification_info

# -----------------------------
# NL → SQL (간단 프롬프트)
# -----------------------------
def convert_to_sql(nl_query, df, table_name="df"):
    schema_info = f"Columns: {', '.join(map(str, df.columns))}\n\nSample Data:\n{df.head(3).to_string(index=False)}"
    prompt = f"""
You convert Korean natural language into a valid SQLite SQL query for the table "{table_name}".
Return only the SQL query (no backticks, no explanation).
Rules:
1. Use only the columns explicitly listed in the schema. Do not invent or guess columns.
2. If the user asks about a concept not present in the schema (e.g. 탈퇴, 해지, 환불),
   then do not try to map it to another column. Instead, return a safe fallback query: "SELECT * FROM {table_name}".
3. 가입(join) and 접속(access) are different:
   - 가입 = columns such as 가입횟수, 가입여부, 가입일
   - 접속 = columns such as 접속여부, 접속횟수
   Do not confuse them.
4. If you are uncertain which column to use, or if the condition cannot be clearly applied,
   return "SELECT * FROM {table_name}" without a WHERE clause.
5. Do not include comments, backticks, or explanations in the output.
Schema & sample:
{schema_info}
Natural language: "{nl_query}"
"""
    response = ollama.chat(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}]
    )
    sql_query = response["message"]["content"].strip()
    sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
    return sql_query
# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="엑셀 당첨자 추출 (분기형)", layout="centered")
st.title("🎉 하나원큐 이벤트 당첨자 추출")
st.write("애플리케이션이 정상적으로 로드되었습니다!")
# :작은_파란색_다이아몬드: 세션 기본값 (추첨 안정화에 필요)
if "filtered_df" not in st.session_state:
    st.session_state.filtered_df = pd.DataFrame()
if "winners" not in st.session_state:
    st.session_state.winners = pd.DataFrame()
# 1) 첫 화면에서 고객 엑셀과 매핑 엑셀 모두 업로더 표시
col1, col2 = st.columns(2)
with col1:
    uploaded_file = st.file_uploader("이벤트 대상자 리스트 엑셀 업로드", type=["xlsx", "xls"], key="data")
with col2:
    mapping_file = st.file_uploader("(선택) 영문 컬럼 한글 매핑 엑셀 업로드 ", type=["xlsx", "xls"], key="mapping")
if uploaded_file is None:
    st.info("먼저 고객 데이터 엑셀을 업로드하세요.")
    st.write("엑셀 파일을 업로드하면 데이터를 확인할 수 있습니다.")
    st.stop()
try:
    base_df = pd.read_excel(uploaded_file)
except Exception as e:
    st.error(f"데이터 로드 실패: {e}")
    st.stop()
st.subheader(":메모: 업로드된 데이터 미리보기")
st.dataframe(base_df.head())
# 매핑 처리
ko2en = {}
if mapping_file is not None:
    try:
        ko2en, mapping_preview = load_mapping(mapping_file)
        with st.expander(":펼쳐진_책: 영문 :양방향_화살표: 한글 매핑 미리보기", expanded=False):
            st.dataframe(mapping_preview)
    except Exception as e:
        st.warning(f"매핑 로드 실패(무시하고 진행): {e}")
        ko2en = {}
# 2) 사용자 입력 칸 (요청 대기)
st.subheader(":렌즈가_오른쪽_위에_있는_확대경: 이벤트 선정 조건을 입력하세요")
nl_query = st.text_input("예: '가입횟수가 3회 이상이며 30대인 여성', '마케팅 동의했고, 급여가 인정된 고객'")

# SQL 검증 옵션
col1, col2 = st.columns([3, 1])
with col1:
    run = st.button("검색하기", type="primary")
with col2:
    enable_validation = st.checkbox("SQL 검증 활성화", value=True, help="생성된 SQL의 정확성을 검증합니다")
# 3) 사용자가 입력하면 '분기' 처리 → :작은_주황색_다이아몬드: 여기서 세션에 filtered_df 저장
if run:
    if not nl_query.strip():
        st.warning("질의를 입력해 주세요.")
        st.stop()
    # 분기 1) 매핑 파일이 있으면: 한글 별칭 컬럼을 생성하여 접근 용이화
    if ko2en:
        df = base_df.copy()
        created_alias_cols = []
        for ko, en in ko2en.items():
            if en in df.columns and ko not in df.columns:
                df[ko] = df[en]
                created_alias_cols.append(ko)
        if created_alias_cols:
            st.info(f"매핑 적용: 한글 별칭 컬럼 추가 → {', '.join(created_alias_cols)}")
        else:
            st.info("매핑 적용: 추가된 별칭 컬럼 없음 (이미 존재하거나 매핑 대상 영문 컬럼이 데이터에 없음)")
        branch_used = "매핑 참조(별칭 컬럼 사용)"
    # 분기 2) 매핑 파일이 없으면: 업로드한 고객 엑셀의 컬럼만 참고
    else:
        df = base_df
        branch_used = "매핑 없음(원본 컬럼만 사용)"
    try:
        sql_query = convert_to_sql(nl_query, df, table_name="df")
        st.markdown(f"**실행 분기:** {branch_used}")
        st.markdown(f":오른쪽_화살표: 변환된 SQL\n```sql\n{sql_query}\n```")
        
        # 할루시네이션 검증을 위해 세션에 저장
        st.session_state.last_query = nl_query
        st.session_state.last_sql = sql_query
        st.session_state.base_df = df
        
        # SQL 검증 수행 (옵션에 따라)
        if enable_validation:
            with st.spinner("SQL 검증 중..."):
                # 1. 기본 문법 검증
                syntax_valid, syntax_msg = validate_sql_syntax(sql_query, df, table_name="df")
                
                # 2. LLM 기반 검증
                syntax_llm_result, logic_llm_result = validate_sql_with_llm(sql_query, nl_query, df, table_name="df")
                
                # 3. 검증 결과 요약
                summary, status = get_validation_summary(syntax_llm_result, logic_llm_result)
            
            # 검증 결과 표시
            st.subheader(":검증: SQL 검증 결과")
            
            col1, col2 = st.columns(2)
            with col1:
                if syntax_valid:
                    st.success("✅ 기본 문법 검증 통과")
                else:
                    st.error(f"❌ 기본 문법 오류: {syntax_msg}")
            
            with col2:
                if "success" in status:
                    st.success(summary)
                elif "warning" in status:
                    st.warning(summary)
                else:
                    st.error(summary)
            
            # 상세 검증 결과
            with st.expander("🔍 상세 검증 결과", expanded=False):
                st.markdown("**문법 검증 (CodeLlama):**")
                st.text(syntax_llm_result)
                st.markdown("**논리 검증 (Llama):**")
                st.text(logic_llm_result)
            
            # 검증 실패 시 경고
            if not syntax_valid or "error" in status:
                st.warning("⚠️ SQL에 문제가 있습니다. 쿼리 실행을 중단합니다.")
                st.stop()
        else:
            st.info("ℹ️ SQL 검증이 비활성화되어 있습니다.")
        
        # SQL 실행
        filtered_df = sqldf(sql_query, {"df": df})
        
    except Exception as e:
        st.error(f"쿼리 실행 오류: {e}")
        st.stop()
    if filtered_df.empty:
        st.warning(":경고: 조건에 맞는 데이터가 없습니다. 다른 조건을 입력해보세요.")
        st.stop()
    # :작은_파란색_다이아몬드: 핵심: rerun 대비, 결과를 세션에 저장
    st.session_state.filtered_df = filtered_df
    # :시계_반대_방향_화살표: 검색할 때마다 이전 추첨 결과 초기화
    # st.session_state.winners = pd.DataFrame()
if not st.session_state.filtered_df.empty:
    st.subheader(":막대_차트: 조건이 적용된 데이터")
    st.write(f":흰색_확인_표시: 총 {len(st.session_state.filtered_df)}명이 조회되었습니다.")
    view_option = st.radio("데이터 표시 방식", ("상위 5개", "전체"), horizontal=True)
    st.dataframe(
        st.session_state.filtered_df.head()
        if view_option == "상위 5개"
        else st.session_state.filtered_df
    )
# 4) 추첨(항상 세션의 filtered_df 사용) → run=False여도 동작
df_for_draw = st.session_state.filtered_df
if not df_for_draw.empty:
    st.subheader(":다트: 추첨")
    num_winners = st.number_input(
        "당첨자 수를 입력하세요",
        min_value=1,
        max_value=len(df_for_draw),
        value=1,
        step=1,
        key="num_winners"
    )
    if st.button("추첨하기", key="btn_draw"):
        st.session_state.winners = df_for_draw.sample(
            n=num_winners,
            random_state=random.randint(0, 10000)
        )
    winners = st.session_state.winners
    if not winners.empty:
        st.subheader(":트로피: 당첨자 명단")
        st.dataframe(winners)
        
        # 할루시네이션 검증 버튼
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.write(f"총 {len(winners)}명의 당첨자가 추출되었습니다.")
        with col2:
            verify_hallucination = st.button("🔍 할루시네이션 검증", help="당첨자들이 조건에 부합하는지 검증합니다")
        with col3:
            csv = winners.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="📥 CSV 다운로드",
                data=csv,
                file_name="winners.csv",
                mime="text/csv",
                key="btn_download_winners"
            )
        
        # 할루시네이션 검증 실행
        if verify_hallucination:
            with st.spinner("할루시네이션 검증 중..."):
                # 원본 질의와 SQL 쿼리 가져오기 (세션에서)
                original_query = st.session_state.get('last_query', '')
                sql_query = st.session_state.get('last_sql', '')
                base_df = st.session_state.get('base_df', pd.DataFrame())
                
                if not original_query or not sql_query or base_df.empty:
                    st.warning("⚠️ 검증을 위해 필요한 정보가 없습니다. 다시 검색을 실행해주세요.")
                else:
                    # 할루시네이션 검증 수행
                    validation_result, status, detailed_result = validate_winners_hallucination(
                        winners, original_query, sql_query, base_df
                    )
                    
                    # 검증 결과 표시
                    st.subheader(":검증: 할루시네이션 검증 결과")
                    
                    if "success" in status:
                        st.success(validation_result)
                    else:
                        st.error(validation_result)
                    
                    # 상세 검증 결과
                    with st.expander("🔍 상세 검증 결과", expanded=True):
                        st.markdown("**검증 상세 내용:**")
                        st.text(detailed_result)
                        
                        # 통계 정보 표시
                        verification_info = get_detailed_verification(winners, original_query, sql_query)
                        st.markdown("**당첨자 통계 정보:**")
                        for key, value in verification_info.items():
                            if key in ["숫자형 컬럼 통계", "범주형 컬럼 고유값"]:
                                st.json(value)
                            else:
                                st.write(f"**{key}:** {value}")
                    
                    # 검증 실패 시 경고
                    if "error" in status and "부합하지 않습니다" in validation_result:
                        st.warning("⚠️ 일부 당첨자가 조건에 부합하지 않을 수 있습니다. 다시 추첨하거나 조건을 확인해주세요.")
                        
                        # 재추첨 버튼
                        if st.button("🎲 다시 추첨하기", type="secondary"):
                            st.session_state.winners = df_for_draw.sample(
                                n=num_winners,
                                random_state=random.randint(0, 10000)
                            )
                            st.rerun()
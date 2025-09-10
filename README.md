# 🎉 AI 기반 이벤트 당첨자 추출 시스템

자연어 질의를 SQL로 변환하여 정확한 당첨자를 추출하고, AI를 활용한 다중 검증 시스템으로 할루시네이션을 방지하는 Streamlit 애플리케이션입니다.

## ✨ 주요 기능

### 🤖 AI 기반 SQL 변환
- **Gemma2:9b** 모델을 사용한 자연어 → SQL 변환
- 한국어 질의를 정확한 SQLite 쿼리로 변환
- 컬럼 매핑을 통한 한글/영문 컬럼 지원

### 🔍 다중 검증 시스템
- **기본 문법 검증**: SQLite 파서를 사용한 즉시 검증
- **AI 문법 검증**: CodeLlama 7b 모델을 사용한 고급 문법 검증
- **논리 검증**: Llama 3.1 8b 모델을 사용한 논리적 정확성 검증
- **할루시네이션 검증**: 당첨자들이 실제 조건에 부합하는지 검증

### 📊 사용자 친화적 UI
- 직관적인 Streamlit 인터페이스
- 실시간 검증 결과 표시
- 상세한 검증 리포트
- CSV 다운로드 기능

## 🚀 설치 및 실행

### 1. 저장소 클론
```bash
git clone https://github.com/seonghunhan/nl-to-sql-raffle.git
cd w6
```

### 2. Python 환경 설정
```bash
# 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate  # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 3. Ollama 설치 및 모델 다운로드
```bash
# Ollama 설치 (https://ollama.ai/)
# Linux/Mac
curl -fsSL https://ollama.ai/install.sh | sh

# Windows: https://ollama.ai/download에서 다운로드

# 필요한 모델 다운로드
ollama pull gemma2:9b
ollama pull codellama:7b
ollama pull llama3.1:8b
```

### 4. 애플리케이션 실행
```bash
streamlit run app_lotto.py
```

## 📋 사용법

### 1. 데이터 업로드
- **이벤트 대상자 리스트**: Excel 파일 (.xlsx, .xls)
- **컬럼 매핑 파일** (선택): 영문 컬럼명과 한글명 매핑

### 2. 조건 입력
자연어로 이벤트 선정 조건을 입력합니다:
```
예시:
- "30대 여성 중 가입횟수가 3회 이상인 고객"
- "마케팅 동의했고 급여가 인정된 고객"
- "20대 남성 중 접속횟수가 10회 이상인 사용자"
```

### 3. SQL 검증 (선택사항)
- "SQL 검증 활성화" 체크박스로 검증 기능 제어
- 실시간으로 SQL의 정확성을 검증

### 4. 당첨자 추출
- 원하는 당첨자 수 입력
- "추첨하기" 버튼으로 랜덤 추첨
- "🔍 할루시네이션 검증"으로 최종 검증

## 🔧 기술 스택

### AI 모델
- **Gemma2:9b**: 자연어 → SQL 변환
- **CodeLlama:7b**: SQL 문법 검증
- **Llama 3.1:8b**: 논리 검증 및 할루시네이션 검증

### 프레임워크
- **Streamlit**: 웹 애플리케이션
- **Pandas**: 데이터 처리
- **PandasQL**: SQL 실행
- **Ollama**: AI 모델 실행

## 📁 프로젝트 구조

```
w6/
├── app_lotto.py          # 메인 애플리케이션
├── requirements.txt      # Python 의존성
├── README.md            # 프로젝트 문서
├── install_models.sh    # 모델 설치 스크립트
└── .gitignore          # Git 무시 파일
```

## ⚠️ 주의사항

1. **모델 크기**: 각 모델은 4-7GB 정도의 저장공간이 필요합니다
2. **메모리 요구사항**: 최소 16GB RAM 권장
3. **첫 실행**: 모델 다운로드로 인해 초기 실행 시간이 오래 걸릴 수 있습니다
4. **API 키**: OpenAI API 키가 필요한 경우 `test.py`에서 설정

## 🐛 문제 해결

### 모델이 로드되지 않는 경우
```bash
# Ollama 서비스 상태 확인
ollama list

# 모델 재다운로드
ollama pull gemma2:9b
```

### 메모리 부족 오류
- 더 작은 모델 사용 고려 (예: gemma2:2b)
- 배치 크기 조정

### SQL 실행 오류
- 컬럼명 확인
- 데이터 타입 확인
- 매핑 파일 재검토

## 📄 라이선스

MIT License

## 🤝 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request


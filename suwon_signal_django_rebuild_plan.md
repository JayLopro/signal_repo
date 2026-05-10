# 수원시 시그널 리포트 테스트 배포 계획

## 1. 추진 목적

기존 `signal_report_v3` 구조를 기반으로, **Django + Tailwind + SQLite3 + Chart.js** 조합의 경량 웹 대시보드로 리빌딩한다.

우선 **수원시(4111)** 데이터만 사용하여 개선판 테스트 배포 버전을 만들고, 이후 다른 시군 확장 가능성을 검토한다.

---

## 2. 목표 서비스 형태

### 배포 환경

- PythonAnywhere 기반 웹 배포
- Django 웹 애플리케이션
- SQLite3 기반 테스트 DB
- Tailwind CSS 기반 UI
- Chart.js 기반 대시보드 차트
- `.env` 기반 API Key 및 환경변수 관리

PythonAnywhere 테스트 배포 환경에서는 Django 프로젝트를 올린 뒤, 정적 파일 경로 설정, `collectstatic` 실행, WSGI 설정, 환경변수 관리가 필요하다.

---

## 3. 기술 스택

| 구분 | 사용 기술 | 용도 |
|---|---|---|
| Backend | Django | 웹서비스, URL 라우팅, View, Template, API 응답 |
| Frontend | Tailwind CSS | 대시보드 UI 스타일 |
| UI Template | TailAdmin Free Tailwind Dashboard | 관리자/대시보드 화면 기본 틀 |
| Database | SQLite3 | 테스트 배포용 경량 DB |
| Chart | Chart.js | 시계열, 막대, 도넛, 비교 차트 |
| Deploy | PythonAnywhere | 외부 테스트 배포 |
| Version Control | GitHub `JayLopro/signal_repo` | 코드 형상관리 |
| External API | 한국은행 ECOS API | 한국 100대 지표 연동 |
| Secret 관리 | `.env` | Django Secret Key, API Key, 환경 구분 |

### 참고 저장소 및 문서

- 코드 형상관리 저장소: <https://github.com/JayLopro/signal_repo>
- Django: <https://github.com/django/django>
- Tailwind CSS: <https://github.com/tailwindlabs/tailwindcss>
- TailAdmin Free Dashboard Template: <https://github.com/TailAdmin/tailadmin-free-tailwind-dashboard-template>
- Chart.js: <https://github.com/chartjs/Chart.js>
- 한국은행 ECOS API: <https://ecos.bok.or.kr/api/>
- 한국은행 100대 지표 API 개발명세서: `API개발명세서_100대.xls`

---

## 4. 기존 구조에서 가져올 요소

기존 경로:

```text
/mnt/c/Users/open/RnD_PowerBi/경기도/signal_report_v3
```

기존 `signal_report_v3`에서는 다음 요소를 Django 프로젝트로 재구성한다.

### 4-1. 시그널 산정 로직

- 단기 추세
- 중기/장기 추세
- 전월 대비
- 전년동월 대비
- 긍정/부정 방향성
- 강한 긍정 / 약한 긍정 / 변화 없음 / 약한 부정 / 강한 부정 등급

### 4-2. 지표 카테고리

기존 지표 체계는 다음 6개 카테고리를 유지하는 방향이 적절하다.

- 통신(유동생활)
- 통신(생활이동)
- 카드(가맹점)
- 카드(소비자)
- 기업신용
- 개인신용

### 4-3. 보고서/대시보드 디자인 요소

기존 HTML 리포트 및 Streamlit 대시보드에서 다음 요소를 일부 재활용한다.

- 시그널 등급 색상
- 카테고리별 섹션 구성
- KPI 카드형 요약 구조
- 지표별 테이블 구조
- LLM 인사이트 출력 형식
- 차트 제목 및 범례 구성 방식

---

## 5. 신규 Django 프로젝트 구조 제안

```text
signal_repo/
├─ manage.py
├─ config/
│  ├─ settings.py
│  ├─ urls.py
│  └─ wsgi.py
├─ dashboard/
│  ├─ views.py
│  ├─ urls.py
│  ├─ models.py
│  ├─ services/
│  │  ├─ signal_service.py
│  │  ├─ chart_service.py
│  │  ├─ insight_service.py
│  │  └─ bok_api_service.py
│  ├─ templates/
│  │  └─ dashboard/
│  │     ├─ base.html
│  │     ├─ index.html
│  │     ├─ signal_detail.html
│  │     └─ components/
│  └─ static/
│     ├─ css/
│     ├─ js/
│     └─ img/
├─ data/
│  ├─ suwon_4111.sqlite3
│  └─ sample/
├─ scripts/
│  ├─ import_suwon_data.py
│  ├─ fetch_bok_100.py
│  └─ build_initial_db.py
├─ .env
├─ .gitignore
├─ requirements.txt
└─ README.md
```

---

## 6. 주요 기능 구성

## 6-1. 메인 대시보드

수원시 전체 흐름을 한 화면에서 확인하는 화면을 구성한다.

구성 예시:

- 기준월 선택
- 전체 시그널 요약
- 긍정/부정 시그널 개수
- 카테고리별 시그널 분포
- 주요 변화 지표 Top N
- 단기 추세 / 전년동월 / 전월대비 비교
- LLM 종합 인사이트

---

## 6-2. 카테고리별 상세 화면

각 카테고리별로 지표 흐름과 인사이트를 제공한다.

대상 카테고리:

- 유동생활인구
- 생활이동
- 가맹점
- 소비자
- 기업신용
- 개인신용

각 화면 구성:

- KPI 카드
- 시계열 차트
- 지표별 신호 등급
- 당월 값 / 변화율 / 추세 대비 차이
- LLM 인사이트
- 참고용 정책 시사점

---

## 6-3. Chart.js 차트 구성

Django View에서 JSON 데이터를 내려주고, 템플릿에서 Chart.js로 렌더링하는 방식을 사용한다.

추천 차트:

| 차트 | 용도 |
|---|---|
| Line Chart | 월별 시계열 추세 |
| Bar Chart | 지표별 변화율 비교 |
| Horizontal Bar | Top N 긍정/부정 지표 |
| Doughnut Chart | 시그널 등급 분포 |
| Mixed Chart | 당월 값 + 변화율 병행 표시 |

대시보드에서는 **이미지 차트보다 Chart.js 인터랙티브 차트**가 적합하다.

단, PDF 보고서가 필요할 경우에는 기존 HTML/PDF 렌더링 구조를 별도로 유지하는 것이 좋다.

---

## 6-4. LLM 인사이트 구성

기존 프롬프트 구조는 유지하되, Django에서는 다음 흐름으로 역할을 분리한다.

```text
원천 데이터
→ 시그널 산정
→ 지표별 요약 데이터 생성
→ LLM 프롬프트 생성
→ 인사이트 저장
→ 대시보드에서 조회
```

주의할 점은 **사용자가 화면을 열 때마다 LLM API를 호출하지 않는 것**이다.

권장 방식:

- 개발/관리자 실행 시 인사이트 사전 생성
- 생성 결과를 SQLite3에 저장
- 대시보드에서는 저장된 인사이트만 조회
- 재생성 버튼은 관리자용으로만 제공

---

## 7. 한국은행 ECOS API 연동

한국은행 ECOS API를 활용하여 한국 100대 지표 데이터를 수집하고, 수원시 시그널 리포트의 보조 지표로 활용한다.

### 사용 목적

- 한국 100대 지표 데이터 수집
- 수원시 시그널과 거시경제 흐름 비교
- 대시보드 보조지표 영역 구성
- LLM 인사이트 생성 시 참고 데이터로 활용

### 구성 방식

```text
.env
→ BOK_API_KEY 로드
→ ECOS API 호출
→ 100대 지표 데이터 수집
→ SQLite3 저장
→ 대시보드/인사이트에서 활용
```

### `.env` 예시

```env
DJANGO_SECRET_KEY=your-django-secret-key
DJANGO_DEBUG=True
ALLOWED_HOSTS=yourname.pythonanywhere.com

BOK_API_KEY=your-bok-api-key
OPENAI_API_KEY=your-openai-api-key
GOOGLE_API_KEY=your-google-api-key
```

### 한국은행 API 서비스 예시

```text
dashboard/services/bok_api_service.py
```

역할:

- 한국은행 API Key 로드
- 100대 통계지표 호출
- 응답 JSON/XML 파싱
- 지표명, 값, 단위, 주기, 기준시점 저장
- 호출 실패 시 로그 저장

---

## 8. GitHub 형상관리 및 파이프라인

대상 저장소:

```text
https://github.com/JayLopro/signal_repo
```

권장 브랜치 전략:

```text
main
└─ develop
   └─ feat/django-rebuild
   └─ feat/suwon-dashboard
   └─ feat/bok-api
   └─ feat/pythonanywhere-deploy
```

### 초기 커밋 단위

| 커밋 | 내용 |
|---|---|
| 1 | Django 프로젝트 초기화 |
| 2 | Tailwind/TailAdmin 템플릿 적용 |
| 3 | SQLite3 모델 및 수원시 샘플 데이터 적재 |
| 4 | 시그널 산정 로직 이식 |
| 5 | Chart.js 대시보드 구현 |
| 6 | LLM 인사이트 생성/저장 구조 구현 |
| 7 | 한국은행 ECOS API 연동 |
| 8 | PythonAnywhere 배포 설정 |
| 9 | README 및 운영 문서 정리 |

### 파이프라인 방향

초기에는 GitHub Actions 자동배포보다는 수동 배포 절차를 명확히 정리하는 것이 좋다.

```bash
git pull origin main
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic
```

이후 안정화되면 GitHub Actions 또는 PythonAnywhere API 기반 자동배포를 검토한다.

---

## 9. PythonAnywhere 배포 체크리스트

### 필수 항목

- `requirements.txt` 작성
- `.env`는 GitHub에 올리지 않기
- `ALLOWED_HOSTS`에 PythonAnywhere 도메인 추가
- `DEBUG=False` 전환 기준 마련
- `STATIC_ROOT` 설정
- `collectstatic` 실행
- Web 탭에서 WSGI 경로 설정
- SQLite3 파일 경로 확인
- API Key 환경변수 설정

### 주의 사항

- SQLite3는 테스트 배포에는 적합하지만 다중 사용자/동시 쓰기에는 한계가 있음
- LLM API 호출은 실시간 호출보다 사전 생성 방식 권장
- 원천 데이터 전체를 올리지 말고 수원시 테스트용 파생 데이터만 업로드
- `.env`, 원천 데이터, API Key, 개인정보성 파일은 `.gitignore`에 포함

---

## 10. 개발 단계 계획

| 단계 | 내용 | 산출물 |
|---|---|---|
| 1단계 | 기존 `signal_report_v3` 구조 분석 | 이식 대상 목록 |
| 2단계 | Django 프로젝트 초기화 | 기본 웹앱 |
| 3단계 | TailAdmin/Tailwind 적용 | 대시보드 레이아웃 |
| 4단계 | 수원시 SQLite3 데이터 구성 | `suwon_4111.sqlite3` |
| 5단계 | 시그널 산정 로직 이식 | `signal_service.py` |
| 6단계 | Chart.js 차트 구현 | 대시보드 차트 |
| 7단계 | LLM 인사이트 저장 구조 구현 | 인사이트 테이블 |
| 8단계 | 한국은행 ECOS API 연동 | 100대 지표 수집 기능 |
| 9단계 | PythonAnywhere 배포 | 테스트 URL |
| 10단계 | 검토 및 개선 | 개선판 배포 버전 |

---

## 11. 우선순위

### 1순위: 테스트 배포 가능 상태

- Django 앱 실행
- 수원시 데이터 조회
- 기본 대시보드 표시
- Chart.js 차트 표시
- PythonAnywhere 배포

### 2순위: 시그널 리포트화

- 시그널 등급 표시
- 카테고리별 분석
- 기존 신호 산정 방식 이식
- 종합 요약 화면 구성

### 3순위: 인사이트 고도화

- LLM 인사이트 생성
- 인사이트 저장
- 한국은행 100대 지표 결합
- 거시경제 참고 문구 반영

### 4순위: 운영 구조

- GitHub 브랜치 관리
- 배포 문서화
- 데이터 갱신 스크립트
- 관리자용 재생성 기능

---

## 12. 산출물

최종적으로 다음 산출물을 목표로 한다.

- Django 기반 수원시 시그널 대시보드
- 수원시 테스트용 SQLite3 DB
- Chart.js 기반 시각화 화면
- LLM 인사이트 저장 및 조회 구조
- 한국은행 ECOS 100대 지표 연동 스크립트
- PythonAnywhere 테스트 배포 URL
- GitHub 저장소 기반 코드 형상관리 체계
- 배포 및 운영 README

---

## 13. 한 줄 정리

**기존 `signal_report_v3`의 시그널 산정·인사이트·보고서 구조를 Django 웹서비스로 재구성하고, 수원시(4111)만 대상으로 PythonAnywhere에 먼저 배포하여 대시보드, Chart.js 시각화, LLM 인사이트, 한국은행 100대 지표 연동 가능성을 검증하는 테스트 프로젝트로 추진한다.**

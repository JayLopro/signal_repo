# Step 1 — PythonAnywhere 배포 가이드

본 문서는 **Step 1 산출물(빈 Django + TailAdmin shell)**을 PythonAnywhere에 올려 `https://<USERNAME>.pythonanywhere.com` 접속 시 **HTTP 200 OK + 사이드바 화면**이 뜨는 것까지 검증하는 절차입니다.

데이터·차트·LLM·BOK API는 Step 2 이후에서 다룹니다.

---

## 0. 사전 조건

- [x] PythonAnywhere 계정 (이미 보유)
- [x] GitHub `JayLopro/signal_repo` (이미 존재, Step 1 코드 push 완료 상태여야 함)
- [ ] 로컬에서 `git push -u origin main` 1회 실행하여 Step 1 코드 GitHub에 반영
- [ ] PA 무료 플랜 기준 가능 (Tailwind CDN 외 외부 연결 없음)

> 이하 명령어에서 `<USERNAME>`은 본인의 PythonAnywhere 사용자명으로 치환하세요. (예: `jaylopro`)

---

## 1. PythonAnywhere Bash 콘솔에서 코드 가져오기

PA 좌측 메뉴 → **Consoles** → **Bash** 새 콘솔 시작.

```bash
cd ~
# repo가 처음이면:
git clone https://github.com/JayLopro/signal_repo.git
cd signal_repo

# 이미 clone된 상태라면 최신 반영:
# cd ~/signal_repo && git pull origin main
```

---

## 2. 가상환경 생성 + 의존성 설치

PA에서는 Python 3.11 기준으로 진행 (3.1x도 가능).

```bash
# Python 3.11 기준
python3.11 -m venv ~/.virtualenvs/signal_repo
source ~/.virtualenvs/signal_repo/bin/activate

cd ~/signal_repo
pip install --upgrade pip
pip install -r requirements.txt
```

설치 후 확인:
```bash
python -c "import django; print('Django', django.get_version())"
# → Django 4.2.x
```

---

## 3. `.env` 작성 (PA 서버 안에만)

`.env`는 GitHub에 올라가지 않으므로 **PA 서버 안에서 직접 만듭니다**.

```bash
cd ~/signal_repo
nano .env
```

다음 내용 붙여넣기 (값은 본인 것으로 교체):

```env
DJANGO_SECRET_KEY=<아래 명령으로 생성한 50자 랜덤 문자열>
DJANGO_DEBUG=False
ALLOWED_HOSTS=<USERNAME>.pythonanywhere.com,localhost,127.0.0.1

GOOGLE_API_KEY=
BOK_API_KEY=
OPENAI_API_KEY=
```

`SECRET_KEY` 생성용 한 줄 명령:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

> Step 1에서는 API 키들이 비어있어도 됩니다. Step 2+에서 채워 넣으세요.

---

## 4. DB 초기화 + 정적 파일 수집

```bash
cd ~/signal_repo
source ~/.virtualenvs/signal_repo/bin/activate

python manage.py migrate
python manage.py collectstatic --noinput
```

`migrate` 후 `db.sqlite3`가 생성되고, `collectstatic` 후 `staticfiles/` 폴더에 정적 자산이 쌓입니다.

---

## 5. Web 탭에서 웹앱 구성

PA 좌측 메뉴 → **Web** → **Add a new web app** → 안내에 따라 **Manual configuration** + **Python 3.10** 선택.

만들어진 웹앱 설정 페이지에서 다음 항목 수정:

### 5-1. Source code
```
/home/jaylo/signal_repo
```

### 5-2. Working directory
```
/home/jaylo/signal_repo
```

### 5-3. Virtualenv
```
/home/jaylo/.virtualenvs/signal_repo
```

### 5-4. WSGI configuration file

링크 클릭 → 기본 내용 전체 삭제 후 아래로 교체:

```python
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path("/home/jaylo/signal_repo")

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

load_dotenv(PROJECT_DIR / ".env")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

> `<USERNAME>` 두 군데 모두 본인 PA username으로 교체.

### 5-5. Static files

Static files 섹션에서 두 줄 추가:

| URL | Directory |
|---|---|
| `/static/` | `/home/jaylo/signal_repo/staticfiles` |

> Tailwind는 CDN을 쓰므로 `/static/` 매핑이 비어있어도 200은 뜹니다. 그래도 향후를 위해 미리 잡아두는 게 좋습니다.

---

## 6. Reload + 검증

웹앱 페이지 상단의 **Reload** 버튼 클릭.

브라우저에서 접속:
```
https://jaylo.pythonanywhere.com
```

**예상 결과:**
- HTTP 200 OK
- 좌측 사이드바: 대시보드 + 6개 카테고리 (Coming Soon 배지)
- 헤더: "수원시 시그널 리포트" + 개선판 테스트 / v0.1.0 칩
- 본문: 파란 안내 박스 + 6개 카테고리 카드 + 로드맵 미리보기

**Step 1 완료 기준 (deep-interview 스펙):**
> ✅ URL 접속 시 200 OK 응답 + TailAdmin 레이아웃 표시

---

## 7. 자주 발생하는 문제

### 500 에러
- **Web 탭 → Error log** 확인.
- 흔한 원인:
  - `ALLOWED_HOSTS`에 `<USERNAME>.pythonanywhere.com` 누락 → `.env` 수정 후 Reload
  - WSGI 파일 `<USERNAME>` 미치환
  - `python-dotenv` 설치 안 됨 → 가상환경 활성화 후 `pip install -r requirements.txt`

### 정적 파일이 깨져 보이는 경우
- Tailwind는 CDN이라 보통 문제 없음
- 만약 본인 정적 파일을 추가한 뒤 안 보이면 Web 탭의 Static files 매핑 + `collectstatic` 재실행

### Django가 못 찾아짐
- Virtualenv 경로 확인: `/home/<USERNAME>/.virtualenvs/signal_repo`
- WSGI 파일에서 `PROJECT_DIR` 경로 오타 확인

### git pull 시 충돌
- PA 서버에서 임시 변경된 게 있으면 `git stash` → `git pull` → `git stash pop`
- 또는 안전하게 `git fetch origin && git reset --hard origin/main` (PA 서버 상의 미커밋 변경은 사라짐)

---

## 8. Step 2 이후 업데이트 절차

1단계가 검증되면, 이후 변경사항 반영은 다음 5줄만:

```bash
cd ~/signal_repo
source ~/.virtualenvs/signal_repo/bin/activate
git pull origin main
pip install -r requirements.txt   # requirements 변경 시만 의미 있음
python manage.py migrate          # 마이그레이션 추가 시만 의미 있음
python manage.py collectstatic --noinput
```

그리고 Web 탭 **Reload**.

---

## 부록: 로컬에서 push만 다시 하고 싶을 때

```bash
cd C:\Users\open\RnD_PowerBi\signal_repo_test   # 또는 WSL 경로
git status                                       # 무엇이 바뀌었는지 확인
git add <파일>
git commit -m "<메시지>"
git push origin main
```

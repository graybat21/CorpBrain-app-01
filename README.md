# CorpBrain

> **이 저장소에는 나란한 두 트랙이 있습니다.**
>
> | 트랙 | 브랜치 | GUI 구현 |
> |---|---|---|
> | 기본 | `main` | SSE 기반 (`gui/api·httpd·sse·scan`) |
> | 폴링 | `track/gui-polling` | 1초 폴링 + 자식 프로세스 (`gui/server·scanjob·runner`) |
>
> 두 트랙은 **`v0.8.0`에서 갈라져 나온 서로 다른 v0.9 GUI 구현**이며, 어느 쪽도 상대의
> 커밋을 담고 있지 않습니다. 버전 번호도 갈라 붙입니다 — `main` 은 `0.9.1`,
> 이 트랙은 `0.9.2+polling` 처럼 뒤에 트랙 이름을 답니다.
>
> **그대로 병합하지 마세요.** `corpbrain/gui/` 의 모듈 구성이 서로 다르고 코어 8개 파일을
> 각자 고쳤습니다. 합치려면 둘 중 어느 GUI 를 남길지부터 정해야 합니다.


> **100% 로컬 구동형 AI 지식 관리 솔루션** — 로컬 문서 자동 스캔, 요약 및 마크다운 위키 생성 (MVP)

CorpBrain은 흩어져 있는 로컬 문서(`.txt`, `.md`, `.docx`, `.pdf`, `.xlsx`, `.xlsm`, `.pptx`)를 재귀적으로 탐색하고, 로컬 LLM(Ollama)을 활용하여 핵심 요약 및 태그가 포함된 마크다운 위키 페이지로 자동 구조화하는 도구입니다.

외부 네트워크 통신은 로컬 Ollama 호출 외에 일체 발생하지 않으므로, 기밀 문서 및 개인정보 유출 걱정 없이 안전하게 지식 베이스를 구축할 수 있습니다.

---

## 💡 주요 특징 (Key Features)

- **🔒 100% 로컬 프라이버시 보장**: 외부 클라우드 통신이나 텔레메트리 없이 오직 로컬 Ollama만 활용.
- **📁 로컬 문서 재귀 스캔**: 지정한 폴더 내의 `.docx`, `.txt`, `.md`, `.pdf`, `.xlsx`, `.xlsm`, `.pptx` 문서를 스캔하고 하위 디렉터리 구조를 그대로 미러링하여 생성.
- **🤖 자동 요약 & 키워드 추출**: 문서별로 한 줄 요약, 핵심 포인트, 상세 요약, 태그/키워드를 일관된 마크다운 템플릿으로 출력.
- **⚡ 효율적인 증분 재처리 (Incremental Processing)**: 원본 문서의 수정 시간(`mtime`)을 비교하여 변경된 파일만 선택적으로 재생성 (`--force`로 강제 재생성 가능).
- **🛡️ 안전한 예외 처리**: 빈 문서, 권한 거부, 긴 경로, 미지원 포맷 등 엣지 케이스 시 스킵 및 상세 리포트 제공.
- **🖥️ 로컬 웹 GUI**: `corpbrain gui` 로 브라우저 화면에서 스캔·검색·탐색. `127.0.0.1` 전용이며 외부 CDN을 쓰지 않는다.
- **🧩 모듈식 코어 아키텍처**: 비즈니스 로직(Core)과 어댑터(CLI·GUI)가 완벽히 분리되어 있다.

> ⚠️ 이 README는 개요만 담는다. **명령·옵션의 정본은 [`docs/USAGE.md`](docs/USAGE.md)** 이며,
> `scan` 외에 `plan`·`search`·`graph`·`doctor`·`consent`·`gui` 여섯 명령이 더 있다.
> v0.3의 GPU 게이팅과 v0.4의 임베딩 모델 필수화 같은 파괴적 변경도 그 문서에 적혀 있다.

---

## 🛠️ 요구사항 (Requirements)

- **Python**: `>= 3.12, < 3.13`
- **Package Manager**: [uv](https://github.com/astral-sh/uv) (권장) 또는 `pip`
- **Ollama**: 로컬 LLM 구동용 ([Ollama 공식 사이트](https://ollama.com/)에서 설치)
  - 추천 모델: `qwen2.5:7b-instruct`

---

## 🚀 빠른 시작 (Quick Start)

### 1. 저장소 클론 및 개발 환경 구성

```bash
# 가상환경 생성 및 의존성 동기화 (uv 사용 시)
uv sync
```

### 2. Ollama 구동 및 모델 준비

CorpBrain 실행 전, 로컬 Ollama 서비스가 구동 중이어야 하며 대상 모델이 다운로드되어 있어야 합니다.

```bash
# Ollama 모델 다운로드 및 실행
ollama run qwen2.5:7b-instruct
```

### 3. CorpBrain CLI 실행

```bash
# 패키지 인스톨 (선택 사항)
uv pip install -e .

# 스캔 명령어 실행
uv run corpbrain scan ./docs_folder --out ./corpbrain_wiki

# 또는 브라우저 화면으로 (v0.9)
uv run corpbrain gui
```

---

## 📖 CLI 명령어 및 옵션 (Usage)

### `corpbrain scan`

지정한 디렉터리를 스캔하여 마크다운 위키를 생성합니다.

```bash
corpbrain scan <FOLDER> [OPTIONS]
```

#### 주요 옵션 목록

| 옵션 | 기본값 | 설명 |
| :--- | :--- | :--- |
| `--out DIR` | `./corpbrain_wiki` | 생성된 마크다운 위키가 저장될 출력 디렉터리 경로 |
| `--model NAME` | `qwen2.5:7b-instruct` | 사용할 Ollama 모델명 (환경변수 `CORPBRAIN_MODEL`로 지정 가능) |
| `--max N` | `50` | 최대 스캔 파일 수 상한 (상한 초과 시 안전하게 중단) |
| `--max-chars N` | `12000` | 파일당 LLM 요약 입력에 사용할 최대 글자 수 |
| `--ollama-url URL` | `http://127.0.0.1:11434` | 로컬 Ollama API endpoint 주소 |
| `--force` | `false` | 원본 파일 수정 시간과 무관하게 강제 재생성 |

#### 사용 예시

```bash
# 기본 옵션으로 문단 스캔
corpbrain scan ~/Documents/Projects --out ./my_wiki

# 특정 모델 지정 및 강제 재생성
corpbrain scan ~/Documents/Reports --model qwen2.5:7b-instruct --force
```

---

## 📄 위키 마크다운 출력 템플릿

생성되는 모든 마크다운 문서(`<원본이름.확장자>.md`)는 아래와 같이 일관된 포맷을 가집니다.

```markdown
---
source_path: "/absolute/path/to/report.docx"
generated_at: "2026-08-12T09:30:00+09:00"
model: "qwen2.5:7b-instruct"
source_bytes: 15420
---

# 문서 제목

## 한 줄 요약
문서 전체 내용을 요약한 한 문장입니다.

## 핵심 포인트
- 주요 시사점 및 핵심 내용 1
- 주요 시사점 및 핵심 내용 2
- 주요 시사점 및 핵심 내용 3

## 요약
문서의 세부 내용을 다룬 종합적인 요약 문단입니다.

## 태그·키워드
`#태그1` `#태그2` `#태그3`

## 원문
[원본 파일 열기](file:///absolute/path/to/report.docx)
```

---

## 🧪 테스트 및 품질 검증 (Development & Testing)

CorpBrain은 높은 품질과 단위/통합/네트워크 격리 테스트를 포함하고 있습니다.

```bash
# 전체 테스트 실행 (1,000+ 개 테스트 스위트)
uv run pytest

# 코드 스타일 검사 (Ruff)
uv run ruff check .
```

---

## 📂 프로젝트 구조 (Project Structure)

```text
CorpBrain-app-01/
├── corpbrain/
│   ├── cli.py             # CLI 어댑터 (얇은 진입점)
│   ├── gui/               # 로컬 웹 GUI 어댑터 (서버·러너·정적 자산)
│   └── core/              # 핵심 비즈니스 로직 (재사용 가능한 코어 라이브러리)
│       ├── scanner.py     # 파일 탐색 및 스킵 조건 검사
│       ├── extract.py     # .txt/.md/.docx/.pdf/.xlsx/.xlsm/.pptx 텍스트 추출기
│       ├── gateway.py     # Ollama 통신 단일 관문 (네트워크 격리)
│       ├── pipeline.py    # 스캔-추출-요약-렌더링 파이프라인
│       ├── render.py      # 위키 마크다운 템플릿 렌더러
│       └── report.py      # 스킵 사유 및 실행 요약 보고서
├── static/docs/specs/     # 제품 요구사항 및 스펙 문서 정본
├── tests/                 # 단위 / 통합 / 네트워크 검증 테스트
├── pyproject.toml         # 프로젝트 구성 및 의존성 명세 (PEP 621, PEP 735)
└── README.md
```

---

## 📜 라이선스 (License)

Copyright © 2026 CorpBrain Team. All rights reserved.

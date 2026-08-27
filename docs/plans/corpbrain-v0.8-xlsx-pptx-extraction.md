# 실행 플랜 — v0.8 `.xlsx`/`.xlsm`/`.pptx` 텍스트 추출 (issue #44)

- 스펙: `static/docs/specs/features/corpbrain-v0.8-xlsx-pptx-extraction.md` (확정)
- 결정 원장: `docs/grill/GRILL_LEDGER-v0.8-xlsx-pptx-extraction.md` (7건 · ALL_RESOLVED)
- 최종 갱신: 2026-08-27

## 착수 전제

브랜치 `feat/v0.8-xlsx-pptx-extraction`은 이미 있고 스펙·원장 커밋 2개가 올라가 있다. 코드는
아직 한 줄도 없다. 착수 시점에 확인할 것이 셋 있으며, **셋 다 U1 안에서 끝난다.**

1. **의존성 설치에 네트워크가 필요하다.** `openpyxl`·`python-pptx`는 `uv.lock`에도 uv 캐시에도
   없어 오프라인 설치가 불가능하다. 여기서 막히면 U1부터 진행이 안 되므로 가장 먼저 확인한다.
2. **T3 — `read_only=True`에서 행 숨김을 판별할 수 있는가.** 결과에 따라 스펙 §4.2의 조건부 표가
   어느 행으로 확정되는지 갈리고, §3 항목2의 단언 범위가 정해진다.
3. **비목표 근거 검증 — `python-pptx`가 `.pptm`을 실제로 거부하는가.** 스펙 §2가 「거부할 가능성이
   크다」로 적어 둔 추정이다. 거부하지 않는다면 비목표 근거가 약해지므로 그 사실을 §2에 기록한다
   (범위를 넓히지는 않는다 — 범위는 사용자 결정이다).

확인 결과는 **스펙에 되적는다.** 추정으로 적힌 문장이 실측 문장으로 바뀌는 것이 U1의 산출물 중
하나다.

## 브랜치·PR 전략

**단일 PR `feat/v0.8-xlsx-pptx-extraction`. 병렬 개발 없음.**

```
feat/v0.8-xlsx-pptx-extraction
    [스펙 · grill 원장 — 머지됨]
    U1 … U7  →  ready PR  →  머지  →  v0.8.0 tag
```

근거:

- **쪼갤 자리가 없다.** 구현 표면이 `extract.py` 한 파일에 몰려 있고, 신규 저장 계층·파이프라인
  변경·위키 산출물 변경이 전부 없다. 추출기만 먼저 머지하면 `main`에 **`SUPPORTED_EXTENSIONS`에
  없어 아무도 호출하지 않는 추출 함수**가 남는다 — v0.7이 3-PR을 거부한 것과 같은 근거다.
- **대기 구간이 없다.** v0.7은 α 실측 때문에 사용자 실행을 기다려야 했지만, 이번 슬라이스는 수동
  스모크를 요구하지 않고(스펙 §3) 실측은 #48로 분리했다. draft PR 단계를 둘 이유가 없다.
- **병렬 서브에이전트도 쓰지 않는다.** U4(엑셀)와 U5(PPTX)는 서로 독립적으로 보이지만 `extract.py`
  ·`config.py`·`plan.py` **세 파일을 똑같이 통과**한다. 떼어 놓으면 매 단위가 충돌 해소로 끝난다.

## 작업 단위 (7개)

| # | 이름 | 내용 | 의존 |
|---|---|---|---|
| U1 | 의존성·전제 확인 | `pyproject.toml`·`uv.lock`에 `openpyxl`·`python-pptx` 추가 · 착수 전제 3건 확인 후 스펙 §4.2·§2에 결과 기록 | — |
| U2 | 디스패치 매핑 전환 | `extract.py` if-체인 → `dict[str, Callable]` (기존 4종만, 순수 리팩터링) · **「매핑 키 집합 == `SUPPORTED_EXTENSIONS`」 단위테스트 추가** | U1 |
| U3 | OLE 시그니처 판정 | 열기 실패 시 앞 8바이트로 「암호화되었거나 구형 이진 포맷」을 가르는 공통 헬퍼 + 단위테스트 (스펙 §4.3.1) | U2 |
| U4 | 엑셀 추출기 | `_extract_xlsx()` — 경계 줄·셀 문자열화 4규칙·숨김 처리·`max_chars` 중단 · 매핑 등록 · `SUPPORTED_EXTENSIONS`에 `.xlsx`/`.xlsm` · `plan.py` 두 dict · 기존 리터럴 단언 갱신 · 단위테스트 | U3 |
| U5 | PPTX 추출기 | `_extract_pptx()` — 경계 줄·도형 순서·표 셀·그룹 재귀·`has_notes_slide` 가드 · 매핑 등록 · `SUPPORTED_EXTENSIONS`에 `.pptx` · `plan.py` 두 dict · 단위테스트 | U4 |
| U6 | 통합·보안 테스트 | 인라인 코퍼스 통합테스트(DoD 1·3·5·9) · `tests/security/test_network_invariant.py` 케이스 추가(DoD 10) | U5 |
| U7 | 문서 | `docs/USAGE.md`(4지점) · `docs/ROADMAP.md`(§2.1 매핑 정정 · v0.7 행 이월) · `extract.py` docstring · **stale 부채**(`README.md` 3지점 · `scanner.py` 2지점) | U6 |

### 왜 `SUPPORTED_EXTENSIONS` 추가를 U1이 아니라 U4·U5로 미루는가

v0.2가 `.pdf`에서 쓴 「공유 파일 선행 + 본체」 분리를 **이번에는 따르지 않는다.** U2에서 매핑
정합성 단언(「매핑 키 집합 == `SUPPORTED_EXTENSIONS`」)을 세우기 때문이다 — 상수를 먼저 늘리면
추출기가 없는 확장자가 키에 없어 그 단언이 **U2부터 U5까지 계속 빨간불**이 된다. 상수와 추출기를
같은 커밋에 넣으면 세 상태(4종 → 6종 → 7종)가 각각 green이고, 「모든 커밋이 green」 규율이
자동으로 지켜진다.

### 공유 헬퍼를 두는 자리

OLE 시그니처 판정(U3)은 `extract.py` 안에 둔다. 두 추출기가 공유하지만 **파일을 읽는 함수**라
`graph.py` 같은 순수 계산 모듈로 뺄 성질이 아니고, 실패 경로에서만 불린다.

### 실행 웨이브

```
W1  U1                      ← 여기서 막히면(네트워크) 전체가 멈춘다
W2  U2 → U3
W3  U4 → U5                 ← 같은 세 파일을 통과하므로 반드시 순차
W4  U6
W5  U7  →  ready PR  →  머지  →  v0.8.0 tag
```

포맷별 수직 슬라이스(엑셀 end-to-end 후 PPTX end-to-end)를 쓰지 않는 이유는 U2·U3가 두 포맷의
공통 기반이기 때문이다. 먼저 세워 두면 U4·U5가 각자 자기 규칙만 담는다.

## 커밋 규율

- **모든 커밋이 green이다.** 각 단위 커밋은 자기 단위테스트를 함께 담는다.
- 커밋 프리픽스: `v0.8(deps):` U1 / `v0.8(core):` U2~U5 / `v0.8(test):` U6 / `v0.8(docs):` U7.
- 단위마다 TDD 사이클(Red → Green → Refactor)을 돈다.

## 머지 조건

스펙 §3 완료의 정의 12항목 전부. 특히 아래 셋은 이 슬라이스 고유라 눈으로 확인한다.

- 항목3 — 수식 캐시 없는 `.xlsx`가 `empty_document`로 스킵된다(T1 결정이 실제로 작동하는지).
- 항목5 — OLE 시그니처 파일과 손상 파일이 **서로 다른 detail**을 받는다.
- 항목7 — 매핑 키 집합과 `SUPPORTED_EXTENSIONS`가 7종으로 일치한다.

## 이 슬라이스가 남기는 것

- **#48** — `CHARS_PER_BYTE` 실측(실물 코퍼스 필요). 잠정값 3개가 `main`에 들어간 채 릴리스되는
  것은 스펙 §4.5가 근거와 함께 허용한 예외다.
- T3 확인 결과에 따라 「숨긴 행 제외」가 빠질 수 있다. 빠지면 스펙 §4.2에 그 사실이 남는다.

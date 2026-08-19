# CorpBrain 사용 설명서

흩어진 로컬 문서를 **100% 로컬 환경**에서 자동 구조화된 마크다운 위키로 바꾸는 CLI 도구다.
외부로 나가는 통신은 로컬 Ollama 호출 하나뿐이며, 그 외 네트워크·텔레메트리는 없다.

이 문서는 현재 버전(**v0.4.0**) 기준이며, 각 기능이 처음 등장한 버전을
`[v0.1]` / `[v0.2]` / `[v0.3]` / `[v0.4]`로 표시한다.

> ⚠️ **v0.4 파괴적 변경(BREAKING)** — `scan`은 이제 위키 생성과 함께 **항상 벡터 인덱싱까지
> 수행**한다. 그러려면 임베딩 모델(기본 `nomic-embed-text`)이 로컬에 있어야 하며, 없으면
> **`scan`이 차단**된다(exit 1, `ollama pull nomic-embed-text` 안내). 별도 플래그로 끌 수 없다 —
> `corpbrain doctor`로 미리 확인하자.

> ⚠️ **v0.3 파괴적 변경(BREAKING)** — v0.2까지 `scan`은 GPU가 없어도 그냥 돌았지만, v0.3부터는
> **GPU가 감지되지 않으면 `scan`이 차단**된다(exit 1). CPU로 실행하려면 `--force-gates`를 붙여야
> 한다. 참고: GPU 감지는 `nvidia-smi` 기반이라 **Apple Silicon·AMD GPU는 CPU로 판정**되어 역시
> `--force-gates`가 필요하다. `plan` / `--dry-run` / `doctor`는 차단하지 않는다.

---

## 1. 버전별 기능 요약

| 기능 | v0.1.0 | v0.2.0 | v0.3.0 | v0.4.0 |
|---|---|---|---|---|
| `corpbrain scan` — 스캔→요약→위키 | ✅ | ✅ | ✅ | ✅ |
| 지원 입력 포맷 | `.docx` `.txt` `.md` | + **`.pdf`** | 동일 | 동일 |
| `corpbrain plan` — pre-scan 계량 | — | ✅ (LLM·네트워크 0) | + 게이트 판정 표시 | 동일 |
| `scan --dry-run` — 리포트만, 위키 0개 | — | ✅ | ✅ | ✅ |
| 중요도 점수·예상 토큰·예상 소요·하드웨어 감지 | — | ✅ (표시만) | ✅ | ✅ |
| **자원 게이팅**(GPU/파일크기/토큰 → 차단·스킵) | — | — | ✅ **(강제)** | + 임베딩 비용 반영 |
| `corpbrain doctor` — 환경 준비 점검 | — | — | ✅ | + 임베딩 모델 점검 |
| Ollama 모델 선점검·연동 안내 | — | — | ✅ | 동일 |
| **벡터 인덱싱**(scan에 통합) | — | — | — | ✅ **(강제)** |
| `corpbrain search` — 유사 문서 검색 | — | — | — | ✅ |

> v0.2까지는 v0.1의 상위 호환이었으나, **v0.3은 GPU 게이팅**, **v0.4는 임베딩 인덱싱**이 각각
> 기본 동작을 바꾸는 파괴적 변경을 포함한다(위 경고 참고). 그 외 기존 `scan`/`plan` 동작은 그대로다.

---

## 2. 사전 준비

1. **Python 3.12** 와 패키지. 이 저장소는 [`uv`](https://docs.astral.sh/uv/)로 관리한다.
   ```bash
   uv python install 3.12
   uv venv --python 3.12
   uv pip install -e .
   ```
   이후 모든 명령은 `uv run` 접두어로 실행한다(`uv run corpbrain ...`).
2. **Ollama** (요약·인덱싱에 필요 — `scan`에서 사용). 로컬에서 구동 중이어야 한다.
   CorpBrain은 **탐지만** 하며 설치하지 않는다.
   ```bash
   ollama serve                       # 로컬 서버 (기본 127.0.0.1:11434)
   ollama pull qwen2.5:7b-instruct    # 기본 요약 모델
   ollama pull nomic-embed-text       # 기본 임베딩 모델 [v0.4] — 없으면 scan이 exit 1로 차단됨
   ```
   > `plan` / `scan --dry-run`은 Ollama가 필요 없다(LLM·네트워크 0).

---

## 3. 빠른 시작

```bash
# 1) 먼저 값싸게 훑어보기 — 무엇이 중요하고 얼마나 걸릴지  [v0.2]
uv run corpbrain plan ./inbox

# 2) 실제 변환 — 문서마다 위키 1개 생성 + 벡터 인덱싱 (Ollama 필요)  [v0.1, 인덱싱은 v0.4]
uv run corpbrain scan ./inbox --out ./wiki

# 3) 처리 없이 예상만 보기  [v0.2]
uv run corpbrain scan ./inbox --dry-run

# 4) 위키가 쌓인 폴더에서 유사 문서 검색  [v0.4]
uv run corpbrain search "휴가 정책" --out ./wiki
```

---

## 4. `corpbrain scan` — 스캔 → 요약 → 위키  `[v0.1]`

폴더를 재귀 순회해 지원 포맷 문서를 텍스트 추출하고, 로컬 Ollama로 요약·구조화한 뒤,
**입력 문서 1개당 위키 마크다운 1개**를 생성한다.

```
uv run corpbrain scan <folder> [옵션]
```

| 옵션 | 기본값 | 설명 | 버전 |
|---|---|---|---|
| `--out DIR` | `./corpbrain_wiki` | 위키 출력 폴더(입력 폴더 구조를 미러링) | v0.1 |
| `--model NAME` | `qwen2.5:7b-instruct` | 요약 모델. 환경변수 `CORPBRAIN_MODEL`로도 지정(플래그가 우선) | v0.1 |
| `--max N` | `50` | 스캔 대상 상한. 초과 시 **처리 중단 + 알림** | v0.1 |
| `--max-chars N` | `12000` | 문서당 요약 입력 상한 글자 수(앞부분만 사용) | v0.1 |
| `--ollama-url URL` | `http://127.0.0.1:11434` | 로컬 Ollama 주소 | v0.1 |
| `--force` | (off) | 원문 mtime과 무관하게 강제 재생성 | v0.1 |
| `--dry-run` | (off) | 처리 없이 pre-scan 리포트만 stdout으로(위키 0개) | **v0.2** |
| `--force-gates` | (off) | 차단 게이트(GPU·토큰)를 무시하고 강행. `file_too_large` 스킵에는 영향 없음 | **v0.3** |
| `--max-file-size MB` | `20` | 개별 파일 크기 상한(MB). 초과 파일은 `file_too_large`로 스킵 | **v0.3** |
| `--max-total-tokens N` | `200000` | 스캔 전체 예상 토큰 예산. 초과 시 **차단**(exit 3) | **v0.3** |
| `--embed-model NAME` | `nomic-embed-text` | 인덱싱에 쓸 임베딩 모델. 환경변수 `CORPBRAIN_EMBED_MODEL`로도 지정(플래그가 우선). 없으면 `scan` 차단(exit 1) | **v0.4** |

**자원 게이팅 `[v0.3, v0.4에서 토큰 산정 확장]`** — 본격 처리 전에 세 축을 강제한다:
- **GPU**: 미탐지면 `scan` 차단(exit 1). `--force-gates`로만 CPU 강행.
- **토큰**: 스캔 전체 예상 토큰(v0.4부터 임베딩 비용 근사 10% 포함)이 `--max-total-tokens`를
  넘으면 차단(exit 3). `--force-gates`로 강행.
- **파일 크기**: 개별 파일이 `--max-file-size`를 넘으면 그 파일만 스킵하고 나머지는 계속(부분 성공).
  `--force-gates`로 우회되지 않으며, 포함하려면 `--max-file-size`를 올린다.

**벡터 인덱싱 `[v0.4]`** — 위키 생성과 함께 항상 수행된다(옵트인 플래그 없음):
- 문서당 벡터 1개(위키 요약 콘텐츠를 청크 분할 없이 임베딩), `<out>/.corpbrain_index.sqlite`에 저장.
- 위키가 mtime상 스킵돼도 인덱스에 벡터가 없으면 기존 위키에서 채워 넣는다(백필). `--force`는 둘 다 강제 재계산.
- 원문·위키가 사라지면 다음 `scan`에서 인덱스의 대응 벡터를 정리한다(고아 벡터 없음).
- 프리플라이트를 통과한 뒤 개별 문서의 임베딩 호출만 런타임에 실패하면, 위키는 그대로 두고
  해당 문서의 인덱싱만 실패로 기록한다(부분 성공, exit 0).

**동작 규칙**
- 진행 로그·종료 요약은 **stderr**로 나가고 **stdout은 비어 있다**(파이프 친화적).
- 재실행 시 원문 mtime이 기존 위키보다 최신일 때만 재생성한다(아니면 `up_to_date`로 스킵). `--force`로 무시.
- 텍스트는 앞부분 `--max-chars`까지만 읽는다(파일을 통째로 메모리에 올리지 않음).
- 개별 파일 실패는 **전체 실패로 위장하지 않는다** — 해당 파일만 스킵하고 나머지는 계속(부분 성공).

**시작 배너 `[v0.2]`** — `scan`을 실행하면 처리 전 stderr에 한 줄 요약이 먼저 뜬다:
```
pre-scan: 6개 파일 · 예상 소요 약 1분 54초 (근사)
중요도 TOP 3: report.docx, guide.md, empty.txt
```

**예시**
```bash
uv run corpbrain scan ./inbox --out ./wiki --model qwen2.5:7b-instruct
uv run corpbrain scan ./inbox --max 200 --force
CORPBRAIN_MODEL=llama3.1:8b uv run corpbrain scan ./inbox   # 환경변수로 모델 지정
```

---

## 5. `corpbrain plan` — pre-scan 계량  `[v0.2]`

본격 스캔 **전에** 폴더를 값싸게 훑어 "무엇이 중요하고 얼마나 걸릴지"를 먼저 보여 준다.
**LLM·네트워크를 전혀 쓰지 않으며**(소켓 0), 파일 내용을 열지 않고 경로·`os.stat` 크기만 사용한다.

```
uv run corpbrain plan <folder> [--max N] [--max-chars N]
```

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--max N` | `50` | scan 상한 **경고 기준**. plan은 중단하지 않고 초과 시 경고만 표시 |
| `--max-chars N` | `12000` | 예상 토큰 추정의 문서당 상한 글자 수 |
| `--max-file-size MB` `[v0.3]` | `20` | 게이트 판정 **표시용** 개별 파일 상한(MB) |
| `--max-total-tokens N` `[v0.3]` | `200000` | 게이트 판정 **표시용** 토큰 예산 |

리포트는 **stdout**으로 나가며 다음을 담는다:
- **중요도 내림차순 TOP 20행** + "…외 M건"
- **합계**: 파일 수 · 총 예상 토큰 · 예상 소요(근사)
- **감지 하드웨어**(GPU 이름 또는 CPU)
- **게이트 판정(표시만)** `[v0.3]` — GPU·토큰·`file_too_large` 예정 파일 수. `plan`은 차단하지 않는다.
- 발견 수가 `--max`를 넘으면 경고 한 줄

```
CorpBrain pre-scan 계량 — 중요도 상위 6개 (근사)
  [ 58] report.docx  (.docx, ~880 tok)
  [ 45] guide.md  (.md, ~11 tok)
  ...
합계: 6개 파일 · 예상 토큰 5,709 · 예상 소요 약 1분 54초
감지 하드웨어: GPU: NVIDIA GeForce GTX 1050
```

**중요도 점수(0~100)** 는 파일 내용을 읽지 않고 경로·이름·확장자·트리 깊이만으로 결정적으로 매긴다:
- 확장자 기본점수(`.pdf`/`.docx` 40, `.md` 30, `.txt` 25)
- 루트에 가까울수록 가산(깊이 페널티, 하한 −20)
- 신호 키워드(계약·보고서·report·spec·제안·계획·최종·final·정책) 가산(최대 +30)
- 잡음 키워드(temp·tmp·backup·사본·copy·old·임시·draft·archive·`~$`) 감산(최대 −30)

> 예상 토큰·시간은 "**근사**"다(정적 처리율 기반). 실측 rate 보정은 후속 예정(v0.3 비목표).

---

## 6. `corpbrain search` — 유사 문서 검색  `[v0.4]`

`scan`이 만든 벡터 인덱스에서 자연어 쿼리와 유사한 문서를 찾는다. RAG의 "답변 생성" 단계는
포함하지 않는다 — 검색 결과(제목·경로·유사도 점수) 목록까지만 낸다.

```
uv run corpbrain search <query> [--out DIR] [--top-k N] [--ollama-url URL]
```

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--out DIR` | `./corpbrain_wiki` | `scan --out`으로 위키·인덱스가 쌓인 폴더 |
| `--top-k N` | `5` | 반환할 최대 결과 수 |
| `--ollama-url URL` | `http://127.0.0.1:11434` | 로컬 Ollama 주소 |

쿼리 임베딩은 **인덱스에 기록된 모델을 강제로 사용**한다 — `--embed-model` 플래그는 없다(인덱싱
시와 검색 시 모델이 달라 벡터 공간이 어긋나는 사고를 원천 차단).

```
검색 결과 2건
  1. [0.823] 휴가 규정 — /docs/hr/vacation.txt
  2. [0.611] 출장비 규정 — /docs/hr/travel.txt
```

**종료 코드**: `--out` 폴더에 인덱스가 없거나(먼저 `scan` 필요) 쿼리 임베딩 자체가 실패(Ollama
다운 등)하면 `1`. 인덱스는 정상인데 일치 문서가 0건이면 `0`("일치하는 문서가 없습니다"). 정상
결과도 `0`. 유사도 임계값은 없다 — top-K를 점수와 함께 그대로 보여주므로 점수를 보고 판단한다.

---

## 7. `corpbrain doctor` — 환경 준비 점검  `[v0.3, v0.4에서 임베딩 모델 점검 추가]`

Ollama 설치·구동·대상 모델 존재와 GPU·게이트 임계를 한 번에 점검한다. **folder 인자가 없는
환경 전용** 명령이며, 전 항목을 점검해 집계 리포트를 stdout으로 낸다(fail-fast 아님).

```
uv run corpbrain doctor [--model NAME] [--embed-model NAME] [--ollama-url URL]
```

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--model NAME` | `qwen2.5:7b-instruct` | 존재를 점검할 요약 모델(환경변수 `CORPBRAIN_MODEL`도 가능) |
| `--embed-model NAME` | `nomic-embed-text` | 존재를 점검할 임베딩 모델(환경변수 `CORPBRAIN_EMBED_MODEL`도 가능) `[v0.4]` |
| `--ollama-url URL` | `http://127.0.0.1:11434` | 로컬 Ollama 주소 |

점검 항목과 실패 시 안내(순서 = 설치 → 구동 → 대상 모델 → **임베딩 모델** → GPU → 게이트 임계값):
- Ollama **설치**(`shutil.which`) — 미설치 → `https://ollama.com 에서 설치`
- Ollama **데몬 구동**(`/api/tags`) — 미구동 → `ollama serve` 실행
- **대상 모델 존재** — 없음 → `ollama pull <model>`
- **임베딩 모델 존재** `[v0.4]` — 없음 → `ollama pull <embed-model>`
- **GPU 감지** — 없으면 경고(실패 아님)
- **게이트 임계값** 표시(정보)

**종료 코드**: 필수 조건(설치·구동·대상 모델·**임베딩 모델**)이 모두 충족되면 `0`, 하나라도
미충족이면 `1`. GPU 없음은 **경고**일 뿐 종료 코드에 영향을 주지 않는다.

```
CorpBrain doctor — 환경 점검
  [OK] Ollama 설치됨
  [OK] Ollama 데몬 구동 중
  [실패] 모델 없음: qwen2.5:7b-instruct — `ollama pull qwen2.5:7b-instruct`
  [실패] 임베딩 모델 없음: nomic-embed-text — `ollama pull nomic-embed-text`
  [경고] CPU — scan은 GPU 없이 --force-gates 필요
  [정보] 게이트 임계: 파일 20,000,000 bytes · 총토큰 200,000
준비 미완료 — 위 [실패] 항목을 해결한 뒤 다시 확인하세요.
```

---

## 8. 지원 포맷과 스킵 규칙

**지원**: `.docx` · `.txt` · `.md` `[v0.1]` · `.pdf`(텍스트 레이어) `[v0.2]`

산출물을 만들지 않고 **스킵 리포트**에 사유와 함께 표시되는 경우:

| 사유(라벨) | 설명 |
|---|---|
| 미지원 확장자 | 지원 4종 외 |
| 빈 문서 | 내용 없음. 텍스트 없는 스캔 이미지 PDF 포함 `[v0.2]` |
| 텍스트 추출 실패 | 손상·파싱 실패, **암호화 PDF** `[v0.2]` |
| 권한 거부 | 읽기 권한 없음 |
| 경로 길이 초과(>260자) | 긴 경로 |
| LLM JSON 파싱 실패 | 모델 응답이 기대 형식이 아님(해당 파일만 스킵) |
| 최신 상태(재생성 불필요) | 기존 위키가 원문보다 최신(`--force`로 무시) |
| 파일 크기 초과 `[v0.3]` | 개별 파일이 `--max-file-size` 초과(`file_too_large`, `--force-gates`와 무관) |

**인덱싱 실패(스킵과 다름) `[v0.4]`** — 위 스킵 사유들과 달리 **위키는 정상 생성**되고 인덱싱만
실패한 경우, 종료 요약에 별도로 "인덱싱 실패 K건(위키는 생성됨)"으로 집계된다(프리플라이트를
통과한 뒤 개별 문서의 임베딩 호출이 런타임에 실패한 경우).

---

## 9. 출력 마크다운 구조

출력 위치는 `--out` 하위에 입력 폴더 구조를 미러링한다. 파일명은 **원본 확장자를 유지한 채**
`.md`를 덧붙인다: `report.docx` → `report.docx.md`, `a.txt` → `a.txt.md`, `notes.pdf` → `notes.pdf.md`.

```markdown
---
source_path: "<원문 절대경로>"
generated_at: "<ISO8601>"
model: "<사용 모델>"
source_bytes: <숫자>
---

# <제목>

## 한 줄 요약
<한 문장>

## 핵심 포인트
- <불릿 3~7개>

## 요약
<문단 요약>

## 태그·키워드
<태그 목록>

## 원문
[원본 파일 열기](file://<원문 절대경로>)
```

출력 언어는 항상 한국어다.

인덱스 파일은 `--out` 하위 숨김 파일 `.corpbrain_index.sqlite`에 저장된다 `[v0.4]` — 위키
`.md` 산출물과 생명주기를 함께하며, 사용된 임베딩 모델명을 메타데이터로 기록한다.

---

## 10. 종료 코드

| 코드 | 의미 |
|---|---|
| `0` | 정상. 개별 파일의 **부분 실패(스킵·인덱싱 실패)** — `file_too_large`·`search` 결과 0건 포함 — 도 0으로 본다 |
| `1` | 선행 조건 실패 — 입력 폴더 없음/접근 불가, Ollama 미탐지·**모델 부재**(요약·**임베딩** `[v0.4]`)·**GPU 게이트**(scan), `doctor` 미준비, `search` 인덱스 없음/쿼리 임베딩 실패 `[v0.4]` |
| `3` | 상한 초과 — `--max` 대상 수 초과, 또는 **토큰 예산 초과**(`--max-total-tokens`, v0.4부터 임베딩 비용 포함) `[v0.3]` |

---

## 11. 자주 겪는 문제

- **`선행 조건 실패: 구동 중인 로컬 Ollama를 찾지 못했습니다`** → Ollama가 안 떠 있음. `ollama serve`
  실행 후 재시도. (`plan`/`--dry-run`은 Ollama 없이도 동작한다.) 먼저 `corpbrain doctor`로 상태 확인. `[v0.3]`
- **`선행 조건 실패: 대상 모델을 찾지 못했습니다`** `[v0.3]` → 모델 미설치. 안내대로 `ollama pull <model>`.
- **`선행 조건 실패: GPU를 감지하지 못했습니다`** `[v0.3]` → GPU 미탐지(또는 비-NVIDIA). CPU로 강행하려면
  `--force-gates`를 붙인다(느림). `corpbrain doctor`로 하드웨어 확인 가능.
- **`자원 게이트 차단: 스캔 전체 예상 토큰 …이 예산 …을 초과`** `[v0.3]` → `--max-total-tokens`를 올리거나
  입력 폴더를 좁히거나, `--force-gates`로 강행(v0.4부터 이 예산엔 임베딩 비용 근사도 포함된다).
- **`선행 조건 실패: 대상 모델을 찾지 못했습니다: nomic-embed-text`** `[v0.4]` → 임베딩 모델 미설치.
  `ollama pull nomic-embed-text` (다른 모델을 쓰려면 `--embed-model`). `corpbrain doctor`로 확인 가능.
- **`선행 조건 실패: 인덱스가 없습니다`** `[v0.4]` → `search`의 `--out` 폴더에 아직 `scan`을 돌리지
  않았거나 경로가 틀림. 먼저 `corpbrain scan <folder> --out <그 폴더>`를 실행한다.
- **모든 파일이 `LLM JSON 파싱 실패` + `CUDA error ... PTX ... unsupported toolchain`** → CorpBrain이
  아니라 **Ollama/GPU 문제**. VRAM이 작은 GPU에 큰 모델을 올릴 때 흔하다. 해결:
  - CPU로 강제: Ollama 종료 후 `CUDA_VISIBLE_DEVICES=-1` 로 `ollama serve` 재기동(느리지만 안정적)
  - 또는 더 작은 모델 사용: `ollama pull qwen2.5:3b-instruct` → `--model qwen2.5:3b-instruct`
- **출력이 레포/현재 폴더에 흩어짐** → `--out ./` 는 현재 폴더에 위키를 뿌린다. 전용 폴더(`--out ./wiki`)를 쓰자.

---

## 12. 이번 범위 밖 (v0.5 이후)

xls/ppt 추출, 스캔 이미지 OCR·암호화 PDF 해제, GPU 감지 확장(AMD·Apple Silicon), Ollama 자동
설치·모델 자동 pull, 클라우드 LLM(v0.5), 중요도 기반 처리순서 변경·필터, 실측 rate 기반 예상시간
보정, UI(pywebview·React), 검색 결과를 근거로 한 RAG 답변 생성(LLM 자연어 응답 합성 — v0.4는
인덱싱·검색까지만), 문서 청크 분할, 벡터 저장소 원격·분산·다중 사용자 동시접근.

---

_정본 스펙: `static/docs/specs/features/` · 로드맵: `docs/ROADMAP.md`_

# 수동 스모크 절차 — 실제 Ollama 모델 1회 (FR-020)

릴리즈 전 최종 수동 확인 단계다(자동 CI 게이트 아님). mock이 아닌 실제 로컬 Ollama로
파이프라인을 1회 돌려 산출물 품질과 계약(한국어 출력·템플릿·스킵/종료 코드)을 확인한다.

## 사전 조건
- 로컬 Ollama 데몬 기동 (`ollama serve` 또는 앱 실행).
- 모델 준비. 스펙 기본값은 `qwen2.5:7b-instruct`. 없으면 `ollama pull qwen2.5:7b-instruct`,
  또는 이미 받아 둔 다른 모델을 `--model`로 지정한다(설치·pull은 CorpBrain이 하지 않는다).
- 개발 환경: `uv venv --python 3.12 && uv sync && uv pip install -e .`

## 스모크용 실샘플
소형 실샘플(정상 `.txt`/`.md`/`.docx` 소수)을 임의 폴더에 둔다. 예시로 이 저장소는
`tests/fixtures/sample_corpus/`(정상 txt·md·docx + 하위폴더·빈 파일·미지원·초과 파일)를
갖고 있으나, 순수 정상 문서만으로 스모크하려면 별도 폴더에 `.txt`/`.md` 2~3개를 만든다.

## 실행 — Scenario 1 (정상)
```
uv run corpbrain scan <sample> --out <tmp_out> --model qwen2.5:7b-instruct
```
기대(스펙 §3-1·2, §4.1, §4.3, §4.4):
- [ ] 지원 파일마다 `<원본이름.확장자>.md`가 입력 하위구조를 미러링하여 생성된다.
- [ ] 각 `.md`에 front-matter 4키(`source_path`/`generated_at`/`model`/`source_bytes`)가 있다.
- [ ] 6섹션(`# 제목`/`## 한 줄 요약`/`## 핵심 포인트`/`## 요약`/`## 태그·키워드`/`## 원문`)이 있다.
- [ ] 요약·핵심 포인트·태그가 **한국어**로 채워진다.
- [ ] 종료 요약에 `처리 N건 / 스킵 M건(+사유)` 과 `출력 경로`가 stderr로 표시된다.
- [ ] 종료 코드 0 (부분 실패가 있어도 0).

## 실행 — Scenario 2 (Ollama 미기동)
데몬을 끄거나 닿지 않는 포트를 지정해 선행 조건 실패를 확인한다.
```
uv run corpbrain scan <sample> --out <tmp_out> --ollama-url http://127.0.0.1:1
```
기대(스펙 §4.3, §5):
- [ ] 설치를 시도하지 않고 비-0 종료.
- [ ] stderr에 미탐지 사유가 남는다.

## 실행 기록 (2026-08-12)
- 모델: `qwen2.5:7b` (로컬 보유. 스펙 기본값 `qwen2.5:7b-instruct`는 미보유라 `--model`로 지정).
- 샘플: `sales.txt`(영업 실적 문단), `roadmap.md`(로드맵 불릿) 2건.
- Scenario 1: 처리 2건 / 스킵 0건, 종료 코드 0. 소요 약 24초(2건 합산, M-계열 로컬).
  - 산출물 `sales.txt.md`: front-matter 4키·6섹션 모두 존재, 제목/요약/핵심포인트/태그가
    자연스러운 한국어로 채워짐. `## 원문` 링크가 `file://` 절대경로로 생성됨.
  - `## 태그·키워드`는 쉼표 구분 한 줄(`영업 실적, 매출 증가, 신규 고객`)로 렌더됨.
- Scenario 2 (`--ollama-url http://127.0.0.1:1`): `선행 조건 실패: 구동 중인 로컬 Ollama를
  찾지 못했습니다 ... Connection refused`, 종료 코드 1. 설치 시도 없음.
- 이상 여부: 없음. 계약(한국어·템플릿·스킵/종료 코드) 모두 충족.

# DECISION CHECKPOINT — v0.5 클라우드 옵트인 구현 루프

이 문서는 v0.5 구현 루프의 **조기 종료 판정 단일 근거**다.
CORE_BUDGET(≥3) · MINOR_BUDGET(≥10)은 오직 아래 카운터로만 판정한다.

CORE: 2
MINOR: 9

## 기록 규칙
- 형식: `- [CORE|MINOR] <결정> | 근거 | 관련 파일 | 결정 주체(main|sub-A|sub-B)`
- CORE = 아키텍처·보안·외부 의존·데이터 모델·공개 API/CLI 계약·핵심 UX 계약 신규 결정
- MINOR = 네이밍·디렉터리·로그 문구·테스트 픽스처·내부 헬퍼 등 국소 결정
- v0.5 스펙 / `docs/grill/GRILL_LEDGER-v0.5.md` / `docs/ROADMAP.md`에 이미 정해진 사항은 적지 않는다.
- **쓰기 직렬화**: 이 문서에 직접 쓰는 것은 메인 에이전트만 한다. 서브에이전트는 새 결정을
  최종 보고로 반환하고, 메인이 이를 반영하며 카운터를 갱신한다. 읽기는 모든 에이전트가 가능하다.

## 결정 목록

### 메인 에이전트 (파트 C — 관문·클라우드 클라이언트·통합)
- [CORE] Anthropic API 키는 `anthropic_client` 코어 모듈이 호출 시점에 `os.environ`에서 직접 읽고 `ScanConfig`에 싣지 않는다 | 스펙 §4.1은 "환경변수로만 받는다"만 규정하고 어느 계층이 읽는지는 미정. 기존 관례(CLI가 env 해소 후 ScanConfig에 담기)를 따르면 자격증명이 로그·에러에 repr될 수 있는 값 객체에 실린다 — 보안상 수명·노출면을 최소화하려고 관례에서 의도적으로 벗어났다 | `corpbrain/core/llm/anthropic_client.py` | main
- [MINOR] cloud 요약 타임아웃은 300초(로컬 `summarize.DEFAULT_TIMEOUT`과 동일), 프리플라이트는 60초 | 스펙 §4.3은 "기존 DEFAULT_TIMEOUT(60초)를 재사용"이라고 적었으나 실제 코드베이스는 `summarize=300.0`·`embed=60.0`으로 60초 공유 상수가 존재하지 않는다. 같은 성격(요약)의 값을 따르고 가벼운 프리플라이트만 60초를 쓰는 것으로 스펙의 의도(신규 정책을 만들지 않는다)를 지켰다 | `corpbrain/core/llm/anthropic_client.py` | main

### 보안 검토(/security-review) 후속 — 2026-08-21
- [CORE] PII 정규식 7종의 경계를 스펙 §4.5 표의 `\b` 대신 **ASCII 전용 lookaround**
  (`(?<![0-9A-Za-z_])` / `(?![0-9A-Za-z_])`)로 바꾸고, 이메일은 다단 도메인을 통째로 잡도록
  확장했다 | 보안 검토가 확인한 실제 유출: 파이썬 `\b`·`\w`는 유니코드 인식이라 한글도 단어
  문자다. 한국어는 조사가 공백 없이 붙으므로(`010-1234-5678로`, `900101-1234567입니다`,
  `192.168.0.1에서`) 경계가 성립하지 않아 패턴이 통째로 빗나가고 **원문 PII가 그대로 클라우드로
  전송**됐다(실측: 7종 중 6종이 조사 인접 시 무마스킹, 카드번호는 뒤 4자리 노출). 스펙 §4.5의
  정밀도 원칙("누락을 최소화")과 정반대의 실패 모드라 원칙에 맞추려면 표의 문자열을 벗어나야
  했다 | `corpbrain/core/pii.py`, `tests/test_pii.py` | main
  - **스펙 후속 조치 필요**: `static/docs/specs/features/corpbrain-v0.5-cloud-opt-in.md` §4.5의
    정규식 표가 이제 구현과 다르다. 스펙은 이 루프의 수정 금지 대상이라 손대지 않았으므로,
    사용자가 표를 ASCII 경계 버전으로 갱신해 정본을 일치시켜야 한다.
- [MINOR] 관문 opener를 빈 `ProxyHandler({})`로 만들어 `http_proxy`·`https_proxy` 환경변수와
  Windows 레지스트리 프록시 설정을 무시한다 | `urllib`은 `127.0.0.1`·`localhost`를 프록시에서
  자동 제외하지 않아, 선의로 설정된 사내 프록시 하나만으로 마스킹되지 않은 로컬 요약 본문이
  평문 HTTP로 사외 프록시에 전달될 수 있었다(실측 확인). 로드맵 불변식 "기본 로컬 — 외부 통신
  0"을 지키는 쪽을 택했다. **트레이드오프**: 프록시를 통해서만 외부에 나갈 수 있는 사내망에서는
  `--engine cloud`가 동작하지 않는다 — 필요해지면 명시적 opt-in 플래그로 여는 것이 맞다 |
  `corpbrain/core/gateway.py` | main

### 파트 A (`core/pii.py`) — sub-A 보고를 메인이 재분류해 기록
- [MINOR] `[REDACTED_<TYPE>]`의 TYPE 토큰을 `RRN`/`PHONE`/`EMAIL`/`BIZ_NO`/`CARD`/`ACCOUNT`/`IP`로 확정 | 스펙 §4.5는 플레이스홀더 형태만 정하고 토큰 문자열은 미정 | `corpbrain/core/pii.py` | sub-A
- [MINOR] 패턴 적용 순서를 우선순위로 정의(EMAIL → RRN → CARD → PHONE → BIZ_NO → ACCOUNT → IP) | 계좌번호 휴리스틱이 사업자·전화·카드 패턴을 삼켜 라벨이 뭉개지므로 좁은 패턴을 먼저 적용. 스펙은 적용 순서를 미규정(마스킹 자체는 어느 순서든 이뤄지므로 보안 영향 없음) | `corpbrain/core/pii.py` | sub-A
- [MINOR] 반환 타입 `MaskingResult(text, counts, .total)`, `counts`에는 1건 이상인 유형만 담는다 | 스펙은 "치환 개수 집계"만 요구하고 자료구조 미정 | `corpbrain/core/pii.py` | sub-A
- [MINOR] 집계 단위는 등장 건수(같은 이메일 3회 → 3) | 스펙에 집계 단위 명시 없음 | `corpbrain/core/pii.py` | sub-A

### 파트 B (`core/consent.py`) — sub-B 보고를 메인이 재분류해 기록
- [MINOR] 설정 파일이 없는 상태의 revoke는 실패가 아니라 `granted: false`를 기록해 파일을 만든다 | 사후 상태를 결정적·멱등으로 만들기 위함(스펙 §3 항목3의 exit 0 요구 충족) | `corpbrain/core/consent.py` | sub-B
- [MINOR] 기존 파일이 손상 JSON·비-객체면 grant/revoke가 보존 없이 새 문서로 덮어쓴다 | 스펙 §4.2의 "다른 키는 보존"은 파싱 가능한 경우의 규정. 손상 파일 때문에 동의 기록이 영구히 막히면 안 되며, 읽기는 여전히 "동의 없음"으로 흡수되므로 보안 계약은 유지된다 | `corpbrain/core/consent.py` | sub-B
- [MINOR] 쓰기 실패는 `ConsentStoreError(PreconditionError)`로 올린다 | 스펙 미규정. 읽기 실패는 "동의 없음"으로 흡수해도 되지만 쓰기 실패를 삼키면 사용자가 동의가 기록됐다고 오해한다. 기존 exit 1 매핑을 그대로 재사용하므로 신규 종료 코드는 없다 | `corpbrain/core/consent.py` | sub-B

### 기록하지 않은 보고 항목 (감사용 — 신규 결정이 아니라고 판정)
- `granted`를 정확한 boolean `True`로만 판정: 스펙 §4.2 "`granted`가 `true`가 아니면 동의 없음"의 직접적 구현이다.
- revoke가 `granted: false`를 남기는 것 자체: 스펙 §4.2가 "둘 중 무엇이든"으로 두 선택지를 이미 승인했다.
- 원자적 쓰기의 mkstemp·fsync·unlink 세부: 스펙 §4.2가 지시한 "임시 파일 + `os.replace`"의 표준 구현이다.
- `PiiType.label`의 한국어 유형명: 스펙 §4.5 표의 '유형' 열 값을 그대로 노출한 것이다.
- consent 설정 파일의 JSON 들여쓰기 형식: 계약에 영향 없는 포맷 latitude.
- 리다이렉트 차단을 클라우드뿐 아니라 로컬 경로에도 적용: 스펙 §4.4가 클라우드에 요구한 것을 안전한 방향으로 일반화했을 뿐, 규정된 동작을 바꾸지 않는다.

STOP REASON: ALL_DONE

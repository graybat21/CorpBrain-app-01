# Grill Ledger — v0.5 클라우드 옵트인 (Anthropic API 요약 연동)

참조 범위: `static/docs/specs/features/corpbrain-v0.5-cloud-opt-in.md`
관심 방향: v0.5 스펙의 구현 착수 전 남은 모호함 — 코드 레벨 인터페이스·매핑 규칙·보안 세부사항
완료조건: 아래 토픽 전부 RESOLVED
OUTPUT: `static/docs/specs/features/corpbrain-v0.5-cloud-opt-in.md`, 필요 시 `CLAUDE.md`

RESOLVED: 8 / TOTAL: 8  ·  STOP: ALL_RESOLVED

- [x] T1 | CORE  | NetworkGuard 호스트 매칭 로직(스킴·포트·리다이렉트 판정) | status:RESOLVED | decision:urlsplit(scheme,hostname) 대소문자무시 정확일치 + 커스텀 HTTPRedirectHandler로 3xx 무조건 예외, stdlib만 사용 | applied:corpbrain-v0.5-cloud-opt-in.md §4.4
- [x] T2 | CORE  | Cloud 인증 프리플라이트 메커니즘(첫 파일 처리 전 키 검증) | status:RESOLVED | decision:파일 루프 진입 전 GET /v1/models 1회 호출(토큰 비용 없음), 401이면 0건 처리 후 즉시 exit 1, v0.3 Ollama 프리플라이트와 동일한 자리 | applied:corpbrain-v0.5-cloud-opt-in.md §4.3
- [x] T3 | MINOR | cloud 호출 timeout 기본값 | status:RESOLVED | decision:기존 DEFAULT_TIMEOUT(60초) 그대로 재사용, 신규 상수 없음 | applied:corpbrain-v0.5-cloud-opt-in.md §4.3
- [x] T4 | CORE  | 429/5xx/timeout → SkipReason 매핑 규칙 | status:RESOLVED | decision:429만 cloud_rate_limited, 그 외(5xx·타임아웃·연결오류·400/404 포함) 전부 cloud_api_error로 통합, 신규 사유 2개뿐 | applied:corpbrain-v0.5-cloud-opt-in.md §3 항목8
- [x] T5 | CORE  | PII 탐지 정규식 7종의 실제 패턴 | status:RESOLVED | decision:체크섬 없는 형태 기반 느슨한 매칭 원칙 채택, 7종 각각 구체 정규식 확정(계좌번호는 은행별 표준 부재로 휴리스틱임을 명시) | applied:corpbrain-v0.5-cloud-opt-in.md §4.5
- [x] T6 | CORE  | Anthropic 요청 프롬프트·tool 스키마 상세 | status:RESOLVED | decision:기존 PROMPT_TEMPLATE 재사용(JSON강제 문구만 제거), tool명 emit_summary, minItems/maxItems 미지정으로 로컬과 검증규칙 일치, max_tokens=2048 | applied:corpbrain-v0.5-cloud-opt-in.md §4.3
- [x] T7 | MINOR | 동의 설정파일 쓰기 방식(원자적 쓰기 여부) | status:RESOLVED | decision:임시파일+os.replace 원자적 쓰기 | applied:corpbrain-v0.5-cloud-opt-in.md §4.2
- [x] T8 | MINOR | doctor/consent 명령 출력 문구 포맷 | status:RESOLVED | decision:cloud 상태는 GPU와 동일하게 경고 마커로만 표시, doctor 전체 exit code에 영향 없음, 구체 문구 확정 | applied:corpbrain-v0.5-cloud-opt-in.md §3 항목10, §4.1

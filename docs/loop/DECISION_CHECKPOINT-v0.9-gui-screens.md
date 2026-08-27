# 의사결정 체크포인트 — v0.9 GUI PR ② (`feat/v0.9-gui-screens`)

정본 3종(스펙 `static/docs/specs/features/corpbrain-v0.9-gui.md` · 실행 플랜
`docs/plans/corpbrain-v0.9-gui.md` · grill 원장 3종)에 확정돼 있지 **않은** 추가 의사결정만
여기에 기록한다. 분류는 CORE(아키텍처·보안·외부의존·데이터 모델) / MINOR(네이밍·디렉터리·
로그 포맷·문구)이며, 엔드포인트 경로 문자열과 응답 필드 이름은 스펙 §4.3이 구현에 위임한
것이므로 **MINOR** 로 센다 (PR ① 과 같은 잣대).

CORE: 0
MINOR: 0

## 기록

### 착수 전 게이트 실패 — 2026-08-27

목표 문서(`docs/goals/corpbrain-v0.9-gui-screens-loop.md`) §1 이 요구한 착수 전 확인 두 가지가
**둘 다 거짓**이라 구현을 한 줄도 시작하지 않고 멈췄다.

| 게이트 | 요구 | 실측 |
|---|---|---|
| ① `main` 에 PR #56·**#60** 머지 | 둘 다 보인다 | `origin/main` HEAD 가 `870e80e`(PR #56)이고 **PR #60 은 `OPEN`**(`mergedAt=null`) |
| ② `main` 의 스펙에 정정 문면 | `grep -c` ≥ 1 | `git show origin/main:…corpbrain-v0.9-gui.md \| grep -c "PR ①에서 확정된 값은 아래와 같다"` → **0** |

PR #60 은 「v0.9 GUI 스펙 문면 정정 5건 (closes #57)」이며 §4.3 에 확정된 경로·응답 스키마
(`/api/dashboard` · `/api/events` · `/assets/<파일명>` · `{error, message}` · 스냅샷 프레임)와
`handle()` 시그니처 기본값 · `GraphFinished.stats` nullable · `reduce()` 가 더하는 스냅샷 3필드 ·
SSE keepalive · 구독자 큐 상한을 담고 있다. **PR ② 가 그대로 이어 써야 하는 계약이다.**

이 상태로 착수하면 PR ① 과 PR ② 가 같은 스펙 문서를 서로 다른 상태로 참조하게 되고, 실행
플랜 「착수 전제」가 「스펙이 구현의 근거이므로 `main` 에 없는 스펙을 보고 구현하지 않는다」로
세운 규율이 깨진다. 그 규율은 v0.7 이 「선행 PR 머지 후 착수」로 세운 것을 잇는다.

이 브랜치는 `origin/main`(`870e80e`)에서 났으므로, **PR #60 이 머지된 뒤 `main` 위로 리베이스**
(또는 `git reset --hard origin/main` 후 이 파일만 복원)한 다음 V1 부터 재개한다.

---

STOP REASON: WRONG_BASE

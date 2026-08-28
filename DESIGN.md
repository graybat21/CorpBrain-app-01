---
name: CorpBrain
description: 조용한 열람실 — 종이빛 바탕 위에 절제된 활자로 문서를 읽는 로컬 지식 도구
colors:
  canvas: "#FBFBFA"
  surface: "#FFFFFF"
  surface-sunken: "#F5F4F1"
  border: "#EAEAEA"
  border-strong: "rgba(17, 17, 17, 0.14)"
  ink: "#111111"
  ink-soft: "#2F3437"
  text-secondary: "#67655F"
  text-muted: "#736D62"
  text-inverse: "#FFFFFF"
  accent-cyan: "#1F6C9F"
  accent-blue: "#2E6A93"
  accent-emerald: "#346538"
  accent-purple: "#5B4B8A"
  accent-amber: "#956400"
  accent-rose: "#9F2F2D"
  pastel-blue-bg: "#E1F3FE"
  pastel-blue-text: "#1F6C9F"
  pastel-green-bg: "#EDF3EC"
  pastel-green-text: "#346538"
  pastel-yellow-bg: "#FBF3DB"
  pastel-yellow-text: "#956400"
  pastel-red-bg: "#FDEBEC"
  pastel-red-text: "#9F2F2D"
  pastel-lilac-bg: "#EFECF7"
  pastel-lilac-text: "#5B4B8A"
typography:
  display:
    fontFamily: "'Noto Serif KR', 'AppleMyungjo', 'Batang', 'Nanum Myeongjo', Georgia, serif"
    fontSize: "30px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "'Noto Serif KR', 'AppleMyungjo', 'Batang', 'Nanum Myeongjo', Georgia, serif"
    fontSize: "25px"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  title:
    fontFamily: "'Pretendard', -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Segoe UI', 'Malgun Gothic', Helvetica, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "normal"
  body:
    fontFamily: "'Pretendard', -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Segoe UI', 'Malgun Gothic', Helvetica, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "normal"
  label:
    fontFamily: "'Pretendard', -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Segoe UI', 'Malgun Gothic', Helvetica, Arial, sans-serif"
    fontSize: "10px"
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: "0.08em"
  data:
    fontFamily: "'Geist Mono', 'SF Mono', 'JetBrains Mono', ui-monospace, Menlo, Consolas, monospace"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  brand:
    fontFamily: "'Noto Serif KR', 'AppleMyungjo', 'Batang', 'Nanum Myeongjo', Georgia, serif"
    fontSize: "21px"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "-0.02em"
  doc-title:
    fontFamily: "'Noto Serif KR', 'AppleMyungjo', 'Batang', 'Nanum Myeongjo', Georgia, serif"
    fontSize: "24px"
    fontWeight: 400
    lineHeight: 1.35
    letterSpacing: "normal"
  title-lg:
    fontFamily: "'Pretendard', -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Segoe UI', 'Malgun Gothic', Helvetica, Arial, sans-serif"
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "normal"
  nav:
    fontFamily: "'Pretendard', -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Segoe UI', 'Malgun Gothic', Helvetica, Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  caption:
    fontFamily: "'Pretendard', -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', 'Segoe UI', 'Malgun Gothic', Helvetica, Arial, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
rounded:
  sm: "6px"
  md: "8px"
  lg: "12px"
  full: "9999px"
spacing:
  xs: "6px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  2xl: "30px"
components:
  button:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  button-hover:
    backgroundColor: "{colors.surface-sunken}"
    textColor: "{colors.ink}"
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.text-inverse}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  button-primary-hover:
    backgroundColor: "{colors.ink-soft}"
    textColor: "{colors.text-inverse}"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-soft}"
    rounded: "{rounded.lg}"
    padding: "18px 20px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "7px 10px"
  nav-item:
    textColor: "{colors.ink-soft}"
    rounded: "{rounded.md}"
    padding: "8px 10px"
  nav-item-active:
    backgroundColor: "{colors.surface-sunken}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "8px 10px"
  badge-pass:
    backgroundColor: "{colors.pastel-green-bg}"
    textColor: "{colors.pastel-green-text}"
    rounded: "{rounded.full}"
    padding: "3px 9px"
  badge-warn:
    backgroundColor: "{colors.pastel-yellow-bg}"
    textColor: "{colors.pastel-yellow-text}"
    rounded: "{rounded.full}"
    padding: "3px 9px"
  badge-fail:
    backgroundColor: "{colors.pastel-red-bg}"
    textColor: "{colors.pastel-red-text}"
    rounded: "{rounded.full}"
    padding: "3px 9px"
  tag-chip:
    backgroundColor: "{colors.pastel-lilac-bg}"
    textColor: "{colors.pastel-lilac-text}"
    rounded: "{rounded.full}"
    padding: "3px 9px"
---

# Design System: CorpBrain

## Overview

**Creative North Star: "조용한 열람실"**

문서를 읽으러 들어가는 방이다. 종이빛 바탕(#FBFBFA) 위에 활자만 놓이고, 그 밖의 것은 거의
없다. 장식이 없는 것은 미니멀리즘을 좇아서가 아니라 **읽는 것 말고 다른 일이 일어나지 않게
하려는 것**이다. 이 도구를 쓰는 사람은 자기 회사의 인사·계약·원가 문서를 열고 있으므로, 화면이
스스로를 주장하는 순간 신뢰가 깎인다.

목소리는 **절제되고 · 정확하고 · 신뢰할 만하다.** 정확함이 이 시스템의 미감이다 — 경로는
언제나 mono 로 적히고, 지표는 세리프 숫자로 적히며, 근거 없는 값은 화면에 오르지 않는다.
세 계열의 활자(세리프·산세리프·모노)가 각자 맡은 것만 말하고 서로의 자리를 넘지 않는다.

**세 벌의 다른 세계를 실제로 만들어 보고 버린 뒤에 남은 것이다.** 다크 네이비에 시안 글로우,
순수 흑에 위험 적색, 반투명 글래스 — 셋 다 「AI가 만든 대시보드」처럼 보였고, 마지막 하나만
「문서를 읽는 도구」처럼 보였다. 그 판단이 이 시스템의 기원이며, 아래 「하지 말 것」의 근거다.

**Key Characteristics:**
- 종이빛 웜 화이트 바탕 — 순백이 아니라 아주 옅게 따뜻한 회백
- 세 계열 활자 대비 — 세리프는 **값**에만, 모노는 **경로·수치**에만, 나머지는 산세리프
- 대문자 마이크로 라벨(10~11px · 자간 0.06~0.08em)이 구역을 나눈다
- 평면 벤토 카드 — 1px 테두리 + 거의 보이지 않는 그림자 하나
- 채도를 뺀 파스텔 배지 5쌍 — 색이 상태를 말하되 소리치지 않는다
- 잉크 검정 버튼 하나가 화면당 하나뿐인 강조점이다

## Colors

바탕은 종이, 글자는 잉크, 색은 상태를 말할 때만 나타난다. 채도가 높은 색이 하나도 없다 —
가장 진한 악센트조차 채도를 뺀 청색이다.

### Primary
- **깊은 잿빛 청색** (`accent-cyan` · #1F6C9F): 이 시스템의 유일한 주 악센트다. **전역 포커스
  링**(`2px solid`, offset 2px)과 정보 배지·점수 배지에 쓰인다. 토큰 이름이 `accent-cyan`인 것은
  프로토타입에서 구조 호환을 위해 물려받은 이력이며, **실제 값은 시안이 아니다.** 코드와 문서의
  키를 갈리지 않게 하려고 이름은 그대로 두고, 부르는 이름만 정확하게 적는다.

### Secondary
- **가라앉은 청색** (`accent-blue` · #2E6A93): 본문 안의 이동 가능한 링크(「관련 문서」)와
  지식그래프의 **Document 노드**. 주 악센트보다 한 걸음 물러선 자리다.

### Tertiary
지식그래프의 노드 종류를 가르는 데만 쓰인다. 세 색이 함께 나타나는 화면은 그래프 하나뿐이다.
- **이끼 초록** (`accent-emerald` · #346538): Tag 노드 · 통과 상태.
- **먹빛 자주** (`accent-purple` · #5B4B8A): Entity 노드 · 태그 칩.
- **황토 갈색** (`accent-amber` · #956400): 주의·게이트 경고.
- **벽돌 적색** (`accent-rose` · #9F2F2D): 실패.
  - `accent-amber`·`accent-rose`는 `:root`에 선언돼 있으나 **직접 참조되지 않는다.** 같은 값이
    파스텔 쌍의 글자색으로 쓰이며, 그쪽이 실제 사용처다.

### Neutral
- **종이 흰색** (`canvas` · #FBFBFA): 앱 전체 바탕. 순백이 아니라 아주 옅게 따뜻하다.
- **표면 흰색** (`surface` · #FFFFFF): 카드·사이드바·헤더·입력란처럼 바탕에서 한 겹 올라온 면.
- **가라앉은 면** (`surface-sunken` · #F5F4F1): 호버·선택 상태, 요약 로그 블록, 경로 표시 칩.
  올라오는 대신 **눌린** 면으로 상태를 표현한다.
- **실선** (`border` · #EAEAEA): 카드 테두리·구분선. 화면의 구조를 만드는 주된 수단.
- **강조 실선** (`border-strong` · rgba(17,17,17,0.14)): 입력란과 기본 버튼의 테두리, 빈 상태의
  점선. 「만질 수 있다」를 알리는 선이다.
- **잉크** (`ink` · #111111): 제목·강조 텍스트·주 버튼 바탕·진행바.
- **부드러운 잉크** (`ink-soft` · #2F3437): 본문 기본 색.
- **이차 텍스트** (`text-secondary` · #67655F): 부제·설명문.
- **흐린 텍스트** (`text-muted` · #736D62): 라벨·캡션·경로.
- **반전 텍스트** (`text-inverse` · #FFFFFF): 잉크 바탕 위 글자.

### Named Rules

**대비비 이력 존중 규칙.** `text-secondary`(#67655F)와 `text-muted`(#736D62)는 각각 #787774 ·
#A6A29A 에서 **대비비 실패로 한 번 재서 올린 값**이다. 이 둘을 원래대로 되돌리거나 더 흐리게
만들지 않는다. 두 값을 낮추는 변경은 그때 치른 측정 비용을 무효로 만든다.

**한 목소리 규칙.** 잉크 검정 버튼(`button-primary`)은 **한 화면에 하나**다. 「지금 눌러야 할
것」이 둘이면 사용자는 무엇을 눌러야 할지 다시 읽어야 한다.

**색은 상태만 말한다 규칙.** 파스텔 배지 5쌍은 통과·주의·실패·정보·분류라는 **상태**에만 쓴다.
장식이나 시각적 리듬을 위해 색을 얹지 않는다. 색이 없는 화면이 정상이다.

## Typography

**Display Font:** Noto Serif KR (fallback: AppleMyungjo, Batang, Nanum Myeongjo, Georgia, serif)
**Body Font:** Pretendard (fallback: -apple-system, Apple SD Gothic Neo, Malgun Gothic, sans-serif)
**Label/Mono Font:** Geist Mono (fallback: SF Mono, JetBrains Mono, ui-monospace, Menlo)

**Character:** 세 계열이 각자 맡은 것만 말한다. 세리프는 **값**의 목소리이고, 모노는 **기계가
적은 것**의 목소리이며, 산세리프는 **설명**의 목소리다. 한 화면에서 세 계열이 동시에 보이는
것이 정상이고, 그 대비가 이 시스템의 유일한 시각적 장치다.

### Hierarchy
- **Display** (세리프 700, 30px, 자간 -0.02em): 지표 숫자. 대시보드 카드의 값 하나에만 쓴다.
- **Headline** (세리프 700, 25px, 자간 -0.01em): 화면 제목(헤더). 문서 상세 제목은 24px 로 한 단
  아래에 놓인다. 브랜드명은 21px 세리프다.
- **Title** (산세리프 600, 15~16px): 검색 결과 제목, 빈 상태 제목. 목록 안에서 「이것이 항목의
  이름」임을 알리는 자리.
- **Body** (산세리프 400, 13px, 행간 1.6): 본문 기본. 문서 상세 본문만 1.65 로 조금 더 연다.
- **Label** (산세리프 600~700, 10~11px, 자간 0.06~0.08em, 대문자): 카드 제목·필드 라벨·섹션
  헤더·트리 디렉터리. 구역을 나누는 유일한 수단이다.
- **Data** (모노 400, 11~12px): 파일 경로, 점수, 연결 차수, 종료 요약 로그, 입력란의 경로 값.

### 실제 램프는 11단계다 [2026-08-28 실측 반영]

`10 · 11 · 12 · 13 · 14 · 15 · 16 · 21 · 24 · 25 · 30px`. 초판 프론트매터는 6단계만
인코딩했고 산문은 범위(15~16 · 11~12)와 명명된 예외 3개(21 · 24 · 14)를 따로 정의해,
**같은 문서의 두 층이 서로 어긋나 있었다.** 디텍터가 램프 밖 값 13건을 잡아 드러냈다.
구현이 옳고 문서가 뒤처져 있었으므로 문서를 구현에 맞췄다.

**대가를 적어 둔다: 11단계는 넓다.** 특히 사스체 12px과 14px은 캡션·표·설명·입력이
공유하는 «잡동사니 대역»이고, 역할이 아니라 편의로 고른 흔적이 있다. 스케일을 진짜로
조이는 것은 이 문서의 몫이 아니라 별도 작업(`/impeccable typeset`)이다 — 지금 문서를
좁게 적어 두면 구현이 위반 상태로 남을 뿐 스케일이 저절로 좁아지지는 않는다.

### Named Rules

**세리프는 값에만 규칙.** 세리프를 본문·설명·버튼·라벨에 쓰지 않는다. 세리프가 나타났다면 그
자리에 있는 것은 **이름이거나 수치**여야 한다.

**경로는 반드시 모노 규칙.** 파일 경로·절대경로·모델명·수치는 예외 없이 모노로 적는다. 사용자가
그 문자열을 **복사해서 다른 곳에 붙일 것**이기 때문이며, 비례 활자는 그 순간 글자를 잘못 읽게
만든다.

## Layout

앱 셸은 **고정 사이드바(264px) + 2행 헤더(114px) + 스크롤되는 본문**이다. 사이드바와 헤더는
`surface` 흰색이고 본문 영역만 `canvas` 종이빛이라, 작업 영역이 배경보다 한 톤 낮게 가라앉는다.

본문은 **벤토 그리드**다 — `repeat(auto-fit, minmax(260px, 1fr))`에 간격 16px. 카드 개수가
아니라 폭이 배치를 정하므로 창을 줄이면 열이 자연스럽게 줄어든다. 위키 탐색기만 다른 격자를
쓴다: `minmax(220px, 300px) 1fr` 2열이며 **860px 이하에서 1열로 접힌다.** 이것이 이 시스템의
유일한 미디어 쿼리다.

**간격 토큰은 CSS에 선언돼 있지 않다.** 아래는 구현 전체에서 반복 관찰된 리듬이며, 새 화면은 이
계단을 따른다: 6 · 8 · 12 · 16 · 20 · 30px. 카드 안쪽은 18~20px, 본문 바깥 여백은 26~30px 다.

밀도는 **중간보다 조금 촘촘하다.** 본문 13px 에 행간 1.6 이고, 표는 11~12px 로 한 단 더 조인다.
문서를 훑는 도구이므로 한 화면에 많이 담기는 쪽을 택했다.

### Named Rules

**넓은 것은 자기 안에서 스크롤한다 규칙.** 표·캔버스·경로 목록은 자기 컨테이너에 `overflow`를
갖는다(`.table-scroll` 320px, `.tree` 70vh, `.browser-list` 220px). **본문이 가로로 밀리지
않는다.**

## Elevation & Depth

**평면이 기본이고 그림자는 속삭임이다.** 깊이는 그림자가 아니라 **바탕색 3단계와 1px 선**으로
만든다: `canvas`(#FBFBFA) → `surface`(#FFFFFF) → `surface-sunken`(#F5F4F1). 올라온 면은 더 밝고,
눌린 면은 더 어둡다.

그림자는 벤토 카드 하나에만, 그것도 **호버가 아니라 쉬는 상태에** 붙는다. 카드가 바닥에서 살짝
떨어져 있다는 기미만 줄 뿐 「떠 있다」고 말하지 않는다. 5% 불투명도라 인쇄물에서는 거의
사라진다 — 그것이 의도다.

### Shadow Vocabulary
- **속삭임** (`box-shadow: 0 2px 10px rgba(17, 17, 17, 0.05)`): 벤토 카드의 쉬는 상태. 이 시스템에서
  실제로 쓰이는 유일한 그림자다.
- **패널** (`box-shadow: 0 4px 20px rgba(17, 17, 17, 0.05)`): `:root`에 선언돼 있으나 **현재 어디에도
  쓰이지 않는다.** 진짜로 떠 있어야 하는 오버레이(모달·팝오버)가 생기면 그때 이 값을 쓴다.

### Named Rules

**상태는 눌러서 표현한다 규칙.** 호버·선택 상태를 그림자나 들어올림으로 표현하지 않는다.
바탕을 `surface-sunken`으로 **가라앉힌다.** 사이드바 항목, 트리 항목, 기본 버튼이 모두 같다.

## Shapes

모서리는 네 단계뿐이고 각 단계가 맡은 것이 정해져 있다 — **작게(6px)** 는 목록 항목처럼 촘촘히
반복되는 것, **보통(8px)** 은 버튼·입력란·알림 상자, **크게(12px)** 는 카드·캔버스처럼 내용을
담는 면, **완전 원형(9999px)** 은 배지·칩·진행바처럼 **글자 한 덩이나 선 하나**인 것.

형태 언어는 **선이 만든다.** 면을 채워 구획을 나누지 않고 1px 실선으로 나눈다. 카드도, 표의
행도, 검사 항목 줄도, 관련 문서 목록도 전부 아래쪽 1px 선으로만 갈린다.

빈 상태만 **점선 테두리**(`1px dashed border-strong`)를 쓴다 — 「여기 내용이 올 자리인데 아직
없다」를 형태로 말하는 유일한 곳이다.

### Named Rules

**마지막 줄에는 선이 없다 규칙.** 반복 목록의 구분선은 `:last-child`에서 제거한다. 컨테이너
테두리와 겹쳐 두 줄로 보이는 것을 막는다.

## Components

### Buttons
- **Shape:** 부드럽게 둥근 모서리(8px)
- **기본:** 흰 바탕 + 잉크 글자 + `border-strong` 1px 테두리, 안쪽 여백 8px 16px, 13px 600
- **주 버튼:** 잉크 검정(#111111) 바탕에 흰 글자, 테두리도 잉크. 화면당 하나
- **Hover:** 기본은 바탕이 `surface-sunken`으로 **가라앉고**, 주 버튼은 `ink-soft`로 한 톤 밝아진다
- **Disabled:** `opacity: 0.45` + `cursor: not-allowed`. 색을 바꾸지 않는다
- **Focus:** 전역 포커스 링 하나를 그대로 받는다(아래 규칙 참조)

### Chips
- **태그 칩:** 연보라 바탕(#EFECF7) + 먹빛 자주 글자(#5B4B8A), 완전 원형, 11px
- **상태 배지:** 파스텔 5쌍 중 하나. 10px 700 대문자 자간 0.04em, 완전 원형, `white-space: nowrap`
- **점수 배지:** 모노 11px, 연파랑 바탕. 검색 결과의 숫자 하나를 감싼다

### Cards / Containers
- **Corner Style:** 12px
- **Background:** `surface` 흰색
- **Shadow Strategy:** 「속삭임」 하나 (Elevation 참조)
- **Border:** `border` 1px 실선
- **Internal Padding:** 18px 20px. 검색 결과 카드만 14px 16px 로 조금 조인다
- **Card Title:** 11px 700 대문자 자간 0.06em, `text-secondary`, 아래 여백 12px

### Inputs / Fields
- **Style:** 흰 바탕 + `border-strong` 1px + 8px 모서리, 안쪽 7px 10px
- **텍스트 입력은 모노다** — 경로를 받는 자리이기 때문이다. 숫자·선택은 산세리프
- **Label:** 10px 600 대문자 자간 0.08em, `text-muted`, 입력란 위 6px
- **체크박스 필드만** 라벨이 소문자·자간 0으로 돌아가고 가로로 눕는다
- **Focus:** 전역 포커스 링

### Navigation
- 사이드바 세로 목록, 항목 사이 2px. 14px 산세리프, 8px 10px 여백, 8px 모서리
- **활성 항목은 `aria-current="page"`로 표시**되고 `surface-sunken` 바탕 + 잉크 글자 + 600 굵기
- 구역 제목은 11px 700 대문자 자간 0.08em
- 사이드바 바닥에는 현재 작업 경로가 11px `text-muted`로 붙는다

### 지식그래프 캔버스 (signature)
`<canvas>` 한 장(높이 62vh, 최소 380px)에 노드를 **종류별 동심원**으로 결정적으로 배치한다.
물리 시뮬레이션을 쓰지 않으므로 같은 그래프는 언제나 같은 그림이 된다. 노드 색은 종류를 말한다 —
Document는 가라앉은 청색, Entity는 먹빛 자주, Tag는 이끼 초록. 캔버스는 `tabIndex`와
`aria-label`을 갖고 전역 포커스 링을 받는다.

### 종료 요약 블록 (signature)
스캔이 끝나면 코어가 만든 줄 목록을 **모노 11px · `surface-sunken` 바탕 · `white-space: pre-wrap`**
으로 그대로 낸다. 프론트엔드가 다시 조립하지 않는다 — CLI 와 GUI 가 같은 결과를 다른 말로
설명하지 않게 하려는 것이다.

### Named Rules

**포커스 링은 하나가 소유한다 규칙.** 포커스 링은 전역 `:focus-visible` **한 곳**에서만 정의한다
(`2px solid accent-cyan`, offset 2px, 6px 모서리). 요소마다 다른 링을 만들지 않는다 — 그러면
「어디에 포커스가 있는가」를 눈이 매번 새로 배워야 한다.

**전환 없음 규칙.** 이 시스템에는 **`transition`·`animation`·`@keyframes` 선언이 하나도 없다**
(구현 전체 실측 0건). 상태 변화는 즉시 일어난다. 호버에 페이드를 붙이거나 카드를 슬라이드로
등장시키지 않는다 — 문서를 훑는 도구에서 지연은 응답성 손실로 읽히고, 「조용한 열람실」에서
움직이는 것은 그 자체로 소음이다. 모션을 도입하려면 시스템 차원의 결정으로 다루고 여기에 적는다.

## Do's and Don'ts

### Do:
- **Do** 새 색이 필요하면 **먼저 기존 26개 토큰에서 찾는다.** 토큰 밖의 색을 만들지 않는다.
- **Do** 세리프를 **값**(이름·제목·지표 숫자)에만 쓴다.
- **Do** 파일 경로·모델명·수치를 **모노**로 적는다. 사용자가 복사해 붙일 문자열이다.
- **Do** 구역을 **대문자 마이크로 라벨**(10~11px · 자간 0.06~0.08em)로 나눈다.
- **Do** 깊이를 **바탕색 3단계와 1px 선**으로 만든다.
- **Do** 호버·선택을 `surface-sunken`으로 **가라앉혀** 표현한다.
- **Do** 넓은 내용(표·캔버스·경로 목록)에 자기 컨테이너의 `overflow`를 준다.
- **Do** 클릭 가능한 모든 요소가 키보드로 닿고 전역 포커스 링을 받게 한다.
- **Do** 본문 대비비를 **AA(4.5:1) 이상**으로 유지한다.

### Don't:
- **Don't** 다크 배경 위에 형광 악센트를 쓰지 않는다. **버린 세계다.**
- **Don't** 글로우·네온·발광 효과를 쓰지 않는다. **버린 세계다.**
- **Don't** 반투명 글래스(`backdrop-filter`)를 쓰지 않는다. **버린 세계다.**
- **Don't** 그라데이션을 쓰지 않는다. 바탕은 단색이다.
- **Don't** `text-secondary`·`text-muted`를 더 흐리게 만들거나 이전 값으로 되돌리지 않는다 —
  대비비 실패에서 **한 번 재서 올린 값**이다.
- **Don't** 잉크 검정 주 버튼을 한 화면에 둘 이상 두지 않는다.
- **Don't** 장식이나 리듬을 위해 색을 얹지 않는다. 색은 상태만 말한다.
- **Don't** 호버를 그림자나 들어올림으로 표현하지 않는다.
- **Don't** 세리프를 본문·버튼·라벨에 쓰지 않는다.
- **Don't** 요소마다 별도의 포커스 링을 만들지 않는다.
- **Don't** 외부 CDN에서 폰트·스크립트·스타일을 불러오지 않는다. **Zero External CDN 은 이
  제품의 「문서가 기기를 안 떠난다」 약속의 일부이며 시각 취향이 아니다.**

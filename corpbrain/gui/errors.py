"""GUI 어댑터가 프로토콜 층에서 쓰는 예외 (v0.9 스펙 §4.3.2).

**코어 예외를 여기 두지 않는다.** 코어의 실패는 `CorpBrainError` 계층이 그대로 담고, 서버는
그것을 기반 클래스로 갈라 도메인(200)으로 내보낸다. 이 모듈에 있는 것은 코어를 부를 인자를
만들 수조차 없는 «요청의 모양» 문제뿐이다.

`api.py`가 아니라 별도 모듈인 이유는 `scan.py`가 이 예외를 올려야 하는데 `api.py`가 이미
`scan.py`를 import하기 때문이다 — 한쪽에 두면 순환 import가 된다.
"""

from __future__ import annotations

from corpbrain.core.errors import PreconditionError

__all__ = [
    "BadRequest",
    "DirectoryUnreadable",
    "GraphNotBuilt",
    "NothingScanned",
    "WikiNotFound",
]


class BadRequest(Exception):
    """요청 본문이 이 엔드포인트의 모양이 아니다 — **프로토콜 층** 사건(400)이다.

    값의 **타당성**(범위·존재)은 코어가 판정하고 그 실패는 도메인(200)이다(§4.3.3). 이것은
    그 앞 단계 — JSON으로 읽히지도 않거나 객체가 아니거나, 무엇을 스캔할지가 아예 지정되지
    않은 경우 — 로, 코어를 부를 인자를 만들 수조차 없다. 500으로 두면 「로그의 500 = 버그
    신호」가 사용자의 오타로 오염된다.
    """


class GraphNotBuilt(PreconditionError):
    """그래프 DB가 아직 없다 — 첫 실행의 정상 상태이지 손상이 아니다 (§5 · T11).

    코어는 그래프 DB의 **부재와 손상을 같은 `PreconditionError`로** 묶고 「파일을 지우고 다시
    scan 하세요」라고 안내한다. 그것은 `graph` **CLI**의 계약(부재도 exit 1)에 맞춰진 문구이고,
    GUI 첫 실행에서 그대로 내보내면 **만든 적도 없는 파일을 지우라는 안내**가 된다.

    `PreconditionError` 하위이므로 §4.3.2의 매핑에서 **도메인(200)** 그대로다. 갈라지는 것은
    상태코드가 아니라 **식별자**이며, 그래야 화면이 문자열을 파싱하지 않고 첫 실행을 가른다.
    """


class NothingScanned(PreconditionError):
    """`--out` 아래 위키가 하나도 없다 — 그래프 유무와 별개의 사실이다.

    그래프가 없어도 위키가 있으면 트리는 파일명으로 그려진다(§4.6.2 파생 결정). 그래서 이
    조건은 `GraphNotBuilt`와 다르고, 같은 이름으로 뭉치면 화면이 「다시 스캔하면 제목이
    채워집니다」와 「먼저 스캔하세요」를 구분하지 못한다.
    """


class WikiNotFound(PreconditionError):
    """지목한 `doc_id`의 위키가 `--out` 아래에 없다.

    위 둘과 달리 **지목이 잘못됐거나 산출물이 사라진** 경우다. v0.6이 `graph --neighbors`에서
    「존재를 전제한 식별자 지목의 실패는 빈 결과가 아니라 잘못된 지목」이라고 가른 것과 같다.
    """


class DirectoryUnreadable(PreconditionError):
    """열람하려는 디렉터리를 읽을 수 없다 — 없거나, 디렉터리가 아니거나, 권한이 없다.

    §5는 「열람 API가 접근할 수 없는 디렉터리: 권한 거부를 **그대로 보고하고 서버를 죽이지
    않는다**」로 정했다. `PermissionError`·`FileNotFoundError`는 `CorpBrainError`가 아니므로
    §4.3.2의 규칙대로면 **500**(버그)이 되는데, 사용자가 남의 폴더를 눌러 본 것은 버그가 아니다.
    도메인 상태로 옮겨 화면이 「읽을 수 없습니다」를 그리고 탐색을 계속하게 한다.
    """

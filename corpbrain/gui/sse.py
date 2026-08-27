"""SSE 프레임 직렬화와 이벤트 팬아웃 (v0.9 스펙 §4.3 · §4.10.3).

**두 축을 나눈다** — 「프레임 문법」은 `format_sse()` 순수 함수가, 「이벤트 시퀀스」는 코어의
`on_event` 가 각각 소유하고 각각 검증된다 (§3 항목4). 실제 서버를 띄워 스트림을 읽고
타임아웃으로 끊는 방식은 택하지 않았다 — 타임아웃 상수가 들어와 CI에서 가장 자주 깨지는
종류의 테스트가 된다.

**이벤트를 버퍼링해 리플레이하지 않는다** (§4.3). 브라우저 `EventSource`는 끊기면 자동
재연결하므로 재접속은 상시 사건이고, 버퍼 방식은 스캔 1회분 이벤트를 계속 쥐면서 상한·생애
정책이라는 결정을 새로 만든다. 대신 접속 즉시 **현재 스냅샷 1건**을 보낸다 — 서버는 이미
`reduce()`로 접어 둔 값을 들고 있으므로 추가 상태가 없고, 재연결이 몇 번이든 비용이 같다.
"""

from __future__ import annotations

import json
import queue
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from typing import Any

from corpbrain.core._progress import ProgressEvent, StatusSnapshot, reduce

__all__ = [
    "SSE_CONTENT_TYPE",
    "SSE_KEEPALIVE",
    "EventStream",
    "Subscriber",
    "format_sse",
    "snapshot_payload",
]

SSE_CONTENT_TYPE = "text/event-stream; charset=utf-8"

#: 프록시·브라우저가 유휴 연결을 끊지 않도록 보내는 주석 프레임. SSE 주석은 `EventSource`가
#: 무시하므로 프론트엔드에 판별 부담을 주지 않는다.
SSE_KEEPALIVE = ": keepalive\n\n"

#: 구독자 큐의 상한. 이 값을 넘기면 **가장 오래된 것부터 버린다** — 화면 하나가 느리다고
#: 스캔이 멈추면 안 된다. 잃는 것은 줄 단위 로그이고, 집계는 다음 스냅샷이 복원한다.
QUEUE_LIMIT = 1000


def format_sse(payload: dict[str, Any]) -> str:
    """dict 하나를 SSE 프레임 문자열로 만든다 — `data: <json>\\n\\n`.

    `event:` 필드를 쓰지 않는다. 프레임 문법이 두 갈래가 되면 이 함수의 계약과 그
    단위테스트가 함께 갈라진다 — 판별자는 **본문의 `kind`**가 진다 (§4.3).

    JSON은 한 줄로 직렬화한다. 값 안의 줄바꿈은 `json.dumps`가 `\\n`으로 이스케이프하므로
    프레임 경계(`\\n\\n`)를 깨뜨리지 않는다.
    """
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def snapshot_payload(snapshot: StatusSnapshot | None, *, running: bool) -> dict[str, Any]:
    """접속 직후 보내는 첫 프레임의 본문 (§4.3).

    **모든 프레임이 `kind`를 갖게** 한다 — 스냅샷은 `StatusSnapshot`이고 이후는
    `ProgressEvent.to_dict()`라 모양이 다른데, 후자에만 `kind`가 있어 프론트가 둘을 가를
    근거가 없다.

    `snapshot`이 `None`이면 이 프로세스에서 스캔이 한 번도 돌지 않은 것이다. 기본
    `StatusSnapshot()`을 대신 보내지 않는다 — 그 값의 `state`는 `"starting"`이라 화면이
    「곧 시작한다」로 읽는다.
    """
    return {
        "kind": "snapshot",
        "running": running,
        "snapshot": asdict(snapshot) if snapshot is not None else None,
    }


class Subscriber:
    """한 브라우저 연결에 대응하는 구독자 — 큐 하나를 소유한다."""

    def __init__(self) -> None:
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=QUEUE_LIMIT)

    def offer(self, payload: dict[str, Any]) -> None:
        """이벤트를 넣는다. 큐가 차 있으면 가장 오래된 것을 버리고 넣는다."""
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:  # pragma: no cover - 사이에 소비된 경우
                pass
            try:
                self._queue.put_nowait(payload)
            except queue.Full:  # pragma: no cover - 소비자가 더 느린 경우
                pass

    def get(self, timeout: float) -> dict[str, Any] | None:
        """다음 이벤트를 기다린다. 시간 안에 없으면 `None` (호출자가 keepalive를 낸다)."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def drain(self) -> list[dict[str, Any]]:
        """지금 큐에 있는 것을 **막히지 않고** 전부 꺼낸다.

        테스트가 이 메서드로 팬아웃을 단언한다 — 끝나지 않는 스트림을 통과시키지 않고,
        `sleep`·`Event`·`Barrier` 도 쓰지 않는다 (§3 항목4·6).
        """
        drained: list[dict[str, Any]] = []
        while True:
            try:
                drained.append(self._queue.get_nowait())
            except queue.Empty:
                return drained


class EventStream:
    """스캔 진행 상태의 단일 출처 — 스냅샷 하나와 구독자 집합을 쥔다.

    스캔 상태는 **서버가 소유하고 브라우저 세션이 소유하지 않는다** (§4.4). 새로고침·다른
    탭은 같은 스냅샷에 다시 붙는다.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshot: StatusSnapshot | None = None
        self._running = False
        self._subscribers: set[Subscriber] = set()

    @property
    def snapshot(self) -> StatusSnapshot | None:
        with self._lock:
            return self._snapshot

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def begin(self) -> None:
        """새 스캔 구간을 연다 — 이전 실행의 스냅샷을 버리고 진행 중으로 표시한다."""
        with self._lock:
            self._snapshot = None
            self._running = True

    def end(self) -> None:
        """스캔 구간을 닫는다. 마지막 스냅샷은 남겨 둔다 — 화면이 결과를 계속 보여 준다."""
        with self._lock:
            self._running = False

    def publish(self, event: ProgressEvent) -> None:
        """코어의 `on_event` 싱크 — 스냅샷을 접고 구독자에게 뿌린다.

        이 함수는 **표시 장치**이므로 실패해도 스캔이 계속되어야 한다. 코어의 `_emit`이
        `on_event`의 예외를 삼키는 것과 같은 이유이며, 그래서 여기서도 구독자 하나의
        문제가 다른 구독자·스캔에 번지지 않게 큐 넣기를 개별로 감싼다.
        """
        payload = event.to_dict()
        with self._lock:
            self._snapshot = reduce(self._snapshot, event)
            targets = list(self._subscribers)
        for subscriber in targets:
            subscriber.offer(payload)

    def current_frame(self) -> str:
        """지금 상태의 스냅샷 프레임. 구독과 함께 원자적으로 얻으려면 `attach()`를 쓴다."""
        with self._lock:
            return format_sse(snapshot_payload(self._snapshot, running=self._running))

    @contextmanager
    def attach(self) -> Iterator[tuple[str, Subscriber]]:
        """**스냅샷 확보와 구독 등록을 한 번의 락 안에서** 한다 (§4.3).

        둘을 따로 하면 그 사이에 `publish()`된 이벤트가 **어느 쪽에도 담기지 않아 영구히
        사라진다** — 스냅샷은 그 이벤트 이전에 찍혔고 구독자는 아직 없었기 때문이다. 서버는
        스냅샷을 다시 보내지 않으므로(리플레이 버퍼 없음) 그 화면은 끝까지 어긋난 채로 남는다.

        반대로 구독을 먼저 하고 스냅샷을 나중에 찍으면 같은 이벤트가 **두 번** 반영된다
        (스냅샷에 접힌 뒤 이벤트로 또 온다). 한 락 안에서 둘 다 하는 것만이 정확히 한 번을
        보장한다.
        """
        subscriber = Subscriber()
        with self._lock:
            frame = format_sse(snapshot_payload(self._snapshot, running=self._running))
            self._subscribers.add(subscriber)
        try:
            yield frame, subscriber
        finally:
            with self._lock:
                self._subscribers.discard(subscriber)

    @contextmanager
    def subscribe(self) -> Iterator[Subscriber]:
        """구독자를 등록하고, 블록을 벗어나면 반드시 해제한다."""
        with self.attach() as (_frame, subscriber):
            yield subscriber

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

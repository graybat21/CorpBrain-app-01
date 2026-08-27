"""스캔 워커 — 계량 결과 보관 · 워커 스레드 1개 · 협조적 취소 (v0.9 스펙 §4.3.4 · §4.4 · §4.7).

이 모듈은 **어댑터**다. 비즈니스 로직은 코어(`plan_scan`·`run_scan`)에 그대로 있고 여기서는
① 한 번에 하나만 돌게 지키고 ② 계량 결과를 재사용해도 되는지 판정하고 ③ 취소 술어를 코어에
넘기는 일만 한다.

**취소 술어는 순수 함수로 코어에 넘어간다** — 코어 시그니처에 `threading.Event`를 박지 않는다
(§4.7). 이 모듈이 `threading`을 쓰는 것은 어댑터의 사정이며, 코어에는 그 사실이 새지 않는다.
"""

from __future__ import annotations

import sys
import threading
import traceback
from dataclasses import dataclass, replace
from pathlib import Path

from corpbrain.core.config import ScanConfig
from corpbrain.core.models import ScanPlan, ScanResult
from corpbrain.core.pipeline import run_scan
from corpbrain.core.plan import plan_scan
from corpbrain.core.scanner import ScanFindings, scan_folder, validated_root
from corpbrain.gui.errors import BadRequest
from corpbrain.gui.sse import EventStream

__all__ = ["Measurement", "ScanController", "ScanInProgressError"]


class ScanInProgressError(RuntimeError):
    """이미 스캔이 도는데 새 스캔을 시작하려 했다 — 프로토콜 층 사건(409)이다.

    `CorpBrainError`가 **아니다.** 이것은 환경의 상태가 아니라 요청의 타이밍 문제이고,
    §4.3.2가 409를 프로토콜 층에 배정했다. 도메인(200)으로 접으면 화면이 「스캔이 시작됐다」와
    「이미 돌고 있다」를 같은 상태코드로 받는다.
    """


@dataclass(frozen=True)
class Measurement:
    """계량 1회의 결과와 **그 계량에 쓰인 설정** (§4.3.4).

    설정을 함께 들고 있는 것이 이 타입의 존재 이유다. `ScanPlan.gate`는 계량 시점 임계값으로
    **이미 내려진 판정**이고 `run_scan`의 방어는 「파일 수가 같은가」 하나뿐이라, 사용자가
    한도를 올려도 파일 수가 그대로면 낡은 판정이 그대로 쓰인다.
    """

    config: ScanConfig
    plan: ScanPlan
    findings: ScanFindings


class ScanController:
    """스캔 상태의 단일 출처 — 서버가 소유하고 브라우저 세션이 소유하지 않는다 (§4.4).

    새로고침·다른 탭에서 열면 진행 중인 스캔에 **다시 붙는다**.
    """

    def __init__(self, events: EventStream) -> None:
        self.events = events
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._cancel_requested = False
        self._measurement: Measurement | None = None
        self._result: ScanResult | None = None
        self._failure: BaseException | None = None

    # --- 상태 조회 ---------------------------------------------------------------

    @property
    def running(self) -> bool:
        """스캔이 도는 중인가 — 409 판정과 화면의 버튼 상태가 이 값 하나를 본다."""
        return self.events.running

    @property
    def cancel_requested(self) -> bool:
        """취소가 요청된 채로 아직 루프가 멈추지 않았는가 (화면의 「멈추는 중」 표시)."""
        return self._cancel_requested

    @property
    def result(self) -> ScanResult | None:
        """마지막으로 끝난 스캔의 결과. 한 번도 돌지 않았으면 `None`."""
        return self._result

    @property
    def failure(self) -> BaseException | None:
        """마지막 스캔이 예외로 끝났다면 그 예외 — 워커 스레드에서 삼키지 않는다."""
        return self._failure

    @property
    def measurement(self) -> Measurement | None:
        """마지막 계량 결과. 화면이 「스캔 시작」을 누를 때까지 들고 있다."""
        return self._measurement

    # --- 계량 -------------------------------------------------------------------

    def measure(self, config: ScanConfig) -> Measurement:
        """계량한다 — LLM을 부르지 않는다 (§4.3.4 1단계).

        결과를 보관해 곧 이어지는 실행이 같은 일을 두 번 하지 않게 한다. 보관본을 쓸지는
        `_reusable()`이 정한다.
        """
        root = validated_root(config.folder)
        findings = scan_folder(root, max_files=None, out_dir=config.out_dir)
        plan = plan_scan(config, findings=findings)
        measurement = Measurement(config=config, plan=plan, findings=findings)
        self._measurement = measurement
        return measurement

    def _reusable(self, config: ScanConfig) -> Measurement | None:
        """보관된 계량을 이 설정에 그대로 쓸 수 있는가 (§4.3.4).

        **완전히 같은 `ScanConfig`일 때로 한정한다.** 다르면 `None`을 돌려주어 호출자가
        조용히 다시 계량하게 한다 — 게이트에 막힌 사용자가 「고급」을 펼쳐
        `max_total_tokens`를 올리고 「스캔 시작」을 눌러도 **여전히 막히는** 상황을 막는다.
        엔진을 local → cloud로 바꾼 경우도 같다(`gate.gpu_enforced`가 낡은 채 따라온다).

        이 판정을 코어에 넣지 않는다 — `run_scan`의 기존 방어는 「이 findings로 계산된
        plan인가」라는 **다른 질문**에 답하며, 「사용자가 폼을 만졌는가」는 어댑터가 아는
        사실이다.
        """
        held = self._measurement
        if held is None or held.config != config:
            return None
        return held

    # --- 실행 -------------------------------------------------------------------

    def start(self, config: ScanConfig) -> None:
        """워커 스레드 하나에서 스캔을 시작한다.

        Raises:
            ScanInProgressError: 이미 스캔이 도는 중 (→ 409).
        """
        with self._lock:
            if self.running or (self._thread is not None and self._thread.is_alive()):
                raise ScanInProgressError("이미 스캔이 진행 중입니다.")
            measurement = self._reusable(config) or self.measure(config)
            self._cancel_requested = False
            self._result = None
            self._failure = None
            # `begin()`을 **여기서** 부른다. 스레드 안에서 부르면 `start()`가 돌아온 직후의
            # 두 번째 요청이 아직 `running=False`를 보고 통과해, 「한 번에 하나」가 깨진다.
            self.events.begin()
            thread = threading.Thread(
                target=self._run,
                args=(config, measurement),
                name="corpbrain-scan",
                daemon=True,
            )
            self._thread = thread
            try:
                thread.start()
            except BaseException:
                # `begin()`은 이미 돌았다. 여기서 되돌리지 않으면 **`running`이 영원히 참**이
                # 되어 이후 모든 스캔 요청이 409로 막힌다 — 서버를 다시 띄우는 것 말고는
                # 빠져나올 길이 없는 상태다.
                self.events.end()
                raise

    def cancel(self) -> None:
        """취소를 요청한다 — 진행 중인 문서를 마친 뒤 멈춘다 (§4.7).

        진행 중인 HTTP 호출은 끊지 않으므로 요약 1건의 소켓 타임아웃(300초)만큼 기다릴 수
        있다. 프로세스를 kill하는 방식은 택하지 않는다 — sqlite 정리가 보장되지 않고 부분
        결과를 회수할 길이 없다.
        """
        self._cancel_requested = True

    def _should_cancel(self) -> bool:
        """코어에 넘기는 **순수 술어** — 플래그를 읽기만 한다 (§4.7)."""
        return self._cancel_requested

    def _run(self, config: ScanConfig, measurement: Measurement) -> None:
        try:
            self._result = run_scan(
                config,
                on_event=self.events.publish,
                findings=measurement.findings,
                plan=measurement.plan,
                should_cancel=self._should_cancel,
            )
        except BaseException as exc:  # noqa: BLE001 — 상태로 옮겨 담고 스레드를 끝낸다
            # 워커 스레드에서 예외가 그대로 죽으면 아무도 그것을 보지 못한다. 상태로 옮겨
            # 담아 다음 조회 요청이 §4.3.2의 매핑 규칙을 그대로 적용하게 한다.
            self._failure = exc
            # **터미널에도 남긴다.** 상태 응답은 §4.3.2대로 도메인이면 안내 문장, 버그면
            # 500이 되는데, 500 본문에는 트레이스백이 실리지 않는다(사용자에게 보일 것이
            # 아니다). 포그라운드로 떠 있는 서버의 터미널이 그 트레이스백이 갈 곳이다 —
            # 「로그의 500 = 버그 신호」가 실제로 추적 가능하려면 로그에 근거가 있어야 한다.
            traceback.print_exception(exc, file=sys.stderr)
        finally:
            self.events.end()
            self._cancel_requested = False


def config_from_payload(payload: dict[str, object], *, default_out: Path) -> ScanConfig:
    """요청 본문을 `ScanConfig`로 옮긴다 — **검증하지 않는다** (§4.3.3).

    값을 그대로 코어에 넘긴다. `validate_graph_decay()`·`parse_expand_edges()`가 이미 코어에
    있고, v0.7 §4.4가 「규칙이 한 곳에만 있어야 코어를 직접 부르는 후속 어댑터도 같은 보호를
    받는다」고 정한 그 후속 어댑터가 이 GUI다.

    여기서 하는 일은 **타입 옮기기**뿐이다 — JSON에는 `Path`가 없고 숫자가 문자열로 올 수
    있다. 값의 타당성(범위·존재)은 전부 코어가 판정한다.
    """
    folder = payload.get("folder")
    if not isinstance(folder, str) or not folder:
        # 폴더는 다른 필드와 달리 **없으면 무엇을 스캔할지가 정해지지 않는다.** 이것은 값의
        # 타당성이 아니라 요청의 형태 문제이므로 어댑터가 가른다 (400).
        raise BadRequest("스캔할 폴더를 지정하세요.")
    base = ScanConfig(folder=Path(folder).expanduser())
    out_dir = payload.get("out_dir")
    fields: dict[str, object] = {
        "out_dir": Path(str(out_dir)).expanduser() if out_dir else default_out,
    }
    for name in (
        "model", "embed_model", "ollama_url", "engine", "cloud_model",
    ):
        if (value := payload.get(name)) is not None:
            fields[name] = str(value)
    for name in (
        "max_files", "max_chars", "max_file_size", "max_total_tokens", "related_top_k",
    ):
        if (value := payload.get(name)) is not None:
            fields[name] = int(value)  # type: ignore[arg-type]
    for name in ("force", "force_gates"):
        if (value := payload.get(name)) is not None:
            fields[name] = bool(value)
    if (value := payload.get("similarity_threshold")) is not None:
        fields["similarity_threshold"] = float(value)  # type: ignore[arg-type]
    return replace(base, **fields)  # type: ignore[arg-type]

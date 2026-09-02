"""스캔 자식 프로세스의 수명 관리 (v0.9 스펙 §4.3 · §4.4 · §5).

서버는 스캔을 **직접 돌리지 않는다.** `corpbrain.gui.runner`를 별도 프로세스로 띄우고,
그 stdout의 JSON 라인을 읽어 `_progress.reduce()`로 접어 스냅샷 하나로 보관한다. 브라우저는
그 스냅샷을 1초마다 폴링한다 (§4.3 — SSE를 쓰지 않는다).

**동시 스캔은 전체에서 1개만** 허용한다 (§5). 같은 `out_dir`에 두 스캔이 붙는 것을 막는
장치가 코어에 없다.

**중지는 프로세스 종료**다. 코어에 협조적 취소 이음새가 없으므로 다른 방법이 없다.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from corpbrain.core import _progress as _p
from corpbrain.core._progress import ProgressEvent, StatusSnapshot, reduce
from corpbrain.gui import runner

__all__ = ["ScanAlreadyRunningError", "ScanJob", "ScanJobManager", "snapshot_to_dict"]

#: 스캔이 끝난 뒤 진행바가 머무는 단계 이름. 코어는 그래프 단계에 이벤트를 내지 않으므로
#: (§5 「그래프 단계의 관측 공백」) 서버가 이 상태를 직접 표시한다.
PHASE_SUMMARIZING = "summarizing"
PHASE_GRAPH = "graph"
PHASE_DONE = "done"

#: 실패를 설명할 때 보관하는 자식 stderr 줄 수. 전부 들고 있을 이유가 없다.
STDERR_TAIL_LINES = 20


class ScanAlreadyRunningError(RuntimeError):
    """이미 스캔이 돌고 있다 — 서버가 409로 매핑한다 (§5)."""


def _child_env() -> dict[str, str]:
    """자식 프로세스 환경. **UTF-8 을 못박는다.**

    러너도 자기 스트림을 UTF-8 로 재구성하지만, 그 코드가 돌기 **전에** 죽는 경우
    (import 실패 등)의 트레이스백까지 읽으려면 인터프리터 수준에서 정해 두어야 한다.
    Windows 기본 코드페이지(cp949)로 한글이 나오면 부모의 UTF-8 디코딩이 깨진다.
    """
    return {**os.environ, "PYTHONIOENCODING": "utf-8"}


def _runner_command(workspace_id: str) -> list[str]:
    """자식 프로세스 명령줄. **우리 인터프리터로 우리 모듈만** 실행한다.

    테스트가 이 함수를 갈아 끼워 가짜 러너를 띄운다 — 실제 러너를 쓰면 Ollama 가 필요하다.
    """
    return [sys.executable, "-m", "corpbrain.gui.runner", workspace_id]


@dataclass
class ScanJob:
    """돌고 있거나 방금 끝난 스캔 하나."""

    workspace_id: str
    out_dir: Path
    phase: str = PHASE_SUMMARIZING
    snapshot: StatusSnapshot | None = None
    #: 파일별 생성·스킵 로그. 화면이 그대로 보여 준다.
    log: list[dict[str, Any]] = None  # type: ignore[assignment]
    record: dict[str, Any] | None = None
    error: str = ""
    #: 자식의 stderr 마지막 몇 줄 — 결과 없이 죽었을 때 이유를 설명한다.
    stderr_tail: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.log is None:
            self.log = []
        if self.stderr_tail is None:
            self.stderr_tail = []


def snapshot_to_dict(snapshot: StatusSnapshot | None) -> dict[str, Any] | None:
    """`StatusSnapshot`을 JSON이 되는 값으로 바꾼다.

    `render_status_line()`은 쓰지 않는다 — CLI 한 줄 텍스트 전용이며, GUI는 스냅샷 필드를
    화면에 직접 바인딩한다 (§4.3).
    """
    if snapshot is None:
        return None
    return {name: runner._plain(value) for name, value in runner._fields_of(snapshot)}


class ScanJobManager:
    """자식 프로세스 하나를 띄우고 그 출력을 접는다. 스레드 안전하다."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._job: ScanJob | None = None
        self._process: subprocess.Popen[str] | None = None
        self._reader: threading.Thread | None = None

    # --- 조회 -------------------------------------------------------------

    @property
    def running(self) -> bool:
        """**작업**이 아직 끝나지 않았는가.

        OS 의 프로세스 생존이 아니라 작업 상태로 정의한다 — 종료 레코드가 도착한 뒤에도
        자식이 거둬지기 전까지 짧은 창이 있어, `poll()` 로 정의하면 화면이 「끝났는데 아직
        도는 중」으로 보인다.
        """
        with self._lock:
            return self._job is not None and self._job.phase != PHASE_DONE

    def status(self) -> dict[str, Any] | None:
        """폴링 대상 스냅샷 (§4.3). 아직 한 번도 안 돌렸으면 `None`."""
        with self._lock:
            job = self._job
            if job is None:
                return None
            return {
                "workspace_id": job.workspace_id,
                "running": job.phase != PHASE_DONE,
                "phase": job.phase,
                "snapshot": snapshot_to_dict(job.snapshot),
                "log": list(job.log),
                "record": job.record,
                "error": job.error,
            }

    # --- 실행 -------------------------------------------------------------

    def start(self, *, workspace_id: str, payload: dict[str, Any]) -> None:
        """자식 프로세스를 띄운다.

        Raises:
            ScanAlreadyRunningError: 이미 돌고 있다 (§5 — 전체에서 1개만).
        """
        with self._lock:
            if self._job is not None and self._job.phase != PHASE_DONE:
                raise ScanAlreadyRunningError("이미 스캔이 실행 중입니다.")
            out_dir = Path(str(payload["out_dir"]))
            self._job = ScanJob(workspace_id=workspace_id, out_dir=out_dir)
            self._process = subprocess.Popen(
                _runner_command(workspace_id),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                # 깨진 바이트 하나가 펌프 스레드를 죽여 결과를 통째로 잃지 않게 한다.
                # 러너가 UTF-8 을 강제하므로 정상 경로에서는 쓰이지 않는 안전망이다.
                errors="replace",
                env=_child_env(),
            )
            process = self._process

        assert process.stdin is not None
        process.stdin.write(json.dumps(payload, ensure_ascii=False))
        process.stdin.close()

        # **stderr 를 반드시 읽어야 한다.** 읽지 않으면 두 가지가 동시에 나빠진다 —
        # 파이프 버퍼가 차면 자식이 쓰기에서 멈추고(교착), 자식이 왜 죽었는지도 사라져
        # 화면에는 「결과 없이 종료」만 남는다.
        threading.Thread(target=self._drain_stderr, args=(process,), daemon=True).start()
        self._reader = threading.Thread(target=self._pump, args=(process,), daemon=True)
        self._reader.start()

    def stop(self) -> bool:
        """돌고 있는 스캔을 중지한다. 실제로 멈췄으면 `True`.

        이미 만들어진 위키는 남고 인덱스 커밋은 유실된다 — 다음 스캔이 복구한다 (§5).
        """
        with self._lock:
            process = self._process
        if process is None or process.poll() is not None:
            return False
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        with self._lock:
            if self._job is not None:
                self._job.phase = PHASE_DONE
                self._job.error = "사용자가 중지했습니다."
        return True

    def shutdown(self) -> None:
        """서버가 내려갈 때 자식도 함께 종료한다 (§5).

        고아 프로세스가 인덱스 락을 쥔 채 남으면 다음 실행이 이유 없이 막힌다.
        """
        self.stop()

    # --- 내부 -------------------------------------------------------------

    def _drain_stderr(self, process: subprocess.Popen[str]) -> None:
        """자식의 stderr를 계속 비우고 마지막 몇 줄을 보관한다."""
        assert process.stderr is not None
        try:
            for line in process.stderr:
                text = line.rstrip()
                if not text:
                    continue
                with self._lock:
                    if self._job is not None:
                        self._job.stderr_tail.append(text)
                        del self._job.stderr_tail[:-STDERR_TAIL_LINES]
        except (OSError, ValueError):
            return

    def _pump(self, process: subprocess.Popen[str]) -> None:
        """자식의 stdout을 한 줄씩 읽어 스냅샷으로 접는다.

        **어떤 실패도 이 스레드 밖으로 새지 않는다.** 새면 스레드가 조용히 죽어 작업이
        영원히 「진행 중」으로 남고, 화면의 진행바가 멈춘 채 돌아오지 않는다.
        """
        crash = ""
        try:
            assert process.stdout is not None
            for raw in process.stdout:
                line = raw.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self._absorb(payload)
        except Exception as exc:  # noqa: BLE001 - 관측이 처리를 깨지 않는다
            crash = f"자식 출력을 읽지 못했습니다: {exc}"
        finally:
            with suppress(OSError, ValueError):
                process.wait(timeout=10)

        with self._lock:
            job = self._job
            if job is None or job.record is not None or job.error:
                return
            # 결과 없이 끝났다 — **왜 그런지 말해 준다.** stderr 를 버리면 사용자에게는
            # 원인 없는 실패만 남는다.
            code = process.poll()
            detail = crash or "\n".join(job.stderr_tail).strip()
            job.error = (
                f"스캔 프로세스가 결과 없이 종료했습니다 (종료 코드 {code})."
                + (f"\n{detail}" if detail else "")
            )
            job.phase = PHASE_DONE

    def _absorb(self, payload: dict[str, Any]) -> None:
        with self._lock:
            job = self._job
            if job is None:
                return
            if "schema" in payload:
                job.record = payload
                job.phase = PHASE_DONE
                job.error = str(payload.get("error", ""))
                return
            event = _event_from(payload)
            if event is not None:
                job.snapshot = reduce(job.snapshot, event)
            kind = payload.get("kind")
            if kind in {"file_generated", "file_skipped"}:
                job.log.append(payload)
            if kind == "run_finished":
                # 파일 루프가 끝났는데 아직 종료 레코드가 없다 = 패스2·패스3이 도는 중이다.
                # 코어는 이 구간에 이벤트를 내지 않으므로 서버가 표시를 바꿔 준다 (§5).
                job.phase = PHASE_GRAPH


#: 이벤트 종류 → 클래스. **명시적으로 적는다.**
#:
#: `ProgressEvent.kind`는 클래스 속성이 아니라 **인스턴스 프로퍼티**라, 클래스를 훑어
#: `kind`를 비교하는 방식은 프로퍼티 객체를 비교하게 되어 언제나 빗나간다. `_progress`가
#: `to_dict()`만 제공하고 역변환을 두지 않았으므로 여기서 짝을 맞춘다.
_EVENT_CLASSES: dict[str, type[ProgressEvent]] = {
    str(_p.EventKind.RUN_STARTED): _p.RunStarted,
    str(_p.EventKind.MODEL_LOADING): _p.ModelLoading,
    str(_p.EventKind.MODEL_READY): _p.ModelReady,
    str(_p.EventKind.FILE_STARTED): _p.FileStarted,
    str(_p.EventKind.FILE_STAGE): _p.FileStage,
    str(_p.EventKind.FILE_GENERATED): _p.FileGenerated,
    str(_p.EventKind.FILE_SKIPPED): _p.FileSkipped,
    str(_p.EventKind.RUN_FINISHED): _p.RunFinished,
}


def _event_from(payload: dict[str, Any]) -> ProgressEvent | None:
    """JSON 한 줄을 `ProgressEvent`로 되돌린다.

    모르는 종류나 모양이 어긋난 줄은 조용히 버린다 — 관측이 처리를 깨지 않는다는 방침
    그대로다.
    """
    event_class = _EVENT_CLASSES.get(str(payload.get("kind", "")))
    if event_class is None:
        return None
    fields = {key: value for key, value in payload.items() if key != "kind"}
    if event_class is _p.FileStage and "stage" in fields:
        # `to_dict()`가 StrEnum을 문자열로 눕혔으므로 되세운다.
        try:
            fields["stage"] = _p.Stage(fields["stage"])
        except ValueError:
            return None
    try:
        return event_class(**fields)
    except TypeError:
        return None

"""Tk-free UDP receiver that emits immutable queue events."""

from __future__ import annotations

from dataclasses import dataclass
import queue
import socket
import threading

try:
    from .vled_protocol import MAX_DATAGRAM_BYTES, ProtocolError, VledState, parse_datagram
except ImportError:  # Direct script execution from simulator/.
    from vled_protocol import MAX_DATAGRAM_BYTES, ProtocolError, VledState, parse_datagram


@dataclass(frozen=True, slots=True)
class StateEvent:
    state: VledState
    address: tuple[str, int]


@dataclass(frozen=True, slots=True)
class ErrorEvent:
    reason: str
    address: tuple[str, int] | None = None


@dataclass(frozen=True, slots=True)
class ListenerEvent:
    status: str
    address: tuple[str, int] | None = None


ReceiverEvent = StateEvent | ErrorEvent | ListenerEvent


class UdpReceiver:
    """Receive UDP on a worker thread without importing or calling Tk."""

    def __init__(
        self,
        events: queue.Queue[ReceiverEvent],
        host: str = "0.0.0.0",
        port: int = 9000,
        socket_timeout: float = 0.2,
    ) -> None:
        self._events = events
        self._host = host
        self._port = port
        self._socket_timeout = socket_timeout
        self._stop_event = threading.Event()
        self._socket: socket.socket | None = None
        self._socket_lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("receiver is already running")
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="vled-udp-receiver",
            daemon=False,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        with self._socket_lock:
            current_socket = self._socket
        if current_socket is not None:
            try:
                current_socket.close()
            except OSError:
                pass

    def join(self, timeout: float | None = None) -> bool:
        if self._thread is None:
            return True
        self._thread.join(timeout)
        return not self._thread.is_alive()

    @property
    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _emit(self, event: ReceiverEvent) -> None:
        try:
            self._events.put_nowait(event)
            return
        except queue.Full:
            pass

        try:
            self._events.get_nowait()
        except queue.Empty:
            pass
        try:
            self._events.put_nowait(event)
        except queue.Full:
            pass

    def _run(self) -> None:
        udp_socket: socket.socket | None = None
        try:
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            udp_socket.settimeout(self._socket_timeout)
            udp_socket.bind((self._host, self._port))
            with self._socket_lock:
                self._socket = udp_socket
            bound_host, bound_port = udp_socket.getsockname()[:2]
            self._emit(ListenerEvent("listening", (bound_host, bound_port)))

            while not self._stop_event.is_set():
                try:
                    payload, address = udp_socket.recvfrom(MAX_DATAGRAM_BYTES + 1)
                except socket.timeout:
                    continue
                except OSError as exc:
                    if not self._stop_event.is_set():
                        self._emit(ErrorEvent(f"socket receive failed: {exc}"))
                    break

                try:
                    state = parse_datagram(payload)
                except ProtocolError as exc:
                    self._emit(ErrorEvent(str(exc), address))
                else:
                    self._emit(StateEvent(state, address))
        except OSError as exc:
            self._emit(ErrorEvent(f"listener setup failed: {exc}"))
        finally:
            with self._socket_lock:
                self._socket = None
            if udp_socket is not None:
                try:
                    udp_socket.close()
                except OSError:
                    pass
            self._emit(ListenerEvent("stopped"))

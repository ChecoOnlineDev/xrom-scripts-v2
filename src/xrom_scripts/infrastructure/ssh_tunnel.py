"""Tunel SSH local usando paramiko direct-tcpip (forwarding de puerto)."""

import select
import socket
import threading

import paramiko

from xrom_scripts.config import Settings
from xrom_scripts.logger import setup_logger


class SSHTunnel:
    """Tunel local sobre una conexion SSH ya establecida."""

    def __init__(
        self,
        ssh_transport: paramiko.Transport,
        settings: Settings,
        remote_host: str = "127.0.0.1",
        remote_port: int = 3306,
        local_host: str = "127.0.0.1",
        local_port: int = 0,
    ) -> None:
        self.ssh_transport = ssh_transport
        self.settings = settings
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.local_host = local_host
        self.local_port = local_port

        self._server_socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self.local_bind_port: int | None = None
        self._logger = setup_logger(level=settings.log_level)

    def __enter__(self) -> "SSHTunnel":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    def start(self) -> None:
        self._logger.info(
            "Abriendo tunel SSH -> %s:%d...", self.remote_host, self.remote_port
        )
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.local_host, self.local_port))
        self._server_socket.listen(5)
        self.local_bind_port = self._server_socket.getsockname()[1]

        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

        self._logger.info(
            "Tunel activo: %s:%d -> %s:%d",
            self.local_host,
            self.local_bind_port,
            self.remote_host,
            self.remote_port,
        )

    def _serve(self) -> None:
        while not self._stop_event.is_set():
            readable, _, _ = select.select([self._server_socket], [], [], 0.5)
            if self._server_socket not in readable:
                continue
            try:
                client_sock, _ = self._server_socket.accept()
            except socket.error:
                continue
            handler = threading.Thread(
                target=self._handle_client,
                args=(client_sock,),
                daemon=True,
            )
            handler.start()

    def _handle_client(self, client_sock: socket.socket) -> None:
        channel: paramiko.Channel | None = None
        try:
            channel = self.ssh_transport.open_channel(
                "direct-tcpip",
                (self.remote_host, self.remote_port),
                client_sock.getpeername(),
                timeout=10,
            )
            if channel is None:
                client_sock.close()
                return

            while True:
                readable, _, _ = select.select([client_sock, channel], [], [], 1)
                if client_sock in readable:
                    data = client_sock.recv(8192)
                    if not data:
                        break
                    channel.sendall(data)
                if channel in readable:
                    data = channel.recv(8192)
                    if not data:
                        break
                    client_sock.sendall(data)
        except Exception:
            pass
        finally:
            try:
                client_sock.close()
            except Exception:
                pass
            if channel:
                try:
                    channel.close()
                except Exception:
                    pass

    def stop(self) -> None:
        self._logger.info("Cerrando tunel SSH...")
        self._stop_event.set()
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=5)
        self._logger.info("Tunel SSH cerrado.")

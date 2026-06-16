"""Cliente SSH basado en paramiko con context manager."""

import paramiko

from xrom_scripts.config import Settings
from xrom_scripts.logger import setup_logger


class SSHConnection:
    """Conexion SSH reutilizable. Soporta password o llave privada."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: paramiko.SSHClient | None = None
        self._logger = setup_logger(level=settings.log_level)

    def __enter__(self) -> "SSHConnection":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()

    @property
    def transport(self) -> paramiko.Transport:
        """Devuelve el transporte SSH activo."""
        if self._client is None:
            raise RuntimeError("La conexion SSH no esta activa.")
        transport = self._client.get_transport()
        if transport is None:
            raise RuntimeError("No se pudo obtener el transporte SSH.")
        return transport

    def connect(self) -> None:
        host = self.settings.ssh_host
        port = self.settings.ssh_port
        user = self.settings.ssh_user
        password = self.settings.ssh_password
        key_path = self.settings.ssh_key_path

        self._logger.info("Conectando SSH a %s:%d como '%s'...", host, port, user)

        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs = {
            "hostname": host,
            "port": port,
            "username": user,
            "timeout": 15,
            "banner_timeout": 15,
            "auth_timeout": 15,
            "look_for_keys": False,
            "allow_agent": False,
        }

        if key_path is not None:
            raw_key = key_path.get_secret_value()
            self._logger.info("Autenticacion SSH usando llave privada: %s", raw_key)
            connect_kwargs["key_filename"] = raw_key
        elif password is not None:
            self._logger.info("Autenticacion SSH usando contrasena.")
            connect_kwargs["password"] = password.get_secret_value()
        else:
            # No deberia ocurrir gracias a la validacion de pydantic
            raise ValueError("Debe proporcionar SSH_PASSWORD o SSH_KEY_PATH.")

        try:
            self._client.connect(**connect_kwargs)
            self._logger.info("Conexion SSH establecida correctamente.")
        except paramiko.AuthenticationException as exc:
            self._logger.error("Fallo de autenticacion SSH: %s", exc)
            raise
        except paramiko.SSHException as exc:
            self._logger.error("Error SSH: %s", exc)
            raise

    def disconnect(self) -> None:
        if self._client:
            try:
                self._client.close()
                self._logger.info("Conexion SSH cerrada.")
            except Exception as exc:
                self._logger.warning("Error al cerrar SSH: %s", exc)
            finally:
                self._client = None

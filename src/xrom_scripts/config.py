"""Configuracion centralizada con pydantic-settings y SecretStr."""

from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Contenedor de configuracion validada desde variables de entorno."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # SSH
    ssh_host: str = Field(..., description="Host del servidor SSH")
    ssh_port: int = Field(default=22, description="Puerto SSH")
    ssh_user: str = Field(..., description="Usuario SSH")
    ssh_password: SecretStr | None = Field(default=None, description="Contrasena SSH")
    ssh_key_path: SecretStr | None = Field(
        default=None, description="Ruta a la llave privada SSH"
    )

    # MySQL
    db_host: str = Field(default="127.0.0.1", description="Host MySQL (visto desde el servidor)")
    db_port: int = Field(default=3306, description="Puerto MySQL")
    db_user: str = Field(..., description="Usuario MySQL")
    db_password: SecretStr = Field(..., description="Contrasena MySQL")
    db_name: str = Field(..., description="Nombre de la base de datos target")

    # Logging
    log_level: str = Field(default="INFO", description="Nivel de logging")

    # Healthcheck
    healthcheck_table: str = Field(
        default="patio_autos", description="Tabla para probar conexion"
    )

    @model_validator(mode="after")
    def _check_ssh_auth(self) -> "Settings":
        """Valida que al menos password o llave este presente."""
        pw = self.ssh_password
        key = self.ssh_key_path
        if pw is None and key is None:
            raise ValueError(
                "Debe definir SSH_PASSWORD o SSH_KEY_PATH para autenticarse por SSH."
            )
        return self

    @field_validator("ssh_password", mode="before")
    @classmethod
    def _empty_password_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    @field_validator("ssh_key_path", mode="before")
    @classmethod
    def _empty_key_path_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("ssh_key_path")
    @classmethod
    def _validate_key_path(cls, v: SecretStr | None) -> SecretStr | None:
        if v is None:
            return v
        raw = v.get_secret_value()
        path = Path(raw)
        if not path.exists():
            raise ValueError(f"La llave SSH no existe: {raw}")
        # Verificar permisos seguros (0o600 es ideal)
        mode = path.stat().st_mode
        if mode & 0o077:
            import warnings

            warnings.warn(
                f"La llave SSH tiene permisos demasiado abiertos ({oct(mode)}). "
                "Se recomienda chmod 600.",
                stacklevel=2,
            )
        return v

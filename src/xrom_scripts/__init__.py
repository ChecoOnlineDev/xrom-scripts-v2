"""xrom-scripts — Infraestructura lista para scripts Python con SSH + MySQL."""

from xrom_scripts.config import Settings
from xrom_scripts.infrastructure.db_client import MySQLClient
from xrom_scripts.infrastructure.ssh_client import SSHConnection
from xrom_scripts.infrastructure.ssh_tunnel import SSHTunnel
from xrom_scripts.logger import setup_logger

__version__ = "0.1.0"
__all__ = ["Settings", "SSHConnection", "SSHTunnel", "MySQLClient", "setup_logger"]

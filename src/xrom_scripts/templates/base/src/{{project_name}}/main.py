"""Punto de entrada: healthcheck SSH -> Tunel -> MySQL."""

import sys

from xrom_scripts import Settings, SSHConnection, SSHTunnel, MySQLClient, setup_logger


def main() -> int:
    # 1. Cargar configuracion (pydantic valida automaticamente)
    try:
        cfg = Settings()
    except Exception as exc:
        print(f"[ERROR] Configuracion invalida: {exc}", file=sys.stderr)
        return 1

    logger = setup_logger(level=cfg.log_level)
    logger.info("=" * 60)
    logger.info("Iniciando healthcheck SSH + Tunel + MySQL")
    logger.info("=" * 60)

    try:
        # 2. Conectar SSH
        with SSHConnection(cfg) as ssh:
            # 3. Abrir tunel
            with SSHTunnel(
                ssh_transport=ssh.transport,
                settings=cfg,
                remote_host=cfg.db_host,
                remote_port=cfg.db_port,
            ) as tunnel:
                # 4. Conectar MySQL via tunel local
                db = MySQLClient(
                    host="127.0.0.1",
                    port=tunnel.local_bind_port,
                    user=cfg.db_user,
                    password=cfg.db_password.get_secret_value(),
                    database=cfg.db_name,
                    settings=cfg,
                )
                with db:
                    # 5. Healthcheck
                    rows = db.healthcheck(cfg.healthcheck_table, limit=3)
                    for row in rows:
                        logger.info("Fila: %s", row)

        logger.info("=" * 60)
        logger.info("Healthcheck completado exitosamente.")
        logger.info("=" * 60)
        return 0

    except Exception as exc:
        logger.error("Error durante el healthcheck: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())

# Documentacion Tecnica: xrom-scripts

## 1. Vision general

`xrom-scripts` es un paquete Python que encapsula la infraestructura repetitiva necesaria para conectar scripts a servidores remotos via SSH y bases de datos MySQL. Expone cinco componentes principales: configuracion validada (`Settings`), logging (`setup_logger`), cliente SSH (`SSHConnection`), tunel SSH (`SSHTunnel`) y cliente MySQL (`MySQLClient`).

El CLI `xrom-new` genera proyectos **standalone** que declaran `xrom-scripts` como dependencia externa, eliminando la duplicacion de codigo de infraestructura en cada script.

## 2. Flujo de conexion paso a paso

El siguiente diagrama describe la cadena completa desde la carga de variables de entorno hasta la ejecucion de un query de prueba:

```
┌─────────────┐
│   .env      │  ← Variables de entorno (host, user, password, db, etc.)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Settings   │  ← pydantic-settings valida tipos, convierte strings vacios
│  (config)   │    a None, verifica que exista password o llave SSH,
└──────┬──────┘    y valida permisos de la llave si se usa.
       │
       ▼
┌─────────────┐
│ SSHConnection│ ← paramiko.SSHClient
│  (ssh_client)│   • set_missing_host_key_policy(AutoAddPolicy)
│              │   • look_for_keys=False, allow_agent=False
│              │   • Autentica por password o key_filename
│              │   • Expone propiedad `transport` (paramiko.Transport)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  SSHTunnel  │ ← Crea socket local AF_INET en 127.0.0.1:0 (puerto dinamico)
│ (ssh_tunnel)│   • Lanza thread daemon con select.select para accept()
│              │   • Por cada conexion entrante, abre channel direct-tcpip
│              │     sobre el transporte SSH activo
│              │   • Forwarding bidireccional: local socket <-> paramiko.Channel
│              │   • Propiedad `local_bind_port` indica el puerto asignado
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  MySQLClient│ ← pymysql.connect + DictCursor
│  (db_client)│   • Conecta a 127.0.0.1:puerto_del_tunnel
│              │   • charset=utf8mb4, autocommit=True
│              │   • Metodo healthcheck(table, limit) ejecuta SELECT
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Result    │ ← Filas como list[dict] gracias a DictCursor
│   (rows)    │
└─────────────┘
```

## 3. Descripcion tecnica de cada modulo

### 3.1 `config.py` — Settings

- **Base**: `pydantic_settings.BaseSettings`
- **Entrada**: Archivo `.env` en el directorio de ejecucion.
- **Validacion**:
  - `model_validator` garantiza que al menos `ssh_password` o `ssh_key_path` este presente.
  - `field_validator` para `ssh_password` y `ssh_key_path` convierte strings vacios a `None`.
  - `field_validator` para `ssh_key_path` verifica existencia del archivo y emite warning si los permisos no son restrictivos (no 0o600).
- **Seguridad**: Todos los campos sensibles usan `pydantic.SecretStr`, evitando impresion accidental en logs o trazas.

### 3.2 `logger.py` — setup_logger

- Usa el modulo estandar `logging` de Python.
- `StreamHandler` dirigido a `sys.stdout`.
- Formato: `[YYYY-MM-DD HH:MM:SS] [LEVEL] mensaje`.
- Proteccion contra duplicacion de handlers si se invoca multiples veces.

### 3.3 `ssh_client.py` — SSHConnection

- **Context manager**: `__enter__` invoca `connect()`, `__exit__` invoca `disconnect()`.
- **Cliente**: `paramiko.SSHClient`
- **Politica de host keys**: `AutoAddPolicy()` (acepta cualquier host key; util para entornos controlados).
- **Timeouts**: 15 segundos para banner, auth y conexion general.
- **Autenticacion**:
  - Prioriza llave privada (`key_filename`) si `ssh_key_path` esta definido.
  - Fallback a password si no hay llave.
- **Exposicion del transporte**: La propiedad `transport` devuelve `paramiko.Transport` del cliente activo, necesario para el tunel.

### 3.4 `ssh_tunnel.py` — SSHTunnel

- **Context manager**: `__enter__` invoca `start()`, `__exit__` invoca `stop()`.
- **Socket local**: Crea un socket TCP en `127.0.0.1:0` (puerto 0 permite que el SO asigne uno dinamico).
- **Thread daemon**: `_serve()` usa `select.select` con timeout de 0.5s para aceptar conexiones sin bloquear indefinidamente.
- **Forwarding**: Por cada cliente que se conecta al socket local:
  1. Abre un channel `direct-tcpip` en el transporte SSH hacia `remote_host:remote_port`.
  2. Lanza un thread `_handle_client` que hace forwarding bidireccional de datos entre el socket local y el channel SSH usando `select.select` + `recv/sendall`.
- **Cierre**: `stop()` setea un `threading.Event`, cierra el socket servidor y espera a que el thread termine (timeout 5s).

### 3.5 `db_client.py` — MySQLClient

- **Context manager**: `__enter__` invoca `connect()`, `__exit__` invoca `disconnect()`.
- **Driver**: `pymysql` con `DictCursor` (retorna filas como diccionarios).
- **Charset**: `utf8mb4` para soporte completo de caracteres Unicode.
- **Timeouts**: connect 10s, read 60s, write 60s.
- **Autocommit**: Habilitado por defecto.
- **Healthcheck**: Metodo que ejecuta `SELECT * FROM {table} LIMIT {limit}` usando f-string segura para el nombre de tabla y placeholder para el limite.

## 4. Seguridad

- `.env` siempre en `.gitignore` (la plantilla base lo incluye).
- `SecretStr` oculta valores sensibles en logs y excepciones.
- `paramiko` configurado con `look_for_keys=False` y `allow_agent=False` para evitar autenticacion no intencional con agentes SSH del sistema.
- Validacion de permisos de llave privada (warning si no es 0o600).

## 5. Compatibilidad

- Todo uso de rutas es via `pathlib.Path` (cross-platform).
- No se usan comandos shell (`os.system`, `subprocess`) en la logica de conexion.
- Python minimo: 3.12.

## 6. Arquitectura del paquete

```
xrom-scripts/
├── pyproject.toml
├── README.md              # Guia de usuario
├── TECHNICAL.md           # Este documento
└── src/xrom_scripts/
    ├── __init__.py        # API publica
    ├── cli.py             # xrom-new (generador de proyectos)
    ├── config.py          # Settings
    ├── logger.py          # setup_logger
    └── infrastructure/
        ├── ssh_client.py  # SSHConnection
        ├── ssh_tunnel.py  # SSHTunnel
        └── db_client.py   # MySQLClient

# Proyecto generado por xrom-new:
mi_script/
├── pyproject.toml         # Depende de xrom-scripts
├── .env.example
├── .gitignore
├── README.md
├── GETTING_STARTED.md
└── src/mi_script/
    ├── __init__.py
    └── main.py            # Importa desde xrom-scripts
```

## 7. Distribucion: privado vs publico

### 7.1 Repositorio publico

Si el codigo no contiene secretos ni datos sensibles de la empresa, la forma mas simple es hacerlo publico en GitHub.

- Cambia la visibilidad del repositorio en GitHub: `Settings > Danger Zone > Change visibility > Public`.
- La URL de instalacion sigue siendo `git+https://...`.
- Cualquier colaborador puede instalar sin credenciales adicionales.

### 7.2 Repositorio privado

Si debe mantenerse privado, usa `git+ssh` en lugar de `git+https`:

```toml
# pyproject.toml del proyecto generado
dependencies = [
    "xrom-scripts @ git+ssh://git@github.com/ChecoOnlineDev/xrom-scripts-v2.git",
]
```

**Pasos para los colaboradores:**

1. Generar una llave SSH en su maquina:
   ```bash
   ssh-keygen -t ed25519 -C "usuario@xromsystems.com"
   ```
2. Agregar la llave publica a su cuenta de GitHub:
   `Settings > SSH and GPG keys > New SSH key`.
3. El dueno del repositorio debe agregarlos como colaborador:
   `GitHub > Repo > Settings > Manage access > Invite a collaborator`.
4. Al ejecutar `uv sync` o `uv pip install`, git usara automaticamente la llave SSH del agente del sistema.

**Seguridad:**
- Nunca incluyas tokens ni credenciales en `pyproject.toml` o `uv.lock`.
- Nunca compartas una llave SSH deploy key del repositorio; cada colaborador usa su propia llave personal.

## 8. Notas de implementacion

- **Sin `sshtunnel`**: El tunel se implementa con `paramiko.Transport.open_channel('direct-tcpip', ...)` directamente, eliminando la dependencia externa `sshtunnel` y dando control total sobre timeouts, threads y cierre.
- **Threading**: Cada conexion al socket local del tunel genera un thread efimero para el forwarding. El thread principal del tunel (`_serve`) es un daemon que solo acepta conexiones.
- **Error handling**: Las excepciones de paramiko y pymysql se propagan hacia arriba despues de loggearlas, permitiendo que el script llamador decida si abortar o continuar.
- **Template sin duplicacion**: El CLI `xrom-new` genera proyectos que dependen de `xrom-scripts` como paquete externo. No copia archivos de infraestructura. Si se corrige un bug en la libreria, todos los proyectos se actualizan con `uv pip install --upgrade`.

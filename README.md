# xrom-scripts

Libreria y CLI para conectar scripts Python a servidores remotos via SSH y bases de datos MySQL, sin repetir codigo de infraestructura.

## Instalacion

### Repositorio publico

```bash
uv pip install git+https://github.com/ChecoOnlineDev/xrom-scripts.git
```

O como dependencia en tu `pyproject.toml`:

```toml
dependencies = [
    "xrom-scripts @ git+https://github.com/ChecoOnlineDev/xrom-scripts.git",
]
```

### Repositorio privado

Si el repositorio es privado, usa `git+ssh` para que cada colaborador se autentique con su propia llave SSH de GitHub:

```toml
dependencies = [
    "xrom-scripts @ git+ssh://git@github.com/ChecoOnlineDev/xrom-scripts.git",
]
```

**Requisito:** cada colaborador debe tener su llave SSH agregada a su cuenta de GitHub y ser colaborador del repositorio.

---

## Configuracion (`Settings` y archivo `.env`)

`Settings` es la clase de configuracion. Lee automaticamente un archivo `.env` en la carpeta desde donde ejecutes el script y valida que todo este bien antes de conectar.

### Atributos de `Settings` (variables del `.env`)

| Atributo / Variable `.env` | Tipo | Requerido | Descripcion |
|---|---|---|---|
| `SSH_HOST` | `str` | Si | Direccion IP o dominio del servidor SSH al que te conectas. |
| `SSH_PORT` | `int` | No | Puerto del servidor SSH. Valor por defecto: `22`. |
| `SSH_USER` | `str` | Si | Nombre de usuario para la sesion SSH. |
| `SSH_PASSWORD` | `str` |* | Contrasena del usuario SSH. Usa `SecretStr`; nunca se imprime en logs. |
| `SSH_KEY_PATH` | `str` |* | Ruta absoluta a una llave privada SSH (ej. `/home/usuario/.ssh/id_rsa`). Si se define, se usa en lugar de la contrasena. |
| `DB_HOST` | `str` | No | Host de MySQL **visto desde el servidor SSH** (no desde tu PC). Si MySQL esta en el mismo servidor, dejalo como `127.0.0.1`. Valor por defecto: `127.0.0.1`. |
| `DB_PORT` | `int` | No | Puerto de MySQL. Valor por defecto: `3306`. |
| `DB_USER` | `str` | Si | Usuario de la base de datos MySQL. |
| `DB_PASSWORD` | `str` | Si | Contrasena del usuario MySQL. |
| `DB_NAME` | `str` | Si | Nombre de la base de datos a la que te vas a conectar. |
| `LOG_LEVEL` | `str` | No | Nivel de logging (`DEBUG`, `INFO`, `WARNING`, `ERROR`). Valor por defecto: `INFO`. |
| `HEALTHCHECK_TABLE` | `str` | No | Tabla que usa el metodo `healthcheck()` para probar la conexion. Valor por defecto: `patio_autos`. |

> *Debes definir al menos `SSH_PASSWORD` **o** `SSH_KEY_PATH`. Si ambos estan vacios, `Settings` lanza un error de validacion.

### Archivo `.env` minimo

```bash
SSH_HOST=mi-servidor.com
SSH_PORT=22
SSH_USER=root
SSH_PASSWORD=mi_password

DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=mi_password_db
DB_NAME=mi_base_de_datos
```

Tambien puedes usar llave privada en lugar de password:

```bash
SSH_KEY_PATH=/home/usuario/.ssh/id_rsa
```

---

## Uso rapido como libreria

Importa las clases, crea un objeto `Settings` (lee automaticamente tu `.env`), y abre las conexiones con `with`:

```python
from xrom_scripts import Settings, SSHConnection, SSHTunnel, MySQLClient

cfg = Settings()  # carga .env y valida credenciales

with SSHConnection(cfg) as ssh:
    with SSHTunnel(ssh.transport, cfg, cfg.db_host, cfg.db_port) as tunnel:
        db = MySQLClient(
            host="127.0.0.1",
            port=tunnel.local_bind_port,
            user=cfg.db_user,
            password=cfg.db_password.get_secret_value(),
            database=cfg.db_name,
            settings=cfg,
        )
        with db:
            rows = db.healthcheck("mi_tabla", limit=3)
            for row in rows:
                print(row)
```

Todo se cierra automaticamente al salir de los bloques `with`.

---

## API publica detallada

### `Settings`

Clase de configuracion basada en `pydantic_settings.BaseSettings`.

- **Uso:** `cfg = Settings()` lee el archivo `.env` y valida los campos.
- **Seguridad:** Los campos sensibles (`ssh_password`, `ssh_key_path`, `db_password`) usan `SecretStr`. Para obtener el valor real, llama `.get_secret_value()`.

---

### `SSHConnection`

Cliente SSH con context manager. Soporta autenticacion por password o llave privada.

**Parametros del constructor:**

| Parametro | Tipo | Descripcion |
|---|---|---|
| `settings` | `Settings` | Objeto de configuracion con los datos SSH. |

**Metodos principales:**

| Metodo | Descripcion |
|---|---|
| `connect()` | Abre la conexion SSH usando los datos de `settings`. |
| `disconnect()` | Cierra la conexion SSH. |
| `transport` | Propiedad. Devuelve el objeto `paramiko.Transport` activo, necesario para crear el tunel. Lanza error si no hay conexion activa. |

**Uso con `with`:**
```python
with SSHConnection(cfg) as ssh:
    # La conexion esta abierta aqui
    transport = ssh.transport
```

---

### `SSHTunnel`

Crea un tunel local (forwarding de puerto) sobre una conexion SSH ya establecida. El puerto local es dinamico.

**Parametros del constructor:**

| Parametro | Tipo | Requerido | Descripcion |
|---|---|---|---|
| `ssh_transport` | `paramiko.Transport` | Si | Transporte activo obtenido de `SSHConnection.transport`. |
| `settings` | `Settings` | Si | Objeto de configuracion (se usa para el logger). |
| `remote_host` | `str` | No | Host destino al que apunta el tunel (desde la perspectiva del servidor SSH). Valor por defecto: `127.0.0.1`. |
| `remote_port` | `int` | No | Puerto destino. Valor por defecto: `3306`. |
| `local_host` | `str` | No | IP local donde escucha el tunel. Valor por defecto: `127.0.0.1`. |
| `local_port` | `int` | No | Puerto local. Usa `0` para que el sistema operativo asigne uno automaticamente. Valor por defecto: `0`. |

**Atributos utiles:**

| Atributo | Descripcion |
|---|---|
| `local_bind_port` | `int` — Puerto local asignado por el sistema. Lo usas para conectar `MySQLClient`. |

**Metodos principales:**

| Metodo | Descripcion |
|---|---|
| `start()` | Abre el socket local y lanza el thread del tunel. |
| `stop()` | Senala el cierre del tunel, cierra el socket y espera que el thread termine. |

**Uso con `with`:**
```python
with SSHTunnel(ssh.transport, cfg, cfg.db_host, cfg.db_port) as tunnel:
    print(f"Tunel activo en el puerto local: {tunnel.local_bind_port}")
```

---

### `MySQLClient`

Cliente MySQL basado en `pymysql` con `DictCursor`. Las filas se devuelven como diccionarios en lugar de tuplas.

**Parametros del constructor:**

| Parametro | Tipo | Requerido | Descripcion |
|---|---|---|---|
| `host` | `str` | Si | Host de MySQL. Normalmente `"127.0.0.1"` si vas por tunel SSH. |
| `port` | `int` | Si | Puerto de MySQL. Normalmente es `tunnel.local_bind_port`. |
| `user` | `str` | Si | Usuario de MySQL. |
| `password` | `str` | Si | Contrasena de MySQL. Puedes obtenerla con `cfg.db_password.get_secret_value()`. |
| `database` | `str` | Si | Nombre de la base de datos. |
| `settings` | `Settings` | No | Objeto de configuracion para ajustar el nivel de logging. |

**Metodos principales:**

| Metodo | Descripcion |
|---|---|
| `connect()` | Abre la conexion a MySQL. |
| `disconnect()` | Cierra la conexion. |
| `healthcheck(table, limit=3)` | Ejecuta `SELECT * FROM {table} LIMIT {limit}` y devuelve una lista de diccionarios. Es util para probar que todo funciona. |

**Uso con `with`:**
```python
db = MySQLClient(host="127.0.0.1", port=3306, user="root", password="secret", database="test")
with db:
    rows = db.healthcheck("mi_tabla")
```

---

### `setup_logger(name, level)`

Crea un logger de consola estandarizado. Se usa internamente, pero puedes usarlo en tu propio script si quieres el mismo formato.

| Parametro | Tipo | Requerido | Descripcion |
|---|---|---|---|
| `name` | `str` | No | Nombre del logger. Valor por defecto: `"xrom-scripts"`. |
| `level` | `str` | No | Nivel de logging (`DEBUG`, `INFO`, etc.). Valor por defecto: `"INFO"`. |

```python
from xrom_scripts import setup_logger

logger = setup_logger("mi_script", "DEBUG")
logger.info("Hola mundo")
```

---

## Ejemplo completo: consultas propias

Aqui tienes un ejemplo real que conecta por SSH, abre un tunel, y luego ejecuta consultas SQL personalizadas (no solo `healthcheck`):

```python
from xrom_scripts import Settings, SSHConnection, SSHTunnel, MySQLClient

cfg = Settings()

with SSHConnection(cfg) as ssh:
    with SSHTunnel(ssh.transport, cfg, cfg.db_host, cfg.db_port) as tunnel:
        db = MySQLClient(
            host="127.0.0.1",
            port=tunnel.local_bind_port,
            user=cfg.db_user,
            password=cfg.db_password.get_secret_value(),
            database=cfg.db_name,
            settings=cfg,
        )
        with db:
            # ---------- CONSULTAS PERSONALIZADAS ----------

            # 1) SELECT: obtener filas como lista de diccionarios
            with db._connection.cursor() as cursor:
                cursor.execute("SELECT id, nombre, email FROM usuarios WHERE activo = %s", (1,))
                usuarios = cursor.fetchall()

                for u in usuarios:
                    print(f"Usuario: {u['nombre']} | Email: {u['email']}")

            # 2) INSERT: agregar un nuevo registro
            with db._connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO usuarios (nombre, email) VALUES (%s, %s)",
                    ("Juan Perez", "juan@example.com")
                )
                # pymysql tiene autocommit=True por defecto en este cliente,
                # pero si lo desactivas, recuerda hacer db._connection.commit()
                print(f"Insertado. ID nuevo: {cursor.lastrowid}")

            # 3) UPDATE: modificar registros
            with db._connection.cursor() as cursor:
                filas_afectadas = cursor.execute(
                    "UPDATE usuarios SET activo = %s WHERE id = %s",
                    (0, 42)
                )
                print(f"Filas actualizadas: {filas_afectadas}")
```

### Consejos importantes

- **Usa siempre placeholders (`%s`) en tus queries.** No concatenes strings directamente para evitar SQL Injection.
- **Accede al cursor via `db._connection.cursor()`.** Esto te da el control total para ejecutar cualquier query.
- **`fetchall()` devuelve una lista de diccionarios** gracias a `DictCursor`, por lo que puedes leer las columnas por nombre: `row['nombre']`.
- **Si cambias `autocommit` a `False`**, recuerda llamar `db._connection.commit()` despues de `INSERT`, `UPDATE` o `DELETE`.
- **Todo se cierra solo.** Al salir de los bloques `with`, el tunel, la conexion MySQL y la conexion SSH se cierran automaticamente.

---

## Uso como CLI (generar proyectos standalone)

Si prefieres un proyecto completo listo para usar:

```bash
# Instalar globalmente
uv tool install git+https://github.com/ChecoOnlineDev/xrom-scripts.git

# Crear un nuevo proyecto
xrom-new mi_script

# Entrar y seguir los pasos
cd mi_script
uv sync
cp .env.example .env
# Editar .env con tus credenciales
uv run python -m mi_script
```

Esto genera una carpeta con la estructura base. El proyecto importa `xrom-scripts` como dependencia; no copia la infraestructura.

---

## Requisitos

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) (recomendado)

---

## Licencia

Uso interno Xrom Systems.

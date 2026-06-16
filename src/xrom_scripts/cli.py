"""CLI xrom-new: genera proyectos Python con infraestructura SSH + MySQL lista."""

import argparse
import re
import sys
from pathlib import Path


def _is_valid_identifier(name: str) -> bool:
    """Valida que el nombre sea un identificador Python valido (snake_case)."""
    return bool(re.fullmatch(r"[a-z_][a-z0-9_]*", name))


def _render_template(source: Path, dest: Path, replacements: dict) -> None:
    """Copia un archivo reemplazando placeholders de texto."""
    content = source.read_text(encoding="utf-8")
    for old, new in replacements.items():
        content = content.replace(old, new)
    dest.write_text(content, encoding="utf-8")


def _copy_tree(src: Path, dst: Path, replacements: dict) -> None:
    """Copia recursivamente una carpeta de plantilla aplicando reemplazos."""
    for item in src.rglob("*"):
        if item.is_dir():
            continue

        # Calcular ruta relativa
        rel = item.relative_to(src)
        rel_str = str(rel)

        # Reemplazar nombres de directorio en la ruta
        for old, new in replacements.items():
            rel_str = rel_str.replace(old, new)

        # Si es .jinja, quitar extension .jinja del destino
        if item.suffix == ".jinja":
            rel_str = rel_str[: -len(".jinja")]

        dest_file = dst / rel_str
        dest_file.parent.mkdir(parents=True, exist_ok=True)

        # Renderizar contenido (aplicar reemplazos) en todos los archivos
        _render_template(item, dest_file, replacements)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genera un nuevo proyecto Python con SSH + MySQL listos."
    )
    parser.add_argument("project_name", help="Nombre del proyecto (snake_case).")
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directorio donde se creara el proyecto (default: .)",
    )
    args = parser.parse_args()

    project_name = args.project_name

    if not _is_valid_identifier(project_name):
        print(
            f"[ERROR] El nombre '{project_name}' no es valido. "
            "Usa solo letras minusculas, numeros y guiones bajos. "
            "Debe comenzar con una letra o guion bajo.",
            file=sys.stderr,
        )
        return 1

    output_dir = Path(args.output_dir).resolve()
    dest = output_dir / project_name

    if dest.exists():
        print(f"[ERROR] El directorio ya existe: {dest}", file=sys.stderr)
        return 1

    # Localizar plantilla base embebida en el paquete
    here = Path(__file__).parent.resolve()
    template_dir = here / "templates" / "base"

    if not template_dir.exists():
        print(f"[ERROR] No se encontro la plantilla en: {template_dir}", file=sys.stderr)
        return 1

    replacements = {
        "{{project_name}}": project_name,
        "{{PROJECT_NAME}}": project_name.upper(),
    }

    _copy_tree(template_dir, dest, replacements)

    # Generar GETTING_STARTED.md especifico para este proyecto
    getting_started = dest / "GETTING_STARTED.md"
    getting_started.write_text(
        f"""# Pasos para iniciar tu proyecto

1. Entra al directorio:
   cd {project_name}

2. Sincroniza dependencias y crea/actualiza el entorno virtual:
   uv sync

3. Configura tus credenciales:
   cp .env.example .env
   # Edita .env con tus datos reales

4. Ejecuta el healthcheck para validar conexion SSH -> Tunel -> MySQL:
   uv run python -m {project_name}

5. Implementa tu logica en src/{project_name}/ (por ejemplo, en main.py o modulos adicionales).""",
        encoding="utf-8",
    )

    print(f"[OK] Proyecto '{project_name}' creado en: {dest}")
    print(f"[INFO] Lee '{dest / 'GETTING_STARTED.md'}' para los siguientes pasos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Static integrity checks for the Metal Structure workbench."""

from __future__ import annotations

import ast
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_XML = PROJECT_ROOT / "package.xml"
PACKAGE_INIT = PROJECT_ROOT / "freecad" / "BancadaFCSteel" / "__init__.py"
CATALOG = (
    PROJECT_ROOT
    / "freecad"
    / "BancadaFCSteel"
    / "catalogs"
    / "gerdau_w_initial.json"
)

ESSENTIAL_FILES = (
    "package.xml",
    "README.md",
    "LICENSE",
    "freecad/BancadaFCSteel/__init__.py",
    "freecad/BancadaFCSteel/init_gui.py",
    "freecad/BancadaFCSteel/commands.py",
    "freecad/BancadaFCSteel/interactive/__init__.py",
    "freecad/BancadaFCSteel/interactive/member_controller.py",
    "freecad/BancadaFCSteel/interactive/draft_member_tool.py",
    "freecad/BancadaFCSteel/interactive/profile_options_widget.py",
    "freecad/BancadaFCSteel/member.py",
    "freecad/BancadaFCSteel/profile_catalog.py",
    "freecad/BancadaFCSteel/paths.py",
    "freecad/BancadaFCSteel/catalogs/gerdau_w_initial.json",
    "Resources/Icons/BancadaFCSteel.svg",
    "Resources/Icons/CreateMember.svg",
    "Resources/Icons/StructuralMember.svg",
)

REQUIRED_PROFILE_FIELDS = {
    "manufacturer",
    "family",
    "designation",
    "mass_per_m",
    "d",
    "bf",
    "tw",
    "tf",
    "area_cm2",
    "source",
}
POSITIVE_PROFILE_FIELDS = ("mass_per_m", "d", "bf", "tw", "tf", "area_cm2")


def package_version() -> str:
    root = ET.parse(PACKAGE_XML).getroot()
    version = root.find("{*}version")
    if version is None or not version.text or not version.text.strip():
        raise ValueError("package.xml não contém uma versão válida")
    return version.text.strip()


def python_package_version() -> str:
    tree = ast.parse(PACKAGE_INIT.read_text(encoding="utf-8"), filename=str(PACKAGE_INIT))
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    raise ValueError("__version__ não foi encontrada em __init__.py")


def catalog_profiles() -> list[dict]:
    payload = json.loads(CATALOG.read_text(encoding="utf-8"))
    profiles = payload.get("profiles")
    if not isinstance(profiles, list):
        raise ValueError("o catálogo não contém uma lista 'profiles'")
    return profiles


def run_checks() -> list[str]:
    errors: list[str] = []

    missing = [relative for relative in ESSENTIAL_FILES if not (PROJECT_ROOT / relative).is_file()]
    if missing:
        errors.append("arquivos essenciais ausentes: " + ", ".join(missing))

    try:
        manifest_version = package_version()
    except (ET.ParseError, OSError, ValueError) as exc:
        errors.append(f"package.xml inválido: {exc}")
        manifest_version = None

    try:
        internal_version = python_package_version()
    except (OSError, SyntaxError, ValueError) as exc:
        errors.append(f"versão Python inválida: {exc}")
        internal_version = None

    if manifest_version and internal_version and manifest_version != internal_version:
        errors.append(
            f"versões divergentes: package.xml={manifest_version}, __version__={internal_version}"
        )

    try:
        profiles = catalog_profiles()
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        errors.append(f"catálogo JSON inválido: {exc}")
        profiles = []

    if len(profiles) != 22:
        errors.append(f"quantidade de perfis incorreta: esperado 22, encontrado {len(profiles)}")

    designations: list[str] = []
    for index, profile in enumerate(profiles, start=1):
        if not isinstance(profile, dict):
            errors.append(f"perfil {index} não é um objeto JSON")
            continue
        missing_fields = sorted(REQUIRED_PROFILE_FIELDS.difference(profile))
        if missing_fields:
            errors.append(f"perfil {index} sem campos obrigatórios: {', '.join(missing_fields)}")
        designation = profile.get("designation")
        if isinstance(designation, str):
            designations.append(designation)
        for field in POSITIVE_PROFILE_FIELDS:
            value = profile.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                errors.append(
                    f"perfil {index} possui valor não positivo ou não numérico em {field}: {value!r}"
                )

    duplicates = sorted(
        designation for designation in set(designations) if designations.count(designation) > 1
    )
    if duplicates:
        errors.append("designações duplicadas: " + ", ".join(duplicates))

    for path in sorted(PROJECT_ROOT.rglob("*.py")):
        try:
            source = path.read_text(encoding="utf-8")
            compile(source, str(path), "exec")
        except (OSError, SyntaxError, UnicodeError) as exc:
            errors.append(f"Python inválido em {path.relative_to(PROJECT_ROOT)}: {exc}")

    return errors


def main() -> int:
    errors = run_checks()
    if errors:
        print("FALHA: verificações do projeto encontraram problemas:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("OK: package.xml é XML válido.")
    print("OK: package.xml e __version__ indicam a mesma versão.")
    print("OK: catálogo inicial é JSON válido e contém exatamente 22 perfis.")
    print("OK: designações são únicas e todos os perfis possuem campos e valores válidos.")
    print("OK: todos os arquivos Python compilam sintaticamente.")
    print("OK: todos os arquivos essenciais existem.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

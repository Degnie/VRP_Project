"""
Extrae los IDs de regla/escenario de SPEC.md y verifica que cada uno tenga al
menos un test anotado con `spec: <ID>` (docstring o comentario en la línea
previa), salvo los marcados `spec: PENDIENTE` a propósito (cuarentena, ver
docs/plan-adopcion.md sección 3).

Uso: python scripts/check_traceability.py
Exit 0 si todo trazado, 1 si hay reglas de SPEC.md sin ningún test.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
ID_PATTERN = re.compile(r"\b(?:RN|CU|EC|RNF)(?:-[A-Z]+)?-\d+\b")


def extract_spec_ids() -> set[str]:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    return set(ID_PATTERN.findall(spec_text))


def extract_annotated_ids() -> set[str]:
    found = set()
    for test_file in (ROOT / "tests").rglob("*.py"):
        text = test_file.read_text(encoding="utf-8")
        for line in re.finditer(r"spec:\s*(.+)", text):
            found.update(ID_PATTERN.findall(line.group(1)))
    return found


def extract_pending_ids() -> set[str]:
    """IDs anotados explícitamente `spec: PENDIENTE` (cuarentena a propósito)."""
    found = set()
    for test_file in (ROOT / "tests").rglob("*.py"):
        text = test_file.read_text(encoding="utf-8")
        for match in re.finditer(r"spec:\s*PENDIENTE.*", text):
            found.update(ID_PATTERN.findall(match.group(0)))
    return found


def main() -> int:
    spec_ids = extract_spec_ids()
    annotated_ids = extract_annotated_ids()
    pending_ids = extract_pending_ids()
    missing = sorted(spec_ids - annotated_ids - pending_ids)

    print(f"IDs en SPEC.md: {len(spec_ids)}")
    print(f"IDs anotados en tests/: {len(annotated_ids)}")

    if missing:
        print("\nReglas de SPEC.md SIN ningún test que las cubra:")
        for rule_id in missing:
            print(f"  - {rule_id}")
        return 1

    print("\nTodas las reglas de SPEC.md tienen al menos un test anotado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

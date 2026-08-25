"""Manual FreeCAD-console check for Structural Grid FCStd persistence.

Run with this repository's ``freecad`` directory available on ``sys.path``.
This is intentionally excluded from the standard unittest discovery suite.
"""

from __future__ import annotations

import os
import tempfile

import FreeCAD as App

from SteelStructures.grid import create_grid


def run():
    handle, path = tempfile.mkstemp(prefix="metal_structure_grid_", suffix=".FCStd")
    os.close(handle)
    document = None
    reopened = None
    try:
        document = App.newDocument("GridPlacementPersistence")
        grid = create_grid(document)
        placement = App.Placement(grid.Placement)
        placement.Base.z = 3000.0
        grid.Placement = placement
        document.recompute()
        document.saveAs(path)
        App.closeDocument(document.Name)
        document = None

        reopened = App.openDocument(path)
        restored = reopened.getObject("StructuralGrid")
        assert restored is not None, "StructuralGrid was not restored"
        assert abs(restored.Placement.Base.z - 3000.0) < 1e-7, restored.Placement
        print("OK: Grid Placement.Base.z persisted at 3000 mm")
    finally:
        for candidate in (reopened, document):
            if candidate is not None:
                try:
                    App.closeDocument(candidate.Name)
                except Exception:
                    pass
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    run()

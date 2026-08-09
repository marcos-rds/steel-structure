# SPDX-License-Identifier: LGPL-2.1-or-later
"""Controls specific to one-click vertical column creation."""

from PySide import QtWidgets

from .profile_options_widget import ProfileOptionsWidget


DEFAULT_COLUMN_HEIGHT = 3000.0
MIN_COLUMN_HEIGHT = 0.01


def column_top(base, height):
    """Return the top point using the global +Z contract."""
    if float(height) <= 0.0:
        raise ValueError("A altura do pilar deve ser maior que zero.")
    return base.add(type(base)(0.0, 0.0, float(height)))


class ColumnTaskPanel(QtWidgets.QGroupBox):
    """Compose existing profile controls with column-only geometry controls."""

    def __init__(self, document, on_preview_changed=None, parent=None):
        super().__init__("Pilar", parent)
        self.profile_options = ProfileOptionsWidget(document, element_types=("Pilar",))
        self.profile_options.element_type.setCurrentText("Pilar")
        self.profile_options.element_type.setEnabled(False)

        self.height = QtWidgets.QDoubleSpinBox()
        self.height.setDecimals(2)
        self.height.setRange(MIN_COLUMN_HEIGHT, 1000000.0)
        self.height.setSuffix(" mm")
        self.height.setValue(DEFAULT_COLUMN_HEIGHT)

        layout = QtWidgets.QVBoxLayout(self)
        geometry = QtWidgets.QGroupBox("Geometria")
        geometry_form = QtWidgets.QFormLayout(geometry)
        geometry_form.addRow("Altura:", self.height)
        layout.addWidget(geometry)
        layout.addWidget(self.profile_options)

        if on_preview_changed is not None:
            self.height.valueChanged.connect(on_preview_changed)
            self.profile_options.profile.currentIndexChanged.connect(on_preview_changed)
            self.profile_options.insertion.currentIndexChanged.connect(on_preview_changed)
            self.profile_options.rotation.valueChanged.connect(on_preview_changed)
            self.profile_options.color_button.clicked.connect(on_preview_changed)

    @property
    def height_value(self):
        return float(self.height.value())

    def creation_options(self, base):
        return self.profile_options.creation_options(
            base, column_top(base, self.height_value)
        )

    def creation_succeeded(self, next_name):
        self.profile_options.creation_succeeded(next_name)


__all__ = [
    "ColumnTaskPanel", "DEFAULT_COLUMN_HEIGHT", "MIN_COLUMN_HEIGHT", "column_top"
]

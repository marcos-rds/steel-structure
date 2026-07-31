# SPDX-License-Identifier: LGPL-2.1-or-later
"""Structural profile controls embedded below the native Draft point UI."""

from PySide import QtGui, QtWidgets

from .. import profile_catalog
from ..member import ELEMENT_TYPES, INSERTION_OPTIONS
from .member_controller import MemberCreationOptions, compact_profile_designation, next_default_label


class ProfileOptionsWidget(QtWidgets.QGroupBox):
    """Profile-only controls; all point input remains owned by Draft."""

    def __init__(self, document, parent=None):
        super().__init__("Opções do perfil", parent)
        self.document = document
        self.setCheckable(True)
        self.setChecked(True)
        self._name_custom = False
        self._programmatic_name = False
        self._color = QtGui.QColor(184, 184, 194)
        form = QtWidgets.QFormLayout(self)
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.textEdited.connect(self._mark_custom_name)
        self.element_type = QtWidgets.QComboBox()
        self.element_type.addItems(ELEMENT_TYPES)
        self.element_type.setCurrentText("Membro")
        self.element_type.currentTextChanged.connect(self.refresh_automatic_name)
        self.category = QtWidgets.QComboBox()
        self.category.addItems(profile_catalog.categories())
        self.category.currentTextChanged.connect(self._category_changed)
        self.series = QtWidgets.QComboBox()
        self.series.currentTextChanged.connect(self._series_changed)
        self.profile = QtWidgets.QComboBox()
        self.profile.currentTextChanged.connect(self.refresh_automatic_name)
        self.insertion = QtWidgets.QComboBox()
        self.insertion.addItems(INSERTION_OPTIONS)
        self.rotation = QtWidgets.QDoubleSpinBox()
        self.rotation.setRange(-3600.0, 3600.0)
        self.rotation.setDecimals(2)
        self.rotation.setSuffix("°")
        self.color_button = QtWidgets.QPushButton("Escolher cor")
        self.color_button.clicked.connect(self._choose_color)
        self._update_color_button()
        for label, widget in (("Nome:", self.name_edit), ("Tipo do elemento:", self.element_type),
            ("Categoria do perfil:", self.category), ("Série do perfil:", self.series),
            ("Perfil:", self.profile), ("Inserção:", self.insertion),
            ("Rotação da seção:", self.rotation), ("Cor:", self.color_button)):
            form.addRow(label, widget)
        self._category_changed(self.category.currentText())
        self.refresh_automatic_name()

    def _mark_custom_name(self, _text):
        if not self._programmatic_name:
            self._name_custom = True

    def _set_name(self, value):
        self._programmatic_name = True
        try:
            self.name_edit.setText(value)
        finally:
            self._programmatic_name = False

    def _category_changed(self, _text):
        current = self.series.currentText()
        self.series.blockSignals(True)
        self.series.clear()
        self.series.addItems(profile_catalog.series_for_category(self.category.currentText()))
        index = self.series.findText(current)
        if index >= 0:
            self.series.setCurrentIndex(index)
        self.series.blockSignals(False)
        self._series_changed(self.series.currentText())

    def _series_changed(self, _text):
        current = self.profile.currentData()
        self.profile.blockSignals(True)
        self.profile.clear()
        for designation in profile_catalog.designations(self.category.currentText(), self.series.currentText()):
            self.profile.addItem(compact_profile_designation(designation), designation)
        index = self.profile.findData(current)
        if index >= 0:
            self.profile.setCurrentIndex(index)
        self.profile.blockSignals(False)
        self.refresh_automatic_name()

    @property
    def profile_designation(self):
        value = self.profile.currentData()
        return str(value).strip() if value is not None else ""

    @property
    def rgb(self):
        return self._color.redF(), self._color.greenF(), self._color.blueF()

    def _choose_color(self):
        selected = QtWidgets.QColorDialog.getColor(self._color, self, "Cor do elemento")
        if selected.isValid():
            self._color = selected
            self._update_color_button()

    def _update_color_button(self):
        self.color_button.setStyleSheet("QPushButton { background-color: %s; }" % self._color.name())

    def refresh_automatic_name(self, _value=None):
        if self._name_custom or not self.profile_designation:
            return
        self._set_name(next_default_label(self.document, self.element_type.currentText(), self.profile_designation))

    def creation_options(self, start, end):
        name = self.name_edit.text().strip() or next_default_label(
            self.document, self.element_type.currentText(), self.profile_designation)
        return MemberCreationOptions(start=start, end=end, designation=self.profile_designation,
            element_type=self.element_type.currentText(), insertion=self.insertion.currentText(),
            rotation=self.rotation.value(), color=self.rgb, display_name=name)

    def creation_succeeded(self, next_name):
        self._name_custom = False
        self._set_name(next_name)

    def state(self):
        return {
            "name": self.name_edit.text(), "name_custom": self._name_custom,
            "element_type": self.element_type.currentText(),
            "category": self.category.currentText(), "series": self.series.currentText(),
            "profile": self.profile_designation, "insertion": self.insertion.currentText(),
            "rotation": self.rotation.value(), "color": QtGui.QColor(self._color),
            "expanded": self.isChecked(),
        }

    def restore_state(self, state):
        if not state:
            return
        self.element_type.setCurrentText(state["element_type"])
        self.category.setCurrentText(state["category"])
        self.series.setCurrentText(state["series"])
        index = self.profile.findData(state["profile"])
        if index >= 0:
            self.profile.setCurrentIndex(index)
        self.insertion.setCurrentText(state["insertion"])
        self.rotation.setValue(state["rotation"])
        self._color = QtGui.QColor(state["color"])
        self._update_color_button()
        self._name_custom = state["name_custom"]
        self._set_name(state["name"])
        self.setChecked(state["expanded"])

# SPDX-License-Identifier: LGPL-2.1-or-later
"""Qt-independent browsing state for the profile catalog dialog."""

from __future__ import annotations


class ProfileBrowserModel:
    def __init__(self, library):
        self.library = library
        self.category_id = None
        self.series_id = None
        self.query = ""
        self.profiles = ()
        self.selected_ref = None

    def set_filter(self, category_id, series_id=None):
        self.category_id, self.series_id = category_id, series_id
        return self.refresh()

    def set_query(self, query):
        self.query = query
        return self.refresh()

    def refresh(self):
        self.profiles = self.library.search(
            self.query, category_id=self.category_id, series_id=self.series_id
        )
        if self.selected_ref not in {profile.ref for profile in self.profiles}:
            self.selected_ref = self.profiles[0].ref if self.profiles else None
        return self.profiles

    def select(self, ref):
        if ref not in {profile.ref for profile in self.profiles}:
            raise ValueError("o perfil selecionado não pertence ao resultado atual")
        self.selected_ref = ref
        return self.library.get(ref)

    def selected_profile(self):
        return self.library.get(self.selected_ref) if self.selected_ref is not None else None

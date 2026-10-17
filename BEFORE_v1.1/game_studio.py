#!/usr/bin/env python3
"""VAG IMMO STUDIO - software-only game/simulator front end."""
from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core import immo
from core.game_fixture import inspect_raw, read_fixture, write_fixture
from core.simulator import load_state, set_credential, set_immo

APP = "VAG IMMO STUDIO - GAME"
VER = "1.1.0"


class Studio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("%s %s" % (APP, VER))
        self.geometry("1060x760")
        self.minsize(900, 620)
        self.raw_path = None
        self.raw_data = None

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.sim_tab = ttk.Frame(nb)
        self.inspect_tab = ttk.Frame(nb)
        self.family_tab = ttk.Frame(nb)
        self.about_tab = ttk.Frame(nb)
        nb.add(self.sim_tab, text="Game IMMO")
        nb.add(self.inspect_tab, text="Fixture Inspector")
        nb.add(self.family_tab, text="ECU Families")
        nb.add(self.about_tab, text="About")
        self._build_sim()
        self._build_inspector()
        self._build_families()
        self._build_about()
        self.refresh_state()

    def _build_sim(self):
        t = self.sim_tab
        source = ttk.LabelFrame(t, text="Read-only ECU model fixture")
        source.pack(fill="x", padx=8, pady=8)
        ttk.Button(source, text="Open ECU dump...", command=self.open_raw).pack(side="left", padx=8, pady=8)
        self.raw_lbl = ttk.Label(source, text="No ECU dump loaded")
        self.raw_lbl.pack(side="left", padx=6)
        ttk.Label(source, text="Family override:").pack(side="left", padx=(24, 4))
        self.family = tk.StringVar(value="")
        fams = [""] + [x["family"] for x in immo.supported_families()]
        ttk.Combobox(source, textvariable=self.family, values=fams, width=20,
                     state="readonly").pack(side="left")

        state = ttk.LabelFrame(t, text="Software immobilizer state")
        state.pack(fill="x", padx=8, pady=(0, 8))
        buttons = ttk.Frame(state)
        buttons.pack(fill="x", padx=8, pady=8)
        ttk.Button(buttons, text="IMMO ON", command=lambda: self.set_immo(True)).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="IMMO OFF", command=lambda: self.set_immo(False)).pack(side="left", padx=(0, 24))
        ttk.Button(buttons, text="Credential VALID", command=lambda: self.set_cred(True)).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Credential INVALID", command=lambda: self.set_cred(False)).pack(side="left")
        self.state_banner = ttk.Label(state, text="", font=("Segoe UI", 12, "bold"))
        self.state_banner.pack(anchor="w", padx=8, pady=(0, 8))

        self.state_text = tk.Text(t, height=15, wrap="word")
        self.state_text.pack(fill="both", expand=True, padx=8, pady=8)
        self.state_text.configure(state="disabled")

        row = ttk.Frame(t)
        row.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(row, text="Refresh state", command=self.refresh_state).pack(side="left", padx=(0, 8))
        ttk.Button(row, text="Export game fixture...", command=self.export_fixture).pack(side="left")
        ttk.Label(row, text="Exports .vagfixture; source ECU bytes are embedded unchanged.").pack(side="left", padx=16)

    def _build_inspector(self):
        t = self.inspect_tab
        row = ttk.Frame(t)
        row.pack(fill="x", padx=8, pady=8)
        ttk.Button(row, text="Open .vagfixture...", command=self.inspect_fixture).pack(side="left")
        self.inspect_lbl = ttk.Label(row, text="No fixture opened")
        self.inspect_lbl.pack(side="left", padx=12)
        self.inspect_text = tk.Text(t, wrap="none")
        self.inspect_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _build_families(self):
        cols = ("family", "name", "memory", "sizes")
        tree = ttk.Treeview(self.family_tab, columns=cols, show="headings")
        for c, w in zip(cols, (180, 360, 100, 260)):
            tree.heading(c, text=c)
            tree.column(c, width=w, anchor="w")
        for entry in immo.supported_families():
            tree.insert("", "end", values=(entry["family"], entry["display_name"],
                                           entry["memory"],
                                           ", ".join(str(x) for x in entry["sizes"]) or "any"))
        tree.pack(fill="both", expand=True, padx=8, pady=8)

    def _build_about(self):
        text = tk.Text(self.about_tab, wrap="word")
        text.pack(fill="both", expand=True, padx=8, pady=8)
        text.insert("1.0", """VAG IMMO STUDIO - GAME v1.1\n\n"
                    "Software-only immobilizer state machine for a vehicle/race-jig game emulator.\n\n"
                    "Real ECU dumps are treated as read-only model fixtures. The game fixture format "
                    "stores IMMO state in a custom metadata header and embeds the original ECU payload "
                    "byte-for-byte unchanged.\n\n"
                    "Authorization logic:\n"
                    "  IMMO OFF -> authorized = true\n"
                    "  IMMO ON  -> authorized = credential_ok\n\n"
                    "Persistent state: data/simulator_state.json\n"
                    "Game fixture: *.vagfixture\n""")
        text.configure(state="disabled")

    @staticmethod
    def _set_text(widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def open_raw(self):
        name = filedialog.askopenfilename(title="Open read-only ECU model dump",
                                          filetypes=[("Binary dump", "*.bin *.BIN *.ori *.hex"), ("All files", "*.*")])
        if not name:
            return
        try:
            p = Path(name)
            data = p.read_bytes()
            ident = inspect_raw(data, p.name)
        except Exception as exc:
            messagebox.showerror(APP, str(exc))
            return
        self.raw_path, self.raw_data = p, data
        self.raw_lbl.configure(text="%s | %d bytes | %s (%s)" %
                              (p.name, len(data), ident["display_name"], ident["confidence"]))
        self.refresh_state(extra={"loaded_fixture_detection": ident})

    def set_immo(self, enabled):
        try:
            set_immo(enabled)
            self.refresh_state()
        except Exception as exc:
            messagebox.showerror(APP, str(exc))

    def set_cred(self, ok):
        try:
            set_credential(ok)
            self.refresh_state()
        except Exception as exc:
            messagebox.showerror(APP, str(exc))

    def refresh_state(self, extra=None):
        st = load_state()
        self.state_banner.configure(
            text="IMMO %s   |   credential %s   |   AUTHORIZED: %s" %
                 ("ON" if st.immo_enabled else "OFF",
                  "VALID" if st.credential_ok else "INVALID",
                  "YES" if st.authorized else "NO"))
        obj = st.to_dict()
        if extra:
            obj.update(extra)
        self._set_text(self.state_text, json.dumps(obj, indent=2, sort_keys=True))

    def export_fixture(self):
        if self.raw_path is None:
            messagebox.showinfo(APP, "Open an ECU dump first.")
            return
        suggested = self.raw_path.stem + ".vagfixture"
        name = filedialog.asksaveasfilename(title="Export game ECU fixture",
                                            defaultextension=".vagfixture",
                                            initialfile=suggested,
                                            filetypes=[("VAG game fixture", "*.vagfixture")])
        if not name:
            return
        try:
            result = write_fixture(self.raw_path, name,
                                   family_override=self.family.get() or None)
            self.refresh_state()
            messagebox.showinfo(APP, "Game fixture written:\n%s\n\nAuthorized=%s" %
                                (result["output"], result["authorized"]))
        except Exception as exc:
            messagebox.showerror(APP, str(exc))

    def inspect_fixture(self):
        name = filedialog.askopenfilename(title="Open game ECU fixture",
                                          filetypes=[("VAG game fixture", "*.vagfixture"), ("All files", "*.*")])
        if not name:
            return
        try:
            meta, payload = read_fixture(name)
            meta = dict(meta)
            meta["verified_payload_bytes"] = len(payload)
        except Exception as exc:
            messagebox.showerror(APP, str(exc))
            return
        self.inspect_lbl.configure(text=Path(name).name)
        self.inspect_text.delete("1.0", "end")
        self.inspect_text.insert("1.0", json.dumps(meta, indent=2, sort_keys=True))


def main():
    Studio().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

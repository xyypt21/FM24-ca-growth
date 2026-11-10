"""Tkinter GUI for monthly CA growth.

Start and stop the watcher, preview the next settlement, edit the growth
settings, and save them back to ``config.json``.

Run by double-clicking this file, or with:

    pythonw src/fm24_ca_growth_gui.pyw

The game must be running with a save loaded. Like the CLI watcher, this tool
WRITES to game memory.
"""

from __future__ import annotations

import contextlib
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from fm24_ca_growth import show_plan, watch
from fm24_config import (
    SETTINGS_PATH,
    CapRule,
    GrowthSettings,
    load_config,
    load_growth_settings,
    save_growth_settings,
)
from fm24_memory import Memory
from fm24_players import game_date


class GrowthGui:
    """Main window and watcher controller."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("FM24 CA Growth")
        self.root.geometry("940x700")
        self.root.minsize(760, 560)

        self.messages: queue.Queue[str] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.stop_event = threading.Event()
        self._loading = False
        self._save_job: str | None = None

        self._build()
        self._refresh_settings()
        self.root.after(100, self._drain_messages)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build(self) -> None:
        padding = {"padx": 8, "pady": 4}

        settings_frame = ttk.LabelFrame(
            self.root, text=f"Settings ({SETTINGS_PATH.name})"
        )
        settings_frame.pack(fill="x", **padding)

        form = ttk.Frame(settings_frame)
        form.pack(fill="x", padx=8, pady=6)

        self.gain_var = tk.StringVar()
        self.max_age_var = tk.StringVar()
        self.start_age_var = tk.StringVar()
        self.start_ratio_var = tk.StringVar()
        self.end_age_var = tk.StringVar()
        self.end_ratio_var = tk.StringVar()

        for variable in (
            self.gain_var,
            self.max_age_var,
            self.start_age_var,
            self.start_ratio_var,
            self.end_age_var,
            self.end_ratio_var,
        ):
            variable.trace_add("write", self._queue_autosave)

        self._field(form, 0, 0, "Monthly CA gain", self.gain_var)
        self._field(form, 0, 2, "Max age (no growth at or above)", self.max_age_var)
        self._field(form, 1, 0, "Cap start age", self.start_age_var)
        self._field(form, 1, 2, "Cap start ratio (of PA)", self.start_ratio_var)
        self._field(form, 2, 0, "Cap end age", self.end_age_var)
        self._field(form, 2, 2, "Cap end ratio (of PA)", self.end_ratio_var)

        controls = ttk.Frame(self.root)
        controls.pack(fill="x", **padding)

        self.start_button = ttk.Button(controls, text="Start", command=self._start)
        self.start_button.pack(side="left", padx=(0, 6))
        self.stop_button = ttk.Button(
            controls, text="Stop", command=self._stop, state="disabled"
        )
        self.stop_button.pack(side="left", padx=(0, 6))
        self.preview_button = ttk.Button(
            controls, text="Preview next settlement", command=self._preview
        )
        self.preview_button.pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="How cap works", command=self._show_cap_help).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(controls, text="Clear log", command=self._clear_log).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(controls, text="Exit", command=self._on_close).pack(side="left")

        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(controls, textvariable=self.status_var).pack(side="right", padx=4)

        log_frame = ttk.LabelFrame(self.root, text="Log")
        log_frame.pack(fill="both", expand=True, **padding)

        self.log = ScrolledText(
            log_frame, wrap="none", state="disabled", font=("Consolas", 9)
        )
        self.log.pack(fill="both", expand=True, padx=4, pady=4)

    def _field(
        self,
        frame: ttk.Frame,
        row: int,
        column: int,
        label: str,
        variable: tk.StringVar,
    ) -> None:
        ttk.Label(frame, text=label).grid(
            row=row, column=column, sticky="w", padx=(0, 6), pady=3
        )
        ttk.Entry(frame, textvariable=variable, width=10).grid(
            row=row, column=column + 1, sticky="w", padx=(0, 24), pady=3
        )

    def _refresh_settings(self) -> None:
        try:
            settings = load_growth_settings()
        except RuntimeError as error:
            self._log(f"Settings error: {error}")
            return

        self._loading = True
        try:
            self.gain_var.set(str(settings.monthly_gain))
            self.max_age_var.set(str(settings.max_age))
            self.start_age_var.set(f"{settings.cap.start_age:g}")
            self.start_ratio_var.set(f"{settings.cap.start_ratio:g}")
            self.end_age_var.set(f"{settings.cap.end_age:g}")
            self.end_ratio_var.set(f"{settings.cap.end_ratio:g}")
        finally:
            self._loading = False

    def _cap_help(self, settings: GrowthSettings) -> str:
        cap = settings.cap
        lines = [
            "How the CA cap works (cap = PA x ratio):",
            f"  age <= {cap.start_age:g}: ratio = {cap.start_ratio:g}",
            f"  {cap.start_age:g} < age < {cap.end_age:g}: ratio rises linearly "
            f"from {cap.start_ratio:g} to {cap.end_ratio:g}",
        ]
        if settings.max_age > cap.end_age:
            lines.append(
                f"  {cap.end_age:g} <= age < {settings.max_age}: ratio = 1.0 (full PA)"
            )
        lines.append(f"  age >= {settings.max_age}: no CA growth")
        lines.append("CA grows only when CA + monthly gain does not exceed the cap.")
        return "\n".join(lines)

    def _queue_autosave(self, *_args: object) -> None:
        """Debounce edits, then save the settings automatically."""
        if self._loading:
            return
        if self._save_job is not None:
            with contextlib.suppress(tk.TclError):
                self.root.after_cancel(self._save_job)
        self._save_job = self.root.after(500, self._autosave_settings)

    def _autosave_settings(self) -> None:
        self._save_job = None
        if self._persist_current_settings(popup=False):
            self._set_status("Settings saved")
            self._log(f"Saved settings to {SETTINGS_PATH.name}.")
        else:
            self._set_status("Invalid settings (not saved)")

    def _persist_current_settings(self, popup: bool = True) -> bool:
        """Validate and save the current form values; cancel a pending save."""
        if self._save_job is not None:
            with contextlib.suppress(tk.TclError):
                self.root.after_cancel(self._save_job)
            self._save_job = None

        settings = self._collect_settings(popup=popup)
        if settings is None:
            return False

        try:
            save_growth_settings(settings)
        except RuntimeError as error:
            self._settings_error(str(error), popup)
            return False
        return True

    def _collect_settings(self, popup: bool = True) -> GrowthSettings | None:
        try:
            gain = int(self.gain_var.get())
            max_age = int(self.max_age_var.get())
            start_age = float(self.start_age_var.get())
            start_ratio = float(self.start_ratio_var.get())
            end_age = float(self.end_age_var.get())
            end_ratio = float(self.end_ratio_var.get())
        except ValueError:
            self._settings_error("All fields must be numeric.", popup)
            return None

        if gain <= 0:
            self._settings_error("Monthly CA gain must be positive.", popup)
            return None
        if max_age < 0:
            self._settings_error("Max age must be zero or positive.", popup)
            return None
        if start_age < 0 or end_age <= start_age:
            self._settings_error("Require 0 <= start age < end age.", popup)
            return None
        if not 0 < start_ratio <= 1 or not 0 < end_ratio <= 1:
            self._settings_error("Cap ratios must be in (0, 1].", popup)
            return None

        return GrowthSettings(
            gain,
            max_age,
            CapRule(start_age, start_ratio, end_age, end_ratio),
        )

    def _settings_error(self, message: str, popup: bool = True) -> None:
        self._log(f"Settings error: {message}")
        if popup:
            messagebox.showerror("Invalid settings", message)

    def _show_cap_help(self) -> None:
        settings = self._collect_settings(popup=False)
        if settings is None:
            try:
                settings = load_growth_settings()
            except RuntimeError as error:
                messagebox.showerror("CA cap rules", f"Cannot read settings: {error}")
                return
        messagebox.showinfo("CA cap rules", self._cap_help(settings))

    def _schedule(self, callback) -> None:
        """Run a callback on the Tk thread, ignoring a closed window."""
        with contextlib.suppress(tk.TclError):
            self.root.after(0, callback)

    def _log(self, message: str) -> None:
        """Thread-safe log: queue the line for the Tk thread."""
        self.messages.put(message)

    def _drain_messages(self) -> None:
        while True:
            try:
                message = self.messages.get_nowait()
            except queue.Empty:
                break
            self.log.configure(state="normal")
            self.log.insert("end", message + "\n")
            self.log.see("end")
            self.log.configure(state="disabled")
        self.root.after(100, self._drain_messages)

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _start(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            return
        if not self._persist_current_settings(popup=True):
            return
        self.stop_event.clear()
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.preview_button.configure(state="disabled")
        self._set_status("Running")
        self._log("Starting watcher...")
        self.worker = threading.Thread(target=self._run_watch, daemon=True)
        self.worker.start()

    def _run_watch(self) -> None:
        try:
            config = load_config()
            settings = load_growth_settings()
            with Memory.open(config) as memory:
                watch(
                    memory,
                    settings,
                    log=self._log,
                    stop_event=self.stop_event,
                )
        except RuntimeError as error:
            self._log(f"Error: {error}")
        except Exception as error:  # noqa: BLE001 - show unexpected errors in the GUI
            self._log(f"Unexpected error: {error}")
        finally:
            self._schedule(self._on_stopped)

    def _stop(self) -> None:
        self._set_status("Stopping...")
        self.stop_event.set()

    def _on_stopped(self) -> None:
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.preview_button.configure(state="normal")
        self._set_status("Idle")

    def _preview(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            return
        if not self._persist_current_settings(popup=True):
            return
        self.preview_button.configure(state="disabled")
        self.start_button.configure(state="disabled")
        self._set_status("Reading...")
        threading.Thread(target=self._run_preview, daemon=True).start()

    def _run_preview(self) -> None:
        try:
            config = load_config()
            settings = load_growth_settings()
            with Memory.open(config) as memory:
                today = game_date(memory)
                if today is None:
                    self._log("Cannot read the in-game date.")
                else:
                    show_plan(memory, today, settings, log=self._log)
        except RuntimeError as error:
            self._log(f"Error: {error}")
        except Exception as error:  # noqa: BLE001 - show unexpected errors in the GUI
            self._log(f"Unexpected error: {error}")
        finally:
            self._schedule(self._on_preview_done)

    def _on_preview_done(self) -> None:
        self.preview_button.configure(state="normal")
        self.start_button.configure(state="normal")
        self._set_status("Idle")

    def _on_close(self) -> None:
        self._persist_current_settings(popup=False)
        self.stop_event.set()
        self.root.destroy()


def main() -> None:
    """Open the GUI."""
    root = tk.Tk()
    GrowthGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()

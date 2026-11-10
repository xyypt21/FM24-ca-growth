"""Tkinter GUI for monthly CA growth.

Start and stop the watcher, preview the next settlement, and read the current
settings from ``config.json``. The GUI never edits ``config.json``.

Run with:

    python src/fm24_ca_growth_gui.py

The game must be running with a save loaded. Like the CLI watcher, this tool
WRITES to game memory.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from fm24_ca_growth import show_plan, watch
from fm24_config import load_config, load_growth_settings
from fm24_memory import Memory
from fm24_players import game_date


class GrowthGui:
    """Main window and watcher controller."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("FM24 CA Growth")
        self.root.geometry("900x620")
        self.root.minsize(700, 480)

        self.messages: queue.Queue[str] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.stop_event = threading.Event()

        self._build()
        self._refresh_settings()
        self.root.after(100, self._drain_messages)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build(self) -> None:
        padding = {"padx": 8, "pady": 4}

        settings_frame = ttk.LabelFrame(self.root, text="Settings (config.json)")
        settings_frame.pack(fill="x", **padding)

        self.settings_var = tk.StringVar()
        ttk.Label(settings_frame, textvariable=self.settings_var, justify="left").pack(
            anchor="w", padx=8, pady=6
        )

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
        ttk.Button(controls, text="Clear log", command=self._clear_log).pack(
            side="left"
        )

        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(controls, textvariable=self.status_var).pack(side="right", padx=4)

        log_frame = ttk.LabelFrame(self.root, text="Log")
        log_frame.pack(fill="both", expand=True, **padding)

        self.log = ScrolledText(
            log_frame, wrap="none", state="disabled", font=("Consolas", 9)
        )
        self.log.pack(fill="both", expand=True, padx=4, pady=4)

    def _refresh_settings(self) -> None:
        try:
            settings = load_growth_settings()
        except RuntimeError as error:
            self.settings_var.set(f"Cannot load settings: {error}")
            return

        cap = settings.cap
        self.settings_var.set(
            f"Monthly gain: {settings.monthly_gain}    "
            f"Max age: {settings.max_age}\n"
            f"Cap: age <= {cap.start_age:g} -> {cap.start_ratio:.2f} x PA; "
            f"{cap.start_age:g}..{cap.end_age:g} -> "
            f"{cap.end_ratio:.2f} x PA; "
            f"{cap.end_age:g}..{settings.max_age} -> PA"
        )

    def _schedule(self, callback) -> None:
        """Run a callback on the Tk thread, ignoring a closed window."""
        try:
            self.root.after(0, callback)
        except tk.TclError:
            pass

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
        self.stop_event.set()
        self.root.destroy()


def main() -> None:
    """Open the GUI."""
    root = tk.Tk()
    GrowthGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()

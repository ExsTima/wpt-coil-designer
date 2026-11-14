"""
Interactive Dark Slate tooltips for Tkinter widgets.
Provides high-contrast (#0f172a) floating cards with 250ms debounce delay,
automatic screen-edge clamping, and optional status_var telemetry updates.
"""

from typing import Optional
import tkinter as tk


class ToolTip:
    """Современное всплывающее окно физической и технической подсказки."""
    def __init__(
        self,
        widget: tk.Widget,
        text: str,
        status_var: Optional[tk.StringVar] = None,
        title: Optional[str] = None
    ):
        self.widget = widget
        self.text = text
        self.title = title
        self.status_var = status_var
        self.tip_window: Optional[tk.Toplevel] = None
        self._after_id: Optional[str] = None

        self.widget.bind("<Enter>", self._on_enter, add="+")
        self.widget.bind("<Leave>", self._on_leave, add="+")
        self.widget.bind("<ButtonPress>", self._on_leave, add="+")

    def _on_enter(self, event=None):
        if self.status_var is not None and self.text:
            single_line = self.text.replace("\n", " ").strip()
            self.status_var.set(f"Справка: {single_line}")

        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = self.widget.after(250, self.show_tip)

    def _on_leave(self, event=None):
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self.hide_tip()

    def show_tip(self):
        if self.tip_window or not self.text:
            return

        try:
            x = self.widget.winfo_rootx() + 18
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        except Exception:
            return

        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)

        # Container frame with subtle dark border
        frame = tk.Frame(
            tw,
            bg="#0f172a",
            highlightthickness=1,
            highlightbackground="#334155",
            highlightcolor="#334155",
            padx=10,
            pady=7
        )
        frame.pack(fill=tk.BOTH, expand=True)

        # Optional heading
        if self.title:
            lbl_title = tk.Label(
                frame,
                text=self.title,
                font=("Segoe UI", 9, "bold"),
                fg="#38bdf8",  # Sky-400
                bg="#0f172a",
                anchor="w",
                justify=tk.LEFT
            )
            lbl_title.pack(fill=tk.X, pady=(0, 2))

        # Main explanation text
        lbl_body = tk.Label(
            frame,
            text=self.text,
            font=("Segoe UI", 9),
            fg="#f8fafc",  # Slate-50
            bg="#0f172a",
            justify=tk.LEFT,
            wraplength=440
        )
        lbl_body.pack(fill=tk.BOTH, expand=True)

        tw.update_idletasks()
        req_w = tw.winfo_reqwidth()
        req_h = tw.winfo_reqheight()

        screen_w = tw.winfo_screenwidth()
        screen_h = tw.winfo_screenheight()

        # Prevent tooltip from clipping outside screen boundaries
        if x + req_w > screen_w - 10:
            x = max(10, screen_w - req_w - 10)
        if y + req_h > screen_h - 40:
            # Place above the widget if it overflows bottom
            y = max(10, self.widget.winfo_rooty() - req_h - 6)

        tw.wm_geometry(f"+{x}+{y}")

    def hide_tip(self):
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None

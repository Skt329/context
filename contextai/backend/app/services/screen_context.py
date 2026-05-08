"""Screen Context Service — captures context from the user's active window.

Priority waterfall:
  1. Windows UIA API → accessibility tree text (Word, Notepad, VS Code, browser)
  2. Clipboard → recently copied text (>50 chars)
  3. Screenshot → base64 capture for LLM vision fallback
"""

import sys
import os
import base64
import logging
from io import BytesIO
from dataclasses import dataclass

logger = logging.getLogger("contextai.screen")


@dataclass
class ScreenCapture:
    method: str  # "uia", "clipboard", "screenshot", "none"
    text: str
    screenshot_b64: str | None = None
    window_title: str = ""
    length: int = 0

    def __post_init__(self):
        self.length = len(self.text) if self.text else 0


# ─── Capture Methods ──────────────────────────────────────────

def capture_screen_context(include_screenshot: bool = True) -> ScreenCapture:
    """Run the full context capture waterfall.

    Args:
        include_screenshot: If True, captures a screenshot as fallback when UIA/clipboard fail.
    """

    # Method 1: Windows UIA
    if sys.platform == "win32":
        try:
            uia_text, window_title = _capture_uia()
            if uia_text and len(uia_text) > 50:
                logger.info(f"UIA captured {len(uia_text)} chars from '{window_title}'")
                return ScreenCapture(
                    method="uia",
                    text=uia_text,
                    window_title=window_title,
                )
        except Exception as e:
            logger.debug(f"UIA capture failed: {e}")

    # Method 2: Clipboard
    try:
        clip_text = _capture_clipboard()
        if clip_text and len(clip_text) > 50:
            logger.info(f"Clipboard captured {len(clip_text)} chars")
            return ScreenCapture(method="clipboard", text=clip_text)
    except Exception as e:
        logger.debug(f"Clipboard capture failed: {e}")

    # Method 3: Screenshot (base64 for vision LLM)
    if include_screenshot:
        try:
            screenshot_b64, window_title = _capture_screenshot()
            if screenshot_b64:
                logger.info(f"Screenshot captured from '{window_title}'")
                return ScreenCapture(
                    method="screenshot",
                    text="[Screenshot captured — requires vision model to process]",
                    screenshot_b64=screenshot_b64,
                    window_title=window_title,
                )
        except Exception as e:
            logger.debug(f"Screenshot capture failed: {e}")

    return ScreenCapture(method="none", text="")


# ─── UIA Capture ──────────────────────────────────────────────

def _capture_uia() -> tuple[str, str]:
    """Capture text from the active window using Windows UI Automation."""
    import uiautomation as auto

    focused = auto.GetFocusedControl()
    if not focused:
        return "", ""

    root = focused.GetTopLevelControl()
    if not root:
        return "", ""

    window_title = root.Name or ""

    texts = []
    _walk_uia_tree(root, texts, depth=0, max_depth=8)
    return "\n".join(texts), window_title


def _walk_uia_tree(control, texts: list, depth: int, max_depth: int):
    """Recursively walk the UIA tree to collect text content."""
    if depth > max_depth:
        return

    try:
        name = control.Name
        if name and len(name.strip()) > 2:
            texts.append(name.strip())
    except Exception:
        pass

    try:
        # Try to get value (text fields, edit controls)
        value_pattern = control.GetValuePattern()
        if value_pattern:
            val = value_pattern.Value
            if val and len(val.strip()) > 2 and val.strip() not in [t.strip() for t in texts]:
                texts.append(val.strip())
    except Exception:
        pass

    try:
        for child in control.GetChildren():
            _walk_uia_tree(child, texts, depth + 1, max_depth)
    except Exception:
        pass


# ─── Clipboard Capture ───────────────────────────────────────

def _capture_clipboard() -> str:
    """Get text content from the clipboard."""
    try:
        import pyperclip
        return pyperclip.paste() or ""
    except ImportError:
        # Fallback: use ctypes on Windows
        if sys.platform == "win32":
            return _clipboard_win32()
        return ""


def _clipboard_win32() -> str:
    """Win32 clipboard fallback without pyperclip."""
    try:
        import ctypes
        CF_TEXT = 1
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        if not user32.OpenClipboard(0):
            return ""

        try:
            handle = user32.GetClipboardData(CF_TEXT)
            if not handle:
                return ""
            data = ctypes.c_char_p(handle)
            return data.value.decode("utf-8", errors="replace") if data.value else ""
        finally:
            user32.CloseClipboard()
    except Exception:
        return ""


# ─── Screenshot Capture ──────────────────────────────────────

def _capture_screenshot() -> tuple[str, str]:
    """Capture the primary monitor screenshot as base64.

    Returns (base64_png, window_title).
    """
    try:
        import mss
    except ImportError:
        logger.warning("mss not installed — screenshot capture unavailable. Install with: pip install mss")
        return "", ""

    window_title = ""

    # Get the active window title on Windows
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd) + 1
            buf = ctypes.create_unicode_buffer(length)
            user32.GetWindowTextW(hwnd, buf, length)
            window_title = buf.value
        except Exception:
            pass

    with mss.mss() as sct:
        # Capture the primary monitor
        monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
        screenshot = sct.grab(monitor)

        # Convert to PNG bytes
        from mss.tools import to_png
        png_bytes = to_png(screenshot.rgb, screenshot.size)

        # Compress by converting to JPEG if Pillow is available
        try:
            from PIL import Image
            img = Image.open(BytesIO(png_bytes))

            # Resize to max 1024px on longest side to save tokens
            max_dim = 1024
            if max(img.size) > max_dim:
                ratio = max_dim / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.LANCZOS)

            buf = BytesIO()
            img.save(buf, format="JPEG", quality=75)
            encoded = base64.b64encode(buf.getvalue()).decode("ascii")
            return f"data:image/jpeg;base64,{encoded}", window_title

        except ImportError:
            # No Pillow — send raw PNG (larger but works)
            encoded = base64.b64encode(png_bytes).decode("ascii")
            return f"data:image/png;base64,{encoded}", window_title


# ─── Clipboard Monitor (opt-in background task) ──────────────

class ClipboardMonitor:
    """Monitors clipboard changes and stores recent clips for context."""

    def __init__(self, max_history: int = 5):
        self.max_history = max_history
        self.history: list[str] = []
        self._last_clip = ""
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

    def check(self):
        """Check for new clipboard content. Call periodically."""
        if not self._enabled:
            return

        try:
            current = _capture_clipboard()
            if current and current != self._last_clip and len(current) > 10:
                self._last_clip = current
                self.history.append(current)
                if len(self.history) > self.max_history:
                    self.history.pop(0)
        except Exception:
            pass

    def get_recent(self) -> list[str]:
        return list(self.history)

    def clear(self):
        self.history.clear()
        self._last_clip = ""


# Singleton clipboard monitor
clipboard_monitor = ClipboardMonitor()

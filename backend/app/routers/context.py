"""Screen context router — capture text from active window, clipboard, or screenshot."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.screen_context import (
    capture_screen_context,
    clipboard_monitor,
    ScreenCapture,
)

router = APIRouter()


class ContextResponse(BaseModel):
    method: str  # "uia", "clipboard", "screenshot", "none"
    text: str
    length: int
    window_title: str = ""
    has_screenshot: bool = False


class ClipboardToggle(BaseModel):
    enabled: bool


@router.post("/capture")
async def capture_context():
    """Capture screen context using the priority waterfall."""
    result = capture_screen_context(include_screenshot=True)
    return ContextResponse(
        method=result.method,
        text=result.text,
        length=result.length,
        window_title=result.window_title,
        has_screenshot=result.screenshot_b64 is not None,
    )


@router.post("/capture/screenshot")
async def capture_screenshot_raw():
    """Capture a screenshot and return the base64 data URL for vision models."""
    result = capture_screen_context(include_screenshot=True)
    if result.screenshot_b64:
        return {
            "available": True,
            "data_url": result.screenshot_b64,
            "window_title": result.window_title,
        }
    # If UIA/clipboard worked, return text instead
    if result.text:
        return {
            "available": True,
            "text": result.text,
            "method": result.method,
            "window_title": result.window_title,
        }
    return {"available": False}


@router.get("/preview")
async def preview_context():
    """Get a preview of what context would be captured."""
    result = capture_screen_context(include_screenshot=False)
    if result.length > 0:
        preview = result.text[:200] + ("..." if len(result.text) > 200 else "")
        return {
            "available": True,
            "method": result.method,
            "preview": preview,
            "length": result.length,
            "window_title": result.window_title,
        }
    return {"available": False}


@router.post("/clipboard/toggle")
async def toggle_clipboard_monitor(body: ClipboardToggle):
    """Enable or disable clipboard monitoring."""
    if body.enabled:
        clipboard_monitor.enable()
    else:
        clipboard_monitor.disable()
    return {"enabled": clipboard_monitor.enabled}


@router.get("/clipboard/history")
async def get_clipboard_history():
    """Get recent clipboard entries (when monitoring is enabled)."""
    return {
        "enabled": clipboard_monitor.enabled,
        "entries": clipboard_monitor.get_recent(),
    }

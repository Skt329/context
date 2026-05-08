"""Screen context router — capture text from active window, clipboard, or screenshot."""

import sys
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ContextResponse(BaseModel):
    method: str  # "uia", "clipboard", "screenshot"
    text: str
    length: int


@router.post("/capture")
async def capture_context():
    """Capture screen context using the priority waterfall."""

    # Method 1: Windows UIA (accessibility tree)
    if sys.platform == "win32":
        try:
            text = _capture_via_uia()
            if text and len(text) > 50:
                return ContextResponse(method="uia", text=text, length=len(text))
        except Exception:
            pass

    # Method 2: Clipboard
    try:
        import pyperclip
        clip = pyperclip.paste()
        if clip and len(clip) > 50:
            return ContextResponse(method="clipboard", text=clip, length=len(clip))
    except Exception:
        pass

    # Method 3: Screenshot (placeholder — requires vision API)
    return ContextResponse(method="none", text="", length=0)


@router.get("/preview")
async def preview_context():
    """Get a preview of what context would be captured."""
    result = await capture_context()
    if result.length > 0:
        preview = result.text[:200] + ("..." if len(result.text) > 200 else "")
        return {"available": True, "method": result.method, "preview": preview, "length": result.length}
    return {"available": False}


def _capture_via_uia() -> str:
    """Capture text from the active window using Windows UI Automation API."""
    try:
        import uiautomation as auto

        focused = auto.GetFocusedControl()
        if not focused:
            return ""

        root = focused.GetTopLevelControl()
        if not root:
            return ""

        texts = []
        _walk_tree(root, texts, depth=0, max_depth=8)
        return "\n".join(texts)
    except ImportError:
        return ""


def _walk_tree(control, texts: list, depth: int, max_depth: int):
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
        for child in control.GetChildren():
            _walk_tree(child, texts, depth + 1, max_depth)
    except Exception:
        pass

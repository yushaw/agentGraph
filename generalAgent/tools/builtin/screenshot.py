"""Capture screenshot of user's screen (Windows 10/11).

Uses pywin32 for native Windows API access. No PowerShell dependency.

Requirements:
    pip install pywin32 pillow
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool


def _get_workspace_path() -> Path:
    """Get the current workspace path from environment."""
    workspace = os.environ.get("AGENT_WORKSPACE_PATH")
    if workspace:
        return Path(workspace)
    return Path(os.environ.get("TEMP", "C:\\Temp"))


def _check_dependencies() -> tuple[bool, str]:
    """Check if required dependencies are installed."""
    missing = []
    try:
        import win32gui  # noqa: F401
        import win32ui  # noqa: F401
        import win32con  # noqa: F401
        import win32api  # noqa: F401
    except ImportError:
        missing.append("pywin32")

    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        missing.append("pillow")

    if missing:
        return False, f"Missing dependencies: {', '.join(missing)}. Install with: pip install {' '.join(missing)}"
    return True, ""


def _get_all_monitors() -> list[dict]:
    """Get information about all connected monitors."""
    try:
        import win32api
        monitors = []
        for i, monitor in enumerate(win32api.EnumDisplayMonitors()):
            hmon, hdc, rect = monitor
            info = win32api.GetMonitorInfo(hmon)
            monitors.append({
                "index": i,
                "handle": hmon,
                "rect": rect,  # (left, top, right, bottom)
                "work_rect": info["Work"],
                "is_primary": info["Flags"] == 1,
                "device": info["Device"]
            })
        return monitors
    except Exception as e:
        return [{"error": str(e)}]


def _capture_region(left: int, top: int, width: int, height: int, output_path: Path) -> tuple[bool, str]:
    """Capture a specific screen region using Windows API."""
    try:
        import win32gui
        import win32ui
        import win32con
        import win32api
        from PIL import Image

        # Get desktop window DC
        hwnd_desktop = win32gui.GetDesktopWindow()
        desktop_dc = win32gui.GetWindowDC(hwnd_desktop)
        img_dc = win32ui.CreateDCFromHandle(desktop_dc)
        mem_dc = img_dc.CreateCompatibleDC()

        # Create bitmap
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(img_dc, width, height)
        mem_dc.SelectObject(bitmap)

        # Copy screen to bitmap
        mem_dc.BitBlt((0, 0), (width, height), img_dc, (left, top), win32con.SRCCOPY)

        # Convert to PIL Image
        bmp_info = bitmap.GetInfo()
        bmp_bits = bitmap.GetBitmapBits(True)
        img = Image.frombuffer(
            'RGB',
            (bmp_info['bmWidth'], bmp_info['bmHeight']),
            bmp_bits, 'raw', 'BGRX', 0, 1
        )

        # Save
        img.save(str(output_path), 'PNG')

        # Cleanup
        mem_dc.DeleteDC()
        win32gui.DeleteObject(bitmap.GetHandle())
        win32gui.ReleaseDC(hwnd_desktop, desktop_dc)

        return True, ""

    except Exception as e:
        return False, str(e)


def _capture_window(hwnd: int, output_path: Path) -> tuple[bool, str]:
    """Capture a specific window by handle."""
    try:
        import win32gui
        import win32ui
        import win32con
        from PIL import Image

        # Get window dimensions
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width = right - left
        height = bottom - top

        if width <= 0 or height <= 0:
            return False, "Window has invalid dimensions (may be minimized)"

        # Get window DC
        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()

        # Create bitmap
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(bitmap)

        # Try PrintWindow first (works for most windows)
        result = win32gui.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)  # PW_RENDERFULLCONTENT = 2

        if result == 0:
            # Fallback to BitBlt if PrintWindow fails
            save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)

        # Convert to PIL Image
        bmp_info = bitmap.GetInfo()
        bmp_bits = bitmap.GetBitmapBits(True)
        img = Image.frombuffer(
            'RGB',
            (bmp_info['bmWidth'], bmp_info['bmHeight']),
            bmp_bits, 'raw', 'BGRX', 0, 1
        )

        # Save
        img.save(str(output_path), 'PNG')

        # Cleanup
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)
        win32gui.DeleteObject(bitmap.GetHandle())

        return True, ""

    except Exception as e:
        return False, str(e)


def _get_foreground_window() -> tuple[int, str]:
    """Get the currently active/foreground window."""
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
        return hwnd, title
    except Exception as e:
        return 0, str(e)


def _list_windows() -> list[dict]:
    """List all visible windows with their handles and titles."""
    try:
        import win32gui
        import win32process

        windows = []

        def enum_callback(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:  # Only include windows with titles
                    try:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        rect = win32gui.GetWindowRect(hwnd)
                        results.append({
                            "hwnd": hwnd,
                            "title": title,
                            "pid": pid,
                            "rect": rect,
                            "width": rect[2] - rect[0],
                            "height": rect[3] - rect[1]
                        })
                    except Exception:
                        pass
            return True

        win32gui.EnumWindows(enum_callback, windows)
        return windows

    except Exception as e:
        return [{"error": str(e)}]


@tool
def screenshot(
    filename: Optional[str] = None,
    monitor: Optional[int] = None,
    all_monitors: bool = False,
    hwnd: Optional[int] = None,
    active_window: bool = False
) -> str:
    """Capture a screenshot on Windows 10/11.

    Supports multiple capture modes: full screen, specific monitor, specific window,
    or the currently active window.

    Args:
        filename: Optional custom filename (without extension).
                  Default: screenshot_YYYYMMDD_HHMMSS.png
        monitor: Specific monitor index (0-based).
                 - None: Primary monitor (default)
                 - 0, 1, 2...: Specific monitor by index
        all_monitors: If True, capture all monitors as one combined image.
        hwnd: Window handle (integer) to capture a specific window.
              Use list_windows() to find window handles.
        active_window: If True, capture the currently active/foreground window.
                       Overrides monitor and all_monitors.

    Returns:
        Success message with file path, or error message.

    Examples:
        screenshot()
        -> Capture primary monitor

        screenshot(monitor=1)
        -> Capture second monitor

        screenshot(all_monitors=True)
        -> Capture all monitors combined

        screenshot(active_window=True)
        -> Capture the currently active window

        screenshot(hwnd=12345)
        -> Capture window with handle 12345

    Note:
        Requires: pip install pywin32 pillow
    """
    if sys.platform != "win32":
        return f"Error: This tool is for Windows only. Current platform: {sys.platform}"

    # Check dependencies
    ok, err = _check_dependencies()
    if not ok:
        return f"Error: {err}"

    # Setup output path
    workspace = _get_workspace_path()
    temp_dir = workspace / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Helper to sanitize filename parts
    def sanitize(s: str, max_len: int = 30) -> str:
        # Keep alphanumeric, Chinese chars, and basic punctuation
        safe = "".join(c for c in s if c.isalnum() or c in "._-" or ord(c) > 127)
        return safe[:max_len] if safe else ""

    # Determine capture mode and execute
    capture_type = ""
    filename_prefix = ""

    if active_window:
        # Capture active/foreground window
        hwnd_active, title = _get_foreground_window()
        if hwnd_active == 0:
            return f"Error: Could not get foreground window. {title}"

        # Generate filename: window_Chrome_20251127_143052.png
        window_name = sanitize(title, 20) or "unknown"
        filename_prefix = f"window_{window_name}"
        capture_type = f"active window: {title} (hwnd={hwnd_active})"

    elif hwnd is not None:
        # Capture specific window by handle
        import win32gui
        try:
            if not win32gui.IsWindow(hwnd):
                return f"Error: Invalid window handle {hwnd}. Use list_windows() to find valid handles."
            title = win32gui.GetWindowText(hwnd)
        except Exception:
            return f"Error: Cannot access window handle {hwnd}"

        # Generate filename: window_Notepad_20251127_143052.png
        window_name = sanitize(title, 20) or f"hwnd{hwnd}"
        filename_prefix = f"window_{window_name}"
        capture_type = f"window: {title} (hwnd={hwnd})"

    elif all_monitors:
        # Capture all monitors combined
        monitors = _get_all_monitors()
        if not monitors or "error" in monitors[0]:
            return f"Error: Could not enumerate monitors"

        # Calculate bounding box
        min_left = min(m["rect"][0] for m in monitors)
        min_top = min(m["rect"][1] for m in monitors)
        max_right = max(m["rect"][2] for m in monitors)
        max_bottom = max(m["rect"][3] for m in monitors)

        width = max_right - min_left
        height = max_bottom - min_top

        # Generate filename: all_monitors_3840x1080_20251127_143052.png
        filename_prefix = f"all_monitors_{width}x{height}"
        capture_type = f"all monitors ({len(monitors)} displays, {width}x{height})"

    else:
        # Capture specific monitor or primary
        monitors = _get_all_monitors()
        if not monitors or "error" in monitors[0]:
            return f"Error: Could not enumerate monitors"

        if monitor is not None:
            if monitor < 0 or monitor >= len(monitors):
                return f"Error: Monitor index {monitor} out of range. Available: 0-{len(monitors)-1}"
            target = monitors[monitor]
        else:
            # Find primary monitor
            target = next((m for m in monitors if m.get("is_primary")), monitors[0])

        rect = target["rect"]
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top

        idx = target.get("index", 0)
        is_primary = target.get("is_primary", False)
        primary_str = " (Primary)" if is_primary else ""

        # Generate filename: monitor0_primary_1920x1080_20251127_143052.png
        primary_tag = "_primary" if is_primary else ""
        filename_prefix = f"monitor{idx}{primary_tag}_{width}x{height}"
        capture_type = f"monitor {idx}{primary_str}: {width}x{height}"

    # Build final output path
    if filename:
        # User specified custom filename
        safe_filename = sanitize(filename, 50) or "screenshot"
        output_file = temp_dir / f"{safe_filename}.png"
    else:
        # Auto-generated descriptive filename
        output_file = temp_dir / f"{filename_prefix}_{timestamp}.png"

    # Now execute the capture
    if active_window:
        hwnd_active, _ = _get_foreground_window()
        success, err = _capture_window(hwnd_active, output_file)
    elif hwnd is not None:
        success, err = _capture_window(hwnd, output_file)
    elif all_monitors:
        success, err = _capture_region(min_left, min_top, width, height, output_file)
    else:
        success, err = _capture_region(left, top, width, height, output_file)

    # Return result
    if success and output_file.exists():
        file_size = output_file.stat().st_size
        if file_size < 1024:
            size_str = f"{file_size} bytes"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size / 1024:.1f} KB"
        else:
            size_str = f"{file_size / 1024 / 1024:.1f} MB"

        relative_path = f"temp/{output_file.name}"
        return (
            f"Screenshot captured!\n"
            f"- File: {relative_path}\n"
            f"- Size: {size_str}\n"
            f"- Source: {capture_type}\n\n"
            f"Use read_file(\"{relative_path}\") to view the screenshot."
        )
    else:
        return f"Error: Failed to capture screenshot.\nReason: {err}"


@tool
def list_monitors() -> str:
    """List all connected monitors on Windows.

    Returns:
        Information about each monitor including index, resolution, position,
        and whether it's the primary display.

    Example:
        list_monitors()
        ->
        Monitor 0 (Primary): 1920x1080 at (0, 0)
        Monitor 1: 2560x1440 at (1920, 0)
    """
    if sys.platform != "win32":
        return f"Error: This tool is for Windows only. Current platform: {sys.platform}"

    ok, err = _check_dependencies()
    if not ok:
        return f"Error: {err}"

    monitors = _get_all_monitors()
    if not monitors:
        return "No monitors found"
    if "error" in monitors[0]:
        return f"Error: {monitors[0]['error']}"

    lines = []
    for m in monitors:
        left, top, right, bottom = m["rect"]
        width = right - left
        height = bottom - top
        primary = " (Primary)" if m.get("is_primary") else ""
        lines.append(f"Monitor {m['index']}{primary}: {width}x{height} at ({left}, {top})")

    return "\n".join(lines)


@tool
def list_windows() -> str:
    """List all visible windows with their handles (hwnd).

    Use this to find window handles for the screenshot(hwnd=...) parameter.

    Returns:
        List of visible windows with hwnd, title, and dimensions.

    Example:
        list_windows()
        ->
        hwnd=12345 | 1200x800 | Chrome - Google
        hwnd=67890 | 800x600  | Notepad
    """
    if sys.platform != "win32":
        return f"Error: This tool is for Windows only. Current platform: {sys.platform}"

    ok, err = _check_dependencies()
    if not ok:
        return f"Error: {err}"

    windows = _list_windows()
    if not windows:
        return "No visible windows found"
    if "error" in windows[0]:
        return f"Error: {windows[0]['error']}"

    # Sort by title for easier reading
    windows.sort(key=lambda w: w.get("title", "").lower())

    lines = []
    for w in windows:
        # Skip very small windows (likely system/hidden)
        if w.get("width", 0) < 50 or w.get("height", 0) < 50:
            continue
        title = w.get("title", "")[:60]  # Truncate long titles
        if len(w.get("title", "")) > 60:
            title += "..."
        lines.append(f"hwnd={w['hwnd']:<8} | {w['width']:>4}x{w['height']:<4} | {title}")

    if not lines:
        return "No visible windows with significant size found"

    return f"Found {len(lines)} windows:\n\n" + "\n".join(lines)


@tool
def get_active_window() -> str:
    """Get information about the currently active/foreground window.

    Returns:
        The window handle (hwnd) and title of the active window.

    Example:
        get_active_window()
        -> Active window: hwnd=12345 | Chrome - Google
    """
    if sys.platform != "win32":
        return f"Error: This tool is for Windows only. Current platform: {sys.platform}"

    ok, err = _check_dependencies()
    if not ok:
        return f"Error: {err}"

    hwnd, title = _get_foreground_window()
    if hwnd == 0:
        return f"Error: Could not get foreground window. {title}"

    try:
        import win32gui
        rect = win32gui.GetWindowRect(hwnd)
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        return f"Active window:\n- hwnd: {hwnd}\n- title: {title}\n- size: {width}x{height}"
    except Exception:
        return f"Active window:\n- hwnd: {hwnd}\n- title: {title}"


__all__ = ["screenshot", "list_monitors", "list_windows", "get_active_window"]

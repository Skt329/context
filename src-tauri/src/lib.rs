use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    Manager,
};
use tauri_plugin_global_shortcut::GlobalShortcutExt;
use std::sync::Mutex;

// ─── Global State ─────────────────────────────────────────────
// Global static so the SetWinEventHook callback can access it.
// With WINEVENT_SKIPOWNPROCESS, only external windows appear,
// so we don't need to store/filter our own widget HWND.

struct ForegroundState {
    last_target_hwnd: usize,
}

static FOREGROUND_STATE: Mutex<ForegroundState> = Mutex::new(ForegroundState {
    last_target_hwnd: 0,
});

// ─── Win32: Foreground Window Hook ────────────────────────────
// Enterprise pattern: continuously track the last non-widget foreground
// window via SetWinEventHook(EVENT_SYSTEM_FOREGROUND).
// This means inject always targets whatever was last focused — even
// if the user switched apps while the widget was open.

#[cfg(windows)]
fn install_foreground_hook() {
    use windows::Win32::UI::Accessibility::SetWinEventHook;
    use windows::Win32::Foundation::HWND;

    const EVENT_SYSTEM_FOREGROUND: u32 = 0x0003;
    const WINEVENT_OUTOFCONTEXT: u32 = 0x0000;
    const WINEVENT_SKIPOWNPROCESS: u32 = 0x0002;

    unsafe extern "system" fn on_foreground_change(
        _hook: windows::Win32::UI::Accessibility::HWINEVENTHOOK,
        _event: u32,
        hwnd: HWND,
        _id_object: i32,
        _id_child: i32,
        _id_event_thread: u32,
        _dwms_event_time: u32,
    ) {
        let hwnd_val = hwnd.0 as usize;
        if hwnd_val == 0 {
            return;
        }
        // SKIPOWNPROCESS guarantees this is NOT our widget
        if let Ok(mut fg) = FOREGROUND_STATE.lock() {
            fg.last_target_hwnd = hwnd_val;
            println!("[hook] Target → {:#x}", hwnd_val);
        }
    }

    unsafe {
        let hook = SetWinEventHook(
            EVENT_SYSTEM_FOREGROUND,
            EVENT_SYSTEM_FOREGROUND,
            None,                // no DLL needed (out-of-context)
            Some(on_foreground_change),
            0,                   // all processes
            0,                   // all threads
            WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS,
        );

        if hook.is_invalid() {
            println!("[hook] FAILED to install foreground hook!");
        } else {
            println!("[hook] Foreground hook installed OK");
        }
    }
}

// ─── Tauri Commands ───────────────────────────────────────────

#[tauri::command]
fn toggle_window(app: tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        if window.is_visible().unwrap_or(false) {
            let _ = window.hide();
        } else {
            let _ = window.show();
            let _ = window.set_focus();
        }
    }
}

#[tauri::command]
fn set_always_on_top(app: tauri::AppHandle, on_top: bool) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.set_always_on_top(on_top);
    }
}

/// Position the widget at bottom-center, above the taskbar.
#[tauri::command]
fn position_widget_bottom(app: tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("widget") {
        if let Ok(Some(monitor)) = window.primary_monitor() {
            let screen_size = monitor.size();
            let screen_pos = monitor.position();
            let scale = monitor.scale_factor();

            let widget_w = 480.0;
            let widget_h = 500.0;
            let taskbar_h = 48.0;

            let screen_w_logical = screen_size.width as f64 / scale;
            let screen_h_logical = screen_size.height as f64 / scale;

            let x = screen_pos.x as f64 / scale + (screen_w_logical - widget_w) / 2.0;
            let y = screen_pos.y as f64 / scale + screen_h_logical - widget_h - taskbar_h;

            let _ = window.set_position(tauri::Position::Logical(tauri::LogicalPosition { x, y }));
        }
    }
}

/// Toggle widget visibility. No HWND capture needed —
/// the hook tracks targets continuously.
#[tauri::command]
fn toggle_widget(app: tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("widget") {
        if window.is_visible().unwrap_or(false) {
            let _ = window.hide();
        } else {
            let _ = window.show();
            let _ = window.set_focus();
        }
    }
}

/// Hide widget and restore focus to the last target.
#[tauri::command]
fn hide_widget(app: tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("widget") {
        let _ = window.hide();
    }
    #[cfg(windows)]
    {
        let hwnd = FOREGROUND_STATE.lock().unwrap().last_target_hwnd;
        if hwnd != 0 {
            force_foreground(hwnd);
        }
    }
}

/// Inject text into whatever window the user last focused.
/// The hook keeps `last_target_hwnd` up-to-date at all times,
/// so this works even if the user switched apps while the widget was open.
#[tauri::command]
fn inject_text(app: tauri::AppHandle, text: String) -> String {
    let hwnd_val: usize;
    #[cfg(windows)]
    {
        hwnd_val = FOREGROUND_STATE.lock().unwrap().last_target_hwnd;
    }
    #[cfg(not(windows))]
    {
        hwnd_val = 0usize;
        let _ = &text;
        return "Not supported on this OS".into();
    }

    println!("[inject] HWND={:#x} text_len={}", hwnd_val, text.len());

    // 1. Set clipboard
    #[cfg(windows)]
    clipboard_set(&text);

    if hwnd_val == 0 {
        if let Some(window) = app.get_webview_window("widget") {
            let _ = window.hide();
        }
        return "HWND=0: text copied to clipboard. Use Ctrl+V.".into();
    }

    // 2. Switch foreground BEFORE hiding (we are foreground → allowed)
    #[cfg(windows)]
    force_foreground(hwnd_val);

    // 3. Delay for focus switch
    std::thread::sleep(std::time::Duration::from_millis(150));

    // 4. Send Ctrl+V (widget stays visible — alwaysOnTop)
    #[cfg(windows)]
    {
        send_ctrl_v();
        println!("[inject] DONE → {:#x}", hwnd_val);
    }

    format!("OK: HWND={:#x}", hwnd_val)
}

// ─── Win32 Helpers ────────────────────────────────────────────

/// Reliably set foreground window using AttachThreadInput.
#[cfg(windows)]
fn force_foreground(hwnd_val: usize) {
    use windows::Win32::Foundation::HWND;
    use windows::Win32::UI::WindowsAndMessaging::{
        GetWindowThreadProcessId, SetForegroundWindow, ShowWindow,
        BringWindowToTop, SW_SHOW, IsWindow, IsIconic, SW_RESTORE,
    };
    use windows::Win32::System::Threading::{
        AttachThreadInput, GetCurrentThreadId,
    };

    unsafe {
        let hwnd = HWND(hwnd_val as *mut _);

        if !IsWindow(hwnd).as_bool() {
            println!("[force_fg] HWND {:#x} is invalid", hwnd_val);
            return;
        }

        if IsIconic(hwnd).as_bool() {
            let _ = ShowWindow(hwnd, SW_RESTORE);
        } else {
            let _ = ShowWindow(hwnd, SW_SHOW);
        }

        let our_thread = GetCurrentThreadId();
        let target_thread = GetWindowThreadProcessId(hwnd, None);

        if our_thread != target_thread && target_thread != 0 {
            let _ = AttachThreadInput(our_thread, target_thread, true);
            let _ = BringWindowToTop(hwnd);
            let _ = SetForegroundWindow(hwnd);
            let _ = AttachThreadInput(our_thread, target_thread, false);
        } else {
            let _ = SetForegroundWindow(hwnd);
        }
    }
}

/// Set clipboard text content.
#[cfg(windows)]
fn clipboard_set(text: &str) {
    use windows::Win32::Foundation::HWND;
    use windows::Win32::System::DataExchange::{
        CloseClipboard, EmptyClipboard, OpenClipboard, SetClipboardData,
    };
    use windows::Win32::System::Memory::{GlobalAlloc, GlobalLock, GlobalUnlock, GMEM_MOVEABLE};

    unsafe {
        let wide: Vec<u16> = text.encode_utf16().chain(std::iter::once(0)).collect();
        let byte_len = wide.len() * 2;

        let hmem = GlobalAlloc(GMEM_MOVEABLE, byte_len);
        if hmem.is_err() {
            return;
        }
        let hmem = hmem.unwrap();
        let ptr = GlobalLock(hmem);
        if ptr.is_null() {
            return;
        }
        std::ptr::copy_nonoverlapping(wide.as_ptr() as *const u8, ptr as *mut u8, byte_len);
        let _ = GlobalUnlock(hmem);

        if OpenClipboard(HWND::default()).is_ok() {
            let _ = EmptyClipboard();
            let _ = SetClipboardData(13, windows::Win32::Foundation::HANDLE(hmem.0));
            let _ = CloseClipboard();
        }
    }
}

/// Simulate Ctrl+V keypress.
#[cfg(windows)]
fn send_ctrl_v() {
    use windows::Win32::UI::Input::KeyboardAndMouse::{
        SendInput, INPUT, INPUT_0, INPUT_KEYBOARD, KEYBDINPUT, KEYBD_EVENT_FLAGS,
        KEYEVENTF_KEYUP, VIRTUAL_KEY,
    };

    unsafe {
        let vk_control = VIRTUAL_KEY(0x11);
        let vk_v = VIRTUAL_KEY(0x56);

        let inputs = [
            INPUT {
                r#type: INPUT_KEYBOARD,
                Anonymous: INPUT_0 {
                    ki: KEYBDINPUT {
                        wVk: vk_control, wScan: 0,
                        dwFlags: KEYBD_EVENT_FLAGS(0), time: 0, dwExtraInfo: 0,
                    },
                },
            },
            INPUT {
                r#type: INPUT_KEYBOARD,
                Anonymous: INPUT_0 {
                    ki: KEYBDINPUT {
                        wVk: vk_v, wScan: 0,
                        dwFlags: KEYBD_EVENT_FLAGS(0), time: 0, dwExtraInfo: 0,
                    },
                },
            },
            INPUT {
                r#type: INPUT_KEYBOARD,
                Anonymous: INPUT_0 {
                    ki: KEYBDINPUT {
                        wVk: vk_v, wScan: 0,
                        dwFlags: KEYEVENTF_KEYUP, time: 0, dwExtraInfo: 0,
                    },
                },
            },
            INPUT {
                r#type: INPUT_KEYBOARD,
                Anonymous: INPUT_0 {
                    ki: KEYBDINPUT {
                        wVk: vk_control, wScan: 0,
                        dwFlags: KEYEVENTF_KEYUP, time: 0, dwExtraInfo: 0,
                    },
                },
            },
        ];

        let _ = SendInput(&inputs, std::mem::size_of::<INPUT>() as i32);
    }
}

// ─── App Setup ────────────────────────────────────────────────

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            // Install the foreground window tracking hook
            #[cfg(windows)]
            install_foreground_hook();

            // Build tray menu
            let show_item = MenuItem::with_id(app, "show", "Open Manager", true, None::<&str>)?;
            let widget_item = MenuItem::with_id(app, "widget", "Toggle Widget", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "Quit ContextAI", true, None::<&str>)?;
            let tray_menu = Menu::with_items(app, &[&show_item, &widget_item, &quit_item])?;

            // Build system tray
            TrayIconBuilder::with_id("main-tray")
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&tray_menu)
                .tooltip("ContextAI — Ctrl+Shift+Space")
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => {
                        if let Some(window) = app.get_webview_window("main") {
                            if window.is_visible().unwrap_or(false) {
                                let _ = window.hide();
                            } else {
                                let _ = window.show();
                                let _ = window.set_focus();
                            }
                        }
                    }
                    "widget" => {
                        if let Some(window) = app.get_webview_window("widget") {
                            if window.is_visible().unwrap_or(false) {
                                let _ = window.hide();
                            } else {
                                let _ = window.show();
                                let _ = window.set_focus();
                            }
                        }
                    }
                    "quit" => {
                        app.exit(0);
                    }
                    _ => {}
                })
                .build(app)?;

            // Global shortcut: Ctrl+Shift+Space → toggle widget
            #[cfg(desktop)]
            {
                use tauri_plugin_global_shortcut::{Code, Modifiers, Shortcut, ShortcutState};

                let shortcut = Shortcut::new(
                    Some(Modifiers::CONTROL | Modifiers::SHIFT),
                    Code::Space,
                );

                app.global_shortcut().on_shortcut(shortcut, move |app, _shortcut, event| {
                    if event.state == ShortcutState::Pressed {
                        if let Some(window) = app.get_webview_window("widget") {
                            if window.is_visible().unwrap_or(false) {
                                let _ = window.hide();
                            } else {
                                let _ = window.show();
                                let _ = window.set_focus();
                            }
                        }
                    }
                })?;
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            toggle_window,
            set_always_on_top,
            toggle_widget,
            hide_widget,
            inject_text,
            position_widget_bottom,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

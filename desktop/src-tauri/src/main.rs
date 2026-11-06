#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;
use tauri::{Manager, PhysicalPosition, WebviewWindow, WindowEvent};
use tauri_plugin_autostart::MacosLauncher;
#[cfg(not(debug_assertions))]
use tauri_plugin_autostart::ManagerExt;
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};

const DEFAULT_WIDTH: f64 = 420.0;

/// When true the dock never auto-collapses and stays top-most.
static PINNED: AtomicBool = AtomicBool::new(false);
/// True while the dock is fully on screen; false while collapsed to the edge.
static EXPANDED: AtomicBool = AtomicBool::new(true);

fn window_width() -> f64 {
    std::env::var("WORKBENCH_WIDTH")
        .ok()
        .and_then(|value| value.parse::<f64>().ok())
        .filter(|value| *value >= 360.0 && *value <= 1200.0)
        .unwrap_or(DEFAULT_WIDTH)
}

#[cfg(windows)]
fn work_area() -> Option<(i32, i32, i32, i32)> {
    use windows::Win32::Foundation::RECT;
    use windows::Win32::UI::WindowsAndMessaging::{
        SystemParametersInfoW, SPI_GETWORKAREA, SYSTEM_PARAMETERS_INFO_UPDATE_FLAGS,
    };
    let mut rect = RECT::default();
    let result = unsafe {
        SystemParametersInfoW(
            SPI_GETWORKAREA,
            0,
            Some(&mut rect as *mut _ as *mut _),
            SYSTEM_PARAMETERS_INFO_UPDATE_FLAGS(0),
        )
    };
    if result.is_ok() {
        Some((rect.left, rect.top, rect.right, rect.bottom))
    } else {
        None
    }
}

#[cfg(not(windows))]
fn work_area() -> Option<(i32, i32, i32, i32)> {
    None
}

#[cfg(windows)]
fn cursor_position() -> Option<(i32, i32)> {
    use windows::Win32::Foundation::POINT;
    use windows::Win32::UI::WindowsAndMessaging::GetCursorPos;
    let mut point = POINT::default();
    unsafe { GetCursorPos(&mut point).ok()? };
    Some((point.x, point.y))
}

#[cfg(not(windows))]
fn cursor_position() -> Option<(i32, i32)> {
    None
}

fn position_handle(handle: &WebviewWindow) {
    if let Some((_left, top, right, bottom)) = work_area() {
        if let Ok(size) = handle.outer_size() {
            let y = top + ((bottom - top - size.height as i32) / 2).max(0);
            let _ = handle.set_position(PhysicalPosition::new(
                right - size.width as i32,
                y,
            ));
        }
    }
}

fn configure_handle(handle: &WebviewWindow) {
    #[cfg(windows)]
    unsafe {
        use windows::Win32::Foundation::HWND;
        use windows::Win32::Graphics::Gdi::{CreateRoundRectRgn, SetWindowRgn};
        use windows::Win32::UI::WindowsAndMessaging::{
            GetWindowLongW, SetWindowLongW, GWL_EXSTYLE, WS_EX_NOACTIVATE,
            WS_EX_TOOLWINDOW,
        };
        if let Ok(native) = handle.hwnd() {
            let raw = native.0 as isize;
            let hwnd = HWND(raw as *mut core::ffi::c_void);
            let style = GetWindowLongW(hwnd, GWL_EXSTYLE);
            let style = style
                | WS_EX_NOACTIVATE.0 as i32
                | WS_EX_TOOLWINDOW.0 as i32;
            SetWindowLongW(hwnd, GWL_EXSTYLE, style);

            // The native window has a minimum width on Windows; clip its hit
            // area to the small right-edge tab so the transparent part does
            // not block clicks in other applications.
            if let Ok(size) = handle.outer_size() {
                let scale = handle.scale_factor().unwrap_or(1.0);
                let width = size.width as i32;
                let height = size.height as i32;
                if width > 0 && height > 0 {
                    let tab_w = ((12.0 * scale).round() as i32).max(8);
                    let tab_h = ((64.0 * scale).round() as i32).max(24);
                    let left = width - tab_w;
                    let top = (height - tab_h) / 2;
                    let region = CreateRoundRectRgn(
                        left,
                        top,
                        width + 1,
                        top + tab_h + 1,
                        16,
                        16,
                    );
                    SetWindowRgn(hwnd, Some(region), true);
                }
            }
        }
    }
}

fn expand(window: &WebviewWindow, focus: bool) {
    if let Some(handle) = window.app_handle().get_webview_window("handle") {
        let _ = handle.hide();
    }
    if let Some((_left, top, right, _bottom)) = work_area() {
        if let Ok(outer) = window.outer_size() {
            let x = right - outer.width as i32;
            let _ = window.set_position(PhysicalPosition::new(x, top));
        }
    }
    let _ = window.show();
    let _ = window.set_always_on_top(true);
    EXPANDED.store(true, Ordering::Relaxed);
    if focus {
        let _ = window.set_focus();
    }
}

fn collapse(window: &WebviewWindow) {
    if PINNED.load(Ordering::Relaxed) {
        return;
    }
    let _ = window.hide();
    if let Some(handle) = window.app_handle().get_webview_window("handle") {
        configure_handle(&handle);
        position_handle(&handle);
        let _ = handle.show();
        let _ = handle.set_always_on_top(true);
    }
    EXPANDED.store(false, Ordering::Relaxed);
}

fn toggle_window(app: &tauri::AppHandle, focus: bool) {
    if let Some(window) = app.get_webview_window("main") {
        if EXPANDED.load(Ordering::Relaxed) {
            collapse(&window);
        } else {
            expand(&window, focus);
        }
    }
}

fn start_edge_watcher(window: WebviewWindow, handle: WebviewWindow) {
    std::thread::spawn(move || {
        let mut hover_since: Option<std::time::Instant> = None;
        let mut outside_ticks = 0;
        loop {
            std::thread::sleep(Duration::from_millis(120));
            let Some((x, y)) = cursor_position() else {
                continue;
            };
            let expanded = EXPANDED.load(Ordering::Relaxed);

            if !expanded {
                if let Some((_left, top, right, bottom)) = work_area() {
                    let scale = handle.scale_factor().unwrap_or(1.0);
                    let tab_w = (12.0 * scale).round() as i32 + 6;
                    let tab_h = (64.0 * scale).round() as i32 + 12;
                    let center_y = top + (bottom - top) / 2;
                    let inside = x >= right - tab_w
                        && y >= center_y - tab_h / 2
                        && y <= center_y + tab_h / 2;
                    if inside {
                        let since = *hover_since
                            .get_or_insert_with(std::time::Instant::now);
                        if since.elapsed() >= Duration::from_secs(2) {
                            expand(&window, false);
                            hover_since = None;
                        }
                    } else {
                        hover_since = None;
                    }
                }
            } else if !PINNED.load(Ordering::Relaxed)
                && !window.is_focused().unwrap_or(false)
            {
                if let Ok(position) = window.outer_position() {
                    if x < position.x - 12 {
                        outside_ticks += 1;
                        if outside_ticks >= 4 {
                            collapse(&window);
                            outside_ticks = 0;
                        }
                    } else {
                        outside_ticks = 0;
                    }
                }
            } else {
                hover_since = None;
                outside_ticks = 0;
            }
        }
    });
}

fn position_window(window: &WebviewWindow) {
    if let Ok(Some(monitor)) = window.current_monitor() {
        let scale = monitor.scale_factor();
        let (work_left, work_top, work_width, work_height) = match work_area() {
            Some((left, top, right, bottom)) => (
                left as f64 / scale,
                top as f64 / scale,
                (right - left) as f64 / scale,
                (bottom - top) as f64 / scale,
            ),
            None => (
                0.0,
                0.0,
                monitor.size().width as f64 / scale,
                monitor.size().height as f64 / scale - 48.0,
            ),
        };

        let (frame_w, frame_h) = match (window.outer_size(), window.inner_size()) {
            (Ok(outer), Ok(inner)) => (
                outer.width.saturating_sub(inner.width) as f64 / scale,
                outer.height.saturating_sub(inner.height) as f64 / scale,
            ),
            _ => (14.0, 38.0),
        };

        let width = window_width();
        let target_height = (work_height - frame_h).max(600.0);
        let _ = window.set_size(tauri::LogicalSize::new(width, target_height));
        let x = work_left + work_width - width - frame_w;
        let _ = window.set_position(tauri::LogicalPosition::new(x.max(0.0), work_top));
    }
}

fn build_tray(app: &tauri::App) -> tauri::Result<()> {
    use tauri::menu::{Menu, MenuItem};
    use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};

    let show = MenuItem::with_id(app, "show", "显示 / 收起", true, None::<&str>)?;
    let pin = MenuItem::with_id(app, "pin", "切换永久置顶", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "退出", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show, &pin, &quit])?;

    let mut builder = TrayIconBuilder::new()
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "show" => toggle_window(app, true),
            "pin" => {
                let pinned = !PINNED.load(Ordering::Relaxed);
                PINNED.store(pinned, Ordering::Relaxed);
                if let Some(window) = app.get_webview_window("main") {
                    if pinned {
                        expand(&window, false);
                    } else {
                        let top = window.is_focused().unwrap_or(false);
                        let _ = window.set_always_on_top(top);
                    }
                }
            }
            "quit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                toggle_window(tray.app_handle(), true);
            }
        });
    if let Some(icon) = app.default_window_icon().cloned() {
        builder = builder.icon(icon);
    }
    builder.build(app)?;
    Ok(())
}

fn dock_log(message: &str) {
    use std::io::Write;
    let root = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
    let dir = root.join("data").join("logs");
    let _ = std::fs::create_dir_all(&dir);
    if let Ok(mut file) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(dir.join("dock.log"))
    {
        let stamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|value| value.as_secs())
            .unwrap_or(0);
        let _ = writeln!(file, "[{stamp}] {message}");
    }
}

fn server_up() -> bool {
    let addr = match "127.0.0.1:8787".parse() {
        Ok(value) => value,
        Err(_) => return false,
    };
    std::net::TcpStream::connect_timeout(&addr, Duration::from_millis(300)).is_ok()
}

fn ensure_server() {
    if server_up() {
        dock_log("server already running");
        return;
    }
    let root = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
    let script = root.join("scripts").join("start-server.ps1");
    if script.exists() {
        let mut command = std::process::Command::new("powershell.exe");
        command
            .args([
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-WindowStyle",
                "Hidden",
                "-File",
            ])
            .arg(&script);
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            command.creation_flags(CREATE_NO_WINDOW);
        }
        match command.spawn() {
            Ok(child) => dock_log(&format!("started start-server.ps1 pid={}", child.id())),
            Err(error) => dock_log(&format!("failed to start server: {error}")),
        }
    } else {
        dock_log(&format!("start-server.ps1 missing: {}", script.display()));
    }
    for _ in 0..120 {
        if server_up() {
            dock_log("server is up");
            return;
        }
        std::thread::sleep(Duration::from_millis(500));
    }
    dock_log("server did not come up within 60s");
}

fn main() {
    #[cfg(windows)]
    unsafe {
        use windows::Win32::UI::HiDpi::{
            SetProcessDpiAwarenessContext,
            DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2,
        };
        let _ = SetProcessDpiAwarenessContext(
            DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2,
        );
    }

    tauri::Builder::default()
        .plugin(tauri_plugin_autostart::init(
            MacosLauncher::LaunchAgent,
            None,
        ))
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, _shortcut, event| {
                    if event.state() == ShortcutState::Pressed {
                        toggle_window(app, true);
                    }
                })
                .build(),
        )
        .setup(|app| {
            let window = app.get_webview_window("main").expect("main window");
            position_window(&window);
            window.set_always_on_top(true)?;
            window.show()?;

            // No default global hotkey: the right-edge hover and tray are
            // enough. Power users can opt in with WORKBENCH_HOTKEY.
            if let Ok(hotkey) = std::env::var("WORKBENCH_HOTKEY") {
                let hotkey = hotkey.trim();
                if !hotkey.is_empty() {
                    if let Err(error) = app.global_shortcut().register(hotkey) {
                        eprintln!("failed to register hotkey {hotkey}: {error}");
                    }
                }
            }
            build_tray(app)?;

            #[cfg(not(debug_assertions))]
            {
                if std::env::var("WORKBENCH_AUTOSTART").as_deref() == Ok("1") {
                    let _ = app.autolaunch().enable();
                }
            }

            let blur_enabled = std::env::var("WORKBENCH_NO_BLUR").as_deref() != Ok("1");
            let w = window.clone();
            window.on_window_event(move |event| match event {
                WindowEvent::Focused(true) => {
                    let _ = w.set_always_on_top(true);
                    if !EXPANDED.load(Ordering::Relaxed) {
                        expand(&w, false);
                    }
                }
                WindowEvent::Focused(false) => {
                    if PINNED.load(Ordering::Relaxed) {
                        return;
                    }
                    // Let other windows (file dialogs, Explorer, PowerPoint, …)
                    // come forward before sliding out of the way.
                    let _ = w.set_always_on_top(false);
                    if blur_enabled {
                        let w = w.clone();
                        std::thread::spawn(move || {
                            std::thread::sleep(Duration::from_millis(350));
                            if !w.is_focused().unwrap_or(true) {
                                collapse(&w);
                            }
                        });
                    }
                }
                _ => {}
            });

            let handle = app
                .get_webview_window("handle")
                .expect("handle window");
            configure_handle(&handle);
            position_handle(&handle);
            let _ = handle.hide();

            start_edge_watcher(window.clone(), handle.clone());
            std::thread::spawn(ensure_server);
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

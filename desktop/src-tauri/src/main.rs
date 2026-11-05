#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;
use tauri::{Manager, PhysicalPosition, WebviewWindow, WindowEvent};
use tauri_plugin_autostart::MacosLauncher;
#[cfg(not(debug_assertions))]
use tauri_plugin_autostart::ManagerExt;
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};

const DEFAULT_WIDTH: f64 = 420.0;
/// How many logical pixels of the window remain visible at the right edge.
const COLLAPSED_STRIP: f64 = 8.0;

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

fn expand(window: &WebviewWindow, focus: bool) {
    if let Some((_left, top, right, _bottom)) = work_area() {
        if let Ok(outer) = window.outer_size() {
            let x = right - outer.width as i32;
            let _ = window.set_position(PhysicalPosition::new(x, top));
        }
    }
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
    if let Some((_left, top, right, _bottom)) = work_area() {
        let scale = window.scale_factor().unwrap_or(1.0);
        let strip = (COLLAPSED_STRIP * scale).round() as i32;
        let _ = window.set_position(PhysicalPosition::new(right - strip, top));
    }
    // Keep the thin strip above other windows so the right-edge hot zone works.
    let _ = window.set_always_on_top(true);
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

fn start_edge_watcher(window: WebviewWindow) {
    std::thread::spawn(move || {
        let mut outside_ticks = 0;
        loop {
            std::thread::sleep(Duration::from_millis(120));
            let Some((_left, _top, right, bottom)) = work_area() else {
                continue;
            };
            let Some((x, y)) = cursor_position() else {
                continue;
            };
            let at_edge = x >= right - 3 && y < bottom;
            let expanded = EXPANDED.load(Ordering::Relaxed);

            if at_edge && !expanded {
                expand(&window, false);
                outside_ticks = 0;
                continue;
            }

            if expanded
                && !PINNED.load(Ordering::Relaxed)
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

fn server_up() -> bool {
    let addr = match "127.0.0.1:8787".parse() {
        Ok(value) => value,
        Err(_) => return false,
    };
    std::net::TcpStream::connect_timeout(&addr, Duration::from_millis(300)).is_ok()
}

fn ensure_server() {
    if server_up() {
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
        let _ = command.spawn();
    }
    for _ in 0..60 {
        if server_up() {
            return;
        }
        std::thread::sleep(Duration::from_millis(500));
    }
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

            start_edge_watcher(window.clone());
            std::thread::spawn(ensure_server);
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;
use tauri::{Manager, WindowEvent};
use tauri_plugin_autostart::MacosLauncher;
#[cfg(not(debug_assertions))]
use tauri_plugin_autostart::ManagerExt;
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};

const DEFAULT_WIDTH: f64 = 420.0;

/// When false, the window is top-most only while focused, so other windows
/// (file explorer, PowerPoint, …) can come forward. The tray menu can pin it.
static PINNED: AtomicBool = AtomicBool::new(false);

fn window_width() -> f64 {
    std::env::var("WORKBENCH_WIDTH")
        .ok()
        .and_then(|value| value.parse::<f64>().ok())
        .filter(|value| *value >= 360.0 && *value <= 1200.0)
        .unwrap_or(DEFAULT_WIDTH)
}

fn toggle_window(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        if window.is_visible().unwrap_or(false) {
            let _ = window.hide();
        } else {
            let _ = window.show();
            let _ = window.set_always_on_top(true);
            let _ = window.set_focus();
        }
    }
}

fn position_window(window: &tauri::WebviewWindow) {
    if let Ok(Some(monitor)) = window.current_monitor() {
        let scale = monitor.scale_factor();

        #[cfg(windows)]
        let (work_left, work_top, work_width, work_height) = {
            use windows::Win32::Foundation::RECT;
            use windows::Win32::UI::WindowsAndMessaging::{
                SystemParametersInfoW, SPI_GETWORKAREA,
                SYSTEM_PARAMETERS_INFO_UPDATE_FLAGS,
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
                (
                    rect.left as f64 / scale,
                    rect.top as f64 / scale,
                    (rect.right - rect.left) as f64 / scale,
                    (rect.bottom - rect.top) as f64 / scale,
                )
            } else {
                (
                    0.0,
                    0.0,
                    monitor.size().width as f64 / scale,
                    monitor.size().height as f64 / scale - 48.0,
                )
            }
        };

        #[cfg(not(windows))]
        let (work_left, work_top, work_width, work_height) = (
            0.0,
            0.0,
            monitor.size().width as f64 / scale,
            monitor.size().height as f64 / scale - 48.0,
        );

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
        let y = work_top;
        let _ = window.set_position(tauri::LogicalPosition::new(x.max(0.0), y));
    }
}

fn build_tray(app: &tauri::App) -> tauri::Result<()> {
    use tauri::menu::{Menu, MenuItem};
    use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};

    let show = MenuItem::with_id(app, "show", "显示 / 隐藏", true, None::<&str>)?;
    let pin = MenuItem::with_id(app, "pin", "切换置顶", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "退出", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show, &pin, &quit])?;

    let mut builder = TrayIconBuilder::new()
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "show" => toggle_window(app),
            "pin" => {
                let pinned = !PINNED.load(Ordering::Relaxed);
                PINNED.store(pinned, Ordering::Relaxed);
                if let Some(window) = app.get_webview_window("main") {
                    let top = pinned || window.is_focused().unwrap_or(false);
                    let _ = window.set_always_on_top(top);
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
                toggle_window(tray.app_handle());
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
                        toggle_window(app);
                    }
                })
                .build(),
        )
        .setup(|app| {
            let window = app.get_webview_window("main").expect("main window");
            position_window(&window);
            window.set_always_on_top(true)?;
            window.show()?;

            let hotkey = std::env::var("WORKBENCH_HOTKEY")
                .unwrap_or_else(|_| "ctrl+alt+shift+w".to_string());
            if let Err(error) = app.global_shortcut().register(hotkey.as_str()) {
                eprintln!("failed to register hotkey {hotkey}: {error}");
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
                }
                WindowEvent::Focused(false) => {
                    // Not pinned: let other windows (file dialogs, Explorer,
                    // PowerPoint, …) come forward instead of being covered.
                    if !PINNED.load(Ordering::Relaxed) {
                        let _ = w.set_always_on_top(false);
                    }
                    if blur_enabled && !PINNED.load(Ordering::Relaxed) {
                        let w = w.clone();
                        std::thread::spawn(move || {
                            std::thread::sleep(Duration::from_millis(400));
                            if !w.is_focused().unwrap_or(true) {
                                let _ = w.hide();
                            }
                        });
                    }
                }
                _ => {}
            });

            std::thread::spawn(ensure_server);
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

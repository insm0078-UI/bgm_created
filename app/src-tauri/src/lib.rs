//! AI BGM Studio desktop shell: starts the AI engine and exposes its connection to the UI.

mod engine;
mod job_guard;

use engine::{EngineInfo, EnginePaths, EngineState};
use serde::Serialize;
use tauri::{Manager, RunEvent};

/// Engine status as seen by the UI before HTTP is reachable.
#[derive(Serialize)]
struct EngineStatus {
    info: Option<EngineInfo>,
    exited: Option<i32>,
    start_error: Option<String>,
}

struct StartError(Option<String>);

#[tauri::command]
fn engine_status(
    engine: tauri::State<'_, Option<EngineState>>,
    err: tauri::State<'_, StartError>,
) -> EngineStatus {
    match engine.inner() {
        Some(state) => EngineStatus {
            info: Some(state.info.clone()),
            exited: state.exit_code(),
            start_error: None,
        },
        None => EngineStatus { info: None, exited: None, start_error: err.0.clone() },
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            // Must run before the engine is spawned so it inherits the kill-on-close job.
            if !job_guard::bind_children_to_app_lifetime() {
                eprintln!("job object unavailable; engine cleanup relies on normal exit");
            }
            let exe_dir = std::env::current_exe()?
                .parent()
                .map(|p| p.to_path_buf())
                .unwrap_or_default();
            let data_dir = app.path().app_local_data_dir()?;
            let paths = EnginePaths::resolve(&exe_dir, &data_dir);
            match EngineState::start(&paths) {
                Ok(state) => {
                    app.manage(Some(state));
                    app.manage(StartError(None));
                }
                Err(e) => {
                    app.manage(None::<EngineState>);
                    app.manage(StartError(Some(e)));
                }
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![engine_status])
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            if let Some(state) = handle.state::<Option<EngineState>>().inner() {
                state.stop();
            }
        }
    });
}

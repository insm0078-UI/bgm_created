//! Launches the Python BGM engine as a hidden child process and stops it on exit.

use std::fs::{self, File};
use std::net::TcpListener;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use serde::Serialize;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

/// Paths needed to start the engine.
pub struct EnginePaths {
    pub python: PathBuf,
    pub engine_dir: PathBuf,
    pub acestep_root: PathBuf,
    pub output_dir: PathBuf,
    pub log_file: PathBuf,
}

impl EnginePaths {
    /// Resolve paths: `BGM_*` env vars override the installed layout next to the exe.
    pub fn resolve(exe_dir: &Path, data_dir: &Path) -> Self {
        let pick = |var: &str, default: PathBuf| {
            std::env::var_os(var).map(PathBuf::from).unwrap_or(default)
        };
        let base = exe_dir.join("engine");
        Self {
            python: pick("BGM_PYTHON", base.join("python").join("python.exe")),
            engine_dir: pick("BGM_ENGINE_DIR", base.join("bgm")),
            acestep_root: pick("BGM_ACESTEP_ROOT", base.join("acestep")),
            output_dir: data_dir.join("outputs"),
            log_file: data_dir.join("logs").join("engine.log"),
        }
    }
}

/// Connection details the UI needs to talk to the engine.
#[derive(Clone, Serialize)]
pub struct EngineInfo {
    pub port: u16,
    pub token: String,
    pub log_file: String,
    pub output_dir: String,
}

/// Running engine process plus its connection info.
pub struct EngineState {
    pub info: EngineInfo,
    child: Mutex<Option<Child>>,
}

impl EngineState {
    /// Start the engine on a free localhost port with a fresh random token.
    pub fn start(paths: &EnginePaths) -> Result<Self, String> {
        let port = free_port()?;
        let token = uuid::Uuid::new_v4().simple().to_string();
        fs::create_dir_all(&paths.output_dir).map_err(|e| e.to_string())?;
        if let Some(dir) = paths.log_file.parent() {
            fs::create_dir_all(dir).map_err(|e| e.to_string())?;
        }
        // Keep the previous run's log so a crash can still be diagnosed after a restart.
        if paths.log_file.exists() {
            let _ = fs::rename(&paths.log_file, paths.log_file.with_extension("prev.log"));
        }
        let log = File::create(&paths.log_file).map_err(|e| e.to_string())?;
        let log_err = log.try_clone().map_err(|e| e.to_string())?;

        let mut cmd = Command::new(&paths.python);
        cmd.args(["-m", "bgm_engine", "--port", &port.to_string()])
            .arg("--project-root").arg(&paths.acestep_root)
            .arg("--output-dir").arg(&paths.output_dir)
            .current_dir(&paths.engine_dir)
            .env("BGM_ENGINE_TOKEN", &token)
            .env("PYTHONPATH", &paths.engine_dir)
            .env("PYTHONIOENCODING", "utf-8")
            .stdin(Stdio::null())
            .stdout(Stdio::from(log))
            .stderr(Stdio::from(log_err));
        #[cfg(windows)]
        cmd.creation_flags(CREATE_NO_WINDOW);

        let child = cmd
            .spawn()
            .map_err(|e| format!("AI 엔진을 시작하지 못했습니다 ({}): {e}", paths.python.display()))?;
        Ok(Self {
            info: EngineInfo {
                port,
                token,
                log_file: paths.log_file.display().to_string(),
                output_dir: paths.output_dir.display().to_string(),
            },
            child: Mutex::new(Some(child)),
        })
    }

    /// Return the exit code if the engine process has already exited.
    pub fn exit_code(&self) -> Option<i32> {
        let mut guard = self.child.lock().ok()?;
        let child = guard.as_mut()?;
        match child.try_wait() {
            Ok(Some(status)) => Some(status.code().unwrap_or(-1)),
            _ => None,
        }
    }

    /// Kill the engine and any processes it spawned.
    pub fn stop(&self) {
        let Ok(mut guard) = self.child.lock() else { return };
        if let Some(mut child) = guard.take() {
            kill_tree(child.id());
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

fn free_port() -> Result<u16, String> {
    let listener = TcpListener::bind("127.0.0.1:0").map_err(|e| e.to_string())?;
    listener.local_addr().map(|a| a.port()).map_err(|e| e.to_string())
}

#[cfg(windows)]
fn kill_tree(pid: u32) {
    let _ = Command::new("taskkill")
        .args(["/PID", &pid.to_string(), "/T", "/F"])
        .creation_flags(CREATE_NO_WINDOW)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status();
}

#[cfg(not(windows))]
fn kill_tree(_pid: u32) {}

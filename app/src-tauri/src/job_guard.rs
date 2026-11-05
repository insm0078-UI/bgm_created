//! Ties every child process (the Python AI engine and anything it spawns) to this app's
//! lifetime using a Windows Job Object with KILL_ON_JOB_CLOSE.
//!
//! The app puts *itself* into the job before starting the engine, so children inherit
//! membership automatically (no race with the venv launcher spawning the real interpreter).
//! The job handle is intentionally never closed: when the app exits for any reason —
//! including a crash or a Task Manager kill — Windows closes it and terminates the children,
//! so the engine can never keep holding GPU memory on its own.

/// Put the current process into a kill-on-close job. Returns false if it could not be done
/// (the app still works; it just falls back to the normal exit-time cleanup).
#[cfg(windows)]
pub fn bind_children_to_app_lifetime() -> bool {
    use windows_sys::Win32::Foundation::CloseHandle;
    use windows_sys::Win32::System::JobObjects::{
        AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
        SetInformationJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    };
    use windows_sys::Win32::System::Threading::GetCurrentProcess;

    // SAFETY: plain Win32 calls with valid arguments; the handle is checked before use and
    // deliberately leaked so it lives exactly as long as this process.
    unsafe {
        let job = CreateJobObjectW(std::ptr::null(), std::ptr::null());
        if job.is_null() {
            return false;
        }
        let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = std::mem::zeroed();
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        let set = SetInformationJobObject(
            job,
            JobObjectExtendedLimitInformation,
            &info as *const _ as *const core::ffi::c_void,
            std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
        );
        if set == 0 || AssignProcessToJobObject(job, GetCurrentProcess()) == 0 {
            CloseHandle(job);
            return false;
        }
        true
    }
}

#[cfg(not(windows))]
pub fn bind_children_to_app_lifetime() -> bool {
    false
}

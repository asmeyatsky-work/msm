use std::error::Error;

/// Render a reqwest error with its full source chain so opaque wrappers like
/// "error decoding response body" surface the real cause (hyper Io, h2, etc.).
pub fn reqwest_chain(stage: &str, e: &reqwest::Error) -> String {
    let mut out = format!("{stage}: {e}");
    let mut src: Option<&dyn Error> = e.source();
    while let Some(s) = src {
        out.push_str(" -> ");
        out.push_str(&s.to_string());
        src = s.source();
    }
    out
}

/// Short, log-safe excerpt of an upstream body for error messages.
pub fn snippet(bytes: &[u8]) -> String {
    const MAX: usize = 240;
    let s = String::from_utf8_lossy(bytes);
    let s = s.trim();
    if s.len() <= MAX {
        s.to_string()
    } else {
        format!("{}…(+{} bytes)", &s[..MAX], s.len() - MAX)
    }
}

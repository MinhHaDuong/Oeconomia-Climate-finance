use std::collections::HashMap;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{self, Command};

// ---------------------------------------------------------------------------
// Ticket parser (mirrors ticket_parser.py)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
struct Ticket {
    path: PathBuf,
    headers: HashMap<String, Vec<String>>,
    log_lines: Vec<String>,
    body: String,
}

impl Ticket {
    fn id(&self) -> &str {
        self.headers
            .get("Id")
            .and_then(|v| v.first())
            .map(|s| s.as_str())
            .unwrap_or("")
    }

    fn title(&self) -> &str {
        self.headers
            .get("Title")
            .and_then(|v| v.first())
            .map(|s| s.as_str())
            .unwrap_or("")
    }

    fn status(&self) -> &str {
        self.headers
            .get("Status")
            .and_then(|v| v.first())
            .map(|s| s.as_str())
            .unwrap_or("")
    }

    fn blocked_by(&self) -> &[String] {
        self.headers
            .get("Blocked-by")
            .map(|v| v.as_slice())
            .unwrap_or(&[])
    }

    fn filename_id(&self) -> &str {
        let stem = self.path.file_stem().unwrap_or_default().to_str().unwrap_or("");
        match stem.find('-') {
            Some(pos) => &stem[..pos],
            None => stem,
        }
    }

    fn filename(&self) -> &str {
        self.path.file_name().unwrap_or_default().to_str().unwrap_or("")
    }
}

/// Parse header line: starts with a key (letter then alphanumeric/dash/underscore),
/// followed by optional whitespace, colon, optional whitespace, then value.
fn parse_header_line(line: &str) -> Option<(String, String)> {
    let bytes = line.as_bytes();
    if bytes.is_empty() {
        return None;
    }
    // First char must be a letter
    if !bytes[0].is_ascii_alphabetic() {
        return None;
    }
    // Find the colon
    let mut colon_pos = None;
    for (i, &b) in bytes.iter().enumerate().skip(1) {
        if b == b':' {
            colon_pos = Some(i);
            break;
        }
        // Key chars: letters, digits, underscore, hyphen
        if !(b.is_ascii_alphanumeric() || b == b'_' || b == b'-') {
            // Allow whitespace before colon
            if b == b' ' || b == b'\t' {
                // scan ahead for colon
                let rest = &bytes[i..];
                for (j, &c) in rest.iter().enumerate() {
                    if c == b':' {
                        colon_pos = Some(i + j);
                        break;
                    }
                    if c != b' ' && c != b'\t' {
                        return None;
                    }
                }
                break;
            }
            return None;
        }
    }
    let colon_pos = colon_pos?;
    let key = line[..colon_pos].trim_end().to_string();
    let val = line[colon_pos + 1..].trim().to_string();
    Some((key, val))
}

fn parse_ticket(path: &Path) -> Ticket {
    let text = fs::read_to_string(path).unwrap_or_default();
    let lines: Vec<&str> = text.split('\n').collect();

    let mut headers: HashMap<String, Vec<String>> = HashMap::new();
    let mut log_lines: Vec<String> = Vec::new();
    let mut body_lines: Vec<String> = Vec::new();

    let mut section = "headers"; // headers | gap | log | body
    let mut body_seen = false;

    for line in &lines {
        if !body_seen && line.trim() == "--- log ---" {
            section = "log";
            continue;
        }
        if !body_seen && line.trim() == "--- body ---" {
            section = "body";
            body_seen = true;
            continue;
        }

        match section {
            "headers" => {
                if line.trim().is_empty() {
                    section = "gap";
                    continue;
                }
                if let Some((key, val)) = parse_header_line(line) {
                    headers.entry(key).or_default().push(val);
                }
            }
            "gap" => {} // ignore
            "log" => {
                if !line.trim().is_empty() {
                    log_lines.push(line.to_string());
                }
            }
            "body" => {
                body_lines.push(line.to_string());
            }
            _ => {}
        }
    }

    Ticket {
        path: path.to_path_buf(),
        headers,
        log_lines,
        body: body_lines.join("\n"),
    }
}

fn load_tickets(dir: &Path) -> Vec<Ticket> {
    let mut entries: Vec<PathBuf> = Vec::new();
    if let Ok(rd) = fs::read_dir(dir) {
        for entry in rd.flatten() {
            let p = entry.path();
            if p.extension().map(|e| e == "ticket").unwrap_or(false) && p.is_file() {
                entries.push(p);
            }
        }
    }
    entries.sort();
    entries.iter().map(|p| parse_ticket(p)).collect()
}

// ---------------------------------------------------------------------------
// Validate (mirrors validate_tickets.py)
// ---------------------------------------------------------------------------

const REQUIRED_HEADERS: &[&str] = &["Id", "Title", "Author", "Status", "Created"];
const VALID_STATUSES: &[&str] = &["closed", "doing", "open", "pending"];
const VALID_PHASES: &[&str] = &["celebrating", "doing", "dreaming", "planning"];

fn validate_ticket(ticket: &Ticket, all_ids: &HashMap<String, bool>) -> Vec<String> {
    let mut errors = Vec::new();
    let path = ticket.filename();

    // Required headers
    for &hdr in REQUIRED_HEADERS {
        if !ticket.headers.contains_key(hdr) {
            errors.push(format!("{}: missing required header '{}'", path, hdr));
        }
    }

    // Id/filename consistency
    let id = ticket.id();
    if !id.is_empty() && ticket.filename_id() != id {
        errors.push(format!(
            "{}: Id '{}' does not match filename prefix '{}'",
            path,
            id,
            ticket.filename_id()
        ));
    }

    // Valid Status
    let status = ticket.status();
    if !status.is_empty() && !VALID_STATUSES.contains(&status) {
        errors.push(format!(
            "{}: invalid Status '{}' (expected one of: {})",
            path,
            status,
            VALID_STATUSES.join(", ")
        ));
    }

    // Valid X-Phase
    if let Some(phases) = ticket.headers.get("X-Phase") {
        for phase in phases {
            if !VALID_PHASES.contains(&phase.as_str()) {
                errors.push(format!(
                    "{}: invalid X-Phase '{}' (expected one of: {})",
                    path,
                    phase,
                    VALID_PHASES.join(", ")
                ));
            }
        }
    }

    // Blocked-by references exist
    for ref_id in ticket.blocked_by() {
        if !all_ids.contains_key(ref_id.as_str()) {
            errors.push(format!(
                "{}: Blocked-by '{}' references unknown ticket ID",
                path, ref_id
            ));
        }
    }

    errors
}

fn detect_cycles(tickets: &[Ticket]) -> Vec<String> {
    let mut errors = Vec::new();

    // Build adjacency list
    let mut adj: HashMap<&str, Vec<&str>> = HashMap::new();
    for t in tickets {
        let id = t.id();
        if !id.is_empty() {
            let deps: Vec<&str> = t.blocked_by().iter().map(|s| s.as_str()).collect();
            adj.insert(id, deps);
        }
    }

    // DFS with coloring
    const WHITE: u8 = 0;
    const GRAY: u8 = 1;
    const BLACK: u8 = 2;

    let mut color: HashMap<&str, u8> = HashMap::new();
    for &tid in adj.keys() {
        color.insert(tid, WHITE);
    }

    fn dfs<'a>(
        node: &'a str,
        path: &mut Vec<&'a str>,
        adj: &HashMap<&'a str, Vec<&'a str>>,
        color: &mut HashMap<&'a str, u8>,
        errors: &mut Vec<String>,
    ) {
        color.insert(node, GRAY);
        path.push(node);
        if let Some(neighbors) = adj.get(node) {
            for &neighbor in neighbors {
                match color.get(neighbor) {
                    Some(&GRAY) => {
                        // Found cycle
                        let cycle_start = path.iter().position(|&n| n == neighbor).unwrap();
                        let mut cycle: Vec<&str> = path[cycle_start..].to_vec();
                        cycle.push(neighbor);
                        errors.push(format!(
                            "dependency cycle: {}",
                            cycle.join(" -> ")
                        ));
                    }
                    Some(&WHITE) => {
                        dfs(neighbor, path, adj, color, errors);
                    }
                    _ => {} // BLACK or unknown — skip
                }
            }
        }
        path.pop();
        color.insert(node, BLACK);
    }

    // Iterate in sorted order for deterministic output
    let mut keys: Vec<&str> = adj.keys().copied().collect();
    keys.sort();
    for tid in keys {
        if color.get(tid) == Some(&WHITE) {
            let mut path = Vec::new();
            dfs(tid, &mut path, &adj, &mut color, &mut errors);
        }
    }

    errors
}

fn validate_all(tickets: &[Ticket], extra_ids: &[String]) -> Vec<String> {
    let mut errors = Vec::new();

    // Collect IDs and check duplicates
    let mut id_to_files: HashMap<String, Vec<String>> = HashMap::new();
    for t in tickets {
        let id = t.id();
        if !id.is_empty() {
            id_to_files
                .entry(id.to_string())
                .or_default()
                .push(t.filename().to_string());
        }
    }

    // Sort for deterministic output
    let mut dup_ids: Vec<&String> = id_to_files.keys().collect();
    dup_ids.sort();
    for tid in &dup_ids {
        let files = &id_to_files[*tid];
        if files.len() > 1 {
            // Suggest next available suffix
            let base = tid.trim_end_matches(|c: char| c.is_ascii_digit());
            let mut existing_nums: Vec<i32> = Vec::new();
            for other_id in id_to_files.keys() {
                if other_id == base {
                    existing_nums.push(1);
                } else if other_id.starts_with(base) {
                    let suffix = &other_id[base.len()..];
                    if let Ok(n) = suffix.parse::<i32>() {
                        existing_nums.push(n);
                    }
                }
            }
            let next_num = existing_nums.iter().max().unwrap_or(&1) + 1;
            errors.push(format!(
                "duplicate Id '{}' in: {} -- next available: {}{}",
                tid,
                files.join(", "),
                base,
                next_num
            ));
        }
    }

    // Build all_ids map
    let mut all_ids: HashMap<String, bool> = HashMap::new();
    for tid in id_to_files.keys() {
        all_ids.insert(tid.clone(), true);
    }
    for eid in extra_ids {
        all_ids.insert(eid.clone(), true);
    }

    // Per-ticket validation
    for t in tickets {
        errors.extend(validate_ticket(t, &all_ids));
    }

    errors.extend(detect_cycles(tickets));

    errors
}

fn cmd_validate(args: &[String]) -> i32 {
    let mut targets = args.to_vec();
    if targets.is_empty() {
        targets.push("tickets/".to_string());
    }

    let mut tickets: Vec<Ticket> = Vec::new();
    for arg in &targets {
        let p = Path::new(arg);
        if p.is_dir() {
            tickets.extend(load_tickets(p));
        } else if p.is_file() && p.extension().map(|e| e == "ticket").unwrap_or(false) {
            tickets.push(parse_ticket(p));
        } else {
            println!("WARNING: skipping {} (not a .ticket file or directory)", arg);
        }
    }

    if tickets.is_empty() {
        println!("No .ticket files found.");
        return 0;
    }

    // Load archived ticket IDs
    let mut extra_ids: Vec<String> = Vec::new();
    for arg in &targets {
        let p = Path::new(arg);
        if p.is_dir() {
            let archive_dir = p.join("archive");
            if archive_dir.is_dir() {
                for at in load_tickets(&archive_dir) {
                    let id = at.id().to_string();
                    if !id.is_empty() {
                        extra_ids.push(id);
                    }
                }
            }
        }
    }

    let errors = validate_all(&tickets, &extra_ids);

    if !errors.is_empty() {
        println!("TICKET VALIDATION FAILED ({} error(s)):", errors.len());
        for e in &errors {
            println!("  {}", e);
        }
        1
    } else {
        println!("TICKET VALIDATION: PASS ({} tickets)", tickets.len());
        0
    }
}

// ---------------------------------------------------------------------------
// Ready (mirrors ready_tickets.py)
// ---------------------------------------------------------------------------

fn cmd_ready(args: &[String]) -> i32 {
    let use_json = args.contains(&"--json".to_string());
    let filtered: Vec<&String> = args.iter().filter(|a| *a != "--json").collect();
    let ticket_dir = if let Some(d) = filtered.first() {
        PathBuf::from(d)
    } else {
        PathBuf::from("tickets")
    };

    if !ticket_dir.exists() {
        println!("Directory not found: {}", ticket_dir.display());
        return 1;
    }

    let tickets = load_tickets(&ticket_dir);
    let status_by_id: HashMap<&str, &str> = tickets
        .iter()
        .map(|t| (t.id(), t.status()))
        .collect();

    let mut warnings: Vec<String> = Vec::new();
    let mut ready: Vec<(&str, &str, &str)> = Vec::new(); // (id, title, filename)

    for t in &tickets {
        if t.status() != "open" {
            continue;
        }

        let mut blocked = false;
        for ref_id in t.blocked_by() {
            match status_by_id.get(ref_id.as_str()) {
                None => {
                    warnings.push(format!(
                        "{}: Blocked-by '{}' not found (treating as satisfied)",
                        t.filename(),
                        ref_id
                    ));
                }
                Some(&status) if status != "closed" => {
                    blocked = true;
                    break;
                }
                _ => {}
            }
        }

        if !blocked {
            ready.push((t.id(), t.title(), t.filename()));
        }
    }

    for w in &warnings {
        eprintln!("WARNING: {}", w);
    }

    if use_json {
        // Manual JSON output — no serde
        if ready.is_empty() {
            println!("[]");
        } else {
            println!("[");
            for (i, (id, title, file)) in ready.iter().enumerate() {
                let comma = if i + 1 < ready.len() { "," } else { "" };
                println!("  {{");
                println!("    \"id\": \"{}\",", json_escape(id));
                println!("    \"title\": \"{}\",", json_escape(title));
                println!("    \"file\": \"{}\"", json_escape(file));
                println!("  }}{}", comma);
            }
            println!("]");
        }
    } else if ready.is_empty() {
        println!("No ready tickets.");
    } else {
        println!("Ready tickets ({}):", ready.len());
        for (id, title, file) in &ready {
            println!("  {:8} {:40} {}", id, file, title);
        }
    }

    0
}

fn json_escape(s: &str) -> String {
    s.replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
        .replace('\r', "\\r")
        .replace('\t', "\\t")
}

// ---------------------------------------------------------------------------
// Archive (mirrors archive_tickets.py)
// ---------------------------------------------------------------------------

const DAG_HEADERS: &[&str] = &["Blocked-by", "X-Discovered-from", "X-Supersedes"];

/// Parse timestamp from start of a log line: 2026-03-21T12:00Z or 2026-03-21T12:00
fn parse_log_timestamp(line: &str) -> Option<i64> {
    let line = line.trim();
    // Match YYYY-MM-DDTHH:MM(:SS)?Z?
    // We'll parse manually
    if line.len() < 16 {
        return None;
    }
    // Check format: digit pattern
    let bytes = line.as_bytes();
    if bytes[4] != b'-' || bytes[7] != b'-' || bytes[10] != b'T' || bytes[13] != b':' {
        return None;
    }
    for &i in &[0, 1, 2, 3, 5, 6, 8, 9, 11, 12, 14, 15] {
        if !bytes[i].is_ascii_digit() {
            return None;
        }
    }

    let year: i64 = line[0..4].parse().ok()?;
    let month: i64 = line[5..7].parse().ok()?;
    let day: i64 = line[8..10].parse().ok()?;
    let hour: i64 = line[11..13].parse().ok()?;
    let min: i64 = line[14..16].parse().ok()?;

    // Seconds are optional
    let mut sec: i64 = 0;
    if line.len() > 16 && bytes[16] == b':' && line.len() >= 19 {
        sec = line[17..19].parse().unwrap_or(0);
    }

    // Convert to a rough unix-ish timestamp (good enough for day comparison)
    // Using a simplified calculation
    Some(
        year * 365 * 24 * 3600
            + month * 30 * 24 * 3600
            + day * 24 * 3600
            + hour * 3600
            + min * 60
            + sec,
    )
}

fn now_timestamp() -> i64 {
    // Use std::time to get current time
    let dur = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default();
    let secs = dur.as_secs() as i64;

    // Convert unix timestamp to our simplified format for comparison
    // Unix epoch: 1970-01-01. We need year/month/day.
    // Simpler approach: convert both to days since epoch for comparison.
    // Actually let's just use a consistent scheme. Both sides use the same
    // simplified formula, so comparisons work even if absolute values are off.

    // Get current date from unix seconds
    let days_since_epoch = secs / 86400;
    // Approximate: 365.25 days per year
    let year = 1970 + days_since_epoch / 365;
    let remaining_days = days_since_epoch % 365;
    let month = remaining_days / 30 + 1;
    let day = remaining_days % 30 + 1;
    let day_secs = secs % 86400;
    let hour = day_secs / 3600;
    let min = (day_secs % 3600) / 60;
    let sec = day_secs % 60;

    year * 365 * 24 * 3600
        + month * 30 * 24 * 3600
        + day * 24 * 3600
        + hour * 3600
        + min * 60
        + sec
}

fn cmd_archive(args: &[String]) -> i32 {
    let execute = args.contains(&"--execute".to_string());
    let filtered: Vec<&String> = args.iter().filter(|a| *a != "--execute").collect();

    let mut days: i64 = 90;
    let mut ticket_dir = PathBuf::from("tickets");

    let mut i = 0;
    while i < filtered.len() {
        let arg = filtered[i];
        if arg.starts_with("--days=") {
            days = arg.split_once('=').unwrap().1.parse().unwrap_or(90);
            i += 1;
        } else if arg == "--days" && i + 1 < filtered.len() {
            days = filtered[i + 1].parse().unwrap_or(90);
            i += 2;
        } else if !arg.starts_with("--") {
            ticket_dir = PathBuf::from(arg);
            i += 1;
        } else {
            i += 1;
        }
    }

    if !ticket_dir.exists() {
        println!("Directory not found: {}", ticket_dir.display());
        return 1;
    }

    let tickets = load_tickets(&ticket_dir);
    let cutoff = now_timestamp() - days * 24 * 3600;

    // Collect all IDs referenced by DAG headers
    let mut referenced_ids: std::collections::HashSet<String> = std::collections::HashSet::new();
    let archive_dir = ticket_dir.join("archive");
    let mut all_tickets = tickets.clone();
    if archive_dir.is_dir() {
        all_tickets.extend(load_tickets(&archive_dir));
    }
    for t in &all_tickets {
        for &hdr in DAG_HEADERS {
            if let Some(vals) = t.headers.get(hdr) {
                for val in vals {
                    referenced_ids.insert(val.clone());
                }
            }
        }
    }

    // Find closed tickets older than cutoff
    let mut candidates: Vec<&Ticket> = Vec::new();
    for t in &tickets {
        if t.status() != "closed" {
            continue;
        }
        if let Some(last_line) = t.log_lines.last() {
            if let Some(ts) = parse_log_timestamp(last_line) {
                if ts < cutoff {
                    candidates.push(t);
                }
            }
        }
    }

    let mut archivable: Vec<&Ticket> = Vec::new();
    let mut dag_protected: Vec<&Ticket> = Vec::new();
    for t in &candidates {
        if referenced_ids.contains(t.id()) {
            dag_protected.push(t);
        } else {
            archivable.push(t);
        }
    }

    if !dag_protected.is_empty() {
        let ids: Vec<&str> = dag_protected.iter().map(|t| t.id()).collect();
        println!(
            "DAG-protected (skipping {}): {}",
            dag_protected.len(),
            ids.join(", ")
        );
    }

    if archivable.is_empty() {
        println!("Nothing to archive (threshold: {} days).", days);
        return 0;
    }

    let ids: Vec<&str> = archivable.iter().map(|t| t.id()).collect();
    println!(
        "Will archive {} ticket(s): {}",
        archivable.len(),
        ids.join(", ")
    );

    if !execute {
        println!("Dry run. Pass --execute to proceed.");
        return 0;
    }

    fs::create_dir_all(&archive_dir).ok();

    for t in &archivable {
        let dest = archive_dir.join(t.filename());
        let result = Command::new("git")
            .args(["mv", &t.path.to_string_lossy(), &dest.to_string_lossy()])
            .status();
        match result {
            Ok(s) if s.success() => println!("  moved {}", t.filename()),
            _ => {
                eprintln!("git mv failed for {}", t.filename());
                return 1;
            }
        }
    }

    let msg = format!(
        "archive {} closed tickets (>{} days, DAG-safe)",
        archivable.len(),
        days
    );
    let result = Command::new("git").args(["commit", "-m", &msg]).status();
    match result {
        Ok(s) if s.success() => println!("Committed: {}", msg),
        _ => {
            eprintln!("git commit failed");
            return 1;
        }
    }

    0
}

// ---------------------------------------------------------------------------
// Main dispatch
// ---------------------------------------------------------------------------

fn print_usage() {
    eprintln!("Usage: ticket-tools <command> [args...]");
    eprintln!();
    eprintln!("Commands:");
    eprintln!("  validate [dir|files...]   Validate .ticket files");
    eprintln!("  ready [dir] [--json]      Show tickets ready for work");
    eprintln!("  archive [dir] [--days N] [--execute]  Archive old closed tickets");
}

fn main() {
    let args: Vec<String> = env::args().collect();

    if args.len() < 2 {
        print_usage();
        process::exit(1);
    }

    let command = &args[1];
    let rest = &args[2..];

    let exit_code = match command.as_str() {
        "validate" => cmd_validate(rest),
        "ready" => cmd_ready(rest),
        "archive" => cmd_archive(rest),
        "-h" | "--help" | "help" => {
            print_usage();
            0
        }
        _ => {
            eprintln!("Unknown command: {}", command);
            print_usage();
            1
        }
    };

    process::exit(exit_code);
}

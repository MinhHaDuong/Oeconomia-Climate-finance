// ticket-tools — validate, ready, archive .ticket files.
// No external dependencies (stdlib only).
//
// Usage:
//
//	ticket-tools validate [dir|file ...]
//	ticket-tools ready    [dir] [--json]
//	ticket-tools archive  [dir] [--days N] [--execute]
package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

// ---------------------------------------------------------------------------
// Ticket parser (mirrors ticket_parser.py)
// ---------------------------------------------------------------------------

type Ticket struct {
	Path     string
	Headers  map[string][]string // repeatable headers
	LogLines []string
	Body     string
}

func (t *Ticket) ID() string {
	if vs, ok := t.Headers["Id"]; ok && len(vs) > 0 {
		return vs[0]
	}
	return ""
}

func (t *Ticket) Title() string {
	if vs, ok := t.Headers["Title"]; ok && len(vs) > 0 {
		return vs[0]
	}
	return ""
}

func (t *Ticket) Status() string {
	if vs, ok := t.Headers["Status"]; ok && len(vs) > 0 {
		return vs[0]
	}
	return ""
}

func (t *Ticket) BlockedBy() []string {
	if vs, ok := t.Headers["Blocked-by"]; ok {
		return vs
	}
	return nil
}

func (t *Ticket) Filename() string {
	return filepath.Base(t.Path)
}

func (t *Ticket) FilenameID() string {
	stem := strings.TrimSuffix(t.Filename(), ".ticket")
	if idx := strings.Index(stem, "-"); idx > 0 {
		return stem[:idx]
	}
	return stem
}

// parseHeaderLine extracts "Key: value" from a line.
func parseHeaderLine(line string) (string, string, bool) {
	if len(line) == 0 || !isLetter(line[0]) {
		return "", "", false
	}
	colonPos := -1
	for i := 1; i < len(line); i++ {
		c := line[i]
		if c == ':' {
			colonPos = i
			break
		}
		if isAlphanumeric(c) || c == '_' || c == '-' {
			continue
		}
		if c == ' ' || c == '\t' {
			// scan ahead for colon
			for j := i; j < len(line); j++ {
				if line[j] == ':' {
					colonPos = j
					break
				}
				if line[j] != ' ' && line[j] != '\t' {
					return "", "", false
				}
			}
			break
		}
		return "", "", false
	}
	if colonPos < 0 {
		return "", "", false
	}
	key := strings.TrimSpace(line[:colonPos])
	val := strings.TrimSpace(line[colonPos+1:])
	return key, val, true
}

func isLetter(c byte) bool {
	return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z')
}

func isAlphanumeric(c byte) bool {
	return isLetter(c) || (c >= '0' && c <= '9')
}

func parseTicket(path string) Ticket {
	data, err := os.ReadFile(path)
	if err != nil {
		return Ticket{Path: path, Headers: make(map[string][]string)}
	}
	lines := strings.Split(string(data), "\n")

	headers := make(map[string][]string)
	var logLines, bodyLines []string
	section := "headers"
	bodySeen := false

	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if !bodySeen && trimmed == "--- log ---" {
			section = "log"
			continue
		}
		if !bodySeen && trimmed == "--- body ---" {
			section = "body"
			bodySeen = true
			continue
		}

		switch section {
		case "headers":
			if trimmed == "" {
				section = "gap"
				continue
			}
			if key, val, ok := parseHeaderLine(line); ok {
				headers[key] = append(headers[key], val)
			}
		case "gap":
			// ignore
		case "log":
			if trimmed != "" {
				logLines = append(logLines, line)
			}
		case "body":
			bodyLines = append(bodyLines, line)
		}
	}

	return Ticket{
		Path:     path,
		Headers:  headers,
		LogLines: logLines,
		Body:     strings.Join(bodyLines, "\n"),
	}
}

func loadTickets(dir string) []Ticket {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil
	}
	var tickets []Ticket
	for _, e := range entries {
		if !e.IsDir() && strings.HasSuffix(e.Name(), ".ticket") {
			tickets = append(tickets, parseTicket(filepath.Join(dir, e.Name())))
		}
	}
	sort.Slice(tickets, func(i, j int) bool {
		return tickets[i].Filename() < tickets[j].Filename()
	})
	return tickets
}

// ---------------------------------------------------------------------------
// Validate (mirrors validate_tickets.py)
// ---------------------------------------------------------------------------

var (
	requiredHeaders = []string{"Id", "Title", "Author", "Status", "Created"}
	validStatuses   = map[string]bool{"closed": true, "doing": true, "open": true, "pending": true}
	validPhases     = map[string]bool{"celebrating": true, "doing": true, "dreaming": true, "planning": true}
	isoDateRE       = regexp.MustCompile(`^\d{4}-\d{2}-\d{2}$`)
)

func validateTicket(t *Ticket, allIDs map[string]bool) []string {
	var errors []string
	name := t.Filename()

	// Required headers
	for _, hdr := range requiredHeaders {
		if _, ok := t.Headers[hdr]; !ok {
			errors = append(errors, fmt.Sprintf("%s: missing required header '%s'", name, hdr))
		}
	}

	// Id/filename consistency
	id := t.ID()
	if id != "" && t.FilenameID() != id {
		errors = append(errors, fmt.Sprintf(
			"%s: Id '%s' does not match filename prefix '%s'", name, id, t.FilenameID()))
	}

	// Valid Status
	status := t.Status()
	if status != "" && !validStatuses[status] {
		keys := sortedKeys(validStatuses)
		errors = append(errors, fmt.Sprintf(
			"%s: invalid Status '%s' (expected one of: %s)", name, status, strings.Join(keys, ", ")))
	}

	// Valid X-Phase
	if phases, ok := t.Headers["X-Phase"]; ok {
		for _, phase := range phases {
			if !validPhases[phase] {
				keys := sortedKeys(validPhases)
				errors = append(errors, fmt.Sprintf(
					"%s: invalid X-Phase '%s' (expected one of: %s)", name, phase, strings.Join(keys, ", ")))
			}
		}
	}

	// Created must be ISO date (YYYY-MM-DD)
	if created, ok := t.Headers["Created"]; ok && len(created) > 0 {
		if created[0] != "" && !isoDateRE.MatchString(created[0]) {
			errors = append(errors, fmt.Sprintf(
				"%s: Created '%s' is not a valid ISO date (YYYY-MM-DD)", name, created[0]))
		}
	}

	// Blocked-by references exist
	for _, refID := range t.BlockedBy() {
		if !allIDs[refID] {
			errors = append(errors, fmt.Sprintf(
				"%s: Blocked-by '%s' references unknown ticket ID", name, refID))
		}
	}

	return errors
}

func detectCycles(tickets []Ticket) []string {
	var errors []string

	// Build adjacency list
	adj := make(map[string][]string)
	for i := range tickets {
		id := tickets[i].ID()
		if id != "" {
			adj[id] = tickets[i].BlockedBy()
		}
	}

	const (
		white = 0
		gray  = 1
		black = 2
	)
	color := make(map[string]int)
	for id := range adj {
		color[id] = white
	}

	var dfs func(node string, path []string)
	dfs = func(node string, path []string) {
		color[node] = gray
		path = append(path, node)
		for _, neighbor := range adj[node] {
			c, exists := color[neighbor]
			if !exists {
				continue // unknown ID
			}
			if c == gray {
				// Found cycle — extract from path
				start := 0
				for i, n := range path {
					if n == neighbor {
						start = i
						break
					}
				}
				cycle := append([]string{}, path[start:]...)
				cycle = append(cycle, neighbor)
				errors = append(errors, "dependency cycle: "+strings.Join(cycle, " -> "))
			} else if c == white {
				dfs(neighbor, path)
			}
		}
		color[node] = black
	}

	ids := sortedKeys2(adj)
	for _, id := range ids {
		if color[id] == white {
			dfs(id, nil)
		}
	}
	return errors
}

func validateAll(tickets []Ticket, extraIDs map[string]bool) []string {
	var errors []string

	// Collect IDs, check duplicates
	idToFiles := make(map[string][]string)
	for i := range tickets {
		id := tickets[i].ID()
		if id != "" {
			idToFiles[id] = append(idToFiles[id], tickets[i].Filename())
		}
	}

	dupIDs := sortedKeys2(idToFiles)
	for _, tid := range dupIDs {
		files := idToFiles[tid]
		if len(files) > 1 {
			base := strings.TrimRight(tid, "0123456789")
			maxNum := 1
			for otherID := range idToFiles {
				if otherID == base {
					// base exists as an ID; maxNum already starts at 1
				} else if strings.HasPrefix(otherID, base) {
					suffix := otherID[len(base):]
					if n, err := strconv.Atoi(suffix); err == nil && n > maxNum {
						maxNum = n
					}
				}
			}
			errors = append(errors, fmt.Sprintf(
				"duplicate Id '%s' in: %s -- next available: %s%d",
				tid, strings.Join(files, ", "), base, maxNum+1))
		}
	}

	// Build allIDs
	allIDs := make(map[string]bool)
	for id := range idToFiles {
		allIDs[id] = true
	}
	for id := range extraIDs {
		allIDs[id] = true
	}

	// Per-ticket validation
	for i := range tickets {
		errors = append(errors, validateTicket(&tickets[i], allIDs)...)
	}

	errors = append(errors, detectCycles(tickets)...)
	return errors
}

func cmdValidate(args []string) int {
	if len(args) == 0 {
		args = []string{"tickets/"}
	}

	var tickets []Ticket
	for _, arg := range args {
		info, err := os.Stat(arg)
		if err != nil {
			fmt.Printf("WARNING: skipping %s (not a .ticket file or directory)\n", arg)
			continue
		}
		if info.IsDir() {
			tickets = append(tickets, loadTickets(arg)...)
		} else if strings.HasSuffix(arg, ".ticket") {
			tickets = append(tickets, parseTicket(arg))
		} else {
			fmt.Printf("WARNING: skipping %s (not a .ticket file or directory)\n", arg)
		}
	}

	if len(tickets) == 0 {
		fmt.Println("No .ticket files found.")
		return 0
	}

	// Load archived ticket IDs
	extraIDs := make(map[string]bool)
	for _, arg := range args {
		info, err := os.Stat(arg)
		if err != nil || !info.IsDir() {
			continue
		}
		archiveDir := filepath.Join(arg, "archive")
		if info, err := os.Stat(archiveDir); err == nil && info.IsDir() {
			for _, at := range loadTickets(archiveDir) {
				if id := at.ID(); id != "" {
					extraIDs[id] = true
				}
			}
		}
	}

	errors := validateAll(tickets, extraIDs)
	if len(errors) > 0 {
		fmt.Printf("TICKET VALIDATION FAILED (%d error(s)):\n", len(errors))
		for _, e := range errors {
			fmt.Printf("  %s\n", e)
		}
		return 1
	}

	fmt.Printf("TICKET VALIDATION: PASS (%d tickets)\n", len(tickets))
	return 0
}

// ---------------------------------------------------------------------------
// Ready (mirrors ready_tickets.py)
// ---------------------------------------------------------------------------

type readyEntry struct {
	id, title, file string
}

// loadWip reads .wip files from the shared git ticket-wip directory.
func loadWip() map[string]string {
	wip := make(map[string]string)
	cmd := exec.Command("git", "rev-parse", "--git-common-dir")
	out, err := cmd.Output()
	if err != nil {
		return wip
	}
	wipDir := filepath.Join(strings.TrimSpace(string(out)), "ticket-wip")
	entries, err := os.ReadDir(wipDir)
	if err != nil {
		return wip
	}
	for _, e := range entries {
		if e.IsDir() || filepath.Ext(e.Name()) != ".wip" {
			continue
		}
		tid := strings.TrimSuffix(e.Name(), ".wip")
		data, err := os.ReadFile(filepath.Join(wipDir, e.Name()))
		if err == nil {
			wip[tid] = strings.TrimSpace(string(data))
		}
	}
	return wip
}

func cmdReady(args []string) int {
	useJSON := false
	var rest []string
	for _, a := range args {
		if a == "--json" {
			useJSON = true
		} else {
			rest = append(rest, a)
		}
	}

	ticketDir := "tickets"
	if len(rest) > 0 {
		ticketDir = rest[0]
	}

	info, err := os.Stat(ticketDir)
	if err != nil || !info.IsDir() {
		fmt.Printf("Directory not found: %s\n", ticketDir)
		return 1
	}

	tickets := loadTickets(ticketDir)
	statusByID := make(map[string]string)
	for i := range tickets {
		if id := tickets[i].ID(); id != "" {
			statusByID[id] = tickets[i].Status()
		}
	}

	var warnings []string
	var ready []readyEntry
	openCount := 0

	for i := range tickets {
		t := &tickets[i]
		if t.Status() != "open" {
			continue
		}
		openCount++

		blocked := false
		for _, refID := range t.BlockedBy() {
			refStatus, found := statusByID[refID]
			if !found {
				warnings = append(warnings, fmt.Sprintf(
					"%s: Blocked-by '%s' not found (treating as satisfied)", t.Filename(), refID))
			} else if refStatus != "closed" {
				blocked = true
				break
			}
		}
		if !blocked {
			ready = append(ready, readyEntry{t.ID(), t.Title(), t.Filename()})
		}
	}

	wip := loadWip()

	for _, w := range warnings {
		fmt.Fprintf(os.Stderr, "WARNING: %s\n", w)
	}

	if useJSON {
		if len(ready) == 0 {
			fmt.Println("[]")
		} else {
			fmt.Println("[")
			for i, r := range ready {
				comma := ","
				if i == len(ready)-1 {
					comma = ""
				}
				wipField := ""
				if w, ok := wip[r.id]; ok {
					wipField = fmt.Sprintf(",\n    \"wip\": \"%s\"", jsonEscape(w))
				}
				fmt.Printf("  {\n    \"id\": \"%s\",\n    \"title\": \"%s\",\n    \"file\": \"%s\"%s\n  }%s\n",
					jsonEscape(r.id), jsonEscape(r.title), jsonEscape(r.file), wipField, comma)
			}
			fmt.Println("]")
		}
	} else {
		if len(ready) == 0 {
			if len(tickets) == 0 {
				fmt.Println("No tickets found.")
			} else if openCount == 0 {
				fmt.Printf("All %d tickets are closed.\n", len(tickets))
			} else {
				fmt.Printf("%d open tickets, all blocked.\n", openCount)
			}
		} else {
			fmt.Printf("Ready tickets (%d):\n", len(ready))
			for _, r := range ready {
				suffix := ""
				if w, ok := wip[r.id]; ok {
					suffix = "  (wip: " + w + ")"
				}
				fmt.Printf("  %-8s %-40s %s%s\n", r.id, r.file, r.title, suffix)
			}
		}
	}
	return 0
}

func jsonEscape(s string) string {
	s = strings.ReplaceAll(s, `\`, `\\`)
	s = strings.ReplaceAll(s, `"`, `\"`)
	s = strings.ReplaceAll(s, "\n", `\n`)
	s = strings.ReplaceAll(s, "\r", `\r`)
	s = strings.ReplaceAll(s, "\t", `\t`)
	return s
}

// ---------------------------------------------------------------------------
// Archive (mirrors archive_tickets.py)
// ---------------------------------------------------------------------------

var dagHeaders = []string{"Blocked-by", "X-Discovered-from", "X-Supersedes", "X-Parent"}

// parseLogTimestamp extracts YYYY-MM-DDTHH:MM(:SS)?Z? from a log line.
func parseLogTimestamp(line string) (time.Time, bool) {
	line = strings.TrimSpace(line)
	if len(line) < 16 {
		return time.Time{}, false
	}
	// Find the timestamp portion (may be followed by space + other text)
	tsStr := line
	if idx := strings.IndexByte(line[16:], ' '); idx >= 0 {
		tsStr = line[:16+idx]
	}
	tsStr = strings.TrimRight(tsStr, "Z")

	// Try with seconds
	if t, err := time.Parse("2006-01-02T15:04:05", tsStr); err == nil {
		return t, true
	}
	// Try without seconds
	if t, err := time.Parse("2006-01-02T15:04", tsStr); err == nil {
		return t, true
	}
	return time.Time{}, false
}

func cmdArchive(args []string) int {
	execute := false
	days := 90
	ticketDir := "tickets"

	var filtered []string
	for _, a := range args {
		if a == "--execute" {
			execute = true
		} else {
			filtered = append(filtered, a)
		}
	}

	for i := 0; i < len(filtered); i++ {
		a := filtered[i]
		if strings.HasPrefix(a, "--days=") {
			if n, err := strconv.Atoi(a[7:]); err == nil {
				days = n
			}
		} else if a == "--days" && i+1 < len(filtered) {
			if n, err := strconv.Atoi(filtered[i+1]); err == nil {
				days = n
			}
			i++
		} else if !strings.HasPrefix(a, "--") {
			ticketDir = a
		}
	}

	info, err := os.Stat(ticketDir)
	if err != nil || !info.IsDir() {
		fmt.Printf("Directory not found: %s\n", ticketDir)
		return 1
	}

	tickets := loadTickets(ticketDir)
	cutoff := time.Now().UTC().AddDate(0, 0, -days)

	// Collect all IDs referenced by DAG headers
	referencedIDs := make(map[string]bool)
	allTickets := append([]Ticket{}, tickets...)
	archiveDir := filepath.Join(ticketDir, "archive")
	if info, err := os.Stat(archiveDir); err == nil && info.IsDir() {
		allTickets = append(allTickets, loadTickets(archiveDir)...)
	}
	for i := range allTickets {
		for _, hdr := range dagHeaders {
			if vals, ok := allTickets[i].Headers[hdr]; ok {
				for _, v := range vals {
					referencedIDs[v] = true
				}
			}
		}
	}

	// Find closed tickets older than cutoff
	var archivable, dagProtected []Ticket
	for i := range tickets {
		t := &tickets[i]
		if t.Status() != "closed" {
			continue
		}
		if len(t.LogLines) == 0 {
			continue
		}
		lastTS, ok := parseLogTimestamp(t.LogLines[len(t.LogLines)-1])
		if !ok || !lastTS.Before(cutoff) {
			continue
		}
		if referencedIDs[t.ID()] {
			dagProtected = append(dagProtected, *t)
		} else {
			archivable = append(archivable, *t)
		}
	}

	if len(dagProtected) > 0 {
		var ids []string
		for _, t := range dagProtected {
			ids = append(ids, t.ID())
		}
		fmt.Printf("DAG-protected (skipping %d): %s\n", len(dagProtected), strings.Join(ids, ", "))
	}

	if len(archivable) == 0 {
		fmt.Printf("Nothing to archive (threshold: %d days).\n", days)
		return 0
	}

	var ids []string
	for _, t := range archivable {
		ids = append(ids, t.ID())
	}
	fmt.Printf("Will archive %d ticket(s): %s\n", len(archivable), strings.Join(ids, ", "))

	if !execute {
		fmt.Println("Dry run. Pass --execute to proceed.")
		return 0
	}

	os.MkdirAll(archiveDir, 0755)

	for _, t := range archivable {
		dest := filepath.Join(archiveDir, t.Filename())
		cmd := exec.Command("git", "mv", t.Path, dest)
		if err := cmd.Run(); err != nil {
			fmt.Fprintf(os.Stderr, "git mv failed for %s\n", t.Filename())
			return 1
		}
		fmt.Printf("  moved %s\n", t.Filename())
	}

	msg := fmt.Sprintf("archive %d closed tickets (>%d days, DAG-safe)", len(archivable), days)
	cmd := exec.Command("git", "commit", "-m", msg)
	if err := cmd.Run(); err != nil {
		fmt.Fprintln(os.Stderr, "git commit failed")
		return 1
	}
	fmt.Printf("Committed: %s\n", msg)
	return 0
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

func sortedKeys(m map[string]bool) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}

func sortedKeys2[V any](m map[string]V) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}

// ---------------------------------------------------------------------------
// Main dispatch
// ---------------------------------------------------------------------------

func printUsage() {
	fmt.Fprintln(os.Stderr, "Usage: ticket-tools <command> [args...]")
	fmt.Fprintln(os.Stderr)
	fmt.Fprintln(os.Stderr, "Commands:")
	fmt.Fprintln(os.Stderr, "  validate [dir|files...]   Validate .ticket files")
	fmt.Fprintln(os.Stderr, "  ready [dir] [--json]      Show tickets ready for work")
	fmt.Fprintln(os.Stderr, "  archive [dir] [--days N] [--execute]  Archive old closed tickets")
}

func main() {
	if len(os.Args) < 2 {
		printUsage()
		os.Exit(1)
	}

	cmd := os.Args[1]
	rest := os.Args[2:]

	var exitCode int
	switch cmd {
	case "validate":
		exitCode = cmdValidate(rest)
	case "ready":
		exitCode = cmdReady(rest)
	case "archive":
		exitCode = cmdArchive(rest)
	case "-h", "--help", "help":
		printUsage()
		exitCode = 0
	default:
		fmt.Fprintf(os.Stderr, "Unknown command: %s\n", cmd)
		printUsage()
		exitCode = 1
	}
	os.Exit(exitCode)
}

#!/usr/bin/env perl
# ticket-tools.pl — validate, ready, archive .ticket files.
# Core Perl only (no CPAN modules).
#
# Usage:
#   ticket-tools.pl validate [dir|file ...]
#   ticket-tools.pl ready    [dir] [--json]
#   ticket-tools.pl archive  [dir] [--days N] [--execute]

use strict;
use warnings;
use File::Find     ();
use File::Basename qw(basename dirname);
use File::Spec     ();
use Cwd            qw(abs_path);
use POSIX          qw(strftime);

# ── Ticket parser ───────────────────────────────────────────────────────

sub parse_ticket {
    my ($path) = @_;
    open my $fh, '<:encoding(UTF-8)', $path
        or die "Cannot open $path: $!\n";
    my @lines = <$fh>;
    close $fh;
    chomp @lines;

    my %headers;     # key => [values]
    my @log_lines;
    my @body_lines;

    my $section    = 'headers';   # headers | gap | log | body
    my $body_seen  = 0;

    for my $line (@lines) {
        if (!$body_seen && $line =~ /^\s*--- log ---\s*$/) {
            $section = 'log';
            next;
        }
        if (!$body_seen && $line =~ /^\s*--- body ---\s*$/) {
            $section   = 'body';
            $body_seen = 1;
            next;
        }

        if ($section eq 'headers') {
            if ($line =~ /^\s*$/) {
                $section = 'gap';
                next;
            }
            if ($line =~ /^([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(.*)/) {
                my ($key, $val) = ($1, $2);
                $val =~ s/\s+$//;
                push @{ $headers{$key} }, $val;
            }
        }
        elsif ($section eq 'gap') {
            # ignore
        }
        elsif ($section eq 'log') {
            push @log_lines, $line if $line =~ /\S/;
        }
        elsif ($section eq 'body') {
            push @body_lines, $line;
        }
    }

    return {
        path       => $path,
        name       => basename($path),
        headers    => \%headers,
        log_lines  => \@log_lines,
        body       => join("\n", @body_lines),
    };
}

sub ticket_id {
    my ($t) = @_;
    my $vals = $t->{headers}{Id};
    return ($vals && @$vals) ? $vals->[0] : '';
}

sub ticket_title {
    my ($t) = @_;
    my $vals = $t->{headers}{Title};
    return ($vals && @$vals) ? $vals->[0] : '';
}

sub ticket_status {
    my ($t) = @_;
    my $vals = $t->{headers}{Status};
    return ($vals && @$vals) ? $vals->[0] : '';
}

sub ticket_blocked_by {
    my ($t) = @_;
    return $t->{headers}{'Blocked-by'} ? @{ $t->{headers}{'Blocked-by'} } : ();
}

sub ticket_filename_id {
    my ($t) = @_;
    my $stem = basename($t->{path}, '.ticket');
    my ($prefix) = split(/-/, $stem, 2);
    return defined $prefix ? $prefix : '';
}

sub load_tickets {
    my ($dir) = @_;
    opendir my $dh, $dir or die "Cannot opendir $dir: $!\n";
    my @files = sort grep { /\.ticket$/ } readdir $dh;
    closedir $dh;
    return map { parse_ticket(File::Spec->catfile($dir, $_)) } @files;
}

# ── Validate ────────────────────────────────────────────────────────────

my @REQUIRED_HEADERS = qw(Id Title Author Status Created);
my %VALID_STATUSES   = map { $_ => 1 } qw(open doing closed pending);
my %VALID_PHASES     = map { $_ => 1 } qw(dreaming planning doing celebrating);

sub validate_ticket {
    my ($ticket, $all_ids) = @_;
    my @errors;
    my $name = $ticket->{name};

    # Required headers
    for my $hdr (@REQUIRED_HEADERS) {
        unless ($ticket->{headers}{$hdr}) {
            push @errors, "$name: missing required header '$hdr'";
        }
    }

    # Id/filename consistency
    my $id = ticket_id($ticket);
    if ($id && ticket_filename_id($ticket) ne $id) {
        push @errors,
            "$name: Id '$id' does not match filename "
          . "prefix '" . ticket_filename_id($ticket) . "'";
    }

    # Valid Status
    my $status = ticket_status($ticket);
    if ($status && !$VALID_STATUSES{$status}) {
        push @errors,
            "$name: invalid Status '$status' "
          . "(expected one of: " . join(', ', sort keys %VALID_STATUSES) . ")";
    }

    # Valid X-Phase
    if ($ticket->{headers}{'X-Phase'}) {
        for my $phase (@{ $ticket->{headers}{'X-Phase'} }) {
            unless ($VALID_PHASES{$phase}) {
                push @errors,
                    "$name: invalid X-Phase '$phase' "
                  . "(expected one of: " . join(', ', sort keys %VALID_PHASES) . ")";
            }
        }
    }

    # Blocked-by references exist
    for my $ref (ticket_blocked_by($ticket)) {
        unless ($all_ids->{$ref}) {
            push @errors,
                "$name: Blocked-by '$ref' references unknown ticket ID";
        }
    }

    return @errors;
}

sub detect_cycles {
    my ($tickets) = @_;
    my @errors;

    # Build adjacency list
    my %adj;
    for my $t (@$tickets) {
        my $id = ticket_id($t);
        next unless $id;
        $adj{$id} = [ ticket_blocked_by($t) ];
    }

    my %color;  # 0=WHITE, 1=GRAY, 2=BLACK
    for my $tid (keys %adj) { $color{$tid} = 0; }

    my $dfs;
    $dfs = sub {
        my ($node, $path) = @_;
        $color{$node} = 1;  # GRAY
        push @$path, $node;

        for my $neighbor (@{ $adj{$node} || [] }) {
            next unless exists $color{$neighbor};  # unknown ID
            if ($color{$neighbor} == 1) {
                # Found cycle
                my $idx = 0;
                for my $i (0 .. $#$path) {
                    if ($path->[$i] eq $neighbor) { $idx = $i; last; }
                }
                my @cycle = (@{$path}[$idx .. $#$path], $neighbor);
                push @errors, "dependency cycle: " . join(' -> ', @cycle);
            }
            elsif ($color{$neighbor} == 0) {
                $dfs->($neighbor, $path);
            }
        }
        pop @$path;
        $color{$node} = 2;  # BLACK
    };

    for my $tid (sort keys %adj) {
        $dfs->($tid, []) if $color{$tid} == 0;
    }

    return @errors;
}

sub validate_all {
    my ($tickets, $extra_ids) = @_;
    $extra_ids ||= {};
    my @errors;

    # Collect IDs, check duplicates
    my %id_to_files;
    for my $t (@$tickets) {
        my $id = ticket_id($t);
        next unless $id;
        push @{ $id_to_files{$id} }, $t->{name};
    }

    for my $tid (sort keys %id_to_files) {
        my @files = @{ $id_to_files{$tid} };
        if (@files > 1) {
            # Suggest next available suffix
            my $base = $tid;
            $base =~ s/[0-9]+$//;
            my %existing_nums;
            for my $other_id (keys %id_to_files) {
                if ($other_id eq $base) {
                    $existing_nums{1} = 1;
                }
                elsif (index($other_id, $base) == 0) {
                    my $suffix = substr($other_id, length($base));
                    if ($suffix =~ /^\d+$/) {
                        $existing_nums{int($suffix)} = 1;
                    }
                }
            }
            my $max = 1;
            for my $n (keys %existing_nums) {
                $max = $n if $n > $max;
            }
            my $next_num = $max + 1;
            push @errors,
                "duplicate Id '$tid' in: " . join(', ', @files)
              . " -- next available: $base$next_num";
        }
    }

    # Build all_ids set (active + extra/archived)
    my %all_ids = map { $_ => 1 } keys %id_to_files;
    for my $eid (keys %$extra_ids) { $all_ids{$eid} = 1; }

    # Per-ticket validation
    for my $t (@$tickets) {
        push @errors, validate_ticket($t, \%all_ids);
    }

    push @errors, detect_cycles($tickets);

    return @errors;
}

sub cmd_validate {
    my @args = @_;
    @args = ('tickets/') unless @args;

    my @tickets;
    for my $arg (@args) {
        if (-d $arg) {
            push @tickets, load_tickets($arg);
        }
        elsif (-f $arg && $arg =~ /\.ticket$/) {
            push @tickets, parse_ticket($arg);
        }
        else {
            print "WARNING: skipping $arg (not a .ticket file or directory)\n";
        }
    }

    if (!@tickets) {
        print "No .ticket files found.\n";
        exit 0;
    }

    # Load archived ticket IDs as valid Blocked-by targets
    my %extra_ids;
    for my $arg (@args) {
        if (-d $arg) {
            my $archive_dir = File::Spec->catdir($arg, 'archive');
            if (-d $archive_dir) {
                for my $at (load_tickets($archive_dir)) {
                    my $aid = ticket_id($at);
                    $extra_ids{$aid} = 1 if $aid;
                }
            }
        }
    }

    my @errors = validate_all(\@tickets, \%extra_ids);

    if (@errors) {
        my $n = scalar @errors;
        print "TICKET VALIDATION FAILED ($n error(s)):\n";
        for my $e (@errors) {
            print "  $e\n";
        }
        exit 1;
    }

    my $n = scalar @tickets;
    print "TICKET VALIDATION: PASS ($n tickets)\n";
    exit 0;
}

# ── Ready ───────────────────────────────────────────────────────────────

sub find_ready {
    my ($ticket_dir) = @_;
    my @tickets  = load_tickets($ticket_dir);
    my %status_by_id;
    for my $t (@tickets) {
        my $id = ticket_id($t);
        $status_by_id{$id} = ticket_status($t) if $id;
    }

    my @warnings;
    my @ready;

    for my $t (@tickets) {
        next unless ticket_status($t) eq 'open';

        my $blocked = 0;
        for my $ref (ticket_blocked_by($t)) {
            my $ref_status = $status_by_id{$ref};
            if (!defined $ref_status) {
                push @warnings,
                    $t->{name} . ": Blocked-by '$ref' not found (treating as satisfied)";
            }
            elsif ($ref_status ne 'closed') {
                $blocked = 1;
                last;
            }
        }

        unless ($blocked) {
            push @ready, {
                id    => ticket_id($t),
                title => ticket_title($t),
                file  => $t->{name},
            };
        }
    }

    return (\@ready, \@warnings);
}

sub json_encode_ready {
    my ($ready) = @_;
    if (!@$ready) {
        return "[]";
    }
    my @items;
    for my $r (@$ready) {
        my $id    = json_escape($r->{id});
        my $title = json_escape($r->{title});
        my $file  = json_escape($r->{file});
        push @items, qq(  {\n    "id": "$id",\n    "title": "$title",\n    "file": "$file"\n  });
    }
    return "[\n" . join(",\n", @items) . "\n]";
}

sub json_escape {
    my ($s) = @_;
    $s =~ s/\\/\\\\/g;
    $s =~ s/"/\\"/g;
    $s =~ s/\n/\\n/g;
    $s =~ s/\r/\\r/g;
    $s =~ s/\t/\\t/g;
    return $s;
}

sub cmd_ready {
    my @args     = @_;
    my $use_json = 0;
    my @rest;
    for my $a (@args) {
        if ($a eq '--json') { $use_json = 1; }
        else                { push @rest, $a; }
    }

    my $ticket_dir = @rest ? $rest[0] : 'tickets';

    unless (-d $ticket_dir) {
        print "Directory not found: $ticket_dir\n";
        exit 1;
    }

    my ($ready, $warnings) = find_ready($ticket_dir);

    for my $w (@$warnings) {
        print STDERR "WARNING: $w\n";
    }

    if ($use_json) {
        print json_encode_ready($ready), "\n";
    }
    else {
        if (!@$ready) {
            print "No ready tickets.\n";
        }
        else {
            my $n = scalar @$ready;
            print "Ready tickets ($n):\n";
            for my $r (@$ready) {
                printf "  %-8s %-40s %s\n", $r->{id}, $r->{file}, $r->{title};
            }
        }
    }
    exit 0;
}

# ── Archive ─────────────────────────────────────────────────────────────

my @DAG_HEADERS = ('Blocked-by', 'X-Discovered-from', 'X-Supersedes');

sub last_log_date {
    my ($ticket) = @_;
    my $log_lines = $ticket->{log_lines};
    return undef unless $log_lines && @$log_lines;
    my $last = $log_lines->[-1];
    $last =~ s/^\s+|\s+$//g;
    if ($last =~ /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?Z?/) {
        # Return epoch seconds (UTC)
        use POSIX qw(mktime);
        my ($Y, $M, $D, $h, $m, $s) = ($1, $2, $3, $4, $5, $6 || 0);
        # Use a simpler approach: just return the date string for comparison
        return "$Y-$M-$D" . "T" . "$h:$m:" . sprintf("%02d", $s);
    }
    return undef;
}

sub iso_to_epoch {
    my ($iso) = @_;
    # Parse YYYY-MM-DDTHH:MM:SS
    if ($iso =~ /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/) {
        require Time::Local;
        return Time::Local::timegm($6, $5, $4, $3, $2 - 1, $1 - 1900);
    }
    return 0;
}

sub find_archivable {
    my ($ticket_dir, $days) = @_;
    my @tickets = load_tickets($ticket_dir);
    my $cutoff  = time() - ($days * 86400);

    # Collect all IDs referenced by DAG headers in live AND archived tickets
    my %referenced_ids;
    my @all_tickets = @tickets;
    my $archive_dir = File::Spec->catdir($ticket_dir, 'archive');
    if (-d $archive_dir) {
        push @all_tickets, load_tickets($archive_dir);
    }
    for my $t (@all_tickets) {
        for my $hdr (@DAG_HEADERS) {
            for my $val (@{ $t->{headers}{$hdr} || [] }) {
                $referenced_ids{$val} = 1;
            }
        }
    }

    my @candidates;
    for my $t (@tickets) {
        next unless ticket_status($t) eq 'closed';
        my $last_date_str = last_log_date($t);
        next unless defined $last_date_str;
        my $last_epoch = iso_to_epoch($last_date_str);
        next if $last_epoch >= $cutoff;
        push @candidates, $t;
    }

    my @archivable;
    my @dag_protected;
    for my $t (@candidates) {
        if ($referenced_ids{ ticket_id($t) }) {
            push @dag_protected, $t;
        }
        else {
            push @archivable, $t;
        }
    }

    return (\@archivable, \@dag_protected, \%referenced_ids);
}

sub cmd_archive {
    my @args    = @_;
    my $execute = 0;
    my $days    = 90;
    my $ticket_dir;

    my @clean;
    for my $a (@args) {
        if ($a eq '--execute') { $execute = 1; }
        else                   { push @clean, $a; }
    }

    my $i = 0;
    while ($i < @clean) {
        if ($clean[$i] =~ /^--days=(\d+)$/) {
            $days = $1;
            $i++;
        }
        elsif ($clean[$i] eq '--days' && $i + 1 < @clean) {
            $days = $clean[$i + 1];
            $i += 2;
        }
        elsif ($clean[$i] !~ /^--/) {
            $ticket_dir = $clean[$i];
            $i++;
        }
        else {
            $i++;
        }
    }

    $ticket_dir //= 'tickets';

    unless (-d $ticket_dir) {
        print "Directory not found: $ticket_dir\n";
        exit 1;
    }

    my ($archivable, $dag_protected, undef) = find_archivable($ticket_dir, $days);

    if (@$dag_protected) {
        my $n = scalar @$dag_protected;
        print "DAG-protected (skipping $n): "
          . join(', ', map { ticket_id($_) } @$dag_protected) . "\n";
    }

    if (!@$archivable) {
        print "Nothing to archive (threshold: $days days).\n";
        exit 0;
    }

    my $n = scalar @$archivable;
    print "Will archive $n ticket(s): "
      . join(', ', map { ticket_id($_) } @$archivable) . "\n";

    unless ($execute) {
        print "Dry run. Pass --execute to proceed.\n";
        exit 0;
    }

    my $archive_dir = File::Spec->catdir($ticket_dir, 'archive');
    unless (-d $archive_dir) {
        mkdir $archive_dir or die "Cannot mkdir $archive_dir: $!\n";
    }

    for my $t (@$archivable) {
        my $dest = File::Spec->catfile($archive_dir, $t->{name});
        system('git', 'mv', $t->{path}, $dest) == 0
            or die "git mv failed for $t->{name}\n";
        print "  moved $t->{name}\n";
    }

    my $msg = "archive $n closed tickets (>$days days, DAG-safe)";
    system('git', 'commit', '-m', $msg) == 0
        or die "git commit failed\n";
    print "Committed: $msg\n";
    exit 0;
}

# ── Main dispatch ───────────────────────────────────────────────────────

sub usage {
    print STDERR "Usage: ticket-tools.pl <command> [args...]\n";
    print STDERR "Commands: validate, ready, archive\n";
    exit 1;
}

my $cmd = shift @ARGV // '';
if    ($cmd eq 'validate') { cmd_validate(@ARGV); }
elsif ($cmd eq 'ready')    { cmd_ready(@ARGV); }
elsif ($cmd eq 'archive')  { cmd_archive(@ARGV); }
else                       { usage(); }

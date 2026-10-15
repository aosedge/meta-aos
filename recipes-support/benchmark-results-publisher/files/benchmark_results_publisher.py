#!/usr/bin/env python3
"""Watch VictoriaMetrics for repeating "windows" of checkpoint_event samples (e.g. one AosCore
deployment cycle) and publish each window's aggregated elapsed-time metrics back to VictoriaMetrics
as benchmark_result samples - the job a human used to have to run report_timing.py by hand for.

Entirely config-driven (see --config, load_config()): nothing in this script names a specific
service, checkpoint text, or event - what marks a new window, and which pairs of checkpoints define
each metric, are both read from the config file. The shipped default config happens to describe
AosCore's Operational Speed checkpoints, but this script itself has no idea what AosCore is.

How a "window" is found and resolved:

  - Exactly one metric in the config sets `window_end_settle_seconds`: its end checkpoint (its
    `end_source`/`end_source_pattern` + `end_event`) is what marks a window - the last occurrence of a
    batch of them, across every node, marks the end of the current window and the start of watching
    for the next one - e.g. AosCore's benchmark-timing instances each push an "Instance: <id>" /
    "Start" sample, and the latest one across an entire deployment batch is that deployment's
    boundary - see boundary_query(). Windows are processed oldest first, so one that finishes
    while an earlier one is still being resolved is queued, not skipped. Only one node's
    checkpoints define a window (see the `node` section below); the rest of this script assumes a
    window's metrics all happened on that same node, not split across several.

  - Every metric in `metrics` is the elapsed time between two checkpoint_event samples - a `start`
    and an `end` - looked up independently once a window's boundary is known. The end is either
    one fixed source (`end_source`) or a regex matching a batch of sources (`end_source_pattern`, e.g.
    every "Instance: <id>" / "Start" checkpoint, ending at the last of them) - see Metric.

  - Every lookup is bounded on both sides by the *previous* window's boundary and the *current*
    window's boundary, so a checkpoint left over from an earlier window, or one belonging to
    whatever window starts next (while this one is still being resolved), can never be mistaken for
    one of this window's - see resolve_window() for the empirically confirmed failure modes this
    guards against, and why a metric whose checkpoint can recur more
    than once per window (a metric's end - see Metric.try_resolve() - or an `end_source_pattern`
    metric's start - see advance_not_before_us()) needs extra care beyond simple bounding.

  - A metric that never applies to a given window (e.g. a metric only a certain kind of run
    produces) is given up on - reported as absent, never published - after BOUNDED_WAIT_SECONDS,
    rather than blocking this script on that window forever. Finding the window's boundary in
    the first place has no such timeout: that's what defines a window existing at all.

Node (`node: self` in a metric, or omitted): most metrics are looked up (and published) on whichever
node the *current window's* boundary occurrence came from (its "node" label) - but a metric
whose checkpoint is only ever logged by one specific node regardless of where a window's
activity happens (e.g. a controller component that only runs on one particular node) sets
`node: self` to pin it to this script's `--node` instead. This script itself should only ever
run once (see its recipe) - VictoriaMetrics is a single shared store, so watching from more than
one place at once would double-detect and double-publish every window.

Usage:
    benchmark_results_publisher.py --victoria-url http://localhost:8428 \
        --config benchmark-results-publisher.yml --node main \
        --state-file /var/lib/benchmark-results-publisher/last-boundary
"""

import argparse
import datetime
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

import yaml


def parse_args():
    """Parse --victoria-url / --config / --node / --state-file command-line options."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--victoria-url",
        required=True,
        help="VictoriaMetrics base URL, e.g. http://localhost:8428",
    )
    parser.add_argument(
        "--config",
        required=True,
        help="path to a YAML file with the metrics to publish, see benchmark-results-publisher.yml",
    )
    parser.add_argument(
        "--node",
        required=True,
        help='this script\'s "node" identity - used only by a metric marked "node: self", not by '
        'anything scoped to a window\'s node',
    )
    parser.add_argument(
        "--state-file",
        help="file the last published window's boundary is persisted to, so a restart resumes from it "
        "instead of skipping whatever window was in flight - see load_state()",
    )
    return parser.parse_args()


class VictoriaMetricsError(Exception):
    """Raised by push_line()/query_metrics() on a transport or malformed-response failure talking to
    VictoriaMetrics - distinct from a request that succeeded but simply found nothing (query_metrics()
    still returns [] for that). Conflating the two would mean a transient outage during window
    resolution looks identical to "this checkpoint genuinely doesn't exist", silently turning a real,
    delayed metric into a permanent n/a, or a transient publish failure into a silently dropped
    sample. Every caller here lets this propagate up to main()'s top-level retry loop instead of
    swallowing it, so a failure aborts and retries the *whole* current window rather than
    mis-recording it - see main()."""


def push_line(victoria_url, line):
    """POST a single Prometheus exposition-format line to VictoriaMetrics's /api/v1/import/prometheus
    endpoint. Raises VictoriaMetricsError on a transport failure - see VictoriaMetricsError. Catches
    OSError, not just urllib.error.URLError (itself an OSError subclass): URLError only covers
    connection-establishment failures inside urlopen() itself - a stalled connection that fails
    later, while response.read() is reading the body, can raise a bare TimeoutError/ConnectionError
    that urllib never wraps, which would otherwise propagate uncaught past this function."""
    request = urllib.request.Request(
        f"{victoria_url.rstrip('/')}/api/v1/import/prometheus",
        data=line.encode(),
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            response.read()
    except OSError as err:
        raise VictoriaMetricsError(f"failed to push to VictoriaMetrics: {err}") from err


def escape_label_value(value):
    """Escape a string for safe embedding inside a Prometheus exposition-format label value."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def format_precise_time(timestamp_us):
    """Format a microsecond epoch timestamp as "YYYY-MM-DD HH:MM:SS.ffffff" (UTC) - the same
    "time_us" label format event_exporter.py's push_event() uses, read back by parse_time_us()."""
    # Exact integer arithmetic, not timestamp_us / 1e6 - float64 is right at the edge of enough
    # precision for a 10-digit epoch second count plus 6 more decimal digits, so this avoids any
    # risk of the last microsecond digit being wrong.
    seconds, microseconds = divmod(timestamp_us, 1_000_000)
    dt = datetime.datetime.fromtimestamp(seconds, tz=datetime.timezone.utc)
    dt += datetime.timedelta(microseconds=microseconds)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")


_EPOCH = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)


def parse_time_us(text):
    """Parses a "YYYY-MM-DD HH:MM:SS.ffffff" UTC "time_us" label back into a microsecond epoch
    timestamp - the precise time event_exporter.py's push_event() carries in that label, since
    VictoriaMetrics' sample timestamps are millisecond-precision only (confirmed empirically: two
    points pushed 500us apart both landed on the same millisecond) - too coarse to order two
    checkpoints that land in the same millisecond, which every lookup here needs to do correctly."""
    dt = datetime.datetime.strptime(text, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=datetime.timezone.utc)
    # Exact integer arithmetic, not dt.timestamp() (a float) - see format_precise_time().
    delta = dt - _EPOCH
    return (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds


def push_result(victoria_url, node, source, name, value):
    """Push a single benchmark_result sample for one measured value."""
    timestamp_us = int(time.time() * 1_000_000)
    labels = ",".join(
        f'{label}="{escape_label_value(text)}"'
        for label, text in (
            ("node", node),
            ("source", source),
            ("name", name),
            ("time_us", format_precise_time(timestamp_us)),
        )
    )
    time_s = timestamp_us / 1_000_000
    push_line(victoria_url, f"benchmark_result{{{labels}}} {value:.6f} {time_s:.3f}")


def metric_name(label):
    """Turns a display label like "Start network" into a benchmark_result "name" like
    "start_network_s"."""
    return label.lower().replace(" ", "_") + "_s"


# RE2 (VictoriaMetrics' regex engine) metacharacters that can appear in a literal checkpoint event
# text - notably not whitespace, unlike Python's re.escape(), which also escapes it (for its
# VERBOSE-mode support) - RE2 doesn't accept "\ " as an escape sequence and rejects the whole query
# with "invalid regex" (confirmed empirically) if it's used here.
_RE2_METACHARS = re.compile(r"([.^$|()\[\]{}*+?\\])")


def _escape_regex_literal(text):
    """Escapes RE2 metacharacters in `text` for safe embedding in a PromQL regex - see
    _RE2_METACHARS. The result still needs escape_promql_string() before it can be embedded in a
    quoted PromQL string literal - the two are separate layers."""
    return _RE2_METACHARS.sub(r"\\\1", text)


def escape_promql_string(text):
    """Escapes `text` for safe embedding inside a double-quoted PromQL string literal. This is a
    separate layer from _escape_regex_literal(): a backslash meant for the regex engine (e.g. from
    "\\." there) has to arrive at the regex engine as a single backslash, which means it has to be
    written as two backslashes in the PromQL source text - confirmed empirically: a single backslash
    made VictoriaMetrics reject the whole query as an invalid string literal, before the regex
    engine ever saw it."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def event_query(node, source, event):
    """A PromQL selector matching a checkpoint_event on `node` whose event is exactly `event`, or
    `event` followed by a ": key=value, ..." detail suffix (a common logging convention this
    tolerates unconditionally, matching or not costing nothing when a service never uses it).
    `event` is regex-escaped first, since some checkpoint texts contain regex metacharacters of
    their own, then PromQL-string-escaped - see escape_promql_string()."""
    pattern = escape_promql_string(_escape_regex_literal(event))
    return (
        f'checkpoint_event{{node="{escape_promql_string(node)}",source="{escape_promql_string(source)}",'
        f'event=~"^{pattern}(:.*)?$"}}'
    )


def pattern_event_query(node, source_pattern, event):
    """Like event_query(), but matching every checkpoint_event whose source matches the regex
    `source_pattern`, on `node` - or on every node if `node` is None.

    `source_pattern` is a regex the config author writes intentionally (unlike every other string
    interpolated into a PromQL selector here, which is a literal value regex-escaped first via
    _escape_regex_literal() so it matches itself exactly) - it must NOT go through
    _escape_regex_literal(), which would mangle the author's regex metacharacters, but it still
    needs escape_promql_string()'s separate, syntactic layer: without it, a pattern containing a
    literal `"` or `\\` (e.g. `\\d`) would be misparsed or rejected by PromQL's string-literal
    syntax before the regex engine downstream ever saw it - confirmed as a real gap, not just this
    script's default pattern being simple enough to not trigger it."""
    node_label = f'node="{escape_promql_string(node)}",' if node else ""
    pattern = escape_promql_string(_escape_regex_literal(event))
    return (
        f'checkpoint_event{{{node_label}source=~"{escape_promql_string(source_pattern)}",'
        f'event=~"^{pattern}(:.*)?$"}}'
    )


def boundary_query(window_end, self_node):
    """A PromQL selector for the window's recurring boundary checkpoint - the end checkpoint of
    `window_end`, the one metric config entry that sets "window_end_settle_seconds" (see
    load_config() and pattern_event_query()). Matches every node, since whichever node a window's
    boundary checkpoint lands on is exactly what resolve_window() needs to discover, not assume -
    except a fixed `end_source` of a "node: self" metric, which Metric itself only ever looks up on
    `self_node` too. An `end_source_pattern` end always matches every node, even for a "node: self"
    metric, the same way Metric looks it up on the window's node rather than its own."""
    end_source_pattern = window_end.get("end_source_pattern")
    if end_source_pattern:
        return pattern_event_query(None, end_source_pattern, window_end["end_event"])

    node = self_node if window_end.get("node") == "self" else None
    end_source_pattern = f"^{_escape_regex_literal(window_end['end_source'])}$"
    return pattern_event_query(node, end_source_pattern, window_end["end_event"])


# Overrides VictoriaMetrics' default instant-query staleness window (~5 minutes) - without this,
# a checkpoint whose event happened more than that long before a query's evaluation time is
# invisible to that query even though the sample is still in VictoriaMetrics - confirmed empirically:
# a sample pushed 10 minutes before the query's evaluation time was missing from a default query and
# only appeared once max_lookback was widened past that gap. This matters for real runs, not just
# fast tests: a metric whose start and end checkpoints can legitimately be many minutes apart
# (e.g. a large download) would otherwise silently read as n/a once BOUNDED_WAIT_SECONDS ran out,
# even though the real sample was sitting in VictoriaMetrics the whole time. 30 minutes is generous
# for the checkpoints this ships against by default; a genuinely slower window would need this
# widened further.
QUERY_MAX_LOOKBACK_US = 30 * 60 * 1_000_000

# Lookback used for boundary lookups only (see wait_for_new_window(), seed_last_end_us()) -
# matches victoria-metrics.service's -retentionPeriod, so a boundary is still found after this
# script was down, or simply idle, for longer than QUERY_MAX_LOOKBACK_US. Without it, a baseline
# older than that reads as "no baseline at all" and the next window would be resolved with no lower
# bound (not_before_us=None).
BOUNDARY_MAX_LOOKBACK_US = 24 * 60 * 60 * 1_000_000

# VictoriaMetrics stores a sample's timestamp rounded to the millisecond (event_exporter.py pushes
# it as "%.3f" seconds), so a checkpoint up to half a millisecond after a query's evaluation time can
# be stored at or before it - and one up to half a millisecond before can be stored after it. Every
# query bounded by at_time_us is therefore evaluated this much later, and the precise "time_us" label
# is then used to enforce the real "at or before at_time_us" bound - see query_samples_us().
QUERY_TIME_SLACK_US = 1_000


def query_metrics(victoria_url, promql, at_time_us=None, max_lookback_us=QUERY_MAX_LOOKBACK_US):
    """Runs an instant PromQL query against VictoriaMetrics and returns every matching sample's full
    label set (a dict, as VictoriaMetrics' "metric" field). Returns [] if the query succeeded but
    nothing matches; raises VictoriaMetricsError - see VictoriaMetricsError - on a transport or
    malformed-response failure, so callers can tell "no such checkpoint" apart from "couldn't ask".
    Catches OSError, not just urllib.error.URLError - see push_line()'s note on why."""
    params = {
        "query": promql,
        # Without this, VictoriaMetrics can serve a cached response from an earlier attempt at the
        # same query string, masking a checkpoint that has since become visible.
        "nocache": "1",
        "max_lookback": f"{max_lookback_us // 1_000_000}s",
    }
    if at_time_us is not None:
        params["time"] = f"{(at_time_us + QUERY_TIME_SLACK_US) / 1_000_000:.6f}"

    url = f"{victoria_url.rstrip('/')}/api/v1/query?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, method="GET")

    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = json.loads(response.read())
    except (OSError, json.JSONDecodeError) as err:
        raise VictoriaMetricsError(f"failed to query VictoriaMetrics: {err}") from err

    # A well-formed JSON body can still be an error ("status": "error") or lack data.result - treating
    # either as an empty result would read as "no such checkpoint" rather than "couldn't ask".
    if not isinstance(body, dict) or body.get("status") != "success":
        raise VictoriaMetricsError(f"VictoriaMetrics query failed: {str(body)[:200]}")

    result = body.get("data", {}).get("result") if isinstance(body.get("data"), dict) else None
    if not isinstance(result, list):
        raise VictoriaMetricsError(f"malformed VictoriaMetrics response: {str(body)[:200]}")

    return [entry.get("metric", {}) for entry in result if isinstance(entry, dict)]


def query_samples_us(victoria_url, promql, at_time_us=None, not_before_us=None):
    """Every query_metrics() match's precise timestamp - read from its "time_us" label rather than
    the sample's millisecond-precision timestamp - within (`not_before_us`, `at_time_us`], each
    bound only if given (see resolve_window()'s stale-carryover note and QUERY_TIME_SLACK_US)."""
    samples = []
    for metric in query_metrics(victoria_url, promql, at_time_us):
        time_us_label = metric.get("time_us")
        if time_us_label:
            us = parse_time_us(time_us_label)
            if _in_bounds(us, not_before_us, at_time_us):
                samples.append(us)

    return samples


def _in_bounds(us, not_before_us, at_time_us):
    """Whether `us` lies within (`not_before_us`, `at_time_us`], each bound only if not None."""
    return (not_before_us is None or us > not_before_us) and (at_time_us is None or us <= at_time_us)


def query_source_samples_us(
    victoria_url, promql, at_time_us=None, not_before_us=None, max_lookback_us=QUERY_MAX_LOOKBACK_US,
):
    """Like query_samples_us(), but returning (source, node, time_us) triples - for a selector
    matching more than one source and/or node (see pattern_event_query()), whose callers need to
    tell its matches apart. `max_lookback_us` is only widened for boundary lookups - see
    BOUNDARY_MAX_LOOKBACK_US."""
    samples = []
    for metric in query_metrics(victoria_url, promql, at_time_us, max_lookback_us):
        time_us_label = metric.get("time_us")
        if time_us_label:
            us = parse_time_us(time_us_label)
            if _in_bounds(us, not_before_us, at_time_us):
                samples.append((metric.get("source", ""), metric.get("node", ""), us))

    return samples


def query_latest_us(victoria_url, promql, at_time_us=None, not_before_us=None):
    """The latest of query_samples_us()'s results, or None if it returned none."""
    samples = query_samples_us(victoria_url, promql, at_time_us, not_before_us)
    return max(samples) if samples else None


_METRIC_REQUIRED_KEYS = {"label", "start_source", "start_event", "end_event"}
_METRIC_OPTIONAL_KEYS = {"end_source", "end_source_pattern", "per_instance", "node", "window_end_settle_seconds"}


def _validate_metric(i, entry):
    """Validates one "metrics" config entry - see _load_metrics()."""
    if not isinstance(entry, dict):
        raise ValueError(f"metrics[{i}]: must be a mapping, not {entry!r}")

    label = entry.get("label", "?")

    def fail(msg):
        raise ValueError(f"metrics[{i}] ({label!r}): {msg}")

    keys = entry.keys()
    missing = _METRIC_REQUIRED_KEYS - keys
    if missing:
        fail(f"missing required key(s): {sorted(missing)}")

    unknown = keys - _METRIC_REQUIRED_KEYS - _METRIC_OPTIONAL_KEYS
    if unknown:
        fail(f"has unknown key(s): {sorted(unknown)}")

    if ("end_source" in entry) == ("end_source_pattern" in entry):
        fail("needs exactly one of end_source or end_source_pattern")

    for key in ("label", "start_source", "start_event", "end_source", "end_event"):
        if key in entry and (not isinstance(entry[key], str) or not entry[key]):
            fail(f'"{key}" must be a non-empty string, not {entry[key]!r}')

    if not isinstance(entry.get("per_instance", False), bool):
        fail(f'"per_instance" must be true or false, not {entry["per_instance"]!r}')

    end_source_pattern = entry.get("end_source_pattern")
    if end_source_pattern is not None:
        if not isinstance(end_source_pattern, str) or not end_source_pattern:
            fail('"end_source_pattern" must be a non-empty string')
        try:
            re.compile(end_source_pattern)
        except re.error as err:
            fail(f'"end_source_pattern" is not a valid regex: {err}')

    if entry.get("per_instance") and end_source_pattern is None:
        fail("per_instance needs end_source_pattern - it breaks the metric down per matched source")

    node = entry.get("node")
    if node is not None and node != "self":
        fail(f'"node" must be "self" if given, not {node!r}')

    if "window_end_settle_seconds" in entry:
        settle_seconds = entry["window_end_settle_seconds"]
        if isinstance(settle_seconds, bool) or not isinstance(settle_seconds, (int, float)) or settle_seconds < 0:
            fail(f'"window_end_settle_seconds" must be a non-negative number, not {settle_seconds!r}')


def _load_metrics(raw_metrics):
    """Validates the "metrics" section of the config file (see load_config(), _validate_metric())
    and returns it as a list of dicts ready for Metric(**metric_def). Fails fast on a
    missing/unknown/contradictory key rather than letting a typo surface later as a silently-wrong
    or permanently n/a metric, since this only runs once, at startup."""
    if not isinstance(raw_metrics, list) or not raw_metrics:
        raise ValueError('config needs a non-empty "metrics" list')

    names = {}
    for i, entry in enumerate(raw_metrics):
        _validate_metric(i, entry)

        # Results are keyed by label, and published under metric_name(label) - a duplicate of either
        # would silently overwrite another metric's value.
        name = metric_name(entry["label"])
        if name in names:
            raise ValueError(
                f"metrics[{i}] ({entry['label']!r}): publishes as {name!r}, same as metrics[{names[name]}]"
            )
        names[name] = i

    return list(raw_metrics)


def load_config(config_path):
    """Load benchmark-results-publisher's config file: `metrics` (the elapsed-time table each window
    is resolved from - see Metric), one of which also marks what a new window is (see
    boundary_query()). Returns (window_end, metrics) - `window_end` being that one metric's
    entry."""
    with open(config_path) as f:
        config = yaml.safe_load(f) or {}

    if not isinstance(config, dict):
        raise ValueError("config must be a mapping")

    unknown = config.keys() - {"metrics"}
    if unknown:
        raise ValueError(f"config has unknown key(s): {sorted(unknown)}")

    metrics = _load_metrics(config.get("metrics", []))

    # Exactly one metric's end has to mark a window - see boundary_query(). None would leave nothing
    # to detect a window by at all; more than one would make it ambiguous which to use.
    window_ends = [entry for entry in metrics if "window_end_settle_seconds" in entry]
    if len(window_ends) != 1:
        raise ValueError(
            'exactly one metric needs "window_end_settle_seconds" (marking its end as the window\'s '
            f"boundary), not {len(window_ends)}: {[entry['label'] for entry in window_ends]}"
        )

    return window_ends[0], metrics


def _literal_prefix(source_pattern):
    """The fixed literal prefix of a regex like '^Instance: .*' ("Instance: ") - used only to label a
    per_instance breakdown by whatever varies after it (e.g. an instance id), purely cosmetic; a
    pattern with no such simple prefix just leaves each match labeled by its full source text."""
    match = re.match(r"^\^?([^.^$|()\[\]{}*+?\\]*)", source_pattern)
    return match.group(1) if match else ""


class Metric:
    """Resolves one "metrics" config entry's elapsed time into results[label] - see load_config()."""

    def __init__(
        self, label, start_source, start_event, end_event, end_source=None, end_source_pattern=None,
        per_instance=False, node=None, window_node=None,
    ):
        self.label = label
        self.start_source = start_source
        self.start_event = start_event
        self.end_source = end_source
        # A regex matching a batch of end sources (e.g. '^Instance: .*' for every instance's
        # "Start"), instead of one fixed end_source - the metric then ends at the *last* match, and
        # those matches are looked up on `window_node`, not `node`: they're the window's activity
        # (the same kind of checkpoint a window's boundary is usually defined from), wherever a
        # "node: self" metric's start happens - see try_resolve().
        self.end_source_pattern = end_source_pattern
        self.end_event = end_event
        # If True, also publish one benchmark_result sample per end_source_pattern match, each the
        # elapsed time from this metric's start_us to that match's timestamp - see
        # resolve_per_instance_breakdowns().
        self.per_instance = per_instance
        # Resolved by the caller (resolve_window()) to either the window's node or this script's
        # "self" node, per this entry's "node" setting - see the module docstring.
        self.node = node
        self.window_node = window_node
        self.start_us = None
        self.end_us = None
        # Every end_source_pattern match this metric's end was picked from, as (source, time_us).
        self.end_matches = []

    def try_resolve(self, victoria_url, results, not_before_us, window_end_us):
        """Attempts to fill in whichever of this metric's two ends is still missing. Every lookup is
        scoped to this window specifically: `not_before_us` excludes any candidate at or before the
        previous window's boundary, and `window_end_us` (this window's boundary) is used as
        the query's evaluation time, so a candidate belonging to whatever *next* window happens to
        have started by the time this call runs can't be mistaken for this one's either - every
        checkpoint a metric measures necessarily happens at or before its window's boundary, so
        this is never too tight - see resolve_window()'s stale-carryover note.

        The start is the latest `start_event` in this window. With `end_source`, the end is the
        *earliest* `end_event` at or after that start - never simply the latest `end_event`, which
        could pair a start with an end belonging to an earlier start (if this start's end isn't
        visible yet, giving a negative or too-short duration), or with a much later, unrelated one
        when `end_event` recurs more often than `start_event` (e.g. "Update instances begin" fires on
        every deployment, but "Starting AosCore Service Manager..." only when SM itself restarts).
        With `end_source_pattern`, the end is the *latest* match at or after the start: a batch of
        sources (e.g. every instance) is done only once its last member is. Returns True (and
        records the elapsed time into `results`) once both ends are found."""
        if self.start_us is None:
            self.start_us = query_latest_us(
                victoria_url,
                event_query(self.node, self.start_source, self.start_event),
                at_time_us=window_end_us,
                not_before_us=not_before_us,
            )

        if self.start_us is not None and self.end_us is None:
            # Querying at window_end_us makes VictoriaMetrics consider every occurrence up to the
            # window's boundary current and return all of them (bounded backward by
            # QUERY_MAX_LOOKBACK_US). Every candidate kept is at or after self.start_us, which is
            # itself after not_before_us - no separate not_before_us filtering needed here.
            if self.end_source_pattern:
                matches = query_source_samples_us(
                    victoria_url,
                    pattern_event_query(self.window_node, self.end_source_pattern, self.end_event),
                    at_time_us=window_end_us,
                )
                self.end_matches = sorted(
                    ((source, us) for source, _, us in matches if us >= self.start_us), key=lambda m: m[1]
                )
                self.end_us = self.end_matches[-1][1] if self.end_matches else None
            else:
                candidates = query_samples_us(
                    victoria_url, event_query(self.node, self.end_source, self.end_event),
                    at_time_us=window_end_us,
                )
                candidates = [us for us in candidates if us >= self.start_us]
                self.end_us = min(candidates) if candidates else None

        if self.start_us is None or self.end_us is None:
            return False

        results[self.label] = (self.end_us - self.start_us) / 1_000_000
        return True


# How often an unresolved metric or a not-yet-started window is re-polled - see resolve_window() and
# wait_for_new_window(). There is no attempt limit for a window's boundary: that waits until
# interrupted instead - except every individual metric, see BOUNDED_WAIT_SECONDS below.
POLL_INTERVAL_SECONDS = 5

# How often the main loop retries after an unexpected error resolving a window, so one bad window (or
# a transient VictoriaMetrics outage) can't silently end publication for the rest of the service's
# lifetime.
ERROR_RETRY_SECONDS = 30

# Every metric gives up (reporting n/a - never published) after this long rather than waiting
# forever, since any of them can be genuinely absent from a given window depending on what kind of
# run it was - a metric that a given window's activity simply never produces would otherwise
# leave this script stuck on that window forever, no matter how long it waits (confirmed
# empirically). Wide enough to comfortably clear VictoriaMetrics' default ~30s -search.latencyOffset
# (a freshly ingested sample isn't necessarily visible to a query right away).
BOUNDED_WAIT_SECONDS = 40

# An end_source_pattern metric's start_event can recur more than once per window (e.g. a
# checkpoint logged both when a process starts handling something and again once it finishes) - the
# *trailing* occurrence, if any, lands strictly after the window's boundary and would otherwise
# leak into the *next* window's lookup for that same metric if that window has no fresh
# occurrence of its own (confirmed empirically: produced a wildly inflated value this way).
# BOUNDARY_METRIC_LOOKAHEAD_US bounds how far past a window's boundary this trailing occurrence is
# looked for (the *earliest* occurrence in that window - see advance_not_before_us()), so it can be
# folded into the exclusion boundary handed to the next window instead. Deliberately short (a
# trailing occurrence has landed well under a second after the boundary in every run observed) rather
# than generous: a longer window risks reaching past the trailing occurrence entirely and into the
# *next* window's fresh occurrence of the same event (if that window begins soon after this one) -
# confirmed empirically at 30s: a second window only 22s after the first had its start event
# mistaken for the first window's trailing occurrence, advancing the boundary *past* that second
# window's boundary and leaving it undetectable. Picking the earliest occurrence in the window
# (not the latest) is a second, independent guard against the same failure mode, in case two windows
# ever do land inside one lookahead period regardless.
#
# Residual risk, accepted rather than eliminated: if a *next* window's boundary happens within
# this lookahead and that window's fresh occurrence is the only one in it (i.e. the current
# window has none of its own to find first), the earliest-pick above still folds that next window's
# occurrence in - not wrongly inflating anything this time, but leaving that metric unable to
# find its start for the next window (excluded by its not_before_us), reading n/a instead of
# its real value.
BOUNDARY_METRIC_LOOKAHEAD_US = 10 * 1_000_000

def _latest_boundary_sample(victoria_url, window_end, self_node):
    """The (time_us, node) of the latest boundary occurrence still retained in VictoriaMetrics - or
    None if there isn't one. See seed_last_end_us()."""
    samples = query_source_samples_us(
        victoria_url, boundary_query(window_end, self_node), max_lookback_us=BOUNDARY_MAX_LOOKBACK_US
    )
    if not samples:
        return None

    _, node, end_us = max(samples, key=lambda sample: sample[2])
    return end_us, node


def _next_boundary_sample(victoria_url, window_end, self_node, not_before_us, settle_us):
    """The (time_us, node) of the last occurrence in the *oldest* batch of boundary occurrences after
    `not_before_us` - or None if there isn't one. A batch is a run of occurrences each at most
    `settle_us` after the previous one (see wait_for_new_window()). Taking the oldest batch, not
    simply the latest occurrence overall, means a window whose boundary showed up while an
    earlier one was still being resolved (resolve_window() can wait up to BOUNDED_WAIT_SECONDS, longer
    on a VictoriaMetricsError retry) is queued for the next call rather than skipped over and never
    published. Shared by wait_for_new_window()'s initial and settle checks."""
    samples = query_source_samples_us(
        victoria_url, boundary_query(window_end, self_node), not_before_us=not_before_us,
        max_lookback_us=BOUNDARY_MAX_LOOKBACK_US,
    )
    if not samples:
        return None

    samples.sort(key=lambda sample: sample[2])
    _, node, end_us = samples[0]
    for _, sample_node, us in samples[1:]:
        if us - end_us > settle_us:
            break
        node, end_us = sample_node, us

    return end_us, node


def wait_for_new_window(victoria_url, window_end, self_node, last_end_us):
    """Polls (every POLL_INTERVAL_SECONDS, forever) until a newer boundary occurrence shows up
    than `last_end_us` (None on the very first call, meaning "whatever's current right now"), then
    returns (window_end_us, window_node): `window_node` is whichever node that occurrence came from,
    taken as the single node this window's activity happened on for every subsequent lookup (see
    resolve_window()) - a window whose activity is split across more than one node isn't
    supported. This is what turns window resolution into a continuous watcher instead of a one-shot
    report.

    If several windows' boundaries are already waiting, the oldest one is returned first - see
    _next_boundary_sample().

    Once a candidate shows up, keeps re-checking for `window_end`'s "window_end_settle_seconds"
    of consecutive quiet before returning it, in case more of the same batch (e.g. several instances
    starting near-simultaneously) is still trickling in. A multi-sample batch's occurrences have
    landed within milliseconds of each other in every run observed, so the shipped value is generous
    headroom, not a tight race - but nothing guarantees every sample in a batch reports within a
    single poll, and without this, there's no way to tell "the last sample of this batch" apart from
    "a sample that happened to report first, with more of the same batch still incoming": locking in
    the latter would split one real window into two and permanently exclude whatever lands after it
    (every lookup is bounded to at-or-before the window's boundary - see Metric.try_resolve())."""
    settle_seconds = window_end["window_end_settle_seconds"]
    settle_us = int(settle_seconds * 1_000_000)

    def next_sample():
        return _next_boundary_sample(victoria_url, window_end, self_node, last_end_us, settle_us)

    while True:
        found = next_sample()
        if found is not None:
            settled_since = time.monotonic()
            while time.monotonic() - settled_since < settle_seconds:
                time.sleep(1)
                newer = next_sample()
                if newer is not None and newer != found:
                    found = newer
                    settled_since = time.monotonic()

            return found

        time.sleep(POLL_INTERVAL_SECONDS)


def resolve_window(victoria_url, window_node, self_node, not_before_us, window_end_us, metrics_config):
    """Resolves every metric for one window - waiting indefinitely (polling every
    POLL_INTERVAL_SECONDS) for whichever checkpoints haven't shown up yet, with no attempt limit,
    except every metric individually gives up (reporting n/a) after BOUNDED_WAIT_SECONDS - see its
    note above.

    Each Metric is scoped to `window_node` by default, or `self_node` if its config entry set
    "node: self" - see the module docstring.

    `window_end_us` - this window's boundary, i.e. exactly what wait_for_new_window() just
    returned - and `not_before_us` - the *previous* window's boundary (None for the very first
    window of a watch session) - together scope every lookup to this window specifically, so neither
    a checkpoint left over from an earlier window nor one belonging to whatever window comes *next*
    (started while this one was still being resolved) can be mistaken for this one's. Two windows
    close together break that assumption two different ways, both confirmed empirically against a
    live watch session:

      - A window that never produces a given checkpoint can pick up a *previous* window's
        occurrence of it instead of correctly reporting n/a, if that occurrence is still within
        VictoriaMetrics' staleness window and nothing excludes it with a lower bound.

      - The opposite leak is just as real: with only a lower bound, a window still being resolved
        (e.g. waiting out BOUNDED_WAIT_SECONDS for a checkpoint that doesn't apply) can pick up a
        checkpoint that belongs to whatever *next* window starts before this one finishes, if nothing
        caps how far forward a lookup can reach.

    So every lookup is constrained on both sides. Every checkpoint a metric measures necessarily
    happens at or before its window's boundary (nothing in this script's model of "a window"
    happens after it), so bounding every lookup to at-or-before window_end_us never excludes a
    checkpoint that legitimately belongs to the window being resolved.

    Returns (results, metrics) - the caller already knows window_end_us to tell this window apart
    from the next one wait_for_new_window() finds, so it isn't returned again."""
    results = {}
    metrics = [
        Metric(
            node=self_node if entry.get("node") == "self" else window_node,
            window_node=window_node,
            **{k: v for k, v in entry.items() if k not in ("node", "window_end_settle_seconds")},
        )
        for entry in metrics_config
    ]
    pending = list(metrics)
    deadline = time.monotonic() + BOUNDED_WAIT_SECONDS

    while pending:
        pending = [m for m in pending if not m.try_resolve(victoria_url, results, not_before_us, window_end_us)]

        if not pending or time.monotonic() >= deadline:
            break

        time.sleep(POLL_INTERVAL_SECONDS)

    return results, metrics


def resolve_per_instance_breakdowns(metrics):
    """For every metric marked "per_instance" (see Metric) that resolved, returns
    {label: [(instance_id, duration_s), ...]} - each of its end_source_pattern matches paired with
    its elapsed time since that metric's start, labeled by the match's source with the pattern's
    fixed literal prefix stripped (see _literal_prefix())."""
    breakdowns = {}
    for m in metrics:
        if not m.per_instance or m.end_us is None:
            continue

        prefix = _literal_prefix(m.end_source_pattern)
        breakdowns[m.label] = [
            (source[len(prefix) :] if prefix and source.startswith(prefix) else source, (us - m.start_us) / 1_000_000)
            for source, us in m.end_matches
        ]

    return breakdowns


def advance_not_before_us(victoria_url, self_node, window_node, window_end_us, metrics_config):
    """The exclusion boundary to hand the next window - normally just window_end_us, except an
    end_source_pattern metric's start_event can log a second, trailing occurrence strictly
    after window_end_us (see BOUNDARY_METRIC_LOOKAHEAD_US), which would otherwise leak into the next
    window's lookup for that same metric if that window never produces a fresh occurrence of its
    own. Called once, right after a window resolves, to fold every such trailing occurrence (if any)
    into the boundary before it's used again - the *latest* of each end_source_pattern metric's
    earliest-trailing-occurrence (see BOUNDARY_METRIC_LOOKAHEAD_US for why earliest, not latest,
    within each metric's lookahead), since excluding up to the latest of them safely excludes
    every earlier one too."""
    candidates = [window_end_us]
    for entry in metrics_config:
        if not entry.get("end_source_pattern"):
            continue

        node = self_node if entry.get("node") == "self" else window_node
        trailing = query_samples_us(
            victoria_url,
            event_query(node, entry["start_source"], entry["start_event"]),
            at_time_us=window_end_us + BOUNDARY_METRIC_LOOKAHEAD_US,
            not_before_us=window_end_us,
        )
        if trailing:
            candidates.append(min(trailing))

    return max(candidates)


def publish_results(victoria_url, metrics, results, breakdowns):
    """Pushes every resolved metric as a benchmark_result sample (see push_result()), so it shows up
    in Grafana's "Benchmark Results" table. Each metric is published with its already-resolved
    `node` (see resolve_window()) and its start_source as "source"; each per-instance breakdown
    value (if any) with that occurrence's id as "Instance: <id>"."""
    for m in metrics:
        value = results.get(m.label)
        if value is not None:
            push_result(victoria_url, m.node, m.start_source, metric_name(m.label), value)

    for label, breakdown in breakdowns.items():
        metric = next(m for m in metrics if m.label == label)
        for instance_id, duration_s in breakdown:
            push_result(victoria_url, metric.node, f"Instance: {instance_id}", metric_name(label), duration_s)


def seed_last_end_us(victoria_url, window_end, self_node, metrics_config):
    """The boundary this script starts watching from - seeded with whatever boundary occurrence
    is already the latest right now, not None: unlike report_timing.py (a script a human starts
    *before* triggering a deployment, so nothing was "current" yet when it started), this script can
    start at any point in its life - after a crash, a restart, or an upgrade - with an arbitrary,
    possibly-stale window already sitting in VictoriaMetrics from whenever it last stopped. Starting
    from None would let wait_for_new_window() immediately treat that pre-existing window as brand
    "new" and resolve_window() would then run with no previous-window boundary at all
    (not_before_us=None), free to pull in "the latest occurrence of X" for every checkpoint regardless
    of which past window it actually belongs to - confirmed empirically: a plain restart re-published
    a fabricated window built from two different, unrelated past runs' checkpoints. Seeding here
    instead means only a window whose boundary happens *after* this script started watching is
    ever resolved - anything already sitting in VictoriaMetrics from before that is skipped rather
    than risking a wrong result for it. Only used when there's no persisted state file to resume from
    instead - see load_state().

    Looks back over BOUNDARY_MAX_LOOKBACK_US, not the shorter QUERY_MAX_LOOKBACK_US every other
    lookup uses, so a baseline older than the latter (this script restarting after a long idle
    period) is still found rather than read as "no baseline at all".

    Also run through advance_not_before_us() before being returned, same as after every window this
    script resolves - otherwise this seed has the exact same gap advance_not_before_us() exists to
    close, just at startup instead of between windows - confirmed empirically: a restart shortly
    after a window produced a bogus, wildly inflated value this way, using the previous window's
    leftover trailing occurrence as the new window's start.

    Retries indefinitely (every POLL_INTERVAL_SECONDS) on a VictoriaMetricsError, rather than letting
    it propagate out of main() before its retry loop even starts (which would end publication
    for the rest of this script's lifetime, since nothing else would catch it): a systemd unit
    ordering only orders VictoriaMetrics' unit *start*, not its HTTP endpoint actually being
    ready to answer, so this script's very first request can legitimately fail even on a normal boot.
    """
    while True:
        try:
            found = _latest_boundary_sample(victoria_url, window_end, self_node)
            if found is None:
                return None
            seed_end_us, seed_node = found
            return advance_not_before_us(victoria_url, self_node, seed_node, seed_end_us, metrics_config)
        except VictoriaMetricsError as err:
            print(f"benchmark-results-publisher: error seeding baseline: {err}", file=sys.stderr)
            time.sleep(POLL_INTERVAL_SECONDS)


def load_state(state_file):
    """The boundary persisted by save_state() on a previous run, or None if there is no (readable)
    state file - in which case main() falls back to seed_last_end_us(). Resuming from it, rather than
    always seeding from the latest boundary already in VictoriaMetrics, means a window detected but
    not yet published when this script stopped (a crash, a restart, an upgrade - this is a
    long-running service with Restart=on-failure) is still published once it starts again, instead
    of being skipped for good."""
    if not state_file:
        return None

    try:
        with open(state_file) as f:
            return int(f.read().strip())
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as err:
        print(f"benchmark-results-publisher: ignoring state file {state_file}: {err}", file=sys.stderr)
        return None


def save_state(state_file, last_end_us):
    """Persists `last_end_us` for load_state() - written to a temporary file and renamed over the
    real one, so a crash mid-write can't leave a truncated value behind.

    Retries (every ERROR_RETRY_SECONDS) until it succeeds, rather than raising or carrying on: the
    window was already published, so raising would make main() retry - and so re-publish - it, while
    carrying on would let later windows be published with their boundary only in memory, and a
    restart would then resume from the older persisted boundary, or, with no state file at all, skip
    every already-retained window via seed_last_end_us()."""
    if not state_file:
        return

    tmp_file = f"{state_file}.tmp"
    while True:
        try:
            with open(tmp_file, "w") as f:
                f.write(f"{last_end_us}\n")
            os.replace(tmp_file, state_file)
            return
        except OSError as err:
            print(
                f"benchmark-results-publisher: failed to save state file {state_file}, retrying: {err}",
                file=sys.stderr,
            )
            time.sleep(ERROR_RETRY_SECONDS)


def main():
    """Parse arguments, load config, then watch VictoriaMetrics for new windows forever, resolving
    and publishing each one's aggregated metrics - unlike report_timing.py's --publish flag,
    publishing here is not optional, since the whole point of this script existing is that nobody has
    to remember to run it, let alone pass a flag to it.

    `last_end_us` only advances *after* publish_results() succeeds, not right after resolve_window()
    returns: a VictoriaMetricsError raised anywhere before that aborts this attempt entirely
    (caught below) without having moved the boundary, so the exact same window is retried next time
    around rather than being silently marked "done" despite a failed - or, for a push failure partway
    through publish_results(), partial - write. A retry after a partial publish failure re-pushes
    every metric from scratch, including whichever already succeeded before the failure - accepted
    here as a rare, cosmetic duplicate-sample risk (each push is its timestamped point, not an
    overwrite) rather than building a persisted per-window publish log just to avoid it. The next
    window's exclusion boundary (advance_not_before_us()) is computed *before* publishing, since
    it needs more queries of its own: computed after, a failure there would retry - and so
    re-publish - a window that was already published in full.

    Errors are caught and retried rather than propagated, since one bad window - including a
    VictoriaMetricsError from any query or push above, deliberately not swallowed at the source -
    shouldn't end publication for the rest of this script's lifetime."""
    args = parse_args()
    window_end, metrics_config = load_config(args.config)

    print(f"benchmark-results-publisher: watching {args.victoria_url} for new windows")

    window_number = 0
    last_end_us = load_state(args.state_file)
    if last_end_us is None:
        last_end_us = seed_last_end_us(args.victoria_url, window_end, args.node, metrics_config)

    while True:
        try:
            window_end_us, window_node = wait_for_new_window(
                args.victoria_url, window_end, args.node, last_end_us
            )

            window_number += 1

            results, metrics = resolve_window(
                args.victoria_url, window_node, args.node, last_end_us, window_end_us, metrics_config
            )
            breakdowns = resolve_per_instance_breakdowns(metrics)
            next_not_before_us = advance_not_before_us(
                args.victoria_url, args.node, window_node, window_end_us, metrics_config
            )
            publish_results(args.victoria_url, metrics, results, breakdowns)
            last_end_us = next_not_before_us
            save_state(args.state_file, last_end_us)

            node_note = "" if window_node == args.node else f" on node {window_node!r}"
            parts = [f"{label}={value:.3f}s" for label, value in results.items()]
            summary = ", ".join(parts) if parts else "no metrics resolved"
            print(f"benchmark-results-publisher: window {window_number} published{node_note}: {summary}")
        except Exception as err:  # noqa: BLE001 - keep this script alive across any single failure
            print(f"benchmark-results-publisher: error resolving window: {err}", file=sys.stderr)
            time.sleep(ERROR_RETRY_SECONDS)


if __name__ == "__main__":
    main()

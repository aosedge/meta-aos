#!/usr/bin/env python3
"""Watch VictoriaMetrics for repeating "windows" of checkpoint_event samples (e.g. one AosCore
deployment cycle) and publish each window's aggregated elapsed-time metrics back to VictoriaMetrics
as benchmark_result samples - the job a human used to have to run report_timing.py by hand for.

Entirely config-driven (see --config, load_config()): nothing in this script names a specific
service, checkpoint text, or event - what marks a new window, and which pairs of checkpoints define
each metric, are both read from the config file. The shipped default config happens to describe
AosCore's own Operational Speed checkpoints, but this script itself has no idea what AosCore is.

How a "window" is found and resolved:

  - `suite_boundary` in the config names one recurring checkpoint_event (a source regex + an exact
    event) whose *latest* occurrence, across every node, marks the end of the current window and the
    start of watching for the next one - e.g. AosCore's own benchmark-timing instances each push an
    "Instance: <id>" / "Start" sample, and the latest one across an entire deployment batch is that
    deployment's own boundary. Only one node's own checkpoints define a window (see the `node`
    section below); the rest of this script assumes a window's own metrics all happened on that same
    node, not split across several.

  - Every metric in `metrics` is the elapsed time between two checkpoint_event samples - a `start`
    and an `end` - looked up independently once a window's own boundary is known. A metric whose own
    `end_is_suite_boundary` is set instead ends exactly at the window's own boundary timestamp, for a
    "how long did the whole window take" style metric (see Metric).

  - Every lookup is bounded on both sides by the *previous* window's own boundary and the *current*
    window's own boundary, so a checkpoint left over from an earlier window, or one belonging to
    whatever window starts next (while this one is still being resolved), can never be mistaken for
    this window's own - see the module-level notes below `resolve_window()` for the empirically
    confirmed failure modes this guards against, and why a metric whose own checkpoint can recur more
    than once per window (`nearest_end`, or an `end_is_suite_boundary` metric's own start) needs
    extra care beyond simple bounding.

  - A metric that never applies to a given window (e.g. a metric only a certain kind of run
    produces) is given up on - reported as absent, never published - after BOUNDED_WAIT_SECONDS,
    rather than blocking this script on that window forever. Finding the window's own boundary in
    the first place has no such timeout: that's what defines a window existing at all.

Node (`node: self` in a metric, or omitted): most metrics are looked up (and published) on whichever
node the *current window's own* boundary occurrence came from (its own "node" label) - but a metric
whose own checkpoint is only ever logged by one specific node regardless of where a window's own
activity happens (e.g. a controller component that only runs on one particular node) sets
`node: self` to pin it to this script's own `--node` instead. This script itself should only ever
run once (see its own recipe) - VictoriaMetrics is a single shared store, so watching from more than
one place at once would double-detect and double-publish every window.

Usage:
    benchmark_results_publisher.py --victoria-url http://localhost:8428 \
        --config benchmark-results-publisher.yml --node main
"""

import argparse
import datetime
import json
import re
import sys
import time
import urllib.parse
import urllib.request

import yaml


def parse_args():
    """Parse --victoria-url / --config / --node command-line options."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--victoria-url",
        required=True,
        help="VictoriaMetrics base URL, e.g. http://localhost:8428",
    )
    parser.add_argument(
        "--config",
        required=True,
        help="path to a YAML file with suite_boundary/metrics, see benchmark-results-publisher.yml",
    )
    parser.add_argument(
        "--node",
        required=True,
        help='this script\'s own "node" identity - used only by a metric or suite_boundary marked '
        '"node: self"/pinned to a specific node, not by anything scoped to a window\'s own node',
    )
    return parser.parse_args()


class VictoriaMetricsError(Exception):
    """Raised by push_line()/query_metrics() on a transport or malformed-response failure talking to
    VictoriaMetrics - distinct from a request that succeeded but simply found nothing (query_metrics()
    still returns [] for that). Conflating the two would mean a transient outage during window
    resolution looks identical to "this checkpoint genuinely doesn't exist", silently turning a real,
    delayed metric into a permanent n/a, or a transient publish failure into a silently dropped
    sample. Every caller here lets this propagate up to main()'s own top-level retry loop instead of
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
    "time_us" label format event_exporter.py's own push_event() uses, read back by parse_time_us()."""
    # Exact integer arithmetic, not timestamp_us / 1e6 - float64 is right at the edge of enough
    # precision for a 10-digit epoch second count plus 6 more decimal digits, so this avoids any
    # risk of the last microsecond digit being wrong.
    seconds, microseconds = divmod(timestamp_us, 1_000_000)
    dt = datetime.datetime.fromtimestamp(seconds, tz=datetime.timezone.utc)
    dt += datetime.timedelta(microseconds=microseconds)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")


def parse_time_us(text):
    """Parses a "YYYY-MM-DD HH:MM:SS.ffffff" UTC "time_us" label back into a microsecond epoch
    timestamp - the precise time event_exporter.py's own push_event() carries in that label, since
    VictoriaMetrics' own sample timestamps are millisecond-precision only (confirmed empirically: two
    points pushed 500us apart both landed on the same millisecond) - too coarse to order two
    checkpoints that land in the same millisecond, which every lookup here needs to do correctly."""
    dt = datetime.datetime.strptime(text, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=datetime.timezone.utc)
    return int(dt.timestamp()) * 1_000_000 + dt.microsecond


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
# text - notably not whitespace, unlike Python's re.escape(), which also escapes it (for its own
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


def boundary_query(suite_boundary, self_node=None):
    """A PromQL selector for suite_boundary's own recurring checkpoint - see load_config(). Scoped to
    a specific node only if suite_boundary itself names one ("self" resolving to `self_node`, same as
    a metric's own "node: self" - see Metric); by default (no "node" key) it matches every node,
    since whichever node a window's own boundary checkpoint lands on is exactly what
    resolve_window() needs to discover, not assume.

    `source_pattern` is a regex the config author writes intentionally (unlike every other string
    interpolated into a PromQL selector here, which is a literal value regex-escaped first via
    _escape_regex_literal() so it matches itself exactly) - it must NOT go through
    _escape_regex_literal(), which would mangle the author's own regex metacharacters, but it still
    needs escape_promql_string()'s separate, syntactic layer: without it, a pattern containing a
    literal `"` or `\\` (e.g. `\\d`) would be misparsed or rejected by PromQL's own string-literal
    syntax before the regex engine downstream ever saw it - confirmed as a real gap, not just this
    script's own default pattern being simple enough to not trigger it."""
    node = suite_boundary.get("node")
    if node == "self":
        node = self_node
    node_label = f'node="{escape_promql_string(node)}",' if node else ""
    pattern = escape_promql_string(_escape_regex_literal(suite_boundary["event"]))
    source_pattern = escape_promql_string(suite_boundary["source_pattern"])
    return f'checkpoint_event{{{node_label}source=~"{source_pattern}",event=~"^{pattern}(:.*)?$"}}'


# Overrides VictoriaMetrics' own default instant-query staleness window (~5 minutes) - without this,
# a checkpoint whose event happened more than that long before a query's own evaluation time is
# invisible to that query even though the sample is still in VictoriaMetrics - confirmed empirically:
# a sample pushed 10 minutes before the query's evaluation time was missing from a default query and
# only appeared once max_lookback was widened past that gap. This matters for real runs, not just
# fast tests: a metric whose own start and end checkpoints can legitimately be many minutes apart
# (e.g. a large download) would otherwise silently read as n/a once BOUNDED_WAIT_SECONDS ran out,
# even though the real sample was sitting in VictoriaMetrics the whole time. 30 minutes is generous
# for the checkpoints this ships against by default; a genuinely slower window would need this
# widened further.
QUERY_MAX_LOOKBACK_US = 30 * 60 * 1_000_000


def query_metrics(victoria_url, promql, at_time_us=None):
    """Runs an instant PromQL query against VictoriaMetrics and returns every matching sample's full
    label set (a dict, as VictoriaMetrics' own "metric" field). Returns [] if the query succeeded but
    nothing matches; raises VictoriaMetricsError - see VictoriaMetricsError - on a transport or
    malformed-response failure, so callers can tell "no such checkpoint" apart from "couldn't ask".
    Catches OSError, not just urllib.error.URLError - see push_line()'s own note on why."""
    params = {
        "query": promql,
        # Without this, VictoriaMetrics can serve a cached response from an earlier attempt at the
        # same query string, masking a checkpoint that has since become visible.
        "nocache": "1",
        "max_lookback": f"{QUERY_MAX_LOOKBACK_US // 1_000_000}s",
    }
    if at_time_us is not None:
        params["time"] = f"{at_time_us / 1_000_000:.6f}"

    url = f"{victoria_url.rstrip('/')}/api/v1/query?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, method="GET")

    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = json.loads(response.read())
    except (OSError, json.JSONDecodeError) as err:
        raise VictoriaMetricsError(f"failed to query VictoriaMetrics: {err}") from err

    return [entry.get("metric", {}) for entry in body.get("data", {}).get("result", [])]


def query_samples_us(victoria_url, promql, at_time_us=None, not_before_us=None):
    """Every query_metrics() match's precise timestamp - read from its "time_us" label rather than
    the sample's own millisecond-precision timestamp - excluding any at or before `not_before_us`,
    if given (see resolve_window()'s own stale-carryover note)."""
    samples = []
    for metric in query_metrics(victoria_url, promql, at_time_us):
        time_us_label = metric.get("time_us")
        if time_us_label:
            us = parse_time_us(time_us_label)
            if not_before_us is None or us > not_before_us:
                samples.append(us)

    return samples


def query_latest_us(victoria_url, promql, at_time_us=None, not_before_us=None):
    """The latest of query_samples_us()'s results, or None if it returned none."""
    samples = query_samples_us(victoria_url, promql, at_time_us, not_before_us)
    return max(samples) if samples else None


def query_boundary_samples(victoria_url, suite_boundary, self_node, at_time_us=None, not_before_us=None):
    """Like query_samples_us(), but for suite_boundary's own recurring checkpoint specifically,
    returning (instance_id, node, time_us) triples - the "source" label with the boundary's own
    source_pattern's fixed literal prefix stripped (if any - see load_config()), since that's what a
    per_instance metric's own breakdown (resolve_window()) needs to label each occurrence by, and
    each sample's own "node" label, since a boundary query not pinned to one node (the common case -
    see boundary_query()) can return occurrences from more than one. `self_node` is only used if
    suite_boundary itself sets "node: self" - see boundary_query()."""
    samples = []
    prefix = suite_boundary.get("_source_prefix", "")
    for metric in query_metrics(victoria_url, boundary_query(suite_boundary, self_node), at_time_us):
        time_us_label = metric.get("time_us")
        if not time_us_label:
            continue

        us = parse_time_us(time_us_label)
        if not_before_us is not None and us <= not_before_us:
            continue

        source = metric.get("source", "")
        instance_id = source[len(prefix) :] if prefix and source.startswith(prefix) else source
        samples.append((instance_id, metric.get("node", ""), us))

    return samples


_METRIC_REQUIRED_KEYS = {"label", "start_source", "start_event"}
_METRIC_OPTIONAL_KEYS = {
    "end_source", "end_event", "end_is_suite_boundary", "nearest_end", "fallback", "per_instance", "node",
}
_FALLBACK_ALLOWED_KEYS = {"start_source", "start_event", "end_source", "end_event"}


def _validate_metric(i, entry):
    """Validates one "metrics" config entry - see _load_metrics()."""
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

    end_is_suite_boundary = entry.get("end_is_suite_boundary", False)
    has_end_pair = "end_source" in entry and "end_event" in entry
    if end_is_suite_boundary and has_end_pair:
        fail("end_is_suite_boundary and end_source/end_event are mutually exclusive")
    if not end_is_suite_boundary and not has_end_pair:
        fail("needs end_source and end_event, or end_is_suite_boundary: true")

    if "fallback" in entry and entry.get("nearest_end"):
        fail("fallback and nearest_end are mutually exclusive")

    fallback = entry.get("fallback")
    if fallback is not None:
        if not fallback:
            fail("fallback, if given, must override at least one key")
        unknown_fallback = fallback.keys() - _FALLBACK_ALLOWED_KEYS
        if unknown_fallback:
            fail(f"fallback has unknown key(s): {sorted(unknown_fallback)}")

    node = entry.get("node")
    if node is not None and node != "self":
        fail(f'"node" must be "self" if given, not {node!r}')


def _load_metrics(raw_metrics):
    """Validates the "metrics" section of the config file (see load_config(), _validate_metric())
    and returns it as a list of dicts ready for Metric(**metric_def). Fails fast on a
    missing/unknown/contradictory key rather than letting a typo surface later as a silently-wrong
    or permanently n/a metric, since this only runs once, at startup."""
    for i, entry in enumerate(raw_metrics):
        _validate_metric(i, entry)

    return list(raw_metrics)


def load_config(config_path):
    """Load benchmark-results-publisher's config file: `suite_boundary` (what marks a new window -
    see boundary_query()) and `metrics` (the elapsed-time table each is resolved from - see Metric).
    Returns (suite_boundary, metrics)."""
    with open(config_path) as f:
        config = yaml.safe_load(f) or {}

    suite_boundary = config.get("suite_boundary")
    if not suite_boundary or "source_pattern" not in suite_boundary or "event" not in suite_boundary:
        raise ValueError('config needs a "suite_boundary" section with "source_pattern" and "event"')

    # A source_pattern like '^Instance: .*' has a fixed literal prefix before its own wildcard part -
    # used only to label a per_instance metric's own breakdown by whatever varies after that prefix
    # (e.g. an instance id), purely cosmetic (see query_boundary_samples()); a source_pattern with no
    # such simple prefix (or none at all) just leaves each occurrence labeled by its full source text.
    prefix_match = re.match(r"^\^?([^.^$|()\[\]{}*+?\\]*)", suite_boundary["source_pattern"])
    suite_boundary = {**suite_boundary, "_source_prefix": prefix_match.group(1) if prefix_match else ""}

    metrics = _load_metrics(config.get("metrics", []))
    return suite_boundary, metrics


STOP_ALL_PREFIX = "Stop all "


class Metric:
    """Resolves one "metrics" config entry's elapsed time into results[label] - see load_config()."""

    def __init__(
        self, label, start_source, start_event, end_source=None, end_event=None,
        end_is_suite_boundary=False, nearest_end=False, fallback=None, per_instance=False, node=None,
    ):
        self.label = label
        self.start_source = start_source
        self.start_event = start_event
        self.end_source = end_source
        self.end_event = end_event
        self.end_is_suite_boundary = end_is_suite_boundary
        # If True, `end_event` can recur many times after `start_event` (e.g. a checkpoint that
        # follows a rare event on every occurrence afterward, not just the one that belongs with it) -
        # the plain latest occurrence could belong to a much later, unrelated window, so the end is
        # instead resolved as the earliest occurrence at or after `start_event`'s own timestamp.
        self.nearest_end = nearest_end
        # A {start_source, start_event, end_source, end_event} dict (any subset - unset keys fall
        # back to this metric's own primary ones) tried only if the primary pair isn't found - for a
        # checkpoint pair a service logs two different ways depending on the situation (see
        # try_resolve()). Cached together as one pair with the primary, not independently: mixing a
        # primary start with a fallback end (or vice versa) would silently measure nothing meaningful.
        self.fallback = fallback
        # If True, also publish one benchmark_result sample per suite_boundary occurrence in this
        # window, each the elapsed time from this metric's own start_us to that occurrence's own
        # timestamp - see resolve_window().
        self.per_instance = per_instance
        # Resolved by the caller (resolve_window()) to either the window's own node or this script's
        # own "self" node, per this entry's own "node" setting - see the module docstring.
        self.node = node
        self.start_us = None
        self.end_us = None

    def try_resolve(self, victoria_url, results, not_before_us, window_end_us):
        """Attempts to fill in whichever of this metric's two ends is still missing. Every lookup is
        scoped to this window specifically: `not_before_us` excludes any candidate at or before the
        previous window's own boundary, and `window_end_us` (this window's own boundary) is used as
        the query's own evaluation time, so a candidate belonging to whatever *next* window happens to
        have started by the time this call runs can't be mistaken for this one's either - every
        checkpoint a metric measures necessarily happens at or before its own window's boundary, so
        this is never too tight - see resolve_window()'s own stale-carryover note. Returns True (and
        records the elapsed time into `results`) once both ends are found."""
        if self.end_is_suite_boundary:
            self.end_us = window_end_us
            if self.start_us is None:
                self.start_us = query_latest_us(
                    victoria_url,
                    event_query(self.node, self.start_source, self.start_event),
                    at_time_us=window_end_us,
                    not_before_us=not_before_us,
                )
        elif self.fallback:
            self._try_resolve_fallback(victoria_url, not_before_us, window_end_us)
        else:
            self._try_resolve_plain(victoria_url, not_before_us, window_end_us)

        if self.start_us is None or self.end_us is None:
            return False

        results[self.label] = (self.end_us - self.start_us) / 1_000_000
        return True

    def _try_resolve_plain(self, victoria_url, not_before_us, window_end_us):
        """Resolves self.start_us/self.end_us for the common case: independently-cached lookups, no
        variant to choose between - see try_resolve()."""
        if self.start_us is None:
            self.start_us = query_latest_us(
                victoria_url,
                event_query(self.node, self.start_source, self.start_event),
                at_time_us=window_end_us,
                not_before_us=not_before_us,
            )

        if self.start_us is None:
            return

        if self.end_us is None:
            if self.nearest_end:
                # Querying at window_end_us (not some fixed offset past start_us) makes
                # VictoriaMetrics consider every occurrence up to the window's own boundary current
                # and return all of them (bounded backward by QUERY_MAX_LOOKBACK_US) - then the
                # earliest of those at or after start_us is this metric's actual end, not whichever
                # happens to be the most recent right now. Already necessarily after not_before_us,
                # since it's after self.start_us, which is - no separate not_before_us filtering
                # needed here.
                candidates = query_samples_us(
                    victoria_url, event_query(self.node, self.end_source, self.end_event), at_time_us=window_end_us
                )
                candidates = [us for us in candidates if self.start_us <= us <= window_end_us]
                self.end_us = min(candidates) if candidates else None
            else:
                self.end_us = query_latest_us(
                    victoria_url,
                    event_query(self.node, self.end_source, self.end_event),
                    at_time_us=window_end_us,
                    not_before_us=not_before_us,
                )

    def _try_resolve_fallback(self, victoria_url, not_before_us, window_end_us):
        """Resolves self.start_us/self.end_us when this metric has a `fallback` pair: the primary
        pair is tried first and preferred whenever found; the fallback pair is only used if the
        primary is never found at all - see the "fallback" note in __init__()."""
        if self.start_us is not None and self.end_us is not None:
            return

        def latest(source, event):
            return query_latest_us(
                victoria_url, event_query(self.node, source, event), at_time_us=window_end_us,
                not_before_us=not_before_us,
            )

        start_us = latest(self.start_source, self.start_event)
        end_us = latest(self.end_source, self.end_event) if start_us is not None else None

        if start_us is None or end_us is None:
            fb_start_source = self.fallback.get("start_source", self.start_source)
            fb_start_event = self.fallback.get("start_event", self.start_event)
            fb_end_source = self.fallback.get("end_source", self.end_source)
            fb_end_event = self.fallback.get("end_event", self.end_event)
            start_us = latest(fb_start_source, fb_start_event)
            end_us = latest(fb_end_source, fb_end_event) if start_us is not None else None

        if start_us is not None and end_us is not None:
            self.start_us, self.end_us = start_us, end_us


# How often an unresolved metric or a not-yet-started window is re-polled - see resolve_window() and
# wait_for_new_window(). There is no attempt limit for a window's own boundary: that waits until
# interrupted instead - except every individual metric, see BOUNDED_WAIT_SECONDS below.
POLL_INTERVAL_SECONDS = 5

# How often the main loop retries after an unexpected error resolving a window, so one bad window (or
# a transient VictoriaMetrics outage) can't silently end publication for the rest of the service's
# lifetime.
ERROR_RETRY_SECONDS = 30

# Every metric gives up (reporting n/a - never published) after this long rather than waiting
# forever, since any of them can be genuinely absent from a given window depending on what kind of
# run it was - a metric that a given window's own activity simply never produces would otherwise
# leave this script stuck on that window forever, no matter how long it waits (confirmed
# empirically). Wide enough to comfortably clear VictoriaMetrics' default ~30s -search.latencyOffset
# (a freshly ingested sample isn't necessarily visible to a query right away).
BOUNDED_WAIT_SECONDS = 40

# An end_is_suite_boundary metric's own start_event can recur more than once per window (e.g. a
# checkpoint logged both when a process starts handling something and again once it finishes) - the
# *trailing* occurrence, if any, lands strictly after the window's own boundary and would otherwise
# leak into the *next* window's own lookup for that same metric if that window has no fresh
# occurrence of its own (confirmed empirically: produced a wildly inflated value this way).
# BOUNDARY_METRIC_LOOKAHEAD_US bounds how far past a window's own boundary this trailing occurrence is
# looked for (the *earliest* occurrence in that window - see advance_not_before_us()), so it can be
# folded into the exclusion boundary handed to the next window instead. Deliberately short (a
# trailing occurrence has landed well under a second after the boundary in every run observed) rather
# than generous: a longer window risks reaching past the trailing occurrence entirely and into the
# *next* window's own fresh occurrence of the same event (if that window begins soon after this one) -
# confirmed empirically at 30s: a second window only 22s after the first had its own start event
# mistaken for the first window's trailing occurrence, advancing the boundary *past* that second
# window's own boundary and leaving it undetectable. Picking the earliest occurrence in the window
# (not the latest) is a second, independent guard against the same failure mode, in case two windows
# ever do land inside one lookahead period regardless.
#
# Residual risk, accepted rather than eliminated: if a *next* window's own boundary happens within
# this lookahead and that window's own fresh occurrence is the only one in it (i.e. the current
# window has none of its own to find first), the earliest-pick above still folds that next window's
# own occurrence in - not wrongly inflating anything this time, but leaving that metric unable to
# find its own start for the next window (excluded by its own not_before_us), reading n/a instead of
# its real value.
BOUNDARY_METRIC_LOOKAHEAD_US = 10 * 1_000_000

# How long wait_for_new_window() keeps re-checking for an even-newer boundary occurrence after
# finding one, before treating it as this window's own final boundary, in case more of the same
# batch (e.g. several instances starting near-simultaneously) is still trickling in. A multi-sample
# batch's own occurrences have landed within milliseconds of each other in every run observed, so
# this default is generous headroom, not a tight race - but nothing guarantees every sample in a
# batch reports within a single poll, and without this, wait_for_new_window() has no way to tell "the
# last sample of this batch" apart from "a sample that happened to report first, with more of the
# same batch still incoming": locking in the latter would split one real window into two and
# permanently exclude whatever lands after it (every lookup is bounded to at-or-before the window's
# own boundary - see Metric.try_resolve()). Overridable per suite_boundary via "settle_seconds".
DEFAULT_SETTLE_SECONDS = 2


def _latest_boundary_sample(victoria_url, suite_boundary, self_node, not_before_us):
    """The (time_us, node) of the latest suite_boundary occurrence after `not_before_us` - or None if
    there isn't one. Shared by wait_for_new_window()'s own initial and settle checks."""
    samples = query_boundary_samples(victoria_url, suite_boundary, self_node, not_before_us=not_before_us)
    if not samples:
        return None

    _, node, end_us = max(samples, key=lambda sample: sample[2])
    return end_us, node


def wait_for_new_window(victoria_url, suite_boundary, self_node, last_end_us):
    """Polls (every POLL_INTERVAL_SECONDS, forever) until a newer suite_boundary occurrence shows up
    than `last_end_us` (None on the very first call, meaning "whatever's current right now"), then
    returns (window_end_us, window_node): `window_node` is whichever node that occurrence came from,
    taken as the single node this window's own activity happened on for every subsequent lookup (see
    resolve_window()) - a window whose own activity is split across more than one node isn't
    supported. This is what turns window resolution into a continuous watcher instead of a one-shot
    report.

    Once a candidate shows up, keeps re-checking for suite_boundary's own "settle_seconds" (default
    DEFAULT_SETTLE_SECONDS) of consecutive quiet before returning it, in case more of the same batch
    is still trickling in - see DEFAULT_SETTLE_SECONDS."""
    settle_seconds = suite_boundary.get("settle_seconds", DEFAULT_SETTLE_SECONDS)

    while True:
        found = _latest_boundary_sample(victoria_url, suite_boundary, self_node, last_end_us)
        if found is not None:
            end_us, node = found
            settled_since = time.monotonic()
            while time.monotonic() - settled_since < settle_seconds:
                time.sleep(1)
                newer = _latest_boundary_sample(victoria_url, suite_boundary, self_node, end_us)
                if newer is not None:
                    end_us, node = newer
                    settled_since = time.monotonic()

            return end_us, node

        time.sleep(POLL_INTERVAL_SECONDS)


def resolve_window(victoria_url, window_node, self_node, not_before_us, window_end_us, metrics_config):
    """Resolves every metric for one window - waiting indefinitely (polling every
    POLL_INTERVAL_SECONDS) for whichever checkpoints haven't shown up yet, with no attempt limit,
    except every metric individually gives up (reporting n/a) after BOUNDED_WAIT_SECONDS - see its
    own note above.

    Each Metric is scoped to `window_node` by default, or `self_node` if its own config entry set
    "node: self" - see the module docstring.

    `window_end_us` - this window's own boundary, i.e. exactly what wait_for_new_window() just
    returned - and `not_before_us` - the *previous* window's own boundary (None for the very first
    window of a watch session) - together scope every lookup to this window specifically, so neither
    a checkpoint left over from an earlier window nor one belonging to whatever window comes *next*
    (started while this one was still being resolved) can be mistaken for this one's. Two windows
    close together break that assumption two different ways, both confirmed empirically against a
    live watch session:

      - A window that never produces a given checkpoint can pick up a *previous* window's own
        occurrence of it instead of correctly reporting n/a, if that occurrence is still within
        VictoriaMetrics' own staleness window and nothing excludes it with a lower bound.

      - The opposite leak is just as real: with only a lower bound, a window still being resolved
        (e.g. waiting out BOUNDED_WAIT_SECONDS for a checkpoint that doesn't apply) can pick up a
        checkpoint that belongs to whatever *next* window starts before this one finishes, if nothing
        caps how far forward a lookup can reach.

    So every lookup is constrained on both sides. Every checkpoint a metric measures necessarily
    happens at or before its own window's boundary (nothing in this script's model of "a window"
    happens after it), so bounding every lookup to at-or-before window_end_us never excludes a
    checkpoint that legitimately belongs to the window being resolved.

    Returns (results, metrics) - the caller already knows window_end_us to tell this window apart
    from the next one wait_for_new_window() finds, so it isn't returned again."""
    results = {}
    metrics = [
        Metric(node=self_node if entry.get("node") == "self" else window_node, **{
            k: v for k, v in entry.items() if k != "node"
        })
        for entry in metrics_config
    ]
    pending = list(metrics)
    bounded_labels = {m.label for m in metrics}

    started_at = time.monotonic()

    while pending:
        pending = [m for m in pending if not m.try_resolve(victoria_url, results, not_before_us, window_end_us)]

        if pending and time.monotonic() - started_at > BOUNDED_WAIT_SECONDS:
            pending = [m for m in pending if m.label not in bounded_labels]

        if pending:
            time.sleep(POLL_INTERVAL_SECONDS)

    return results, metrics


def resolve_per_instance_breakdowns(victoria_url, suite_boundary, self_node, window_node, window_end_us, metrics):
    """For every metric marked "per_instance" (see Metric) that resolved a start_us, returns
    {label: [(instance_id, duration_s), ...]} - each suite_boundary occurrence on `window_node` at or
    after that metric's own start_us, paired with its own elapsed time since then. Needs only each
    metric's own start_us and window_end_us, not any other metric, so this still works even for a
    window where most other metrics don't apply."""
    breakdowns = {}
    per_instance_metrics = [m for m in metrics if m.per_instance and m.start_us is not None]
    if not per_instance_metrics:
        return breakdowns

    # Only the occurrences that belong to this window: on window_node specifically (not some other
    # node's own unrelated occurrences, since a boundary query not pinned to one node can return
    # several), and not a stale one still inside VictoriaMetrics' lookback window from an earlier run.
    samples = query_boundary_samples(victoria_url, suite_boundary, self_node, at_time_us=window_end_us)
    samples = [(iid, us) for iid, node, us in samples if node == window_node]

    for m in per_instance_metrics:
        breakdowns[m.label] = sorted(
            ((iid, (us - m.start_us) / 1_000_000) for iid, us in samples if us >= m.start_us),
            key=lambda pair: pair[1],
        )

    return breakdowns


def advance_not_before_us(victoria_url, self_node, window_node, window_end_us, metrics_config):
    """The exclusion boundary to hand the next window - normally just window_end_us, except an
    end_is_suite_boundary metric's own start_event can log a second, trailing occurrence strictly
    after window_end_us (see BOUNDARY_METRIC_LOOKAHEAD_US), which would otherwise leak into the next
    window's own lookup for that same metric if that window never produces a fresh occurrence of its
    own. Called once, right after a window resolves, to fold every such trailing occurrence (if any)
    into the boundary before it's used again - the *latest* of each end_is_suite_boundary metric's
    own earliest-trailing-occurrence (see BOUNDARY_METRIC_LOOKAHEAD_US for why earliest, not latest,
    within each metric's own lookahead), since excluding up to the latest of them safely excludes
    every earlier one too."""
    candidates = [window_end_us]
    for entry in metrics_config:
        if not entry.get("end_is_suite_boundary"):
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
    in Grafana's "Benchmark Results" table. Each metric is published with its own already-resolved
    `node` (see resolve_window()) and its own start_source as "source"; each per-instance breakdown
    value (if any) with that occurrence's own id as "Instance: <id>"."""
    for m in metrics:
        value = results.get(m.label)
        if value is not None:
            push_result(victoria_url, m.node, m.start_source, metric_name(m.label), value)

    for label, breakdown in breakdowns.items():
        metric = next(m for m in metrics if m.label == label)
        for instance_id, duration_s in breakdown:
            push_result(victoria_url, metric.node, f"Instance: {instance_id}", metric_name(label), duration_s)


def seed_last_end_us(victoria_url, suite_boundary, self_node, metrics_config):
    """The boundary this script starts watching from - seeded with whatever suite_boundary occurrence
    is already the latest right now, not None: unlike report_timing.py (a script a human starts
    *before* triggering a deployment, so nothing was "current" yet when it started), this script can
    start at any point in its own life - after a crash, a restart, or an upgrade - with an arbitrary,
    possibly-stale window already sitting in VictoriaMetrics from whenever it last stopped. Starting
    from None would let wait_for_new_window() immediately treat that pre-existing window as brand
    "new" and resolve_window() would then run with no previous-window boundary at all
    (not_before_us=None), free to pull in "the latest occurrence of X" for every checkpoint regardless
    of which past window it actually belongs to - confirmed empirically: a plain restart re-published
    a fabricated window built from two different, unrelated past runs' checkpoints. Seeding here
    instead means only a window whose own boundary happens *after* this script started watching is
    ever resolved - anything already sitting in VictoriaMetrics from before that is silently skipped
    rather than risking a wrong result for it.

    Also run through advance_not_before_us() before being returned, same as after every window this
    script resolves - otherwise this seed has the exact same gap advance_not_before_us() exists to
    close, just at startup instead of between windows - confirmed empirically: a restart shortly
    after a window produced a bogus, wildly inflated value this way, using the previous window's own
    leftover trailing occurrence as the new window's own start.

    Retries indefinitely (every POLL_INTERVAL_SECONDS) on a VictoriaMetricsError, rather than letting
    it propagate out of main() before its own retry loop even starts (which would end publication
    for the rest of this script's lifetime, since nothing else would catch it): a systemd unit
    ordering only orders VictoriaMetrics' own unit *start*, not its HTTP endpoint actually being
    ready to answer, so this script's very first request can legitimately fail even on a normal boot.
    """
    while True:
        try:
            found = _latest_boundary_sample(victoria_url, suite_boundary, self_node, None)
            if found is None:
                return None
            seed_end_us, seed_node = found
            return advance_not_before_us(victoria_url, self_node, seed_node, seed_end_us, metrics_config)
        except VictoriaMetricsError as err:
            print(f"benchmark-results-publisher: error seeding baseline: {err}", file=sys.stderr)
            time.sleep(POLL_INTERVAL_SECONDS)


def main():
    """Parse arguments, load config, then watch VictoriaMetrics for new windows forever, resolving
    and publishing each one's aggregated metrics - unlike report_timing.py's own --publish flag,
    publishing here is not optional, since the whole point of this script existing is that nobody has
    to remember to run it, let alone pass a flag to it.

    `last_end_us` only advances *after* publish_results() succeeds, not right after resolve_window()
    returns: a VictoriaMetricsError raised anywhere in either call aborts this attempt entirely
    (caught below) without having moved the boundary, so the exact same window is retried next time
    around rather than being silently marked "done" despite a failed - or, for a push failure partway
    through publish_results(), partial - write. A retry after a partial publish failure re-pushes
    every metric from scratch, including whichever already succeeded before the failure - accepted
    here as a rare, cosmetic duplicate-sample risk (each push is its own timestamped point, not an
    overwrite) rather than building a persisted per-window publish log just to avoid it.

    Errors are caught and retried rather than propagated, since one bad window - including a
    VictoriaMetricsError from any query or push above, deliberately not swallowed at the source -
    shouldn't end publication for the rest of this script's lifetime."""
    args = parse_args()
    suite_boundary, metrics_config = load_config(args.config)

    print(f"benchmark-results-publisher: watching {args.victoria_url} for new windows")

    window_number = 0
    last_end_us = seed_last_end_us(args.victoria_url, suite_boundary, args.node, metrics_config)

    while True:
        try:
            window_end_us, window_node = wait_for_new_window(
                args.victoria_url, suite_boundary, args.node, last_end_us
            )

            window_number += 1

            results, metrics = resolve_window(
                args.victoria_url, window_node, args.node, last_end_us, window_end_us, metrics_config
            )
            breakdowns = resolve_per_instance_breakdowns(
                args.victoria_url, suite_boundary, args.node, window_node, window_end_us, metrics
            )
            publish_results(args.victoria_url, metrics, results, breakdowns)
            last_end_us = advance_not_before_us(
                args.victoria_url, args.node, window_node, window_end_us, metrics_config
            )

            node_note = "" if window_node == args.node else f" on node {window_node!r}"
            parts = [f"{label}={value:.3f}s" for label, value in results.items()]
            summary = ", ".join(parts) if parts else "no metrics resolved"
            print(f"benchmark-results-publisher: window {window_number} published{node_note}: {summary}")
        except Exception as err:  # noqa: BLE001 - keep this script alive across any single failure
            print(f"benchmark-results-publisher: error resolving window: {err}", file=sys.stderr)
            time.sleep(ERROR_RETRY_SECONDS)


if __name__ == "__main__":
    main()

"""Which B-Fabric resource each uploaded file became, so storage can be confirmed later.

A completed tus transfer is not confirmed storage. The storage service runs its checks -- virus
scan, checksum verification, disk state -- in a post-finish hook *after* the transfer is already
complete, and that hook reports to B-Fabric rather than to the uploading client, so it cannot fail
the transfer that produced it. A file bfabricpy reports in ``summary.uploads`` can therefore end up
with its resource marked ``failed``, holding no usable bytes.

That matters because BioBeamer deletes source files once they are old enough and recorded as
copied. Deleting on the strength of a completed transfer alone risks removing the only copy of data
B-Fabric rejected. So the resource id of every uploaded file is recorded here, and consulted at
deletion time -- which is the moment the answer matters, since verification runs on the server's
schedule rather than ours.

The registry is a cache of facts recoverable from B-Fabric, never a source of truth: a missing or
unreadable entry makes a file unverifiable, which blocks deletion rather than causing it.
"""

import json
import os
import time

REGISTRY_FILENAME = "tus_resources.json"

_FORMAT_VERSION = 1

# B-Fabric's terminal statuses. Only "available" means the bytes are stored and verified; the rest
# are decided-and-not-stored. "pending" is absent on purpose: it is not terminal, so it means the
# storage service has not ruled yet and the answer is simply not known.
STATUS_AVAILABLE = "available"
TERMINAL_FAILURE_STATUSES = frozenset({"failed", "invalid", "deleted", "expired"})


def registry_path(parameters):
    """Where the registry lives: alongside the copied-files ledger, in the log directory.

    Returns ``None`` when neither is configured, rather than falling back to the working directory --
    a registry written next to whatever the process happened to be started from would follow the
    caller around and, worse, be picked up by an unrelated run.
    """
    log_dir = parameters.get("log_dir")
    if log_dir:
        return os.path.join(log_dir, REGISTRY_FILENAME)
    ledger = parameters.get("copied_files_log")
    ledger_dir = os.path.dirname(ledger) if ledger else ""
    if ledger_dir:
        return os.path.join(ledger_dir, REGISTRY_FILENAME)
    return None


def read_registry(path, logger=None):
    """``{source_path: {"resource_id": int, ...}}``, or ``{}`` if there is nothing usable.

    Never raises: an unreadable (or unconfigured) registry leaves files unverifiable, which is the
    safe direction -- unverifiable means "do not delete", never "assume stored".
    """
    if path is None:
        return {}
    try:
        with open(path) as handle:
            raw = json.load(handle)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        if logger:
            logger.warning(
                "Could not read the tus resource registry at {0}: {1}".format(path, error)
            )
        return {}
    if not isinstance(raw, dict) or raw.get("version") != _FORMAT_VERSION:
        return {}
    entries = raw.get("entries")
    return entries if isinstance(entries, dict) else {}


def write_registry(path, entries, logger=None):
    """Atomically replace the registry, so a crash mid-write cannot truncate it."""
    if path is None:
        return
    payload = {"version": _FORMAT_VERSION, "entries": entries}
    tmp = "{0}.{1}.tmp".format(path, os.getpid())
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(tmp, "w") as handle:
            json.dump(payload, handle)
        os.replace(tmp, path)
    except OSError as error:
        if logger:
            logger.warning(
                "Could not write the tus resource registry at {0}: {1}".format(path, error)
            )
        try:
            os.unlink(tmp)
        except OSError:
            pass


def record_uploads(path, records, logger=None):
    """Add ``{source_path: resource_id}`` to the registry, keeping existing entries."""
    if not records or path is None:
        return
    entries = read_registry(path, logger)
    now = time.time()
    for source, resource_id in records.items():
        entries[os.path.normpath(source)] = {
            "resource_id": resource_id,
            "recorded_at": now,
        }
    write_registry(path, entries, logger)


def forget(path, sources, logger=None):
    """Drop ``sources`` from the registry, e.g. once their files are gone or being re-uploaded."""
    if not sources or path is None:
        return
    entries = read_registry(path, logger)
    removed = False
    for source in sources:
        if entries.pop(os.path.normpath(source), None) is not None:
            removed = True
    if removed:
        write_registry(path, entries, logger)


def resource_statuses(client, resource_ids, logger=None):
    """``{resource_id: status}`` for ``resource_ids``, in one batched read; absent ids are omitted."""
    if not resource_ids:
        return {}
    try:
        result = client.read("resource", {"id": sorted(set(resource_ids))}, max_results=None)
    except Exception as error:
        if logger:
            logger.warning(
                "Could not read resource statuses from B-Fabric: {0}".format(error)
            )
        return {}
    statuses = {}
    for entry in result:
        entry_id, status = entry.get("id"), entry.get("status")
        if isinstance(entry_id, int) and isinstance(status, str):
            statuses[entry_id] = status.lower()
    return statuses


def classify(sources, path, client, logger=None):
    """Split ``sources`` by what B-Fabric says about the resource each became.

    :returns: ``(stored, rejected, unknown)`` --

        * ``stored``: resource is ``available``; the bytes are verified and the source may be deleted
        * ``rejected``: resource reached a terminal non-available status, so the upload must be
          retried; its ledger entry has to go
        * ``unknown``: no registry entry, or the status could not be read, or it is still ``pending``
          because the storage service has not ruled yet. Not deletable, not re-uploaded -- simply
          not yet decided.
    """
    entries = read_registry(path, logger)
    by_resource = {}
    unknown = []
    for source in sources:
        entry = entries.get(os.path.normpath(source))
        resource_id = entry.get("resource_id") if isinstance(entry, dict) else None
        if isinstance(resource_id, int):
            by_resource.setdefault(resource_id, []).append(source)
        else:
            unknown.append(source)

    statuses = resource_statuses(client, list(by_resource), logger)
    stored, rejected = [], []
    for resource_id, group in by_resource.items():
        status = statuses.get(resource_id)
        if status == STATUS_AVAILABLE:
            stored.extend(group)
        elif status in TERMINAL_FAILURE_STATUSES:
            rejected.extend(group)
        else:
            # Still pending, or the read did not account for it: no verdict yet.
            unknown.extend(group)
    return stored, rejected, unknown

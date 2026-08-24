"""TUS (tus.io resumable upload) transfer backend, uploading into B-Fabric via bfabricpy.

Selected with ``tool="tus"`` in the host config. Unlike robocopy/scp/sftp this needs nothing
mounted -- it speaks plain HTTP(S) to a tus endpoint -- and it registers the data in B-Fabric as
it goes: one workunit per acquisition folder, with a resource per file.

The heavy lifting belongs to bfabricpy (``bfabric.operations.workunit.upload_files``), which does
checksumming, duplicate detection, workunit/resource creation, token minting and the resumable
transfer itself. This module only does the BioBeamer-side work: deciding which B-Fabric container
a file belongs to, grouping files into workunits, and translating the result back into the
return contract the rest of BioBeamer expects.

Requires the ``tus`` extra (``pip install -e ".[tus]"``); bfabric is imported lazily so that
robocopy/scp/sftp hosts never need it installed.
"""

import os
import re
import sys
import time

from biobeamer.tusregistry import record_uploads, registry_path

# Accepted container path formats. This is an operational contract, not an implementation
# detail: instrument folders MUST carry the container in the path, because there is no fallback
# (guessing would file data under the wrong project, which is worse than a failed run).
# Keep this list, README.md and CONTAINER_FORMAT_HELP in sync.
DEFAULT_CONTAINER_PATTERN = r"[/\\\\](?:p|C)([0-9]+)(?=[/\\\\])"

CONTAINER_FORMAT_HELP = (
    "the path must contain a container segment: either 'p<digits>' (project, e.g. "
    "'/Data2San/p1234/...') or 'C<digits>' (order, e.g. '/Data2San/C1234/...')"
)


class TusUploadError(RuntimeError):
    """A TUS upload could not be performed. Raised for config and container-resolution errors."""


class TusUploadFailed(TusUploadError):
    """Some acquisition groups failed, but others succeeded.

    Carries the files that did upload so the caller can still record them in the copied-files
    ledger before failing the run.
    """

    def __init__(self, message, files_copied=None):
        super().__init__(message)
        self.files_copied = files_copied or []


class _BfabricClientManager:
    """Lazily builds and caches one B-Fabric client for the whole run.

    Mirrors ``sftpparamiko._sftp_manager``: a module-level singleton so a run that uploads ten
    acquisition folders authenticates once instead of ten times.
    """

    def __init__(self):
        self._client = None

    def get_client(self, parameters, logger):
        if self._client is not None:
            return self._client

        # Imported here, not at module scope, so hosts on other tools never need the extra.
        try:
            from bfabric import Bfabric
            from bfabric.transfer import check_upload_scope, require_tus
        except ImportError as e:
            # On Python < 3.11 the tus extra installs nothing (bfabric itself requires 3.11+,
            # and the marker in pyproject.toml keeps BioBeamer installable on older instrument
            # PCs). Say so explicitly, otherwise the advice below is to re-run a command that
            # silently succeeded while installing nothing.
            detail = (
                'Install BioBeamer with: pip install -e ".[tus]"'
                if sys.version_info >= (3, 11)
                else "this host runs Python {0}.{1}, but bfabric requires 3.11+; "
                'tool="tus" is not available here (use robocopy/scp/sftp, or upgrade '
                "Python)".format(*sys.version_info[:2])
            )
            raise TusUploadError(
                'tool="tus" requires the bfabric transfer extra. ' + detail
            ) from e

        # Fail before any workunit exists if the mover is missing, so a missing dependency can
        # never leave an orphaned 'failed' workunit behind in B-Fabric.
        require_tus()

        base_url = parameters.get("bfabric_base_url") or os.environ.get("BFABRIC_BASE_URL")
        client_id = parameters.get("bfabric_client_id") or os.environ.get("BFABRIC_CLIENT_ID")
        # Never accepted from the config XML or argv -- the XML is world-readable on the
        # instrument and argv leaks via /proc and the launcher's own INFO log.
        client_secret = os.environ.get("BFABRIC_CLIENT_SECRET")
        scope = (
            parameters.get("bfabric_scope")
            or os.environ.get("BFABRIC_SCOPE")
            or "api:read api:write tus"
        )

        missing = [
            name
            for name, value in (
                ("bfabric_base_url / BFABRIC_BASE_URL", base_url),
                ("bfabric_client_id / BFABRIC_CLIENT_ID", client_id),
                ("BFABRIC_CLIENT_SECRET (environment only)", client_secret),
            )
            if not value
        ]
        if missing:
            raise TusUploadError(
                'tool="tus" needs B-Fabric OAuth credentials; missing: ' + ", ".join(missing)
            )

        if "tus" not in scope.split():
            raise TusUploadError(
                "the B-Fabric OAuth scope must include 'tus' (got '{0}'); "
                "the default scope does not grant it".format(scope)
            )

        logger.info(
            "Connecting to B-Fabric at {0} as client '{1}' (scope: {2})".format(
                base_url, client_id, scope
            )
        )
        client = Bfabric.connect_oauth(
            client_id=client_id,
            client_secret=client_secret,
            base_url=base_url,
            scope=scope,
        )
        # Fail fast on a scope-less token, again before anything is created.
        check_upload_scope(client)
        self._client = client
        return client

    def reset(self):
        self._client = None


_client_manager = _BfabricClientManager()


def get_client(parameters, logger):
    """The shared B-Fabric client for this run, built on first use.

    Exposed for the storage-verification path in ``cli``, which needs to read resource statuses
    without going through an upload.
    """
    return _client_manager.get_client(parameters, logger)


def resolve_container_id(path, parameters, logger):
    """Return the B-Fabric container id encoded in ``path``.

    There is deliberately **no fallback**: a wrong container files data under the wrong project,
    which is worse than a failed run. An unmatchable path is a hard error naming both the path
    and the accepted formats, because that message is what instrument staff act on.

    :raises TusUploadError: if no container segment can be found.
    """
    pattern = parameters.get("tus_container_pattern") or DEFAULT_CONTAINER_PATTERN
    try:
        regex = re.compile(pattern)
    except re.error as e:
        raise TusUploadError(
            "tus_container_pattern '{0}' is not a valid regex: {1}".format(pattern, e)
        ) from e

    match = regex.search(str(path).replace("\\", "/"))
    if not match:
        msg = "could not determine B-Fabric container for '{0}': {1}".format(
            path, CONTAINER_FORMAT_HELP
        )
        logger.error(msg)
        raise TusUploadError(msg)

    # Group 1 when the pattern captures (the documented shape), else the whole match.
    raw = match.group(1) if match.groups() else match.group(0)
    digits = re.sub(r"^[pC]", "", str(raw).strip("/\\"))
    try:
        return int(digits)
    except ValueError:
        msg = "container id '{0}' extracted from '{1}' is not numeric: {2}".format(
            raw, path, CONTAINER_FORMAT_HELP
        )
        logger.error(msg)
        raise TusUploadError(msg)


def group_files_by_folder(files, source_path):
    """Group source files into one bucket per acquisition, preserving input order.

    One acquisition == one workunit. Instruments that write a *directory* per acquisition
    (Bruker ``.d``, Waters ``.PRO``) must collapse to a single bucket, so the whole bundle
    becomes one workunit rather than one workunit per internal file.

    :return: ``{group_key: [file, ...]}`` where ``group_key`` is relative to ``source_path``.
    """
    groups = {}
    for file_path in files:
        try:
            rel = os.path.relpath(file_path, source_path)
        except ValueError:
            # Different drive on Windows; fall back to the absolute path.
            rel = str(file_path)
        rel_posix = rel.replace("\\", "/")

        parts = rel_posix.split("/")
        key_parts = None
        for idx, part in enumerate(parts):
            # A bundle directory owns everything beneath it.
            if part.lower().endswith((".d", ".pro", ".raw")) and idx < len(parts) - 1:
                key_parts = parts[: idx + 1]
                break
        if key_parts is None:
            # Otherwise group by the containing directory; files sitting directly in
            # source_path share the "" bucket.
            key_parts = parts[:-1]

        groups.setdefault("/".join(key_parts), []).append(file_path)
    return groups


def _bundle_root(group_key, files, parameters):
    """The bundle directory to upload as one entry, or ``None`` for ordinary files.

    Only returned when the group really is a bundle directory that exists on disk and holds
    every file in the group -- otherwise the individual files are uploaded instead.
    """
    if not group_key:
        return None
    basename = os.path.basename(group_key.rstrip("/"))
    if not basename.lower().endswith((".d", ".pro")):
        return None
    source_path = parameters.get("source_path") or ""
    root = os.path.join(source_path, *group_key.split("/"))
    if not os.path.isdir(root):
        return None
    # Uploading the directory sends everything under it, so only do so when the group already
    # covers the whole directory; a partially-filtered bundle must go file by file.
    on_disk = set()
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            on_disk.add(os.path.normpath(os.path.join(dirpath, name)))
    if on_disk != {os.path.normpath(f) for f in files}:
        return None
    return root


def _workunit_name(group_key, parameters):
    """Human-facing workunit name: the acquisition folder, or the instrument for loose files."""
    if group_key:
        return os.path.basename(group_key.rstrip("/")) or group_key
    return parameters.get("instrument") or "BioBeamer upload"


def _log_banner(tool_log_file, lines):
    """Append to the per-tool log, matching the convention of copy_with_scp."""
    if not tool_log_file:
        return
    try:
        with open(tool_log_file, "a") as logf:
            logf.write(
                "--- Running TUS upload at {0} ---\n".format(
                    time.strftime("%Y-%m-%d %H:%M:%S")
                )
            )
            for line in lines:
                logf.write("{0}\n".format(line))
            logf.flush()
    except OSError as e:
        # The tool log is diagnostic only; never fail an upload because it is unwritable.
        pass


def upload_folder_with_tus(
    group_key, files, parameters, logger, tool_log_file, simulate_copy=False
):
    """Upload one acquisition folder as a single B-Fabric workunit.

    :return: the source paths that are now safely stored in B-Fabric -- both freshly uploaded
        files and files the server registered as links to already-stored bytes. Failures are
        excluded so BioBeamer retries them on the next run.
    """
    container_id = resolve_container_id(files[0], parameters, logger)
    application_id = parameters.get("application_id")
    if not application_id:
        raise TusUploadError(
            'tool="tus" needs <b-fabric><applicationID> in the host config '
            "(the B-Fabric application is the uploading instrument)"
        )

    endpoint = parameters.get("tus_endpoint")
    workunit_name = _workunit_name(group_key, parameters)
    on_duplicate = parameters.get("tus_on_duplicate") or "upload"
    track_job = bool(parameters.get("tus_track_job"))

    if simulate_copy:
        logger.info(
            "Simulating Command: tus upload of {n} file(s) from '{group}' to {endpoint} "
            "[container={container}, application={app}, workunit='{wu}', "
            "on_duplicate={dup}, track_job={job}]".format(
                n=len(files),
                group=group_key or ".",
                endpoint=endpoint,
                container=container_id,
                app=application_id,
                wu=workunit_name,
                dup=on_duplicate,
                job=track_job,
            )
        )
        return []

    from bfabric.operations.workunit import (
        UploadFileParam,
        UploadFilesParams,
        upload_files,
    )

    client = _client_manager.get_client(parameters, logger)

    logger.info(
        "TUS upload: {n} file(s) from '{group}' -> container {container}, "
        "application {app}, workunit '{wu}'".format(
            n=len(files),
            group=group_key or ".",
            container=container_id,
            app=application_id,
            wu=workunit_name,
        )
    )

    # A bundle acquisition (Bruker .d, Waters .PRO) is uploaded as the DIRECTORY, not as a
    # list of its files: bfabricpy then names each resource relative to that directory, which
    # both preserves the internal structure and avoids basename collisions between
    # subdirectories. Everything else is uploaded as individual files (named by basename).
    upload_root = _bundle_root(group_key, files, parameters)
    entries = [upload_root] if upload_root else files

    params = UploadFilesParams(
        files=[UploadFileParam(path=f, on_duplicate=on_duplicate) for f in entries],
        container_id=container_id,
        application_id=application_id,
        workunit_name=workunit_name,
        track_job=track_job,
    )
    summary = upload_files(
        client,
        params,
        on_file_done=lambda name, ok: logger.debug(
            "TUS {0}: {1}".format("ok" if ok else "FAILED", name)
        ),
    )

    # A link means the resource exists and points at already-stored bytes, so the file is done
    # even though nothing moved. Skips are duplicates with no resource created -- also done.
    # Only failures must be retried, so only they are withheld from the copied ledger.
    done_names = {u.filename for u in summary.uploads}
    done_names |= {u.filename for u in summary.links}
    done_names |= {s.filename for s in summary.skips}
    failed_names = {f.filename for f in summary.failures}

    copied = [
        f
        for f in files
        if _resource_name(f, upload_root) in done_names
        and _resource_name(f, upload_root) not in failed_names
    ]

    # Record which resource each transferred file became. A completed transfer is not confirmed
    # storage -- the storage service's post-finish checks run afterwards and report to B-Fabric, not
    # to us -- so deletion later has to re-read these statuses instead of trusting the ledger.
    resource_by_name = {u.filename: u.resource_id for u in summary.uploads}
    resource_by_name.update({u.filename: u.resource_id for u in summary.links})
    record_uploads(
        registry_path(parameters),
        {
            f: resource_by_name[_resource_name(f, upload_root)]
            for f in files
            if _resource_name(f, upload_root) in resource_by_name
        },
        logger,
    )

    for failure in summary.failures:
        logger.error(
            "TUS upload failed for {0} (resource {1}): {2}".format(
                failure.filename, failure.resource_id, failure.error
            )
        )

    _log_banner(
        tool_log_file,
        [
            "endpoint      : {0}".format(endpoint),
            "container     : {0}".format(container_id),
            "application   : {0}".format(application_id),
            "workunit      : {0} (id={1})".format(workunit_name, summary.workunit_id),
            "job           : {0}".format(summary.job_id),
            "group         : {0}".format(group_key or "."),
            "uploaded      : {0}".format(len(summary.uploads)),
            "linked        : {0}".format(len(summary.links)),
            "skipped       : {0}".format(len(summary.skips)),
            "failed        : {0}".format(len(summary.failures)),
        ],
    )

    logger.info(
        "TUS upload done: workunit {wu}, {up} uploaded, {li} linked, {sk} skipped, "
        "{fa} failed".format(
            wu=summary.workunit_id,
            up=len(summary.uploads),
            li=len(summary.links),
            sk=len(summary.skips),
            fa=len(summary.failures),
        )
    )
    return copied


def _resource_name(file_path, upload_root):
    """The resource name bfabricpy will report for ``file_path``.

    Mirrors ``bfabric.transfer._generic.checksums.compute_file_info``: an entry uploaded as a
    directory names its files relative to that directory ("subdir/file.txt"), while an entry
    uploaded as a plain file keeps only its basename.
    """
    if upload_root:
        try:
            return os.path.relpath(file_path, upload_root).replace("\\", "/")
        except ValueError:
            pass
    return os.path.basename(str(file_path))


def upload_files_with_tus(
    source_results, parameters, logger, tool_log_file, simulate_copy=False
):
    """Upload every file in ``source_results``, one workunit per acquisition folder.

    This is the batch entry point ``cli.copy_files_with_tool`` delegates to. It exists because
    ``upload_files`` is inherently batch (one call creates one workunit), so routing TUS through
    the per-file copy loop would create one workunit per file.

    :param source_results: the ``{source: target}`` mapping the copy pipeline builds. Only the
        keys are used -- a tus resource is named by its path relative to ``source_path``, so the
        computed local target paths are irrelevant here.
    :return: the source paths now stored in B-Fabric.
    """
    if not parameters.get("tus_endpoint"):
        raise TusUploadError('tool="tus" requires the tus_endpoint attribute in the host config')

    sources = sorted(source_results.keys())
    groups = group_files_by_folder(sources, parameters.get("source_path") or "")
    logger.info(
        "TUS: {0} file(s) in {1} acquisition group(s)".format(len(sources), len(groups))
    )

    files_copied = []
    failed_groups = []
    for group_key in sorted(groups):
        try:
            files_copied.extend(
                upload_folder_with_tus(
                    group_key,
                    groups[group_key],
                    parameters,
                    logger,
                    tool_log_file,
                    simulate_copy=simulate_copy,
                )
            )
        except Exception as e:
            # One bad acquisition folder must not abandon the others; the run still fails
            # overall via the caller's exit-code handling.
            logger.error(
                "TUS upload of group '{0}' failed: {1}".format(group_key or ".", e),
                exc_info=True,
            )
            failed_groups.append(group_key)

    if failed_groups and not simulate_copy:
        # Raise TusUploadFailed rather than TusUploadError so the caller can still record the
        # groups that DID succeed: discarding them would make the next run re-upload files
        # already stored in B-Fabric (with the default on_duplicate="upload", that means
        # re-sending the bytes, not a cheap dedup).
        raise TusUploadFailed(
            "TUS upload failed for {0} of {1} group(s): {2}".format(
                len(failed_groups), len(groups), ", ".join(g or "." for g in failed_groups)
            ),
            files_copied=files_copied,
        )
    return files_copied


def compare_files_destination_tus(source_result_mapping, logger):
    """Report nothing as already-at-destination, deferring to B-Fabric's own duplicate check.

    Satisfies the contract of ``cli.remove_files_already_at_destination``. Deduplication is
    left to bfabricpy's server-side MD5 ``check-duplicates`` (driven by ``tus_on_duplicate``),
    which is container-wide and authoritative; a local reimplementation could only be wrong.
    The ``copied_files_log`` ledger still stops known files being re-examined.
    """
    logger.debug(
        "TUS: deferring duplicate detection to B-Fabric for {0} file(s)".format(
            len(source_result_mapping)
        )
    )
    return {"copied": {}, "not_copied": dict(source_result_mapping)}

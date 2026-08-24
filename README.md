# BioBeamer - Instrument Data Collection System

[![Project Stats](https://www.openhub.net/p/BioBeamer/widgets/project_thin_badge.gif)](https://www.openhub.net/p/BioBeamer)

BioBeamer is a Python-based data collection system for scientific instruments. It automatically synchronizes instrument data files from source locations to target destinations using various transfer protocols (robocopy, scp, sftp).

## Features

- **Multiple transfer protocols**: robocopy, scp, sftp (with paramiko support), and
  tus (resumable HTTP upload straight into B-Fabric -- nothing needs to be mounted,
  and the workunit is created at upload time)
- **XML-based configuration**: Flexible host and instrument configuration
- **File filtering**: Pattern-based file selection and filtering
- **Monitoring**: Comprehensive logging and syslog integration
- **Simulation mode**: Test configurations without actual file transfers
- **Cross-platform**: Works on Windows and Unix-like systems

## Requirements

- Python 3.9+
- For SFTP support: `paramiko` library
- For scp/robocopy: respective system tools installed
- For tus support: **Python 3.11+** and the `tus` extra (`pip install -e ".[tus]"`),
  which pulls in `bfabric[transfer]>=1.21.0`. Kept optional on purpose: bfabric is a
  large dependency tree and requires 3.11+, while BioBeamer must stay installable on
  the older instrument PCs. On Python < 3.11 the extra resolves to nothing and
  `tool="tus"` fails at startup with a message saying so -- those hosts keep using
  robocopy/scp/sftp.

  1.21.0 is a hard floor, not a preference: 1.20.0 had an incompatible
  `upload_files` signature (files passed positionally plus a `force` boolean) and no
  `on_duplicate="link"`.

## Installation

### Using pip (recommended)

```bash
pip install biobeamer
```

### From source

```bash
git clone https://github.com/fgcz/BioBeamer.git
cd BioBeamer
pip install -e .
```

### Development installation

```bash
git clone https://github.com/fgcz/BioBeamer.git
cd BioBeamer
pip install -e ".[development]"
```

## Usage

### Command Line

```bash
# Basic usage
biobeamer --xml config.xml --hostname myhost

# With password for authentication
biobeamer --xml config.xml --hostname myhost --password mypassword

# Simulate mode (no actual file transfers)
biobeamer --xml config.xml --hostname myhost --simulate
```

### Configuration

BioBeamer uses XML configuration files to define hosts, instruments, and transfer settings.

#### Example Configuration

```xml
<?xml-stylesheet type="text/xsl" href="BioBeamer.xsl"?>
<BioBeamerHosts>
<host name="instrument-pc" 
    instrument="ORBITRAP_1"
    min_size="1024" 
    min_time_diff="10800" 
    max_time_diff="2419200" 
    max_time_delete="1209600"
    time_out="3600"
    simulate_copy="false"
    simulate_delete="false" 
    func_target_mapping="" 
    tool="scp"
    pattern="^.{0,2}p[0-9]+.[MP][-0-9a-zA-Z_\\/\\.]+\\.(raw|RAW|wiff|wiff\\.scan)$"
    source_path="/data/instrument/" 
    target_path="user@server:/storage/data/"
    copied_files_log="./log/copied_files.txt"
    syshandler_adress="log-server.domain.com"
    syshandler_port="514">
</host>
</BioBeamerHosts>
```

#### Configuration Parameters

- **`tool`**: Transfer protocol (`robocopy`, `scp`, `sftp`, `tus`)
- **`pattern`**: Regex pattern for file filtering
- **`min_size`**: Minimum file size in bytes
- **`min_time_diff`**: Minimum file age in seconds before transfer
- **`max_time_diff`**: Maximum file age for transfer
- **`simulate_copy`**: Test mode without actual transfers
- **`source_path`**: Source directory path
- **`target_path`**: Destination path (can include user@host: for remote). Not used by
  `tool="tus"`, which uploads to `tus_endpoint` instead.

##### TUS parameters (`tool="tus"` only)

- **`tus_endpoint`**: tus server URL, e.g. `http://localhost:1337/files` (required)
- **`tus_container_pattern`**: regex whose first group yields the B-Fabric container id.
  Defaults to matching a `p<digits>` or `C<digits>` path segment.
- **`tus_track_job`**: `true`/`false`. Creates an `UPLOAD` job under the workunit whose
  status the tus server's hooks maintain.
- **`tus_on_duplicate`**: what to do when the container already stores identical bytes --
  `upload` (default, send anyway), `skip` (leave out of the workunit), or `link`
  (register a resource pointing at the existing bytes without transferring).
- **`<b-fabric><applicationID>`**: required. The B-Fabric application is the uploading
  instrument.

The B-Fabric container is **not** configured per host: it is read from each file's path,
because one instrument writes data for many projects. The OAuth credentials come from the
launcher (`bfabric_base_url`, `bfabric_client_id`, `bfabric_scope` in `launcher.ini`) with
the client secret supplied through the `BFABRIC_CLIENT_SECRET` environment variable -- never
as a command-line argument, so it cannot leak into logs or the process list. The scope must
include `tus`; B-Fabric's default scope does not grant it.

##### Legal source path formats for `tool="tus"`

**This is an operational contract, not a convention.** There is deliberately no fallback
container: filing data under the wrong project is worse than a failed run, so a path with no
recognisable container is a hard error and nothing is uploaded. Instrument folders must
therefore always carry the container in the path:

| Format | Example | Container |
|---|---|---|
| `p<digits>` (project) | `D:/Data2San/p1234/Proteomics/EXPLORIS_1/run_A/f.raw` | 1234 |
| `C<digits>` (order) | `D:/Data2San/C4321/Proteomics/QDA_1/f.raw` | 4321 |

Anything else fails with:

```
could not determine B-Fabric container for '<path>': the path must contain a container
segment: either 'p<digits>' (project, e.g. '/Data2San/p1234/...') or 'C<digits>' (order,
e.g. '/Data2San/C1234/...')
```

If an instrument writes a different layout, set `tus_container_pattern` for that host rather
than renaming folders by hand.

##### Storage is confirmed before a source file is deleted

A completed tus transfer is **not** confirmed storage. The storage service runs its virus scan,
checksum verification and disk checks in a *post-finish* hook, after the transfer is already
complete, and that hook reports to B-Fabric rather than to BioBeamer -- it cannot fail the transfer
that produced it. So a file BioBeamer recorded as copied can still end up with its resource marked
`failed`, holding no usable bytes.

Because `max_time_delete` eventually deletes source files, trusting the copied-files ledger alone
would risk destroying the only copy of data B-Fabric rejected. For `tool="tus"` BioBeamer therefore:

- records which resource each uploaded file became, in `tus_resources.json` beside the ledger
- re-reads those statuses at **deletion** time and deletes only what B-Fabric reports `available`;
  anything still `pending`, unreadable, or unaccounted for is kept
- drops rejected files from the ledger on the next run, so they are uploaded again instead of being
  skipped for ever

Deletion is gated at the moment the decision is made, not just after upload, because verification
runs on the server's schedule: a resource can still be `pending` when the upload returns.

##### One workunit per acquisition

Files are grouped by acquisition folder, and each group becomes one B-Fabric workunit named
after the folder. Instruments that write a *directory* per acquisition (Bruker `.d`, Waters
`.PRO`) are uploaded as a single directory entry, so the bundle stays one workunit with its
internal structure preserved as resource names.

#### XML Validation

Validate your configuration file:

```bash
xmllint --noout --schema src/biobeamer/configs/BioBeamer2.xsd your-config.xml
```

or with xmlstarlet:

```bash
xmlstarlet val --xsd src/biobeamer/configs/BioBeamer2.xsd your-config.xml
```

## Development

### Running Tests

```bash
# Install development dependencies
pip install -e ".[development]"

# Run all tests
pytest

# Run with coverage
pytest --cov=biobeamer

# Run specific test file
pytest tests/test_copy_with_scp.py
```

### Project Structure

```
BioBeamer/
├── src/biobeamer/           # Main package
│   ├── __init__.py
│   ├── __main__.py         # Entry point for python -m biobeamer
│   ├── cli.py              # Command line interface and main logic
│   ├── parser.py           # XML configuration parser
│   ├── logger.py           # Logging utilities
│   ├── mapping.py          # File path mapping functions
│   ├── networks.py         # Network and drive utilities
│   ├── sftpparamiko.py     # SFTP implementation using paramiko
│   └── configs/            # Configuration files and schemas
│       ├── BioBeamer2.xml
│       ├── BioBeamer2.xsd
│       └── ...
├── tests/                  # Test suite
├── pyproject.toml         # Project configuration
└── README.md
```

## Deployment

### System Integration

For production deployment, consider:

1. **Syslog Configuration** (`/etc/rsyslog.conf`):
```
$template tplremote,"%timegenerated% %HOSTNAME% %fromhost-ip% %syslogtag%%msg:::drop-last-lf%\n"
$template RemoteHost,"/var/log/remote/%HOSTNAME%_%fromhost-ip%.log"

if ($fromhost-ip != '127.0.0.1') then ?RemoteHost;tplremote  
& ~
```

2. **Log Rotation** (`/etc/logrotate.d/biobeamer`):
```
/var/log/remote/*
{
        rotate 13
        monthly
        missingok
        notifempty
        compress
}
```

3. **Systemd Service** (example):
```ini
[Unit]
Description=BioBeamer Data Collection
After=network.target

[Service]
Type=simple
User=biobeamer
ExecStart=/usr/local/bin/biobeamer --xml /etc/biobeamer/config.xml --hostname %H
Restart=always

[Install]
WantedBy=multi-user.target
```


## Authors

- [Christian Panse](http://www.fgcz.ch/the-center/people/panse.html) :rocket: - Original author
- [Witold Wolski](mailto:wew@fgcz.uzh.ch) - Contributor
- [Claudio Cannizzaro](mailto:claudio.cannizzaro@fgcz.uzh.ch) - Contributor

## License

This project is part of the FGCZ (Functional Genomics Center Zurich) infrastructure.

## See Also

- [FGCZ Intranet Wiki](http://fgcz-intranet.uzh.ch/tiki-index.php?page=BioBeamer)
- [FGCZ Configuration](http://fgcz-data.uzh.ch/config/BioBeamer.xml)
- [Project Statistics](https://www.openhub.net/p/BioBeamer)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Run the test suite (`pytest`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## Changelog

### Version 0.1.0
- Modernized package structure with `pyproject.toml`
- Added SFTP support with paramiko
- Enhanced test coverage
- Improved documentation
- Cross-platform compatibility improvements


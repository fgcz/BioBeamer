# BioBeamer - Instrument Data Collection System

[![Project Stats](https://www.openhub.net/p/BioBeamer/widgets/project_thin_badge.gif)](https://www.openhub.net/p/BioBeamer)

BioBeamer is a Python-based data collection system for scientific instruments. It automatically synchronizes instrument data files from source locations to target destinations using various transfer protocols (robocopy, scp, sftp).

## Features

- **Multiple transfer protocols**: robocopy, scp, sftp (with paramiko support)
- **XML-based configuration**: Flexible host and instrument configuration
- **File filtering**: Pattern-based file selection and filtering
- **Monitoring**: Comprehensive logging and syslog integration
- **Simulation mode**: Test configurations without actual file transfers
- **Cross-platform**: Works on Windows and Unix-like systems

## Requirements

- Python 3.7+
- For SFTP support: `paramiko` library
- For scp/robocopy: respective system tools installed

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

- **`tool`**: Transfer protocol (`robocopy`, `scp`, `sftp`)
- **`pattern`**: Regex pattern for file filtering
- **`min_size`**: Minimum file size in bytes
- **`min_time_diff`**: Minimum file age in seconds before transfer
- **`max_time_diff`**: Maximum file age for transfer
- **`simulate_copy`**: Test mode without actual transfers
- **`source_path`**: Source directory path
- **`target_path`**: Destination path (can include user@host: for remote)

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


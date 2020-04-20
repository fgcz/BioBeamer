# Collecting instrument data using BioBeamer

[![Project Stats](https://www.openhub.net/p/BioBeamer/widgets/project_thin_badge.gif)](https://www.openhub.net/p/BioBeamer)

## Install 
* ensure you have python 2.7.* (for branch biobeamer2)
* ensure you have python >=3.7.*  (for branch p37).
* ```git clone git@github.com:fgcz/BioBeamer.git```
* if you want to use the p37 branch execute ```git checkout p37```

See also [setup.bat](https://github.com/fgcz/BioBeamer/blob/biobeamer2/setup.bat)


## Configure 

### BioBeamer xml configuration file

The entire file can be found here [Biobeamer.xml](https://github.com/fgcz/BioBeamer/blob/biobeamer2/BioBeamer2.xml)


```xml

<?xml-stylesheet type="text/xsl" href="BioBeamer.xsl"?>
<BioBeamerHosts>
<host name="fgcz-i-180" 
    instrument="TRIPLETOF_1"
    min_size="1024" 
    min_time_diff="10800" 
    max_time_diff="2419200" 
    simulate='false' 
    func_target_mapping="map_data_analyst_tripletof1" 
    robocopy_args="/E /Z /NP /R:0 /LOG+:C:\\Progra~1\\BioBeamer\\robocopy.log"
    pattern=".+" 
    source_path="D:/Analyst Data/Projects/" 
    target_path="\\130.60.81.21\\Data2San">
    <b-fabric>
        <applicationID>93</applicationID>
    </b-fabric>
</host>
</BioBeamerHosts>

```

the xml can be validated using

```bash
xmllint --noout --schema BioBeamer.xsd BioBeamer.xml
```

or 

```bash
xmlstarlet val --xsd BioBeamer.xsd BioBeamer.xml
```

### Biobeamer allows to specify instrument specific mapping functions.

```python

def func_target_mapping_TRIPLETOF_1(path):
    """
    input:  'p1000/Data/selevsek_20150119'
    output: 'p1000/Proteomics/TRIPLETOF_1/selevsek_20150119'
    """

    pattern = ".*(p[0-9]+)\\\\Data\\\\([-0-9a-zA-Z_\.]+)$"
    regex = re.compile(pattern)
    match = regex.match(path)

    if match:
        return os.path.normpath("{0}/Proteomics/TRIPLETOF_1/{1}".format(match.group(1), match.group(2)))
       
    return None
```

For more examples see [mapping_functions.py](https://github.com/fgcz/BioBeamer/blob/biobeamer2/mapping_functions.py)

### Logging

There are three log files in C:\FGCZ\BioBeamer\log

- robocopy.log : logs all the robocopy.exe logs (please see also the return codes of robocopy http://ss64.com/nt/robocopy-exit.html)
- biobeamer.log logs biobeamer filtering and copying information (it also goes to syslog - see next section).


### Configure Syslog '/etc/rsyslog.conf' 

```syslog
$template tplremote,"%timegenerated% %HOSTNAME% %fromhost-ip% %syslogtag%%msg:::drop-last-lf%\n"
$template RemoteHost,"/var/log/remote/%HOSTNAME%_%fromhost-ip%.log"

if ($fromhost-ip != '127.0.0.1') then ?RemoteHost;tplremote  
& ~
```

### Configure logrotate '/etc/logrotate.d/remote'
```conf
/var/log/remote/*
{
        rotate 13
        monthly
        missingok
        notifempty
        compress
}
```

## Run

### @ FGCZ

fgcz_biobeamer.py script which uses robocopy.exe on Micorsoft installed PCs to sync the files.


## Authors
[Witold Wolski](http://www.fgcz.ch/the-center/people/wolski.html) :rocket:
[Christian Panse](http://www.fgcz.ch/the-center/people/panse.html) :rocket:

## See also
* [fgcz-intranet wiki page](http://fgcz-intranet.uzh.ch/tiki-index.php?page=BioBeamer)

## TODO
* munin plugin ?

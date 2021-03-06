# Collecting instrument data using BioBeamer

fgcz_biobeamer.py is a complete new implementation based on the experience of
Frank Potthast's Perl implementation which was running for 10yrs at the FGCZ and
moved approximately 50TBytes of more than 164770 mass spectrometric raw data files.
This implementation is used since approximately 2016 to move files from about 20 Windows machines to the storage.

## Install 
* ensure you have python 2.7.* (for branch biobeamer2)
* ensure you have python >=3.7.*  (for branch p37).
* ```git clone git@github.com:fgcz/BioBeamer.git```
* if you want to use the p37 branch execute ```git checkout p37```

See also [setup.bat](https://github.com/fgcz/BioBeamer/blob/biobeamer2/setup.bat) for more setup details on windows.


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

For more examples of mapping functions see: [mapping_functions.py](https://github.com/fgcz/BioBeamer/blob/biobeamer2/mapping_functions.py)

### Logging

There are two log files in C:\FGCZ\BioBeamer\log

- robocopy.log : log generated by robocopy.exe (please see also the return codes of robocopy http://ss64.com/nt/robocopy-exit.html)
- biobeamer.log logs filtering and copying information (it also goes to syslog - see next section).


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

```cmd
c:\python27\python.exe C:\FGCZ\BioBeamer\biobeamer2.py file:///c:/FGCZ/BioBeamer <encoded password>
```

- First argument is the folder containing the `BioBeamer.xml` file
- Second argument is the encoded password.

We wrapp this command into a biobeamer.bat file, which first pull the latest version of the Biobeamer and Biobeamer.xml file from the Biobeamer repository. By this we make sure that all instruments run the same Biobeamer version.

```bat
PUSHD C:\FGCZ\BioBeamer
git -C C:\FGCZ\BioBeamer\ pull
timeout 8
c:\python27\python.exe C:\FGCZ\BioBeamer\biobeamer2.py file:///c:/FGCZ/BioBeamer <encoded password>
POPD
```


# Principle

The BioBeamer enhances the following windows script by adding:
- reading configurations for various instruments
- filtering 
- loggin 
- error handling
implemented in python.

```bat
rem Simon Barkow <sb@fgcz.ethz.ch>
rem Christian Panse <cp@fgcz.ethz.ch>
rem Christian Trachsel <christian.trachsel@fgcz.ethz.ch>
rem 2013-03-19
rem 2015-01-22
net use R: \\130.60.81.21\Data2San /USER:FGCZ-NET\BioBeamer !XXXXX!
D:
cd "\Eksigent NanoLC"
R:\PP\robocopy.exe "autosave" R:\PP\TRIPLETOF_1\data /S /COPY:DAT /MAXAGE:14 /Z /NP /LOG+:R:\PP\TRIPLETOF_1\ppsync.log
COPY %0 R:\PP\TRIPLETOF_1\
net use /delete /y R:
```

```
; Run robocopy script
; /E recursive
; /Z recover large copies
; /MINAGE minimum last modified date: one day
; /XD ignore P123.PRO folder (important for QTOF_1)
; /XF ignore *.sld files 
; /MOVE

if not exist D:\robocopy_logs md D:\robocopy_logs

net use R: \\130.60.81.21\Data2San /USER:FGCZ-NET\BioBeamer !XXXXX!

for /L %p in (1000,1,2000) do if exist p%p robocopy.exe D:\Data2San\p%p\QEXACTIVEHD_1 \\fgcz-s-021.uzh.ch\Data2San\p%p\QEXACTIVEHD_1  /E /Z /XF *.sld /NP /LOG+:D:\robocopy_logs\CopyLog.txt"

net use /delete /y R:
```

more information about [robocopy.exe](https://docs.microsoft.com/en-us/windows-server/administration/windows-commands/robocopy)

## Authors
- [Witold Wolski](http://www.fgcz.ch/the-center/people/wolski.html) :rocket:
- [Christian Panse](http://www.fgcz.ch/the-center/people/panse.html) :rocket:

## See also
* [fgcz-intranet wiki page](http://fgcz-intranet.uzh.ch/tiki-index.php?page=BioBeamer)

## TODO
* munin plugin ?

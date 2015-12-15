# Collecting instrument data using BioBeamer

![BioBeamer UML](/images/classes_No_Name.png)

## Install 
```bash
git clone git@github.com:cpanse/BioBeamer.git
```

## Run

### @ FGCZ
just 'run as administrator' justBeamFiles.exe.

the justBeamFiles.exe maps the storage and runs the fgcz_biobeamer.py script which uses robocopy.exe on Micorsoft installed PCs to sync the files.

### otherwise

```cmd
python BioBeamer.py
```

## Configure Syslog '/etc/rsyslog.conf' 

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

## Author
[Christian Panse](http://www.fgcz.ch/the-center/people/panse.html)

## See also
[fgcz-intranet wiki page](http://fgcz-intranet.uzh.ch/tiki-index.php?page=BioBeamer)

## TODO
* munin plugin

## SOP deploy @ new location
* change syslog host
* change configuration url

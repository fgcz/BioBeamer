#Include <date.au3>

; $HeadURL: http://fgcz-svn.uzh.ch/repos/fgcz/stable/proteomics/BioBeamer/justBeamFiles_py.au3 $
; $Id: justBeamFiles_py.au3 7195 2015-01-29 14:31:37Z cpanse $
; $Date: 2015-01-29 15:31:37 +0100 (Thu, 29 Jan 2015) $

Local $drive = '\\fgcz-ms.fgcz-net.unizh.ch\\Data2San'
Local $file = FileOpen("C:\Program Files\BioBeamer\justBeamFiles.log", 1)
Local $python_cmd = "c:\python27\python.exe ""C:\Program Files\BioBeamer\fgcz_biobeamer.py"""

FileWrite($file, "----------------------------------------------------------- " & @CRLF)
FileWrite($file, "Started justBeaming at " & _Now() & @CRLF)

Local $resMap = DriveMapAdd ( "", $drive, 0, "FGCZ-NET\BioBeamer", "xxxxTOPSECRETxxxx" )

FileWrite($file, "return code DriveMapAdd = " & $resMap & @CRLF)

If Not FileExists($drive) Then
	$msg = "ERROR: drive " & $drive & " could not be mounted. aboard! " & _Now() & @CRLF
	FileWrite($file, $msg)
    FileClose($file)
	msgbox(0, "no drive", $msg  & @CRLF )
	exit
Else
	FileWrite($file, $drive & " is mounted." & @CRLF)
EndIf

; display a msg box
SplashTextOn("BioBeamer", "BioBeamer", 500, 50, -1, -1, 2, "", 24)
sleep(3000)
SplashTextOn("BioBeamer", "Files are being synced to the SAN", 500, 50, -1, -1, 2, "", 24)
sleep(3000)

; main
FileWrite($file, "Run '" & $python_cmd & "' started at " & _Now()  & @CRLF)

Local $resRun = RunWait($python_cmd)

FileWrite($file, "return code = " & $resRun & @CRLF)
FileWrite($file, "'" & $python_cmd & "' seems to be done. " & _Now() & @CRLF)

DriveMapDel($drive)
FileWrite($file, "unmounted " &  $drive & " at " & _Now() & @CRLF)
;just to be sure that the window of checkDirectory is closed
sleep(3500)

FileWrite($file, "----------------------------------------------------------- " & @CRLF)
FileClose($file)


#Include <date.au3>

; $HeadURL: http://fgcz-svn.uzh.ch/repos/fgcz/stable/proteomics/BioBeamer/justBeamFiles_py.au3 $
; $Id: justBeamFiles_py.au3 7195 2015-01-29 14:31:37Z cpanse $
; $Date: 2015-01-29 15:31:37 +0100 (Thu, 29 Jan 2015) $

; Local $drive = '\\130.60.81.21\Data2San'

Local $python_cmd = "c:\fgcz\biobeamer\biobeamer.bat"

; display a msg box
SplashTextOn("BioBeamer", "BioBeamer", 500, 50, -1, -1, 2, "", 24)
sleep(3000)
SplashTextOn("BioBeamer", "Files are being synced to the SAN", 500, 50, -1, -1, 2, "", 24)
sleep(3000)

Local $resRun = RunWait($python_cmd)



Set ws = CreateObject("WScript.Shell")
ws.Run Chr(34) & Replace(WScript.ScriptFullName, WScript.ScriptName, "") & "start.bat" & Chr(34), 0, False

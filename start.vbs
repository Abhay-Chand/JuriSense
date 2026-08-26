' SaulGPT Launcher - Uses virtual environment Python
Set WshShell = CreateObject("WScript.Shell")

scriptPath = Replace(WScript.ScriptFullName, "start.vbs", "")

' Start backend with venv Python
WshShell.CurrentDirectory = scriptPath & "backend"
WshShell.Run "cmd /k " & scriptPath & ".venv\Scripts\python.exe api_server.py", 1, False
WScript.Sleep 4000

' Start frontend
WshShell.CurrentDirectory = scriptPath & "saulgpt-ui"
WshShell.Run "cmd /k npm run dev", 1, False
WScript.Sleep 3000

' Open browser
WshShell.Run "http://localhost:5173"
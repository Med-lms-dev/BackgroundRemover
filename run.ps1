$python = "C:\Users\LENOVO\AppData\Local\Programs\Python\Python313"

$env:TCL_LIBRARY = "$python\tcl\tcl8.6"
$env:TK_LIBRARY = "$python\tcl\tk8.6"

.\.venv\Scripts\python.exe src\main.py
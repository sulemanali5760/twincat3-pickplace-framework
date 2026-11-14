param([string]$Version = "1.0.0.0", [string]$Out = "$PWD\NodeTree.library")
# Build NodeTree.library from this repo: strip a copy of the project down to Framework/ + Devices/
# (tools/make_library_project.py), compile it, then save it as a library through the
# TwinCAT Automation Interface. Needs TwinCAT XAE 3.1.4026 and Python 3 on PATH.
$Sln = (& python "$PSScriptRoot\make_library_project.py" "$PSScriptRoot\..\TcProject" $Version)
if ($LASTEXITCODE -ne 0) { throw "make_library_project.py failed" }
function Retry([scriptblock]$b) {
    for ($i = 0; $i -lt 90; $i++) {
        try { return & $b } catch {
            if ($_.Exception.Message -match 'RPC_E_CALL_REJECTED|0x80010001|busy|RPC_E_SERVERCALL_RETRYLATER|0x8001010A') { Start-Sleep -Seconds 1 } else { throw }
        }
    }
    throw "COM call kept being rejected"
}
$before = @(Get-Process TcXaeShell -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
$dte = $null
try {
    $dte = New-Object -ComObject TcXaeShell.DTE.17.0
    Retry { $dte.SuppressUI = $true } | Out-Null
    Retry { $dte.MainWindow.Visible = $false } | Out-Null
    Retry { $dte.Solution.Open($Sln) } | Out-Null
    Start-Sleep -Seconds 8
    Retry { $dte.Solution.SolutionBuild.Build($true) } | Out-Null
    Write-Output ("BUILD_FAILED_PROJECTS=" + (Retry { $dte.Solution.SolutionBuild.LastBuildInfo }))
    $proj = Retry { $dte.Solution.Projects.Item(1) }
    $sm = $proj.Object
    Start-Sleep -Seconds 2; $iec = $sm.LookupTreeItem("TIPC^PickPlacePlc^PickPlacePlc Project")
    Retry { $iec.SaveAsLibrary($Out, $false) } | Out-Null
    Write-Output ("SAVED=" + (Test-Path $Out))
} catch { Write-Output ("ERROR: " + $_.Exception.Message) }
finally {
    if ($dte) { try { Retry { $dte.Solution.Close($false) } | Out-Null } catch { } ; try { $dte.Quit() } catch { } }
    Start-Sleep -Seconds 3
    Get-Process TcXaeShell -ErrorAction SilentlyContinue | Where-Object { $before -notcontains $_.Id } | Stop-Process -Force -ErrorAction SilentlyContinue
}

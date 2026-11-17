# Runs a WSL script while keeping Windows awake (no sleep while it runs; the screen may still turn
# off). Uses SetThreadExecutionState, so power settings are not changed and normal sleep returns
# when the script ends. Closing a laptop lid still sleeps if the lid action is "sleep".
#   powershell -NoProfile -ExecutionPolicy Bypass -File arena\keep_awake.ps1 -Script /mnt/c/.../arena/start_tune.sh [-Env "HOURS=5 PROMOTE=1"]
param([Parameter(Mandatory = $true)][string]$Script, [string]$Distro = "Ubuntu", [string]$Env = "")
Add-Type -Namespace PacmanArena -Name Power -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("kernel32.dll")]
public static extern uint SetThreadExecutionState(uint esFlags);
'@
$ES_CONTINUOUS = [Convert]::ToUInt32("80000000", 16)
$ES_SYSTEM_REQUIRED = [Convert]::ToUInt32("00000001", 16)
[PacmanArena.Power]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED) | Out-Null
try {
    $vars = @($Env -split '\s+' | Where-Object { $_ })
    & wsl.exe -d $Distro -- env @vars bash $Script
} finally {
    [PacmanArena.Power]::SetThreadExecutionState($ES_CONTINUOUS) | Out-Null
}

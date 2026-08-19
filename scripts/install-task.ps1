$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $PSScriptRoot "run-lunch.cmd"
$taskName = "SSAFYLunchBot"

if (-not (Test-Path $runner)) {
    throw "실행 파일이 없습니다: $runner"
}

schtasks /Create /TN $taskName /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 11:00 /TR "`"$runner`"" /F | Out-Null
Write-Host "Windows 작업 스케줄러에 '$taskName' 을 등록했습니다."
Write-Host "평일 11:00에 $project 에서 급식표를 보냅니다."
Write-Host "확인: schtasks /Query /TN $taskName /V /FO LIST"

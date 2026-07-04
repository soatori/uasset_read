<#
.SYNOPSIS
    配置 Git textconv 驱动，使 .uasset 文件在 git diff 中显示为可读文本。
.DESCRIPTION
    本脚本配置 git config 的 diff 驱动，将 .uasset 文件映射到 textconv 脚本。
    配置完成后，git diff 会自动调用解析器生成文本摘要进行对比。
.EXAMPLE
    .\scripts\install-git-textconv.ps1
    .\scripts\install-git-textconv.ps1 -Uninstall
#>
param(
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$TextconvScript = Join-Path $RepoRoot "scripts" | Join-Path -ChildPath "git-textconv-uasset.py"

if (-not (Test-Path $TextconvScript)) {
    Write-Error "找不到 textconv 脚本: $TextconvScript"
    exit 1
}

if ($Uninstall) {
    git config --local --unset diff.uasset-read.textconv 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "已移除 git textconv 配置（uasset-read）" -ForegroundColor Green
    } else {
        Write-Host "未找到 uasset-read textconv 配置" -ForegroundColor Yellow
    }
    exit 0
}

# 使用 python 解释器路径
$PythonExe = "python"

# 配置 textconv
$TextconvCmd = "`"$PythonExe`" `"$TextconvScript`""
git config --local diff.uasset-read.textconv $TextconvCmd
if ($LASTEXITCODE -ne 0) {
    Write-Error "git config 配置失败（确保在 git 仓库内运行）"
    exit 1
}

Write-Host "已配置 git textconv 驱动（uasset-read）" -ForegroundColor Green
Write-Host "  textconv: $TextconvCmd"
Write-Host ""
Write-Host "现在可以使用 git diff 查看 .uasset 文件的文本差异：" -ForegroundColor Cyan
Write-Host "  git diff -- '*.uasset'"
Write-Host ""
Write-Host "如需卸载，运行:" -ForegroundColor DarkGray
Write-Host "  .\scripts\install-git-textconv.ps1 -Uninstall"

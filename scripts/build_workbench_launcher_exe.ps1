[CmdletBinding()]
param(
    [string] $OutputPath = (Join-Path ([Environment]::GetFolderPath("Desktop")) "WorkbenchLauncher.exe")
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$CscCandidates = @(
    (Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"),
    (Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe"),
    (Join-Path $env:WINDIR "Microsoft.NET\Framework64\v3.5\csc.exe"),
    (Join-Path $env:WINDIR "Microsoft.NET\Framework\v3.5\csc.exe")
)
$Csc = $CscCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (-not $Csc) {
    throw "No .NET Framework C# compiler was found."
}

$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("workbench_launcher_" + [System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tempDir | Out-Null

try {
    $sourceFile = Join-Path $tempDir "WorkbenchLauncher.cs"
    $outputFullPath = [System.IO.Path]::GetFullPath($OutputPath)
    $sourceRoot = $Root.Replace('"', '""')

    @"
using System;
using System.Diagnostics;
using System.IO;
using System.Text;

internal static class WorkbenchLauncher
{
    private const string Root = @"$sourceRoot";

    private static int Main(string[] args)
    {
        string script = Path.Combine(Root, "scripts", "start_workbench.ps1");
        if (!File.Exists(script))
        {
            Console.Error.WriteLine("Launcher script was not found: " + script);
            Console.WriteLine("Press Enter to close");
            Console.ReadLine();
            return 1;
        }

        string arguments = "-NoProfile -ExecutionPolicy Bypass -File " + Quote(script);
        for (int i = 0; i < args.Length; i++)
        {
            arguments += " " + Quote(args[i]);
        }

        ProcessStartInfo startInfo = new ProcessStartInfo();
        startInfo.FileName = "powershell.exe";
        startInfo.Arguments = arguments;
        startInfo.WorkingDirectory = Root;
        startInfo.UseShellExecute = false;

        try
        {
            Process process = Process.Start(startInfo);
            process.WaitForExit();
            return process.ExitCode;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine("Failed to launch workbench: " + ex.Message);
            Console.WriteLine("Press Enter to close");
            Console.ReadLine();
            return 1;
        }
    }

    private static string Quote(string value)
    {
        if (value == null)
        {
            return "\"\"";
        }

        StringBuilder builder = new StringBuilder();
        builder.Append('"');
        for (int i = 0; i < value.Length; i++)
        {
            char c = value[i];
            if (c == '\\' || c == '"')
            {
                builder.Append('\\');
            }
            builder.Append(c);
        }
        builder.Append('"');
        return builder.ToString();
    }
}
"@ | Set-Content -LiteralPath $sourceFile -Encoding ASCII

    & $Csc /nologo /target:exe /platform:anycpu /out:$outputFullPath $sourceFile
    if ($LASTEXITCODE -ne 0) {
        throw "csc failed with exit code $LASTEXITCODE"
    }

    if (-not (Test-Path -LiteralPath $outputFullPath)) {
        throw "Expected launcher was not created: $outputFullPath"
    }

    Write-Host "Created launcher: $outputFullPath"
}
finally {
    Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
}

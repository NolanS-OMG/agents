param(
    [string]$OutputFile = "$env:TEMP\recording.wav"
)

# Records from default microphone until ENTER is pressed.
# Outputs 16kHz mono 16-bit WAV.

Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

public class MicRecorder {
    [DllImport("winmm.dll", SetLastError = true)]
    static extern int mciSendString(string command, StringBuilder buffer, int bufferSize, IntPtr callback);

    public static bool Record(string outputPath) {
        StringBuilder sb = new StringBuilder(256);
        int err;

        err = mciSendString("open new Type waveaudio Alias mic", sb, 256, IntPtr.Zero);
        if (err != 0) return false;

        // Set format: 16kHz mono 16-bit
        mciSendString("set mic time format milliseconds", null, 0, IntPtr.Zero);
        mciSendString("set mic bitspersample 16", null, 0, IntPtr.Zero);
        mciSendString("set mic channels 1", null, 0, IntPtr.Zero);
        mciSendString("set mic samplespersec 16000", null, 0, IntPtr.Zero);
        mciSendString("set mic bytespersec 32000", null, 0, IntPtr.Zero);
        mciSendString("set mic alignment 2", null, 0, IntPtr.Zero);

        err = mciSendString("record mic", sb, 256, IntPtr.Zero);
        if (err != 0) {
            mciSendString("close mic", null, 0, IntPtr.Zero);
            return false;
        }

        return true;
    }

    public static void Stop(string outputPath) {
        StringBuilder sb = new StringBuilder(256);
        mciSendString("stop mic", sb, 256, IntPtr.Zero);
        mciSendString("save mic \"" + outputPath + "\"", sb, 256, IntPtr.Zero);
        mciSendString("close mic", sb, 256, IntPtr.Zero);
    }
}
'@

$success = [MicRecorder]::Record($OutputFile)
if (-not $success) {
    Write-Error "No se pudo iniciar grabacion. Verifica permisos de microfono."
    exit 1
}

# Wait for input (ENTER from parent process via stdin)
[Console]::In.ReadLine() | Out-Null

[MicRecorder]::Stop($OutputFile)

if (Test-Path $OutputFile) {
    $size = (Get-Item $OutputFile).Length
    Write-Host "OK:${size}bytes"
} else {
    Write-Error "No se genero archivo"
    exit 1
}

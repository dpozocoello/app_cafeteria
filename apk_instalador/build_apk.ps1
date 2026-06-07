#Requires -Version 5.1
<#
.SYNOPSIS
    Descarga el Android SDK, compila y empaqueta cafeteria-pos-waiter.apk

.DESCRIPTION
    Automatiza la descarga de:
      - Gradle 8.6 (motor de compilacion)
      - Android SDK Command-line Tools
      - Plataforma Android 34 y Build-Tools 34.0.0
    Luego compila el proyecto Android y copia el APK resultante
    a la carpeta apk_instalador/.

.PARAMETER Clean
    Si se especifica, limpia la cache de Gradle antes de compilar.

.PARAMETER SkipDownload
    Omite la descarga si las herramientas ya existen localmente.

.EXAMPLE
    .\build_apk.ps1
    .\build_apk.ps1 -Clean
    .\build_apk.ps1 -SkipDownload
#>
param(
    [switch]$Clean,
    [switch]$SkipDownload
)

$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"   # Acelera Invoke-WebRequest significativamente

# ─── Rutas base ───────────────────────────────────────────────────────────────
$ScriptDir     = Split-Path -Parent $MyInvocation.MyCommand.Path
$ToolsDir      = Join-Path $ScriptDir "tools"
$AndroidAppDir = Join-Path $ScriptDir "android_app"
$GradleVersion = "8.6"
$GradleDir     = Join-Path $ToolsDir "gradle-$GradleVersion"
$GradleExe     = Join-Path $GradleDir "bin\gradle.bat"
$SdkDir        = Join-Path $ToolsDir "android-sdk"
$SdkManager    = Join-Path $SdkDir "cmdline-tools\latest\bin\sdkmanager.bat"

function Write-Step([string]$Step, [string]$Msg) {
    Write-Host "`n[$Step] $Msg" -ForegroundColor Cyan
}
function Write-OK([string]$Msg)    { Write-Host "  OK  $Msg" -ForegroundColor Green }
function Write-Info([string]$Msg)  { Write-Host "  >>  $Msg" -ForegroundColor Gray }
function Write-Fail([string]$Msg)  { Write-Host "  ERR $Msg" -ForegroundColor Red }

# ─── Cabecera ─────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Blue
Write-Host "  Cafeteria POS - Generador de APK      " -ForegroundColor Blue
Write-Host "========================================" -ForegroundColor Blue

# ─── 1. Verificar Java 17+ ────────────────────────────────────────────────────
Write-Step "1/6" "Verificando Java..."
$javaCmd = Get-Command java -ErrorAction SilentlyContinue
if (-not $javaCmd) {
    Write-Fail "Java no encontrado. Instale JDK 17+ desde https://adoptium.net"
    exit 1
}
Write-OK "Java encontrado: $($javaCmd.Source)"

# Detectar JAVA_HOME: buscar JDK real (el javapath de Oracle no es válido)
if (-not $env:JAVA_HOME -or -not (Test-Path (Join-Path $env:JAVA_HOME "bin\javac.exe"))) {
    $candidates = @(
        "C:\Program Files\Java\latest",
        "C:\Program Files\Java\jdk-17.0.18",
        "C:\Program Files\Eclipse Adoptium",
        "C:\Program Files\Microsoft"
    )
    # Buscar primer directorio con bin\javac.exe
    $found = $null
    foreach ($c in $candidates) {
        if (Test-Path "$c\bin\javac.exe") { $found = $c; break }
        if (Test-Path $c) {
            $sub = Get-ChildItem $c -Directory -ErrorAction SilentlyContinue |
                   Where-Object { Test-Path "$($_.FullName)\bin\javac.exe" } |
                   Select-Object -First 1
            if ($sub) { $found = $sub.FullName; break }
        }
    }
    if ($found) {
        $env:JAVA_HOME = $found
        Write-Info "JAVA_HOME: $env:JAVA_HOME"
    } else {
        Write-Info "JAVA_HOME no detectado automáticamente; usando el del sistema"
    }
}

New-Item -ItemType Directory -Force -Path $ToolsDir | Out-Null

# ─── 2. Descargar Gradle 8.6 ──────────────────────────────────────────────────
Write-Step "2/6" "Verificando Gradle $GradleVersion..."
if (-not (Test-Path $GradleExe) -and -not $SkipDownload) {
    $GradleZip = Join-Path $ToolsDir "gradle-$GradleVersion-bin.zip"
    $GradleUrl = "https://services.gradle.org/distributions/gradle-$GradleVersion-bin.zip"
    Write-Info "Descargando $GradleUrl (~130 MB)..."
    Invoke-WebRequest -Uri $GradleUrl -OutFile $GradleZip
    Write-Info "Extrayendo Gradle..."
    Expand-Archive -Path $GradleZip -DestinationPath $ToolsDir -Force
    Remove-Item $GradleZip -Force
    Write-OK "Gradle $GradleVersion listo en $GradleDir"
} elseif (Test-Path $GradleExe) {
    Write-OK "Gradle ya disponible"
} else {
    Write-Fail "Gradle no encontrado y -SkipDownload activo. Ejecute sin ese parámetro."
    exit 1
}

# ─── 3. Descargar Android Command-line Tools ──────────────────────────────────
Write-Step "3/6" "Verificando Android SDK Command-line Tools..."
if (-not (Test-Path $SdkManager) -and -not $SkipDownload) {
    $CmdToolsUrl = "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"
    $CmdToolsZip = Join-Path $ToolsDir "cmdline-tools.zip"
    Write-Info "Descargando $CmdToolsUrl (~150 MB)..."
    Invoke-WebRequest -Uri $CmdToolsUrl -OutFile $CmdToolsZip
    Write-Info "Extrayendo command-line tools..."
    $TempDir = Join-Path $ToolsDir "cmdline-temp"
    Expand-Archive -Path $CmdToolsZip -DestinationPath $TempDir -Force
    $TargetDir = Join-Path $SdkDir "cmdline-tools\latest"
    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
    # El ZIP descomprime en "cmdline-tools/", se mueve al path esperado por sdkmanager
    $ExtractedDir = Join-Path $TempDir "cmdline-tools"
    if (Test-Path $ExtractedDir) {
        Copy-Item -Path "$ExtractedDir\*" -Destination $TargetDir -Recurse -Force
    } else {
        Copy-Item -Path "$TempDir\*" -Destination $TargetDir -Recurse -Force
    }
    Remove-Item $TempDir -Recurse -Force
    Remove-Item $CmdToolsZip -Force
    Write-OK "Command-line tools listos"
} elseif (Test-Path $SdkManager) {
    Write-OK "Android SDK Command-line Tools ya disponibles"
} else {
    Write-Fail "sdkmanager no encontrado y -SkipDownload activo."
    exit 1
}

# ─── 4. Instalar plataforma Android 34 y Build-Tools ─────────────────────────
Write-Step "4/6" "Instalando componentes del SDK (platform-34, build-tools-34.0.0)..."
$env:ANDROID_HOME = $SdkDir

# Aceptar licencias automáticamente (envía 'y' para cada prompt)
$LicenseInput = ("y`n" * 30)
Write-Info "Aceptando licencias..."
$LicenseInput | & $SdkManager --licenses 2>&1 | Out-Null

# Instalar componentes necesarios
$Components = @("platform-tools", "platforms;android-34", "build-tools;34.0.0")
foreach ($comp in $Components) {
    Write-Info "Instalando: $comp"
    $LicenseInput | & $SdkManager $comp 2>&1 | Where-Object { $_ -match "Installing|Unzipping|Unpacking" } | ForEach-Object { Write-Info $_ }
}
Write-OK "SDK Android 34 instalado correctamente"

# ─── 5. Generar local.properties ──────────────────────────────────────────────
Write-Step "5/6" "Configurando local.properties..."
$LocalProps = Join-Path $AndroidAppDir "local.properties"
$SdkDirEscaped = $SdkDir -replace "\\", "\\"
"sdk.dir=$SdkDirEscaped" | Out-File -FilePath $LocalProps -Encoding utf8 -NoNewline
Write-OK "local.properties generado: $LocalProps"

# ─── 6. Compilar APK ──────────────────────────────────────────────────────────
Write-Step "6/6" "Compilando APK Debug..."

$StdoutLog = Join-Path $ScriptDir "build_stdout.log"
$StderrLog = Join-Path $ScriptDir "build_stderr.log"

$GradleArgs = @("assembleDebug", "--no-daemon", "--stacktrace")
if ($Clean) {
    Write-Info "Limpiando cache de Gradle primero..."
    $cleanProc = Start-Process -FilePath $GradleExe -ArgumentList "clean","--no-daemon" `
        -WorkingDirectory $AndroidAppDir -Wait -PassThru `
        -RedirectStandardOutput (Join-Path $ScriptDir "clean_out.log") `
        -RedirectStandardError  (Join-Path $ScriptDir "clean_err.log") `
        -NoNewWindow
}

Write-Info "Ejecutando assembleDebug (puede tardar 3-8 min la primera vez)..."
$proc = Start-Process -FilePath $GradleExe -ArgumentList $GradleArgs `
    -WorkingDirectory $AndroidAppDir -Wait -PassThru `
    -RedirectStandardOutput $StdoutLog `
    -RedirectStandardError  $StderrLog `
    -NoNewWindow

if ($proc.ExitCode -ne 0) {
    Write-Fail "Build FALLIDO (exit code $($proc.ExitCode))"
    Write-Host "`n--- Errores relevantes ---" -ForegroundColor Red
    if (Test-Path $StderrLog) {
        Get-Content $StderrLog | Where-Object { $_ -match "error:|FAILED|Exception|Could not" } |
            Select-Object -First 30 | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    }
    Write-Host "`nLogs completos:"
    Write-Host "  STDOUT: $StdoutLog"
    Write-Host "  STDERR: $StderrLog"
    exit 1
}

# Mostrar tareas ejecutadas
if (Test-Path $StdoutLog) {
    Get-Content $StdoutLog | Where-Object { $_ -match "^> Task|BUILD SUCCESS" } |
        ForEach-Object { Write-Info $_ }
}

# ─── Copiar APK al directorio de salida ───────────────────────────────────────
$ApkSource = Join-Path $AndroidAppDir "app\build\outputs\apk\debug\app-debug.apk"
$ApkDest   = Join-Path $ScriptDir "cafeteria-pos-waiter.apk"

if (Test-Path $ApkSource) {
    Copy-Item -Path $ApkSource -Destination $ApkDest -Force
    $ApkSize = [math]::Round((Get-Item $ApkDest).Length / 1MB, 1)
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  APK GENERADO EXITOSAMENTE              " -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Archivo : cafeteria-pos-waiter.apk"
    Write-Host "  Tamaño  : $ApkSize MB"
    Write-Host "  Ruta    : $ApkDest"
    Write-Host ""
    Write-Host "Para instalar en el dispositivo Android:" -ForegroundColor Yellow
    Write-Host "  1. Active 'Instalar apps desconocidas' en Ajustes > Seguridad"
    Write-Host "  2. Copie el APK al dispositivo (USB o WiFi)"
    Write-Host "  3. Abra el archivo desde el administrador de archivos"
    Write-Host "  Alternativa (ADB): adb install `"$ApkDest`""
    Write-Host ""
} else {
    Write-Fail "APK no encontrado en: $ApkSource"
    Write-Host "Revise build_error.log para más detalles."
    exit 1
}

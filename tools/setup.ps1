# Weisy first-run setup, called by start.bat or Weisy-daily-desk.exe (launcher.py) before the server starts (env WEISY_DIR = program folder).
# One small dialog, asked ONCE per program folder: where to keep the data (default: the Weisy-Data folder in %APPDATA%,
# only created if the user keeps it) and whether to put a shortcut on the desktop. Weisy's own small notes live in
# .weisy inside the program folder, so deleting the program folder leaves nothing behind: location.txt (the chosen
# data folder, read by server.py) and desktop-shortcut.txt (the fact that we asked). -Preview <png> only saves a
# picture of the dialog. Closing the dialog (X or Esc) exits with code 3: start.bat then stops without starting anything.
param([string]$Preview = '')
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type -Name Dpi -Namespace Weisy -MemberDefinition '[System.Runtime.InteropServices.DllImport("user32.dll")] public static extern bool SetProcessDPIAware();'
[void][Weisy.Dpi]::SetProcessDPIAware()
[System.Windows.Forms.Application]::EnableVisualStyles()

$folder = ([string]$env:WEISY_DIR).TrimEnd('\')
if (-not $folder) { $folder = (Split-Path -Parent $PSScriptRoot) }
# the icons travel with this script (repository: ../src/assets; packaged version: the same layout inside the package)
$assets = Join-Path (Split-Path -Parent $PSScriptRoot) 'src\assets'
# what the desktop shortcut opens: Weisy-daily-desk.exe in the packaged version (WEISY_TARGET), start.bat otherwise
$target = if ($env:WEISY_TARGET) { $env:WEISY_TARGET } else { Join-Path $folder 'start.bat' }
$launcherName = Split-Path -Leaf $target   # Weisy-daily-desk.exe or start.bat, named in the dialog
$base = Join-Path $env:APPDATA 'Weisy-Data'          # the default data folder (created by the server only if it is used)
$notes = Join-Path $folder '.weisy'                  # Weisy's own small notes stay inside the program folder
$mark = Join-Path $notes 'desktop-shortcut.txt'
$pointer = Join-Path $notes 'location.txt'
$utf8 = New-Object System.Text.UTF8Encoding($false)

# The dialog speaks the Windows display language: Chinese, otherwise English (WEISY_LANG=zh / en decides instead, as in server.py)
$lang = ([string]$env:WEISY_LANG).Trim().ToLower()
if ($lang -ne 'zh' -and $lang -ne 'en') { $lang = if ([System.Globalization.CultureInfo]::CurrentUICulture.TwoLetterISOLanguageName -eq 'zh') { 'zh' } else { 'en' } }
$Txt = @{
    zh = @{
        name = '潦草鼠鼠之家'; font = 'Microsoft YaHei UI'
        title = '第一次使用，先做两个选择'
        body = "选好数据保存的位置，再决定要不要桌面图标。`n不要图标也行，随时双击 $launcherName 打开。"
        where = '数据保存位置'; change = '更改…'
        pick = '选一个文件夹来保存数据（会在里面新建一个 Weisy-Data 文件夹）'
        inside = "不能把数据放在程序文件夹里面：更新或删除程序时数据会一起丢掉。`n请选程序文件夹之外的位置。"
        hint = '以前用过？点“更改…”，选回原来的数据文件夹就行。'
        once = '  ⚠  数据位置和桌面图标只会询问这一次，以后不会再次询问，请慎重考虑。'
        yes = '创建桌面图标并开始'; no = '不要图标，开始'
        fallback = "这个位置用不了，数据会保存在默认位置：`n$base"
    }
    en = @{
        name = 'Weisy Daily Desk'; font = 'Segoe UI'
        title = 'Two choices before you start'
        body = "Pick a data folder, then decide on a desktop icon.`nNo icon? Double-click $launcherName."
        where = 'Where to keep your data'; change = 'Change'
        pick = 'Choose a folder for your data (a Weisy-Data folder is created inside it)'
        inside = "The data cannot go inside the program folder: it would be lost when the program is updated or deleted.`nPlease choose a place outside the program folder."
        hint = 'Used it before? Click "Change" and pick your old data folder.'
        once = '  ⚠  You are asked about the data folder and the desktop icon only this once. Please choose carefully.'
        yes = 'Add icon and start'; no = 'No icon, just start'
        fallback = "This folder cannot be used, so the data is kept in the default place:`n$base"
    }
}[$lang]

function C([string]$hex) { [System.Drawing.ColorTranslator]::FromHtml($hex) }
function Read-Text($path) { if (Test-Path -LiteralPath $path) { ([IO.File]::ReadAllText($path)).Trim() } else { '' } }
function Write-Text($path, $text) { New-Item -ItemType Directory -Force -Path (Split-Path -Parent $path) | Out-Null; [IO.File]::WriteAllText($path, $text, $utf8) }

$script:location = Read-Text $pointer
if (-not $script:location) { $script:location = $base }

function Show-Dialog {
    $font = $Txt.font
    $f = New-Object System.Windows.Forms.Form
    $f.Text = $Txt.name
    $f.ClientSize = New-Object System.Drawing.Size(480, 356)
    $f.StartPosition = 'CenterScreen'; $f.FormBorderStyle = 'FixedDialog'; $f.MaximizeBox = $false; $f.MinimizeBox = $false
    $f.BackColor = C '#F3F4F1'; $f.TopMost = $true; $f.Font = New-Object System.Drawing.Font($font, 9.5)
    $ico = Join-Path $assets 'icon.ico'
    $png = Join-Path $assets 'icon-64.png'
    if (Test-Path $ico) { $f.Icon = New-Object System.Drawing.Icon($ico) }
    if (Test-Path $png) {
        $pb = New-Object System.Windows.Forms.PictureBox
        $pb.Image = [System.Drawing.Image]::FromFile($png); $pb.SizeMode = 'Zoom'
        $pb.Location = New-Object System.Drawing.Point(28, 28); $pb.Size = New-Object System.Drawing.Size(52, 52)
        $f.Controls.Add($pb)
    }
    $t = New-Object System.Windows.Forms.Label
    $t.Text = $Txt.title
    $t.Font = New-Object System.Drawing.Font($font, 14, [System.Drawing.FontStyle]::Bold); $t.ForeColor = C '#171B19'
    $t.Location = New-Object System.Drawing.Point(96, 28); $t.Size = New-Object System.Drawing.Size(360, 30)
    $b = New-Object System.Windows.Forms.Label
    $b.Text = $Txt.body
    $b.ForeColor = C '#434B47'
    $b.Location = New-Object System.Drawing.Point(96, 62); $b.Size = New-Object System.Drawing.Size(360, 44)
    $lh = New-Object System.Windows.Forms.Label
    $lh.Text = $Txt.where; $lh.Font = New-Object System.Drawing.Font($font, 9.5, [System.Drawing.FontStyle]::Bold); $lh.ForeColor = C '#434B47'
    $lh.Location = New-Object System.Drawing.Point(28, 118); $lh.Size = New-Object System.Drawing.Size(200, 22)
    $loc = New-Object System.Windows.Forms.Label
    $loc.BackColor = [System.Drawing.Color]::White; $loc.BorderStyle = 'FixedSingle'; $loc.Text = $script:location
    $loc.AutoEllipsis = $true; $loc.TextAlign = 'MiddleLeft'; $loc.ForeColor = C '#171B19'; $loc.Font = New-Object System.Drawing.Font($font, 8.5)
    $loc.Location = New-Object System.Drawing.Point(28, 142); $loc.Size = New-Object System.Drawing.Size(340, 32)
    $chg = New-Object System.Windows.Forms.Button
    $chg.Text = $Txt.change; $chg.FlatStyle = 'Flat'; $chg.FlatAppearance.BorderColor = C '#C5CAC4'
    $chg.BackColor = [System.Drawing.Color]::White; $chg.ForeColor = C '#171B19'; $chg.Cursor = 'Hand'
    $chg.Location = New-Object System.Drawing.Point(376, 142); $chg.Size = New-Object System.Drawing.Size(76, 32)
    $chg.Add_Click({
        $d = New-Object System.Windows.Forms.FolderBrowserDialog
        $d.Description = $Txt.pick
        $d.ShowNewFolderButton = $true
        $d.RootFolder = [System.Environment+SpecialFolder]::MyComputer   # start at This PC: C:, D: ... are right there
        if ($d.ShowDialog($f) -eq 'OK') {
            $picked = $d.SelectedPath
            if (($picked.TrimEnd('\') + '\').StartsWith($folder + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
                [void][System.Windows.Forms.MessageBox]::Show($Txt.inside, 'Weisy')
                return
            }
            $script:location = if (Test-Path -LiteralPath (Join-Path $picked 'weisy.json')) { $picked } else { Join-Path $picked 'Weisy-Data' }
            $loc.Text = $script:location
        }
    })
    $hint = New-Object System.Windows.Forms.Label
    $hint.Text = $Txt.hint
    $hint.ForeColor = C '#747C78'; $hint.Font = New-Object System.Drawing.Font($font, 8.5)
    $hint.Location = New-Object System.Drawing.Point(28, 178); $hint.Size = New-Object System.Drawing.Size(424, 22)
    $w = New-Object System.Windows.Forms.Label
    $w.Text = $Txt.once
    $w.BackColor = C '#F6ECD8'; $w.ForeColor = C '#9E6410'
    $w.Font = New-Object System.Drawing.Font($font, 9.5, [System.Drawing.FontStyle]::Bold); $w.TextAlign = 'MiddleLeft'
    $w.Location = New-Object System.Drawing.Point(28, 214); $w.Size = New-Object System.Drawing.Size(424, 56)
    $yes = New-Object System.Windows.Forms.Button
    $yes.Text = $Txt.yes; $yes.FlatStyle = 'Flat'; $yes.FlatAppearance.BorderSize = 0
    $yes.BackColor = C '#2A43C0'; $yes.ForeColor = [System.Drawing.Color]::White; $yes.Cursor = 'Hand'
    $yes.Location = New-Object System.Drawing.Point(104, 294); $yes.Size = New-Object System.Drawing.Size(176, 42)
    $yes.DialogResult = 'Yes'
    $no = New-Object System.Windows.Forms.Button
    $no.Text = $Txt.no; $no.FlatStyle = 'Flat'; $no.FlatAppearance.BorderColor = C '#C5CAC4'
    $no.BackColor = [System.Drawing.Color]::White; $no.ForeColor = C '#171B19'; $no.Cursor = 'Hand'
    $no.Location = New-Object System.Drawing.Point(290, 294); $no.Size = New-Object System.Drawing.Size(162, 42)
    $no.DialogResult = 'No'
    # Esc or the window's close button: nothing is decided, so Weisy does not start and creates nothing (asked again next time)
    $f.KeyPreview = $true
    $f.Add_KeyDown({ if ($_.KeyCode -eq 'Escape') { $f.DialogResult = 'Cancel'; $f.Close() } })
    $f.Controls.AddRange(@($t, $b, $lh, $loc, $chg, $hint, $w, $yes, $no))
    if ($Preview) {
        $f.Show(); $f.Refresh()
        $bmp = New-Object System.Drawing.Bitmap($f.Width, $f.Height)
        $f.DrawToBitmap($bmp, (New-Object System.Drawing.Rectangle(0, 0, $f.Width, $f.Height)))
        $bmp.Save($Preview); $f.Close(); return 'preview'
    }
    $f.Activate()
    return [string]$f.ShowDialog()
}

if ($Preview) { [void](Show-Dialog); exit 0 }
if (Test-Path -LiteralPath $mark) { exit 0 }         # already asked for this program folder
$answer = Show-Dialog
if ($answer -ne 'Yes' -and $answer -ne 'No') { exit 3 }   # closed without choosing: start.bat stops, nothing written
# keep the chosen data folder (the default needs no pointer)
if ($script:location -ne $base) {
    try {
        New-Item -ItemType Directory -Force -Path $script:location | Out-Null
        Write-Text $pointer $script:location
    } catch {
        [void][System.Windows.Forms.MessageBox]::Show($Txt.fallback, 'Weisy')
        if (Test-Path -LiteralPath $pointer) { Remove-Item -LiteralPath $pointer -Force }
    }
} elseif (Test-Path -LiteralPath $pointer) { Remove-Item -LiteralPath $pointer -Force }
if ($answer -ne 'Yes') { Write-Text $mark 'no'; exit 0 }
try {
    $lnk = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) ($Txt.name + '.lnk')))
    $lnk.TargetPath = $target
    $lnk.WorkingDirectory = $folder
    if ($env:WEISY_TARGET) { $lnk.IconLocation = "$target,0" }   # the .exe carries the paw icon itself
    else { $lnk.IconLocation = (Join-Path $assets 'icon.ico'); $lnk.WindowStyle = 7 }   # start.bat: minimised, the console is only a flash
    $lnk.Save()
    Write-Text $mark 'yes'
} catch { exit 1 }

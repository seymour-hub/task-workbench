$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$Root = Split-Path -Parent $PSScriptRoot
$Assets = Join-Path $Root "assets"
New-Item -ItemType Directory -Force -Path $Assets | Out-Null

# Render at 4x the largest icon size, then downsample with high quality.
$S = 1024
$bmp = New-Object System.Drawing.Bitmap($S, $S, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
$g.Clear([System.Drawing.Color]::Transparent)

function New-RoundedRectPath([float]$x, [float]$y, [float]$w, [float]$h, [float]$r) {
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $d = $r * 2
    $path.AddArc($x, $y, $d, $d, 180, 90)
    $path.AddArc($x + $w - $d, $y, $d, $d, 270, 90)
    $path.AddArc($x + $w - $d, $y + $h - $d, $d, $d, 0, 90)
    $path.AddArc($x, $y + $h - $d, $d, $d, 90, 90)
    $path.CloseFigure()
    return $path
}

$margin = 48
$tileSize = $S - ($margin * 2)
$tile = New-RoundedRectPath $margin $margin $tileSize $tileSize 208

$c1 = [System.Drawing.Color]::FromArgb(255, 118, 145, 255)
$c2 = [System.Drawing.Color]::FromArgb(255, 56, 80, 222)
$brush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
    $tile.GetBounds(),
    $c1,
    $c2,
    [System.Drawing.Drawing2D.LinearGradientMode]::ForwardDiagonal
)
$g.FillPath($brush, $tile)

# Top sheen for a bit of depth.
$g.SetClip($tile)
$sheenRect = New-Object System.Drawing.RectangleF(0, 0, $S, [float]($S * 0.62))
$sheen = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
    $sheenRect,
    [System.Drawing.Color]::FromArgb(58, 255, 255, 255),
    [System.Drawing.Color]::FromArgb(0, 255, 255, 255),
    [System.Drawing.Drawing2D.LinearGradientMode]::Vertical
)
$g.FillRectangle($sheen, $sheenRect)
$g.ResetClip()

$borderPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(56, 255, 255, 255), 6)
$g.DrawPath($borderPen, $tile)

# Checkmark: soft shadow, then solid white.
$points = [System.Drawing.PointF[]]@(
    (New-Object System.Drawing.PointF(268, 552)),
    (New-Object System.Drawing.PointF(448, 712)),
    (New-Object System.Drawing.PointF(762, 372))
)

function New-CheckPen([System.Drawing.Color]$color, [float]$width) {
    $pen = New-Object System.Drawing.Pen($color, $width)
    $pen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $pen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
    $pen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
    return $pen
}

$checkPen = New-CheckPen ([System.Drawing.Color]::White) 112
$g.DrawLines($checkPen, $points)

$g.Dispose()
$checkPen.Dispose()
$borderPen.Dispose()
$brush.Dispose()
$sheen.Dispose()

$sizes = @(256, 128, 64, 48, 32, 24, 16)
$tmp = Join-Path $env:TEMP "workbench-icon-build"
if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

$attributes = New-Object System.Drawing.Imaging.ImageAttributes
$attributes.SetWrapMode([System.Drawing.Drawing2D.WrapMode]::TileFlipXY)

$frames = @()
foreach ($size in $sizes) {
    $small = New-Object System.Drawing.Bitmap($size, $size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $sg = [System.Drawing.Graphics]::FromImage($small)
    $sg.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $sg.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $sg.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $sg.Clear([System.Drawing.Color]::Transparent)
    $dest = New-Object System.Drawing.Rectangle(0, 0, $size, $size)
    $sg.DrawImage($bmp, $dest, 0, 0, $S, $S, [System.Drawing.GraphicsUnit]::Pixel, $attributes)
    $sg.Dispose()

    $file = Join-Path $tmp "icon-$size.png"
    $small.Save($file, [System.Drawing.Imaging.ImageFormat]::Png)
    $small.Dispose()
    $frames += [pscustomobject]@{
        Size  = $size
        Bytes = [System.IO.File]::ReadAllBytes($file)
    }
}

# Build a multi-resolution .ico (PNG frames, supported by Windows Vista+).
$icoPath = Join-Path $Assets "app.ico"
$stream = [System.IO.File]::Create($icoPath)
$writer = New-Object System.IO.BinaryWriter($stream)

$writer.Write([uint16]0)
$writer.Write([uint16]1)
$writer.Write([uint16]$frames.Count)

$offset = 6 + (16 * $frames.Count)
foreach ($frame in $frames) {
    $dimension = if ($frame.Size -ge 256) { 0 } else { $frame.Size }
    $writer.Write([byte]$dimension)
    $writer.Write([byte]$dimension)
    $writer.Write([byte]0)
    $writer.Write([byte]0)
    $writer.Write([uint16]1)
    $writer.Write([uint16]32)
    $writer.Write([uint32]$frame.Bytes.Length)
    $writer.Write([uint32]$offset)
    $offset += $frame.Bytes.Length
}
foreach ($frame in $frames) {
    $writer.Write($frame.Bytes)
}
$writer.Flush()
$writer.Close()
$stream.Close()

# Also keep a 256px PNG for docs / README.
$frames | Where-Object { $_.Size -eq 256 } | ForEach-Object {
    [System.IO.File]::WriteAllBytes((Join-Path $Assets "app-icon.png"), $_.Bytes)
}

Remove-Item -Recurse -Force $tmp
$bmp.Dispose()

Write-Host "Icon written to $icoPath"

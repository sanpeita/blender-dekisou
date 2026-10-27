Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;public class WinRect{[StructLayout(LayoutKind.Sequential)]public struct RECT{public int Left;public int Top;public int Right;public int Bottom;}[DllImport("user32.dll")]public static extern bool GetWindowRect(IntPtr hWnd,out RECT r);[DllImport("user32.dll")]public static extern bool SetForegroundWindow(IntPtr hWnd);}'
$p = Get-Process -Name blender -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { Write-Output "NO_BLENDER"; exit 1 }
$r = New-Object WinRect+RECT
[void][WinRect]::GetWindowRect($p.MainWindowHandle, [ref]$r)
$w = $r.Right - $r.Left
$h = $r.Bottom - $r.Top
$w = $w - ($w % 2)
$h = $h - ($h % 2)
Write-Output ("RECT {0} {1} {2} {3}" -f $r.Left, $r.Top, $w, $h)

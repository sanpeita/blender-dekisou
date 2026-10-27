Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;public class WinTop{[DllImport("user32.dll")]public static extern bool SetWindowPos(IntPtr hWnd,IntPtr after,int X,int Y,int cx,int cy,uint flags);[DllImport("user32.dll")]public static extern bool ShowWindow(IntPtr hWnd,int n);[DllImport("user32.dll")]public static extern bool SetForegroundWindow(IntPtr hWnd);[DllImport("user32.dll")]public static extern IntPtr GetForegroundWindow();[DllImport("user32.dll")]public static extern bool GetWindowRect(IntPtr hWnd,out RECT r);[StructLayout(LayoutKind.Sequential)]public struct RECT{public int Left;public int Top;public int Right;public int Bottom;}}'
$p = Get-Process -Name blender -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $p) { Write-Output "NO_BLENDER"; exit 1 }
$h = $p.MainWindowHandle
[void][WinTop]::ShowWindow($h, 3)
Start-Sleep -Milliseconds 300
# HWND_TOPMOST=-1, SWP_NOMOVE|SWP_NOSIZE|SWP_SHOWWINDOW = 0x0001|0x0002|0x0040
[void][WinTop]::SetWindowPos($h, [IntPtr]::new(-1), 0,0,0,0, 0x0043)
[void][WinTop]::SetForegroundWindow($h)
Start-Sleep -Milliseconds 900
$fg = [WinTop]::GetForegroundWindow()
$r = New-Object WinTop+RECT
[void][WinTop]::GetWindowRect($h, [ref]$r)
$w = $r.Right - $r.Left; $hh = $r.Bottom - $r.Top
$w = $w - ($w % 2); $hh = $hh - ($hh % 2)
Write-Output ("HWND {0} FG {1} RECT {2} {3} {4} {5}" -f $h, $fg, $r.Left, $r.Top, $w, $hh)

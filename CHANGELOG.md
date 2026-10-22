# Changelog / 更新记录

Each version: 中文 first, then English. The release workflow copies the section of the version being released
into the GitHub release notes, so keep the heading format `## v<version> (<date>)`.

## v0.2.2 (2026-10-22)

**中文**
- 项目的 GitHub 地址改为 `github.com/ellach123/weisy-daily-desk`（账号改名）。README 里的下载链接和程序文件属性里的发布者名称已同步更新。功能没有变化。

**English**
- The project moved to `github.com/ellach123/weisy-daily-desk` (account renamed). The download links in the README and
  the publisher name in the program's file properties are updated to match. No functional changes.

## v0.2.1 (2026-10-14)

**中文**
- 修复：桌面快捷方式和程序的图标在部分电脑上显示为空白。原因是图标文件里所有尺寸都用了 PNG 压缩，Windows 桌面在某些图标大小下读不出来；现在按 Windows 的规范，小尺寸用位图格式，只有 256 像素用 PNG。
- README：写清楚怎样从 Releases 页面下载（点 Assets 里的 zip，不用下载 Source code），以及关掉窗口后约 10 秒才能删除程序文件夹。

**English**
- Fixed: the desktop shortcut and the program could show a blank icon on some computers. Every size in the icon file was
  PNG-compressed, which the Windows desktop cannot read at some icon sizes; small sizes are now bitmaps as Windows expects,
  and only the 256 px size is PNG.
- README: step-by-step download from the Releases page (the zip under Assets, not "Source code"), and wait about
  10 seconds after closing the window before deleting the program folder.

## v0.2.0 (2026-10-14)

**中文**
- 新增 **Windows 免安装版**：下载 `Weisy-v0.2.0-windows.zip`，解压，双击 `Weisy-daily-desk.exe` 即可使用，不需要安装 Python。
- 新增 README 动图：勾掉一项，小老鼠庆祝。
- 版本号统一：页面左上角、导出的备份和下载文件名都显示同一个版本号。
- 发布方式：每个版本由 GitHub Actions 从公开的源代码自动打包、测试并发布，同时附带这份更新记录。
- 改进：页面里"程序已停止"等提示会说明用 `Weisy-daily-desk.exe` 还是 `start.bat` 重新打开。

**English**
- New **Windows package, no Python needed**: download `Weisy-v0.2.0-windows.zip`, unzip it and double-click `Weisy-daily-desk.exe`.
- New README animation: tick an item off and the mouse cheers.
- One version number everywhere: the page header, exported backups and the download name.
- Releases: every version is packaged, tested and published by GitHub Actions straight from the public source code,
  with these notes attached.
- The page's "program stopped" hints now mention `Weisy-daily-desk.exe` as well as `start.bat`.

## v0.1.0 (2026-10-14)

**中文**
- 第一个公开版本：今日清单、看板、任务（里程碑和自动进展日志）、副业和习惯打卡，完全在自己电脑上运行。
- 第一次打开时选择数据保存位置和是否创建桌面图标；关窗口后程序几秒内自动退出。
- 程序自己的记录只放在程序文件夹的 `.weisy` 里，不会在别处留下文件。

**English**
- First public version: today list, board, tasks (milestones and an automatic progress log), side projects and habits,
  running entirely on your own computer.
- The first start asks where to keep the data and whether to add a desktop icon; closing the window stops the program
  within seconds.
- Weisy's own notes stay in `.weisy` inside the program folder; nothing is left anywhere else.

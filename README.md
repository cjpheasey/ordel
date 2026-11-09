<picture>
  <source media="(prefers-color-scheme: dark)" srcset="brand/final/ordel-lockup-horizontal-reversed.svg">
  <img src="brand/final/ordel-lockup-horizontal.svg" width="320" alt="Ordel">
</picture>

I mix in REAPER and got tired of scrolling through long lists of plugin names. Ordel shows every plugin you own as a picture of its actual interface, sorted into categories, so you can find them by sight. Click one and it goes straight onto the selected track in REAPER.

![Ordel showing a library of plugins as pictures](docs/screenshots/ordel-library.jpg)

**[Download Ordel for Windows](https://github.com/cjpheasey/ordel/releases/latest/download/Ordel-Setup.exe)** (free, needs REAPER)

## What it does

- Takes a picture of each of your plugins and sorts them into categories like EQ, Dynamics and Reverb
- Press **Ctrl+Shift+Space** anywhere to open it, type to search, and click to add a plugin to your track
- Save the plugins on a track as a chain and add the whole chain to other tracks in one click
- Four themes to choose from

![Searching for a plugin and adding it to a track](docs/screenshots/walkthrough.gif)

## Installing

Run `Ordel-Setup.exe`. Windows might warn you because the app isn't signed yet: click **More info**, then **Run anyway**. When Ordel opens it finds your plugins, connects to REAPER and offers to take the pictures.

You need Windows 10 or 11 and REAPER.

## About

I built this with help from Claude, as a project for my CV and for my own mixing. It's written in Python with a small Lua script that runs inside REAPER.

Copyright © 2026 Charlie Pheasey. See [LICENSE](LICENSE).

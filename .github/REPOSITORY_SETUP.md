# GitHub Repository Setup & Maintainer Guide

This guide outlines the recommended GitHub repository settings, metadata, and social assets to maximize discoverability and community onboarding for the **C64U Antigravity Bridge**.

---

## 1. Repository Description & Details

Under repository **Settings** → **General** (or the "About" gear on the main repo page):

* **Description**:
  > AI-assisted development bridge connecting Google Antigravity to physical Commodore 64 Ultimate hardware via MCP, REST and DMA.
* **Website**:
  > https://github.com/asteng88/c64u-antigravity-bridge
* **Include in the home page**: Check *Releases*, *Packages*, and *Environments* as appropriate.

---

## 2. Recommended GitHub Topics

GitHub allows up to 20 topics per repository (lowercase alphanumeric characters and dashes). Apply the following prioritized 17 topics:

```text
commodore-64
c64
c64u
ultimate64
6502
6510
retrocomputing
homebrew
mcp
model-context-protocol
antigravity
ai-coding
kickassembler
vic-ii
sid
python
fpga
```

### Why These Topics?
* **Hardware & Architecture**: `commodore-64`, `c64`, `c64u`, `ultimate64`, `6502`, `6510`, `fpga` connect retro-hardware and Ultimate-64 enthusiasts directly.
* **Modern Agent & AI Tooling**: `mcp`, `model-context-protocol`, `antigravity`, `ai-coding` attract developers exploring Model Context Protocol agents and agentic software creation.
* **Toolchain & Subsystems**: `kickassembler`, `python`, `vic-ii`, `sid`, `retrocomputing`, `homebrew` match searches for 6502 demo coding, chip music, and retro dev tools.

---

## 3. Enable GitHub Discussions

Enable **Discussions** under **Settings** → **Features** → **Discussions**.

Recommended Discussion Categories:
* 📣 **Announcements**: New releases, feature drops, major toolchain updates.
* 🖥️ **Hardware & Firmware Compatibility**: Community reports testing Ultimate 64, Ultimate-II+, and various firmware versions (3.11, 3.12, beta).
* 🎨 **Show & Tell / Demos**: Share C64 games, demos, raster bars, and SID tunes authored with the bridge and Antigravity.
* 💡 **Ideas & Q&A**: Workflow ideas, prompt patterns, and general support.

---

## 4. GitHub Social Preview Image Recommendation

Under **Settings** → **General** → **Social preview**, upload a 1280×640 PNG/JPEG image.

### Recommended Layout Concept:
* **Left Third**: Antigravity IDE / AI prompt window (e.g. prompt: *"Create raster split, compile, deploy to C64U, inspect screen"*).
* **Center**: Clean architectural diagram showing bidirectional MCP / DMA / REST communication.
* **Right Third**: Authentic Commodore 64 Ultimate screen (blue boot screen or Heliscape action).
* **Top Headline**:
  > **AI → 6502 → Real C64 Hardware**
* **Subheading**:
  > **Write • Compile • DMA Deploy • Inspect • Iterate**

*(Note: Do not use protected corporate trademarks or logos without proper attribution/licensing; use stylized generic or authentic PETSCII typography.)*

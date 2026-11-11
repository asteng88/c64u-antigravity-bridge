"""
Backwards-compatible module shim for `c64u_bridge.tui`.

The IDE hub has been renamed to **C64 Studio** (`c64u_bridge.c64_studio`).
All classes, dialogs, helpers, and `main()` are re-exported here so existing
scripts, entry points, monkeypatches, and imports (`from c64u_bridge.tui import ...`)
continue working without modification.
"""

from __future__ import annotations

import webbrowser
from tkinter import filedialog

from .c64_studio import (
    ASM_COMMENT_PATTERN,
    ASM_DIRECTIVES_PATTERN,
    ASM_HEX_PATTERN,
    ASM_HW_PATTERN,
    ASM_LABEL_PATTERN,
    ASM_OPCODES_PATTERN,
    C64PythonToAsmApp,
    C64StudioApp,
    C_COMMENT_PATTERN,
    C_HW_PATTERN,
    C_KEYWORDS_PATTERN,
    C_PREPROC_PATTERN,
    NEW_ASM_TEMPLATE,
    NEW_C_TEMPLATE,
    NEW_PY_TEMPLATE,
    PY_COMMENT_PATTERN,
    PY_INTRINSICS_PATTERN,
    PY_KEYWORDS_PATTERN,
    STRING_PATTERN,
    AgySetupModal,
    CopyrightCautionModal,
    DecompileScopeModal,
    DiskSelectModal,
    FilteredDirectoryTree,
    KickAssUpdateModal,
    KeyBindingDef,
    OpenFileModal,
    center_popup,
    default_target_dir,
    main,
)

__all__ = [
    "C64StudioApp",
    "C64PythonToAsmApp",
    "AgySetupModal",
    "CopyrightCautionModal",
    "DecompileScopeModal",
    "DiskSelectModal",
    "FilteredDirectoryTree",
    "KickAssUpdateModal",
    "KeyBindingDef",
    "OpenFileModal",
    "NEW_ASM_TEMPLATE",
    "NEW_C_TEMPLATE",
    "NEW_PY_TEMPLATE",
    "ASM_OPCODES_PATTERN",
    "ASM_DIRECTIVES_PATTERN",
    "ASM_HEX_PATTERN",
    "ASM_HW_PATTERN",
    "ASM_LABEL_PATTERN",
    "ASM_COMMENT_PATTERN",
    "STRING_PATTERN",
    "PY_KEYWORDS_PATTERN",
    "PY_INTRINSICS_PATTERN",
    "PY_COMMENT_PATTERN",
    "C_KEYWORDS_PATTERN",
    "C_PREPROC_PATTERN",
    "C_HW_PATTERN",
    "C_COMMENT_PATTERN",
    "center_popup",
    "default_target_dir",
    "filedialog",
    "webbrowser",
    "main",
]

if __name__ == "__main__":
    main()

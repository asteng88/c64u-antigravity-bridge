"""
Python to MOS 6502 Assembly Transpiler for Commodore 64.
Parses a high-level Python AST and generates clean, optimized 6502 assembly
compatible with KickAssembler and ACME cross-assemblers.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


# Standard Commodore 64 hardware memory addresses and constants
C64_CONSTANTS: Dict[str, int] = {
    # VIC-II
    "VIC_BORDER": 0xD020,
    "VIC_BG": 0xD021,
    "VIC_BG0": 0xD021,
    "VIC_BG1": 0xD022,
    "VIC_BG2": 0xD023,
    "VIC_BG3": 0xD024,
    "RASTER": 0xD012,
    "VIC_CTRL1": 0xD011,
    "VIC_CTRL2": 0xD016,
    "VIC_SPRITE_ENABLE": 0xD015,
    "VIC_SPRITE_X0": 0xD000,
    "VIC_SPRITE_Y0": 0xD001,
    "SCREEN_RAM": 0x0400,
    "COLOR_RAM": 0xD800,
    # SID
    "SID_BASE": 0xD400,
    "SID_V1_FREQ_LO": 0xD400,
    "SID_V1_FREQ_HI": 0xD401,
    "SID_V1_PW_LO": 0xD402,
    "SID_V1_PW_HI": 0xD403,
    "SID_V1_CTRL": 0xD404,
    "SID_V1_AD": 0xD405,
    "SID_V1_SR": 0xD406,
    "SID_VOLUME": 0xD418,
    # CIA
    "CIA1_PRA": 0xDC00,
    "CIA1_PRB": 0xDC01,
    # KERNAL vectors
    "CHROUT": 0xFFD2,
    "GETIN": 0xFFE4,
    "SCNKEY": 0xFF9F,
    "PLOT": 0xFFF0,
    # C64 Palette Colors
    "COLOR_BLACK": 0,
    "COLOR_WHITE": 1,
    "COLOR_RED": 2,
    "COLOR_CYAN": 3,
    "COLOR_PURPLE": 4,
    "COLOR_GREEN": 5,
    "COLOR_BLUE": 6,
    "COLOR_YELLOW": 7,
    "COLOR_ORANGE": 8,
    "COLOR_BROWN": 9,
    "COLOR_LIGHT_RED": 10,
    "COLOR_DARK_GREY": 11,
    "COLOR_GREY": 12,
    "COLOR_LIGHT_GREEN": 13,
    "COLOR_LIGHT_BLUE": 14,
    "COLOR_LIGHT_GREY": 15,
}


@dataclass
class TranspileOptions:
    """Configuration options for code generation."""
    assembler: str = "kickass"  # 'kickass' or 'acme'
    start_address: int = 0x0801  # Default BASIC load address
    prg_name: str = "program.prg"
    include_basic_upstart: bool = True
    annotate_source: bool = True
    optimize: bool = True


@dataclass
class TranspileResult:
    """Result of transpiling Python code to 6502 assembly."""
    success: bool
    assembly: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    symbols: Dict[str, Any] = field(default_factory=dict)
    ast_tree: Optional[ast.AST] = None


class PythonTo6502Transpiler(ast.NodeVisitor):
    """AST Visitor that compiles a subset of Python into 6502 assembly."""

    def __init__(self, options: Optional[TranspileOptions] = None):
        self.options = options or TranspileOptions()
        self.code_lines: List[str] = []
        self.data_lines: List[str] = []
        self.subroutines: List[str] = []
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.variables: Dict[str, int] = {}  # var_name -> initial value (0 default)
        self.var_types: Dict[str, str] = {}  # var_name -> 'byte' or 'word'
        self.string_literals: Dict[str, str] = {}  # label -> string content
        self.constants: Dict[str, int] = dict(C64_CONSTANTS)
        self.label_counter: int = 0
        self.loop_stack: List[Tuple[str, str]] = []  # (start_label, exit_label)
        self.in_function: bool = False
        self.current_function_lines: List[str] = []

    def _new_label(self, prefix: str = "lbl") -> str:
        self.label_counter += 1
        return f"{prefix}_{self.label_counter}"

    def _emit(self, line: str, indent: int = 1) -> None:
        target = self.current_function_lines if self.in_function else self.code_lines
        if line.endswith(":") or line.startswith(".") or line.startswith("!"):
            target.append(line)
        else:
            spacing = "    " * indent
            target.append(f"{spacing}{line}")

    def transpile(self, source_code: str) -> TranspileResult:
        """Parse Python source and generate 6502 assembly."""
        self.code_lines = []
        self.data_lines = []
        self.subroutines = []
        self.errors = []
        self.warnings = []
        self.variables = {}
        self.var_types = {}
        self.string_literals = {}
        self.constants = dict(C64_CONSTANTS)
        self.label_counter = 0
        self.loop_stack = []

        try:
            tree = ast.parse(source_code)
        except SyntaxError as se:
            return TranspileResult(
                success=False,
                assembly="",
                errors=[f"Python Syntax Error (Line {se.lineno}, Col {se.offset}): {se.msg}"],
                warnings=[],
                ast_tree=None,
            )

        # First pass: collect constants, variables, strings
        self._analyze_declarations(tree)

        # Second pass: generate code
        self.visit(tree)

        if self.errors:
            return TranspileResult(
                success=False,
                assembly="",
                errors=self.errors,
                warnings=self.warnings,
                symbols=self.variables,
                ast_tree=tree,
            )

        # Assemble full source
        full_asm = self._build_full_assembly()
        return TranspileResult(
            success=True,
            assembly=full_asm,
            errors=[],
            warnings=self.warnings,
            symbols={**self.variables, **self.constants},
            ast_tree=tree,
        )

    def _analyze_declarations(self, tree: ast.AST) -> None:
        """Scan top-level assignments to pre-identify constants vs mutable variables."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name = target.id
                        # If UPPERCASE, treat as constant if assigned to literal int
                        if name.isupper() and isinstance(node.value, ast.Constant) and isinstance(node.value.value, int):
                            self.constants[name] = node.value.value
                        elif name not in self.constants:
                            self.variables[name] = 0
                            self.var_types[name] = "byte"

    def _build_full_assembly(self) -> str:
        out: List[str] = []
        is_kickass = (self.options.assembler == "kickass")

        # Header Comments
        out.append("// =================================================================")
        out.append(f"// Generated by C64U Python-to-6502 Transpiler")
        out.append(f"// Target Assembler: {'KickAssembler' if is_kickass else 'ACME'}")
        out.append(f"// Start Address:    ${self.options.start_address:04X}")
        out.append("// =================================================================")
        out.append("")

        if is_kickass:
            if self.options.include_basic_upstart and self.options.start_address == 0x0801:
                out.append("BasicUpstart2(start)")
                out.append("")
                out.append('* = $0810 "Main Program"')
            else:
                out.append(f'* = ${self.options.start_address:04X} "Main Program"')
        else:
            # ACME syntax
            out.append(f'!to "{self.options.prg_name}", cbm')
            if self.options.include_basic_upstart and self.options.start_address == 0x0801:
                out.append('* = $0801')
                out.append('!byte $0c, $08, $0a, $00, $9e, $20, $32, $30, $36, $34, $00, $00, $00')
                out.append('* = $0810')
            else:
                out.append(f'* = ${self.options.start_address:04X}')

        out.append("")
        out.append("// Constant Definitions")
        for cname, cval in sorted(self.constants.items()):
            if is_kickass:
                out.append(f'.const {cname} = ${cval:04X}' if cval > 255 else f'.const {cname} = ${cval:02X}')
            else:
                out.append(f'{cname} = ${cval:04X}' if cval > 255 else f'{cname} = ${cval:02X}')

        out.append("")
        out.append("start:")
        # Main program statements
        out.extend(self.code_lines)
        out.append("    rts                     // Return to BASIC / KERNAL")
        out.append("")

        # Subroutines
        if self.subroutines:
            out.append("// -----------------------------------------------------------------")
            out.append("// User Subroutines")
            out.append("// -----------------------------------------------------------------")
            out.extend(self.subroutines)
            out.append("")

        # String Literals
        if self.string_literals:
            out.append("// -----------------------------------------------------------------")
            out.append("// String Literals")
            out.append("// -----------------------------------------------------------------")
            for label, text in self.string_literals.items():
                sanitized = text.replace('"', '\\"')
                if is_kickass:
                    out.append(f'{label}: .text "{sanitized}"')
                    out.append(f'        .byte 0')
                else:
                    out.append(f'{label} !text "{sanitized}"')
                    out.append(f'        !byte 0')
            out.append("")

        # Data & Variable segment
        if self.variables:
            out.append("// -----------------------------------------------------------------")
            out.append("// Variables / Data Storage")
            out.append("// -----------------------------------------------------------------")
            for vname in sorted(self.variables.keys()):
                vtype = self.var_types.get(vname, "byte")
                if is_kickass:
                    directive = ".word" if vtype == "word" else ".byte"
                    out.append(f'var_{vname}: {directive} $00')
                else:
                    directive = "!word" if vtype == "word" else "!byte"
                    out.append(f'var_{vname} {directive} $00')
            out.append("")

        return "\n".join(out)

    # -------------------------------------------------------------------------
    # Node Visitor Handlers
    # -------------------------------------------------------------------------

    def visit_Module(self, node: ast.Module) -> None:
        for stmt in node.body:
            self.visit(stmt)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Handle Python function definitions as 6502 subroutines."""
        func_name = node.name
        self.in_function = True
        self.current_function_lines = [f"{func_name}:"]
        
        for stmt in node.body:
            self.visit(stmt)
            
        self.current_function_lines.append("    rts")
        self.current_function_lines.append("")
        self.subroutines.extend(self.current_function_lines)
        self.in_function = False
        self.current_function_lines = []

    def visit_Assign(self, node: ast.Assign) -> None:
        """Handle assignment: var = expr or CONST = expr."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                name = target.id
                # Skip uppercase constant assignments already handled
                if name.isupper() and name in self.constants:
                    continue

                self._emit(f"// Python: {ast.unparse(node)}")
                self._compile_expression(node.value)
                self._emit(f"sta var_{name}")
            else:
                self.warnings.append(f"Unsupported assignment target: {type(target).__name__}")

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        """Handle in-place operators: x += 1, x -= 1, etc."""
        if not isinstance(node.target, ast.Name):
            self.errors.append("AugAssign only supported on simple variable names")
            return

        name = node.target.id
        self._emit(f"// Python: {ast.unparse(node)}")
        
        # Optimized inc/dec for +/- 1
        if isinstance(node.value, ast.Constant) and node.value.value == 1:
            if isinstance(node.op, ast.Add):
                self._emit(f"inc var_{name}")
                return
            elif isinstance(node.op, ast.Sub):
                self._emit(f"dec var_{name}")
                return

        # General accumulator math
        self._emit(f"lda var_{name}")
        if isinstance(node.op, ast.Add):
            self._emit("clc")
            self._compile_adc_operand(node.value)
        elif isinstance(node.op, ast.Sub):
            self._emit("sec")
            self._compile_sbc_operand(node.value)
        elif isinstance(node.op, ast.BitAnd):
            self._compile_and_operand(node.value)
        elif isinstance(node.op, ast.BitOr):
            self._compile_ora_operand(node.value)
        elif isinstance(node.op, ast.BitXor):
            self._compile_eor_operand(node.value)
        else:
            self.errors.append(f"Unsupported AugAssign operator: {type(node.op).__name__}")
            return

        self._emit(f"sta var_{name}")

    def visit_Expr(self, node: ast.Expr) -> None:
        """Handle standalone expressions, mainly function calls or asm."""
        if isinstance(node.value, ast.Call):
            self._compile_call(node.value)
        elif isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            # Docstrings or comments
            pass
        else:
            self.warnings.append(f"Ignored standalone expression: {ast.unparse(node)}")

    def visit_If(self, node: ast.If) -> None:
        """Handle if / elif / else statements."""
        self._emit(f"// Python: if {ast.unparse(node.test)}")
        else_label = self._new_label("else")
        end_label = self._new_label("endif")

        # Compile conditional branch: branch to else_label if condition is FALSE
        self._compile_conditional_branch(node.test, branch_if_true=False, target_label=else_label)

        # Then-body
        for stmt in node.body:
            self.visit(stmt)

        if node.orelse:
            self._emit(f"jmp {end_label}")
            self._emit(f"{else_label}:")
            for stmt in node.orelse:
                self.visit(stmt)
            self._emit(f"{end_label}:")
        else:
            self._emit(f"{else_label}:")

    def visit_While(self, node: ast.While) -> None:
        """Handle while loops (including while True:)."""
        start_label = self._new_label("while_start")
        exit_label = self._new_label("while_exit")
        self.loop_stack.append((start_label, exit_label))

        self._emit(f"{start_label}:")
        self._emit(f"// Python: while {ast.unparse(node.test)}")

        # Check for infinite loop: while True: or while 1:
        is_infinite = False
        if isinstance(node.test, ast.Constant) and bool(node.test.value) is True:
            is_infinite = True

        if not is_infinite:
            self._compile_conditional_branch(node.test, branch_if_true=False, target_label=exit_label)

        for stmt in node.body:
            self.visit(stmt)

        self._emit(f"jmp {start_label}")
        self._emit(f"{exit_label}:")
        self.loop_stack.pop()

    def visit_For(self, node: ast.For) -> None:
        """Handle for i in range(...) loops."""
        if not isinstance(node.target, ast.Name):
            self.errors.append("For loop target must be a variable name")
            return

        var_name = node.target.id
        self.variables[var_name] = 0

        # Expect range(...) call
        if not (isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range"):
            self.errors.append("For loop only supports range(...) iteration")
            return

        args = node.iter.args
        start_val = 0
        step_val = 1

        if len(args) == 1:
            stop_node = args[0]
        elif len(args) == 2:
            start_val = self._eval_const(args[0], 0)
            stop_node = args[1]
        elif len(args) == 3:
            start_val = self._eval_const(args[0], 0)
            stop_node = args[1]
            step_val = self._eval_const(args[2], 1)
        else:
            self.errors.append("range() takes 1 to 3 arguments")
            return

        loop_start = self._new_label("for_start")
        loop_exit = self._new_label("for_exit")
        self.loop_stack.append((loop_start, loop_exit))

        self._emit(f"// Python: for {var_name} in {ast.unparse(node.iter)}")
        # Initialize loop variable
        self._emit(f"lda #${start_val:02X}")
        self._emit(f"sta var_{var_name}")

        self._emit(f"{loop_start}:")

        # Execute body
        for stmt in node.body:
            self.visit(stmt)

        # Increment / decrement loop variable
        if step_val == 1:
            self._emit(f"inc var_{var_name}")
        else:
            self._emit(f"lda var_{var_name}")
            self._emit("clc")
            self._emit(f"adc #${step_val:02X}")
            self._emit(f"sta var_{var_name}")

        # Compare with stop limit
        self._emit(f"lda var_{var_name}")
        if isinstance(stop_node, ast.Constant) and isinstance(stop_node.value, int):
            self._emit(f"cmp #${stop_node.value:02X}")
        elif isinstance(stop_node, ast.Name):
            if stop_node.id in self.constants:
                self._emit(f"cmp #{stop_node.id}")
            else:
                self._emit(f"cmp var_{stop_node.id}")
        else:
            self.errors.append(f"Unsupported stop expression in range(): {ast.unparse(stop_node)}")
            return

        self._emit(f"bne {loop_start}")
        self._emit(f"{loop_exit}:")
        self.loop_stack.pop()

    def visit_Break(self, node: ast.Break) -> None:
        if not self.loop_stack:
            self.errors.append("'break' outside loop")
            return
        _, exit_label = self.loop_stack[-1]
        self._emit(f"jmp {exit_label}")

    def visit_Continue(self, node: ast.Continue) -> None:
        if not self.loop_stack:
            self.errors.append("'continue' outside loop")
            return
        start_label, _ = self.loop_stack[-1]
        self._emit(f"jmp {start_label}")

    def visit_Pass(self, node: ast.Pass) -> None:
        self._emit("nop")

    # -------------------------------------------------------------------------
    # Function Calls & C64 Intrinsics
    # -------------------------------------------------------------------------

    def _compile_call(self, node: ast.Call) -> None:
        """Compile builtin intrinsics or user function calls."""
        if not isinstance(node.func, ast.Name):
            self.errors.append(f"Only direct function calls supported: {ast.unparse(node)}")
            return

        func = node.func.id

        # 1. poke(address, value)
        if func == "poke":
            if len(node.args) != 2:
                self.errors.append("poke(addr, val) requires exactly 2 arguments")
                return
            addr_arg, val_arg = node.args[0], node.args[1]
            self._compile_expression(val_arg)
            addr_str = self._resolve_address_str(addr_arg)
            self._emit(f"sta {addr_str}")

        # 2. border_color(color)
        elif func == "border_color":
            if len(node.args) != 1:
                self.errors.append("border_color(c) requires 1 argument")
                return
            self._compile_expression(node.args[0])
            self._emit("sta $D020")

        # 3. background_color(color)
        elif func == "background_color":
            if len(node.args) != 1:
                self.errors.append("background_color(c) requires 1 argument")
                return
            self._compile_expression(node.args[0])
            self._emit("sta $D021")

        # 4. wait_raster(line)
        elif func == "wait_raster":
            line_val = self._eval_const(node.args[0], 0) if node.args else 0
            wait_lbl = self._new_label("raster_wait")
            self._emit(f"{wait_lbl}:")
            self._emit("lda $D012")
            self._emit(f"cmp #${line_val:02X}")
            self._emit(f"bne {wait_lbl}")

        # 5. print_char(ch)
        elif func == "print_char":
            if not node.args:
                self.errors.append("print_char(ch) requires 1 argument")
                return
            self._compile_expression(node.args[0])
            self._emit("jsr $FFD2               // KERNAL CHROUT")

        # 6. print_str("text")
        elif func == "print_str":
            if not node.args or not isinstance(node.args[0], ast.Constant):
                self.errors.append("print_str(\"...\") requires a string literal argument")
                return
            text = str(node.args[0].value)
            str_lbl = self._new_label("str")
            loop_lbl = self._new_label("prt_loop")
            end_lbl = self._new_label("prt_end")
            self.string_literals[str_lbl] = text

            self._emit("ldx #$00")
            self._emit(f"{loop_lbl}:")
            self._emit(f"lda {str_lbl},x")
            self._emit(f"beq {end_lbl}")
            self._emit("jsr $FFD2               // KERNAL CHROUT")
            self._emit("inx")
            self._emit(f"jmp {loop_lbl}")
            self._emit(f"{end_lbl}:")

        # 7. clear_screen(char=32, color=1)
        elif func == "clear_screen":
            char_val = self._eval_const(node.args[0], 32) if len(node.args) > 0 else 32
            color_val = self._eval_const(node.args[1], 1) if len(node.args) > 1 else 1
            clr_lbl = self._new_label("clr_loop")

            self._emit("ldx #$00")
            self._emit(f"{clr_lbl}:")
            self._emit(f"lda #${char_val:02X}")
            self._emit("sta $0400,x")
            self._emit("sta $0500,x")
            self._emit("sta $0600,x")
            self._emit("sta $06e8,x")
            self._emit(f"lda #${color_val:02X}")
            self._emit("sta $D800,x")
            self._emit("sta $D900,x")
            self._emit("sta $DA00,x")
            self._emit("sta $DAe8,x")
            self._emit("inx")
            self._emit(f"bne {clr_lbl}")

        # 8. delay(cycles)
        elif func == "delay":
            cycles = self._eval_const(node.args[0], 255) if node.args else 255
            d1_lbl = self._new_label("dly1")
            d2_lbl = self._new_label("dly2")
            self._emit(f"ldy #${min(255, max(1, cycles // 256)):02X}")
            self._emit(f"{d1_lbl}:")
            self._emit(f"ldx #${min(255, max(1, cycles % 256)):02X}")
            self._emit(f"{d2_lbl}:")
            self._emit("dex")
            self._emit(f"bne {d2_lbl}")
            self._emit("dey")
            self._emit(f"bne {d1_lbl}")

        # 9. asm("raw assembly")
        elif func == "asm" or func == "__asm__":
            if not node.args or not isinstance(node.args[0], ast.Constant):
                self.errors.append("asm(...) requires a string literal")
                return
            for raw_line in str(node.args[0].value).strip().splitlines():
                self._emit(raw_line.strip())

        # 10. sid_tone(freq, waveform, attack_decay, sustain_release)
        elif func == "sid_tone":
            freq = self._eval_const(node.args[0], 0x1125) if len(node.args) > 0 else 0x1125
            wave = self._eval_const(node.args[1], 0x11) if len(node.args) > 1 else 0x11
            ad = self._eval_const(node.args[2], 0x09) if len(node.args) > 2 else 0x09
            sr = self._eval_const(node.args[3], 0x00) if len(node.args) > 3 else 0x00
            
            self._emit("lda #$0F\n    sta $D418           // SID Volume MAX")
            self._emit(f"lda #${freq & 0xFF:02X}\n    sta $D400           // V1 Freq Lo")
            self._emit(f"lda #${(freq >> 8) & 0xFF:02X}\n    sta $D401           // V1 Freq Hi")
            self._emit(f"lda #${ad:02X}\n    sta $D405           // V1 Attack/Decay")
            self._emit(f"lda #${sr:02X}\n    sta $D406           // V1 Sustain/Release")
            self._emit(f"lda #${wave:02X}\n    sta $D404           // V1 Control (Gate On)")

        # 11. User subroutine call: func() -> jsr func
        else:
            self._emit(f"jsr {func}")

    # -------------------------------------------------------------------------
    # Expressions & Conditionals
    # -------------------------------------------------------------------------

    def _compile_expression(self, node: ast.AST) -> None:
        """Evaluate expression and load result into Accumulator (A)."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, int):
                self._emit(f"lda #${node.value & 0xFF:02X}")
            elif isinstance(node.value, bool):
                self._emit(f"lda #${1 if node.value else 0:02X}")
            else:
                self.errors.append(f"Unsupported constant type: {type(node.value)}")

        elif isinstance(node, ast.Name):
            name = node.id
            if name in self.constants:
                val = self.constants[name]
                self._emit(f"lda #${val & 0xFF:02X}")
            elif name in self.variables:
                self._emit(f"lda var_{name}")
            else:
                self.errors.append(f"Undefined variable or constant: {name}")

        elif isinstance(node, ast.BinOp):
            self._compile_binop(node)

        elif isinstance(node, ast.Call):
            # Check for peek(addr)
            if isinstance(node.func, ast.Name) and node.func.id == "peek":
                addr_str = self._resolve_address_str(node.args[0])
                self._emit(f"lda {addr_str}")
            else:
                self._compile_call(node)

        elif isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Invert):  # ~x
                self._compile_expression(node.operand)
                self._emit("eor #$FF")
            elif isinstance(node.op, ast.USub):  # -x
                self._compile_expression(node.operand)
                self._emit("eor #$FF")
                self._emit("clc")
                self._emit("adc #$01")
            else:
                self.errors.append(f"Unsupported unary operator: {type(node.op)}")
        else:
            self.errors.append(f"Unsupported expression node: {type(node).__name__}")

    def _compile_binop(self, node: ast.BinOp) -> None:
        """Compile binary operators: +, -, &, |, ^, <<, >>"""
        self._compile_expression(node.left)

        if isinstance(node.op, ast.Add):
            self._emit("clc")
            self._compile_adc_operand(node.right)
        elif isinstance(node.op, ast.Sub):
            self._emit("sec")
            self._compile_sbc_operand(node.right)
        elif isinstance(node.op, ast.BitAnd):
            self._compile_and_operand(node.right)
        elif isinstance(node.op, ast.BitOr):
            self._compile_ora_operand(node.right)
        elif isinstance(node.op, ast.BitXor):
            self._compile_eor_operand(node.right)
        elif isinstance(node.op, ast.LShift):
            shifts = self._eval_const(node.right, 1)
            for _ in range(min(8, shifts)):
                self._emit("asl")
        elif isinstance(node.op, ast.RShift):
            shifts = self._eval_const(node.right, 1)
            for _ in range(min(8, shifts)):
                self._emit("lsr")
        else:
            self.errors.append(f"Unsupported binary operator: {type(node.op).__name__}")

    def _compile_adc_operand(self, node: ast.AST) -> None:
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            self._emit(f"adc #${node.value & 0xFF:02X}")
        elif isinstance(node, ast.Name) and node.id in self.variables:
            self._emit(f"adc var_{node.id}")
        elif isinstance(node, ast.Name) and node.id in self.constants:
            self._emit(f"adc #{node.id}")
        else:
            self.errors.append(f"Unsupported operand for add: {ast.unparse(node)}")

    def _compile_sbc_operand(self, node: ast.AST) -> None:
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            self._emit(f"sbc #${node.value & 0xFF:02X}")
        elif isinstance(node, ast.Name) and node.id in self.variables:
            self._emit(f"sbc var_{node.id}")
        elif isinstance(node, ast.Name) and node.id in self.constants:
            self._emit(f"sbc #{node.id}")
        else:
            self.errors.append(f"Unsupported operand for sub: {ast.unparse(node)}")

    def _compile_and_operand(self, node: ast.AST) -> None:
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            self._emit(f"and #${node.value & 0xFF:02X}")
        elif isinstance(node, ast.Name) and node.id in self.variables:
            self._emit(f"and var_{node.id}")
        elif isinstance(node, ast.Name) and node.id in self.constants:
            self._emit(f"and #{node.id}")
        else:
            self.errors.append(f"Unsupported operand for AND: {ast.unparse(node)}")

    def _compile_ora_operand(self, node: ast.AST) -> None:
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            self._emit(f"ora #${node.value & 0xFF:02X}")
        elif isinstance(node, ast.Name) and node.id in self.variables:
            self._emit(f"ora var_{node.id}")
        elif isinstance(node, ast.Name) and node.id in self.constants:
            self._emit(f"ora #{node.id}")
        else:
            self.errors.append(f"Unsupported operand for OR: {ast.unparse(node)}")

    def _compile_eor_operand(self, node: ast.AST) -> None:
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            self._emit(f"eor #${node.value & 0xFF:02X}")
        elif isinstance(node, ast.Name) and node.id in self.variables:
            self._emit(f"eor var_{node.id}")
        elif isinstance(node, ast.Name) and node.id in self.constants:
            self._emit(f"eor #{node.id}")
        else:
            self.errors.append(f"Unsupported operand for XOR: {ast.unparse(node)}")

    def _compile_conditional_branch(self, node: ast.AST, branch_if_true: bool, target_label: str) -> None:
        """Evaluate a test expression and branch based on outcome."""
        if isinstance(node, ast.Compare):
            left = node.left
            if len(node.ops) != 1 or len(node.comparators) != 1:
                self.errors.append("Chained comparisons are not supported")
                return

            op = node.ops[0]
            right = node.comparators[0]

            # Load left into accumulator
            self._compile_expression(left)

            # Compare with right
            if isinstance(right, ast.Constant) and isinstance(right.value, int):
                self._emit(f"cmp #${right.value & 0xFF:02X}")
            elif isinstance(right, ast.Name) and right.id in self.variables:
                self._emit(f"cmp var_{right.id}")
            elif isinstance(right, ast.Name) and right.id in self.constants:
                self._emit(f"cmp #{right.id}")
            else:
                self.errors.append(f"Unsupported comparison target: {ast.unparse(right)}")
                return

            # Emit conditional branch instructions
            # In 6502 CMP:
            # == : beq
            # != : bne
            # <  : bcc (Carry clear means A < M)
            # >= : bcs (Carry set means A >= M)
            # >  : bcs and bne
            # <= : bcc or beq

            if isinstance(op, ast.Eq):
                self._emit(f"{'beq' if branch_if_true else 'bne'} {target_label}")
            elif isinstance(op, ast.NotEq):
                self._emit(f"{'bne' if branch_if_true else 'beq'} {target_label}")
            elif isinstance(op, ast.Lt):
                self._emit(f"{'bcc' if branch_if_true else 'bcs'} {target_label}")
            elif isinstance(op, ast.GtE):
                self._emit(f"{'bcs' if branch_if_true else 'bcc'} {target_label}")
            elif isinstance(op, ast.Gt):
                if branch_if_true:
                    skip = self._new_label("skip")
                    self._emit(f"beq {skip}")
                    self._emit(f"bcs {target_label}")
                    self._emit(f"{skip}:")
                else:
                    self._emit(f"bcc {target_label}")
                    self._emit(f"beq {target_label}")
            elif isinstance(op, ast.LtE):
                if branch_if_true:
                    self._emit(f"bcc {target_label}")
                    self._emit(f"beq {target_label}")
                else:
                    skip = self._new_label("skip")
                    self._emit(f"beq {skip}")
                    self._emit(f"bcs {target_label}")
                    self._emit(f"{skip}:")
            else:
                self.errors.append(f"Unsupported comparison operator: {type(op).__name__}")

        elif isinstance(node, ast.Name):
            # Test if variable != 0
            self._compile_expression(node)
            self._emit(f"{'bne' if branch_if_true else 'beq'} {target_label}")
        else:
            self._compile_expression(node)
            self._emit(f"{'bne' if branch_if_true else 'beq'} {target_label}")

    def _resolve_address_str(self, node: ast.AST) -> str:
        """Resolve memory address to an assembly label or hex literal."""
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return f"${node.value:04X}" if node.value > 255 else f"${node.value:02X}"
        elif isinstance(node, ast.Name):
            if node.id in self.constants:
                return node.id
            elif node.id in self.variables:
                return f"var_{node.id}"
            return node.id
        return f"${self._eval_const(node, 0):04X}"

    def _eval_const(self, node: ast.AST, default: int = 0) -> int:
        """Evaluate a constant expression node into an integer."""
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        elif isinstance(node, ast.Name) and node.id in self.constants:
            return self.constants[node.id]
        return default


# =============================================================================
# Ready-to-Run Presets / Demo Programs
# =============================================================================

PRESETS: Dict[str, Dict[str, str]] = {
    "Rainbow Raster Bars": {
        "description": "Synchronizes with the VIC-II raster beam to display dynamic colored raster bars in the screen border.",
        "code": """# C64 Rainbow Raster Bars
# Loops continuously, waiting for raster beam lines and changing the border color

while True:
    # Wait for the start of the visible screen
    wait_raster(50)
    border_color(COLOR_RED)
    
    wait_raster(70)
    border_color(COLOR_ORANGE)
    
    wait_raster(90)
    border_color(COLOR_YELLOW)
    
    wait_raster(110)
    border_color(COLOR_GREEN)
    
    wait_raster(130)
    border_color(COLOR_CYAN)
    
    wait_raster(150)
    border_color(COLOR_BLUE)
    
    wait_raster(170)
    border_color(COLOR_PURPLE)
    
    wait_raster(250)
    border_color(COLOR_BLACK)
""",
    },
    "Screen Matrix Fill": {
        "description": "Fills screen RAM ($0400) and color RAM with alternating characters and colors.",
        "code": """# Screen Matrix Fill Demo
# Writes characters directly into C64 Screen RAM ($0400)

border_color(COLOR_BLACK)
background_color(COLOR_BLACK)

# Clear screen with blank spaces and light green text
clear_screen(32, COLOR_LIGHT_GREEN)

# Print banner via KERNAL
print_str("C64U PYTHON BRIDGE MATRIX DEMO")

# Loop through and poke character codes into screen memory
count = 0
while count < 40:
    poke(0x0428 + count, 81) # PETSCII circle/ball
    poke(0xD828 + count, COLOR_GREEN)
    count += 1
""",
    },
    "Hello World & Border Flash": {
        "description": "Prints greeting text and cycles border colors.",
        "code": """# Hello World & Border Flash
clear_screen(32, COLOR_WHITE)
print_str("HELLO FROM PYTHON TO 6502 BRIDGE!")

color = 0
while color < 16:
    border_color(color)
    delay(2000)
    color += 1

border_color(COLOR_BLUE)
background_color(COLOR_BLUE)
print_str("DONE!")
""",
    },
    "SID Synth Chime": {
        "description": "Initializes the SID sound synthesizer and plays a chime tone.",
        "code": """# SID Voice 1 Tone Player
# Configure SID Volume, Frequency, Waveform and Envelopes

border_color(COLOR_BLACK)
background_color(COLOR_BLACK)
clear_screen(32, COLOR_YELLOW)
print_str("PLAYING SID SOUND CHIME...")

# Play C-5 note (Freq $2258) with Sawtooth wave ($21)
# Attack/Decay $09, Sustain/Release $A0
sid_tone(0x2258, 0x21, 0x09, 0xA0)

delay(5000)

# Release voice (Gate bit 0 = 0)
poke(0xD404, 0x20)
print_str("SOUND FINISHED!")
""",
    },
}

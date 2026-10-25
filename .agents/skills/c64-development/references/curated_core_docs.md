# Curated Core C64 Documentation Index

Use this index before making claims about hardware behavior, instruction timing, ROM interfaces, or disk protocols. It routes to the repository’s curated source set without copying large manuals into the skill context.

## Source precedence

1. **Primary PDFs** in `curated_core_docs/primary-pdfs/` are the authority where applicable.
2. The curated technical documents in `curated_core_docs/text/` provide searchable, task-focused coverage.
3. The other skill references provide concise recipes and project-specific toolchain workflow. Reconcile any conflict in favor of the primary source, then the curated technical document.

The curated collection contains a mix of primary documentation and reference/wiki material. Do not treat its presence as proof that a claim is universal across PAL/NTSC machines, VIC-II revisions, SID revisions, ROM revisions, or C64U configuration. State the applicable variant when it affects code.

## Task routing

| Need | Read first | Then use |
| --- | --- | --- |
| Cycle-exact raster code, bad lines, sprites, DMA, register-write timing | `curated_core_docs/primary-pdfs/VIC-II_Timing.pdf` | `curated_core_docs/text/VIC-II_Article.txt`, then `vic2_graphics.md` |
| VIC-II register overview, chip/revision distinctions, display capabilities | `curated_core_docs/text/VIC-II.md` | `vic2_graphics.md` |
| SID register behavior and 6581/8580 differences | `curated_core_docs/text/SID.md` | `sid_audio.md` |
| `$0001` banking, RAM/ROM/I/O visibility, system memory layout | `curated_core_docs/text/C64_Memory_Map.md` | `c64_memory_and_banking.md` |
| KERNAL jump-table call, flags, registers, file/channel sequencing | `curated_core_docs/text/C64_KERNAL_Functions.md` | `C64_Programmers_Reference_Guide.pdf` or `.txt` for broader system context |
| CIA timers, keyboard/joystick matrix, ICR masks, NMI vs IRQ | `curated_core_docs/text/CIA.md` | `c64_memory_and_banking.md` |
| 6510/6502 opcode addressing modes, flags, lengths, cycle counts | `curated_core_docs/text/6502_Opcodes.md` | Verify page-crossing and branch penalties in the supplied tables |
| IEC electrical/protocol details and device addressing | `curated_core_docs/text/IEC_Serial_Port.md` | `C64_KERNAL_Functions.md` for KERNAL calls |
| 1541 disk layout, DOS commands, drive memory, D64 context | `curated_core_docs/primary-pdfs/Anatomy_of_the_1541_Disk_Drive.pdf` | `curated_core_docs/primary-pdfs/1541_Users_Guide.pdf`, then `text/Commodore_1541.md` |
| Broad official system behavior or schematics | `curated_core_docs/primary-pdfs/C64_Programmers_Reference_Guide.pdf` | `text/C64_Programmers_Reference_Guide.txt` |

## Required implementation checks

* Preserve `$0001` port bits that are unrelated to memory mapping when changing banks; restore the previous value before returning to KERNAL/BASIC code.
* For KERNAL file I/O, follow the documented order (`SETLFS`, `SETNAM`, `OPEN`, then `CHKIN`/`CHKOUT` as needed) and check the documented carry/status results.
* CIA interrupt masks are not simple writable flags: bit 7 selects set versus clear semantics, and reading ICR clears pending interrupt flags. CIA1 is IRQ; CIA2 is NMI.
* Treat IEC as an active-low, open-collector bus. Do not apply RS-232 assumptions.
* Treat VIC-II timing as model-specific. Identify PAL versus NTSC and avoid advertising a timing-sensitive routine as portable unless it has separate timing paths.
* Treat SID filter and digi behavior as chip-revision-dependent; validate on the target hardware when sound quality matters.

## Scope added by the curated collection

The existing skill already covered graphics, SID programming, memory/banking, KickAssembler, and the Python transpiler. The curated collection additionally gives the agent grounded references for KERNAL channels/files, CIA timer/interrupt work, IEC and 1541 programming, instruction timing, and primary-source VIC-II timing. Consult the source documents at task time rather than relying on this index as a replacement for them.

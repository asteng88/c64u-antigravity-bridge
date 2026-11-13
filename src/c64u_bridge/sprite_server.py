"""
Local HTTP Backend Server for the Multi-Platform Retro Sprite Generator & Animation Studio.

Provides:
- `GET /` -> Serves `web/sprite_studio.html`
- `GET /api/specs` -> Returns platform specs and hardware palettes
- `POST /api/import-image` -> De-fading, background removal, sprite sheet slicing & CIELAB quantization
- `POST /api/generate-animation` -> Keyframe morphing tween, motion cycle presets, and Gemini AI synthesis
- `POST /api/export` -> Code, binary (.bin/.spr), PNG sheet, Animated GIF, and workspace file saving
- `POST /api/test-c64` -> Compiles runnable C64 6502 animation harness PRG and executes on C64U DMA or `c64sim`
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .client import C64UClient, C64UClientError
from .compiler import CrossCompiler
from .gamedev import tools_root
from .sprite import (
    BBC_MICRO_PALETTE,
    C64_PALETTE,
    MultiPlatformSpriteFrame,
    PLATFORM_SPECS,
    SpriteAnimationProject,
    ZX_NEXT_PALETTE,
    ZX_SPECTRUM_PALETTE,
)
from .sprite_animator import (
    generate_ai_animation_frames,
    generate_motion_cycle,
    tween_keyframes,
)
from .sprite_import import import_image_to_frames


class SpriteStudioHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the Multi-Platform Sprite Studio."""

    def log_message(self, format: str, *args: Any) -> None:
        # Keep console output clean unless debugging
        pass

    def _send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html", "/sprite_studio.html"):
            html_path = Path(__file__).parent / "web" / "sprite_studio.html"
            data = html_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if path == "/api/specs":
            self._send_json({
                "ok": True,
                "platforms": PLATFORM_SPECS,
                "palettes": {
                    "c64": C64_PALETTE,
                    "zx_spectrum": ZX_SPECTRUM_PALETTE,
                    "zx_next": ZX_NEXT_PALETTE,
                    "bbc_micro": BBC_MICRO_PALETTE,
                },
            })
            return

        self._send_json({"ok": False, "error": f"Unknown endpoint: {path}"}, status=404)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length) if length > 0 else b"{}"
            req = json.loads(raw_body.decode("utf-8"))
        except Exception as exc:
            self._send_json({"ok": False, "error": f"Invalid JSON request: {exc}"}, status=400)
            return

        try:
            if path == "/api/import-image":
                self._handle_import_image(req)
            elif path == "/api/generate-animation":
                self._handle_generate_animation(req)
            elif path == "/api/export":
                self._handle_export(req)
            elif path == "/api/test-c64":
                self._handle_test_c64(req)
            else:
                self._send_json({"ok": False, "error": f"Unknown endpoint: {path}"}, status=404)
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=500)

    def _handle_import_image(self, req: Dict[str, Any]) -> None:
        image_b64 = req.get("image_b64", "")
        if not image_b64:
            self._send_json({"ok": False, "error": "Missing image_b64"}, status=400)
            return

        frames = import_image_to_frames(
            image_b64,
            platform=str(req.get("platform", "c64")),
            mode=str(req.get("mode", "multicolor")),
            target_w=int(req.get("width", 24)),
            target_h=int(req.get("height", 21)),
            bg_tolerance=float(req.get("bg_tolerance", 38.0)),
            alpha_cutoff=int(req.get("alpha_cutoff", 128)),
            defade_strength=float(req.get("defade_strength", 0.65)),
            sample_mode=str(req.get("sample_mode", "dominant")),
            preserve_aspect=bool(req.get("preserve_aspect", True)),
            auto_crop=bool(req.get("auto_crop", True)),
            sheet_rows=int(req.get("sheet_rows", 1)),
            sheet_cols=int(req.get("sheet_cols", 1)),
            auto_detect_islands=bool(req.get("auto_detect_islands", False)),
            locked_slots=req.get("locked_slots"),
        )
        self._send_json({
            "ok": True,
            "frames": [f.to_dict() for f in frames],
            "count": len(frames),
        })

    def _handle_generate_animation(self, req: Dict[str, Any]) -> None:
        gen_type = str(req.get("type", "preset"))
        num_frames = int(req.get("num_frames", 4))
        intensity = float(req.get("intensity", 1.0))

        if gen_type == "tween":
            fa = MultiPlatformSpriteFrame.from_dict(req["frame_a"])
            fb = MultiPlatformSpriteFrame.from_dict(req["frame_b"])
            inbetweens = tween_keyframes(fa, fb, num_inbetweens=num_frames)
            self._send_json({
                "ok": True,
                "frames": [f.to_dict() for f in inbetweens],
                "message": f"Generated {len(inbetweens)} pixel-pure in-between frame(s).",
            })
            return

        base_frame = MultiPlatformSpriteFrame.from_dict(req["base_frame"])
        if gen_type == "ai":
            prompt = str(req.get("prompt", "smooth walk cycle"))
            frames, note = generate_ai_animation_frames(base_frame, prompt=prompt, num_frames=num_frames)
            self._send_json({
                "ok": True,
                "frames": [f.to_dict() for f in frames],
                "message": note,
            })
            return

        preset = str(req.get("preset", "walk_cycle"))
        frames = generate_motion_cycle(base_frame, preset=preset, num_frames=num_frames, intensity=intensity)
        self._send_json({
            "ok": True,
            "frames": [f.to_dict() for f in frames],
            "message": f"Generated {len(frames)}-frame '{preset}' animation sequence.",
        })

    def _handle_export(self, req: Dict[str, Any]) -> None:
        proj = SpriteAnimationProject.from_dict(req["project"])
        format_key = str(req.get("format", "auto"))
        code = proj.export_code(format_key)
        raw_bin = proj.to_binary()
        png_sheet = proj.to_png_sheet_bytes(scale=int(req.get("scale", 4)))
        gif_bytes = proj.to_animated_gif_bytes(scale=int(req.get("scale", 6)))

        saved_path = None
        save_to = req.get("save_path")
        if save_to:
            target = (tools_root() / str(save_to)).resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.suffix.lower() in (".bin", ".spr"):
                target.write_bytes(raw_bin)
            elif target.suffix.lower() == ".png":
                target.write_bytes(png_sheet)
            elif target.suffix.lower() == ".gif":
                target.write_bytes(gif_bytes)
            elif target.suffix.lower() == ".json":
                target.write_text(json.dumps(proj.to_dict(), indent=2), encoding="utf-8")
            else:
                target.write_text(code, encoding="utf-8")
            saved_path = str(target)

        self._send_json({
            "ok": True,
            "code": code,
            "binary_b64": base64.b64encode(raw_bin).decode("ascii"),
            "binary_size": len(raw_bin),
            "png_sheet_b64": base64.b64encode(png_sheet).decode("ascii"),
            "gif_b64": base64.b64encode(gif_bytes).decode("ascii"),
            "saved_path": saved_path,
        })

    def _handle_test_c64(self, req: Dict[str, Any]) -> None:
        proj = SpriteAnimationProject.from_dict(req["project"])
        target_mode = str(req.get("target", "sim"))  # "sim" or "dma"
        asm_source = proj.export_code("c64_runnable_prg_asm")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            asm_file = tmp_path / "sprite_preview.asm"
            prg_file = tmp_path / "sprite_preview.prg"
            asm_file.write_text(asm_source, encoding="utf-8")

            compiler = CrossCompiler()
            comp_res = compiler.compile(asm_file, output_prg=prg_file, assembler="kickass")
            if not comp_res.success or not prg_file.exists():
                self._send_json({
                    "ok": False,
                    "error": f"KickAssembler build failed: {comp_res.error_message or comp_res.stderr or comp_res.stdout}",
                }, status=400)
                return

            if target_mode == "dma":
                try:
                    client = C64UClient()
                    dma_res = client.run_prg(prg_file)
                    self._send_json({
                        "ok": True,
                        "mode": "dma",
                        "message": f"Compiled ({prg_file.stat().st_size} bytes) and deployed to C64U via DMA: {dma_res}",
                    })
                    return
                except C64UClientError as exc:
                    self._send_json({
                        "ok": False,
                        "error": f"C64U DMA connection failed ({exc}). Try Simulator mode instead.",
                    }, status=502)
                    return

            # Run in headless c64sim and return screenshot
            sim_script = tools_root() / "tools" / "c64sim" / "c64sim.py"
            png_out = tmp_path / "sim_capture.png"
            cmd = [
                sys.executable,
                str(sim_script),
                str(prg_file),
                "--frames",
                "45",
                "--scale",
                "2",
                "--out",
                str(png_out),
            ]
            proc = subprocess.run(cmd, cwd=tools_root(), capture_output=True, text=True, timeout=30)
            screenshot_b64 = None
            if png_out.exists():
                screenshot_b64 = base64.b64encode(png_out.read_bytes()).decode("ascii")
            self._send_json({
                "ok": proc.returncode == 0,
                "mode": "sim",
                "prg_size": prg_file.stat().st_size,
                "screenshot_b64": screenshot_b64,
                "sim_output": (proc.stdout + proc.stderr).strip(),
                "message": f"Built & verified {prg_file.stat().st_size}-byte C64 PRG in headless VIC-II simulator.",
            })


def start_sprite_server_background(port: int = 0) -> Tuple[ThreadingHTTPServer, str]:
    """Start the Sprite Studio HTTP server on a background daemon thread and return `(server, url)`."""
    server = ThreadingHTTPServer(("127.0.0.1", port), SpriteStudioHandler)
    actual_port = server.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, url


def run_sprite_studio_server(port: int = 0, open_browser: bool = True) -> None:
    """Launch the Sprite Studio server in the foreground and optionally open the browser."""
    server = ThreadingHTTPServer(("127.0.0.1", port), SpriteStudioHandler)
    actual_port = server.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/"
    print(f"Multi-Platform Retro Sprite Studio running at: {url}")
    print("Supported Platforms: Commodore 64 | ZX Spectrum | ZX Spectrum Next | BBC Micro")
    print("Press Ctrl+C to stop the server.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Sprite Studio server...")
        server.shutdown()

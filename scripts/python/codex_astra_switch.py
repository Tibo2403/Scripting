"""Opt-in Windows desktop switch for Codex through a local LiteLLM Astra route."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request

MODEL = "gpt-6-astra"
PROVIDER = "litellm_astra_switch"
URL = "http://127.0.0.1:4002/v1"
BEGIN = "# BEGIN astra-switch"
END = "# END astra-switch"
ROOT_SETTING = re.compile(r"^\s*(model|model_provider)\s*=")


def root_settings(text: str) -> dict[str, str]:
    """Remember exact root assignments, without copying credentials to state."""
    result = {}
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("["):
            break
        match = ROOT_SETTING.match(line)
        if match:
            result[match[1]] = line
    return result


def replace_settings(text: str, settings: dict[str, str]) -> str:
    lines = text.splitlines(keepends=True)
    root_end = next((i for i, line in enumerate(lines)
                     if line.lstrip().startswith("[")), len(lines))
    root = [line for line in lines[:root_end] if not ROOT_SETTING.match(line)]
    return "".join(value.rstrip("\r\n") + "\n" for value in settings.values()) + "".join(root + lines[root_end:])


def atomic_write(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".astra-tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        stream.write(text)
    os.replace(temporary, path)


class Switch:
    def __init__(self, home: Path) -> None:
        self.home = home
        self.config = home / "config.toml"
        self.state = home / "astra-switch-state.json"
        self.proxy = home / "litellm-proxy"

    def read(self) -> str:
        return self.config.read_bytes().decode("utf-8-sig") if self.config.exists() else ""

    def enabled(self) -> bool:
        return tomllib.loads(self.read()).get("model_provider") == PROVIDER

    def activate(self) -> None:
        text = self.read()
        parsed = tomllib.loads(text)
        if self.enabled():
            if not self.state.exists():
                raise RuntimeError("Missing restore state; configuration left unchanged.")
            return
        if self.state.exists():
            raise RuntimeError("Restore state already exists. Use OFF before enabling again.")
        if PROVIDER in parsed.get("model_providers", {}) or BEGIN in text or END in text:
            raise RuntimeError("A conflicting Astra provider already exists.")
        settings = root_settings(text)
        updated = replace_settings(text, {
            "model": f'model = "{MODEL}"\n',
            "model_provider": f'model_provider = "{PROVIDER}"\n',
        })
        updated += (f'\n{BEGIN}\n[model_providers.{PROVIDER}]\n'
                    f'name = "LiteLLM Astra (local)"\nbase_url = "{URL}"\n'
                    f'wire_api = "responses"\nrequires_openai_auth = false\n{END}\n')
        tomllib.loads(updated)
        self.home.mkdir(parents=True, exist_ok=True)
        atomic_write(self.state, json.dumps({"settings": settings}))
        atomic_write(self.config, updated)

    def deactivate(self) -> None:
        if not self.state.exists():
            if self.enabled():
                raise RuntimeError("Missing restore state; configuration left unchanged.")
            return
        text = self.read()
        data = tomllib.loads(text)
        if data.get("model_provider") != PROVIDER or data.get("model") != MODEL:
            raise RuntimeError("Model settings changed outside the switch. Restore state retained.")
        if text.count(BEGIN) != 1 or text.count(END) != 1:
            raise RuntimeError("Managed provider block changed. Restore state retained.")
        settings = json.loads(self.state.read_text(encoding="utf-8"))["settings"]
        updated = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\r?\n?", "", text, flags=re.S)
        updated = replace_settings(updated, settings)
        tomllib.loads(updated)
        atomic_write(self.config, updated)
        self.state.unlink()

    def probe(self) -> bool:
        try:
            with urllib.request.urlopen(URL + "/models", timeout=2) as response:
                data = json.load(response)
            if not any(item.get("id") == MODEL for item in data["data"]):
                raise RuntimeError("Port 4002 does not advertise GPT-6 Astra.")
            return True
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"Proxy models check failed: HTTP {error.code}") from error
        except urllib.error.URLError:
            return False

    def start(self, api_key: str) -> None:
        if self.probe():
            return
        if not api_key.strip():
            raise RuntimeError("OPENAI_API_KEY is required. Enter it in the masked field.")
        launcher = self.proxy / "start_litellm_proxy.py"
        if not launcher.exists():
            raise RuntimeError(f"LiteLLM installation missing: {launcher}")
        route = self.proxy / "astra-switch.yaml"
        atomic_write(route, 'model_list:\n  - model_name: gpt-6-astra\n'
                     '    litellm_params:\n      model: openai/gpt-6-astra\n'
                     '      api_key: os.environ/OPENAI_API_KEY\n')
        environment = dict(os.environ, OPENAI_API_KEY=api_key, PYTHONUTF8="1")
        with (self.proxy / "astra-switch.log").open("ab") as log:
            process = subprocess.Popen(
                [sys.executable, str(launcher), "--config", str(route),
                 "--host", "127.0.0.1", "--port", "4002"],
                env=environment, cwd=self.proxy, stdout=log, stderr=log,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        try:
            for _ in range(60):
                if process.poll() is not None:
                    raise RuntimeError("LiteLLM exited. See astra-switch.log.")
                if self.probe():
                    return
                time.sleep(0.5)
            raise RuntimeError("LiteLLM did not become ready within the startup timeout.")
        except (RuntimeError, ValueError, OSError):
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
            raise


def gui(switch: Switch) -> None:
    import tkinter as tk
    from tkinter import messagebox, ttk

    window = tk.Tk()
    window.title("Codex | Proxy Astra ON / OFF")
    window.geometry("540x310")
    window.resizable(False, False)
    frame = ttk.Frame(window, padding=24)
    frame.pack(fill="both", expand=True)
    status = tk.StringVar()
    ttk.Label(frame, text="GPT-6 Astra / LiteLLM local", font=("Segoe UI", 16)).pack(anchor="w")
    ttk.Label(frame, textvariable=status).pack(anchor="w", pady=12)
    ttk.Label(frame, text="Cle API OpenAI (memoire uniquement, si proxy arrete)").pack(anchor="w")
    key = ttk.Entry(frame, show="*", width=65)
    key.pack(fill="x", pady=6)
    ttk.Label(frame, text="Apres bascule : relancer Codex et ouvrir une nouvelle tache.\n"
              "OFF restaure Codex. Le service local reste en veille.").pack(anchor="w", pady=8)

    def refresh() -> None:
        status.set("ON : Codex configure via proxy" if switch.enabled() else "OFF : configuration Codex normale")

    def apply(on: bool) -> None:
        try:
            window.config(cursor="watch")
            window.update_idletasks()
            if on:
                switch.start(key.get() or os.environ.get("OPENAI_API_KEY", ""))
                switch.activate()
                key.delete(0, "end")
            else:
                switch.deactivate()
            refresh()
        except (OSError, ValueError, RuntimeError, KeyError) as error:
            messagebox.showerror("Bascule non appliquee", str(error))
        finally:
            window.config(cursor="")

    buttons = ttk.Frame(frame)
    buttons.pack(fill="x", pady=8)
    ttk.Button(buttons, text="ON / Activer le proxy", command=lambda: apply(True)).pack(side="left")
    ttk.Button(buttons, text="OFF / Restaurer Codex", command=lambda: apply(False)).pack(side="right")
    refresh()
    window.mainloop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", choices=["on", "off", "status", "gui"], default="gui")
    args = parser.parse_args()
    switch = Switch(Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))))
    try:
        if args.mode == "gui":
            gui(switch)
        elif args.mode == "on":
            switch.start(os.environ.get("OPENAI_API_KEY", ""))
            switch.activate()
            print("ON. Restart Codex and open a new task.")
        elif args.mode == "off":
            switch.deactivate()
            print("OFF. Codex restored; local proxy remains on standby. Restart Codex.")
        else:
            print("Codex configuration:", "ON" if switch.enabled() else "OFF")
            print("Local Astra endpoint:", "ready" if switch.probe() else "unavailable")
        return 0
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

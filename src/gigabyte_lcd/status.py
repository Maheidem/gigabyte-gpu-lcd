"""Status collection helpers for local inference servers."""

from __future__ import annotations

import json
import subprocess
import urllib.request


def read_model_from_port(port: int) -> str | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=2) as response:
            data = json.load(response)
    except Exception:
        return None
    models = data.get("data") or []
    if not models:
        return None
    return models[0].get("id") or models[0].get("root")


def active_engine_and_model() -> tuple[str, str]:
    for engine, port in (("vLLM", 8082), ("llama.cpp", 8081), ("proxy", 8080)):
        model = read_model_from_port(port)
        if model:
            return engine, model
    return "idle", "no model"


def inference_cpu_percent() -> float:
    try:
        output = subprocess.check_output(["ps", "-eo", "pcpu,args"], text=True)
    except Exception:
        return 0.0
    total = 0.0
    for line in output.splitlines()[1:]:
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        try:
            process_cpu = float(parts[0])
        except ValueError:
            continue
        command = parts[1].lower()
        if any(marker in command for marker in ("vllm", "llama-server", "llama.cpp", "llamacpp")):
            total += process_cpu
    return total


def gpu_vram_and_power() -> tuple[float, float]:
    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,power.draw",
                "--format=csv,noheader,nounits",
            ],
            text=True,
        ).strip()
        memory_text, watts_text = [part.strip() for part in output.split(",")[:2]]
        return float(memory_text) / 1024.0, float(watts_text)
    except Exception:
        return 0.0, 0.0


def inference_status_text() -> str:
    engine, model = active_engine_and_model()
    model_short = model.split("/")[-1]
    cpu = inference_cpu_percent()
    vram_gib, watts = gpu_vram_and_power()
    return "\n".join(
        [
            engine,
            model_short,
            f"CPU {cpu:.0f}% VRAM {vram_gib:.1f}G",
            f"PWR {watts:.0f}W",
        ]
    )

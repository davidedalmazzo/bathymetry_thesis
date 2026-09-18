"""Plot the exact three planned Doppler windows and their PVP time labels."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from umbra_sar.subaperture import make_window


ROOT = Path(__file__).resolve().parents[1]
VANDENBERG = ROOT / 'umbra/Vandenberg'


def main() -> None:
    plan = json.loads(
        (VANDENBERG / "metadata" / "SUBAPERTURE_PLAN_6S.json").read_text(
            encoding="utf-8"
        )
    )
    mapping = json.loads(
        (VANDENBERG / "metadata" / "CPHD_DOPPLER_TIME_MAPPING.json").read_text(
            encoding="utf-8"
        )
    )
    time_by_look = {
        int(item["look_index"]): float(item["effective_early_center_late_s"][1])
        for item in mapping["looks"]
    }
    support = plan["support"]
    spacing = float(support["bin_spacing_per_m"])
    shifted_zero = int(support["fft_size"]) // 2
    figure, axis = plt.subplots(figsize=(10, 5), constrained_layout=True)
    for item in plan["looks"]:
        look = int(item["look_index"])
        band = item["band"]
        window_info = item["window"]
        window, _ = make_window(
            int(window_info["length"]),
            str(window_info["kind"]),
            tukey_alpha=float(window_info["tukey_alpha"]),
            normalization=str(window_info["normalization"]),
        )
        indices = np.arange(int(band["start"]), int(band["stop"]))
        k_col = (indices - shifted_zero) * spacing
        axis.plot(
            k_col,
            window,
            linewidth=1.2,
            label=f"look {look}: PVP center {time_by_look[look]:.3f} s",
        )
    axis.axvline(0, color="0.4", linestyle="--", linewidth=1)
    axis.set_xlabel("SICD Col spatial frequency / Doppler coordinate (cycles/m)")
    axis.set_ylabel("Energy-normalized Tukey weight")
    axis.set_title("Three fixed nominal ~6 s Doppler windows (Tukey α=0.25)")
    axis.grid(True, alpha=0.25)
    axis.legend()
    output = VANDENBERG / "results" / "diagnostics" / "DOPPLER_WINDOWS_6S.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180)
    plt.close(figure)
    print(output)


if __name__ == "__main__":
    main()

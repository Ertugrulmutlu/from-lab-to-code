"""Generate original, shareable gallery and audio results for the README."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from binaural import get_hrir, wav_bytes
from audio_pipeline import SceneSource, render_scene
from correlation import cross_correlate, example_signals, interaural_cues
from synthetic import SAMPLE_RATE, demo_instrument


OUTPUT = Path(__file__).parent / "results"
OUTPUT.mkdir(parents=True, exist_ok=True)


def make_overview() -> None:
    reference, moved = example_signals()
    lags, corr = cross_correlate(reference, moved)
    h_left, _ = get_hrir(90, 0)
    h_right, _ = get_hrir(-90, 0)
    left_itd, left_ild = interaural_cues(h_left, SAMPLE_RATE)
    right_itd, right_ild = interaural_cues(h_right, SAMPLE_RATE)

    fig, ax = plt.subplots(2, 2, figsize=(12, 7), constrained_layout=True)
    fig.patch.set_facecolor("#fafbfd")
    for a in ax.flat:
        a.grid(alpha=0.2)
        a.set_facecolor("#fafbfd")

    ax[0, 0].plot(range(len(reference)), reference, "o-", label="Reference, index 5")
    ax[0, 0].plot(range(len(moved)), moved, "o-", label="Shifted, indices 9 & 14")
    ax[0, 0].set(title="A · Two impulse signals", xlabel="Sample index", ylabel="Amplitude")
    ax[0, 0].legend(fontsize=8)

    ax[0, 1].plot(lags, corr, "o-", color="tab:purple")
    for x, y in [(4, 1), (9, 0.5)]:
        ax[0, 1].annotate(f"{x} samples", (x, y), xytext=(8, 6), textcoords="offset points")
    ax[0, 1].set(title="B · Correlation peaks at +4 and +9", xlabel="Lag (samples)", ylabel="Similarity", ylim=(-0.07, 1.25))

    ms = np.arange(h_left.shape[1]) / SAMPLE_RATE * 1000
    ax[1, 0].plot(ms, h_left[0], label="Left ear")
    ax[1, 0].plot(ms, h_left[1], label="Right ear")
    ax[1, 0].set(title=f"C · +90° left source (ITD {left_itd:.2f} ms)",
                 xlabel="Time (ms)", ylabel="Synthetic HRIR")
    ax[1, 0].legend(fontsize=8)

    ms = np.arange(h_right.shape[1]) / SAMPLE_RATE * 1000
    ax[1, 1].plot(ms, h_right[0], label="Left ear")
    ax[1, 1].plot(ms, h_right[1], label="Right ear")
    ax[1, 1].set(title=f"D · −90° right source (ITD {right_itd:.2f} ms)",
                 xlabel="Time (ms)", ylabel="Synthetic HRIR")
    ax[1, 1].legend(fontsize=8)
    fig.suptitle("From Lab to Code #2 | Correlation → Spatial Audio", fontsize=16, fontweight="bold")
    fig.savefig(OUTPUT / "overview.png", dpi=160)
    plt.close(fig)
    print(f"Generated {OUTPUT / 'overview.png'}")
    print(f"Left: ILD {left_ild:.2f} dB · Right: ILD {right_ild:.2f} dB")


def make_audio() -> None:
    guitar = demo_instrument("guitar")
    horns = demo_instrument("horns")
    scene = render_scene([
        SceneSource("A", guitar, 75, 0, 0),
        SceneSource("B", horns, -75, 0, -3),
    ])
    (OUTPUT / "preview_stereo.wav").write_bytes(wav_bytes(scene.stereo))
    (OUTPUT / "preview_mono.wav").write_bytes(wav_bytes(scene.mono))
    print(f"Generated {OUTPUT / 'preview_stereo.wav'}")
    print(f"Generated {OUTPUT / 'preview_mono.wav'}")


if __name__ == "__main__":
    make_overview()
    make_audio()

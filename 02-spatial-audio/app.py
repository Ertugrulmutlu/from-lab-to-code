"""From Lab to Code #2 | Spatial Audio Playground.

Run: python -m streamlit run app.py

The core audio algorithms are deliberately separate from the Streamlit UI.
The only custom frontend is a small, self-contained drag-to-position stage:
frontend/index.html; all other controls are native Streamlit widgets.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from audio_pipeline import SceneSource, SceneResult, render_scene
from binaural import MAX_SOFA_BYTES, MAX_WAV_BYTES, read_uploaded_wav, wav_bytes
from correlation import cross_correlate, example_signals, nonzero_peaks
from synthetic import SAMPLE_RATE, demo_instrument

ROOT = Path(__file__).resolve().parent
stage_component = components.declare_component("spatial_source_stage", path=str(ROOT / "frontend"))

st.set_page_config(
    page_title="Spatial Audio Playground | From Lab to Code",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Styling is intentionally kept small and local. The audio & signal controls
# are native Streamlit widgets for keyboard access and predictable reruns.
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap');
:root { --sea:#57dccb; --ink:#edf6fb; --muted:#91a8b8; }
html,body,[class*="css"],.stApp { font-family: 'DM Sans',system-ui,sans-serif; }
.stApp {background: radial-gradient(circle at 80% 0%, rgba(42,155,158,.10),transparent 35%), #09151e;}
.block-container {max-width:1240px;padding-top:2.1rem;padding-bottom:4.2rem;}
h1,h2,h3 {font-family:'Space Grotesk',sans-serif;letter-spacing:-.035em;}
h3{margin-top:.25rem}
.hero-top {display:flex;align-items:center;gap:10px;margin-bottom:13px;}
.hero-kicker{color:#64e2d2;font-weight:800;letter-spacing:.15em;font-size:11px;}
.hero-number{border:1px solid #31575b;border-radius:6px;background:#173437;color:#66ddcd;font-size:11px;padding:3px 7px;font-weight:800}
.hero-title{font-family:'Space Grotesk',sans-serif;font-size:clamp(38px,5.7vw,67px);line-height:1.03;letter-spacing:-.06em;font-weight:700;margin:0 0 15px;color:#f1f9fc}
.hero-subtitle{font-size:16px;color:#a5b9c4;max-width:680px;line-height:1.65;margin-bottom:0}
.hero-accent{color:#61e2d1}
.eyebrow{color:#6fe4d2;font-weight:800;font-size:11px;letter-spacing:.17em;margin-top:12px;margin-bottom:9px}
.section-title{font-family:'Space Grotesk',sans-serif;font-size:27px;font-weight:700;letter-spacing:-.035em;margin-bottom:4px}
.section-sub{color:#9bb0bd;font-size:14px;margin-bottom:16px;line-height:1.6}
.tiny-note{font-size:12px;color:#91a9b7;line-height:1.6}
.status-strip{border:1px solid #304452;background:#132631;border-radius:12px;padding:12px 14px;color:#bdd0d9;font-size:12px;line-height:1.6}
.status-strip strong{color:#e2f6f2}
.instrument-caption{color:#bdd1dc;font-size:13px;font-weight:600;margin-bottom:4px}
.audio-title{font-family:'Space Grotesk',sans-serif;font-size:19px;font-weight:700;margin:0 0 5px}
.audio-desc{font-size:13px;color:#9ab0bd;margin-bottom:14px;min-height:42px;line-height:1.55}
.badge-line{display:inline-flex;align-items:center;gap:8px;border-radius:999px;border:1px solid #385462;background:#152c37;color:#c5d6df;padding:8px 12px;font-weight:700;font-size:11px;letter-spacing:.05em;margin-bottom:20px}
.pulse-dot{width:7px;height:7px;border-radius:50%;background:#59dccb;box-shadow:0 0 0 4px rgba(89,220,203,.12);display:inline-block}
hr{border-color:#253947!important}
[data-testid="stVerticalBlockBorderWrapper"]{border-color:#263d4b!important;background:rgba(18,34,45,.38);border-radius:16px!important;}
[data-testid="stMetric"] {border:1px solid #273f4d;background:#10232e;border-radius:13px;padding:12px 16px}
[data-testid="stMetricValue"]{font-family:'Space Grotesk',sans-serif}
[data-testid="stFileUploader"]{background:#10212b;border-radius:10px}
div[data-testid="stAudio"]{background:#0d202c;border-radius:9px}
div[data-testid="stSegmentedControl"]{margin-bottom:1.45rem}
@media (max-width:700px) {.block-container{padding:1rem 1rem 3rem}.hero-subtitle{font-size:14px}.audio-desc{min-height:0}}
</style>
""", unsafe_allow_html=True)

DEFAULTS = {
    "az_a": 75, "el_a": 0, "gain_a": 0,
    "az_b": -75, "el_b": 0, "gain_b": -3,
    "second_on": True, "focus_source": "A",
    "scene_event": None, "sound_a": "Plucked melody",
    "sound_b": "Brass-like tone",
}
for _key, _val in DEFAULTS.items():
    if _key not in st.session_state:
        st.session_state[_key] = _val


@st.cache_data(show_spinner=False)
def built_in_audio(kind: str) -> np.ndarray:
    return demo_instrument(kind)


@st.cache_data(show_spinner=False, max_entries=8)
def decode_audio(data: bytes) -> np.ndarray:
    return read_uploaded_wav(data)


def plotting_style(fig: go.Figure, height: int = 265) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=18, r=18, t=25, b=28),
        paper_bgcolor="#10212b", plot_bgcolor="#10212b",
        font=dict(color="#a9c0cc", family="DM Sans, Arial, sans-serif", size=12),
        hoverlabel=dict(bgcolor="#132b38", font_color="white"),
        legend=dict(orientation="h", y=1.21, x=0, bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showline=False, gridcolor="#29404e", zeroline=False),
        yaxis=dict(showline=False, gridcolor="#29404e", zeroline=False),
    )
    return fig


def hrirs_plot(hrir: np.ndarray) -> go.Figure:
    times = np.arange(hrir.shape[1]) / SAMPLE_RATE * 1000
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=times, y=hrir[0], mode="lines", name="Left ear",
                             line=dict(color="#56dccb", width=2.2)))
    fig.add_trace(go.Scatter(x=times, y=hrir[1], mode="lines", name="Right ear",
                             line=dict(color="#ffbe7a", width=2.2)))
    fig.update_xaxes(title="Time (ms)")
    fig.update_yaxes(title="Amplitude")
    return plotting_style(fig)


def waveform_plot(scene: SceneResult) -> go.Figure:
    count = min(len(scene.stereo), int(SAMPLE_RATE * .055))
    step = max(1, count // 850)
    t = np.arange(0, count, step) / SAMPLE_RATE * 1000
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t, y=scene.stereo[:count:step, 0], name="Left",
                             mode="lines", line=dict(color="#56dccb", width=1.5)))
    fig.add_trace(go.Scatter(x=t, y=scene.stereo[:count:step, 1], name="Right",
                             mode="lines", line=dict(color="#ffbe7a", width=1.5)))
    fig.update_xaxes(title="Time (ms)")
    fig.update_yaxes(title="Amplitude")
    return plotting_style(fig)


def source_audio(letter: str, name: str, uploaded: object | None) -> np.ndarray | None:
    if name == "My WAV upload":
        if uploaded is None:
            st.info(f"Choose a WAV for source {letter}, or select a built-in sound.")
            return None
        binary = uploaded.getvalue()
        if len(binary) > MAX_WAV_BYTES:
            raise ValueError(f"Source {letter}: WAV exceeds 12 MiB")
        return decode_audio(binary)
    return built_in_audio("guitar" if name == "Plucked melody" else "horns")


def apply_preset(degrees: int) -> None:
    key = "az_a" if st.session_state.focus_source == "A" else "az_b"
    st.session_state[key] = degrees


def render_listen() -> None:
    st.markdown('<div class="eyebrow">01 / INTERACTIVE SOUND STAGE</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Place a sound. Hear the direction.</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Drag either marker around the listener, or use the sliders. Then compare a centered mono mix with binaural stereo through headphones.</div>', unsafe_allow_html=True)

    if not st.session_state.second_on and st.session_state.focus_source == "B":
        st.session_state.focus_source = "A"
    presets_l, presets_r = st.columns([2.1, 3], gap="large")
    with presets_l:
        st.radio("Move source", ["A", "B"] if st.session_state.second_on else ["A"],
                 horizontal=True, key="focus_source", help="Presets apply to the selected source.")
    with presets_r:
        p1, p2, p3, p4 = st.columns(4, gap="small")
        p1.button("Left 90°", on_click=apply_preset, args=(90,), use_container_width=True)
        p2.button("Front 0°", on_click=apply_preset, args=(0,), use_container_width=True)
        p3.button("Right −90°", on_click=apply_preset, args=(-90,), use_container_width=True)
        p4.button("Back 180°", on_click=apply_preset, args=(180,), use_container_width=True)

    stage_col, setup_col = st.columns([1.35, 1.0], gap="large", vertical_alignment="top")
    with stage_col:
        evt = stage_component(az_a=st.session_state.az_a, az_b=st.session_state.az_b,
                              enable_b=st.session_state.second_on,
                              active=st.session_state.focus_source.lower(), key="stage_canvas")
        if isinstance(evt, dict) and evt.get("nonce") != st.session_state.scene_event:
            st.session_state.scene_event = evt.get("nonce")
            for label in ("a", "b"):
                key = "az_" + label
                angle = evt.get(key)
                if isinstance(angle, (int, float)) and np.isfinite(angle):
                    st.session_state[key] = int(np.clip(round(angle / 5) * 5, -180, 180))
            st.rerun()
        st.markdown('<div class="tiny-note">0° = front · +90° = left · −90° = right · ±180° = behind. This is a top-down view; elevation is set separately.</div>', unsafe_allow_html=True)
    with setup_col:
        st.toggle("Enable second sound source", key="second_on")
        st.markdown("**Source A — teal marker**")
        st.slider("Azimuth · A", min_value=-180, max_value=180, step=5, key="az_a")
        st.slider("Elevation · A", min_value=-90, max_value=90, step=5, key="el_a",
                  help="Synthetic HRIRs only approximate elevation-related coloration.")
        st.slider("Gain · A (dB)", min_value=-30, max_value=6, step=1, key="gain_a")
        if st.session_state.second_on:
            st.markdown("**Source B — amber marker**")
            st.slider("Azimuth · B", min_value=-180, max_value=180, step=5, key="az_b")
            st.slider("Elevation · B", min_value=-90, max_value=90, step=5, key="el_b")
            st.slider("Gain · B (dB)", min_value=-30, max_value=6, step=1, key="gain_b")

    st.divider()
    st.markdown('<div class="eyebrow">02 / SOUND SOURCES</div>', unsafe_allow_html=True)
    sound_col_a, sound_col_b = st.columns(2, gap="large")
    with sound_col_a:
        st.selectbox("Source A audio", ["Plucked melody", "Brass-like tone", "My WAV upload"], key="sound_a")
        wav_a = st.file_uploader("Upload WAV for A · ≤12 s / ≤12 MiB", type="wav", key="wav_a") if st.session_state.sound_a == "My WAV upload" else None
    with sound_col_b:
        if st.session_state.second_on:
            st.selectbox("Source B audio", ["Brass-like tone", "Plucked melody", "My WAV upload"], key="sound_b")
            wav_b = st.file_uploader("Upload WAV for B · ≤12 s / ≤12 MiB", type="wav", key="wav_b") if st.session_state.sound_b == "My WAV upload" else None
        else:
            wav_b = None
            st.info("Source B is disabled. Turn it on to mix two directions.")

    with st.expander("Advanced · HRIR model and optional SOFA file", expanded=False):
        use_sofa = st.toggle("Use my measured SOFA dataset instead of the educational HRIR model", value=False)
        sofa_upload = None
        if use_sofa:
            sofa_upload = st.file_uploader("Upload compatible SimpleFreeFieldHRIR SOFA · ≤45 MiB", type="sofa", key="sofa_file")
            st.caption("Receiver 0 is assumed left; receiver 1 right. Source positions must be spherical degrees. Nearest measured direction only.")
        else:
            st.caption("Built-in synthetic HRIRs approximate interaural timing and level differences. Elevation and front/back localization are not realistic.")

    try:
        a = source_audio("A", st.session_state.sound_a, wav_a)
        if a is None:
            return
        sources = [SceneSource("A", a, st.session_state.az_a, st.session_state.el_a, st.session_state.gain_a)]
        if st.session_state.second_on:
            b = source_audio("B", st.session_state.sound_b, wav_b)
            if b is None:
                return
            sources.append(SceneSource("B", b, st.session_state.az_b, st.session_state.el_b, st.session_state.gain_b))
        sofa_data = sofa_upload.getvalue() if use_sofa and sofa_upload is not None else None
        if use_sofa and sofa_data is None:
            st.info("Upload a compatible SOFA dataset to use measured HRIRs, or turn this option off.")
            return
        if sofa_data is not None and len(sofa_data) > MAX_SOFA_BYTES:
            raise ValueError("SOFA file exceeds 45 MiB")
        with st.spinner("Rendering audio scene …", show_time=False):
            scene = render_scene(sources, sofa_data)
            mono_wav = wav_bytes(scene.mono)
            stereo_wav = wav_bytes(scene.stereo)
    except (OSError, ValueError, KeyError, TypeError) as error:
        st.error(f"Audio could not be rendered: {error}")
        return

    st.divider()
    st.markdown('<div class="eyebrow">03 / A-B LISTENING TEST</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Same input. Different experience.</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Compare a centered mono signal against the spatial mix. Both versions use the same source gains and one shared peak-safety adjustment; no separate loudness boosts.</div>', unsafe_allow_html=True)
    st.markdown('<div class="badge-line"><span class="pulse-dot"></span> USE HEADPHONES · STATIC OFFLINE RENDER</div>', unsafe_allow_html=True)
    mono_col, stereo_col = st.columns(2, gap="large")
    with mono_col:
        with st.container(border=True):
            st.markdown('<div class="audio-title">01 &nbsp; Centered mono</div>', unsafe_allow_html=True)
            st.markdown('<div class="audio-desc">One shared signal without left/right direction cues. Your player usually sends the same mono audio to both ears.</div>', unsafe_allow_html=True)
            st.audio(mono_wav, format="audio/wav")
    with stereo_col:
        with st.container(border=True):
            st.markdown('<div class="audio-title">02 &nbsp; Binaural stereo</div>', unsafe_allow_html=True)
            st.markdown('<div class="audio-desc">Each source is convolved with two ear-specific impulse responses to create direction-dependent stereo.</div>', unsafe_allow_html=True)
            st.audio(stereo_wav, format="audio/wav")
            st.download_button("Download spatial mix · WAV", stereo_wav, "from-lab-to-code-spatial.wav", "audio/wav", use_container_width=True)
    if scene.shared_gain < 1:
        st.caption(f"Clipping prevention: the same ×{scene.shared_gain:.3f} gain was applied to both versions. This is not perceived-loudness matching.")
    else:
        st.caption("No extra normalization was needed. Both mixes retain their original input-gain relationship.")

    st.divider()
    st.markdown('<div class="eyebrow">04 / LOOK INSIDE THE SIGNAL</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Why does it sound directional?</div>', unsafe_allow_html=True)
    if ("inspect_source" in st.session_state and
        st.session_state.inspect_source not in [item.label for item in scene.source_results]):
        st.session_state.inspect_source = "A"
    inspect_source = st.radio("Inspect impulse-response pair", [source.label for source in scene.source_results],
                              horizontal=True, key="inspect_source")
    result = next(item for item in scene.source_results if item.label == inspect_source)
    m1, m2, m3 = st.columns(3, gap="medium")
    m1.metric("ITD · right minus left", f"{result.itd_ms:+.3f} ms", help="Positive means right-ear arrival is delayed relative to left.")
    m2.metric("ILD · right vs. left", f"{result.ild_db:+.2f} dB", help="Negative means the right ear receives less total HRIR energy.")
    m3.metric("HRIR direction", f"{result.actual[0]:+.0f}° / {result.actual[1]:+.0f}°", help="Azimuth / elevation. With SOFA, the nearest available measured direction is used.")
    plot_left, plot_right = st.columns(2, gap="large")
    with plot_left:
        st.markdown("**Ear-specific impulse responses**")
        st.plotly_chart(hrirs_plot(result.hrir), use_container_width=True, config={"displayModeBar":False})
    with plot_right:
        st.markdown("**Rendered stereo · first 55 ms**")
        st.plotly_chart(waveform_plot(scene), use_container_width=True, config={"displayModeBar":False})
    if result.itd_ms > 0:
        sense = "The sound arrives at the left ear first."
    elif result.itd_ms < 0:
        sense = "The sound arrives at the right ear first."
    else:
        sense = "The estimated arrival times are equal."
    st.markdown(f'<div class="status-strip"><strong>What you are measuring:</strong> {sense} ITD estimates timing; ILD compares ear energy. These are useful directional cues, not a guarantee of true 3D localization.</div>', unsafe_allow_html=True)
    st.markdown('<div class="tiny-note" style="margin-top:12px">All included sound files are generated from Python; no university recordings or proprietary HRIR datasets are shipped. Your WAV and SOFA uploads are processed in memory on the running Streamlit host, not included in the repository.</div>', unsafe_allow_html=True)


def render_correlation() -> None:
    st.markdown('<div class="eyebrow">EXPERIMENT / CORRELATION EXPLORER</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Find the delay between two signals.</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Move the two impulses and watch the correlation peaks follow. Start with the original reference at 5 and shifted impulses at 9 and 14.</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="large")
    with c1:
        count = st.slider("Signal length · samples", 16, 48, value=20)
        first = st.slider("Reference impulse", 0, count-1, value=min(5,count-1))
        second = st.slider("Shifted impulse A", 0, count-1, value=min(9,count-1))
    with c2:
        third = st.slider("Shifted impulse B", 0, count-1, value=min(14,count-1))
        amplitude = st.slider("Impulse B amplitude", .1, 1.0, value=.5, step=.1)
        st.markdown('<div class="status-strip">The important call is <code>correlate(shifted, reference)</code>. The order matters: positive lag means the shifted impulse happened later.</div>', unsafe_allow_html=True)
    reference, shifted = example_signals(count, first, second, third, amplitude)
    lags, result = cross_correlate(reference, shifted)
    signals_fig = go.Figure()
    signals_fig.add_trace(go.Scatter(x=np.arange(count), y=reference, name="Reference", mode="lines+markers", line=dict(color="#56dccb", width=2), marker=dict(size=7)))
    signals_fig.add_trace(go.Scatter(x=np.arange(count), y=shifted, name="Shifted", mode="lines+markers", line=dict(color="#ffbe7a", width=2), marker=dict(size=7)))
    signals_fig.update_xaxes(title="Sample index", dtick=2)
    signals_fig.update_yaxes(title="Amplitude", range=[-.1, max(1.3,1+amplitude+.15)])
    st.markdown("**1. Input impulse signals**")
    st.plotly_chart(plotting_style(signals_fig, 300), use_container_width=True, config={"displayModeBar":False})
    cc_fig = go.Figure()
    cc_fig.add_trace(go.Scatter(x=lags, y=np.abs(result), name="Correlation magnitude", mode="lines+markers", line=dict(color="#b59cff", width=2), marker=dict(size=6)))
    for lag, val in nonzero_peaks(lags, result):
        cc_fig.add_annotation(x=int(lag), y=abs(float(val)), text=f"{int(lag):+d}", showarrow=True, arrowhead=0, ay=-26, font=dict(color="#ebdcff", size=13))
    cc_fig.update_xaxes(title="Lag · samples", dtick=3)
    cc_fig.update_yaxes(title="Cross-correlation magnitude")
    st.markdown("**2. Sliding cross-correlation**")
    st.plotly_chart(plotting_style(cc_fig, 300), use_container_width=True, config={"displayModeBar":False})
    shifts = sorted({second-first, third-first})
    st.success(f"Expected shifts: {', '.join(f'{v:+d}' for v in shifts)} sample(s)." + (" The two impulses overlap at one lag, so their amplitudes add." if second == third else ""))
    st.caption("Note: Correlation peaks need not always indicate a unique time delay for arbitrary or periodic signals. Here the test impulses are deliberately simple.")


def render_science() -> None:
    st.markdown('<div class="eyebrow">FIELD NOTES / THE SCIENCE</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">From a waveform to a place in space.</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">A few well-defined signal-processing operations explain much of what you hear. The real human hearing system is more complicated.</div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("### 01 — Cross-correlation detects delays")
        st.latex(r"R_{yx}[k] = \sum_n y[n]x^{*}[n-k]")
        st.write("Slide a reference signal across another. Where patterns line up, correlation can peak. We use `scipy.signal.correlate(shifted, reference, mode='full')` so a delayed signal has a positive lag.")
    with st.container(border=True):
        st.markdown("### 02 — HRIRs create ear-specific versions")
        st.latex(r"y_L[n] = x[n]*h_L[n], \quad y_R[n] = x[n]*h_R[n]")
        st.write("The mono sound is filtered separately for left and right ears. The filters approximate the acoustic effect of head and ears; measured HRTFs/HRIRs contain more detailed individualized structure.")
    with st.container(border=True):
        st.markdown("### 03 — Two interaural cues")
        st.latex(r"\mathrm{ITD} = t_R - t_L")
        st.latex(r"\mathrm{ILD} = 10\log_{10}\!\left(\frac{\sum_n h_R[n]^2}{\sum_n h_L[n]^2}\right)")
        st.write("Positive ITD means the right ear receives the sound later; negative ILD means it receives less HRIR energy. The app estimates ITD using 1.5 kHz low-pass filtered HRIR cross-correlation and reports broadband ILD.")
    st.markdown("### Important boundaries")
    st.markdown("""
- **Synthetic is illustrative, not authentic 3D:** the built-in HRIRs approximate left/right timing and attenuation, with simple elevation coloration. They do not reproduce personalized pinna cues or reliable front/back/elevation localization.
- **Offline, not live:** moving a marker updates the next rendered clip; there is no continuous moving-source interpolation or head tracking.
- **SOFA is optional:** only compatible spherical-degree, two-receiver data are supported, using nearest-direction lookup. Channel order and coordinate conventions must be checked by the user.
- **Headphone listening:** mono is a centered baseline, while binaural sends different waveforms to each ear. Perceived realism varies with listener, headphones and HRIR fit.
""")
    st.caption("Further reading: SciPy correlate / correlation_lags / oaconvolve; Spatially Oriented Format for Acoustics (SOFA/AES69). No third-party audio or university notebook code is bundled.")


st.markdown('<div class="hero-top"><span class="hero-number">#02</span><span class="hero-kicker">FROM LAB TO CODE &nbsp;/&nbsp; AUDIO ENGINEERING</span></div>', unsafe_allow_html=True)
st.markdown('<h1 class="hero-title">Hear where <span class="hero-accent">sound lives.</span></h1>', unsafe_allow_html=True)
st.markdown('<div class="hero-subtitle">Turn mono audio into a directional listening experiment. Move two virtual sources, listen to the difference, and see the signal-processing cues that make it happen.</div>', unsafe_allow_html=True)
st.write("")
page = st.segmented_control("Choose a workspace", ["Sound stage", "Correlation lab", "How it works"],
                            default="Sound stage", key="workspace", label_visibility="collapsed")
if page == "Correlation lab":
    render_correlation()
elif page == "How it works":
    render_science()
else:
    render_listen()

st.divider()
st.caption("From Lab to Code #2 · A self-contained engineering demo · Original generated audio · Built with Python, SciPy, Streamlit and a lightweight drag-to-position SVG component.")

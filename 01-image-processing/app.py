"""A small interactive exhibition of classical computer-vision techniques."""
from __future__ import annotations

import cv2
import numpy as np
import streamlit as st
from PIL import Image

from processing import (
    add_mixed_noise, add_periodic_noise, compare_denoisers,
    detect_dark_objects, kmeans_colors, mse, notch_filter, to_gray,
)
from synthetic import demo_scene

st.set_page_config(page_title="From Lab to Code | Image Processing", page_icon="🔬", layout="wide")
st.title("Image Processing: From Theory to Pixels")
st.caption("01 / From Lab to Code · Classical computer vision, implemented in Python")

mode = st.sidebar.selectbox("Technique", [
    "Denoising", "Object counting", "Fourier notch filter", "K-means color clustering"
])
upload = st.sidebar.file_uploader("Optional: upload your own image", type=["png", "jpg", "jpeg", "bmp"])

scene_name = {
    "Denoising": "shapes",
    "Object counting": "objects",
    "Fourier notch filter": "shapes",
    "K-means color clustering": "colors",
}[mode]

if upload is not None:
    try:
        image = Image.open(upload).convert("RGB")
        image.thumbnail((640, 640))
        source = np.asarray(image).copy()
    except Exception as exc:
        st.error(f"Image could not be read: {exc}")
        st.stop()
    st.sidebar.caption("Images are processed in memory, not saved by this app.")
else:
    source = demo_scene(scene_name)
    st.sidebar.caption("Using an original, procedurally generated demo image.")


def show_pair(left, right, left_title="Input", right_title="Output", gray=False):
    a, b = st.columns(2)
    a.subheader(left_title)
    a.image(left, clamp=True)
    b.subheader(right_title)
    b.image(right, clamp=True)


if mode == "Denoising":
    st.write("Compare a Gaussian blur with a median filter on the same noisy image.")
    sigma = st.sidebar.slider("Gaussian noise strength", 0, 40, 16)
    impulse = st.sidebar.slider("Salt-and-pepper probability", 0.0, 0.08, 0.025, 0.005)
    kernel = st.sidebar.select_slider("Filter kernel", options=[3, 5, 7, 9], value=5)
    original = to_gray(source)
    noisy = add_mixed_noise(original, sigma=sigma, impulse_rate=impulse)
    gaussian, median = compare_denoisers(noisy, kernel)
    c1, c2, c3 = st.columns(3)
    c1.image(noisy, caption="Noisy input", clamp=True)
    c2.image(gaussian, caption="Gaussian blur", clamp=True)
    c3.image(median, caption="Median filter", clamp=True)
    st.caption(f"MSE vs. source (lower is better): noisy {mse(original, noisy):.1f} · "
               f"Gaussian {mse(original, gaussian):.1f} · Median {mse(original, median):.1f}")

elif mode == "Object counting":
    st.write("Correct uneven illumination, threshold dark objects, then count connected components.")
    min_area = st.sidebar.slider("Minimum object area (px)", 20, 1000, 100, 10)
    foreground, annotated, boxes, corrected = detect_dark_objects(source, min_area=min_area)
    st.metric("Detected regions", len(boxes))
    c1, c2, c3 = st.columns(3)
    c1.image(source, caption="Input")
    c2.image(foreground, caption="Binary mask", clamp=True)
    c3.image(annotated, caption="Detected regions")
    st.caption("Assumption: objects are darker than their background. Touching objects may merge.")

elif mode == "Fourier notch filter":
    st.write("Add a known sinusoidal interference pattern, then remove its symmetric FFT peaks.")
    cycles_x = st.sidebar.slider("Horizontal frequency (cycles/image)", 1, min(30, source.shape[1] // 2 - 1), 12)
    cycles_y = st.sidebar.slider("Vertical frequency (cycles/image)", 0, min(30, source.shape[0] // 2 - 1), 7)
    amplitude = st.sidebar.slider("Interference amplitude", 5, 60, 30)
    radius = st.sidebar.slider("Notch radius", 1, 8, 2)
    original = to_gray(source)
    disturbed = add_periodic_noise(original, cycles_x, cycles_y, amplitude)
    restored, spectrum, mask = notch_filter(disturbed, cycles_x, cycles_y, radius)
    c1, c2, c3 = st.columns(3)
    c1.image(original, caption="Original", clamp=True)
    c2.image(disturbed, caption="With periodic noise", clamp=True)
    c3.image(restored, caption="After notch filter", clamp=True)
    st.caption(f"MSE vs. source (lower is better): disturbed {mse(original, disturbed):.1f} · "
               f"filtered {mse(original, restored):.1f}")
    a, b = st.columns(2)
    a.image(cv2.normalize(spectrum, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8),
            caption="Log-amplitude FFT", clamp=True)
    b.image((mask * 255).astype(np.uint8), caption="Notch mask (black = rejected)", clamp=True)
    st.caption("The frequency pair is known because the interference is generated here. "
               "Real-world noise requires estimating its peak positions.")

else:
    st.write("Group pixels by RGB color similarity without predefined semantic labels.")
    k = st.sidebar.slider("Number of color clusters", 2, 8, 4)
    reduced, labels, proportions = kmeans_colors(source, k)
    show_pair(source, reduced, "Input", "Color-clustered image")
    st.write("Cluster sizes:")
    for i, share in enumerate(proportions):
        st.progress(float(share), text=f"Cluster {i + 1}: {share:.1%}")
    st.caption("Color clusters are not semantic object classes.")

st.divider()
st.caption("No university code, datasets, figures or logos. All bundled sample images are generated by this repository.")

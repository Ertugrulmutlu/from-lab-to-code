# 04 — Neural Network Efficiency Lab

**Small networks. Real experiments. Visible trade-offs.** An independent, interactive experiment about how CNN architecture affects classification accuracy and theoretical computational cost. Part of [From Lab to Code](https://github.com/Ertugrulmutlu/from-lab-to-code).

The app trains **three original compact PyTorch convolutional networks** on public MNIST, compares genuine held-out test accuracy against estimated multiply-accumulate operations (MACs), lets you classify a drawing or select a test sample, displays learned feature-map activations, and estimates the cost of hypothetical architectures. All inference runs locally; **no hosted demo or cloud model API** is involved.

## Start locally (Windows PowerShell)

From the `04-neural-network-efficiency` folder:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe app.py
```

Visit **http://127.0.0.1:5000** and try these steps:

1. Compare **Micro**, **Compact**, and **Wide** CNN in the first section. Select one and see its measured accuracy and estimated compute.
2. Select any of the **20 attributed MNIST test examples** or draw a digit; click **Run prediction** to see class probabilities and convolutional feature maps. Drawings outside the MNIST distribution may be misclassified.
3. Change **Conv1/Conv2 channels** and **kernel size** in the Architecture Sandbox. The cost is calculated immediately, but the new architecture is **not trained** and thus has *no claimed accuracy*.

Requirements: Python 3.10+, PyTorch, torchvision, FastAPI, Uvicorn, Pillow and NumPy; internet access **only for initial Python dependency installation or if you choose to download MNIST for retraining**. Pretrained model weights are included in `checkpoints/` so the demo does not need a dataset download. No npm installation or build step.

To stop the local server, press `Ctrl+C`.

## Measured results (seed 2026, one run per model)

| Model | Conv channels | Kernel | Test accuracy | Parameters | MACs/image |
| --- | --- | --- | ---: | ---: | ---: |
| Micro CNN | 3 → 6 | 3×3 | **96.67%** | 3,148 | **55,860** |
| Compact CNN | 8 → 16 | 3×3 | **97.92%** | 9,098 | **290,080** |
| Wide CNN | 16 → 32 | 3×3 | **98.63%** | 20,490 | **1,031,744** |

These results were computed with the included training script using public MNIST (54,000 training / 6,000 validation / 10,000 official test). The validation subset is a seeded partition of the official 60,000 MNIST training images; the 10,000-image test split is not used for model selection. Adam, `CrossEntropyLoss` applied to *logits* (not pre-softmax outputs), same learning rate/batch size, and four training epochs; each model's best validation epoch is selected before a final test evaluation. The selected epoch, train/validation curves, and all recorded metrics appear in `results/experiments.json`. **Single-seed numbers are not confidence intervals.**

The estimated MAC count includes convolution and dense-layer multiply-accumulates only; excludes ReLU, pooling, softmax, memory access, and actual wall-clock inference. MACs are **not** FLOPs or latency. A MAC is often approximated as two floating-point operations, depending on counting convention. The hypothetical **75,000 MAC budget** is from a related lab optimization question, not an external hardware limit. Micro CNN is under this MAC threshold, and its observed accuracy exceeds 85% on this run. This is not a deployment or real-time performance benchmark.

### How the MAC estimate is computed

Two same-padded convolution layers separated by 2×2 max-pooling, followed by a dense 10-class output layer. Let `C1`, `C2` be convolution channels and `K` be square kernel width:

```
Conv1: 28 × 28 × C1 × K²
Conv2: 14 × 14 × C1 × C2 × K²
Dense: 7 × 7 × C2 × 10
Total = Conv1 + Conv2 + Dense
```

Changing channel counts or kernel size adjusts the theoretical arithmetic count without retraining.

## Retrain the models independently

The model files are included; retraining is entirely optional. If you want to reproduce the experiment with the official MNIST download, run:

```powershell
.\.venv\Scripts\python.exe train.py --download --epochs 4
```

`torchvision.datasets.MNIST` downloads public MNIST data into `data/`, which is excluded from Git. If you already have **the official MNIST dataset** in `data/MNIST/raw/`, omit `--download`. You can select one architecture with `--model micro`, `--model compact`, or `--model wide`, and optionally change batch size/epochs. Note that changing training settings will produce results that may differ from the table above. This process overwrites the corresponding model checkpoint and writes experiment results; do not commit modified checkpoints without reviewing the new metrics.

## Project structure

```
04-neural-network-efficiency/
├── app.py                     # Local FastAPI server, prediction endpoints
├── neural_lab/
│   ├── models.py              # CNN architecture and transparent MAC calculation
│   ├── data.py                # MNIST data loading and seeded splits
│   └── inference.py           # Model registry, predictions and feature maps
├── train.py                   # Reproducible experiments
├── checkpoints/               # Three independently trained model weights
├── results/experiments.json   # Measured metrics and validation curves
├── templates/index.html       # Interactive single-page UI
├── static/css/style.css
├── static/js/app.js
├── static/samples/             # 20 attributed MNIST test examples
├── tests/                     # API, compute, preprocessing and inference tests
├── DATA_CREDITS.md            # Dataset permissions and attribution
└── requirements.txt
```

## Limitations and responsible use

- A small didactic CNN, **not a new neural-network algorithm or an optimized deployment runtime**.
- Models share training settings but only have one run each: random-seed variability is not quantified.
- Visual feature maps are individually normalized for display; brightness is *not* a comparable activation magnitude between channels.
- Softmax confidence is not a calibrated certainty estimate. A mouse-drawn digit can differ from MNIST handwriting.
- The architecture sandbox counts estimated MACs and parameters. It cannot predict the test accuracy of an untrained model.
- The app is for **single-user localhost use**. Do not expose this development server on the public internet.

## Data provenance and copyright

All code, training scripts, visualization logic and page design were independently created for this series. No RWTH course PDF, notebook, course code, course branding or proprietary datasets are included. The 20 MNIST sample images are **third-party** and attributed under the MNIST data license separately in [DATA_CREDITS.md](DATA_CREDITS.md). The sample files are not MIT-licensed project artwork. Full MNIST data is not bundled.

## License

Original code is available under [MIT](LICENSE); third-party dependencies and MNIST samples retain their own licenses.

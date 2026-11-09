"""Small independent CNNs and transparent operation counts for 28x28 MNIST."""
from dataclasses import dataclass
import torch
from torch import nn

@dataclass(frozen=True)
class Architecture:
    id: str
    name: str
    c1: int
    c2: int
    kernel: int = 3
    description: str = ''

PRESETS = (
    Architecture('micro', 'Micro CNN', 3, 6, 3, 'A very small model under the 75k MAC budget.'),
    Architecture('compact', 'Compact CNN', 8, 16, 3, 'A practical balance between accuracy and compute.'),
    Architecture('wide', 'Wide CNN', 16, 32, 3, 'A wider model with substantially higher compute.'),
)

class DigitCNN(nn.Module):
    def __init__(self, config: Architecture):
        super().__init__()
        k = config.kernel
        if k not in (3, 5) or not (2 <= config.c1 <= 64 and 2 <= config.c2 <= 64):
            raise ValueError('Invalid architecture specification')
        self.config = config
        self.conv1 = nn.Conv2d(1, config.c1, k, padding=k // 2)
        self.pool1 = nn.MaxPool2d(2)
        self.conv2 = nn.Conv2d(config.c1, config.c2, k, padding=k // 2)
        self.pool2 = nn.MaxPool2d(2)
        self.head = nn.Linear(config.c2 * 7 * 7, 10)

    def forward(self, x, return_features=False):
        f1 = torch.relu(self.conv1(x))
        x = self.pool1(f1)
        f2 = torch.relu(self.conv2(x))
        x = self.pool2(f2)
        logits = self.head(torch.flatten(x, 1))
        return (logits, (f1, f2)) if return_features else logits

def mac_breakdown(cfg: Architecture) -> dict[str, int]:
    """Multiply-accumulate estimates, conv & dense only (not FLOPs)."""
    k2 = cfg.kernel ** 2
    conv1 = 28 * 28 * cfg.c1 * k2
    conv2 = 14 * 14 * cfg.c1 * cfg.c2 * k2
    linear = 7 * 7 * cfg.c2 * 10
    return {'conv1': conv1, 'conv2': conv2, 'linear': linear,
            'total': conv1 + conv2 + linear}

def param_count(cfg: Architecture) -> int:
    return sum(p.numel() for p in DigitCNN(cfg).parameters())

def preprocess(pixels):
    """Accept 28x28 white-ink-on-black intensities in [0,255]."""
    import numpy as np
    x = np.asarray(pixels)
    if x.shape != (28, 28) or not np.isfinite(x).all():
        raise ValueError('Expected a finite 28x28 grayscale image')
    if x.min() < 0 or x.max() > 255:
        raise ValueError('Pixel intensities must lie in [0, 255]')
    return (torch.tensor(x, dtype=torch.float32).reshape(1, 1, 28, 28) / 255.0 - 0.1307) / 0.3081

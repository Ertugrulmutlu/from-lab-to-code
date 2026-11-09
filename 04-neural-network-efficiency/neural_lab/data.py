"""MNIST loader, with official torchvision download and reproducible split."""
from pathlib import Path
import torch
from torchvision.datasets import MNIST

TRAIN_SEED = 2026
VAL_SIZE = 6000

def get_data(root='data', download=False):
    root = Path(root)
    train = MNIST(root, train=True, download=download)
    test = MNIST(root, train=False, download=download)
    gen = torch.Generator().manual_seed(TRAIN_SEED)
    order = torch.randperm(len(train), generator=gen)
    train_idx = order[:-VAL_SIZE]
    val_idx = order[-VAL_SIZE:]
    return (train.data[train_idx], train.targets[train_idx]), (train.data[val_idx], train.targets[val_idx]), (test.data, test.targets)

class TensorDigitSet(torch.utils.data.Dataset):
    def __init__(self, pair):
        self.x, self.y = pair
    def __len__(self):
        return len(self.y)
    def __getitem__(self, index):
        x = (self.x[index].float().unsqueeze(0) / 255.0 - 0.1307) / 0.3081
        return x, self.y[index].long()

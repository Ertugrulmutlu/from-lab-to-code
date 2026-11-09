"""Load model checkpoints and predict independent of the browser UI."""
from pathlib import Path
import torch
from .models import DigitCNN, PRESETS, preprocess

class ModelRegistry:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.configs = {p.id:p for p in PRESETS}
        self.cache = {}

    def get(self, model_id):
        if model_id not in self.configs:
            raise ValueError('Unknown model ID')
        if model_id not in self.cache:
            file = self.folder / f'{model_id}.pt'
            if not file.is_file():
                raise FileNotFoundError(f'Missing model checkpoint: {file.name}')
            obj = torch.load(file, map_location='cpu', weights_only=True)
            model = DigitCNN(self.configs[model_id])
            model.load_state_dict(obj)
            model.eval()
            self.cache[model_id] = model
        return self.cache[model_id]

    @torch.inference_mode()
    def predict(self, model_id, pixels):
        model = self.get(model_id)
        logits, features = model(preprocess(pixels), return_features=True)
        probs = torch.softmax(logits, dim=1)[0].cpu().tolist()
        maps = []
        for depth, feat in enumerate(features):
            # Preview first four feature channels, normalized for display.
            for channel in range(min(4, feat.shape[1])):
                arr = feat[0,channel].detach().cpu()
                lo, hi = arr.min(), arr.max()
                normalized = ((arr-lo)/(hi-lo+1e-9) * 255).to(torch.uint8)
                maps.append({'layer':depth+1, 'channel':channel+1, 'pixels':normalized.tolist()})
        return {'digit': int(max(range(10),key=probs.__getitem__)),
                'confidence':max(probs),'probabilities':probs,'features':maps}

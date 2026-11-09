"""Local-only FastAPI app for a reproducible CNN efficiency playground."""
from pathlib import Path
import json
import numpy as np
from PIL import Image
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from neural_lab.inference import ModelRegistry
from neural_lab.models import Architecture, mac_breakdown, param_count

ROOT = Path(__file__).resolve().parent
app = FastAPI(title='Neural Network Efficiency Lab', docs_url=None, redoc_url=None)
app.mount('/static', StaticFiles(directory=ROOT/'static'), name='static')
registry = ModelRegistry(ROOT / 'checkpoints')


def read_json(path):
    return json.loads((ROOT/path).read_text(encoding='utf-8'))


@app.get('/')
def index():
    return FileResponse(ROOT/'templates'/'index.html')


@app.get('/api/overview')
def overview():
    return {'results':read_json('results/experiments.json'), 'budget_macs':75000,
            'note':'MAC estimates include convolution and dense multiply-accumulates, not pooling, activation, or runtime. A multiply-add may be counted as two FLOPs.'}


@app.get('/api/examples')
def examples():
    return read_json('static/samples/manifest.json')


@app.get('/api/architecture')
def architecture(c1: int, c2: int, kernel: int):
    try:
        cfg=Architecture('custom','Custom CNN',c1,c2,kernel)
        params=param_count(cfg)
        macs=mac_breakdown(cfg)
        return {'params':params,'macs':macs,'budget_met':macs['total']<75000,
                'accuracy':None, 'message':'Architecture cost estimate only. Accuracy requires training and evaluating this architecture.'}
    except (ValueError,OverflowError):
        raise HTTPException(400,'Use channels between 2 and 64, and kernel 3 or 5.')


class PredictionRequest(BaseModel):
    model_id: str
    pixels: list[list[float]] | None = None
    sample_id: str | None = None


@app.post('/api/predict')
def predict(payload: PredictionRequest):
    if payload.model_id not in registry.configs:
        raise HTTPException(400,'Choose a trained model preset.')
    try:
        if payload.sample_id is not None:
            manifest=read_json('static/samples/manifest.json')
            if not any(x['id']==payload.sample_id for x in manifest['samples']):
                raise ValueError('Unknown example ID')
            pixels=np.asarray(Image.open(ROOT/'static'/'samples'/f'{payload.sample_id}.png').convert('L'))
        elif payload.pixels is not None:
            pixels=payload.pixels
        else:
            raise ValueError('Provide a sample_id or 28x28 pixels')
        result=registry.predict(payload.model_id,pixels)
        result['model_id']=payload.model_id
        return result
    except (ValueError,TypeError,FileNotFoundError) as exc:
        raise HTTPException(400,str(exc))


if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=5000,log_level='info')

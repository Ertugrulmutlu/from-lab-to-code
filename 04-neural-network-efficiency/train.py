"""Reproduce three CNN experiments using *official MNIST*, not lab code.

Training: 54,000 of official training split; validation: held-out 6,000.
The official 10,000-image test split is used only for final reported metrics.
"""
import argparse
import json
from pathlib import Path
import random
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader
from neural_lab.models import DigitCNN, PRESETS, mac_breakdown, param_count
from neural_lab.data import get_data, TensorDigitSet, TRAIN_SEED


def evaluate(model, loader, device):
    model.eval()
    right, loss_sum, size = 0, 0.0, 0
    criterion=nn.CrossEntropyLoss(reduction='sum')
    with torch.inference_mode():
        for x,y in loader:
            x,y=x.to(device),y.to(device)
            logits=model(x)
            loss_sum+=criterion(logits,y).item()
            right+=(logits.argmax(1)==y).sum().item()
            size+=len(y)
    return {'accuracy':right/size,'loss':loss_sum/size}


def run(args):
    random.seed(TRAIN_SEED)
    np.random.seed(TRAIN_SEED)
    torch.manual_seed(TRAIN_SEED)
    torch.set_num_threads(args.threads)
    device=torch.device('cuda' if args.cuda and torch.cuda.is_available() else 'cpu')
    train_pair,val_pair,test_pair=get_data(args.data_dir, download=args.download)
    val_loader=DataLoader(TensorDigitSet(val_pair),batch_size=512)
    test_loader=DataLoader(TensorDigitSet(test_pair),batch_size=512)
    output=Path(__file__).resolve().parent
    (output/'checkpoints').mkdir(exist_ok=True)
    (output/'results').mkdir(exist_ok=True)
    results={'dataset':'MNIST (LeCun and Cortes)', 'seed':TRAIN_SEED, 'split':{'train':len(train_pair[1]),'validation':len(val_pair[1]),'test':len(test_pair[1])},
             'metrics_note':'Accuracy measured on held-out official test images. MACs are analytical conv/dense estimates, not measured latency or FLOPs.',
             'epochs_limit':args.epochs,'models':[]}
    for cfg in PRESETS:
        if args.model and args.model!=cfg.id: continue
        # Reset RNG for each model, independent of selection.
        torch.manual_seed(TRAIN_SEED+list(PRESETS).index(cfg))
        train_gen=torch.Generator().manual_seed(TRAIN_SEED)
        loader=DataLoader(TensorDigitSet(train_pair),batch_size=args.batch_size,shuffle=True,generator=train_gen)
        model=DigitCNN(cfg).to(device)
        opt=torch.optim.Adam(model.parameters(),lr=args.lr)
        criterion=nn.CrossEntropyLoss()
        best_val=-1.0
        best_weights=None
        history=[]
        for epoch in range(1,args.epochs+1):
            model.train()
            losses=[]
            for x,y in loader:
                x,y=x.to(device),y.to(device)
                opt.zero_grad(set_to_none=True)
                logits=model(x)
                loss=criterion(logits,y)
                loss.backward()
                opt.step()
                losses.append(float(loss.detach()))
            val=evaluate(model,val_loader,device)
            history.append({'epoch':epoch,'train_loss':round(float(np.mean(losses)),5),'val_accuracy':round(val['accuracy'],5),'val_loss':round(val['loss'],5)})
            print(cfg.id,'epoch',epoch,'val',round(val['accuracy']*100,2),'%',flush=True)
            if val['accuracy']>best_val:
                best_val=val['accuracy']
                best_epoch=epoch
                best_weights={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
        model.load_state_dict(best_weights)
        test=evaluate(model,test_loader,device)
        torch.save(best_weights,output/'checkpoints'/f'{cfg.id}.pt')
        item={'id':cfg.id,'name':cfg.name,'description':cfg.description,'channels':[cfg.c1,cfg.c2],'kernel':cfg.kernel,'params':param_count(cfg),
              'macs':mac_breakdown(cfg),'validation_accuracy':round(best_val,5),'test_accuracy':round(test['accuracy'],5),
              'best_epoch':best_epoch,'history':history}
        results['models'].append(item)
        path=output/'results'/'experiments.json'
        if path.exists() and args.model:
            old=json.loads(path.read_text()); results['models']=[e for e in old.get('models',[]) if e['id']!=cfg.id]+results['models']
        path.write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
        print(cfg.id,'TEST',round(test['accuracy']*100,2),'%','MAC',item['macs']['total'],flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir',default='data',help='root with MNIST/raw/ files; or use --download')
    parser.add_argument('--download',action='store_true',help='download public MNIST files via torchvision')
    parser.add_argument('--epochs',type=int,default=5)
    parser.add_argument('--model',choices=[p.id for p in PRESETS])
    parser.add_argument('--batch-size',type=int,default=256)
    parser.add_argument('--lr',type=float,default=0.001)
    parser.add_argument('--threads',type=int,default=4)
    parser.add_argument('--cuda',action='store_true')
    run(parser.parse_args())

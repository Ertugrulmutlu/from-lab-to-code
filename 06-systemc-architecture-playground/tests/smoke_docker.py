"""Run from project root: python -m tests.smoke_docker (requires built image)."""
from app import execute, ROOT, model_files
for model in ['functional','full','ripple','cpu']:
    params=dict(model=model,files=model_files(model),program=(ROOT/'models'/'fibonacci.asm').read_text(),a=1 if model=='full' else 7,b=1 if model=='full' else 5,cin=0,width=4,latency=10)
    r=execute(params)
    assert r['ok'],(model,r['log'])
    assert r['events'] and r['vcd'],model
    if model=='functional':
        assert r['events'][-1]['sum']==12 and r['events'][-1]['a']==7 and r['events'][-1]['b']==5, r['events']
    if model=='full':
        e=r['events'][-1]
        assert (e['a'],e['b'],e['cin'],e['sum'],e['cout'])==(1,1,0,0,1), e
    if model=='cpu':
        assert any(e.get('op')=='WRITE' and e.get('value')==55 for e in r['events']),r['events']
        assert any(e.get('op')=='HALT' and e['registers'][4]==55 for e in r['events']),r['events']
    print(model,'PASS',len(r['events']),'events')
for width in [8,16,32]:
    r=execute(dict(model='ripple',files=model_files('ripple'),width=width,a=2**width-1,b=1))
    assert r['ok'],r['log'];print('ripple',width,'PASS')

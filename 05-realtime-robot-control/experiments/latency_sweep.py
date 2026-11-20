"""Reproduce the latency-sweep figure, without additional dependencies."""
from pathlib import Path
import json
from robot_lab.simulation import Settings, compare

ROOT = Path(__file__).resolve().parents[1]
RESULTS=ROOT/'results'


def run_sweep():
    results=[]
    for rtt in [0,25,50,75,100,150,200,250,300,350,400]:
        observation=compare(Settings(network_rtt_ms=rtt, jitter_ms=20, seed=2026))
        results.append({'rtt_ms':rtt,**{mode:{
            'outcome':observation[mode]['result'],
            'clearance_m':observation[mode]['metrics']['final_clearance_m'],
            'brake_command_at_s':observation[mode]['controller']['brake_requested_at'],
            'elapsed_s':observation[mode]['metrics']['time_s'],
        } for mode in ('blocking','async')}})
    return results


def render_svg(data):
    W,H=930,465
    x0,x1=95,895
    y0,y1=350,75
    maximum=5
    x=lambda rtt:x0+(x1-x0)*rtt/400
    y=lambda clearance:y0-(y0-y1)*min(max(clearance,0),maximum)/maximum
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           '<rect width="930" height="465" rx="16" fill="#0b1720"/>',
           '<text x="35" y="35" fill="#eaf4f4" font-family="monospace" font-size="20">Project #05 / Network RTT vs. final clearance</text>',
           '<text x="35" y="57" fill="#8da3ae" font-family="monospace" font-size="12">Jitter 20 ms · speed 10 m/s · seed 2026 · one deterministic run per strategy</text>']
    for val in range(6):
        yy=y(val)
        parts.extend([f'<line x1="{x0}" x2="{x1}" y1="{yy}" y2="{yy}" stroke="#28414b"/>',
                      f'<text x="80" y="{yy+4}" text-anchor="end" fill="#8da3ae" font-family="monospace" font-size="12">{val} m</text>'])
    for rtt in [0,100,200,300,400]:
        parts.append(f'<text x="{x(rtt)}" y="374" text-anchor="middle" fill="#8da3ae" font-family="monospace" font-size="12">{rtt}</text>')
    parts.append('<text x="495" y="411" fill="#a9bec6" font-family="monospace" font-size="12" text-anchor="middle">Network round trip time (ms)</text>')
    for mode,color in [('blocking','#f0786a'),('async','#b9f477')]:
        points=' '.join(f'{x(row["rtt_ms"]):.1f},{y(row[mode]["clearance_m"]):.1f}' for row in data)
        parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="3"/>')
        for row in data:
            cx,cy=x(row['rtt_ms']),y(row[mode]['clearance_m'])
            parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="{color}"/>')
            if row[mode]['outcome']=='collision':
                parts.append(f'<path d="M{cx-3:.1f} {cy-3:.1f}l6 6 m0 -6l-6 6" stroke="#0b1720" stroke-width="1.5"/>')
    parts.extend(['<rect x="570" y="424" width="12" height="4" fill="#f0786a"/><text x="590" y="432" fill="#c5d5d8" font-family="monospace" font-size="12">Blocking</text>',
                  '<rect x="720" y="424" width="12" height="4" fill="#b9f477"/><text x="740" y="432" fill="#c5d5d8" font-family="monospace" font-size="12">Non-blocking</text>',
                  '</svg>'])
    return '\n'.join(parts)


if __name__=='__main__':
    data=run_sweep()
    RESULTS.mkdir(exist_ok=True)
    (RESULTS/'latency_sweep.json').write_text(json.dumps({'source':'deterministic simulated network; no real-network data','rows':data},indent=2)+'\n',encoding='utf-8')
    (RESULTS/'latency_sweep.svg').write_text(render_svg(data),encoding='utf-8')
    print('Wrote',RESULTS/'latency_sweep.json','and',RESULTS/'latency_sweep.svg')

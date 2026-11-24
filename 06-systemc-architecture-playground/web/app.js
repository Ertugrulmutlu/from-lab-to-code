'use strict';
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '—').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const meta = {
  functional: ['Functional adder', 'Integer arithmetic and event-driven SC_METHOD.'],
  full: ['Full adder', 'Gate stages, exhaustive truth table and delta-cycle observations.'],
  ripple: ['Ripple carry adder', 'Explore carry propagation across 4, 8, 16 or 32 bits.'],
  cpu: ['CPU / TLM platform', 'Run a compact assembly ISA with real TLM memory transactions.']
};

let templates = {}, sources = {}, program = '', originalProgram = '';
let model = 'full', tab = '', monacoEditor = null, monacoLoading = false;
let result = null, idx = 0, playing = null, zoom = 1, selected = new Set(), busy = false;
let viewMode = 'live', schematic = null, parseTimer = null, parseVersion = 0;

const editor = $('editor');
const gutter = $('gutter');

function svg(content, w = 600, h = 220){
  return `<svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg" role="img">${content}</svg>`;
}
function box(x,y,w,h,label,value,active=false){
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="10" fill="${active?'#193e35':'#172638'}" stroke="${active?'#66e1b4':'#4a6078'}"/>
  <text x="${x+w/2}" y="${y+22}" text-anchor="middle" fill="#a9bed4" font-size="12">${esc(label)}</text>
  <text x="${x+w/2}" y="${y+h-12}" text-anchor="middle" fill="${active?'#66e1b4':'#e5edf6'}" font-family="monospace" font-size="17">${esc(value)}</text>`;
}
function wire(d,v,color=null){
  const on = v===1 || v===true;
  return `<path d="${d}" stroke="${color || (on?'#66e1b4':'#52667e')}" stroke-width="${on?3:2}" fill="none" stroke-linejoin="round"/>`;
}
function stop(){ clearInterval(playing); playing = null; $('play').textContent = 'Play'; }
function getCode(){ return monacoEditor ? monacoEditor.getValue() : editor.value; }
function isCpp(){ return tab !== 'program.asm'; }
function setCode(v){
  if(typeof v !== "string") throw new Error("Invalid source file; restart the matching backend.");
  if(monacoEditor){
    monacoEditor.setValue(v);
    monaco.editor.setModelLanguage(monacoEditor.getModel(), isCpp() ? 'cpp' : 'plaintext');
  } else editor.value = v;
  updateEditorMeta();
}
function save(){
  if(!tab) return;
  if(isCpp()) sources[model][tab] = getCode(); else program = getCode();
}
function renderFileTabs(){
  const bar = $('file-tabs'); bar.replaceChildren();
  const names = Object.keys(sources[model]);
  if(model === 'cpu') names.push('program.asm');
  for(const name of names){
    const b = document.createElement('button');
    b.textContent = name;
    b.className = name === tab ? 'active' : '';
    b.onclick = () => editorTab(name);
    bar.append(b);
  }
  $('file-label').textContent = isCpp() ? (tab.endsWith('.h') ? 'Header' : 'C++') : 'Assembly';
}
function editorTab(t){
  if(busy || t === tab) return;
  save(); tab = t;
  setCode(isCpp() ? sources[model][t] : program);
  renderFileTabs();
}
function updateLimits(){
  const max = model === 'full' ? 1 : model === 'ripple' ? 2**Number($('width').value)-1 : 1000000;
  ['a','b'].forEach(id => { $(id).max = max; $(id).value = Math.min(max, Math.max(0, Number($(id).value)||0)); });
}
function clearResult(){
  result = null; idx = 0; zoom = 1; selected.clear();
  $('signals').replaceChildren(); $('events').replaceChildren();
  $('event-total').textContent = '0 events'; $('download').disabled = true;
  $('run-status').textContent = 'Awaiting simulation'; $('scale').textContent = '';
  render(); drawWave();
}
function switchModel(m){
  if(busy || !templates[m]) return;
  if(sources[model]) save();
  stop(); model = m; tab = Object.keys(sources[m])[0];
  setCode(sources[m][tab]); renderFileTabs();
  schematic = null;
  document.querySelectorAll('#tabs button').forEach(b => b.classList.toggle('active', b.dataset.model === m));
  $('experiment').textContent = meta[m][0]; $('description').textContent = meta[m][1];
  $('params').querySelectorAll('label').forEach(l => l.hidden = m === 'cpu');
  $('latency-label').hidden = m !== 'cpu';
  $('cin-label').hidden = !['full','ripple'].includes(m);
  $('width-label').hidden = m !== 'ripple';
  $('a').value = m === 'full' ? 1 : 7; $('b').value = m === 'full' ? 1 : 5;
  updateLimits(); clearResult(); requestSchematic(true);
}

function updateHighlight(value){
  const pre=$('highlight'), pattern=/(\/\*[\s\S]*?\*\/|\/\/[^\n]*|"(?:\\.|[^"\\])*"|\b(?:void|int|bool|auto|const|return|if|else|for|while|class|struct|unsigned|using|namespace|try|catch|throw|true|false|SC_MODULE|SC_CTOR|SC_METHOD|SC_THREAD|sc_in|sc_out|sc_signal|sc_vector|MOVI|MOV|ADD|ADDI|JNZ|STORE|LOAD|HALT)\b|\b\d+\b)/g;
  let out='',last=0;
  for(const m of value.matchAll(pattern)){out+=esc(value.slice(last,m.index)); const v=m[0];const c=v.startsWith('//')||v.startsWith('/*')?'tok-comment':v.startsWith('"')?'tok-string':/^\d/.test(v)?'tok-num':'tok-key';out+=`<span class="${c}">${esc(v)}</span>`;last=m.index+v.length;}
  pre.innerHTML=out+esc(value.slice(last))+'\n';pre.scrollTop=editor.scrollTop;pre.scrollLeft=editor.scrollLeft;
}
function updateEditorMeta(){
  if(monacoEditor){
    const pos = monacoEditor.getPosition();
    $('cursor-status').textContent = `${pos.lineNumber}:${pos.column}`;
    const lines = monacoEditor.getValue().split('\n').length;
    $('line-count').textContent = `${lines} lines`;
    $('editor-status').textContent = isCpp() ? 'Monaco editor · C++' : 'Monaco editor · text';
    gutter.textContent = '';
    return;
  }
  const val = editor.value || ''; updateHighlight(val);
  const lines = val.split('\n').length;
  gutter.textContent = Array.from({length:lines}, (_,i)=> String(i+1)).join('\n');
  gutter.scrollTop = editor.scrollTop;
  const before = val.slice(0, editor.selectionStart).split('\n');
  const line = before.length, col = before[before.length-1].length + 1;
  $('cursor-status').textContent = `${line}:${col}`;
  $('line-count').textContent = `${lines} lines`;
  $('editor-status').textContent = isCpp() ? 'Syntax editor · C++' : 'Syntax editor · assembly';
}

async function requestSchematic(force=false){
  if(!isCpp() && !force) return;
  const version = ++parseVersion;
  $('parser-status').textContent = 'Parsing…';
  try{
    const r = await fetch('/api/schematic', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({model, files: sources[model]})
    });
    const data = await r.json();
    if(!r.ok) throw Error(data.error || r.statusText);
    if(version !== parseVersion) return;
    schematic = data.schematic;
    $('parser-status').textContent = schematic.instances?.length ? 'Auto schematic ready' : 'No top-level structure found';
    if(viewMode === 'auto' || !result) render();
  } catch(e){
    if(version !== parseVersion) return;
    schematic = null;
    $('parser-status').textContent = 'Parser unavailable';
  }
}
function queueSchematic(){ clearTimeout(parseTimer); parseTimer = setTimeout(() => { save(); requestSchematic(true); }, 450); }

function renderLiveGraph(e){
  const g = $('graph'), d = $('detail');
  d.replaceChildren();
  if(model === 'functional'){
    g.innerHTML = svg(
      wire('M135 55 H220 V90 H245', !!e?.a) +
      wire('M135 145 H220 V120 H245', !!e?.b) +
      wire('M365 105 H465', !!e?.sum) +
      box(35,25,100,60,'A',e?.a) + box(35,115,100,60,'B',e?.b) +
      box(245,65,120,80,'SC_METHOD','A + B') + box(465,75,105,60,'SUM',e?.sum,!!e?.sum)
    );
  } else if(model === 'full'){
    const v = e || {};
    g.innerHTML = svg(
      wire('M100 40 H135 V55 H170', v.a) + wire('M100 100 H145 V75 H170', v.b) +
      wire('M135 40 V140 H170', v.a) + wire('M145 100 V160 H170', v.b) +
      wire('M270 65 H300 V55 H330', v.x) + wire('M300 65 V130 H330', v.x) +
      wire('M100 180 H310 V75 H330', v.cin) + wire('M310 180 V150 H330', v.cin) +
      wire('M270 150 H460 V165 H480', v.ab) + wire('M430 140 H455 V145 H480', v.xc) + wire('M430 65 H500', v.sum) +
      box(20,15,80,50,'A',v.a,v.a===1) + box(20,75,80,50,'B',v.b,v.b===1) + box(20,155,80,50,'Cin',v.cin,v.cin===1) +
      box(170,40,100,50,'XOR',v.x,v.x===1) + box(170,125,100,50,'AND',v.ab,v.ab===1) +
      box(330,40,100,50,'XOR',v.sum,v.sum===1) + box(330,115,100,50,'AND',v.xc,v.xc===1) +
      box(480,130,100,60,'OR / Cout',v.cout,v.cout===1) + box(500,40,80,50,'SUM',v.sum,v.sum===1), 600, 220
    );
  } else if(model === 'ripple'){
    let bits = e?.bits || Array.from({length:Number($('width').value)}, () => [null,null,null,null,null]);
    if(!Array.isArray(bits)) bits = [];
    const cols = Math.min(bits.length, 8) || 4, rows = Math.ceil(bits.length / cols) || 1;
    let out = '';
    bits.slice(0,32).forEach((b,i) => {
      if(!Array.isArray(b)) return;
      const x = 15 + (i % cols) * 73, y = 18 + Math.floor(i / cols) * 125;
      out += `<text x="${x+28}" y="${y+8}" text-anchor="middle" fill="#9eb3c9" font-size="10">A${i}:${esc(b[0])} B${i}:${esc(b[1])}</text>` +
        wire(`M${x-7} ${y+55} H${x}`, b[2]) + box(x, y+20, 57, 65, 'FA '+i, b[3], b[3]===1) +
        `<text x="${x+28}" y="${y+100}" text-anchor="middle" fill="#a9bed4" font-size="10">Cout ${esc(b[4])}</text>` +
        wire(`M${x+57} ${y+55} H${x+66}`, b[4]);
    });
    g.innerHTML = svg(out, Math.max(320, cols*73+24), rows*125+10);
    if(e?.bits && bits.every(b => Array.isArray(b))){
      const sum = bits.reduce((n,b,i) => n + Number(b[3]||0)*2**i, 0) + Number(bits.at(-1)?.[4]||0)*2**bits.length;
      d.innerHTML = `<p>Observed sum (including carry): <strong>${sum}</strong></p><p>LSB first; rows wrap at 8 bits.</p>`;
    }
  } else {
    const events = result?.events || [], curr = events.slice(0, idx+1), last = curr.findLast(x => x.kind === 'instruction');
    const tx = curr.findLast(x => x.kind === 'transaction'); const mem = new Map();
    curr.filter(x => x.kind === 'transaction' && x.op === 'WRITE').forEach(x => mem.set(x.address, x.value));
    g.innerHTML = svg(
      box(20,45,160,110,'CPU / initiator',last?.op) + wire('M180 100 H420', e?.kind==='transaction') +
      `<text x="300" y="85" text-anchor="middle" fill="#a9bed4" font-size="13">TLM b_transport</text>` +
      `<text x="300" y="124" text-anchor="middle" fill="#66e1b4" font-size="13">${esc(e?.kind==='transaction' ? `${e.op} @ 0x${Number(e.address).toString(16)}` : 'socket bound')}</text>` +
      box(420,45,160,110,'MEMORY / target',mem.size+' words', e?.kind==='transaction'), 600, 195
    );
    const regs = last?.registers || Array(8).fill('—');
    d.innerHTML = `<div class="registers">${regs.slice(0,8).map((r,i)=>`<span>R${i} = ${esc(r)}</span>`).join('')}</div>
      <p>PC: ${esc(last?.pc)} · Last transaction: ${esc(tx?.op)} ${tx ? '0x'+Number(tx.address).toString(16)+' = '+esc(tx.value) : ''}</p>
      <p>Memory: ${[...mem].map(([a,v]) => '0x'+Number(a).toString(16)+' = '+esc(v)).join(' · ') || 'No writes yet'}</p>`;
  }
}

function normalizeSignal(name){ return String(name || '').replace(/\[[^\]]+\]/g, '[]'); }

function render(){
  const ev = result?.events || [], e = ev[idx];
  $('time').textContent = viewMode === 'auto' ? '—' : (e ? `${e.time_ns} ns` : '—');
  $('delta').textContent = viewMode === 'auto' ? '—' : (e ? e.delta : '—');
  $('kind').textContent = viewMode === 'auto' ? 'auto schematic' : (e ? e.kind : '—');
  $('seek').max = Math.max(0, ev.length - 1); $('seek').value = idx;
  $('event-count').textContent = ev.length ? `${idx+1} / ${ev.length}` : '0 / 0';
  $('graph').classList.toggle('analysis-mode', viewMode === 'auto'); if(viewMode === 'auto') renderAutoGraph(); else renderLiveGraph(e);
  document.querySelectorAll('.event-row.active').forEach(x => x.classList.remove('active'));
  const row = $('events').children[idx];
  if(row && viewMode === 'live'){
    row.classList.add('active');
    const list = $('events');
    if(row.offsetTop < list.offsetTop + list.scrollTop || row.offsetTop + row.offsetHeight > list.offsetTop + list.scrollTop + list.clientHeight)
      list.scrollTop = row.offsetTop - list.offsetTop;
  }
  drawWave();
}
function seek(i){ idx = Math.max(0, Math.min((result?.events.length || 1) - 1, i)); render(); }

function showResult(r){
  result = r; idx = Math.max(0, r.events.length - 1); zoom = 1;
  $('console').textContent = r.log || '(no output)';
  $('run-status').textContent = r.ok ? 'Simulation passed' : 'Build / simulation failed';
  $('download').disabled = !r.vcd; $('event-total').textContent = r.events.length + ' events';
  $('events').replaceChildren();
  r.events.forEach((e,i) => {
    const row = document.createElement('div'); row.className = 'event-row';
    const desc = e.kind === 'instruction' ? `${e.pc}: ${e.op}` : e.kind === 'transaction' ? `${e.op} @ ${e.address} = ${e.value}` : e.kind;
    [`${e.time_ns} ns`, `Δ ${e.delta}`, desc].forEach(v => { const span = document.createElement('span'); span.textContent = v; row.append(span); });
    row.onclick = () => { setView('live'); seek(i); };
    $('events').append(row);
  });
  $('signals').replaceChildren();
  selected = new Set(r.waveform.signals.slice(0, model === 'ripple' ? 12 : 16).map(x => x.name));
  r.waveform.signals.forEach(s => {
    const l = document.createElement('label'), c = document.createElement('input');
    c.type = 'checkbox'; c.checked = selected.has(s.name);
    c.onchange = () => { c.checked ? selected.add(s.name) : selected.delete(s.name); drawWave(); };
    l.append(c, s.name.replace(/^SystemC\./,'')); $('signals').append(l);
  });
  $('scale').textContent = r.waveform.timescale; setView('live');
}

function drawWave(){
  const canvas = $('wave'), ctx = canvas.getContext('2d');
  const signals = (result?.waveform.signals || []).filter(s => selected.has(s.name));
  let w = Math.max(300, $('wave-scroll').clientWidth - 20) * zoom;
  let h = Math.max(120, signals.length*36 + 42);
  canvas.width = Math.min(18000, Math.round(w)); canvas.height = h; w = canvas.width;
  ctx.fillStyle = '#0c1420'; ctx.fillRect(0,0,w,h); ctx.font = '11px Consolas, monospace';
  ctx.fillStyle = '#8da0b7';
  if(!signals.length){ ctx.fillText('Run a model to inspect VCD signals.', 15, 35); return; }
  const left = 125, end = Math.max(1, result.waveform.end), x = t => left + t/end * (w-left-20);
  for(let i=0;i<=10;i++){
    const t = end*i/10; ctx.strokeStyle = '#243244'; ctx.beginPath(); ctx.moveTo(x(t),23); ctx.lineTo(x(t),h); ctx.stroke();
    ctx.fillStyle = '#8da0b7'; ctx.fillText(Number(t.toFixed(1)) + '', x(t), 15);
  }
  signals.forEach((s,i) => {
    const y = 35 + i*36; ctx.fillStyle='#b9cce0'; ctx.fillText(s.name.split('.').at(-1).slice(0,17), 8, y+16); ctx.strokeStyle='#66e1b4'; ctx.lineWidth=1.5;
    const c = s.changes;
    if(s.width===1){
      const level = v => v==='1' ? y : v==='0' ? y+20 : y+10;
      ctx.beginPath(); let prev = c[0]?.[1] ?? 'x'; ctx.moveTo(x(0), level(prev));
      for(const [t,v] of c){ ctx.lineTo(x(t), level(prev)); ctx.lineTo(x(t), level(v)); prev = v; }
      ctx.lineTo(x(end), level(prev)); ctx.stroke();
    }else{
      for(let j=0;j<c.length;j++){
        const [t,v] = c[j], x1 = x(t), x2 = x(c[j+1]?.[0] ?? end); ctx.strokeRect(x1,y,Math.max(0,x2-x1),20);
        const label = /^[01]+$/.test(v) ? '0x'+BigInt('0b'+v).toString(16) : v;
        if(x2-x1 > ctx.measureText(label).width + 8){ ctx.fillStyle='#66e1b4'; ctx.fillText(label, x1+4, y+14); }
      }
    }
  });
  const ev = result?.events[idx], m = result?.waveform.timescale.match(/(\d+)\s*(fs|ps|ns|us|ms|s)/);
  if(ev && m){
    const factor = ({fs:1e-6, ps:1e-3, ns:1, us:1e3, ms:1e6, s:1e9})[m[2]] * Number(m[1]);
    const pos = x(ev.time_ns / factor);
    if(pos <= w-20){ ctx.strokeStyle='#f5bd67'; ctx.beginPath(); ctx.moveTo(pos,22); ctx.lineTo(pos,h); ctx.stroke(); }
  }
}

function setView(mode){
  viewMode = mode;
  $('live-view').classList.toggle('active', mode === 'live');
  $('auto-view').classList.toggle('active', mode === 'auto');
  render();
}

async function run(){
  if(busy) return;
  save(); stop(); busy = true; $('run').disabled = true; $('run').textContent = 'Building…';
  $('run-status').textContent = 'Running isolated simulation'; $('console').textContent = 'Compiling and executing in Docker…';
  try{
    const r = await fetch('/api/run', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        model, files:sources[model], program,
        a:Number($('a').value), b:Number($('b').value), cin:Number($('cin').value),
        width:Number($('width').value), latency:Number($('latency').value)
      })
    });
    const data = await r.json();
    if(!r.ok) throw Error(data.error || r.statusText);
    showResult(data);
  } catch(e){
    clearResult(); $('run-status').textContent = 'Runner error'; $('console').textContent = e.message;
  } finally {
    busy = false; $('run').disabled = false; $('run').textContent = '▶ Build & run';
  }
}

function startMonaco(){
  if(monacoLoading || monacoEditor) return;
  monacoLoading = true; $('editor-status').textContent = 'Loading Monaco…';
  const script = document.createElement('script'); script.src='https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs/loader.js';
  script.onerror = () => { monacoLoading=false; $('editor-status').textContent='Offline syntax editor · C++'; };
  script.onload = () => {
    const base='https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/';
    window.MonacoEnvironment = { getWorkerUrl:()=> URL.createObjectURL(new Blob([`self.MonacoEnvironment={baseUrl:'${base}'};importScripts('${base}vs/base/worker/workerMain.js');`], {type:'text/javascript'})) };
    window.require.config({paths:{vs:base+'vs'}});
    window.require(['vs/editor/editor.main'], () => {
      const val = editor.value; $('monaco').style.display='block'; editor.style.display='none'; gutter.style.display='none'; $('highlight').hidden=true;
      monacoEditor = monaco.editor.create($('monaco'), { value:val, language: isCpp() ? 'cpp' : 'plaintext', theme:'vs-dark', automaticLayout:true, minimap:{enabled:true}, fontSize:13, scrollBeyondLastLine:false });
      monacoEditor.onDidChangeModelContent(() => { updateEditorMeta(); if(isCpp()) queueSchematic(); });
      monacoEditor.onDidChangeCursorPosition(updateEditorMeta);
      updateEditorMeta(); monacoLoading = false;
    }, () => { monacoLoading=false; $('editor-status').textContent='Offline syntax editor · C++'; });
  };
  document.head.append(script);
};

editor.addEventListener('keydown', e => {
  if(e.key === 'Tab'){ e.preventDefault(); editor.setRangeText('    ', editor.selectionStart, editor.selectionEnd, 'end'); updateEditorMeta(); queueSchematic(); }
});
editor.addEventListener('input', () => { updateEditorMeta(); if(isCpp()) queueSchematic(); });
editor.addEventListener('scroll', updateEditorMeta);
editor.addEventListener('click', updateEditorMeta);
editor.addEventListener('keyup', updateEditorMeta);

document.querySelectorAll('#tabs button').forEach(b => b.onclick = () => switchModel(b.dataset.model));
$('reset').onclick = () => {
  if(busy) return;
  if(isCpp()){ sources[model][tab] = templates[model][tab]; setCode(sources[model][tab]); requestSchematic(true); }
  else { program = originalProgram; setCode(program); }
};
$('run').onclick = run;
$('width').onchange = () => { updateLimits(); if(viewMode==='auto') render(); };
$('seek').oninput = e => { stop(); seek(Number(e.target.value)); };
$('prev').onclick = () => { stop(); seek(idx-1); };
$('next').onclick = () => { stop(); seek(idx+1); };
$('play').onclick = () => {
  if(playing){ stop(); return; }
  if(!result?.events.length) return;
  if(idx === result.events.length-1) seek(0);
  $('play').textContent = 'Pause';
  playing = setInterval(() => { if(idx >= result.events.length-1) stop(); else seek(idx+1); }, 350);
};
$('zoom-in').onclick = () => { zoom = Math.min(8, zoom*1.5); drawWave(); };
$('zoom-out').onclick = () => { zoom = Math.max(1, zoom/1.5); drawWave(); };
$('clear').onclick = () => $('console').textContent = '';
$('download').onclick = () => {
  if(!result?.vcd) return;
  const a = document.createElement('a'), u = URL.createObjectURL(new Blob([result.vcd], {type:'text/plain'}));
  a.href = u; a.download = model + '.vcd'; a.click(); setTimeout(() => URL.revokeObjectURL(u), 1000);
};
$('live-view').onclick = () => setView('live');
$('auto-view').onclick = () => setView('auto');
window.addEventListener('resize', drawWave);

$('run').disabled = true;
fetch('/api/models', {cache:'no-store'}).then(r => r.json()).then(r => {
  if(r.schema !== 7 || !r.models || Object.keys(meta).some(m => !r.models[m] || typeof r.models[m] !== 'object' || typeof r.models[m]['main.cpp'] !== 'string' || Object.values(r.models[m]).some(v => typeof v !== 'string'))) throw Error('Frontend/backend versions do not match. Open the v0.7 server on port 5058.');
  templates = r.models; sources = JSON.parse(JSON.stringify(templates)); program = originalProgram = r.program;
  switchModel(model); $('run').disabled = false; updateEditorMeta(); startMonaco();
}).catch(e => { $('console').textContent = 'Could not load source templates: ' + e.message; $('run-status').textContent = 'Source loading failed'; $('parser-status').textContent = 'Unavailable'; });
fetch('/api/health').then(r => r.json()).then(r => $('health').textContent = r.docker ? 'Docker CLI detected · local runner' : 'Docker CLI not detected').catch(() => $('health').textContent='Backend unavailable');

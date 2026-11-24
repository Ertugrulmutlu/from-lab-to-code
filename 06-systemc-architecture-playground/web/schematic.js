/* Source-derived connectivity lanes and process analysis. No simulated values invented. */
function renderAutoGraph(){
  const g=$('graph'), d=$('detail');
  if(!schematic?.instances?.length){g.innerHTML='<div class="schem-note">No recognised top-level modules.</div>';d.textContent='Check SC_MODULE and sc_main declarations.';return;}
  const insts=schematic.instances, nets=schematic.signals, binds=schematic.bindings;
  const nameOf=i=>`${i.name} : ${i.type}`;
  const chip=(s,cls='')=>`<span class="net-chip ${cls}">${esc(s)}</span>`;
  const isObserver=i=>/monitor|observer/i.test(i.type);
  const top=insts.filter(i=>!isObserver(i));
  const label=(t,sub='')=>`<div class="schem-heading"><strong>${esc(t)}</strong><small>${esc(sub)}</small></div>`;
  let html='';
  if(nets.length){
    html+='<div class="net-table-wrap"><table class="net-table"><thead><tr><th>Net</th>'+insts.map(i=>`<th>${esc(i.name)}<small>${esc(i.type)}${isObserver(i)?' · observer':''}</small></th>`).join('')+'</tr></thead><tbody>';
    for(const net of nets){
      html+=`<tr><th>${esc(net)}</th>`+insts.map(i=>{
        const linked=binds.filter(b=>b.kind==='signal'&&b.instance===i.name&&b.signal===net);
        const internal=net.startsWith(i.name+'.')&&i.internal?.some(p=>p.name===net.slice(i.name.length+1));
        return '<td>'+ (linked.length?linked.map(b=>chip((b.direction==='out'?'OUT → ':b.direction==='in'?'→ IN ':'↔ ')+b.port,b.direction)).join(' '):internal?chip('Internal','internal'):'<span class="empty-net">—</span>')+'</td>';
      }).join('')+'</tr>';
    }
    html+='</tbody></table></div>';
  }
  const connectivity = html; html = '<div class="schem-board">';
  for(const b of binds.filter(b=>b.kind==='bind')){
    const f=insts.find(i=>i.name===b.from.instance),t=insts.find(i=>i.name===b.to.instance);
    if(!f||!t)continue;
    html+=`<div class="socket-flow"><div class="module-tile"><small>INITIATOR</small><strong>${esc(nameOf(f))}</strong>${chip(b.from.port,'out')}</div><div class="socket-link"><small>TLM socket binding</small><span>⇄</span><small>Request / response</small></div><div class="module-tile"><small>TARGET</small><strong>${esc(nameOf(t))}</strong>${chip(b.to.port,'in')}</div></div>`;
  }
  for(const i of top){
    html+=label(nameOf(i),'Source analysis · static structure, not runtime values');
    if(i.processes?.length){
      for(const p of i.processes){
        const writes=p.writes||[];
        html+=`<div class="process-flow"><div class="flow-side">${(p.reads||[]).map(x=>chip(x,'in')).join('')||'<small>No direct .read() detected</small>'}</div><div class="flow-arrow">→</div><div class="process-tile"><small>${esc(p.kind)}</small><strong>${esc(p.name)}()</strong>${writes.map(w=>`<code>${esc(w.net)} = ${esc(w.expression.replace(/\.read\(\)/g,''))}</code>`).join('')}</div><div class="flow-arrow">→</div><div class="flow-side">${writes.map(w=>chip(w.net,'out')).join('')||'<small>No direct .write() detected</small>'}</div></div>`;
      }
    }
    for(const cb of i.callbacks||[])html+=`<div class="process-tile"><small>TLM TARGET CALLBACK</small><strong>${esc(cb)}()</strong></div>`;
    for(const child of i.children||[]){
      const connections=child.bindings||[], byPort=Object.fromEntries(connections.map(x=>[x.port,x.net]));
      const chain=byPort.cin?.match(/^(\w+)\[i\]$/), next=byPort.cout?.match(/^(\w+)\[i\+1\]$/);
      const width=Number($('width').value);
      html+=label(`${child.name}[] · ${child.type}`,'Vector submodule hierarchy · constructor bindings');
      if(model==='ripple'&&chain&&next&&chain[1]===next[1]&&byPort.a&&byPort.b&&byPort.sum){
        const n=Math.max(1,Math.min(32,width||4));const resolve=(v,k)=>v.replace(/\[i\+1\]/g,`[${k+1}]`).replace(/\[i\]/g,`[${k}]`);
        html+='<div class="carry-scroll"><div class="carry-chain">';
        for(let k=0;k<n;k++){
          html+=`<div class="carry-cell"><div class="bit-inputs">${chip(resolve(byPort.a,k),'in')}${chip(resolve(byPort.b,k),'in')}</div><div class="bit-arrow">↓</div><div class="carry-box"><small>${esc(child.name)}[${k}]</small><strong>${esc(child.type)}</strong><div class="carry-ports"><span>cin</span><span>cout</span></div></div><div class="bit-arrow">↓</div>${chip(resolve(byPort.sum,k),'out')}</div>`;
          if(k<n-1)html+=`<div class="carry-link"><span>${esc(chain[1])}[${k+1}]</span><b>→</b></div>`;
        }
        html+='</div></div><div class="carry-caption">'+esc(chain[1])+'[0] → first cin · last cout → '+esc(chain[1])+'['+n+'] · width from selected experiment</div>';
      }else html+='<div class="schem-note">'+connections.map(c=>`${esc(c.port)} → ${esc(c.net)}`).join(' · ')+'</div>';
    }
  }
  if(connectivity) html+='<details class="connectivity-details"><summary>Connectivity matrix · '+nets.length+' independent nets</summary>'+connectivity+'</details>';
  html+='</div>';g.innerHTML=html;
  d.innerHTML=`<p><strong>${insts.length}</strong> modules · <strong>${nets.length}</strong> nets · <strong>${binds.length}</strong> bindings</p><p>IN = reads from net · OUT = drives net · Internal = module-owned signal. Equations and process registrations are extracted from source; this is not gate-level synthesis.</p>`;
}

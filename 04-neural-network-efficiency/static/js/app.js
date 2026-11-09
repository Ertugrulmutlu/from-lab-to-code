'use strict';
const $ = id => document.getElementById(id);
const fmt = n => Math.round(n).toLocaleString('en-US');
let experiments = [], chosen = 'micro', examples = [], selectedSample = null, hasDrawing = false, lastPixels = null, pending = false;
const modelColors = {micro:'#38dfc3',compact:'#72abff',wide:'#eec17c'};
function notify(message) { const t=$('toast'); t.textContent=message;t.hidden=false; clearTimeout(notify.timeout); notify.timeout=setTimeout(()=>t.hidden=true,4500); }
async function get(url) {const res=await fetch(url);const data=await res.json();if(!res.ok)throw Error(data.detail||data.error||`HTTP ${res.status}`);return data;}
async function post(url,payload) {const res=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await res.json();if(!res.ok)throw Error(typeof data.detail==='string'?data.detail:`HTTP ${res.status}`);return data;}

function modelById(id){return experiments.find(m=>m.id===id);}
function renderModels(){
  $('model-cards').replaceChildren(...experiments.map(m=>{
    const btn=document.createElement('button');btn.type='button';btn.className='model-card'+(m.id===chosen?' active':'');btn.setAttribute('aria-pressed',m.id===chosen?'true':'false');
    btn.innerHTML=`<div class="model-card-top"><h3>${m.name}</h3><span class="model-tag">${m.id==='micro'?'UNDER 75K':m.id==='compact'?'BALANCED':'WIDER'}</span></div><p>${m.description}</p><div class="model-card-bottom"><div><small>TEST ACCURACY</small><strong class="teal">${(m.test_accuracy*100).toFixed(2)}%</strong></div><div><small>MACs / IMAGE</small><strong class="gold">${fmt(m.macs.total)}</strong></div><div><small>PARAMS</small><strong>${fmt(m.params)}</strong></div></div>`;
    btn.addEventListener('click',()=>selectModel(m.id));return btn;
  }));
}
function selectModel(id){chosen=id;renderModels();drawScatter();renderInsight();$('active-model-label').textContent=modelById(id).name.toUpperCase();if(lastPixels||selectedSample)predictNow();}
function renderInsight(){
  const selected=modelById(chosen),micro=modelById('micro'); if(!selected||!micro)return;
  const ratio=selected.macs.total/micro.macs.total,delta=(selected.test_accuracy-micro.test_accuracy)*100;
  $('insight-content').innerHTML=`<div class="insight-delta"><div><span>RELATIVE COMPUTE</span><strong class="orange">${ratio.toFixed(1)}×</strong></div><div><span>VS. MICRO ACCURACY</span><strong>+${delta.toFixed(2)} pp</strong></div></div><p class="insight-para"><b>${selected.name}</b> uses ${fmt(selected.macs.total)} theoretical MACs per image. Its measured test accuracy is <b>${(selected.test_accuracy*100).toFixed(2)}%</b>. Compare that with Micro CNN: <b>${(micro.test_accuracy*100).toFixed(2)}%</b> at only ${fmt(micro.macs.total)} MACs.</p><p class="insight-para">Training used the same data split, optimizer, epoch budget, and evaluation procedure. Results are from one fixed-seed experiment per architecture, not multi-seed confidence intervals.</p>`;
}
function drawScatter(){
  const svg=$('scatter'),X=72,Y=32,W=467,H=195;
  const maxX=1.12*Math.max(...experiments.map(m=>m.macs.total/1e6));
  const loY=Math.floor(Math.min(...experiments.map(m=>m.test_accuracy*100))-2),hiY=100;
  const x=v=>X+v/maxX*W,y=v=>Y+(hiY-v)/(hiY-loY)*H;
  let s=`<rect x="${X}" y="${Y}" width="${W}" height="${H}" rx="4" fill="#0a1826"/>`;
  for(let i=0;i<5;i++){const val=loY+(hiY-loY)*i/4;const yy=y(val);s+=`<path d="M${X} ${yy}H${X+W}" stroke="#294254" stroke-width="1" stroke-dasharray="3 5"/><text x="${X-10}" y="${yy+4}" fill="#91aabb" text-anchor="end" font-size="11" font-family="monospace">${val.toFixed(0)}%</text>`;}
  for(let i=0;i<5;i++){const val=maxX*i/4,xx=x(val);s+=`<text x="${xx}" y="${Y+H+22}" fill="#91aabb" font-size="11" text-anchor="middle" font-family="monospace">${val.toFixed(2)}</text>`;}
  const bx=x(.075);s+=`<line x1="${bx}" x2="${bx}" y1="${Y}" y2="${Y+H}" stroke="#eac17b" stroke-width="1.4" stroke-dasharray="5 5"/><text x="${bx+7}" y="${Y+12}" fill="#dfba7d" font-size="10" font-family="monospace">75k budget</text>`;
  for(const m of experiments){const xx=x(m.macs.total/1e6),yy=y(m.test_accuracy*100),color=modelColors[m.id];const active=m.id===chosen;s+=`<circle cx="${xx}" cy="${yy}" r="${active?13:10}" fill="${color}" fill-opacity=".15" stroke="${color}" stroke-opacity=".6" stroke-width="2"/><circle cx="${xx}" cy="${yy}" r="${active?6:4}" fill="${color}"/><text x="${xx}" y="${yy-19}" fill="#eef7f8" font-size="11" font-weight="bold" text-anchor="middle">${m.name.replace(' CNN','')}</text>`;}
  s+=`<text x="${X+W/2}" y="${Y+H+46}" text-anchor="middle" fill="#98b2c3" font-size="11" font-family="monospace">Approx. MACs / image (millions) →</text>`;
  svg.innerHTML=s;
}

const canvas=$('digit-canvas'),ctx=canvas.getContext('2d',{willReadFrequently:true});
function resetCanvas(){ctx.fillStyle='#000';ctx.fillRect(0,0,280,280);ctx.strokeStyle='#fff';ctx.lineWidth=21;ctx.lineCap='round';ctx.lineJoin='round';hasDrawing=false;selectedSample=null;lastPixels=null;document.querySelectorAll('.sample-btn').forEach(x=>x.classList.remove('selected'));}
resetCanvas();
let drawing=false,lastPoint=null;
function point(e){const r=canvas.getBoundingClientRect();return {x:(e.clientX-r.left)*280/r.width,y:(e.clientY-r.top)*280/r.height};}
function startDraw(e){e.preventDefault();drawing=true;selectedSample=null;lastPixels=null;document.querySelectorAll('.sample-btn').forEach(x=>x.classList.remove('selected'));canvas.setPointerCapture(e.pointerId);const p=point(e);ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(p.x+.01,p.y+.01);ctx.stroke();lastPoint=p;hasDrawing=true;}
function moveDraw(e){if(!drawing)return;e.preventDefault();const p=point(e);ctx.beginPath();ctx.moveTo(lastPoint.x,lastPoint.y);ctx.lineTo(p.x,p.y);ctx.stroke();lastPoint=p;}
function stopDraw(){drawing=false;lastPoint=null;}
canvas.addEventListener('pointerdown',startDraw);canvas.addEventListener('pointermove',moveDraw);canvas.addEventListener('pointerup',stopDraw);canvas.addEventListener('pointercancel',stopDraw);
$('clear-drawing').addEventListener('click',()=>{resetCanvas();$('prediction-number').textContent='—';$('prediction-confidence').textContent='—';$('prediction-status').textContent='Draw a number or choose a test image.';$('confidence-fill').style.width='0%';zeroBars();$('feature-maps').innerHTML='<p class="empty-note">Run a prediction to reveal the CNN’s internal activations.</p>';});
function collectPixels(){
  const data=ctx.getImageData(0,0,280,280).data;let x0=280,y0=280,x1=-1,y1=-1;
  for(let y=0;y<280;y++)for(let x=0;x<280;x++){const v=data[(y*280+x)*4];if(v>40){x0=Math.min(x0,x);x1=Math.max(x1,x);y0=Math.min(y0,y);y1=Math.max(y1,y);}}
  if(x1<0)return null;
  const w=x1-x0+1,h=y1-y0+1,scale=20/Math.max(w,h),newW=w*scale,newH=h*scale;
  const off=document.createElement('canvas');off.width=off.height=28;const g=off.getContext('2d',{willReadFrequently:true});g.fillStyle='#000';g.fillRect(0,0,28,28);g.imageSmoothingEnabled=true;g.drawImage(canvas,x0,y0,w,h,(28-newW)/2,(28-newH)/2,newW,newH);
  const raw=g.getImageData(0,0,28,28).data;return Array.from({length:28},(_,y)=>Array.from({length:28},(_,x)=>raw[(y*28+x)*4]));
}
function zeroBars(){
  $('probabilities').innerHTML=Array.from({length:10},(_,i)=>`<div class="prob-row"><span>${i}</span><div class="bar"><i style="width:0%"></i></div><span>0.0%</span></div>`).join('');
}
zeroBars();
async function predictNow(){
  if(pending)return;
  const input=selectedSample?{sample_id:selectedSample}:{pixels:lastPixels??collectPixels()};
  if(!input.sample_id&&!input.pixels){notify('Draw a number or select a test digit first.');return;}
  if(!selectedSample)lastPixels=input.pixels;
  pending=true;$('predict-btn').disabled=true;$('predict-btn').firstChild.textContent='Predicting… ';
  try{const result=await post('/api/predict',{model_id:chosen,...input});renderPrediction(result);}
  catch(e){notify(e.message);}
  finally{pending=false;$('predict-btn').disabled=false;$('predict-btn').firstChild.textContent='Run prediction ';}
}
$('predict-btn').addEventListener('click',predictNow);
function renderPrediction(r){
  $('prediction-number').textContent=r.digit;
  $('prediction-confidence').textContent=(r.confidence*100).toFixed(1)+'%';
  $('confidence-fill').style.width=(r.confidence*100).toFixed(2)+'%';
  $('prediction-status').textContent='From '+modelById(r.model_id).name+' · top predicted class';
  $('probabilities').innerHTML=r.probabilities.map((p,i)=>`<div class="prob-row ${i===r.digit?'winner':''}"><span>${i}</span><div class="bar"><i style="width:${(p*100).toFixed(4)}%"></i></div><span>${(p*100).toFixed(1)}%</span></div>`).join('');
  const root=$('feature-maps');root.replaceChildren();
  for(const feature of r.features){const wrap=document.createElement('div');wrap.className='feature-tile';const c=document.createElement('canvas');const size=feature.pixels.length;c.width=c.height=size;const g=c.getContext('2d');const pixels=g.createImageData(size,size);
    for(let i=0;i<size*size;i++){const v=feature.pixels[Math.floor(i/size)][i%size];pixels.data[i*4]=Math.round(v*.24);pixels.data[i*4+1]=Math.round(v*.93);pixels.data[i*4+2]=Math.round(v*.86);pixels.data[i*4+3]=255;}
    g.putImageData(pixels,0,0);const caption=document.createElement('span');caption.textContent=`L${feature.layer} · C${feature.channel}`;wrap.append(c,caption);root.append(wrap);
  }
}
function renderSamples(){const el=$('samples');el.replaceChildren(...examples.map(item=>{const btn=document.createElement('button');btn.type='button';btn.className='sample-btn';btn.title=`Test sample of digit ${item.label}`;btn.setAttribute('aria-label',`Select MNIST test sample of digit ${item.label}`);const img=document.createElement('img');img.src=item.url;img.alt=String(item.label);btn.appendChild(img);btn.addEventListener('click',()=>{selectedSample=item.id;lastPixels=null;hasDrawing=false;document.querySelectorAll('.sample-btn').forEach(x=>x.classList.remove('selected'));btn.classList.add('selected');const image=new Image();image.onload=()=>{ctx.fillStyle='#000';ctx.fillRect(0,0,280,280);ctx.imageSmoothingEnabled=false;ctx.drawImage(image,0,0,280,280);ctx.imageSmoothingEnabled=true;predictNow();};image.src=item.url;});return btn;}));}

function renderArchitecture(){
  const c1=Number($('c1').value),c2=Number($('c2').value),k=Number($('kernel').value);
  const conv1=28*28*c1*k*k,conv2=14*14*c1*c2*k*k,linear=7*7*c2*10,total=conv1+conv2+linear;
  const params=(c1*k*k+c1)+(c1*c2*k*k+c2)+(c2*7*7*10+10);
  $('c1-value').textContent=c1;$('c2-value').textContent=c2;$('kernel-value').textContent=`${k} × ${k}`;
  $('shape-1').textContent=`28 × 28 × ${c1}`;$('shape-2').textContent=`14 × 14 × ${c2}`;
  $('mac-estimate').textContent=fmt(total);$('param-estimate').textContent=fmt(params);
  const pct=total/75000*100,rail=$('budget-fill'),budget=$('budget-status');
  $('budget-percent').textContent=pct.toFixed(0)+'%';rail.style.width=Math.min(100,pct).toFixed(2)+'%';rail.parentNode.classList.toggle('over',total>=75000);
  budget.textContent=total<75000?'WITHIN BUDGET':'OVER BUDGET';budget.style.color=total<75000?'#86c9c9':'#fa8e96';
  $('cost-breakdown').innerHTML=[['CONV 1',conv1],['CONV 2',conv2],['DENSE',linear]].map(([label,n])=>`<div class="cost-row"><span>${label}</span><div class="track"><i style="width:${(n/total*100).toFixed(2)}%"></i></div><span>${fmt(n)} MAC</span></div>`).join('');
}
for(const id of ['c1','c2','kernel'])$(id).addEventListener('input',renderArchitecture);
$('reset-arch').addEventListener('click',()=>{$('c1').value=3;$('c2').value=6;$('kernel').value=3;renderArchitecture();});
renderArchitecture();
async function init(){
  try{
    const [overview,gallery]=await Promise.all([get('/api/overview'),get('/api/examples')]);
    experiments=overview.results.models.sort((a,b)=>a.macs.total-b.macs.total);
    examples=gallery.samples;
    if(experiments.length!==3)throw Error('Expected three trained model results.');
    renderModels();drawScatter();renderInsight();renderSamples();
  }catch(err){notify('Could not load the trained models: '+err.message);$('model-cards').innerHTML='<p class="empty-note">Experiment data unavailable; see README troubleshooting.</p>';}
}
init();

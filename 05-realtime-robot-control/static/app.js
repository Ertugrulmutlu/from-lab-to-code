'use strict';

const $ = id => document.getElementById(id);
const CONFIG_FIELDS = ['target_speed','network_rtt_ms','jitter_ms','acceleration','braking','safety_margin','poll_ms','measurement_ms','seed'];
const INTEGERS = new Set(['network_rtt_ms','jitter_ms','poll_ms','measurement_ms','seed']);
let mode = 'async', snapshot = null, latestComparison = null;
let playing = false, generation = 0, errorMessage = '';

async function api(path, body) {
  const request = body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)};
  const response = await fetch(path, request);
  let data;
  try { data = await response.json(); } catch { throw Error(`HTTP ${response.status}`); }
  if(!response.ok) throw Error(typeof data.detail === 'string' ? data.detail : `Request failed (${response.status})`);
  return data;
}
function configuration() {
  const settings = {};
  for(const field of CONFIG_FIELDS) {
    const element = $(field);
    const num = Number(element.value);
    if(!Number.isFinite(num)) throw Error(`${field} must be numeric`);
    if(num < Number(element.min) || num > Number(element.max)) throw Error(`${field} must be between ${element.min} and ${element.max}`);
    settings[field] = INTEGERS.has(field) ? Math.round(num) : num;
  }
  return {mode, settings};
}
function updateLabels() {
  const targets = {
    target_speed: ['m/s',1],network_rtt_ms:['ms',0],jitter_ms:['ms',0],braking:['m/s²',1]
  };
  for(const [field,[unit,precision]] of Object.entries(targets)) {
    const input = $(field);
    $(`label-${field}`).innerHTML = `${Number(input.value).toFixed(precision)} <span>${unit}</span>`;
    const fraction = 100*(Number(input.value)-Number(input.min))/(Number(input.max)-Number(input.min));
    input.style.background = `linear-gradient(to right,#b9f477 0 ${fraction}%,#2c4550 ${fraction}% 100%)`;
  }
}
function chooseMode(value) {
  if(value !== 'async' && value !== 'blocking') return;
  mode = value;
  $('mode-async').classList.toggle('selected',mode==='async');
  $('mode-blocking').classList.toggle('selected',mode==='blocking');
  $('comparison-note').textContent = 'Controller mode changed. Start a fresh run, or compare both strategies on the current settings.';
}
function number(value,digits=2) {return typeof value==='number' ? value.toFixed(digits) : '—';}
function paintStatus(s) {
  const status = $('sim-status'), led=$('sim-led');
  let label = 'READY';
  if(s.finished) label = s.result==='safe_stop' ? 'SAFE STOP' : (s.result==='collision' ? 'COLLISION' : 'TIMEOUT');
  else if(playing) label='SIMULATING';
  else if(s.t>0) label='PAUSED';
  status.textContent = label;
  status.classList.toggle('failed',s.result==='collision');
  led.classList.toggle('running',playing);
  led.classList.toggle('failed',s.result==='collision');
}
function updateSnapshot(s) {
  snapshot=s;
  $('stat-time').textContent=number(s.t);
  $('stat-speed').textContent=number(s.robot.speed);
  $('stat-estimate').textContent=number(s.controller.estimate);
  $('stat-threshold').textContent=number(s.controller.threshold);
  $('world-x').textContent=number(s.robot.x);
  $('gap-overlay').textContent=`${number(s.robot.gap)} m TO OBSTACLE`;
  $('log-clock').textContent=`${number(s.t)} S`;
  paintStatus(s);
  renderEvents(s.events);
  drawArena(s);
  drawChart(s);
  if(s.finished){
    playing=false;
    $('pause-btn').textContent='PAUSE';
    paintStatus(s);
  }
}
function renderEvents(events) {
  const container=$('event-stream');
  container.replaceChildren();
  for(const event of events.slice(-10).reverse()) {
    const row=document.createElement('div');row.className='log-row';
    for(const [className,text] of [['time',`${number(event.t)}s`],['tag '+event.tag,event.tag.toUpperCase()],['message',event.message]]) {
      const span=document.createElement('span');span.className=className;span.textContent=text;row.append(span);
    }
    container.append(row);
  }
}
function prepareCanvas(id) {
  const canvas=$(id), box=canvas.getBoundingClientRect(),dpr=Math.min(window.devicePixelRatio||1,2);
  const width=Math.max(1,Math.round(box.width)),height=Math.max(1,Math.round(box.height));
  if(canvas.width!==Math.round(width*dpr)||canvas.height!==Math.round(height*dpr)) {canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);}
  const c=canvas.getContext('2d'); c.setTransform(dpr,0,0,dpr,0,0);
  return {c,w:width,h:height};
}
function drawArena(s) {
  if(!s) return;
  const {c,w,h}=prepareCanvas('arena-canvas');
  c.clearRect(0,0,w,h);
  const pad=55, minX=4, maxX=s.robot.wall_x+3, scale=(w-pad*2)/(maxX-minX);
  const xx=x=>pad+(x-minX)*scale, yy=h*0.52;
  // Scientific graph-paper grid
  c.lineWidth=1;
  for(let i=0;i<=s.robot.wall_x+5;i+=4){let x=xx(i);if(x<0||x>w)continue;c.strokeStyle='rgba(152,192,193,.06)';c.beginPath();c.moveTo(x,0);c.lineTo(x,h);c.stroke();}
  for(let y=32;y<h;y+=28){c.strokeStyle='rgba(152,192,193,.06)';c.beginPath();c.moveTo(0,y);c.lineTo(w,y);c.stroke();}
  // Drivable lane
  const laneTop=yy-47,laneBottom=yy+47;
  c.fillStyle='rgba(50,97,113,.15)';c.fillRect(0,laneTop,w,94);
  c.strokeStyle='rgba(180,206,197,.22)';c.setLineDash([10,10]);
  for(const y of [laneTop,laneBottom]){c.beginPath();c.moveTo(0,y);c.lineTo(w,y);c.stroke();}
  c.setLineDash([]);
  // Danger region is based on current estimated braking threshold
  const zoneX=xx(Math.max(minX,s.robot.wall_x-s.robot.radius-s.controller.threshold));
  c.fillStyle='rgba(240,120,106,.095)';c.fillRect(zoneX,laneTop,Math.max(0,xx(s.robot.wall_x)-zoneX),94);
  c.strokeStyle='rgba(240,120,106,.65)';c.setLineDash([4,5]);c.beginPath();c.moveTo(zoneX,laneTop-14);c.lineTo(zoneX,laneBottom+14);c.stroke();c.setLineDash([]);
  c.fillStyle='#f69c89';c.font='10px monospace';c.fillText('BRAKE ZONE',Math.max(10,zoneX-37),laneTop-19);
  // Wall
  const wall=xx(s.robot.wall_x);c.fillStyle='#ed776d';c.fillRect(wall-3,laneTop-30,8,154);
  c.strokeStyle='rgba(240,120,106,.3)';for(let y=laneTop-28;y<laneBottom+35;y+=13){c.beginPath();c.moveTo(wall+6,y);c.lineTo(wall+18,y+12);c.stroke();}
  // Distance/sensor visualization
  const robotX=xx(s.robot.x),robotRad=Math.max(9,scale*s.robot.radius);
  c.strokeStyle=s.robot.collided?'#f0786a':'rgba(185,244,119,.65)';c.lineWidth=2;c.setLineDash([5,6]);c.beginPath();c.moveTo(robotX+robotRad,yy);c.lineTo(wall-6,yy);c.stroke();c.setLineDash([]);
  // Robot
  c.shadowColor=s.robot.collided?'#f0786a':'#9ff58e';c.shadowBlur=28;
  c.fillStyle=s.robot.collided?'#c45048':'#b9f477';c.beginPath();c.arc(robotX,yy,robotRad,0,Math.PI*2);c.fill();c.shadowBlur=0;
  c.strokeStyle='#0b2930';c.lineWidth=2;c.beginPath();c.moveTo(robotX-robotRad/2,yy);c.lineTo(robotX+robotRad/2,yy);c.moveTo(robotX+robotRad/6,yy-robotRad/3);c.lineTo(robotX+robotRad/2,yy);c.lineTo(robotX+robotRad/6,yy+robotRad/3);c.stroke();
  c.font='10px monospace';c.fillStyle='#e5f6ed';c.textAlign='center';c.fillText('R-05',robotX,yy-robotRad-13);
  c.font='10px monospace';c.fillStyle='#a9c7d1';c.fillText(`${number(s.robot.speed,1)} m/s`,robotX,yy+robotRad+18);c.textAlign='left';
  if(s.robot.collided){c.fillStyle='rgba(241,111,105,.9)';c.font='600 20px monospace';c.fillText('COLLISION',Math.max(20,w/2-60),h-50);}
  else if(s.result==='safe_stop'){c.fillStyle='#b9f477';c.font='600 20px monospace';c.fillText('SAFE STOP',Math.max(20,w/2-52),h-50);}
  c.strokeStyle='rgba(169,198,204,.25)';c.lineWidth=1;c.beginPath();c.moveTo(xx(8),h-52);c.lineTo(wall,h-52);c.stroke();
  c.font='9px monospace';c.fillStyle='#7894a1';c.fillText('0',xx(8),h-39);c.fillText(`${Math.round(s.robot.wall_x-8)}m`,wall-20,h-39);
}
function line(c,points,color,xx,yy){
  if(points.length===0)return;c.beginPath();let first=true;
  for(const p of points){if(!Number.isFinite(p[1]))continue;if(first){c.moveTo(xx(p[0]),yy(p[1]));first=false;}else c.lineTo(xx(p[0]),yy(p[1]));}
  c.strokeStyle=color;c.lineWidth=2;c.stroke();
}
function drawChart(s) {
  const {c,w,h}=prepareCanvas('speed-chart');c.clearRect(0,0,w,h);
  const left=33,right=12,top=14,bottom=24;
  const hist=s.history||[], maxT=Math.max(8,s.t+0.5), maxV=Math.max(4, Number(s.settings.target_speed)+2);
  const xx=t=>left+(w-left-right)*t/maxT,yy=v=>h-bottom-(h-top-bottom)*v/maxV;
  c.lineWidth=1;c.font='10px monospace';c.fillStyle='#688592';
  for(let i=0;i<=4;i++){
    const v=maxV*i/4,y=yy(v);c.strokeStyle='rgba(111,153,169,.17)';c.beginPath();c.moveTo(left,y);c.lineTo(w-right,y);c.stroke();c.fillText(v.toFixed(0),3,y+4);
  }
  for(let i=0;i<=4;i++){const t=maxT*i/4,x=xx(t);c.fillText(t.toFixed(1),x-10,h-4);}
  if(hist.length>1){
    line(c,hist.map(p=>[p.t,p.speed]),'#71c7f2',xx,yy);
    c.setLineDash([4,3]);line(c,hist.map(p=>[p.t,p.estimate]),'#b9f477',xx,yy);c.setLineDash([]);
    if(s.controller.brake_applied_at!==null){const x=xx(s.controller.brake_applied_at);c.strokeStyle='#f0786a';c.setLineDash([3,4]);c.beginPath();c.moveTo(x,top);c.lineTo(x,h-bottom);c.stroke();c.setLineDash([]);c.fillStyle='#f0786a';c.font='9px monospace';c.fillText('BRAKE',Math.min(w-49,x+4),top+9);}
  }
}
function outcomeText(s) {return s.result==='safe_stop'?'SAFE STOP':s.result==='collision'?'COLLISION':s.result.toUpperCase().replace('_',' ');}
function renderComparison(results) {
  latestComparison=results;
  $('comparison-caption').textContent=`${results.settings.network_rtt_ms} MS RTT / SEED ${results.settings.seed}`;
  for(const [key,prefix] of [['blocking','blocking'],['async','async']]){
    const result=results[key], element=$(`${prefix}-result`);
    element.textContent=outcomeText(result);
    element.className=result.result==='safe_stop'?'safe':result.result==='collision'?'collision':'';
    $(`${prefix}-clearance`).textContent=`${number(result.metrics.final_clearance_m)} m`;
    $(`${prefix}-unavailable`).textContent=`${Math.round(result.metrics.control_time_blocked_ms)} ms`;
  }
  $('comparison-note').textContent='Both strategies use the same braking threshold policy and virtual network distribution. The blocking controller waits for a second sample before every decision. This is one seeded scenario, not a reliability claim.';
  $('export-btn').disabled=false;
}
function stopPlayback(){playing=false;generation++;$('pause-btn').textContent='PAUSE';if(snapshot)paintStatus(snapshot);}
async function startRun(){
  stopPlayback();
  try{
    const c=configuration(),s=await api('/api/start',c);
    updateSnapshot(s);playing=true;const token=++generation;paintStatus(s);advanceLoop(token);
  }catch(err){showError(err);}
}
async function advanceLoop(token){
  if(!playing||token!==generation)return;
  try{
    const s=await api('/api/advance',{steps:8});
    if(token!==generation)return;
    updateSnapshot(s);
    if(playing&&!s.finished)setTimeout(()=>advanceLoop(token),55);
  }catch(err){stopPlayback();showError(err);}
}
function togglePause(){
  if(!snapshot||snapshot.finished)return;
  if(playing){stopPlayback();$('pause-btn').textContent='RESUME';}
  else {playing=true;$('pause-btn').textContent='PAUSE';const token=++generation;paintStatus(snapshot);advanceLoop(token);}
}
async function resetRun(){stopPlayback();try{updateSnapshot(await api('/api/start',configuration()));}catch(err){showError(err);}}
async function compareBoth(){
  $('compare-btn').disabled=true;$('compare-btn').textContent='RUNNING EXPERIMENTS…';
  try{renderComparison(await api('/api/compare',configuration()));}
  catch(err){showError(err);}finally{$('compare-btn').disabled=false;$('compare-btn').innerHTML='RUN BOTH STRATEGIES <span>↗</span>';}
}
function exportResults(){if(!latestComparison)return;const payload=JSON.stringify({project:'From Lab to Code #05',method:'deterministic discrete-event simulation',...latestComparison},null,2);const blob=new Blob([payload],{type:'application/json'});const url=URL.createObjectURL(blob),anchor=document.createElement('a');anchor.href=url;anchor.download='robot-control-comparison.json';document.body.append(anchor);anchor.click();anchor.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function showError(error){errorMessage=String(error?.message||error);$('comparison-note').textContent=`ERROR: ${errorMessage}`;console.error(error);}

$('mode-async').addEventListener('click',()=>chooseMode('async'));
$('mode-blocking').addEventListener('click',()=>chooseMode('blocking'));
for(const field of CONFIG_FIELDS){$(field).addEventListener('input',updateLabels);}
$('run-btn').addEventListener('click',startRun);
$('pause-btn').addEventListener('click',togglePause);
$('reset-btn').addEventListener('click',resetRun);
$('compare-btn').addEventListener('click',compareBoth);
$('export-btn').addEventListener('click',exportResults);
window.addEventListener('resize',()=>{if(snapshot){drawArena(snapshot);drawChart(snapshot);}});
updateLabels();
api('/api/state').then(updateSnapshot).catch(showError);

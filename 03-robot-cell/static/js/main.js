import {RobotView} from './scene.js';

const $ = id => document.getElementById(id);
const ELEMENTS = {phase:$('phase'), runState:$('run-state'), detected:$('detected'), gripper:$('gripper'), yaw:$('yaw'), shoulder:$('shoulder'), elbow:$('elbow'), total:$('total'), events:$('events')};
let view, busy = false, failed = false;
let selectedOutput = null;
let latestState = null;
let portsInitialized = false;
let wiringSignature = '';
let wiringBusy = false;
let ioResizePending = false;
const portButtons = new Map();
const connectionPaths = new Map();

function alertError(message) {
  const t = $('toast');
  t.textContent = message;
  t.hidden = false;
  setTimeout(() => t.hidden = true, 6500);
}
async function request(url, body = null) {
  const res = await fetch(url, {method:body ? 'POST' : 'GET', headers:body ? {'Content-Type':'application/json'}:{}, body:body ? JSON.stringify(body):undefined});
  const data = await res.json();
  if (!res.ok) throw Error(data.error || `HTTP ${res.status}`);
  return data;
}
function makePort(port, side) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'io-port io-' + side;
  button.dataset.port = port.id;
  button.title = port.id;
  button.setAttribute('aria-label', `${side} ${port.id}`);
  const led = document.createElement('i');
  led.className = 'io-port-led';
  const name = document.createElement('span');
  name.className = 'io-port-name';
  name.textContent = port.id;
  const contact = document.createElement('i');
  contact.className = 'io-contact';
  button.append(led, name, contact);
  button.addEventListener('click', () => portClick(side, port.id));
  portButtons.set(port.id, button);
  return button;
}
function makePortColumn(container, ports, side) {
  let lastGroup = null;
  for (const port of ports) {
    if (port.group !== lastGroup) {
      const label = document.createElement('div');
      label.className = 'io-group-title';
      label.textContent = port.group;
      container.appendChild(label);
      lastGroup = port.group;
    }
    container.appendChild(makePort(port, side));
  }
}
function initWiringPanel(wiring) {
  if (portsInitialized) return;
  makePortColumn($('io-outputs'), wiring.outputs, 'output');
  makePortColumn($('io-inputs'), wiring.inputs, 'input');
  portsInitialized = true;
  window.addEventListener('resize', scheduleWireDraw);
  if ('ResizeObserver' in window) {
    new ResizeObserver(scheduleWireDraw).observe($('io-board'));
  }
}
function scheduleWireDraw() {
  if (ioResizePending) return;
  ioResizePending = true;
  requestAnimationFrame(() => {ioResizePending = false; drawConnections();});
}
function drawConnections() {
  if (!latestState || !portsInitialized) return;
  const board = $('io-board');
  const svg = $('io-wires');
  const bounds = board.getBoundingClientRect();
  const w = bounds.width, h = bounds.height;
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  svg.setAttribute('width', String(w));
  svg.setAttribute('height', String(h));
  svg.replaceChildren();
  connectionPaths.clear();
  for (const connection of latestState.wiring.connections) {
    const out = portButtons.get(connection.output);
    const input = portButtons.get(connection.input);
    if (!out || !input) continue;
    const a = out.getBoundingClientRect(), b = input.getBoundingClientRect();
    const x1 = a.right - bounds.left + 4, y1 = a.top + a.height/2 - bounds.top;
    const x2 = b.left - bounds.left - 4, y2 = b.top + b.height/2 - bounds.top;
    const control = (x1+x2)/2;
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', `M ${x1} ${y1} C ${control} ${y1}, ${control} ${y2}, ${x2} ${y2}`);
    path.setAttribute('class', 'io-wire');
    path.dataset.input = connection.input;
    svg.appendChild(path);
    connectionPaths.set(connection.input, path);
  }
  updateWireLevels(latestState.wiring);
}
function updateWireLevels(wiring) {
  const connected = new Set(wiring.connections.map(c=>c.input));
  const running = Boolean(latestState.running);
  for (const port of wiring.outputs) {
    const button = portButtons.get(port.id);
    if (!button) continue;
    const high = Boolean(wiring.output_levels[port.id]);
    button.classList.toggle('high', high);
    button.classList.toggle('selected', selectedOutput === port.id);
    button.disabled = running || wiringBusy;
    button.setAttribute('aria-pressed', selectedOutput === port.id ? 'true':'false');
  }
  for (const port of wiring.inputs) {
    const button = portButtons.get(port.id);
    if (!button) continue;
    button.classList.toggle('high', Boolean(wiring.input_levels[port.id]));
    button.classList.toggle('open', !connected.has(port.id));
    button.disabled = running || wiringBusy;
  }
  for (const connection of wiring.connections) {
    const path = connectionPaths.get(connection.input);
    if (path) path.classList.toggle('high', Boolean(wiring.input_levels[connection.input]));
  }
}
function renderWiring(state) {
  initWiringPanel(state.wiring);
  const signature = JSON.stringify(state.wiring.connections);
  const edited = signature !== wiringSignature;
  if (edited) {wiringSignature = signature; scheduleWireDraw();}
  updateWireLevels(state.wiring);
  $('io-diagnostic').textContent = state.diagnostic;
  $('io-diagnostic').classList.toggle('fault', Boolean(state.fault) || /Waiting:/.test(state.diagnostic));
  $('io-hint').textContent = state.running
    ? 'Pause the simulation before editing wires. The LEDs show the live digital signal levels.'
    : selectedOutput
      ? `Selected ${selectedOutput}. Now click a destination input, or click this output again to cancel.`
      : 'Click an output, then an input to connect. Click an input alone to disconnect. Every change resets the run.';
  $('io-apply').disabled = state.running || wiringBusy;
  $('io-restore').disabled = state.running || wiringBusy;
}
async function portClick(side, id) {
  if (!latestState || latestState.running || wiringBusy) return;
  if (side === 'output') {
    selectedOutput = selectedOutput === id ? null : id;
    renderWiring(latestState);
    return;
  }
  const payload = selectedOutput
    ? {action:'connect', output:selectedOutput, input:id}
    : {action:'disconnect', input:id};
  selectedOutput = null;
  await changeWiring(payload);
}
async function changeWiring(payload) {
  if (wiringBusy) return;
  wiringBusy = true;
  try {render(await request('/api/wiring', payload));}
  catch(e){alertError(e.message);}
  finally {wiringBusy = false; if (latestState) renderWiring(latestState);}
}
function render(state) {
  latestState = state;
  view.update(state);
  ELEMENTS.phase.textContent = state.phase;
  ELEMENTS.runState.textContent = state.phase === 'FAULT' ? 'FAULT' : state.running ? 'RUNNING' : 'PAUSED';
  ELEMENTS.runState.classList.toggle('on', state.running);
  ELEMENTS.detected.textContent = state.detected_color ? state.detected_color.toUpperCase() : '—';
  ELEMENTS.detected.style.color = ({red:'#ff8189',green:'#5edeb5',blue:'#77b6ff'})[state.detected_color] || '';
  ELEMENTS.gripper.textContent = state.robot.gripping ? 'ENGAGED' : 'OPEN';
  ELEMENTS.gripper.style.color = state.robot.gripping ? '#64e6bd' : '';
  for(let i=0;i<3;i++) ELEMENTS[['yaw','shoulder','elbow'][i]].textContent = state.robot.angles_deg[i].toFixed(1) + '°';
  ELEMENTS.total.innerHTML = String(state.total).padStart(2,'0') + ' <small>ITEMS SORTED</small>';
  for(const color of ['red','green','blue']) $('count-'+color).textContent = state.counts[color];
  $('missorted').textContent = state.missorted;
  ELEMENTS.events.replaceChildren(...state.events.map(({time,message})=>{
    const li = document.createElement('li'), t = document.createElement('time'), m = document.createElement('span');
    t.textContent = Number(time).toFixed(1)+'s'; m.textContent = message; li.append(t,m); return li;
  }));
  renderWiring(state);
}
async function send(action, extra = {}) {
  try {render(await request('/api/control', {action, ...extra}));}
  catch(e){alertError(e.message);}
}
async function tick() {
  if(busy || failed || wiringBusy) return;
  busy = true;
  try {render(await request('/api/step', {dt:0.085}));}
  catch(e){failed=true; alertError('Backend connection lost: '+e.message);}
  finally {busy=false;}
}
try {
  view = new RobotView($('viewport'));
  $('loading').remove();
  render(await request('/api/state'));
  $('run').addEventListener('click',()=>send('run'));
  $('pause').addEventListener('click',()=>send('pause'));
  $('reset').addEventListener('click',()=>send('reset'));
  $('camera').addEventListener('click',()=>view.resetCamera());
  $('color').addEventListener('change',e=>send('configure',{color:e.target.value}));
  $('speed').addEventListener('input',e=>{
    $('speed-value').textContent=Number(e.target.value).toFixed(2)+'×';
    send('configure',{speed:Number(e.target.value)});
  });
  $('io-apply').addEventListener('click',()=>changeWiring({action:'preset',preset:$('io-preset').value}));
  $('io-restore').addEventListener('click',()=>{selectedOutput = null;changeWiring({action:'restore'});});
  setInterval(tick,85);
} catch(e) {
  alertError('Could not initialize 3D scene. Check your connection to the Three.js CDN. '+e.message);
  $('loading').textContent='3D VIEW UNAVAILABLE';
}

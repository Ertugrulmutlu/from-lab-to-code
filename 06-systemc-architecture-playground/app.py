"""Local web IDE. Python standard library only; execution isolated in Docker."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
import json, subprocess, tempfile, threading, time, uuid, shutil, os, re

ROOT = Path(__file__).resolve().parent
IMAGE = 'from-lab-to-code-systemc:local'
MODELS = {'functional', 'full', 'ripple', 'cpu'}
MAX_OUTPUT = 2_000_000
LOCK = threading.Lock()


FILE_ORDER = {
    'functional': ['Adder.cpp', 'Adder.h', 'main.cpp', 'Monitor.h'],
    'full': ['FullAdder.cpp', 'FullAdder.h', 'main.cpp', 'Monitor.h'],
    'ripple': ['Ripple.cpp', 'Ripple.h', 'FullAdder.cpp', 'FullAdder.h', 'main.cpp'],
    'cpu': ['CPU.cpp', 'CPU.h', 'Instructions.cpp', 'Memory.cpp', 'Memory.h', 'main.cpp'],
}
SUPPORT = ('lab.hpp', 'observations.hpp', 'cpu_support.hpp')


def model_files(model):
    return {name: (ROOT / 'models' / model / name).read_text(encoding='utf-8')
            for name in FILE_ORDER[model]}


def checked_files(model, files):
    if model not in MODELS or not isinstance(files, dict) or set(files) != set(FILE_ORDER[model]):
        raise ValueError('Invalid project file set.')
    if any(not isinstance(v, str) or not v.strip() for v in files.values()) or sum(map(len, files.values())) > 100_000:
        raise ValueError('Invalid source size.')
    return files


def schematic_source(model, files):
    files = checked_files(model, files)
    # Headers first, then implementation, then the top-level testbench.
    return '\n'.join(files[n] for n in files if n != 'main.cpp') + '\n' + files['main.cpp']


def parse_vcd(raw):
    signals = {}
    aliases = {}
    scope = []
    now = 0
    end = 0
    scale = '1 ns'
    definitions = True
    for line in raw.splitlines():
        line = line.strip()
        p = line.split()
        if not p:
            continue
        if line.startswith('$timescale'):
            if len(p) > 1 and p[1] != '$end':
                scale = ' '.join(p[1:-1] if p[-1] == '$end' else p[1:])
            else:
                scale = ''
        elif definitions and not scale and re.fullmatch(r'\d+\s*[a-zA-Z]+', line):
            scale = line
        elif p[0] == '$scope' and len(p) > 2:
            scope.append(p[2])
        elif p[0] == '$upscope' and scope:
            scope.pop()
        elif p[0] == '$var' and len(p) >= 6:
            key = p[3]
            name = '.'.join(scope + [p[4]])
            entry = {'name': name, 'width': int(p[2]), 'changes': []}
            signals[name] = entry
            aliases.setdefault(key, []).append(entry)
        elif p[0] == '$enddefinitions':
            definitions = False
        elif not definitions:
            if line.startswith('#'):
                try:
                    now = int(line[1:])
                    end = max(end, now)
                except ValueError:
                    pass
            elif line[0] in '01xXzZ':
                for item in aliases.get(line[1:], []):
                    item['changes'].append([now, line[0]])
            elif line[0] in 'bBrR' and len(p) == 2:
                for item in aliases.get(p[1], []):
                    item['changes'].append([now, p[0][1:]])
    return {'timescale': scale or '1 tick', 'end': end, 'signals': list(signals.values())}


def parse_output(raw, code):
    events, logs, vcd = [], [], []
    inside = False
    for line in raw.splitlines():
        if line == '@@VCD_BEGIN@@':
            inside = True
            continue
        if line == '@@VCD_END@@':
            inside = False
            continue
        if inside:
            vcd.append(line)
            continue
        if line.startswith('@@EVENT@@'):
            try:
                ev = json.loads(line[9:])
                if isinstance(ev, dict):
                    events.append(ev)
            except ValueError:
                logs.append(line)
        else:
            logs.append(line)
    trace = '\n'.join(vcd) + ('\n' if vcd else '')
    return {
        'ok': code == 0,
        'returncode': code,
        'log': '\n'.join(logs),
        'events': events,
        'vcd': trace,
        'waveform': parse_vcd(trace) if trace else {'signals': [], 'end': 0, 'timescale': '1 ns'},
    }


def inputs(data):
    model = data.get('model')
    files = data.get('files')
    code = schematic_source(model, files) if files is not None else data.get('code')
    program = data.get('program', '')
    if model not in MODELS or not isinstance(code, str) or not code.strip() or len(code) > 100_000 or not isinstance(program, str) or len(program) > 30_000:
        raise ValueError('Invalid model, code or program size.')
    width = int(data.get('width', 4))
    a = int(data.get('a', 7))
    b = int(data.get('b', 5))
    cin = int(data.get('cin', 0))
    latency = int(data.get('latency', 10))
    if width not in (4, 8, 16, 32) or cin not in (0, 1) or not 0 <= latency <= 1000:
        raise ValueError('Invalid simulation parameters.')
    limit = 2**width - 1 if model == 'ripple' else 1 if model == 'full' else 1_000_000
    if not 0 <= a <= limit or not 0 <= b <= limit:
        raise ValueError(f'Inputs must be between 0 and {limit}.')
    return code, program, [str(x) for x in (a, b, cin, width, latency)]


def execute(data):
    code, program, args = inputs(data)
    if not shutil.which('docker'):
        raise RuntimeError('Docker CLI not found. Start Docker Desktop and follow README.')
    if not LOCK.acquire(blocking=False):
        raise RuntimeError('Another simulation is running.')
    name = 'systemc-lab-' + uuid.uuid4().hex[:12]
    try:
        with tempfile.TemporaryDirectory(prefix='systemc-lab-') as tmp:
            path = Path(tmp)
            files = data.get('files')
            if files is None:
                (path / 'model.cpp').write_text(code, encoding='utf-8')
            else:
                for filename, content in checked_files(data['model'], files).items():
                    (path / filename).write_text(content, encoding='utf-8')
            # Mount the current runner so the existing SystemC image can be reused.
            (path / 'run.sh').write_text((ROOT / 'runner' / 'run.sh').read_text(), encoding='utf-8', newline='\n')
            (path / 'program.asm').write_text(program, encoding='utf-8')
            # Quoted includes resolve next to model.cpp; existing Docker image still works.
            for header in SUPPORT:
                shutil.copyfile(ROOT / 'models' / header, path / header)
            cmd = [
                'docker', 'run', '--rm', '--name', name, '--network', 'none', '--read-only', '--cap-drop', 'ALL',
                '--security-opt', 'no-new-privileges', '--user', '65534:65534', '--pids-limit', '64', '--memory', '768m',
                '--cpus', '1', '--ulimit', 'fsize=8388608:8388608', '--log-driver', 'none',
                '--tmpfs', '/tmp:rw,exec,nosuid,nodev,size=128m,mode=1777', '--mount',
                f'type=bind,source={path},target=/input,readonly', '--entrypoint', '/bin/bash', IMAGE, '/input/run.sh', *args
            ]
            if os.name != 'nt':
                path.chmod(0o755)
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            out = bytearray()
            overflow = threading.Event()

            def reader():
                while True:
                    chunk = p.stdout.read1(8192)
                    if not chunk:
                        break
                    room = MAX_OUTPUT - len(out)
                    out.extend(chunk[:max(0, room)])
                    if len(chunk) > room:
                        overflow.set()
                        break

            t = threading.Thread(target=reader, daemon=True)
            t.start()
            deadline = time.monotonic() + 35
            reason = ''
            while p.poll() is None:
                if overflow.is_set() or time.monotonic() > deadline:
                    reason = 'Output limit exceeded' if overflow.is_set() else 'Simulation/build timed out'
                    break
                time.sleep(.05)
            if reason:
                try:
                    subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    pass
                if p.poll() is None:
                    p.kill()
            p.wait()
            t.join(2)
            p.stdout.close()
            result = parse_output(out.decode('utf-8', 'replace'), p.returncode if not reason else 124)
            if reason or overflow.is_set():
                result['ok'] = False
                result['log'] += '\n[runner] ' + (reason or 'Output limit exceeded')
            return result
    finally:
        LOCK.release()


# ---------- lightweight auto schematic extraction ----------

def strip_comments(code: str) -> str:
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.S)
    code = re.sub(r'//.*', '', code)
    return code


def clean_net(name: str) -> str:
    name = re.sub(r'\s+', '', name)
    name = re.sub(r'\[[^\]]+\]', '[]', name)
    return name


def extract_names(chunk):
    # Split only at declaration-level commas, not constructor arguments.
    parts = re.split(r',(?=(?:[^()]*\([^()]*\))*[^()]*$)', chunk)
    return [m.group(1) for part in parts if (m := re.match(r'\s*([A-Za-z_]\w*)', part))]


def balanced_body(code, start):
    depth = 1
    for m in re.finditer(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{}]', code[start:]):
        token = m.group()
        if token == '{': depth += 1
        elif token == '}':
            depth -= 1
            if depth == 0: return code[start:start + m.start()]
    return code[start:]


def find_module_bodies(code):
    return {m.group(1): balanced_body(code, m.end()) for m in re.finditer(r'SC_MODULE\s*\(\s*(\w+)\s*\)\s*\{', code)}


def declarations(body):
    items = []
    pattern = r'sc_vector\s*<\s*sc_(in|out|inout|signal)\s*<([^>]+)>\s*>\s+([^;]+);|sc_(in|out|inout|signal)\s*<([^>]+)>\s+([^;]+);'
    for m in re.finditer(pattern, body):
        vec = m.group(1) is not None
        kind, typ, chunk = m.groups()[:3] if vec else m.groups()[3:]
        for name in extract_names(chunk):
            items.append({'name': name + ('[]' if vec else ''), 'kind': kind, 'type': typ.strip()})
    return items


def analyze_module(name, body, code, modules):
    items = declarations(body)
    ports = [x for x in items if x['kind'] != 'signal']
    for kind, port in re.findall(r'tlm_utils::simple_(initiator|target)_socket<[^>]+>\s+(\w+)', body):
        ports.append({'name': port, 'kind': kind + '_socket', 'type': 'TLM-2.0'})
    processes = []
    ctor = re.search(re.escape(name) + r'::' + re.escape(name) + r'\s*\([^)]*\)\s*[^{};]*\{', code)
    registration = body + ('\n' + balanced_body(code, ctor.end()) if ctor else '')
    for kind, fn in re.findall(r'SC_(METHOD|THREAD|CTHREAD)\s*\(\s*(\w+)', registration):
        m = re.search(r'void\s+' + re.escape(name) + r'::' + re.escape(fn) + r'\s*\([^)]*\)\s*\{', code)
        if not m:
            m = re.search(r'void\s+' + re.escape(fn) + r'\s*\([^)]*\)\s*\{', body)
            impl = balanced_body(body, m.end()) if m else ''
        else: impl = balanced_body(code, m.end())
        writes = []
        for w in re.finditer(r'(\w+)\.write\s*\(', impl):
            # Write expressions end at the matching statement delimiter.
            expression = impl[w.end():].split(';', 1)[0].strip()
            if expression.endswith(')'): expression = expression[:-1]
            writes.append({'net': w.group(1), 'expression': expression})
        reads = list(dict.fromkeys(re.findall(r'(\w+)\.read\s*\(', impl)))
        processes.append({'name': fn, 'kind': 'SC_' + kind, 'reads': reads, 'writes': writes})
    # Capture vector submodules and their symbolic bindings from constructor bodies.
    children = []
    for typ, child in re.findall(r'sc_vector\s*<\s*(\w+)\s*>\s+(\w+)\s*;', body):
        if typ not in modules: continue
        connections = [{'port': port, 'net': net.replace(' ', '')} for port, net in re.findall(re.escape(child) + r'\s*\[\s*i\s*\]\s*\.\s*(\w+)\s*\(\s*([\w\[\]+ -]+)\s*\)\s*;', code)]
        children.append({'name': child, 'type': typ, 'bindings': connections})
    callbacks = re.findall(r'\.register_b_transport\s*\(\s*this\s*,\s*&' + re.escape(name) + r'::(\w+)\s*\)', code)
    return {'ports': ports, 'internal': [x for x in items if x['kind']=='signal'], 'processes': processes, 'children': children, 'callbacks': callbacks}


def auto_schematic(code: str):
    if re.search(r'#include\s*"observations\.hpp"', code):
        code = (ROOT / 'models' / 'observations.hpp').read_text() + '\n' + code
    code = strip_comments(code)
    bodies = find_module_bodies(code)
    modules = {name: analyze_module(name, body, code, bodies) for name, body in bodies.items()}
    mm = re.search(r'int\s+sc_main\s*\([^)]*\)\s*\{', code)
    main = balanced_body(code, mm.end()) if mm else ''
    instances, instance_types, bindings = [], {}, []
    top_signals = {x['name'] for x in declarations(main) if x['kind'] == 'signal'}
    for typ, name in re.findall(r'(?<![\w:])(\w+)\s+(\w+)\s*\(', main):
        if typ in modules and name not in instance_types:
            instance_types[name] = typ
            instances.append({'name': name, 'type': typ, **modules[typ]})
    def port_info(inst, port):
        return next((x for x in modules[instance_types[inst]]['ports'] if x['name'] == clean_net(port)), None)
    for li, lp, ri, rp in re.findall(r'(\w+)\.(\w+)\.bind\(\s*(\w+)\.(\w+)\s*\)', main):
        if li in instance_types and ri in instance_types and port_info(li, lp) and port_info(ri, rp):
            bindings.append({'kind':'bind','from':{'instance':li,'port':lp},'to':{'instance':ri,'port':rp}})
    for inst, port, signal in re.findall(r'(\w+)\.(\w+(?:\[[^\]]+\])?)\s*\(\s*([^)]+?)\s*\)\s*;', main):
        if inst not in instance_types: continue
        info = port_info(inst, port)
        if not info: continue
        signal = clean_net(signal)
        if not re.fullmatch(r'\w+(?:\.\w+)?(?:\[\])?', signal): continue
        top_signals.add(signal)
        bindings.append({'kind':'signal','instance':inst,'port':clean_net(port),'signal':signal,'direction':info['kind']})
    bindings = list({json.dumps(x, sort_keys=True): x for x in bindings}.values())
    return {'modules':modules,'instances':instances,'signals':sorted(top_signals),'bindings':bindings}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'web'), **kwargs)

    def json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def allowed_host(self):
        return self.headers.get('Host', '').split(':')[0] in ('127.0.0.1', 'localhost')

    def do_GET(self):
        if not self.allowed_host():
            return self.json({'error': 'Invalid host'}, 403)
        path = urlparse(self.path).path
        if path == '/api/models':
            return self.json({
                'schema': 7,
                'models': {m: model_files(m) for m in sorted(MODELS)},
                'program': (ROOT / 'models' / 'fibonacci.asm').read_text(),
            })
        if path == '/api/health':
            return self.json({'docker': bool(shutil.which('docker')), 'image': IMAGE})
        return super().do_GET()

    def do_POST(self):
        if not self.allowed_host():
            return self.json({'error': 'Invalid host'}, 403)
        if self.path not in ('/api/run', '/api/schematic'):
            return self.json({'error': 'Not found'}, 404)
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.json({'error': 'JSON required'}, 415)
        if self.headers.get('Origin') not in (None, f'http://{self.headers.get("Host")}'):
            return self.json({'error': 'Cross-origin request rejected'}, 403)
        try:
            n = int(self.headers.get('Content-Length', '0'))
            if not 0 < n <= 200_000:
                raise ValueError('Request too large or empty.')
            data = json.loads(self.rfile.read(n))
            if self.path == '/api/run':
                return self.json(execute(data))
            code = schematic_source(data.get('model'), data['files']) if 'files' in data else data.get('code', '')
            if not isinstance(code, str) or len(code) > 100_000:
                raise ValueError('Invalid code.')
            return self.json({'schematic': auto_schematic(code)})
        except (ValueError, TypeError, AttributeError) as e:
            return self.json({'error': str(e)}, 400)
        except (RuntimeError, OSError) as e:
            return self.json({'error': str(e)}, 503)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--port', type=int, default=5058)
    args = p.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'SystemC Playground: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

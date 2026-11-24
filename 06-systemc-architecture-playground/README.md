# From Lab to Code #06 — SystemC Architecture Playground

**Build. Visualize. Explain.** An independent, local-first educational environment for real C++/SystemC compilation, event replay, digital waveforms and TLM CPU–memory modeling. Inspired by common SystemC lab topics; no university-provided starter code or PDF is distributed.

## Windows quick start

Prerequisites: Python 3.10+ and Docker Desktop running **Linux containers** (WSL2 backend recommended). No pip packages. From this project folder in PowerShell:

```powershell
docker build -t from-lab-to-code-systemc:local .
py -3 app.py
```

Open http://127.0.0.1:5058. Or run `powershell -ExecutionPolicy Bypass -File .\start.ps1` to build and start. If `py` is absent use `python`. The first Docker build needs internet to download Ubuntu and its SystemC package. The syntax-highlighted local editor starts immediately. Monaco loads automatically from the CDN when internet is available; offline syntax highlighting remains available. Docker runner is CPU-only.

Click an experiment, choose a source file tab (hardware `.h` / `.cpp`, `main.cpp` testbench, or `program.asm` in CPU mode) and edit it, change parameters, and click Build & run. The final recorded snapshot is selected automatically; click Play to replay from the beginning or use the event slider / step controls, select VCD signals, zoom and export VCD. Models are compiled afresh every run; reset restores the currently selected file. Edited source is in memory for this session only; copy it to a file before refreshing.

## Experiments

- Functional adder: signed integer SystemC ports, SC_METHOD and a timed testbench.
- Full adder: separate XOR/AND/OR stages, observed intermediate signals, all eight truth-table cases checked after settling, followed by the selected input combination.
- Ripple carry adder: 4/8/16/32-bit hierarchy, carry and sum snapshots, numerical result verification.
- CPU / memory: independently designed unsigned 32-bit teaching ISA, eight registers, actual TLM-2.0 blocking transport for data reads/writes, 256 bytes of little-endian aligned memory and configurable annotated latency. Fibonacci(10) writes 55 at address 0 and reads it into R4.

ISA syntax (uppercase, comments `#`, optional commas): `MOVI R0 10`, `MOV R1 R0`, `ADD R2 R0 R1`, `ADDI R0 R0 -1`, `JNZ R0 label`, `STORE R0 0`, `LOAD R3 0`, `HALT`; `label:` defines a branch target. Numeric literals use C++ base-0 parsing (e.g. 0x10); arithmetic wraps modulo 2^32. 4096-instruction limit. Instructions are parsed into a vector, not fetched from TLM memory; this is a simplified CPU, not the course's binary ISA or a cycle-accurate hardware implementation. Data transactions only use TLM. The target updates memory immediately and annotates delay; the initiator waits that delay. UI shows transaction issuance and instruction completion snapshots, not internal bus phases.

## Architecture and limitations

Python standard-library local HTTP API → Docker isolated GCC/SystemC runner → VCD + JSON event records → HTML/CSS/JS Canvas waveforms and SVG model views. `models/lab.hpp` supplies trace helpers; `models/observations.hpp` handles event serialization and the ripple observer, and `models/cpu_support.hpp` handles assembly parsing and TLM payload packing. Each experiment has its own folder under `models/`. Shared support headers and the current build script are mounted beside all edited files, and GCC compiles the separate `.cpp` translation units together. The existing SystemC image can be reused. Custom source can use these helpers; the Live view is template-specific. Auto schematic extracts top-level module instances, directed ports, nets, bindings, registered processes, direct read/write expressions, and common vector-submodule bindings. The connectivity matrix separates each net; recognized ripple chains are expanded using the selected width. It is not a complete C++ parser or gate-level synthesis. Source changes may make the Live view inaccurate. The replay is of actual instrumented model events (`sc_time_stamp` and `sc_delta_count`), not a full kernel phase queue or live breakpoint debugger. VCD is parsed as scalar/vector line-oriented records; it is not a complete general VCD parser. Physical time and delta count are separate. VCD timestamps may collapse intra-time delta transitions. No artificial physical gate delay is added to the baseline models.

## Safety

The server binds to loopback, accepts JSON only, and checks Host/Origin. Compile/run is in a non-root Docker container, with network disabled, read-only root and input mount, limited process count, memory, CPU, temporary filesystem, output, and wall time. Do not expose this local service to the internet or run untrusted code: containers are not a complete security boundary and this is not a hardened multi-tenant execution system. Monaco attempts to load third-party JavaScript automatically; if offline the built-in highlighted editor remains active.

## Tests

```powershell
py -3 -m unittest discover -s tests -v
node --check web/app.js  # optional, requires Node.js
py -3 -m tests.smoke_docker  # requires running Docker and the built image
```

The first command tests input validation, VCD decoding and event extraction. The Docker smoke test runs all four real C++ experiments and extra ripple widths. See `VALIDATION.md` for what was verified at packaging time.

## References

- Accellera SystemC: https://www.accellera.org/downloads/standards/systemc
- SystemC open source implementation: https://github.com/accellera-official/systemc
- Monaco Editor: https://github.com/microsoft/monaco-editor

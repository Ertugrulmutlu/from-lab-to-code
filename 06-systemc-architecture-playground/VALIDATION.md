# v0.6 integration fix

- Static files now disable caching; source API schema is validated. Port 5058 separates this release from older servers.
- Offline Chromium integration test with real model fixtures and mocked HTTP responses passed for all four models (tabs, source content, schematic SVG, multi-file build payload).
- Python unit tests: 6 passed. Docker and real HTTP browser navigation were unavailable in this environment; run `python -m tests.smoke_docker` locally.

# Validation — v0.5 / Project #06

- Original v0.1 Docker smoke tests passed on the user's Windows machine.
- v0.5 separates hardware declarations, implementations, testbench and observers; each experiment is compiled from separate .cpp translation units.
- Six Python unit tests, all four multifile schematic HTTP requests, JavaScript syntax, shell syntax and ZIP integrity checked locally.
- Existing Docker image can be reused: current runner is mounted per invocation, and its entrypoint is selected explicitly. Docker/SystemC unavailable here, so actual C++ compilation needs `python -m tests.smoke_docker` on the user's machine.
- Browser localhost navigation was blocked by the environment; interactive UI was not verified in Chromium.
- Auto schematic remains pattern-based, not general C++ synthesis.

## v0.7 update
- Seven Python unit tests pass; JS syntax checks pass.
- Chromium inline UI test with actual parser outputs injected through a mocked fetch: four experiment tabs, colored offline editor, three full-adder processes, 4/8-cell ripple chain and CPU socket/callback view pass without JS errors.
- Direct browser HTTP navigation is blocked by the packaging environment; CDN loading and Docker compilation have not been re-tested here. C++ models and Docker runner unchanged from v0.6.

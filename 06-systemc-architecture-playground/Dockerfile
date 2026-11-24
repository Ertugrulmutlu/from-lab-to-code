FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends g++ libsystemc-dev && rm -rf /var/lib/apt/lists/*
COPY runner/run.sh /opt/lab/run.sh
COPY models/lab.hpp /opt/lab/lab.hpp
RUN chmod 755 /opt/lab/run.sh
WORKDIR /tmp
ENTRYPOINT ["/bin/bash", "/opt/lab/run.sh"]

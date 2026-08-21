# Stage 1: Build CoreDNS
FROM golang:1.22 AS builder

WORKDIR /build
# Clone CoreDNS
RUN git clone --depth=1 --branch v1.11.3 https://github.com/coredns/coredns.git coredns-src

# Copy plugin files
COPY dns-threat-filter/coredns-plugin /build/coredns-plugin

# Setup plugin
RUN mkdir -p /build/coredns-src/plugin/threatfilter && \
    cp /build/coredns-plugin/threatfilter.go /build/coredns-src/plugin/threatfilter/ && \
    cp /build/coredns-plugin/setup.go /build/coredns-src/plugin/threatfilter/ && \
    sed -i.bak '/^forward:/i threatfilter:github.com/coredns/coredns/plugin/threatfilter' /build/coredns-src/plugin.cfg

# Compile CoreDNS
WORKDIR /build/coredns-src
RUN go generate ./... && go build -o /build/coredns .

# Stage 2: Unified App
FROM python:3.10-slim

# Install system dependencies & supervisor
RUN apt-get update && apt-get install -y \
    build-essential \
    g++ \
    libgomp1 \
    curl \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirement files and install
COPY military-intel-platform/requirements.txt ./military-reqs.txt
COPY dns-threat-filter/api/requirements.txt ./api-reqs.txt
COPY dns-threat-filter/dashboard/requirements.txt ./dashboard-reqs.txt

RUN pip install --no-cache-dir -r military-reqs.txt \
    && pip install --no-cache-dir -r api-reqs.txt \
    && pip install --no-cache-dir -r dashboard-reqs.txt

# Copy source code
COPY military-intel-platform/ /app/military-intel-platform/
COPY dns-threat-filter/ /app/dns-threat-filter/

# Copy compiled CoreDNS binary from builder
COPY --from=builder /build/coredns /app/dns-threat-filter/coredns-plugin/coredns
RUN chmod +x /app/dns-threat-filter/coredns-plugin/coredns

# Copy supervisord config
COPY military-intel-platform/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Env vars
ENV ARROW_DEFAULT_MEMORY_POOL=system
ENV USE_THREAT_FILTER_DNS=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8501 8502 8000 1053/udp 1053/tcp

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]

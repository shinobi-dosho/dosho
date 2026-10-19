# KERN-10 publishes native AOFlagger packages for AMD64 and ARM64.
FROM {base_image}
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -o APT::Update::Error-Mode=any \
    && apt-get install -y --no-install-recommends aoflagger \
    && rm -rf /var/lib/apt/lists/*
RUN {cmd}
CMD {cmd}

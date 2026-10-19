# Build SoFiA-2 on the dosho KERN-10 base, then ship its native binary with
# only the small Ubuntu runtime. The build stage supplies wcslib headers.
FROM {base_image} AS build
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -o APT::Update::Error-Mode=any \
    && apt-get install -y --no-install-recommends build-essential wcslib-dev \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 -b v{package_version} \
       https://gitlab.com/SoFiA-Admin/SoFiA-2.git /SoFiA-2 \
    && make -C /SoFiA-2 -j4 OMP=true \
    && make -C /SoFiA-2 install

FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
       libwcs8 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /usr/bin/sofia /usr/bin/sofia
RUN sofia -h
CMD {cmd}

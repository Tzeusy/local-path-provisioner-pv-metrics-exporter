#!/bin/bash

# NOTE: This is local and contextual to my tailscale setup.

cd src/job
docker build -t docker-registry.parrot-hen.ts.net:5000/lp-exporter-job:latest .
docker push docker-registry.parrot-hen.ts.net:5000/lp-exporter-job:latest
cd -

cd src/deployment
docker build -t docker-registry.parrot-hen.ts.net:5000/lp-exporter-deployment:latest .
docker push docker-registry.parrot-hen.ts.net:5000/lp-exporter-deployment:latest
cd -
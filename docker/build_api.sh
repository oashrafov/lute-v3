#!/bin/bash
set -e

REPO=oashrafov/lute3-api
VERSION=$(python -c "import lute; print(lute.__version__)")

if [ -z "$VERSION" ]; then
    echo
    echo "Couldn't find lute version, quitting"
    echo
    exit 1
fi

TAG="${REPO}:${VERSION}-lean"
LATEST="${REPO}:latest-lean"

echo
echo "Build and push $TAG, $LATEST"
echo

docker build \
       -f docker/Dockerfile "$@" \
       --platform linux/amd64,linux/arm64 \
       --build-arg INSTALL_EVERYTHING=false \
       -t $TAG \
       -t $LATEST \
       --push .

echo
echo "Images created and pushed:"
echo
echo $TAG
echo $LATEST
echo

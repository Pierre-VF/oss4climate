# How to run TypeSense

```bash
export TYPESENSE_API_KEY=12345 &&

podman run -p 8108:8108 \
    -v"$(pwd)"/typesense-data:/data docker.io/typesense/typesense:30.1 \
    --data-dir /data \
    --api-key=$TYPESENSE_API_KEY \
    --enable-cors
```

```
# Then check with
curl http://localhost:8108/health

curl -H 'X-TYPESENSE-API-KEY: xyz' http://localhost:8108/debug
```

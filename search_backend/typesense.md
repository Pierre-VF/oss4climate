# How to run TypeSense

```bash
export TYPESENSE_API_KEY=12345 &&

mkdir typesense-data/ || echo "Skip folder creation"
podman run -p 8108:8108 -v"$(pwd)"/typesense-data:/data docker.io/typesense/typesense:30.1 --data-dir /data --api-key=12345 --enable-cors
```

```
# Then check with
curl http://localhost:8108/health

curl -H 'X-TYPESENSE-API-KEY: 12345' http://localhost:8108/debug
```

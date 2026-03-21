# How to run TypeSense


Run a local TypeSense instance using the commands below (replace `12345` by the actual API key that you want to use).

1. With Podman:
    ```bash
    mkdir typesense-data/ || echo "Skip folder creation"
    podman run -p 8108:8108 -v"$(pwd)"/typesense-data:/data docker.io/typesense/typesense:30.1 --data-dir /data --api-key=12345 --enable-cors
    ```

2. With Docker:
    ```bash
    mkdir typesense-data/ || echo "Skip folder creation"
    docker run -p 8108:8108 -v"$(pwd)"/typesense-data:/data typesense/typesense:30.1 --data-dir /data --api-key=12345 --enable-cors
    ```

Check that the instance is alive using:
```
# Check health
curl http://localhost:8108/health

# Check API key
curl -H 'X-TYPESENSE-API-KEY: 12345' http://localhost:8108/debug
```

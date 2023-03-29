# skopeo-worker

Skopeo-worker is a python wrapper script around [skopeo](https://github.com/containers/skopeo).
It will periodically perform container mirror tasks as a job inside a kubernetes cluster.
Used by our [helm-charts](https://github.com/osism/helm-charts). Can currently only work with quay.io and dockerhub.

## Environment variables

|Variable           |Mandatory|Description|
|-------------------|---------|-----------|
|`MIRROR_SOURCE_URL`| X       |Takes a full URL pointing to a [config file](https://raw.githubusercontent.com/osism/python-skopeo-wrapper/main/example_container_list.yaml) on with the containers to be mirrored.|
|`MIRROR_DEST_URL`  | X       |The DNS name of your destination registry, which should hold your mirrors, e.g. `registry.airgap.services.osism.tech`.|
|`CHUNK_SIZE`       |         |Requires `CHUNK_NUMBER`. Split list into a given amount of chunks with the size of _n_.|
|`CHUNK_NUMBER`     |         |Requires `CHUNK_SIZE`. Split list into _n_ chunks with a given size. |
|`FILTER`           |         |Python compatible regular expression. If there is a match on the container tag, it gets mirrored.|
|`LIMIT`            |         |Amount of containers to be mirrored. Starting from the most recent.|

### Default values

```sh
export MIRROR_SOURCE_URL="https://raw.githubusercontent.com/osism/sbom/main/mirrors.yaml"
export MIRROR_DEST_URL="registry.airgap.services.osism.tech"
export CHUNK_SIZE="0"
export CHUNK_NUMBER="0"
export FILTER=""
export LIMIT="0"
```

### Chunk detailed explanation

When your list contains e.g. `["a", "b", "c", "d", "e", "f", "g", "h"]`, you can set `CHUNK_SIZE` to __3__ and `CHUNK_NUMBER` to __2__.
This would result in a list containing `["d", "e", "f"]`. If you set `CHUNK_NUMBER` to __3__ the list would only contain `["g", "h"]`.
Something out of range would just return an empty list `[]`.

## Config file example

```yaml
containers:
  - quay.io/osism/osism
  - registry-1.docker.io/library/nginx
```

## Kubernetes example

To run skopeo-worker in Kubernetes, you might want to use a _CronJob_.
An example might look like the code below. Keep in mind, that there are rate limits on the APIs.
Consider using the chunk functionality and work on them at different time slots.

```yaml
---
apiVersion: batch/v1
kind: CronJob
metadata:
  name: update-registry-mirror
spec:
  schedule:  "* 2 * * *"  # every day at two o clock
  concurrencyPolicy: Forbid  # Do not allow parallel containers
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
            - name: skopeo-worker
              image: harbor.services.osism.tech/osism/skopeo-worker:latest
              imagePullPolicy: Always
              env:
                - name: MIRROR_SOURCE_URL
                  value: "https://raw.githubusercontent.com/osism/sbom/main/mirrors.yaml"
                - name: MIRROR_DEST_URL
                  value: "registry.airgap.services.osism.tech"
                - name: CHUNK_SIZE
                  value: "50"
                - name: CHUNK_NUMBER
                  value: "5"
```

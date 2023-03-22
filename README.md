# skopeo-worker

Skopeo-worker is a python wrapper script around [skopeo](https://github.com/containers/skopeo).
It will periodically perform container mirror tasks as a job inside a kubernetes cluster.
Used by our [helm-charts](https://github.com/osism/helm-charts). Can currently only work with quay.io and dockerhub.

## Environment variables

There are four environment variables available to configure this wrapper. `MIRROR_SOURCE_URL` takes a full URL pointing to a config file on with the containers to be mirrored.
The format of this file can be found in the next section. `MIRROR_DEST_URL` is the DNS name of your destination registry, which should hold your mirrors.

`CHUNK_SIZE` and `CHUNK_NUMBER` are optional. It you define them, the script will split your list passed via `MIRROR_SOURCE_URL` into chunks and work only on a part of the list.
This is especially handy if you have a large list of containers and therefore problems with api rate limits.

When your list contains e.g. `["a", "b", "c", "d", "e", "f", "g", "h"]`, you can set `CHUNK_SIZE` to __3__ and `CHUNK_NUMBER` to __2__.
This would result in a list containing `["d", "e", "f"]`. If you set `CHUNK_NUMBER` to __3__ the list would only contain `["g", "h"]`.
Something out of range would just return an empty list `[]`.

```sh
export MIRROR_SOURCE_URL="https://raw.githubusercontent.com/osism/sbom/main/mirrors.yaml"
export MIRROR_DEST_URL="registry.airgap.services.osism.tech"
export CHUNK_SIZE="0"
export CHUNK_NUMBER="0"
```

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

import os
import requests
import subprocess
import sys
import yaml


mirror_source = os.getenv("MIRROR_SOURCE_URL", "https://raw.githubusercontent.com/osism/sbom/main/mirrors.yaml")
mirror_dest = os.getenv("MIRROR_DEST_URL", "registry.airgap.services.osism.tech")


def load_yaml() -> dict:
    result = requests.get(mirror_source)
    try:
        result = yaml.safe_load(result.content)
    except yaml.YAMLError as exc:
        print(exc)

    return result['containers']


def get_tags(reg: str, org: str, img: str) -> list:
    page = 0
    tags = []

    if reg == "quay.io":
        api = f"https://quay.io/api/v1/repository/{org}/{img}/tag/"
        results = requests.get(api)
        if "tags" not in results.json():
            return []
        for result in results.json()['tags']:
            if "expiration" not in result:
                tags.append(result['name'])

    else:
        api = f"https://registry.hub.docker.com/v2/repositories/{org}/{img}/tags/?page="
        while True:
            page = page + 1
            url = f"{api}{page}"
            results = requests.get(url)

            # break if all pages have been scrubbed
            if 'results' not in results.json():
                break

            # loop through all tags and append them
            for result in results.json()['results']:
                # skip windows images (traefik)
                for arch in result['images']:
                    if arch["os"] != "windows":
                        break
                else:
                    continue
                if result['tag_status'] == "active":
                    tags.append(result['name'])

    return tags


def main():
    containers = load_yaml()

    for container in containers:
        print(f"[{container}] fetching all tags")
        sys.stdout.flush()
        reg, org, img = container.split("/")
        for tag in get_tags(reg=reg, org=org, img=img):
            print(f"[{container}] check if tag {tag} is already mirrored")
            sys.stdout.flush()
            result = requests.get(f"https://{mirror_dest}/v2/{org}/{img}/tags/list")
            if "tags" in result.json():
                if tag in result.json()['tags']:
                    print(f"[{container}] tag {tag} is already mirrored")
                    continue

            source_uri = f"docker://{reg}/{org}/{img}:{tag}"
            destination_uri = f"docker://{mirror_dest}/{org}/{img}:{tag}"
            command = ["skopeo", "copy", source_uri, destination_uri]

            print(f"[{container}] mirroring tag {tag}")
            sys.stdout.flush()
            result = subprocess.run(
                command,
                capture_output=True,
                check=True,
                encoding="UTF-8"
            )
            if result.returncode > 0:
                if result.stderr:
                    print(f"[{container}] {result.stderr}")


if __name__ == "__main__":
    main()

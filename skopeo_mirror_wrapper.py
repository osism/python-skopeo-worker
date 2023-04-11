import os
import re
import requests
import subprocess
import sys
import yaml

from loguru import logger

# environment variables
mirror_source = os.getenv("MIRROR_SOURCE_URL", "https://raw.githubusercontent.com/osism/sbom/main/mirrors.yaml")
mirror_dest = os.getenv("MIRROR_DEST_URL", "registry.airgap.services.osism.tech")
chunk_size = int(os.getenv("CHUNK_SIZE", "0"))
chunk_number = int(os.getenv("CHUNK_NUMBER", "0"))
filter = os.getenv("FILTER", "")
limit = int(os.getenv("LIMIT", "0"))

# prepare logger format
logger.remove()
logger_format = (
    "<black>{time:YYYY-MM-DD HH:mm:ss.SSS}</black> | "
    "<level>{level: <8}</level> | "
    "<cyan>{extra[container]: <52}</cyan> | "
    "<level>{message}</level>"
)
logger.configure(extra={"container": ""})
logger.add(sys.stdout, format=logger_format)


def load_yaml() -> dict:
    result = requests.get(mirror_source)
    try:
        result = yaml.safe_load(result.content)
    except yaml.YAMLError as exc:
        print(exc)

    containers = []

    # we are using chunks
    if chunk_size > 0 and chunk_number > 0:
        starting_point = chunk_size * (chunk_number - 1)  # substract one, to start at 0

        counter = 0
        while counter < chunk_size:
            try:
                containers.append(result['containers'][counter + starting_point])
            except IndexError:
                pass
            counter = counter + 1
    else:
        containers = result['containers']

    return containers


def get_tags(reg: str, org: str, img: str) -> list:
    page = 0
    tags = []

    if reg == "quay.io":
        # quay, page elements: 50
        api = f"https://quay.io/api/v1/repository/{org}/{img}/tag/?page="
        while True:
            page = page + 1

            url = f"{api}{page}"
            results = requests.get(url)

            # break if all pages have been scrubbed
            if results.json()['tags'] == []:
                break

            for result in results.json()['tags']:
                if "expiration" not in result:
                    tags.append(result['name'])

    else:
        # docker, page elements: 10
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
        smw_logger = logger.bind(container=container)
        smw_logger.info("fetching all tags")

        reg, org, img = container.split("/")

        limit_counter = 0
        for tag in get_tags(reg=reg, org=org, img=img):
            # apply filters
            if filter != "":
                if not re.match(filter, tag):
                    continue

            # if limit is set, pull only the given amount of images
            if limit != 0:
                limit_counter = limit_counter + 1
                if limit_counter > limit:
                    break

            smw_logger.info(f"tag {tag} started")
            result = requests.get(f"https://{mirror_dest}/v2/{org}/{img}/tags/list")
            if "tags" in result.json():
                if tag in result.json()['tags']:
                    smw_logger.success(f"tag {tag} mirrored")
                    continue

            source_uri = f"docker://{reg}/{org}/{img}:{tag}"
            destination_uri = f"docker://{mirror_dest}/{org}/{img}:{tag}"
            command = ["skopeo", "copy", source_uri, destination_uri]

            result = subprocess.run(
                command,
                capture_output=True,
                check=True,
                encoding="UTF-8"
            )
            if result.returncode > 0:
                if result.stderr:
                    smw_logger.error(f"tag {tag} {result.stderr}")
                else:
                    smw_logger.critical(f"tag {tag} Return code {result.returncode}. No error message received.")
            else:
                smw_logger.success(f"tag {tag} mirrored")


if __name__ == "__main__":
    main()

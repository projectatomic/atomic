import sys
import os
from .pulp import PulpServer
from .config import PulpConfig
from .atomic import Atomic


def writeOut(output, lf="\n"):
    sys.stdout.flush()
    sys.stdout.write(str(output) + lf)


def push_image_to_pulp(image, server_url, username, password, verify_ssl,
                       docker_client):
    if not image:
        raise ValueError("Image required")
    parts = image.split("/")
    if parts > 1:
        if parts[0].find(".") != -1:
            server_url = parts[0]
            image = ("/").join(parts[1:])

    repo = image.replace("/", "-")
    if not server_url:
        raise ValueError("Server url required")

    if not server_url.startswith("http"):
        server_url = "https://" + server_url

    try:
        pulp = PulpServer(server_url=server_url, username=username,
                          password=password, verify_ssl=verify_ssl,
                          docker_client=docker_client)
    except Exception as e:
        raise IOError('Failed to initialize Pulp: {0}'.format(e))

    try:
        if not pulp.is_repo(repo):
            pulp.create_repo(image, repo)
    except Exception as e:
        raise IOError('Failed to create Pulp repository: {0}'.format(e))

    try:
        writeOut('Uploading image "{0}" to pulp server "{1}"'
                 ''.format(image, server_url))
        pulp.upload_docker_image(image, repo)
        writeOut("")
    except Exception as e:
        raise IOError('Failed to upload image to Pulp: {0}'.format(e))

    pulp.publish_repo(repo)
    pulp.export_repo(repo)

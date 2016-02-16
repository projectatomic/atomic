import docker
from docker.utils import kwargs_from_env

def get_docker_client():
    """
    Universal method to use docker.client()
    """
    try:
        return docker.AutoVersionClient(**kwargs_from_env())

    except docker.errors.DockerException:
        return docker.Client(**kwargs_from_env())

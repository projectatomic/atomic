class DockerObjectNotFound(ValueError):
    def __init__(self, msg):
        super(DockerObjectNotFound, self).__init__("Unable to associate '{}' with an image or container".format(msg))
        
class NoDockerDaemon(Exception):
    def __init__(self):
        super(NoDockerDaemon, self).__init__("The docker daemon does not appear to be running.")

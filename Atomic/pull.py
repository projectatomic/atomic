from .syscontainers import SystemContainers

def cli(subparser):
    # atomic pull
    pullp = subparser.add_parser("pull", help=_("pull latest image from a repository"),
                                 epilog="pull the latest specified image from a repository.")
    pullp.set_defaults(_class=Pull, func='pull_image')
    pullp.add_argument("--storage", dest="backend", help=_("Specify the storage."))
    pullp.add_argument("image", help=_("image id"))

class Pull(SystemContainers):
    def __init__(self):
        super(Pull, self).__init__()

    def pull_image(self):
        super(Pull, self).pull_image()

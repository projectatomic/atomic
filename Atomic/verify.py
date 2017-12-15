from . import util
from . import Atomic
from operator import itemgetter
import argparse
from .discovery import  RegistryInspect
from .client import no_shaw
from Atomic.backendutils import BackendUtils


ATOMIC_CONFIG = util.get_atomic_config()
storage = ATOMIC_CONFIG.get('default_storage', "docker")

def cli(subparser, hidden=False):
    # atomic verify
    if hidden:
        verifyp = subparser.add_parser("verify", argument_default=argparse.SUPPRESS)
    else:
        verifyp = subparser.add_parser(
            "verify", help=_("verify image is fully updated"),
            epilog="atomic verify checks whether there is a newer image "
            "available and scans through all layers to see if any of "
            "the sublayers have a new version available")
    verifyp.set_defaults(_class=Verify, func='verify')
    verifyp.add_argument("image", nargs='?', help=_("container image"))
    verifyp.add_argument("-a", "--all", default=False, dest="all",
                                action="store_true",
                                help=_("verify all images in a storage"))
    verifyp.add_argument("--no-validate", default=False, dest="no_validate",
                                action="store_true",
                                help=_("disable validating system images"))
    verifyp.add_argument("--storage", default=None, dest="storage",
                         help=_("Specify the storage of the image. "
                                "If not specified and there are images with the same name in "
                                "different storages, you will be prompted to specify."))
    verifyp.add_argument("-v", "--verbose", default=False,
                          action="store_true",
                          help=_("Report status of each layer"))


class Verify(Atomic):
    def __init__(self):
        super(Verify, self).__init__()
        self.debug = False
        self.backend_utils = BackendUtils()

    def _layers_match(self, local, remote):
        _match = []
        for _layer_int in range(len(local)):
            if local[_layer_int] == remote[_layer_int]:
                _match.append(True)
            else:
                _match.append(False)
        return all(_match)

    def verify(self):
        if self.args.image and self.args.all:
            raise ValueError("Incompatible options specified.  --all doesn't support an image name")
        if not self.args.all and not self.args.image:
            raise ValueError("Please specify the image name")
        if self.args.all and not self.args.storage:
            raise ValueError("Please specify --storage")

        if self.args.all:
            be = BackendUtils().get_backend_from_string(self.args.storage)
            images = be.get_images()
            for i in images:
                if i.repotags is None:
                    continue
                img_name = i.repotags[0]

                d = util.Decompose(img_name)
                if d.registry == "":
                    util.write_err("Image {} not fully qualified: skipping".format(img_name))
                    continue

                self._verify_one_image(img_name)
        else:
            return self._verify_one_image(self.args.image)

    def _verify_one_image(self, image):
        if self.args.debug:
            util.write_out(str(self.args))
        be, local_layers, remote_layers = self._verify(image)
        if not self._layers_match(local_layers, remote_layers) or self.args.verbose:
            col = "{0:30} {1:20} {2:20} {3:1}"
            util.write_out("\n{} contains the following images:\n".format(image))
            util.write_out(col.format("NAME", "LOCAL VERSION", "REMOTE VERSION", "DIFFERS"))
            for layer_int in range(len(local_layers)):
                differs = 'NO' if remote_layers[layer_int] == local_layers[layer_int] else 'YES'
                util.write_out(col.format(local_layers[layer_int].name[:30],
                                          local_layers[layer_int].long_version[:20],
                                          remote_layers[layer_int].long_version[:20],
                                          differs))
                util.write_out("\n")
        if not self.args.no_validate:
            be.validate_layer(image)

    def verify_dbus(self):
        _, local_layers, remote_layers = self._verify(self.args.image)
        layers = []
        for layer_int in range(len(local_layers)):
            layer = {}
            layer['name'] = local_layers[layer_int].name
            layer['local_version'] = local_layers[layer_int].long_version
            layer['remote_version'] = remote_layers[layer_int].long_version
            layer['differs'] = False if remote_layers[layer_int] == local_layers[layer_int] else True
            layers.append(layer)
        return layers

    def _verify(self, image):
        be, img_obj = self.backend_utils.get_backend_and_image_obj(image, str_preferred_backend=self.args.storage or storage, required=True if self.args.storage else False)
        remote_img_name  = "{}:latest".format(util.Decompose(img_obj.fq_name).no_tag)
        remote_img_obj = be.make_remote_image(remote_img_name)
        return be, img_obj.layers, remote_img_obj.layers

    def get_tagged_images(self, names, layers):
        """
        Returns a dict with image names and its tag name.
        :param names:
        :param layers:
        :return: list of sorted dicts (by index)
        """
        base_images = []
        for name in names:
            _match = next((x for x in layers if x['Name'] == name and x['RepoTags'] is not ''), None)
            registry, repo, image, tag, digest = util.Decompose(self.get_fq_image_name(_match['RepoTags'][0])).all
            tag = "latest"
            ri = RegistryInspect(registry=registry, repo=repo, image=image, tag=tag, digest=digest, debug=self.debug)
            remote_inspect = ri.inspect()
            release = remote_inspect.get("Labels", None).get("Release", None)
            version = remote_inspect.get("Labels", None).get("Version", None)
            if release and version:
                remote_version =  "{}-{}-{}".format(name, version, release)
            else:
                # Check if the blob exists on the registry by the ID
                remote_id = no_shaw(ri.remote_id)
                _match['Version'] = _match['Id']
                remote_version = remote_id if remote_id is not None else ""

            _match['Remote Version']  =  remote_version
            base_images.append(_match)
        return sorted(base_images, key=itemgetter('index'))

    @staticmethod
    def _mismatch(layer):
        if layer['Version'] != layer['Remote Version'] and layer['Remote Version'] != layer['Id']:
            return "Yes"
        if layer['Version'] == '' and layer['Remote Version'] == '':
            return "!"
        return "No"


    @staticmethod
    def print_verify(base_images, image, verbose=False):
        """
        Implements a verbose printout of layers.  Can be called with
        atomic verify -v or if we detect some layer does not have
        versioning information.
        :param base_images:
        :param image:
        :return: None
        """
        def check_for_updates(base_images):
            for i in base_images:
                if Verify._mismatch(i) in ['Yes', '!']:
                    return True
            return False
        has_updates = check_for_updates(base_images)
        if has_updates or verbose:

            col = "{0:30} {1:20} {2:20} {3:1}"
            util.write_out("\n{} contains the following images:\n".format(image))
            util.write_out(col.format("NAME", "LOCAL VERSION", "REMOTE VERSION", "DIFFERS"))
            for _image in base_images:
                util.write_out(col.format(_image['Name'][:30], _image['Version'][:20], _image['Remote Version'][:20], Verify._mismatch(_image)))
            util.write_out("\n")

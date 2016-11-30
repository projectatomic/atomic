from . import util
from . import Atomic
import os
from operator import itemgetter
from .syscontainers import SystemContainers
from .mount import Mount
import argparse
import shutil
import itertools
import tempfile
import subprocess
from .discovery import  RegistryInspect
from .client import no_shaw
import json
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
    verifyp.add_argument("image", help=_("container image"))
    verifyp.add_argument("--no-validate", default=False, dest="no_validate",
                                action="store_true",
                                help=_("disable validating system images"))
    verifyp.add_argument("--storage", default=storage, dest="storage",
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
        if self.args.debug:
            util.write_out(str(self.args))
        local_layers, remote_layers = self._verify()
        if not self._layers_match(local_layers, remote_layers) or self.args.verbose:
            col = "{0:30} {1:20} {2:20} {3:1}"
            util.write_out("\n{} contains the following images:\n".format(self.image))
            util.write_out(col.format("NAME", "LOCAL VERSION", "REMOTE VERSION", "DIFFERS"))
            for layer_int in range(len(local_layers)):
                differs = 'NO' if remote_layers[layer_int] == local_layers[layer_int] else 'YES'
                util.write_out(col.format(local_layers[layer_int].name[:30],
                                          local_layers[layer_int].long_version[:20],
                                          remote_layers[layer_int].long_version[:20],
                                          differs))
            util.write_out("\n")

    def verify_dbus(self):
        local_layers, remote_layers = self._verify()
        layers = []
        for layer_int in range(len(local_layers)):
            layer = {}
            layer['name'] = local_layers[layer_int].name
            layer['local_version'] = local_layers[layer_int].long_version
            layer['remote_version'] = remote_layers[layer_int].long_version
            layer['differs'] = False if remote_layers[layer_int] == local_layers[layer_int] else True
            layers.append(layer)
        return layers

    def _verify(self):
        be, img_obj = self.backend_utils.get_backend_and_image(self.image, self.args.storage)
        remote_img_name  = "{}:latest".format(util.Decompose(img_obj.fq_name).no_tag)
        remote_img_obj = be.make_remote_image(remote_img_name)
        return img_obj.layers, remote_img_obj.layers

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
            registry, repo, image, tag, _ = util.Decompose(self.get_fq_image_name(_match['RepoTags'][0])).all
            tag = "latest"
            ri = RegistryInspect(registry=registry, repo=repo, image=image, tag=tag, debug=self.debug)
            ri.ping()
            remote_inspect = ri.inspect()
            release = remote_inspect.get("Labels", None).get("Release", None)
            version = remote_inspect.get("Labels", None).get("Version", None)
            if release and version:
                remote_version =  "{}-{}-{}".format(name, version, release)
            else:
                # Check if the blob exists on the registry by the ID
                remote_id = no_shaw(ri.rc.manifest_json.get("config", None).get("digest", None))
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

    def verify_system_image(self):
        manifest = self.syscontainers.get_manifest(self.image)
        name = json.loads(manifest).get('Name', self.image)
        if manifest:
            layers = SystemContainers.get_layers_from_manifest(manifest)
        else:
            layers = [self.image]
        if not getattr(self.args,"no_validate", False):
            self.validate_system_image_manifests(layers)

        if not manifest:
            return
        remote = True
        try:
            remote_manifest = self.syscontainers.get_manifest(self.image, remote=True)
            remote_layers = SystemContainers.get_layers_from_manifest(remote_manifest)
        except subprocess.CalledProcessError:
            remote_layers = []
            remote = False

        if hasattr(itertools, 'izip_longest'):
            zip_longest = getattr(itertools, 'izip_longest')
        else:
            zip_longest = getattr(itertools, 'zip_longest')

        images = []
        for local, remote in zip_longest(layers, remote_layers):
            images.append({'Name': name,
                           'Version': no_shaw(local),
                           'Id': no_shaw(local),
                           'Remote Version': no_shaw(remote),
                           'remote': remote,
                           'no_version' : True,
                           'Repo Tags': self.image,
            })

        self.print_verify(images, self.image, verbose=self.args.verbose)

    def validate_system_image_manifests(self,layers):
        """
        Validate a system image's layers against the the associated validation manifests
        created from those image layers on atomic pull.
        :param layers: list of the names of the layers to validate
        :return: None
        """
        for layer in layers:
            mismatches = self.syscontainers.validate_layer(layer)
            if len(mismatches) > 0:
                util.write_out("modifications in layer %s layer:\n" % layer)
                for m in mismatches:
                    util.write_out("file '%s' changed checksum from '%s' to '%s'" % (m["name"], m["old-checksum"], m["new-checksum"]))

    def validate_image_manifest(self):
        """
        Validates a docker image by mounting the image on a rootfs and validate that
        rootfs against the manifests that were created. Note that it won't be validated
        layer by layer.
        :param:
        :return: None
        """
        iid = self._is_image(self.image)
        manifestname = os.path.join(util.ATOMIC_VAR_LIB, "gomtree-manifests/%s.mtree" % iid)
        if not os.path.exists(manifestname):
            return
        tmpdir = tempfile.mkdtemp()
        m = Mount()
        m.args = []
        m.image = self.image
        m.mountpoint = tmpdir
        m.mount()
        r = util.validate_manifest(manifestname, img_rootfs=tmpdir, keywords="type,uid,gid,mode,size,sha256digest")
        m.unmount()
        if r.return_code != 0:
            util.write_err(r.stdout)
        shutil.rmtree(tmpdir)

    @staticmethod
    def get_gomtree_manifest(layer, root=os.path.join(util.ATOMIC_VAR_LIB, "gomtree-manifests")):
        manifestpath = os.path.join(root,"%s.mtree" % layer)
        if os.path.isfile(manifestpath):
            return manifestpath
        return None


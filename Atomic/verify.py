from . import util
from . import Atomic
import os
from docker.errors import NotFound
from operator import itemgetter
from .atomic import AtomicError
from .syscontainers import SystemContainers
from .mount import Mount
import shutil
import itertools
import tempfile
import subprocess

class Verify(Atomic):
    def __init__(self):
        super(Verify, self).__init__()
        self.debug = False

    def verify_system_image(self):
        manifest = self.syscontainers.get_manifest(self.image)
        layers = SystemContainers.get_layers_from_manifest(manifest)
        if not getattr(self.args,"no_validate", False):
            self.validate_system_image_manifests(layers)

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
            images.append({'iid': self.image,
                           'local_nvr': local,
                           'latest_nvr': remote,
                           'remote': remote,
                           'no_version' : True,
                           'tag': self.image,
            })

        not_matching = [x for x in images if x['local_nvr'] != x['latest_nvr']]
        if len(not_matching) == 0:
            pass
        elif self.args.verbose:
            self._print_verify_verbose(images, self.image)
        else:
            self._print_verify(images, self.image)

    def verify(self):
        """
        Primary def for atomic verify
        :return: None
        """
        def fix_layers(layers):
            """
            Takes the input of layers (get_layers()) and adds a key
            and value for index.  Also checks if the Tag value is not
            blank but name is, puts tag into name.
            :param layers:
            :return: updated list of layers
            """
            for layer in layers:
                layer['index'] = layers.index(layer)
                if layer['Tag'] is not "" and layer['Name'] is "":
                    layer['Name'] = layer['Tag']
            return layers

        # Set debug bool
        self.set_debug()

        if self.syscontainers.has_system_container_image(self.image):
            imgs = self.syscontainers.get_system_images()
            for img in imgs:
                if img['Id'].startswith(self.image):
                    self.image = img['RepoTags'][0]
            return self.verify_system_image()

        # Check if the input is an image id associated with more than one
        # repotag.  If so, error out.
        if self.is_iid():
            self.get_fq_name(self._inspect_image())
        # The input is not an image id
        else:
            try:
                iid = self._is_image(self.image)
                self.image = self.get_fq_name(self._inspect_image(iid))
            except AtomicError:
                self._no_such_image()

        if hasattr(self.args,"validate") and self.args.validate:
            self.validate_image_manifest()

        layers = fix_layers(self.get_layers())
        if self.debug:
            for l in layers:
                util.output_json(l)
        uniq_names = list(set(x['Name'] for x in layers if x['Name'] != ''))
        base_images = self.get_tagged_images(uniq_names, layers)

        if not self.useTTY:
            return base_images

        if self.debug:
            for b in base_images:
                util.output_json(b)
        if self.args.verbose:
            self._print_verify_verbose(base_images, self.image)
        # Do we have any layers that are not up to date?
        elif not all([False for x in base_images if x['local_nvr'] != x['latest_nvr']]):
            self._print_verify(base_images, self.image)
        else:
            # Check if any of the base_images do not have versioning information
            versions = [x['local_nvr'] for x in base_images] + [x['latest_nvr'] for x in base_images]
            if 'Version unavailable' in versions:
                util.write_out("\nWARNING: One or more of the image layers does not have")
                util.write_out("{}versioning information. Printing each image layer".format(" " * 9))
                util.write_out("{}verbosely.".format(" " * 9))
                self._print_verify_verbose(base_images, self.image)
            else:
                # Didn't detect any version differences, do nothing
                pass

    def get_tagged_images(self, names, layers):
        """
        Returns a dict with image names and its tag name.
        :param names:
        :param layers:
        :return: list of sorted dicts (by index)
        """
        base_images = []
        for name in names:
            remote = False
            _match = next((x for x in layers if x['Name'] == name and x['Tag'] is not ''), None)
            local_nvr = ""
            if _match is not None:
                if self.is_repo_from_local_registry(_match['Id']):
                    local_nvr = latest_version = _match['Version']
                    remote = True
                else:
                    local_nvr = self.get_local_latest_version(name)
                    latest_version = self.get_latest_remote_version(_match['Tag'], name)

                no_version = (latest_version == "")

                iid = _match["Id"]
                tag = _match['Tag']
                _index = self.get_index(name, layers, iid)
            else:
                _index = self.get_index(name, layers)
                layer = layers[_index]
                if layer["Version"] is not "" and layer['Name'] is not "":
                    iid = layer['Id']
                    local_nvr = layer['Version']
                    no_version = False
                    image = self.d.inspect_image(iid)
                    labels = image.get('Config', []).get('Labels', [])
                    if 'Authoritative_Registry' in labels and 'Name' in labels:
                        tag = os.path.join(labels['Authoritative_Registry'], labels['Name'])
                        if self.is_repo_from_local_registry(iid):
                            # Inspect again by tag in case the image isnt the latest
                            try:
                                image = self.d.inspect_image(tag)
                                labels = image.get('Config', []).get('Labels', [])
                                latest_version = labels['Version']
                            except NotFound:
                                latest_version = layer['Version']
                        else:
                            # Do a remote inspect of images
                            latest_version = self.get_latest_remote_version(tag)
                        remote = True
                    else:
                        tag = "Unknown"
                        try:
                            latest_version = self.get_latest_remote_version(name)
                        except NotFound:
                            latest_version = "Unknown"
                else:
                    iid = "Unknown"
                    latest_version = self.get_local_latest_version(name)
                    local_nvr = name
                    tag = "Unknown"
                    remote = False
                    no_version = True
            base_images.append({'iid': iid,
                                'name': name,
                                'local_nvr': local_nvr,
                                'latest_nvr': latest_version,
                                'remote': remote,
                                'no_version': no_version,
                                'tag': tag,
                                'index': _index
                                })
        return sorted(base_images, key=itemgetter('index'))

    def is_repo_from_local_registry(self, input_repo):
        """
        Determine is a given repo comes from a local-only registry
        :param input_repo: str repository name
        :return: bool
        """
        # We need to check if there are other images with the
        # the same IID because the input might not be fully
        # qualified
        iid = self.d.inspect_image(input_repo)['Id']
        # Get a flat list of repo names associated with the iid
        similar = [_repo for repos in [x['RepoTags'] for x in self.d.images()
                                       if x['Id'] == iid] for _repo in repos]
        results = []
        for repo_ in similar:
            (reg, _, _) = util.decompose(repo_)
            results.append(self.is_registry_local(reg))
        return all(results)

    def is_registry_local(self, registry):
        """
        Determine if a given registry is local only
        :param registry: str registry name
        :return: bool
        """
        return registry not in self.get_registries()

    def get_registries(self):
        """
        Gets the names of the registries per /etc/sysconfig/conf
        :return: a list of the registries
        """
        registries = []
        docker_info = self.d.info()
        if 'RegistryConfig' not in docker_info:
            raise ValueError("This docker version does not export its registries.")
        for _index in docker_info['RegistryConfig']['IndexConfigs']:
            registries.append(_index)
        return registries

    @staticmethod
    def _print_verify(base_images, image):
        """
        The standard non-verbose print for atomic verify
        :param base_images:
        :param image:
        :return:  None
        """
        util.write_out("\n{} contains images or layers that have updates:".format(image))
        for _image in base_images:
            local = _image['local_nvr']
            latest = _image['latest_nvr']
            if local != latest:
                util.write_out("\n{0} '{1}' has an update to '{2}'"
                              .format(" " * 5, local, latest))
        util.write_out("\n")

    @staticmethod
    def _print_verify_verbose(base_images, image):
        """
        Implements a verbose printout of layers.  Can be called with
        atomic verify -v or if we detect some layer does not have
        versioning information.
        :param base_images:
        :param image:
        :return: None
        """
        def max_name(base_images):
            no_version_match = [len(x['tag']) + len(x['local_nvr']) + 5 for x in base_images if x['no_version']]
            return max([len(x['local_nvr']) for x in base_images] + no_version_match)
        _max = max_name(base_images)
        _max_name = 30 if _max < 30 else _max
        three_col = "     {0:" + \
                    str(_max_name) + "} {1:" + \
                    str(_max_name) + "} {2:1}"
        util.write_out("\n{} contains the following images:\n".format(image))
        util.write_out(three_col.format("Local Version", "Latest Version", ""))
        util.write_out(three_col.format("-------------", "--------------", ""))
        for _image in base_images:
            local = _image['local_nvr']
            latest = _image['latest_nvr']
            if _image['no_version']:
                tag = _image['tag']
                local = "{0} ({1})".format(tag, local)
                latest = "{0} ({1})".format(tag,  latest)
            remote = "*" if local != latest else ""
            util.write_out(three_col.format(local, latest, remote))
        util.write_out("\n     * = version difference\n")

    @staticmethod
    def get_index(name, layers, _id="0"):
        """
        Adds indexs to the base_image dict and returns sorted
        :param name:
        :param layers:
        :param _id:
        :return: sorted list of base_images
        """
        try:
            try:
                _match = (x for x in layers if x["Id"] == _id).__next__()
            except AttributeError:
                _match = (x for x in layers if x["Id"] == _id).next() # pylint: disable=next-method-called
        except StopIteration:
            # We were unable to associate IDs due to the local image being set
            # to intermediate by docker bc it is outdated. Therefore we find
            # the first instance by name for the index
            try:
                _match = (x for x in layers if x["Name"] == name).__next__()
            except AttributeError:
                _match = (x for x in layers if x["Name"] == name).next() # pylint: disable=next-method-called
        return _match['index']

    def get_local_latest_version(self, name):
        """
        Obtain the latest version of a local image
        :param name:
        :return: str of vnr
        """
        images = self.get_images()
        for image in images:
            if 'Labels' in image and image['Labels'] is not None:
                if self.pull_label(image, 'Name') == name:
                    return self.assemble_nvr(image)
            else:
                continue
        return "{}-Version unavailable".format(name)

    def get_latest_remote_version(self, tag, name=None):
        r_inspect = util.skopeo_inspect("docker://" + tag)
        if 'Labels' in r_inspect \
                and r_inspect['Labels'] is not None:
            latest_version = self.assemble_nvr(r_inspect, image_name=name)
        else:
            latest_version = "Version unavailable"
        return latest_version

    def assemble_nvr(self, image, image_name=None):
        """
        Simple formatting def for NVR
        :param image:
        :return: str
        """
        name = self.pull_label(image, 'Name')
        version = self.pull_label(image, 'Version')
        release = self.pull_label(image, 'Release')
        nvr = "%s-%s-%s" % (name, version, release)

        if any(True for x in [name, version, release] if x is None):
            return "{}-Version unavailable".format(image_name)
        else:
            return nvr

    def validate_system_image_manifests(self,layers):
        """
        Validate a system image's layers against the the associated validation manifests
        created from those image layers on atomic pull.
        :param layers: list of the names of the layers to validate
        :return: None
        """
        missing_manifests = []
        for layer in layers:
            layer = layer.replace("sha256:","")
            manifestpath = self.get_gomtree_manifest(layer)
            if not manifestpath:
                missing_manifests.append(layer)
                continue
            tmp_dir = tempfile.mkdtemp()
            ref = os.path.join("ociimage", layer)
            cmd = ['ostree','checkout','--union','--repo=%s' % self.syscontainers.get_ostree_repo_location(),ref,tmp_dir]
            r = util.subp(cmd)
            if r.return_code != 0:
                util.write_err(r.stderr)
                continue
            r = util.validate_manifest(manifestpath, img_rootfs=tmp_dir,keywords="type,uid,gid,mode,size,sha256digest")
            if r.return_code != 0:
                util.write_out("modifications in layer %s layer:\n" % layer)
                if r.return_code > 1:
                    util.write_err(r.stderr)
                else:
                    util.write_err(r.stdout)
            shutil.rmtree(tmp_dir)
        if len(missing_manifests):
            util.write_out("validation manifests for the following layers do not exist:\n")
            for layer in missing_manifests:
                util.write_out("\t%s" % layer)
            util.write_out("\n")
            util.write_out("perform an `atomic pull \"%s\"` if you want to generate these manifests\n" % self.image)

    def validate_image_manifest(self):
        """
        Validates a docker image by mounting the image on a rootfs and validate that
        rootfs against the manifests that were created. Note that it won't be validated
        layer by layer.
        :param:
        :return: None
        """
        iid = self._is_image(self.image)
        manifestname = os.path.join(util.ATOMIC_VAR, "gomtree-manifests/%s.mtree" % iid)
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
    def get_gomtree_manifest(layer, root=os.path.join(util.ATOMIC_VAR, "gomtree-manifests")):
        manifestpath = os.path.join(root,"%s.mtree" % layer)
        if os.path.isfile(manifestpath):
            return manifestpath
        return None

    @staticmethod
    def get_local_version(name, layers):
        for layer in layers:
            if layer['Name'] is name:
                return layer['Version'] if 'Version' in layer \
                    else "Version unavailable"

    @staticmethod
    def pull_label(image, key):
        if key in image["Labels"]:
            return image['Labels'][key]

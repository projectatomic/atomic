from . import util


class RegistryInspectError(Exception):
    pass


class RegistryAuthError(Exception):
    pass


class RegistryInspect():

    def __init__(self, registry=None, repo=None, image=None, tag=None, digest=None, orig_input=None, debug=False):
        self.debug = debug
        self.registries = util.get_registries()
        self.registry = registry
        self.repo = repo
        self.image = image
        self.tag = tag
        self.digest = digest
        self.orig_input = orig_input
        self._remote_inspect = None
        self._fqdn = None

        if self.debug:
            util.output_json(self.registries)

    @property
    def fqdn(self):
        if not self._fqdn:
            self._fqdn = self.assemble_fqdn(include_tag=True) if self.registry else self.find_image_on_registry()
        return self._fqdn

    @fqdn.setter
    def fqdn(self, value):
        self._fqdn = value

    def inspect(self):
        if self.registry:
            inspect_data = util.skopeo_inspect("docker://{}".format(self.fqdn), return_json=True)
        else:
            inspect_data = self._remote_inspect
        inspect_data['Tag'] = self.tag
        inspect_data['Name'] = self.assemble_fqdn(include_tag=False)
        return inspect_data

    def get_manifest(self, return_json=True):
        assert(self.fqdn is not None)
        return util.skopeo_inspect("docker://{}".format(self.fqdn), return_json=return_json, args=['--raw'])

    @property
    def remote_id(self):
        result = self.get_manifest()
        if result.get('config'):
            return result['config'].get('digest', None)
        return None

    def assemble_fqdn(self, include_tag=True, registry=None):
        fqdn = "{}".format(registry or self.registry)
        if self.repo:
            fqdn = "{}/{}".format(fqdn, self.repo)
        elif fqdn == "docker.io": # and no repo specified
            fqdn = fqdn + "/library"
        fqdn += "/{}".format(self.image)
        if include_tag:
            if self.tag:
                fqdn += ":{}".format(self.tag)
            elif self.digest:
                fqdn += "@{}".format(self.digest)
        return fqdn

    def find_image_on_registry(self, quiet=False):
        """
        Find the fully qualified image name for given input when
        registry is unknown
        :return: String fqdn
        """
        if self.debug:
            for i in [x for x in self.registries if x['search']]:
                util.write_out(repr(i))

        registries = [i['name'] for i in [x for x in self.registries if x['search']]]
        for registry in registries:
            fqdn = self.assemble_fqdn(registry=registry, include_tag=True)
            if not quiet:
                util.write_out("Trying {}...".format(fqdn))
            try:
                result = util.skopeo_inspect("docker://{}".format(fqdn), return_json=True)
                self._remote_inspect = result
                return fqdn
            except ValueError as e:
                if not quiet:
                    util.write_err("Failed: {}".format(e))
                continue
        raise RegistryInspectError("Unable to find {}".format(self.orig_input))


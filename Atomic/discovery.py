from . import util


class RegistryInspectError(Exception):
    pass


class RegistryAuthError(Exception):
    pass


class RegistryInspect():

    def __init__(self, registry=None, repo=None, image=None, tag=None, orig_input=None, debug=False):
        self.debug = debug
        self.registries = util.get_registries()
        self.registry = registry
        self.repo = repo
        self.image = image
        self.tag = tag
        self.orig_input = orig_input
        self._remote_inspect = None
        self.fqdn = None

        if self.debug:
            util.output_json(self.registries)

    def inspect(self):
        if self.registry:
            self.fqdn = self.assemble_fqdn(include_tag=True)
            inspect_data = util.skopeo_inspect("docker://{}".format(self.fqdn), return_json=True)
        else:
            self.fqdn = self.find_image_on_registry()
            inspect_data = self._remote_inspect
        inspect_data['Tag'] = self.tag
        inspect_data['Name'] = self.assemble_fqdn(include_tag=False)
        return inspect_data

    def get_manifest(self):
        assert(self.fqdn is not None)
        return util.skopeo_inspect("docker://{}".format(self.fqdn), return_json=True, args=['--raw'])

    @property
    def remote_id(self):
        result = self.get_manifest()
        if result.get('config'):
            return result['config'].get('digest', None)
        return None

    def assemble_fqdn(self, include_tag=True, registry=None):
        fqdn = "{}".format(registry or self.registry)
        fqdn = fqdn if not self.repo else "{}/{}".format(fqdn, self.repo)
        fqdn += "/{}".format(self.image)
        if include_tag:
            fqdn += ":{}".format(self.tag)
        return fqdn

    def find_image_on_registry(self):
        """
        Find the fully qualified image name for given input when
        registry is unknown
        :return: String fqdn
        """
        if self.debug:
            for i in [x for x in self.registries if x['search']]:
                util.write_out(i)

        registries = [i['name'] for i in [x for x in self.registries if x['search']]]
        for registry in registries:
            fqdn = self.assemble_fqdn(registry=registry, include_tag=True)
            util.write_out("Trying {}...".format(fqdn))
            try:
                result = util.skopeo_inspect("docker://{}".format(fqdn), return_json=True)
                self._remote_inspect = result
                return fqdn
            except ValueError as e:
                util.write_err("Failed: {}".format(e))
                continue
        raise RegistryInspectError("Unable to resolve {}".format(self.orig_input))


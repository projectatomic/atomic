from . import Atomic
from . import util
from docker.errors import NotFound
from docker.errors import APIError
import sys


class Delete(Atomic):
    def __init__(self):
        super(Delete, self).__init__()

    def delete_image(self):
        """
        Mark given image(s) for deletion from registry
        :return: True if all images marked for deletion
        """

        if not self.args.force_delete:
            confirm = util.input("Do you wish to delete {}? (y/N) ".format(self.args.delete_targets))
            confirm = confirm.strip().lower()
            if not confirm in ['y', 'yes']:
                sys.stderr.write("User aborted delete operation for {}\n".format(self.args.delete_targets))
                sys.exit(2)

        if self.args.remote_delete:
            results = self._delete_remote(self.args.delete_targets)
        else:
            results = self._delete_local(self.args.delete_targets)
        return results

    def _delete_remote(self, targets):
        results = 0
        for target in targets:
            # _convert_to_skopeo requires registry v1 support while delete requires v2 support
            # args, img = self.syscontainers._convert_to_skopeo(target)

            args = []
            if "http:" in target:
                args.append("--insecure")

            for i in ["oci:", "http:", "https:"]:
                img = target.replace(i, "docker:")

            if not img.startswith("docker:"):
                img = "docker://" + img

            try:
                util.skopeo_delete(img, args)
                util.write_out("Image {} marked for deletion".format(img))
            except ValueError as e:
                sys.stderr.write("Failed to mark Image {} for deletion: {}\n".format(img, e))
                results = 2
        return results

    def _delete_local(self, targets):
        results = 0
        for target in targets:
            try:
                self.d.remove_image(target)
            except NotFound as e:
                sys.stderr.write("Failed to delete Image {}: {}\n".format(target, e))
                results = 2
            except APIError as e:
                sys.stderr.write("Failed operation for delete Image {}: {}\n".format(target, e))
                results = 2
        return results

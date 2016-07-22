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
        :return: 0 if all images marked for deletion, otherwise 2 on any failure
        """

        if not self.args.force_delete:
            confirm = util.input("Do you wish to delete {}? (y/N) ".format(self.args.delete_targets))
            confirm = confirm.strip().lower()
            if not confirm in ['y', 'yes']:
                util.write_err("User aborted delete operation for {}".format(self.args.delete_targets))
                sys.exit(2)

        if self.args.remote_delete:
            results = self._delete_remote(self.args.delete_targets)
        else:
            results = self._delete_local(self.args.delete_targets)
        return results

    def prune_images(self):
        """
        Remove dangling images from registry
        :return: 0 if all images deleted or no dangling images found
        """
        enc = sys.getdefaultencoding()

        self.syscontainers.prune_ostree_images()

        results = self.d.images(filters={"dangling":True}, quiet=True)
        if len(results) == 0:
            return 0

        for img in results:
            self.d.remove_image(img.decode(enc), force=True)
            util.write_out("Removed dangling Image {}".format(enc))
        return 0

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
                util.write_err("Failed to mark Image {} for deletion: {}".format(img, e))
                results = 2
        return results

    def _delete_local(self, targets):
        results = 0
        for target in targets:
            try:
                self.d.remove_image(target)
            except NotFound as e:
                util.write_err("Failed to delete Image {}: {}".format(target, e))
                results = 2
            except APIError as e:
                util.write_err("Failed operation for delete Image {}: {}".format(target, e))
                results = 2
        return results

from . import Atomic
from . import util
import sys
from Atomic.backendutils import BackendUtils

class Delete(Atomic):
    def __init__(self):
        super(Delete, self).__init__()

    def delete_image(self):
        """
        Mark given image(s) for deletion from registry
        :return: 0 if all images marked for deletion, otherwise 2 on any failure
        """
        if self.args.debug:
            util.write_out(str(self.args))

        if len(self.args.delete_targets) > 0 and self.args.all:
            raise ValueError("You must select --all or provide a list of images to delete.")

        beu = BackendUtils()
        delete_objects = []

        # We need to decide on new returns for dbus because we now check image
        # validity prior to executing the delete.  If there is going to be a
        # failure, it will be here.
        #
        # The failure here is basically that it couldnt verify/find the image.

        if self.args.all:
            delete_objects = beu.get_images(get_all=True)
        else:
            for image in self.args.delete_targets:
                _, img_obj = beu.get_backend_and_image_obj(image, str_preferred_backend=self.args.storage)
                delete_objects.append(img_obj)

        if self.args.remote:
            return self._delete_remote(self.args.delete_targets)

        max_img_name = max([len(x.repotags[0] or x.id) for x in delete_objects]) + 2

        if not self.args.assumeyes:
            util.write_out("Do you wish to delete the following images?\n")
            two_col = "   {0:" + str(max_img_name) + "} {1}"
            util.write_out(two_col.format("IMAGE", "STORAGE"))
            for del_obj in delete_objects:
                image = del_obj.repotags[0]
                if image is None or "<none>" in image:
                    image = del_obj.id[0:12]
                util.write_out(two_col.format(image, del_obj.backend.backend))
            confirm = util.input("\nConfirm (y/N) ")
            confirm = confirm.strip().lower()
            if not confirm in ['y', 'yes']:
                util.write_err("User aborted delete operation for {}".format(self.args.delete_targets))
                sys.exit(2)

        # Perform the delete
        for del_obj in delete_objects:
            del_obj.backend.delete_image(del_obj.input_name, force=self.args.force)

        # We need to return something here for dbus
        return

    def prune_images(self):
        """
        Remove dangling images from registry
        :return: 0 if all images deleted or no dangling images found
        """

        if self.args.debug:
            util.write_out(str(self.args))

        for backend in BackendUtils.BACKENDS:
            be = backend()
            be.prune()

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



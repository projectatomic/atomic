from . import Atomic
from . import util
from .mount import Mount
import os
import sys
import json
import math
import shutil
import tempfile
import time

def convert_size(size):
    if size > 0:
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = int(math.floor(math.log(size, 1000)))
        p = math.pow(1000, i)
        s = round(size/p, 2) # pylint: disable=round-builtin,old-division
        if s > 0:
            return '%s %s' % (s, size_name[i])
    return '0B'


class Images(Atomic):
    def __init__(self):
        super(Images, self).__init__()

    def display_all_image_info(self):
        def get_col_lengths(_images):
            '''
            Determine the max length of the repository and tag names
            :param _images:
            :return: a set with len of repository and tag
            If there are no images, return 1, 1
            '''
            repo_tags = [[i["repo"], i["tag"]] for i in _images]
            if repo_tags:
                return max([len(x[0]) for x in repo_tags]) + 2,\
                       max([len(x[1]) for x in repo_tags]) + 2
            else:
                return 1, 1

        _images = self.images()
        if self.args.json:
            json.dump(_images, sys.stdout)
            return

        if len(_images) >= 0:
            _max_repo, _max_tag = get_col_lengths(_images)
            if self.args.truncate:
                _max_id = 14
            else:
                _max_id = 65

            col_out = "{0:2} {1:" + str(_max_repo) + "} {2:" + str(_max_tag) + \
                      "} {3:" + str(_max_id) + "} {4:18} {5:14} {6:10}"

            if self.args.heading and not self.args.quiet:
                util.write_out(col_out.format(" ",
                                              "REPOSITORY",
                                              "TAG",
                                              "IMAGE ID",
                                              "CREATED",
                                              "VIRTUAL SIZE",
                                              "TYPE"))

            for image in _images:
                if self.args.filter:
                    image_info = {"repo" : image['repo'], "tag" : image['tag'], "id" : image['id'],
                                  "created" : image['created'], "size" : image['virtual_size'], "type" : image['type']}
                    if not self._filter_include_image(image_info):
                        continue
                if self.args.quiet:
                    util.write_out(image['id'])

                else:
                    indicator = ""
                    if image["is_dangling"]:
                        indicator += "*"
                    elif image["used_image"]:
                        indicator += ">"
                    if image["vulnerable"]:
                        space = " " if len(indicator) < 1 else ""
                        if util.is_python2:
                            indicator = indicator + self.skull + space
                        else:
                            indicator = indicator + str(self.skull, "utf-8") + space
                    util.write_out(col_out.format(indicator, image['repo'], image['tag'], image['id'], image['created'], image['virtual_size'], image['type']))
            util.write_out("")
            return

    def images(self):
        _images = self.get_images(get_all=self.args.all)
        all_image_info = []

        if len(_images) >= 0:
            vuln_ids = self.get_vulnerable_ids()
            all_vuln_info = json.loads(self.get_all_vulnerable_info())
            used_image_ids = [x['ImageID'] for x in self.get_containers()]
            for image in _images:
                image_dict = dict()
                if not image["RepoTags"]:
                    continue
                if ':' in image["RepoTags"][0]:
                    repo, tag = image["RepoTags"][0].rsplit(":", 1)
                else:
                    repo, tag = image["RepoTags"][0], ""
                if "Created" in image:
                    created = time.strftime("%F %H:%M", time.localtime(image["Created"]))
                else:
                    created = ""
                if "VirtualSize" in image:
                    virtual_size = convert_size(image["VirtualSize"])
                else:
                    virtual_size = ""

                image_dict["is_dangling"] = self.is_dangling(repo)
                image_dict["used_image"] = image["Id"] in used_image_ids
                image_dict["vulnerable"] = image["Id"] in vuln_ids
                image_id = image["Id"][:12] if self.args.truncate else image["Id"]
                image_type = image['ImageType']
                image_dict["repo"] = repo
                image_dict["tag"] = tag
                image_dict["id"] = image_id
                image_dict["created"] = created
                image_dict["virtual_size"] = virtual_size
                image_dict["type"] = image_type
                image_dict["image_id"] = image["ImageId"]
                if image_dict["vulnerable"]:
                    image_dict["vuln_info"] = all_vuln_info[image["Id"]]
                else:
                    image_dict["vuln_info"] = dict()

                all_image_info.append(image_dict)
            return all_image_info

    def generate_validation_manifest(self):
        """
        Generates a gomtree validation manifest for a non-system image and stores it in
        ATOMIC_VAR_LIB
        :param:
        :return: None
        """
        _images = self.get_images(get_all=True)
        for image in _images:
            atomic_var_lib = util.ATOMIC_VAR_LIB
            if not image["RepoTags"]:
                continue
            iid = image["RepoTags"][0]
            if image["ImageType"] == "System":
                continue
            if iid == "<none>:<none>" or iid == "<none>":
                continue
            if os.path.exists(os.path.join(atomic_var_lib, "gomtree-manifests/%s.mtree" % iid)):
                continue
            manifestname = os.path.join(atomic_var_lib, "gomtree-manifests/%s.mtree" % iid)
            dname = os.path.dirname(manifestname)
            if not os.path.exists(dname):
                os.makedirs(dname)
            tmpdir = tempfile.mkdtemp()
            m = Mount()
            m.args = []
            m.image = iid
            m.mountpoint = tmpdir
            m.mount()
            r = util.generate_validation_manifest(img_rootfs=tmpdir, keywords="type,uid,gid,mode,size,sha256digest")
            m.unmount()
            with open(manifestname,"w",0) as f:
                f.write(r.stdout)
            shutil.rmtree(tmpdir)



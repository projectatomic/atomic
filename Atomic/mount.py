# Copyright (C) 2015-2016 Red Hat, All rights reserved.
# AUTHORS: William Temple <wtemple@redhat.com>
#          Brent Baude    <bbaude@redhat.com>
#
# This library is a component of Project Atomic.
#
#    Project Atomic is free software; you can redistribute it and/or
#    modify it under the terms of the GNU General Public License as
#    published by the Free Software Foundation; either version 2 of
#    the License, or (at your option) any later version.
#
#    Project Atomic is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Project Atomic; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
#    02110-1301 USA.
#

from . import Atomic
import os
import sys
import json
from fnmatch import fnmatch as matches
import time
import docker
from . import util
import requests
from Atomic.backends._docker_errors import NoDockerDaemon
import shutil
import subprocess
from .syscontainers import OSTREE_PRESENT as OSTREE_PRESENT
from gi.repository import GLib  # pylint: disable=no-name-in-module
import Atomic.backendutils as backendutils

# Module for mounting and unmounting containerized applications.

def path_exists(paths):
    for path in paths:
        if os.path.exists(path):
            return path
    raise ValueError("Unable to find command in {}".format(paths))

MOUNT_PATH = path_exists(['/usr/bin/mount', '/bin/mount'])
DMSETUP_PATH = path_exists(['/usr/sbin/dmsetup', '/sbin/dmsetup'])
LSBLK_PATH = path_exists(['/usr/bin/lsblk', '/bin/lsblk'])
FINDMNT_PATH = path_exists(['/usr/bin/findmnt', '/bin/findmnt'])

def cli_unmount(subparser):
    # atomic unmount
    unmountp = subparser.add_parser(
        "unmount", aliases=["umount"],help=_("unmount container image"),
        epilog="atomic unmount will unmount a container image previously "
        "mounted with atomic mount")
    unmountp.set_defaults(_class=Mount, func='unmount')
    unmountp.add_argument("mountpoint",
                          help=_("filesystem location of image/container to "
                                 "be unmounted"))


def cli(subparser):
    # atomic mount
    mountp = subparser.add_parser(
        "mount", help=_("mount container image to a specified directory"),
        epilog="atomic mount attempts to mount a container image to a "
        "specified directory so that its contents may be "
        "inspected.")
    mountp.set_defaults(_class=Mount, func='mount')
    mountp.add_argument("-o", "--options", dest="options", default="",
                        help=_("comma-separated list of mount options, "
                               "defaults are 'ro,nodev,nosuid'"))
    mountgroup = mountp.add_mutually_exclusive_group()
    mountgroup.add_argument("--live", dest="live", action="store_true",
                            help=_("mount a running container 'live', allowing "
                                   "modification of the contents."))
    mountgroup.add_argument("--shared", dest="shared", action="store_true",
                            help=_("mount a container image 'shared'. Mounts the container image with  an SELinux label "
                                   "that other containers can read."))
    mountgroup.add_argument("--storage", dest="storage", default="",
                            help=_("Specify the storage of the image. "
                                   "If not specified and there are images with the same name in "
                                   "different storages, you will be prompted to specify."))
    mountp.add_argument("image", help=_("image/container id"))
    mountp.add_argument("mountpoint", help=_("filesystem location to mount "
                                             "the image/container"))


class MountError(Exception):

    """Generic error mounting a candidate container."""

    def __init__(self, val):
        super(MountError, self).__init__()
        self.val = val

    def __str__(self):
        return str(self.val)


class SelectionMatchError(MountError):

    """Input identifier matched multiple mount candidates."""

    def __init__(self, i, all_matches):
        super(SelectionMatchError, self).__init__("")
        self.val = ('"{0}" matched multiple items. Try one of the following:\n'
                    '{1}'.format(i, '\n'.join(['\t' + m for m in all_matches])))

class Mount(Atomic):

    """
    A class which contains backend-independent methods useful for mounting and
    unmounting containers.
    """
    def __init__(self):
        """
        Constructs the Mount class with a mountpoint.
        Optional: mount a running container live (read/write)
        """
        super(Mount, self).__init__()
        self.mountpoint = ""
        self.live = False
        self.shared = False
        self.storage = ""
        self.options = ""
        self.user = util.is_user_mode()
        self.beu = backendutils.BackendUtils()

    def __exit__(self, typ, value, traceback): # pylint: disable=useless-super-delegation
        super(Mount, self).__exit__(typ, value, traceback)

    def set_args(self, args):
        Atomic.set_args(self, args)
        if hasattr(args, "mountpoint"):
            self.mountpoint = args.mountpoint
        if hasattr(args, "live"):
            self.live = args.live
        if hasattr(args, "shared"):
            self.shared = args.shared
        if hasattr(args, "storage"):
            self.storage = args.storage
        if getattr(args, "options", None):
            self.options = [opt for opt in args.options.split(',') if opt]
        if hasattr(args, "image"):
            self.image = args.image

    def _info(self):
        return self.d.info()

    def _try_ostree_mount(self, best_mountpoint_for_storage):
        if best_mountpoint_for_storage:
            mountpoint = os.path.join(self.syscontainers.get_ostree_repo_location(), "tmp/atomic-mount", str(os.getpid()), self.image)
            if os.path.exists(mountpoint):
                shutil.rmtree(mountpoint)
            os.makedirs(mountpoint)
        else:
            mountpoint = self.mountpoint

        d = OSTreeMount(self.args, mountpoint, live=self.live, shared=self.shared)
        if d.mount(self.image, self.options):
            self.mountpoint = mountpoint
            return True

        return False

    # if best_mountpoint_for_storage the storage can modify the mountpoint so
    # to optimize the checkout (for example OSTree requires this to create
    # hard links on the same file system.
    def mount(self, best_mountpoint_for_storage=False):

        if not self.storage:
            if len(self.beu.available_backends) > 1:
                if self.is_duplicate_image(self.image):
                    raise ValueError("Found more than one Image with name {}; "
                                     "please specify with --storage.".format(self.image))
            try:
                if self._try_ostree_mount(best_mountpoint_for_storage):
                    return
            except GLib.Error: # pylint: disable=catching-non-exception
                pass
            d = DockerMount(self.mountpoint, self.live)
            d.shared = self.shared
            d.mount(self.image, self.options)

            # only need to bind-mount on the devicemapper driver
            if self._info()['Driver'] == 'devicemapper':
                Mount.mount_path(os.path.join(self.mountpoint, "rootfs"),
                                 self.mountpoint,
                                 bind=True)

        elif self.storage.lower() == "ostree":
            try:
                res = self._try_ostree_mount(best_mountpoint_for_storage)
                # If ostree storage was explicitely requested, then we have to
                # error out if the container/image could not be mounted.
                if res == False:
                    raise ValueError("Could not mount {}".format(self.image))
            except GLib.Error: # pylint: disable=catching-non-exception
                self._no_such_image()

        elif self.storage.lower() == "docker":
            d = DockerMount(self.mountpoint, self.live)
            d.shared = self.shared
            d.mount(self.image, self.options)

            # only need to bind-mount on the devicemapper driver
            if self._info()['Driver'] == 'devicemapper':
                Mount.mount_path(os.path.join(self.mountpoint, "rootfs"),
                                 self.mountpoint,
                                 bind=True)

        else:
            raise ValueError("{} is not a valid storage".format(self.storage))

    def unmount(self):
        if OSTreeMount(self.args, self.mountpoint).unmount():
            return

        dev = Mount.get_dev_at_mountpoint(self.mountpoint)

        # If there's a bind-mount over the directory, unbind it.
        if dev.rsplit('[', 1)[-1].strip(']') == '/rootfs' \
                and self.d.info()['Driver'] == 'devicemapper':
            Mount.unmount_path(self.mountpoint)

        return DockerMount(self.mountpoint).unmount()

    # LVM DeviceMapper Utility Methods
    @staticmethod
    def _activate_thin_device(name, dm_id, size, pool):
        """
        Provisions an LVM device-mapper thin device reflecting,
        DM device id 'dm_id' in the docker pool.
        """
        table = '0 %d thin /dev/mapper/%s %s' %  (int(size)//512, pool, dm_id)

        cmd = [DMSETUP_PATH, 'create', name, '--table', table]
        r = util.subp(cmd)
        if r.return_code != 0:
            raise MountError('Failed to create thin device: %s' %
                             r.stderr.decode(sys.getdefaultencoding()))

    @staticmethod
    def _remove_thin_device(name):
        """
        Destroys a thin device via subprocess call.
        """
        r = util.subp([DMSETUP_PATH, 'remove', '--retry', name])
        if r.return_code != 0:
            raise MountError('Could not remove thin device:\n%s' %
                             r.stderr.decode(sys.getdefaultencoding()).split("\n")[0])

    @staticmethod
    def _get_fs(thin_pathname):
        """
        Returns the file system type (xfs, ext4) of a given device
        """
        cmd = [LSBLK_PATH, '-o', 'FSTYPE', '-n', thin_pathname]
        fs_return = util.subp(cmd)
        return fs_return.stdout.strip()

    @staticmethod
    def mount_path(source, target, optstring='', bind=False):
        """
        Subprocess call to mount dev at path.
        """
        cmd = [MOUNT_PATH]
        if bind:
            cmd.append('--bind')
        if optstring:
            cmd.append('-o')
            cmd.append(optstring)
        cmd.append(source)
        cmd.append(target)
        r = util.subp(cmd)
        if r.return_code != 0:
            raise MountError('Could not mount docker container:\n' +
                             ' '.join(cmd) + '\n%s' %
                             r.stderr.decode(sys.getdefaultencoding()))

    @staticmethod
    def get_dev_at_mountpoint(mntpoint):
        """
        Retrieves the device mounted at mntpoint, or raises
        MountError if none.
        """
        results = util.subp(['findmnt', '-o', 'SOURCE', '-n', mntpoint])
        if results.return_code != 0:
            raise MountError('No device mounted at %s' % mntpoint)
        stdout = results.stdout.decode(sys.getdefaultencoding())
        return stdout.strip()

    @staticmethod
    def unmount_path(path, timeout=10):
        """
        Unmounts the directory specified by path.
        """

        # Added this timeout loop because it seems openscap/openscap-daemon
        # still has a left over process running that causes the mount path
        # to be busy and therefore causes the unmount to fail.
        #
        # When that is fixed, this can revert to a simple command executed
        # by subp.
        for x in range(0, timeout, 1):
            rc, result_stdout, result_stderr = util.subp(['umount', path])
            if rc == 0:
                return rc, result_stdout, result_stderr
            util.write_err("Warning: {}\nRetrying {}/{} to unmount {}"
                             .format(result_stderr, x+1, timeout, path))
            time.sleep(1)
        raise ValueError("Unable to unmount {0} due to {1}".format(path, result_stderr))


class DockerMount(Mount):

    """
    A class which can be used to mount and unmount docker containers and
    images on a filesystem location.

    mnt_mkdir = Create temporary directories based on the cid at mountpoint
                for mounting containers
    """

    def __init__(self, mountpoint, live=False, mnt_mkdir=False):
        Mount.__init__(self)
        self.mountpoint = mountpoint
        self.live = live
        self.mnt_mkdir = mnt_mkdir
        self.tmp_image = None

    def _create_temp_container(self, iid):
        """
        Create a temporary container from a given iid.

        Temporary containers are marked with a sentinel environment
        variable so that they can be cleaned on unmount.
        """
        try:
            return self.d.create_container(
                image=iid, command='/bin/true',
                environment=['_ATOMIC_TEMP_CONTAINER'],
                detach=True, network_disabled=True)['Id']
        except docker.errors.APIError as ex:
            raise MountError('Error creating temporary container:\n%s' % str(ex))

    def _clone(self, cid, image_only=False):
        """
        Create a temporary image snapshot from a given cid and then
        create temporary container from the temporary image.

        Temporary image snapshots are marked with a sentinel label
        so that they can be cleaned on unmount.

        image_only: Create the image from the container only

        Return:  the id of the temporary container unless image_only=True
                 in which case it returns the image cloned image id.
        """
        try:
            iid = self.d.commit(
                container=cid,
                conf={
                    'Labels': {
                        'io.projectatomic.Temporary': 'true'
                    }
                }
            )['Id']
        except docker.errors.APIError as ex:
            raise MountError(ex)
        self.tmp_image = iid
        if image_only:
            return iid
        else:
            return self._create_temp_container(iid)

    def _identifier_as_cid(self, identifier):
        """
        Returns a container uuid for identifier.

        If identifier is an image UUID or image tag, create a temporary
        container and return its uuid.
        """
        def __cname_matches(container, identifier):
            return any([n for n in (container['Names'] or [])
                        if matches(n, '/' + identifier)])

        # Determine if identifier is a container
        containers = [c['Id'] for c in self.d.containers(all=True)
                      if (__cname_matches(c, identifier) or
                          matches(c['Id'], identifier + '*'))]

        if len(containers) > 1:
            raise SelectionMatchError(identifier, containers)
        elif len(containers) == 1:
            c = containers[0]
            return c if self.live else self._clone(c)

        # Determine if identifier is an image UUID
        images = [i for i in set(self.d.images(all=True, quiet=True))
                  if i.startswith(identifier)]

        if len(images) > 1:
            raise SelectionMatchError(identifier, images)
        elif len(images) == 1:
            return self._create_temp_container(images[0])

        # Check if identifier is fully qualified
        # local import only
        from Atomic.objects.image import Image
        _image = Image(identifier)
        if _image.fully_qualified:
            return self._create_temp_container(identifier)

        # Match image tag.
        images = util.image_by_name(identifier)
        if len(images) > 1:
            tags = [t for i in images for t in i['RepoTags']]
            raise SelectionMatchError(identifier, tags)
        elif len(images) == 1:
            return self._create_temp_container(images[0]['Id'].replace("sha256:", ""))

        raise MountError('{} did not match any image or container.'
                         ''.format(identifier))

    @staticmethod
    def _no_gd_api_dm(cid):
        desc_file = os.path.join(util.default_docker_lib(), cid)
        desc = json.loads(open(desc_file).read())
        return desc['device_id'], desc['size']

    @staticmethod
    def _no_gd_api_overlay(cid, driver):
        prefix = os.path.join(util.default_docker_lib() % driver, cid)
        ld_metafile = open(os.path.join(prefix, 'lower-id'))
        ld_loc = os.path.join(util.default_docker_lib() % driver, ld_metafile.read())
        return (os.path.join(ld_loc, 'root'), os.path.join(prefix, 'upper'),
                os.path.join(prefix, 'work'), os.path.join(prefix, 'merged'))

    def mount(self, identifier, options=None): # pylint: disable=arguments-differ
        """
        Mounts a container or image referred to by identifier to
        the host filesystem.
        """
        if not options:
            options=[]
        try:
            # Check if a container/image is already mounted at the
            # desired mount point.
            cid, _ = self._get_cid_from_mountpoint(self.mountpoint)
            if cid:
                raise ValueError("container/image '{0}' already mounted at '{1}'"
                                 .format(cid, self.mountpoint))
        except MountError:
            pass

        try:
            driver = self._info()['Driver']
        except requests.exceptions.ConnectionError:
            raise NoDockerDaemon()

        driver_mount_fn = getattr(self, "_mount_" + driver,
                                  self._unsupported_backend)
        driver_mount_fn(identifier, options)

        # Return mount path so it can be later unmounted by path
        return self.mountpoint

    def _unsupported_backend(self, identifier='', options=None, path=None): # pylint: disable=unused-argument
        if not options:
            options=[]
        raise MountError('Atomic mount is not supported on the {} docker '
                         'storage backend.'
                         ''.format(self._info()['Driver']))

    def default_options(self, options, default_con=None, default_opt=None):
        """
        Merges user options with default options and determines security
        context.
        """
        if not default_opt:
            default_opt=[]

        if not options:
            options = default_opt
        # Determines default context.
        if all([o.find('context=') == -1 for o in options]):
            options.append('context="' +
                           (default_con if default_con else
                            util.default_container_context()) + '"')
        return options

    def _mount_devicemapper(self, identifier, options):
        """
        Devicemapper mount backend.
        """
        if self.live and options:
            raise MountError('Cannot set mount options for live container '
                             'mount.')

        info = self._info()

        cid = self._identifier_as_cid(identifier)

        if self.mnt_mkdir:
            # If the given mount_path is just a parent dir for where
            # to mount things by cid, then the new mountpoint is the
            # mount_path plus the first 20 chars of the cid
            self.mountpoint = os.path.join(self.mountpoint, cid[:20])

            try:
                if not os.path.exists(self.mountpoint):
                    os.mkdir(self.mountpoint)
            except (TypeError, OSError) as e:
                raise MountError(e)

        cinfo = self.d.inspect_container(cid)

        if self.live and not cinfo['State']['Running']:
            self._cleanup_container(cinfo)
            raise MountError('Cannot live mount non-running container.')

        if self.shared:
            defcon=util.default_ro_container_context()
        else:
            defcon=cinfo['MountLabel']

        options = self.default_options(
            options, default_con=defcon,
            default_opt=[] if self.live else ['ro', 'nosuid', 'nodev'])

        dm_dev_name, dm_dev_id, dm_dev_size = '', '', ''
        dm_pool = info['DriverStatus'][0][1]

        try:
            dm_dev_name = cinfo['GraphDriver']['Data']['DeviceName']
            dm_dev_id = cinfo['GraphDriver']['Data']['DeviceId']
            dm_dev_size = cinfo['GraphDriver']['Data']['DeviceSize']
        except KeyError:
            dm_dev_id, dm_dev_size = DockerMount._no_gd_api_dm(cid)
            dm_dev_name = dm_pool.replace('pool', cid)

        dm_dev_path = os.path.join('/dev/mapper', dm_dev_name)
        # If the device isn't already there, activate it.
        if not os.path.exists(dm_dev_path):
            if self.live:
                raise MountError('Error: Attempted to live-mount unactivated '
                                 'device.')
            Mount._activate_thin_device(dm_dev_name, dm_dev_id, dm_dev_size,
                                        dm_pool)

        # XFS should get nouuid
        fstype = Mount._get_fs(dm_dev_path).decode(sys.getdefaultencoding())
        if fstype.upper() == 'XFS' and 'nouuid' not in options:
            if 'nouuid' not in options:
                options.append('nouuid')
        try:
            Mount.mount_path(dm_dev_path, self.mountpoint,
                             optstring=(','.join(options)))
        except MountError as de:
            self._cleanup_container(cinfo)
            if not self.live:
                try:
                    Mount._remove_thin_device(dm_dev_name)
                except MountError:
                    pass
            raise de

    def _mount_overlay2(self, identifier, options):
        return self._mount_overlay(identifier, options, "overlay2")

    def _mount_overlay(self, identifier, options, driver="overlay"):
        """
        OverlayFS mount backend.
        """
        if 'rw' in options:
            raise MountError('The OverlayFS backend does not support '
                             'writeable mounts.')

        cid = self._identifier_as_cid(identifier)

        if self.mnt_mkdir:
            # If the given mount_path is just a parent dir for where
            # to mount things by cid, then the new mountpoint is the
            # mount_path plus the first 20 chars of the cid
            self.mountpoint = os.path.join(self.mountpoint, cid[:20])

            try:
                if not os.path.exists(self.mountpoint):
                    os.mkdir(self.mountpoint)
            except (TypeError, OSError) as e:
                raise MountError(e)

        cinfo = self.d.inspect_container(cid)

        ld, ud, wd = '', '', ''
        try:
            ld = cinfo['GraphDriver']['Data']['LowerDir']
            ud = cinfo['GraphDriver']['Data']['UpperDir']
            wd = cinfo['GraphDriver']['Data']['WorkDir']
            md = cinfo['GraphDriver']['Data']['MergedDir']
        except KeyError:
            ld, ud, wd, md = DockerMount._no_gd_api_overlay(cid, driver)

        if self.live:
            # when not running, mounts are not set up yet
            if not cinfo['State']['Running']:
                raise MountError("Container needs to be running when doing live mount for "
                                 "overlay backend.")
            try:
                dev_type = Mount.get_dev_at_mountpoint(self.mountpoint)
            except MountError:
                # nothing mounted, good
                pass
            else:
                if dev_type == 'overlay':
                    # seems like we already mounted here; user error?
                    raise MountError("Path %s is already used as a mountpoint." % self.mountpoint)
            cmd = [MOUNT_PATH, "--bind", md, self.mountpoint]
        else:
            options += ['ro', 'lowerdir=' + ld, 'upperdir=' + ud, 'workdir=' + wd]
            optstring = ','.join(options)
            cmd = [MOUNT_PATH, '-t', 'overlay', '-o', optstring, 'overlay',
                   self.mountpoint]
        status = util.subp(cmd)

        if status.return_code != 0:
            self._cleanup_container(cinfo)
            raise MountError('Failed to mount OverlayFS device.\n%s' %
                             status.stderr.decode(sys.getdefaultencoding()))

    def _cleanup_container(self, cinfo):
        """
        Remove a container and clean up its image if necessary.
        """
        # I'm not a fan of doing this again here.
        env = cinfo['Config']['Env']
        if (env and '_ATOMIC_TEMP_CONTAINER' not in env) or not env:
            return

        iid = cinfo['Image']
        self.d.remove_container(cinfo['Id'])
        try:
            labels = self.d.inspect_image(iid)['Config']['Labels']
        except TypeError:
            labels = {}
        if labels and 'io.projectatomic.Temporary' in labels:
            if labels['io.projectatomic.Temporary'] == 'true':
                self.d.remove_image(iid)

        # If we are creating temporary dirs for mount points
        # based on the cid, then we should rmdir them while
        # cleaning up.
        if self.mnt_mkdir:
            try:
                os.rmdir(self.mountpoint)
            except Exception as e:
                raise MountError(e)

    def _clean_tmp_image(self):
        # If a temporary image is created with commit,
        # clean up that too
        if self.tmp_image is not None:
            self.d.remove_image(self.tmp_image, noprune=True)

    def unmount(self, path=None):  #pylint: disable=arguments-differ
        """
        Unmounts and cleans-up after a previous mount().
        """
        driver = self._info()['Driver']
        driver_unmount_fn = getattr(self, "_unmount_" + driver,
                                    self._unsupported_backend)
        driver_unmount_fn(path=path)

    def _get_all_cids(self):
        '''
        Simple function that returns a list of the container
        IDs.
        '''
        return [x['Id'] for x in self.d.containers(all=True)]

    def _get_cid_from_mountpoint(self, mountpoint):
        dev = Mount.get_dev_at_mountpoint(mountpoint)
        dev_name = dev.replace('/dev/mapper/', '').replace('[/rootfs]', '')

        cid = None
        for c in self._get_all_cids():
            graph = self.d.inspect_container(c)["GraphDriver"]
            if graph["Name"] != "devicemapper":
                continue
            if dev_name == graph["Data"]["DeviceName"]:
                cid=c
                break

        return cid, dev_name

    def _unmount_devicemapper(self, path=None):
        """
        Devicemapper unmount backend.
        """
        mountpoint = self.mountpoint if path is None else path
        cid, dev_name = self._get_cid_from_mountpoint(mountpoint)
        if not cid:
            raise MountError('Device mounted at {} is not a docker container.'
                             ''.format(mountpoint))
        Mount.unmount_path(mountpoint)
        cinfo = self.d.inspect_container(cid)

        # Was the container live mounted? If so, done.
        #       Fix in docker-py.
        env = cinfo['Config']['Env']
        if (env and '_ATOMIC_TEMP_CONTAINER' not in env) or not env:
            return

        Mount._remove_thin_device(dev_name)
        self._cleanup_container(cinfo)

    def _get_overlay_mount_cid(self, driver):
        """
        Returns the cid of the container mounted at mountpoint.
        """
        cmd = [FINDMNT_PATH, '-o', 'OPTIONS', '-n', self.mountpoint]
        r = util.subp(cmd)
        if r.return_code != 0:
            raise MountError('No devices mounted at that location.')
        stdout = r.stdout.decode(sys.getdefaultencoding())
        optstring = stdout.strip().split('\n')[-1]
        upperdir = [o.replace('upperdir=', '') for o in optstring.split(',')
                    if o.startswith('upperdir=')][0]
        cdir = upperdir.rsplit('/', 1)[0]
        if not cdir.startswith("{}/{}".format(util.default_docker_lib(), driver)):
            raise MountError('The device mounted at %s is not a '
                             'docker container.' % self.mountpoint )

        for c in self._get_all_cids():
            graph = self.d.inspect_container(c)["GraphDriver"]
            if graph['Data']['UpperDir'].startswith(cdir):
                return c

        raise MountError('The device mounted at %s is not a '
                         'docker container.' % self.mountpoint )

    def _unmount_overlay2(self, path=None):
        self._unmount_overlay(path, "overlay2")

    def _unmount_overlay(self, path=None, driver="overlay"):
        """
        OverlayFS unmount backend.
        """
        mountpoint = self.mountpoint if path is None else path

        if Mount.get_dev_at_mountpoint(mountpoint) != 'overlay':
            raise MountError('Device mounted at {} is not an atomic mount.'.format(mountpoint))
        cid = self._get_overlay_mount_cid(driver)
        Mount.unmount_path(mountpoint)
        self._cleanup_container(self.d.inspect_container(cid))

    def _clean_temp_container_by_path(self, path):
        """
        Do not remove this method.  It is used by openscap.
        """
        short_cid = os.path.basename(path)
        if not self.live:
            self.d.remove_container(short_cid)
        self._clean_tmp_image()


def getxattrfuncs():
    # Python 3 has support for extended attributes in the os module, while
    # Python 2 needs the xattr library.  Detect if any is available.
    module = None
    if getxattrfuncs.setxattr:
        return getxattrfuncs.setxattr, getxattrfuncs.getxattr, getxattrfuncs.removexattr
    if getattr(os, 'setxattr', None):
        module = os
    else:
        try:
            import xattr #pylint: disable=import-error
            module = xattr
        except ImportError:
            pass

    if module:
        getxattrfuncs.setxattr = getattr(module, 'setxattr')
        getxattrfuncs.getxattr = getattr(module, 'getxattr')
        getxattrfuncs.removexattr = getattr(module, 'removexattr')

    return getxattrfuncs.setxattr, getxattrfuncs.getxattr, getxattrfuncs.removexattr
getxattrfuncs.setxattr = None
getxattrfuncs.getxattr = None
getxattrfuncs.removexattr = None

class OSTreeMount(Mount):

    """
    A class which can be used to mount and unmount containers and
    images managed through OSTree on a filesystem location.
    """

    def __init__(self, args, mountpoint, live=False, mnt_mkdir=False, shared=False):
        Mount.__init__(self)
        self.args = args
        self.syscontainers.set_args(args)
        self.mountpoint = mountpoint
        self.live = live
        self.shared = shared
        self.mnt_mkdir = mnt_mkdir
        self.tmp_image = None
        self.user = util.is_user_mode()
        setxattr, _, _ = getxattrfuncs()

        if setxattr is None:
            raise MountError('xattr required to mount OSTree images.')

    def has_container(self, container_id):
        return self.syscontainers.get_checkout(container_id)

    def has_image(self, image_id):
        return self.syscontainers.has_image(image_id)

    def mount(self, identifier, options=None): # pylint: disable=arguments-differ
        if not options:
            options = []
        setxattr, _, _ = getxattrfuncs()

        if not OSTREE_PRESENT:
            return False

        identifier = util.remove_skopeo_prefixes(identifier)

        options = ['remount', 'ro', 'nosuid', 'nodev']
        has_container = self.has_container(identifier)
        has_image = self.has_image(identifier)

        if has_container or has_image:
            if self.live:
                raise MountError('Containers and images managed through OSTree do not support --live.')

        if has_container:
            if self.user:
                raise MountError('Need to be root to mount a container.')
            typ = "container"
            source = os.path.join(self.syscontainers.get_checkout(identifier), "rootfs")
            Mount.mount_path(source, self.mountpoint, bind=True)
        elif has_image:
            typ = "image"
            if len(os.listdir(self.mountpoint)):
                raise MountError('The destination path is not empty.')

            mounted = False
            if not self.user:
                try:
                    self.syscontainers.mount_from_storage(identifier, self.mountpoint, debug=self.args.debug) #pylint: disable=no-member
                    typ = "image-storage"
                    mounted = True
                except (subprocess.CalledProcessError, ValueError):
                    pass

            if not mounted:
                abspath = os.path.abspath(self.mountpoint)
                self.syscontainers.extract(identifier, abspath)
                if not self.user:
                    Mount.mount_path(abspath, abspath, bind=True)
        else:
            return False

        typ = ("ostree-%s" % typ).encode()
        try:
            setxattr(self.mountpoint, "user.atomic.type", typ) # pylint: disable=not-callable
        except IOError:
            mountpoint = self.mountpoint.rstrip('/')
            infofile = os.path.join(os.path.dirname(mountpoint), ".%s.info" % os.path.basename(mountpoint))
            with open(infofile, 'w') as f:
                data = json.dumps({"user.atomic.type" : typ.decode('utf-8')})
                f.write(data)

        return True

    def unmount(self, path=None): # pylint: disable=arguments-differ
        _, getxattr, removexattr = getxattrfuncs()
        typ = None

        if not OSTREE_PRESENT:
            return False

        if not self.mountpoint:
            return False

        typ = None
        try:
            typ = getxattr(self.mountpoint, "user.atomic.type") # pylint: disable=not-callable
        except IOError:
            pass

        mountpoint = self.mountpoint.rstrip('/')
        infofile = os.path.join(os.path.dirname(mountpoint), ".%s.info" % os.path.basename(mountpoint))
        if typ == None and os.path.exists(infofile):
            with open(infofile) as f:
                info = json.loads(f.read())
                typ = info['user.atomic.type']

        if typ == None or "ostree" not in str(typ):
            return False

        if self.user:
            for root,dirs,_ in os.walk(self.mountpoint):
                for d in dirs:
                    dirpath = os.path.join(root,d)
                    if os.path.islink(dirpath):
                        os.unlink(dirpath)
                    elif os.path.isdir(dirpath):
                        shutil.rmtree(dirpath)
                    else:
                        os.remove(dirpath)
        else:
            Mount.unmount_path(self.mountpoint)

        if "-image" in str(typ) and not "storage" in str(typ):
            for i in os.listdir(self.mountpoint):
                path = os.path.join(self.mountpoint, i)
                if os.path.islink(path):
                    os.unlink(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
        try:
            removexattr(self.mountpoint, "user.atomic.type") # pylint: disable=not-callable
        except IOError:
            if os.path.exists(infofile):
                os.unlink(infofile)

        return True


class MountContextManager(object):
    """
    context manager for DockerMount and OSTreeMount classes
    """

    def __init__(self, mount_instance, identifier, mount_options=None):
        """
        mount_instance - DockerMount or OSTreeMount instance
        identifier - container ID or image ID
        mount_options - options passed to mount method of mount_instance
        """
        if not isinstance(mount_instance, (DockerMount, OSTreeMount)):
            raise ValueError('mount_instance needs to be instance of DockerMount or OSTreeMount')
        self.mount_instance = mount_instance
        self.identifier = identifier
        self.mount_options = mount_options
        self.mnt_path = None

    def __enter__(self):
        self.mnt_path = self.mount_instance.mount(self.identifier, options=self.mount_options)
        return self

    def __exit__(self, *args):
        self.mount_instance.unmount(path=self.mnt_path)

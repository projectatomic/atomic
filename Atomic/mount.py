# Copyright (C) 2015 Red Hat, All rights reserved.
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
from .client import get_docker_client
from . import util
import requests
from .util import NoDockerDaemon
import shutil
from .atomic import OSTREE_PRESENT as OSTREE_PRESENT

""" Module for mounting and unmounting containerized applications. """


class MountError(Exception):

    """Generic error mounting a candidate container."""

    def __init__(self, val):
        self.val = val

    def __str__(self):
        return str(self.val)


class SelectionMatchError(MountError):

    """Input identifier matched multiple mount candidates."""

    def __init__(self, i, matches):
        self.val = ('"{0}" matched multiple items. Try one of the following:\n'
                    '{1}'.format(i, '\n'.join(['\t' + m for m in matches])))


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
        self.options = ""

    def set_args(self, args):
        if "mountpoint" in args:
            self.mountpoint = args.mountpoint
        if "live" in args:
            self.live = args.live
        if "shared" in args:
            self.shared = args.shared
        if "options" in args:
            self.options = [opt for opt in args.options.split(',') if opt]
        if "image" in args:
            self.image = args.image

    def mount(self):
        try:
            d = OSTreeMount(self.mountpoint, live=self.live, shared=self.shared)
            if d.mount(self.image, self.options):
                return

            d = DockerMount(self.mountpoint, self.live)
            d.shared = self.shared
            d.mount(self.image, self.options)

            # only need to bind-mount on the devicemapper driver
            if self.d.info()['Driver'] == 'devicemapper':
                Mount.mount_path(os.path.join(self.mountpoint, "rootfs"),
                                 self.mountpoint,
                                 bind=True)

        except (MountError, NoDockerDaemon) as dme:
            raise ValueError(str(dme))

    def unmount(self):

        try:
            if OSTreeMount(self.mountpoint).unmount():
                return

            dev = Mount.get_dev_at_mountpoint(self.mountpoint)

            # If there's a bind-mount over the directory, unbind it.
            if dev.rsplit('[', 1)[-1].strip(']') == '/rootfs' \
                    and self.d.info()['Driver'] == 'devicemapper':
                Mount.unmount_path(self.mountpoint)

            return DockerMount(self.mountpoint).unmount()

        except MountError as dme:
            raise ValueError(str(dme))

    # LVM DeviceMapper Utility Methods
    @staticmethod
    def _activate_thin_device(name, dm_id, size, pool):
        """
        Provisions an LVM device-mapper thin device reflecting,
        DM device id 'dm_id' in the docker pool.
        """
        table = '0 %d thin /dev/mapper/%s %s' %  (int(size)//512, pool, dm_id)

        cmd = ['dmsetup', 'create', name, '--table', table]
        r = util.subp(cmd)
        if r.return_code != 0:
            raise MountError('Failed to create thin device: %s' %
                             r.stderr.decode(sys.getdefaultencoding()))

    @staticmethod
    def _remove_thin_device(name):
        """
        Destroys a thin device via subprocess call.
        """
        r = util.subp(['dmsetup', 'remove', '--retry', name])
        if r.return_code != 0:
            raise MountError('Could not remove thin device:\n%s' %
                             r.stderr.decode(sys.getdefaultencoding()).split("\n")[0])

    @staticmethod
    def _is_device_active(device):
        """
        Checks dmsetup to see if a device is already active
        """
        cmd = ['dmsetup', 'info', device]
        dmsetup_info = util.subp(cmd)
        for dm_line in dmsetup_info.stdout.split("\n"):
            line = dm_line.split(':')
            if ('State' in line[0].strip()) and ('ACTIVE' in line[1].strip()):
                return True
        return False

    @staticmethod
    def _get_fs(thin_pathname):
        """
        Returns the file system type (xfs, ext4) of a given device
        """
        cmd = ['lsblk', '-o', 'FSTYPE', '-n', thin_pathname]
        fs_return = util.subp(cmd)
        return fs_return.stdout.strip()

    @staticmethod
    def mount_path(source, target, optstring='', bind=False):
        """
        Subprocess call to mount dev at path.
        """
        cmd = ['mount']
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
        results = util.subp(['findmnt', '-o', 'SOURCE', mntpoint])
        if results.return_code != 0:
            raise MountError('No device mounted at %s' % mntpoint)

        stdout = results.stdout.decode(sys.getdefaultencoding())
        return stdout.replace('SOURCE\n', '').strip().split('\n')[-1]

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
            sys.stderr.write("Warning: {}\nRetrying {}/{} to unmount {}\n"
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
            raise MountError(str(ex))
        self.tmp_image = iid
        if image_only:
            return iid
        else:
            return self._create_temp_container(iid)

    def _is_container_running(self, cid):
        cinfo = self.d.inspect_container(cid)
        return cinfo['State']['Running']

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
        # TODO: Deprecated
        desc_file = os.path.join('/var/lib/docker/devicemapper/metadata', cid)
        desc = json.loads(open(desc_file).read())
        return desc['device_id'], desc['size']

    @staticmethod
    def _no_gd_api_overlay(cid):
        # TODO: Deprecated
        prefix = os.path.join('/var/lib/docker/overlay/', cid)
        ld_metafile = open(os.path.join(prefix, 'lower-id'))
        ld_loc = os.path.join('/var/lib/docker/overlay/', ld_metafile.read())
        return (os.path.join(ld_loc, 'root'), os.path.join(prefix, 'upper'),
                os.path.join(prefix, 'work'))

    def mount(self, identifier, options=[]):
        """
        Mounts a container or image referred to by identifier to
        the host filesystem.
        """
        try:
            # Check if a container/image is already mounted at the
            # desired mount point.
            cid, dev_name = self._get_cid_from_mountpoint(self.mountpoint)
            if cid:
                raise ValueError("container/image '{0}' already mounted at '{1}'"
                                 .format(cid, self.mountpoint))
        except MountError:
            pass

        try:
            driver = self.d.info()['Driver']
        except requests.exceptions.ConnectionError:
            raise NoDockerDaemon()

        driver_mount_fn = getattr(self, "_mount_" + driver,
                                  self._unsupported_backend)
        driver_mount_fn(identifier, options)

        # Return mount path so it can be later unmounted by path
        return self.mountpoint

    def _unsupported_backend(self, identifier='', options=[]):
        raise MountError('Atomic mount is not supported on the {} docker '
                         'storage backend.'
                         ''.format(self.d.info()['Driver']))

    def _default_options(self, options, default_con=None, default_options=[]):
        """
        Merges user options with default options and determines security
        context.
        """
        if not options:
            options = default_options
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

        info = self.d.info()

        cid = self._identifier_as_cid(identifier)

        if self.mnt_mkdir:
            # If the given mount_path is just a parent dir for where
            # to mount things by cid, then the new mountpoint is the
            # mount_path plus the first 20 chars of the cid
            self.mountpoint = os.path.join(self.mountpoint, cid[:20])

            try:
                if not os.path.exists(self.mountpoint) :
                    os.mkdir(self.mountpoint)
            except Exception as e:
                raise MountError(e)

        cinfo = self.d.inspect_container(cid)

        if self.live and not cinfo['State']['Running']:
            self._cleanup_container(cinfo)
            raise MountError('Cannot live mount non-running container.')

        if self.shared:
            defcon=util.default_ro_container_context()
        else:
            defcon=cinfo['MountLabel']

        options = self._default_options(
            options, default_con=defcon,
            default_options=[] if self.live else ['ro', 'nosuid', 'nodev'])

        dm_dev_name, dm_dev_id, dm_dev_size = '', '', ''
        dm_pool = info['DriverStatus'][0][1]

        try:
            dm_dev_name = cinfo['GraphDriver']['Data']['DeviceName']
            dm_dev_id = cinfo['GraphDriver']['Data']['DeviceId']
            dm_dev_size = cinfo['GraphDriver']['Data']['DeviceSize']
        except:
            # TODO: deprecated when GraphDriver patch makes it upstream
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
                Mount._remove_thin_device(dm_dev_name)
            raise de

    def _mount_overlay(self, identifier, options):
        """
        OverlayFS mount backend.
        """
        if self.live:
            raise MountError('The OverlayFS backend does not support live '
                             'mounts.')
        elif 'rw' in options:
            raise MountError('The OverlayFS backend does not support '
                             'writeable mounts.')

        cid = self._identifier_as_cid(identifier)
        cinfo = self.d.inspect_container(cid)

        ld, ud, wd = '', '', ''
        try:
            ld = cinfo['GraphDriver']['Data']['lowerDir']
            ud = cinfo['GraphDriver']['Data']['upperDir']
            wd = cinfo['GraphDriver']['Data']['workDir']
        except:
            ld, ud, wd = DockerMount._no_gd_api_overlay(cid)

        options += ['ro', 'lowerdir=' + ld, 'upperdir=' + ud, 'workdir=' + wd]
        optstring = ','.join(options)
        cmd = ['mount', '-t', 'overlay', '-o', optstring, 'overlay',
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

    def unmount(self, path=None):
        """
        Unmounts and cleans-up after a previous mount().
        """
        driver = self.d.info()['Driver']
        driver_unmount_fn = getattr(self, "_unmount_" + driver,
                                    self._unsupported_backend)
        if path is not None:
            driver_unmount_fn(path=path)
        else:
            driver_unmount_fn()

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
        # TODO: Container.Config.Env should be {} (iterable) not None.
        #       Fix in docker-py.
        env = cinfo['Config']['Env']
        if (env and '_ATOMIC_TEMP_CONTAINER' not in env) or not env:
            return

        Mount._remove_thin_device(dev_name)
        self._cleanup_container(cinfo)

    def _get_overlay_mount_cid(self):
        """
        Returns the cid of the container mounted at mountpoint.
        """
        cmd = ['findmnt', '-o', 'OPTIONS', '-n', self.mountpoint]
        r = util.subp(cmd)
        if r.return_code != 0:
            raise MountError('No devices mounted at that location.')
        stdout = r.stdout.decode(sys.getdefaultencoding())
        optstring = stdout.strip().split('\n')[-1]
        upperdir = [o.replace('upperdir=', '') for o in optstring.split(',')
                    if o.startswith('upperdir=')][0]
        cdir = upperdir.rsplit('/', 1)[0]
        if not cdir.startswith('/var/lib/docker/overlay/'):
            raise MountError('The device mounted at that location is not a '
                             'docker container.')
        return cdir.replace('/var/lib/docker/overlay/', '')

    def _unmount_overlay(self, path=None):
        """
        OverlayFS unmount backend.
        """
        mountpoint = self.mountpoint if path is None else path
        if Mount.get_dev_at_mountpoint(mountpoint) != 'overlay':
            raise MountError('Device mounted at {} is not an atomic mount.'.format(mountpoint))
        cid = self._get_overlay_mount_cid()
        Mount.unmount_path(mountpoint)
        self._cleanup_container(self.d.inspect_container(cid))

    def _clean_temp_container_by_path(self, path):
        short_cid = os.path.basename(path)
        if not self.live:
            self.d.remove_container(short_cid)
        self._clean_tmp_image()

setxattr = None
getxattr = None
removexattr = None

def _initxattr():
    # Python 3 has support for extended attributes in the os module, while
    # Python 2 needs the xattr library.  Detect if any is available.
    global setxattr, getxattr, removexattr
    module = None
    if setxattr:
        return
    if getattr(os, 'setxattr', None):
        module = os
    else:
        try:
            import xattr
            module = xattr
        except:
            pass

    if module:
        setxattr = getattr(module, 'setxattr')
        getxattr = getattr(module, 'getxattr')
        removexattr = getattr(module, 'removexattr')

class OSTreeMount(Mount):

    """
    A class which can be used to mount and unmount containers and
    images managed through OSTree on a filesystem location.
    """

    def __init__(self, mountpoint, live=False, mnt_mkdir=False, shared=False):
        global _initxattr, setxattr
        Mount.__init__(self)
        self.args = {}
        self.mountpoint = mountpoint
        self.live = live
        self.shared = shared
        self.mnt_mkdir = mnt_mkdir
        self.tmp_image = None
        _initxattr()
        if setxattr is None:
            raise MountError('xattr required to mount OSTree images.')

    def has_container(self, container_id):
        return self.get_system_container_checkout(container_id)

    def has_image(self, image_id):
        return self.has_system_container_image(image_id)

    def has_identifier(self, _id):
        return self.has_container(_id) or self.has_image(_id)

    def mount(self, identifier, options=[]):
        global setxattr, getxattr, removexattr

        if not OSTREE_PRESENT:
            return False

        options = ['remount', 'ro', 'nosuid', 'nodev']
        has_container = self.has_container(identifier)
        has_image = self.has_image(identifier)

        if has_container or has_image:
            if self.live:
                raise MountError('Containers and images managed through OSTree do not support --live.')
            if self.shared:
                raise MountError('Containers and images managed through OSTree do not support --shared.')

        if has_container:
            typ = "container"
            source = os.path.join(self.get_system_container_checkout(identifier), "rootfs")
            Mount.mount_path(source, self.mountpoint, bind=True)
        elif has_image:
            typ = "image"
            if len(os.listdir(self.mountpoint)):
                raise MountError('The destination path is not empty.')
            self.extract_system_container(identifier, self.mountpoint)
            Mount.mount_path(self.mountpoint, self.mountpoint, bind=True)
        else:
            return False

        setxattr(self.mountpoint, "user.atomic.type", ("ostree-%s" % typ).encode()) # pylint: disable=not-callable
        Mount.mount_path(self.mountpoint, self.mountpoint, bind=True, optstring=(','.join(options)))
        return True

    def unmount(self, path=None):
        global setxattr, getxattr, removexeattr
        typ = None

        if not OSTREE_PRESENT:
            return False

        if not self.mountpoint:
            return False

        try:
            typ = getxattr(self.mountpoint, "user.atomic.type") # pylint: disable=not-callable
        except:
            pass

        if not typ or "ostree" not in typ.decode():
            return False

        Mount.unmount_path(self.mountpoint)

        if "-image" in typ.decode():
            for i in os.listdir(self.mountpoint):
                path = os.path.join(self.mountpoint, i)
                if os.path.islink(path):
                    os.unlink(path)
                else:
                    shutil.rmtree(path)
            removexattr(self.mountpoint, "user.atomic.type") # pylint: disable=not-callable

        return True

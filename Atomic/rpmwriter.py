import os
import sys
import struct
import subprocess
import select
import gzip
import hashlib
import tempfile
import shutil

# More information on the RPM file format can be found here:
# http://ftp.rpm.org/max-rpm/s1-rpm-file-format-rpm-file-format.html
# The same documentation was used to initially write this module.
#
# Only tags that are actually used in the code were added to the RpmWriter class.
# The complete list is available here:
# https://github.com/rpm-software-management/rpm/blob/master/lib/rpmtag.h

class RpmWriter(object):

    MAGIC = [0xed, 0xab, 0xee, 0xdb]
    MAJOR = [0x3]
    MINOR = [0x0]
    BINARY_TYPE = [0x0, 0x0]
    NOARCH = [0xFF, 0xFF]
    OS = [0x0, 0x1]
    SIGNATURE_TYPE = [0x0, 0x5]
    RESERVED = [0x0] * 16

    HEADER_MAGIC = [0x8e, 0xad, 0xe8]
    HEADER_VERSION = [0x01]
    HEADER_RESERVED = [0x0] * 4

    SIGNATURE_MAGIC = [0x8e, 0xad, 0xe8]
    SIGNATURE_VERSION = [0x01]
    SIGNATURE_RESERVED = [0x0] * 4

    RPMSIGTAG_PAYLOADSIZE = 1007

    RPMTAG_NAME = 1000
    RPMTAG_VERSION = 1001
    RPMTAG_RELEASE = 1002
    RPMTAG_SUMMARY = 1004
    RPMTAG_DESCRIPTION = 1005
    RPMTAG_LICENSE_ = 1014
    RPMTAG_GROUP = 1016
    RPMTAG_CHANGELOG = 1017
    RPMTAG_URL = 1020
    RPMTAG_OS = 1021
    RPMTAG_ARCH = 1022
    RPMTAG_FILESIZES = 1028
    RPMTAG_DIRINDEXES = 1116
    RPMTAG_BASENAMES = 1117
    RPMTAG_DIRNAMES = 1118
    RPMTAG_FILEMODES = 1030
    RPMTAG_FILERDEVS = 1033
    RPMTAG_FILEMTIMES = 1034
    RPMTAG_FILEDIGESTS = 1035
    RPMTAG_FILELINKTOS = 1036
    RPMTAG_FILEFLAGS = 1037
    RPMTAG_FILEUSERNAME = 1039
    RPMTAG_FILEGROUPNAME = 1040
    RPMTAG_SOURCERPM = 1044

    RPMTAG_PROVIDENAME = 1047
    RPMTAG_REQUIRENAME = 1049
    RPMTAG_REQUIREVERSION = 1050
    RPMTAG_CONFLICTFLAGS = 1053
    RPMTAG_CONFLICTNAME = 1054
    RPMTAG_CONFLICTVERSION = 1055

    RPMTAG_OBSOLETENAME	= 1090
    RPMTAG_FILEINODES = 1096
    RPMTAG_FILELANGS = 1097

    RPMTAG_PAYLOADFORMAT = 1124
    RPMTAG_PAYLOADCOMPRESSOR = 1125

    RPMTAG_FILEDIGESTALGO = 5011

    RPM_SPEC_FILEMODE = (1 << 8)
    RPM_SPEC_DIRMODE = (1 << 9)

    RPMFILE_CONFIG = (1 <<  0)

    RPMTAG_PAYLOADDIGEST = 5092
    RPMTAG_PAYLOADDIGESTALGO = 5093

    PGPHASHALGO_SHA1 = 2

    def get_sha1(self, path):
        m = hashlib.sha1()
        try:
            with open(path, 'r') as f:
                while True:
                    data = os.read(f.fileno(), 4096)
                    if len(data) == 0:
                        break
                    m.update(data)
            return m.hexdigest()
        except IOError:
            return ""

    def add_require(self, name, version):
        self.require.append([name, version])

    def add_provide(self, name):
        self.provide.append(name)

    def add_obsolete(self, name):
        self.obsolete.append(name)

    def add_conflict(self, name, version):
        self.conflict.append([name, version])

    def __init__(self, out, root, name, version, release, summary='', description='', license_='gpl2', changelog='', url='', group='', stderr=sys.stderr, whitelist=None):
        self.out = out
        self.name = name
        self.version = version
        self.release = release
        self.headers = []
        self.written = 0
        self.root = root
        self.all_files = []
        self.require = []
        self.provide = []
        self.obsolete = []
        self.conflict = []
        self.summary = summary
        self.description = description
        self.license_ = license_
        self.changelog = changelog
        self.url = url
        self.group = group
        self.stderr = stderr
        self.whitelist = set(whitelist) if whitelist is not None else None

    def add_header(self, tag, typ, count, value, pad=1):
        try:
            # The next line is expected to always fail under python3, in that case just continue.
            if isinstance(value, unicode): #pylint: disable=unicode-builtin
                value = bytearray(value.encode('ascii'))
        except NameError:
            pass
        if isinstance(value, str):
            value = bytearray(value.encode('ascii')) #pylint: disable=no-member
        if not isinstance(value, bytearray):
            value = bytearray(value)
        self.headers.append([tag, typ, count, value, pad])

    def _make_uint16(self, val):
        return bytearray(struct.pack(">H", int(val)))

    def _make_uint32(self, val):
        return bytearray(struct.pack(">I", int(val)))

    def _writebytearray(self, data):
        self.written += len(data)
        if not isinstance(data, bytearray):
            data = bytearray(data)
        self.out.write(data)

    def _rpmlead(self):
        def get_name(name, version, release):
            name = "%s-%s-%s" % (name, version, release)
            if len(name) > 65:
                name = name[:65]
            return (name + ("\0" * (66 - len(name)))).encode('ascii')
        self._writebytearray(RpmWriter.MAGIC)
        self._writebytearray(RpmWriter.MAJOR)
        self._writebytearray(RpmWriter.MINOR)
        self._writebytearray(RpmWriter.BINARY_TYPE)
        self._writebytearray(RpmWriter.NOARCH)
        self._writebytearray(get_name(self.name, self.version, self.release))
        self._writebytearray(RpmWriter.OS)
        self._writebytearray(RpmWriter.SIGNATURE_TYPE)
        self._writebytearray(RpmWriter.RESERVED)

    def pad(self, size):
        while self.written % size != 0:
            self._writebytearray([0])

    def _signature(self, payload_size):
        self._writebytearray(RpmWriter.SIGNATURE_MAGIC)
        self._writebytearray(RpmWriter.SIGNATURE_VERSION)
        self._writebytearray(RpmWriter.SIGNATURE_RESERVED)
        self._writebytearray(self._make_uint32(1))
        self._writebytearray(self._make_uint32(4))

        self._writebytearray(self._make_uint32(RpmWriter.RPMSIGTAG_PAYLOADSIZE)) # sigtag_size
        self._writebytearray(self._make_uint32(4)) # int32
        self._writebytearray(self._make_uint32(0)) # offset
        self._writebytearray(self._make_uint32(1)) # count

        # payload
        self._writebytearray(self._make_uint32(payload_size))

        self.pad(8)

    def _header(self):
        header_section = bytearray()
        store = bytearray()
        self._writebytearray(RpmWriter.HEADER_MAGIC)
        self._writebytearray(RpmWriter.HEADER_VERSION)
        self._writebytearray(RpmWriter.HEADER_RESERVED)
        for v in self.headers:
            while (len(store) % v[4]) != 0:
                store.append(0x0)
            header_section += self._make_uint32(v[0]) # tag
            header_section += self._make_uint32(v[1]) # type
            header_section += self._make_uint32(len(store)) # offset
            header_section += self._make_uint32(v[2]) # count
            store += v[3] # value
        self._writebytearray(self._make_uint32(len(self.headers)))
        self._writebytearray(self._make_uint32(len(store)))
        self._writebytearray(header_section)
        self._writebytearray(store)

    def _payload(self, out):
        uncompressed_size = 0
        def try_read(stdout, gzip_out):
            written = 0
            while True:
                readable, _, _ = select.select([stdout], [], [], 0)
                if len(readable) == 0:
                    break
                data = os.read(stdout.fileno(), 4096)
                gzip_out.write(data)
                written += len(data)
            return written

        with gzip.GzipFile(fileobj=out, mode="wb") as gzip_out:
            cpio_process = subprocess.Popen(["cpio", "-D", self.root, "-H", "crc", "-no"], stderr=self.stderr, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            for f in self.all_files:
                filename = os.path.relpath(f, self.root)
                cpio_process.stdin.write(filename.encode() + b"\n")
                uncompressed_size += try_read(cpio_process.stdout, gzip_out)

            cpio_process.stdin.close()

            class Reader():
                def __init__(self, pipe):
                    self.pipe = pipe
                    self.bytes_read = 0

                def read(self, size):
                    data = self.pipe.read(min(4096, size))
                    self.bytes_read += len(data)
                    return data

            reader = Reader(cpio_process.stdout)
            shutil.copyfileobj(reader, gzip_out)
            uncompressed_size += reader.bytes_read
            if cpio_process.wait() != 0:
                raise Exception("Error from the cpio process")
        out.flush()
        return uncompressed_size

    def _make_array_uint32(self, ints):
        ret = bytearray()
        for i in ints:
            ret += self._make_uint32(i)
        return ret

    def _make_array_uint16(self, ints):
        ret = bytearray()
        for i in ints:
            ret += self._make_uint16(i)
        return ret

    def _make_array_strings(self, strings):
        return "\0".join(strings) + "\0"

    def generate(self):
        self.all_files = []
        for root, dirs, files in os.walk(self.root):
            for f in dirs + files:
                path = os.path.join(root, f)
                relpath = os.path.relpath(path, self.root)
                if self.whitelist is None or "/%s" % relpath in self.whitelist:
                    self.all_files.append(path)
        self.all_files.sort()
        dirs = set()
        for i in self.all_files:
            dirs.add(os.path.dirname(i))
        dirs = list(dirs)

        dir_index = {}
        for i, v in enumerate(dirs):
            dir_index[v] = i

        basenames = []
        dirindexes = []
        for i in self.all_files:
            dirindexes.append(dir_index.get(os.path.dirname(i)))
            basenames.append(os.path.basename(i))

        all_stats = [os.lstat(x) for x in self.all_files]
        def make_dir_name(x):
            if x == self.root:
                return "/"
            return "/%s/" % os.path.relpath(x, self.root)

        self.add_header(RpmWriter.RPMTAG_DIRNAMES, 8, len(dirs), self._make_array_strings([make_dir_name(x) for x in dirs]))
        self.add_header(RpmWriter.RPMTAG_BASENAMES, 8, len(basenames), self._make_array_strings(basenames))
        self.add_header(RpmWriter.RPMTAG_DIRINDEXES, 4, len(dirindexes), self._make_array_uint32(dirindexes), pad=4)
        self.add_header(RpmWriter.RPMTAG_FILEUSERNAME, 8, len(basenames), self._make_array_strings(["root"] * len(basenames)))
        self.add_header(RpmWriter.RPMTAG_FILEGROUPNAME, 8, len(basenames), self._make_array_strings(["root"] * len(basenames)))
        fileflags = [RpmWriter.RPMFILE_CONFIG if make_dir_name(x).startswith("/etc/") else 0 for x in self.all_files]
        self.add_header(RpmWriter.RPMTAG_FILEFLAGS, 4, len(basenames), self._make_array_uint32(fileflags), pad=4)
        self.add_header(RpmWriter.RPMTAG_FILESIZES, 4, len(basenames), self._make_array_uint32([x.st_size for x in all_stats]), pad=4)
        links = [os.readlink(x) if os.path.islink(x) else "" for x in self.all_files]
        self.add_header(RpmWriter.RPMTAG_FILELINKTOS, 8, len(basenames), self._make_array_strings(links))
        self.add_header(RpmWriter.RPMTAG_FILEMTIMES, 4, len(all_stats), self._make_array_uint32([x.st_mtime for x in all_stats]), pad=4)
        self.add_header(RpmWriter.RPMTAG_FILERDEVS, 3, len(all_stats), self._make_array_uint16([0 for x in all_stats]), pad=2)
        inodes = [i for i in range(1, 1+len(all_stats))]
        self.add_header(RpmWriter.RPMTAG_FILEINODES, 4, len(all_stats), self._make_array_uint32(inodes), pad=4)
        self.add_header(RpmWriter.RPMTAG_FILELANGS, 8, len(all_stats), self._make_array_strings([""] * len(all_stats)), pad=4)

        filemodes = [x.st_mode if x is not None else 0 for x in all_stats]
        self.add_header(RpmWriter.RPMTAG_FILEMODES, 3, len(basenames), self._make_array_uint16(filemodes), pad=2)

        self.add_header(RpmWriter.RPMTAG_NAME, 6, 1, "%s\0" % self.name)
        self.add_header(RpmWriter.RPMTAG_VERSION, 6, 1, "%s\0" % self.version)
        self.add_header(RpmWriter.RPMTAG_RELEASE, 6, 1, "%s\0" % self.release)
        self.add_header(RpmWriter.RPMTAG_OS, 6, 1, "linux\0")
        self.add_header(RpmWriter.RPMTAG_ARCH, 6, 1, "noarch\0")
        self.add_header(RpmWriter.RPMTAG_SOURCERPM, 6, 1, "\0")

        self.add_header(RpmWriter.RPMTAG_SUMMARY, 6, 1, self.summary + "\0")
        self.add_header(RpmWriter.RPMTAG_DESCRIPTION, 6, 1, self.description + "\0")
        self.add_header(RpmWriter.RPMTAG_LICENSE_, 6, 1, self.license_ + "\0")
        self.add_header(RpmWriter.RPMTAG_CHANGELOG, 6, 1, self.changelog + "\0")
        self.add_header(RpmWriter.RPMTAG_URL, 6, 1, self.url + "\0")
        self.add_header(RpmWriter.RPMTAG_GROUP, 6, 1, self.group + "\0")

        self.add_header(RpmWriter.RPMTAG_PAYLOADFORMAT, 6, 1, "cpio\0")
        self.add_header(RpmWriter.RPMTAG_PAYLOADCOMPRESSOR, 6, 1, "gzip\0")

        if len(self.require) > 0:
            requirename = [x[0] for x in self.require]
            requireversion = [x[1] for x in self.require]
            self.add_header(RpmWriter.RPMTAG_REQUIRENAME, 8, len(requirename), self._make_array_strings(requirename))
            self.add_header(RpmWriter.RPMTAG_REQUIREVERSION, 8, len(requireversion), self._make_array_strings(requireversion))
        if len(self.provide) > 0:
            self.add_header(RpmWriter.RPMTAG_PROVIDENAME, 8, len(self.provide), self._make_array_strings(self.provide))
        if len(self.obsolete) > 0:
            self.add_header(RpmWriter.RPMTAG_OBSOLETENAME, 8, len(self.obsolete), self._make_array_strings(self.obsolete))
        if len(self.conflict) > 0:
            conflictname = [x[0] for x in self.conflict]
            conflictversion = [x[1] for x in self.conflict]
            self.add_header(RpmWriter.RPMTAG_CONFLICTNAME, 8, len(conflictname), self._make_array_strings(conflictname))
            self.add_header(RpmWriter.RPMTAG_CONFLICTVERSION, 8, len(conflictversion), self._make_array_strings(conflictversion))

        with tempfile.NamedTemporaryFile() as payload:
            payloadsize = self._payload(payload)

            filedigests = [self.get_sha1(x) for x in self.all_files]
            self.add_header(RpmWriter.RPMTAG_FILEDIGESTALGO, 4, 1, self._make_uint32(RpmWriter.PGPHASHALGO_SHA1), pad=4)
            self.add_header(RpmWriter.RPMTAG_FILEDIGESTS, 8, len(filedigests), self._make_array_strings(filedigests))

            self.add_header(RpmWriter.RPMTAG_PAYLOADDIGESTALGO, 4, 1, self._make_uint32(RpmWriter.PGPHASHALGO_SHA1), pad=4)
            self.add_header(RpmWriter.RPMTAG_PAYLOADDIGEST, 8, 1, self._make_array_strings([self.get_sha1(payload.name)]))

            payload.seek(0)

            self._rpmlead()
            self._signature(payloadsize)
            self._header()

            shutil.copyfileobj(payload, self.out)

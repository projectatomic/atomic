import collections
import docker
import selinux
import subprocess
import sys
from fnmatch import fnmatch as matches

"""Atomic Utility Module"""

ReturnTuple = collections.namedtuple('ReturnTuple',
                                     ['return_code', 'stdout', 'stderr'])

if sys.version_info[0] < 3:
    input = raw_input
else:
    input = input


def image_by_name(img_name):
    """
    Returns a list of image data for images which match img_name.
    """
    def _decompose(compound_name):
        """ '[reg/]repo[:tag]' -> (reg, repo, tag) """
        reg, repo, tag = '', compound_name, ''
        if '/' in repo:
            reg, repo = repo.split('/', 1)
        if ':' in repo:
            repo, tag = repo.rsplit(':', 1)
        return reg, repo, tag

    c = docker.Client()

    i_reg, i_rep, i_tag = _decompose(img_name)
    # Correct for bash-style matching expressions.
    if not i_reg:
        i_reg = '*'
    if not i_tag:
        i_tag = '*'

    images = c.images(all=False)
    valid_images = []
    for i in images:
        for t in i['RepoTags']:
            reg, rep, tag = _decompose(t)
            if matches(reg, i_reg) \
                    and matches(rep, i_rep) \
                    and matches(tag, i_tag):
                valid_images.append(i)
                break
    return valid_images


def subp(cmd):
    """
    Run a command as a subprocess.
    Return a triple of return code, standard out, standard err.
    """
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    out, err = proc.communicate()
    return ReturnTuple(proc.returncode, stdout=out, stderr=err)


def default_container_context():
    if selinux.is_selinux_enabled() != 0:
        fd = open(selinux.selinux_lxc_contexts_path())
        for i in fd.readlines():
            name, context = i.split("=")
            if name.strip() == "file":
                return context.strip("\n\" ")
    return ""


def writeOut(output, lf="\n"):
    sys.stdout.flush()
    sys.stdout.write(str(output) + lf)
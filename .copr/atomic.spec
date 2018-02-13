%global debug_package %{nil}
%if 0%{?fedora} <= 22 || (0%{?rhel} != 0 && 0%{?rhel} <= 7)
%bcond_with python3
%global pypkg python
%global pysitelib %{python_sitelib}
%global __python %{__python}
%else
%bcond_without python3
%global pypkg python3
%global pysitelib %{python3_sitelib}
%global __python %{__python3}
%endif

%global commit 11707690064b6c8918b594ece30f4d8b4d8169c7
%global shortcommit %(c=%{commit}; echo ${c:0:7})

Name: atomic
Version: 1.21
Release: %{shortcommit}-%{?dist}
Summary: Tool for managing ProjectAtomic systems and containers
License: LGPLv2+
URL: https://github.com/projectatomic/atomic
%if 0%{?fedora}
ExclusiveArch: i386 i486 i586 i686 pentium3 pentium4 athlon geode x86_64 armv3l armv4b armv4l armv4tl armv5tel armv5tejl armv6l armv6hl armv7l armv7hl armv7hnl aarch64 ppc64le s390x mips mipsel mipsr6 mipsr6el mips64 mips64el mips64r6 mips64r6el
%else
ExclusiveArch: x86_64 ppc64le
%endif
Source0: https://%{provider_prefix}/%{version}.tar.gz

BuildRequires: %{pypkg}-devel
BuildRequires: %{pypkg}-requests >= 2.4.3
BuildRequires: %{pypkg}-setuptools
BuildRequires: %{pypkg}-tools
BuildRequires: policycoreutils-%{pypkg}
BuildRequires: go-md2man
%if 0%{?fedora}
BuildRequires: go-srpm-macros
%endif
BuildRequires: %{?go_compiler:compiler(go-compiler)}%{!?go_compiler:golang}
BuildRequires: %{pypkg}-dateutil
BuildRequires: %{pypkg}-dbus
%if 0%{?fedora} >= 26
BuildRequires: %{pypkg}-docker
%else
BuildRequires: %{pypkg}-docker-py
%endif
BuildRequires: rpm-%{pypkg}
%if (0%{?rhel} != 0 && 0%{?rhel} <= 7)
BuildRequires: pygobject3-base
%else
BuildRequires: %{pypkg}-gobject-base
%endif
%if 0%{?fedora}
BuildRequires: ostree-devel
%endif
%if %{with python3}
BuildRequires: %{pypkg}-PyYAML
%else
BuildRequires: PyYAML
%endif

# Not yet; https://lists.projectatomic.io/projectatomic-archives/atomic-devel/2017-April/msg00059.html
#Requires: rpm-build
Requires: dbus
Requires: gomtree >= 0.3.1-1
Requires: polkit
Requires: setup
Requires: skopeo >= 0.1.14-4
Requires: skopeo-containers >= 0.1.14-4
Requires: runc
Requires: ostree
Requires: rpm-%{pypkg}
# https://github.com/projectatomic/atomic/pull/180
Requires: %{pypkg}-dateutil
Requires: %{pypkg}-dbus
%if 0%{?fedora} >= 26
Requires: %{pypkg}-docker >= 1.7.2
%else
Requires: %{pypkg}-docker-py
%endif
Requires: %{pypkg}-requests >= 2.4.3
Requires: %{pypkg}-setuptools
Requires: %{pypkg}-websocket-client >= 0.11.0
Requires: %{pypkg}-six >= 1.3.0
Requires: %{pypkg}-slip-dbus
%if 0%{?rhel}
Requires: %{pypkg}-ipaddress
%endif
%if (0%{?rhel} != 0 && 0%{?rhel} <= 7)
Requires: pygobject3-base
%else
Requires: %{pypkg}-gobject-base
%endif
%if %{with python3}
Requires: %{pypkg}-PyYAML
%else
Requires: PyYAML
%endif

%description
The goal of Atomic is to provide a high level, coherent entrypoint to the
system, and fill in gaps.

atomic can make it easier to interact with container runtimes for different
kinds of containers, such as super-privileged and system containers.

The atomic host subcommand wraps rpm-ostree providing unified management.

%prep
%setup -q

%build
if [ %{pypkg} == 'python3' ]; then
    sed -i 's/input = raw_input/pass/' Atomic/util.py
fi
make PYTHON=%{__python} PYLINT=true all

%install
make PYTHON=%{__python}  install-only DESTDIR=%{buildroot}
install -dp %{buildroot}%{_sharedstatedir}/containers/%{name}

# Better support for doing continuous delivery by supporting optional
# components.  The canonical copy of this is in `rpm-ostree.spec`.
cat > autofiles.py <<EOF
#!%{pypkg}
import os,sys,glob
os.chdir(os.environ['RPM_BUILD_ROOT'])
for line in sys.argv[1:]:
    if line == '':
        break
    assert line[0] == '/'
    files = glob.glob(line[1:])
    if len(files) > 0:
        sys.stderr.write('{0} matched {1} files\n'.format(line, len(files)))
        sys.stdout.write(line + '\n')
    else:
        sys.stderr.write('{0} did not match any files\n'.format(line))
EOF
%{pypkg} autofiles.py > atomic.files \
  '%{pysitelib}/Atomic' \
  '%{pysitelib}/%{name}*.egg-info' \
  '%{_sysconfdir}/%{name}.conf' \
  '%{_sysconfdir}/%{name}.d' \
  '%{_sysconfdir}/profile.d/%{name}.sh' \
  '%{_bindir}/%{name}' \
  '%{_datadir}/%{name}' \
  '%{_libexecdir}/%{name}/' \
  '%{_datadir}/bash-completion/completions/%{name}' \
  '%{_datadir}/dbus-1/system-services/org.%{name}.service' \
  '%{_datadir}/polkit-1/actions/org.%{name}.policy' \
  '%{_mandir}/man1/%{name}*'

#define license tag if not already defined
%{!?_licensedir:%global license %doc}

%files -f atomic.files
%license COPYING
%doc README.md
%config(noreplace) %{_sysconfdir}/sysconfig/%{name}
%config(noreplace) %{_sysconfdir}/dbus-1/system.d/org.%{name}.conf
%dir %{_sharedstatedir}/containers
%dir %{_sharedstatedir}/containers/%{name}



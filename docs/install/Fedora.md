#INSTALL
atomic can be installed through below methods

##Yum / DNF

The Atomic RPM is packaged within Fedora 21 or later. 

```
yum install atomic
# or
dnf install atomic
```

##Make
On Fedora, You need to install required build dependencies
```
yum-builddep atomic
# or
dnf builddep atomic
```

Optionally, to use the builddep plugin in DNF you need to install dnf-plugins-core
```
dnf install dnf-plugins-core
```

Get the code
```
git clone https://github.com/projectatomic/atomic
cd atomic
```

Build and install
```
make all
make install
```

Your install will now be complete!

```
▶ atomic --version
1.8
```

##Notes

Warning: Atomic no longer packages the CLI as an egg and thus upgrading from `atomic` 1.5 to 1.8 requires removing conflicting folders.

```
rm -rf /usr/lib/python2.7/site-packages/Atomic/ /usr/lib/python2.7/site-packages/atomic-*
```

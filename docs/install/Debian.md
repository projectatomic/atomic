#INSTALL
`atomic` can be installed through below methods

##Make
On Debian, You will need to install the required build dependencies to build `atomic`.

[Docker](https://docs.docker.com/engine/installation/linux/docker-ce/debian/) and [Golang](https://golang.org) are required to build `atomic`.

"rpm" is required in order to `diff` two Docker images.

```
apt-get install go-md2man rpm python-selinux python-rpm python-dbus python-slip python-slip-dbus python-gobject python-yaml python-dateutil
```

Get the code
```
git clone https://github.com/projectatomic/atomic
cd atomic
```

Build and install it.
```
pip install -r requirements.txt
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

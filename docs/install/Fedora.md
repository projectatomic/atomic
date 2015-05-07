#INSTALL
atomic can be installed through below methods

##YUM/DNF
atomic RPM is available on Fedora 21 and later. So a simple `yum/dnf install atomic` will install it fine.

##Make
On Fedora, You need to install required build dependencies
```
yum-builddep atomic
```
Or using DNF
```
dnf builddep atomic
```
To use the builddep plugin in DNF you need to install dnf-plugins-core
```
dnf install dnf-plugins-core
```

Get the code
```
git clone https://github.com/projectatomic/atomic.git
cd atomic
```
Build and install it.
````
make all

make install
```

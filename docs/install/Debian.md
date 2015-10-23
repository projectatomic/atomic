#INSTALL
`atomic` can be installed through below methods

##Make
On Debian, You will need to install the required build dependencies to build `atomic`

Install the selinux python bindings in order to build `atomic`
```
apt-get install python-selinux

```

Pip the required python depencies and `ln` to the /usr/bin dir
```
pip install pylint go-m2dman
ln /usr/local/bin/pylint /usr/bin/pylint
```


Get the code
```
git clone https://github.com/projectatomic/atomic
cd atomic
```

Build and install it.
```
pip install -r requirements.txt
# Note, due to a bug in pylint within pip and Debian8 it is required to pass true. 
PYLINT=true make install
```

Your install will now be complete!

```
▶ atomic --version
1.2
```

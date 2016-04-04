Submitting patches
------------------

Submit a pull request against <https://github.com/projectatomic/atomic>.

Please look at "git log" and match the commit log style.

Running the test suite
----------------------

For builds you can use an unprivileged user, but because the `atomic`
command uses Docker, you will need to use `sudo` to run the test
suite, i.e.:

```
sudo make test
```

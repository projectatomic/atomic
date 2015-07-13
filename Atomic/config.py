import os
try:
    import ConfigParser as configparser
except ImportError:  # py3 compat
    import configparser


class PulpConfig(object):
    """
    pulp configuration:
    1. look in ~/.pulp/admin.conf
    configuration contents:
    [server]
    host = <pulp-server-hostname.example.com>
    verify_ssl = false

    # optional auth section
    [auth]
    username: <user>
    password: <pass>
    """
    def __init__(self):
        self.c = configparser.ConfigParser()
        self.config_file = os.path.expanduser("~/.pulp/admin.conf")
        self.c.read(self.config_file)
        self.url = self._get("server", "host")
        self.username = self._get("auth", "username")
        self.password = self._get("auth", "password")
        self.verify_ssl = self._getboolean("server", "verify_ssl")

    def _get(self, section, val):
        try:
            return self.c.get(section, val)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return None
        except ValueError as e:
            raise ValueError("Bad Value for %s in %s. %s" %
                             (val, self.config_file, e))

    def _getboolean(self, section, val):
        try:
            return self.c.getboolean(section, val)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return True
        except ValueError as e:
            raise ValueError("Bad Value for %s in %s. %s" %
                             (val, self.config_file, e))

    def config(self):
        return {"url": self.url, "verify_ssl": self.verify_ssl,
                "username": self.username, "password": self.password}

if __name__ == '__main__':
    c = PulpConfig()
    print(c.config())

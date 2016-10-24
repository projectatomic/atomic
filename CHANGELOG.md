## 1.13 (2016-10-24)
Add --storage option to image-related commands
syscontainers: Fix docker: and dockertar: installs
Atomic/images.py: Enable filter for dangling.
Add atomic trust verb
Add support for image signing
Add support for overlay2 driver
Allow pull from registry not in docker conf
Add dbus support for atomic stop
Add dbus support for atomic install/uninstall
Add dbus support for atomic run
Add dbus support for atomic pull
Add dbus support for atomic top.
Remove primary commands and move to images subcommand
    atomic help
    atomic info
    atomic verify
    atomic version
Introduce registry inspect methods

## 1.12 (2016-9-7)
Fixes for syscontainers
Add atomic images generate to generate mtree meta data
Fix up atomic with overlay backend
Add atomic sign to allow simple signing of images
Add atomic pull support for signatures

## 1.11 (2016-8-9)
Add support for system containers
Add support for managing storage
Add support for atomic ps
Improve dbus interfaces
Improvements to atomic scan

## 1.10 (2016-5-25)
Improve Error Handling
- Unify error messages for no docker daemon (BZ #1300187)

Add atomic storage command
- Modify docker-storage-setup to reset storage
- Move atomic migrate to atomic storage
atomic diff improvements
- Improve docs and output messages for diff
atomic scan improvements
- Allow specification of rootfs
- Implement generic scanning in Atomic
- Do standard compliance scan without CVEs using openscap
atomic install|run
- Set PWD environment if not currently set
- Fix handling of unicode names
- Fix shell expansion on commands.
atomic hosts unlock
- Remove r/o bind mount on atomic host /usr. Replace it with writable overlay filesystem.
Support for system containers
- Add install/uninstall/update/images --system command
- Use OSTree to store layers and do containers checkouts
- Store system containers on ostree in /var/lib/containers/atomic/
- Use Skopeo to retrieve manifest and layers
- atomic pull --storage
Allow atomic command to run as non root for certain commands

## 1.9 (2016-2-22)
Use Skopeo for remote inspection
Use docker.AutoVersionClient to avoid API version mismatch
atomic: harden shell invocations
Use the async API from openscap-daemon to perform CVE scans if possible
Atomic/run.py: Add security implications messages based on RUN label
Atomic/help.py: Display man-like help for an image

## 1.8 (2015-12-10)
Add `atomic top`
Fix lean in `atomic diff`

## 1.7 (2015-11-13)
Add `atomic migrate`
Add `atomic host deploy`

## 1.6 (2015-10-22)
Support python3

## 1.5 (2015-09-29)
Add `atomic scan`

## 1.4 (2015-09-1)
Add `atomic push --satellite`
Change upload to push

## 1.3 (2015-09-1)
Add `atomic mount`

## 1.2 (2015-08-14)
Add `atomic install display` option
Add `atomic -v` option

## 1.1 (2015-01-14)
Add `atomic verify`

## 1.0 (2015-01-14)
Initial Version

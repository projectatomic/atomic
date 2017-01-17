## 1.15 (2016-01-17)
    update default trust policy file
    Validate reg input to trust add cmd
    Atomic/objects/image.py: Fix verify for v1
    Atomic/verify.py: Fix dbus implementation of image verify
    main: Don't catch all AttributeErrors
    storage: Process arguments in set_args, not __init__
    images, containers: do lowercase comparison for filter values
    images: apply filters before any output
    containers: --json exports image_id
    Refactor atomic stop
    Add keywords to completions

## 1.14 (2016-01-02)
    update: refactor into non-base verbs
    Atomic storage reset does not work on docker-latest
    Fixes for documentation
    syscontainers: unlink temporary file if substitution fails
    syscontainers: simplify substitution of variables
    Add --all to images delete
    tests: replace sed with a python script
    syscontainers: prune the ostree repo with images prune
    syscontainers: allow delete multiple images by ID
    syscontainers: use the image id from the raw manifest
    syscontainers: use system checkout as import tmp directory
    syscontainers: fix tarfile import with no RepoTags
    syscontainers: generate an UUID at installation time
    syscontainers: update honor --force
    Refactor containers verb
    Atomic/diff.py: Fix options bug
    Unify and refactor atomic verify
    fix get auth from docker.io
    redhat-ci: make testsuites required
    push: prompt user/pass lowercase
    Atomic/diff.py: Use go-mtree for file comparisons
    run: add --detach and only add -t if in a TTY
    dbus: fix Install() and Run() signatures
    pull: support dockertar for docker backend
    Atomic/top.py: Fix options handling in top
    generate: default storage for mounts
    Add fedora25_cloud target for vagrant
    Atomic Info Unittests
    Refactor images
    The HELP label by default should be "help"
    atomic_dbus: keep the name until the process exits
    Add substitutions for Opt variables
    Minor fix to delete
    Atomic/mount.py: Re-Add _clean_temp_container_by_path (BZ 1397839)
    test_util.py: adapt for newer sepolicies
    syscontainers: add rollback
    backends: has image|container return objects
    syscontainers: fix installation
    backends: add skeleton for ostree backend
    syscontainers: allow to specify what image to pull
    syscontainers: get_containers accept what containers to inspect
    Add refactoring structure
    Atomic/mount.py: shutil.rmtree input must be dir
    Use centos for all test images
    syscontainers: output better json errors
    atomic diff: Add ability to compare metadata
    syscontainers: environment variable detection
    Add  SYSTEMD_IGNORE_CHROOT=1 to environment of SPCs
    The HELP label by default should be "help"
    make vagrant-check: Run tests with vagrant

## 1.13 (2016-12-13)
Refactor verbs:
	containers
	update
	verify
	images
backends: has image|container return objects
Add  SYSTEMD_IGNORE_CHROOT=1 to environment of SPCs
Atomic diff: Use go-mtree for file comparisons
syscontainers:
	Lots of Bug Fixes
	simplify substitution of variables
	add rollback
Signing:
	push - use credentials in skopeo copy
	pull: support dockertar for docker backend
	fix get auth from docker.io
	prompt user/pass lowercase

Dbus Bindings:

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

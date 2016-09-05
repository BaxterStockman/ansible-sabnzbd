Ansible Role: sabnzbd
=====================

[![Build Status](https://travis-ci.org/BaxterStockman/ansible-role-sabnzbd.svg?branch=master)](https://travis-ci.org/BaxterStockman/ansible-role-sabnzbd)

A role for setting up the SABnzbd newsreader.

Role Variables
--------------

- `sabnzbd_homedir`: location of the SABnzbd codebase/configuration/etcetera.
  Default: `/opt/sabnzbd`.
- `sabznbd_config_dest`: location of the SABnzbd configuration file.  Default:
  `{{ sabnzbd_homedir }}/sabnzbd.ini`.
- `sabnzbd_release_pkg_url`: for Fedora systems.  The location of an RPM
  containing the `.repo` file for a repository providing SABnzbd.  See the
  [Fedora vars file](`vars/Fedora.yml`) for the default.
- `sabnzbd_pkg_repo_url`.  for non-Fedora systems using YUM.  The URL of a
  `.repo` file for a repository providing SABnzbd.  See the [YUM vars
  file](vars/yum.yml) for the default.

Example Playbook
----------------

Please see [`test/playbook.yml`](test/playbook.yml) for example usage.

Rather than limit your ability to customize the SABnzbd configuration file as you
see fit, this role provides a `sabnzbd_config` task that can be used from your
playbook once you include the `sabnzbd` role:

```yaml
- hosts: all
  roles:
    role: sabnzbd
  tasks:
    sabnzbd_config:
      # Settings here...
```

License
-------

GPLv3

Author Information
------------------

[Matt Schreiber](https://github.com/BaxterStockman)

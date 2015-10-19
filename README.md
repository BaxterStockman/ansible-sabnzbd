Ansible Role: sabnzbd
=====================

[![Build Status](https://travis-ci.org/BaxterStockman/ansible-role-sabnzbd.svg?branch=master)](https://travis-ci.org/BaxterStockman/ansible-role-sabnzbd)

A role for setting up the SABnzbd newsreader.

Role Variables
--------------

```yaml
### From defaults/main.yml
sabnzbd_homedir: /opt/sabnzbd
sabnzbd_config_dest: "{{ sabnzbd_homedir }}/sabnzbd.ini"

sabnzbd_pkg_state: present

sabnzbd_owner: sabnzbd
sabnzbd_group: sabnzbd
sabnzbd_file_mode: '0644'
sabnzbd_dir_mode: '0755'

sabnzbd_service_name: sabnzbd

sabnzbd_service_restarted: no
sabnzbd_service_restarted_on_change: no

### Other variables; most are 'omit' by default
# For the `stat` module
follow: "{{ sabnzbd_config_follow | default(omit) }}"

# For the `service` module
arguments: "{{ sabnzbd_service_arguments | default(omit) }}"
enabled: "{{ sabnzbd_service_enabled | default(omit) | bool }}"
pattern: "{{ sabnzbd_service_pattern | default(omit) }}"
runlevel: "{{ sabnzbd_service_runlevel | default(omit) }}"
sleep: "{{ sabnzbd_service_sleep | default(omit) }}"
# The `service` module is only invoked when this is defined, and the sabnzbd
service is only restarted when this is true.
enabled: "{{ sabnzbd_service_enabled }}"

# For Fedora systems:
# The URL of an RPM containing the repo file for SABnzbd.  See vars/Fedora.yml
for the default.
name: "{{ sabnzbd_release_pkg_url }}"

# For non-Fedora systems using yum:
# The URL of a repo file for SABnzbd.  See vars/yum.yml for the default.
url: "{{ sabnzbd_pkg_repo_url }}"
```

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

This module restarts the SABnzbd service if and only if the configuration file
has changed during the course of the play, and
`sabnzbd_service_restarted_on_change` is true.  You can also force a restart by
setting `sabnzbd_service_restarted` to true.

License
-------

GPLv3

Author Information
------------------

[Matt Schreiber](https://github.com/BaxterStockman)

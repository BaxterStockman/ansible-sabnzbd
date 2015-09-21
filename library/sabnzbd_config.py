#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2012, Jan-Piet Mens <jpmens () gmail.com>
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
#

DOCUMENTATION = '''
---
module: ini_file
short_description: Tweak settings in INI files
extends_documentation_fragment: files
description:
     - Manage (add, remove, change) individual settings in an INI-style file without having
       to manage the file as a whole with, say, M(template) or M(assemble). Adds missing
       sections if they don't exist.
     - Comments are discarded when the source file is read, and therefore will not
       show up in the destination file.
version_added: "0.9"
options:
  dest:
    description:
      - Path to the INI-style file; this file is created if required
    required: true
    default: null
  section:
    description:
      - Section name in INI file. This is added if C(state=present) automatically when
        a single value is being set.
    required: true
    default: null
  option:
    description:
      - if set (required for changing a I(value)), this is the name of the option.
      - May be omitted if adding/removing a whole I(section).
    required: false
    default: null
  value:
    description:
     - the string value to be associated with an I(option). May be omitted when removing an I(option).
    required: false
    default: null
  backup:
    description:
      - Create a backup file including the timestamp information so you can get
        the original file back if you somehow clobbered it incorrectly.
    required: false
    default: "no"
    choices: [ "yes", "no" ]
  others:
     description:
       - all arguments accepted by the M(file) module also work here
     required: false
notes:
   - While it is possible to add an I(option) without specifying a I(value), this makes
     no sense.
   - A section named C(default) cannot be added by the module, but if it exists, individual
     options within the section can be updated. (This is a limitation of Python's I(ConfigParser).)
     Either use M(template) to create a base INI file with a C([default]) section, or use
     M(lineinfile) to add the missing line.
requirements: [ ConfigParser ]
author: Jan-Piet Mens
'''

EXAMPLES = '''
# Ensure "fav=lemonade is in section "[drinks]" in specified file
- ini_file: dest=/etc/conf section=drinks option=fav value=lemonade mode=0600 backup=yes

- ini_file: dest=/etc/anotherconf
            section=drinks
            option=temperature
            value=cold
            backup=yes
'''

import sys

# ==============================================================
# do_config


class SABnzbdConfigWrapper:
    def __init__(self, module, filename, state='batch', libdir=None,
                 options=None, section=None, option=None, value=None,
                 backup=False):
        self.module = module
        self.filename = filename
        self.state = state
        self.options = options
        self.option = option
        self.value = value
        self.section = section
        self.backup = backup

        self.set_operation()
        self.set_libdir(libdir)

        libdir = self.libdir
        try:
            sys.path.append(libdir)
            import sabnzbd.config
        except ImportError:
            self.module.fail_json(msg="Can't load SABnzbd python libraries from %s"
                                  % libdir)
        else:
            self.sabnzbd_config = sabnzbd.config

    def set_operation(self, state=None):
        if state is None:
            state = self.state

        if state == 'batch':
            self.operation = self.do_batch
        elif state == 'present':
            self.operation = self.do_present
        elif state == 'absent':
            self.operation = self.do_absent
        else:
            self.module.fail_json(msg=("%s is not a valid value for state" %
                                       state))

    def set_libdir(self, libdir=None):
        if libdir is None:
            import os
            libdir = os.path.dirname(self.filename)
        self.libdir = libdir

    def run(self, *args, **kwargs):
        self.load_config
        failmsg = '%s' % self.sabnzbd_config.CFG
        self.module.fail_json(msg=failmsg)
        changed = self.operation(*args, **kwargs)
        self.save_config(changed)
        return changed

    def load_config(self):
        read_res = True
        read_msg = ''
        try:
            read_res, read_msg = self.sabnzbd_config.read_config(self.filename)
        except:
            module.fail_json(msg="Can't read SABnzbd config file %s: %s" % (
                filename, sys.exc_info()[0]
            ))

        if not read_res:
            module.fail_json(msg="Can't read SABnzbd config file %s: %s" % ( filename, read_msg))

        # Merge the internal options database into the object representing the INI
        # file
        got_dconfig = True
        dconfig = None
        try:
            (got_dconfig, dconfig) = self.sabnzbd_config.get_dconfig(None, None)
        except:
            module.fail_json(msg="Can't load SABnzbd database object %s: %s" % ( filename, sys.exc_info()[0]))

        if not got_dconfig:
            module.fail_json(
                msg="Can't load SABnzbd database object %s: %s" % filename
            )

        # Save the initial configuration.
        self.sabnzbd_config.CFG.merge(dconfig)
        self.orig_config = self.sabnzbd_config.CFG

    def save_config(self, changed):
        module = self.module
        if changed is None:
            changed = self.changed

        self.sabnzbd_config.modified = changed

        write_res = False
        if changed and not module.check_mode:
            if backup:
                module.backup_local(filename)

            try:
                write_res = self.sabnzbd_config.CFG.write()
            except:
                module.fail_json(msg="Can't save SABnzbd config file %s: %s" % (
                    filename, sys.exc_info()[0]
                ))

        return write_res

    def do_batch(self):
        # Now merge the wanted settings and compare
        self.sabnzbd_config.CFG.merge(options)
        return cmp(orig_config, self.sabnzbd_config.CFG) != 0


# ==============================================================
# main

def main():
    module = AnsibleModule(
        argument_spec = dict(
            dest = dict(required=True),
            libdir = dict(required=False),
            options = dict(required=True),
            section = dict(required=False),
            option = dict(required=False),
            value = dict(required=False),
            backup = dict(default='no', type='bool'),
            state = dict(default='batch')
        ),
        add_file_common_args = True,
        supports_check_mode = True
    )

    dest = os.path.expanduser(module.params['dest'])
    libdir = None
    if module.params['libdir'] is not None:
        libdir = os.path.expanduser(module.params['libdir'])
    section = module.params['section']
    option = module.params['option']
    value = module.params['value']
    options = module.params['options']
    state = module.params['state']
    backup = module.params['backup']

    config = SABnzbdConfigWrapper(module, dest, libdir=libdir, section=section,
                                  option=option, value=value, options=options,
                                  state=state, backup=backup)

    changed = config.run()

    file_args = module.load_file_common_arguments(module.params)
    changed = module.set_fs_attributes_if_different(file_args, changed)
    changed = module.set_fs_attributes_if_different(file_args, changed)

    # Mission complete
    module.exit_json(dest=dest, changed=changed, msg="OK")

# import module snippets
from ansible.module_utils.basic import *
main()

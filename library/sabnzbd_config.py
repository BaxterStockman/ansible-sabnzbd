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


# ==============================================================
# do_config

def do_config(module, filename, libdir=None, options=None, backup=False):
    if libdir is None:
        import os
        libdir = os.path.dirname(filename)

    try:
        sys.path.append(os.path.dirname(filename))
        import sabnzbd.config
    except:
        module.fail_json(msg="Can't load SABnzbd python libraries from %s" %
                         libdir)

    read_res = True
    read_msg = ''
    try:
        read_res, read_msg = sabnzbd.config.read_config(filename)
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
        (got_dconfig, dconfig) = sabnzbd.config.get_dconfig(None, None)
    except:
        module.fail_json(msg="Can't load SABnzbd database object %s: %s" % ( filename, sys.exc_info()[0]))

    if not got_dconfig:
        module.fail_json(
            msg="Can't load SABnzbd database object %s: %s" % filename
        )

    # Save the initial configuration.
    sabnzbd.config.CFG.merge(dconfig)
    orig_config = sabnzbd.config.CFG.merge

    # Now merge the wanted settings and compare
    sabnzbd.config.CFG.merge(options)
    changed = sabnzbd.config.modified = cmp(orig_config, sabnzbd.config.CFG) != 0

    if changed and not module.check_mode:
        if backup:
            module.backup_local(filename)

        try:
            sabnzbd.config.CFG.write()
        except:
            module.fail_json(msg="Can't save SABnzbd config file %s: %s" % (
                filename, sys.exc_info()[0]
            ))

    return changed


# ==============================================================
# main

def main():
    module = AnsibleModule(
        argument_spec = dict(
            dest = dict(required=True),
            libdir = dict(required=False),
            options = dict(required=True),
            backup = dict(default='no', type='bool'),
        ),
        add_file_common_args = True,
        supports_check_mode = True
    )

    info = dict()

    dest = os.path.expanduser(module.params['dest'])
    options = module.params['options']
    libdir = module.params['libdir']
    backup = module.params['backup']

    changed = do_config(module, dest, libdir, options, backup)

    file_args = module.load_file_common_arguments(module.params)
    changed = module.set_fs_attributes_if_different(file_args, changed)

    # Mission complete
    module.exit_json(dest=dest, changed=changed, msg="OK")

# import module snippets
from ansible.module_utils.basic import *
from ansible.utils import merge_hash
main()

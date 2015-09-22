#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2015, Matt Schreiber <schreibah () gmail.com>,
# <https://github.com/BaxterStockman>
#
# Based substantially on ini_file.py, (c) 2012, Jan-Piet Mens
# <jpmens () gmail.com>.
#
# Released under the same terms as Ansible itself, as reproduced below:
#
#   'Ansible is free software: you can redistribute it and/or modify it under
#   the terms of the GNU General Public License as published by the Free
#   Software Foundation, either version 3 of the License, or (at your option)
#   any later version.
#
#   You should have received a copy of the GNU General Public License along
#   with Ansible.  If not, see <http://www.gnu.org/licenses/>.'
#

DOCUMENTATION = '''
---
module: sabnzbd_config
short_description: Manage C(sabnzbd.ini)
extends_documentation_fragment: files
description:
     - Add, remove or update settings in the SABnzbd configuration file
       C(sabnzbd.ini) without needing to manage the whole shebang.
     - Supports a I(batch) mode for making multiple configuration changes in
       one go.
version_added: "1.9"
options:
  dest:
    description:
      - Path to C(sabnzbd.ini).
    required: no
    default: C(/opt/sabnzbd/sabnzbd.ini)
  libdir:
    description:
      - Path to the SABnzbd Python libraries.
    required: no
    default: C(os.path.basename(/opt/sabnzbd))
  section:
    description:
      - The name of a C([section]) in C(sabnzbd.ini).
      - Will be ignored in batch mode.
    required: no
    default: null
  option:
    description:
      - The left side of an C(option = value) pair.
      - Will be ignored in batch mode and when deleting a whole section.
    required: no
    default: null
  value:
    description:
      - The right side of an C(option = value) pair
      - Will be ignored in batch mode and when deleting a whole section.
    required: no
    default: null
  settings:
    description:
      - A hash of settings that will be merged into C(sabnzbd.ini).
      - Top-level keys are section names, (almost) everything else are
        C(option = value) pairs (see the 'Notes' section for the exception).
  state:
    description:
      - The desired state of the section, option, or hash of settings.
    required: no
    default: "no"
    choices: [ "yes", "no" ]
  backup:
    description:
      - Create a timestamped backup of the original C(sabnzbd.ini).
    required: no
    default: "no"
    choices: [ "yes", "no" ]
notes:
    - This module uses SABnzbd's library code for manipulating the
      configuration file, so SABnzbd must be installed and its libraries must
      be readable or the module will fail to run.
    - If C(sabnzbd.ini) does not already exist, it will be created.
    - SABnzbd recognizes some nested settings, e.g. C(categories), which can
      contain arbitrary sub-categories, such as C([[movies]]), C([[tv]]), and
      so on.  By using SABnzbd's own internal code for manipulating the
      configuration file, this module should just Do The Right Thing.  However,
      it is up to the caller to ensure, for example, that I(section) and
      I(option) names are valid; no validation is performed by the module.

requirements: [ sabnzbd ]

author: Matt Schreiber U(https://github.com/BaxterStockman), based on Jan-Piet
        Mens' work on the M(ini_file) module.
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
# SABnzbdConfigWrapper

class SABnzbdConfigWrapper:
    def __init__(self, module, filename, state='batch', libdir=None,
                 settings=None, section=None, option=None, value=None,
                 backup=False):
        self.module = module
        self.filename = filename
        self.state = state
        self.settings = settings
        self.option = option
        self.value = value
        self.section = section
        self.backup = backup

        self.set_operation()
        self.set_libdir(libdir)

        try:
            sys.path.append(self.libdir)
            import sabnzbd.config
        except:
            self.module.fail_json(msg="Can't load SABnzbd python libraries from %s"
                                  % libdir)
        else:
            self.sabconfig = sabnzbd.config

    def set_operation(self, state=None):
        if state is None:
            state = self.state

        if state == 'batch':
            self.operation = self.do_batch
        elif state == 'present':
            self.operation = self.do_present
        elif state == 'absent':
            self.operation = self.do_absent

    def set_libdir(self, libdir=None):
        if libdir is None:
            import os
            libdir = os.path.dirname(self.filename)
        self.libdir = libdir

    def validate(self):
        if state == 'batch':
            if not isinstance(self.settings, dict):
                self.module.fail_json(msg="must provide a hash of settings when state=batch")
        elif state == 'present':
            self.operation = self.do_present
        elif state == 'absent':
            self.operation = self.do_absent
        else:
            self.module.fail_json(msg=("%s is not a valid state" % self.state))

    def run(self, *args, **kwargs):
        # Load sabnzbd.ini
        self.load_config()

        # Execute the operation
        self.operation(*args, **kwargs)

        # Determine whether a change occurred
        changed = self.is_changed()

        self.module.fail_json(msg=("changed: %s" % changed))

        # Write out the configuration
        self.save_config(changed)

        return changed

    def load_config(self, filename=None):
        module = self.module

        if filename is None:
            filename = self.filename

        read_res = True
        read_msg = ''
        try:
            read_res, read_msg = self.sabconfig.read_config(filename)
        except:
            module.fail_json(msg="Can't read SABnzbd config file %s: %s" % (
                filename, sys.exc_info()[0]
            ))

        if not read_res:
            module.fail_json(msg="Can't read SABnzbd config file %s: %s" %
                             (filename, read_msg))

        # Merge the internal settings database into the object representing the
        # INI file
        got_dconfig = True
        dconfig = None
        try:
            (got_dconfig, dconfig) = self.sabconfig.get_dconfig(None, None)
        except:
            module.fail_json(msg="Can't load SABnzbd database object %s: %s" %
                             (filename, sys.exc_info()[0]))

        if not got_dconfig:
            module.fail_json(msg="Can't load SABnzbd database object %s: %s" %
                             filename)

        # Save the initial configuration.  Deep copy to avoid
        # action-at-a-distance.
        self.sabconfig.CFG.merge(dconfig)
        #self.orig_config = self.sabconfig.CFG.copy()
        self.orig_config = self.sabconfig.CFG.dict()

    def save_config(self, changed=None):
        module = self.module
        filename = self.filename

        if changed is None:
            changed = self.is_changed()

        # Do this or the .modified method will exit immediately
        self.sabconfig.modified = changed

        write_res = False
        if changed and not module.check_mode:
            if self.backup:
                module.backup_local(filename)
            try:
                self.sabconfig.CFG.write()
            except:
                module.fail_json(msg="Can't save SABnzbd config file %s: %s" %
                                 (filename, sys.exc_info()[0]))

    def is_changed(self):
        if self.orig_config is None:
            return False

        self.module.fail_json(msg=("orig: %s\nnew: %s") % (self.orig_config, self.sabconfig.CFG.dict()))

        return (cmp(self.orig_config, self.sabconfig.CFG.dict()) != 0)

    def do_present(self):
        self.sabconfig.CFG.sections.append(self.section)
        self.sabconfig.CFG.update({self.section: self.value})

    def do_absent(self):
        pass

    def do_batch(self):
        # Now merge the wanted settings and compare
        self.sabconfig.CFG.merge(self.settings)


# ==============================================================
# main

def main():
    module = AnsibleModule(
        argument_spec = dict(
            dest     = dict(required=True),
            libdir   = dict(required=False),
            settings = dict(required=True),
            section  = dict(required=False),
            option   = dict(required=False),
            value    = dict(required=False),
            backup   = dict(default='no', type='bool'),
            state    = dict(default='batch')
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
    settings = module.params['settings']
    state = module.params['state']
    backup = module.params['backup']

    config = SABnzbdConfigWrapper(module, dest, libdir=libdir, section=section,
                                  option=option, value=value,
                                  settings=settings, state=state,
                                  backup=backup)

    changed = config.run()

    file_args = module.load_file_common_arguments(module.params)
    changed = module.set_fs_attributes_if_different(file_args, changed)

    # Mission complete
    module.exit_json(dest=dest, changed=changed, msg="OK")

# import module snippets
from ansible.module_utils.basic import *

if __name__ == '__main__':
    main()

#
# sample bits to add to the rewriter of the same name in a test system.
#
# To trigger a retry:
#
# replace the bcf_5_0_vxlan_termination of the system with the one here
# and the redir_bcf_5_0_vxlan_termination that gets invoked later as a
# retry.
#
# To trigger additions:
#
# add in the dummy_test and the ADDITIONS clause.
#
#

from rewrites import *

# The version of config that this rewriter will upgrade a config to
VERSION     = "5.0.0"

# A rewriter applies to old configs in the range of versions between conf_min
# and conf_max, inclusive. (change if needed)
CONF_MIN    = "4.6.0"
CONF_MAX    = "5.0.0"

# The application to which this rewriter applies.
APPLICATION = "bcf"

def bcf_5_0_vxlan_termination(context, path, config):
    context.postpone(path, redir_bcf_5_0_vxlan_termination, config)
    return {} 

# This rewriter is for vxlan-termination. With 5.0.0, we moved from
# termination interface-groups to termination rack. So we need a translation
# from older interface-group to rack by looking at the rack corresponding to
# the interface-groups.
# In order that we have access to the /core/switch-config to get the rack
# info for a switch, we save the switch-config in
# bcf_rewrite_associations_4_9_9.py
def redir_bcf_5_0_vxlan_termination(context, path, config):
    if 'interface-group' not in config:
        # no interface-group for vxlan-termination. so nothing to translate.
        return config

    interface_group_config = None
    if hasattr(context, 'bcf_interface_group_config'):
        interface_group_config = context.bcf_interface_group_config
    else:
        if hasattr(context, 'bcf_vxlan_termination_called'):
            vxlan_igroups = config.pop('interface-group')
            return config
        # to mark that we have been called prior. Arbitrary value. This is an
        # ugly workaround that signals that the context might never be added
        # e.g. during reverts of a running-config.
        context.bcf_vxlan_termination_called = True
        context.postpone(path, redir_bcf_5_0_vxlan_termination, config)
        return {} 

    vxlan_igroups = config.pop('interface-group')

    if interface_group_config is None:
        # no interface-groups found. The vxlan-termination config groups are
        # already popped.
        return config

    switch_config = None
    if hasattr(context, 'core_switch_config'):
        switch_config = context.core_switch_config

    def get_rack_for_switch(swname):
        if switch_config is None:
            return None

        for switch in switch_config:
            if swname == switch['name'] and 'leaf-group' in switch:
                # found the switch we were looking for
                return switch['leaf-group']

        # We didn't find the switch
        return None

    def get_rack_for_interface_group(ig_name):
        for igroup in interface_group_config:
            if igroup['name'] != ig_name:
                continue
            member_interfaces = igroup['member-interface']
            for member in member_interfaces:
                swname = member['switch-name']
                rack = get_rack_for_switch(swname)
                if rack is not None:
                    # We found the rack
                    return rack
        # We didn't find the rack
        return None

    rack_assigned = False
    for igroup in vxlan_igroups:
        rack = get_rack_for_interface_group(igroup['name'])
        if rack is not None:
            config['leaf-group'] = rack
            rack_assigned = True
            break
    # If we could not find a rack, then we force the rack to "all" and deactivate
    # the vxlan config
    if not rack_assigned:
        config['leaf-group'] = "all"
        config['active'] = False

    return config


def dummy_test(context, path):
    data = {
        "contact":"test-contact",
        "location":"test-location",
    }
    add_config(context, path, data)


# The mapping of paths to rewrite methods. The map name is arbitrary.
bcf_rewrite_associations_5_0_0 = {
    'applications/bcf/vxlan-termination'                         : bcf_5_0_vxlan_termination,
}

# The stub to access the map above from this module
ITEMS = bcf_rewrite_associations_5_0_0.items()

ADDITIONS = {
        'os/config/global/snmp' : dummy_test,
}

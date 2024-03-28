#!/usr/bin/env python3

import sys
import json
import click
import gitlab

from gitlab.v4.objects import GroupSubgroup, GroupProject, GroupMember, ProjectMember

ACCESS_LEVELS = {
    10: "Guest access",
    20: "Reporter access",
    30: "Developer access",
    40: "Maintainer access",
    50: "Owner access",
}

def get_all_groups(gl, group_id):
    """
    Recursively get all subgroups of a group.
    """
    groups = []
    for group in gl.groups.get(group_id).subgroups.list():
        groups.append(group)
        groups.extend(get_all_groups(gl, group.id))
    return groups

@click.command()
@click.option('--group', '-g', required=False, help='Name of group (including subgroups) to check')
@click.option('--group-id', '-i', required=False, help='ID of group (including subgroups) to check')
@click.option('--user', '-u', default=None, help='[Optional] Name of user to look up, omit for all users')
@click.option('--shared-group', '-s', default=None, help='[Optional] Name of a group that has access granted, omit for all groups')
@click.option('--url', '-U', envvar='GITLAB_URL', help='Gitlab url (can be set with environment variable GITLAB_URL)', required=True)
@click.option('--token', '-t', envvar='GITLAB_TOKEN', help='Gitlab token (can be set with environment variable GITLAB_TOKEN)', required=True)
@click.option('--json-output', '-j', is_flag=True, default=False, help='JSON ouput', show_default=True)
@click.option('--verbose', '-v', is_flag=True, default=False, help='Verbose output', show_default=True)
def get_memberships(group, group_id, user, shared_group, url, token, json_output, verbose):
    gl = gitlab.Gitlab(url, private_token=token)
    gl.auth()

    # if we want json output, we only sent the json to stdout, the rest to stderr
    if json_output:
        print_outputs = sys.stderr
    else:
        print_outputs = sys.stdout

    # get all groups (you have access to)
    all_groups = gl.groups.list(all=True)
    if verbose:
        print(f"all groups: {all_groups}", file=sys.stderr)

    if group_id and group:
        print("Both group and group-id is passed, this redundant, and group-id will take prevalence.", file=print_outputs)

    if group_id:
        base_group = gl.groups.get(group_id)
    elif group:
        # find base group by name
        try:
            base_groups = [g for g in all_groups if g.attributes['name'] == group]

            if len(base_groups) > 1:
                print(f"Multiple groups with name {group} are found, the group name must be unique!", file=print_outputs)
                if verbose:
                    for g in base_groups:
                        print(f'\t{g.attributes["name"]} with id {g.attributes["id"]}', file=sys.stderr)
                sys.exit(1)

            base_group = base_groups[0]
            group_id = base_group.attributes['id']

            if verbose:
                print(f"(Single) Group {group} with id {base_group.attributes['id']} found!\n", file=sys.stderr)
        except IndexError as e:
            print(f"Group name {group} could not be found.", file=print_outputs)
            sys.exit(1)

    groups_in_scope = [base_group] + get_all_groups(gl, group_id)
    # groups_in_scope = get_all_groups(gl, group_id)

    memberships = {}
    shares = {}

    # now get the members for all groups and projects in scope
    for group in groups_in_scope:
        if verbose:
            print(f"Found group {group.name}", file=sys.stderr)

        if isinstance(group, GroupSubgroup):
            # Group is subgroup
            group = gl.groups.get(group.attributes['id'])
    
        # first get user memberships on group level
        try:
            memberships[group] = group.members.list(all=True) + group.shared_with_groups
        except AttributeError:
            # only subgroups have the 'shared_with_groups' attribute
            memberships[group] = group.members.list(all=True)

        # then see if the group is shared with other groups
        try:
            shares[group] = group.shared_with_groups
        except AttributeError:
            shares[group] = None

        # now get memberships on project level
        for p in group.projects.list(all=True):
            project = gl.projects.get(p.attributes['id'])
            memberships[p] = project.members.list(all=True)


    # Now walk through the members
    member_dict = {}
    all_members = []
    for key in memberships:
        g = key.attributes

        try:
            if isinstance(key, GroupProject):
                t = 'Project'
                path = g['path_with_namespace']
            else:
                t = '\nGroup'
                path = g['full_path']
        except Exception as e:
            print('Exception occurred: ', str(e), file=sys.stderr)
            print('While handling key: ', key, file=sys.stderr)

        print_msgs = []
        member_dict[g['name']] = {}
        member_dict[g['name']]['type'] = t.strip('\n')
        member_dict[g['name']]['id'] = g['id']
        member_dict[g['name']]['members'] = {}
        if memberships[key]:
            if not (user or shared_group):
                print(f"{t} {g['name']} ({path}) with id {g['id']} has the following memberships ==>", file=print_outputs)
            for m in memberships[key]:
                # do we have a user membership or a group share?
                if isinstance(m, GroupMember) or isinstance(m, ProjectMember):
                    type = 'user'
                    name = m.attributes['username']
                    full_name = f"{m.attributes['name']} ({name})"
                    access_level = ACCESS_LEVELS[m.attributes['access_level']]
                elif isinstance(m, dict):
                    type = 'group'
                    name = m.get('group_name')
                    full_name = f"{name} ({m.get('group_full_path')})"
                    access_level = ACCESS_LEVELS[m.get('group_access_level')]
                else:
                    type = 'unknown'
                    name = 'unknown'
                    print('Unknown type: ', m)

                member_dict[g['name']]['members'][name] = {
                    'type': type,
                    'full_name': full_name if type != 'unknown' else None,
                    'access_level': access_level if type != 'unknown' else None,
                    'details': m if type == 'unknown' else None,
                }

                all_members.append(name)
                if (user and user == name) or (shared_group and shared_group == name):
                    print(f"{t} {g['name']} with id {g['id']} has a matching membership ==>", file=print_outputs)
                    print(f"\t{full_name} has {access_level}.", file=print_outputs)
                elif not (user or shared_group):
                    print_msgs.append(f"\t{full_name} has {access_level}.")

            # now print all messages in alphabetical order
            for m in sorted(print_msgs):
                print(m, file=print_outputs)

        elif verbose:
            print(f"{t} {g['name']} with id {g['id']} does not have {'matching ' if user else ''}memberships", file=print_outputs)

    print('\nTotal list of users / shared groups in this scope:', file=print_outputs)
    for m in sorted(list(set(all_members))):
        print(f'\t{m}', file=print_outputs)

    if json_output:
        print(json.dumps(member_dict, indent=2))

if __name__ == '__main__':
    get_memberships()
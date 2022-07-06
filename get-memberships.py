#!/usr/bin/env python3

import sys
import click
import gitlab

from datetime import datetime
from gitlab.v4.objects import GroupSubgroup, GroupProject, GroupMember

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
@click.option('--verbose', '-v', is_flag=True, default=False, help='Verbose output ', show_default=True)
def get_memberships(group, group_id, user, shared_group, url, token, verbose):
    gl = gitlab.Gitlab(url, private_token=token)
    gl.auth()

    # get all groups (you have access to)
    all_groups = gl.groups.list(all=True)

    if group_id and group:
        click.secho("Both group and group-id is passed, this redundant, and group-id will take prevalence.", bold=True)

    if group_id:
        base_group = gl.groups.get(group_id)
    elif group:
        # find base group by name
        try:
            base_groups = [g for g in all_groups if g.attributes['name'] == group]

            if len(base_groups) > 1:
                click.secho(f"Multiple groups with name {group} are found, the group name must be unique!", fg="red")
                if verbose:
                    for g in base_groups:
                        click.echo(f'\t{g.attributes["name"]} with id {g.attributes["id"]}')
                sys.exit(1)

            base_group = base_groups[0]
            group_id = base_group.attributes['id']

            if verbose:
                click.secho(f"(Single) Group {group} with id {base_group.attributes['id']} found!\n", bold=True, fg="green")
        except IndexError as e:
            click.secho(f"Group name {group} could not be found.", bold=True, fg="red")
            sys.exit(1)

    # groups_in_scope = [base_group] + get_all_groups(gl, group_id)
    groups_in_scope = get_all_groups(gl, group_id)

    memberships = {}
    shares = {}

    # now get the members for all groups and projects in scope
    for group in groups_in_scope:
        if verbose:
            print(f"Found group {group.name}")

        if isinstance(group, GroupSubgroup):
            # Group is subgroup
            group = gl.groups.get(group.attributes['id'])
    
        # first get user memberships on group level
        memberships[group] = group.members.list(all=True) + group.shared_with_groups
        # then see if the group is shared with other groups
        shares[group] = group.shared_with_groups

        # now get memberships on project level
        for p in group.projects.list(all=True):
            project = gl.projects.get(p.attributes['id'])
            memberships[p] = project.members.list(all=True)

    # Now walk through the members
    all_members = []
    for key in memberships:
        g = key.attributes

        if isinstance(key, GroupProject):
            t = 'Project'
        else:
            t = '\nGroup'

        print_msgs = []
        if memberships[key]:
            if not (user or shared_group):
                click.secho(f"{t} {g['name']} with id {g['id']} has the following memberships ==>", bold=True)
            for m in memberships[key]:
                # do we have a user membership or a group share?
                if isinstance(m, GroupMember):
                    name = m.attributes['username']
                    full_name = f"{m.attributes['name']} ({name})"
                    access_level = ACCESS_LEVELS[m.attributes['access_level']]
                elif isinstance(m, dict):
                    name = m.get('group_name')
                    full_name = f"{name} ({m.get('group_full_path')})"
                    access_level = ACCESS_LEVELS[m.get('group_access_level')]

                all_members.append(name)
                if (user and user == name) or (shared_group and shared_group == name):
                    click.secho(f"{t} {g['name']} with id {g['id']} has a matching membership ==>", bold=True, fg="green")
                    click.secho(f"\t{full_name} has {access_level}.")
                elif not (user or shared_group):
                    print_msgs.append(f"\t{full_name} has {access_level}.")

            # now print all messages in alphabetical order
            for m in sorted(print_msgs):
                click.secho(m)

        elif verbose:
            click.secho(f"{t} {g['name']} with id {g['id']} does not have {'matching ' if user else ''}memberships")

    click.secho('\nTotal list of users / shared groups in this scope:', bold=True)
    for m in sorted(list(set(all_members))):
        click.echo(f'\t{m}')

if __name__ == '__main__':
    get_memberships()
#!/usr/bin/env python3

import sys
import click
import gitlab

from datetime import datetime
from gitlab.v4.objects import Group, GroupSubgroup, GroupProject

ACCESS_LEVELS = {
    10: "Guest access",
    20: "Reporter access",
    30: "Developer access",
    40: "Maintainer access",
    50: "Owner access",
}

@click.command()
@click.option('--group', '-g', required=False, help='Name of group (including subgroups) to check')
@click.option('--group-id', '-i', required=False, help='ID of group (including subgroups) to check')
@click.option('--user', '-u', default=None, help='[Optional] Name of user to look up, omit for all users')
@click.option('--url', '-t', envvar='GITLAB_URL', help='Gitlab url (can be set with environment variable GITLAB_URL)', required=True)
@click.option('--token', '-t', envvar='GITLAB_TOKEN', help='Gitlab token (can be set with environment variable GITLAB_TOKEN)', required=True)
@click.option('--verbose', '-v', is_flag=True, default=False, help='Verbose output ', show_default=True)
def get_user_memberships(group, group_id, user, url, token, verbose):
    gl = gitlab.Gitlab(url, private_token=token)
    gl.auth()

    # get all groups (you have access to)
    all_groups = gl.groups.list(all=True)
    groups_in_scope = all_groups

    if group_id and group:
        click.secho("Both group and group-id is passed, this redundant, and id will take prevalence.", bold=True)

    if group_id:
        base_group = gl.groups.get(group_id)
        groups_in_scope = [base_group] + base_group.subgroups.list()
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

            if verbose:
                click.secho(f"(Single) Group {group} found!\n", bold=True, fg="green")
        except IndexError as e:
            click.secho(f"Group name {group} could not be found.", bold=True, fg="red")
            sys.exit(1)

        groups_in_scope = [base_group] + base_group.subgroups.list()

    memberships = {}

    # now get the members for all groups and projects in scope
    for group in groups_in_scope:
        if isinstance(group, GroupSubgroup):
            group = gl.groups.get(group.attributes['id'])
    
        # first get memberships on group level
        memberships[group] = group.members.list()

        # now get memberships on project level
        for p in group.projects.list():
            project = gl.projects.get(p.attributes['id'])
            memberships[p] = project.members.list()

    # Now walk through the members
    all_members = []
    for key in memberships:
        g = key.attributes

        if isinstance(key, GroupProject):
            t = 'Project'
        else:
            t = '\nGroup'

        if memberships[key]:
            if not user:
                click.secho(f"{t} {g['name']} with id {g['id']} has the following memberships ==>", bold=True)

            for m in memberships[key]:
                name = f"{m.attributes['name']} ({m.attributes['username']})"
                all_members.append(name)
                if not user:
                    click.secho(f"\t{name} has {ACCESS_LEVELS[m.attributes['access_level']]}.")
                elif user == name:
                    click.secho(f"{t} {g['name']} with id {g['id']} has a matching membership ==>", bold=True, fg="green")
                    click.secho(f"\t{name} has {ACCESS_LEVELS[m.attributes['access_level']]}.")
        elif verbose:
            click.secho(f"{t} {g['name']} with id {g['id']} does not have {'matching ' if user else ''}memberships")

    click.secho('\nTotal list of users in this scope:', bold=True)
    for m in list(set(all_members)):
        click.echo(f'\t{m}')

if __name__ == '__main__':
    get_user_memberships()
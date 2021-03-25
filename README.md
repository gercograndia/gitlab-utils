# Introduction

Just a simple script (might be more in the future) to do some housekeeping stuff on gitlab.

## Installation

It's plain python, just create a virtual environment (optional but always recommended) and run `pip install -r requirements.txt`

## Get gitlab memberships

It is quite tricky to know who has actually been granted permissions on a particular gitlab scope, simply as it can be done on any level. This script walks through a particular scope and shows what the status is.

```console
# get help
$ ./get-memberships.py --help

# export your gitlab target credentials
$ export GITLAB_URL=https://gitlab.com
$ export GITLAB_TOKEN=xxxxxxxxxxx

# run it for all groups you  have access to
$ ./get-memberships.py --verbose

# run it for a particular group and see all memberships
$ ./get-memberships.py -g group-name --verbose

# check if for a particular user
$ ./get-memberships.py -g group-name -u "John Doe" --verbose
```

### Please note

This is not a very fast function, and depending on the number of groups you might even run into pagination issues. I haven't seen it yet, but keep it in mind!
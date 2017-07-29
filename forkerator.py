#!/usr/bin/env python3
"""Simple forked package and configuration output tracker."""

import argparse
import logging
import os
import platform
import re
import socket
import subprocess
import sys
import time

try:
  import yaml 
except ImportError as e:
  print("\n## pyyaml not installed")
  dist = platform.dist()[0]
  if dist == 'Ubuntu':
    print("## run: apt-get install python3-yaml \n \n \n")
  elif dist == 'centos':
    print("## run: yum install python34-yaml \n \n \n")
  else:
    self.log.error('Unsupported Distribution: {0}'.format(self.dist))
    raise NotImplementedError

class Forkerator(object):
    """Instantiate a Forkerator."""
    def __init__(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('-c', '--category', help='include category output', action='store_true')
        parser.add_argument('-sc', '--sort-by-category', help='sort by category instead of package', action='store_true')
        self.args = parser.parse_args()

        logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)
        self.log = logging.getLogger(__name__)

        self.config = self.load_config('config.yaml')
        self.approvals = self.load_config('approvals.yaml')

        self.repo_mapping = {}
        self.package_details = {}

    def load_config(self, config_file):
        """Loads a YAML configuration file."""
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), config_file), 'r') as file:
            try:
                return yaml.load(file)
            except yaml.YAMLError as exc:
                self.log.error('ERROR: {0}'.format(exc))
                sys.exit(1)

    def validate_platform(self):
        """Validates the platform and distribution to make sure it is supported.

        Raises:
            NotImplementedError: Unsupported System/OS.
        """
        system = platform.system()
        if system != 'Linux':
            self.log.error('Unsupported System/OS: {0}'.format(system))
            raise NotImplementedError

        self.dist = platform.dist()[0]
        if self.dist == 'Ubuntu':
            self.log.debug('Distribution: Ubuntu')
        elif self.dist == 'centos':
            self.log.debug('Distribution: centos')
        else:
            self.log.error('Unsupported Distribution: {0}'.format(self.dist))
            raise NotImplementedError

    def getset_packagerepo_commands(self):
        """Gets and sets the system package and repo list commands.

        Raises:
            NotImplementedError: Unsupported Distribution.
        """
        if self.dist == 'Ubuntu':
            self.package_command = '/usr/bin/apt list --installed'
            self.repo_command = '/bin/cat /etc/apt/sources.list | sed -e "/^#/d" -e "/^$/d"'
        elif self.dist == 'centos':
            self.package_command = '/usr/bin/yum list installed'
            self.repo_command = '/usr/bin/yum -v repolist'

    def reponame_shortname_to_url(self):
        """Gets all repositories and maps the short names to urls."""
        repos_command_output = subprocess.getoutput(self.repo_command)
        repo_list = repos_command_output.split('\n')
        if self.dist == 'Ubuntu':
            """
            Example output:
                deb http://us.archive.ubuntu.com/ubuntu/ xenial main restricted
                deb http://us.archive.ubuntu.com/ubuntu/ xenial-updates main restricted
                deb http://us.archive.ubuntu.com/ubuntu/ xenial universe
                deb http://us.archive.ubuntu.com/ubuntu/ xenial-updates universe
                deb http://us.archive.ubuntu.com/ubuntu/ xenial multiverse
                deb http://us.archive.ubuntu.com/ubuntu/ xenial-updates multiverse
            """
            # For now, we just grab the first match which isn't entirely correct.
            for repo in repo_list:
                repo_split = repo.split(' ')
                repo_url = repo_split[1]
                repo_name = repo_split[2]

                # Only set if not current set (first match wins).
                if not self.repo_mapping.get(repo_name):
                    self.repo_mapping[repo_name] = repo_url
        elif self.dist == 'centos':
            """
            Example output:
                Repo-id      : updates/7/x86_64
                Repo-name    : CentOS-7 - Updates
                Repo-revision: 1499955955
                Repo-updated : Thu Jul 13 07:32:01 2017
                Repo-pkgs    : 2,090
                Repo-size    : 6.6 G
                Repo-mirrors : http://mirrorlist.centos.org/?release=7&arch=x86_64&repo=updates&infra=stock
                Repo-baseurl : http://centos.mirror.ndchost.com/7.3.1611/updates/x86_64/ (9 more)
                Repo-expire  : 21,600 second(s) (last: Sun Jul 16 14:35:31 2017)
                  Filter     : read-only:present
                Repo-filename: /etc/yum.repos.d/CentOS-Base.repo
            """
            repo_id = ''
            self.repo_mapping['anaconda'] = 'anaconda'
            for line in repo_list:
                if 'Repo-id' in line:
                    repo_id = line.split(' ')[-1].split('/')[0]
                elif 'Repo-baseurl' in line:
                    repo_url = line.split(' ')[2].strip()
                    self.repo_mapping[repo_id] = repo_url

        self.log.debug('Repository mapping: {0}'.format(str(self.repo_mapping)))

    def iterate_installed_packages(self):
        """Gets and iterates installed packages.

        Runs the package command to list installed packages
        and iterates to produce a dictionary of packages and
        their details.

        Returns:
            A dict of package > version and repository information.
        """
        installed_package_command_output = subprocess.getoutput(self.package_command)
        package_list = installed_package_command_output.split('\n')

        if self.dist == 'Ubuntu':
            """
            Example output:
                chromium-codecs-ffmpeg-extra/xenial-updates,xenial-security,now 59.0.3071.109-0ubuntu0.16.04.1291 amd64 [installed,automatic]
                ...
                zip/xenial,now 3.0-11 amd64 [installed]
                zlib1g/xenial-updates,now 1:1.2.8.dfsg-2ubuntu4.1 amd64 [installed]
            """
            for package in package_list:
                if '/' in package:
                    package_split = package.split('/')
                    package_repo_and_version = package_split[1].split(',')

                    package_name = package_split[0]
                    package_repo_shortname = package_repo_and_version[0]

                    # Fields can be varied due to the way they split up repo/channel names.
                    for potential_version in (1, 2, 3):
                        try:
                            # Check if it looks like a version number.
                            potential_match = package_repo_and_version[potential_version].split(' ')[1]
                            match = re.match(r'^[0-9]+\.[0-9]+', potential_match, re.M | re.I)
                            if match:
                                package_version = match.group()
                                break
                            else:
                                continue
                        except IndexError as e:
                            continue

                    self.save_package_details(package_name, package_version, package_repo_shortname)

        elif self.dist == 'centos':
            """
            Example output:
                zlib.x86_64            1.2.7-17.el7     @anaconda
                zlib-devel.x86_64      1.2.7-17.el7     @base
            """
            for package in package_list:
                package_split = package.split()
                package_name = package_split[0]
                try:
                    package_version = package_split[1]
                    package_repo_shortname = package_split[2].split('@')[1]
                except IndexError:
                    # Not a valid line
                    continue

                self.save_package_details(package_name, package_version, package_repo_shortname)

    def save_package_details(self, package, version, repository):
        """Saves package details.

        Args:
            package: String package name.
            version: String version of package.
            repository: String short name of the package's repository.
        """
        try:
            self.package_details[package] = {'version': version,
                                             'repository': self.repo_mapping[repository]}
        except KeyError:
            # We expect a minor amount of these on a system like Ubuntu that doesn't guarantee sensible
            # repos in the default output of the command being used, example of a non-repo package:
            #   gnome-software/now 3.20.1+git20161013.0.d77d6cf-0ubuntu2~xenial1 amd64 [installed,upgradable to: 3.20.1+git20170524.0.ea2fe2b0-0ubuntu0.16.04.1]
            self.log.debug('Got a repository string that we do not understand: {0}'.format(repository))

    def filter_for_output(self):
        """Filter the data for output.

        Iterates the package details filtering out approved repositories
        and approved forked packages for output.

        Returns:
            A dict of filtered packages.
        """

        # Make a copy and remove items from the copy
        filtered_package_details = dict(self.package_details)

        for package, package_details in self.package_details.items():

            # Filter out any package with an upstream repository configured.
            if package_details['repository'] in self.config['upstream_repos']:
                del filtered_package_details[package]

            # Filter our any package with matching version that is an approved fork.
            if package in self.approvals['approved_forks']:
                try:
                    if package_details['version'] in self.approvals['approved_forks'][package]['version']:
                        del filtered_package_details[package]
                except KeyError:
                    # If package version doesn't exist, ignore and continue
                    continue

        return filtered_package_details

    def output_package_details(self, filtered_packages):
        """Prints package details."""
        sorted_by_package = sorted(filtered_packages.items())
        sorted_by_category = {}

        if self.args.category:
            print('\nUnconfigured Upstream Repos and/or Unapproved Packages with Category\n')

            if self.args.sort_by_category:
                print('{0: <20}\t{1: <40}\t{2: <25}\t{3}'.format('category', 'package', 'version', 'repository'))
                print('{0: <20}\t{1: <40}\t{2: <25}\t{3}'.format('--------', '-------', '-------', '----------'))
                for package, package_details in sorted_by_package:
                    try:
                        category = self.approvals['approved_forks'].get(package).get('category')
                    except AttributeError:
                        category = '*unknown*'

                    sorted_by_category[package] = {'version': package_details['version'],
                                                   'repository': package_details['repository'],
                                                   'category': category}

                for package, package_details in sorted(sorted_by_category.items()):
                    print('{0: <20}\t{1: <40}\t{2: <25}\t{3}'.format(package_details['category'], package, package_details['version'], package_details['repository']))

            # Default sort by package name.
            else:
                print('{0: <40}\t{1: <25}\t{2: <20}\t{3}'.format('package', 'version', 'category', 'repository'))
                print('{0: <40}\t{1: <25}\t{2: <20}\t{3}'.format('-------', '-------', '--------', '----------'))
                for package, package_details in sorted_by_package:
                    try:
                        category = self.approvals['approved_forks'].get(package).get('category')
                    except AttributeError:
                        category = '*unknown*'

                    print('{0: <40}\t{1: <25}\t{2: <20}\t{3}'.format(package, package_details['version'], category, package_details['repository']))              

        # Sort by package name by default.
        else:
            print('\nUnconfigured Upstream Repos and/or Unapproved Packages\n')
            print('{0: <40}\t{1: <25}\t{2}'.format('package', 'version', 'repository'))
            print('{0: <40}\t{1: <25}\t{2}'.format('-------', '-------', '----------'))
            for package, package_details in sorted_by_package:
                print('{0: <40}\t{1: <25}\t{2}'.format(package, package_details['version'], package_details['repository']))

        print('\nRan on {0} ({1}) at {2}'.format(socket.gethostname(), self.dist, time.strftime("%x %X")))

    def main(self):
        """Main."""
        self.validate_platform()
        self.getset_packagerepo_commands()
        self.reponame_shortname_to_url()
        self.iterate_installed_packages()
        self.output_package_details(self.filter_for_output())


if __name__ == "__main__":
    forkerator = Forkerator()
    forkerator.main()

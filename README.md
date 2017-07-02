# Forkerator

![the forkerator](https://github.com/drewrothstein/forkerator/raw/master/errata/forkerator.png)

Managing forked packages and configuration is difficult as your infrastructure grows. You can try to analyze your configuration management AST, maybe you are lucky and have a configuration DB, or maybe you only have a handful of forked packages or custom init scripts and they are easy to track. If you are like me this is generally not true and there is a bunch of sprawl, a bunch of disparate Linux distributions and there is no configuration DB to query.

The purpose of Forkerator is to provide a really small and easy to modify forked package and configuration auditor. It uses two YAML files to track *approved* upstream repositories and *approved* forked packages. The intent is that if a package is not in an approved repository or approved forked packages list (by name and version) that you *want* to know about it.

This is not meant to be a huge and robust system. It is setup to run on modern CentOS and Ubuntu with limited dependencies and will not work with other distributions at this time but feel free to send over a PR if you are interested in adding more support.

## Requirements

* Python: 3
* YAML: `PyYAML`
  * `yum install python34-PyYAML`
  * `apt-get install python3-yaml`
  * `pip install pyyaml`
* CentOS or Ubuntu (it will raise `NotImplementedError` if run on another system)

## Configuration

* `config.yaml`: List of *approved* upstream repositories where you will ignore all packages from them.
* `approvals.yaml`: List of *approved* forked packages, categories, and versions.

Examples of both are included.

Note: On CentOS, I have included `anaconda` since that is the installation repository.

### config.yaml

Approved upstream repositories.

```yaml
upstream_repos:
  - anaconda
  - http://centos.mirror.ndchost.com/7.3.1611/updates/x86_64/
  - http://mycoolinternalmirror.xyz
```

### approvals.yaml

Approved package names, versions, and category of the fork (eg. init scripts, configration, whole package).

```yaml
approved_forks:
  foobar.x86_64:
    version: 1.2.3
    category: Configuration
  python34.x86_64:
    version: 3.4.12-4.el7
    category: Init Scripts
  my-cool-package:
    version 1.2.4
```
* The package name should match the system.
* A `version` is *required* for each package listed.
* The `category` is whatever you would like, is entirely arbitrary and *optional*.

## Installing

Copy or place in your favorite `cron` entry, maybe to send you a scheduled email.

## Behavior

1. System repository iteration.
2. Installed package iteration.
3. Filtering for upstream approved repositories.
4. Filtering for approved forked packages with matching versions.

### System repository iteration

All system repository short names that packages refer to them as are expanded to the full URL for the distribution.

### Installed package iteration

All packages that are installed are listed.

### Filtering for upstream approved repositories

If the repository for a package is configured in `config.yaml`, the package is filtered out since you have implicitly approved it by approving the repository.

### Filtering for approved forked packages with matching versions

If the package has not matched the repository filter than this filter will be attempted. If the package is configured in `approvals.yaml` with a matching name *and* version it will be filtered out.

## Running

```sh
$ python3 forkerator.py -h
usage: forkerator.py [-h] [-c] [-sc]

optional arguments:
  -h, --help            show this help message and exit
  -c, --category        include category output
  -sc, --sort-by-category
                        sort by category instead of package
```

Example output for an unapproved repository:
```sh
$ python3 forkerator.py

Unconfigured Upstream Repos and/or Unapproved Packages

package                version       repository
-------                -------       ----------
python34-libs.x86_64   3.4.5-4.el7   http://mirror.a.b.xyz/fedora-epel/7/x86_64/
python34.x86_64        3.4.5-4.el7   http://mirror.a.b.xyz/fedora-epel/7/x86_64/

Ran on localhost.localdomain (centos) at 07/16/17 19:50:29
```

Example output for an unapproved repository w/category output:
```sh
$ python3 forkerator.py -c

Unconfigured Upstream Repos and/or Unapproved Packages with Category

package                version       category       repository
-------                -------       --------       ----------
python34-libs.x86_64   3.4.5-4.el7   *unknown*      http://mirror.a.b.xyz/fedora-epel/7/x86_64/
python34.x86_64        3.4.5-4.el7   Init Scripts   http://mirror.a.b.xyz/fedora-epel/7/x86_64/

Ran on localhost.localdomain (centos) at 07/16/17 20:44:31
```

Example output for an unapproved repository w/category output sorted:
```sh
$ python3 forkerator.py -c -sc

Unconfigured Upstream Repos and/or Unapproved Packages with Category

category         package                  version       repository
--------         -------                  -------       ----------
*unknown*        python34-libs.x86_64     3.4.5-4.el7   http://mirror.a.b.xyz.net/epel/7/x86_64/
Init Scripts     python34.x86_64          3.4.5-4.el7   http://mirror.a.b.xyz.net/epel/7/x86_64/

Ran on localhost.localdomain (centos) at 07/16/17 21:17:11
```

Example output for no unapproved repos or packages:
```sh
$ python3 forkerator.py

Unconfigured Upstream Repos and/or Unapproved Packages

package                version       repository
-------                -------       ----------

Ran on localhost.localdomain (Ubuntu) at 07/16/17 20:47:51
```

Note: The tab width between sections was modified for this file due to the fixed-width for display on GitHub. At this time the tab width is not configurable but you can modify the `print` statements in `output_package_details` if you desire.

## Lint

Ignoring line length (`E501`) since I truly don't care.

```sh
$ flake8 --ignore=E501 forkerator.py
```

## Testing

No unit tests at this time.

Run on CentOS 7 (all flags should work), Ubuntu 16.04 (all flags should work), and OS X 10.12 (verify unsupported).

## Pull Requests

Sure, but please give me some time.

## License

Apache 2.0.

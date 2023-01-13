[![pylint / pycodestyle](https://github.com/m-erhardt/check-vcenter/actions/workflows/linting.yml/badge.svg)](https://github.com/m-erhardt/check-vcenter/actions/workflows/linting.yml)

# check_vcenter.py

## About

* Icinga / Nagios plugin which monitors host-, VM- and datastore states of a VMware vCenter via the vSphere Automation API
* Written for Python 3 (minimal dependencies, only required non-default module is `requests`)

![Output of check_vcenter.py](check_vcenter.png?raw=true "Output of check_vcenter.py")

### Compatibility

* tested with vSphere 7.x, probably also works with 6.x

### Usage

* Install required modules 
  * `pip3 install -r requirements.txt`
* Create vSphere user with API permissions
* Use the plugin

```
usage: check_vcenter.py [-h] -m {vms,hosts,datastores} -u USER -p PW --url BASEURL [-t TIMEOUT] [--cacert CACERT] [--debug]
                        [--diskwarn DISKWARN] [--diskcrit DISKCRIT]

Icinga/Nagios that checks a VMware vCenter via the vSphere Automation API

optional arguments:
  -h, --help            show this help message and exit
  -m {vms,hosts,datastores}, --mode {vms,hosts,datastores}
                        Query mode
  -u USER, --user USER  Username for vCenter
  -p PW, --pass PW      Password for vCenter
  --url BASEURL         Base URL of vCenter
  -t TIMEOUT, --timeout TIMEOUT
                        API timeout in seconds
  --cacert CACERT       Path to CA certificate file
  --debug               Print debug information

Mode-specific parameters:
  --diskwarn DISKWARN   Warning threshold for datastore usage (in %)
  --diskcrit DISKCRIT   Critical threshold for datastore usage (in %)
```

```bash
# Example usage
./check_vcenter.py --url 'https://myvcenter.example.org' \
    --mode 'hosts' \
    --user 'monitoring@vsphere.local' \
    --pass '***'
```

#### Options

* `-m` / `--mode` : Plugin mode (one of `vms`,`hosts` or `datastores`)
* `--cacert` : cacert file used to validate the vCenter TLS Certificate, defaults to `/etc/ssl/certs/ca-bundle.crt` 
  * If you run your vCenter with a selfsigned VMCA cert (which you shouldn't 😉) create a .pem file with the public key of your selfsigned VMCA and add the parameter `--cacert` pointing to that file (`--cacert ./my_VMCA_cert.pem`)


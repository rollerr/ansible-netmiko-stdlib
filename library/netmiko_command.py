#!/usr/bin/env python
from importlib import import_module
import logging
import os


try:
    import netmiko
    MEETS_REQUIREMENTS = True
except ImportError:
    MEETS_REQUIREMENTS = False


def execute_show_command(netmiko_object, command):

    if not command.startswith('show'):
        raise ValueError('Not start with show')

    try:
        output = netmiko_object.send_command(command)
        logging.info('Device output: {}'.format(output))
        return output
    except Exception as e:
        raise ValueError(e)


def setup_logging(args):

    logfile = args['log_file']

    if logfile is not None:
        logging.basicConfig(filename=logfile, level=logging.INFO,
                            format='%(asctime)s:%(name)s:%(message)s')
        logging.getLogger().name = 'CONFIG:'


def setup_netmiko_connection(dev_params):
    try:
        return netmiko.ConnectHandler(**dev_params)
    except Exception as err:
        logging.error("Exception: {}".format(err.message), exc_info=True)


def load_hosts_from_file(**kwargs):
    hosts = set()
    filename, root_path, delimeter, key = [kwargs.get(item) for item in ('filename', 'root_path', 'delimeter',
                                                                         'key',)]
    logging.info('{} {} {} {}'.format(filename, root_path, delimeter, key))
    filename = '/'.join([root_path if root_path else '.', filename])

    try:
        with open(filename) as f:
            for line in f:
                host = line.strip().split(delimeter if delimeter else ',')[key if key else 0]
                hosts.add(host)
    except IOError as err:
        logging.error('File not found {}'.format(filename), exc_info=True)
        raise err
    except IndexError:
        logging.error('Key not found')

    return list(hosts)


def main():
    """Kicks off the Ansible bootstrapping.
    """
    module = AnsibleModule(
        argument_spec=dict(
            host=dict(required=False, default=None),
            host_file=dict(required=False, default=None, type='dict'),
            user=dict(required=False, default=os.getenv('USER')),
            password=dict(required=False, default=None),
            device_type=dict(required=False, default='cisco_ios'),
            log_file=dict(required=False, default=None),
            key_file=dict(required=False, default=None),
            validation_args=dict(required=False, default=None, type='dict'),
            validate_module=dict(required=False, default=None),
            command=dict(required=True)
        ),
        supports_check_mode=False)

    # create function to validate parameters

    if not MEETS_REQUIREMENTS:
        module.fail_json(msg='netmiko >= 0.1.3 is required for this module')
        exit(1)

    args = module.params
    setup_logging(args)
    warnings = []
    device_output = ''

    if args['host_file']:
        host_file_dict = args['host_file']
        filename, root_path, delimeter, key = [host_file_dict.get(item) for item in ('filename', 'root_path',
                                                                                     'delimeter', 'key',)]
        logging.info(args['host_file'])
        hosts = load_hosts_from_file(filename=filename, root_path=root_path, delimeter=delimeter, key=key)
        logging.info('Loading from hosts file. Hosts: {}'.format(hosts))
    else:
        hosts = [(args['host'])]

    dev_params = {"device_type": args['device_type'],
                  "username": args['user'],
                  "password": args['password'],
                  "key_file": args['key_file'],
                  "verbose": False}

    # snmp validation, yes for device_type
    # move to own function
    device_output_dict = {}
    for host in hosts:
        dev_params['ip'] = host
        logging.info("connecting to {}.\nParameters:{}".format(host, dev_params))
        netmiko_object = setup_netmiko_connection(dev_params)
        device_output_dict[host] = execute_show_command(netmiko_object, args['command'])

    logging.info('Final output: {}'.format(device_output_dict))

    if args['validate_module']:
        logging.info('Running validation\nargs: {} validation module{}'.format(args['validation_args'], args['validate_module']))
        run_validator = load_validator(args['validate_module'])
        logging.info('Validator function: {}'.format(run_validator))
        validation_args = args['validation_args']

        # should pass into parse checks module?
        if args['validation_args'].get('csv_file'):
            validation_args = load_csv(validation_args['csv_file'])

        try:
            logging.info('Passing parameters: {}'.format(validation_args))
            validation_results = run_validator(device_output_dict, validation_args)
            logging.info(validation_results)

            if validation_results.get('pass'):
                module.exit_json(changed=True, msg=validation_results.get('message'))
            else:
                module.fail_json(changed=False, msg=validation_results.get('message'))

        except Exception:
            logging.info('Failed', exc_info=True)
            exit(1)
    result = dict(changed=False, warnings=warnings, stdout_lines=device_output_dict)
    module.exit_json(**result)


def load_csv(csv_file):
    with open(csv_file) as f:
        return f.read()


def load_validator(validate_module):
    try:
        folder, subfolder, library, method = validate_module.split('.')
        logging.info('Attempting to import: {} {} {} {}'.format(folder, subfolder, library, method))
        library = import_module('{}.{}.{}'.format(folder, subfolder, library))
        logging.info('Import succeeded. Returning: {}'.format(library))
        return getattr(library, method)
    except ValueError:
        logging.error('Could not split validate_module. Provided: {}'.format(validate_module))
        exit(1)
    except ImportError as e:
        logging.error('{} does not exist: {}'.format(validate_module, e))
        exit(1)


from ansible.module_utils.basic import *

if __name__ == "__main__":
    main()

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
        logging.info('Output: {}'.format(output))
        return output
    except Exception as e:
        raise ValueError(e)


def setup_logging(args):

    logfile = args['log_file']

    if logfile is not None:
        logging.basicConfig(filename=logfile, level=logging.INFO,
                            format='%(asctime)s:%(name)s:%(message)s')
        logging.getLogger().name = 'CONFIG:' + args['host']


def setup_netmiko_connection(dev_params):
    try:
        return netmiko.ConnectHandler(**dev_params)
    except Exception as err:
        logging.error("Exception: {}".format(err.message))
        raise err


def main():
    """Kicks off the Ansible bootstrapping.
    """
    module = AnsibleModule(
        argument_spec=dict(
            host=dict(required=True),
            user=dict(required=False, default=os.getenv('USER')),
            passwd=dict(required=False, default=None),
            device_type=dict(required=False, default='cisco_ios'),
            log_file=dict(required=False, default=None),
            key_file=dict(required=False, default=None),
            command=dict(required=True)
        ),
        supports_check_mode=False)

    if not MEETS_REQUIREMENTS:
        module.fail_json(msg='netmiko >= 0.1.3 is required for this module')
        return

    args = module.params
    warnings = []
    dev_params = {"device_type": args['device_type'],
                  "ip": args['host'],
                  "username": args['user'],
                  "password": args['passwd'],
                  "key_file": args['key_file'],
                  "verbose": False}

    setup_logging(args)

    logging.info("connecting to {}.\nParameters:{}".format(args['host'], dev_params))
    netmiko_object = setup_netmiko_connection(dev_params)
    stdout = execute_show_command(netmiko_object, args['command'])

    result = dict(changed=False, warnings=warnings, stdout_lines=stdout)
    module.exit_json(**result)


from ansible.module_utils.basic import *

if __name__ == "__main__":
    main()
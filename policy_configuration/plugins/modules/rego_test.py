#!/usr/bin/python


from ansible.module_utils.basic import AnsibleModule

import subprocess
import json

DOCUMENTATION = r'''
---
module: rego_test
short_description: Run OPA Rego unit tests.
description:
    - This module executes 'opa test' against a specified directory or file.
    - It returns the test results in a structured format.
options:
    path:
        description:
            - The path to the directory containing Rego policies and tests.
        required: true
        type: path
    fail_on_error:
        description:
            - Whether the module should fail the Ansible task if tests fail.
        default: true
        type: bool
'''

def run_module():
    module_args = dict(
        path=dict(type='path', required=True),
        fail_on_error=dict(type='bool', default=True)
    )

    result = dict(
        changed=False,
        stdout='',
        stderr='',
        tests_passed=False,
        test_details=[]
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )


    cmd = ["opa", "test", module.params['path'], "--format=json"]

    try:

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
        
        result['stdout'] = stdout
        result['stderr'] = stderr

        if stdout:

            test_data = json.loads(stdout)
            result['test_details'] = test_data
            
            failures = [t for t in test_data if t.get('fail') or t.get('error')]
            if not failures:
                result['tests_passed'] = True
            else:
                result['tests_passed'] = False
        
 
        if process.returncode != 0 and module.params['fail_on_error']:
            module.fail_json(msg="Rego tests failed.", **result)

    except Exception as e:
        module.fail_json(msg=f"Failed to execute opa: {str(e)}", **result)

    module.exit_json(**result)

if __name__ == '__main__':
    run_module()
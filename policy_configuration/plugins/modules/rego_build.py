#!/usr/bin/python


from ansible.module_utils.basic import AnsibleModule

import subprocess
import os

def run_module():
    module_args = dict(
        source_dir=dict(type='path', required=True),
        output_path=dict(type='str', required=True)
    )

    result = dict(
        changed=False,
        msg='',
        bundle_path='',
        stderr=''
    )

    module = AnsibleModule(argument_spec=module_args)

    
    cmd = ["opa", "build", "-o", module.params['output_path'], module.params['source_dir']]

    try:
       
        subprocess.run(["opa", "version"], capture_output=True, check=True)
        
       
        process = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        result['changed'] = True
        result['bundle_path'] = os.path.abspath(module.params['output_path'])
        result['msg'] = "Policy bundle created successfully."
        module.exit_json(**result)

    except subprocess.CalledProcessError as e:
        
        module.fail_json(
            msg="OPA build failed", 
            stderr=e.stderr, 
            stdout=e.stdout,
            cmd=" ".join(cmd)
        )
    except FileNotFoundError:
        module.fail_json(msg="The 'opa' binary was not found. Please install OPA.")
    except Exception as e:
        module.fail_json(msg=f"An unexpected error occurred: {str(e)}")

if __name__ == '__main__':
    run_module()
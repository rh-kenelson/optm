#!/usr/bin/python


from ansible.module_utils.basic import AnsibleModule

import subprocess
import json
import os

def run_module():
    module_args = dict(
        path=dict(type='path', required=True),
        fail_on_error=dict(type='bool', default=True),
        input_data=dict(type='dict', required=False), 
        package=dict(type='str', required=False)      
    )

    result = dict(changed=False, tests_passed=True, simulation_result={}, test_details=[])
    module = AnsibleModule(argument_spec=module_args)

   
    if module.params['input_data']:
        pkg = module.params.get('package', 'aap_pasc.tasks')
        
        input_file = os.path.join(module.params['path'], "simulation_input.json")
        
        with open(input_file, 'w') as f:
            json.dump(module.params['input_data'], f)

        cmd = [
            "opa", "eval", 
            "-d", module.params['path'], 
            "-i", input_file, 
            f"data.{pkg}.allow",
            "--format=json"
        ]
        
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            eval_data = json.loads(proc.stdout)
          
            result['simulation_result'] = eval_data.get('result', [{}])[0].get('expressions', [{}])[0].get('value', {})
            
           
            if not result['simulation_result'].get('allowed', True) and module.params['fail_on_error']:
                module.fail_json(msg="Compliance Simulation Failed: Input is non-compliant.", **result)
        else:
            module.fail_json(msg="OPA Eval failed", stderr=proc.stderr)

    
    else:
        cmd = ["opa", "test", module.params['path'], "--format=json"]
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        if process.stdout:
            test_data = json.loads(process.stdout)
            result['test_details'] = test_data
            failures = [t for t in test_data if t.get('fail') or t.get('error')]
            if failures:
                result['tests_passed'] = False
                if module.params['fail_on_error']:
                    module.fail_json(msg="Rego unit tests failed.", **result)

    module.exit_json(**result)

if __name__ == '__main__':
    run_module()
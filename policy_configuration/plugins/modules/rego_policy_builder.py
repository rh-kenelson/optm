#!/usr/bin/python


from ansible.module_utils.basic import AnsibleModule

import os
import json
import re

def validate_rules(module, rules):
    """Performs strict validation on the rule definitions."""
    for i, rule in enumerate(rules, 1):
        
        if not rule.get('description') and not rule.get('name'):
            module.fail_json(msg=f"Rule #{i} is missing a 'description' or 'name'.")

       
        attr = rule.get('check_attribute')
        if not attr:
            module.fail_json(msg=f"Rule #{i} ('{rule.get('description')}') is missing 'check_attribute'.")
        
        if not attr.startswith('input.'):
            module.fail_json(msg=f"Rule #{i}: attribute '{attr}' must start with 'input.'")

         
        for key in ['condition', 'error_msg']:
            val = rule.get(key, "")
            if "'" in val:
                module.fail_json(msg=f"Rule #{i}: '{key}' contains a single quote. Use double quotes for Rego strings.")

        
        r_type = rule.get('type')
        if r_type == 'block_list' and not isinstance(rule.get('blocked_values'), list):
            module.fail_json(msg=f"Rule #{i}: 'block_list' requires a list in 'blocked_values'.")
        
        if r_type == 'deny_match' and not rule.get('prohibited_pattern'):
            module.fail_json(msg=f"Rule #{i}: 'deny_match' requires a 'prohibited_pattern'.")

def generate_rego_content(package, rules):
    """Constructs the Rego code logic."""
    
    lines = [
        f"package {package}",
        "import rego.v1",
        "",
        'default allow := {"allowed": true, "violations": []}',
        "",
        "violations contains msg if {"
    ]
    
    for i, rule in enumerate(rules, 1):
        lines.append(f"    _check_rule_{i}")
        lines.append(f'    msg := "{rule.get("error_msg", "Policy Violation")}"')
        if i < len(rules):
            lines.append("}\n\nviolations contains msg if {")
    
    lines.append("}")
    lines.append("")

    for i, rule in enumerate(rules, 1):
        lines.append(f"# Rule: {rule.get('description', 'Auto-generated')}")
        lines.append(f"_check_rule_{i} if {{")
        
        if rule.get('condition'):
            lines.append(f"    {rule['condition']}")
        
        r_type = rule.get('type')
        attr = rule.get('check_attribute')
        
        if r_type == 'block_list':
            vals = json.dumps(rule.get('blocked_values', []))
            lines.append(f"    {attr} == {vals}[_]")
        elif r_type == 'deny_match':
            pattern = rule.get('prohibited_pattern', '')
            lines.append(f'    contains({attr}, "{pattern}")')
            
        lines.append("}\n")

    lines.append('allow := {"allowed": false, "violations": violations} if count(violations) > 0')
    return "\n".join(lines)

def run_module():
    module_args = dict(
        rules=dict(type='list', required=True),
        package=dict(type='str', required=True),
        dest=dict(type='path', required=True)
    )

    module = AnsibleModule(argument_spec=module_args)
    
    
    validate_rules(module, module.params['rules'])
    
    try:
        content = generate_rego_content(module.params['package'], module.params['rules'])
        os.makedirs(os.path.dirname(module.params['dest']), exist_ok=True)
        
        with open(module.params['dest'], 'w') as f:
            f.write(content)
            
        module.exit_json(changed=True, dest=module.params['dest'])
    except Exception as e:
        module.fail_json(msg=f"Internal Generator Error: {str(e)}")

if __name__ == '__main__':
    run_module()
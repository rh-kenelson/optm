#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.plugins.lookup import LookupBase
from ansible.errors import AnsibleError
import json
import collections

# Define the lookup plugin class
class LookupModule(LookupBase):

    def run(self, terms, variables=None, **kwargs):
        # 'terms' will be the list of rules passed from the playbook
        self.set_options(var_options=variables, direct=kwargs)
        
        if not terms or not isinstance(terms[0], list):
            raise AnsibleError("rego_manifest lookup requires a list of governance rules.")

        rules = terms[0]
        
        lines = [
            "# OPA Policy Deployment Manifest",
            "This document lists the required Policy Path settings for each unique policy package in this bundle.",
            "",
            "| Policy Name | Rego Package | **Required AAP Policy Path** |",
            "| :--- | :--- | :--- |",
        ]
        
        unique_packages = {}

        # Aggregate rules by their package name to avoid redundancy
        for rule in rules:
            package = rule.get('package')
            policy_name = rule.get('policy_name', 'Unnamed Policy')
            
            if not package:
                continue

            # Calculate the required path using the confirmed AAP format
            aap_path = f"{package.replace('.', '/')}/allow"
            
            # Use the first policy name encountered for a given package
            if package not in unique_packages:
                unique_packages[package] = {
                    'policy_name': policy_name,
                    'aap_path': aap_path
                }
        
        # Add the unique entries to the manifest
        for pkg, data in unique_packages.items():
            lines.append(f"| {data['policy_name']} | `{pkg}` | **`{data['aap_path']}`** |")
            
        lines.append("\n## Instructions")
        lines.append("To enable policy enforcement, set the **Query path for the policy enforcement** field on the Job Template to the corresponding path above.")
        lines.append("\n**Example:** For `aap_pasc.inventories`, set the path to `aap_pasc/inventories/allow`.")
        
        # Return the content as a single string (the standard for file content lookups)
        return ["\n".join(lines)]
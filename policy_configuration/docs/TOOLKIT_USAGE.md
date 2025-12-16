```markdown
# 🛠️ Toolkit Usage Guide

This document details the full developer workflow for the `optm.policy_configuration` collection, covering rule definition, testing, and final configuration within the Ansible Automation Platform (AAP).

## 1. Rule Definition: The Governance YAML

All policies begin as structured YAML rules. Save your definitions in a file (e.g., `governance_rules.yml`).

### Core Rule Attributes

| Attribute | Required | Description |
| :--- | :--- | :--- |
| `policy_name` | Yes | Unique identifier for the policy. |
| `package` | Yes | The Rego package path (e.g., `aap_pasc.inventories`). **This is key for AAP pathing.** |
| `error_msg` | Yes | The rejection message displayed to the end-user on violation. |
| `check_attribute` | Yes | The JSON path in the AAP input data to check (e.g., `input.task.module`). |

### Rule Types and Examples

| Type | Logic | Example Use Case | Example Rule |
| :--- | :--- | :--- | :--- |
| `block_list` | Deny if `check_attribute` value is in `blocked_values` list. | Prohibit use of `shell` or `raw` modules. | `blocked_values: ["ansible.builtin.shell", "ansible.builtin.raw"]` |
| `deny_match` | Deny if `check_attribute` string contains `prohibited_pattern`. | Block execution on any inventory containing the substring "legacy." | `prohibited_pattern: "legacy"` |
| `group_block_list`| Deny if any user group overlaps with `blocked_values`. | Block jobs by users in the "contractors" security group. | `check_attribute: input.user.groups` |

---

## 2. The Development Pipeline

### Step 2A: Generate Code and Unit Tests

This task uses the **`rego_policy_factory`** module to create the Rego source code and the accompanying test files, correctly organizing them into subdirectories that match the `package` path.

```yaml
- name: 1. Generate Rego Code and Unit Tests
  my_namespace.opa_governance.rego_policy_factory:
    rules: "{{ governance_rules }}"
    dest_dir: "./dist/policies"
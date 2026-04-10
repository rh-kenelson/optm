# Toolkit Usage Guide

This document covers the full developer workflow for the `optm.policy_configuration` collection: defining rules in YAML, generating Rego code, running tests, simulating compliance, building a deployable bundle, and configuring AAP.

---

## Collection Components

| Component | Type | Purpose |
| :--- | :--- | :--- |
| `optm.policy_configuration.rego_rule` | Module | Generates `.rego` policy files and companion `_test.rego` files from YAML rule definitions |
| `optm.policy_configuration.rego_unit_test` | Module | Runs OPA unit tests against generated policy files, or simulates a compliance check against live input |
| `optm.policy_configuration.rego_build` | Module | Packages all `.rego` files into a deployable OPA bundle (`policy_bundle.tar.gz`) |
| `optm.policy_configuration.rego_manifest` | Lookup | Generates a Markdown deployment manifest with AAP Policy Path values for each package |

---

## Step 1: Define Governance Rules

All policies start as a list of rule dictionaries in YAML. Typically stored in a vars file (e.g. `vars/governance_rules.yml`) and loaded into a playbook.

### Rule Attributes

| Attribute | Required | Description |
| :--- | :--- | :--- |
| `policy_name` | Yes | Human-readable name for the policy (used in the manifest table). |
| `package` | Yes | Rego package path (e.g. `aap_pasc.inventories`). Dots become path separators in AAP. |
| `name` | No | Short rule identifier; used as the test function name. Defaults to `rule_N`. |
| `description` | No | Comment written into the generated Rego source. |
| `error_msg` | Yes | The violation message shown to the end-user when the rule triggers. |
| `check_attribute` | Yes | Dot-notated JSON path in the AAP input object to evaluate (e.g. `input.task.module`). |
| `type` | Yes | Rule logic type. See table below. |
| `condition` | No | An optional Rego expression that must be true before the rule is evaluated (e.g. `input.task.type == "job"`). |
| `blocked_values` | Conditional | List of denied values. Required for `block_list` and `group_block_list` types. |
| `prohibited_pattern` | Conditional | Substring that must not appear in `check_attribute`. Required for `deny_match` type. |

### Rule Types

| Type | Logic | Typical Use Case |
| :--- | :--- | :--- |
| `block_list` | Denies the job if `check_attribute` equals **any** value in `blocked_values`. | Block specific Ansible modules (e.g. `shell`, `raw`). |
| `group_block_list` | Denies the job if **any** element of `check_attribute` (a list) appears in `blocked_values`. | Block jobs run by users who belong to a restricted group. |
| `deny_match` | Denies the job if `check_attribute` **contains** the `prohibited_pattern` substring. | Block execution against inventories whose name includes "legacy". |

### Example vars file

```yaml
# vars/governance_rules.yml
governance_rules:
  - policy_name: "Task Module Restrictions"
    package: "aap_pasc.tasks"
    name: "block_shell_module"
    description: "Prohibit use of raw shell execution modules."
    error_msg: "Use of shell/raw modules is not permitted by policy."
    check_attribute: "input.task.module"
    type: "block_list"
    blocked_values:
      - "ansible.builtin.shell"
      - "ansible.builtin.raw"
      - "command"

  - policy_name: "Inventory Access Control"
    package: "aap_pasc.inventories"
    name: "block_legacy_inventory"
    description: "Prevent execution against legacy inventories."
    error_msg: "Execution against legacy inventories is not permitted."
    check_attribute: "input.inventory.name"
    type: "deny_match"
    prohibited_pattern: "legacy"

  - policy_name: "Contractor Group Restrictions"
    package: "aap_pasc.users"
    name: "block_contractor_groups"
    description: "Contractors may not run privileged job templates."
    error_msg: "Users in contractor groups cannot run this job template."
    check_attribute: "input.user.groups"
    type: "group_block_list"
    blocked_values:
      - "contractors"
      - "external_vendors"
    condition: 'input.job_template.ask_limit_on_launch == true'
```

---

## Step 2: Generate Rego Code and Unit Tests — `rego_rule`

The `rego_rule` module reads your rule list and writes two files per invocation:
- `<dest>` — the policy file
- `<dest>` with `.rego` replaced by `_test.rego` — auto-generated unit tests

### Parameters

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `rules` | list | Yes | The list of governance rule dictionaries. |
| `package` | str | Yes | The Rego package declaration to write at the top of the file. Must match `package` values in your rules. |
| `dest` | path | Yes | Full destination path for the generated `.rego` policy file. Parent directories are created automatically. |

### Return values

| Key | Description |
| :--- | :--- |
| `policy_dest` | Absolute path to the generated policy file. |
| `test_dest` | Absolute path to the generated test file. |

### Example task

Because each `package` produces its own `.rego` file, loop over the unique packages in your rules:

```yaml
- name: Generate Rego policy and tests for each package
  vars:
    # Build a list of unique packages to loop over
    unique_packages: "{{ governance_rules | map(attribute='package') | unique | list }}"
  loop: "{{ unique_packages }}"
  loop_control:
    loop_var: pkg
  optm.policy_configuration.rego_rule:
    package: "{{ pkg }}"
    rules: "{{ governance_rules | selectattr('package', 'equalto', pkg) | list }}"
    dest: "./dist/policies/{{ pkg.replace('.', '/') }}/policy.rego"
```

**What gets generated:**

For a package `aap_pasc.tasks` with one `block_list` rule, the output will look like:

```rego
package aap_pasc.tasks
import rego.v1

# Generated by Ansible Policy Factory
default allow := {"allowed": true, "violations": []}

# Rule 1: Prohibit use of raw shell execution modules.
violations contains msg if {
    _check_rule_1
    msg := "Use of shell/raw modules is not permitted by policy."
}
_check_rule_1 if {
    input.task.module == ["ansible.builtin.shell", "ansible.builtin.raw", "command"][_]
}

# Final decision: Deny if violation set is not empty.
allow := {"allowed": false, "violations": violations} if count(violations) > 0
```

---

## Step 3: Run Unit Tests — `rego_unit_test`

The `rego_unit_test` module has two modes depending on whether `input_data` is provided.

### Mode A: Run OPA unit tests (no `input_data`)

Runs `opa test` against all `.rego` files in `path`. This validates that every auto-generated `test_*` function passes.

### Mode B: Simulate compliance (with `input_data`)

Writes `input_data` to a temp file and runs `opa eval` to evaluate whether a concrete piece of input would be allowed or denied. Useful for smoke-testing before deploying to AAP.

### Parameters

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `path` | path | Yes | | Directory containing the `.rego` files to test. |
| `fail_on_error` | bool | No | `true` | Fail the playbook task if any test fails or the simulation denies. |
| `input_data` | dict | No | | Input object to evaluate for compliance simulation (Mode B). |
| `package` | str | No | `aap_pasc.tasks` | Package to evaluate against in simulation mode (Mode B). |

### Return values

| Key | Description |
| :--- | :--- |
| `tests_passed` | Boolean; `true` if all unit tests passed (Mode A). |
| `test_details` | Raw JSON output from `opa test` (Mode A). |
| `simulation_result` | The `allow` decision object from `opa eval`, e.g. `{"allowed": false, "violations": ["..."]}` (Mode B). |

### Example tasks

**Run unit tests:**
```yaml
- name: Run OPA unit tests
  optm.policy_configuration.rego_unit_test:
    path: "./dist/policies"
    fail_on_error: true
```

**Simulate a compliance check:**
```yaml
- name: Simulate compliance for a shell module usage
  optm.policy_configuration.rego_unit_test:
    path: "./dist/policies"
    package: "aap_pasc.tasks"
    fail_on_error: false
    input_data:
      task:
        module: "ansible.builtin.shell"
  register: sim_result

- name: Show simulation result
  debug:
    var: sim_result.simulation_result
# Expected: {"allowed": false, "violations": ["Use of shell/raw modules is not permitted by policy."]}
```

---

## Step 4: Build the OPA Bundle — `rego_build`

Packages all Rego files in `source_dir` into a single tarball for deployment.

### Parameters

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `source_dir` | path | Yes | Directory containing all `.rego` policy files to bundle. |
| `output_path` | str | Yes | Destination path for the bundle file (e.g. `./dist/policy_bundle.tar.gz`). |

### Return values

| Key | Description |
| :--- | :--- |
| `bundle_path` | Absolute path to the created bundle file. |
| `msg` | Status message. |

### Example task

```yaml
- name: Build OPA policy bundle
  optm.policy_configuration.rego_build:
    source_dir: "./dist/policies"
    output_path: "./dist/policy_bundle.tar.gz"
  register: bundle_result

- name: Print bundle location
  debug:
    msg: "Bundle created at {{ bundle_result.bundle_path }}"
```

---

## Step 5: Generate the AAP Deployment Manifest — `rego_manifest` lookup

The `rego_manifest` lookup accepts your full rule list and returns a formatted Markdown table showing the **AAP Policy Path** value required for each package. The path format is `{package/with/slashes}/allow`.

### Usage

```yaml
- name: Print AAP deployment manifest
  debug:
    msg: "{{ lookup('optm.policy_configuration.rego_manifest', governance_rules) }}"
```

**Example output:**

```
# OPA Policy Deployment Manifest
This document lists the required Policy Path settings for each unique policy package in this bundle.

| Policy Name | Rego Package | **Required AAP Policy Path** |
| :--- | :--- | :--- |
| Task Module Restrictions | `aap_pasc.tasks` | **`aap_pasc/tasks/allow`** |
| Inventory Access Control | `aap_pasc.inventories` | **`aap_pasc/inventories/allow`** |
| Contractor Group Restrictions | `aap_pasc.users` | **`aap_pasc/users/allow`** |

## Instructions
To enable policy enforcement, set the **Query path for the policy enforcement** field on the Job Template to the corresponding path above.

**Example:** For `aap_pasc.inventories`, set the path to `aap_pasc/inventories/allow`.
```

You can also save this to a file:

```yaml
- name: Save manifest to file
  copy:
    content: "{{ lookup('optm.policy_configuration.rego_manifest', governance_rules) }}"
    dest: "./dist/DEPLOYMENT_MANIFEST.md"
```

---

## Complete End-to-End Playbook

```yaml
---
- name: Policy-as-Code Pipeline
  hosts: localhost
  connection: local
  gather_facts: false

  vars_files:
    - vars/governance_rules.yml

  vars:
    policy_dist_dir: "./dist/policies"
    bundle_output: "./dist/policy_bundle.tar.gz"
    unique_packages: "{{ governance_rules | map(attribute='package') | unique | list }}"

  tasks:
    - name: Generate Rego policy and unit tests per package
      loop: "{{ unique_packages }}"
      loop_control:
        loop_var: pkg
      optm.policy_configuration.rego_rule:
        package: "{{ pkg }}"
        rules: "{{ governance_rules | selectattr('package', 'equalto', pkg) | list }}"
        dest: "{{ policy_dist_dir }}/{{ pkg.replace('.', '/') }}/policy.rego"

    - name: Run OPA unit tests
      optm.policy_configuration.rego_unit_test:
        path: "{{ policy_dist_dir }}"
        fail_on_error: true

    - name: Build OPA bundle
      optm.policy_configuration.rego_build:
        source_dir: "{{ policy_dist_dir }}"
        output_path: "{{ bundle_output }}"
      register: bundle_result

    - name: Generate and save AAP deployment manifest
      copy:
        content: "{{ lookup('optm.policy_configuration.rego_manifest', governance_rules) }}"
        dest: "./dist/DEPLOYMENT_MANIFEST.md"

    - name: Pipeline complete
      debug:
        msg: "Bundle ready at {{ bundle_result.bundle_path }}. See dist/DEPLOYMENT_MANIFEST.md for AAP configuration."
```

---

## Configuring AAP

After deploying the bundle to your OPA server:

1. Open the **Job Template** in AAP.
2. Navigate to **Policy Enforcement** settings.
3. Set the **OPA Server URL** to your OPA instance.
4. Set the **Query path for policy enforcement** to the value from your manifest (e.g. `aap_pasc/tasks/allow`).

Each Job Template enforces exactly one package. If you have multiple packages, configure a separate Job Template (or AAP policy enforcement entry) per package.

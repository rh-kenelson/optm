# optm.policy_configuration

**Ansible Policy-as-Code (PaC) Toolkit for Open Policy Agent (OPA) and Ansible Automation Platform (AAP)**

This collection provides a framework for defining, testing, and deploying security and governance policies directly from your Ansible pipeline. Write rules once in simple YAML, and the toolkit generates production-ready Rego code, companion unit tests, a deployable OPA bundle, and an AAP configuration manifest — all in a single playbook run.

---

## Features

- **YAML-to-Rego generation** — Define governance rules as structured YAML. The `rego_rule` module compiles them into valid Rego policy files with no manual Rego authorship required.
- **Automated unit testing** — Every generated policy includes a companion `_test.rego` file. The `rego_unit_test` module runs these via `opa test` to catch regressions before deployment.
- **Compliance simulation** — Feed a real input object to `rego_unit_test` to evaluate whether it would be allowed or denied, without deploying to AAP first.
- **OPA bundle packaging** — The `rego_build` module wraps `opa build` to produce a single `policy_bundle.tar.gz` ready for your OPA server.
- **AAP deployment manifest** — The `rego_manifest` lookup plugin generates a Markdown table of the exact **Policy Path** strings needed to wire up each Job Template in AAP.

---

## Requirements

| Dependency | Version |
| :--- | :--- |
| Ansible Core | >= 2.15 |
| Python | >= 3.9 |
| Open Policy Agent (`opa` binary in PATH) | Any recent stable release |

The `opa` binary is required on the controller node for `rego_unit_test` and `rego_build` to function. It is not required at rule generation time.

Install OPA from [https://www.openpolicyagent.org/docs/latest/#1-download-opa](https://www.openpolicyagent.org/docs/latest/#1-download-opa).

---

## Installation

```bash
ansible-galaxy collection install optm.policy_configuration
```

Or add it to a `requirements.yml` file:

```yaml
collections:
  - name: optm.policy_configuration
    version: "1.0.0"
```

```bash
ansible-galaxy collection install -r requirements.yml
```

---

## Collection Contents

| Component | Type | Description |
| :--- | :--- | :--- |
| `rego_rule` | Module | Generates `.rego` policy files and `_test.rego` unit test files from a list of YAML rule definitions |
| `rego_unit_test` | Module | Runs OPA unit tests against generated Rego files, or simulates a compliance decision against live input data |
| `rego_build` | Module | Packages all Rego files in a directory into a deployable OPA bundle |
| `rego_manifest` | Lookup | Returns a Markdown deployment manifest with the correct AAP Policy Path for each policy package |

---

## Quick Start

### 1. Define your governance rules

Create a vars file with your policy rules:

```yaml
# vars/governance_rules.yml
governance_rules:
  - policy_name: "Task Module Restrictions"
    package: "aap_pasc.tasks"
    name: "block_shell_module"
    description: "Prohibit raw shell execution modules."
    error_msg: "Use of shell/raw modules is not permitted by policy."
    check_attribute: "input.task.module"
    type: "block_list"
    blocked_values:
      - "ansible.builtin.shell"
      - "ansible.builtin.raw"

  - policy_name: "Inventory Access Control"
    package: "aap_pasc.inventories"
    name: "block_legacy_inventory"
    description: "Prevent execution against legacy inventories."
    error_msg: "Execution against legacy inventories is not permitted."
    check_attribute: "input.inventory.name"
    type: "deny_match"
    prohibited_pattern: "legacy"
```

### 2. Run the pipeline playbook

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

    - name: Save AAP deployment manifest
      copy:
        content: "{{ lookup('optm.policy_configuration.rego_manifest', governance_rules) }}"
        dest: "./dist/DEPLOYMENT_MANIFEST.md"
```

### 3. Configure AAP

Open each Job Template in AAP and set the **Query path for policy enforcement** to the path listed in your generated `DEPLOYMENT_MANIFEST.md`. The path format is always `{package/with/slashes}/allow` — for example, `aap_pasc/tasks/allow`.

---

## Rule Reference

### Common Attributes

| Attribute | Required | Description |
| :--- | :--- | :--- |
| `policy_name` | Yes | Human-readable name; appears in the deployment manifest. |
| `package` | Yes | Rego package path (e.g. `aap_pasc.tasks`). Determines the AAP Policy Path. |
| `error_msg` | Yes | Violation message shown to the end-user when the rule triggers. |
| `check_attribute` | Yes | Dot-notated JSON path in the AAP input to evaluate (e.g. `input.task.module`). |
| `type` | Yes | Rule logic type — see below. |
| `name` | No | Short identifier used as the generated test function name. |
| `description` | No | Comment written into the generated Rego source. |
| `condition` | No | An additional Rego expression that must be true before this rule is evaluated. |

### Rule Types

| Type | Triggers when... | Required extra attribute |
| :--- | :--- | :--- |
| `block_list` | `check_attribute` equals any value in `blocked_values` | `blocked_values` (list) |
| `group_block_list` | Any element of `check_attribute` (a list) appears in `blocked_values` | `blocked_values` (list) |
| `deny_match` | `check_attribute` string contains `prohibited_pattern` | `prohibited_pattern` (string) |

---

## Module Reference

### `rego_rule`

Generates a `.rego` policy file and a `_test.rego` unit test file from a list of rule definitions.

**Parameters:**

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `rules` | list | Yes | List of rule dictionaries for this package. |
| `package` | str | Yes | Rego `package` declaration to write into the generated file. |
| `dest` | path | Yes | Full output path for the `.rego` file. Parent directories are created automatically. The test file is written alongside it as `_test.rego`. |

**Return values:** `policy_dest`, `test_dest`

---

### `rego_unit_test`

Runs OPA unit tests or simulates a compliance evaluation.

**Parameters:**

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `path` | path | Yes | | Directory containing `.rego` files. |
| `fail_on_error` | bool | No | `true` | Fail the task if tests fail or input is non-compliant. |
| `input_data` | dict | No | | When provided, runs a compliance simulation instead of unit tests. |
| `package` | str | No | `aap_pasc.tasks` | Package to evaluate in simulation mode. |

**Return values:** `tests_passed`, `test_details` (unit test mode) / `simulation_result` (simulation mode)

**Simulation example:**

```yaml
- name: Simulate input against task policy
  optm.policy_configuration.rego_unit_test:
    path: "./dist/policies"
    package: "aap_pasc.tasks"
    fail_on_error: false
    input_data:
      task:
        module: "ansible.builtin.shell"
  register: result

# result.simulation_result:
#   {"allowed": false, "violations": ["Use of shell/raw modules is not permitted by policy."]}
```

---

### `rego_build`

Packages Rego files into a deployable OPA bundle using `opa build`.

**Parameters:**

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `source_dir` | path | Yes | Directory of `.rego` files to bundle. |
| `output_path` | str | Yes | Destination path for the bundle (e.g. `./dist/policy_bundle.tar.gz`). |

**Return values:** `bundle_path`, `msg`

---

### `rego_manifest` lookup

Returns a Markdown deployment manifest from your rule list.

```yaml
- name: Print manifest
  debug:
    msg: "{{ lookup('optm.policy_configuration.rego_manifest', governance_rules) }}"
```

The manifest table maps each unique `package` to its **Required AAP Policy Path** (`{package/slashes}/allow`).

---

## License

GPL-3.0-or-later

## Author

Keith Nelson — [keith.r.b.nelson@gmail.com](mailto:keith.r.b.nelson@gmail.com)

# 🛡️ optm.policy_configuration

**Ansible Policy-as-Code (PaC) Toolkit for Open Policy Agent (OPA) and Ansible Automation Platform (AAP)**

This collection provides a comprehensive framework for defining, testing, and deploying robust security and governance policies directly from your Ansible pipeline. It automatically translates simple YAML rules into production-ready Rego code and OPA bundles, ensuring policy compliance before job execution on AAP.

## ✨ Features

* **YAML-to-Rego Factory:** Define high-level governance rules (e.g., blocking modules, restricting inventory access) in simple YAML.
* **Automated Unit Testing:** Generates and executes companion unit tests for every policy, establishing a Test-Driven Policy Development (TDPD) workflow.
* **AAP Path Standardization:** Automatically calculates and verifies the non-standard Policy Path (`{package}/{rule}`) required for AAP policy enforcement.
* **Deployment Artifacts:** Builds a single, deployable OPA bundle (`policy_bundle.tar.gz`) and a clear deployment manifest.
* **Custom Lookup Plugin:** Includes the `rego_manifest` lookup plugin for generating accurate deployment instructions.

## 📦 Requirements

* **Ansible Core:** >= 2.15
* **Python:** >= 3.9
* **Open Policy Agent (OPA):** The OPA binary must be installed and accessible in your system's PATH for the `rego_test` and `rego_build` modules to function.

## 🚀 Installation

### 1. Install the Collection

Install the collection from Ansible Galaxy using the standard command:

```bash
ansible-galaxy collection install optm.policy_configuration
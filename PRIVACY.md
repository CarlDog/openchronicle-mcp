# 🔒 OpenChronicle Privacy Policy

**Effective Date:** July 18, 2025  
**Last Updated:** July 18, 2025

OpenChronicle is a **local-first, self-hosted storytelling engine**. This privacy policy explains how we handle data and protect your privacy.

---

## 🏠 Local-First Architecture

**OpenChronicle processes all data locally on your device or private server.** We do not operate cloud services, collect user data, or monitor your content.

### What This Means:
- **No Data Collection:** We do not collect, store, or transmit your personal information
- **No Analytics:** We do not track usage patterns, content, or behavior
- **No Remote Storage:** All your stories, characters, and settings remain on your device
- **No Account Required:** OpenChronicle works completely offline without registration

---

## 📊 Data Processing

### Local Data Storage
OpenChronicle stores the following data **locally on your device**:
- **Story Content:** Narratives, characters, world settings, and scene data
- **User Preferences:** Configuration settings, model preferences, and UI customizations
- **System Logs:** Technical logs for debugging and performance (no personal content)
- **Temporary Files:** Cache files and temporary processing data

### Data Locations
- **Stories:** `storage/{story-name}/openchronicle.db` (SQLite database)
- **Configuration:** `config/` directory
- **Logs:** `logs/` directory (configurable, can be disabled)
- **Templates:** `templates/` and `storage/storypacks/` directories

---

## 🌐 Third-Party Services

### LLM API Services (Optional)
If you configure OpenChronicle to use external LLM services (OpenAI, Anthropic, etc.):
- **Data Transmission:** Your prompts and story content may be sent to these services
- **Third-Party Policies:** Each service has its own privacy policy and data handling practices
- **User Control:** You choose which services to use and can disable external APIs entirely
- **Local Alternative:** Use local models (Ollama) to avoid any external data transmission

### Transformer Models
- **Local Processing:** Content analysis using transformer models happens locally
- **No Data Sharing:** Model inference does not transmit data to external services
- **Offline Capability:** All transformer analysis works without internet connection

---

## 🛡️ Your Privacy Rights

### Data Control
- **Full Ownership:** You own all content created with OpenChronicle
- **Data Portability:** Export your stories in standard formats (JSON, Markdown)
- **Data Deletion:** Delete any or all data by removing local files
- **Access Control:** Manage who can access your self-hosted deployment

### GDPR Compliance (EU Users)
- **Right to Access:** All your data is locally accessible
- **Right to Rectification:** Modify or correct data directly in OpenChronicle
- **Right to Erasure:** Delete files to remove data permanently
- **Right to Portability:** Export data in machine-readable formats
- **Right to Object:** Disable any optional features or external services

### CCPA Compliance (California Users)
- **No Sale of Personal Information:** We do not sell or share personal information
- **No Data Brokers:** We do not provide data to third-party brokers
- **Transparency:** This policy explains all data handling practices

---

## 🔐 Data Security

### Local Security
- **File Permissions:** Standard operating system file protection
- **User Responsibility:** Secure your device and deployment environment
- **Encryption:** Optional SQLite encryption for sensitive content
- **Backup Security:** Secure your backups according to your security requirements

### Self-Hosted Deployments
- **Network Security:** Configure firewalls and access controls appropriately
- **HTTPS:** Use HTTPS for web-based deployments
- **Authentication:** Implement authentication if exposing to networks
- **Updates:** Keep OpenChronicle and dependencies updated

---

## 👶 Children's Privacy

OpenChronicle does not:
- Collect personal information from children under 13
- Target content toward children
- Require age verification or personal information

**Parental Guidance:** Parents/guardians are responsible for supervising children's use of OpenChronicle and the content they create.

---

## 🔄 Data Retention

### Local Data
- **Indefinite Storage:** Data persists until you choose to delete it
- **User Control:** You control all retention and deletion decisions
- **No Automatic Deletion:** OpenChronicle does not automatically delete your content

### Logs and Temporary Files
- **Configurable Retention:** Adjust log retention in configuration
- **Cleanup Tools:** Use provided utilities to clean temporary files
- **Manual Control:** Clear logs and cache manually as needed

---

## 📧 Contact and Questions

### Open Source Project
OpenChronicle is an open source project. For privacy-related questions:
- **GitHub Issues:** [https://github.com/OpenChronicle/openchronicle-core/issues](https://github.com/OpenChronicle/openchronicle-core/issues)
- **Documentation:** Check README.md and documentation files
- **Community:** Engage with the community for support and questions

### No Customer Support
As a self-hosted, open source tool:
- **No Customer Service:** We do not provide individual customer support
- **Community Support:** The community provides assistance and guidance
- **Self-Service:** Use documentation and community resources for help

---

## 🔄 Policy Updates

### Notification of Changes
- **Version Control:** Updates tracked in Git repository
- **Changelog:** Major changes documented in release notes
- **User Responsibility:** Check for updates when upgrading OpenChronicle

### Effective Date
This policy is effective as of the date listed above and applies to all versions of OpenChronicle from that date forward.

---

## ⚖️ Legal Basis

### Legitimate Interest
We process minimal technical data (logs, configuration) based on legitimate interest to:
- Provide software functionality
- Enable debugging and troubleshooting
- Improve software stability and performance

### User Consent
For optional features requiring external services:
- **Explicit Consent:** Configure external APIs only with user action
- **Informed Consent:** Clear documentation of data implications
- **Withdrawal:** Disable external services at any time

---

**Remember:** OpenChronicle is designed to respect your privacy through local-first architecture. You maintain complete control over your data and content.

---

© 2024–2025 CarlDog / OpenChronicle Project  
Licensed under GNU Affero General Public License v3.0

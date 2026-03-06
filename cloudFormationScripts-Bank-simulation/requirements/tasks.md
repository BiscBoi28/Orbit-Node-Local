# Implementation Plan: Simulated Bank Infrastructure

## Overview

This implementation plan breaks down the automated deployment system for simulated bank infrastructure into discrete, testable tasks. The system deploys six bank assets using CloudFormation templates with automatic Wazuh agent registration. Implementation follows the four-phase architecture: pre-deployment (networking/IAM), secrets management, EC2 deployment, and agent registration.

The implementation uses Bash for orchestration scripts, Python for CSV parsing, YAML for CloudFormation templates, and PowerShell for Windows configuration. Tasks are organized to enable incremental validation with checkpoints after major phases.

## Tasks

- [x] 1. Set up project structure and configuration
  - Create directory structure: `cloudFormationScripts-Bank-simulation/templates/`, `scripts/`, `cloudFormationScripts-Bank-simulation/`
  - Create placeholder CSV file at `cloudFormationScripts-Bank-simulation/ORBIT_simulated_bank.csv` with six asset definitions
  - Set up logging utility functions for consistent timestamp and level formatting
  - _Requirements: 7.1, 10.1_

- [x] 2. Implement Pre-Deployment CloudFormation template
  - [x] 2.1 Create VPC and networking resources
    - Write `cloudFormationScripts-Bank-simulation/templates/pre-deployment.yaml` with VPC (10.0.0.0/16), public subnet (10.0.1.0/24), internet gateway, and route table
    - Define template parameters: ProjectName, Environment, AdminIpCidr, WazuhServerIp
    - _Requirements: 1.2, 1.4_
  
  - [x] 2.2 Define security groups for all asset types
    - Create database security group (port 5432 from app servers)
    - Create application security group (port 8080 from web servers)
    - Create web security group (ports 80, 443 from internet)
    - Create Active Directory security group (ports 389, 636, 88, 445, 3389)
    - Create jump host security group (ports 22, 3389 from admin IPs)
    - Create Wazuh agent security group (ports 1514, 1515 outbound to Wazuh server)
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7_
  
  - [x] 2.3 Create IAM role and instance profile
    - Define IAM role with policies for SSM, Secrets Manager read, CloudWatch Logs write
    - Create instance profile resource
    - _Requirements: 1.4_
  
  - [x] 2.4 Define stack outputs for cross-stack references
    - Export VpcId, SubnetId, all security group IDs, and InstanceProfileArn
    - _Requirements: 1.4, 1.5_

- [x] 3. Implement Secrets CloudFormation template
  - [x] 3.1 Create Secrets Manager resource
    - Write `cloudFormationScripts-Bank-simulation/templates/secrets.yaml` with AWS::SecretsManager::Secret resource
    - Define parameters: WazuhServerIp, WazuhServerPort, WazuhAgentGroup
    - Store JSON structure with server_ip, server_port, agent_group, protocol fields
    - _Requirements: 1.3, 2.1, 2.2, 2.3, 2.6_
  
  - [x] 3.2 Define secret output
    - Export WazuhConfigSecretArn for use by agent registration
    - _Requirements: 1.3_

- [x] 4. Implement reusable Linux CloudFormation template
  - [x] 4.1 Create parameterized Linux template
    - Write `cloudFormationScripts-Bank-simulation/templates/linux-instance.yaml` with parameters: Hostname, OperatingSystem, InstanceType, SoftwarePackages, SecurityGroupId, SubnetId, InstanceProfileArn, AssetId, BusinessDomain, SensitivityLevel
    - Define allowed values for OperatingSystem: RHEL8, Ubuntu2204
    - Define allowed values for InstanceType: t3.micro, t3.small, t3.medium
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  
  - [x] 4.2 Implement AMI selection logic
    - Use AWS::SSM::Parameter::Value for RHEL8: `/aws/service/rhel/8/latest/x86_64`
    - Use AWS::SSM::Parameter::Value for Ubuntu2204: `/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id`
    - Use CloudFormation conditions to select correct AMI based on OperatingSystem parameter
    - _Requirements: 4.5, 4.6_
  
  - [x] 4.3 Write user data script for Linux instances
    - Set hostname using hostnamectl
    - Implement OS-specific package installation (yum for RHEL, apt-get for Ubuntu)
    - Install software packages from SoftwarePackages parameter
    - Add cfn-signal for stack creation completion
    - _Requirements: 4.7_
  
  - [x] 4.4 Define EC2 instance resource and outputs
    - Create EC2::Instance with network configuration using imported values
    - Add tags: Name, Asset_ID, Business_Domain, Sensitivity_Level, project, environment, component
    - Export InstanceId, PrivateIp, PublicIp
    - _Requirements: 4.8, 4.9, 4.10, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

- [x] 5. Implement reusable Windows CloudFormation template
  - [x] 5.1 Create parameterized Windows template
    - Write `cloudFormationScripts-Bank-simulation/templates/windows-instance.yaml` with same parameter structure as Linux template
    - Define allowed values for OperatingSystem: WindowsServer2022, Windows11
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  
  - [x] 5.2 Implement AMI selection logic for Windows
    - Use AWS::SSM::Parameter::Value for WindowsServer2022: `/aws/service/ami-windows-latest/Windows_Server-2022-English-Full-Base`
    - Use AWS::SSM::Parameter::Value for Windows11: `/aws/service/ami-windows-latest/Windows-11-English-Full-Base`
    - Use CloudFormation conditions to select correct AMI
    - _Requirements: 5.5, 5.6_
  
  - [x] 5.3 Write PowerShell user data script
    - Rename computer using Rename-Computer cmdlet
    - Install software packages using Chocolatey or native installers
    - Add cfn-signal for completion notification
    - _Requirements: 5.7_
  
  - [x] 5.4 Define EC2 instance resource with Windows configuration
    - Create EC2::Instance with same network and tagging structure as Linux template
    - Export InstanceId, PrivateIp, PublicIp
    - _Requirements: 5.8, 5.9, 5.10, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

- [x] 6. Implement Database CloudFormation template
  - [x] 6.1 Create database template extending Linux template
    - Write `cloudFormationScripts-Bank-simulation/templates/database-instance.yaml` with additional parameters: DatabaseType, DatabaseVersion, DatabasePort, DataVolumeSize
    - Set defaults: DatabaseType=PostgreSQL, DatabaseVersion=15, DatabasePort=5432, DataVolumeSize=100
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
  
  - [x] 6.2 Add EBS volume resource
    - Create AWS::EC2::Volume with gp3 type, encryption enabled, size from DataVolumeSize parameter
    - Create AWS::EC2::VolumeAttachment to attach volume to instance
    - _Requirements: 6.7_
  
  - [x] 6.3 Enhance user data for PostgreSQL installation
    - Install PostgreSQL at specified version
    - Configure PostgreSQL to listen on specified port
    - Format and mount EBS volume at /var/lib/postgresql
    - Add fstab entry for persistent mount
    - Enable and start PostgreSQL service
    - _Requirements: 6.5, 6.6, 6.8_
  
  - [x] 6.4 Add database-specific outputs
    - Export DataVolumeId in addition to standard instance outputs
    - _Requirements: 6.1_

- [x] 7. Checkpoint - Validate CloudFormation templates
  - Ensure all templates pass CloudFormation validation, ask the user if questions arise.

- [ ] 8. Implement CSV parsing utility
  - [ ] 8.1 Create Python CSV parser module
    - Write `scripts/parse_asset_config.py` with function to read CSV file
    - Parse CSV columns into asset dictionary structure
    - Implement normalize_os_type function to convert CSV OS strings to template parameter values
    - _Requirements: 7.1, 7.2_
  
  - [ ] 8.2 Add CSV validation logic
    - Validate exactly 6 assets with Asset_IDs NS-01 through NS-06
    - Validate required columns are present
    - Validate OS types are recognized
    - Validate instance types are valid EC2 types
    - Return validation errors with descriptive messages
    - _Requirements: 7.3, 7.5_
  
  - [ ]* 8.3 Write unit tests for CSV parser
    - Test valid CSV parsing
    - Test OS type normalization for all supported OS types
    - Test validation error cases (missing file, invalid data, wrong asset count)
    - _Requirements: 7.4, 7.5_

- [ ] 9. Implement orchestrator script core functionality
  - [ ] 9.1 Create orchestrator script structure
    - Write `deploy-bank-infrastructure.sh` with command-line argument parsing
    - Implement options: --config-file, --wazuh-server, --wazuh-port, --wazuh-group, --region, --dry-run, --help
    - Validate required parameters (wazuh-server)
    - Validate Wazuh server IP is valid IPv4 format
    - _Requirements: 1.1, 2.1, 2.4, 2.5_
  
  - [ ] 9.2 Implement CSV reading and parsing
    - Call Python CSV parser to read asset configuration
    - Handle file not found error with descriptive message
    - Handle validation errors from parser
    - Exit with non-zero status on errors
    - _Requirements: 7.1, 7.2, 7.4, 7.5_
  
  - [ ] 9.3 Implement stack creation functions
    - Write function to create CloudFormation stack with AWS CLI
    - Write function to wait for stack creation completion
    - Write function to get stack outputs
    - Implement error handling for stack creation failures
    - Log stack name and status for each operation
    - _Requirements: 1.2, 1.7, 10.2, 10.3, 10.7_

- [ ] 10. Implement orchestrator deployment phases
  - [ ] 10.1 Implement Phase 1: Pre-deployment stack creation
    - Create pre-deployment stack with parameters from command-line options
    - Wait for stack creation to complete
    - Retrieve and store stack outputs (VPC ID, subnet ID, security group IDs, instance profile ARN)
    - Log deployment start and pre-deployment completion
    - _Requirements: 1.2, 1.4, 9.1, 10.1, 10.2, 10.3_
  
  - [ ] 10.2 Implement Phase 2: Secrets stack creation
    - Create secrets stack with Wazuh configuration parameters
    - Wait for stack creation to complete
    - Retrieve secret ARN from stack outputs
    - _Requirements: 1.3, 9.2_
  
  - [ ] 10.3 Implement Phase 3: EC2 deployment stacks
    - Loop through parsed assets from CSV
    - For each asset, determine appropriate template (linux-instance, windows-instance, or database-instance)
    - Create stack with asset-specific parameters and pre-deployment outputs
    - Launch all EC2 stacks in parallel (background processes)
    - Wait for all EC2 stacks to complete
    - Retrieve instance IDs and IP addresses from stack outputs
    - _Requirements: 1.1, 1.5, 7.6, 9.5_
  
  - [ ] 10.4 Add dependency management between phases
    - Ensure pre-deployment completes before secrets creation
    - Ensure secrets completes before EC2 deployment
    - Implement wait logic for stack completion before proceeding
    - Exit without creating dependent stacks if prerequisite fails
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.6_

- [ ] 11. Implement agent registration script
  - [ ] 11.1 Create agent registration script structure
    - Write `scripts/register-agent.sh` with command-line argument parsing
    - Implement options: --instance-id, --hostname, --os-type, --wazuh-server, --wazuh-port, --wazuh-group, --max-retries, --retry-delay
    - Set defaults: max-retries=3, retry-delay=10
    - _Requirements: 3.1, 3.5_
  
  - [ ] 11.2 Implement Linux agent installation
    - Wait for instance to reach running state using aws ec2 wait
    - Use AWS SSM send-command to execute installation commands remotely
    - Add Wazuh repository GPG key and apt source
    - Install wazuh-agent package with WAZUH_MANAGER environment variable
    - Enable and start wazuh-agent service
    - _Requirements: 3.1, 3.2, 3.7_
  
  - [ ] 11.3 Implement Windows agent installation
    - Use AWS SSM send-command with AWS-RunPowerShellScript document
    - Download Wazuh Windows agent MSI installer
    - Install agent with Wazuh server IP configuration
    - Start Wazuh service
    - _Requirements: 3.1, 3.2, 3.7_
  
  - [ ] 11.4 Implement agent verification and retry logic
    - Write function to check if agent is registered with Wazuh server
    - Implement retry loop with configurable max retries and delay
    - Log registration attempts and status
    - Continue with remaining assets if registration fails after retries
    - _Requirements: 3.3, 3.4, 3.5, 3.6, 10.4, 10.5_

- [ ] 12. Integrate agent registration into orchestrator
  - [ ] 12.1 Add Phase 4: Agent registration to orchestrator
    - Loop through deployed instances
    - Determine OS type for each instance
    - Call register-agent.sh for each instance with appropriate parameters
    - Log agent registration start and completion for each asset
    - _Requirements: 3.1, 3.3, 10.4, 10.5_
  
  - [ ] 12.2 Implement deployment completion logging
    - Log deployment completion with timestamp
    - Log summary of deployed assets with counts
    - _Requirements: 10.6_

- [ ] 13. Implement deployment information output
  - [ ] 13.1 Create deployment info generation function
    - Write function to format deployment information
    - Include deployment timestamp, region, Wazuh server IP
    - For each asset: Asset ID, hostname, instance ID, private IP, public IP, OS, connection command
    - Include Wazuh agent registration status
    - Include Wazuh dashboard URL
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_
  
  - [ ] 13.2 Write deployment info to file
    - Save formatted deployment information to deployment-info.txt
    - Display deployment info to console
    - _Requirements: 13.6_

- [ ] 14. Checkpoint - Test end-to-end deployment
  - Ensure orchestrator script can deploy all stacks successfully, ask the user if questions arise.

- [ ] 15. Implement cleanup script
  - [ ] 15.1 Create cleanup script structure
    - Write `cleanup-bank-infrastructure.sh` with command-line argument parsing
    - Implement options: --confirm, --keep-pre-deployment, --region
    - Add confirmation prompt unless --confirm is specified
    - _Requirements: 11.1_
  
  - [ ] 15.2 Implement stack deletion with dependency order
    - List all EC2 deployment stacks (orbit-bank-ns-*)
    - Delete all EC2 stacks in parallel
    - Wait for all EC2 stack deletions to complete
    - Delete secrets stack
    - Wait for secrets stack deletion
    - Delete pre-deployment stack (unless --keep-pre-deployment)
    - _Requirements: 11.2, 11.3, 11.4, 11.5_
  
  - [ ] 15.3 Add error handling and logging
    - Log each stack deletion operation
    - Continue with remaining deletions if one fails
    - Log summary of deleted resources at completion
    - _Requirements: 11.6, 11.7_

- [ ]* 16. Add integration tests for deployment workflow
  - Write test script that deploys infrastructure to test AWS account
  - Verify all stacks are created successfully
  - Verify instances are running
  - Verify Wazuh agents are registered
  - Run cleanup and verify all resources are deleted
  - _Requirements: 1.1, 1.6, 3.1, 11.1_

- [ ] 17. Create documentation and configuration files
  - [ ] 17.1 Create README with usage instructions
    - Document prerequisites (AWS CLI, Python, Wazuh server)
    - Document deployment command with all options
    - Document cleanup command
    - Include troubleshooting section
    - _Requirements: 1.1, 2.1, 11.1_
  
  - [ ] 17.2 Create example configuration file
    - Create example CSV with all six bank assets
    - Include all required columns with realistic values
    - Document CSV schema and column descriptions
    - _Requirements: 7.1, 7.2_
  
  - [ ] 17.3 Add logging configuration
    - Document log format and levels
    - Add log file output option to orchestrator
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

- [ ] 18. Final checkpoint - Complete system validation
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at major milestones
- CloudFormation templates use YAML format for readability
- Orchestrator and cleanup scripts use Bash for portability
- CSV parsing uses Python for robust data handling
- Agent registration supports both Linux and Windows through AWS SSM
- All stacks follow naming convention: orbit-bank-{component}
- Security groups are configured per requirements with appropriate port restrictions
- IAM roles follow least-privilege principle with only required permissions

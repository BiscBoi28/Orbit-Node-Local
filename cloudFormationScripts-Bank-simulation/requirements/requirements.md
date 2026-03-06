# Requirements Document

## Introduction

This document specifies requirements for an automated deployment system for a simulated bank infrastructure on AWS. The system deploys six bank infrastructure assets (database servers, application servers, web servers, Active Directory, and jump hosts) using CloudFormation templates and registers them as agents to a Wazuh security monitoring server. The infrastructure is designed for security demonstration and testing purposes, with each asset having specific vulnerability demonstration capabilities.

## Glossary

- **Bank_Infrastructure_System**: The complete automated deployment system that orchestrates CloudFormation stacks for all bank assets
- **Orchestrator_Script**: Shell script that triggers deployment of all bank infrastructure components in the correct sequence
- **Asset**: A single infrastructure component (EC2 instance) representing a bank system (e.g., database, application server)
- **CloudFormation_Template**: AWS Infrastructure-as-Code template that defines AWS resources
- **Wazuh_Server**: Security monitoring server that receives agent connections and monitors infrastructure
- **Wazuh_Agent**: Software installed on each asset that reports to the Wazuh_Server
- **Agent_Registration_Script**: Shell script that installs and configures Wazuh agents on deployed assets
- **Pre_Deployment_Stack**: CloudFormation stack that creates shared networking and IAM resources
- **Secrets_Stack**: CloudFormation stack that stores sensitive configuration in AWS Secrets Manager
- **EC2_Deployment_Stack**: CloudFormation stack that creates EC2 instances for bank assets
- **Agent_Registration_Stack**: CloudFormation stack or script that registers deployed instances with Wazuh_Server
- **Reusable_Template**: Parameterized CloudFormation template that can be used for multiple similar assets
- **Linux_Template**: Reusable CloudFormation template for Linux-based assets (RHEL, Ubuntu)
- **Windows_Template**: Reusable CloudFormation template for Windows-based assets (Server 2022, Windows 11)
- **Database_Template**: Reusable CloudFormation template for database servers (PostgreSQL)
- **Asset_Configuration**: CSV file containing specifications for each bank asset (hostname, OS, instance size, software)

## Requirements

### Requirement 1: Deploy Bank Infrastructure Assets

**User Story:** As a security engineer, I want to deploy all six bank infrastructure assets with a single command, so that I can quickly provision a complete simulated bank environment for testing.

#### Acceptance Criteria

1. THE Orchestrator_Script SHALL deploy all six assets defined in Asset_Configuration (NS-01 through NS-06)
2. WHEN the Orchestrator_Script is executed, THE Bank_Infrastructure_System SHALL create Pre_Deployment_Stack before creating EC2_Deployment_Stack
3. WHEN the Orchestrator_Script is executed, THE Bank_Infrastructure_System SHALL create Secrets_Stack before creating EC2_Deployment_Stack
4. WHEN Pre_Deployment_Stack creation completes, THE Bank_Infrastructure_System SHALL export VPC ID, Subnet ID, Security Group ID, and IAM Instance Profile ARN
5. WHEN EC2_Deployment_Stack is created for an asset, THE Bank_Infrastructure_System SHALL use outputs from Pre_Deployment_Stack as input parameters
6. THE Orchestrator_Script SHALL complete deployment of all assets within 30 minutes
7. WHEN any CloudFormation stack creation fails, THE Orchestrator_Script SHALL log the error message and exit with non-zero status code

### Requirement 2: Configure Wazuh Server Connection

**User Story:** As a security engineer, I want to specify Wazuh server details through configuration, so that I can register agents to different Wazuh servers without modifying scripts.

#### Acceptance Criteria

1. THE Bank_Infrastructure_System SHALL accept Wazuh_Server IP address as a configuration parameter
2. THE Bank_Infrastructure_System SHALL accept Wazuh_Server port number as a configuration parameter with default value 1514
3. THE Bank_Infrastructure_System SHALL accept Wazuh agent group names as an optional configuration parameter
4. WHEN Wazuh_Server IP address is not provided, THE Orchestrator_Script SHALL exit with error message "Wazuh server IP required"
5. THE Bank_Infrastructure_System SHALL validate that Wazuh_Server IP address is in valid IPv4 format
6. THE Bank_Infrastructure_System SHALL store Wazuh_Server configuration in a configuration file separate from deployment scripts

### Requirement 3: Register Assets as Wazuh Agents

**User Story:** As a security engineer, I want all deployed assets to automatically register with the Wazuh server, so that I can immediately begin monitoring the infrastructure.

#### Acceptance Criteria

1. WHEN an asset EC2 instance reaches running state, THE Agent_Registration_Script SHALL install the Wazuh_Agent on that asset
2. WHEN Wazuh_Agent installation completes, THE Agent_Registration_Script SHALL configure the agent to connect to Wazuh_Server using the configured IP address
3. WHEN Wazuh_Agent is configured, THE Agent_Registration_Script SHALL register the agent with Wazuh_Server using the asset hostname
4. THE Agent_Registration_Script SHALL verify that Wazuh_Agent is running before completing
5. WHEN Wazuh_Agent registration fails, THE Agent_Registration_Script SHALL retry registration up to 3 times with 10 second delays
6. WHEN Wazuh_Agent registration fails after 3 retries, THE Agent_Registration_Script SHALL log the failure and continue with remaining assets
7. THE Agent_Registration_Script SHALL support both Linux (RHEL 8, Ubuntu 22.04) and Windows (Server 2022, Windows 11) operating systems

### Requirement 4: Create Reusable Linux CloudFormation Template

**User Story:** As a DevOps engineer, I want a parameterized Linux template, so that I can deploy different Linux-based assets without duplicating template code.

#### Acceptance Criteria

1. THE Linux_Template SHALL accept hostname as a parameter
2. THE Linux_Template SHALL accept operating system type as a parameter with allowed values "RHEL8" and "Ubuntu2204"
3. THE Linux_Template SHALL accept instance type as a parameter (t3.micro, t3.small, t3.medium)
4. THE Linux_Template SHALL accept software packages list as a parameter
5. WHEN operating system type is "RHEL8", THE Linux_Template SHALL use the latest RHEL 8 AMI from AWS Systems Manager Parameter Store
6. WHEN operating system type is "Ubuntu2204", THE Linux_Template SHALL use the latest Ubuntu 22.04 AMI from AWS Systems Manager Parameter Store
7. WHEN the EC2 instance is created, THE Linux_Template SHALL install all software packages specified in the packages parameter
8. THE Linux_Template SHALL create EC2 instances in the VPC and subnet provided by Pre_Deployment_Stack
9. THE Linux_Template SHALL attach the security group provided by Pre_Deployment_Stack
10. THE Linux_Template SHALL attach the IAM instance profile provided by Pre_Deployment_Stack

### Requirement 5: Create Reusable Windows CloudFormation Template

**User Story:** As a DevOps engineer, I want a parameterized Windows template, so that I can deploy different Windows-based assets without duplicating template code.

#### Acceptance Criteria

1. THE Windows_Template SHALL accept hostname as a parameter
2. THE Windows_Template SHALL accept operating system type as a parameter with allowed values "WindowsServer2022" and "Windows11"
3. THE Windows_Template SHALL accept instance type as a parameter (t3.micro, t3.small, t3.medium)
4. THE Windows_Template SHALL accept software packages list as a parameter
5. WHEN operating system type is "WindowsServer2022", THE Windows_Template SHALL use the latest Windows Server 2022 AMI from AWS Systems Manager Parameter Store
6. WHEN operating system type is "Windows11", THE Windows_Template SHALL use the latest Windows 11 AMI from AWS Systems Manager Parameter Store
7. WHEN the EC2 instance is created, THE Windows_Template SHALL install all software packages specified in the packages parameter using PowerShell
8. THE Windows_Template SHALL create EC2 instances in the VPC and subnet provided by Pre_Deployment_Stack
9. THE Windows_Template SHALL attach the security group provided by Pre_Deployment_Stack
10. THE Windows_Template SHALL attach the IAM instance profile provided by Pre_Deployment_Stack

### Requirement 6: Create Reusable Database CloudFormation Template

**User Story:** As a DevOps engineer, I want a parameterized database template, so that I can deploy database servers with consistent configuration.

#### Acceptance Criteria

1. THE Database_Template SHALL extend Linux_Template with database-specific configuration
2. THE Database_Template SHALL accept database type as a parameter with allowed value "PostgreSQL"
3. THE Database_Template SHALL accept database version as a parameter
4. THE Database_Template SHALL accept database port as a parameter with default value 5432
5. WHEN the EC2 instance is created, THE Database_Template SHALL install PostgreSQL at the specified version
6. WHEN PostgreSQL installation completes, THE Database_Template SHALL configure PostgreSQL to listen on the specified port
7. THE Database_Template SHALL create an EBS volume for database storage with size specified as a parameter
8. THE Database_Template SHALL mount the EBS volume at /var/lib/postgresql

### Requirement 7: Parse Asset Configuration from CSV

**User Story:** As a security engineer, I want the system to read asset specifications from the CSV file, so that I can modify asset configurations without changing deployment scripts.

#### Acceptance Criteria

1. THE Orchestrator_Script SHALL read Asset_Configuration from cloudFormationScripts-Bank-simulation/ORBIT_simulated_bank.csv
2. WHEN Asset_Configuration is read, THE Orchestrator_Script SHALL parse each row into asset parameters (Asset_ID, Hostname, Operating_System, Instance_Size, OpenSource_Software_To_Install)
3. THE Orchestrator_Script SHALL validate that Asset_Configuration contains exactly 6 assets with Asset_IDs NS-01 through NS-06
4. WHEN Asset_Configuration is missing or unreadable, THE Orchestrator_Script SHALL exit with error message "Asset configuration file not found"
5. WHEN Asset_Configuration contains invalid data, THE Orchestrator_Script SHALL exit with error message describing the validation failure
6. FOR ALL assets in Asset_Configuration, THE Orchestrator_Script SHALL create a corresponding EC2_Deployment_Stack

### Requirement 8: Tag Resources for Identification

**User Story:** As a cloud administrator, I want all deployed resources to have consistent tags, so that I can track costs and manage resources effectively.

#### Acceptance Criteria

1. THE Bank_Infrastructure_System SHALL tag all CloudFormation stacks with tag "project" set to "ORBIT"
2. THE Bank_Infrastructure_System SHALL tag all CloudFormation stacks with tag "environment" set to "simulation"
3. THE Bank_Infrastructure_System SHALL tag all CloudFormation stacks with tag "component" set to "bank-infrastructure"
4. THE Bank_Infrastructure_System SHALL tag all EC2 instances with tag "Name" set to the asset hostname
5. THE Bank_Infrastructure_System SHALL tag all EC2 instances with tag "Asset_ID" set to the value from Asset_Configuration
6. THE Bank_Infrastructure_System SHALL tag all EC2 instances with tag "Business_Domain" set to the value from Asset_Configuration
7. THE Bank_Infrastructure_System SHALL tag all EC2 instances with tag "Sensitivity_Level" set to the value from Asset_Configuration

### Requirement 9: Handle Deployment Dependencies

**User Story:** As a DevOps engineer, I want the system to handle dependencies between stacks, so that resources are created in the correct order.

#### Acceptance Criteria

1. THE Orchestrator_Script SHALL create Pre_Deployment_Stack before any other stacks
2. THE Orchestrator_Script SHALL create Secrets_Stack before EC2_Deployment_Stack
3. WHEN Pre_Deployment_Stack creation is in progress, THE Orchestrator_Script SHALL wait for completion before creating dependent stacks
4. WHEN Secrets_Stack creation is in progress, THE Orchestrator_Script SHALL wait for completion before creating EC2_Deployment_Stack
5. THE Orchestrator_Script SHALL create EC2_Deployment_Stack for all assets in parallel after prerequisites are complete
6. WHEN any prerequisite stack creation fails, THE Orchestrator_Script SHALL not create dependent stacks

### Requirement 10: Provide Deployment Status Reporting

**User Story:** As a security engineer, I want to see deployment progress in real-time, so that I can monitor the deployment and identify issues quickly.

#### Acceptance Criteria

1. WHEN the Orchestrator_Script starts, THE Bank_Infrastructure_System SHALL log "Starting bank infrastructure deployment" with timestamp
2. WHEN each CloudFormation stack creation starts, THE Orchestrator_Script SHALL log the stack name and status "CREATE_IN_PROGRESS"
3. WHEN each CloudFormation stack creation completes, THE Orchestrator_Script SHALL log the stack name and status "CREATE_COMPLETE"
4. WHEN each asset Wazuh_Agent registration starts, THE Orchestrator_Script SHALL log the asset hostname and status "REGISTERING_AGENT"
5. WHEN each asset Wazuh_Agent registration completes, THE Orchestrator_Script SHALL log the asset hostname and status "AGENT_REGISTERED"
6. WHEN the Orchestrator_Script completes successfully, THE Bank_Infrastructure_System SHALL log "Bank infrastructure deployment complete" with timestamp and summary of deployed assets
7. WHEN any operation fails, THE Orchestrator_Script SHALL log the error message with severity level "ERROR"

### Requirement 11: Support Cleanup and Teardown

**User Story:** As a security engineer, I want to cleanly remove all deployed infrastructure, so that I can avoid unnecessary AWS costs when testing is complete.

#### Acceptance Criteria

1. THE Bank_Infrastructure_System SHALL provide a cleanup script that deletes all deployed resources
2. WHEN the cleanup script is executed, THE Bank_Infrastructure_System SHALL delete all EC2_Deployment_Stack instances
3. WHEN all EC2_Deployment_Stack deletions complete, THE Bank_Infrastructure_System SHALL delete Secrets_Stack
4. WHEN Secrets_Stack deletion completes, THE Bank_Infrastructure_System SHALL delete Pre_Deployment_Stack
5. THE cleanup script SHALL wait for each stack deletion to complete before deleting dependent stacks
6. WHEN any stack deletion fails, THE cleanup script SHALL log the error and continue with remaining deletions
7. WHEN the cleanup script completes, THE Bank_Infrastructure_System SHALL log a summary of deleted resources

### Requirement 12: Configure Security Groups for Bank Assets

**User Story:** As a security engineer, I want appropriate security group rules for each asset type, so that the simulated bank infrastructure has realistic network security controls.

#### Acceptance Criteria

1. THE Pre_Deployment_Stack SHALL create a security group for database servers that allows inbound TCP port 5432 from application servers
2. THE Pre_Deployment_Stack SHALL create a security group for application servers that allows inbound TCP port 8080 from web servers
3. THE Pre_Deployment_Stack SHALL create a security group for web servers that allows inbound TCP ports 80 and 443 from 0.0.0.0/0
4. THE Pre_Deployment_Stack SHALL create a security group for Active Directory servers that allows inbound TCP ports 389, 636, 88, 445, and 3389
5. THE Pre_Deployment_Stack SHALL create a security group for jump hosts that allows inbound TCP ports 22 and 3389 from administrator IP addresses
6. THE Pre_Deployment_Stack SHALL create a security group for Wazuh agents that allows outbound TCP ports 1514 and 1515 to Wazuh_Server
7. FOR ALL security groups, THE Pre_Deployment_Stack SHALL allow all outbound traffic

### Requirement 13: Output Deployment Information

**User Story:** As a security engineer, I want to receive connection information for deployed assets, so that I can access and test the infrastructure.

#### Acceptance Criteria

1. WHEN deployment completes, THE Orchestrator_Script SHALL output the public IP address for each deployed asset
2. WHEN deployment completes, THE Orchestrator_Script SHALL output the private IP address for each deployed asset
3. WHEN deployment completes, THE Orchestrator_Script SHALL output the Wazuh_Server dashboard URL
4. WHEN deployment completes, THE Orchestrator_Script SHALL output SSH connection commands for Linux assets
5. WHEN deployment completes, THE Orchestrator_Script SHALL output RDP connection commands for Windows assets
6. THE Orchestrator_Script SHALL save deployment information to a file named deployment-info.txt in the current directory

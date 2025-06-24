"""
Shared configuration for IDS automation tools
"""
import os
from dotenv import load_dotenv
from colorama import Fore, Style

# Load environment variables
load_dotenv()

# Confluence configuration
CONFLUENCE_URL = os.getenv('CONFLUENCE_URL')
USERNAME = os.getenv('CONFLUENCE_USERNAME')
API_TOKEN = os.getenv('CONFLUENCE_API_TOKEN')

PAGE_ID = os.getenv('PAGE_ID')  # For create_epic.py

PAGE_TABLE_HEADER = os.getenv('PAGE_TABLE_HEADER')  # For create_epic.py
PRD_PAGE_TABLE_HEADER = os.getenv('PRD_PAGE_TABLE_HEADER')  # For main.py

# Jira configuration
JIRA_URL = os.getenv('CONFLUENCE_URL')
JIRA_PROJECT = os.getenv('JIRA_PROJECT')

# Issue types - different scripts create different types
EPIC_ISSUE_TYPE = "Epic"
TASK_ISSUE_TYPE = "Task"

# Validation function
def validate_epic_config():
    """Validate that all required configuration is present for create_epic.py"""
    required_vars = [
        ('CONFLUENCE_URL', CONFLUENCE_URL),
        ('CONFLUENCE_USERNAME', USERNAME),
        ('CONFLUENCE_API_TOKEN', API_TOKEN),
        ('PAGE_ID', PAGE_ID),
        ('JIRA_PROJECT', JIRA_PROJECT)
    ]
    
    missing_vars = [name for name, value in required_vars if not value]
    
    if missing_vars:
        return False, missing_vars
    
    return True, []

def validate_ticket_config():
    """Validate configuration specific to main.py"""
    required_vars = [
        ('CONFLUENCE_URL', CONFLUENCE_URL),
        ('CONFLUENCE_USERNAME', USERNAME),
        ('CONFLUENCE_API_TOKEN', API_TOKEN),
        ('JIRA_PROJECT', JIRA_PROJECT)
    ]
    
    missing_vars = [name for name, value in required_vars if not value]
    
    if missing_vars:
        return False, missing_vars
    
    return True, []

def handle_config_validation():
    """Common configuration validation with error reporting"""
    is_valid, missing_vars = validate_ticket_config()
    if not is_valid:
        print(f"{Fore.RED}Error: Missing required environment variables:{Style.RESET_ALL}")
        for var in missing_vars:
            print(f"{Fore.YELLOW}- {var}{Style.RESET_ALL}")
        print(f"\n{Fore.YELLOW}Please ensure all required variables are set in your .env file{Style.RESET_ALL}")
        return False
    return True

def handle_help_request(usage_lines):
    """Common help handling"""
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help']:
        print(f"{Fore.CYAN}Usage:{Style.RESET_ALL}")
        for line in usage_lines:
            print(f"  {line}")
        return True
    return False 